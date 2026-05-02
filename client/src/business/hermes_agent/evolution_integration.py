"""
进化系统与Hermes Agent的集成层

将自我进化能力与现有的Agent系统无缝对接：
- 经验积累 ↔ 用户画像
- Skill评估 ↔ 工具使用记录
- 策略进化 ↔ 自适应学习循环
- 反馈收集 ↔ 用户反馈记录
"""
from typing import Optional, Dict, List, Any
import logging

from business.evolution import (
    EvolutionSystem,
    TaskType,
    SkillUsage,
    HumanFeedback,
    FeedbackType
)
from . import UserProfileManager, get_profile_manager
from .adaptive_learning_loop import AdaptiveLearningLoop

logger = logging.getLogger(__name__)


class EvolutionIntegration:
    """进化系统集成器"""

    def __init__(self):
        self.evolution_system = EvolutionSystem()
        self.profile_manager = get_profile_manager()
        self.learning_loop = AdaptiveLearningLoop()

    async def record_task_completion(
        self,
        user_id: str,
        task_type: str,
        task_description: str,
        tools_used: List[str],
        success: bool,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        记录任务完成情况，同时更新进化系统和用户画像
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            task_description: 任务描述
            tools_used: 使用的工具列表
            success: 是否成功
            execution_time: 执行时间（秒）
            metadata: 元数据
        
        Returns:
            experience_id: 经验ID
        """
        # 转换任务类型
        task_type_enum = self._convert_task_type(task_type)
        
        # 创建SkillUsage列表
        skill_usages = [
            SkillUsage(
                skill_name=tool,
                input_params={},
                output_result={},
                execution_time=execution_time / len(tools_used) if tools_used else execution_time,
                success=success
            )
            for tool in tools_used
        ]
        
        # 记录到进化系统
        experience_id = self.evolution_system.record_experience(
            task_type=task_type_enum,
            task_description=task_description,
            skills_used=skill_usages,
            success=success,
            execution_time=execution_time,
            metadata=metadata
        )
        
        # 更新用户画像
        if user_id:
            self.profile_manager.record_interaction(
                user_id=user_id,
                query=task_description,
                response="任务执行完成",
                context={"topic": task_type},
                tools=tools_used
            )
            
            # 记录成功/失败模式
            profile = self.profile_manager.profiles.get(user_id)
            if profile:
                pattern = f"{task_type}: {task_description[:50]}..."
                if success and pattern not in profile.successful_patterns:
                    profile.successful_patterns.append(pattern)
                elif not success and pattern not in profile.failed_patterns:
                    profile.failed_patterns.append(pattern)
        
        # 更新自适应学习循环
        await self.learning_loop.learn(
            task=task_description,
            result={"tools_used": tools_used, "success": success},
            feedback=None
        )
        
        logger.info(f"✅ 任务记录完成: {experience_id}")
        return experience_id

    def record_feedback(
        self,
        experience_id: str,
        user_id: str,
        rating: int,
        feedback_type: str = "thumbs_up",
        comments: str = "",
        suggested_improvements: Optional[List[str]] = None
    ):
        """
        记录用户反馈，同时更新进化系统和用户画像
        
        Args:
            experience_id: 经验ID
            user_id: 用户ID
            rating: 评分（1-5）
            feedback_type: 反馈类型
            comments: 评论
            suggested_improvements: 改进建议
        """
        # 转换反馈类型
        feedback_type_enum = FeedbackType.THUMBS_UP if rating >= 4 else FeedbackType.THUMBS_DOWN
        
        # 创建HumanFeedback对象
        human_feedback = HumanFeedback(
            feedback_type=feedback_type_enum,
            rating=rating,
            comments=comments,
            suggested_improvements=suggested_improvements or []
        )
        
        # 更新进化系统
        self.evolution_system.add_feedback(experience_id, human_feedback)
        
        # 更新用户画像
        if user_id:
            self.profile_manager.record_feedback(
                interaction_id=f"ir_{experience_id.split('_')[1]}",
                feedback=feedback_type,
                rating=rating / 5.0  # 归一化到0-1
            )
        
        # 如果有改进建议，学习这些事实
        if suggested_improvements and user_id:
            for improvement in suggested_improvements:
                self.profile_manager.learn_fact(user_id, f"improvement_{experience_id}", improvement)
        
        logger.info(f"✅ 反馈记录完成: {experience_id}, 评分: {rating}")

    def suggest_tools(self, task_description: str) -> List[Dict[str, Any]]:
        """
        根据任务描述推荐工具
        
        Args:
            task_description: 任务描述
        
        Returns:
            推荐的工具列表
        """
        return self.evolution_system.suggest_skills(task_description)

    async def run_skill_discovery(self):
        """运行技能发现，自动发现新模式"""
        result = self.evolution_system.run_skill_discovery()
        
        if result.new_skills:
            logger.info(f"🔍 发现 {len(result.new_skills)} 个新技能")
            for skill in result.new_skills:
                logger.info(f"  - {skill.name}: {skill.description}")
        
        if result.improved_skills:
            logger.info(f"🔧 发现 {len(result.improved_skills)} 个改进机会")
        
        return result

    def get_evolution_summary(self, days: int = 7) -> Dict[str, Any]:
        """获取进化摘要"""
        return self.evolution_system.get_evolution_summary(days)

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的进化事件"""
        events = self.evolution_system.get_recent_events(limit)
        return [{
            "event_id": e.event_id,
            "event_type": e.event_type.value,
            "timestamp": str(e.timestamp),
            "description": e.description,
            "impact": e.impact.value,
            "confidence": e.confidence
        } for e in events]

    def _convert_task_type(self, task_type: str) -> TaskType:
        """将字符串任务类型转换为枚举"""
        task_type_lower = task_type.lower()
        
        if any(kw in task_type_lower for kw in ["code", "代码", "编程"]):
            return TaskType.CODE_GENERATION
        elif any(kw in task_type_lower for kw in ["document", "文档", "写作"]):
            return TaskType.DOCUMENT_WRITING
        elif any(kw in task_type_lower for kw in ["data", "分析", "统计"]):
            return TaskType.DATA_ANALYSIS
        elif any(kw in task_type_lower for kw in ["ui", "界面", "前端"]):
            return TaskType.UI_GENERATION
        elif any(kw in task_type_lower for kw in ["plan", "规划", "任务"]):
            return TaskType.TASK_PLANNING
        else:
            return TaskType.OTHER


# ==================== 单例 ====================

_evolution_integration: Optional[EvolutionIntegration] = None


def get_evolution_integration() -> EvolutionIntegration:
    """获取进化集成器单例"""
    global _evolution_integration
    if _evolution_integration is None:
        _evolution_integration = EvolutionIntegration()
    return _evolution_integration


# ==================== 便捷函数 ====================

async def record_task(
    user_id: str,
    task_type: str,
    task_description: str,
    tools_used: List[str],
    success: bool,
    execution_time: float
) -> str:
    """便捷函数：记录任务"""
    integration = get_evolution_integration()
    return await integration.record_task_completion(
        user_id=user_id,
        task_type=task_type,
        task_description=task_description,
        tools_used=tools_used,
        success=success,
        execution_time=execution_time
    )


def record_user_feedback(
    experience_id: str,
    user_id: str,
    rating: int,
    comments: str = "",
    suggested_improvements: Optional[List[str]] = None
):
    """便捷函数：记录用户反馈"""
    integration = get_evolution_integration()
    integration.record_feedback(
        experience_id=experience_id,
        user_id=user_id,
        rating=rating,
        comments=comments,
        suggested_improvements=suggested_improvements
    )


def recommend_tools(task_description: str) -> List[Dict[str, Any]]:
    """便捷函数：推荐工具"""
    integration = get_evolution_integration()
    return integration.suggest_tools(task_description)