"""
LLM-as-a-Verifier Engine — OS级通用验证基础设施

基于 Stanford/Berkeley 的 LLM-as-a-Verifier 框架（ICLR 2026）：
  https://github.com/llm-as-a-verifier/llm-as-a-verifier

核心思想：
  - 不用外部奖励模型，让 LLM 自己当验证者
  - 通过三个维度扩展验证质量：G(粒度)、K(重复验证)、C(标准分解)
  - 奖励公式：R(t, τ) = (1/CK) ΣΣΣ p(v_g|t,c,τ) × φ(v_g)
  - Best-of-N 选择：循环赛机制选最优候选

LivingTree AI OS 集成方式：
  - 作为 GlobalModelRouter 的可选后处理层
  - 任何模块通过 VerifierRegistry 注册评估标准
  - 直接调用 Ollama /api/chat 的 logprobs 参数

作者：LivingTree AI OS
日期：2026-04-27
参考：
  - LLM-as-a-Verifier: https://arxiv.org/abs/2506.01369
  - Incentivizing LLMs to Self-Verify (ICLR 2026)
  - dnhkng/RYS (层重复增强): https://github.com/dnhkng/RYS
from __future__ import annotations
"""


import json
import logging
import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════


class ScoringMode(Enum):
    """评分模式"""
    GRANULARITY = "granularity"       # 粒度评分（G维）：用概率分布计算期望分
    BINARY = "binary"                 # 二元评分：通过/不通过
    LIKERT = "likert"                 # 李克特量表：1-5/1-7/1-10
    CUSTOM = "custom"                 # 自定义评分函数


class SelectionStrategy(Enum):
    """候选选择策略"""
    BEST_OF_N = "best_of_n"           # 最高分即最优
    ROUND_ROBIN = "round_robin"       # 循环赛（两两比较）
    WEIGHTED = "weighted"             # 加权评分
    THRESHOLD = "threshold"           # 阈值筛选（多个可过线）


@dataclass
class VerificationCriteria:
    """单条评估标准"""
    name: str                          # 标准名称（如 "法规符合性"）
    description: str                   # 标准描述（注入 prompt）
    weight: float = 1.0                # 权重（默认等权）
    scoring_mode: ScoringMode = ScoringMode.GRANULARITY
    granularity: int = 20              # G: 评分粒度（1-20）
    threshold: float = 0.0             # 最低通过线（0=无门槛）

    def to_prompt_text(self) -> str:
        """转为 prompt 中的标准描述"""
        mode_desc = {
            ScoringMode.GRANULARITY: f"请按1-{self.granularity}分评估",
            ScoringMode.BINARY: "请判断通过或不通过",
            ScoringMode.LIKERT: f"请按李克特量表评分",
            ScoringMode.CUSTOM: self.description,
        }
        return f"[{self.name}] {mode_desc.get(self.scoring_mode, '')} — {self.description}"


@dataclass
class VerificationConfig:
    """验证配置"""
    # 三大缩放维度
    granularity: int = 20              # G: 评分粒度（用前G个字母/token表示分数）
    n_verifications: int = 3           # K: 重复验证次数（降低方差）
    criteria: list[VerificationCriteria] = field(default_factory=list)  # C: 评估标准

    # 选择策略
    selection_strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN
    threshold: float = 10.0            # 全局最低通过线

    # LLM 配置（默认从 NanochatConfig 读取，不硬编码）
    model: str = ""                    # 验证用模型（空=从系统配置读取 L3 模型）
    temperature: float = 0.1           # 低温度 = 更确定的评分
    num_predict: int = 5               # 只需生成评分 token（极短）

    # Ollama 连接（空=从系统配置读取 ollama.url）
    ollama_url: str = ""

    # 性能
    timeout: int = 30                  # 单次请求超时
    cache_enabled: bool = True         # 缓存验证结果


@dataclass
class VerificationResult:
    """单条候选的验证结果"""
    candidate_id: str                  # 候选标识
    content: str                       # 候选内容
    total_reward: float = 0.0          # 总奖励 R(t, τ)
    criteria_rewards: dict[str, float] = field(default_factory=dict)  # 各维度奖励
    criteria_scores: dict[str, list[float]] = field(default_factory=dict)  # 各维度各轮原始分
    wins: int = 0                      # 循环赛胜场
    matches: int = 0                   # 循环赛总场次
    passed: bool = False               # 是否通过阈值
    metadata: dict = field(default_factory=dict)  # 额外信息


@dataclass
class BatchVerificationResult:
    """批量验证结果"""
    task_description: str
    candidates: list[VerificationResult] = field(default_factory=list)
    best_candidate_id: str = ""
    best_candidate_content: str = ""
    total_candidates: int = 0
    total_verifications: int = 0
    elapsed_seconds: float = 0.0
    config_summary: dict = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════
# 分数 Token 映射
# ════════════════════════════════════════════════════════════════

class ScoreTokenMapper:
    """
    分数 ↔ Token 映射器

    原框架用字母 A-T 表示 1-20 分，我们支持两种模式：
    1. 字母模式（兼容原框架）：A=1, B=2, ..., T=20
    2. 数字模式（本地模型友好）：1=1, 2=2, ..., 20=20
    """

    # 字母 → 分数映射
    LETTER_SCORE_MAP: dict[str, int] = {
        chr(ord('A') + i): i + 1 for i in range(20)
    }
    # 分数 → 字母映射
    SCORE_LETTER_MAP: dict[int, str] = {v: k for k, v in LETTER_SCORE_MAP.items()}

    # 预计算归一化因子
    MAX_SCORE: int = 20
    MIN_SCORE: int = 1

    @classmethod
    def score_to_token(cls, score: int, mode: str = "letter") -> str:
        """分数 → token 字符串"""
        score = max(cls.MIN_SCORE, min(cls.MAX_SCORE, score))
        if mode == "letter":
            return cls.SCORE_LETTER_MAP.get(score, str(score))
        return str(score)

    @classmethod
    def token_to_score(cls, token: str) -> int:
        """token 字符串 → 分数"""
        token = token.strip()
        # 先试字母
        if token.upper() in cls.LETTER_SCORE_MAP:
            return cls.LETTER_SCORE_MAP[token.upper()]
        # 再试数字
        try:
            return max(cls.MIN_SCORE, min(cls.MAX_SCORE, int(token)))
        except ValueError:
            return cls.MIN_SCORE  # 无法解析，给最低分

    @classmethod
    def normalize(cls, score: float) -> float:
        """归一化到 0-1"""
        return (score - cls.MIN_SCORE) / (cls.MAX_SCORE - cls.MIN_SCORE)


# ════════════════════════════════════════════════════════════════
# 核心验证引擎
# ════════════════════════════════════════════════════════════════

class VerifierEngine:
    """
    OS级通用验证引擎

    核心能力：
    1. 从 N 个候选中选最优（Best-of-N）
    2. 通过 G×K×C 三维度扩展验证质量
    3. 直接调用 Ollama logprobs API
    4. 支持任意模块注册评估标准
    """

    def __init__(self, config: VerificationConfig | None = None):
        self.config = config or VerificationConfig()
        self._cache: dict[str, VerificationResult] = {}  # 缓存
        self._usage_history: list[dict] = []  # 使用历史

        # ── 从系统配置填充默认值（不硬编码）──────────────────
        self._load_from_system_config()

    def _load_from_system_config(self):
        """从 NanochatConfig 读取 ollama_url、model 等配置，避免硬编码"""
        try:
            from client.src.business.nanochat_config import config as sys_config
            # Ollama URL
            if not self.config.ollama_url and sys_config.ollama.url:
                self.config.ollama_url = sys_config.ollama.url.rstrip("/v1")
        except ImportError:
            logger.warning("[Verifier] NanochatConfig 不可用，使用空 ollama_url（需手动指定）")

        # 验证模型：如果未指定，尝试从 MEMORY 中记录的配置或合理默认获取
        if not self.config.model:
            # 优先从环境变量
            import os
            self.config.model = os.environ.get("LIVINGTREE_VERIFIER_MODEL", "")
        if not self.config.model:
            # 兜底：使用 L3 意图理解模型（qwen3.5:4b），但不硬编码
            # 由调用方通过 config.model 或 verify["model"] 传入
            logger.info("[Verifier] 未指定验证模型，调用时需通过 model 参数指定")

    # ── 单次概率评分 ──────────────────────────────────────────

    def _call_ollama_logprobs(
        self,
        prompt: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        调用 Ollama /api/chat，获取 logprobs

        返回：
        {
            "content": "生成的文本",
            "logprobs": [{"token": "B", "logprob": -0.3, "top_logprobs": [...]}]
        }
        """
        import urllib.request
        import urllib.error

        url = self.config.ollama_url
        if not url:
            raise RuntimeError(
                "[Verifier] ollama_url 未配置。请在 NanochatConfig 中设置 ollama.url，"
                "或在 VerificationConfig 中指定 ollama_url"
            )
        url = f"{url}/api/chat"
        payload = {
            "model": model or self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.num_predict,
            },
            "logprobs": True,
            "top_logprobs": 20,  # 获取所有候选 token 的概率
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result
        except urllib.error.URLError as e:
            logger.error(f"[Verifier] Ollama 请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"[Verifier] 请求异常: {e}")
            raise

    def _extract_probabilistic_score(
        self,
        response: dict[str, Any],
    ) -> tuple[float, dict[str, float]]:
        """
        从 Ollama logprobs 响应中提取概率化评分

        返回：(期望分, 各token概率分布)
        公式：E[score] = Σ p(v_g) × φ(v_g)
        """
        logprobs_list = response.get("logprobs", [])
        if not logprobs_list:
            # fallback: 直接解析 content
            content = response.get("message", {}).get("content", "").strip()
            score = ScoreTokenMapper.token_to_score(content)
            return float(score), {content: 1.0}

        # 从第一个 token 的 top_logprobs 计算期望
        first_token_probs: dict[str, float] = {}
        expected_score = 0.0

        # 取第一个 token 位置（评分只占一个 token）
        first_entry = logprobs_list[0]
        top_logprobs = first_entry.get("top_logprobs", [])

        if top_logprobs:
            # 从 top_logprobs 提取概率分布
            for entry in top_logprobs:
                token = entry.get("token", "").strip()
                logprob = entry.get("logprob", -999)
                prob = 10 ** (logprob / 10) if logprob > -999 else 0.0  # 简化 log10→概率
                first_token_probs[token] = prob

            # 归一化
            total_prob = sum(first_token_probs.values())
            if total_prob > 0:
                first_token_probs = {k: v / total_prob for k, v in first_token_probs.items()}

            # 计算期望分 E[score]
            for token, prob in first_token_probs.items():
                score = ScoreTokenMapper.token_to_score(token)
                expected_score += prob * score
        else:
            # fallback: 用实际生成的 token
            actual_token = first_entry.get("token", "").strip()
            expected_score = float(ScoreTokenMapper.token_to_score(actual_token))
            first_token_probs[actual_token] = 1.0

        return expected_score, first_token_probs

    # ── 单标准 × 单轮验证 ─────────────────────────────────────

    def _verify_single(
        self,
        task: str,
        candidate: str,
        criterion: VerificationCriteria,
        model: str | None = None,
    ) -> tuple[float, dict[str, float]]:
        """
        对单个候选执行一次验证

        返回：(分数, token概率分布)
        """
        # 构造验证 prompt
        prompt = self._build_verification_prompt(task, candidate, criterion)

        # 调用 LLM + logprobs
        response = self._call_ollama_logprobs(prompt, model)
        score, probs = self._extract_probabilistic_score(response)

        return score, probs

    def _build_verification_prompt(
        self,
        task: str,
        candidate: str,
        criterion: VerificationCriteria,
    ) -> str:
        """构造验证 prompt"""
        if criterion.scoring_mode == ScoringMode.BINARY:
            return f"""请评估以下回答是否满足要求。

## 评估标准
{criterion.name}: {criterion.description}

## 任务
{task}

## 待评估的回答
{candidate}

## 评分方式
请仅输出一个字：通过 或 不通过。"""

        elif criterion.scoring_mode == ScoringMode.LIKERT:
            return f"""请按李克特量表评估以下回答的质量。

## 评估标准
{criterion.name}: {criterion.description}

## 任务
{task}

## 待评估的回答
{candidate}

## 评分方式
请仅输出一个数字（1-{criterion.granularity}），不要输出其他任何内容。"""

        else:  # GRANULARITY (默认)
            return f"""请评估以下回答的质量。

## 评估标准
{criterion.name}: {criterion.description}

## 任务
{task}

## 待评估的回答（截取前2000字）
{candidate[:2000]}

## 评分方式
请仅输出一个大写英文字母（A-{chr(ord('A') + criterion.granularity - 1)}），
其中 A=1分（最差），{chr(ord('A') + criterion.granularity - 1)}={criterion.granularity}分（最好）。
不要输出任何其他内容。"""

    # ── 完整验证流程 ──────────────────────────────────────────

    def verify_candidate(
        self,
        task: str,
        candidate_id: str,
        candidate_content: str,
        criteria: list[VerificationCriteria] | None = None,
        n_verifications: int | None = None,
        model: str | None = None,
    ) -> VerificationResult:
        """
        验证单个候选（C × K 次调用）

        R(t, τ) = (1/CK) × Σ_c Σ_k φ(v_g) × p(v_g|t,c,τ)
        """
        criteria = criteria or self.config.criteria
        K = n_verifications or self.config.n_verifications
        model = model or self.config.model

        if not criteria:
            logger.warning("[Verifier] 未指定评估标准，使用默认通用标准")
            criteria = [VerificationCriteria(
                name="整体质量",
                description="回答的准确性、完整性、相关性",
                granularity=self.config.granularity,
            )]

        # 缓存键
        cache_key = hashlib.md5(
            f"{task}|{candidate_content[:500]}|{[c.name for c in criteria]}|{K}".encode()
        ).hexdigest()

        if self.config.cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]

        result = VerificationResult(
            candidate_id=candidate_id,
            content=candidate_content,
        )

        for criterion in criteria:
            scores_per_round: list[float] = []
            for k in range(K):
                try:
                    score, probs = self._verify_single(
                        task, candidate_content, criterion, model
                    )
                    scores_per_round.append(score)
                except Exception as e:
                    logger.warning(f"[Verifier] 验证异常 ({criterion.name} 第{k+1}轮): {e}")
                    scores_per_round.append(ScoreTokenMapper.MIN_SCORE)

            # 该标准的平均分
            avg_score = sum(scores_per_round) / len(scores_per_round)
            result.criteria_scores[criterion.name] = scores_per_round
            result.criteria_rewards[criterion.name] = avg_score

        # 加权总奖励
        total_weight = sum(c.weight for c in criteria)
        if total_weight > 0:
            result.total_reward = sum(
                result.criteria_rewards[c.name] * c.weight for c in criteria
            ) / total_weight

        # 阈值判断
        result.passed = result.total_reward >= self.config.threshold

        # 缓存
        if self.config.cache_enabled:
            self._cache[cache_key] = result

        return result

    # ── Best-of-N 选择 ────────────────────────────────────────

    def select_best(
        self,
        task: str,
        candidates: dict[str, str] | list[str],
        criteria: list[VerificationCriteria] | None = None,
        strategy: SelectionStrategy | None = None,
        model: str | None = None,
    ) -> BatchVerificationResult:
        """
        从 N 个候选中选最优（Best-of-N）

        candidates:
          dict: {"id1": "content1", "id2": "content2", ...}
          list: ["content1", "content2", ...]（自动编号）

        strategy:
          BEST_OF_N: 直接按总奖励排序
          ROUND_ROBIN: 循环赛（两两比较，每个标准独立比较）
        """
        strategy = strategy or self.config.selection_strategy
        criteria = criteria or self.config.criteria
        model = model or self.config.model

        # 标准化输入
        if isinstance(candidates, list):
            candidates = {str(i): c for i, c in enumerate(candidates)}

        start_time = time.time()
        batch_result = BatchVerificationResult(
            task_description=task,
            total_candidates=len(candidates),
            config_summary={
                "G": self.config.granularity,
                "K": self.config.n_verifications,
                "C": len(criteria),
                "strategy": strategy.value,
                "model": model,
            },
        )

        # 1. 验证所有候选
        for cid, content in candidates.items():
            result = self.verify_candidate(
                task, cid, content, criteria=criteria, model=model
            )
            batch_result.candidates.append(result)

        # 2. 选择策略
        if strategy == SelectionStrategy.BEST_OF_N:
            # 按总奖励排序
            sorted_results = sorted(
                batch_result.candidates,
                key=lambda r: r.total_reward,
                reverse=True,
            )
            best = sorted_results[0]

        elif strategy == SelectionStrategy.ROUND_ROBIN:
            # 循环赛：每个标准独立比较
            results_list = batch_result.candidates
            n = len(results_list)

            for i in range(n):
                for j in range(i + 1, n):
                    ri = results_list[i]
                    rj = results_list[j]

                    # 每个标准投一票
                    for criterion in criteria:
                        score_i = ri.criteria_rewards.get(criterion.name, 0)
                        score_j = rj.criteria_rewards.get(criterion.name, 0)
                        if score_i > score_j:
                            ri.wins += 1
                        elif score_j > score_i:
                            rj.wins += 1
                        ri.matches += 1
                        rj.matches += 1

            best = max(results_list, key=lambda r: r.wins)

        elif strategy == SelectionStrategy.THRESHOLD:
            passed = [r for r in batch_result.candidates if r.passed]
            best = max(passed, key=lambda r: r.total_reward) if passed else max(
                batch_result.candidates, key=lambda r: r.total_reward
            )

        else:  # WEIGHTED = same as BEST_OF_N
            best = max(batch_result.candidates, key=lambda r: r.total_reward)

        batch_result.best_candidate_id = best.candidate_id
        batch_result.best_candidate_content = best.content
        batch_result.elapsed_seconds = time.time() - start_time
        batch_result.total_verifications = (
            len(candidates) * len(criteria) * self.config.n_verifications
        )

        # 记录使用历史
        self._usage_history.append({
            "timestamp": time.time(),
            "task": task[:100],
            "n_candidates": len(candidates),
            "n_criteria": len(criteria),
            "strategy": strategy.value,
            "best_id": best.candidate_id,
            "best_reward": best.total_reward,
            "elapsed": batch_result.elapsed_seconds,
        })

        return batch_result

    # ── 工具方法 ──────────────────────────────────────────────

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        logger.info("[Verifier] 缓存已清除")

    def get_usage_stats(self) -> dict:
        """获取使用统计"""
        if not self._usage_history:
            return {"total_verifications": 0}

        total = len(self._usage_history)
        avg_reward = sum(h["best_reward"] for h in self._usage_history) / total
        avg_time = sum(h["elapsed"] for h in self._usage_history) / total

        return {
            "total_verifications": total,
            "avg_best_reward": round(avg_reward, 2),
            "avg_elapsed_seconds": round(avg_time, 2),
            "most_used_strategy": max(
                set(h["strategy"] for h in self._usage_history),
                key=lambda s: sum(1 for h in self._usage_history if h["strategy"] == s),
            ),
            "recent_5": self._usage_history[-5:],
        }

    def print_verification_report(self, batch_result: BatchVerificationResult):
        """打印验证报告"""
        print("\n" + "=" * 70)
        print("  LLM-as-a-Verifier 验证报告")
        print("=" * 70)
        print(f"  任务：{batch_result.task_description[:80]}")
        print(f"  配置：G={batch_result.config_summary.get('G')}, "
              f"K={batch_result.config_summary.get('K')}, "
              f"C={batch_result.config_summary.get('C')}")
        print(f"  策略：{batch_result.config_summary.get('strategy')}")
        print(f"  模型：{batch_result.config_summary.get('model')}")
        print(f"  耗时：{batch_result.elapsed_seconds:.1f}s "
              f"({batch_result.total_verifications} 次验证)")
        print("-" * 70)

        # 排名
        sorted_results = sorted(
            batch_result.candidates,
            key=lambda r: r.total_reward,
            reverse=True,
        )

        for i, r in enumerate(sorted_results):
            marker = "🏆" if r.candidate_id == batch_result.best_candidate_id else "  "
            status = "✅ PASS" if r.passed else "❌ FAIL"
            print(f"  {marker} #{i+1} [{r.candidate_id}] "
                  f"R={r.total_reward:.2f} {status} "
                  f"(wins={r.wins}/{r.matches})")

            # 各维度详情
            for cname, reward in r.criteria_rewards.items():
                scores = r.criteria_scores.get(cname, [])
                score_str = ", ".join(f"{s:.1f}" for s in scores)
                print(f"       └─ {cname}: {reward:.2f} [{score_str}]")

        print("=" * 70)
        print(f"  最优候选：[{batch_result.best_candidate_id}] "
              f"R={sorted_results[0].total_reward:.2f}")
        print("=" * 70 + "\n")


# ════════════════════════════════════════════════════════════════
# 验证标准注册中心
# ════════════════════════════════════════════════════════════════


class VerifierRegistry:
    """
    验证标准注册中心（单例）

    各模块注册自己的评估标准，VerifierEngine 按模块名查找。
    """

    _instance: VerifierRegistry | None = None

    def __init__(self):
        self._registry: dict[str, list[VerificationCriteria]] = {}
        self._config_overrides: dict[str, dict] = {}

    @classmethod
    def get_instance(cls) -> VerifierRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        module_name: str,
        criteria: list[VerificationCriteria],
        config_override: dict | None = None,
    ):
        """
        注册模块的评估标准

        Args:
            module_name: 模块名（如 "ei_agent", "hermes_agent", "fusion_rag"）
            criteria: 评估标准列表
            config_override: 配置覆盖（如 {"granularity": 10, "n_verifications": 2}）
        """
        self._registry[module_name] = criteria
        if config_override:
            self._config_overrides[module_name] = config_override
        logger.info(f"[VerifierRegistry] 注册模块 '{module_name}': "
                    f"{len(criteria)} 条标准")

    def get_criteria(self, module_name: str) -> list[VerificationCriteria]:
        """获取模块的评估标准"""
        return self._registry.get(module_name, [])

    def get_config_override(self, module_name: str) -> dict:
        """获取模块的配置覆盖"""
        return self._config_overrides.get(module_name, {})

    def list_modules(self) -> list[str]:
        """列出所有已注册模块"""
        return list(self._registry.keys())

    def unregister(self, module_name: str):
        """注销模块"""
        self._registry.pop(module_name, None)
        self._config_overrides.pop(module_name, None)


# ════════════════════════════════════════════════════════════════
# 预置评估标准
# ════════════════════════════════════════════════════════════════


def get_universal_criteria() -> list[VerificationCriteria]:
    """通用评估标准（适用于所有模块）"""
    return [
        VerificationCriteria(
            name="准确性",
            description="回答是否事实正确、无幻觉、无错误信息",
            weight=1.5,
            granularity=20,
        ),
        VerificationCriteria(
            name="完整性",
            description="回答是否完整覆盖了任务要求的所有方面",
            weight=1.2,
            granularity=20,
        ),
        VerificationCriteria(
            name="相关性",
            description="回答是否与任务直接相关，没有跑题或冗余信息",
            weight=1.0,
            granularity=20,
        ),
    ]


def get_ei_agent_criteria() -> list[VerificationCriteria]:
    """环评模块评估标准"""
    return [
        VerificationCriteria(
            name="法规符合性",
            description="是否引用并遵循了相关环保法规和标准（如GB、HJ标准）",
            weight=1.5,
            granularity=20,
        ),
        VerificationCriteria(
            name="数据准确性",
            description="环评数据（气象、地形、排放源）是否合理、有依据",
            weight=1.5,
            granularity=20,
        ),
        VerificationCriteria(
            name="评价方法正确性",
            description="采用的预测模型和评价方法是否符合导则要求",
            weight=1.3,
            granularity=20,
        ),
        VerificationCriteria(
            name="结论可靠性",
            description="评价结论是否逻辑清晰、有充分的数据支撑",
            weight=1.2,
            granularity=20,
        ),
        VerificationCriteria(
            name="完整性",
            description="是否覆盖了所有评价因子和敏感目标",
            weight=1.0,
            granularity=20,
        ),
        VerificationCriteria(
            name="对策可行性",
            description="环保对策措施是否具有技术可行性和经济合理性",
            weight=1.0,
            granularity=20,
        ),
        VerificationCriteria(
            name="风险识别",
            description="是否识别了潜在环境风险并提出了应急方案",
            weight=0.8,
            granularity=20,
        ),
    ]


def get_fusion_rag_criteria() -> list[VerificationCriteria]:
    """检索增强模块评估标准"""
    return [
        VerificationCriteria(
            name="检索相关性",
            description="检索到的文档片段是否与用户查询直接相关",
            weight=1.5,
            granularity=20,
        ),
        VerificationCriteria(
            name="信息完整性",
            description="是否检索到了足够的信息来回答用户的问题",
            weight=1.2,
            granularity=20,
        ),
        VerificationCriteria(
            name="时效性",
            description="检索到的信息是否为最新、有效的",
            weight=1.0,
            granularity=20,
        ),
    ]


def get_code_generation_criteria() -> list[VerificationCriteria]:
    """代码生成模块评估标准"""
    return [
        VerificationCriteria(
            name="正确性",
            description="生成的代码是否能正确运行、无语法和逻辑错误",
            weight=2.0,
            granularity=20,
        ),
        VerificationCriteria(
            name="可读性",
            description="代码是否结构清晰、命名规范、有适当注释",
            weight=1.0,
            granularity=20,
        ),
        VerificationCriteria(
            name="安全性",
            description="代码是否存在安全漏洞（注入、XSS等）",
            weight=1.5,
            granularity=20,
        ),
    ]


# ════════════════════════════════════════════════════════════════
# 便捷函数
# ════════════════════════════════════════════════════════════════

_engine_instance: VerifierEngine | None = None


def get_verifier_engine(config: VerificationConfig | None = None) -> VerifierEngine:
    """获取全局 VerifierEngine 单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = VerifierEngine(config)
    return _engine_instance


def quick_verify(
    task: str,
    candidate: str,
    criteria: list[VerificationCriteria] | None = None,
) -> VerificationResult:
    """
    快速验证单个候选（使用默认配置）

    Args:
        task: 任务描述
        candidate: 候选回答
        criteria: 评估标准（None=通用标准）

    Returns:
        VerificationResult
    """
    engine = get_verifier_engine()
    return engine.verify_candidate(
        task=task,
        candidate_id="default",
        candidate_content=candidate,
        criteria=criteria or get_universal_criteria(),
    )


def auto_register_default_modules():
    """
    自动注册 LivingTree OS 内置模块的评估标准

    在系统启动时调用一次即可。
    """
    registry = VerifierRegistry.get_instance()

    # 注册各模块的标准
    registry.register("universal", get_universal_criteria())
    registry.register("ei_agent", get_ei_agent_criteria(), {
        "granularity": 20,
        "n_verifications": 4,  # 环评需要更严格的验证
        "threshold": 12.0,
    })
    registry.register("fusion_rag", get_fusion_rag_criteria(), {
        "n_verifications": 2,
    })
    registry.register("code_generation", get_code_generation_criteria(), {
        "n_verifications": 3,
    })

    logger.info(f"[VerifierRegistry] 已注册 {len(registry.list_modules())} 个模块")
    return registry
