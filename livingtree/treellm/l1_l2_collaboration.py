"""L1-L2 Bidirectional Collaboration — deep reasoning + fast execution in parallel.

Protocol:
  L2 (pro reasoning) acts as supervisor — declares needs via <need> tags.
  L1 (flash execution) fulfills needs in parallel — VFS, tools, knowledge, SQL.
  Human can intervene at any point via <need type="human">.

Delegation levels:
  fire-and-forget — L1 executes, L2 doesn't wait for result
  need-result     — L1 executes, L2 waits for result to continue reasoning
  need-approval   — L1 prepares a proposal, L2 approves before execution

Flow:
  User → L2 starts reasoning → declares <need> → L1 fulfills in parallel
       → L2 continues (if fire-and-forget) or waits (if need-result)
       → Human can be asked via <need type="human">
       → L1 can ask L2 questions (reverse delegation)
       → Final synthesis by L2

Usage:
    collab = L1L2Collaboration(tree_llm)
    result = await collab.collaborative_chat(
        user_query="分析这个项目的架构问题",
        max_rounds=5,
        human_callback=my_human_handler,
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger


class NeedType(str, Enum):
    TOOL = "tool"
    KNOWLEDGE = "knowledge"
    FILE = "file"
    SQL = "sql"
    SEARCH = "search"
    HUMAN = "human"
    QUESTION = "question"  # L1 asking L2


class DelegateLevel(str, Enum):
    FIRE_AND_FORGET = "fire-and-forget"
    NEED_RESULT = "need-result"
    NEED_APPROVAL = "need-approval"


@dataclass
class Need:
    """A declared need from L2 to L1 (or human)."""
    id: str
    type: NeedType
    level: DelegateLevel
    description: str
    params: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    fulfilled: bool = False
    result: Any = None
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class CollaborationRound:
    """One round of L2 reasoning + L1 fulfillment."""
    round_id: int
    l2_input: str = ""
    l2_reasoning: str = ""
    l2_needs: list[Need] = field(default_factory=list)
    l1_results: list[dict] = field(default_factory=list)
    l1_questions: list[str] = field(default_factory=list)
    human_interventions: list[dict] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class CollaborationResult:
    """Final output of a collaborative session."""
    text: str = ""
    rounds: list[CollaborationRound] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    l2_calls: int = 0
    l1_calls: int = 0
    human_calls: int = 0
    method: str = "l1_l2_collaboration"
    insights: list[str] = field(default_factory=list)  # L1 observations for L2 learning


# ── Need tag parser ──
_NEED_RE = re.compile(
    r'<need\s+id="(?P<id>[^"]+)"\s+type="(?P<type>[^"]+)"'
    r'\s*(?:level="(?P<level>[^"]+)")?\s*'
    r'(?:timeout="(?P<timeout>[^"]+)")?\s*>'
    r'(?P<description>.*?)'
    r'</need>',
    re.DOTALL,
)


class L1L2Collaboration:
    """Orchestrates L1(flash) ↔ L2(pro) bidirectional collaboration.

    L2 supervises and does deep reasoning. L1 executes fast operations.
    They communicate via <need> tags and structured delegation.
    """

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._world_state: dict[str, Any] = {}
        self._session_needs: list[Need] = []
        self._human_callback: Callable | None = None
        self._history: list[CollaborationRound] = []
        self._l2_feedback_for_l1: list[str] = []  # L2's suggestions to L1

    # ═══ Main entry point ═══════════════════════════════════════════

    async def collaborative_chat(
        self,
        user_query: str,
        max_rounds: int = 5,
        human_callback: Callable | None = None,
        l2_provider: str = "",
        l2_model: str = "",
        extra_context: str = "",
    ) -> CollaborationResult:
        """Execute a collaborative L1+L2 session.

        Args:
            user_query: The user's original question/task.
            max_rounds: Maximum rounds of L2 reasoning.
            human_callback: async fn(question: str, timeout: float) -> str | None.
                Returns human answer or None (timeout → L2 decides autonomously).
            l2_provider: Force specific L2 provider.
            l2_model: Force specific L2 model.
            extra_context: Additional context to inject.
        """
        t0 = time.time()
        self._human_callback = human_callback
        result = CollaborationResult()

        # Start L1 preloading in background while L2 begins reasoning
        l1_preload_task = asyncio.create_task(self._l1_preload(user_query, extra_context))

        # Build initial L2 prompt with collaboration instructions
        l2_prompt = self._build_l2_system_prompt(user_query, extra_context)
        current_context = l2_prompt
        accumulated_knowledge: list[str] = []

        for round_num in range(max_rounds):
            cr = CollaborationRound(round_id=round_num + 1)
            t_round = time.time()

            # L2 reasoning phase
            l2_response = await self._l2_reason(
                current_context, accumulated_knowledge, l2_provider, l2_model,
            )
            cr.l2_reasoning = l2_response

            # Parse <need> declarations
            needs = self._parse_needs(l2_response, round_num)
            cr.l2_needs = needs

            if not needs:
                # No needs declared → L2 is done reasoning
                result.text = l2_response
                cr.elapsed_ms = (time.time() - t_round) * 1000
                self._history.append(cr)
                break

            # Fulfill needs — parallel where possible
            fire_forget_tasks = []
            need_result_tasks = []
            approval_tasks = []

            for need in needs:
                if need.type == NeedType.HUMAN:
                    # Human oracle
                    human_answer = await self._ask_human(need.description, need.params.get("timeout", 120))
                    if human_answer:
                        cr.human_interventions.append({
                            "need_id": need.id,
                            "question": need.description,
                            "answer": human_answer,
                        })
                        need.fulfilled = True
                        need.result = human_answer
                        result.human_calls += 1
                    else:
                        # Auto-decide
                        need.result = "[AUTO] L2 will decide autonomously"
                        need.fulfilled = True

                elif need.level == DelegateLevel.FIRE_AND_FORGET:
                    fire_forget_tasks.append(self._l1_fulfill(need))
                    need.fulfilled = True
                    need.result = "dispatched"

                elif need.level == DelegateLevel.NEED_RESULT:
                    need_result_tasks.append(self._l1_fulfill(need))

                elif need.level == DelegateLevel.NEED_APPROVAL:
                    approval_tasks.append(self._l1_fulfill(need))

            # Execute in parallel
            if fire_forget_tasks:
                asyncio.gather(*fire_forget_tasks)  # Don't wait

            if need_result_tasks:
                await asyncio.gather(*need_result_tasks)

            # Approval tasks: L1 prepared proposal, L2 needs to approve
            if approval_tasks:
                await asyncio.gather(*approval_tasks)
                # Inject approval request back to L2 in next round
                approval_context = "\n".join(
                    f"[APPROVAL NEEDED: {n.id}] {n.description}\nProposal: {n.result}"
                    for n in needs if n.level == DelegateLevel.NEED_APPROVAL and n.fulfilled
                )
                if approval_context:
                    accumulated_knowledge.append(approval_context)

            # Collect L1 results and build context for next round
            l1_results_text = []
            for need in needs:
                if need.fulfilled and need.level != DelegateLevel.FIRE_AND_FORGET:
                    status = "✅" if not need.error else f"❌ {need.error}"
                    l1_results_text.append(
                        f"[{need.id}] {need.type}({need.level}): {status}"
                        f"{chr(10) + str(need.result)[:2000] if need.result else ''}"
                    )
                cr.l1_results.append({
                    "need_id": need.id,
                    "type": need.type.value,
                    "result": str(need.result)[:500] if need.result else "",
                    "error": need.error,
                })
                result.l1_calls += 1

            if l1_results_text:
                accumulated_knowledge.append("\n--- L1 Results ---\n" + "\n".join(l1_results_text))

            # Build context for next L2 round
            current_context = self._build_next_round_context(
                user_query, accumulated_knowledge, needs, round_num, max_rounds,
            )

            cr.elapsed_ms = (time.time() - t_round) * 1000
            self._history.append(cr)
            result.rounds.append(cr)
            result.l2_calls += 1

        # Wait for L1 preload to finish
        try:
            preload = await l1_preload_task
            if preload:
                result.insights = preload
        except Exception:
            pass

        result.total_elapsed_ms = (time.time() - t0) * 1000
        logger.info(
            f"L1L2Collab: {len(result.rounds)} rounds, "
            f"L2={result.l2_calls}, L1={result.l1_calls}, Human={result.human_calls}, "
            f"{result.total_elapsed_ms:.0f}ms"
        )
        return result

    # ═══ L2 supervisor ═══════════════════════════════════════════════

    def _build_l2_system_prompt(self, user_query: str, extra_context: str) -> str:
        return (
            "You are the L2 supervisor model for a collaborative AI system.\n\n"
            "## Your Role\n"
            "- You are the DEEP REASONING layer. Think carefully, plan strategically.\n"
            "- You have an L1 (fast/flash) assistant that can execute operations for you.\n"
            "- Your context window should contain ONLY reasoning — not tool result clutter.\n\n"
            "## How to delegate to L1\n"
            "Declare what you need using <need> tags:\n\n"
            '<need id="req1" type="tool" level="need-result">search_codebase("upload")</need>\n'
            '<need id="req2" type="file" level="need-result">read config/livingtree.yaml</need>\n'
            '<need id="req3" type="knowledge" level="fire-and-forget">index this document</need>\n'
            '<need id="req4" type="human" level="need-result" timeout="120">'
            "Should I delete /data/production/users.db? This looks dangerous.</need>\n\n"
            "## Delegation levels\n"
            "- fire-and-forget: L1 does it, you don't need the result. Keep reasoning.\n"
            "- need-result: L1 does it, return the result to you for next reasoning step.\n"
            "- need-approval: L1 prepares a proposal, you review and approve before execution.\n\n"
            "## Need types\n"
            "- tool: Execute a tool (web_search, browser_browse, api_call, bash, git, etc.)\n"
            "- file: Read/write files via VirtualFS\n"
            "- knowledge: Query knowledge base, RAG, vector search\n"
            "- sql: Execute SQL query\n"
            "- search: Web search via multi-engine\n"
            "- human: Ask the human user for input\n"
            "- question: L1 is asking you a question (reverse delegation)\n\n"
            "## Rules\n"
            "1. Delegate everything routine to L1. Reserve your context for DEEP THINKING.\n"
            "2. Multiple <need> tags in one response are OK — they execute in parallel.\n"
            "3. If you don't know something, ask L1 to look it up. Don't guess.\n"
            "4. For dangerous operations, use level=\"need-approval\" or type=\"human\".\n"
            "5. When you have all information, provide your final synthesis WITHOUT <need> tags.\n\n"
            f"{extra_context}\n\n"
            f"## Current Task\n{user_query}\n\n"
            "Begin your reasoning. Declare needs if you require information."
        )

    def _build_next_round_context(
        self, query: str, knowledge: list[str], previous_needs: list[Need],
        round_num: int, max_rounds: int,
    ) -> str:
        unfulfilled = [n for n in previous_needs if not n.fulfilled]
        parts = [
            f"## Round {round_num + 1}/{max_rounds}\n\nOriginal task: {query}\n",
        ]
        if knowledge:
            parts.append("## Accumulated Knowledge\n" + "\n".join(knowledge[-5:]))
        if unfulfilled:
            parts.append("\n## Unfulfilled Needs\n" + "\n".join(
                f"- [{n.id}] {n.type}: {n.description} ({n.error or 'pending'})"
                for n in unfulfilled
            ))
        parts.append("\nContinue your reasoning. Declare new needs or provide final synthesis.")
        return "\n".join(parts)

    async def _l2_reason(
        self, context: str, knowledge: list[str],
        provider: str, model: str,
    ) -> str:
        """Call L2 for deep reasoning."""
        if not self._tree:
            return "L2 not available"

        # Inject accumulated knowledge
        if knowledge:
            context += "\n\n## Knowledge So Far\n" + "\n".join(knowledge[-3:])

        try:
            resp = await self._tree.chat(
                messages=[{"role": "user", "content": context}],
                provider=provider or "",
                model=model or "",
                temperature=0.3, max_tokens=4096, timeout=120,
                enable_coach=False,  # Already coached at this level
                enable_onto=False,   # Already enriched
            )
            return resp.text if resp and hasattr(resp, "text") else ""
        except Exception as e:
            logger.warning(f"L2 reasoning failed: {e}")
            return ""

    # ═══ L1 executor ═════════════════════════════════════════════════

    async def _l1_fulfill(self, need: Need) -> None:
        """Execute a need via L1 (fast/flash model or direct tool call)."""
        t0 = time.time()
        try:
            if need.type == NeedType.FILE:
                need.result = await self._handle_file_need(need)
            elif need.type == NeedType.TOOL:
                need.result = await self._handle_tool_need(need)
            elif need.type == NeedType.KNOWLEDGE:
                need.result = await self._handle_knowledge_need(need)
            elif need.type == NeedType.SEARCH:
                need.result = await self._handle_search_need(need)
            elif need.type == NeedType.SQL:
                need.result = await self._handle_sql_need(need)
            elif need.type == NeedType.QUESTION:
                # L1 is asking L2 — forward to L2 feedback queue
                self._l2_feedback_for_l1.append(need.description)
                need.result = "forwarded to L2"
            else:
                need.result = await self._handle_generic_need(need)
            need.fulfilled = True
        except Exception as e:
            need.error = str(e)[:200]
            need.fulfilled = False
            logger.debug(f"L1 fulfill [{need.id}]: {e}")
        need.elapsed_ms = (time.time() - t0) * 1000

    async def _handle_file_need(self, need: Need) -> str:
        path = need.params.get("path", need.description.strip())
        op = need.params.get("op", "read")
        if op == "write":
            content = need.params.get("content", "")
            from pathlib import Path as _Path
            _Path(path).parent.mkdir(parents=True, exist_ok=True)
            _Path(path).write_text(content, encoding="utf-8")
            return f"Written {len(content)} bytes to {path}"
        else:
            from pathlib import Path as _Path
            p = _Path(path)
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")[:5000]
            elif p.exists():
                return "\n".join(str(x) for x in p.iterdir())[:5000]
            return f"Path not found: {path}"

    async def _handle_tool_need(self, need: Need) -> str:
        tool_call = need.description.strip()
        if not self._tree:
            return "TreeLLM not available"
        try:
            bus = self._tree._get_capability_bus_sync() if hasattr(self._tree, '_get_capability_bus_sync') else None
            if not bus:
                from livingtree.treellm.capability_bus import get_capability_bus
                bus = get_capability_bus()
            result = await bus.route(tool_call)
            return str(result)[:5000] if result else "Tool executed (no output)"
        except Exception as e:
            return f"Tool error: {e}"

    async def _handle_knowledge_need(self, need: Need) -> str:
        query = need.description.strip()
        try:
            from livingtree.knowledge.vector_store import VectorStore
            store = VectorStore()
            results = store.search_similar(
                store.embed(query), top_k=5,
            )
            return "\n".join(results[:5]) if results else "No relevant knowledge found"
        except Exception as e:
            return f"Knowledge query error: {e}"

    async def _handle_search_need(self, need: Need) -> str:
        query = need.description.strip()
        try:
            from livingtree.capability.llm_web_search import web_search
            results = await web_search(query)
            if isinstance(results, list):
                return "\n\n".join(
                    f"{i+1}. {r.get('title','')}: {r.get('snippet','')[:300]}"
                    for i, r in enumerate(results[:5])
                )
            return str(results)[:5000]
        except Exception as e:
            return f"Search error: {e}"

    async def _handle_sql_need(self, need: Need) -> str:
        query = need.description.strip()
        try:
            import sqlite3
            db_path = need.params.get("db", ".livingtree/cache.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            conn.close()
            if cols:
                return "\n".join(
                    " | ".join(str(v) for v in row) for row in rows[:20]
                )
            return f"Query executed: {len(rows)} rows affected"
        except Exception as e:
            return f"SQL error: {e}"

    async def _handle_generic_need(self, need: Need) -> str:
        if self._tree:
            try:
                resp = await self._tree.chat(
                    messages=[{"role": "user", "content": need.description}],
                    temperature=0.1, max_tokens=500, timeout=20,
                    enable_coach=False, enable_onto=False,
                )
                return resp.text[:2000] if resp and hasattr(resp, "text") else ""
            except Exception:
                pass
        return f"Need type '{need.type}' not handled"

    # ═══ Human oracle ═══════════════════════════════════════════════

    async def _ask_human(self, question: str, timeout: float = 120) -> str | None:
        if not self._human_callback:
            return None
        try:
            return await asyncio.wait_for(
                self._human_callback(question, timeout),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.debug(f"Human oracle timeout ({timeout}s): {question[:80]}")
            return None
        except Exception as e:
            logger.warning(f"Human oracle error: {e}")
            return None

    # ═══ L1 preloading ══════════════════════════════════════════════

    async def _l1_preload(self, user_query: str, extra_context: str) -> list[str]:
        """L1 pre-fetches context while L2 reasons. Returns insights for L2."""
        insights = []
        try:
            # Parallel preloads
            tasks = [
                self._preload_knowledge(user_query),
                self._preload_files(extra_context),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    insights.extend(r)
                elif isinstance(r, str) and r:
                    insights.append(r)
        except Exception as e:
            logger.debug(f"L1 preload: {e}")
        return insights

    async def _preload_knowledge(self, query: str) -> list[str]:
        try:
            from livingtree.knowledge.vector_store import VectorStore
            store = VectorStore()
            embedding = store.embed(query)
            docs = store.search_similar(embedding, top_k=3)
            return [f"[L1 preload] Knowledge: {d}" for d in docs]
        except Exception:
            return []

    async def _preload_files(self, extra_context: str) -> list[str]:
        if not extra_context:
            return []
        # Check if extra_context mentions file paths
        paths = re.findall(r'[\w./-]+\.(?:py|yaml|json|toml|md|sql|txt)', extra_context)
        results = []
        for p in paths[:3]:
            try:
                from pathlib import Path as _Path
                fp = _Path(p)
                if fp.exists():
                    results.append(f"[L1 preload] File {p}: {fp.read_text(encoding='utf-8')[:1000]}")
            except Exception:
                pass
        return results

    # ═══ Need parsing ═══════════════════════════════════════════════

    def _parse_needs(self, text: str, round_num: int) -> list[Need]:
        needs = []
        for m in _NEED_RE.finditer(text):
            try:
                need = Need(
                    id=m.group("id") or f"auto_{round_num}_{len(needs)}",
                    type=NeedType(m.group("type")),
                    level=DelegateLevel(m.group("level") or "need-result"),
                    description=m.group("description").strip(),
                    params={"timeout": int(m.group("timeout"))} if m.group("timeout") else {},
                )
                needs.append(need)
            except ValueError as e:
                logger.debug(f"Invalid need tag: {e}")
        return needs

    # ═══ L2 self-learning feedback to L1 ═══════════════════════════

    def get_l1_suggestions(self) -> list[str]:
        """L2's suggestions for improving L1 behavior. Call periodically."""
        suggestions = list(self._l2_feedback_for_l1)
        self._l2_feedback_for_l1.clear()
        return suggestions

    def stats(self) -> dict:
        return {
            "rounds": len(self._history),
            "total_needs": len(self._session_needs),
            "l2_suggestions": len(self._l2_feedback_for_l1),
            "world_state_keys": list(self._world_state.keys()),
        }

    # ═══ Multi-Model Conference — collaborative deliberation ═══

    async def conference(
        self, problem: str, context: str = "", max_rounds: int = 3,
    ) -> dict[str, Any]:
        """Three-model deliberation when a complex problem is detected.

        Embedding: finds similar past issues from recording_engine snapshots
        L1: proposes quick fixes based on pattern matching
        L2: evaluates proposals, synthesizes final decision

        Returns {decision, proposals, confidence, trace}
        """
        t0 = time.time()
        proposals: list[dict] = []

        # Round 1: Embedding finds similar past incidents
        try:
            from .three_model_intelligence import get_three_model_intelligence
            tmi = get_three_model_intelligence(self._tree)
            similar = tmi.find_similar_snapshot(problem, top_k=3)
            for s in similar:
                proposals.append({
                    "source": "embedding",
                    "from_past": s.summary,
                    "confidence": 0.6,
                    "suggestion": f"Past similar issue resolved: {s.summary[:100]}",
                })
        except Exception:
            pass

        # Round 2: L1 proposes quick fixes (from recording_engine patterns)
        try:
            from .recording_engine import get_recording_engine
            rec = get_recording_engine()
            recordings = rec.list_recordings()[-10:]
            for r in recordings:
                if isinstance(r, dict) and r.get("events", 0) > 2:
                    proposals.append({
                        "source": "l1",
                        "from_recording": r.get("id", ""),
                        "confidence": 0.5,
                        "suggestion": f"Pattern from recording {r.get('id','')}: check tool chain",
                    })
        except Exception:
            pass

        # Round 3: L2 evaluates and synthesizes
        if self._tree:
            deliberation_prompt = (
                f"## Problem\n{problem}\n\n"
                f"## Context\n{context}\n\n"
                f"## Proposals from L1 and Embedding\n"
                + "\n".join(
                    f"- [{p['source']}] conf={p['confidence']:.2f}: {p['suggestion']}"
                    for p in proposals[:5]
                )
                + "\n\nAs the L2 supervisor, evaluate these proposals and provide:\n"
                  "1. Root cause analysis\n"
                  "2. Recommended action (choose or synthesize)\n"
                  "3. Confidence level (0.0-1.0)\n"
                  "4. Fallback plan if recommendation fails\n"
                  "Output as JSON: "
                  '{"root_cause":"...","action":"...","confidence":0.8,"fallback":"..."}'
            )
            try:
                resp = await self._tree.chat(
                    messages=[{"role": "user", "content": deliberation_prompt}],
                    temperature=0.2, max_tokens=800, timeout=30,
                    enable_coach=False, enable_onto=False,
                )
                l2_text = resp.text if resp and hasattr(resp, "text") else ""
                l2_decision = self._parse_json(l2_text)
            except Exception:
                l2_decision = {"root_cause": "unknown", "action": "retry",
                              "confidence": 0.3, "fallback": "escalate to human"}

            # L2 may also delegate to L1 via <need>
            needs = self._parse_needs(l2_text, 0)
            for need in needs:
                await self._l1_fulfill(need)

            return {
                "decision": l2_decision.get("action", "retry"),
                "root_cause": l2_decision.get("root_cause", ""),
                "confidence": l2_decision.get("confidence", 0.5),
                "fallback": l2_decision.get("fallback", "escalate"),
                "proposals": proposals,
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        return {
            "decision": "no_l2_available",
            "proposals": proposals,
            "elapsed_ms": (time.time() - t0) * 1000,
        }

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            import re as _re
            from livingtree.serialization.json_utils import _json_loads
            m = _re.search(r'\{.*\}', text, _re.DOTALL)
            if m:
                return _json_loads(m.group(0))
        except Exception:
            pass
        return {}


# ── Singleton ──
_collaboration: L1L2Collaboration | None = None


def get_l1_l2_collaboration(tree_llm=None) -> L1L2Collaboration:
    global _collaboration
    if _collaboration is None and tree_llm is not None:
        _collaboration = L1L2Collaboration(tree_llm)
    elif _collaboration is None:
        _collaboration = L1L2Collaboration()
    return _collaboration
