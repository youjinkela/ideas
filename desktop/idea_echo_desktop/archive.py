from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import threading
from urllib.parse import quote
from uuid import uuid4, UUID

from .vault import Vault,safe_name


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
                original=candidate.read_bytes()
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
            return {"operation_id":operation_id,"path":relative,"content":after.decode("utf-8-sig"),"attachments":[a["path"] for a in attachments],"mode":mode}

    def commit(self,operation_id):
        operation_id=str(UUID(operation_id))
        with self.lock:
            directory=self.operations/operation_id
            op=json.loads((directory/"operation.json").read_text("utf-8"))
            if op["vault"]!=str(self.root):raise ValueError("笔记库已改变，请重新预览")
            target=self.path(op["path"])
            if op["state"]=="complete":return op["receipt"]
            expected=(directory/"result.bin").read_bytes()
            current=target.read_bytes() if target.exists() else b""
            if current.startswith(expected) and current:
                return self._complete(directory,op)
            if op["mode"]=="new" and target.exists():raise ValueError("同名笔记已出现，请重新选择标题")
            if op["mode"]=="append" and (not target.is_file() or checksum(current)!=op["original_hash"]):
                raise ValueError("笔记已被外部修改，原文备份和待写内容已保留，请重新预览")
            for image in op["attachments"]:
                source=self.images/image["source"]
                if not source.exists() or checksum(source.read_bytes())!=image["sha256"]:raise ValueError("本机缺图，未完成归档")
                dest=self.path(image["path"])
                dest.parent.mkdir(exist_ok=True)
                if dest.exists():
                    if checksum(dest.read_bytes())!=image["sha256"]:raise ValueError("附件重名但内容不同")
                else:
                    with dest.open("xb") as out:
                        out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
            if op["mode"]=="new":
                with target.open("xb") as out:
                    out.write(expected);out.flush();os.fsync(out.fileno())
            else:
                # Windows range lock prevents concurrent editors during validation+write.
                with target.open("r+b") as out:
                    if os.name=="nt":
                        import msvcrt
                        msvcrt.locking(out.fileno(),msvcrt.LK_NBLCK,max(len(expected),1))
                    try:
                        if checksum(out.read())!=op["original_hash"]:raise ValueError("笔记刚刚发生变化，请重新预览")
                        out.seek(0);out.write(expected);out.truncate();out.flush();os.fsync(out.fileno())
                    finally:
                        if os.name=="nt":
                            out.seek(0);msvcrt.locking(out.fileno(),msvcrt.LK_UNLCK,max(len(expected),1))
            return self._complete(directory,op)

    def _complete(self,directory,op):
        receipt={"operation_id":op["operation_id"],"path":op["path"],"idea_id":op["idea_id"],"complete":True}
        op.update(state="complete",receipt=receipt)
        atomic_write(directory/"operation.json",json.dumps(op,ensure_ascii=False).encode())
        return receipt
