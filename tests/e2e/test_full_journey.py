import hashlib
import io
from pathlib import Path
import re
from urllib.parse import unquote
from uuid import uuid4
from PIL import Image
from fastapi.testclient import TestClient
from idea_echo.app import create_app
from idea_echo.auth import create_user
from idea_echo.settings import Settings
from idea_echo.backup import create_backup,restore_backup
from idea_echo_desktop.cache import Cache
from idea_echo_desktop.sync import sync_cloud
from idea_echo_desktop.archive import ArchiveManager


def test_full_graphical_capture_review_archive_and_restore(tmp_path):
    settings=Settings(data_dir=tmp_path/"cloud")
    create_user(settings,"owner","long-private-password")
    cache=Cache(tmp_path/"desktop")
    record_id=str(uuid4());aid=str(uuid4())
    image=io.BytesIO();Image.new("RGB",(8,6),"green").save(image,"PNG");data=image.getvalue()
    digest=hashlib.sha256(data).hexdigest()
    with TestClient(create_app(settings)) as client:
        token=client.post("/v1/auth/login",json={"username":"owner","password":"long-private-password"}).json()["token"]
        headers={"Authorization":"Bearer "+token}
        payload={"text":"一两句话加一张图片","recorded_at":"2026-10-22T09:00:00+08:00","attachments":[{"id":aid,"order":0,"mime_type":"image/png","size_bytes":len(data),"sha256":digest}]}
        request={"mutation_id":str(uuid4()),"expected_version":0,"payload":payload}
        assert client.put(f"/v1/ideas/{record_id}/record",headers=headers,json=request).status_code==200
        assert client.put(f"/v1/attachments/{aid}/content",headers=headers,content=data).status_code==200
        sync_cloud(cache,"http://testserver",token,client)
        cache.save_reflection(record_id,"我主动补充的发散",0)
        sync_cloud(cache,"http://testserver",token,client)
    vault=tmp_path/"vault";vault.mkdir();(vault/"灵感").mkdir()
    manager=ArchiveManager(vault,tmp_path/"archive-operations",cache.root/"attachments")
    record=cache.get(record_id)
    op=manager.preview(record,record["reflection"],"new",folder="灵感",title="图文点子")
    receipt=manager.commit(op["operation_id"])
    assert manager.commit(op["operation_id"])==receipt
    manager.acknowledge(op["operation_id"])
    note=vault/receipt["path"];body=note.read_text("utf-8")
    assert "我主动补充的发散" in body
    for link in re.findall(r"!\[[^\]]*\]\(([^)]+)\)",body):
        attachment=note.parent/unquote(link)
        assert attachment.resolve().is_relative_to(vault.resolve())
        assert hashlib.sha256(attachment.read_bytes()).hexdigest()==digest
    (vault/"已有.md").write_text("原有内容\n",encoding="utf-8")
    append=manager.preview(record,"这次追加","append",target="已有.md")
    manager.commit(append["operation_id"]);manager.commit(append["operation_id"])
    assert (vault/"已有.md").read_text("utf-8").count("这次追加")==1
    archive=tmp_path/"backup.zip"
    create_backup(settings.data_dir,archive)
    restore_backup(archive,tmp_path/"restored")
    assert (tmp_path/"restored"/"attachments"/aid).read_bytes()==data
