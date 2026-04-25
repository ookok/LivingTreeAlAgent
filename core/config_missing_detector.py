"""
配置缺失检测器 - ConfigMissingDetector

检测 hermes-agent 执行时因配置缺失导致的错误，
并提供可点击跳转的智能提示。

支持的检测场景：
1. API Key 缺失 (OPENAI_API_KEY, ANTHROPIC_API_KEY 等)
2. 配置文件缺失 (.env, config.yaml)
3. 模型配置缺失 (model.provider, model.base_url 等)
4. Skill 配置缺失 (skills.config.*)
5. 工具依赖缺失 (browser, mcp 等)

架构升级（v2）：
- 保留硬编码正则作为快速路径（Fast Path，< 1ms）
- 引入 AIReasoningEngine 作为智能路径（Smart Path，500ms）
- 级联：快速匹配失败 → AI 推理 → 未知错误降级

使用示例：
    detector = ConfigMissingDetector()
    result = detector.check_error(error_message)
    if result.is_missing_config:
        logger.info(result.config_key)  # e.g., "OPENAI_API_KEY"
        logger.info(result.hint)         # "请配置 OpenAI API Key"
        logger.info(result.link_text)     # "[配置 API Key]"
"""

from core.logger import get_logger
logger = get_logger('config_missing_detector')

import re
import os
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# 尝试导入 AI 推理引擎（可选依赖）
# ============================================================

try:
    from core.ai_reasoning_engine import AIReasoningEngine, ReasoningResult as AIRationalResult
    _HAS_AI_REASONING = True
except ImportError:
    _HAS_AI_REASONING = False
    logger.debug("AIReasoningEngine not available, using regex-only mode")


# ============================================================
# 配置缺失模式定义
# ============================================================

@dataclass
class ConfigPattern:
    """单个配置缺失的检测模式"""
    key: str                    # 配置项名称
    category: str               # 分类: api_key, model, skill, tool, file
    pattern: re.Pattern         # 匹配正则
    hint: str                   # 提示文本
    link_path: str              # 跳转路径 (用于 SettingsDialog 定位 Tab)
    url: Optional[str] = None   # 官方文档链接 (如果有)


# 常见的 API Key 环境变量模式
API_KEY_PATTERNS = [
    ConfigPattern(
        key="OPENAI_API_KEY",
        category="api_key",
        pattern=re.compile(r"OPENAI_API_KEY|openai.*key.*missing|openai.*not.*configured", re.I),
        hint="请配置 OpenAI API Key",
        link_path="providers",
        url="https://platform.openai.com/api-keys"
    ),
    ConfigPattern(
        key="ANTHROPIC_API_KEY",
        category="api_key",
        pattern=re.compile(r"ANTHROPIC_API_KEY|anthropic.*key.*missing|claude.*not.*configured", re.I),
        hint="请配置 Anthropic API Key",
        link_path="providers",
        url="https://console.anthropic.com/settings/keys"
    ),
    ConfigPattern(
        key="DEEPSEEK_API_KEY",
        category="api_key",
        pattern=re.compile(r"DEEPSEEK_API_KEY|deepseek.*key.*missing", re.I),
        hint="请配置 DeepSeek API Key",
        link_path="providers",
        url="https://platform.deepseek.com/api_keys"
    ),
    ConfigPattern(
        key="ZAI_API_KEY",
        category="api_key",
        pattern=re.compile(r"ZAI_API_KEY|z.ai.*key.*missing|glm.*not.*configured", re.I),
        hint="请配置 Z.AI / GLM API Key",
        link_path="providers"
    ),
    ConfigPattern(
        key="KIMI_API_KEY",
        category="api_key",
        pattern=re.compile(r"KIMI_API_KEY|kimi.*key.*missing|moonshot.*not.*configured", re.I),
        hint="请配置 Kimi API Key",
        link_path="providers",
        url="https://platform.moonshot.cn/console/api-keys"
    ),
    ConfigPattern(
        key="DASHSCOPE_API_KEY",
        category="api_key",
        pattern=re.compile(r"DASHSCOPE_API_KEY|dashscope.*key.*missing|aliyun.*not.*configured", re.I),
        hint="请配置 DashScope API Key",
        link_path="providers",
        url="https://dashscope.console.aliyun.com/apiKey"
    ),
    ConfigPattern(
        key="HF_TOKEN",
        category="api_key",
        pattern=re.compile(r"HF_TOKEN|huggingface.*token.*missing", re.I),
        hint="请配置 HuggingFace Token",
        link_path="providers",
        url="https://huggingface.co/settings/tokens"
    ),
]

# 模型配置缺失模式
MODEL_PATTERNS = [
    ConfigPattern(
        key="model.provider",
        category="model",
        pattern=re.compile(r"model.*not.*set|no.*model.*configured|missing.*model.*config", re.I),
        hint="请选择默认模型",
        link_path="models"
    ),
    ConfigPattern(
        key="model.base_url",
        category="model",
        pattern=re.compile(r"base.*url.*missing|endpoint.*not.*set|api.*endpoint.*missing", re.I),
        hint="请配置模型 API Endpoint",
        link_path="models"
    ),
    ConfigPattern(
        key="model.default",
        category="model",
        pattern=re.compile(r"default.*model.*missing|no.*default.*model", re.I),
        hint="请设置默认模型",
        link_path="models"
    ),
]

# Skill 配置缺失模式
SKILL_PATTERNS = [
    ConfigPattern(
        key="skills.config",
        category="skill",
        pattern=re.compile(r"skill.*config.*missing|missing.*skill.*setting|skills\.config", re.I),
        hint="请配置 Skill 设置",
        link_path="skills"
    ),
]

# 工具依赖缺失模式
TOOL_PATTERNS = [
    ConfigPattern(
        key="browser",
        category="tool",
        pattern=re.compile(r"browser.*not.*installed|chrome.*not.*found|playwright.*missing|browser.*dependency", re.I),
        hint="请安装浏览器工具",
        link_path="agent",
        url="https://docs.hermes-agent.dev/docs/user-guide/browser"
    ),
    ConfigPattern(
        key="mcp",
        category="tool",
        pattern=re.compile(r"mcp.*server.*not.*found|mcp.*config.*missing|MCP.*not.*configured", re.I),
        hint="请配置 MCP Server",
        link_path="mcp"
    ),
]

# 配置文件缺失模式
FILE_PATTERNS = [
    ConfigPattern(
        key=".env",
        category="file",
        pattern=re.compile(r"\.env.*not.*found|no.*\.env.*file|missing.*\.env", re.I),
        hint="请创建 .env 配置文件",
        link_path="general"
    ),
    ConfigPattern(
        key="config.yaml",
        category="file",
        pattern=re.compile(r"config\.yaml.*not.*found|no.*config.*file|missing.*config", re.I),
        hint="请创建 config.yaml 配置文件",
        link_path="general"
    ),
    ConfigPattern(
        key="SOUL.md",
        category="file",
        pattern=re.compile(r"SOUL\.md.*not.*found|no.*personality.*file", re.I),
        hint="请创建 SOUL.md 个性化文件",
        link_path="general"
    ),
]

# 所有检测模式汇总
ALL_PATTERNS = (
    API_KEY_PATTERNS
    + MODEL_PATTERNS
    + SKILL_PATTERNS
    + TOOL_PATTERNS
    + FILE_PATTERNS
)


# ============================================================
# 检测结果
# ============================================================

@dataclass
class MissingConfigResult:
    """配置缺失检测结果"""
    is_missing_config: bool = False      # 是否是配置缺失错误
    config_key: Optional[str] = None    # 缺失的配置项名称
    category: Optional[str] = None      # 分类
    hint: Optional[str] = None          # 用户提示
    link_path: Optional[str] = None       # 设置面板跳转路径
    url: Optional[str] = None             # 官方文档链接
    suggestions: List[str] = field(default_factory=list)  # 建议操作列表
    # v2 新增：支持 AI 推理
    confidence: float = 0.0              # 置信度 0.0-1.0
    reasoning_steps: List[str] = field(default_factory=list)  # 推理过程
    reasoning_mode: str = "regex"        # 推理模式: regex / ai_reasoning


# ============================================================
# 配置缺失检测器
# ============================================================

class ConfigMissingDetector:
    """
    配置缺失检测器

    检测 hermes-agent 执行时因配置缺失导致的错误，
    并提供智能提示和修复建议。
    """

    # 常见的配置缺失错误信息前缀/关键词
    GENERIC_MISSING_PATTERNS = [
        re.compile(r"missing.*config|config.*missing|configuration.*missing", re.I),
        re.compile(r"not.*configured|unconfigured|no.*config", re.I),
        re.compile(r"environment.*variable.*not.*set|env.*not.*set", re.I),
        re.compile(r"api.*key.*required|key.*required|auth.*required", re.I),
    ]

    def __init__(self):
        self._pattern_map: Dict[str, ConfigPattern] = {}
        for p in ALL_PATTERNS:
            self._pattern_map[p.key] = p

    def check_error(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissingConfigResult:
        """
        检测错误信息是否包含配置缺失

        Args:
            error_message: 完整的错误信息
            context: 额外上下文（如 last_action, provider 等）

        Returns:
            MissingConfigResult: 检测结果
        """
        if not error_message:
            return MissingConfigResult()

        # 1. 精确模式匹配（快速路径，< 1ms）
        for pattern_def in ALL_PATTERNS:
            if pattern_def.pattern.search(error_message):
                return MissingConfigResult(
                    is_missing_config=True,
                    config_key=pattern_def.key,
                    category=pattern_def.category,
                    hint=pattern_def.hint,
                    link_path=pattern_def.link_path,
                    url=pattern_def.url,
                    suggestions=self._get_suggestions(pattern_def),
                    confidence=0.95,
                    reasoning_steps=[
                        f"[Regex] 匹配模式: {pattern_def.pattern.pattern}",
                        f"[Regex] 配置键: {pattern_def.key}",
                        f"[Regex] 建议: {pattern_def.hint}",
                    ],
                    reasoning_mode="regex",
                )

        # 2. 通用缺失模式匹配（快速路径）
        for generic_pattern in self.GENERIC_MISSING_PATTERNS:
            if generic_pattern.search(error_message):
                # 尝试提取具体缺失的配置项名称
                config_key = self._extract_config_key(error_message)
                if config_key:
                    pattern_def = self._pattern_map.get(config_key)
                    if pattern_def:
                        return MissingConfigResult(
                            is_missing_config=True,
                            config_key=config_key,
                            category=pattern_def.category,
                            hint=pattern_def.hint,
                            link_path=pattern_def.link_path,
                            url=pattern_def.url,
                            suggestions=self._get_suggestions(pattern_def),
                            confidence=0.85,
                            reasoning_steps=[
                                "[Regex] 匹配通用缺失模式",
                                f"[Regex] 提取配置键: {config_key}",
                                f"[Regex] 建议: {pattern_def.hint}",
                            ],
                            reasoning_mode="regex",
                        )
                    else:
                        # 未知配置项，提供通用提示
                        return MissingConfigResult(
                            is_missing_config=True,
                            config_key=config_key,
                            category="unknown",
                            hint=f"请检查配置项: {config_key}",
                            link_path="general",
                            suggestions=[f"配置 {config_key}", "运行 hermes doctor 检查配置"],
                            confidence=0.6,
                            reasoning_steps=[
                                "[Regex] 匹配通用缺失模式",
                                f"[Regex] 提取配置键: {config_key}",
                                "[Regex] 未知配置键，提供通用建议",
                            ],
                            reasoning_mode="regex",
                        )

        # 3. AI 推理（智能路径，用于未知错误）
        if _HAS_AI_REASONING:
            return self._ai_check_error(error_message, context)

        return MissingConfigResult()

    def _ai_check_error(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissingConfigResult:
        """
        使用 AI 推理引擎检测配置缺失（智能路径）

        仅在正则匹配失败时调用。
        """
        try:
            engine = self._get_reasoning_engine()
            ai_result = engine.reason_about_error(error_message, context)

            if ai_result.is_config_issue:
                return MissingConfigResult(
                    is_missing_config=True,
                    config_key=ai_result.inferred_config_key,
                    category=ai_result.config_category or "unknown",
                    hint=ai_result.action_suggestion or f"请检查配置: {ai_result.inferred_config_key}",
                    link_path=ai_result.link_path or "general",
                    suggestions=[ai_result.action_suggestion or "配置检查"],
                    confidence=ai_result.confidence,
                    reasoning_steps=ai_result.reasoning_steps,
                    reasoning_mode=ai_result.reasoning_mode,
                )
            else:
                return MissingConfigResult(
                    confidence=ai_result.confidence,
                    reasoning_steps=ai_result.reasoning_steps,
                    reasoning_mode=ai_result.reasoning_mode,
                )

        except Exception as e:
            logger.warning(f"[Detector] AI reasoning failed: {e}")
            return MissingConfigResult()

    _reasoning_engine: Optional[Any] = None

    def _get_reasoning_engine(self):
        """获取推理引擎实例（懒加载）"""
        if not _HAS_AI_REASONING:
            return None

        if self._reasoning_engine is None:
            from core.ai_reasoning_engine import AIReasoningEngine
            # 尝试获取 SystemBrain
            try:
                from core.system_brain import get_system_brain

                brain = get_system_brain()
                self._reasoning_engine = AIReasoningEngine(system_brain=brain)
                logger.info("[Detector] AI Reasoning Engine initialized with SystemBrain")
            except Exception as e:
                logger.debug(f"[Detector] SystemBrain not available: {e}")
                self._reasoning_engine = AIReasoningEngine()
                logger.info("[Detector] AI Reasoning Engine initialized (fast mode only)")

        return self._reasoning_engine

    def _extract_config_key(self, error_message: str) -> Optional[str]:
        """从错误信息中提取配置项名称"""
        # 匹配常见格式: "missing OPENAI_API_KEY", "OPENAI_API_KEY not set"
        patterns = [
            re.compile(r"missing\s+([A-Z_][A-Z0-9_]*)", re.I),
            re.compile(r"([A-Z_][A-Z0-9_]*)\s+not\s+set", re.I),
            re.compile(r"no\s+([a-z_][a-z0-9_]*)\s+configured", re.I),
            re.compile(r"([a-z_][a-z0-9_]*\.?[a-z0-9_]*)\s+missing", re.I),
        ]

        for pattern in patterns:
            match = pattern.search(error_message)
            if match:
                return match.group(1)

        return None

    def _get_suggestions(self, pattern_def: ConfigPattern) -> List[str]:
        """获取修复建议"""
        suggestions = []

        # 基础建议
        suggestions.append(f"配置 {pattern_def.key}")

        # 根据分类添加特定建议
        if pattern_def.category == "api_key":
            suggestions.append("运行 hermes doctor 检查 API Key")
            suggestions.append("运行 hermes setup 配置向导")
            if pattern_def.url:
                suggestions.append(f"获取 Key: {pattern_def.url}")
        elif pattern_def.category == "model":
            suggestions.append("运行 hermes model list 查看可用模型")
            suggestions.append("在设置中选择默认模型")
        elif pattern_def.category == "tool":
            suggestions.append("运行 hermes doctor --fix 自动修复")
            if pattern_def.url:
                suggestions.append(f"查看文档: {pattern_def.url}")
        elif pattern_def.category == "file":
            suggestions.append("运行 hermes setup 创建配置文件")

        return suggestions

    def check_all_missing(self) -> List[MissingConfigResult]:
        """
        检查所有可能的配置缺失项

        Returns:
            List[MissingConfigResult]: 所有缺失的配置项列表
        """
        results = []
        hermes_home = self._get_hermes_home()
        env_path = hermes_home / ".env"

        # 检查 .env 文件
        if not env_path.exists():
            results.append(MissingConfigResult(
                is_missing_config=True,
                config_key=".env",
                category="file",
                hint="请创建 .env 配置文件",
                link_path="general",
                suggestions=["运行 hermes setup 创建配置", "复制 .env.example 到 .env"]
            ))
        else:
            # 检查必需的 API Key
            content = env_path.read_text(encoding="utf-8", errors="ignore")
            required_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
            for key in required_keys:
                if key not in os.environ and key not in content:
                    pattern_def = self._pattern_map.get(key)
                    if pattern_def:
                        results.append(MissingConfigResult(
                            is_missing_config=True,
                            config_key=key,
                            category="api_key",
                            hint=pattern_def.hint,
                            link_path=pattern_def.link_path,
                            url=pattern_def.url,
                            suggestions=self._get_suggestions(pattern_def)
                        ))

        return results

    def _get_hermes_home(self) -> Path:
        """获取 Hermes Home 目录"""
        home = os.environ.get("HERMES_HOME")
        if home:
            return Path(home)
        return Path.home() / ".hermes"


# ============================================================
# 快捷函数
# ============================================================

_detector_instance: Optional[ConfigMissingDetector] = None


def get_config_detector() -> ConfigMissingDetector:
    """获取检测器单例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ConfigMissingDetector()
    return _detector_instance


def check_config_missing(error_message: str) -> MissingConfigResult:
    """快捷函数：检测配置缺失"""
    return get_config_detector().check_error(error_message)
