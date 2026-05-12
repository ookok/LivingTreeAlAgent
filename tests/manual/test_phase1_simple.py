"""Phase 1: Simple Module Tests — Bottom-up behavioral verification.
Runs actual module code, not just imports. Tests fundamental operations.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════
# LAYER 0: CONFIG
# ═══════════════════════════════════════════

def test_config():
    from livingtree.config.settings import LTAIConfig, ModelConfig, get_config

    cfg = get_config()
    assert cfg.version == "2.0.0"
    assert cfg.api.port == 8100
    assert cfg.model.flash_model == "deepseek/deepseek-v4-flash"

    mc = ModelConfig()
    assert mc.flash_model == "deepseek/deepseek-v4-flash"

    for attr in ["model", "api", "observability", "network", "cell", "execution"]:
        assert getattr(cfg, attr, None) is not None, f"cfg.{attr} missing"

    print("  [PASS] Config layer")

# ═══════════════════════════════════════════
# LAYER 1: KNOWLEDGE
# ═══════════════════════════════════════════

def test_knowledge():
    from livingtree.knowledge import KnowledgeBase, VectorStore

    kb = KnowledgeBase()
    assert kb is not None

    vs = VectorStore()
    assert vs is not None

    print("  [PASS] KnowledgeBase + VectorStore")

def test_struct_memory():
    from livingtree.knowledge.struct_mem import get_struct_mem, EventEntry
    import time

    mem = get_struct_mem()
    assert mem is not None
    assert len(mem._entries) >= 0

    # Store via buffer (correct API)
    entry = EventEntry(
        id="test_key",
        session_id="test_session",
        timestamp=datetime.fromtimestamp(time.time(), timezone.utc).isoformat(),
        role="user",
        content="Hello World",
    )
    mem._buffer.add(entry)
    assert len(mem._buffer.entries) > 0
    assert mem._buffer.entries[-1].id == "test_key"
    assert mem._buffer.entries[-1].content == "Hello World"

    print("  [PASS] StructMemory buffer add/retrieve")

# ═══════════════════════════════════════════
# LAYER 2: TreeLLM
# ═══════════════════════════════════════════

def test_treellm():
    from livingtree.treellm.core import TreeLLM
    from livingtree.config.settings import get_config

    cfg = get_config()
    llm = TreeLLM()
    assert llm is not None

    # Add Ollama provider (local)
    from livingtree.treellm.providers import create_ollama_provider
    llm.add_provider(create_ollama_provider())
    assert len(llm._providers) >= 1
    assert "ollama" in llm._providers

    print(f"  [PASS] TreeLLM with {len(llm._providers)} provider(s)")

# ═══════════════════════════════════════════
# LAYER 3: CAPABILITY
# ═══════════════════════════════════════════

def test_capability():
    from livingtree.capability import SkillFactory, ToolMarket, SkillEntry
    from livingtree.capability.skill_buckets import CapabilityBucket

    sf = SkillFactory()
    assert sf is not None

    # Verify capability bucket enum
    assert CapabilityBucket.REASONING == "reasoning"
    assert CapabilityBucket.CODE == "code"

    # Verify SkillEntry model
    entry = SkillEntry(
        module_name="test_skill",
        bucket=CapabilityBucket.CODE,
        description="Test skill for verification",
    )
    assert entry.module_name == "test_skill"
    assert entry.bucket == CapabilityBucket.CODE

    print("  [PASS] SkillFactory + SkillEntry + CapabilityBucket")

# ═══════════════════════════════════════════
# LAYER 4: EXECUTION
# ═══════════════════════════════════════════

def test_execution():
    from livingtree.execution import TaskPlanner, Orchestrator, SelfHealer, CostAware

    tp = TaskPlanner(max_depth=3)
    assert tp is not None

    orch = Orchestrator(max_agents=5, max_parallel=2)
    assert orch is not None

    sh = SelfHealer(check_interval=60)
    assert sh is not None

    ca = CostAware(daily_budget_tokens=500_000)
    assert ca is not None

    print("  [PASS] TaskPlanner + Orchestrator + SelfHealer + CostAware")

# ═══════════════════════════════════════════
# LAYER 5: DNA
# ═══════════════════════════════════════════

def test_dna_life_engine():
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    hub = IntegrationHub(config=get_config(), lazy=False)
    hub._init_sync()

    # Verify world wiring
    assert hub.world is not None
    assert hub.world.consciousness is not None
    assert hub.world.knowledge_base is not None
    assert hub.world.task_planner is not None
    assert hub.world.orchestrator is not None
    assert hub.world.self_healer is not None
    assert hub.world.skill_factory is not None
    assert hub.world.tool_market is not None
    assert hub.engine is not None

    print("  [PASS] Hub init + World wiring (8 components verified)")

# ═══════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 1: Simple Module Tests (Bottom-Up)")
    print("=" * 60)

    tests = [
        ("Layer 0: Config", test_config),
        ("Layer 1: KnowledgeBase", test_knowledge),
        ("Layer 1: StructMemory", test_struct_memory),
        ("Layer 2: TreeLLM", test_treellm),
        ("Layer 3: Capability", test_capability),
        ("Layer 4: Execution", test_execution),
        ("Layer 5: DNA/LifeEngine", test_dna_life_engine),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")

    print(f"\n  Results: {passed} passed, {failed} failed")
    print("=" * 60)
