import importlib
import pytest
from fastapi.testclient import TestClient
from test_cache import raw_event

ORIGIN="http://127.0.0.1:47821"


def test_settings_network_failure_is_safe_json_and_preserves_config(tmp_path,monkeypatch):
    import httpx
    app=desktop(tmp_path)
    class FailedCloud:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def post(self,*args,**kwargs):raise httpx.ConnectError('TLS interrupted sensitive-test-password')
    with TestClient(app,base_url=ORIGIN,raise_server_exceptions=False) as client:
        h=session(client)
        monkeypatch.setattr(httpx,'Client',lambda **kwargs:FailedCloud())
        response=client.post('/local/settings',headers=h,json={'cloud_url':'https://ideas.example.com','username':'owner','password':'sensitive-test-password'})
        assert response.status_code==502
        assert '无法连接云端' in response.json()['detail']
        assert 'sensitive-test-password' not in response.text
        assert not app.state.settings.get('cloud_url')


def desktop(tmp_path):
    try:module=importlib.import_module("idea_echo_desktop.app")
    except ImportError:pytest.fail("Desktop review service is not implemented")
    return module.create_desktop_app(tmp_path,ORIGIN,"test-bootstrap")


def session(client):
    response=client.post("/local/session",headers={"Origin":ORIGIN},json={"bootstrap":"test-bootstrap"})
    assert response.status_code==200
    return {"Origin":ORIGIN,"X-CSRF-Token":response.json()["csrf"]}


def test_session_origin_and_csrf_guard_filesystem_actions(tmp_path):
    app=desktop(tmp_path)
    with TestClient(app,base_url=ORIGIN) as client:
        assert client.get("/local/ideas").status_code==401
        h=session(client)
        assert client.post("/local/status",json={"id":raw_event()["entity_id"],"value":"reviewed"}).status_code==403
        assert client.post("/local/status",headers=h|{"Origin":"https://evil.example"},json={}).status_code==403
        assert client.get("/local/ideas",headers={"Host":"evil.example"}).status_code==403


def test_user_reflection_is_durable(tmp_path):
    app=desktop(tmp_path);app.state.cache.apply_events([raw_event()])
    with TestClient(app,base_url=ORIGIN) as client:
        h=session(client)
        assert len(client.get("/local/ideas").json()["ideas"])==1
        response=client.post("/local/reflection",headers=h,json={"id":raw_event()["entity_id"],"reflection":"我来编辑"})
        assert response.status_code==200
        assert app.state.cache.get(raw_event()["entity_id"])["reflection"]=="我来编辑"


def test_local_delete_requires_session_and_csrf_and_removes_from_all_views(tmp_path):
    app=desktop(tmp_path);app.state.cache.apply_events([raw_event()])
    body={"id":raw_event()["entity_id"]}
    with TestClient(app,base_url=ORIGIN) as client:
        assert client.post("/local/delete",json=body).status_code==401
        h=session(client)
        assert client.post("/local/delete",json=body).status_code==403
        assert client.post("/local/delete",headers=h|{"Origin":"https://evil.example"},json=body).status_code==403
        assert len(client.get("/local/ideas?view=all").json()["ideas"])==1
        assert client.post("/local/delete",headers=h,json=body).status_code==200
        assert client.get("/local/ideas?view=all").json()["ideas"]==[]
        assert client.post("/local/delete",headers=h,json=body).status_code==200
        response=client.post('/local/reflection',headers=h,json=body|{'reflection':'删除后仍打开的旧页面'})
        assert response.status_code==410
        assert response.json()['detail']['deleted_id']==body['id']


def test_settings_do_not_disclose_secrets(tmp_path):
    app=desktop(tmp_path)
    with TestClient(app,base_url=ORIGIN) as client:
        session(client)
        response=client.get("/local/settings")
        assert response.status_code==200
        assert "token" not in response.json() and "ai_key" not in response.json()


def test_javascript_mime_does_not_depend_on_windows_registry(tmp_path):
    with TestClient(desktop(tmp_path),base_url=ORIGIN) as client:
        response=client.get("/assets/app.js")
        assert response.status_code==200
        assert response.headers["content-type"].split(";")[0] in ("text/javascript","application/javascript")

