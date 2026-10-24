"""Real pythonw startup must serve the review page without a console."""
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows login startup')
def test_windowless_startup_serves_review_page(tmp_path):
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
    process = subprocess.Popen(
        [str(pythonw), '-m', 'idea_echo_desktop.app', '--data-dir', str(tmp_path / 'data'),
         '--port', str(port), '--no-browser'],
        cwd=tmp_path, creationflags=subprocess.DETACHED_PROCESS,
    )
    try:
        with httpx.Client(trust_env=False, timeout=0.3) as client:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                assert process.poll() is None, 'Windowless review service exited during startup'
                try:
                    response = client.get(f'http://127.0.0.1:{port}/')
                    if response.status_code == 200:
                        assert '点子' in response.text
                        assert client.get(f'http://127.0.0.1:{port}/local/settings').status_code == 401
                        return
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            pytest.fail('Windowless review service never became ready')
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
