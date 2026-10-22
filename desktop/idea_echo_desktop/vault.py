from pathlib import Path, PurePosixPath
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
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
        self.identity=(self.root.stat().st_dev,self.root.stat().st_ino)

    @contextmanager
    def guard(self,relative,create_parents=False):
        """Pin all Windows directory identities without FILE_SHARE_DELETE."""
        if os.name!='nt':raise ValueError("安全归档当前只支持 Windows")
        parts=PurePosixPath(relative.replace('\\','/')).parts
        if ':' in relative or relative.startswith(('/','\\')) or any(p=='..' or p.startswith('.') for p in parts):raise ValueError("不安全的归档路径")
        handles=[]
        try:
            ancestors=list(reversed(self.root.parents))+[self.root]
            for directory in ancestors:
                handles.append(_win_handle(directory,directory=True))
            if (self.root.stat().st_dev,self.root.stat().st_ino)!=self.identity:raise ValueError("笔记库身份已变化")
            directory=self.root
            for part in parts[:-1]:
                directory=directory/part
                if create_parents:directory.mkdir(exist_ok=True)
                handles.append(_win_handle(directory,directory=True))
            yield self.path(relative)
        finally:
            for handle in reversed(handles):_kernel().CloseHandle(handle)

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


def _kernel():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    return kernel


def _win_handle(path,directory=False,write=False):
    kernel=_kernel()
    handle=kernel.CreateFileW(str(path),0x80000000|(0x40000000 if write else 0),3 if directory else 1,None,3,0x02200000,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    info=(wintypes.DWORD*2)()
    if not kernel.GetFileInformationByHandleEx(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or info[0]&0x400 or directory and not info[0]&0x10:
        kernel.CloseHandle(handle);raise ValueError("不允许通过链接、重解析点或已改变的目录归档")
    return handle


@contextmanager
def safe_open(path,write=False):
    import msvcrt
    handle=_win_handle(path,write=write)
    try:fd=msvcrt.open_osfhandle(handle,os.O_BINARY|(os.O_RDWR if write else os.O_RDONLY))
    except BaseException:_kernel().CloseHandle(handle);raise
    with os.fdopen(fd,'r+b' if write else 'rb') as file:yield file


