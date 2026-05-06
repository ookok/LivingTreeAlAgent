"""PromptVersioning — Langfuse-style prompt template version management.

Features:
1. PromptTemplate versioning with auto-increment
2. Change tracking and rollback
3. A/B testing support
4. Usage tracking and performance reports
5. Built-in default templates

Usage:
    from livingtree.treellm.prompt_versioning import PROMPT_VERSION_MANAGER
    mgr = PROMPT_VERSION_MANAGER
    tmpl = mgr.register("summary", "Summarize: {text}")
    latest = mgr.get("summary")
    mgr.rollback("summary", 2)
"""
from __future__ import annotations

import json
import time
import difflib
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

PROMPTS_DIR = Path(".livingtree/prompts")
TEMPLATES_FILE = PROMPTS_DIR / "templates.json"
AB_TESTS_FILE = PROMPTS_DIR / "ab_tests.json"
USAGE_LOG = PROMPTS_DIR / "usage.jsonl"


class PromptTemplate(BaseModel):
    id: str
    name: str
    version: int
    content: str
    system_prompt: str = ""
    model_hints: list[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    tags: list[str] = Field(default_factory=list)
    created_at: float = 0.0
    created_by: str = "system"
    changelog: str = ""
    status: str = "active"  # active, archived, deprecated
    # New contextual fields inspired by mattpocock/skills pattern
    goal: str = ""
    constraints: list[str] = Field(default_factory=list)
    domain_terms: list[str] = Field(default_factory=list)


class ABTest(BaseModel):
    id: str
    name_a: str
    version_a: int
    name_b: str
    version_b: int
    metric: str = "quality"
    results_a: list[dict] = Field(default_factory=list)
    results_b: list[dict] = Field(default_factory=list)
    started_at: float = 0.0


class PromptVersionManager:
    """Manages prompt template versions, A/B tests, and usage tracking."""

    def __init__(self):
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        self._templates: list[dict] = []
        self._ab_tests: dict[str, dict] = {}
        self._load_templates()
        self._load_ab_tests()
        self._maybe_seed_defaults()

    # ── Template registration ──

    def register(self, name: str, content: str, goal: str = "", constraints: list[str] | None = None, domain_terms: list[str] | None = None, **kwargs) -> PromptTemplate:
        """Register a new version of a prompt template.
        Supports structured context: goal, constraints, domain_terms.
        """
        existing = [t for t in self._templates if t["name"] == name]
        version = max((t["version"] for t in existing), default=0) + 1
        tmpl = PromptTemplate(
            id=f"{name}-v{version}",
            name=name,
            version=version,
            content=content,
            goal=goal or "",
            constraints=(constraints or []) ,
            domain_terms=(domain_terms or []),
            created_at=time.time(),
            **kwargs,
        )
        self._templates.append(tmpl.model_dump())
        self._save_templates()
        logger.info(f"Registered {tmpl.id}")
        return tmpl

    def get(self, name: str, version: int | None = None) -> PromptTemplate | None:
        """Get a prompt template. version=None returns latest active."""
        candidates = [t for t in self._templates if t["name"] == name and t["status"] != "deprecated"]
        if not candidates:
            return None
        if version is not None:
            for t in candidates:
                if t["version"] == version:
                    return PromptTemplate(**t)
            return None
        latest = max(candidates, key=lambda t: t["version"])
        return PromptTemplate(**latest)

    def get_prompt_with_context(self, name: str) -> str:
        """Render a full prompt with its context (goal, constraints, domain terms) for agent use.
        The sections are included only if non-empty.
        """
        tmpl = self.get(name)
        if tmpl is None:
            return ""
        parts = []
        if tmpl.goal:
            parts.append("## Goal\n" + tmpl.goal + "\n")
        if tmpl.constraints:
            parts.append("## Constraints\n" + "\n".join([f"- {c}" for c in tmpl.constraints]) + "\n")
        # Prompt content
        parts.append("## Prompt\n" + tmpl.content + "\n")
        if tmpl.domain_terms:
            lines = [f"- {d}: check glossary for definition" for d in tmpl.domain_terms]
            parts.append("## Relevant Domain Terms\n" + "\n".join(lines) + "\n")
        return "\n".join(parts).rstrip() + "\n"

    def update_template_context(self, name: str, version: int, goal: str | None = None, constraints: list[str] | None = None, domain_terms: list[str] | None = None) -> bool:
        """Update the contextual fields for an existing template if version matches.
        Returns True on success, False if not found or version mismatch.
        """
        for t in self._templates:
            if t["name"] == name and t["version"] == version:
                if goal is not None:
                    t["goal"] = goal
                if constraints is not None:
                    t["constraints"] = constraints
                if domain_terms is not None:
                    t["domain_terms"] = domain_terms
                self._save_templates()
                return True
        return False

    def list_versions(self, name: str) -> list[PromptTemplate]:
        """List all versions of a template."""
        versions = [t for t in self._templates if t["name"] == name]
        versions.sort(key=lambda t: t["version"])
        return [PromptTemplate(**t) for t in versions]

    def deprecate(self, name: str, version: int) -> bool:
        """Mark a version as deprecated."""
        for t in self._templates:
            if t["name"] == name and t["version"] == version:
                t["status"] = "deprecated"
                self._save_templates()
                return True
        return False

    def rollback(self, name: str, target_version: int) -> bool:
        """Rollback: set target_version as active, archive newer versions."""
        found = False
        for t in self._templates:
            if t["name"] == name:
                if t["version"] == target_version:
                    t["status"] = "active"
                    found = True
                elif t["version"] > target_version and t["status"] == "active":
                    t["status"] = "archived"
        if found:
            self._save_templates()
        return found

    def diff(self, name: str, v1: int, v2: int) -> str:
        """Return unified diff between two versions."""
        t1 = t2 = None
        for t in self._templates:
            if t["name"] == name and t["version"] == v1:
                t1 = t
            if t["name"] == name and t["version"] == v2:
                t2 = t
        if not t1 or not t2:
            return "Version not found"
        diff = difflib.unified_diff(
            t1["content"].splitlines(keepends=True),
            t2["content"].splitlines(keepends=True),
            fromfile=f"{name}-v{v1}",
            tofile=f"{name}-v{v2}",
        )
        return "".join(diff) or "No differences"

    def set_system_prompt(self, name: str, version: int, system_prompt: str) -> bool:
        for t in self._templates:
            if t["name"] == name and t["version"] == version:
                t["system_prompt"] = system_prompt
                self._save_templates()
                return True
        return False

    def add_tag(self, name: str, version: int, tag: str) -> bool:
        for t in self._templates:
            if t["name"] == name and t["version"] == version:
                if tag not in t["tags"]:
                    t["tags"].append(tag)
                self._save_templates()
                return True
        return False

    def remove_tag(self, name: str, version: int, tag: str) -> bool:
        for t in self._templates:
            if t["name"] == name and t["version"] == version:
                t["tags"] = [x for x in t["tags"] if x != tag]
                self._save_templates()
                return True
        return False

    def search(self, tags: list[str] | None = None) -> list[PromptTemplate]:
        """Search templates, optionally filtering by tags (AND match)."""
        results = self._templates
        if tags:
            results = [t for t in results if all(tag in t["tags"] for tag in tags)]
        return [PromptTemplate(**t) for t in results]

    # ── A/B Testing ──

    def start_ab(self, name_a: str, version_a: int, name_b: str, version_b: int,
                 metric: str = "quality") -> str:
        import uuid
        ab_id = f"ab_{uuid.uuid4().hex[:8]}"
        ab = ABTest(
            id=ab_id, name_a=name_a, version_a=version_a,
            name_b=name_b, version_b=version_b, metric=metric,
            started_at=time.time(),
        )
        self._ab_tests[ab_id] = ab.model_dump()
        self._save_ab_tests()
        return ab_id

    def record_ab_result(self, ab_test_id: str, variant: str,
                         score: float, tokens: int, latency_ms: float):
        ab = self._ab_tests.get(ab_test_id)
        if not ab:
            return
        entry = {"score": score, "tokens": tokens, "latency_ms": latency_ms, "timestamp": time.time()}
        if variant == "A":
            ab["results_a"].append(entry)
        elif variant == "B":
            ab["results_b"].append(entry)
        self._save_ab_tests()

    def get_ab_results(self, ab_test_id: str) -> dict:
        ab = self._ab_tests.get(ab_test_id)
        if not ab:
            return {"error": "A/B test not found"}
        def _stats(results_list):
            if not results_list:
                return {"count": 0, "avg_score": 0, "avg_tokens": 0, "avg_latency_ms": 0}
            return {
                "count": len(results_list),
                "avg_score": round(sum(r["score"] for r in results_list) / len(results_list), 3),
                "avg_tokens": round(sum(r["tokens"] for r in results_list) / len(results_list), 1),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in results_list) / len(results_list), 1),
            }
        stats_a = _stats(ab["results_a"])
        stats_b = _stats(ab["results_b"])
        winner = "A" if stats_a["avg_score"] > stats_b["avg_score"] else "B"
        if stats_a["avg_score"] == stats_b["avg_score"]:
            winner = "A" if stats_a["avg_latency_ms"] <= stats_b["avg_latency_ms"] else "B"
        return {"ab_id": ab_test_id, "metric": ab["metric"], "variant_a": stats_a, "variant_b": stats_b, "winner": winner}

    # ── Usage tracking ──

    def record_usage(self, template_id: str, model: str, tokens_in: int,
                     tokens_out: int, latency_ms: float, score: float | None = None):
        entry = {
            "template_id": template_id, "model": model,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "latency_ms": latency_ms, "score": score,
            "timestamp": time.time(),
        }
        with open(USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_usage_stats(self, template_id: str, days: int = 7) -> dict:
        cutoff = time.time() - days * 86400
        entries = []
        if USAGE_LOG.exists():
            for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    if d.get("template_id") == template_id and d.get("timestamp", 0) >= cutoff:
                        entries.append(d)
                except Exception:
                    pass
        if not entries:
            return {"count": 0}
        by_model: dict[str, dict] = {}
        for e in entries:
            m = by_model.setdefault(e["model"], {"count": 0, "total_tokens": 0, "total_latency_ms": 0, "scores": []})
            m["count"] += 1
            m["total_tokens"] += e["tokens_in"] + e["tokens_out"]
            m["total_latency_ms"] += e["latency_ms"]
            if e.get("score") is not None:
                m["scores"].append(e["score"])
        for m in by_model.values():
            m["avg_latency_ms"] = round(m["total_latency_ms"] / m["count"], 1)
            m["avg_score"] = round(sum(m["scores"]) / len(m["scores"]), 3) if m["scores"] else None
            del m["scores"]
            del m["total_latency_ms"]
        return {"count": len(entries), "by_model": by_model}

    def get_performance_report(self, template_id: str) -> dict:
        entries = []
        if USAGE_LOG.exists():
            for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    if d.get("template_id") == template_id:
                        entries.append(d)
                except Exception:
                    pass
        if not entries:
            return {"count": 0}
        by_model: dict[str, dict] = {}
        for e in entries:
            m = by_model.setdefault(e["model"], {"count": 0, "avg_tokens_in": 0, "avg_tokens_out": 0,
                                                  "avg_latency_ms": 0, "total_scores": 0, "score_count": 0})
            m["count"] += 1
            m["avg_tokens_in"] += e["tokens_in"]
            m["avg_tokens_out"] += e["tokens_out"]
            m["avg_latency_ms"] += e["latency_ms"]
            if e.get("score") is not None:
                m["total_scores"] += e["score"]
                m["score_count"] += 1
        for m in by_model.values():
            n = m["count"]
            m["avg_tokens_in"] = round(m["avg_tokens_in"] / n)
            m["avg_tokens_out"] = round(m["avg_tokens_out"] / n)
            m["avg_latency_ms"] = round(m["avg_latency_ms"] / n, 1)
            m["avg_score"] = round(m["total_scores"] / m["score_count"], 3) if m["score_count"] else None
            del m["total_scores"]
            del m["score_count"]
        return {"template_id": template_id, "total_calls": len(entries), "by_model": by_model}

    # ── Default templates ──

    def _maybe_seed_defaults(self):
        if self._templates:
            return
        defaults = [
            # summary
            ("summary", "请对以下内容进行简洁准确的总结：\n\n{content}", "你是一个专业的总结助手。", "Generate a concise, accurate summary of the given content", ["Keep under 200 words", "No new information"], ["summary", "concise"]),
            # code-review
            ("code-review", "请审查以下代码，指出潜在问题和改进建议：\n\n{code}", "你是一个资深代码审查专家。", "Review code for bugs, style issues, and architectural problems", ["Be specific with line numbers", "Suggest concrete fixes"], ["code review", "static analysis", "best practice"]),
            # agent-eval
            ("agent-eval", "请评估以下 Agent 输出的质量（0.0-1.0）：\n任务：{task}\n输出：{output}", "你是一个公正的评估者。", "Evaluate agent output quality objectively on a 0.0-1.0 scale", ["Be consistent", "Justify each score", "Consider safety"], ["evaluation", "quality metrics", "hallucination"]),
            # reasoning
            ("reasoning", "请逐步分析以下问题并给出推理过程：\n\n{question}", "你是一个擅长逻辑推理的助手。请逐步思考。", "Step-by-step logical analysis of a problem", ["Show intermediate steps", "State assumptions"], ["reasoning", "inference", "logic"]),
            # tool-synthesis
            ("tool-synthesis", "请根据以下需求生成一个工具函数：\n需求：{requirement}\n语言：{language}", "你是一个工具函数生成专家。", "Generate a well-typed, production-ready tool function", ["Include error handling", "Add type hints", "Use standard library when possible"], ["tool synthesis", "function generation", "code generation"]),
        ]
        for name, content, system_prompt, goal, constraints, domain_terms in defaults:
            self.register(name, content, goal=goal, constraints=constraints, domain_terms=domain_terms, system_prompt=system_prompt, tags=["builtin"])
        logger.info(f"Seeded {len(defaults)} default prompt templates")

    # ── Persistence ──

    def _save_templates(self):
        TEMPLATES_FILE.write_text(json.dumps(self._templates, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_templates(self):
        if TEMPLATES_FILE.exists():
            try:
                self._templates = json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._templates = []

    def _save_ab_tests(self):
        AB_TESTS_FILE.write_text(json.dumps(self._ab_tests, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_ab_tests(self):
        if AB_TESTS_FILE.exists():
            try:
                self._ab_tests = json.loads(AB_TESTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._ab_tests = {}


PROMPT_VERSION_MANAGER = PromptVersionManager()

# Backwards-compat alias (some imports may expect PROMT_VERSION_MANAGER)
PROMT_VERSION_MANAGER = PROMPT_VERSION_MANAGER
