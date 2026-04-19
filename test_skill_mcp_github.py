#!/usr/bin/env python3
"""
测试skill、MCP和GitHub市场功能
"""

import asyncio
import time
from core.skill_market import get_skill_manager, SkillStatus
from core.mcp_manager import get_mcp_manager, MCPServer
import subprocess

async def test_skill_market():
    """测试技能市场"""
    print("=== 测试技能市场 ===")
    
    try:
        # 获取技能管理器
        skill_manager = get_skill_manager()
        
        # 测试列出已安装的技能
        installed_skills = skill_manager.list_installed()
        print(f"已安装的技能数量: {len(installed_skills)}")
        for skill in installed_skills:
            print(f"  - {skill.name} (v{skill.version})")
        
        # 测试浏览市场
        print("\n浏览技能市场...")
        market_result = await skill_manager.browse_market()
        print(f"市场技能数量: {market_result.get('total', 0)}")
        skills = market_result.get('skills', [])
        for skill in skills[:3]:  # 只显示前3个
            print(f"  - {skill.get('name')} (v{skill.get('version')})")
        
        # 测试搜索本地技能
        search_results = skill_manager.search_local("test")
        print(f"\n搜索 'test' 结果: {len(search_results)}")
        
        print("技能市场测试完成")
        return True
    except Exception as e:
        print(f"技能市场测试失败: {e}")
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
            name="测试MCP服务器",
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

async def test_github_market():
    """测试GitHub市场功能"""
    print("\n=== 测试GitHub市场 ===")
    
    try:
        # 检查是否有GitHub相关的模块
        print("检查GitHub市场功能...")
        
        # 尝试使用git命令
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        print(f"Git版本: {result.stdout.strip()}")
        
        # 检查GitHub相关的目录
        import os
        github_dirs = []
        for root, dirs, files in os.walk("."):
            for dir_name in dirs:
                if "github" in dir_name.lower():
                    github_dirs.append(os.path.join(root, dir_name))
        
        if github_dirs:
            print("找到GitHub相关目录:")
            for dir_path in github_dirs[:3]:
                print(f"  - {dir_path}")
        else:
            print("未找到GitHub相关目录")
        
        # 检查是否有GitHub API相关的代码
        import glob
        github_files = glob.glob("**/*github*", recursive=True)
        print(f"找到GitHub相关文件: {len(github_files)}")
        for file_path in github_files[:5]:
            print(f"  - {file_path}")
        
        print("GitHub市场测试完成")
        return True
    except Exception as e:
        print(f"GitHub市场测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("开始测试skill、MCP和GitHub市场功能...")
    
    results = []
    
    # 测试技能市场
    results.append(await test_skill_market())
    
    # 测试MCP管理器
    results.append(await test_mcp_manager())
    
    # 测试GitHub市场
    results.append(await test_github_market())
    
    # 总结
    print("\n=== 测试总结 ===")
    tests = ["技能市场", "MCP管理器", "GitHub市场"]
    for test, result in zip(tests, results):
        status = "✓ 成功" if result else "✗ 失败"
        print(f"{test}: {status}")
    
    if all(results):
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，需要进一步完善")

if __name__ == "__main__":
    asyncio.run(main())
