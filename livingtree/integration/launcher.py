"""Service launcher and lifecycle management for the LivingTree platform.

Provides different launch modes:
- client: Interactive CLI chat client
- server: FastAPI server with WebSocket
- test: Run integration tests
- quick: Single quick interaction
"""

from __future__ import annotations

import asyncio
import enum
import sys
from typing import Optional

from loguru import logger

from ..config import LTAIConfig, get_config
from .hub import IntegrationHub


class LaunchMode(enum.Enum):
    CLIENT = "client"
    SERVER = "server"
    TEST = "test"
    QUICK = "quick"
    CHECK = "check"


def launch(mode: LaunchMode, config: Optional[LTAIConfig] = None) -> int:
    """Launch the LivingTree platform in the specified mode.

    Returns exit code (0 = success).
    """
    logger.info(f"LivingTree v2.0.0 launching in {mode.value} mode")

    try:
        if mode == LaunchMode.CLIENT:
            asyncio.run(_run_client(config))
        elif mode == LaunchMode.SERVER:
            asyncio.run(_run_server(config))
        elif mode == LaunchMode.TEST:
            asyncio.run(_run_tests(config))
        elif mode == LaunchMode.QUICK:
            asyncio.run(_run_quick(config))
        elif mode == LaunchMode.CHECK:
            asyncio.run(_run_check(config))
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Launch failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def _run_client(config: Optional[LTAIConfig] = None) -> None:
    """Run interactive CLI client."""
    hub = IntegrationHub(config)
    await hub.start()

    print("\n" + "=" * 60)
    print("  LivingTree Digital Life Form v2.0.0")
    print("  Type 'help' for commands, 'quit' to exit")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            break

        if user_input.lower() == "help":
            _print_help()
            continue

        if user_input.lower() == "status":
            status = hub.get_status()
            print(f"\n{_format_status(status)}\n")
            continue

        if user_input.lower() == "peers":
            peers = await hub.discover_peers()
            print(f"\nPeers: {len(peers)} discovered\n")
            continue

        # Process through life engine
        print(f"\nProcessing: {user_input[:80]}...\n")
        try:
            result = await hub.chat(user_input)
            print(f"[Session: {result['session_id']}]")
            print(f"[Intent: {result['intent'][:100]}...]" if result.get('intent') else "")
            print(f"[Plan: {len(result.get('plan', []))} steps]")
            print(f"[Success rate: {result.get('success_rate', 0):.0%}]")
            print(f"[Generation: {result.get('generation', 0)}]")
            print(f"[Mutations: {result.get('mutations', 0)}]")
            print(f"[Reflections: {len(result.get('reflections', []))}]")
            print()
        except Exception as e:
            print(f"[Error: {e}]")
            import traceback
            traceback.print_exc()

    await hub.shutdown()
    print("\nLivingTree shutdown complete. Goodbye.")


async def _run_server(config: Optional[LTAIConfig] = None) -> None:
    """Run FastAPI server."""
    from ..api.server import create_app
    import uvicorn

    hub = IntegrationHub(config)
    await hub.start()

    cfg = hub.config
    app = create_app(hub=hub)

    config_kwargs = {
        "app": app,
        "host": cfg.api.host,
        "port": cfg.api.port,
        "log_level": cfg.observability.log_level.lower(),
    }
    if cfg.api.workers > 1:
        config_kwargs["workers"] = cfg.api.workers

    logger.info(f"Server starting on http://{cfg.api.host}:{cfg.api.port}")
    server = uvicorn.Server(uvicorn.Config(**config_kwargs))
    try:
        await server.serve()
    finally:
        await hub.shutdown()


async def _run_tests(config: Optional[LTAIConfig] = None) -> None:
    """Run integration tests."""
    hub = IntegrationHub(config)
    await hub.start()

    passed = 0
    failed = 0
    tests = []

    # Test 1: Basic chat
    try:
        result = await hub.chat("你好，请做一个简单的任务")
        assert result["session_id"], "No session ID"
        passed += 1
        tests.append(("Basic chat", "PASS"))
    except Exception as e:
        failed += 1
        tests.append(("Basic chat", f"FAIL: {e}"))

    # Test 2: Task planning
    try:
        plan = await hub.task_planner.decompose_task("生成环评报告", domain="环评报告")
        assert len(plan) > 0, "Empty plan"
        passed += 1
        tests.append(("Task planning", "PASS"))
    except Exception as e:
        failed += 1
        tests.append(("Task planning", f"FAIL: {e}"))

    # Test 3: Knowledge base
    try:
        from ..knowledge.knowledge_base import Document
        doc_id = hub.knowledge_base.add_knowledge(
            Document(title="Test Doc", content="Test content for knowledge base")
        )
        assert doc_id, "No document ID"
        results = hub.knowledge_base.search("Test")
        assert len(results) > 0, "No search results"
        passed += 1
        tests.append(("Knowledge base", "PASS"))
    except Exception as e:
        failed += 1
        tests.append(("Knowledge base", f"FAIL: {e}"))

    # Test 4: Cell registration
    try:
        from ..cell.cell_ai import CellAI
        cell = CellAI(name="test_cell")
        hub.cell_registry.register(cell)
        cells = hub.cell_registry.discover()
        assert len(cells) > 0, "No cells registered"
        passed += 1
        tests.append(("Cell registration", "PASS"))
    except Exception as e:
        failed += 1
        tests.append(("Cell registration", f"FAIL: {e}"))

    # Test 5: Status
    try:
        status = hub.get_status()
        assert status["version"], "No version"
        passed += 1
        tests.append(("Status check", "PASS"))
    except Exception as e:
        failed += 1
        tests.append(("Status check", f"FAIL: {e}"))

    print("\n" + "=" * 50)
    print("  LivingTree Integration Tests")
    print("=" * 50)
    for name, result in tests:
        status_icon = "OK" if "PASS" in result else "FAIL"
        print(f"  [{status_icon}] {name}: {result}")
    print(f"\n  Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
    print("=" * 50)

    await hub.shutdown()


async def _run_quick(config: Optional[LTAIConfig] = None) -> None:
    """Run a single quick interaction."""
    hub = IntegrationHub(config)
    await hub.start()

    # Use command-line args or stdin
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "请介绍一下你自己的能力"
    print(f"\n> {msg}\n")

    result = await hub.chat(msg)
    print(f"Session: {result['session_id']}")
    print(f"Intent: {result['intent']}")
    print(f"Plan: {len(result['plan'])} steps")
    print(f"Generation: {result['generation']}")

    await hub.shutdown()


async def _run_check(config: Optional[LTAIConfig] = None) -> None:
    """Run environment check."""
    hub = IntegrationHub(config)

    print("\n" + "=" * 50)
    print("  LivingTree Environment Check")
    print("=" * 50)

    checks = [
        ("Python Version", sys.version),
        ("Config Loaded", str(hub.config.version)),
        ("DNA Layer", "OK" if hub.life_engine else "MISSING"),
        ("Cell Registry", "OK" if hub.cell_registry else "MISSING"),
        ("Knowledge Base", "OK" if hub.knowledge_base else "MISSING"),
        ("Skill Factory", "OK" if hub.skill_factory else "MISSING"),
        ("Network Node", "OK" if hub.node else "MISSING"),
        ("Orchestrator", "OK" if hub.orchestrator else "MISSING"),
        ("Self Healer", "OK" if hub.self_healer else "MISSING"),
    ]

    for name, status in checks:
        icon = "OK" if "OK" in status else "??" if "MISSING" not in status else "XX"
        print(f"  [{icon}] {name}: {status}")
    print("=" * 50 + "\n")


def _print_help() -> None:
    print("""
Commands:
  <message>    Send a message to the life engine
  status       Display engine status
  peers        Discover network peers
  help         Show this help
  quit/exit    Shutdown and exit

Examples:
  > 帮我生成一份环评报告
  > 分析这个项目的环境风险
  > 训练一个专家模型
""")

def _format_status(status: dict) -> str:
    lines = []
    life = status.get("life_engine", {})
    cells = status.get("cells", {})
    net = status.get("network", {})
    orch = status.get("orchestrator", {})
    heal = status.get("healer", {})

    lines.append(f"  Life Engine: gen={life.get('generation', 0)}, mutations={life.get('mutations', 0)}")
    lines.append(f"  Cells: {cells.get('registered', 0)} registered")
    lines.append(f"  Network: {net.get('status', 'unknown')}")
    lines.append(f"  Orchestrator: {orch.get('total_agents', 0)} agents")
    lines.append(f"  Healer: {'active' if heal.get('running') else 'inactive'}")
    return "\n".join(lines)
