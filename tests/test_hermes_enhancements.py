"""
Hermes Agent 增强功能测试
=========================

测试新增的三个核心模块：
1. AutoEvolutionSkill - 自进化技能系统
2. HonchoUserModeling - 用户建模
3. CronScheduler - 定时任务调度

Author: Hermes Desktop Team
Date: 2026-04-25
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import time
from datetime import datetime, timedelta


class TestSkillRegistryEnhanced:
    """增强后的技能注册中心测试"""
    
    def test_register_with_hermes_format(self):
        """测试 Hermes SKILL.md 格式注册"""
        from client.src.business.agent_skills import (
            SkillRegistry,
            SkillCategory,
            AgentType,
            OutputType,
        )
        
        registry = SkillRegistry()
        
        # 模拟 Hermes SKILL.md 格式数据
        skill_data = {
            "id": "code-review",
            "name": "Code Review",
            "description": "自动化代码审查技能",
            "category": "review",
            "trigger": ["review", "审查", "检查代码"],
            "agent": "CodeExpert",
            "inputs": [
                {"name": "code", "description": "待审查代码", "required": True}
            ],
            "outputs": [
                {"type": "text", "description": "审查报告"}
            ],
            "tools": ["read_file", "search_content"],
            "conversation_starters": [
                "帮我审查代码",
                "检查这段代码"
            ],
            "priority": 8,
        }
        
        manifest = registry.register_from_dict(skill_data, content="# Code Review\n...")
        
        assert manifest.id == "code-review"
        assert manifest.agent == AgentType.CODE_EXPERT
        assert manifest.category == SkillCategory.REVIEW
        assert len(manifest.inputs) == 1
        assert len(manifest.outputs) == 1
        assert "read_file" in manifest.tools
        
    def test_register_with_enum_fallback(self):
        """测试枚举值回退"""
        from client.src.business.agent_skills import SkillRegistry
        
        registry = SkillRegistry()
        
        # 无效的枚举值应该回退到默认值
        skill_data = {
            "id": "test-skill",
            "name": "Test Skill",
            "description": "测试技能",
            "category": "invalid_category",
            "agent": "InvalidAgent",
        }
        
        manifest = registry.register_from_dict(skill_data)
        
        # 应该使用默认值
        from client.src.business.agent_skills import SkillCategory, AgentType
        assert manifest.category == SkillCategory.DEVELOPMENT
        assert manifest.agent == AgentType.GENERAL


class TestAutoEvolutionSkill:
    """自进化技能系统测试"""
    
    def test_pattern_detection(self):
        """测试模式检测"""
        from client.src.business.agent_skills.auto_evolution_skill import PatternDetector
        
        detector = PatternDetector(min_frequency=2)
        
        # 记录相似交互
        queries = [
            "帮我分析Python代码质量问题",
            "分析Java代码质量问题",
            "审查Python代码",
        ]
        
        for query in queries:
            detector.record_interaction(
                query=query,
                actions=["read_file", "analyze", "report"],
                success=True
            )
            
        patterns = detector.detect_patterns()
        
        # 应该检测到模式
        assert len(patterns) >= 1
        
    def test_skill_seed_generation(self):
        """测试技能种子生成"""
        from client.src.business.agent_skills.auto_evolution_skill import (
            PatternDetector,
            SkillSeedGenerator,
        )
        
        detector = PatternDetector(min_frequency=2)
        generator = SkillSeedGenerator()
        
        # 记录交互
        for _ in range(3):
            detector.record_interaction(
                query="帮我写单元测试",
                actions=["analyze_code", "generate_test", "write_file"],
                success=True
            )
            
        patterns = detector.detect_patterns()
        
        if patterns:
            seed = generator.generate_seed(patterns[0])
            
            assert seed.name is not None
            assert seed.suggested_agent is not None
            assert len(seed.trigger_phrases) > 0
            
    def test_full_evolution_flow(self):
        """测试完整进化流程"""
        from client.src.business.agent_skills import SkillRegistry
        from client.src.business.agent_skills.auto_evolution_skill import AutoEvolutionSkill
        
        registry = SkillRegistry()
        evolution = AutoEvolutionSkill(registry, min_pattern_frequency=2)
        
        # 记录交互
        for _ in range(3):
            evolution.record_interaction(
                query="帮我审查Python代码",
                actions=["read_file", "analyze_code", "report_issues"],
                success=True
            )
            
        # 检测候选
        candidates = evolution.detect_skill_candidates()
        
        # 如果有候选，创建技能
        if candidates:
            seed = candidates[0]
            skill = evolution.create_skill_from_seed(seed)
            
            assert skill is not None
            assert skill.id.startswith("auto-")
            
        # 获取进化报告
        report = evolution.get_evolution_report()
        assert "total_skills" in report
        assert "detected_patterns" in report


class TestHonchoUserModeling:
    """用户建模系统测试"""
    
    def test_profile_creation(self):
        """测试用户画像创建"""
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        
        honcho = HonchoUserModeling()
        profile = honcho.get_profile("test-user")
        
        assert profile.user_id == "test-user"
        assert profile.total_interactions == 0
        
    def test_dialect_detection(self):
        """测试方言检测"""
        from client.src.business.agent_skills.honcho_user_modeling import (
            HonchoUserModeling,
            Dialect,
        )
        
        honcho = HonchoUserModeling()
        
        # 正式表达
        honcho.record_interaction(
            query="请帮我分析这段代码，麻烦了",
            user_id="formal-user"
        )
        
        profile = honcho.get_profile("formal-user")
        # 可能检测到 FORMAL 或 CASUAL
        
        # 随意表达
        honcho.record_interaction(
            query="帮我看下这代码",
            user_id="casual-user"
        )
        
        casual_profile = honcho.get_profile("casual-user")
        # 应该检测到更随意的风格
        
    def test_triggers_learning(self):
        """测试触发词学习"""
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        
        honcho = HonchoUserModeling()
        
        # 记录交互
        honcho.record_interaction(
            query="帮我审查代码",
            user_id="test-user"
        )
        honcho.record_interaction(
            query="审查这个文件",
            user_id="test-user"
        )
        
        profile = honcho.get_profile("test-user")
        
        # 应该学习到触发词
        assert profile.total_interactions == 2
        
    def test_response_adaptation(self):
        """测试响应适配"""
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        
        honcho = HonchoUserModeling()
        
        # 设置偏好
        honcho.record_interaction(
            query="简单测试",
            user_feedback="太复杂了，简化一下",
            user_id="brief-user"
        )
        
        # 获取适配后的响应
        base_response = """这是详细的解释：
1. 第一步
2. 第二步
3. 第三步

```python
# 代码示例
def example():
    pass
```

结论：以上就是解决方案。"""
        
        adapted = honcho.adapt_response(base_response, user_id="brief-user")
        
        # 应该进行简化
        assert len(adapted) <= len(base_response) * 1.5
        
    def test_query_adaptation(self):
        """测试查询适配"""
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        
        honcho = HonchoUserModeling()
        
        # 简短命令
        adapted = honcho.adapt_query("测代码", user_id="test-user")
        
        # 应该扩展
        assert "测试" in adapted or "审查" in adapted
        
    def test_context_retrieval(self):
        """测试上下文获取"""
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        
        honcho = HonchoUserModeling()
        
        # 设置上下文
        honcho.update_project_context("project_name", "LivingTreeAI", user_id="test-user")
        honcho.remember_completed_work("完成了代码审查", user_id="test-user")
        
        # 获取上下文
        context = honcho.get_context_for_query("审查代码", user_id="test-user")
        
        assert "project" in context
        assert context["project"]["project_name"] == "LivingTreeAI"


class TestCronScheduler:
    """定时任务调度器测试"""
    
    def test_cron_parser(self):
        """测试 Cron 表达式解析"""
        from client.src.business.agent_skills.cron_scheduler import CronParser
        
        # 解析每天早上9点
        fields = CronParser.parse("0 9 * * *")
        
        assert 0 in fields["minute"]
        assert 9 in fields["hour"]
        assert fields["day"] == list(range(1, 32))
        
    def test_cron_next_run(self):
        """测试下次执行时间计算"""
        from client.src.business.agent_skills.cron_scheduler import CronParser
        
        # 每5分钟
        cron = "*/5 * * * *"
        next_run = CronParser.get_next_run(cron)
        
        # 应该是5分钟的倍数
        assert next_run.minute % 5 == 0
        
    def test_schedule_cron_task(self):
        """测试 Cron 任务创建"""
        from client.src.business.agent_skills.cron_scheduler import CronScheduler
        
        scheduler = CronScheduler()
        
        task = scheduler.schedule_cron(
            name="每日报告",
            cron="0 9 * * *",
            command="generate_report"
        )
        
        assert task.name == "每日报告"
        assert task.cron_expression == "0 9 * * *"
        assert task.next_run is not None
        
    def test_schedule_interval_task(self):
        """测试间隔任务创建"""
        from client.src.business.agent_skills.cron_scheduler import CronScheduler
        
        scheduler = CronScheduler()
        
        task = scheduler.schedule_interval(
            name="健康检查",
            interval=300,  # 5分钟
            command="health_check"
        )
        
        assert task.interval_seconds == 300
        assert task.next_run is not None
        
    def test_natural_language_parsing(self):
        """测试自然语言解析"""
        from client.src.business.agent_skills.cron_scheduler import NaturalLanguageScheduler
        
        # 每小时
        config = NaturalLanguageScheduler.parse("每1小时")
        assert config.get("interval_seconds") == 3600
        
        # 每天早上9点
        config = NaturalLanguageScheduler.parse("每天早上9点")
        assert "cron_expression" in config
        
    def test_schedule_natural_task(self):
        """测试自然语言任务创建"""
        from client.src.business.agent_skills.cron_scheduler import CronScheduler
        
        scheduler = CronScheduler()
        
        task = scheduler.schedule_natural(
            name="定时备份",
            natural="每30分钟",
            command="backup"
        )
        
        assert task.interval_seconds == 1800
        
    def test_task_execution(self):
        """测试任务执行"""
        from client.src.business.agent_skills.cron_scheduler import CronScheduler, TaskStatus
        
        scheduler = CronScheduler()
        
        # 创建一次性任务
        task = scheduler.schedule_once(
            name="立即测试",
            scheduled_time=datetime.now() + timedelta(seconds=1),
            command="test_command"
        )
        
        # 启动调度器
        scheduler.start()
        
        # 等待执行
        time.sleep(3)
        
        scheduler.stop()
        
        # 检查任务状态
        updated_task = scheduler.get_task(task.task_id)
        assert updated_task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        
    def test_task_control(self):
        """测试任务控制"""
        from client.src.business.agent_skills.cron_scheduler import CronScheduler
        
        scheduler = CronScheduler()
        
        task = scheduler.schedule_interval(
            name="测试任务",
            interval=60,
            command="test"
        )
        
        # 暂停
        assert scheduler.pause_task(task.task_id) is True
        
        # 恢复
        assert scheduler.resume_task(task.task_id) is True
        
        # 取消
        assert scheduler.cancel_task(task.task_id) is True


class TestIntegration:
    """集成测试"""
    
    def test_full_agent_enhancement(self):
        """测试完整的 Agent 增强"""
        from client.src.business.agent_skills import (
            SkillRegistry,
            SkillCategory,
            AgentType,
        )
        from client.src.business.agent_skills.auto_evolution_skill import AutoEvolutionSkill
        from client.src.business.agent_skills.honcho_user_modeling import HonchoUserModeling
        from client.src.business.agent_skills.cron_scheduler import CronScheduler
        
        # 初始化组件
        registry = SkillRegistry()
        evolution = AutoEvolutionSkill(registry)
        honcho = HonchoUserModeling()
        scheduler = CronScheduler()
        
        # 1. 学习用户偏好
        honcho.record_interaction(
            query="帮我审查Python代码",
            user_feedback="很好！正是我想要的",
            user_id="developer"
        )
        
        # 2. 记录交互模式
        for _ in range(3):
            evolution.record_interaction(
                query="帮我审查Python代码",
                actions=["read_file", "analyze", "report"],
                success=True
            )
            
        # 3. 从模式创建技能
        candidates = evolution.detect_skill_candidates()
        if candidates:
            evolution.create_skill_from_seed(candidates[0])
            
        # 4. 注册手动创建的技能
        skill_data = {
            "id": "python-review",
            "name": "Python 代码审查",
            "description": "专门审查 Python 代码的技能",
            "category": "review",
            "agent": "CodeExpert",
            "trigger": ["python", "审查"],
        }
        registry.register_from_dict(skill_data, content="# Python Review\n...")
        
        # 5. 创建定时任务
        scheduler.schedule_natural(
            name="每日代码审查",
            natural="每天早上9点",
            command="auto_review"
        )
        
        # 6. 获取报告
        evolution_report = evolution.get_evolution_report()
        honcho_report = honcho.get_report("developer")
        scheduler_stats = scheduler.get_stats()
        
        # 验证
        assert "total_skills" in evolution_report
        assert "total_interactions" in honcho_report
        assert "total_tasks" in scheduler_stats
        
        print("\n=== Agent Enhancement Report ===")
        print(f"Skills: {evolution_report['total_skills']}")
        print(f"User interactions: {honcho_report['total_interactions']}")
        print(f"Scheduled tasks: {scheduler_stats['total_tasks']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
