"""
测试 Agent Reach 多平台搜索工具

测试内容：
1. AgentReachTool 基本功能测试
2. 平台列表获取测试
3. 搜索功能测试
4. 平台状态检查测试
5. 工具注册测试

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from client.src.business.tools.agent_reach_tool import AgentReachTool, Platform, SearchMode


async def test_agent_reach_tool():
    """测试 AgentReachTool 基本功能"""
    print("测试 Agent Reach 多平台搜索工具...")
    print("=" * 60)
    
    # 1. 创建工具实例
    print("\n[1] 测试创建 AgentReachTool 实例...")
    try:
        tool = AgentReachTool()
        print(f"    ✓ 工具创建成功")
        print(f"    ✓ 工具名称: {tool.name}")
        print(f"    ✓ 工具类别: {tool.category}")
        print(f"    ✓ 工具类型: {tool.node_type}")
        print(f"    ✓ Agent Reach 可用: {'是' if tool.is_available() else '否'}")
    except Exception as e:
        print(f"    ✗ 工具创建失败: {e}")
        return
    
    # 2. 测试获取支持的平台列表
    print("\n[2] 测试获取支持的平台列表...")
    try:
        platforms = tool.get_supported_platforms()
        print(f"    ✓ 成功获取 {len(platforms)} 个支持的平台")
        print(f"    ✓ 平台列表: {platforms}")
    except Exception as e:
        print(f"    ✗ 获取平台列表失败: {e}")
    
    # 3. 测试列出平台模式
    print("\n[3] 测试 list 模式...")
    try:
        result = await tool.execute(query="", mode="list")
        if result["success"]:
            print(f"    ✓ list 模式执行成功")
            print(f"    ✓ 返回平台数量: {len(result['data'])}")
        else:
            print(f"    ✗ list 模式执行失败: {result['message']}")
    except Exception as e:
        print(f"    ✗ list 模式执行异常: {e}")
    
    # 4. 测试搜索功能（仅当 Agent Reach 可用时）
    print("\n[4] 测试搜索功能...")
    if tool.is_available():
        try:
            result = await tool.execute(
                query="AI agent",
                platforms=["github"],
                mode="search"
            )
            
            if result["success"]:
                print(f"    ✓ 搜索成功")
                print(f"    ✓ 找到 {len(result['data'])} 条结果")
                for item in result["data"][:2]:
                    print(f"      - [{item.get('platform')}] {item.get('title', '')[:50]}...")
            else:
                print(f"    ✗ 搜索失败: {result['message']}")
        except Exception as e:
            print(f"    ✗ 搜索异常: {e}")
    else:
        print("    ⚠️ Agent Reach 不可用，跳过搜索测试")
    
    # 5. 测试平台状态检查
    print("\n[5] 测试平台状态检查...")
    try:
        status_list = tool.get_all_platform_status()
        configured_count = sum(1 for s in status_list if s["configured"])
        print(f"    ✓ 成功获取所有平台状态")
        print(f"    ✓ 已配置平台: {configured_count}/{len(status_list)}")
        
        # 测试单个平台状态
        status = tool.get_platform_status("github")
        print(f"    ✓ GitHub 状态: {'已配置' if status['configured'] else '未配置'}")
    except Exception as e:
        print(f"    ✗ 平台状态检查失败: {e}")
    
    # 6. 测试智能体信息获取
    print("\n[6] 测试获取智能体信息...")
    try:
        agent_info = tool.get_agent_info()
        print(f"    ✓ 获取智能体信息成功")
        print(f"    ✓ 工具名称: {agent_info['name']}")
        print(f"    ✓ 支持平台数量: {len(agent_info['supported_platforms'])}")
        print(f"    ✓ 参数数量: {len(agent_info['parameters'])}")
    except Exception as e:
        print(f"    ✗ 获取智能体信息失败: {e}")
    
    # 7. 测试配置功能
    print("\n[7] 测试平台配置...")
    try:
        # 测试配置不存在的平台
        result = tool.configure_platform("invalid_platform")
        print(f"    ✓ 无效平台配置返回: {result}")
        
        # 测试获取平台状态
        status = tool.get_platform_status("github")
        print(f"    ✓ GitHub 配置状态: {status}")
    except Exception as e:
        print(f"    ✗ 平台配置测试失败: {e}")
    
    # 8. 测试参数验证
    print("\n[8] 测试参数验证...")
    try:
        # 空查询测试
        result = await tool.execute(query="", mode="search")
        print(f"    ✓ 空查询测试: {'成功拦截' if not result['success'] else '未拦截'}")
        
        # 正常查询测试（如果可用）
        if tool.is_available():
            result = await tool.execute(query="test", mode="search")
            print(f"    ✓ 正常查询测试: {'成功' if result['success'] else '失败'}")
    except Exception as e:
        print(f"    ✗ 参数验证测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agent_reach_tool())