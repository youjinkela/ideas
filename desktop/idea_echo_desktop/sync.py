import hashlib
import httpx
from .archive import atomic_write
from .cache import Cache


def sync_cloud(cache: Cache,cloud_url: str,token: str,client=None) -> dict:
    headers={"Authorization":"Bearer "+token}
    owns=client is None
    client=client or httpx.Client(base_url=cloud_url,timeout=30,follow_redirects=False)
    sent=0
    delete_supported=None
    def pull():
        for _ in range(10000):
            params={"after":cache.cursor(),"limit":100}
            if cache.generation():params["generation"]=cache.generation()
            response=client.get("/v1/changes",params=params,headers=headers)
            if response.status_code==409 and response.json().get("detail",{}).get("cursor_reset"):
                cache.set_generation(response.json()["detail"]["generation"],reset=True);continue
            response.raise_for_status();page=response.json()
            if page.get("generation"):cache.set_generation(page["generation"])
            cache.apply_events(page["events"])
            if not page["has_more"]:return
        raise ValueError("同步页数过多，请稍后重试")
    try:
        pull()
        for operation in cache.pending():
            if not cache.operation_current(operation,begin=True):continue
            body={k:operation[k] for k in ("mutation_id","expected_version","payload")}
            response=client.put(f"/v1/ideas/{operation['id']}/{operation['kind']}",headers=headers,json=body)
            if response.status_code==404 and operation['kind']=='delete':
                if delete_supported is None:
                    health=client.get('/health');health.raise_for_status();delete_supported=health.json().get('sync_deletion') is True
                if not delete_supported:response.raise_for_status()
                cache.acknowledge(operation,{'accepted_version':0});sent+=1;continue
            if response.status_code==410 and operation['kind']=='record':
                cache.remote_delete(operation['id']);continue
            if response.status_code==409:
                cache.mark_conflict(operation,response.json().get("detail"));continue
            response.raise_for_status()
            if operation['kind']=='record':
                try:
                    for image in operation['payload']['attachments']:
                        if not cache.operation_current(operation):break
                        meta=client.get(f"/v1/attachments/{image['id']}",headers=headers);meta.raise_for_status()
                        if meta.json().get('content_ready') and meta.json().get('sha256')==image['sha256']:continue
                        path=cache.root/'attachments'/image['id']
                        if path.stat().st_size!=image['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=image['sha256']:
                            raise ValueError('本机图片校验失败，点子仍保留，请重新添加图片')
                        with path.open('rb') as stream:
                            uploaded=client.put(f"/v1/attachments/{image['id']}/content",headers=headers,content=iter(lambda:stream.read(1024*1024),b''))
                        uploaded.raise_for_status()
                except (httpx.HTTPError,OSError,ValueError):
                    if cache.operation_current(operation):raise
                if not cache.operation_current(operation):continue
            cache.acknowledge(operation,response.json());sent+=1
        pull()
        image_dir=cache.root/"attachments"
        image_dir.mkdir(exist_ok=True)
        waiting=0
        for idea in cache.list_ideas():
            for image in idea.get("attachments",[]):
                path=image_dir/image["id"]
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==image["sha256"]:continue
                result=client.get(f"/v1/attachments/{image['id']}/content",headers=headers)
                if result.status_code==409:waiting+=1;continue
                result.raise_for_status()
                if len(result.content)>20*1024*1024 or len(result.content)!=image["size_bytes"] or hashlib.sha256(result.content).hexdigest()!=image["sha256"]:
                    raise ValueError("图片校验失败，本地编辑已保留，请重试")
                atomic_write(path,result.content)
        return {"sent":sent,"waiting_images":waiting,"pending":len(cache.pending())}
    finally:
        if owns:client.close()

