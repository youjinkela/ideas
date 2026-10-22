from datetime import datetime
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import threading
from urllib.parse import quote
from uuid import uuid4, UUID

from .vault import Vault,safe_name,safe_open


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path,data: bytes):
    temp=path.with_name(path.name+"."+uuid4().hex+".tmp")
    try:
        with temp.open("xb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def write_durable(out,data):
    out.write(data);out.flush();os.fsync(out.fileno())


def publish_new(path,data):
    # Both paths are inside a pinned directory. Windows rename refuses replacement.
    temp=path.with_name('idea-echo-stage-'+uuid4().hex+'.tmp')
    try:
        with temp.open('xb') as out:write_durable(out,data)
        os.rename(temp,path)
    finally:temp.unlink(missing_ok=True)


def read_safe(path):
    with safe_open(path) as source:return source.read()


class ArchiveManager(Vault):
    def __init__(self,root: Path,operations: Path,images: Path):
        super().__init__(root)
        self.operations=Path(operations)
        self.operations.mkdir(parents=True,exist_ok=True)
        self.images=Path(images)
        self.lock=threading.RLock()

    def preview(self,idea,reflection,mode,folder="",title=None,target=None):
        if mode not in ("new","append"):
            raise ValueError("请选择新建或追加")
        with self.lock:
            for stored in sorted(self.operations.glob('*/operation.json'),key=lambda p:p.stat().st_mtime,reverse=True):
                previous=json.loads(stored.read_text('utf-8'))
                if previous.get('vault')==str(self.root) and previous.get('idea_id')==idea['id'] and previous.get('state') in ('writing','complete') and not previous.get('confirmed'):
                    return self._preview_result(stored.parent,previous,resumed=True)
            if mode=="new":
                directory=self.path(folder)
                if not directory.is_dir():raise ValueError("文件夹不存在")
                filename=safe_name(title or idea.get("text","").splitlines()[0] if idea.get("text") else title or "图片点子")
                candidate=directory/filename
                suffix=1
                while candidate.exists():
                    candidate=directory/f"{Path(filename).stem}-{suffix}.md";suffix+=1
                relative=candidate.relative_to(self.root).as_posix()
                original=b""
            else:
                if not target:raise ValueError("请选择已有笔记")
                candidate=self.path(target)
                if candidate.suffix.lower()!=".md" or not candidate.is_file():raise ValueError("请选择已有 Markdown 笔记")
                relative=candidate.relative_to(self.root).as_posix()
                with self.guard(relative):original=read_safe(candidate)
                try:original.decode("utf-8-sig")
                except UnicodeError:raise ValueError("目标笔记不是 UTF-8，请先转换编码")
            attachments=[]
            for image in sorted(idea.get("attachments",[]),key=lambda a:a.get("order",0)):
                aid=str(UUID(image["id"]))
                source=self.images/aid
                ext={"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}.get(image["mime_type"])
                if not ext or not source.is_file() or checksum(source.read_bytes())!=image["sha256"]:
                    raise ValueError("图片尚未同步完整，请同步后再归档")
                image_rel=(Path(relative).parent/"_attachments"/f"{aid}.{ext}").as_posix()
                self.path(image_rel)
                attachments.append({"source":aid,"path":image_rel,"sha256":image["sha256"]})
            operation_id=str(uuid4())
            title_text=(title or "点子").replace("\n"," ").replace("\r"," ")
            text=(f"# {title_text}\n\n## 原始点子\n{idea.get('text','')}\n\n")
            if attachments:
                text+="\n".join(f"![点子图片 {i+1}]({quote('_attachments/'+Path(a['path']).name,safe='/')})" for i,a in enumerate(attachments))+"\n\n"
            text+=f"## 我的发散\n{reflection}\n\n---\n记录时间：{idea.get('recorded_at','')}\n回顾时间：{datetime.now().astimezone().isoformat()}\n来源：点子回声 / {idea['id']}\n"
            text+=f"\n<!-- idea-echo-operation:{operation_id} -->\n"
            newline="\r\n" if b"\r\n" in original else "\n"
            body=text.replace("\n",newline).encode("utf-8")
            after=original+(newline*2).encode()+body if mode=="append" else body
            op={"operation_id":operation_id,"idea_id":idea["id"],"mode":mode,"path":relative,"vault":str(self.root),"original_hash":checksum(original),"expected_hash":checksum(after),"attachments":attachments,"state":"prepared"}
            directory=self.operations/operation_id
            directory.mkdir()
            atomic_write(directory/"original.bin",original)
            atomic_write(directory/"result.bin",after)
            atomic_write(directory/"operation.json",json.dumps(op,ensure_ascii=False).encode())
            return self._preview_result(directory,op)

    def _preview_result(self,directory,op,resumed=False):
        return {"operation_id":op['operation_id'],"path":op['path'],"content":(directory/'result.bin').read_bytes().decode('utf-8-sig'),"attachments":[a['path'] for a in op['attachments']],"mode":op['mode'],"resumed":resumed}

    def acknowledge(self,operation_id):
        directory=self.operations/str(UUID(operation_id))
        op=json.loads((directory/'operation.json').read_text('utf-8'))
        if op['vault']!=str(self.root) or op['state']!='complete':raise ValueError('归档尚未完成')
        op['confirmed']=True
        atomic_write(directory/'operation.json',json.dumps(op,ensure_ascii=False).encode())

    def commit(self,operation_id):
        operation_id=str(UUID(operation_id))
        with self.lock,ExitStack() as pins:
            directory=self.operations/operation_id
            op=json.loads((directory/"operation.json").read_text("utf-8"))
            if op["vault"]!=str(self.root):raise ValueError("笔记库已改变，请重新预览")
            # Pin parent identity before the final path check or any vault write.
            target=pins.enter_context(self.guard(op['path']))
            image_paths={image['path']:pins.enter_context(self.guard(image['path'],create_parents=True)) for image in op['attachments']}
            if op["state"]=="complete":return op["receipt"]
            expected=(directory/"result.bin").read_bytes()
            current=read_safe(target) if target.exists() else b""
            if current.startswith(expected) and current:
                return self._complete(directory,op)
            if op["mode"]=="new" and target.exists():raise ValueError("同名笔记已出现，请重新选择标题")
            recovering=op['state']=='writing' and current==expected[:len(current)] and len(current)>=(directory/'original.bin').stat().st_size and len(current)<=len(expected)
            if op["mode"]=="append" and (not target.is_file() or checksum(current)!=op["original_hash"] and not recovering):
                raise ValueError("笔记已被外部修改，原文备份和待写内容已保留，请重新预览")
            for image in op["attachments"]:
                source=self.images/image["source"]
                if not source.exists() or checksum(source.read_bytes())!=image["sha256"]:raise ValueError("本机缺图，未完成归档")
                dest=image_paths[image['path']]
                if dest.exists():
                    if checksum(read_safe(dest))!=image["sha256"]:raise ValueError("附件重名但内容不同")
                else:
                    publish_new(dest,source.read_bytes())
            if op["mode"]=="new":
                publish_new(target,expected)
            else:
                # No-share-write, no-share-delete, OPEN_REPARSE_POINT file handle.
                with safe_open(target,write=True) as out:
                    now=out.read();stat=os.fstat(out.fileno());identity=[stat.st_dev,stat.st_ino]
                    if checksum(now)!=op['original_hash'] and not (recovering and now==current and op.get('file_identity')==identity):raise ValueError('笔记刚刚发生变化，请重新预览')
                    op.update(state='writing',file_identity=identity)
                    atomic_write(directory/'operation.json',json.dumps(op,ensure_ascii=False).encode())
                    offset=(directory/'original.bin').stat().st_size
                    out.seek(offset);write_durable(out,expected[offset:]);out.truncate();out.flush();os.fsync(out.fileno())
            return self._complete(directory,op)

    def _complete(self,directory,op):
        receipt={"operation_id":op["operation_id"],"path":op["path"],"idea_id":op["idea_id"],"complete":True}
        op.update(state="complete",receipt=receipt)
        atomic_write(directory/"operation.json",json.dumps(op,ensure_ascii=False).encode())
        return receipt
