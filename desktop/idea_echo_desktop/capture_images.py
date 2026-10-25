"""Account-local, immutable image staging for browser captures."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
from uuid import UUID

from PIL import Image,UnidentifiedImageError

MAX_IMAGE_BYTES=20*1024*1024
MAX_RECORD_BYTES=200*1024*1024
MAX_IMAGES=20
FORMATS={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}


class ImageLimitError(ValueError):pass
class CaptureDeleted(ValueError):pass


def _id(value):return str(UUID(str(value)))


def _folder(parent,name):
    parent=Path(parent);path=parent/name
    if path.is_symlink() or path.is_junction() or path.resolve().parent!=parent.resolve():
        raise ValueError('图片目录不可用')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def _file(path):
    if path.is_symlink() or path.is_junction() or not path.is_file():raise ValueError('图片尚未保存完整，请重新添加')
    return path


def image_descriptor(path,image_id):
    path=_file(Path(path));size=path.stat().st_size
    if size>MAX_IMAGE_BYTES:raise ImageLimitError('单张图片不能超过20MiB')
    try:
        with Image.open(path) as image:
            if image.width*image.height>100000000:raise ImageLimitError('图片分辨率过大')
            mime=FORMATS.get(image.format)
            if not mime:raise ValueError('仅支持JPEG、PNG和WebP图片')
            image.verify()
    except ImageLimitError:raise
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as error:
        raise ValueError('图片不是有效的JPEG、PNG或WebP文件') from None
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return {'id':_id(image_id),'mime_type':mime,'size_bytes':size,'sha256':digest.hexdigest()}


async def stage_image(root,idea_id,image_id,chunks,*,lock,deleted):
    idea_id=_id(idea_id);image_id=_id(image_id)
    base=_folder(root,'capture-staging')
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=base,prefix='.upload-',delete=False) as stream:
            temp=Path(stream.name);size=0
            async for chunk in chunks:
                size+=len(chunk)
                if size>MAX_IMAGE_BYTES:raise ImageLimitError('单张图片不能超过20MiB')
                stream.write(chunk)
            stream.flush();os.fsync(stream.fileno())
        descriptor=image_descriptor(temp,image_id)
        with lock:
            if deleted():raise CaptureDeleted('这条点子已删除；当前内容可另存为新点子')
            directory=_folder(base,idea_id);target=directory/image_id
            try:os.link(temp,target)
            except FileExistsError:
                if image_descriptor(target,image_id)!=descriptor:raise ValueError('图片编号已用于不同内容')
        return descriptor
    finally:
        if temp:temp.unlink(missing_ok=True)


def publish_images(root,idea_id,descriptors):
    if not descriptors:return []
    source=_folder(_folder(root,'capture-staging'),_id(idea_id))
    destination=_folder(root,'attachments')
    checked=[]
    for descriptor in descriptors:
        aid=_id(descriptor['id']);actual=image_descriptor(source/aid,aid)
        if actual!={key:descriptor[key] for key in actual}:raise ValueError('图片校验未通过，请重新添加')
        target=destination/aid
        if target.exists() and image_descriptor(target,aid)!=actual:raise ValueError('图片编号已用于不同内容')
        checked.append((source/aid,target,actual))
    created=[]
    try:
        for image,target,actual in checked:
            try:os.link(image,target);created.append(actual['id'])
            except FileExistsError:
                if image_descriptor(target,actual['id'])!=actual:raise ValueError('图片编号已用于不同内容')
    except BaseException:
        for aid in created:
            try:(destination/aid).unlink(missing_ok=True)
            except OSError:pass
        raise
    return created


def clear_staged(root,idea_id):
    base=Path(root)/'capture-staging';directory=base/_id(idea_id)
    if not directory.exists():return
    if base.is_symlink() or base.is_junction() or directory.is_symlink() or directory.is_junction() or directory.resolve().parent!=base.resolve():
        raise ValueError('图片目录不可用')
    for path in directory.iterdir():
        try:valid=_id(path.name)==path.name
        except ValueError:valid=False
        if valid and path.is_file() and not path.is_symlink() and path.resolve().parent==directory.resolve():path.unlink()
    try:directory.rmdir()
    except OSError:pass


def prune_staged(root,before_timestamp=None):
    base=Path(root)/'capture-staging'
    if not base.exists() or base.is_symlink() or base.is_junction():return
    cutoff=before_timestamp if before_timestamp is not None else time.time()-7*86400
    for path in base.iterdir():
        if path.is_symlink() or path.is_junction() or path.stat().st_mtime>=cutoff:continue
        try:
            if path.is_dir() and _id(path.name)==path.name:clear_staged(root,path.name)
            elif path.is_file() and path.name.startswith('.upload-') and path.resolve().parent==base.resolve():path.unlink()
        except (ValueError,OSError):continue
