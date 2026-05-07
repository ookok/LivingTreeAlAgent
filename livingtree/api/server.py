"""FastAPI server for LivingTree — serves web frontend + full REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import setup_routes


def create_app(hub=None, config=None) -> FastAPI:
    app = FastAPI(
        title="LivingTree AI Agent",
        description="Digital Lifeform — Web UI + REST + WebSocket API",
        version="2.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = getattr(getattr(config, 'api', None), 'cors_origins', ["*"])
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    if hub:
        app.state.hub = hub

    setup_routes(app)

    # Static files: serve web frontend from client/web/
    web_root = Path(__file__).resolve().parent.parent.parent / "client" / "web"
    if web_root.exists():
        if (web_root / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(web_root / "assets")), name="assets")
        app.mount("/css", StaticFiles(directory=str(web_root / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(web_root / "js")), name="js")

        @app.get("/")
        async def serve_index():
            return FileResponse(str(web_root / "index.html"))

    return app
