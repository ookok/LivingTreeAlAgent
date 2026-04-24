"""
Enhanced Integration - 增强集成层
连接渐进式学习和反思式学习，实现自动化调用
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime

try:
    from .seamless_enhancer import SeamlessEnhancer, EnhancementContext
    from .trigger_decider import TriggerDecider, EnhancementType, TaskAnalysis
except ImportError:
    from seamless_enhancer import SeamlessEnhancer, EnhancementContext
    from trigger_decider import TriggerDecider, EnhancementType, TaskAnalysis


@dataclass
class LearnedSkill:
    """已学习的技能"""
    skill_id: str                    # 技能ID
    name: str                        # 技能名称
    description: str                # 描述
    triggers: List[str] = field(default_factory=list)  # 触发词
    action: str = ""                 # 执行动作
    examples: List[str] = field(default_factory=list)   # 示例
    success_count: int = 0           # 成功次数
    use_count: int = 0              # 使用次数
    avg_quality: float = 0.0        # 平均质量
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    is_refined: bool = False        # 是否经过反思改进


@dataclass
class FailureLesson:
    """失败教训"""
    lesson_id: str                   # 教训ID
    query_pattern: str              # 查询模式
    failure_reason: str             # 失败原因
    original_attempt: str           # 原始尝试
    improved_attempt: str           # 改进后的尝试
    improvement_strategy: str       # 改进策略
    success_after_fix: bool = True  # 修复后是否成功
    times_encountered: int = 1      # 遇到次数
    last_encountered: datetime = field(default_factory=datetime.now)


class EnhancedIntegration:
    """增强集成层
    
    核心思想：
    1. **渐进式学习**：从成功中提取可复用的技能
    2. **反思式学习**：从失败中提取改进策略
    3. **自动化调用**：用户无感知，系统自动选择最优路径
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化集成层"""
        self.config = config or {}
        
        # 创建无缝增强器
        self._enhancer = SeamlessEnhancer(
            config=self.config.get("enhancer", {})
        )
        
        # 触发决策器
        self._decider = TriggerDecider(
            self.config.get("decider", {})
        )
        
        # 已学习的技能库
        self._skills: Dict[str, LearnedSkill] = {}
        
        # 失败教训库
        self._lessons: Dict[str, FailureLesson] = {}
        
        # 反思式Agent组件 (懒加载)
        self._reflective_agent = None
        self._multi_path_explorer = None
        self._world_model = None
        self._collective = None
        
        # 配置
        self.auto_learn = self.config.get("auto_learn", True)
        self.auto_reflect = self.config.get("auto_reflect", True)
        self.min_success_for_skill = self.config.get("min_success_for_skill", 3)
    
    # ==================== 主入口 ====================
    
    async def chat(self, message: str) -> str:
        """主入口 - 用户无感调用
        
        内部自动完成：
        1. 检查技能库 → 匹配则直接使用
        2. 任务分析 → 决定增强策略
        3. 执行 + 反思 → 必要时重试
        4. 学习 → 从结果中提取新技能/教训
        """
        # 1. 检查技能库
        matched_skill = await self._match_skill(message)
        if matched_skill:
            matched_skill.use_count += 1
            matched_skill.last_used = datetime.now()
            return matched_skill.action
        
        # 2. 检查失败教训
        matched_lesson = await self._match_lesson(message)
        if matched_lesson:
            message = await self._apply_lesson(message, matched_lesson)
        
        # 3. 任务分析
        analysis = self._decider.analyze(message)
        
        # 4. 执行并反思
        result = await self._execute_with_enhancement(message, analysis)
        
        # 5. 学习
        if self.auto_learn:
            await self._learn_from_result(message, result, analysis)
        
        return result
    
    # ==================== 技能匹配 ====================
    
    async def _match_skill(self, query: str) -> Optional[LearnedSkill]:
        """匹配已学技能"""
        query_lower = query.lower()
        
        best_match = None
        best_score = 0.0
        
        for skill in self._skills.values():
            # 检查触发词
            for trigger in skill.triggers:
                if trigger.lower() in query_lower:
                    score = len(trigger) / len(query)  # 触发词占比
                    if score > best_score:
                        best_score = score
                        best_match = skill
        
        return best_match if best_score > 0.1 else None
    
    async def _match_lesson(self, query: str) -> Optional[FailureLesson]:
        """匹配失败教训"""
        query_lower = query.lower()
        
        for lesson in self._lessons.values():
            if lesson.query_pattern.lower() in query_lower:
                return lesson
        
        return None
    
    async def _apply_lesson(self, query: str, lesson: FailureLesson) -> str:
        """应用失败教训改进查询"""
        lesson.times_encountered += 1
        lesson.last_encountered = datetime.now()
        
        # 简单策略：如果有改进后的尝试，用它替换原查询中的关键部分
        if lesson.improved_attempt:
            # 返回改进后的查询
            return lesson.improved_attempt
        
        return query
    
    # ==================== 增强执行 ====================
    
    async def _execute_with_enhancement(
        self,
        query: str,
        analysis: TaskAnalysis
    ) -> str:
        """增强执行"""
        # 多路径探索 (复杂任务)
        if EnhancementType.MULTI_PATH in analysis.enabled_enhancements:
            result = await self._execute_multi_path(query, analysis)
            if result:
                return result
        
        # 世界模型模拟 (高风险)
        if EnhancementType.WORLD_MODEL in analysis.enabled_enhancements:
            result = await self._execute_world_model(query, analysis)
            if result:
                return result
        
        # 集体智能 (多领域)
        if EnhancementType.COLLECTIVE in analysis.enabled_enhancements:
            result = await self._execute_collective(query, analysis)
            if result:
                return result
        
        # 反思循环 (失败后)
        if EnhancementType.REFLECTION in analysis.enabled_enhancements:
            result = await self._execute_reflective(query, analysis)
            if result:
                return result
        
        # 基础执行
        return await self._base_execute(query)
    
    async def _execute_multi_path(
        self,
        query: str,
        analysis: TaskAnalysis
    ) -> Optional[str]:
        """多路径探索"""
        if self._multi_path_explorer is None:
            try:
                from core.multi_path_explorer import MultiPathExplorer, ExplorerConfig
                self._multi_path_explorer = MultiPathExplorer(ExplorerConfig(max_parallel_paths=3))
            except ImportError:
                return None
        
        # 简化执行
        return None
    
    async def _execute_world_model(
        self,
        query: str,
        analysis: TaskAnalysis
    ) -> Optional[str]:
        """世界模型模拟"""
        if self._world_model is None:
            try:
                from core.world_model_simulator import SimulationEngine
                self._world_model = SimulationEngine()
            except ImportError:
                return None
        
        return None
    
    async def _execute_collective(
        self,
        query: str,
        analysis: TaskAnalysis
    ) -> Optional[str]:
        """集体智能"""
        if self._collective is None:
            try:
                from core.collective_intelligence import CollectiveIntelligence
                self._collective = CollectiveIntelligence()
            except ImportError:
                return None
        
        return None
    
    async def _execute_reflective(
        self,
        query: str,
        analysis: TaskAnalysis
    ) -> Optional[str]:
        """反思循环"""
        if self._reflective_agent is None:
            try:
                from core.reflective_agent import ReflectiveAgentLoop
                self._reflective_agent = ReflectiveAgentLoop()
            except ImportError:
                return None
        
        return None
    
    async def _base_execute(self, query: str) -> str:
        """基础执行"""
        return f"[执行] {query}"
    
    # ==================== 渐进式学习 ====================
    
    async def _learn_from_result(
        self,
        query: str,
        result: str,
        analysis: TaskAnalysis
    ):
        """从结果中学习"""
        # 判断是否成功
        is_success = self._check_success(result)
        
        if is_success:
            # 渐进式学习：提取技能
            await self._extract_skill(query, result, analysis)
        else:
            # 反思式学习：记录教训
            await self._extract_lesson(query, result, analysis)
    
    def _check_success(self, result: str) -> bool:
        """检查是否成功"""
        fail_keywords = ["错误", "失败", "error", "failed", "exception", "抱歉"]
        return not any(kw in result.lower() for kw in fail_keywords)
    
    async def _extract_skill(
        self,
        query: str,
        result: str,
        analysis: TaskAnalysis
    ):
        """提取技能"""
        # 生成技能ID
        skill_id = self._generate_id(query)
        
        # 检查是否已存在
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            skill.success_count += 1
            
            # 更新动作（如果更好）
            if len(result) < len(skill.action) * 1.5:
                skill.action = result
            
            # 更新质量
            skill.avg_quality = (skill.avg_quality * (skill.success_count - 1) + 1.0) / skill.success_count
        else:
            # 创建新技能
            skill = LearnedSkill(
                skill_id=skill_id,
                name=self._generate_skill_name(query),
                description=f"处理 {','.join(analysis.domains)} 任务",
                triggers=self._extract_triggers(query),
                action=result,
                success_count=1
            )
            self._skills[skill_id] = skill
    
    async def _extract_lesson(
        self,
        query: str,
        result: str,
        analysis: TaskAnalysis
    ):
        """提取失败教训"""
        lesson_id = self._generate_id(query + "_fail")
        
        # 创建教训
        lesson = FailureLesson(
            lesson_id=lesson_id,
            query_pattern=query[:50],
            failure_reason=result[:100],
            original_attempt=query,
            improved_attempt="",  # 待反思改进后填充
            improvement_strategy=""
        )
        
        self._lessons[lesson_id] = lesson
    
    def _generate_id(self, text: str) -> str:
        """生成ID"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:12]
    
    def _generate_skill_name(self, query: str) -> str:
        """生成技能名称"""
        # 取前30字符
        name = query[:30]
        if len(query) > 30:
            name += "..."
        return name
    
    def _extract_triggers(self, query: str) -> List[str]:
        """提取触发词"""
        triggers = []
        
        # 取前20字符
        if len(query) > 20:
            triggers.append(query[:20])
        
        # 提取关键词
        words = query.split()
        for word in words[:5]:
            if len(word) >= 3:
                triggers.append(word)
        
        return list(set(triggers))
    
    # ==================== 反思改进 ====================
    
    async def reflect_and_improve(self, lesson_id: str, improved_query: str):
        """反思并改进
        
        当用户或系统提供改进后的查询时，更新教训记录
        """
        if lesson_id in self._lessons:
            lesson = self._lessons[lesson_id]
            lesson.improved_attempt = improved_query
            lesson.improvement_strategy = "manual_reflection"
            
            # 如果有对应的技能，更新它
            skill_id = self._generate_id(lesson.query_pattern)
            if skill_id in self._skills:
                self._skills[skill_id].is_refined = True
    
    # ==================== 统计接口 ====================
    
    def get_skills_summary(self) -> Dict[str, Any]:
        """获取技能摘要"""
        return {
            "total_skills": len(self._skills),
            "total_uses": sum(s.use_count for s in self._skills.values()),
            "refined_skills": sum(1 for s in self._skills.values() if s.is_refined),
            "skills": [
                {
                    "name": s.name,
                    "use_count": s.use_count,
                    "success_rate": s.success_count / s.use_count if s.use_count > 0 else 0
                }
                for s in list(self._skills.values())[:10]
            ]
        }
    
    def get_lessons_summary(self) -> Dict[str, Any]:
        """获取教训摘要"""
        return {
            "total_lessons": len(self._lessons),
            "total_encounters": sum(l.times_encountered for l in self._lessons.values()),
            "lessons": [
                {
                    "pattern": l.query_pattern[:30],
                    "encounters": l.times_encountered,
                    "improved": bool(l.improved_attempt)
                }
                for l in list(self._lessons.values())[:10]
            ]
        }
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """获取集成统计"""
        return {
            "skills": self.get_skills_summary(),
            "lessons": self.get_lessons_summary(),
            "enhancer": self._enhancer.get_stats()
        }


# ==================== 便捷工厂函数 ====================

def create_enhanced_agent(config: Dict[str, Any] = None) -> EnhancedIntegration:
    """创建增强Agent工厂"""
    return EnhancedIntegration(config)


async def quick_chat(message: str) -> str:
    """快速聊天 - 一行代码使用"""
    agent = create_enhanced_agent()
    return await agent.chat(message)
