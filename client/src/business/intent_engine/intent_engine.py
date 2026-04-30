# -*- coding: utf-8 -*-
"""
IntentEngine - 意图引擎主入口
==============================

整合所有组件，提供统一的意图解析 API。

使用方式：
    engine = IntentEngine()
    intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")
    
    print(intent.intent_type)    # IntentType.CODE_GENERATION
    print(intent.tech_stack)      # ['fastapi', 'python']
    print(intent.action)          # 编写
    print(intent.target)          # 登录接口
from __future__ import annotations
"""


from typing import Optional, List, Dict, Any
from .intent_types import Intent, IntentType, IntentPriority
from .intent_parser import IntentParser
from .tech_stack_detector import TechStackDetector
from .constraint_extractor import ConstraintExtractor
from .composite_detector import CompositeDetector


class IntentEngine:
    """
    意图引擎
    
    整合意图解析、技术栈检测、约束提取、复合意图检测。
    
    设计原则：
    1. 快速响应：优先使用规则匹配，无需 LLM 调用
    2. 可扩展：各组件独立，易于替换和增强
    3. 可解释：每一步都有置信度，便于调试
    """
    
    def __init__(
        self,
        use_llm_enhancement: bool = False,
        project_context: Optional[str] = None,
    ):
        """
        初始化意图引擎
        
        Args:
            use_llm_enhancement: 是否使用 LLM 增强解析
            project_context: 项目上下文（如 package.json、requirements.txt 内容）
        """
        self.use_llm_enhancement = use_llm_enhancement
        self.project_context = project_context or ""
        
        # 初始化各组件
        self.parser = IntentParser()
        self.tech_detector = TechStackDetector()
        self.constraint_extractor = ConstraintExtractor()
        self.composite_detector = CompositeDetector()
        
        # 统计信息
        self.stats = {
            "total_parsed": 0,
            "composite_detected": 0,
            "avg_confidence": 0.0,
        }
    
    def parse(self, query: str) -> Intent:
        """
        解析用户查询为结构化意图
        
        Args:
            query: 自然语言查询
            
        Returns:
            Intent: 结构化的意图对象
        """
        # 1. 基础解析（意图类型 + 动作 + 目标）
        intent = self.parser.parse(query)
        
        # 2. 技术栈检测
        tech_stack, tech_confidence = self.tech_detector.detect(query)
        intent.tech_stack = tech_stack
        intent.tech_confidence = tech_confidence
        
        # 如果项目上下文存在，尝试推断技术栈
        if not tech_stack and self.project_context:
            stacks_from_ctx, _ = self.tech_detector.detect(self.project_context)
            if stacks_from_ctx:
                intent.tech_stack = stacks_from_ctx
                intent.tech_confidence = 0.6  # 降级置信度
        
        # 3. 约束提取
        constraints, constraint_confidence = self.constraint_extractor.extract(query)
        intent.constraints = constraints
        
        # 4. 复合意图检测
        is_composite, sub_intents = self.composite_detector.detect(query)
        if is_composite:
            intent.is_composite = True
            intent.sub_intents = sub_intents
            intent.intent_type = IntentType.MULTIPLE
        
        # 5. 合并置信度
        intent.confidence = self._calculate_final_confidence(
            intent, tech_confidence, constraint_confidence
        )
        
        # 6. 计算完整性
        intent.completeness = self._calculate_completeness(intent)
        
        # 更新统计
        self._update_stats(intent)
        
        return intent
    
    def parse_batch(self, queries: List[str]) -> List[Intent]:
        """批量解析"""
        return [self.parse(q) for q in queries]
    
    def _calculate_final_confidence(
        self,
        intent: Intent,
        tech_confidence: float,
        constraint_confidence: float,
    ) -> float:
        """计算最终置信度"""
        weights = {
            "intent_type": 0.4,
            "tech_stack": 0.3,
            "constraints": 0.2,
            "completeness": 0.1,
        }
        
        scores = {
            "intent_type": intent.confidence,
            "tech_stack": tech_confidence if intent.tech_stack else 0.5,
            "constraints": constraint_confidence,
            "completeness": intent.completeness,
        }
        
        final = sum(weights[k] * scores[k] for k in weights)
        
        # 复合意图降低置信度
        if intent.is_composite:
            final *= 0.9
        
        return min(final, 0.98)  # 最高不超过 0.98
    
    def _calculate_completeness(self, intent: Intent) -> float:
        """计算意图完整性"""
        score = 0.0
        
        # 意图类型明确 (+0.2)
        if intent.intent_type != IntentType.UNKNOWN:
            score += 0.2
        
        # 有动作词 (+0.15)
        if intent.action:
            score += 0.15
        
        # 有目标 (+0.25)
        if intent.target:
            score += 0.25
        
        # 技术栈明确 (+0.2)
        if intent.tech_stack:
            score += 0.2
        
        # 约束明确 (+0.1)
        if intent.constraints:
            score += 0.1
        
        # 有描述 (+0.1)
        if intent.target_description:
            score += 0.1
        
        return min(score, 1.0)
    
    def _update_stats(self, intent: Intent):
        """更新统计信息"""
        self.stats["total_parsed"] += 1
        if intent.is_composite:
            self.stats["composite_detected"] += 1
        
        # 滑动平均置信度
        n = self.stats["total_parsed"]
        old_avg = self.stats["avg_confidence"]
        self.stats["avg_confidence"] = (old_avg * (n - 1) + intent.confidence) / n
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "composite_rate": (
                self.stats["composite_detected"] / self.stats["total_parsed"]
                if self.stats["total_parsed"] > 0 else 0
            ),
        }
    
    def suggest_model(self, intent: Intent) -> str:
        """
        根据意图类型建议使用的模型
        
        通过 config_provider 读取模型层级映射，不再硬编码模型名。
        
        Returns:
            模型名称
        """
        # 简单任务 → L1
        simple_intents = {
            IntentType.KNOWLEDGE_QUERY,
            IntentType.CONCEPT_EXPLANATION,
            IntentType.CODE_EXPLANATION,
        }
        
        # 中等任务 → L3
        medium_intents = {
            IntentType.CODE_GENERATION,
            IntentType.CODE_MODIFICATION,
            IntentType.DEBUGGING,
            IntentType.BUG_FIX,
            IntentType.CODE_UNDERSTANDING,
            IntentType.CODE_REVIEW,
        }
        
        # 复杂任务 → L4
        complex_intents = {
            IntentType.API_DESIGN,
            IntentType.DATABASE_DESIGN,
            IntentType.CODE_REFACTOR,
            IntentType.CODE_OPTIMIZATION,
            IntentType.PERFORMANCE_ANALYSIS,
            IntentType.DEPLOYMENT,
            IntentType.MULTIPLE,
        }
        
        # 从系统配置读取对应层级的模型
        try:
            from business.config_provider import get_l1_model, get_l3_model, get_l4_model
            if intent.intent_type in simple_intents:
                return get_l1_model()
            elif intent.intent_type in medium_intents:
                return get_l3_model()
            elif intent.intent_type in complex_intents:
                return get_l4_model()
            else:
                return get_l3_model()
        except Exception:
            # 配置读取失败时回退
            if intent.intent_type in simple_intents:
                return "qwen2.5:1.5b"
            elif intent.intent_type in complex_intents:
                return "qwen3.5:9b"
            else:
                return "qwen3.5:4b"
    
    def explain(self, intent: Intent) -> str:
        """
        生成意图解释
        
        用于调试和日志。
        """
        lines = [
            f"## 意图解析结果",
            f"",
            f"**原始查询**: {intent.raw_input}",
            f"**意图类型**: {intent.intent_type.value}",
            f"**动作**: {intent.action or '(未识别)'}",
            f"**目标**: {intent.target or '(未识别)'}",
            f"**优先级**: {intent.priority.name}",
            f"",
            f"### 技术栈",
            f"- 检测到: {', '.join(intent.tech_stack) if intent.tech_stack else '无'}",
            f"- 置信度: {intent.tech_confidence:.2f}",
            f"",
            f"### 约束条件",
        ]
        
        if intent.constraints:
            for c in intent.constraints:
                req = "[必须]" if c.required else "[可选]"
                lines.append(f"- {req} {c.name}: {c.value}")
        else:
            lines.append("- 无")
        
        lines.extend([
            f"",
            f"### 质量指标",
            f"- 整体置信度: {intent.confidence:.2f}",
            f"- 完整性: {intent.completeness:.2f}",
            f"- 是否复合: {'是' if intent.is_composite else '否'}",
        ])
        
        if intent.is_composite:
            lines.append(f"- 子意图数量: {len(intent.sub_intents)}")
        
        lines.append(f"")
        lines.append(f"### 建议模型")
        lines.append(f"- {self.suggest_model(intent)}")
        
        return "\n".join(lines)
