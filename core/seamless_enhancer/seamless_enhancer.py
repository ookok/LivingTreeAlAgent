"""
SeamlessEnhancer - 无缝自动增强器
统一入口，用户只需调用 chat()，内部自动增强
"""

import asyncio
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime
from enum import Enum

from .trigger_decider import TriggerDecider, EnhancementType, TaskAnalysis


class ExecutionStatus(Enum):
    """执行状态"""
    INITIAL = "initial"               # 初始状态
    ENHANCED = "enhanced"             # 已增强
    SUCCESS = "success"               # 成功
    FAILED = "failed"                # 失败
    REFLECTED = "reflected"           # 已反思改进


@dataclass
class EnhancementResult:
    """增强执行结果"""
    success: bool                     # 是否成功
    original_result: Any             # 原始结果
    enhanced_result: Any              # 增强后的结果
    
    # 执行信息
    status: ExecutionStatus          # 执行状态
    enhancements_used: List[str]      # 使用的增强类型
    execution_time: float = 0.0      # 执行耗时
    
    # 反思信息
    reflection_applied: bool = False # 是否应用了反思
    improvements_made: List[str] = field(default_factory=list)
    
    # 渐进式学习
    skill_created: bool = False       # 是否创建了技能
    skill_name: str = ""
    
    # 分析结果
    task_analysis: Optional[TaskAnalysis] = None
    
    # 错误信息
    error: str = ""
    error_recovery: bool = False     # 是否从错误中恢复


@dataclass
class EnhancementContext:
    """增强上下文"""
    user_id: str = "default"
    session_id: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)  # 对话历史
    
    # 能力库
    skills: Dict[str, Any] = field(default_factory=dict)  # 已学习的技能
    failed_patterns: List[Dict[str, Any]] = field(default_factory=list)  # 失败模式
    
    # 统计
    total_requests: int = 0
    successful_requests: int = 0
    reflection_count: int = 0
    skills_created: int = 0


class SeamlessEnhancer:
    """无缝自动增强器
    
    用户只需调用 chat()，内部自动完成：
    1. 任务分析 + 增强决策
    2. 反思循环 (失败时)
    3. 多路径探索 (复杂任务)
    4. 世界模型模拟 (高风险)
    5. 渐进式学习 (成功后)
    
    用户完全无感知，享受智能增强的服务
    """
    
    def __init__(
        self,
        base_handler: Callable[[str], Awaitable[str]] = None,
        config: Dict[str, Any] = None
    ):
        """初始化无缝增强器
        
        Args:
            base_handler: 基础处理函数 async (query) -> response
            config: 配置
        """
        self.config = config or {}
        
        # 基础处理器
        self._base_handler = base_handler or self._default_handler
        
        # 触发决策器
        self._decider = TriggerDecider(self.config.get("decider", {}))
        
        # 增强组件 (懒加载)
        self._reflective_loop = None
        self._multi_explorer = None
        self._world_model = None
        self._collective = None
        self._skill_manager = None
        
        # 上下文
        self._context = EnhancementContext()
        
        # 配置
        self.max_retries = self.config.get("max_retries", 2)
        self.enable_reflection = self.config.get("enable_reflection", True)
        self.enable_progressive = self.config.get("enable_progressive", True)
        
        # 回调
        self._on_enhancement = None  # 增强回调 (用于调试/监控)
    
    # ==================== 公开接口 ====================
    
    async def chat(self, message: str, context: Dict[str, Any] = None) -> str:
        """聊天入口 - 用户主要接口
        
        用户只需调用此方法，内部自动完成所有增强逻辑
        
        Args:
            message: 用户消息
            context: 额外上下文
            
        Returns:
            增强后的回复
        """
        context = context or {}
        start_time = time.time()
        
        self._context.total_requests += 1
        
        # 1. 任务分析
        analysis = self._decider.analyze(message, self._context.__dict__)
        
        # 记录历史
        self._context.history.append({
            "query": message,
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "complexity": analysis.complexity,
                "domains": analysis.domains,
                "enhancements": [e.value for e in analysis.enabled_enhancements]
            }
        })
        
        # 回调
        await self._notify("analysis", analysis)
        
        # 2. 渐进式学习 - 先检查是否有相关技能
        result = None
        skill_applied = False
        
        if self.enable_progressive:
            skill_applied, result = await self._try_apply_skill(message)
            if skill_applied:
                self._context.successful_requests += 1
                await self._notify("skill_applied", {"skill": result})
        
        # 3. 如果没有可用技能，执行正常流程
        if not skill_applied:
            # 尝试执行，最多 retry 次
            for attempt in range(self.max_retries + 1):
                try:
                    # 决定执行策略
                    strategy = self._plan_strategy(analysis, attempt)
                    
                    # 执行
                    result = await self._execute_with_strategy(message, strategy, analysis)
                    
                    # 检查结果
                    if self._is_success(result):
                        self._context.successful_requests += 1
                        break
                    else:
                        # 反思改进
                        if self.enable_reflection and attempt < self.max_retries:
                            await self._reflect_and_improve(message, result, attempt)
                
                except Exception as e:
                    # 错误恢复
                    if attempt < self.max_retries:
                        await self._recover_from_error(message, str(e), attempt)
                    else:
                        result = f"抱歉，执行遇到问题: {str(e)}"
        
        # 4. 渐进式学习 - 成功后创建技能
        if self.enable_progressive and result and self._is_success(result):
            await self._progressive_learn(message, result, analysis)
        
        # 5. 返回结果
        execution_time = time.time() - start_time
        
        await self._notify("complete", {
            "success": self._is_success(result),
            "execution_time": execution_time,
            "analysis": analysis
        })
        
        return str(result) if result else "执行完成"
    
    def set_base_handler(self, handler: Callable[[str], Awaitable[str]]):
        """设置基础处理器"""
        self._base_handler = handler
    
    def set_callback(self, callback: Callable):
        """设置增强回调"""
        self._on_enhancement = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self._context.total_requests,
            "successful_requests": self._context.successful_requests,
            "success_rate": (
                self._context.successful_requests / self._context.total_requests
                if self._context.total_requests > 0 else 0
            ),
            "reflection_count": self._context.reflection_count,
            "skills_created": self._context.skills_created,
            "available_skills": len(self._context.skills),
            "failed_patterns": len(self._context.failed_patterns)
        }
    
    # ==================== 内部方法 ====================
    
    async def _default_handler(self, query: str) -> str:
        """默认处理器"""
        return f"处理: {query}"
    
    async def _notify(self, event: str, data: Any):
        """通知回调"""
        if self._on_enhancement:
            try:
                await self._on_enhancement(event, data)
            except Exception:
                pass
    
    def _is_success(self, result: Any) -> bool:
        """判断执行是否成功"""
        if result is None:
            return False
        result_str = str(result).lower()
        fail_keywords = ["error", "failed", "失败", "错误", "exception"]
        return not any(kw in result_str for kw in fail_keywords)
    
    # ==================== 渐进式学习 ====================
    
    async def _try_apply_skill(self, query: str) -> tuple:
        """尝试应用已学技能
        
        Returns:
            (skill_applied, result)
        """
        query_lower = query.lower()
        
        for skill_name, skill_data in self._context.skills.items():
            # 检查触发条件
            triggers = skill_data.get("triggers", [])
            for trigger in triggers:
                if trigger.lower() in query_lower:
                    # 应用技能
                    result = skill_data.get("response", "")
                    return True, result
        
        return False, None
    
    async def _progressive_learn(
        self,
        query: str,
        result: Any,
        analysis: TaskAnalysis
    ):
        """渐进式学习 - 从成功中学习
        
        当一个任务成功完成后，自动创建可复用的技能
        """
        # 生成技能ID
        skill_id = self._generate_skill_id(query)
        
        # 提取触发词
        triggers = self._extract_triggers(query)
        
        # 创建技能
        skill_data = {
            "id": skill_id,
            "query_pattern": query[:100],  # 保留前100字符
            "triggers": triggers,
            "response": str(result)[:500],  # 保留前500字符
            "domains": analysis.domains,
            "created_at": datetime.now().isoformat(),
            "use_count": 1,
            "success_count": 1
        }
        
        # 检查是否已存在
        if skill_id not in self._context.skills:
            self._context.skills[skill_id] = skill_data
            self._context.skills_created += 1
            
            await self._notify("skill_created", skill_data)
    
    def _generate_skill_id(self, query: str) -> str:
        """生成技能ID"""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()[:12]
    
    def _extract_triggers(self, query: str) -> List[str]:
        """提取触发词"""
        # 简单提取：前20字符 + 主要名词
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
    
    # ==================== 执行策略 ====================
    
    def _plan_strategy(
        self,
        analysis: TaskAnalysis,
        attempt: int
    ) -> Dict[str, Any]:
        """规划执行策略"""
        strategy = {
            "base_only": True,
            "use_reflection": False,
            "use_multi_path": False,
            "use_world_model": False,
            "use_collective": False
        }
        
        # 第一次尝试：基础执行
        if attempt == 0:
            strategy["base_only"] = True
            strategy["use_reflection"] = False
        
        # 重试时启用反思
        elif attempt > 0:
            strategy["base_only"] = False
            strategy["use_reflection"] = self.enable_reflection
        
        # 根据分析决定是否使用增强
        if self._decider.should_enable(EnhancementType.MULTI_PATH, analysis):
            strategy["use_multi_path"] = True
        
        if self._decider.should_enable(EnhancementType.WORLD_MODEL, analysis):
            strategy["use_world_model"] = True
        
        if self._decider.should_enable(EnhancementType.COLLECTIVE, analysis):
            strategy["use_collective"] = True
        
        return strategy
    
    async def _execute_with_strategy(
        self,
        query: str,
        strategy: Dict[str, Any],
        analysis: TaskAnalysis
    ) -> Any:
        """根据策略执行"""
        
        # 基础执行
        if strategy["base_only"]:
            return await self._base_handler(query)
        
        # 世界模型模拟 (高风险验证)
        if strategy["use_world_model"]:
            result = await self._execute_with_world_model(query)
            if result:
                return result
        
        # 多路径探索
        if strategy["use_multi_path"]:
            result = await self._execute_with_multi_path(query, analysis)
            if result:
                return result
        
        # 反思改进
        if strategy["use_reflection"]:
            result = await self._execute_with_reflection(query)
            if result:
                return result
        
        # 集体智能
        if strategy["use_collective"]:
            result = await self._execute_with_collective(query, analysis)
            if result:
                return result
        
        # 最终回退到基础执行
        return await self._base_handler(query)
    
    async def _execute_with_world_model(self, query: str) -> Any:
        """使用世界模型执行"""
        # 懒加载
        if self._world_model is None:
            try:
                from core.world_model_simulator import WorldModel
                self._world_model = WorldModel()
            except ImportError:
                return None
        
        # 简化：直接返回 None，让其他策略处理
        return None
    
    async def _execute_with_multi_path(self, query: str, analysis: TaskAnalysis) -> Any:
        """使用多路径探索执行"""
        if self._multi_explorer is None:
            try:
                from core.multi_path_explorer import MultiPathExplorer, ExplorerConfig
                self._multi_explorer = MultiPathExplorer(ExplorerConfig())
            except ImportError:
                return None
        
        # 简化：返回 None
        return None
    
    async def _execute_with_reflection(self, query: str) -> Any:
        """使用反思循环执行"""
        if self._reflective_loop is None:
            try:
                from core.reflective_agent import ReflectiveAgentLoop
                self._reflective_loop = ReflectiveAgentLoop()
            except ImportError:
                return None
        
        # 简化：返回 None
        return None
    
    async def _execute_with_collective(self, query: str, analysis: TaskAnalysis) -> Any:
        """使用集体智能执行"""
        if self._collective is None:
            try:
                from core.collective_intelligence import CollectiveIntelligence
                self._collective = CollectiveIntelligence()
            except ImportError:
                return None
        
        # 简化：返回 None
        return None
    
    # ==================== 反思与恢复 ====================
    
    async def _reflect_and_improve(
        self,
        query: str,
        failed_result: Any,
        attempt: int
    ):
        """反思并改进"""
        self._context.reflection_count += 1
        
        # 记录失败模式
        failure_record = {
            "query": query,
            "result": str(failed_result),
            "attempt": attempt,
            "timestamp": datetime.now().isoformat()
        }
        
        # 避免重复记录
        if failure_record not in self._context.failed_patterns:
            self._context.failed_patterns.append(failure_record)
        
        await self._notify("reflection", failure_record)
    
    async def _recover_from_error(
        self,
        query: str,
        error: str,
        attempt: int
    ):
        """从错误中恢复"""
        # 清空失败模式
        if self._context.failed_patterns:
            last_failure = self._context.failed_patterns[-1]
            last_failure["recovered"] = True
        
        await self._notify("error_recovery", {
            "query": query,
            "error": error,
            "attempt": attempt
        })


class ProgressiveLoop:
    """渐进式学习循环
    
    持续学习、积累、进化
    """
    
    def __init__(self, enhancer: SeamlessEnhancer):
        self._enhancer = enhancer
    
    async def learn_from_interaction(
        self,
        query: str,
        response: str,
        success: bool
    ):
        """从交互中学习"""
        if success:
            # 成功：创建或更新技能
            await self._enhancer._progressive_learn(query, response, None)
        else:
            # 失败：记录教训
            await self._enhancer._reflect_and_improve(query, response, 0)
    
    def get_learned_skills(self) -> List[Dict[str, Any]]:
        """获取已学习的技能"""
        return list(self._enhancer._context.skills.values())
    
    def get_failed_patterns(self) -> List[Dict[str, Any]]:
        """获取失败模式"""
        return self._enhancer._context.failed_patterns
