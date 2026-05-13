"""Minimal init trace tests — verify key init chain steps work.

Tests that each component of the async init pipeline can be imported
and instantiated without throwing. This is the "smoke test" of the init chain.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestInitChain:
    """Sequential tests for the hub initialization chain."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from livingtree.integration.hub import IntegrationHub
        from livingtree.config.settings import get_config
        self.hub = IntegrationHub(config=get_config(), lazy=True)
        self.hub._init_sync()

    def test_sync_init_basics(self):
        """_init_sync wires basic components."""
        assert self.hub.world is not None
        assert self.hub.world.consciousness is not None
        con = self.hub.world.consciousness
        assert hasattr(con, "_paid_models") or hasattr(con, "_free_models")

    def test_secret_vault(self):
        """Secret vault loads without crashing."""
        from livingtree.config.secrets import get_secret_vault
        vault = get_secret_vault()
        vault._ensure_loaded()
        assert vault is not None

    def test_async_disk_import(self):
        """Core async_disk module imports."""
        from livingtree.core.async_disk import get_disk
        assert get_disk is not None

    def test_pkg_manager_import(self):
        """Package manager imports."""
        from livingtree.integration.pkg_manager import ensure_environment
        assert ensure_environment is not None

    def test_self_healer_component(self):
        """SelfHealer is wired after init."""
        assert self.hub.world.self_healer is not None

    def test_node_component(self):
        """Node is wired after init."""
        assert self.hub.world.node is not None

    def test_model_registry_import(self):
        """Model registry imports correctly."""
        from livingtree.treellm.model_registry import ModelRegistry
        registry = ModelRegistry.instance()
        assert registry is not None

    def test_skill_factory_wired(self):
        """SkillFactory is wired."""
        assert self.hub.world.skill_factory is not None

    def test_tool_market_wired(self):
        """ToolMarket is wired."""
        assert self.hub.world.tool_market is not None

    def test_knowledge_base_wired(self):
        """KnowledgeBase is wired."""
        assert self.hub.world.knowledge_base is not None

    def test_vector_store_wired(self):
        """VectorStore is wired."""
        assert self.hub.world.vector_store is not None

    def test_code_graph_wired(self):
        """CodeGraph is wired."""
        assert self.hub.world.code_graph is not None

    def test_orchestrator_wired(self):
        """Orchestrator is wired."""
        assert self.hub.world.orchestrator is not None

    def test_no_import_crash_full_chain(self):
        """The full init chain imports all key submodules without crashing."""
        # These are the modules that were historically broken
        modules = [
            "livingtree.treellm.classifier",
            "livingtree.capability.tool_synthesis",
            "livingtree.capability.tool_meta",
            "livingtree.lsp.lsp_manager",
            "livingtree.dna.expert_role_manager",
            "livingtree.dna.unified_skill_system",
            "livingtree.core.unified_registry",
            "livingtree.core.execution_pipeline",
        ]
        for mod_name in modules:
            try:
                import importlib
                importlib.import_module(mod_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {mod_name}: {e}")
