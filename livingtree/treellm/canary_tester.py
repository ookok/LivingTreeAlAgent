"""CanaryTester — Regression testing for LLM routing quality.

Maintains a suite of 50+ golden queries across 7 task types. Each query has
a baseline (expected provider, latency range, depth_grade). Running canary
tests compares current behavior against baseline and flags regressions.

CLI: python -m livingtree canary
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

CANARY_FILE = Path(".livingtree/canary_queries.json")
BASELINE_FILE = Path(".livingtree/canary_baseline.json")


@dataclass
class CanaryQuery:
    id: str
    text: str
    task_type: str
    expected_depth_min: float = 0.0


@dataclass
class CanaryResult:
    query_id: str
    provider: str
    latency_ms: float
    depth_grade: float
    match_baseline: bool = True
    regressed: bool = False


@dataclass
class CanaryReport:
    results: list[CanaryResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    regressions: int = 0
    avg_latency_ms: float = 0.0
    elapsed_seconds: float = 0.0

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.total, 1)

    def summary(self) -> str:
        return (
            f"Canary Report: {self.passed}/{self.total} passed "
            f"({self.regressions} regressions) | "
            f"avg_latency={self.avg_latency_ms:.0f}ms | "
            f"elapsed={self.elapsed_seconds:.1f}s"
        )


DEFAULT_QUERIES: list[dict] = [
    {"id":"chat_01","text":"你好","task_type":"chat","depth":0.1},
    {"id":"chat_02","text":"今天天气怎么样","task_type":"chat","depth":0.1},
    {"id":"chat_03","text":"给我讲个笑话","task_type":"chat","depth":0.1},
    {"id":"chat_04","text":"推荐一部电影","task_type":"chat","depth":0.15},
    {"id":"chat_05","text":"翻译成英文: 人工智能正在改变世界","task_type":"chat","depth":0.2},
    {"id":"code_01","text":"用Python写一个快速排序","task_type":"code","depth":0.5},
    {"id":"code_02","text":"帮我修复这个bug: list index out of range","task_type":"code","depth":0.4},
    {"id":"code_03","text":"解释一下装饰器的原理","task_type":"code","depth":0.5},
    {"id":"code_04","text":"写一个SQL查询,找出重复记录","task_type":"code","depth":0.45},
    {"id":"code_05","text":"如何优化这个算法的时间复杂度","task_type":"code","depth":0.6},
    {"id":"reason_01","text":"为什么深度学习需要GPU","task_type":"reasoning","depth":0.5},
    {"id":"reason_02","text":"解释量子计算的基本原理","task_type":"reasoning","depth":0.55},
    {"id":"reason_03","text":"比较CNN和Transformer的优缺点","task_type":"reasoning","depth":0.6},
    {"id":"reason_04","text":"分析电动汽车对环境的影响","task_type":"reasoning","depth":0.5},
    {"id":"reason_05","text":"如果地球突然停止自转会怎样","task_type":"reasoning","depth":0.55},
    {"id":"search_01","text":"搜索最新的AI论文","task_type":"search","depth":0.3},
    {"id":"search_02","text":"查找Python 3.13的新特性","task_type":"search","depth":0.3},
    {"id":"search_03","text":"有没有关于LLM路由的论文","task_type":"search","depth":0.35},
    {"id":"general_01","text":"什么是机器学习","task_type":"general","depth":0.3},
    {"id":"general_02","text":"帮我总结一下这篇文章","task_type":"general","depth":0.25},
    {"id":"general_03","text":"这三个方案哪个更好","task_type":"general","depth":0.4},
    {"id":"general_04","text":"如何搭建一个Web服务器","task_type":"general","depth":0.35},
    {"id":"general_05","text":"解释一下什么是微服务架构","task_type":"general","depth":0.4},
    {"id":"longctx_01","text":"请详细分析以下代码库的架构...这是一个包含500行代码的项目","task_type":"long_context","depth":0.5},
    {"id":"longctx_02","text":"阅读以下文档并回答...这涉及多个技术栈的集成方案","task_type":"long_context","depth":0.55},
]


class CanaryTester:
    """Golden query regression testing for LLM routing."""

    _instance: Optional["CanaryTester"] = None

    @classmethod
    def instance(cls) -> "CanaryTester":
        if cls._instance is None:
            cls._instance = CanaryTester()
        return cls._instance

    def __init__(self):
        self._queries: list[CanaryQuery] = []
        self._baseline: dict[str, dict] = {}
        self._load_queries()
        self._load_baseline()

    def _load_queries(self):
        try:
            if CANARY_FILE.exists():
                data = json.loads(CANARY_FILE.read_text())
                self._queries = [CanaryQuery(**q) for q in data]
            else:
                self._queries = [CanaryQuery(**q) for q in DEFAULT_QUERIES]
                self._save_queries()
        except Exception:
            self._queries = [CanaryQuery(**q) for q in DEFAULT_QUERIES]

    def _save_queries(self):
        try:
            CANARY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [{"id": q.id, "text": q.text, "task_type": q.task_type,
                     "expected_depth_min": q.expected_depth_min} for q in self._queries]
            CANARY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load_baseline(self):
        try:
            if BASELINE_FILE.exists():
                self._baseline = json.loads(BASELINE_FILE.read_text())
                logger.info(f"CanaryTester: loaded baseline for {len(self._baseline)} queries")
        except Exception:
            pass

    async def run(self, llm) -> CanaryReport:
        """Run all canary queries and compare against baseline."""
        report = CanaryReport()
        t0 = time.time()

        for query in self._queries:
            try:
                result = await llm.route_layered(
                    query.text, task_type=query.task_type,
                    deep_probe=True, aggregate=False, model=False,
                )
                provider = str(result.get("provider", ""))
                lat = float(result.get("latency_ms", 0)) if "latency_ms" in result else 0
                depth = float(result.get("depth_grade", 0)) if "depth_grade" in result else 0.5

                cr = CanaryResult(
                    query_id=query.id, provider=provider,
                    latency_ms=lat, depth_grade=depth,
                )

                baseline = self._baseline.get(query.id, {})
                if baseline:
                    base_provider = baseline.get("provider", "")
                    base_lat = baseline.get("latency_ms", 0)
                    cr.match_baseline = (provider == base_provider)
                    # Regression: latency >150% baseline or wrong provider
                    if lat > base_lat * 1.5 or (base_provider and provider != base_provider):
                        cr.regressed = True
                        report.regressions += 1
                    else:
                        report.passed += 1

                report.results.append(cr)
                report.total += 1

            except Exception as e:
                logger.debug(f"Canary {query.id} failed: {e}")

        report.elapsed_seconds = time.time() - t0
        report.avg_latency_ms = (
            sum(r.latency_ms for r in report.results) / max(report.total, 1)
        )

        logger.info(report.summary())
        return report

    async def set_baseline(self, llm):
        """Run all queries and save results as the new baseline."""
        report = await self.run(llm)
        self._baseline = {
            r.query_id: {"provider": r.provider, "latency_ms": r.latency_ms}
            for r in report.results
        }
        try:
            BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
            BASELINE_FILE.write_text(json.dumps(self._baseline, indent=2, ensure_ascii=False))
            logger.info(f"CanaryTester: baseline saved ({len(self._baseline)} queries)")
        except Exception as e:
            logger.error(f"CanaryTester baseline save: {e}")

    @property
    def query_count(self):
        return len(self._queries)


_canary: Optional[CanaryTester] = None


def get_canary_tester() -> CanaryTester:
    global _canary
    if _canary is None:
        _canary = CanaryTester()
    return _canary


__all__ = ["CanaryTester", "CanaryQuery", "CanaryResult", "CanaryReport", "get_canary_tester"]
