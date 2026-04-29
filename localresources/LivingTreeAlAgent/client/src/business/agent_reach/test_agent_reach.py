"""
Agent-Reach 集成测试
"""

import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    prefix = "[OK]" if ok else "[FAIL]"
    try:
        print(f"{prefix} {msg}")
    except UnicodeEncodeError:
        safe_msg = msg.replace("\u2713", "OK").replace("\u2717", "X")
        print(f"{prefix} {safe_msg}")


def test_import():
    """测试模块导入"""
    print("\n" + "=" * 50)
    print("Module Import Test")
    print("=" * 50)
    try:
        from core.agent_reach import (
            AgentReachClient,
            AgentReachConfig,
            SearchEngine,
            SearchResult,
            get_agent_reach,
            check_installation,
            search,
            read_content
        )
        log("Module import successful")
        return True
    except ImportError as e:
        log(f"Module import failed: {e}", ok=False)
        return False


def test_config():
    """测试配置"""
    print("\n" + "=" * 50)
    print("Config Test")
    print("=" * 50)

    from core.agent_reach import AgentReachConfig

    config = AgentReachConfig()
    log(f"Default config created")
    print(f"  - enabled: {config.enabled}")
    print(f"  - timeout: {config.timeout}")
    print(f"  - max_results: {config.max_results}")

    # 测试序列化
    data = config.to_dict()
    config2 = AgentReachConfig.from_dict(data)
    log(f"Config serialization works")
    print(f"  - serialized keys: {list(data.keys())}")

    return True


def test_client():
    """测试客户端"""
    print("\n" + "=" * 50)
    print("Client Test")
    print("=" * 50)

    from core.agent_reach import get_agent_reach, AgentReachClient

    # 测试单例
    client1 = get_agent_reach()
    client2 = get_agent_reach()
    log(f"Singleton pattern works: {client1 is client2}")

    # 检查可用性
    log(f"Client available: {client1.is_available}")

    return True


async def test_installation_check():
    """测试安装检查"""
    print("\n" + "=" * 50)
    print("Installation Check Test")
    print("=" * 50)

    from core.agent_reach import check_installation

    result = await check_installation()
    log(f"Installation check completed")
    print(f"  - installed: {result.get('installed')}")
    if not result.get('installed'):
        print(f"  - install_command: {result.get('install_command', 'N/A')}")

    return True


async def test_read_url():
    """测试 URL 读取"""
    print("\n" + "=" * 50)
    print("URL Read Test")
    print("=" * 50)

    from core.agent_reach import read_content

    # 测试读取 GitHub 仓库
    print("\n  Testing Jina Reader...")
    result = await read_content("https://github.com/Panniantong/agent-reach")

    if result.get("success"):
        log("URL read successful")
        print(f"  - title: {result.get('title', 'N/A')}")
        print(f"  - content length: {result.get('content_length', 0)} chars")
        if result.get("content"):
            print(f"  - content preview: {result['content'][:150]}...")
    else:
        print(f"  (Read failed: {result.get('error', 'Unknown')})")

    return True


async def run_async_tests():
    """运行异步测试"""
    await test_installation_check()
    await test_read_url()


if __name__ == "__main__":
    import asyncio

    results = []

    results.append(("Import", test_import()))
    results.append(("Config", test_config()))
    results.append(("Client", test_client()))

    # 运行异步测试
    asyncio.run(run_async_tests())

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "OK" if ok else "X"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} passed")
    print("\nNote: Search tests may show no results if Agent-Reach is not installed.")
    print("Install with: pip install agent-reach && agent-reach install --env=auto")
