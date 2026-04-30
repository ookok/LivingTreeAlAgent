"""
ModelAutoDetectorAndUpgrader - 模型自动检测与升级器

功能：
1. 检测新 API 连接（用户添加后自动发现）
2. 自动测试模型能力（thinking、多模态、速度、质量）
3. 自动对比现有 L0/L3/L4 模型，决策是否升级
4. 通过 UserClarificationRequester 询问用户确认
5. 自动更新模型配置

所有 LLM 连接信息从 NanochatConfig 读取，不硬编码。
"""

import asyncio
import json
import os
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger

try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


@dataclass
class ModelProfile:
    """模型能力画像"""
    model_name: str
    api_endpoint: str               # API 地址
    api_type: str = "ollama"        # ollama / openai_compatible / custom

    # 能力指标
    thinking_capable: bool = False  # 是否支持思考模式
    multimodal_capable: bool = False  # 是否支持多模态
    speed_tokens_per_sec: float = 0.0  # 生成速度
    quality_score: float = 0.0      # 质量评分 (0-10)
    context_length: int = 4096      # 上下文长度
    parameter_size: str = ""        # 参数量描述（如 "7B", "35B"）

    # 测试状态
    tested_at: float = 0.0
    test_success: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "api_endpoint": self.api_endpoint,
            "api_type": self.api_type,
            "thinking_capable": self.thinking_capable,
            "multimodal_capable": self.multimodal_capable,
            "speed_tokens_per_sec": round(self.speed_tokens_per_sec, 2),
            "quality_score": round(self.quality_score, 1),
            "context_length": self.context_length,
            "parameter_size": self.parameter_size,
            "tested_at": self.tested_at,
            "test_success": self.test_success,
        }


@dataclass
class UpgradeDecision:
    """升级决策"""
    should_upgrade: bool
    level: str                       # L0 / L3 / L4
    current_model: str
    new_model: str
    reason: str
    speed_improvement: float = 0.0   # 速度提升百分比
    quality_improvement: float = 0.0 # 质量提升百分比
    requires_confirmation: bool = True


class ModelAutoDetectorAndUpgrader:
    """
    模型自动检测与升级器

    功能：
    1. 监控配置变化，发现新的 API 端点
    2. 自动测试端点上可用模型的能力
    3. 对比现有 L0/L3/L4 模型
    4. 决策是否升级（可配置为自动或需用户确认）

    用法：
        detector = ModelAutoDetectorAndUpgrader()

        # 手动触发检测
        await detector.detect_and_evaluate()

        # 后台监控
        await detector.start_monitoring()

        # 手动添加端点
        await detector.add_endpoint("http://new-api:11434", "ollama")
    """

    # 升级阈值（新模型需要显著优于现有模型才升级）
    SPEED_IMPROVEMENT_THRESHOLD = 1.3   # 速度提升 30%
    QUALITY_IMPROVEMENT_THRESHOLD = 1.15  # 质量提升 15%

    # 速度测试 prompt
    SPEED_TEST_PROMPT = "请重复以下数字序列：1, 2, 3, 4, 5, 6, 7, 8, 9, 10"

    # 质量测试 prompt（简单推理题）
    QUALITY_TEST_PROMPT = """一个农夫带着一只狼、一只羊和一棵白菜过河。
河上有一条小船，农夫每次只能带一样东西过河。
如果农夫不在，狼会吃羊，羊会吃白菜。
请给出最少的过河步骤。"""

    def __init__(
        self,
        require_user_confirmation: bool = True,
        auto_upgrade_threshold: str = "significant",  # any / significant / none
        check_interval: int = 600,  # 后台检查间隔（秒），默认 10 分钟
    ):
        """
        初始化

        Args:
            require_user_confirmation: 是否需要用户确认升级
            auto_upgrade_threshold: 自动升级阈值
                - "any": 任何改进都升级
                - "significant": 显著改进才升级（默认）
                - "none": 不自动升级
            check_interval: 后台检查间隔（秒）
        """
        self._require_confirmation = require_user_confirmation
        self._auto_threshold = auto_upgrade_threshold
        self._check_interval = check_interval

        # 已知的 API 端点和模型画像
        self._known_endpoints: Dict[str, str] = {}  # url -> api_type
        self._model_profiles: Dict[str, ModelProfile] = {}  # "endpoint:model" -> ModelProfile
        self._upgrade_history: List[Dict[str, Any]] = []

        # 当前模型配置（从系统读取）
        self._current_models: Dict[str, str] = {}  # L0/L3/L4 -> model_name

        self._logger = logger.bind(component="ModelAutoDetector")
        self._running = False

        # 初始化
        self._load_current_config()

    # ── 配置读取 ────────────────────────────────────────

    def _load_current_config(self):
        """从系统配置加载当前模型配置"""
        try:
            from business.nanochat_config import config
            ollama_url = config.ollama.url

            if ollama_url:
                self._known_endpoints[ollama_url] = "ollama"

            self._logger.info(f"从 NanochatConfig 加载 Ollama 端点: {ollama_url}")
        except Exception as e:
            self._logger.warning(f"加载 NanochatConfig 失败: {e}")

        # 从环境变量检测 API
        env_endpoints = {
            "OPENAI_API_BASE": "openai",
            "OPENAI_BASE_URL": "openai",
            "OLLAMA_HOST": "ollama",
            "OLLAMA_URL": "ollama",
            "ANTHROPIC_BASE_URL": "anthropic",
        }
        for env_var, api_type in env_endpoints.items():
            url = os.environ.get(env_var, "")
            if url and url not in self._known_endpoints:
                self._known_endpoints[url] = api_type
                self._logger.info(f"从环境变量检测到 {api_type} 端点: {url} ({env_var})")

        # 加载当前选举模型
        self._load_elected_models()

    def _load_elected_models(self):
        """加载当前选举的 L0/L3/L4 模型"""
        # 尝试从 GlobalModelRouter 获取当前模型
        try:
            from business.global_model_router import get_global_router
            router = get_global_router()
            if router and hasattr(router, '_tier_models'):
                self._current_models = dict(router._tier_models)
                self._logger.info(f"当前选举模型: {self._current_models}")
        except Exception:
            pass

        # 如果无法从 router 获取，使用默认值
        if not self._current_models:
            self._current_models = {
                "L0": "qwen3.5:2b",
                "L3": "qwen3.5:4b",
                "L4": "qwen3.6:35b-a3b",
            }

    def _get_ollama_url(self) -> str:
        """获取 Ollama URL（从系统配置）"""
        try:
            from business.nanochat_config import config
            return config.ollama.url or "http://localhost:11434"
        except Exception:
            return "http://localhost:11434"

    # ── API 端点检测 ────────────────────────────────────

    async def detect_and_evaluate(self) -> List[ModelProfile]:
        """
        检测所有已知端点上的可用模型并评估

        Returns:
            发现的模型画像列表
        """
        self._logger.info("开始检测可用模型...")

        all_profiles = []

        for endpoint, api_type in self._known_endpoints.items():
            try:
                models = await self._list_models(endpoint, api_type)
                self._logger.info(f"端点 {endpoint}: 发现 {len(models)} 个模型")

                for model_name in models:
                    profile = await self._test_model(endpoint, api_type, model_name)
                    if profile:
                        all_profiles.append(profile)
                        key = f"{endpoint}:{model_name}"
                        self._model_profiles[key] = profile

            except Exception as e:
                self._logger.error(f"检测端点 {endpoint} 失败: {e}")

        # 对比并决策
        for profile in all_profiles:
            await self._evaluate_upgrade(profile)

        self._logger.info(
            f"检测完成: {len(all_profiles)} 个模型可用, "
            f"{len([p for p in all_profiles if p.test_success])} 个测试通过"
        )
        return all_profiles

    async def _list_models(self, endpoint: str, api_type: str) -> List[str]:
        """列出 API 端点上的可用模型"""
        models = []

        if api_type == "ollama":
            models = await self._list_ollama_models(endpoint)
        elif api_type in ("openai", "openai_compatible"):
            models = await self._list_openai_models(endpoint)
        else:
            self._logger.warning(f"不支持的 API 类型: {api_type}")

        return models

    async def _list_ollama_models(self, endpoint: str) -> List[str]:
        """列出 Ollama 端点的可用模型"""
        try:
            url = endpoint.rstrip("/") + "/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            self._logger.error(f"获取 Ollama 模型列表失败: {e}")
            return []

    async def _list_openai_models(self, endpoint: str) -> List[str]:
        """列出 OpenAI 兼容端点的可用模型"""
        try:
            url = endpoint.rstrip("/") + "/models"
            req = urllib.request.Request(url)
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except Exception as e:
            self._logger.error(f"获取 OpenAI 模型列表失败: {e}")
            return []

    # ── 模型能力测试 ────────────────────────────────────

    async def _test_model(
        self, endpoint: str, api_type: str, model_name: str
    ) -> Optional[ModelProfile]:
        """测试单个模型的能力"""
        self._logger.info(f"测试模型: {model_name} @ {endpoint}")

        profile = ModelProfile(
            model_name=model_name,
            api_endpoint=endpoint,
            api_type=api_type,
        )

        try:
            # 并行测试
            thinking, multimodal, speed, quality = await asyncio.gather(
                self._test_thinking(endpoint, api_type, model_name),
                self._test_multimodal(endpoint, api_type, model_name),
                self._test_speed(endpoint, api_type, model_name),
                self._test_quality(endpoint, api_type, model_name),
                return_exceptions=True,
            )

            profile.thinking_capable = thinking if isinstance(thinking, bool) else False
            profile.multimodal_capable = multimodal if isinstance(multimodal, bool) else False
            profile.speed_tokens_per_sec = speed if isinstance(speed, (int, float)) else 0.0
            profile.quality_score = quality if isinstance(quality, (int, float)) else 0.0

            profile.test_success = True
            profile.tested_at = time.time()

            self._logger.info(
                f"  {model_name}: thinking={profile.thinking_capable}, "
                f"multimodal={profile.multimodal_capable}, "
                f"speed={profile.speed_tokens_per_sec:.1f} tok/s, "
                f"quality={profile.quality_score:.1f}/10"
            )

        except Exception as e:
            profile.test_success = False
            profile.error = str(e)
            self._logger.error(f"  {model_name} 测试失败: {e}")

        return profile

    async def _test_thinking(
        self, endpoint: str, api_type: str, model_name: str
    ) -> bool:
        """测试模型是否支持思考模式"""
        try:
            response = await self._chat_completion(
                endpoint, api_type, model_name,
                prompt="1+1=?",
                max_tokens=200,
            )
            # 如果响应为空但 thinking 不为空，说明是思考模型
            if not response.get("content") and response.get("thinking"):
                return True

            # 如果响应中包含 <think 标签，也认为支持思考
            content = response.get("content", "") + response.get("thinking", "")
            if "<think" in content or "思考" in content[:50]:
                return True

            return False
        except Exception:
            return False

    async def _test_multimodal(
        self, endpoint: str, api_type: str, model_name: str
    ) -> bool:
        """测试模型是否支持多模态（通过名称启发式判断）"""
        multimodal_keywords = [
            "vision", "vl", "vlm", "multimodal", "image",
            "llava", "cogvlm", "qwen-vl", "gemini",
        ]
        name_lower = model_name.lower()
        for kw in multimodal_keywords:
            if kw in name_lower:
                return True
        return False

    async def _test_speed(
        self, endpoint: str, api_type: str, model_name: str
    ) -> float:
        """测试模型生成速度（tokens/second）"""
        try:
            start = time.time()
            response = await self._chat_completion(
                endpoint, api_type, model_name,
                prompt=self.SPEED_TEST_PROMPT,
                max_tokens=100,
            )
            elapsed = time.time() - start

            content = response.get("content", "") or response.get("thinking", "")
            # 粗略估计 token 数（中文约 1.5 字/token）
            token_count = len(content) / 1.5

            if elapsed > 0 and token_count > 0:
                return token_count / elapsed

            return 0.0
        except Exception:
            return 0.0

    async def _test_quality(
        self, endpoint: str, api_type: str, model_name: str
    ) -> float:
        """测试模型推理质量（0-10 分）"""
        try:
            response = await self._chat_completion(
                endpoint, api_type, model_name,
                prompt=self.QUALITY_TEST_PROMPT,
                max_tokens=500,
            )

            content = response.get("content", "") or response.get("thinking", "")

            # 启发式评分
            score = 0.0

            # 1. 内容长度（太短说明没答好）
            if len(content) > 100:
                score += 2.0
            elif len(content) > 50:
                score += 1.0

            # 2. 包含关键词（说明理解了题目）
            keywords = ["农夫", "狼", "羊", "白菜", "过河", "船"]
            found = sum(1 for kw in keywords if kw in content)
            score += found * 1.0  # 每个关键词 1 分

            # 3. 步骤化（说明给出了方案）
            step_indicators = ["第", "步", "1.", "2.", "1）", "2）", "首先", "然后", "最后"]
            found_steps = sum(1 for si in step_indicators if si in content)
            score += min(found_steps * 0.5, 2.0)

            return min(score, 10.0)
        except Exception:
            return 0.0

    async def _chat_completion(
        self,
        endpoint: str,
        api_type: str,
        model_name: str,
        prompt: str,
        max_tokens: int = 200,
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        if api_type == "ollama":
            return await self._ollama_chat(endpoint, model_name, prompt, max_tokens)
        elif api_type in ("openai", "openai_compatible"):
            return await self._openai_chat(endpoint, model_name, prompt, max_tokens)
        else:
            return {}

    async def _ollama_chat(
        self, endpoint: str, model_name: str, prompt: str, max_tokens: int
    ) -> Dict[str, Any]:
        """Ollama /api/chat 请求"""
        url = endpoint.rstrip("/") + "/api/chat"
        payload = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        loop = asyncio.get_event_loop()
        resp_text = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        )

        data = json.loads(resp_text)
        message = data.get("message", {})
        return {
            "content": message.get("content", ""),
            "thinking": message.get("thinking", ""),
        }

    async def _openai_chat(
        self, endpoint: str, model_name: str, prompt: str, max_tokens: int
    ) -> Dict[str, Any]:
        """OpenAI 兼容 /chat/completions 请求"""
        url = endpoint.rstrip("/") + "/chat/completions"
        payload = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        loop = asyncio.get_event_loop()
        resp_text = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        )

        data = json.loads(resp_text)
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return {
                "content": message.get("content", ""),
                "thinking": "",  # OpenAI 格式暂不解析 thinking
            }
        return {}

    # ── 升级决策 ────────────────────────────────────────

    async def _evaluate_upgrade(self, profile: ModelProfile) -> Optional[UpgradeDecision]:
        """评估是否应该升级某个层级"""
        if not profile.test_success:
            return None

        decisions = []

        # 对比 L0（速度优先）
        l0_decision = self._compare_for_level(profile, "L0", prioritize_speed=True)
        if l0_decision:
            decisions.append(l0_decision)

        # 对比 L3（推理优先）
        l3_decision = self._compare_for_level(profile, "L3", prioritize_quality=True)
        if l3_decision:
            decisions.append(l3_decision)

        # 对比 L4（生成质量优先）
        l4_decision = self._compare_for_level(profile, "L4", prioritize_quality=True)
        if l4_decision:
            decisions.append(l4_decision)

        # 处理决策
        for decision in decisions:
            if not decision.should_upgrade:
                continue

            if self._require_confirmation:
                approved = await self._request_user_confirmation(decision)
                if approved:
                    await self._execute_upgrade(decision)
                else:
                    self._logger.info(f"用户拒绝升级: {decision.new_model}")
            elif self._auto_threshold != "none":
                await self._execute_upgrade(decision)

        return decisions[0] if decisions else None

    def _compare_for_level(
        self,
        new_profile: ModelProfile,
        level: str,
        prioritize_speed: bool = False,
        prioritize_quality: bool = False,
    ) -> Optional[UpgradeDecision]:
        """将新模型与指定层级的当前模型对比"""
        current_model_name = self._current_models.get(level, "")
        if not current_model_name or new_profile.model_name == current_model_name:
            return None  # 相同模型，跳过

        # 获取当前模型的画像（如果测试过）
        current_profile = self._get_profile_for_model(current_model_name)

        # 对比指标
        if current_profile and current_profile.test_success:
            speed_ratio = (
                new_profile.speed_tokens_per_sec / current_profile.speed_tokens_per_sec
                if current_profile.speed_tokens_per_sec > 0 else 1.0
            )
            quality_diff = new_profile.quality_score - current_profile.quality_score
        else:
            # 没有当前模型画像，使用默认值
            speed_ratio = new_profile.speed_tokens_per_sec / 5.0  # 假设 5 tok/s 基线
            quality_diff = new_profile.quality_score - 5.0  # 假设 5 分基线

        should_upgrade = False
        reason = ""

        if prioritize_speed:
            if speed_ratio >= self.SPEED_IMPROVEMENT_THRESHOLD:
                should_upgrade = True
                reason = f"速度提升 {speed_ratio:.1f}x（阈值 {self.SPEED_IMPROVEMENT_THRESHOLD}x）"
            elif self._auto_threshold == "any" and speed_ratio > 1.0:
                should_upgrade = True
                reason = f"速度提升 {speed_ratio:.1f}x（any 模式）"

        elif prioritize_quality:
            quality_ratio = new_profile.quality_score / max(current_profile.quality_score, 0.1) if current_profile and current_profile.test_success else new_profile.quality_score / 5.0
            if quality_ratio >= self.QUALITY_IMPROVEMENT_THRESHOLD:
                should_upgrade = True
                reason = f"质量提升 {quality_diff:.1f} 分（阈值 {self.QUALITY_IMPROVEMENT_THRESHOLD}x）"
            elif self._auto_threshold == "any" and quality_diff > 0:
                should_upgrade = True
                reason = f"质量提升 {quality_diff:.1f} 分（any 模式）"

        if not should_upgrade:
            reason = f"提升不够显著（速度 {speed_ratio:.1f}x, 质量 +{quality_diff:.1f}）"

        return UpgradeDecision(
            should_upgrade=should_upgrade,
            level=level,
            current_model=current_model_name,
            new_model=new_profile.model_name,
            reason=reason,
            speed_improvement=speed_ratio - 1.0,
            quality_improvement=quality_diff,
            requires_confirmation=self._require_confirmation,
        )

    def _get_profile_for_model(self, model_name: str) -> Optional[ModelProfile]:
        """获取已测试过的模型画像"""
        for key, profile in self._model_profiles.items():
            if profile.model_name == model_name and profile.test_success:
                return profile
        return None

    async def _request_user_confirmation(self, decision: UpgradeDecision) -> bool:
        """请求用户确认升级"""
        self._logger.info(f"请求用户确认升级 {decision.level}: {decision.new_model}")

        try:
            from business.self_evolution.user_clarification_requester import (
                UserClarificationRequester
            )
            requester = UserClarificationRequester()

            response = await requester.request_clarification(
                question=(
                    f"发现更好的 {decision.level} 模型候选：\n\n"
                    f"  当前: {decision.current_model}\n"
                    f"  新模型: {decision.new_model}\n"
                    f"  速度提升: {decision.speed_improvement * 100:+.0f}%\n"
                    f"  质量变化: {decision.quality_improvement:+.1f} 分\n"
                    f"  原因: {decision.reason}\n\n"
                    f"是否升级？"
                ),
                options=[
                    "A. 立即升级",
                    "B. 稍后提醒我",
                    "C. 跳过此模型",
                ]
            )

            if response and "A" in response:
                return True
            return False

        except Exception as e:
            self._logger.warning(f"用户确认请求失败（默认不升级）: {e}")
            return False

    async def _execute_upgrade(self, decision: UpgradeDecision):
        """执行模型升级"""
        self._logger.info(
            f"执行 {decision.level} 模型升级: "
            f"{decision.current_model} → {decision.new_model}"
        )

        # 更新内存中的模型配置
        self._current_models[decision.level] = decision.new_model

        # 尝试更新 GlobalModelRouter
        try:
            from business.global_model_router import get_global_router
            router = get_global_router()
            if router and hasattr(router, '_tier_models'):
                router._tier_models[decision.level] = decision.new_model
                self._logger.info(f"GlobalModelRouter 模型已更新")
        except Exception as e:
            self._logger.warning(f"更新 GlobalModelRouter 失败: {e}")

        # 记录升级历史
        self._upgrade_history.append({
            "level": decision.level,
            "from": decision.current_model,
            "to": decision.new_model,
            "reason": decision.reason,
            "timestamp": time.time(),
        })

        self._logger.info(f"{decision.level} 模型升级完成: {decision.new_model}")

    # ── 手动添加端点 ────────────────────────────────────

    async def add_endpoint(self, url: str, api_type: str = "ollama"):
        """
        手动添加 API 端点

        Args:
            url: API 端点 URL
            api_type: API 类型（ollama / openai / openai_compatible）
        """
        if url in self._known_endpoints:
            self._logger.info(f"端点已存在: {url}")
            return

        self._known_endpoints[url] = api_type
        self._logger.info(f"添加端点: {url} ({api_type})")

        # 立即检测
        await self.detect_and_evaluate()

    # ── 后台监控 ────────────────────────────────────────

    async def start_monitoring(self):
        """开始后台监控（检测新端点和模型）"""
        self._running = True
        self._logger.info(
            f"开始后台监控（每 {self._check_interval}s 检查一次）"
        )

        while self._running:
            try:
                # 重新加载配置（检测变化）
                old_endpoints = dict(self._known_endpoints)
                self._load_current_config()

                # 如果有新端点
                new_endpoints = set(self._known_endpoints.keys()) - set(old_endpoints.keys())
                if new_endpoints:
                    self._logger.info(f"检测到新端点: {new_endpoints}")
                    await self.detect_and_evaluate()

            except Exception as e:
                self._logger.error(f"监控循环异常: {e}")

            await asyncio.sleep(self._check_interval)

    def stop_monitoring(self):
        """停止后台监控"""
        self._running = False
        self._logger.info("后台监控已停止")

    # ── 工具方法 ────────────────────────────────────────

    def list_profiles(self) -> List[Dict[str, Any]]:
        """列出所有已测试的模型画像"""
        return [p.to_dict() for p in self._model_profiles.values()]

    def get_upgrade_history(self) -> List[Dict[str, Any]]:
        """获取升级历史"""
        return list(self._upgrade_history)

    def get_current_models(self) -> Dict[str, str]:
        """获取当前模型配置"""
        return dict(self._current_models)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "known_endpoints": len(self._known_endpoints),
            "tested_models": len(self._model_profiles),
            "successful_tests": sum(
                1 for p in self._model_profiles.values() if p.test_success
            ),
            "upgrade_count": len(self._upgrade_history),
            "current_models": self._current_models,
            "monitoring": self._running,
        }
