"""
AI 推理引擎
AI Reasoning Engine

用 Hermes SystemBrain 替代硬编码检查，
实现自适应的配置诊断和修复建议。

设计原则：
1. 级联架构：快速正则（已知错误）→ AI 推理（未知错误）
2. 零外部依赖：仅依赖 SystemBrain（Ollama 本地模型）
3. 可插拔：作为独立模块，随时替换底层模型
4. 可解释：每个推理结果附带置信度和推理过程

使用示例：
    engine = AIReasoningEngine()
    result = engine.reason_about_error(
        error_message="Failed to connect: Z.ai API returned 401",
        context={"last_action": "chat_completion", "provider": "z.ai"}
    )
    if result.is_config_issue:
        logger.info(result.inferred_config_key)   # "ZAI_API_KEY"
        logger.info(result.action_suggestion)      # "配置 Z.AI API Key"
"""

import re
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from core.logger import get_logger
logger = get_logger('ai_reasoning_engine')


logger = logging.getLogger(__name__)


# ── 推理结果 ─────────────────────────────────────────────────────────

@dataclass
class ReasoningResult:
    """
    AI 推理结果

    所有字段都附带了推理依据（reasoning），
    方便事后回溯和调试。
    """

    # 是否是配置问题
    is_config_issue: bool = False

    # 推理出的配置键（如果有）
    inferred_config_key: Optional[str] = None

    # 配置分类：api_key / model / network / tool / file / unknown
    config_category: Optional[str] = None

    # 推断的缺失原因
    inferred_cause: Optional[str] = None

    # 建议的操作
    action_suggestion: Optional[str] = None

    # 设置面板跳转路径
    link_path: Optional[str] = None

    # 置信度：0.0 ~ 1.0
    confidence: float = 0.0

    # 推理过程（可供用户查看）
    reasoning_steps: List[str] = field(default_factory=list)

    # 原始错误信息
    original_error: str = ""

    # 推理耗时（毫秒）
    reasoning_time_ms: float = 0.0

    # 使用的推理模式：fast_pattern / ai_reasoning
    reasoning_mode: str = "none"

    def add_step(self, step: str):
        """添加推理步骤"""
        self.reasoning_steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_config_issue": self.is_config_issue,
            "inferred_config_key": self.inferred_config_key,
            "config_category": self.config_category,
            "inferred_cause": self.inferred_cause,
            "action_suggestion": self.action_suggestion,
            "link_path": self.link_path,
            "confidence": self.confidence,
            "reasoning_steps": self.reasoning_steps,
            "original_error": self.original_error[:100],
            "reasoning_time_ms": self.reasoning_time_ms,
            "reasoning_mode": self.reasoning_mode,
        }


# ── 快速模式匹配（已知的常见错误）─────────────────────────────

# 已知错误 → 配置键的快速映射
KNOWN_ERROR_PATTERNS = {
    # API Key 缺失
    r"OPENAI_API_KEY": ("OPENAI_API_KEY", "api_key", "providers", 0.95),
    r"ANTHROPIC_API_KEY|claude.*not.*configured": ("ANTHROPIC_API_KEY", "api_key", "providers", 0.95),
    r"DEEPSEEK_API_KEY": ("DEEPSEEK_API_KEY", "api_key", "providers", 0.95),
    r"ZAI_API_KEY|z\.ai.*key|glm.*not.*configured": ("ZAI_API_KEY", "api_key", "providers", 0.9),
    r"KIMI_API_KEY|moonshot.*not.*configured": ("KIMI_API_KEY", "api_key", "providers", 0.9),
    r"DASHSCOPE_API_KEY|aliyun.*not.*configured": ("DASHSCOPE_API_KEY", "api_key", "providers", 0.9),
    r"HF_TOKEN|huggingface.*token": ("HF_TOKEN", "api_key", "providers", 0.9),

    # 模型配置缺失
    r"model.*not.*set|no.*model.*configured|missing.*model.*config": ("model.default", "model", "models", 0.85),
    r"model\.provider|provider.*not.*configured": ("model.provider", "model", "models", 0.85),
    r"base.*url.*missing|endpoint.*not.*set": ("model.base_url", "model", "models", 0.8),

    # 连接错误
    r"connection.*refused|ECONNREFUSED": ("network.connection", "network", "ollama", 0.8),
    r"connection.*timeout|ETIMEDOUT": ("network.timeout", "network", "ollama", 0.8),
    r"ssl.*error|SSL.*verification.*failed": ("network.ssl", "network", "ollama", 0.8),

    # 文件缺失
    r"\.env.*not.*found|no.*\.env": (".env", "file", "general", 0.9),
    r"config\.yaml.*not.*found": ("config.yaml", "file", "general", 0.9),
    r"SOUL\.md.*not.*found": ("SOUL.md", "file", "general", 0.9),

    # 工具缺失
    r"browser.*not.*installed|chrome.*not.*found": ("browser", "tool", "agent", 0.85),
    r"mcp.*server.*not.*found|mcp.*not.*configured": ("mcp", "tool", "providers", 0.85),
}


def _fast_match(error_message: str) -> Optional[ReasoningResult]:
    """
    快速模式匹配（同步，无 AI 调用）

    适用于已知的常见错误模式，响应时间 < 1ms。
    """
    error_lower = error_message.lower()

    for pattern, (config_key, category, link_path, confidence) in KNOWN_ERROR_PATTERNS.items():
        if re.search(pattern, error_lower, re.IGNORECASE):
            return ReasoningResult(
                is_config_issue=True,
                inferred_config_key=config_key,
                config_category=category,
                inferred_cause=f"检测到 {config_key} 相关错误",
                action_suggestion=f"请配置 {config_key}",
                link_path=link_path,
                confidence=confidence,
                reasoning_steps=[
                    f"[Fast Pattern] 匹配到已知模式: {pattern}",
                    f"[Fast Pattern] 推断配置键: {config_key}",
                    f"[Fast Pattern] 建议操作: 配置 {config_key}",
                ],
                original_error=error_message,
                reasoning_mode="fast_pattern",
            )

    return None


# ── AI 推理引擎 ─────────────────────────────────────────────────────

class AIReasoningEngine:
    """
    AI 推理引擎

    使用 SystemBrain（Ollama 本地模型）进行深度推理，
    弥补硬编码正则无法覆盖的未知错误。

    工作流程：
    1. 接收错误信息和上下文
    2. 生成推理提示（包含上下文、配置知识库）
    3. 调用 SystemBrain 进行推理
    4. 解析推理结果，返回结构化建议
    """

    # 配置知识库（帮助 AI 理解配置结构）
    CONFIG_KNOWLEDGE = """
## 可用配置键（参考）
- OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY
- ZAI_API_KEY, KIMI_API_KEY, DASHSCOPE_API_KEY, HF_TOKEN
- model.provider (模型提供商: openai/anthropic/deepseek/zai/kimi 等)
- model.base_url (API 端点)
- model.default (默认模型名称)
- browser (浏览器工具)
- mcp (MCP Server 配置)
- .env, config.yaml, SOUL.md (配置文件)

## 配置分类
- api_key: API 密钥缺失
- model: 模型配置缺失
- network: 网络连接问题
- tool: 工具依赖缺失
- file: 配置文件缺失
- permission: 权限问题
- unknown: 无法确定

## 设置面板路径
- providers: AI 提供商设置（API Key 配置）
- models: 模型设置（选择默认模型）
- agent: Agent 设置（工具配置）
- ollama: Ollama 本地服务设置
- general: 通用设置
"""

    REASONING_PROMPT_TEMPLATE = """你是一个配置诊断专家。请分析以下错误信息，推断出：
1. 这是不是配置问题？
2. 如果是，具体缺失的是哪个配置项？
3. 应该跳转到哪个设置页面？
4. 给用户什么操作建议？

## 错误信息
{error_message}

## 上下文
{context}

{config_knowledge}

请以 JSON 格式输出推理结果：
{{
  "is_config_issue": true/false,
  "inferred_config_key": "配置键名称或 null",
  "config_category": "api_key/model/network/tool/file/permission/unknown",
  "inferred_cause": "推断的原因描述",
  "action_suggestion": "给用户的操作建议（简短）",
  "link_path": "settings/settings_dialog 跳转路径（如 providers/models/agent）",
  "confidence": 0.0-1.0
}}

只输出 JSON，不要有其他内容。"""

    def __init__(self, system_brain=None, timeout: float = 5.0):
        """
        初始化推理引擎

        Args:
            system_brain: SystemBrain 实例（可选，为 None 时仅用快速匹配）
            timeout: AI 推理超时时间（秒）
        """
        self._brain = system_brain
        self._timeout = timeout
        self._enabled = system_brain is not None

    def set_system_brain(self, brain):
        """设置 SystemBrain 实例"""
        self._brain = brain
        self._enabled = brain is not None

    def reason_about_error(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReasoningResult:
        """
        推理错误信息

        Args:
            error_message: 错误信息文本
            context: 额外上下文（如 last_action, provider 等）

        Returns:
            ReasoningResult: 推理结果
        """
        start_time = time.time()
        context = context or {}

        # Step 1: 快速模式匹配（已知错误）
        fast_result = _fast_match(error_message)
        if fast_result and fast_result.confidence >= 0.85:
            logger.debug(f"[Reasoning] Fast match: {fast_result.inferred_config_key}")
            return fast_result

        # Step 2: AI 深度推理（未知错误或低置信度）
        if self._enabled and self._brain:
            try:
                ai_result = self._ai_reason(error_message, context, start_time)
                if ai_result and ai_result.confidence >= 0.6:
                    # AI 推理成功
                    if fast_result:
                        # 如果 AI 推理结果与快速匹配一致，取置信度更高的
                        if (fast_result.inferred_config_key == ai_result.inferred_config_key
                                and ai_result.confidence > fast_result.confidence):
                            return ai_result
                        # 否则取 AI 结果（因为 AI 可能有更多信息）
                        return ai_result
                    return ai_result
            except Exception as e:
                logger.warning(f"[Reasoning] AI reasoning failed: {e}")

        # Step 3: 降级处理
        if fast_result:
            logger.debug(f"[Reasoning] Falling back to fast match: {fast_result.inferred_config_key}")
            return fast_result

        # 完全无法判断
        elapsed_ms = (time.time() - start_time) * 1000
        return ReasoningResult(
            is_config_issue=False,
            confidence=0.0,
            reasoning_steps=["无法确定是否为配置问题，建议检查错误信息或查看日志"],
            original_error=error_message,
            reasoning_time_ms=elapsed_ms,
            reasoning_mode="none",
        )

    def _ai_reason(
        self,
        error_message: str,
        context: Dict[str, Any],
        start_time: float,
    ) -> Optional[ReasoningResult]:
        """调用 AI 进行推理"""
        if not self._brain or not error_message:
            return None

        # 构建上下文字符串
        context_str = json.dumps(context, ensure_ascii=False, indent=2)
        if len(context_str) > 500:
            context_str = context_str[:500] + "..."

        # 填充提示模板
        prompt = self.REASONING_PROMPT_TEMPLATE.format(
            error_message=error_message[:1000],  # 限制长度
            context=context_str,
            config_knowledge=self.CONFIG_KNOWLEDGE,
        )

        # 调用 SystemBrain
        try:
            response = self._brain.generate(
                prompt,
                max_tokens=300,
                temperature=0.1,  # 低温度，保证 JSON 输出的稳定性
            )
        except Exception as e:
            logger.warning(f"[Reasoning] SystemBrain call failed: {e}")
            return None

        # 解析 JSON 响应
        return self._parse_ai_response(response, error_message, start_time)

    def _parse_ai_response(
        self,
        raw_response: str,
        error_message: str,
        start_time: float,
    ) -> Optional[ReasoningResult]:
        """解析 AI 返回的 JSON"""
        try:
            # 提取 JSON（可能有 markdown 包装）
            json_str = raw_response.strip()
            if json_str.startswith("```"):
                # 去掉 markdown 代码块
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            data = json.loads(json_str)

            elapsed_ms = (time.time() - start_time) * 1000

            return ReasoningResult(
                is_config_issue=data.get("is_config_issue", False),
                inferred_config_key=data.get("inferred_config_key"),
                config_category=data.get("config_category", "unknown"),
                inferred_cause=data.get("inferred_cause"),
                action_suggestion=data.get("action_suggestion"),
                link_path=data.get("link_path", "general"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning_steps=[
                    "[AI Reasoning] 分析错误信息",
                    f"[AI Reasoning] 推断配置键: {data.get('inferred_config_key', 'None')}",
                    f"[AI Reasoning] 分类: {data.get('config_category', 'unknown')}",
                    f"[AI Reasoning] 建议: {data.get('action_suggestion', 'N/A')}",
                ],
                original_error=error_message,
                reasoning_time_ms=elapsed_ms,
                reasoning_mode="ai_reasoning",
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[Reasoning] Failed to parse AI response: {e}")
            logger.debug(f"[Reasoning] Raw response: {raw_response[:200]}")
            return None

    def reason_about_config_value(
        self,
        config_key: str,
        config_value: Any,
        expected_type: Optional[str] = None,
    ) -> ReasoningResult:
        """
        推理配置值的合理性

        用于：
        - 验证配置值是否符合预期格式
        - 发现潜在配置错误
        - 给出配置优化建议

        Args:
            config_key: 配置键
            config_value: 当前配置值
            expected_type: 期望的类型（如 "url", "api_key", "model_name"）

        Returns:
            ReasoningResult: 推理结果
        """
        start_time = time.time()
        reason = []

        # URL 格式检查
        if expected_type == "url" or "url" in config_key.lower():
            url_pattern = re.compile(r"^https?://[^\s]+$")
            if not url_pattern.match(str(config_value)):
                reason.append(f"URL 格式不正确: {config_value}")
                # 尝试推断正确格式
                if not str(config_value).startswith("http"):
                    return ReasoningResult(
                        is_config_issue=True,
                        inferred_config_key=config_key,
                        config_category="network",
                        inferred_cause="URL 缺少协议前缀",
                        action_suggestion=f"URL 应以 http:// 或 https:// 开头",
                        link_path="ollama",
                        confidence=0.9,
                        reasoning_steps=reason,
                        original_error=str(config_value),
                        reasoning_time_ms=(time.time() - start_time) * 1000,
                        reasoning_mode="fast_pattern",
                    )

        # API Key 格式检查
        if expected_type == "api_key" or "key" in config_key.lower():
            value_str = str(config_value)
            # 常见 API Key 格式检查
            if len(value_str) < 10:
                reason.append(f"API Key 可能过短: {len(value_str)} 字符")

        # 模型名称格式检查
        if expected_type == "model_name" or "model" in config_key.lower():
            value_str = str(config_value)
            if ":" not in value_str and not value_str.startswith("hf:"):
                reason.append(f"模型名称缺少版本标签: {value_str}")
                return ReasoningResult(
                    is_config_issue=True,
                    inferred_config_key=config_key,
                    config_category="model",
                    inferred_cause="模型名称格式不符合 Ollama 规范",
                    action_suggestion='建议格式: "模型名:版本" 如 qwen2.5:7b',
                    link_path="models",
                    confidence=0.7,
                    reasoning_steps=[
                        "[Fast Pattern] 检查模型名称格式",
                        f"[Fast Pattern] 发现: {value_str} 缺少版本标签",
                    ],
                    original_error=str(config_value),
                    reasoning_time_ms=(time.time() - start_time) * 1000,
                    reasoning_mode="fast_pattern",
                )

        # 无问题
        reason.append("配置值格式检查通过")
        return ReasoningResult(
            is_config_issue=False,
            inferred_config_key=config_key,
            confidence=0.95,
            reasoning_steps=reason,
            original_error=str(config_value),
            reasoning_time_ms=(time.time() - start_time) * 1000,
            reasoning_mode="fast_pattern",
        )

    def batch_reason(self, errors: List[str]) -> List[ReasoningResult]:
        """
        批量推理多条错误信息

        Args:
            errors: 错误信息列表

        Returns:
            List[ReasoningResult]: 推理结果列表
        """
        return [self.reason_about_error(e) for e in errors]


# ── 单例 ─────────────────────────────────────────────────────────────

_reasoning_engine: Optional[AIReasoningEngine] = None


def get_reasoning_engine() -> AIReasoningEngine:
    """获取推理引擎单例"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = AIReasoningEngine()
    return _reasoning_engine


def init_reasoning_engine(system_brain) -> AIReasoningEngine:
    """初始化推理引擎（设置 SystemBrain）"""
    global _reasoning_engine
    _reasoning_engine = AIReasoningEngine(system_brain=system_brain)
    return _reasoning_engine
