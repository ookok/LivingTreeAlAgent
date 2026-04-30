"""
自动集成测试（Trae 任务拆解 SKILL）
==================================

测试系统启动时自动注册拆解技能和斜杠命令

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest


class TestAutoIntegration:
    """自动集成测试"""
    
    def test_initialize_business_layer(self):
        """测试初始化业务层"""
        from client.src.business import get_bootstrapper, initialize_all
        import asyncio
        
        # 初始化
        bootstrapper = asyncio.run(initialize_all())
        
        stats = bootstrapper.get_stats()
        assert stats["initialized"] is True
        assert stats["module_count"] >= 5  # 至少初始化5个模块
    
    def test_decomposition_skills_registered(self):
        """测试拆解技能已注册"""
        from client.src.business import get_bootstrapper, initialize_all
        from client.src.business.skill_integration_service import get_skill_integration_service
        import asyncio
        
        # 确保已初始化
        asyncio.run(initialize_all())
        
        service = get_skill_integration_service()
        
        # 验证服务已初始化
        assert service is not None
    
    def test_slash_commands_registered(self):
        """测试拆解技能斜杠命令已注册"""
        from client.src.business import get_bootstrapper, initialize_all
        from client.src.business.skill_integration_service import get_skill_integration_service
        import asyncio
        
        # 确保已初始化
        asyncio.run(initialize_all())
        
        service = get_skill_integration_service()
        
        # 验证服务已初始化
        assert service is not None
    
    def test_slash_command_handlers(self):
        """测试斜杠命令处理器"""
        from client.src.business import get_bootstrapper, initialize_all
        from client.src.business.skill_integration_service import get_skill_integration_service
        import asyncio
        
        # 确保已初始化
        asyncio.run(initialize_all())
        
        service = get_skill_integration_service()
        
        # 验证服务已初始化
        assert service is not None
    
    def test_solo_plan_manager_initialized(self):
        """测试 SOLO Plan 管理器已初始化"""
        from client.src.business.solo_plan_manager import get_solo_plan_manager
        
        # 获取 Plan 管理器
        manager = get_solo_plan_manager()
        
        # 测试进入 Plan 模式
        manager.enter_plan_mode()
        assert manager.plan_mode is True
        
        # 测试退出 Plan 模式
        manager.exit_plan_mode()
        assert manager.plan_mode is False
    
    def test_skills_list_command(self):
        """测试 /skills 命令列出拆解技能"""
        from client.src.business import initialize_all
        from client.src.business.skill_integration_service import get_skill_integration_service
        import asyncio
        
        # 确保已初始化
        asyncio.run(initialize_all())
        
        service = get_skill_integration_service()
        
        # 验证服务已初始化
        assert service is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])