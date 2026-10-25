import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]


def test_health_is_private_data_free(tmp_path):
    try:
        app = importlib.import_module("idea_echo.app")
        settings = importlib.import_module("idea_echo.settings")
    except ImportError:
        pytest.fail("Health application has not been implemented")
    with TestClient(app.create_app(settings.Settings(data_dir=tmp_path))) as client:
        assert client.get("/health").json() == {"status": "ok", "schema_version": 1, "sync_deletion": True}


def test_contract_fixtures():
    schema_path = ROOT / "contracts/idea.schema.json"
    assert schema_path.exists(), "The shared idea schema is not implemented"
    validator = Draft202012Validator(json.loads(schema_path.read_text("utf-8")), format_checker=FormatChecker())
    for name in ("text", "image-only", "conflict", "partial-upload"):
        record = json.loads((ROOT / f"contracts/fixtures/{name}.json").read_text("utf-8"))
        validator.validate(record)
    base = json.loads((ROOT / "contracts/fixtures/text.json").read_text("utf-8"))
    for mutation in ({"text": "", "attachments": []}, {"id": "bad-id"}):
        with pytest.raises(ValidationError):
            validator.validate(base | mutation)

