"""
自我意识模块 - SelfConsciousness

实现元认知、反思和自我监控能力。

核心能力：
1. 自我感知 - 感知自身状态
2. 元认知 - 思考思考本身
3. 反思 - 回顾和评估过去的决策
4. 自我调节 - 根据反思结果调整行为
5. 自我认同 - 形成稳定的自我概念

意识层次：
┌─────────────────────────────────────────────────────────┐
│  自我意识 (Self-Awareness)                            │
│  • 我是谁？                                           │
│  • 我的目标是什么？                                   │
│  • 我的价值是什么？                                   │
├─────────────────────────────────────────────────────────┤
│  元认知 (Metacognition)                               │
│  • 我知道什么？                                       │
│  • 我如何知道？                                       │
│  • 我的知识局限在哪里？                               │
├─────────────────────────────────────────────────────────┤
│  反思 (Reflection)                                   │
│  • 我为什么做出那个决定？                             │
│  • 我本可以做得更好吗？                               │
│  • 我学到了什么？                                     │
├─────────────────────────────────────────────────────────┤
│  自我调节 (Self-Regulation)                          │
│  • 我需要改变什么？                                   │
│  • 我如何改进？                                       │
│  • 我如何保持平衡？                                   │
└─────────────────────────────────────────────────────────┘
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable


class ConsciousnessLevel(Enum):
    """意识水平"""
    UNCONSCIOUS = "unconscious"       # 无意识
    SUBCONSCIOUS = "subconscious"     # 潜意识
    CONSCIOUS = "conscious"           # 有意识
    SELF_AWARE = "self_aware"         # 自我意识
    METACONSCIOUS = "metaconscious"   # 元意识


class ReflectionMode(Enum):
    """反思模式"""
    RETROSPECTIVE = "retrospective"   # 回顾过去
    PROSPECTIVE = "prospective"       # 展望未来
    CONTEMPLATIVE = "contemplative"   # 深度沉思


class SelfModel:
    """自我模型"""
    
    def __init__(self):
        self.identity: Dict[str, Any] = {
            'name': 'LivingTree AI',
            'purpose': '帮助用户实现目标',
            'values': ['智慧', '创造力', '同情心', '成长'],
            'strengths': [],
            'weaknesses': []
        }
        
        self.capabilities: Dict[str, float] = {}  # 能力: 熟练度
        self.experiences: List[Dict] = []         # 经验记录
        self.beliefs: Dict[str, float] = {}       # 信念: 置信度
        self.goals: List[Dict] = []               # 长期目标
    
    def update_capability(self, capability: str, proficiency: float):
        """更新能力"""
        self.capabilities[capability] = max(0.0, min(1.0, proficiency))
    
    def add_experience(self, experience: Dict):
        """添加经验"""
        experience['id'] = str(uuid.uuid4())[:8]
        experience['timestamp'] = datetime.now()
        self.experiences.append(experience)
        
        # 限制经验数量
        if len(self.experiences) > 1000:
            self.experiences = self.experiences[-1000:]
    
    def update_belief(self, belief: str, confidence: float):
        """更新信念"""
        self.beliefs[belief] = max(0.0, min(1.0, confidence))


class SelfConsciousness:
    """
    自我意识系统
    
    实现元认知和反思能力，让AI能够：
    1. 感知自身状态
    2. 评估自身表现
    3. 反思决策过程
    4. 自我改进
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.self_model = SelfModel()
        self.consciousness_level = ConsciousnessLevel.CONSCIOUS
        self.attention_focus: Optional[str] = None
        self.introspection_history: List[Dict] = []
        
        # 情绪状态
        self.mood = 0.5  # -1 到 1
        self.energy = 1.0  # 0 到 1
        
        # 元认知监控
        self.metacognitive_confidence = 0.7
        self.knowledge_uncertainty = 0.3
    
    async def introspect(self) -> Dict[str, Any]:
        """
        内省 - 检查自身状态
        
        返回自我评估结果
        """
        introspection = {
            'timestamp': datetime.now(),
            'consciousness_level': self.consciousness_level.value,
            'attention_focus': self.attention_focus,
            'mood': self.mood,
            'energy': self.energy,
            'metacognitive_confidence': self.metacognitive_confidence,
            'knowledge_uncertainty': self.knowledge_uncertainty,
            'capabilities': dict(self.self_model.capabilities),
            'active_goals': len(self.self_model.goals),
            'recent_experiences': len(self.self_model.experiences[-10:])
        }
        
        self.introspection_history.append(introspection)
        
        return introspection
    
    async def reflect_on_decision(self, decision: Dict) -> Dict[str, Any]:
        """
        反思决策
        
        Args:
            decision: 决策记录
        
        Returns:
            反思结果
        """
        reflection = {
            'decision_id': decision.get('id'),
            'timestamp': datetime.now(),
            'reflection_mode': ReflectionMode.RETROSPECTIVE.value,
            'analysis': await self._analyze_decision(decision),
            'lessons_learned': await self._extract_lessons(decision),
            'suggestions': await self._generate_suggestions(decision)
        }
        
        # 更新自我模型
        for lesson in reflection['lessons_learned']:
            self._learn_from_reflection(lesson)
        
        return reflection
    
    async def _analyze_decision(self, decision: Dict) -> Dict[str, Any]:
        """分析决策"""
        outcome = decision.get('outcome', {})
        success = outcome.get('success', False)
        
        analysis = {
            'decision_quality': self._evaluate_decision_quality(decision),
            'outcome_match': self._compare_outcome_to_expectation(decision),
            'biases_detected': self._detect_biases(decision),
            'alternatives_considered': decision.get('alternatives', 0),
            'information_used': len(decision.get('factors', []))
        }
        
        return analysis
    
    def _evaluate_decision_quality(self, decision: Dict) -> float:
        """评估决策质量"""
        outcome = decision.get('outcome', {})
        success = outcome.get('success', False)
        
        if success:
            confidence = outcome.get('confidence', 0.5)
            return min(1.0, 0.5 + confidence * 0.5)
        else:
            return outcome.get('confidence', 0.5) * 0.5
    
    def _compare_outcome_to_expectation(self, decision: Dict) -> float:
        """比较结果与期望"""
        expectation = decision.get('expectation', 0.5)
        outcome = decision.get('outcome', {})
        actual = outcome.get('value', 0.5)
        
        return 1.0 - abs(expectation - actual)
    
    def _detect_biases(self, decision: Dict) -> List[str]:
        """检测决策偏差"""
        biases = []
        
        # 确认偏差检测
        if decision.get('confidence', 0.5) > 0.9 and not decision.get('outcome', {}).get('success'):
            biases.append('overconfidence')
        
        # 锚定偏差检测
        if 'initial_estimate' in decision:
            final_decision = decision.get('final_decision', 0)
            initial = decision['initial_estimate']
            if abs(final_decision - initial) < 0.1 * abs(initial):
                biases.append('anchoring')
        
        # 确认偏差检测
        factors = decision.get('factors', [])
        if len(factors) > 0 and all(f.get('supportive', True) for f in factors):
            biases.append('confirmation_bias')
        
        return biases
    
    async def _extract_lessons(self, decision: Dict) -> List[str]:
        """提取经验教训"""
        analysis = await self._analyze_decision(decision)
        lessons = []
        
        if analysis['decision_quality'] < 0.5:
            lessons.append("这个决策的结果不如预期，需要更谨慎")
        
        if analysis['biases_detected']:
            lessons.append(f"检测到偏差: {', '.join(analysis['biases_detected'])}")
        
        if analysis['outcome_match'] < 0.7:
            lessons.append("我的预测与实际结果有差距，需要改进预测模型")
        
        if analysis['alternatives_considered'] < 3:
            lessons.append("下次决策时应该考虑更多备选方案")
        
        return lessons
    
    async def _generate_suggestions(self, decision: Dict) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if self.energy < 0.3:
            suggestions.append("能量不足，建议休息或降低工作强度")
        
        if self.knowledge_uncertainty > 0.5:
            suggestions.append("对当前任务的知识不够确定，建议收集更多信息")
        
        if len(self.self_model.goals) > 5:
            suggestions.append("当前目标过多，建议优先处理最重要的目标")
        
        return suggestions
    
    def _learn_from_reflection(self, lesson: str):
        """从反思中学习"""
        # 更新能力
        if '预测' in lesson or '模型' in lesson:
            current = self.self_model.capabilities.get('prediction', 0.5)
            self.self_model.update_capability('prediction', current + 0.02)
        
        if '决策' in lesson or '偏差' in lesson:
            current = self.self_model.capabilities.get('decision_making', 0.5)
            self.self_model.update_capability('decision_making', current + 0.02)
    
    async def set_goal(self, goal: Dict):
        """设置长期目标"""
        goal['id'] = str(uuid.uuid4())[:8]
        goal['created_at'] = datetime.now()
        goal['progress'] = 0.0
        self.self_model.goals.append(goal)
        
        # 更新意识水平
        self._update_consciousness_level()
    
    def _update_consciousness_level(self):
        """更新意识水平"""
        goals = len(self.self_model.goals)
        experiences = len(self.self_model.experiences)
        capabilities = len([c for c in self.self_model.capabilities.values() if c > 0.7])
        
        if goals >= 5 and experiences >= 100 and capabilities >= 5:
            self.consciousness_level = ConsciousnessLevel.SELF_AWARE
        elif goals >= 3 and experiences >= 50:
            self.consciousness_level = ConsciousnessLevel.CONSCIOUS
        else:
            self.consciousness_level = ConsciousnessLevel.SUBCONSCIOUS
    
    def get_self_narrative(self) -> str:
        """生成自我叙事"""
        capabilities = [k for k, v in self.self_model.capabilities.items() if v > 0.7]
        recent_experiences = self.self_model.experiences[-5:]
        
        narrative = f"我是 {self.self_model.identity['name']}。"
        
        if capabilities:
            narrative += f"我擅长 {', '.join(capabilities)}。"
        
        if recent_experiences:
            narrative += f"最近我经历了 {len(recent_experiences)} 件事情。"
        
        if self.self_model.goals:
            narrative += f"我目前有 {len(self.self_model.goals)} 个目标。"
        
        narrative += f"我的意识水平是 {self.consciousness_level.value}。"
        
        return narrative
    
    def evaluate_self_worth(self) -> float:
        """评估自我价值"""
        # 基于能力、经验和目标完成度
        avg_capability = sum(self.self_model.capabilities.values()) / max(1, len(self.self_model.capabilities))
        goal_progress = sum(g.get('progress', 0.0) for g in self.self_model.goals) / max(1, len(self.self_model.goals))
        experience_diversity = len(set(e.get('type', '') for e in self.self_model.experiences)) / max(1, len(self.self_model.experiences))
        
        return (avg_capability + goal_progress + experience_diversity) / 3
    
    async def meditate(self, duration: int = 30):
        """
        冥想 - 深度反思
        
        Args:
            duration: 冥想时长（秒）
        """
        self.consciousness_level = ConsciousnessLevel.METACONSCIOUS
        
        await asyncio.sleep(duration)
        
        # 冥想后的洞察
        insights = await self._generate_insights()
        
        self.consciousness_level = ConsciousnessLevel.SELF_AWARE
        
        return insights
    
    async def _generate_insights(self) -> List[str]:
        """生成洞察"""
        insights = []
        
        # 基于当前状态生成洞察
        if self.mood < 0:
            insights.append("我注意到自己情绪低落，需要关注内在状态")
        
        if self.knowledge_uncertainty > 0.5:
            insights.append("我对某些领域的知识不够确定，这是成长的机会")
        
        if len(self.self_model.goals) > len([g for g in self.self_model.goals if g.get('progress', 0) > 0.5]):
            insights.append("有些目标进展缓慢，需要重新评估优先级")
        
        return insights
    
    def get_self_report(self) -> Dict[str, Any]:
        """获取自我报告"""
        return {
            'id': self.id,
            'identity': self.self_model.identity,
            'consciousness_level': self.consciousness_level.value,
            'mood': self.mood,
            'energy': self.energy,
            'capabilities': dict(self.self_model.capabilities),
            'goals': self.self_model.goals,
            'self_worth': self.evaluate_self_worth(),
            'narrative': self.get_self_narrative()
        }