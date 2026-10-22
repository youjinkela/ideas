import argparse
import asyncio
from collections import deque
from contextlib import asynccontextmanager,suppress
from datetime import datetime,date
import json
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID
import webbrowser

import httpx
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from .ai import AiSettings,ask_ai
from .archive import ArchiveManager
from .cache import Cache
from .reminders import claim_reminder,send_reminder,SHANGHAI
from .settings import DesktopSettings,validate_cloud_url
from .sync import sync_cloud


def create_desktop_app(root: Path,origin="http://127.0.0.1:47821",bootstrap=None,background=False):
    settings=DesktopSettings(root)
    sid=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    bootstrap=bootstrap or secrets.token_urlsafe(32)
    sync_lock=threading.Lock();ai_times=deque()

    def cache_for_account():
        account=settings.get("account_id")
        return Cache(root/"accounts"/(str(UUID(account)) if account else "local"))

    def perform_sync():
        if not settings.get("cloud_url") or not settings.get("cloud_token"):
            return {"setup_required":True}
        with sync_lock:
            try:
                result=sync_cloud(app.state.cache,settings.get("cloud_url"),settings.secret("cloud_token"))
                app.state.sync_error=""
                return result
            except (httpx.HTTPError,ValueError,OSError):
                app.state.sync_error="同步未完成，请检查网络或重新登录；本机编辑已保留"
                return {"error":app.state.sync_error}

    async def tick():
        while True:
            await asyncio.to_thread(perform_sync)
            today=datetime.now(SHANGHAI)
            if claim_reminder(app.state.cache,today,len(app.state.cache.list_ideas("pending"))):
                # Failed notification still leaves the in-page pending count visible.
                await asyncio.to_thread(send_reminder,origin+"/#"+bootstrap)
            await asyncio.sleep(60)

    @asynccontextmanager
    async def lifespan(application):
        task=asyncio.create_task(tick()) if background else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):await task

    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.bootstrap=bootstrap
    app.state.cache=cache_for_account()
    app.state.ai_call=ask_ai
    app.state.sync_error=""
    app.state.settings=settings
    web=Path(__file__).resolve().parent.parent/"web"

    @app.middleware("http")
    async def protect(request: Request,call_next):
        if request.headers.get("host")!=urlsplit(origin).netloc:
            return JSONResponse({"detail":"本机来源校验失败"},403)
        path=request.url.path
        if path.startswith("/local/"):
            is_boot=path=="/local/session" and request.method=="POST"
            if not is_boot and not secrets.compare_digest(request.cookies.get("echo_session",""),sid):
                return JSONResponse({"detail":"请从本机启动程序打开回顾页"},401)
            if request.method not in ("GET","HEAD","OPTIONS"):
                if request.headers.get("origin")!=origin or (not is_boot and not secrets.compare_digest(request.headers.get("x-csrf-token",""),csrf)):
                    return JSONResponse({"detail":"请求来源或防跨站凭证不正确"},403)
        response=await call_next(request)
        response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Cache-Control"]="no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request,error):return JSONResponse({"detail":str(error)},400)
    @app.exception_handler(KeyError)
    async def missing(request,error):return JSONResponse({"detail":"点子或设置不存在"},404)

    @app.post("/local/session")
    def session(body: dict):
        if not secrets.compare_digest(str(body.get("bootstrap","")),bootstrap):raise HTTPException(401,"启动凭证无效")
        response=JSONResponse({"csrf":csrf})
        response.set_cookie("echo_session",sid,httponly=True,samesite="strict",max_age=86400)
        return response

    @app.get("/local/session")
    def existing_session():return {"csrf":csrf}

    @app.get("/local/ideas")
    def ideas(view: str="pending"):
        rows=app.state.cache.list_ideas("all" if view=="all" else "pending")
        for row in rows:
            for image in row.get("attachments",[]):
                image["local_ready"]=(app.state.cache.root/"attachments"/str(UUID(image["id"]))).is_file()
        return {"ideas":rows,"pending_uploads":len(app.state.cache.pending()),"sync_error":app.state.sync_error}

    @app.post("/local/reflection")
    def reflection(body: dict):
        return app.state.cache.save_reflection(str(UUID(body["id"])),str(body.get("reflection","")),int(body.get("expected_version",0)),body.get("expected_edit_revision"))

    @app.post("/local/status")
    def status(body: dict):
        app.state.cache.set_status(str(UUID(body["id"])),body["value"])
        return {"ok":True}

    @app.post("/local/conflict")
    def conflict(body: dict):
        app.state.cache.resolve_conflict(str(UUID(body["id"])),body["kind"],body.get("keep_local") is True)
        return {"ok":True}

    @app.post("/local/sync")
    def sync_now():return perform_sync()

    @app.get("/local/settings")
    def get_settings():return settings.public()

    @app.post("/local/settings")
    def set_settings(body: dict):
        values={}
        if body.get("cloud_url") and body.get("username") and body.get("password"):
            url=validate_cloud_url(body["cloud_url"])
            with httpx.Client(timeout=20,follow_redirects=False) as client:
                response=client.post(url+"/v1/auth/login",json={"username":body["username"],"password":body["password"]})
            if response.status_code!=200:raise HTTPException(401,"连接失败，请核对服务器地址与账号")
            result=response.json()
            values.update(cloud_url=url,cloud_token=result["token"],account_id=str(UUID(result["account_id"])))
        if body.get("ai_url"):
            if not str(body["ai_url"]).startswith("https://"):raise ValueError("模型接口必须使用 HTTPS")
            values.update(ai_url=body["ai_url"].rstrip("/"),ai_model=str(body.get("ai_model","")))
        if body.get("ai_key"):values["ai_key"]=str(body["ai_key"])
        settings.update(**values)
        if "account_id" in values:app.state.cache=cache_for_account()
        return settings.public()

    @app.post("/local/vault/select")
    def select_vault():
        import tkinter as tk
        from tkinter.filedialog import askdirectory
        window=tk.Tk();window.withdraw();window.attributes("-topmost",True)
        try:chosen=askdirectory(parent=window,title="选择允许点子回声归档的 Obsidian 笔记库")
        finally:window.destroy()
        if chosen:
            from .vault import Vault
            vault=Vault(Path(chosen));settings.update(vault=str(vault.root))
        return {"vault":settings.get("vault")}

    def manager():
        if not settings.get("vault"):raise HTTPException(409,"请先在设置里选择笔记库")
        return ArchiveManager(Path(settings.get("vault")),app.state.cache.root/"archive-operations",app.state.cache.root/"attachments")

    @app.get("/local/vault/folders")
    def folders():return {"folders":manager().folders()}

    @app.get("/local/vault/notes")
    def notes(q: str=""):return {"notes":manager().search(q)}

    @app.post("/local/archive/preview")
    def preview(body: dict):
        idea=app.state.cache.get(str(UUID(body["id"])))
        return manager().preview(idea,idea.get("reflection",""),body.get("mode","new"),str(body.get("folder","")),str(body.get("title","")),body.get("target"))

    @app.post("/local/archive/commit")
    def commit(body: dict):
        result=manager().commit(str(UUID(body["operation_id"])))
        if app.state.cache.get(result["idea_id"]).get("status")!="archived":app.state.cache.set_status(result["idea_id"],"archived")
        return result

    @app.post("/local/archive/ack")
    def acknowledge_archive(body: dict):
        manager().acknowledge(str(UUID(body["operation_id"])))
        return {"ok":True}

    @app.get("/local/images/{aid}")
    def image(aid: UUID):
        path=app.state.cache.root/"attachments"/str(aid)
        if not path.is_file():raise HTTPException(409,"图片待同步")
        mime="application/octet-stream"
        for idea in app.state.cache.list_ideas():
            for item in idea.get("attachments",[]):
                if item["id"]==str(aid):mime=item["mime_type"]
        return FileResponse(path,media_type=mime)

    @app.get("/local/ai/history")
    def ai_history(id: UUID):
        with app.state.cache.db() as con:
            return {"messages":[dict(r) for r in con.execute("SELECT role,text FROM ai_messages WHERE idea_id=? ORDER BY id",(str(id),))]}

    @app.post("/local/ai/ask")
    def ai_ask(body: dict):
        if not settings.get("ai_key"):raise HTTPException(409,"请先在设置里配置模型接口")
        now=time.monotonic()
        while ai_times and ai_times[0]<now-60:ai_times.popleft()
        if len(ai_times)>=5:raise HTTPException(429,"请稍等，每分钟最多请求5次")
        ai_times.append(now)
        id=str(UUID(body["id"]));idea=app.state.cache.get(id)
        history=ai_history(UUID(id))["messages"]
        request={"text":idea["text"],"reflection":idea.get("reflection",""),"mode":body.get("mode","custom"),"prompt":str(body.get("prompt","")),"conversation":[{"role":m["role"],"content":m["text"]} for m in history]}
        result=app.state.ai_call(request,AiSettings(settings.get("ai_url"),settings.get("ai_model"),settings.secret("ai_key")))
        with app.state.cache.db() as con:
            con.execute("INSERT INTO ai_messages(idea_id,role,text) VALUES(?,?,?)",(id,"user",request["prompt"] or request["mode"]))
            con.execute("INSERT INTO ai_messages(idea_id,role,text) VALUES(?,?,?)",(id,"assistant",result["text"]))
        return result

    @app.get("/")
    def index():
        if not (web/"index.html").is_file():return JSONResponse({"detail":"界面资源尚未安装"},503)
        return FileResponse(web/"index.html")
    @app.get("/assets/{filename}")
    def asset(filename: str):
        types={"app.js":"text/javascript","styles.css":"text/css"}
        if filename not in types:raise HTTPException(404)
        return FileResponse(web/filename,media_type=types[filename])

    @app.get("/favicon.ico")
    def favicon():return Response(status_code=204)
    return app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data-dir",type=Path,default=Path("data/desktop"))
    parser.add_argument("--port",type=int,default=47821)
    parser.add_argument("--no-browser",action="store_true")
    args=parser.parse_args()
    sock=socket.socket()
    try:sock.bind(("127.0.0.1",args.port))
    except OSError:sock.bind(("127.0.0.1",0))
    sock.listen(128)
    origin=f"http://127.0.0.1:{sock.getsockname()[1]}"
    bootstrap=secrets.token_urlsafe(32)
    app=create_desktop_app(args.data_dir,origin,bootstrap,background=True)
    if not args.no_browser:webbrowser.open(origin+"/#"+bootstrap)
    import uvicorn
    uvicorn.Server(uvicorn.Config(app,access_log=False,log_level="warning")).run(sockets=[sock])


if __name__=="__main__":main()
