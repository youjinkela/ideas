import hashlib
from uuid import UUID
from fastapi import FastAPI, Request, Depends, Query, HTTPException
from .settings import Settings
from .auth import Login, login, require_owner
from .db import connect
from .records import Mutation, apply_mutation, read_changes


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
    def changes(after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=100), owner: str = Depends(require_owner)):
        return read_changes(settings, owner, after, limit)

    return app

