from pathlib import Path, PurePosixPath
import re
import unicodedata


def safe_name(title: str) -> str:
    name=unicodedata.normalize("NFC",title)
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",name).strip().rstrip(" .")[:80].rstrip(" .")
    if name.lower().endswith(".md"):
        name=name[:-3].rstrip(" .")
    if not name:
        name="未命名点子"
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]",name.split(".")[0],re.I):
        name="_"+name
    return name+".md"


class Vault:
    def __init__(self,root: Path):
        self.root=Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("请选择笔记库目录")

    def path(self,relative: str) -> Path:
        relative=relative.replace("\\","/")
        parts=PurePosixPath(relative).parts
        if ":" in relative or relative.startswith("/") or any(p in ("..",) or p.startswith(".") for p in parts):
            raise ValueError("目标必须位于授权笔记库的普通目录内")
        current=self.root
        if not current.is_dir():
            raise ValueError("笔记库已移动，请重新选择")
        for part in parts:
            current=current/part
            if current.is_symlink() or current.is_junction():
                raise ValueError("不允许通过链接或目录联接写入")
        if not current.resolve().is_relative_to(self.root):
            raise ValueError("目标超出笔记库")
        return current

    def folders(self):
        result=[""]
        for path in self.root.rglob("*"):
            rel=path.relative_to(self.root).as_posix()
            try:
                if self.path(rel).is_dir():result.append(rel)
            except ValueError:
                continue
        return sorted(result)

    def search(self,query):
        result=[]
        for path in self.root.rglob("*.md"):
            rel=path.relative_to(self.root).as_posix()
            try:
                if query.casefold() in rel.casefold() and self.path(rel).is_file():result.append(rel)
            except ValueError:
                continue
            if len(result)>=200:break
        return sorted(result)

