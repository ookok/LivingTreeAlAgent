# experience_optimizer.py — 体验优化引擎

import json
import time
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import asdict

from .models import (
    UIPainPoint, PainType, PainCause,
    ClientConfig, generate_client_id,
)


class ExperienceOptimizer:
    """
    体验优化引擎

    功能：
    1. UI埋点捕获（反复求助/长停留/操作回退）
    2. 痛点原因推断
    3. 自动生成UI补丁
    4. 提示卡片注入
    """

    # 阈值配置
    REPEATED_HELP_THRESHOLD = 3      # 3次反复求助触发
    LONG_STAY_THRESHOLD = 30         # 30秒长停留
    OPERATION_ROLLBACK_WINDOW = 60  # 60秒内操作回退

    def __init__(
        self,
        data_dir: Path = None,
        config: ClientConfig = None,
    ):
        """
        初始化体验优化器

        Args:
            data_dir: 数据存储目录
            config: 客户端配置
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or ClientConfig()
        if not self._config.client_id:
            self._config.client_id = generate_client_id()

        # 存储文件
        self._pain_points_file = self._data_dir / "pain_points.json"
        self._events_file = self._data_dir / "raw_events.json"
        self._hints_file = self._data_dir / "injected_hints.json"

        # 内存缓存
        self._pain_points: Dict[str, UIPainPoint] = {}
        self._raw_events: List[Dict[str, Any]] = []
        self._injected_hints: Dict[str, Dict[str, Any]] = {}

        # 事件追踪（内存）
        self._recent_events: List[Dict[str, Any]] = []  # 最近事件

        # 加载数据
        self._load_pain_points()
        self._load_events()
        self._load_hints()

        # 清理过期事件
        self._cleanup_old_events()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "experience"

    def _load_pain_points(self):
        """加载痛点记录"""
        if self._pain_points_file.exists():
            try:
                with open(self._pain_points_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        pp = UIPainPoint.from_dict(item)
                        self._pain_points[pp.id] = pp
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_events(self):
        """加载原始事件"""
        if self._events_file.exists():
            try:
                with open(self._events_file, "r", encoding="utf-8") as f:
                    self._raw_events = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_hints(self):
        """加载已注入提示"""
        if self._hints_file.exists():
            try:
                with open(self._hints_file, "r", encoding="utf-8") as f:
                    self._injected_hints = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_pain_points(self):
        """保存痛点记录"""
        data = [p.to_dict() for p in self._pain_points.values()]
        with open(self._pain_points_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_events(self):
        """保存原始事件"""
        with open(self._events_file, "w", encoding="utf-8") as f:
            json.dump(self._raw_events, f, ensure_ascii=False, indent=2)

    def _save_hints(self):
        """保存已注入提示"""
        with open(self._hints_file, "w", encoding="utf-8") as f:
            json.dump(self._injected_hints, f, ensure_ascii=False, indent=2)

    def _cleanup_old_events(self):
        """清理过期事件（保留7天）"""
        cutoff = int((datetime.now() - timedelta(days=7)).timestamp())
        self._raw_events = [
            e for e in self._raw_events
            if e.get("timestamp", 0) > cutoff
        ]
        if self._raw_events:
            self._save_events()

    def _generate_pain_id(self, module: str, pain_type: PainType) -> str:
        """生成痛点ID"""
        raw = f"{module}:{pain_type.value}:{int(time.time())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def record_event(
        self,
        event_type: str,
        module: str,
        duration: float = 0,
        metadata: Dict[str, Any] = None,
    ):
        """
        记录UI事件

        Args:
            event_type: 事件类型 (help_request/click/stay/rollback/form_abandon)
            module: 涉及模块
            duration: 持续时间（秒）
            metadata: 额外元数据
        """
        event = {
            "type": event_type,
            "module": module,
            "timestamp": int(time.time()),
            "duration": duration,
            "metadata": metadata or {},
        }

        self._recent_events.append(event)
        self._raw_events.append(event)

        # 阈值检查
        self._check_thresholds(event)

        # 定期保存
        if len(self._raw_events) % 100 == 0:
            self._save_events()

    def _check_thresholds(self, event: Dict[str, Any]):
        """检查阈值并触发痛点记录"""
        now = event["timestamp"]
        module = event["module"]

        # 1. 反复求助检测
        if event["type"] == "help_request":
            recent_helps = [
                e for e in self._recent_events
                if e["type"] == "help_request"
                and e["module"] == module
                and now - e["timestamp"] < 300  # 5分钟内
            ]
            if len(recent_helps) >= self.REPEATED_HELP_THRESHOLD:
                self._create_pain_point(
                    module=module,
                    pain_type=PainType.REPEATED_HELP,
                    cause=PainCause.INSUFFICIENT_HINT,
                    description=f"5分钟内{len(recent_helps)}次求助",
                )

        # 2. 长停留检测
        if event["type"] == "stay" and event["duration"] > self.LONG_STAY_THRESHOLD:
            self._create_pain_point(
                module=module,
                pain_type=PainType.LONG_STAY,
                cause=PainCause.UNKNOWN,
                description=f"停留{event['duration']:.0f}秒",
            )

        # 3. 操作回退检测
        if event["type"] == "rollback":
            self._create_pain_point(
                module=module,
                pain_type=PainType.OPERATION_ROLLBACK,
                cause=PainCause.FLOW_UNCLEAR,
                description="用户在短时间内回退了操作",
            )

        # 4. 表单放弃检测
        if event["type"] == "form_abandon":
            self._create_pain_point(
                module=module,
                pain_type=PainType.FORM_ABANDON,
                cause=PainCause.OPTION_COMPLEX,
                description="用户放弃了填写表单",
            )

    def _create_pain_point(
        self,
        module: str,
        pain_type: PainType,
        cause: PainCause,
        description: str,
    ) -> UIPainPoint:
        """创建痛点记录"""
        pain_id = self._generate_pain_id(module, pain_type)

        # 检查是否已存在（避免重复）
        for existing in self._pain_points.values():
            if existing.module == module and existing.pain_type == pain_type:
                # 累加次数
                existing.count += 1
                self._save_pain_points()
                return existing

        pain_point = UIPainPoint(
            id=pain_id,
            module=module,
            pain_type=pain_type,
            cause=cause,
            description=description,
            timestamp=int(time.time()),
            client_id=self._config.client_id,
            count=1,
            resolved=False,
        )

        self._pain_points[pain_id] = pain_point
        self._save_pain_points()

        return pain_point

    def infer_cause(self, pain_point: UIPainPoint) -> PainCause:
        """
        推断痛点原因（使用启发式规则）

        Args:
            pain_point: 痛点记录

        Returns:
            PainCause: 推断的原因
        """
        module = pain_point.module.lower()
        pain_type = pain_point.pain_type

        # 基于模块的启发式推断
        if "config" in module or "setting" in module:
            return PainCause.DEFAULT_UNREASONABLE
        elif "form" in module or "input" in module:
            return PainCause.OPTION_COMPLEX
        elif "network" in module or "connect" in module:
            return PainCause.NETWORK_ISSUE
        elif "help" in module or "hint" in module:
            return PainCause.INSUFFICIENT_HINT
        elif "flow" in module or "wizard" in module:
            return PainCause.FLOW_UNCLEAR

        return PainCause.UNKNOWN

    def generate_hint_card(
        self,
        pain_point: UIPainPoint,
    ) -> Dict[str, Any]:
        """
        生成提示卡片

        Args:
            pain_point: 痛点记录

        Returns:
            Dict: 提示卡片内容
        """
        module = pain_point.module
        cause = self.infer_cause(pain_point)

        # 基于原因的提示模板
        hint_templates = {
            PainCause.INSUFFICIENT_HINT: {
                "title": "💡 使用提示",
                "content": f"这个模块的使用方法：...",
                "action": "查看详细帮助",
            },
            PainCause.OPTION_COMPLEX: {
                "title": "📋 选项说明",
                "content": f"这些选项的含义：...",
                "action": "查看推荐设置",
            },
            PainCause.DEFAULT_UNREASONABLE: {
                "title": "⚙️ 默认值建议",
                "content": f"推荐将 {module} 的值调整为：...",
                "action": "应用推荐值",
            },
            PainCause.FLOW_UNCLEAR: {
                "title": "🔄 操作流程",
                "content": f"建议的操作步骤：...",
                "action": "查看流程图",
            },
            PainCause.NETWORK_ISSUE: {
                "title": "🌐 网络诊断",
                "content": f"检测到网络可能有问题，建议：...",
                "action": "运行网络诊断",
            },
        }

        template = hint_templates.get(cause, {
            "title": "❓ 需要帮助",
            "content": f"关于 {module} 的问题",
            "action": "联系支持",
        })

        hint = {
            "module": module,
            "pain_id": pain_point.id,
            "title": template["title"],
            "content": template["content"],
            "action": template["action"],
            "created_at": int(time.time()),
        }

        self._injected_hints[pain_point.id] = hint
        self._save_hints()

        return hint

    def get_unresolved_pain_points(
        self,
        limit: int = 10,
    ) -> List[UIPainPoint]:
        """获取未解决的痛点（按次数排序）"""
        unresolved = [
            p for p in self._pain_points.values()
            if not p.resolved
        ]
        return sorted(unresolved, key=lambda p: p.count, reverse=True)[:limit]

    def resolve_pain_point(self, pain_id: str) -> bool:
        """标记痛点为已解决"""
        pain_point = self._pain_points.get(pain_id)
        if pain_point is None:
            return False

        pain_point.resolved = True
        self._save_pain_points()

        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        all_points = list(self._pain_points.values())
        unresolved = [p for p in all_points if not p.resolved]

        # 按类型统计
        by_type: Dict[str, int] = {}
        for p in all_points:
            key = p.pain_type.value
            by_type[key] = by_type.get(key, 0) + 1

        return {
            "total_pain_points": len(all_points),
            "unresolved": len(unresolved),
            "resolved": len(all_points) - len(unresolved),
            "by_type": by_type,
            "top_modules": self._get_top_modules(5),
        }

    def _get_top_modules(self, limit: int) -> List[Dict[str, Any]]:
        """获取热门模块"""
        module_counts: Dict[str, int] = {}
        for p in self._pain_points.values():
            module_counts[p.module] = module_counts.get(p.module, 0) + p.count

        sorted_modules = sorted(
            module_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]

        return [{"module": m, "count": c} for m, c in sorted_modules]


# 全局单例
_optimizer_instance: Optional[ExperienceOptimizer] = None


def get_experience_optimizer() -> ExperienceOptimizer:
    """获取体验优化器全局实例"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = ExperienceOptimizer()
    return _optimizer_instance


# ============ 终极版新增：行业感知蒸馏 ============

from .models import (
    DistillationRule, DistillationCategory,
    IndustryInsight,
)


class IndustryDistiller:
    """
    行业感知蒸馏器

    功能：
    1. 用户行为收集（搜索/筛选/反馈）
    2. 模式识别与规则提炼
    3. 知识注入到 AI Prompt
    """

    # 最小证据数量（达到才生成规则）
    MIN_EVIDENCE_COUNT = 5
    # 最小置信度
    MIN_CONFIDENCE = 0.7

    # 行业关键词映射
    CATEGORY_KEYWORDS = {
        DistillationCategory.SEARCH_FILTER: [
            "筛选", "过滤", "查找", "搜索", "排序", "order by", "filter"
        ],
        DistillationCategory.PRODUCT_PREFERENCE: [
            "品牌", "型号", "款式", "颜色", "size", "brand", "model", "color"
        ],
        DistillationCategory.PRICE_SENSITIVITY: [
            "价格", "便宜", "贵", "性价比", "预算", "price", "cheap", "budget"
        ],
        DistillationCategory.BRAND_LOYALTY: [
            "只买", "只要", "一直用", "品牌", "回购", "always", "only", "loyal"
        ],
        DistillationCategory.USER_HABIT: [
            "习惯", "经常", "偏好", "喜欢", "prefer", "usually", "often"
        ],
    }

    def __init__(self, data_dir: Path = None):
        """
        初始化蒸馏器

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 存储文件
        self._insights_file = self._data_dir / "industry_insights.json"
        self._rules_file = self._data_dir / "distillation_rules.json"

        # 内存缓存
        self._insights: Dict[str, IndustryInsight] = {}
        self._rules: Dict[str, DistillationRule] = {}

        # 加载数据
        self._load_insights()
        self._load_rules()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "distillation"

    def _load_insights(self):
        """加载行业洞察"""
        if self._insights_file.exists():
            try:
                with open(self._insights_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        insight = IndustryInsight.from_dict(item)
                        self._insights[insight.id] = insight
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_rules(self):
        """加载蒸馏规则"""
        if self._rules_file.exists():
            try:
                with open(self._rules_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        rule = DistillationRule.from_dict(item)
                        self._rules[rule.id] = rule
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_insights(self):
        """保存行业洞察"""
        data = [i.to_dict() for i in self._insights.values()]
        with open(self._insights_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_rules(self):
        """保存蒸馏规则"""
        data = [r.to_dict() for r in self._rules.values()]
        with open(self._rules_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_behavior(
        self,
        category: DistillationCategory,
        keywords: List[str],
        context: str = "",
        module: str = "",
    ):
        """
        记录用户行为

        Args:
            category: 行为类别
            keywords: 关键词列表
            context: 上下文描述
            module: 来源模块
        """
        insight_id = hashlib.sha256(
            f"{category.value}:{','.join(keywords)}:{int(time.time())}".encode()
        ).hexdigest()[:12]

        # 检查是否已存在相同的行为
        for existing in self._insights.values():
            if (existing.category == category and
                    set(existing.keywords) == set(keywords)):
                # 累加频率
                existing.frequency += 1
                self._save_insights()
                return existing

        insight = IndustryInsight(
            id=insight_id,
            category=category,
            keywords=keywords,
            frequency=1,
            context=context,
            timestamp=int(time.time()),
            module=module,
        )

        self._insights[insight_id] = insight
        self._save_insights()

        # 检查是否达到蒸馏条件
        if insight.frequency >= self.MIN_EVIDENCE_COUNT:
            self._try_distill_rule(insight)

        return insight

    def _try_distill_rule(self, insight: IndustryInsight):
        """尝试蒸馏规则"""
        # 检查证据数量
        similar = [
            i for i in self._insights.values()
            if i.category == insight.category and set(i.keywords) & set(insight.keywords)
        ]

        if len(similar) < self.MIN_EVIDENCE_COUNT:
            return

        # 计算置信度
        confidence = min(len(similar) / 10.0, 1.0)  # 最多10个证据

        if confidence < self.MIN_CONFIDENCE:
            return

        # 生成规则
        rule_id = hashlib.sha256(
            f"{insight.category.value}:{','.join(insight.keywords)}".encode()
        ).hexdigest()[:8]

        # 检查是否已存在
        if rule_id in self._rules:
            return

        rule_text = self._generate_rule_text(insight.category, insight.keywords, similar)
        example = self._generate_example(insight.category, insight.keywords)

        rule = DistillationRule(
            id=rule_id,
            category=insight.category,
            pattern=",".join(insight.keywords),
            rule=rule_text,
            evidence_count=len(similar),
            confidence=confidence,
            source_modules=list(set(i.module for i in similar)),
            created_at=int(time.time()),
            updated_at=int(time.time()),
            enabled=True,
            example=example,
        )

        self._rules[rule_id] = rule
        self._save_rules()

        return rule

    def _generate_rule_text(
        self,
        category: DistillationCategory,
        keywords: List[str],
        evidence: List[IndustryInsight],
    ) -> str:
        """生成规则文本"""
        keyword_str = "/".join(keywords[:3])  # 最多3个关键词

        templates = {
            DistillationCategory.SEARCH_FILTER: (
                f"当用户搜索包含「{keyword_str}」时，"
                f"自动推荐高级筛选选项，包括：品牌、价格区间、销量排序等。"
            ),
            DistillationCategory.PRODUCT_PREFERENCE: (
                f"用户偏好「{keyword_str}」相关产品，"
                f"在推荐列表中优先展示符合这些特征的选项。"
            ),
            DistillationCategory.PRICE_SENSITIVITY: (
                f"用户对「{keyword_str}」的价格敏感度较高，"
                f"优先推荐性价比高的产品，并展示价格趋势。"
            ),
            DistillationCategory.BRAND_LOYALTY: (
                f"用户对「{keyword_str}」品牌有较高忠诚度，"
                f"当该品牌有新货时主动提醒，并推荐相关品牌替代品。"
            ),
            DistillationCategory.USER_HABIT: (
                f"用户习惯于「{keyword_str}」的交互方式，"
                f"记住该偏好并在后续对话中优先使用类似模式。"
            ),
        }

        return templates.get(category, f"用户关注「{keyword_str}」相关主题。")

    def _generate_example(self, category: DistillationCategory, keywords: List[str]) -> str:
        """生成示例"""
        keyword_str = "/".join(keywords[:2])

        examples = {
            DistillationCategory.SEARCH_FILTER: f"用户搜索「{keyword_str}」时，自动展开筛选面板",
            DistillationCategory.PRODUCT_PREFERENCE: f"优先展示「{keyword_str}」相关热门产品",
            DistillationCategory.PRICE_SENSITIVITY: f"为用户标注「{keyword_str}」的价格走势和优惠",
            DistillationCategory.BRAND_LOYALTY: f"当「{keyword_str}」品牌上新时，置顶提醒用户",
            DistillationCategory.USER_HABIT: f"记住用户偏好「{keyword_str}」，下次直接推荐",
        }

        return examples.get(category, f"根据「{keyword_str}」提供个性化建议")

    def get_active_rules(self) -> List[DistillationRule]:
        """获取活跃规则"""
        return [r for r in self._rules.values() if r.enabled]

    def get_rules_by_category(self, category: DistillationCategory) -> List[DistillationRule]:
        """按类别获取规则"""
        return [r for r in self._rules.values() if r.category == category and r.enabled]

    def generate_prompt_augmentation(self) -> str:
        """
        生成 Prompt 增强文本

        用于注入到 AI 的 System Prompt 中

        Returns:
            str: 增强文本
        """
        rules = self.get_active_rules()
        if not rules:
            return ""

        augmentations = ["[用户偏好知识库]"]
        for rule in rules:
            augmentations.append(f"- {rule.rule}")

        return "\n".join(augmentations)

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        rule = self._rules.get(rule_id)
        if rule is None:
            return False

        rule.enabled = False
        rule.updated_at = int(time.time())
        self._save_rules()
        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        rules = list(self._rules.values())
        enabled = [r for r in rules if r.enabled]

        # 按类别统计
        by_category: Dict[str, int] = {}
        for r in rules:
            key = r.category.value
            by_category[key] = by_category.get(key, 0) + 1

        return {
            "total_insights": len(self._insights),
            "total_rules": len(rules),
            "enabled_rules": len(enabled),
            "by_category": by_category,
            "avg_confidence": sum(r.confidence for r in enabled) / max(len(enabled), 1),
        }


# 全局单例
_distiller_instance: Optional[IndustryDistiller] = None


def get_industry_distiller() -> IndustryDistiller:
    """获取行业蒸馏器全局实例"""
    global _distiller_instance
    if _distiller_instance is None:
        _distiller_instance = IndustryDistiller()
    return _distiller_instance
