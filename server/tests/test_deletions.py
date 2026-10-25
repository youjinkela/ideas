import hashlib
import io
from uuid import uuid4
from PIL import Image
from idea_echo.db import connect
from test_records import mutation


def test_delete_purges_source_and_unshared_image_and_replay_cannot_revive(setup_api):
    c,a,b,settings=setup_api
    image=io.BytesIO();Image.new('RGB',(4,4),'green').save(image,format='PNG');data=image.getvalue()
    aid=str(uuid4());id=str(uuid4());base=f'/v1/ideas/{id}'
    descriptor={'id':aid,'order':0,'mime_type':'image/png','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    original=mutation(attachments=[descriptor])
    assert c.put(base+'/record',headers=a,json=original).status_code==200
    assert c.put(f'/v1/attachments/{aid}/content',headers=a,content=data).status_code==200
    request={'mutation_id':str(uuid4()),'expected_version':1,'payload':{}}
    assert c.put(base+'/delete',headers=b,json=request).status_code==404
    assert c.put(base+'/delete',headers=a,json=request).status_code==200
    assert c.put(base+'/delete',headers=a,json=request).status_code==200
    assert c.put(base+'/record',headers=a,json=original).status_code==410
    assert c.put(base+'/record',headers=a,json=mutation('离线旧副本',1)).status_code==410
    assert c.get(f'/v1/attachments/{aid}/content',headers=a).status_code==404
    assert not (settings.data_dir/'attachments'/aid).exists()
    events=c.get('/v1/changes',headers=a).json()['events']
    assert len(events)==1 and events[0]['kind']=='delete'
    assert events[0]['payload']=={'id':id,'attachment_ids':[aid]}
    with connect(settings) as con:
        assert con.execute('SELECT COUNT(*) FROM entities WHERE id=?',(id,)).fetchone()[0]==0


def test_delete_preserves_image_shared_by_another_idea(setup_api):
    c,a,_,settings=setup_api
    image=io.BytesIO();Image.new('RGB',(3,3),'blue').save(image,format='PNG');data=image.getvalue()
    aid=str(uuid4());first,second=str(uuid4()),str(uuid4())
    descriptor={'id':aid,'order':0,'mime_type':'image/png','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    for id in (first,second):assert c.put(f'/v1/ideas/{id}/record',headers=a,json=mutation(attachments=[descriptor])).status_code==200
    assert c.put(f'/v1/attachments/{aid}/content',headers=a,content=data).status_code==200
    assert c.put(f'/v1/ideas/{first}/delete',headers=a,json={'mutation_id':str(uuid4()),'expected_version':1,'payload':{}}).status_code==200
    assert c.get(f'/v1/attachments/{aid}/content',headers=a).content==data
    assert any(e['entity_id']==second for e in c.get('/v1/changes',headers=a).json()['events'])


def test_failed_image_cleanup_is_retried_without_reviving_deleted_record(setup_api,monkeypatch):
    from pathlib import Path
    c,a,_,settings=setup_api
    from test_attachments import register
    aid,data=register(c,a)
    assert c.put(f'/v1/attachments/{aid}/content',headers=a,content=data).status_code==200
    id=next(e['entity_id'] for e in c.get('/v1/changes',headers=a).json()['events'] if e['kind']=='record')
    request={'mutation_id':str(uuid4()),'expected_version':1,'payload':{}}
    original_unlink=Path.unlink
    def fail_unlink(path,*args,**kwargs):
        if path.name==aid:raise OSError('synthetic file busy')
        return original_unlink(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',fail_unlink)
        import pytest
        with pytest.raises(OSError):c.put(f'/v1/ideas/{id}/delete',headers=a,json=request)
        assert c.get('/v1/changes',headers=a).status_code==200
    assert c.get('/v1/changes',headers=a).status_code==200
    assert not (settings.data_dir/'attachments'/aid).exists()
    assert c.put(f'/v1/ideas/{id}/record',headers=a,json=mutation()).status_code==410


def test_delete_also_removes_images_replaced_by_later_edits(setup_api):
    c,a,_,settings=setup_api
    id=str(uuid4());aids=[]
    for version,color in enumerate(('red','blue')):
        image=io.BytesIO();Image.new('RGB',(4,4),color).save(image,format='PNG');data=image.getvalue()
        aid=str(uuid4());aids.append(aid)
        descriptor={'id':aid,'order':0,'mime_type':'image/png','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        assert c.put(f'/v1/ideas/{id}/record',headers=a,json=mutation(version=version,attachments=[descriptor])).status_code==200
        assert c.put(f'/v1/attachments/{aid}/content',headers=a,content=data).status_code==200
    assert c.put(f'/v1/ideas/{id}/delete',headers=a,json={'mutation_id':str(uuid4()),'expected_version':2,'payload':{}}).status_code==200
    assert all(not (settings.data_dir/'attachments'/aid).exists() for aid in aids)
    assert all(c.get(f'/v1/attachments/{aid}/content',headers=a).status_code==404 for aid in aids)
