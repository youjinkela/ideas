import hashlib
import importlib
from pathlib import Path
from uuid import uuid4
import pytest


def manager(tmp_path):
    try:
        module=importlib.import_module("idea_echo_desktop.archive")
    except ImportError:
        pytest.fail("Obsidian archiving is not implemented")
    vault=tmp_path/"vault"
    vault.mkdir(exist_ok=True)
    images=tmp_path/"images"
    images.mkdir(exist_ok=True)
    return module.ArchiveManager(vault,tmp_path/"operations",images),vault,images


def idea():
    return {"id":str(uuid4()),"text":"一句点子💡","recorded_at":"2026-10-22T10:00:00+08:00","attachments":[]}


def test_new_and_append_preserve_existing_text_and_no_duplicates(tmp_path):
    m,v,_=manager(tmp_path)
    (v/"学习").mkdir()
    first=m.preview(idea(),"我的发散",mode="new",folder="学习",title="我的点子💡")
    receipt=m.commit(first["operation_id"])
    target=v/receipt["path"]
    assert "我的发散" in target.read_text("utf-8")
    before=target.read_bytes()
    second=m.preview(idea(),"再想一层",mode="append",target=receipt["path"])
    assert m.commit(second["operation_id"])==m.commit(second["operation_id"])
    assert target.read_bytes().startswith(before)
    assert target.read_text("utf-8").count("再想一层")==1


@pytest.mark.parametrize("name",["CON","AUX.txt","点子 .","emoji💡","a/b","相同标题"])
def test_safe_unique_filenames(tmp_path,name):
    m,v,_=manager(tmp_path)
    a=m.commit(m.preview(idea(),"",mode="new",title=name)["operation_id"])
    b=m.commit(m.preview(idea(),"",mode="new",title=name)["operation_id"])
    assert a["path"]!=b["path"]
    assert (v/a["path"]).is_file()
    assert (v/b["path"]).is_file()


def test_image_is_local_relative_attachment(tmp_path):
    m,v,images=manager(tmp_path)
    record=idea()
    aid=str(uuid4());data=b"test image bytes"
    (images/aid).write_bytes(data)
    record["attachments"]=[{"id":aid,"mime_type":"image/png","sha256":hashlib.sha256(data).hexdigest()}]
    receipt=m.commit(m.preview(record,"",mode="new",title="含图")["operation_id"])
    body=(v/receipt["path"]).read_text("utf-8")
    assert f"_attachments/{aid}.png" in body
    assert (v/"_attachments"/f"{aid}.png").read_bytes()==data
    assert "http" not in body


def test_external_edit_and_missing_image_do_not_fake_success(tmp_path):
    m,v,_=manager(tmp_path)
    (v/"note.md").write_text("用户原文",encoding="utf-8")
    op=m.preview(idea(),"新增",mode="append",target="note.md")
    (v/"note.md").write_text("外部更新",encoding="utf-8")
    with pytest.raises(ValueError):m.commit(op["operation_id"])
    assert (v/"note.md").read_text("utf-8")=="外部更新"
    record=idea();record["attachments"]=[{"id":str(uuid4()),"sha256":"a"*64,"mime_type":"image/png"}]
    with pytest.raises(ValueError):m.preview(record,"",mode="new",title="缺图")

