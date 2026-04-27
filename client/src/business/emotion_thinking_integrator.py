"""
情绪感知与思考模式集成器
=========================

将情绪感知和专家思考模式无缝集成，实现智能的情绪适配回复。

工作流程：
1. 用户消息 → 情绪感知模块（识别情绪）
2. 情绪结果 → 思考模式选择器（选择合适的思考模式）
3. 思考模式 → 思考模式控制器（注入指令）
4. 最终 → 生成情绪适配的专家回复

Author: LivingTreeAI Team
Date: 2026-04-27
"""

import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============= 数据类 =============

@dataclass
class IntegratedResult:
    """集成处理结果"""
    emotion_result: Dict  # 情绪识别结果
    thinking_mode: str      # 选择的思考模式
    enhanced_prompt: str    # 增强后的Prompt
    emotion_instruction: str # 情绪适配指令
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "emotion": self.emotion_result,
            "thinking_mode": self.thinking_mode,
            "enhanced_prompt": self.enhanced_prompt[:200] + "...",  # 截断，避免过长
            "emotion_instruction": self.emotion_instruction,
        }


# ============= 集成器 =============

class EmotionThinkingIntegrator:
    """
    情绪感知与思考模式集成器
    
    功能：
    1. 自动情绪识别
    2. 智能思考模式选择
    3. 情绪适配指令生成
    4. 与GlobalModelRouter无缝集成
    """
    
    def __init__(self, use_llm: bool = True):
        """
        初始化集成器
        
        Args:
            use_llm: 是否使用LLM进行情绪识别
        """
        self.use_llm = use_llm
        self._emotion_perception = None
        self._thinking_controller = None
        
        logger.info(f"[EmotionThinkingIntegrator] 初始化完成，use_llm={use_llm}")
    
    def _get_emotion_perception(self):
        """延迟加载情绪感知器"""
        if self._emotion_perception is None:
            try:
                from client.src.business.emotion_perception import get_emotion_perception
                self._emotion_perception = get_emotion_perception(use_llm=self.use_llm)
            except ImportError as e:
                logger.error(f"情绪感知模块导入失败: {e}")
                return None
        return self._emotion_perception
    
    def _get_thinking_controller(self):
        """延迟加载思考模式控制器"""
        if self._thinking_controller is None:
            try:
                from client.src.business.ei_agent.expert_thinking_mode import (
                    get_expert_thinking_controller
                )
                self._thinking_controller = get_expert_thinking_controller()
            except ImportError as e:
                logger.error(f"思考模式控制器导入失败: {e}")
                return None
        return self._thinking_controller
    
    async def process(
        self,
        user_message: str,
        expert_type: str = "environmental_assessment",
        context: Optional[List[dict]] = None,
        force_thinking_mode: Optional[str] = None,  # 强制指定思考模式（可选）
    ) -> IntegratedResult:
        """
        处理用户消息（完整集成流程）
        
        Args:
            user_message: 用户消息
            expert_type: 专家类型
            context: 对话上下文
            force_thinking_mode: 强制指定思考模式（如果提供，跳过自动选择）
            
        Returns:
            IntegratedResult: 集成处理结果
        """
        # 1. 情绪感知
        perception = self._get_emotion_perception()
        if perception is None:
            logger.warning("[集成器] 情绪感知模块不可用，跳过情绪识别")
            emotion_result = {
                "emotion_type": "neutral",
                "intensity": 0.0,
                "confidence": 0.0,
            }
        else:
            emotion_result_obj = await perception.perceive(user_message, context)
            emotion_result = emotion_result_obj.to_dict()
        
        # 2. 选择思考模式
        if force_thinking_mode:
            thinking_mode = force_thinking_mode
            logger.info(f"[集成器] 强制使用思考模式: {thinking_mode}")
        else:
            thinking_mode = self._select_thinking_mode(emotion_result)
        
        # 3. 设置思考模式控制器
        controller = self._get_thinking_controller()
        if controller is None:
            logger.error("[集成器] 思考模式控制器不可用")
            return IntegratedResult(
                emotion_result=emotion_result,
                thinking_mode=thinking_mode,
                enhanced_prompt="",
                emotion_instruction="",
            )
        
        # 设置专家类型（动态，按名称字符串，无枚举）
        if expert_type:
            if not controller.set_expert_by_name(expert_type):
                logger.warning(f"[集成器] 设置专家类型失败: {expert_type}，将尝试自动匹配")

        # 设置思考模式（动态，按名称字符串）
        if thinking_mode:
            if not controller.set_thinking_mode_by_name(thinking_mode):
                logger.warning(f"[集成器] 设置思考模式失败: {thinking_mode}")
        
        # 设置情绪状态
        controller.set_emotional_state(
            emotion_result["emotion_type"],
            emotion_result["intensity"]
        )
        
        # 4. 生成增强Prompt（这里需要外部提供base prompt）
        # 注意：这个方法只返回配置，实际的prompt增强需要在调用处完成
        emotion_instruction = controller._generate_emotion_instruction()
        
        logger.info(
            f"[集成器] 处理完成: emotion={emotion_result['emotion_type']}, "
            f"mode={thinking_mode}, intensity={emotion_result['intensity']}"
        )
        
        return IntegratedResult(
            emotion_result=emotion_result,
            thinking_mode=thinking_mode,
            enhanced_prompt="",  # 需要外部调用controller.get_enhanced_system_prompt()
            emotion_instruction=emotion_instruction,
        )
    
    def _select_thinking_mode(self, emotion_result: dict) -> str:
        """
        根据情绪选择思考模式
        
        Args:
            emotion_result: 情绪识别结果
            
        Returns:
            思考模式字符串
        """
        emotion_type = emotion_result.get("emotion_type", "neutral")
        intensity = emotion_result.get("intensity", 0.0)
        
        # 高强度负面情绪 → 分析式（更理性、更专业）
        if emotion_type in ["anger", "anxious", "frustrated", "disappointed", "worried"]:
            if intensity > 0.7:
                return "analytical"
            else:
                return "guided"
        
        # 困惑情绪 → 引导式（更注重引导和建议）
        if emotion_type in ["confused", "lost", "helpless"]:
            return "guided"
        
        # 正面情绪 → 沉浸式（更亲切、更有同理心）
        if emotion_type in ["joy", "happy", "satisfied", "excited", "relieved"]:
            return "immersive"
        
        # 中性情绪 → 沉浸式（默认）
        return "immersive"
    
    async def process_and_enhance_prompt(
        self,
        user_message: str,
        base_system_prompt: str,
        expert_type: str = "environmental_assessment",
        context: Optional[List[dict]] = None,
        force_thinking_mode: Optional[str] = None,
    ) -> Tuple[IntegratedResult, str]:
        """
        处理用户消息并增强System Prompt（一步完成）
        
        Args:
            user_message: 用户消息
            base_system_prompt: 基础System Prompt
            expert_type: 专家类型
            context: 对话上下文
            force_thinking_mode: 强制指定思考模式
            
        Returns:
            (IntegratedResult, enhanced_prompt)
        """
        # 处理消息
        result = await self.process(
            user_message=user_message,
            expert_type=expert_type,
            context=context,
            force_thinking_mode=force_thinking_mode,
        )
        
        # 增强Prompt
        controller = self._get_thinking_controller()
        if controller:
            enhanced_prompt = controller.get_enhanced_system_prompt(base_system_prompt)
            result.enhanced_prompt = enhanced_prompt
        else:
            enhanced_prompt = base_system_prompt
        
        return result, enhanced_prompt
    
    async def process_and_enhance_messages(
        self,
        user_message: str,
        messages: List[Dict[str, str]],
        expert_type: str = "environmental_assessment",
        context: Optional[List[dict]] = None,
        force_thinking_mode: Optional[str] = None,
    ) -> Tuple[IntegratedResult, List[Dict[str, str]]]:
        """
        处理用户消息并增强消息列表（一步完成）
        
        Args:
            user_message: 用户消息
            messages: 原始消息列表
            expert_type: 专家类型
            context: 对话上下文
            force_thinking_mode: 强制指定思考模式
            
        Returns:
            (IntegratedResult, enhanced_messages)
        """
        # 处理消息
        result = await self.process(
            user_message=user_message,
            expert_type=expert_type,
            context=context,
            force_thinking_mode=force_thinking_mode,
        )
        
        # 增强消息列表
        controller = self._get_thinking_controller()
        if controller:
            enhanced_messages = controller.inject_to_messages(messages)
            # 更新result中的enhanced_prompt
            result.enhanced_prompt = enhanced_messages[0].get("content", "") if enhanced_messages else ""
        else:
            enhanced_messages = messages
        
        return result, enhanced_messages


# ============= 全局单例 =============

_default_integrator: Optional[EmotionThinkingIntegrator] = None

def get_emotion_thinking_integrator(use_llm: bool = True) -> EmotionThinkingIntegrator:
    """获取集成器实例（单例）"""
    global _default_integrator
    if _default_integrator is None:
        _default_integrator = EmotionThinkingIntegrator(use_llm=use_llm)
    return _default_integrator


# ============= 便捷函数 =============

async def process_with_emotion_and_thinking(
    user_message: str,
    base_system_prompt: str,
    expert_type: str = "environmental_assessment",
    context: Optional[List[dict]] = None,
) -> Tuple[dict, str]:
    """
    便捷函数：处理用户消息（集成情绪感知和思考模式）
    
    Args:
        user_message: 用户消息
        base_system_prompt: 基础System Prompt
        expert_type: 专家类型
        context: 对话上下文
        
    Returns:
        (emotion_result, enhanced_prompt)
    """
    integrator = get_emotion_thinking_integrator()
    result, enhanced_prompt = await integrator.process_and_enhance_prompt(
        user_message=user_message,
        base_system_prompt=base_system_prompt,
        expert_type=expert_type,
        context=context,
    )
    return result.to_dict(), enhanced_prompt


# ============= 测试代码 =============

if __name__ == "__main__":
    import asyncio
    
    async def test_integrator():
        """测试集成器"""
        print("🧪 测试情绪感知与思考模式集成器")
        print("=" * 60)
        
        integrator = EmotionThinkingIntegrator(use_llm=False)  # 使用关键词匹配
        
        test_cases = [
            ("你们这个系统太垃圾了！", "environmental_assessment"),
            ("我有点困惑，不知道该怎么填写", "environmental_assessment"),
            ("太好了！终于成功了！", "environmental_assessment"),
            ("帮我看看这个项目的情况", "regulation"),
        ]
        
        for user_msg, expert_type in test_cases:
            print(f"\n用户消息: {user_msg}")
            print(f"专家类型: {expert_type}")
            
            # 处理并增强Prompt
            result, enhanced_prompt = await integrator.process_and_enhance_prompt(
                user_message=user_msg,
                base_system_prompt="你是一个环评专家。",
                expert_type=expert_type,
            )
            
            print(f"情绪识别: {result.emotion_result}")
            print(f"思考模式: {result.thinking_mode}")
            print(f"情绪指令: {result.emotion_instruction[:100]}...")
            print(f"增强Prompt长度: {len(enhanced_prompt)}")
            print("-" * 60)
        
        print("\n✅ 测试完成！")
    
    asyncio.run(test_integrator())
