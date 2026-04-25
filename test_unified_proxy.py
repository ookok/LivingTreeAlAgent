# -*- coding: utf-8 -*-
"""
统一代理配置测试
================

测试功能：
1. 统一代理设置
2. GitHub 搜索
3. 搜索源管理
"""

import asyncio
import sys
import os

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_unified_config():
    """测试统一配置"""
    print("=" * 50)
    print("Testing Unified Proxy Config")
    print("=" * 50)

    from client.src.business.unified_proxy_config import UnifiedProxyConfig, SearchSource

    # 获取单例
    config = UnifiedProxyConfig.get_instance()

    # 设置代理
    print("\n1. Setting proxy...")
    config.set_proxy("http://127.0.0.1:7890")
    print(f"   Proxy: {config.get_proxy()}")
    print(f"   Enabled: {config.is_enabled()}")

    # 设置 GitHub Token
    print("\n2. Setting GitHub Token...")
    config.set_github_token("ghp_test_token_xxx")
    print(f"   Token: {config.get_github_token()[:10]}...")

    # 管理搜索源
    print("\n3. Managing search sources...")
    sources = config.get_enabled_sources()
    print(f"   Enabled: {[s.value for s in sources]}")

    # 禁用 GitHub
    config.disable_source(SearchSource.GITHUB)
    sources = config.get_enabled_sources()
    print(f"   After disabling GitHub: {[s.value for s in sources]}")

    # 重新启用
    config.enable_source(SearchSource.GITHUB)
    sources = config.get_enabled_sources()
    print(f"   After re-enabling: {[s.value for s in sources]}")

    # 导出环境变量
    print("\n4. Exporting env vars...")
    env_vars = config.export_env_vars()
    for key, value in env_vars.items():
        print(f"   {key}={value}")

    # 配置摘要
    print("\n5. Config summary...")
    summary = config.get_config_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")

    print("\n[PASS] Unified config test completed!")


async def test_github_search():
    """测试 GitHub 搜索"""
    print("\n" + "=" * 50)
    print("Testing GitHub Search")
    print("=" * 50)

    from client.src.business.unified_proxy_config import UnifiedProxyConfig

    config = UnifiedProxyConfig.get_instance()

    # 设置 GitHub Token（如果没有，可以使用无 Token 搜索）
    if not config.get_github_token():
        token = input("\nEnter GitHub Token (or press Enter to skip): ").strip()
        if token:
            config.set_github_token(token)

    # 执行搜索
    query = "python async programming"
    print(f"\nSearching: {query}")

    results = await asyncio.to_thread(config.search_github, query, 5)

    if results:
        print(f"\n[OK] Found {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            print(f"   {r['snippet'][:60]}..." if r['snippet'] else "   (no description)")
            print(f"   Stars: {r['score']} | {r['url']}")
    else:
        print("\n[FAIL] No results found")

    return results


def test_market_whitelist():
    """测试市场白名单"""
    print("\n" + "=" * 50)
    print("测试市场白名单")
    print("=" * 50)

    from client.src.business.app_proxy_config import MarketWhitelist

    # 测试 GitHub URL
    test_urls = [
        "https://github.com/microsoft/vscode",
        "https://api.github.com/search/repositories",
        "https://huggingface.co/transformers",
        "https://openrouter.ai/api/v1/models",
        "https://duckduckgo.com/?q=python",
    ]

    print("\n检查 URL 白名单:")
    for url in test_urls:
        market = MarketWhitelist.check_url(url)
        is_github = MarketWhitelist.is_github_url(url)
        print(f"   {url}")
        print(f"   -> 市场: {market}, GitHub: {is_github}")

    # 获取所有域名
    print("\n所有白名单域名:")
    domains = MarketWhitelist.get_all_domains()
    for d in sorted(domains):
        print(f"   - {d}")


def main():
    """主函数"""
    print("\n[START] Testing Unified Proxy Config...\n")

    # 测试统一配置
    test_unified_config()

    # 测试 GitHub 搜索
    results = asyncio.run(test_github_search())

    # 测试市场白名单
    test_market_whitelist()

    print("\n" + "=" * 50)
    print("[DONE] All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
