import hashlib
import httpx
from .archive import atomic_write
from .cache import Cache


def sync_cloud(cache: Cache,cloud_url: str,token: str,client=None) -> dict:
    headers={"Authorization":"Bearer "+token}
    owns=client is None
    client=client or httpx.Client(base_url=cloud_url,timeout=30,follow_redirects=False)
    sent=0
    try:
        for operation in cache.pending():
            body={k:operation[k] for k in ("mutation_id","expected_version","payload")}
            response=client.put(f"/v1/ideas/{operation['id']}/{operation['kind']}",headers=headers,json=body)
            if response.status_code==409:
                cache.mark_conflict(operation,response.json().get("detail"));continue
            response.raise_for_status()
            cache.acknowledge(operation,response.json());sent+=1
        while True:
            response=client.get("/v1/changes",params={"after":cache.cursor(),"limit":100},headers=headers)
            response.raise_for_status()
            page=response.json()
            cache.apply_events(page["events"])
            if not page["has_more"]:break
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

