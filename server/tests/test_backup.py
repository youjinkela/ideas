import importlib
import zipfile
import pytest
from test_attachments import register


def backup_module():
    try:return importlib.import_module("idea_echo.backup")
    except ImportError:pytest.fail("Verified backup and restore are not implemented")


def test_backup_restores_database_and_images(setup_api,tmp_path):
    c,a,_,settings=setup_api
    aid,data=register(c,a)
    assert c.put(f"/v1/attachments/{aid}/content",headers=a,content=data).status_code==200
    module=backup_module();archive=tmp_path/"backup.zip"
    manifest=module.create_backup(settings.data_dir,archive)
    assert "ideas.db" in manifest["files"]
    assert module.verify_backup(archive)["valid"] is True
    target=tmp_path/"restored"
    module.restore_backup(archive,target)
    assert (target/"attachments"/aid).read_bytes()==data
    assert (target/"ideas.db").is_file()


def test_restore_refuses_nonempty_destination(setup_api,tmp_path):
    *_,settings=setup_api
    module=backup_module();archive=tmp_path/"backup.zip"
    module.create_backup(settings.data_dir,archive)
    target=tmp_path/"existing";target.mkdir();(target/"keep.txt").write_text("keep")
    with pytest.raises(ValueError):module.restore_backup(archive,target)
    assert (target/"keep.txt").read_text()=="keep"


def test_corruption_and_traversal_detected(setup_api,tmp_path):
    *_,settings=setup_api
    module=backup_module();archive=tmp_path/"backup.zip"
    module.create_backup(settings.data_dir,archive)
    with zipfile.ZipFile(archive,"a") as out:out.writestr("../outside.txt",b"bad")
    with pytest.raises(ValueError):module.verify_backup(archive)


def test_backup_rejects_corrupted_confirmed_image(setup_api,tmp_path):
    c,a,_,settings=setup_api
    aid,data=register(c,a)
    c.put(f"/v1/attachments/{aid}/content",headers=a,content=data)
    (settings.data_dir/"attachments"/aid).write_bytes(b"corrupt image")
    with pytest.raises(ValueError):backup_module().create_backup(settings.data_dir,tmp_path/"bad-backup.zip")
