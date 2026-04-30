"""
SkillIntegrator - 技能系统集成器

将 PASK 主动式智能体与现有的 SkillEvolution 集成。
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from ..demand_detector import LatentNeed
from ..proactive_agent import ProactiveAction
from business.skill_evolution import (
    VibeSkillBuilder,
    SkillEncapsulationEngine,
    SkillRatingSystem,
    SkillVersionControl
)


class SkillIntegrator:
    """技能系统集成器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillIntegrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化集成器"""
        if self._initialized:
            return
        
        self._logger = logger.bind(component="SkillIntegrator")
        
        # 延迟加载，避免初始化时的依赖问题
        self._skill_builder = None
        self._encapsulation_engine = None
        self._rating_system = None
        self._version_control = None
        self._load_dependencies()
        
        self._initialized = True
        self._logger.info("SkillIntegrator 初始化完成")
    
    def _load_dependencies(self):
        """延迟加载依赖"""
        try:
            from business.skill_evolution import (
                VibeSkillBuilder,
                SkillEncapsulationEngine,
                SkillRatingSystem,
                SkillVersionControl
            )
            self._skill_builder = VibeSkillBuilder()
            self._encapsulation_engine = SkillEncapsulationEngine()
            self._rating_system = SkillRatingSystem()
            self._version_control = SkillVersionControl()
            self._logger.debug("技能进化模块加载成功")
        except Exception as e:
            self._logger.warning(f"技能进化模块加载失败: {e}")
    
    def create_skill_from_need(self, need: LatentNeed) -> Optional[Any]:
        """
        根据潜在需求创建技能
        
        Args:
            need: 潜在需求
            
        Returns:
            创建的技能
        """
        if not self._skill_builder:
            self._logger.warning("技能构建器未加载，跳过技能创建")
            return None
        
        try:
            # 根据需求类型创建相应的技能
            skill_name = f"proactive_{need.need_id}"
            
            if "信息解答" in need.description:
                skill = self._skill_builder.create(
                    name=skill_name,
                    description=f"主动提供信息解答，基于用户需求: {need.description}",
                    triggers=["question", "information"],
                    actions=["provide_info"]
                )
            elif "任务管理" in need.description:
                skill = self._skill_builder.create(
                    name=skill_name,
                    description=f"主动管理用户任务，基于用户需求: {need.description}",
                    triggers=["request", "task"],
                    actions=["manage_task"]
                )
            elif "日程管理" in need.description:
                skill = self._skill_builder.create(
                    name=skill_name,
                    description=f"主动安排日程，基于用户需求: {need.description}",
                    triggers=["planning", "schedule"],
                    actions=["schedule"]
                )
            elif "技术支持" in need.description:
                skill = self._skill_builder.create(
                    name=skill_name,
                    description=f"主动提供技术支持，基于用户需求: {need.description}",
                    triggers=["complaint", "error"],
                    actions=["support"]
                )
            else:
                # 默认创建通用技能
                skill = self._skill_builder.create(
                    name=skill_name,
                    description=f"主动响应，基于用户需求: {need.description}",
                    triggers=["general"],
                    actions=["respond"]
                )
            
            # 封装技能
            encapsulated = self._encapsulation_engine.encapsulate(skill)
            
            # 注册版本
            self._version_control.create_version(
                skill_id=skill_name,
                skill=encapsulated,
                change_type="new"
            )
            
            self._logger.info(f"根据需求创建技能: {skill_name}")
            return encapsulated
            
        except Exception as e:
            self._logger.error(f"根据需求创建技能失败: {e}")
            return None
    
    def rate_action_effectiveness(self, action: ProactiveAction, feedback: str, rating: float):
        """
        评价主动行为的效果
        
        Args:
            action: 主动行为
            feedback: 用户反馈
            rating: 评分 (0-1)
        """
        if not self._rating_system:
            self._logger.warning("评分系统未加载，跳过评分")
            return
        
        try:
            # 创建评分记录
            self._rating_system.add_rating(
                skill_id=action.action_id,
                rating=rating,
                feedback=feedback,
                context=action.description
            )
            
            # 根据评分更新技能
            if rating < 0.5:
                self._version_control.create_version(
                    skill_id=action.action_id,
                    skill=None,  # 标记需要改进
                    change_type="fix"
                )
            
            self._logger.debug(f"已评价行为效果: {action.action_id}")
            
        except Exception as e:
            self._logger.warning(f"评价行为效果失败: {e}")
    
    def get_recommended_skills(self, need: LatentNeed) -> List[Any]:
        """
        根据需求获取推荐的技能
        
        Args:
            need: 潜在需求
            
        Returns:
            推荐的技能列表
        """
        if not self._skill_builder:
            self._logger.warning("技能构建器未加载，跳过推荐")
            return []
        
        try:
            # 根据需求优先级和类型匹配技能
            recommendations = []
            
            if need.priority() > 0.7:
                # 高优先级需求，推荐相关技能
                recommendations = self._skill_builder.search(
                    query=need.description,
                    max_results=5
                )
            
            return recommendations
            
        except Exception as e:
            self._logger.warning(f"获取推荐技能失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "skill_builder_status": "active",
            "encapsulation_engine_status": "active",
            "rating_system_status": "active",
            "version_control_status": "active"
        }
    
    @classmethod
    def get_instance(cls) -> "SkillIntegrator":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance