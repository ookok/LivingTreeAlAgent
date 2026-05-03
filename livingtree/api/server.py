"""FastAPI server factory for the LivingTree digital life form.

Provides:
- POST /api/chat — synchronous and streaming chat
- GET /api/health — health check
- GET /api/tools — list available tools
- GET /api/skills — list available skills
- GET /api/metrics — runtime metrics
- GET /api/status — life engine status
- WS /ws — real-time WebSocket updates
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import setup_routes


def create_app(hub=None, config=None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        hub: IntegrationHub instance (created if not provided)
        config: LTAIConfig instance (loaded from config if not provided)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="LivingTree AI Agent API",
        description="Digital Lifeform — REST and WebSocket API for the LivingTree platform",
        version="2.0.0",
        docs_url="/docs" if not config or getattr(config.api, 'docs_enabled', True) else None,
        redoc_url="/redoc" if not config or getattr(config.api, 'docs_enabled', True) else None,
    )

    # CORS
    origins = config.api.cors_origins if config and hasattr(config, 'api') else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store hub reference
    if hub:
        app.state.hub = hub

    setup_routes(app)

    return app
