"""FastAPI server for LivingTree — serves web frontend + full REST API."""

from __future__ import annotations

from pathlib import Path

import traceback
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, RedirectResponse, JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from loguru import logger

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

    # Rate limiting — 100 req/min per IP, burst 20
    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ═══ Global Exception Handlers ═══

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Return structured 422 for Pydantic validation errors."""
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": exc.errors(),
                "trace_id": str(uuid.uuid4())[:8],
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Return consistent error format for HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "detail": exc.detail,
                "trace_id": str(uuid.uuid4())[:8],
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all for unhandled exceptions. Logs full traceback for debugging."""
        trace_id = str(uuid.uuid4())[:8]
        logger.error(
            f"[{trace_id}] Unhandled exception on {request.method} {request.url.path}: "
            f"{type(exc).__name__}: {exc}"
        )
        logger.error(f"[{trace_id}] Traceback:\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred. Check server logs.",
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # ═══ Startup: ConcurrencyGuard ═══
    @app.on_event("startup")
    async def startup_concurrency_guard():
        try:
            from ..core.concurrency_guard import get_concurrency_guard
            guard = get_concurrency_guard()
            logger.info(f"ConcurrencyGuard active (max_concurrent={guard.max_concurrent})")
        except Exception as e:
            logger.warning(f"ConcurrencyGuard startup skipped: {e}")

    # ═══ OTEL Middleware ═══
    try:
        from ..observability.otel_integration import get_otel, OtelMiddleware
        otel = get_otel()
        app.add_middleware(OtelMiddleware)
        logger.info("OTEL middleware wired")
    except Exception as e:
        logger.debug(f"OTEL middleware skipped: {e}")

    # ═══ Hub Wiring ═══
    if hub:
        app.state.hub = hub
        app.state.life = hub.world if hasattr(hub, "world") else hub
    else:
        # No hub provided — create a real IntegrationHub in background
        from ..integration.hub import IntegrationHub
        from ..config import get_config
        _hub = IntegrationHub(config=config or get_config())
        app.state.hub = _hub
        app.state.life = _hub.world if hasattr(_hub, "world") else None
        import asyncio as _asyncio
        app.state.hub_init_task = _asyncio.ensure_future(_hub.start())
    
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

    # PWA manifest + SW (always served)
    @app.get("/manifest.json")
    async def serve_manifest():
        mf = web_root / "manifest.json"
        from fastapi.responses import Response
        return Response(content=mf.read_bytes() if mf.exists() else b"{}", media_type="application/manifest+json")

    @app.get("/sw.js")
    async def serve_sw():
        sw = web_root / "sw.js"
        from fastapi.responses import Response
        return Response(content=sw.read_bytes() if sw.exists() else b"", media_type="application/javascript",
                       headers={"Service-Worker-Allowed": "/"})

    if web_root.exists():
        if (web_root / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(web_root / "assets")), name="assets")
        app.mount("/css", StaticFiles(directory=str(web_root / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(web_root / "js")), name="js")
        app.mount("/core", StaticFiles(directory=str(web_root / "core")), name="core")
        app.mount("/services", StaticFiles(directory=str(web_root / "services")), name="services")
        app.mount("/components", StaticFiles(directory=str(web_root / "components")), name="components")

        @app.get("/static/evolution.html")
        async def serve_evolution():
            return FileResponse(str(web_root / "evolution.html"))

        @app.get("/db-explorer")
        async def serve_db_explorer():
            return FileResponse(str(web_root / "db-explorer.html"))

        @app.get("/favicon.ico")
        async def serve_favicon():
            return FileResponse(str(web_root / "assets" / "favicon.ico")) if (web_root / "assets" / "favicon.ico").exists() else Response(status_code=204)

        @app.get("/app.js")
        async def serve_app_js():
            return FileResponse(str(web_root / "app.js"))

    return app
