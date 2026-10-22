import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from .db import connect
from .records import dumps
from .settings import Settings

STORAGE_LOCK = threading.RLock()  # Also used by backup/garbage collection.
IMAGE_LOCK = threading.Lock()
FORMATS = {"PNG":"image/png", "JPEG":"image/jpeg", "WEBP":"image/webp"}


def metadata(settings: Settings, owner: str, aid: str) -> dict:
    with connect(settings) as con:
        row=con.execute("SELECT * FROM attachments WHERE id=? AND owner=?",(aid,owner)).fetchone()
    if not row:
        raise HTTPException(404,"未找到附件")
    return dict(row) | {"descriptor":json.loads(row["metadata"])}


def attachment_path(settings: Settings, aid: str) -> Path:
    return settings.data_dir / "attachments" / aid


def store_attachment(settings: Settings, owner_id: str, attachment_id: str, stream) -> dict:
    meta=metadata(settings,owner_id,attachment_id)["descriptor"]
    folder=settings.data_dir/"attachments"
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=folder,delete=False) as out:
            temp=Path(out.name)
            digest=hashlib.sha256()
            size=0
            while chunk:=stream.read(1024*1024):
                size+=len(chunk)
                if size>settings.max_image_bytes or size>meta["size_bytes"]:
                    raise HTTPException(413,"图片超过登记大小")
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if size!=meta["size_bytes"] or digest.hexdigest()!=meta["sha256"]:
            raise HTTPException(422,"图片尚未传完整或校验失败，可重试")
        try:
            with IMAGE_LOCK, Image.open(temp) as image:
                if image.width*image.height>settings.max_pixels or FORMATS.get(image.format)!=meta["mime_type"]:
                    raise HTTPException(422,"图片格式或分辨率不符合配置")
                image.verify()
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
            raise HTTPException(422,"不是有效的受支持图片")
        receipt={"id":attachment_id,"sha256":meta["sha256"],"content_ready":True}
        with STORAGE_LOCK,connect(settings) as con:
            con.execute("BEGIN IMMEDIATE")
            current=con.execute("SELECT ready FROM attachments WHERE id=? AND owner=?",(attachment_id,owner_id)).fetchone()
            if not current:
                raise HTTPException(404,"附件引用已失效，请重新同步")
            target=attachment_path(settings,attachment_id)
            if not current["ready"] or not target.exists():
                os.replace(temp,target)
                con.execute("UPDATE attachments SET ready=1 WHERE id=?",(attachment_id,))
                con.execute("INSERT INTO events(owner,kind,entity_id,payload) VALUES(?,?,?,?)",(owner_id,"attachment",attachment_id,dumps(receipt)))
        return receipt
    finally:
        if temp and temp.exists():
            temp.unlink()


def open_attachment(settings: Settings, owner_id: str, attachment_id: str) -> Path:
    meta=metadata(settings,owner_id,attachment_id)
    path=attachment_path(settings,attachment_id)
    if not meta["ready"] or not path.is_file():
        raise HTTPException(409,"图片仍待上传")
    return path


def thumbnail(settings: Settings, owner: str, aid: str) -> bytes:
    path=open_attachment(settings,owner,aid)
    with IMAGE_LOCK,Image.open(path) as image:
        image.thumbnail((480,480))
        out=io.BytesIO()
        image.convert("RGB").save(out,"JPEG",quality=80)
        return out.getvalue()


def collect_unreferenced(settings: Settings,before: float | None=None) -> int:
    cutoff=before if before is not None else time.time()-7*86400
    with STORAGE_LOCK,connect(settings) as con:
        con.execute("BEGIN IMMEDIATE")
        rows=con.execute("SELECT id FROM attachments WHERE created<? AND NOT EXISTS(SELECT 1 FROM attachment_refs r WHERE r.attachment_id=attachments.id)",(cutoff,)).fetchall()
        for row in rows:
            attachment_path(settings,row["id"]).unlink(missing_ok=True)
            con.execute("DELETE FROM attachments WHERE id=?",(row["id"],))
        return len(rows)

