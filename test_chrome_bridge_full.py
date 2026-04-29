"""
完整功能测试脚本
运行前确保：
1. Chrome 已启动并开启远程调试：chrome --remote-debugging-port=9222
2. 千问已手动登录（你已确认）
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from client.src.business.chrome_bridge.tools.chrome_bridge_tool import get_chrome_bridge_tool


async def test_qianwen_quarkchat():
    """测试1: 访问千问QuarkChat，提问并获取回复"""
    print("=" * 60)
    print("测试1: 千问QuarkChat 提问测试")
    print("=" * 60)

    tool = get_chrome_bridge_tool()

    # 1. 导航到QuarkChat
    print("\n[1/4] 正在导航到 https://www.qianwen.com/quarkchat ...")
    result = tool.execute("navigate", url="https://www.qianwen.com/quarkchat")
    if not result.get("success"):
        print(f"❌ 导航失败: {result.get('error')}")
        return False
    print(f"✅ 导航成功: {result.get('data', {}).get('title', '')}")

    # 等待页面完全加载
    print("[2/4] 等待页面加载完成 (5秒)...")
    await asyncio.sleep(5)

    # 2. 语义操作：输入问题并发送
    print("\n[3/4] 正在通过语义操作输入问题并发送...")
    result = tool.execute(
        "semantic_operate",
        instruction="在输入框中输入'你是什么大模型?'，然后点击发送按钮",
        url="https://www.qianwen.com/quarkchat"
    )
    if not result.get("success"):
        print(f"❌ 语义操作失败: {result.get('error')}")
        return False
    print(f"✅ 语义操作成功，执行了 {result.get('data', {}).get('operations_executed', 0)} 个操作")

    # 3. 等待AI回复
    print("\n[4/4] 等待AI回复 (10秒)...")
    await asyncio.sleep(10)

    # 4. 提取回复内容
    print("\n正在提取AI回复内容...")
    result = tool.execute(
        "extract",
        url="https://www.qianwen.com/quarkchat"
    )
    if result.get("success"):
        data = result.get("data", {})
        reply = data.get("last_reply", "")
        print(f"\n✅ 千问回复内容:")
        print("-" * 60)
        print(reply[:500] if reply else "（未获取到回复，页面可能还在加载）")
        print("-" * 60)
        return True
    else:
        print(f"❌ 提取内容失败: {result.get('error')}")
        return False


async def test_github_readme():
    """测试2: 访问GitHub仓库，读取README"""
    print("\n" + "=" * 60)
    print("测试2: GitHub 仓库 README 读取测试")
    print("=" * 60)

    tool = get_chrome_bridge_tool()

    # 1. 导航到GitHub仓库
    repo_url = "https://github.com/ookok/LivingTreeAlAgent"
    print(f"\n[1/3] 正在导航到 {repo_url} ...")
    result = tool.execute("navigate", url=repo_url)
    if not result.get("success"):
        print(f"❌ 导航失败: {result.get('error')}")
        return False
    print(f"✅ 导航成功: {result.get('data', {}).get('title', '')}")

    # 2. 等待页面加载
    print("\n[2/3] 等待页面加载完成 (3秒)...")
    await asyncio.sleep(3)

    # 3. 提取仓库内容和README
    print("\n[3/3] 正在提取仓库信息和README...")
    result = tool.execute("extract", url=repo_url)
    if result.get("success"):
        data = result.get("data", {})
        print(f"\n✅ 仓库信息:")
        print(f"  名称: {data.get('name', 'N/A')}")
        print(f"  描述: {data.get('description', 'N/A')}")
        print(f"  Stars: {data.get('stars', 'N/A')}, Forks: {data.get('forks', 'N/A')}")
        readme = data.get("readme", "")
        print(f"\n  README 内容预览 (前500字符):")
        print("-" * 60)
        print(readme[:500] if readme else "（未找到README内容）")
        print("..." if len(readme) > 500 else "")
        print("-" * 60)
        return True
    else:
        print(f"❌ 提取失败: {result.get('error')}")
        return False


async def main():
    """主测试函数"""
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # 只显示警告和错误

    print("Chrome Bridge 自动化测试")
    print("=" * 60)
    print("前提条件:")
    print("  1. Chrome 已启动并开启远程调试 (--remote-debugging-port=9222)")
    print("  2. 千问已登录")
    print()

    # 测试千问QuarkChat
    qwen_ok = await test_qianwen_quarkchat()

    # 测试GitHub README
    github_ok = await test_github_readme()

    # 测试结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"千问QuarkChat测试: {'✅ 通过' if qwen_ok else '❌ 失败'}")
    print(f"GitHub README测试:  {'✅ 通过' if github_ok else '❌ 失败'}")

    if qwen_ok and github_ok:
        print("\n🎉 所有测试通过! Chrome Bridge 功能正常")
    else:
        print("\n⚠️ 部分测试失败，请检查上面的错误信息")


if __name__ == "__main__":
    asyncio.run(main())
