#!/usr/bin/env python3
"""
LivingTree AI 启动脚本

运行方式：
python start_livingtree.py [start|interactive|status]
"""

import sys
import os
import asyncio

# 先导入标准库的 platform，避免与项目中的 platform.py 冲突
import platform as std_platform
sys.modules['platform'] = std_platform

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src', 'business'))

from living_tree_core import LivingTree, interactive_mode


async def main():
    if len(sys.argv) < 2:
        print("🌲 LivingTree AI")
        print("=================")
        print("用法: python start_livingtree.py <command>")
        print("")
        print("命令:")
        print("  start       - 启动生命系统")
        print("  interactive - 进入交互模式")
        print("  status      - 查看系统状态")
        print("")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'interactive':
        await interactive_mode()
    elif command == 'start':
        living_tree = LivingTree()
        try:
            await living_tree.start()
        except KeyboardInterrupt:
            await living_tree.shutdown()
    elif command == 'status':
        print("🌲 LivingTree AI 状态")
        print("=====================")
        print("注意: 需要运行中的实例才能获取详细状态")
        print("启动命令: python start_livingtree.py start")
    else:
        print(f"❌ 未知命令: {command}")


if __name__ == '__main__':
    asyncio.run(main())