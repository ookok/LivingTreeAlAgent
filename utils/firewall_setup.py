# utils/firewall_setup.py
# 防火墙设置工具 - 命令行/脚本调用

"""
防火墙设置工具

用法:
    python -m utils.firewall_setup --add-rules     # 添加防火墙规则
    python -m utils.firewall_setup --remove-rules  # 移除防火墙规则
    python -m utils.firewall_setup --status       # 查看防火墙状态
    python -m utils.firewall_setup --check         # 检查规则是否存在
"""

import sys
import json
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.security import get_firewall_manager, FirewallRule


def add_all_rules():
    """添加所有防火墙规则"""
    print("正在添加 Living Tree AI 防火墙规则...")

    manager = get_firewall_manager()

    # 检查管理员权限
    if not manager.is_admin():
        print("⚠️  警告: 需要管理员权限才能修改防火墙规则")
        print("请以管理员身份运行此脚本")
        return False

    success, message = manager.add_app_rules()

    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")

    return success


def remove_all_rules():
    """移除所有防火墙规则"""
    print("正在移除 Living Tree AI 防火墙规则...")

    manager = get_firewall_manager()

    if not manager.is_admin():
        print("⚠️  需要管理员权限")
        return False

    rules = [
        "P2P Discovery",
        "Relay Server",
        "Web UI",
        "LAN Chat",
    ]

    success_all = True
    for rule in rules:
        success, message = manager.remove_rule(rule)
        if success:
            print(f"✅ {message}")
        else:
            print(f"ℹ️  {message}")
            success_all = False

    return success_all


def show_status():
    """显示防火墙状态"""
    print("Living Tree AI 防火墙状态检查")
    print("=" * 50)

    manager = get_firewall_manager()
    status = manager.get_firewall_status()

    print(f"\n管理员权限: {'✅ 是' if status['is_admin'] else '❌ 否'}")
    print(f"防火墙启用: {'✅ 是' if status['firewall_enabled'] else '❌ 否'}")

    print("\n网络配置:")
    for profile, enabled in status["profiles"].items():
        print(f"  {profile}: {'启用' if enabled else '禁用'}")

    print(f"\n应用规则数量: {len(status['app_rules'])}")

    if status["app_rules"]:
        print("\n当前应用规则:")
        for rule in status["app_rules"]:
            print(f"  - {rule.get('DisplayName', 'Unknown')}")

    return True


def check_rules():
    """检查规则是否存在"""
    print("检查 Living Tree AI 防火墙规则...")
    print("=" * 50)

    manager = get_firewall_manager()

    rules = [
        "Living Tree AI - P2P Discovery",
        "Living Tree AI - Relay Server",
        "Living Tree AI - Web UI",
        "Living Tree AI - LAN Chat",
    ]

    all_exist = True
    for rule in rules:
        exists = manager.check_rule_exists(rule)
        status = "✅ 存在" if exists else "❌ 不存在"
        print(f"  {rule}: {status}")
        if not exists:
            all_exist = False

    return all_exist


def open_port_example():
    """示例：开放单个端口"""
    manager = get_firewall_manager()

    # 开放端口 50000
    success, message = manager.open_port(50000, "TCP", "Living Tree AI - Custom Port")
    print(message)

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Living Tree AI 防火墙设置工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python firewall_setup.py --add-rules     添加所有防火墙规则
  python firewall_setup.py --remove-rules  移除所有防火墙规则
  python firewall_setup.py --status        查看防火墙状态
  python firewall_setup.py --check         检查规则是否存在

注意: 大多数操作需要管理员权限
        """
    )

    parser.add_argument(
        "--add-rules",
        action="store_true",
        help="添加所有防火墙规则"
    )

    parser.add_argument(
        "--remove-rules",
        action="store_true",
        help="移除所有防火墙规则"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="显示防火墙状态"
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="检查规则是否存在"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出"
    )

    args = parser.parse_args()

    # 如果没有参数，显示帮助
    if not any([args.add_rules, args.remove_rules, args.status, args.check]):
        parser.print_help()
        return 0

    result = None

    if args.add_rules:
        result = add_all_rules()
    elif args.remove_rules:
        result = remove_all_rules()
    elif args.status:
        result = show_status()
    elif args.check:
        result = check_rules()

    if args.json and isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())