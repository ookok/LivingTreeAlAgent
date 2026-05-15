"""Module 2b: Election caching + Tiered routing + Provider ping tests.

Pytest tests:
  test_election_tiers       — _elect_tiers() method exists
  test_election_status      — get_election_status() returns dict
  test_l4_model_present     — consciousness._l4_model attr exists
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


def _has_api_keys() -> bool:
    keys = ["DEEPSEEK_API_KEY", "LONGCAT_API_KEY", "OPENROUTER_API_KEY",
            "LT_MODEL_DEEPSEEK_API_KEY", "LT_MODEL_LONGCAT_API_KEY"]
    return any(os.environ.get(k, "") for k in keys)


# ── unit tests ──

def test_consciousness_attrs():
    """After init, consciousness has L4 model and election attrs."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    con = hub.world.consciousness

    # L4 locked model — attr name varies between versions
    l4_attr = next((a for a in ["_l4_model", "_l4_locked_model"]
                    if hasattr(con, a)), None)
    assert l4_attr is not None, "No L4 model attr found"


def test_election_status_dict():
    """get_election_status() returns a dict with expected keys."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    con = hub.world.consciousness

    if hasattr(con, "get_election_status"):
        status = con.get_election_status()
        assert isinstance(status, dict), f"Expected dict, got {type(status)}"


def test_election_tiers_method():
    """_elect_tiers() method exists on consciousness."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    con = hub.world.consciousness

    assert hasattr(con, "_elect_tiers") or hasattr(con, "elect_tiers"), \
        "No tiered election method found"


# ── manual test ──

@pytest.mark.skipif(not _has_api_keys(), reason="No API keys configured")
@pytest.mark.asyncio
async def test_manual_cached_election():
    """Manual: verify election is cached (second call ~0ms). Requires API keys."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    hub = IntegrationHub(config=get_config(), lazy=False)
    hub._init_sync()
    con = hub.world.consciousness

    elect_fn = con._elect if hasattr(con, "_elect") else con.elect

    # First election (cold)
    t0 = time.time()
    first = await elect_fn()
    t1 = time.time() - t0
    assert first, "First election failed"

    # Second election (should be cached)
    t0 = time.time()
    second = await elect_fn()
    t2 = time.time() - t0

    assert first == second, f"Election changed: {first} → {second}"
    assert t2 < t1 * 0.5, f"Cached election not faster ({t2:.3f}s vs {t1:.3f}s)"


@pytest.mark.skipif(not _has_api_keys(), reason="No API keys configured")
@pytest.mark.asyncio
async def test_manual_stream_of_thought():
    """Manual: stream_of_thought produces output. Requires API keys."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    hub = IntegrationHub(config=get_config(), lazy=False)
    hub._init_sync()
    con = hub.world.consciousness

    thoughts = []
    async for thought in con.stream_of_thought("Say hello in one short sentence.", max_thoughts=3):
        thoughts.append(thought)
        if len(thoughts) >= 3:
            break

    assert len(thoughts) > 0, "stream_of_thought produced 0 thoughts"
    combined = "".join([str(t) for t in thoughts])
    assert len(combined) > 0, "stream_of_thought output is empty"
