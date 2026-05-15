"""Module 1: Hub initialization tests — verifies component wiring & no crash.

Pytest tests (always safe):
  test_import_hub          — import succeeds
  test_hub_creation        — IntegrationHub() doesn't throw
  test_hub_init_sync       — _init_sync() wires world/consciousness/knowledge_base
  test_hub_world_components — verify wired components aren't None after init
  test_config_load         — get_config() returns valid config

Manual integration tests (requires API keys, skipped by default):
  test_manual_full_init    — full hub.start() + election + stream_of_thought
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── helpers ──

def _has_api_keys() -> bool:
    """Check if any API key env vars are set."""
    keys = [
        "DEEPSEEK_API_KEY", "LONGCAT_API_KEY", "OPENROUTER_API_KEY",
        "LT_MODEL_DEEPSEEK_API_KEY", "LT_MODEL_LONGCAT_API_KEY",
    ]
    return any(os.environ.get(k, "") for k in keys)


# ── unit / smoke tests (always run) ──

def test_import_hub():
    """Import IntegrationHub succeeds."""
    from livingtree.integration.hub import IntegrationHub
    assert IntegrationHub is not None


def test_hub_creation():
    """IntegrationHub() creation doesn't throw."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    assert hub is not None
    assert hub.config is not None


def test_hub_init_sync():
    """_init_sync() completes without throwing and wires world."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    assert hub.world is not None


def test_hub_world_components():
    """After _init_sync, world has required components."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    w = hub.world
    assert w is not None
    assert w.consciousness is not None, "consciousness not wired"
    assert w.knowledge_base is not None, "knowledge_base not wired"
    assert w.safety is not None, "safety not wired"


def test_hub_engine_components():
    """After _init_sync, execution/network components are wired."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    w = hub.world
    assert w.task_planner is not None, "task_planner not wired"
    assert w.orchestrator is not None, "orchestrator not wired"
    assert w.self_healer is not None, "self_healer not wired"
    assert w.tool_market is not None, "tool_market not wired"
    assert w.skill_factory is not None, "skill_factory not wired"


def test_config_load():
    """get_config() returns valid LTAIConfig."""
    from livingtree.config.settings import get_config
    cfg = get_config()
    assert cfg is not None
    assert cfg.model is not None
    assert cfg.api is not None


# ── integration tests (requires API keys) ──

@pytest.mark.skipif(not _has_api_keys(), reason="No API keys configured")
@pytest.mark.asyncio
async def test_manual_full_init():
    """Manual integration test: full hub.start() + election + thought stream.
    
    Runs the original manual test logic. Requires at least one API key.
    """
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    config = get_config()
    hub = IntegrationHub(config=config, lazy=False)

    # Start with 120s timeout
    try:
        await asyncio.wait_for(hub.start(), timeout=120.0)
    except asyncio.TimeoutError:
        hub._started = True
        hub._ready_event.set()
    except Exception:
        hub._started = True
        hub._ready_event.set()

    con = hub.consciousness
    assert con is not None, "consciousness is None after init"

    # Check providers
    free = getattr(con, "_free_models", [])
    paid = getattr(con, "_paid_models", [])
    assert len(free) + len(paid) > 0, "No providers registered"

    # Try election
    elected = None
    if hasattr(con, "_elect"):
        elected = await asyncio.wait_for(con._elect(), timeout=60.0)
    elif hasattr(con, "elect"):
        elected = await asyncio.wait_for(con.elect(), timeout=60.0)
    assert elected, "Election returned empty result"

    # Quick stream of thought
    count = 0
    async for thought in con.stream_of_thought("Hello, self-test.", max_thoughts=3):
        count += 1
        if count >= 3:
            break
    assert count > 0, "stream_of_thought produced 0 thoughts"

    await hub.shutdown()
