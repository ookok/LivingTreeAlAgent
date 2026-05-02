"""
Hermes-Agent 用户画像与成长系统
基于 NousResearch/hermes-agent 思想：伴随式成长的个性化助手

核心思想：
- 记住用户的编码习惯、技术偏好、踩过的坑
- 越用越懂你，从执行者变成"数字合伙人"
- 构建用户画像，实现真正的个性化
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib


class PreferenceType(Enum):
    TONE = "tone"                    # 语气偏好
    RESPONSE_LENGTH = "response_length"  # 回复长度
    CODE_STYLE = "code_style"        # 代码风格
    WORKFLOW = "workflow"            # 工作流偏好
    TOPIC = "topic"                  # 话题偏好
    LANGUAGE = "language"            # 语言偏好
    EXPERTISE = "expertise"          # 专业领域
    HABIT = "habit"                 # 习惯


@dataclass
class UserPreference:
    """用户偏好"""
    type: PreferenceType
    value: Any
    confidence: float = 1.0
    source: str = "inferred"  # inferred / explicit / learned
    updated_at: float = field(default_factory=time.time)
    evidence: List[str] = field(default_factory=list)  # 支持证据


@dataclass
class InteractionRecord:
    """交互记录"""
    id: str
    timestamp: float
    query: str
    response: str
    feedback: str = ""  # thumbs_up / thumbs_down /改进建议
    context: Dict[str, Any] = field(default_factory=dict)
    agents_used: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    duration: float = 0.0
    rating: float = 0.0


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    name: str = ""
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    interaction_count: int = 0

    # 偏好
    preferences: Dict[str, UserPreference] = field(default_factory=dict)

    # 统计
    topic_stats: Dict[str, int] = field(default_factory=dict)  # 话题频率
    agent_stats: Dict[str, int] = field(default_factory=dict)   # Agent使用频率
    tool_stats: Dict[str, int] = field(default_factory=dict)     # 工具使用频率
    time_patterns: Dict[str, int] = field(default_factory=dict)  # 使用时段

    # 学习
    successful_patterns: List[str] = field(default_factory=list)  # 成功模式
    failed_patterns: List[str] = field(default_factory=list)     # 失败模式
    learned_facts: Dict[str, str] = field(default_factory=dict)  # 学到的事实

    # 经验
    remembered_tasks: List[Dict] = field(default_factory=list)   # 记住的任务
    project_contexts: Dict[str, Dict] = field(default_factory=dict)  # 项目上下文


class UserProfileManager:
    """用户画像管理器"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or "./data/user_profiles")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.profiles: Dict[str, UserProfile] = {}
        self.current_user_id: Optional[str] = None
        self._interaction_history: List[InteractionRecord] = []

        self._load_all_profiles()

    def _get_profile_file(self, user_id: str) -> Path:
        return self.storage_dir / f"{user_id}.json"

    def _load_all_profiles(self):
        """加载所有用户画像"""
        for f in self.storage_dir.glob("*.json"):
            if f.name == "index.json":
                continue
            try:
                data = json.loads(f.read_text())
                profile = UserProfile(
                    user_id=data["user_id"],
                    name=data.get("name", ""),
                    created_at=data.get("created_at", time.time()),
                    last_active=data.get("last_active", time.time()),
                    interaction_count=data.get("interaction_count", 0),
                    preferences={
                        k: UserPreference(
                            type=PreferenceType(v["type"]),
                            value=v["value"],
                            confidence=v.get("confidence", 1.0),
                            source=v.get("source", "inferred")
                        )
                        for k, v in data.get("preferences", {}).items()
                    },
                    topic_stats=data.get("topic_stats", {}),
                    agent_stats=data.get("agent_stats", {}),
                    tool_stats=data.get("tool_stats", {}),
                    successful_patterns=data.get("successful_patterns", []),
                    failed_patterns=data.get("failed_patterns", []),
                    learned_facts=data.get("learned_facts", {})
                )
                self.profiles[profile.user_id] = profile
            except Exception as e:
                print(f"[HermesAgent] Failed to load profile {f}: {e}")

    def _save_profile(self, user_id: str):
        """保存用户画像"""
        profile = self.profiles.get(user_id)
        if not profile:
            return

        data = {
            "user_id": profile.user_id,
            "name": profile.name,
            "created_at": profile.created_at,
            "last_active": profile.last_active,
            "interaction_count": profile.interaction_count,
            "preferences": {
                k: {
                    "type": v.type.value,
                    "value": v.value,
                    "confidence": v.confidence,
                    "source": v.source,
                    "evidence": v.evidence
                }
                for k, v in profile.preferences.items()
            },
            "topic_stats": profile.topic_stats,
            "agent_stats": profile.agent_stats,
            "tool_stats": profile.tool_stats,
            "successful_patterns": profile.successful_patterns,
            "failed_patterns": profile.failed_patterns,
            "learned_facts": profile.learned_facts
        }

        self._get_profile_file(user_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

    def get_or_create_profile(self, user_id: str, name: str = "") -> UserProfile:
        """获取或创建用户画像"""
        if user_id not in self.profiles:
            self.profiles[user_id] = UserProfile(
                user_id=user_id,
                name=name or user_id
            )
            self._save_profile(user_id)

        return self.profiles[user_id]

    def set_current_user(self, user_id: str):
        """设置当前用户"""
        self.current_user_id = user_id
        if user_id in self.profiles:
            self.profiles[user_id].last_active = time.time()
            self._save_profile(user_id)

    def get_current_profile(self) -> Optional[UserProfile]:
        """获取当前用户画像"""
        if self.current_user_id:
            return self.profiles.get(self.current_user_id)
        return None

    def record_interaction(
        self,
        user_id: str,
        query: str,
        response: str,
        context: Dict[str, Any] = None,
        agents: List[str] = None,
        tools: List[str] = None
    ) -> InteractionRecord:
        """记录一次交互"""
        if user_id not in self.profiles:
            self.get_or_create_profile(user_id)

        profile = self.profiles[user_id]

        record = InteractionRecord(
            id=f"ir_{int(time.time() * 1000)}",
            timestamp=time.time(),
            query=query,
            response=response,
            context=context or {},
            agents_used=agents or [],
            tools_used=tools or []
        )

        self._interaction_history.append(record)
        profile.interaction_count += 1
        profile.last_active = time.time()

        # 更新统计
        if context:
            topic = context.get("topic", "")
            if topic:
                profile.topic_stats[topic] = profile.topic_stats.get(topic, 0) + 1

        for agent in (agents or []):
            profile.agent_stats[agent] = profile.agent_stats.get(agent, 0) + 1

        for tool in (tools or []):
            profile.tool_stats[tool] = profile.tool_stats.get(tool, 0) + 1

        # 学习时段模式
        hour = int(time.localtime().tm_hour)
        profile.time_patterns[str(hour)] = profile.time_patterns.get(str(hour), 0) + 1

        # 推断偏好
        self._infer_preferences(profile, query, response)

        self._save_profile(user_id)
        return record

    def _infer_preferences(self, profile: UserProfile, query: str, response: str):
        """从交互中推断偏好"""
        query_lower = query.lower()

        # 推断语气偏好
        if any(w in query_lower for w in ["请", "麻烦", "谢谢", "请问"]):
            self._update_preference(
                profile,
                PreferenceType.TONE,
                "polite",
                confidence=0.6,
                source="inferred",
                evidence=["使用礼貌用语"]
            )

        # 推断回复长度偏好
        if any(w in query_lower for w in ["详细", "完整", "具体"]):
            self._update_preference(
                profile,
                PreferenceType.RESPONSE_LENGTH,
                "detailed",
                confidence=0.7,
                source="inferred",
                evidence=["要求详细回答"]
            )
        elif any(w in query_lower for w in ["简洁", "简短", "简单"]):
            self._update_preference(
                profile,
                PreferenceType.RESPONSE_LENGTH,
                "concise",
                confidence=0.7,
                source="inferred",
                evidence=["要求简短回答"]
            )

        # 推断专业领域
        topics = {
            "python": ["python", "py"],
            "javascript": ["js", "javascript", "node"],
            "电商": ["电商", "shop", "卖", "商品"],
            "数据": ["数据", "分析", "统计"]
        }

        for topic, keywords in topics.items():
            if any(k in query_lower for k in keywords):
                profile.topic_stats[topic] = profile.topic_stats.get(topic, 0) + 5

    def _update_preference(
        self,
        profile: UserProfile,
        pref_type: PreferenceType,
        value: Any,
        confidence: float = 0.5,
        source: str = "inferred",
        evidence: List[str] = None
    ):
        """更新偏好"""
        key = pref_type.value
        existing = profile.preferences.get(key)

        if existing:
            # 更新置信度
            if confidence > existing.confidence:
                existing.value = value
                existing.confidence = confidence
                existing.updated_at = time.time()
                existing.evidence.extend(evidence or [])
        else:
            profile.preferences[key] = UserPreference(
                type=pref_type,
                value=value,
                confidence=confidence,
                source=source,
                evidence=evidence or []
            )

    def record_feedback(
        self,
        interaction_id: str,
        feedback: str,
        rating: float = 0.0
    ):
        """记录反馈"""
        for record in reversed(self._interaction_history):
            if record.id == interaction_id:
                record.feedback = feedback
                record.rating = rating

                # 如果是负面反馈，记录失败模式
                if rating < 0.5 and self.current_user_id:
                    profile = self.profiles.get(self.current_user_id)
                    if profile:
                        pattern = f"query:{record.query[:50]}..."
                        if pattern not in profile.failed_patterns:
                            profile.failed_patterns.append(pattern)

                self._save_profile(self.current_user_id)
                break

    def learn_fact(self, user_id: str, key: str, value: str):
        """学习一个事实"""
        if user_id not in self.profiles:
            return

        profile = self.profiles[user_id]
        profile.learned_facts[key] = value
        self._save_profile(user_id)

        print(f"[HermesAgent] Learned fact: {key} = {value}")

    def get_context_for_llm(self, user_id: str, max_history: int = 10) -> str:
        """为 LLM 生成用户上下文"""
        profile = self.profiles.get(user_id)
        if not profile:
            return ""

        lines = []
        lines.append(f"## 用户画像: {profile.name}")

        # 基本信息
        lines.append(f"- 交互次数: {profile.interaction_count}")
        lines.append(f"- 最后活跃: {time.strftime('%Y-%m-%d %H:%M', time.localtime(profile.last_active))}")

        # 偏好
        if profile.preferences:
            lines.append("\n### 已知偏好:")
            for pref in profile.preferences.values():
                lines.append(f"- {pref.type.value}: {pref.value} (置信度: {pref.confidence:.0%})")

        # 学到的事实
        if profile.learned_facts:
            lines.append("\n### 已记住的信息:")
            for k, v in profile.learned_facts.items():
                lines.append(f"- {k}: {v}")

        # 最近话题
        if profile.topic_stats:
            top_topics = sorted(profile.topic_stats.items(), key=lambda x: -x[1])[:3]
            lines.append(f"\n### 常用话题: {', '.join(t[0] for t in top_topics)}")

        # 最近交互历史
        recent = self._interaction_history[-max_history:]
        if recent:
            lines.append("\n### 最近交互:")
            for r in recent:
                lines.append(f"- [{time.strftime('%H:%M', time.localtime(r.timestamp))}] {r.query[:40]}...")

        return "\n".join(lines)

    def remember_task(
        self,
        user_id: str,
        task_type: str,
        task_data: Dict[str, Any],
        result: Any = None
    ):
        """记住一个任务"""
        if user_id not in self.profiles:
            return

        profile = self.profiles[user_id]
        profile.remembered_tasks.append({
            "type": task_type,
            "data": task_data,
            "result": result,
            "timestamp": time.time()
        })

        # 只保留最近 100 个
        if len(profile.remembered_tasks) > 100:
            profile.remembered_tasks = profile.remembered_tasks[-100:]

        self._save_profile(user_id)

    def get_similar_task(
        self,
        user_id: str,
        task_type: str,
        similarity_fn: Callable[[Dict, Dict], float] = None
    ) -> Optional[Dict]:
        """查找相似任务"""
        profile = self.profiles.get(user_id)
        if not profile:
            return None

        # 简单实现：按类型匹配
        similar = [
            t for t in profile.remembered_tasks
            if t.get("type") == task_type
        ]

        return similar[-1] if similar else None


# ==================== 单例 ====================

_profile_manager: Optional[UserProfileManager] = None


def get_profile_manager() -> UserProfileManager:
    """获取用户画像管理器单例"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = UserProfileManager()
    return _profile_manager


def get_current_user_context(max_history: int = 10) -> str:
    """获取当前用户的上下文（供 LLM 使用）"""
    manager = get_profile_manager()
    if manager.current_user_id:
        return manager.get_context_for_llm(manager.current_user_id, max_history)
    return ""


# ==================== 意图识别与澄清 ====================
# 从架构指南 Phase A 新增 (2026-04-28)

from business.hermes_agent.intent_recognizer import Intent, IntentRecognizer
from business.hermes_agent.intent_clarifier import AdaptiveClarifier, ClarificationResult, ClarificationStrategy
from business.hermes_agent.progressive_ui_renderer import ProgressiveUIRenderer, UIRenderState, RenderPriority

# 咨询意图常量
CONSULTING_INTENTS = {
    "eia_report": "环境影响评价报告生成",
    "feasibility_study": "可行性研究报告生成",
    "financial_analysis": "财务分析报告生成",
    "code_generation": "Python代码生成",
    "document_generation": "文档生成",
}

# ==================== 自适应学习循环 ====================
# 从架构指南 Phase C 新增 (2026-04-28)

from business.hermes_agent.adaptive_learning_loop import (
    AdaptiveLearningLoop,
    LearningSample,
    Policy,
    LearningMode,
)

# ==================== 多Agent编排 ====================
# 从架构指南 Phase C 新增 (2026-04-28)

from business.hermes_agent.multi_agent_orchestrator import (
    MultiAgentOrchestrator,
    Agent,
    SubTask,
    AgentRole,
)

# ==================== 进化系统集成 ====================
# 从架构指南 Phase D 新增 (2026-05-02)

from business.hermes_agent.evolution_integration import (
    EvolutionIntegration,
    get_evolution_integration,
    record_task,
    record_user_feedback,
    recommend_tools,
)

# 自我驱动系统
from business.self_driving import SelfDrivingSystem, SystemState, get_self_driving_system
from business.curiosity_engine import CuriosityEngine, get_curiosity_engine
from business.auditor_agent import AuditorAgent, get_auditor_agent
from business.analogy_transfer import AnalogyTransferEngine, get_analogy_engine
from business.self_identity import SelfIdentity, get_self_identity
from business.tool_discovery import ToolDiscoveryEngine, get_tool_discovery_engine

# ==================== 数字咨询工程师 ====================
# 从架构指南 Phase E 新增 (2026-05-02)

from business.aria import (
    ARIAController,
    GenerationTask,
    GenerationStatus,
    MarkdownDSLParser,
    WordRenderer,
    get_aria_controller,
    StyleLearner,
    StyleDefinition,
    TableStyleDefinition,
)
from business.map_agent import (
    MapAgentController,
    MapInteractionMode,
    PerceptionTool,
    GeometryTool,
    OverlayAnalysisTool,
    MobilityTool,
    ExportTool,
    get_map_agent_controller,
)
from business.consulting_engineer import (
    ConsultingEngineer,
    ProjectContext,
    TaskResult,
    get_consulting_engineer,
    create_eia_project,
    create_feasibility_project,
)


__all__ = [
    # 原有导出
    "PreferenceType",
    "UserPreference",
    "InteractionRecord",
    "UserProfile",
    "UserProfileManager",
    "get_profile_manager",
    "get_current_user_context",
    # 新增导出 (Phase A)
    "Intent",
    "IntentRecognizer",
    "AdaptiveClarifier",
    "ClarificationResult",
    "ClarificationStrategy",
    "ProgressiveUIRenderer",
    "UIRenderState",
    "RenderPriority",
    "CONSULTING_INTENTS",
    # 新增导出 (Phase C)
    "AdaptiveLearningLoop",
    "LearningSample",
    "Policy",
    "LearningMode",
    "MultiAgentOrchestrator",
    "Agent",
    "SubTask",
    "AgentRole",
    # 新增导出 (Phase D - 进化系统)
    "EvolutionIntegration",
    "get_evolution_integration",
    "record_task",
    "record_user_feedback",
    "recommend_tools",
    # 新增导出 (Phase E - 数字咨询工程师)
    "ConsultingEngineer",
    "ProjectContext",
    "TaskResult",
    "get_consulting_engineer",
    "create_eia_project",
    "create_feasibility_project",
    # 新增导出 (Phase F - 自我驱动系统)
    "SelfDrivingSystem",
    "SystemState",
    "get_self_driving_system",
    "CuriosityEngine",
    "get_curiosity_engine",
    "AuditorAgent",
    "get_auditor_agent",
    "AnalogyTransferEngine",
    "get_analogy_engine",
    "SelfIdentity",
    "get_self_identity",
    "ToolDiscoveryEngine",
    "get_tool_discovery_engine",
    # 新增导出 (Phase G - A.R.I.A系统)
    "ARIAController",
    "GenerationTask",
    "GenerationStatus",
    "MarkdownDSLParser",
    "WordRenderer",
    "get_aria_controller",
    "StyleLearner",
    "StyleDefinition",
    "TableStyleDefinition",
    # 新增导出 (Phase H - Map Agent系统)
    "MapAgentController",
    "MapInteractionMode",
    "PerceptionTool",
    "GeometryTool",
    "OverlayAnalysisTool",
    "MobilityTool",
    "ExportTool",
    "get_map_agent_controller",
    "MAP_CONFIG",
    "update_config",
    "validate_config",
    "print_config_summary",
]
