import argparse
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import re
from pathlib import Path,PurePosixPath
import sqlite3
import tempfile
from uuid import UUID,uuid4
import zipfile
from .attachments import storage_guard
from .settings import Settings


def file_hash(path: Path):
    digest=hashlib.sha256()
    with path.open("rb") as source:
        while data:=source.read(1024*1024):digest.update(data)
    return digest.hexdigest()


def create_backup(data_dir: Path,destination: Path) -> dict:
    data_dir=Path(data_dir);destination=Path(destination)
    if not (data_dir/"ideas.db").is_file():raise ValueError("没有可备份的数据库")
    if destination.exists():raise ValueError("备份文件已存在，不覆盖")
    destination.parent.mkdir(parents=True,exist_ok=True)
    settings=Settings(data_dir=data_dir)
    with storage_guard(settings),tempfile.TemporaryDirectory(prefix="idea-echo-backup-",dir=destination.parent) as tmp:
        snapshot=Path(tmp)/"ideas.db"
        with closing(sqlite3.connect(data_dir/"ideas.db")) as source,closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
            target.execute("DELETE FROM sessions")
            target.commit()
            descriptors=[(row[0],json.loads(row[1])) for row in target.execute("SELECT id,metadata FROM attachments WHERE ready=1 AND EXISTS(SELECT 1 FROM attachment_refs r WHERE r.attachment_id=attachments.id)")]
        files={"ideas.db":snapshot}
        for aid,descriptor in descriptors:
            aid=str(UUID(aid));image=data_dir/"attachments"/aid
            if not image.is_file():raise ValueError("有已确认附件缺失，备份未完成")
            if file_hash(image)!=descriptor["sha256"]:raise ValueError("原图校验失败，不能把损坏附件标记为有效备份")
            files["attachments/"+aid]=image
        manifest={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),"files":{name:file_hash(path) for name,path in files.items()}}
        try:
            with zipfile.ZipFile(destination,"x",zipfile.ZIP_DEFLATED) as archive:
                for name,path in files.items():archive.write(path,name)
                archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False))
            verify_backup(destination)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return manifest


def _safe_entry(name):
    if name=="ideas.db":return
    parts=PurePosixPath(name).parts
    if len(parts)!=2 or parts[0]!="attachments" or str(UUID(parts[1]))!=parts[1]:raise ValueError("备份中有不允许的路径")


def verify_backup(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            names=[info.filename for info in infos]
            if len(set(names))!=len(names) or "manifest.json" not in names:raise ValueError("备份包含重复条目或缺少清单")
            if archive.getinfo("manifest.json").file_size>5*1024*1024 or sum(info.file_size for info in infos)>20*1024**3:raise ValueError("备份超过校验容量")
            manifest=json.loads(archive.read("manifest.json"))
            if manifest.get("schema_version")!=1 or "ideas.db" not in manifest.get("files",{}):raise ValueError("备份版本或数据库无效")
            if set(names)!=set(manifest["files"])|{"manifest.json"}:raise ValueError("备份条目与清单不一致")
            for name,expected in manifest["files"].items():
                _safe_entry(name)
                digest=hashlib.sha256()
                with archive.open(name) as source:
                    while data:=source.read(1024*1024):digest.update(data)
                if digest.hexdigest()!=expected:raise ValueError("备份校验失败")
            return {"valid":True,"manifest":manifest}
    except (zipfile.BadZipFile,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError("备份文件无效或已损坏") from error


def restore_backup(source: Path,empty_destination: Path) -> None:
    target=Path(empty_destination)
    if target.exists() and any(target.iterdir()):raise ValueError("只能恢复到空目录，不能覆盖已有数据")
    manifest=verify_backup(source)["manifest"]
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        for name,expected in manifest["files"].items():
            _safe_entry(name)
            output=target.joinpath(*PurePosixPath(name).parts)
            output.parent.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256()
            with archive.open(name) as content,output.open("xb") as dest:
                while chunk:=content.read(1024*1024):digest.update(chunk);dest.write(chunk)
            if digest.hexdigest()!=expected:raise ValueError("恢复过程中校验失败，请保留原备份重新恢复到另一个空目录")
    with closing(sqlite3.connect(target/"ideas.db")) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("恢复的数据库完整性检查失败")
        con.execute("CREATE TABLE IF NOT EXISTS sync_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        con.execute("INSERT OR REPLACE INTO sync_metadata VALUES('generation',?)",(str(uuid4()),))
        con.commit()


def rotate_backups(directory: Path) -> list[Path]:
    directory=Path(directory).resolve(strict=True)
    candidates=[]
    for path in directory.iterdir():
        match=re.fullmatch(r"idea-echo-(\d{8}T\d{6})\.zip",path.name)
        if match and path.is_file() and not path.is_symlink():
            timestamp=datetime.strptime(match[1],"%Y%m%dT%H%M%S")
            candidates.append((timestamp,path))
    candidates.sort(reverse=True)
    days={};weeks={}
    for timestamp,path in candidates:
        days.setdefault(timestamp.date(),path)
        weeks.setdefault(timestamp.isocalendar()[:2],path)
    keep=set(list(days.values())[:7])|set(list(weeks.values())[:4])
    # Refuse rotation if any retained recovery point is invalid.
    for path in keep:verify_backup(path)
    removed=[]
    for _,path in candidates:
        if path not in keep:
            path.unlink();removed.append(path)
    return removed


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["create","verify","restore","rotate"])
    parser.add_argument("--data-dir",type=Path,default=Settings().data_dir)
    parser.add_argument("--file",type=Path)
    parser.add_argument("--directory",type=Path)
    parser.add_argument("--destination",type=Path)
    args=parser.parse_args()
    if args.command=="rotate":
        if not args.directory:parser.error("轮换需要 --directory")
        rotate_backups(args.directory)
    elif not args.file:parser.error("需要 --file")
    elif args.command=="create":create_backup(args.data_dir,args.file)
    elif args.command=="verify":verify_backup(args.file)
    elif args.destination:restore_backup(args.file,args.destination)
    else:parser.error("恢复需要显式指定 --destination 空目录")
    print("完成：备份/恢复已校验；恢复后请重新登录。")


if __name__=="__main__":main()
