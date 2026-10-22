from fastapi import FastAPI
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Idea Echo", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    @app.get("/health")
    def health():
        return {"status": "ok", "schema_version": 1}

    return app

