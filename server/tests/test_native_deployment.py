from pathlib import Path
import configparser
import io
import subprocess
import tarfile
import pytest

ROOT=Path(__file__).resolve().parents[2]


def test_release_archive_preserves_unix_line_endings():
    if not (ROOT/'.git').exists():pytest.skip('Source checkout packaging test only')
    archive=subprocess.run(['git','-c','core.autocrlf=true','archive','--worktree-attributes','--format=tar','HEAD','deploy/native'],cwd=ROOT,capture_output=True,check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as package:
        for name in ('deploy/native/install.sh','deploy/native/idea-echo.service'):
            data=package.extractfile(name).read()
            assert b'\r\n' not in data, f'{name}: release archive must use LF, not CRLF'


def test_native_service_is_private_unprivileged_and_durable():
    path=ROOT/'deploy/native/idea-echo.service'
    assert path.is_file(), 'Native systemd service is not implemented'
    config=configparser.ConfigParser(interpolation=None,strict=False);config.read(path,encoding='utf-8')
    service=config['Service']
    assert service['User']=='idea-echo'
    assert '--host 127.0.0.1' in service['ExecStart']
    assert '--port 8000' in service['ExecStart']
    assert service['StateDirectory']=='idea-echo'
    assert service['ProtectSystem']=='strict'
    assert service['NoNewPrivileges']=='true'
    assert service['UMask']=='0077'


def test_native_install_keeps_secrets_out_and_refuses_unit_overwrite():
    path=ROOT/'deploy/native/install.sh'
    assert path.is_file(), 'Native installer is not implemented'
    script=path.read_text('utf-8')
    assert 'set -euo pipefail' in script
    assert 'cmp -s' in script
    assert '--no-deps' in script
    assert 'init-user' not in script  # password creation is a separate interactive step
    assert '0.0.0.0' not in script
    assert 'docker ' not in script
