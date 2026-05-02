"""
LivingTree AI Agent — Unified Entry Point
===========================================

基于新 livingtree/ 架构的统一入口。

Usage:
    python -m livingtree server          # 启动完整 API 服务 (FastAPI)
    python -m livingtree client          # 启动桌面客户端 (PyQt6)
    python -m livingtree relay           # 启动中继服务器
    python -m livingtree tracker         # 启动 P2P 追踪器
    python -m livingtree app             # 启动企业应用
    python -m livingtree test            # 运行集成测试
    python -m livingtree bench           # 运行性能基准
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='ignore').decode('ascii'))


def run_server():
    safe_print("[livingtree] Starting LivingTree API Server...")
    from livingtree.server.app import start_server

    host = "0.0.0.0"
    port = 8100

    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        if arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]

    start_server(host=host, port=port, reload=False)


def run_client():
    safe_print("[livingtree] Starting Desktop Client...")
    client_main = os.path.join(PROJECT_ROOT, 'client', 'src', 'main.py')
    args = [sys.executable, client_main] + sys.argv[2:]
    os.execv(sys.executable, args)


def run_relay():
    safe_print("[livingtree] Starting Relay Server...")
    relay_main = os.path.join(PROJECT_ROOT, 'server', 'relay_server', 'main.py')
    if os.path.exists(relay_main):
        os.execv(sys.executable, [sys.executable, relay_main])
    else:
        safe_print("[livingtree] Relay server file not found.")


def run_tracker():
    safe_print("[livingtree] Starting Tracker Server...")
    tracker_main = os.path.join(PROJECT_ROOT, 'server', 'tracker_server.py')
    if os.path.exists(tracker_main):
        os.execv(sys.executable, [sys.executable, tracker_main])
    else:
        safe_print("[livingtree] Tracker server file not found.")


def run_app():
    safe_print("[livingtree] Starting Enterprise App...")
    app_main = os.path.join(PROJECT_ROOT, 'app', 'main.py')
    if os.path.exists(app_main):
        os.execv(sys.executable, [sys.executable, app_main])
    else:
        safe_print("[livingtree] App not found.")


def run_test():
    safe_print("[livingtree] Running integration tests...")
    from livingtree.core.life_engine import LifeEngine
    from livingtree.core.intent.parser import IntentParser
    from livingtree.infrastructure.config import get_config
    from livingtree.core.model.router import get_model_router

    safe_print("  Testing Config...")
    config = get_config()
    assert config.version == "1.0.0"

    safe_print("  Testing IntentParser...")
    parser = IntentParser()
    intent = parser.parse("帮我写一份关于AI安全的报告")
    assert intent.type.value == "writing"

    safe_print("  Testing ModelRouter...")
    router = get_model_router()
    assert router.classify_complexity(0.5) is not None

    safe_print("  Testing LifeEngine...")
    engine = LifeEngine()
    response = engine.handle_request("你好")
    assert response.trace_id
    assert response.text

    safe_print("  Testing LifeEngine health...")
    health = engine.get_health()
    assert health["version"] == "1.0.0"

    safe_print("")
    safe_print("  ALL INTEGRATION TESTS PASSED")


def run_bench():
    safe_print("[livingtree] Running performance benchmark...")
    import time
    from livingtree.core.life_engine import LifeEngine
    from livingtree.core.intent.parser import IntentParser

    test_cases = [
        "你好",
        "帮我写一份报告",
        "用Python实现一个快速排序算法",
        "分析一下人工智能的未来发展趋势",
    ]

    engine = LifeEngine()
    parser = IntentParser()

    safe_print(f"  {'Test Case':<40} {'Intent':<15} {'Complexity':<12} {'Duration(ms)':<15}")
    safe_print("  " + "-" * 82)

    for case in test_cases:
        t0 = time.time()
        intent = parser.parse(case)
        response = engine.handle_request(case)
        duration = (time.time() - t0) * 1000

        safe_print(f"  {case[:38]:<40} {intent.type.value:<15} "
                   f"{intent.complexity:<12.3f} {duration:<15.2f}")

    safe_print("")
    safe_print("  BENCHMARK COMPLETE")


def run_quick():
    """Quick interactive mode — direct LifeEngine session"""
    safe_print("[livingtree] Quick Interactive Mode")
    safe_print("  Type 'quit' to exit.")
    safe_print("")

    from livingtree.core.life_engine import LifeEngine
    engine = LifeEngine()

    while True:
        try:
            user_input = input("You> ").strip()
            if user_input.lower() in ('quit', 'exit', 'q'):
                safe_print("Bye!")
                break
            if not user_input:
                continue

            response = engine.handle_request(user_input)
            safe_print(f"LT> {response.text}")
            safe_print(f"    [trace={response.trace_id}, score={response.learning.score:.2f}]")
        except KeyboardInterrupt:
            safe_print("\nBye!")
            break
        except Exception as e:
            safe_print(f"Error: {e}")


COMMANDS = {
    "server": run_server,
    "client": run_client,
    "relay": run_relay,
    "tracker": run_tracker,
    "app": run_app,
    "test": run_test,
    "bench": run_bench,
    "quick": run_quick,
}


def main():
    if len(sys.argv) < 2:
        safe_print("LivingTree AI Agent v1.0.0")
        safe_print(f"Available commands: {', '.join(COMMANDS.keys())}")
        safe_print("")
        safe_print("Quick start: python -m livingtree server")
        return

    cmd = sys.argv[1].lower()
    handler = COMMANDS.get(cmd)

    if handler:
        handler()
    else:
        safe_print(f"Unknown command: {cmd}")
        safe_print(f"Available: {', '.join(COMMANDS.keys())}")


if __name__ == "__main__":
    main()
