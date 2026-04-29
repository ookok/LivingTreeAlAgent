"""
Chrome Bridge 完整功能测试脚本
测试内容：
1. 千问QuarkChat一键登录+提问
2. GitHub仓库README读取
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from client.src.business.chrome_bridge.credential_manager import get_credential_manager
from client.src.business.chrome_bridge.tools.chrome_bridge_tool import ChromeBridgeTool


async def test_qianwen_login_and_chat():
    """测试千问QuarkChat一键登录和提问"""
    print("=" * 50)
    print("测试1: 千问QuarkChat一键登录+提问")
    print("=" * 50)

    # 1. 先保存千问凭证（首次运行时需要手动输入）
    cred_mgr = get_credential_manager()
    domain = "qianwen.com"

    if not cred_mgr.load_credential(domain):
        print(f"首次运行，请先保存{domain}的登录凭证:")
        username = input("用户名: ")
        password = input("密码: ")
        cred_mgr.save_credential(domain, username, password)
        print(f"凭证已保存到本地加密存储")

    # 2. 创建Chrome桥接工具
    tool = ChromeBridgeTool(debug_port=9222, headless=False)

    # 3. 一键登录千问
    print("\n正在执行一键登录...")
    login_result = tool.execute(
        action="login",
        domain=domain,
        username_selector="input[type='text'], input[placeholder*='手机']",
        password_selector="input[type='password']",
        login_button_selector="button[type='submit'], .login-btn"
    )

    if not login_result.get("success"):
        print(f"登录失败: {login_result.get('error')}")
        return False

    print(f"登录成功! 用户名: {login_result.get('data', {}).get('username')}")

    # 4. 导航到QuarkChat页面
    print("\n正在导航到QuarkChat页面...")
    nav_result = tool.execute(
        action="navigate",
        url="https://www.qianwen.com/quarkchat"
    )

    if not nav_result.get("success"):
        print(f"导航失败: {nav_result.get('error')}")
        return False

    # 5. 语义操作：输入问题并发送
    print("\n正在使用语义操作输入问题...")
    chat_result = tool.execute(
        action="semantic_operate",
        instruction="在输入框中输入'你是什么大模型?'，然后点击发送按钮",
        url="https://www.qianwen.com/quarkchat"
    )

    if not chat_result.get("success"):
        print(f"语义操作失败: {chat_result.get('error')}")
        return False

    print(f"操作完成，执行了{chat_result.get('data', {}).get('operations_executed')}个操作")

    # 6. 等待回复并提取内容
    print("\n等待AI回复(10秒)...")
    await asyncio.sleep(10)

    print("\n正在提取回复内容...")
    extract_result = tool.execute(
        action="extract",
        url="https://www.qianwen.com/quarkchat"
    )

    if extract_result.get("success"):
        data = extract_result.get("data", {})
        print(f"\n千问回复内容:")
        print("-" * 50)
        print(data.get("last_reply", "未获取到回复内容"))
        print("-" * 50)
        return True
    else:
        print(f"提取内容失败: {extract_result.get('error')}")
        return False


async def test_github_readme():
    """测试GitHub仓库README读取"""
    print("\n" + "=" * 50)
    print("测试2: GitHub仓库README读取")
    print("=" * 50)

    # 1. 创建Chrome桥接工具
    tool = ChromeBridgeTool(debug_port=9222, headless=False)

    # 2. 导航到GitHub仓库页面
    repo_url = "https://github.com/ookok/LivingTreeAlAgent"
    print(f"\n正在导航到GitHub仓库: {repo_url}")

    nav_result = tool.execute(
        action="navigate",
        url=repo_url
    )

    if not nav_result.get("success"):
        print(f"导航失败: {nav_result.get('error')}")
        return False

    # 3. 提取仓库内容和README
    print("\n正在提取仓库内容和README...")
    extract_result = tool.execute(
        action="extract",
        url=repo_url
    )

    if not extract_result.get("success"):
        print(f"提取失败: {extract_result.get('error')}")
        return False

    data = extract_result.get("data", {})
    print(f"\n仓库名称: {data.get('name')}")
    print(f"仓库描述: {data.get('description')}")
    print(f"Stars: {data.get('stars')}, Forks: {data.get('forks')}")
    print(f"\nREADME内容预览:")
    print("-" * 50)
    readme = data.get("readme", "")
    print(readme[:500] + "..." if len(readme) > 500 else readme)
    print("-" * 50)
    return True


async def main():
    """主测试函数"""
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    print("Chrome Bridge 自动化测试开始")
    print("请确保:")
    print("1. Chrome已启动并开启远程调试端口: chrome --remote-debugging-port=9222")
    print("2. 已安装所有依赖: pip install cryptography loguru websockets")
    print()

    input("按Enter键开始测试...")

    # 测试千问
    qianwen_ok = await test_qianwen_login_and_chat()

    # 测试GitHub
    github_ok = await test_github_readme()

    # 测试结果汇总
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"千问QuarkChat测试: {'通过' if qianwen_ok else '失败'}")
    print(f"GitHub README测试: {'通过' if github_ok else '失败'}")

    if qianwen_ok and github_ok:
        print("\n所有测试通过! Chrome Bridge功能正常")
    else:
        print("\n部分测试失败，请检查日志")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
