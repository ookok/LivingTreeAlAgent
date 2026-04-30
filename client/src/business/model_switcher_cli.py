"""
Model Switcher CLI - 一键模型切换命令行工具

类似 cc-switch 的命令行界面，支持：
- 列出所有模型
- 一键切换模型
- 测试模型连接
- 循环切换模型

使用方式:
    python -m client.src.business.model_switcher_cli list
    python -m client.src.business.model_switcher_cli switch claude-3-5-sonnet
    python -m client.src.business.model_switcher_cli next
    python -m client.src.business.model_switcher_cli test gpt-4o
    python -m client.src.business.model_switcher_cli status

参考项目: https://github.com/farion1231/cc-switch

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import argparse
import sys
import asyncio

from client.src.business.model_switcher import (
    ModelSwitcher,
    switch_model,
    next_model,
    prev_model,
    get_models,
    get_current
)


def print_models(models):
    """打印模型列表"""
    print("=" * 60)
    print("可用模型列表")
    print("=" * 60)
    
    current_model = get_current()
    current_name = current_model.name if current_model else None
    
    for model in models:
        status = "●" if model.name == current_name else "○"
        enabled = "✓" if model.enabled else "✗"
        default = "*" if model.default else " "
        
        print(f"{status} [{enabled}] {default} {model.name}")
        print(f"     提供者: {model.provider}")
        print(f"     Model ID: {model.model_id}")
        print(f"     优先级: {model.priority}")
        print()


def print_status():
    """打印状态"""
    switcher = ModelSwitcher.get_instance()
    stats = switcher.get_stats()
    current = get_current()
    
    print("=" * 60)
    print("模型切换器状态")
    print("=" * 60)
    print(f"当前模型: {current.name if current else '未设置'}")
    print(f"总模型数: {stats['total_models']}")
    print(f"启用模型: {stats['enabled_models']}")
    print(f"提供者: {', '.join(stats['providers'])}")
    print()


def cmd_list(args):
    """列出所有模型"""
    models = get_models()
    print_models(models)


def cmd_switch(args):
    """切换模型"""
    if not args.model_name:
        print("请指定模型名称")
        return
    
    result = switch_model(args.model_name)
    
    print("=" * 60)
    print("切换结果")
    print("=" * 60)
    print(f"成功: {result.success}")
    print(f"消息: {result.message}")
    if result.previous_model:
        print(f"之前: {result.previous_model}")
    if result.current_model:
        print(f"当前: {result.current_model}")
    if result.provider:
        print(f"提供者: {result.provider}")
    print()


def cmd_next(args):
    """切换到下一个模型"""
    result = next_model()
    
    print("=" * 60)
    print("循环切换结果")
    print("=" * 60)
    print(f"成功: {result.success}")
    print(f"消息: {result.message}")
    if result.previous_model:
        print(f"之前: {result.previous_model}")
    if result.current_model:
        print(f"当前: {result.current_model}")
    print()


def cmd_prev(args):
    """切换到上一个模型"""
    result = prev_model()
    
    print("=" * 60)
    print("循环切换结果")
    print("=" * 60)
    print(f"成功: {result.success}")
    print(f"消息: {result.message}")
    if result.previous_model:
        print(f"之前: {result.previous_model}")
    if result.current_model:
        print(f"当前: {result.current_model}")
    print()


async def cmd_test(args):
    """测试模型连接"""
    if not args.model_name:
        print("请指定模型名称")
        return
    
    switcher = ModelSwitcher.get_instance()
    result = await switcher.test_model(args.model_name)
    
    print("=" * 60)
    print("测试结果")
    print("=" * 60)
    print(f"模型: {result['model']}")
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")
    if "response_time" in result:
        print(f"响应时间: {result['response_time']:.2f}s")
    print()


def cmd_status(args):
    """显示状态"""
    print_status()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="一键模型切换器 - 类似 cc-switch 的跨平台模型管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
类似 cc-switch 的功能：
- 支持 Claude Code / Codex / Gemini CLI / OpenCode / OpenClaw
- 一键切换当前使用的模型
- 模型状态监控
- 快速配置切换

参考项目: https://github.com/farion1231/cc-switch
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list - 列出所有模型
    subparsers.add_parser('list', help='列出所有可用模型')
    
    # switch - 切换模型
    switch_parser = subparsers.add_parser('switch', help='切换到指定模型')
    switch_parser.add_argument('model_name', help='模型名称')
    
    # next - 下一个模型
    subparsers.add_parser('next', help='切换到下一个模型')
    
    # prev - 上一个模型
    subparsers.add_parser('prev', help='切换到上一个模型')
    
    # test - 测试模型
    test_parser = subparsers.add_parser('test', help='测试模型连接')
    test_parser.add_argument('model_name', help='模型名称')
    
    # status - 显示状态
    subparsers.add_parser('status', help='显示当前状态')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # 执行命令
    if args.command == 'list':
        cmd_list(args)
    elif args.command == 'switch':
        cmd_switch(args)
    elif args.command == 'next':
        cmd_next(args)
    elif args.command == 'prev':
        cmd_prev(args)
    elif args.command == 'test':
        asyncio.run(cmd_test(args))
    elif args.command == 'status':
        cmd_status(args)


if __name__ == '__main__':
    main()