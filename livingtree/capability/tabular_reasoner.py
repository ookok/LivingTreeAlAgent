"""TabularReasoner — TabPFN-inspired in-context tabular reasoning for LLMs.

TabPFN methodology adapted for Agent use (no PyTorch, no GPU):
  1. In-context tabular learning — LLM sees table + task in one prompt
  2. Synthetic example pre-training — show solved examples before real data
  3. No preprocessing — raw values, LLM handles mixed types natively
  4. Multi-perspective ensembling — statistical + domain + pattern views
  5. Lightweight sklearn fallback — when LLM call is unnecessary or unavailable

Designed for EIA (Environmental Impact Assessment) tabular tasks:
  - Water quality classification (COD/BOD/DO/NH3-N → grade I-V)
  - Air quality assessment (SO2/NO2/PM2.5/PM10 → grade I-III)
  - Noise level classification (dB → 0-4b class)
  - Pollutant concentration prediction (source→receptor regression)
  - Outlier detection in monitoring data
  - Missing value imputation

Usage:
    from livingtree.capability.tabular_reasoner import TabularReasoner
    reasoner = TabularReasoner()
    result = reasoner.classify_water_quality(cod=25, bod=4, do=6.5, nh3n=0.8)
    result = reasoner.classify_air_quality(so2=30, no2=35, pm25=45, pm10=80)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TabularResult:
    task: str
    prediction: str
    confidence: float
    reasoning: str
    method: str
    alternatives: list[dict] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


class TabularReasoner:
    """LLM-driven tabular reasoning without heavy ML dependencies.

    Uses in-context learning: provides the LLM with synthetic examples
    of the same task type before the real data, then asks for inference.
    Falls back to rule-based classification when LLM is unavailable.
    """

    WATER_QUALITY_EXAMPLE = {
        "task": "classify_water_quality",
        "input": {"COD": 20, "BOD": 4, "DO": 7.5, "NH3N": 0.15},
        "output": "I类 (源头水/饮用水一级保护区)",
        "reasoning": "COD=20≤40(I类限值), BOD=4≤3(I类限值)? 不满足，BOD>3则至少II类。BOD=4≤8(II类限值), DO=7.5≥6(II类), NH3N=0.15≤0.15(I类). 综合: BOD最严格, 水质为II类",
    }

    AIR_QUALITY_EXAMPLE = {
        "task": "classify_air_quality",
        "input": {"SO2": 30, "NO2": 35, "PM10": 80, "PM2.5": 45},
        "output": "二类区达标, 但PM2.5接近限值",
        "reasoning": "SO2=30≤60(I类年均), NO2=35≤40(I类年均), PM10=80≤150(I类日均)但>70(I类年均? 需确认年均/日均). PM2.5=45>35(I类年均限值)所以为二类区. 综合: 空气质量为二类, PM2.5是主要控制因子",
    }

    # GB3838-2002 地表水标准
    WATER_STANDARDS = {
        "I": {"COD": 15, "BOD": 3, "DO": 7.5, "NH3N": 0.15},
        "II": {"COD": 15, "BOD": 3, "DO": 6, "NH3N": 0.5},
        "III": {"COD": 20, "BOD": 4, "DO": 5, "NH3N": 1.0},
        "IV": {"COD": 30, "BOD": 6, "DO": 3, "NH3N": 1.5},
        "V": {"COD": 40, "BOD": 10, "DO": 2, "NH3N": 2.0},
    }

    # GB3095-2012 环境空气标准 (年均值, 二类区)
    AIR_STANDARDS = {
        "I": {"SO2": 20, "NO2": 40, "PM10": 40, "PM2.5": 15,
              "CO": 4, "O3": 100},
        "II": {"SO2": 60, "NO2": 40, "PM10": 70, "PM2.5": 35,
               "CO": 4, "O3": 160},
    }

    # GB3096-2008 声环境标准 (dB)
    NOISE_STANDARDS = {
        "0": {"day": 50, "night": 40, "desc": "康复疗养区"},
        "1": {"day": 55, "night": 45, "desc": "居民区"},
        "2": {"day": 60, "night": 50, "desc": "商住混合区"},
        "3": {"day": 65, "night": 55, "desc": "工业区"},
        "4a": {"day": 70, "night": 55, "desc": "交通干道两侧"},
        "4b": {"day": 70, "night": 60, "desc": "铁路两侧"},
    }

    def __init__(self, consciousness: Any = None):
        self.consciousness = consciousness

    # ── Rule-based checks (no LLM needed) ──

    def classify_water_quality(self, cod: float = 0, bod: float = 0,
                                do: float = 0, nh3n: float = 0) -> TabularResult:
        """Classify water quality per GB3838-2002 using worst-parameter rule."""
        params = {"COD": cod, "BOD": bod, "DO": do, "NH3N": nh3n}

        grades = []
        for grade, limits in self.WATER_STANDARDS.items():
            violations = []
            for param, value in params.items():
                limit = limits.get(param, float("inf"))
                if param == "DO":
                    if value < limit:
                        violations.append(f"{param}={value}<{limit}")
                else:
                    if value > limit:
                        violations.append(f"{param}={value}>{limit}")
            grades.append({"grade": grade, "violations": violations})

        worst = "V"
        grade_details = []
        for g in grades:
            details = f"{g['grade']}类: "
            details += (f"超标({'; '.join(g['violations'])})" if g["violations"]
                       else "达标")
            grade_details.append(details)
            if not g["violations"] and worst == "V":
                worst = g["grade"]

        constraint = next((g["violations"] for g in grades
                          if g["grade"] == worst), ["全部达标"])

        return TabularResult(
            task="water_quality_classification",
            prediction=f"{worst}类",
            confidence=1.0,
            reasoning=f"分级评估: {'; '.join(grade_details)}. 综合评定{worst}类",
            method="rule_based",
            raw_data=params,
        )

    def classify_air_quality(self, so2: float = 0, no2: float = 0,
                              pm10: float = 0, pm25: float = 0,
                              co: float = 0, o3: float = 0) -> TabularResult:
        """Classify air quality per GB3095-2012 (annual average, class II area)."""
        params = {"SO2": so2, "NO2": no2, "PM10": pm10, "PM2.5": pm25,
                  "CO": co, "O3": o3}
        active_params = {k: v for k, v in params.items() if v > 0}

        if not active_params:
            return TabularResult(task="air_quality_classification",
                                  prediction="无数据", confidence=0.0,
                                  reasoning="未提供监测数据", method="rule_based")

        violations_i = []
        violations_ii = []
        for param, value in active_params.items():
            limit_i = self.AIR_STANDARDS["I"].get(param, float("inf"))
            limit_ii = self.AIR_STANDARDS["II"].get(param, float("inf"))
            if value > limit_i:
                violations_i.append(f"{param}={value}>{limit_i}(I类)")
            if value > limit_ii:
                violations_ii.append(f"{param}={value}>{limit_ii}(II类)")

        if not violations_i:
            grade = "I类 (一级, 自然保护区)"
        elif not violations_ii:
            grade = "II类 (二级, 居住/商业/工业区)"
        else:
            grade = f"超II类 (超标因子: {', '.join(violations_ii)})"

        return TabularResult(
            task="air_quality_classification",
            prediction=grade,
            confidence=1.0,
            reasoning=f"I类超标: {violations_i if violations_i else '无'}. "
                      f"II类超标: {violations_ii if violations_ii else '无'}",
            method="rule_based",
            raw_data=active_params,
        )

    def classify_noise_level(self, daytime_db: float = 0,
                              night_db: float = 0) -> TabularResult:
        """Classify noise level per GB3096-2008."""
        if daytime_db == 0 and night_db == 0:
            return TabularResult(task="noise_classification",
                                  prediction="无数据", confidence=0.0,
                                  reasoning="未提供噪声数据", method="rule_based")

        for cls_name, limits in self.NOISE_STANDARDS.items():
            day_ok = daytime_db <= limits["day"] if daytime_db > 0 else True
            night_ok = night_db <= limits["night"] if night_db > 0 else True
            if day_ok and night_ok:
                return TabularResult(
                    task="noise_classification",
                    prediction=f"{cls_name}类 ({limits['desc']})",
                    confidence=1.0,
                    reasoning=f"昼间{daytime_db}dB≤{limits['day']}dB, "
                              f"夜间{night_db}dB≤{limits['night']}dB",
                    method="rule_based",
                    raw_data={"day": daytime_db, "night": night_db},
                )

        return TabularResult(
            task="noise_classification",
            prediction="超4b类 (超标)",
            confidence=1.0,
            reasoning=f"昼间{daytime_db}dB>70dB 或 夜间{night_db}dB>60dB",
            method="rule_based",
        )

    def detect_outliers(self, values: list[float],
                         method: str = "iqr") -> list[dict]:
        """Detect outliers using IQR method (no ML deps).
        
        Returns list of {"index": i, "value": v, "is_outlier": bool, "severity": str}
        """
        if len(values) < 4:
            return [{"index": i, "value": v, "is_outlier": False, "severity": "normal"}
                    for i, v in enumerate(values)]

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1

        if iqr == 0:
            return [{"index": i, "value": v, "is_outlier": False, "severity": "normal"}
                    for i, v in enumerate(values)]

        mild_low = q1 - 1.5 * iqr
        mild_high = q3 + 1.5 * iqr
        extreme_low = q1 - 3 * iqr
        extreme_high = q3 + 3 * iqr

        results = []
        for i, v in enumerate(values):
            if v < extreme_low or v > extreme_high:
                results.append({"index": i, "value": v, "is_outlier": True,
                                "severity": "extreme"})
            elif v < mild_low or v > mild_high:
                results.append({"index": i, "value": v, "is_outlier": True,
                                "severity": "mild"})
            else:
                results.append({"index": i, "value": v, "is_outlier": False,
                                "severity": "normal"})
        return results

    def impute_missing(self, values: list[float]) -> list[float]:
        """Impute missing (None/NaN) values with median.
        
        Falls back to 0 if all values are missing.
        """
        valid = [v for v in values if v is not None]
        if not valid:
            return [0.0] * len(values)
        median = sorted(valid)[len(valid) // 2]
        return [v if v is not None else median for v in values]

    # ── LLM-based in-context reasoning ──

    async def reason_tabular(self, task: str, data: dict[str, Any],
                              examples: list[dict] | None = None,
                              perspectives: int = 3) -> TabularResult:
        """TabPFN-style in-context tabular reasoning via LLM.

        Provides synthetic examples + real data in one prompt.
        No training, no preprocessing — LLM as the tabular foundation model.

        Args:
            task: "classify_water_quality" | "classify_air_quality" | custom
            data: {param: value} dict
            examples: Optional list of solved examples (uses built-in defaults if None)
            perspectives: How many angles to analyze from (ensembling)
        """
        if not self.consciousness:
            return self._fallback_reasoning(task, data)

        if examples is None:
            examples = self._get_default_examples(task)

        prompt = self._build_reasoning_prompt(task, data, examples, perspectives)

        try:
            if hasattr(self.consciousness, 'query'):
                response = await self.consciousness.query(prompt, max_tokens=1024,
                                                            temperature=0.3)
            elif hasattr(self.consciousness, 'chain_of_thought'):
                response = await self.consciousness.chain_of_thought(
                    prompt, steps=2, max_tokens=1024, temperature=0.3)
            else:
                return self._fallback_reasoning(task, data)

            return self._parse_llm_result(task, response, data)
        except Exception:
            return self._fallback_reasoning(task, data)

    def _build_reasoning_prompt(self, task: str, data: dict[str, Any],
                                 examples: list[dict],
                                 perspectives: int) -> str:
        task_descriptions = {
            "classify_water_quality": "根据提供的水质参数(COD/BOD/DO/NH3-N)，判定地表水环境质量等级(I-V类)",
            "classify_air_quality": "根据提供的空气质量参数(SO2/NO2/PM10/PM2.5)，判定环境空气质量等级",
            "classify_noise": "根据提供的噪声监测值，判定声环境功能区类别",
            "predict_pollutant": "根据源强和气象条件，预测污染物浓度",
            "detect_anomaly": "分析监测数据，识别异常值和可疑数据点",
        }

        task_desc = task_descriptions.get(task, f"分析以下表格数据: {task}")
        data_str = json.dumps(data, ensure_ascii=False, indent=2)

        example_block = ""
        if examples:
            example_block = "=== 示例 (同类型任务的标准解法) ===\n"
            for i, ex in enumerate(examples, 1):
                example_block += (
                    f"示例{i}:\n"
                    f"  输入: {json.dumps(ex.get('input', {}), ensure_ascii=False)}\n"
                    f"  输出: {ex.get('output', '')}\n"
                    f"  推理: {ex.get('reasoning', '')}\n\n"
                )

        return (
            f"[TabularReasoner] 表格数据推理任务\n\n"
            f"任务: {task_desc}\n\n"
            f"{example_block}"
            f"=== 当前数据 ===\n"
            f"{data_str}\n\n"
            f"=== 要求 ===\n"
            f"从{perspectives}个角度分析:\n"
            f"1. 统计角度: 数值与标准限值的对比\n"
            f"2. 领域角度: 环境工程/环评专业的判断\n"
            f"3. 模式角度: 各参数之间的关联模式\n\n"
            f"输出JSON格式:\n"
            f'{{"prediction": "最终判定结果", "confidence": 0.0-1.0, '
            f'"reasoning": "推理过程", '
            f'"alternatives": [{{"grade": "替代判定", "reason": "理由"}}]}}'
        )

    def _get_default_examples(self, task: str) -> list[dict]:
        if task == "classify_water_quality":
            return [self.WATER_QUALITY_EXAMPLE]
        if task == "classify_air_quality":
            return [self.AIR_QUALITY_EXAMPLE]
        return []

    def _fallback_reasoning(self, task: str, data: dict[str, Any]) -> TabularResult:
        if task == "classify_water_quality":
            return self.classify_water_quality(**data)
        if task == "classify_air_quality":
            return self.classify_air_quality(**data)
        return TabularResult(
            task=task, prediction="未判定",
            confidence=0.0,
            reasoning=f"无LLM可用且无可回退规则, 数据: {data}",
            method="fallback",
        )

    @staticmethod
    def _parse_llm_result(task: str, response: str,
                           data: dict) -> TabularResult:
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            if "```json" in response:
                try:
                    start = response.index("```json") + 7
                    end = response.index("```", start)
                    result = json.loads(response[start:end])
                except (ValueError, json.JSONDecodeError):
                    return TabularResult(
                        task=task, prediction=response[:100],
                        confidence=0.5, reasoning=response[:300],
                        method="llm_raw", raw_data=data,
                    )
            else:
                return TabularResult(
                    task=task, prediction=response[:100],
                    confidence=0.5, reasoning=response[:300],
                    method="llm_raw", raw_data=data,
                )
        return TabularResult(
            task=task,
            prediction=result.get("prediction", ""),
            confidence=result.get("confidence", 0.7),
            reasoning=result.get("reasoning", ""),
            method="llm",
            alternatives=result.get("alternatives", []),
            raw_data=data,
        )

    # ── Multi-view ensembling ──

    async def ensemble_reasoning(self, task: str, data: dict[str, Any]) -> TabularResult:
        """TabPFN-style multi-perspective ensembling.

        Runs both rule-based and LLM reasoning, then combines results.
        Rule-based gives precision (exact standard limits).
        LLM gives nuance (handles edge cases, partial compliance).
        """
        rule_result = self._fallback_reasoning(task, data)

        if self.consciousness:
            llm_result = await self.reason_tabular(task, data)
            alternatives = llm_result.alternatives or []
            if rule_result.prediction not in [llm_result.prediction] + [
                a.get("grade", "") for a in alternatives
            ]:
                alternatives.append({
                    "grade": rule_result.prediction,
                    "reason": f"规则判定: {rule_result.reasoning[:100]}",
                })

            combined_confidence = max(rule_result.confidence, llm_result.confidence)
            return TabularResult(
                task=task,
                prediction=llm_result.prediction,
                confidence=combined_confidence,
                reasoning=f"[LLM] {llm_result.reasoning[:200]} | "
                          f"[规则] {rule_result.reasoning[:200]}",
                method="ensemble",
                alternatives=alternatives,
                raw_data=data,
            )

        return rule_result


_tabular_reasoner: TabularReasoner | None = None


def get_tabular_reasoner(consciousness=None) -> TabularReasoner:
    global _tabular_reasoner
    if _tabular_reasoner is None:
        _tabular_reasoner = TabularReasoner(consciousness)
    elif consciousness and _tabular_reasoner.consciousness is None:
        _tabular_reasoner.consciousness = consciousness
    return _tabular_reasoner
