import os
import pytest
from idea_echo_desktop.settings import DesktopSettings


@pytest.mark.skipif(os.name!="nt",reason="DPAPI is Windows-specific")
def test_credentials_are_encrypted_on_disk_and_roundtrip(tmp_path):
    settings=DesktopSettings(tmp_path)
    settings.update(cloud_token="temporary-test-cloud-token",ai_key="temporary-test-ai-key")
    raw=(tmp_path/"settings.json").read_text("utf-8")
    assert "temporary-test-cloud-token" not in raw
    assert "temporary-test-ai-key" not in raw
    reopened=DesktopSettings(tmp_path)
    assert reopened.secret("cloud_token")=="temporary-test-cloud-token"
    assert reopened.secret("ai_key")=="temporary-test-ai-key"
