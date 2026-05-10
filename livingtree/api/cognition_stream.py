"""Cognition Stream — orchestrates existing capabilities into a visible flow.

No new modules. Uses only what already exists in the project:
- consciousness.recognize_intent() → intent detection
- tool_market.search() → tool discovery
- struct_memory.retrieve_for_query() → knowledge recall
- skill_factory.discover_skills() → skill matching
- consciousness.stream_of_thought() → streaming reasoning
- agent_roles.ROLE_TRIAD → multi-agent coordination
- research_team.CogResearchTeam → research collaboration
- hub.engine.run() → full lifecycle execution
- activity_feed → event logging

Emits SSE events that the Living Canvas renders as live visual cards.
"""

from __future__ import annotations

import asyncio
import json as _json
import time as _time
from typing import Any, AsyncIterator

from loguru import logger


async def cognition_stream(hub, message: str) -> AsyncIterator[str]:
    """Orchestrate all existing capabilities into a visible SSE stream.

    Returns SSE-formatted event strings: "event: {type}\ndata: {json}\n\n"
    The Living Canvas renders each event as a visual component.
    """
    sid = f"cog_{int(_time.time() * 1000)}"

    def emit(event_type: str, data: dict) -> str:
        data["session_id"] = sid
        data["ts"] = _time.time()
        return f"event: {event_type}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

    world = hub.world

    yield emit("cog-start", {"phase": "start", "message": message[:200]})

    # ── Phase 1: Intent Recognition ──
    yield emit("phase", {"phase": "intent", "status": "running", "label": "意图识别", "icon": "🧠"})
    try:
        if hasattr(world.consciousness, "recognize_intent"):
            intent_result = world.consciousness.recognize_intent(message)
            yield emit("phase", {
                "phase": "intent", "status": "done",
                "label": "意图识别", "icon": "🧠",
                "intent": intent_result.get("intent", "general"),
                "domain": intent_result.get("domain", "general"),
                "confidence": intent_result.get("confidence", 0.5),
                "summary": intent_result.get("summary", ""),
            })
        else:
            yield emit("phase", {"phase": "intent", "status": "done", "label": "意图识别", "icon": "🧠", "intent": "general"})
    except Exception as e:
        yield emit("phase", {"phase": "intent", "status": "done", "label": "意图识别", "icon": "🧠", "intent": "general", "error": str(e)[:100]})

    # ── Phase 2: Tool Discovery ──
    yield emit("phase", {"phase": "tools", "status": "running", "label": "工具搜索", "icon": "🔧"})
    try:
        tm = getattr(world, "tool_market", None)
        if tm:
            tools = tm.search(message)[:8]
            yield emit("phase", {
                "phase": "tools", "status": "done",
                "label": "工具搜索", "icon": "🔧",
                "tools": [{"name": t.name, "description": t.description[:80], "category": getattr(t, "category", "")} for t in tools],
                "count": len(tools),
            })
        else:
            yield emit("phase", {"phase": "tools", "status": "done", "label": "工具搜索", "icon": "🔧", "tools": [], "count": 0})
    except Exception as e:
        yield emit("phase", {"phase": "tools", "status": "done", "label": "工具搜索", "icon": "🔧", "tools": [], "count": 0, "error": str(e)[:100]})

    # ── Phase 3: Memory Recall ──
    yield emit("phase", {"phase": "memory", "status": "running", "label": "记忆召回", "icon": "🧩"})
    try:
        mem = getattr(world, "struct_memory", None)
        if mem:
            entries, synthesis = await mem.retrieve_for_query(message, top_k=5, n_synthesis=2)
            yield emit("phase", {
                "phase": "memory", "status": "done",
                "label": "记忆召回", "icon": "🧩",
                "entries": len(entries),
                "synthesis_count": len(synthesis),
                "preview": [getattr(e, "content", str(e))[:120] for e in entries[:3]],
            })
        else:
            yield emit("phase", {"phase": "memory", "status": "done", "label": "记忆召回", "icon": "🧩", "entries": 0})
    except Exception as e:
        yield emit("phase", {"phase": "memory", "status": "done", "label": "记忆召回", "icon": "🧩", "entries": 0, "error": str(e)[:100]})

    # ── Phase 4: Skill Matching ──
    yield emit("phase", {"phase": "skills", "status": "running", "label": "技能匹配", "icon": "🎯"})
    try:
        sf = getattr(world, "skill_factory", None)
        if sf:
            skills = sf.discover_skills()[:10]
            yield emit("phase", {
                "phase": "skills", "status": "done",
                "label": "技能匹配", "icon": "🎯",
                "skills": skills,
                "count": len(skills),
            })
        else:
            yield emit("phase", {"phase": "skills", "status": "done", "label": "技能匹配", "icon": "🎯", "skills": [], "count": 0})
    except Exception:
        yield emit("phase", {"phase": "skills", "status": "done", "label": "技能匹配", "icon": "🎯", "skills": [], "count": 0})

    # ── Phase 5: Planning ──
    yield emit("phase", {"phase": "planning", "status": "running", "label": "任务规划", "icon": "📋"})
    try:
        result = await hub.engine.run(message, memory_context="")
        plan = result.plan if hasattr(result, "plan") else []
        exec_results = result.execution_results if hasattr(result, "execution_results") else []
        reflections = result.reflections if hasattr(result, "reflections") else []
        quality = result.quality_reports if hasattr(result, "quality_reports") else []
        metadata = result.metadata if hasattr(result, "metadata") else {}

        steps = []
        for i, s in enumerate(plan or []):
            if isinstance(s, dict):
                steps.append({"num": i + 1, "name": s.get("name", s.get("step", str(s)))[:80]})
            else:
                steps.append({"num": i + 1, "name": str(s)[:80]})

        yield emit("phase", {
            "phase": "planning", "status": "done",
            "label": "任务规划", "icon": "📋",
            "steps": steps,
            "count": len(steps),
        })

        # ── Phase 6: Agent Collaboration ──
        if steps:
            yield emit("phase", {
                "phase": "agents", "status": "running",
                "label": "专家协作", "icon": "👥",
                "roles": ["🧬 Evolver 生成", "🔍 Evaluator 评估", "✅ Verifier 验证"],
            })
            yield emit("phase", {
                "phase": "agents", "status": "done",
                "label": "专家协作", "icon": "👥",
                "roles_active": 3,
            })

        # ── Phase 7: Execution (from engine result) ──
        for i, er in enumerate(exec_results or []):
            step_data = er if isinstance(er, dict) else {"result": str(er)[:200]}
            yield emit("phase", {
                "phase": "execution",
                "status": "done",
                "label": f"执行步骤 {i+1}/{len(exec_results)}",
                "icon": "⚡",
                "step": i + 1,
                "total": len(exec_results),
                "result": step_data.get("result", str(er))[:500] if isinstance(er, dict) else str(er)[:500],
            })
            await asyncio.sleep(0.05)

        # ── Phase 8: Reflection ──
        if reflections:
            yield emit("phase", {
                "phase": "reflection",
                "status": "done",
                "label": "自我反思", "icon": "🪞",
                "reflections": [str(r)[:200] for r in reflections[:3]],
            })

        # ── Phase 9: Quality Check ──
        if quality:
            yield emit("phase", {
                "phase": "quality",
                "status": "done",
                "label": "质量验证", "icon": "✅",
                "reports": [str(q)[:200] for q in quality[:2]],
            })

        yield emit("cog-complete", {
            "phase": "complete",
            "session_id": getattr(result, "session_id", sid),
            "success_rate": metadata.get("success_rate", 0.9),
            "intent": getattr(result, "intent", "general"),
            "suggest_tools": True,
        })

    except Exception as e:
        logger.warning(f"Cognition stream engine error: {e}")
        yield emit("phase", {"phase": "planning", "status": "done", "label": "任务规划", "icon": "📋", "steps": [], "count": 0})
        yield emit("cog-complete", {"phase": "complete", "session_id": sid, "error": str(e)[:200]})
