"""API layer — FastAPI server with REST and WebSocket endpoints.

Exports: create_app (FastAPI application factory)
"""

from .server import create_app
from .routes import setup_routes

__all__ = ["create_app", "setup_routes"]
