"""Sub-Agent Parallel Dispatch Engine — word-trap protected task distribution.

Inspired by Web Access Skill's sub-agent architecture:
  1. Main agent decomposes task → distributes to N sub-agents
  2. Each sub-agent operates independently in parallel
  3. Results flow back as summaries (NOT full context)
  4. Word-trap protection: main agent's prompt to sub-agent is sanitized

Key innovations:
  - Word-trap guard: strips tool-presupposing language from sub-prompts
  - Context budget: each sub-agent capped at N tokens, only summary returned
  - Experience recording: sub-agent operations auto-saved per domain
  - Parallel Chrome tabs: multiple sub-agents share one browser session
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Word-Trap Protection ═══

# Words that unconsciously constrain sub-agent tool choice
TRAP_WORDS = {
    "搜索": "调研",
    "search": "investigate",
    "fetch": "access",
    "抓取": "获取",
    "查找": "了解",
    "找到": "发现",
    "爬取": "收集",
    "打开链接": "访问页面",
    "打开网页": "浏览页面",
    "打开": "查看",
    "读取网页": "浏览内容",
}

# Neutral task verbs that don't presuppose tools
NEUTRAL_VERBS = [
    "调研", "了解", "分析", "查看", "获取", "收集",
    "汇总", "整理", "核实", "确认", "评估",
    "investigate", "research", "analyze", "review",
    "gather", "collect", "verify", "assess", "explore",
]


@dataclass
class SubTask:
    """A task dispatched to a sub-agent."""
    id: str
    target: str           # URL or platform or search topic
    task_description: str  # neutral-language task description
    priority: int = 0
    max_tabs: int = 5      # max concurrent tabs/pages


@dataclass
class SubAgentResult:
    """Result returned from a sub-agent (summary only, not full context)."""
    task_id: str
    target: str
    status: str           # "done", "partial", "failed"
    summary: str           # concise summary (max 500 chars)
    key_findings: list[str] = field(default_factory=list)
    pages_visited: int = 0
    elapsed_ms: float = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class DispatchReport:
    """Aggregated report from all sub-agents."""
    main_task: str
    sub_tasks: int
    completed: int
    failed: int
    total_pages_visited: int
    results: list[SubAgentResult] = field(default_factory=list)
    merged_summary: str = ""
    elapsed_ms: float = 0


class SubAgentDispatch:
    """Word-trap protected parallel task dispatch engine.

    Usage:
        dispatch = SubAgentDispatch()
        tasks = dispatch.decompose(
            "调研10个平台首页趋势",
            platforms=["小红书", "微博", "B站", "知乎", "GitHub"],
        )
        report = await dispatch.execute(tasks, hub=hub)
        print(report.merged_summary)
    """

    def __init__(self, max_parallel: int = 10, tab_limit_per_agent: int = 10):
        self._max_parallel = max_parallel
        self._tab_limit = tab_limit_per_agent

    def decompose(
        self,
        main_task: str,
        platforms: list[str] = None,
        urls: list[str] = None,
        search_queries: list[str] = None,
    ) -> list[SubTask]:
        """Decompose a main task into neutral-language sub-tasks.

        Word-trap protection: strips tool-presupposing language.
        """
        tasks = []
        idx = 0

        # URL-based tasks
        if urls:
            for url in urls[:self._max_parallel]:
                domain = self._extract_domain(url)
                tasks.append(SubTask(
                    id=f"sub_{idx}",
                    target=url,
                    task_description=self._neutralize(
                        f"访问 {domain} 并获取页面主要内容"
                    ),
                    priority=1,
                    max_tabs=3,
                ))
                idx += 1

        # Platform-based tasks (e.g. "调研小红书首页趋势")
        if platforms:
            for platform in platforms[:self._max_parallel]:
                tasks.append(SubTask(
                    id=f"sub_{idx}",
                    target=platform,
                    task_description=self._neutralize(
                        f"调研 {platform} 的当前内容和趋势"
                    ),
                    priority=0,
                    max_tabs=self._tab_limit,
                ))
                idx += 1

        # Search query tasks
        if search_queries:
            for query in search_queries[:self._max_parallel]:
                tasks.append(SubTask(
                    id=f"sub_{idx}",
                    target=query,
                    task_description=self._neutralize(
                        f"收集关于 {query} 的最新信息"
                    ),
                    priority=2,
                    max_tabs=5,
                ))
                idx += 1

        tasks.sort(key=lambda t: t.priority)
        return tasks[:self._max_parallel]

    async def execute(
        self,
        tasks: list[SubTask],
        hub: Any = None,
        fetch_fn: callable = None,
    ) -> DispatchReport:
        """Execute all sub-tasks in parallel, returning only summaries."""
        start = time.time()

        sem = asyncio.Semaphore(self._max_parallel)

        async def run_one(task: SubTask) -> SubAgentResult:
            async with sem:
                return await self._execute_single(task, hub, fetch_fn)

        results = await asyncio.gather(*[run_one(t) for t in tasks], return_exceptions=True)

        # Process results
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                valid_results.append(SubAgentResult(
                    task_id="error", target="unknown",
                    status="failed", summary="", errors=[str(r)],
                ))
            else:
                valid_results.append(r)

        completed = sum(1 for r in valid_results if r.status == "done")
        failed = sum(1 for r in valid_results if r.status == "failed")
        total_pages = sum(r.pages_visited for r in valid_results)

        merged = self._merge_summaries(valid_results)

        report = DispatchReport(
            main_task=f"{len(tasks)} sub-tasks",
            sub_tasks=len(tasks),
            completed=completed,
            failed=failed,
            total_pages_visited=total_pages,
            results=valid_results,
            merged_summary=merged,
            elapsed_ms=(time.time() - start) * 1000,
        )

        logger.info(
            "SubAgentDispatch: %d/%d done, %d pages, %.0fms",
            completed, len(tasks), total_pages, report.elapsed_ms,
        )
        return report

    async def _execute_single(
        self, task: SubTask, hub: Any, fetch_fn: callable,
    ) -> SubAgentResult:
        """Execute one sub-task."""
        t0 = time.time()
        result = SubAgentResult(
            task_id=task.id, target=task.target, status="partial",
        )

        try:
            # If fetch_fn provided, use it for actual fetching
            if fetch_fn and task.target.startswith("http"):
                content = await fetch_fn(task.target)
                if content:
                    result.pages_visited = 1
                    result.summary = content[:500] if isinstance(content, str) else str(content)[:500]
                    result.status = "done"

            # If hub available, use LLM to summarize
            elif hub and task.target:
                prompt = (
                    f"Briefly summarize what you know about this (2-3 sentences):\n"
                    f"Task: {task.task_description}\nTarget: {task.target}"
                )
                try:
                    response = hub.chat(prompt)
                    if response:
                        result.summary = response[:500]
                        result.status = "done"
                except Exception:
                    result.summary = f"[{task.target}] — 未能获取信息"
                    result.status = "partial"
            else:
                result.summary = f"[{task.target}] — 待采集"
                result.status = "partial"

        except Exception as e:
            result.errors.append(str(e))
            result.status = "failed"

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    @staticmethod
    def _merge_summaries(results: list[SubAgentResult]) -> str:
        """Merge sub-agent summaries into a concise report."""
        if not results:
            return "无结果"

        lines = ["# 并行调研汇总"]
        for r in results:
            icon = {"done": "✅", "partial": "⚠️", "failed": "❌"}[r.status]
            lines.append(f"\n{icon} **{r.target[:60]}** ({r.pages_visited}页)")
            if r.summary:
                lines.append(f"  {r.summary[:300]}")
            if r.key_findings:
                for f in r.key_findings[:3]:
                    lines.append(f"  - {f}")

        return "\n".join(lines)

    @staticmethod
    def _neutralize(text: str) -> str:
        """Replace trap words with neutral alternatives."""
        for trap, neutral in TRAP_WORDS.items():
            if trap in text:
                text = text.replace(trap, neutral)
        return text

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url[:50]


# ═══ Site Experience Recorder ═══

class SiteExperienceRecorder:
    """Auto-record site operation experiences per domain.

    After each successful browser operation on a site, records:
      - URL patterns that work
      - Login requirements
      - Anti-crawl characteristics
      - Best access path

    Stored per-domain as markdown files in ~/.livingtree/site_experiences/
    """

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree/site_experiences")
        os.makedirs(self._data_dir, exist_ok=True)

    def record(
        self, domain: str, operation: str, success: bool,
        details: str = "", url_pattern: str = "",
    ) -> None:
        """Record an operation experience for a domain."""
        filename = os.path.join(self._data_dir, f"{domain.replace('.', '_')}.md")
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            "operation": operation,
            "success": success,
            "details": details,
            "url_pattern": url_pattern,
        }

        existing = []
        if os.path.exists(filename):
            try:
                with open(filename, encoding="utf-8") as f:
                    existing = json.load(f) if f.read().strip().startswith("[") else []
            except Exception:
                pass

        existing.append(entry)
        # Keep last 50 entries
        existing = existing[-50:]

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def get_experience(self, domain: str, operation: str = "") -> list[dict]:
        filename = os.path.join(self._data_dir, f"{domain.replace('.', '_')}.md")
        if not os.path.exists(filename):
            return []
        try:
            with open(filename, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                return []
            if operation:
                data = [e for e in data if operation in e.get("operation", "")]
            return data[-20:]
        except Exception:
            return []

    def get_best_path(self, domain: str) -> str:
        """Get the best known access path for a domain."""
        experiences = self.get_experience(domain)
        successful = [e for e in experiences if e.get("success")]
        if not successful:
            successful = experiences

        # Find most common successful patterns
        from collections import Counter
        patterns = Counter(e.get("url_pattern", "") for e in successful if e.get("url_pattern"))
        best = patterns.most_common(1)
        if best:
            return best[0][0]

        # Fallback: most recent successful
        for e in reversed(successful):
            if e.get("details"):
                return e["details"][:200]

        return ""

    def get_stats(self) -> dict:
        try:
            files = [f for f in os.listdir(self._data_dir) if f.endswith(".md")]
            total_entries = 0
            for f in files:
                try:
                    with open(os.path.join(self._data_dir, f), encoding="utf-8") as fh:
                        data = json.load(fh)
                        total_entries += len(data) if isinstance(data, list) else 0
                except Exception:
                    pass
            return {"domains": len(files), "total_entries": total_entries}
        except Exception:
            return {"domains": 0, "total_entries": 0}


# ═══ Singleton ═══

_dispatch: Optional[SubAgentDispatch] = None
_recorder: Optional[SiteExperienceRecorder] = None


def get_dispatch() -> SubAgentDispatch:
    global _dispatch
    if _dispatch is None:
        _dispatch = SubAgentDispatch()
    return _dispatch

def get_experience_recorder() -> SiteExperienceRecorder:
    global _recorder
    if _recorder is None:
        _recorder = SiteExperienceRecorder()
    return _recorder
