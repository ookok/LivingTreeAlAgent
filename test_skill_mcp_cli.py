#!/usr/bin/env python3
"""
测试skill、MCP和CLI插件功能
"""

import asyncio
import time
from core.skill_evolution.engine import EvolutionEngine
from core.skill_evolution.database import EvolutionDatabase
from core.mcp_manager import get_mcp_manager, MCPServer
import subprocess

async def test_skill_evolution():
    """测试技能进化系统"""
    print("=== 测试技能进化系统 ===")
    
    try:
        # 初始化数据库
        import tempfile
        import os
        db_path = None
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            db = EvolutionDatabase(db_path)
            engine = EvolutionEngine(db)
            
            # 测试执行记录
            class ExecutionRecord:
                def __init__(self, tool_name, success, duration, phase, tool_args):
                    self.tool_name = tool_name
                    self.success = success
                    self.duration = duration
                    self.phase = phase
                    self.tool_args = tool_args
            
            # 创建测试执行记录
            execution_records = [
                ExecutionRecord("terminal", True, 1.2, "execution", {"command": "dir"}),
                ExecutionRecord("terminal", True, 0.8, "execution", {"command": "echo hello"}),
            ]
            
            # 测试技能固化
            result = engine.consolidate(
                task_id="test_task_1",
                task_description="执行终端命令测试",
                execution_records=execution_records,
                task_type="terminal"
            )
            
            print(f"技能固化结果: {result.success}")
            if result.success:
                print(f"技能ID: {result.skill_id}")
                print(f"技能名称: {result.skill_name}")
            
            # 测试技能树
            skill_tree = engine.get_skill_tree()
            print(f"技能树: {skill_tree}")
            
            # 测试合并候选
            merge_candidates = engine.find_merge_candidates()
            print(f"可合并的技能: {len(merge_candidates)}")
            
            print("技能进化系统测试完成")
            return True
        finally:
            if db_path and os.path.exists(db_path):
                os.unlink(db_path)
    except Exception as e:
        print(f"技能进化系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mcp_manager():
    """测试MCP管理器"""
    print("\n=== 测试MCP管理器 ===")
    
    try:
        # 获取MCP管理器
        mcp_manager = get_mcp_manager()
        
        # 测试列出服务器
        servers = mcp_manager.list_servers()
        print(f"当前MCP服务器数量: {len(servers)}")
        
        # 测试添加服务器
        test_server = mcp_manager.add_server(
            name="测试服务器",
            url="http://localhost:8765",
            protocol="http",
            description="测试用MCP服务器",
            tags=["test", "local"]
        )
        print(f"添加测试服务器: {test_server.id}")
        
        # 测试获取服务器
        server = mcp_manager.get_server(test_server.id)
        if server:
            print(f"获取服务器成功: {server.name}")
        
        # 测试删除服务器
        mcp_manager.remove_server(test_server.id)
        print("删除测试服务器成功")
        
        # 测试发现市场
        market_servers = mcp_manager.discover_market()
        print(f"市场服务器数量: {len(market_servers)}")
        
        print("MCP管理器测试完成")
        return True
    except Exception as e:
        print(f"MCP管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_cli_terminal():
    """测试CLI终端工具"""
    print("\n=== 测试CLI终端工具 ===")
    
    try:
        # 测试执行简单命令
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "echo 'Hello from CLI test'"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[stderr] {result.stderr}"
        print(f"执行命令结果: {output}")
        
        # 测试执行目录命令
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "dir"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[stderr] {result.stderr}"
        print(f"目录列表: {output[:500]}...")
        
        print("CLI终端工具测试完成")
        return True
    except Exception as e:
        print(f"CLI终端工具测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("开始测试skill、MCP和CLI插件功能...")
    
    results = []
    
    # 测试技能进化系统
    results.append(await test_skill_evolution())
    
    # 测试MCP管理器
    results.append(await test_mcp_manager())
    
    # 测试CLI终端工具
    results.append(await test_cli_terminal())
    
    # 总结
    print("\n=== 测试总结 ===")
    tests = ["技能进化系统", "MCP管理器", "CLI终端工具"]
    for test, result in zip(tests, results):
        status = "✓ 成功" if result else "✗ 失败"
        print(f"{test}: {status}")
    
    if all(results):
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，需要进一步完善")

if __name__ == "__main__":
    asyncio.run(main())
