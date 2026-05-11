"""Test LivingTree full pipeline with 3 travel-planning questions.

Runs WITHOUT starting the HTTP server — uses IntegrationHub directly.
Tests: L0-L4 layers, memory, storage, knowledge base, reasoning, learning.
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

# Ensure the project root is on the path
ROOT = Path(__file__).resolve().parent.parent  # tests/ → project root
sys.path.insert(0, str(ROOT))


async def banner(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


@pytest.mark.skip(reason="Requires custom parametrized fixture setup — run directly via __main__")
async def test_question(hub, question: str, index: int) -> dict:
    """Run a single question through the full chat pipeline."""
    print(f"\n{'─' * 60}")
    print(f"  Test #{index}: {question[:60]}")
    print(f"{'─' * 60}")

    t0 = time.time()
    try:
        result = await hub.chat(question)
        elapsed = time.time() - t0

        # Extract pipeline indicators
        session_id = result.get("session_id", "?")
        intent = result.get("intent", "?")
        plan_steps = len(result.get("plan", [])) if result.get("plan") else 0
        exec_count = len(result.get("execution_results", []))
        reflections = result.get("reflections", []) or []
        success_rate = result.get("success_rate", 0)
        quality = result.get("quality", []) or []
        generation = result.get("generation", 0)
        mode = result.get("mode", "chat")

        # Summary
        print(f"  Mode:          {mode}")
        print(f"  Session:       {session_id[:16]}")
        print(f"  Intent:        {intent}")
        print(f"  Plan steps:    {plan_steps}")
        print(f"  Exec results:  {exec_count}")
        print(f"  Reflections:   {len(reflections)}")
        print(f"  Quality checks:{len(quality)}")
        print(f"  Success rate:  {success_rate:.2%}")
        print(f"  Generation:    {generation}")
        print(f"  Elapsed:       {elapsed:.1f}s")
        print(f"  Status:        {'✅' if success_rate >= 0.5 else '⚠️'}")

        return {
            "index": index,
            "question": question[:60],
            "mode": mode,
            "session_id": session_id,
            "intent": intent,
            "plan_steps": plan_steps,
            "exec_count": exec_count,
            "reflections": len(reflections),
            "success_rate": success_rate,
            "elapsed": elapsed,
            "ok": True,
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ❌ Failed: {e}")
        print(f"  Elapsed: {elapsed:.1f}s (failed)")
        return {
            "index": index,
            "question": question[:60],
            "mode": "error",
            "error": str(e)[:200],
            "elapsed": elapsed,
            "ok": False,
        }


async def main():
    print("=" * 60)
    print("  LivingTree Pipeline Test")
    print("  (no HTTP server — direct hub.chat())")
    print("=" * 60)

    # Phase 1: Initialize hub
    await banner("Phase 1: Hub Initialization")
    t0 = time.time()

    try:
        from livingtree.integration.hub import IntegrationHub
        from livingtree.config.settings import get_config
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        print("  Check: cd LivingTreeAlAgent && python -m livingtree (first)")
        sys.exit(1)

    config = get_config()
    print(f"  Config loaded (v{config.version})")
    print(f"  Flash: {config.model.flash_model}")
    print(f"  Pro:   {config.model.pro_model}")

    print("\n  Creating IntegrationHub (lazy=False for full init)...")
    hub = IntegrationHub(config=config, lazy=False)
    print(f"  Hub created (lazy=False)")

    print("\n  Starting hub (init all components, no web server)...")
    try:
        await asyncio.wait_for(hub.start(), timeout=120.0)
    except asyncio.TimeoutError:
        print("  ⚠️ Hub init timed out after 120s (continuing anyway)")
        hub._started = True  # Force start for partial test
        hub._ready_event.set()
    except Exception as e:
        print(f"  ⚠️ Hub init had errors: {str(e)[:200]}")
        print("  Continuing with partial initialization...")
        hub._started = True
        hub._ready_event.set()

    elapsed_init = time.time() - t0
    print(f"\n  Init complete in {elapsed_init:.1f}s")

    # Check what's available
    print("\n  Component status:")
    components = [
        ("engine", hub.engine),
        ("consciousness", hub.consciousness),
        ("knowledge_base", hub.world.knowledge_base if hub.world else None),
        ("struct_memory", hub.struct_memory),
        ("embedding_scorer", hub.embedding_scorer),
        ("foresight_gate", getattr(hub.world, "foresight_gate", None) if hub.world else None),
    ]
    for name, comp in components:
        status = "✅" if comp else "❌"
        print(f"    {status} {name}")

    # Phase 2: Test questions
    await banner("Phase 2: Travel Pipeline Tests")

    questions = [
        "国庆去哪玩？我想找一个适合两人出行的国内目的地，预算在2000元左右。",
        "南京有什么好玩的？推荐一些适合年轻情侣的景点和美食。",
        "预算2000元，两人能玩几天？请帮我规划一下南京三日游的具体行程和花费。",
    ]

    results = []
    for i, q in enumerate(questions):
        result = await test_question(hub, q, i + 1)
        results.append(result)
        # Brief pause between questions
        await asyncio.sleep(2)

    # Phase 3: Knowledge / Memory check
    await banner("Phase 3: Knowledge Persistence Check")
    try:
        if hub.world and hub.world.knowledge_base:
            stats = hub.world.knowledge_base.stats() if hasattr(hub.world.knowledge_base, "stats") else {}
            print(f"  KB documents: {stats.get('total_documents', '?')}")
            print(f"  KB embeddings: {stats.get('total_embeddings', '?')}")
        else:
            print("  ❌ Knowledge base not available")

        if hub.struct_memory:
            mem_stats = hub.struct_memory.stats() if hasattr(hub.struct_memory, "stats") else {}
            print(f"  Memory entries: {mem_stats.get('total_entries', '?')}")
        else:
            print("  ❌ Struct memory not available")
    except Exception as e:
        print(f"  ⚠️ Knowledge check: {e}")

    # Phase 4: Summary
    await banner("Phase 4: Test Summary")
    total = len(results)
    ok_count = sum(1 for r in results if r["ok"])
    avg_rate = sum(r.get("success_rate", 0) for r in results if r["ok"]) / max(ok_count, 1)
    avg_time = sum(r.get("elapsed", 0) for r in results if r["ok"]) / max(ok_count, 1)

    print(f"  Questions:     {total}")
    print(f"  Successful:    {ok_count}/{total}")
    print(f"  Failed:        {total - ok_count}/{total}")
    print(f"  Avg success:   {avg_rate:.1%}")
    print(f"  Avg elapsed:   {avg_time:.1f}s")

    # Detail table
    print(f"\n  {'#':<3} {'Question':<50} {'Intent':<12} {'Plan':<5} {'Exec':<5} {'Rate':<7} {'Time':<7}")
    print(f"  {'─' * 3} {'─' * 50} {'─' * 12} {'─' * 5} {'─' * 5} {'─' * 7} {'─' * 7}")
    for r in results:
        q = r["question"][:48]
        intent = r.get("intent", "error")[:10]
        plan = r.get("plan_steps", 0)
        exec_c = r.get("exec_count", 0)
        rate = f"{r.get('success_rate', 0):.1%}"
        elapsed = f"{r.get('elapsed', 0):.1f}s"
        print(f"  {r['index']:<3} {q:<50} {intent:<12} {plan:<5} {exec_c:<5} {rate:<7} {elapsed:<7}")

    # Shutdown
    await banner("Shutdown")
    print("  Shutting down hub...")
    try:
        await hub.shutdown()
    except Exception:
        pass
    print("  Done.")


if __name__ == "__main__":
    asyncio.run(main())
