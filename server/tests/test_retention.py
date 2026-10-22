from datetime import datetime,timedelta
from pathlib import Path
import importlib
import shutil


def test_rotation_keeps_seven_days_four_weeks_and_unrelated_files(setup_api,tmp_path):
    *_,settings=setup_api
    module=importlib.import_module("idea_echo.backup")
    source=tmp_path/"source.zip";module.create_backup(settings.data_dir,source)
    directory=tmp_path/"backups";directory.mkdir()
    for offset in range(30):
        day=datetime(2026,10,22)-timedelta(days=offset)
        shutil.copyfile(source,directory/f"idea-echo-{day:%Y%m%d}T010000.zip")
    (directory/"unrelated.zip").write_bytes(b"user file")
    assert hasattr(module,"rotate_backups"),"Automatic scoped retention is not implemented"
    module.rotate_backups(directory)
    remaining={p.name for p in directory.glob("idea-echo-*.zip")}
    assert remaining=={f"idea-echo-202610{day:02d}T010000.zip" for day in [4,11,16,17,18,19,20,21,22]}
    assert (directory/"unrelated.zip").read_bytes()==b"user file"
