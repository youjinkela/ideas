import hashlib
import io
from uuid import uuid4
from PIL import Image
from test_records import mutation


def image_bytes(format="PNG"):
    out=io.BytesIO()
    Image.new("RGB",(3,2),"red").save(out,format)
    return out.getvalue()


def register(c,a,data=None):
    data=data or image_bytes()
    aid=str(uuid4())
    meta={"id":aid,"order":0,"mime_type":"image/png","size_bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
    response=c.put(f"/v1/ideas/{uuid4()}/record",headers=a,json=mutation("",attachments=[meta]))
    assert response.status_code==200
    return aid,data


def test_partial_upload_never_marks_content_ready(setup_api):
    c,a,_,_=setup_api
    aid,data=register(c,a)
    url=f"/v1/attachments/{aid}/content"
    assert c.put(url,headers=a,content=data[:10]).status_code==422
    assert c.get(url,headers=a).status_code==409
    assert c.put(url,headers=a,content=data).status_code==200
    assert c.get(url,headers=a).content==data


def test_same_id_retry_is_idempotent(setup_api):
    c,a,_,_=setup_api
    aid,data=register(c,a)
    url=f"/v1/attachments/{aid}/content"
    assert c.put(url,headers=a,content=data).json()==c.put(url,headers=a,content=data).json()
    events=c.get("/v1/changes",headers=a).json()["events"]
    assert len([e for e in events if e["kind"]=="attachment"])==1


def test_wrong_hash_or_mime_rejected(setup_api):
    c,a,_,_=setup_api
    aid,data=register(c,a)
    assert c.put(f"/v1/attachments/{aid}/content",headers=a,content=b"x"*len(data)).status_code==422
    aid,jpg=register(c,a,image_bytes("JPEG"))
    assert c.put(f"/v1/attachments/{aid}/content",headers=a,content=jpg).status_code==422


def test_cross_owner_cannot_download(setup_api):
    c,a,b,_=setup_api
    aid,data=register(c,a)
    url=f"/v1/attachments/{aid}/content"
    c.put(url,headers=a,content=data)
    assert c.get(url,headers=b).status_code==404
    assert c.get(url).status_code==401


def test_size_limit_is_enforced_before_accepting_metadata(setup_api):
    c,a,_,s=setup_api
    meta={"id":str(uuid4()),"order":0,"mime_type":"image/png","size_bytes":s.max_image_bytes+1,"sha256":"a"*64}
    assert c.put(f"/v1/ideas/{uuid4()}/record",headers=a,json=mutation("",attachments=[meta])).status_code==413


def test_server_readiness_is_checked_not_old_client_upload_history(setup_api):
    c,a,_,_=setup_api
    aid,data=register(c,a)
    response=c.get(f"/v1/attachments/{aid}",headers=a)
    assert response.status_code==200
    assert response.json()["content_ready"] is False
    c.put(f"/v1/attachments/{aid}/content",headers=a,content=data)
    assert c.get(f"/v1/attachments/{aid}",headers=a).json()["content_ready"] is True

