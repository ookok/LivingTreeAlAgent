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
    TUI = "tui"  # deprecated — kept for backward compat


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
    """Run web server — UI available immediately, hub initializes in background."""
    from ..api.server import create_app
    import uvicorn

    hub = IntegrationHub(config)
    cfg = hub.config
    app = create_app(hub=hub, config=cfg)

    host = cfg.api.host
    port = cfg.api.port

    # Start hub in background, server is available immediately
    app.state.hub_init_task = asyncio.create_task(_init_hub_with_progress(hub))

    print(f"\n{'='*50}")
    print(f"  🌳 LivingTree AI Agent v2.1")
    print(f"  Web UI:  http://{host}:{port}")
    print(f"  API:     http://{host}:{port}/api/health")
    print(f"  {'='*50}")
    print(f"  Hub initializing in background...")
    print(f"  Open browser to see startup progress\n")

    config_kwargs = {
        "app": app, "host": host, "port": port,
        "log_level": cfg.observability.log_level.lower(),
        # ── Performance tuning ──
        "backlog": 2048,                        # Connection queue
        "limit_concurrency": 1000,              # Max concurrent connections
        "limit_max_requests": 10000,            # Restart worker after N requests (prevent memory leak)
        "timeout_keep_alive": 30,               # Keep-alive timeout (seconds)
        "timeout_graceful_shutdown": 10,        # Graceful shutdown timeout
        "ws_max_size": 16 * 1024 * 1024,       # 16MB WebSocket max
        "h11_max_incomplete_event_size": 16384, # HTTP parser buffer
    }
    if cfg.api.workers > 1:
        config_kwargs["workers"] = cfg.api.workers
    else:
        # Default to CPU count - 1 (min 1) for better concurrency
        import os as _os
        cpu_count = _os.cpu_count() or 4
        config_kwargs["workers"] = max(1, cpu_count - 1)

    server = uvicorn.Server(uvicorn.Config(**config_kwargs))
    try:
        await server.serve()
    finally:
        if app.state.hub_init_task:
            app.state.hub_init_task.cancel()
        try:
            await hub.shutdown()
        except Exception:
            pass


async def _init_hub_with_progress(hub):
    """Initialize hub with progress tracking."""
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()

    hub._boot_progress = {"stage": "starting", "pct": 0, "detail": "创建 Hub..."}
    await _asyncio.sleep(0.1)
    hub._boot_progress = {"stage": "loading", "pct": 10, "detail": "加载配置..."}
    await _asyncio.sleep(0.1)

    def _sync_init():
        hub._boot_progress = {"stage": "loading", "pct": 20, "detail": "初始化同步组件..."}
        hub._init_sync()

    hub._boot_progress = {"stage": "loading", "pct": 15, "detail": "创建生活世界..."}
    await loop.run_in_executor(None, _sync_init)

    hub._boot_progress = {"stage": "loading", "pct": 80, "detail": "启动异步服务..."}
    await hub._init_async()

    hub._boot_progress = {"stage": "ready", "pct": 100, "detail": "系统就绪"}
    if hasattr(hub, '_ready_event'):
        hub._ready_event.set()
    hub._started = True


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
