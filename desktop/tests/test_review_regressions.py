import hashlib
import os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from test_archive import manager,idea
from test_cache import raw_event
from idea_echo_desktop.cache import Cache
from idea_echo_desktop.sync import sync_cloud
from idea_echo.app import create_app
from idea_echo.settings import Settings
from idea_echo.auth import create_user
from idea_echo.backup import create_backup,restore_backup


def test_stale_editor_never_overwrites_remote_or_other_window(tmp_path):
    cache=Cache(tmp_path);event=raw_event();id=event['entity_id'];cache.apply_events([event])
    cache.apply_events([{'seq':2,'kind':'review','entity_id':id,'payload':{'reflection':'较新内容','review_version':1}}])
    with pytest.raises(ValueError):cache.save_reflection(id,'旧页面',0)
    assert cache.get(id)['reflection']=='较新内容'
    cache.save_reflection(id,'窗口一',1,expected_edit_revision=cache.get(id).get('edit_revision',0))
    with pytest.raises(ValueError):cache.save_reflection(id,'窗口二',1,expected_edit_revision=0)
    assert cache.get(id)['reflection']=='窗口一'


class BrokenWriter:
    def __init__(self,file):self.file=file
    def __enter__(self):return self
    def __exit__(self,*args):return self.file.__exit__(*args)
    def __getattr__(self,name):return getattr(self.file,name)
    def write(self,data):
        self.file.write(data[:max(1,len(data)//2)]);self.file.flush()
        raise OSError('simulated disk interruption')


@pytest.mark.parametrize('mode',['new','append','image'])
def test_partial_write_retries_without_losing_original(tmp_path,monkeypatch,mode):
    m,v,images=manager(tmp_path);record=idea()
    if mode=='append':(v/'note.md').write_bytes(b'ORIGINAL\r\n')
    if mode=='image':
        aid=str(uuid4());data=b'image bytes'*32;(images/aid).write_bytes(data)
        record['attachments']=[{'id':aid,'mime_type':'image/png','sha256':hashlib.sha256(data).hexdigest()}]
    op=m.preview(record,'仅追加一次',mode='append' if mode=='append' else 'new',target='note.md' if mode=='append' else None,title='note')
    import idea_echo_desktop.archive as archive
    original_write=archive.write_durable;broken=False
    def interrupted(file,data):
        nonlocal broken
        if not broken:
            broken=True;file.write(data[:max(1,len(data)//2)]);file.flush();raise OSError('simulated disk interruption')
        return original_write(file,data)
    with monkeypatch.context() as patch:
        patch.setattr(archive,'write_durable',interrupted)
        with pytest.raises(OSError):m.commit(op['operation_id'])
    receipt=m.commit(op['operation_id'])
    body=(v/receipt['path']).read_text('utf-8')
    assert body.count('仅追加一次')==1
    if mode=='append':assert (v/receipt['path']).read_bytes().startswith(b'ORIGINAL\r\n')
    if mode=='image':assert (v/'_attachments'/f'{aid}.png').read_bytes()==data


@pytest.mark.skipif(os.name!='nt',reason='Windows directory identity test')
def test_directory_cannot_be_replaced_by_junction_during_commit(tmp_path,monkeypatch):
    import _winapi
    m,v,_=manager(tmp_path);directory=v/'folder';directory.mkdir();outside=tmp_path/'outside';outside.mkdir()
    op=m.preview(idea(),'safe',mode='new',folder='folder',title='note')
    original=m.path;attempted=False
    def race(relative):
        nonlocal attempted
        path=original(relative)
        if relative=='folder/note.md' and not attempted:
            attempted=True
            try:directory.rename(v/'moved')
            except OSError:return path
            _winapi.CreateJunction(str(outside),str(directory))
        return path
    monkeypatch.setattr(m,'path',race)
    try:m.commit(op['operation_id'])
    except (ValueError,OSError):pass
    assert not (outside/'note.md').exists()


def test_lost_response_new_preview_recovers_same_operation(tmp_path):
    m,v,_=manager(tmp_path);record=idea();(v/'note.md').write_text('原文',encoding='utf-8')
    op=m.preview(record,'一次',mode='append',target='note.md');m.commit(op['operation_id'])
    reopened,_,_=manager(tmp_path)
    resumed=reopened.preview(record,'一次',mode='append',target='note.md')
    assert resumed['operation_id']==op['operation_id']
    reopened.commit(resumed['operation_id'])
    assert (v/'note.md').read_text('utf-8').count('## 我的发散')==1


def test_backup_restore_generation_rewinds_cursor_without_losing_drafts(tmp_path):
    settings=Settings(data_dir=tmp_path/'cloud');create_user(settings,'alice','long-correct-password')
    cache=Cache(tmp_path/'desktop');backup=tmp_path/'backup.zip'
    def login(client):return client.post('/v1/auth/login',json={'username':'alice','password':'long-correct-password'}).json()['token']
    def record(client,token,id):
        client.put(f'/v1/ideas/{id}/record',headers={'Authorization':'Bearer '+token},json={'mutation_id':str(uuid4()),'expected_version':0,'payload':{'text':'idea','recorded_at':'2026-10-22T08:00:00Z','attachments':[]}})
    first=str(uuid4())
    with TestClient(create_app(settings)) as cloud:
        token=login(cloud);record(cloud,token,first);create_backup(settings.data_dir,backup)
        record(cloud,token,str(uuid4()));sync_cloud(cache,'http://testserver',token,cloud)
    restore_backup(backup,tmp_path/'restored');new=str(uuid4())
    cache.save_reflection(first,'保留本机待传草稿',0)
    with TestClient(create_app(Settings(data_dir=tmp_path/'restored'))) as cloud:
        token=login(cloud);record(cloud,token,new);sync_cloud(cache,'http://testserver',token,cloud)
    assert cache.get(new)['text']=='idea'
    assert cache.get(first)['reflection']=='保留本机待传草稿'
