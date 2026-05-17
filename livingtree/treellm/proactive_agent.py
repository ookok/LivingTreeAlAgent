"""Proactive Agent — morning brief, learning journal, task planning, semantic autocomplete.

Four innovations built on existing capabilities:
  1. morning_brief()    — startup report (git changes, open PRs, test status, health)
  2. learn_from_fix()   — auto-save root cause → fix → verification to KB
  3. plan_task(query)   — confirm-before-execute multi-step planning
  4. suggest_code(query)— context-aware code hinting
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from loguru import logger

LEARNING_DB = Path(".livingtree/learning_journal.json")


# ═══ 1. Morning Brief ═══

async def morning_brief(tree_llm=None) -> str:
    """Generate a startup brief: what changed, what's broken, what needs attention."""
    lines = ["🌅 Morning Brief", f"{'='*40}", ""]

    # Git status
    try:
        from livingtree.treellm.unified_exec import run_sync
        r = run_sync("git log --oneline --since='24 hours ago'", timeout=10)
        commits = r.stdout.strip()
        lines.append(f"📝 Recent commits (24h):")
        lines.append(commits[:500] if commits else "  (none)")
    except Exception:
        lines.append("📝 Git: unavailable")

    # Git diff stat
    try:
        from livingtree.treellm.unified_exec import run_sync
        r = run_sync("git diff --stat HEAD~5", timeout=10)
        lines.append(f"\n📊 Changes (last 5 commits):\n{r.stdout[:500]}")
    except Exception:
        pass

    # Open PRs
    try:
        from livingtree.treellm.unified_exec import run_sync
        r = run_sync("gh pr list --state open --limit 5 --json number,title,author", timeout=15)
        if r.success and r.stdout.strip():
            data = json.loads(r.stdout)
            lines.append(f"\n🔀 Open PRs ({len(data)}):")
            for pr in data[:5]:
                lines.append(f"  #{pr['number']} {pr['title'][:60]} — {pr['author']}")
    except Exception:
        pass

    # Test status
    try:
        from livingtree.treellm.unified_exec import run_sync
        r = run_sync("python -m pytest tests/ -q --tb=no 2>&1 | tail -3", timeout=60)
        lines.append(f"\n🧪 Tests:\n{r.stdout[:300] or '(none)'}")
    except Exception:
        lines.append("\n🧪 Tests: skipped")

    # System health
    try:
        if tree_llm:
            alive = [p for p in tree_llm._providers if p not in getattr(tree_llm, '_dead_providers', set())]
            dead = list(getattr(tree_llm, '_dead_providers', set()))
            lines.append(f"\n🫀 Health: {len(alive)} providers alive")
            if dead:
                lines.append(f"  Dead: {', '.join(dead)}")
    except Exception:
        pass

    # AI summary via L1
    brief_text = "\n".join(lines)
    if tree_llm:
        try:
            summary_prompt = (
                f"Summarize this morning brief in 1-2 sentences. "
                f"Highlight what needs attention.\n\n{brief_text[:2000]}"
            )
            resp = await tree_llm.chat(
                [{"role": "user", "content": summary_prompt}],
                max_tokens=200, temperature=0.3,
                enable_coach=False, enable_onto=False,
            )
            if resp and hasattr(resp, 'text') and resp.text:
                brief_text += f"\n\n💡 {resp.text.strip()}"
        except Exception:
            pass

    return brief_text


# ═══ 2. Learning Journal ═══

def learn_from_fix(problem: str, root_cause: str, fix: str, verification: str,
                   tags: str = "") -> str:
    """Record a fix to the learning journal. LLM retrieves for future similar issues."""
    entry = {
        "time": time.time(),
        "problem": problem[:500],
        "root_cause": root_cause[:500],
        "fix": fix[:1000],
        "verification": verification[:300],
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "embedding": None,  # Filled by vector store on index
    }

    entries = _load_journal()
    entries.append(entry)
    _save_journal(entries)

    try:
        from livingtree.knowledge.vector_store import VectorStore
        store = VectorStore()
        text = f"{problem} {root_cause} {fix}"
        vec = store.embed(text)
        store.add_vectors([(f"learn:{len(entries)}", vec)])
    except Exception:
        pass

    return f"Learning recorded: {len(entries)} entries total. Tags: {tags or 'none'}"


def find_similar_problem(query: str, top_k: int = 3) -> str:
    """Find similar past problems in the learning journal."""
    entries = _load_journal()
    if not entries:
        return "No learning entries yet."

    try:
        from livingtree.knowledge.vector_store import VectorStore
        store = VectorStore()
        q_vec = store.embed(query)
        # Brute-force cosine for small dataset
        scores = []
        for i, e in enumerate(entries):
            e_text = f"{e.get('problem','')} {e.get('root_cause','')}"
            e_vec = store.embed(e_text) if hasattr(store, 'embed') else None
            if e_vec and q_vec:
                sim = sum(a * b for a, b in zip(q_vec, e_vec))
                scores.append((i, sim))
        scores.sort(key=lambda x: -x[1])

        results = []
        for idx, score in scores[:top_k]:
            if score > 0.5:
                e = entries[idx]
                results.append(
                    f"Problem: {e['problem'][:100]}\n"
                    f"Fix: {e['fix'][:200]}\n"
                    f"Verification: {e['verification'][:100]}"
                )
        return "\n\n".join(results) if results else "No similar problems found."
    except Exception:
        # Keyword fallback
        results = []
        for e in entries:
            if query.lower() in e.get("problem", "").lower():
                results.append(f"Fix: {e['fix'][:200]}")
        return "\n\n".join(results[:3]) if results else "No similar problems found."


def list_learnings(limit: int = 10) -> str:
    """List recent learning entries."""
    entries = _load_journal()[-limit:]
    if not entries:
        return "No learning entries yet."
    lines = []
    for i, e in enumerate(reversed(entries)):
        tags = ", ".join(e.get("tags", []))
        lines.append(
            f"{i+1}. [{tags}] {e['problem'][:80]}\n"
            f"   Fix: {e['fix'][:120]}"
        )
    return "\n".join(lines)


def _load_journal() -> list[dict]:
    if not LEARNING_DB.exists():
        return []
    try:
        return json.loads(LEARNING_DB.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_journal(entries: list[dict]):
    LEARNING_DB.parent.mkdir(parents=True, exist_ok=True)
    LEARNING_DB.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══ 3. Multi-round Task Planning ═══

async def plan_task(tree_llm, query: str) -> str:
    """Generate a multi-step plan. LLM proposes, human confirms, then executes."""
    plan_prompt = (
        f"You are a planning assistant. Break down this task into clear steps.\n\n"
        f"Task: {query}\n\n"
        f"Output a numbered plan with 2-5 steps. Each step should be concrete and verifiable.\n"
        f"Format:\n"
        f"1. [Step name] — what to do, what tools to use, expected output\n"
        f"2. ...\n\n"
        f"After listing steps, ask: 'Shall I proceed step by step? Reply: go, skip N, or stop.'"
    )

    if tree_llm:
        resp = await tree_llm.chat(
            [{"role": "user", "content": plan_prompt}],
            max_tokens=500, temperature=0.3,
            enable_coach=False, enable_onto=False,
        )
        if resp and hasattr(resp, 'text') and resp.text:
            return "📋 Task Plan\n" + resp.text

    # Fallback heuristic
    code_keywords = ["代码", "函数", "code", "def ", "class ", ".py", "重构", "修复"]
    if any(kw in query.lower() for kw in code_keywords):
        return (
            "📋 Task Plan\n\n"
            f"1. 分析现状 — grep_code / codegraph_callers / read_file\n"
            f"2. 设计方案 — 基于分析结果给出修改方案\n"
            f"3. 实施修改 — write_file / git_commit\n"
            f"4. 验证测试 — run_test\n"
            f"5. 提交代码 — git_push + gh_pr_create\n\n"
            f"Shall I proceed step by step? Reply: go, skip N, or stop."
        )
    return (
        "📋 Task Plan\n\n"
        f"1. 理解需求 — 分析任务，明确目标\n"
        f"2. 执行任务 — 调用需要的工具\n"
        f"3. 验证结果 — 检查输出是否满足要求\n\n"
        f"Shall I proceed? Reply: go, or give more details."
    )


# ═══ 4. Semantic Code Autocomplete ═══

async def suggest_code(tree_llm, partial_query: str) -> str | None:
    """Suggest code completions based on project context. Shows in TUI."""
    # Only trigger for code-like queries
    code_signals = [".py", "def ", "class ", "import ", "重构", "修复", "code", "函数", "模块"]
    if not any(s in partial_query for s in code_signals):
        return None

    if len(partial_query) < 10:
        return None

    try:
        # Search similar code
        from livingtree.capability.semantic_code_search import search_codebase
        results = search_codebase(partial_query, top_k=2)
        if results:
            hints = []
            for r in results[:2]:
                hints.append(f"📁 {r.get('file','')}: {r.get('snippet','')[:100]}")
            return "\n".join(hints)

        # Fallback: function name suggestions
        from livingtree.treellm.codegraph_tools import codegraph_deps
        module_hint = partial_query.split()[-1].strip('"').strip("'")
        if module_hint:
            deps = codegraph_deps(module_hint)
            if deps and "no results" not in deps.lower():
                return f"💡 {module_hint} depends on: {deps[:200]}"
    except Exception:
        pass

    return None
