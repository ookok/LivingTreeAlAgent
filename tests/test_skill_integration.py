"""
技能发现深度集成测试
====================

测试技能发现模块与系统的深度集成：
1. 技能发现引擎集成测试
2. 技能匹配引擎集成测试
3. 技能图谱集成测试
4. 技能集成服务集成测试
5. 完整集成流程测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio
from client.src.business import (
    integrate_optimization,
    get_integration_bootstrapper,
    get_skill_integration_service,
)


class TestSkillDiscoveryIntegration:
    """技能发现引擎集成测试"""
    
    @pytest.mark.asyncio
    async def test_skill_discovery_integration(self):
        """测试技能发现引擎集成"""
        print("测试技能发现引擎集成...")
        
        # 深度集成
        result = await integrate_optimization()
        
        assert result["success"] is True
        
        # 检查技能发现引擎是否初始化
        bootstrapper = get_integration_bootstrapper()
        skill_discovery = bootstrapper.get_skill_discovery()
        
        assert skill_discovery is not None
        assert hasattr(skill_discovery, 'analyze_repo')
        
        print("✓ 技能发现引擎集成成功")
    
    @pytest.mark.asyncio
    async def test_skill_matcher_integration(self):
        """测试技能匹配引擎集成"""
        print("测试技能匹配引擎集成...")
        
        bootstrapper = get_integration_bootstrapper()
        skill_matcher = bootstrapper.get_skill_matcher()
        
        assert skill_matcher is not None
        assert hasattr(skill_matcher, 'match')
        assert hasattr(skill_matcher, 'recommend')
        
        # 测试匹配功能
        matches = skill_matcher.match("帮我写一个Python函数", ["python", "pyqt", "llm"])
        
        assert len(matches) > 0
        assert any(m.skill_name == "python" for m in matches)
        
        print("✓ 技能匹配引擎集成成功")


class TestSkillGraphIntegration:
    """技能图谱集成测试"""
    
    @pytest.mark.asyncio
    async def test_skill_graph_integration(self):
        """测试技能图谱集成"""
        print("测试技能图谱集成...")
        
        bootstrapper = get_integration_bootstrapper()
        skill_graph = bootstrapper.get_skill_graph()
        
        assert skill_graph is not None
        assert hasattr(skill_graph, 'add_node')
        assert hasattr(skill_graph, 'add_edge')
        assert hasattr(skill_graph, 'find_shortest_path')
        
        print("✓ 技能图谱集成成功")
    
    def test_skill_graph_build(self):
        """测试技能图谱构建"""
        print("测试技能图谱构建...")
        
        bootstrapper = get_integration_bootstrapper()
        skill_graph = bootstrapper.get_skill_graph()
        
        stats = skill_graph.get_stats()
        
        assert stats["nodes"] > 0
        assert stats["edges"] >= 0
        
        print(f"✓ 技能图谱构建成功: {stats['nodes']} 节点, {stats['edges']} 边")


class TestSkillIntegrationService:
    """技能集成服务测试"""
    
    @pytest.mark.asyncio
    async def test_skill_integration_service(self):
        """测试技能集成服务"""
        print("测试技能集成服务...")
        
        service = get_skill_integration_service()
        
        assert service is not None
        assert hasattr(service, 'match_skills')
        assert hasattr(service, 'recommend_skills')
        assert hasattr(service, 'find_skill_path')
        
        print("✓ 技能集成服务集成成功")
    
    @pytest.mark.asyncio
    async def test_skill_matching_service(self):
        """测试技能匹配服务"""
        print("测试技能匹配服务...")
        
        service = get_skill_integration_service()
        
        # 测试匹配技能
        result = await service.match_skills("帮我创建一个AI聊天机器人")
        
        assert result.matches is not None
        assert result.recommendations is not None
        
        print(f"✓ 匹配到 {len(result.matches)} 个技能")
        print(f"✓ 推荐了 {len(result.recommendations)} 个技能")
    
    @pytest.mark.asyncio
    async def test_skill_recommendation(self):
        """测试技能推荐"""
        print("测试技能推荐...")
        
        service = get_skill_integration_service()
        
        recommendations = await service.recommend_skills("Python开发")
        
        assert isinstance(recommendations, list)
        
        print(f"✓ 获取到 {len(recommendations)} 个推荐技能")


class TestSkillHooksIntegration:
    """技能感知钩子集成测试"""
    
    @pytest.mark.asyncio
    async def test_skill_hooks_registration(self):
        """测试技能感知钩子注册"""
        print("测试技能感知钩子注册...")
        
        bootstrapper = get_integration_bootstrapper()
        hook_manager = bootstrapper.get_hook_manager()
        
        assert hook_manager is not None
        
        # 检查钩子是否注册
        stats = hook_manager.get_stats()
        
        print(f"✓ 钩子管理器已注册 {stats.get('total_hooks', 0)} 个钩子")


class TestEndToEndSkillIntegration:
    """端到端技能集成测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_skill_integration(self):
        """测试端到端技能集成流程"""
        print("\n=== 端到端技能集成测试 ===")
        
        # 1. 深度集成所有组件
        print("1. 深度集成所有组件...")
        result = await integrate_optimization()
        
        assert result["success"] is True
        print("✓ 集成成功")
        
        # 2. 获取所有技能组件
        print("\n2. 获取技能组件...")
        bootstrapper = get_integration_bootstrapper()
        
        skill_discovery = bootstrapper.get_skill_discovery()
        skill_matcher = bootstrapper.get_skill_matcher()
        skill_graph = bootstrapper.get_skill_graph()
        skill_service = bootstrapper.get_skill_integration_service()
        
        assert all([skill_discovery, skill_matcher, skill_graph, skill_service])
        print("✓ 所有技能组件已初始化")
        
        # 3. 测试技能发现
        print("\n3. 测试技能发现...")
        if skill_discovery:
            result = skill_discovery.analyze_repo("client/src/business")
            print(f"✓ 发现 {result.total_skills_found} 个技能")
        
        # 4. 测试技能匹配
        print("\n4. 测试技能匹配...")
        if skill_matcher:
            matches = skill_matcher.match("构建RAG系统", ["python", "llm", "rag", "api"])
            print(f"✓ 匹配到 {len(matches)} 个技能")
        
        # 5. 测试技能图谱
        print("\n5. 测试技能图谱...")
        if skill_graph:
            stats = skill_graph.get_stats()
            print(f"✓ 图谱: {stats['nodes']} 节点, {stats['edges']} 边")
            
            clusters = skill_graph.cluster()
            print(f"✓ 聚类: {len(clusters)} 个聚类")
        
        # 6. 测试技能集成服务
        print("\n6. 测试技能集成服务...")
        if skill_service:
            match_result = await skill_service.match_skills("创建GUI应用")
            print(f"✓ 匹配结果: {len(match_result.matches)} 个匹配, {len(match_result.recommendations)} 个推荐")
        
        print("\n=== 端到端技能集成测试完成 ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])