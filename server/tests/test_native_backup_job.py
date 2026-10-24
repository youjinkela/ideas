from pathlib import Path
import runpy
import sqlite3
import pytest
from test_attachments import register
from idea_echo.backup import restore_backup

RUNNER = Path(__file__).resolve().parents[2] / 'deploy/native/backup-job.py'


def runner():
    assert RUNNER.is_file(), 'Native backup job is not implemented'
    return runpy.run_path(str(RUNNER))['run_once']


def test_native_job_publishes_verified_recoverable_images(setup_api, tmp_path):
    client, auth, _, settings = setup_api
    aid, image = register(client, auth)
    assert client.put(f'/v1/attachments/{aid}/content', headers=auth, content=image).status_code == 200
    result = runner()(settings.data_dir, tmp_path / 'backups')
    assert result['restore_checked'] is True
    archive = tmp_path / 'backups' / result['file']
    assert archive.is_file()
    restored = tmp_path / 'independent-restore'
    restore_backup(archive, restored)
    assert (restored / 'attachments' / aid).read_bytes() == image
    with sqlite3.connect(restored / 'ideas.db') as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0
    assert not list((tmp_path / 'backups').glob('.pending-*'))


def test_failed_backup_keeps_existing_recovery_point(setup_api, tmp_path):
    client, auth, _, settings = setup_api
    aid, image = register(client, auth)
    client.put(f'/v1/attachments/{aid}/content', headers=auth, content=image)
    folder = tmp_path / 'backups'
    folder.mkdir()
    previous = folder / 'keep.zip'
    previous.write_bytes(b'existing backup is untouched')
    (settings.data_dir / 'attachments' / aid).write_bytes(b'damaged')
    with pytest.raises(ValueError):
        runner()(settings.data_dir, folder)
    assert previous.read_bytes() == b'existing backup is untouched'
    assert list(folder.iterdir()) == [previous]
