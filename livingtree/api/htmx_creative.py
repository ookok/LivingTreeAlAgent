"""HTMX Creative routes — garden, timeline, dreams, emotions."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

creative_router = APIRouter(prefix="/creative", tags=["creative"])


__all__ = ["creative_router"]
