import importlib
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from idea_echo.app import create_app
from idea_echo.settings import Settings
from idea_echo.auth import create_user
from idea_echo_desktop.cache import Cache


def test_desktop_created_raw_record_precedes_its_review_and_status(tmp_path):
    from idea_echo_desktop.sync import sync_cloud
    settings=Settings(data_dir=tmp_path/'cloud')
    create_user(settings,'creator','long-correct-password')
    cache=Cache(tmp_path/'desktop');id=str(uuid4())
    cache.create_idea(id,'电脑上添加的原始点子',[])
    cache.save_reflection(id,'稍后补充的发散',0)
    cache.set_status(id,'reviewed')
    with TestClient(create_app(settings)) as cloud:
        token=cloud.post('/v1/auth/login',json={'username':'creator','password':'long-correct-password'}).json()['token']
        result=sync_cloud(cache,'http://testserver',token,cloud)
        assert result['sent']==3 and cache.pending()==[]
        assert cache.get(id)['raw_version']==1
        events=cloud.get('/v1/changes',headers={'Authorization':'Bearer '+token}).json()['events']
        assert [event['kind'] for event in events]==['record','review','status']


def test_capture_image_failure_retains_stable_queue_and_full_graph_retries(tmp_path):
    import hashlib
    import httpx
    from test_capture import png_bytes
    from idea_echo_desktop.sync import sync_cloud
    settings=Settings(data_dir=tmp_path/'cloud');create_user(settings,'creator','long-correct-password')
    cache=Cache(tmp_path/'desktop');id,aid=str(uuid4()),str(uuid4());data=png_bytes()
    stage=cache.root/'capture-staging'/id;stage.mkdir(parents=True);(stage/aid).write_bytes(data)
    meta={'id':aid,'order':0,'mime_type':'image/png','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    cache.create_idea(id,'图文上传不能只确认文字',[meta]);cache.save_reflection(id,'发散',0)
    queued=cache.pending()[0]
    with TestClient(create_app(settings)) as cloud:
        token=cloud.post('/v1/auth/login',json={'username':'creator','password':'long-correct-password'}).json()['token']
        class Flaky:
            fail=True
            def get(self,*args,**kwargs):return cloud.get(*args,**kwargs)
            def put(self,url,**kwargs):
                if self.fail and url.endswith('/content'):return httpx.Response(503,request=httpx.Request('PUT','http://testserver'+url))
                return cloud.put(url,**kwargs)
        flaky=Flaky()
        with pytest.raises(httpx.HTTPStatusError):sync_cloud(cache,'http://testserver',token,flaky)
        assert cache.pending()[0]['mutation_id']==queued['mutation_id']
        assert cache.get(id)['raw_version']==0
        flaky.fail=False
        sync_cloud(cache,'http://testserver',token,flaky)
        assert cache.pending()==[] and cache.get(id)['raw_version']==1
        auth={'Authorization':'Bearer '+token}
        assert cloud.get(f'/v1/attachments/{aid}/content',headers=auth).content==data
        events=cloud.get('/v1/changes',headers=auth).json()['events']
        assert [e['kind'] for e in events]==['record','attachment','review']


def test_deletion_during_record_upload_does_not_resurrect_local_capture(tmp_path):
    from idea_echo_desktop.sync import sync_cloud
    settings=Settings(data_dir=tmp_path/'cloud');create_user(settings,'creator','long-correct-password')
    cache=Cache(tmp_path/'desktop');id=str(uuid4());cache.create_idea(id,'上传时被删除',[])
    with TestClient(create_app(settings)) as cloud:
        token=cloud.post('/v1/auth/login',json={'username':'creator','password':'long-correct-password'}).json()['token']
        class DeleteAfterPut:
            def get(self,*args,**kwargs):return cloud.get(*args,**kwargs)
            def put(self,url,**kwargs):
                result=cloud.put(url,**kwargs)
                if url.endswith('/record'):cache.delete_idea(id)
                return result
        sync_cloud(cache,'http://testserver',token,DeleteAfterPut())
        assert cache.list_ideas('all')==[]
        assert [op['kind'] for op in cache.pending()]==['delete']
        sync_cloud(cache,'http://testserver',token,cloud)
        assert cache.pending()==[]


def test_missing_remote_delete_reconciles_a_late_original_upload(tmp_path):
    import httpx
    from idea_echo_desktop.sync import sync_cloud
    settings=Settings(data_dir=tmp_path/'cloud');create_user(settings,'creator','long-correct-password')
    cache=Cache(tmp_path/'desktop');id=str(uuid4());cache.create_idea(id,'迟到的上传仍必须删除',[])
    original=cache.pending()[0]
    with TestClient(create_app(settings)) as cloud:
        token=cloud.post('/v1/auth/login',json={'username':'creator','password':'long-correct-password'}).json()['token']
        class FailedBeforeCreate:
            def get(self,*args,**kwargs):return cloud.get(*args,**kwargs)
            def put(self,*args,**kwargs):raise httpx.ConnectError('synthetic failed write')
        with pytest.raises(httpx.ConnectError):sync_cloud(cache,'http://testserver',token,FailedBeforeCreate())
        cache.delete_idea(id)
        sync_cloud(cache,'http://testserver',token,cloud)
        assert cache.pending()==[] and cache.list_ideas('all')==[]
        auth={'Authorization':'Bearer '+token}
        assert cloud.put(f'/v1/ideas/{id}/record',headers=auth,json={k:original[k] for k in ('mutation_id','expected_version','payload')}).status_code==200
        cache.apply_events(cloud.get('/v1/changes',headers=auth).json()['events'])
        assert cache.list_ideas('all')==[]
        assert [op['kind'] for op in cache.pending()]==['delete']
        sync_cloud(cache,'http://testserver',token,cloud)
        assert cache.pending()==[]
        assert [e['kind'] for e in cloud.get('/v1/changes',headers=auth).json()['events']]==['delete']


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
