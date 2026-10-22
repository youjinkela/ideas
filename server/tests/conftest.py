import importlib
import pytest
from fastapi.testclient import TestClient
from idea_echo.app import create_app
from idea_echo.settings import Settings


@pytest.fixture
def setup_api(tmp_path):
    settings = Settings(data_dir=tmp_path)
    try:
        auth = importlib.import_module("idea_echo.auth")
    except ImportError:
        pytest.fail("Account initialization is not implemented")
    auth.create_user(settings, "alice", "correct-password-alice")
    auth.create_user(settings, "bob", "correct-password-bob")
    with TestClient(create_app(settings)) as client:
        a = client.post("/v1/auth/login", json={"username":"alice", "password":"correct-password-alice"})
        b = client.post("/v1/auth/login", json={"username":"bob", "password":"correct-password-bob"})
        assert a.status_code == b.status_code == 200
        yield client, {"Authorization": "Bearer " + a.json()["token"]}, {"Authorization": "Bearer " + b.json()["token"]}, settings

