import base64
import ctypes
from ctypes import wintypes
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from .archive import atomic_write


def secret_transform(data: bytes,decrypt=False) -> bytes:
    if os.name!="nt":raise ValueError("此版本的凭证保存使用 Windows DPAPI")
    class Blob(ctypes.Structure):
        _fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]
    source=ctypes.create_string_buffer(data)
    incoming=Blob(len(data),ctypes.cast(source,ctypes.POINTER(ctypes.c_ubyte)))
    outgoing=Blob()
    crypto=ctypes.WinDLL("crypt32",use_last_error=True)
    method=crypto.CryptUnprotectData if decrypt else crypto.CryptProtectData
    method.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    method.restype=wintypes.BOOL
    if not method(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(outgoing)):
        raise ValueError("无法读取本机安全凭证，请重新登录或配置")
    try:return ctypes.string_at(outgoing.data,outgoing.size)
    finally:
        kernel=ctypes.WinDLL("kernel32")
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree(outgoing.data)


def validate_cloud_url(url):
    parsed=urlsplit(url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("","/"):
        raise ValueError("请填写服务器根地址，例如 https://ideas.example.com")
    if parsed.scheme=="http":
        try:private=ipaddress.ip_address(parsed.hostname).is_private
        except ValueError:private=parsed.hostname=="localhost"
        if not private:raise ValueError("公网服务器必须使用 HTTPS")
    elif parsed.scheme!="https":raise ValueError("服务器地址需要 HTTPS")
    return url.rstrip("/")


class DesktopSettings:
    def __init__(self,root: Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.file=self.root/"settings.json"
        self.values=json.loads(self.file.read_text("utf-8")) if self.file.exists() else {}

    def get(self,key,default=""):
        return self.values.get(key,default)

    def secret(self,key):
        encoded=self.values.get(key,"")
        return secret_transform(base64.b64decode(encoded),True).decode() if encoded else ""

    def update(self,**values):
        updated=dict(self.values)
        for key,value in values.items():
            updated[key]=base64.b64encode(secret_transform(value.encode())).decode() if key in ("cloud_token","ai_key") and value else value
        atomic_write(self.file,json.dumps(updated,ensure_ascii=False).encode())
        self.values=updated

    def public(self):
        return {k:self.get(k) for k in ("cloud_url","account_id","vault","ai_url","ai_model")} | {"cloud_connected":bool(self.get("cloud_token")),"ai_configured":bool(self.get("ai_key"))}

