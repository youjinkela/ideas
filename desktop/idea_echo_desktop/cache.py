from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4


class Cache:
    def __init__(self, root: Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=threading.RLock()
        with self.db() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS ideas(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox(id TEXT,kind TEXT,request TEXT,conflict TEXT,PRIMARY KEY(id,kind));
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS archives(id TEXT PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY,idea_id TEXT,role TEXT,text TEXT);
            """)

    @contextmanager
    def db(self):
        with self.lock:
            con=sqlite3.connect(self.root/"cache.db",timeout=30)
            con.row_factory=sqlite3.Row
            try:
                yield con
                con.commit()
            except BaseException:
                con.rollback()
                raise
            finally:
                con.close()

    def _idea(self, con, id):
        row=con.execute("SELECT data FROM ideas WHERE id=?",(id,)).fetchone()
        if not row:
            raise KeyError("点子不存在")
        return json.loads(row[0])

    def _store(self,con,id,data):
        con.execute("INSERT OR REPLACE INTO ideas VALUES(?,?)",(id,json.dumps(data,ensure_ascii=False)))

    def list_ideas(self,view="all"):
        with self.db() as con:
            rows=[json.loads(r[0]) for r in con.execute("SELECT data FROM ideas ORDER BY rowid DESC")]
            conflicts={(r[0],r[1]):json.loads(r[2]) for r in con.execute("SELECT id,kind,conflict FROM outbox WHERE conflict IS NOT NULL")}
        for row in rows:
            row["conflicts"]={k[1]:v for k,v in conflicts.items() if k[0]==row["id"]}
        return [r for r in rows if view=="all" or r.get("status","pending") in ("pending","later")]

    def get(self,id):
        with self.db() as con:
            return self._idea(con,id)

    def apply_events(self,events):
        with self.db() as con:
            for event in events:
                id,kind,payload=event["entity_id"],event["kind"],event["payload"]
                if kind=="attachment":
                    for row in con.execute("SELECT id,data FROM ideas").fetchall():
                        data=json.loads(row["data"])
                        for image in data.get("attachments",[]):
                            if image["id"]==id:
                                image["content_ready"]=payload["content_ready"]
                        self._store(con,row["id"],data)
                else:
                    try:
                        data=self._idea(con,id)
                    except KeyError:
                        data={"id":id,"reflection":"","status":"pending","review_version":0,"status_version":0}
                    pending=con.execute("SELECT 1 FROM outbox WHERE id=? AND kind=?",(id,kind)).fetchone()
                    if kind=="record":
                        readiness={a["id"]:a.get("content_ready",False) for a in data.get("attachments",[])}
                        data.update(payload)
                        for image in data.get("attachments",[]):
                            image["content_ready"]=readiness.get(image["id"],False)
                    elif not pending:
                        if kind=="review":
                            if data.get("reflection","")!=payload["reflection"] or data.get("review_version",0)!=payload["review_version"]:
                                data["edit_revision"]=data.get("edit_revision",0)+1
                            data.update(reflection=payload["reflection"],review_version=payload["review_version"])
                        elif kind=="status":
                            data.update(status=payload["value"],status_version=payload["status_version"])
                    self._store(con,id,data)
                con.execute("INSERT OR REPLACE INTO meta VALUES('cursor',?)",(str(event["seq"]),))

    def cursor(self):
        with self.db() as con:
            row=con.execute("SELECT value FROM meta WHERE key='cursor'").fetchone()
            return int(row[0]) if row else 0

    def _queue(self,con,id,kind,payload,version):
        old=con.execute("SELECT request FROM outbox WHERE id=? AND kind=?",(id,kind)).fetchone()
        if old:
            version=json.loads(old[0])["expected_version"]
        request={"mutation_id":str(uuid4()),"expected_version":version,"payload":payload}
        con.execute("INSERT OR REPLACE INTO outbox VALUES(?,?,?,NULL)",(id,kind,json.dumps(request,ensure_ascii=False)))

    def save_reflection(self,id,text,expected_version=0,expected_edit_revision=None):
        if len(text)>200000:
            raise ValueError("发散内容过长，请分开整理")
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            data=self._idea(con,id)
            if expected_version!=data.get("review_version",0) or expected_edit_revision is not None and expected_edit_revision!=data.get("edit_revision",0):
                raise ValueError("发散已有新版本；旧稿仍留在编辑框，请先复制保留，再重新选择点子对比合并")
            data["reflection"]=text
            data["edit_revision"]=data.get("edit_revision",0)+1
            self._queue(con,id,"review",{"reflection":text},data.get("review_version",expected_version))
            self._store(con,id,data)
        return data

    def generation(self):
        with self.db() as con:
            row=con.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
            return row[0] if row else None

    def set_generation(self,generation,reset=False):
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO meta VALUES('generation',?)",(generation,))
            if reset:con.execute("INSERT OR REPLACE INTO meta VALUES('cursor','0')")

    def set_status(self,id,value):
        if value not in ("pending","later","reviewed","archived"):
            raise ValueError("状态不正确")
        with self.db() as con:
            data=self._idea(con,id)
            data["status"]=value
            self._queue(con,id,"status",{"value":value},data.get("status_version",0))
            self._store(con,id,data)

    def pending(self):
        with self.db() as con:
            return [dict(json.loads(r["request"]),id=r["id"],kind=r["kind"]) for r in con.execute("SELECT * FROM outbox WHERE conflict IS NULL")]

    def acknowledge(self,old,ack):
        with self.db() as con:
            row=con.execute("SELECT request FROM outbox WHERE id=? AND kind=?",(old["id"],old["kind"])).fetchone()
            if not row:
                return
            current=json.loads(row[0])
            if current["mutation_id"]==old["mutation_id"]:
                con.execute("DELETE FROM outbox WHERE id=? AND kind=?",(old["id"],old["kind"]))
            else:
                current["expected_version"]=ack["accepted_version"]
                con.execute("UPDATE outbox SET request=? WHERE id=? AND kind=?",(json.dumps(current),old["id"],old["kind"]))
            data=self._idea(con,old["id"])
            data[{"review":"review_version","status":"status_version"}[old["kind"]]]=ack["accepted_version"]
            self._store(con,old["id"],data)

    def mark_conflict(self,operation,detail):
        with self.db() as con:
            con.execute("UPDATE outbox SET conflict=? WHERE id=? AND kind=? AND json_extract(request,'$.mutation_id')=?",(json.dumps(detail),operation["id"],operation["kind"],operation["mutation_id"]))

    def resolve_conflict(self,id,kind,keep_local):
        with self.db() as con:
            row=con.execute("SELECT * FROM outbox WHERE id=? AND kind=?",(id,kind)).fetchone()
            if not row or not row["conflict"]:
                raise ValueError("未找到待处理冲突")
            detail=json.loads(row["conflict"])
            if not isinstance(detail,dict) or "version" not in detail:
                raise ValueError("冲突需要重新登录或检查服务器")
            request=json.loads(row["request"])
            data=self._idea(con,id)
            field="reflection" if kind=="review" else "status"
            if keep_local:
                request.update(expected_version=detail["version"],mutation_id=str(uuid4()))
                con.execute("UPDATE outbox SET request=?,conflict=NULL WHERE id=? AND kind=?",(json.dumps(request),id,kind))
            else:
                current=detail.get("current") or {}
                data[field]=current.get("reflection" if kind=="review" else "value", "" if kind=="review" else "pending")
                con.execute("DELETE FROM outbox WHERE id=? AND kind=?",(id,kind))
            data["review_version" if kind=="review" else "status_version"]=detail["version"]
            self._store(con,id,data)
