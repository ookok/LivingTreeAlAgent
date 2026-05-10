"""FastAPI server for LivingTree — serves web frontend + full REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, RedirectResponse

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
        app.state.life = hub.world if hasattr(hub, "world") else hub
    else:
        class _DummyHub:
            _started = True
            _treellm = None
            _elected = ""

            def __getattr__(self, name): return None

            async def _init_treellm(self):
                from ..treellm.core import TreeLLM
                from ..treellm.providers import create_deepseek_provider, create_longcat_provider, create_openrouter_provider, create_ollama_provider
                from ..config import get_config
                cfg = get_config()
                llm = TreeLLM()
                dk = cfg.model.deepseek_api_key
                if dk: llm.add_provider(create_deepseek_provider(dk))
                lk = cfg.model.longcat_api_key
                if lk: llm.add_provider(create_longcat_provider(lk))
                rk = cfg.model.openrouter_api_key
                if rk: llm.add_provider(create_openrouter_provider(rk, cfg.model.openrouter_default_model))
                llm.add_provider(create_ollama_provider())
                self._treellm = llm
                # Pre-elect on startup
                if llm.provider_names:
                    self._elected = await llm.elect(list(llm._providers.keys()))
                    print(f"[TreeLLM] Pre-elected: {self._elected}")

            async def chat(self, msg, **kw):
                if self._treellm is None:
                    await self._init_treellm()
                if not self._elected:
                    self._elected = await self._treellm.elect(list(self._treellm._providers.keys()))

                result = await self._treellm.chat([{"role":"user","content":msg}], provider=self._elected)
                text = result.text if hasattr(result,'text') and not getattr(result,'error','') else ""
                if not text or len(text) <= 5:
                    # Re-elect on failure
                    self._elected = await self._treellm.elect(list(self._treellm._providers.keys()))
                    if self._elected:
                        result = await self._treellm.chat([{"role":"user","content":msg}], provider=self._elected)
                        text = result.text if hasattr(result,'text') and not getattr(result,'error','') else ""
                if text and len(text) > 5:
                    return {"session_id":"local","intent":"chat","reflections":[text],"plan":[],"execution_results":[]}
                return {"session_id":"local","intent":"chat","reflections":["TreeLLM选举未找到可用模型"],"plan":[],"execution_results":[]}

        app.state.hub = _DummyHub()
        # Pre-init TreeLLM at startup so first chat is fast
        import asyncio as _asyncio
        _asyncio.ensure_future(app.state.hub._init_treellm())
    
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
