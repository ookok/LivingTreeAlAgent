"""FastAPI server for LivingTree — serves web frontend + full REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from .routes import setup_routes
from .auth import setup_auth_routes
from .openai_proxy import setup_openai_proxy
from .code_api import setup_code_routes
from .wework_bot import setup_bot_routes
from .github_auth import setup_github_routes
from .audit import setup_audit_routes
from .workspace import setup_workspace_routes


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
    # GZip compression for static assets (CSS/JS/HTML)
    app.add_middleware(GZipMiddleware, minimum_size=512)

    if hub:
        app.state.hub = hub

    setup_routes(app)
    setup_auth_routes(app)
    setup_openai_proxy(app)
    setup_code_routes(app)
    setup_bot_routes(app)
    setup_github_routes(app)
    setup_audit_routes(app)
    setup_workspace_routes(app)

    # ═══ HTMX Web Layer (Jinja2 templates + hypermedia) ═══
    from .htmx_web import setup_htmx
    setup_htmx(app)

    # Static files: serve web frontend from client/web/
    web_root = Path(__file__).resolve().parent.parent.parent / "client" / "web"
    if web_root.exists():
        if (web_root / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(web_root / "assets")), name="assets")
        app.mount("/css", StaticFiles(directory=str(web_root / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(web_root / "js")), name="js")
        app.mount("/core", StaticFiles(directory=str(web_root / "core")), name="core")
        app.mount("/services", StaticFiles(directory=str(web_root / "services")), name="services")
        app.mount("/components", StaticFiles(directory=str(web_root / "components")), name="components")

        @app.get("/")
        async def serve_index():
            return FileResponse(str(web_root / "index.html"))

        @app.get("/favicon.ico")
        async def serve_favicon():
            return FileResponse(str(web_root / "assets" / "favicon.ico")) if (web_root / "assets" / "favicon.ico").exists() else Response(status_code=204)

        @app.get("/app.js")
        async def serve_app_js():
            return FileResponse(str(web_root / "app.js"))

    return app
