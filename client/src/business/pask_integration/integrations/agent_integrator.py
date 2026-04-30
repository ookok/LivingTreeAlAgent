"""
AgentIntegrator - 智能体集成器

将 PASK 主动式智能体与现有的 HermesAgent 集成。
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from ..demand_detector import DemandDetector
from ..proactive_agent import ProactiveAgent
from business.hermes_agent import (
    UserProfile,
    UserPreference,
    PreferenceType,
    InteractionRecord
)


class AgentIntegrator:
    """智能体集成器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentIntegrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化集成器"""
        if self._initialized:
            return
        
        self._logger = logger.bind(component="AgentIntegrator")
        self._detector = DemandDetector()
        self._proactive_agent = ProactiveAgent()
        self._hermes_agent = None  # 延迟加载
        
        self._initialized = True
        self._logger.info("AgentIntegrator 初始化完成")
    
    def _get_hermes_agent(self):
        """延迟加载 HermesAgent"""
        if self._hermes_agent is None:
            from business.hermes_agent import HermesAgent
            self._hermes_agent = HermesAgent.get_instance()
        return self._hermes_agent
    
    async def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        处理用户消息，集成需求检测和主动行为
        
        Args:
            user_id: 用户ID
            message: 用户消息
            
        Returns:
            处理结果
        """
        # 使用 PASK 检测需求
        detection_result = self._detector.process_message(message)
        
        # 获取潜在需求
        latent_needs = self._detector.get_latent_needs()
        
        # 生成主动行为
        needs_dict = [need.to_dict() for need in latent_needs]
        actions = await self._proactive_agent.generate_actions(needs_dict)
        
        # 执行最高优先级的主动行为
        executed_action = await self._proactive_agent.execute_next_action()
        
        # 更新 Hermes 用户画像
        self._update_user_profile(user_id, message, detection_result)
        
        return {
            "detection": detection_result,
            "latent_needs": needs_dict,
            "generated_actions": [a.to_dict() for a in actions],
            "executed_action": executed_action.to_dict() if executed_action else None
        }
    
    def _update_user_profile(self, user_id: str, message: str, detection_result: Dict[str, Any]):
        """更新 Hermes 用户画像"""
        try:
            hermes = self._get_hermes_agent()
            
            # 根据检测结果更新用户画像
            intents = detection_result.get("intents", [])
            for intent in intents:
                intent_type = intent.get("intent_type", "")
                
                if intent_type == "question":
                    hermes.add_preference(
                        user_id=user_id,
                        preference=UserPreference(
                            type=PreferenceType.TOPIC,
                            value="知识问答",
                            evidence=[message]
                        )
                    )
                elif intent_type == "request":
                    hermes.add_preference(
                        user_id=user_id,
                        preference=UserPreference(
                            type=PreferenceType.WORKFLOW,
                            value="任务请求",
                            evidence=[message]
                        )
                    )
                elif intent_type == "planning":
                    hermes.add_preference(
                        user_id=user_id,
                        preference=UserPreference(
                            type=PreferenceType.HABIT,
                            value="日程规划",
                            evidence=[message]
                        )
                    )
            
            self._logger.debug(f"已更新用户画像: {user_id}")
            
        except Exception as e:
            self._logger.warning(f"更新用户画像失败: {e}")
    
    def get_latent_needs(self) -> List[Dict[str, Any]]:
        """获取检测到的潜在需求"""
        needs = self._detector.get_latent_needs()
        return [need.to_dict() for need in needs]
    
    def get_pending_actions(self) -> List[Dict[str, Any]]:
        """获取待执行的主动行为"""
        actions = self._proactive_agent.get_pending_actions()
        return [a.to_dict() for a in actions]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "detector_history_length": len(self._detector._conversation_history),
            "pending_actions": len(self._proactive_agent.get_pending_actions()),
            "executed_actions": len(self._proactive_agent.get_executed_actions()),
            "proactive_enabled": self._proactive_agent._confidence_threshold > 0
        }
    
    @classmethod
    def get_instance(cls) -> "AgentIntegrator":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance