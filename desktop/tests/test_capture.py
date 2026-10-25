from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from idea_echo_desktop.app import create_desktop_app
from idea_echo_desktop.cache import Cache
from idea_echo_desktop.settings import DesktopSettings
from test_app import ORIGIN,session

OWNER='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


def png_bytes(color='green'):
    import io
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(3,2),color).save(stream,format='PNG')
    return stream.getvalue()


def capture_app(root):
    DesktopSettings(root).update(account_id=OWNER)
    return create_desktop_app(root,ORIGIN,'test-bootstrap')


def test_capture_is_durable_and_retries_do_not_duplicate_or_overwrite(tmp_path):
    cache=Cache(tmp_path);id=str(uuid4())
    first=cache.create_idea(id,'  电脑新点子\n保留多行  ',[])
    queued=cache.pending()[0]
    reopened=Cache(tmp_path)
    assert reopened.create_idea(id,'  电脑新点子\n保留多行  ',[])==first
    assert reopened.get(id)['text']=='电脑新点子\n保留多行'
    assert first['status']=='pending'
    assert datetime.fromisoformat(first['recorded_at']).utcoffset() is not None
    assert reopened.pending()==[queued]
    assert queued['kind']=='record' and queued['expected_version']==0
    with pytest.raises(ValueError):reopened.create_idea(id,'不同内容',[])
    assert len(reopened.list_ideas('all'))==1
    with pytest.raises(ValueError):reopened.create_idea(str(uuid4()),' \n ',[])


def test_never_uploaded_capture_can_be_deleted_without_cloud_work(tmp_path):
    cache=Cache(tmp_path);id=str(uuid4())
    cache.create_idea(id,'还没有上传',[])
    cache.delete_idea(id)
    assert cache.list_ideas('all')==[] and cache.pending()==[]
    with pytest.raises(ValueError):cache.create_idea(id,'还没有上传',[])


def test_capture_api_is_scoped_and_requires_session_origin_and_csrf(tmp_path):
    app=capture_app(tmp_path)
    body={'id':str(uuid4()),'scope':OWNER,'text':'网页原始点子','attachments':[]}
    with TestClient(app,base_url=ORIGIN) as client:
        assert client.post('/local/ideas',json=body).status_code==401
        headers=session(client)
        assert client.post('/local/ideas',json=body).status_code==403
        assert client.post('/local/ideas',headers=headers|{'Origin':'https://foreign.invalid'},json=body).status_code==403
        assert client.post('/local/ideas',headers=headers,json=body|{'scope':'different-account'}).status_code==409
        assert client.get('/local/capture/config').json()['ready'] is True
        response=client.post('/local/ideas',headers=headers,json=body)
        assert response.status_code==200
        assert response.json()['idea']['text']=='网页原始点子'
        assert client.post('/local/ideas',headers=headers,json=body).json()['idea']['id']==body['id']
        assert len(client.get('/local/ideas?view=all').json()['ideas'])==1


def test_capture_without_configured_account_guides_setup_without_hidden_local_records(tmp_path):
    app=create_desktop_app(tmp_path,ORIGIN,'test-bootstrap')
    with TestClient(app,base_url=ORIGIN) as client:
        headers=session(client)
        assert client.get('/local/capture/config').json()['ready'] is False
        response=client.post('/local/ideas',headers=headers,json={'id':str(uuid4()),'scope':'local','text':'本机想法','attachments':[]})
        assert response.status_code==409
        assert app.state.cache.list_ideas('all')==[]


def test_image_only_capture_validates_bytes_and_is_immediately_readable(tmp_path):
    app=capture_app(tmp_path);id,aid=str(uuid4()),str(uuid4());data=png_bytes()
    with TestClient(app,base_url=ORIGIN) as client:
        headers=session(client);image_headers=headers|{'X-Capture-Scope':OWNER}
        url=f'/local/capture/{id}/images/{aid}'
        assert client.put(url,headers=image_headers|{'X-Capture-Scope':'foreign'},content=data).status_code==409
        response=client.put(url,headers=image_headers,content=data)
        assert response.status_code==200
        assert client.put(url,headers=image_headers,content=data).json()==response.json()
        body={'id':id,'scope':OWNER,'text':'','attachments':[response.json()|{'order':0}]}
        saved=client.post('/local/ideas',headers=headers,json=body)
        assert saved.status_code==200
        assert client.get(f'/local/images/{aid}').content==data
        assert client.get('/local/ideas').json()['ideas'][0]['attachments'][0]['local_ready'] is True
        assert client.get(f'/local/capture/{id}/receipt',headers={'X-Capture-Scope':OWNER}).json()['idea']['id']==id
        assert client.post('/local/ideas',headers=headers,json=body).json()['idea']['id']==id
        assert len(app.state.cache.list_ideas('all'))==1
        client.post('/local/delete',headers=headers,json={'id':id})
        assert not (app.state.cache.root/'attachments'/aid).exists()
        assert client.put(url,headers=image_headers,content=data).status_code==410


def test_invalid_or_oversized_images_do_not_publish_and_bad_descriptors_do_not_save(tmp_path):
    app=capture_app(tmp_path);id,aid=str(uuid4()),str(uuid4())
    with TestClient(app,base_url=ORIGIN) as client:
        headers=session(client);image_headers=headers|{'X-Capture-Scope':OWNER};url=f'/local/capture/{id}/images/{aid}'
        assert client.put(url,headers=image_headers,content=b'not an image').status_code==400
        assert client.put(url,headers=image_headers,content=b'x'*(21*1024*1024)).status_code==413
        meta=client.put(url,headers=image_headers,content=png_bytes()).json()
        body={'id':id,'scope':OWNER,'text':'文字仍然由用户保留','attachments':[meta|{'order':0,'sha256':'a'*64}]}
        assert client.post('/local/ideas',headers=headers,json=body).status_code==400
        assert app.state.cache.list_ideas('all')==[]
        assert not list((app.state.cache.root/'capture-staging').glob('.upload-*'))


def test_publish_never_overwrites_another_ideas_image(tmp_path):
    app=capture_app(tmp_path);first,second,aid=str(uuid4()),str(uuid4()),str(uuid4())
    with TestClient(app,base_url=ORIGIN) as client:
        headers=session(client);image_headers=headers|{'X-Capture-Scope':OWNER}
        original=png_bytes('red')
        meta=client.put(f'/local/capture/{first}/images/{aid}',headers=image_headers,content=original).json()
        assert client.post('/local/ideas',headers=headers,json={'id':first,'scope':OWNER,'text':'第一条','attachments':[meta|{'order':0}]}).status_code==200
        other=client.put(f'/local/capture/{second}/images/{aid}',headers=image_headers,content=png_bytes('blue')).json()
        assert client.post('/local/ideas',headers=headers,json={'id':second,'scope':OWNER,'text':'第二条','attachments':[other|{'order':0}]}).status_code==400
        assert client.get(f'/local/images/{aid}').content==original


@pytest.mark.parametrize('failure',['link','database'])
def test_failed_capture_rolls_back_published_images_and_keeps_staged_sources(tmp_path,monkeypatch,failure):
    import hashlib
    import os
    cache=Cache(tmp_path);id=str(uuid4());directory=cache.root/'capture-staging'/id;directory.mkdir(parents=True)
    images=[]
    for color in ('green','blue'):
        aid=str(uuid4());data=png_bytes(color);(directory/aid).write_bytes(data)
        images.append({'id':aid,'order':len(images),'mime_type':'image/png','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    if failure=='link':
        original=os.link;calls=0
        def broken_link(source,target):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('synthetic disk failure')
            return original(source,target)
        monkeypatch.setattr(os,'link',broken_link)
    else:monkeypatch.setattr(cache,'_store',lambda *args:(_ for _ in ()).throw(OSError('synthetic database failure')))
    with pytest.raises(OSError):cache.create_idea(id,'失败后可以重试',images)
    assert cache.list_ideas('all')==[] and cache.pending()==[]
    assert all((directory/image['id']).is_file() for image in images)
    assert not list((cache.root/'attachments').iterdir())
