import hashlib
import json
import time
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, AwareDatetime, ConfigDict, model_validator
from .db import connect
from .settings import Settings


class AttachmentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    order: int = Field(ge=0)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=100000)
    recorded_at: AwareDatetime
    attachments: list[AttachmentDescriptor] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self):
        if not self.text.strip() and not self.attachments:
            raise ValueError("请填写文字或添加图片")
        if len({a.order for a in self.attachments}) != len(self.attachments) or len({a.id for a in self.attachments}) != len(self.attachments):
            raise ValueError("图片ID和顺序不得重复")
        return self


class ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reflection: str = Field(max_length=200000)


class StatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Literal["pending", "later", "reviewed", "archived"]


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mutation_id: UUID
    expected_version: int = Field(ge=0)
    payload: dict


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def apply_mutation(settings: Settings, owner_id: str, kind: str, entity_id: str, mutation: Mutation) -> dict:
    model = {"record":RecordPayload,"review":ReviewPayload,"status":StatusPayload}[kind]
    try:
        payload = model.model_validate(mutation.payload).model_dump(mode="json")
    except ValueError:
        raise HTTPException(422, "记录格式不正确，内容或图片顺序无效")
    if kind == "record":
        images = payload["attachments"]
        if len(images)>settings.max_images or sum(a["size_bytes"] for a in images)>settings.max_total_bytes or any(a["size_bytes"]>settings.max_image_bytes for a in images):
            raise HTTPException(413, "图片超出配置容量，请减小图片或分开保存")
    fingerprint = hashlib.sha256(dumps([kind,entity_id,mutation.model_dump(mode="json")]).encode()).hexdigest()
    with connect(settings) as con:
        con.execute("BEGIN IMMEDIATE")
        prior = con.execute("SELECT * FROM mutations WHERE owner=? AND id=?", (owner_id,str(mutation.mutation_id))).fetchone()
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise HTTPException(409, "重试标识已用于不同请求")
            return json.loads(prior["ack"])
        foreign = con.execute("SELECT owner FROM entities WHERE id=? AND kind='record' AND owner<>?", (entity_id,owner_id)).fetchone()
        if foreign:
            raise HTTPException(404, "未找到记录")
        existing = con.execute("SELECT * FROM entities WHERE owner=? AND id=? AND kind=?", (owner_id,entity_id,kind)).fetchone()
        version = existing["version"] if existing else 0
        if version != mutation.expected_version:
            raise HTTPException(409, {"current":json.loads(existing["payload"]) if existing else None, "version":version})
        if kind != "record" and not con.execute("SELECT 1 FROM entities WHERE owner=? AND id=? AND kind='record'", (owner_id,entity_id)).fetchone():
            raise HTTPException(404, "点子尚未同步")
        if kind == "record":
            con.execute("DELETE FROM attachment_refs WHERE owner=? AND idea_id=?", (owner_id,entity_id))
            for image in payload["attachments"]:
                aid = image["id"]
                # Order belongs to the idea manifest, not immutable image content.
                metadata = dumps({k:v for k,v in image.items() if k!="order"})
                old = con.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()
                if old and (old["owner"]!=owner_id or old["metadata"]!=metadata):
                    raise HTTPException(409, "附件ID已用于其他内容")
                con.execute("INSERT OR IGNORE INTO attachments(id,owner,metadata,created) VALUES(?,?,?,?)", (aid,owner_id,metadata,time.time()))
                con.execute("INSERT INTO attachment_refs VALUES(?,?,?)", (owner_id,entity_id,aid))
        payload |= {"id":entity_id, {"record":"raw_version","review":"review_version","status":"status_version"}[kind]:version+1}
        encoded = dumps(payload)
        con.execute("INSERT OR REPLACE INTO entities VALUES(?,?,?,?,?)", (owner_id,entity_id,kind,version+1,encoded))
        con.execute("INSERT INTO events(owner,kind,entity_id,payload) VALUES(?,?,?,?)", (owner_id,kind,entity_id,encoded))
        ack = {"mutation_id":str(mutation.mutation_id), "accepted_version":version+1}
        con.execute("INSERT INTO mutations VALUES(?,?,?,?)", (owner_id,str(mutation.mutation_id),fingerprint,dumps(ack)))
        return ack


def read_changes(settings: Settings, owner_id: str, after: int, limit: int) -> dict:
    with connect(settings) as con:
        rows = con.execute("SELECT * FROM events WHERE owner=? AND seq>? ORDER BY seq LIMIT ?", (owner_id,after,limit+1)).fetchall()
    events = [{"seq":r["seq"], "kind":r["kind"], "entity_id":r["entity_id"], "payload":json.loads(r["payload"])} for r in rows[:limit]]
    return {"events":events, "next_cursor":events[-1]["seq"] if events else after, "has_more":len(rows)>limit}

