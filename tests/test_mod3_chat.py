"""Module 3: Chat interaction tests — FastAPI client + consciousness methods.

Unit tests (always safe):
  test_fastapi_app_creation      — create_app() succeeds
  test_fastapi_health_endpoint   — GET /api/health → 200
  test_chat_request_model        — ChatRequest model validation
  test_consciousness_import      — DualModelConsciousness import
  test_consciousness_methods     — key methods exist on consciousness

Manual integration (requires API keys):
  test_manual_chat_flow          — full chat via hub
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _has_api_keys() -> bool:
    keys = ["DEEPSEEK_API_KEY", "LONGCAT_API_KEY", "OPENROUTER_API_KEY",
            "LT_MODEL_DEEPSEEK_API_KEY", "LT_MODEL_LONGCAT_API_KEY"]
    return any(os.environ.get(k, "") for k in keys)


# ── FastAPI unit tests ──

@pytest.fixture(scope="module")
def test_app():
    """Create FastAPI app with dummy hub for testing."""
    from livingtree.api.server import create_app
    return create_app(hub=None, config=None)


@pytest.fixture(scope="module")
def client(test_app):
    """FastAPI TestClient."""
    return TestClient(test_app)


def test_fastapi_app_creation(test_app):
    """create_app() returns a valid FastAPI app."""
    assert test_app is not None
    assert test_app.title == "LivingTree AI Agent"


def test_fastapi_health_endpoint(client):
    """GET /api/health returns 200."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_fastapi_docs(client):
    """GET /docs returns 200 (Swagger UI)."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_fastapi_favicon(client):
    """GET /favicon.ico returns 200 or 204."""
    response = client.get("/favicon.ico")
    assert response.status_code in (200, 204)


# ── ChatRequest model tests ──

def test_chat_request_model():
    """ChatRequest model validation works."""
    from livingtree.api.routes import ChatRequest
    req = ChatRequest(message="Hello")
    assert req.message == "Hello"
    assert req.session_id is None
    assert req.context == {}


def test_chat_request_with_session():
    """ChatRequest accepts optional session_id."""
    from livingtree.api.routes import ChatRequest
    req = ChatRequest(message="Test", session_id="abc123")
    assert req.session_id == "abc123"


# ── Consciousness unit tests ──

def test_consciousness_import():
    """DualModelConsciousness imports cleanly."""
    from livingtree.dna.dual_consciousness import DualModelConsciousness
    assert DualModelConsciousness is not None


def test_consciousness_methods():
    """After init, consciousness has core methods."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    con = hub.world.consciousness

    methods = ["stream_of_thought", "chain_of_thought", "recognize_intent"]
    for m in methods:
        assert hasattr(con, m), f"Missing method: {m}"


# ── manual integration test (requires API keys) ──

@pytest.mark.skipif(not _has_api_keys(), reason="No API keys configured")
@pytest.mark.asyncio
async def test_manual_chat_flow():
    """Manual: full chat flow via consciousness. Requires API keys."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    hub = IntegrationHub(config=get_config(), lazy=False)
    hub._init_sync()
    con = hub.consciousness

    # Stream of thought
    thoughts = []
    async for thought in con.stream_of_thought("Hello, how are you?", max_thoughts=2):
        thoughts.append(thought)
        if len(thoughts) >= 2:
            break
    assert len(thoughts) > 0, "stream_of_thought failed"

    # Chain of thought
    result = await con.chain_of_thought("1+1=? Answer briefly.", max_steps=1)
    assert result, "chain_of_thought returned empty"

    # Recognize intent
    intent = await con.recognize_intent("What is the weather today?")
    assert intent is not None, "recognize_intent returned None"

    await hub.shutdown()
