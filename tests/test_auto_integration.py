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
        from client.src.business import initialize_business_layer, is_initialized
        
        # 初始化
        result = initialize_business_layer()
        
        assert result["success"] is True
        assert result["initialized"] is True
        assert result["skills_registered"] >= 3  # 至少包含3个拆解技能
        assert result["commands_registered"] >= 4  # 至少包含4个拆解相关命令
        
        # 验证已初始化
        assert is_initialized() is True
    
    def test_decomposition_skills_registered(self):
        """测试拆解技能已注册"""
        from client.src.business import initialize_business_layer, get_initializer
        
        # 确保已初始化
        initialize_business_layer()
        
        initializer = get_initializer()
        registry = initializer.get_registry()
        
        # 检查架构设计技能
        skill = registry.get_skill("architecture_designer")
        assert skill is not None
        assert skill.name == "架构设计与系统规划"
        
        # 检查代码重构技能
        skill = registry.get_skill("code_refactorer")
        assert skill is not None
        assert skill.name == "代码重构与优化"
        
        # 检查任务拆解技能
        skill = registry.get_skill("task_splitter_pro")
        assert skill is not None
        assert skill.name == "智能任务拆解大师"
    
    def test_slash_commands_registered(self):
        """测试拆解技能斜杠命令已注册"""
        from client.src.business import initialize_business_layer, get_initializer
        
        # 确保已初始化
        initialize_business_layer()
        
        initializer = get_initializer()
        slash_commands = initializer.get_slash_commands()
        
        # 获取所有命令
        commands = slash_commands.list_commands()
        command_names = [cmd["command"] for cmd in commands]
        
        # 检查架构设计命令
        assert "/arch" in command_names
        
        # 检查代码重构命令
        assert "/refactor" in command_names
        
        # 检查任务拆解命令
        assert "/decompose" in command_names
        
        # 检查 Plan 模式命令
        assert "/plan" in command_names
    
    def test_slash_command_handlers(self):
        """测试斜杠命令处理器"""
        from client.src.business import initialize_business_layer, get_initializer
        
        # 确保已初始化
        initialize_business_layer()
        
        initializer = get_initializer()
        slash_commands = initializer.get_slash_commands()
        
        # 测试 /arch 命令
        result = slash_commands.execute("/arch")
        assert result["command"] == "/arch"
        assert result["skill_id"] == "architecture_designer"
        assert result["status"] == "ready"
        
        # 测试 /refactor 命令
        result = slash_commands.execute("/refactor")
        assert result["command"] == "/refactor"
        assert result["skill_id"] == "code_refactorer"
        assert result["status"] == "ready"
        
        # 测试 /decompose 命令
        result = slash_commands.execute("/decompose")
        assert result["command"] == "/decompose"
        assert result["skill_id"] == "task_splitter_pro"
        assert result["status"] == "ready"
        
        # 测试 /plan 命令
        result = slash_commands.execute("/plan")
        assert result["command"] == "/plan"
        assert result["status"] == "plan_mode_active"
    
    def test_solo_plan_manager_initialized(self):
        """测试 SOLO Plan 管理器已初始化"""
        from client.src.business import initialize_business_layer, get_solo_plan_manager
        
        # 确保已初始化
        initialize_business_layer()
        
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
        from client.src.business import initialize_business_layer, get_initializer
        
        # 确保已初始化
        initialize_business_layer()
        
        initializer = get_initializer()
        slash_commands = initializer.get_slash_commands()
        
        # 执行 /skills 命令
        result = slash_commands.execute("/skills")
        
        assert "skills" in result
        skill_names = [s["name"] for s in result["skills"]]
        
        # 验证拆解技能已列出
        assert "架构设计与系统规划" in skill_names
        assert "代码重构与优化" in skill_names
        assert "智能任务拆解大师" in skill_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])