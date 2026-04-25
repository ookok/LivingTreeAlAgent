"""
智能提示系统 — 意图引擎
=======================
用 SmolLM2 本地实时分析情境，生成温暖人心的提示语
"""

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import re

from .models import ContextInfo, GeneratedHint, HintType, HintLevel, HintConfig
from .hint_templates import HintTemplateStore


class IntentCategory(Enum):
    """意图类别"""
    # 决策类
    DECISION_COMPARE = "decision_compare"        # 比较决策
    DECISION_RISK = "decision_risk"              # 风险决策
    DECISION_PRIORITY = "decision_priority"     # 优先级决策

    # 操作类
    OPERATION_HINT = "operation_hint"           # 操作提示
    OPERATION_SHORTCUT = "operation_shortcut"    # 快捷键
    OPERATION_WARNING = "operation_warning"      # 操作警告

    # 学习类
    LEARNING_EXPLANATION = "learning_explanation"  # 解释说明
    LEARNING_TIP = "learning_tip"                # 小技巧
    LEARNING_CONTEXT = "learning_context"        # 上下文补充

    # 情感类
    EMOTIONAL_SUPPORT = "emotional_support"      # 情感支持
    EMOTIONAL_CELEBRATE = "emotional_celebrate"  # 庆祝成功
    EMOTIONAL_COMFORT = "emotional_comfort"      # 安慰


@dataclass
class IntentResult:
    """意图分析结果"""
    category: IntentCategory
    primary_intent: str
    confidence: float
    suggested_actions: List[str] = field(default_factory=list)
    context_summary: str = ""
    emotional_tone: str = "neutral"  # warm/neutral/playful/professional


class HintIntentEngine:
    """
    提示意图引擎

    功能：
    1. 分析 ContextInfo，理解用户当前情境
    2. 匹配最佳提示模板或生成 AI 提示
    3. 融合用户画像，生成个性化提示
    4. 控制提示频率，避免打扰
    """

    # 提示生成系统提示词
    SYSTEM_PROMPT = """你是一个温暖的 AI 助手，名字叫"小叶子"。

你的职责是在用户操作时提供贴心、简短、有用的提示。

要求：
1. 语气温暖友好，像朋友聊天
2. 每条提示不超过 50 字
3. 优先用 Emoji 表达情感
4. 主动提供有价值的信息，不废话
5. 如果检测到问题，用关心的方式提醒

温度公式 = 共情开头 + 利益点 + 行动建议
示例：
- 冷："推荐 Ollama，因为稳定。"
- 暖："嘿，看你网络有点波动，用本地 Ollama 会更稳哦～"

当前用户环境信息：{device_info}
当前场景：{scene_name}
用户正在：{user_action}
用户目标：{user_goal}
可用选项：{options}

历史行为：{action_history}

请生成 1-3 条简短提示。"""

    def __init__(
        self,
        template_store: HintTemplateStore = None,
        config: HintConfig = None
    ):
        self.config = config or HintConfig()
        self.template_store = template_store or HintTemplateStore()

        # 本地模型调用（延迟加载）
        self._local_client = None
        self._use_local = True

        # 缓存
        self._hint_cache: Dict[str, Tuple[GeneratedHint, float]] = {}
        self._cache_ttl = 30  # 缓存30秒

        # 频率控制
        self._last_hint_time: Dict[str, datetime] = {}
        self._min_interval = 10  # 同一场景最少间隔秒数

        # 忽略列表
        self._dismissed_hints: Dict[str, int] = {}
        self._max_dismiss_before_hide = 3

        # 订阅上下文
        self._context_callbacks: List[Callable[[ContextInfo], None]] = []

    def _get_local_client(self):
        """获取本地模型客户端（延迟加载）"""
        if self._local_client is None:
            try:
                from client.src.business.smolllm2 import get_l0_router
                self._local_client = get_l0_router()
            except ImportError:
                try:
                    from client.src.business.system_brain import get_system_brain
                    self._local_client = get_system_brain()
                except ImportError:
                    self._local_client = None
                    self._use_local = False
        return self._local_client

    def analyze_context(self, context: ContextInfo) -> IntentResult:
        """分析上下文，返回意图结果"""
        # 缓存检查
        cache_key = context.scene_id
        if cache_key in self._hint_cache:
            cached_hint, cached_time = self._hint_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return IntentResult(
                    category=IntentCategory.OPERATION_HINT,
                    primary_intent="cache_hit",
                    confidence=1.0,
                    context_summary=f"缓存命中: {cached_hint.content[:30]}..."
                )

        # 意图分类
        category = self._classify_intent(context)

        # 构建上下文摘要
        context_summary = self._build_context_summary(context)

        return IntentResult(
            category=category,
            primary_intent=context.user_action or context.scene_id,
            confidence=0.8,
            context_summary=context_summary,
            emotional_tone=self._detect_emotional_tone(context)
        )

    def _classify_intent(self, context: ContextInfo) -> IntentCategory:
        """意图分类"""
        scene_id = context.scene_id.lower()
        action = context.user_action.lower()
        options_count = len(context.options)

        # 决策类
        if options_count >= 2 or "选择" in action or "比较" in action:
            if any(k in action for k in ["风险", "安全", "可靠"]):
                return IntentCategory.DECISION_RISK
            return IntentCategory.DECISION_COMPARE

        # 操作警告
        if any(k in action for k in ["删除", "危险", "警告", "注意"]):
            return IntentCategory.OPERATION_WARNING

        # 快捷键
        if any(k in action for k in ["快捷键", "shortcut", "快速"]):
            return IntentCategory.OPERATION_SHORTCUT

        # 情感支持
        if any(k in action for k in ["失败", "错误", "困难", "卡住"]):
            return IntentCategory.EMOTIONAL_COMFORT

        # 学习类
        if any(k in context.scene_id for k in ["learn", "tutorial", "help"]):
            return IntentCategory.LEARNING_TIP

        # 场景特定
        if "model_select" in scene_id:
            return IntentCategory.DECISION_COMPARE
        if "chat" in scene_id:
            return IntentCategory.EMOTIONAL_SUPPORT

        return IntentCategory.OPERATION_HINT

    def _build_context_summary(self, context: ContextInfo) -> str:
        """构建上下文摘要"""
        parts = []
        if context.scene_name:
            parts.append(f"场景：{context.scene_name}")
        if context.user_action:
            parts.append(f"动作：{context.user_action}")
        if context.user_goal:
            parts.append(f"目标：{context.user_goal}")
        if context.options:
            parts.append(f"选项：{', '.join(context.options[:3])}")
        if context.device_info:
            info = context.device_info
            if "network" in info:
                parts.append(f"网络：{info['network']}")
            if "memory" in info:
                parts.append(f"内存：{info['memory']}%")
        return " | ".join(parts)

    def _detect_emotional_tone(self, context: ContextInfo) -> str:
        """检测情感基调"""
        action = context.user_action.lower()
        if any(k in action for k in ["失败", "错误", "挫折", "困难"]):
            return "warm"
        if any(k in action for k in ["成功", "完成", "好"]):
            return "celebrate"
        if context.urgency > 0.7:
            return "professional"
        return "warm"

    def generate_hint(
        self,
        context: ContextInfo,
        intent: IntentResult = None,
        force: bool = False
    ) -> Optional[GeneratedHint]:
        """生成提示"""
        # 频率控制
        if not force:
            last_time = self._last_hint_time.get(context.scene_id)
            if last_time:
                elapsed = (datetime.now() - last_time).total_seconds()
                if elapsed < self._min_interval:
                    return None
            if self._dismissed_hints.get(context.scene_id, 0) >= self._max_dismiss_before_hide:
                return None

        intent = intent or self.analyze_context(context)

        # 1. 尝试模板匹配
        template_hint = self._match_template(context, intent)
        if template_hint:
            return template_hint

        # 2. 尝试本地模型生成
        if self.config.use_local_model:
            ai_hint = self._generate_with_local_model(context, intent)
            if ai_hint:
                self._hint_cache[context.scene_id] = (ai_hint, time.time())
                self._last_hint_time[context.scene_id] = datetime.now()
                return ai_hint

        # 3. 回退到默认提示
        return self._generate_default_hint(context, intent)

    def _match_template(
        self,
        context: ContextInfo,
        intent: IntentResult
    ) -> Optional[GeneratedHint]:
        """匹配提示模板"""
        templates = self.template_store.get_templates(
            scene_id=context.scene_id,
            hint_type=self._intent_to_hint_type(intent.category)
        )
        if not templates:
            return None

        best_template = None
        best_score = 0
        for template in templates:
            score = self._score_template(template, context, intent)
            if score > best_score:
                best_score = score
                best_template = template

        if best_template and best_score > 0.3:
            return self.template_store.fill_template(best_template, context)
        return None

    def _score_template(
        self,
        template,
        context: ContextInfo,
        intent: IntentResult
    ) -> float:
        """给模板打分"""
        score = 0.0
        if template.scene_id == context.scene_id:
            score += 0.5
        if template.hint_type == self._intent_to_hint_type(intent.category):
            score += 0.3
        if context.device_info:
            if template.conditions.get("network") and context.device_info.get("network"):
                score += 0.1
            if template.conditions.get("memory") and context.device_info.get("memory"):
                score += 0.1
        return score

    def _intent_to_hint_type(self, category: IntentCategory) -> HintType:
        """意图类别转提示类型"""
        mapping = {
            IntentCategory.DECISION_COMPARE: HintType.COMPARISON_HINT,
            IntentCategory.DECISION_RISK: HintType.ACTION_WARNING,
            IntentCategory.DECISION_PRIORITY: HintType.RECOMMENDATION,
            IntentCategory.OPERATION_HINT: HintType.ACTION_SUGGESTION,
            IntentCategory.OPERATION_SHORTCUT: HintType.ACTION_SHORTCUT,
            IntentCategory.OPERATION_WARNING: HintType.ACTION_WARNING,
            IntentCategory.LEARNING_EXPLANATION: HintType.LEARNING_HINT,
            IntentCategory.LEARNING_TIP: HintType.PROACTIVE_HELP,
            IntentCategory.LEARNING_CONTEXT: HintType.CONTEXT_REMINDER,
            IntentCategory.EMOTIONAL_SUPPORT: HintType.PROACTIVE_HELP,
            IntentCategory.EMOTIONAL_CELEBRATE: HintType.CELEBRATION,
            IntentCategory.EMOTIONAL_COMFORT: HintType.COMFORT,
        }
        return mapping.get(category, HintType.PROACTIVE_HELP)

    def _generate_with_local_model(
        self,
        context: ContextInfo,
        intent: IntentResult
    ) -> Optional[GeneratedHint]:
        """使用本地模型生成提示"""
        client = self._get_local_client()
        if not client:
            return None

        try:
            prompt = self._build_prompt(context)
            response = None

            if hasattr(client, "generate"):
                response = client.generate(prompt, max_tokens=200)
            elif hasattr(client, "quick_route"):
                response = client.quick_route(prompt)
                if hasattr(response, "route"):
                    response = str(response.route)

            return self._parse_model_response(response, context, intent)

        except Exception as e:
            print(f"Local model generation failed: {e}")
            self._use_local = False
            return None

    def _build_prompt(self, context: ContextInfo) -> str:
        """构建提示词"""
        device_info = json.dumps(context.device_info or {}, ensure_ascii=False)
        action_history = ", ".join(context.user_history[-5:] or ["无"])

        return self.SYSTEM_PROMPT.format(
            device_info=device_info,
            scene_name=context.scene_name,
            user_action=context.user_action or "未知",
            user_goal=context.user_goal or "未知",
            options=", ".join(context.options[:5]) if context.options else "无",
            action_history=action_history
        )

    def _parse_model_response(
        self,
        response: Any,
        context: ContextInfo,
        intent: IntentResult
    ) -> Optional[GeneratedHint]:
        """解析模型响应"""
        if not response:
            return None

        text = str(response).strip()
        emoji = "💡"
        content = text

        # 提取 Emoji
        emoji_match = re.search(r'[\U0001F300-\U0001F9FF]', text)
        if emoji_match:
            emoji = emoji_match.group(0)
            content = text.replace(emoji, "", 1).strip()

        content = content.strip('"\n ')
        if len(content) > 200:
            content = content[:200] + "..."

        if not content:
            return None

        return GeneratedHint(
            hint_id=f"hint_{datetime.now().timestamp()}",
            hint_type=self._intent_to_hint_type(intent.category),
            hint_level=self._context_to_level(context),
            title="",
            content=content,
            emoji=emoji,
            context=context,
            source="intent_engine",
            confidence=intent.confidence
        )

    def _context_to_level(self, context: ContextInfo) -> HintLevel:
        """上下文转提示层级"""
        if context.urgency > 0.8:
            return HintLevel.IMPORTANT
        if context.importance > 0.7:
            return HintLevel.GENTLE
        return HintLevel.GLOW

    def _generate_default_hint(
        self,
        context: ContextInfo,
        intent: IntentResult
    ) -> Optional[GeneratedHint]:
        """生成默认提示"""
        templates = self.template_store.get_templates(scene_id=context.scene_id)
        if templates:
            return self.template_store.fill_template(templates[0], context)

        default_contents = {
            "model_select": "选模型不纠结？本地模型稳定快速，云模型能力更强～",
            "chat": "有问题随时问我，我在这里帮你～",
            "writing": "写作遇到瓶颈？试试让我帮你整理思路",
            "network_issue": "网络有点不稳，先用本地功能吧～",
            "low_performance": "系统有点累，减少点后台任务会更流畅哦",
        }

        content = default_contents.get(context.scene_id, "有问题尽管问～")

        return GeneratedHint(
            hint_id=f"hint_{datetime.now().timestamp()}",
            hint_type=self._intent_to_hint_type(intent.category),
            hint_level=self._context_to_level(context),
            title="",
            content=content,
            emoji="💡",
            context=context,
            source="default",
            confidence=0.5
        )

    def dismiss_hint(self, hint_id: str, scene_id: str) -> None:
        """用户忽略提示"""
        self._dismissed_hints[scene_id] = self._dismissed_hints.get(scene_id, 0) + 1

    def reset_dismissals(self, scene_id: str) -> None:
        """重置忽略计数"""
        self._dismissed_hints[scene_id] = 0

    def subscribe_to_context(self, callback: Callable[[ContextInfo], None]) -> None:
        """订阅上下文更新"""
        self._context_callbacks.append(callback)

    def on_context_update(self, context: ContextInfo) -> Optional[GeneratedHint]:
        """上下文更新回调"""
        intent = self.analyze_context(context)
        return self.generate_hint(context, intent)


# 全局单例
_engine_instance: Optional[HintIntentEngine] = None
_engine_lock = threading.Lock()


def get_hint_engine() -> HintIntentEngine:
    """获取提示意图引擎单例"""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = HintIntentEngine()
        return _engine_instance
