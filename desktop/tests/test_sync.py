import importlib
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from idea_echo.app import create_app
from idea_echo.settings import Settings
from idea_echo.auth import create_user
from idea_echo_desktop.cache import Cache


def test_desktop_pulls_and_pushes_real_cloud_api(tmp_path):
    try:sync=importlib.import_module("idea_echo_desktop.sync")
    except ImportError:pytest.fail("Desktop cloud synchronization is not implemented")
    settings=Settings(data_dir=tmp_path/"cloud")
    create_user(settings,"alice","long-correct-password")
    cache=Cache(tmp_path/"desktop")
    with TestClient(create_app(settings)) as cloud:
        token=cloud.post("/v1/auth/login",json={"username":"alice","password":"long-correct-password"}).json()["token"]
        id=str(uuid4())
        body={"mutation_id":str(uuid4()),"expected_version":0,"payload":{"text":"云端点子","recorded_at":"2026-10-22T08:00:00+08:00","attachments":[]}}
        cloud.put(f"/v1/ideas/{id}/record",headers={"Authorization":"Bearer "+token},json=body)
        sync.sync_cloud(cache,"http://testserver",token,cloud)
        assert cache.get(id)["text"]=="云端点子"
        cache.save_reflection(id,"电脑端补充",0)
        sync.sync_cloud(cache,"http://testserver",token,cloud)
        assert cache.pending()==[]
        events=cloud.get("/v1/changes",headers={"Authorization":"Bearer "+token}).json()["events"]
        assert any(e["kind"]=="review" and e["payload"]["reflection"]=="电脑端补充" for e in events)
        peer=Cache(tmp_path/'second-desktop')
        sync.sync_cloud(peer,'http://testserver',token,cloud)
        cache.delete_idea(id)
        sync.sync_cloud(cache,'http://testserver',token,cloud)
        sync.sync_cloud(peer,'http://testserver',token,cloud)
        assert cache.list_ideas('all')==peer.list_ideas('all')==[]
        assert cache.pending()==[]
        assert [e['kind'] for e in cloud.get('/v1/changes',headers={'Authorization':'Bearer '+token}).json()['events']]==['delete']
