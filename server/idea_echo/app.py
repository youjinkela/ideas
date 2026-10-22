import hashlib
import tempfile
from pathlib import Path
from uuid import UUID
from fastapi import FastAPI, Request, Depends, Query, HTTPException
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool
from .settings import Settings
from .auth import Login, login, require_owner
from .db import connect
from .records import Mutation, apply_mutation, read_changes
from .attachments import store_attachment, open_attachment, metadata, thumbnail, attachment_path


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Idea Echo", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    @app.get("/health")
    def health():
        return {"status": "ok", "schema_version": 1}

    @app.post("/v1/auth/login")
    def login_route(body: Login, request: Request):
        return login(settings, body, request.client.host if request.client else "unknown")

    @app.post("/v1/auth/logout")
    def logout(request: Request, owner: str = Depends(require_owner)):
        digest=hashlib.sha256(request.headers["authorization"][7:].encode()).hexdigest()
        with connect(settings) as con:
            con.execute("DELETE FROM sessions WHERE digest=?", (digest,))
        return {"ok":True}

    @app.get("/v1/capabilities")
    def capabilities(owner: str = Depends(require_owner)):
        return {"max_text_chars":100000,"max_image_bytes":settings.max_image_bytes,"max_images":settings.max_images,"max_total_bytes":settings.max_total_bytes,"formats":["image/jpeg","image/png","image/webp"]}

    @app.put("/v1/ideas/{idea_id}/{kind}")
    def mutate(idea_id: UUID, kind: str, body: Mutation, owner: str = Depends(require_owner)):
        if kind not in ("record","review","status"):
            raise HTTPException(404)
        return apply_mutation(settings, owner, kind, str(idea_id), body)

    @app.get("/v1/changes")
    def changes(after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=100),generation: str | None=Query(None,max_length=80), owner: str = Depends(require_owner)):
        return read_changes(settings, owner, after, limit,generation)

    @app.put("/v1/attachments/{aid}/content")
    async def upload(aid: UUID, request: Request, owner: str=Depends(require_owner)):
        meta=metadata(settings,owner,str(aid))["descriptor"]
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        size=0
        with tempfile.TemporaryFile(dir=settings.data_dir) as staged:
            async for chunk in request.stream():
                size+=len(chunk)
                if size>settings.max_image_bytes or size>meta["size_bytes"]:
                    raise HTTPException(413,"图片超出容量")
                staged.write(chunk)
            staged.seek(0)
            return await run_in_threadpool(store_attachment,settings,owner,str(aid),staged)

    @app.get("/v1/attachments/{aid}")
    def attachment_info(aid: UUID,owner: str=Depends(require_owner)):
        info=metadata(settings,owner,str(aid))
        return info["descriptor"] | {"content_ready":bool(info["ready"]) and attachment_path(settings,str(aid)).is_file()}

    @app.get("/v1/attachments/{aid}/content")
    def download(aid: UUID,owner: str=Depends(require_owner)):
        path=open_attachment(settings,owner,str(aid))
        mime=metadata(settings,owner,str(aid))["descriptor"]["mime_type"]
        return FileResponse(path,media_type=mime,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/v1/attachments/{aid}/thumbnail")
    def thumb(aid: UUID,owner: str=Depends(require_owner)):
        return Response(thumbnail(settings,owner,str(aid)),media_type="image/jpeg",headers={"Cache-Control":"private, no-store"})

    return app

