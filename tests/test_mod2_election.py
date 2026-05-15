"""Module 2: Model election tests — HolisticElection + TreeLLM routing.

Pytest tests (always safe):
  test_import_election     — HolisticElection import succeeds
  test_election_instantiate — HolisticElection() creates without throw
  test_tree_llm_import     — TreeLLM import + instantiation
  test_provider_registry   — can add providers to TreeLLM
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


# ── unit / smoke tests ──

def test_import_election():
    """HolisticElection imports cleanly."""
    from livingtree.treellm.holistic_election import HolisticElection
    assert HolisticElection is not None


def test_election_instantiate():
    """HolisticElection() creates without throw."""
    from livingtree.treellm.holistic_election import HolisticElection
    he = HolisticElection()
    assert he is not None


def test_tree_llm_import():
    """TreeLLM imports and creates without throw."""
    from livingtree.treellm.core import TreeLLM
    llm = TreeLLM()
    assert llm is not None
    assert hasattr(llm, "_providers")
    assert hasattr(llm, "provider_names")


def test_tree_llm_add_provider():
    """Can register a provider to TreeLLM."""
    from livingtree.treellm.core import TreeLLM
    from livingtree.treellm.providers import create_ollama_provider
    llm = TreeLLM()
    provider = create_ollama_provider()
    llm.add_provider(provider)
    assert len(llm.provider_names) > 0


def test_bandit_router_import():
    """ThompsonRouter (bandit routing) imports cleanly."""
    from livingtree.treellm.bandit_router import ThompsonRouter
    assert ThompsonRouter is not None


def test_hub_election_status():
    """After _init_sync, hub has consciousness with election methods."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    hub = IntegrationHub(config=get_config(), lazy=True)
    hub._init_sync()
    con = hub.world.consciousness
    assert con is not None
    # Check that election methods exist
    assert hasattr(con, "_paid_models") or hasattr(con, "provider_names"), \
        "No provider listing method found"
    assert hasattr(con, "_elect_tiers") or hasattr(con, "get_election_status"), \
        "No election method found"


# ── manual integration test (requires API keys) ──

@pytest.mark.skipif(not _has_api_keys(), reason="No API keys configured")
@pytest.mark.asyncio
async def test_manual_election():
    """Manual: full election with real providers. Requires API keys."""
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config
    from livingtree.treellm.holistic_election import HolisticElection

    hub = IntegrationHub(config=get_config(), lazy=False)
    hub._init_sync()
    con = hub.world.consciousness
    assert con is not None

    paid = getattr(con, "_paid_models", [])
    free = getattr(con, "_free_models", [])
    assert len(paid) + len(free) > 0, "No providers available"

    # Run election
    elected = await con._elect() if hasattr(con, "_elect") else await con.elect()
    assert elected, "Election produced no result"
    assert isinstance(elected, str), f"Elected should be str, got {type(elected)}"
