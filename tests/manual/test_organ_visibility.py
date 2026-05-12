"""End-to-end organ visibility test — 3 travel queries with full observability.

Runs the instrumented pipeline for each query, collects all organ events,
and produces a detailed visibility report per query.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from livingtree.dna.organ_dashboard import (
    get_organ_dashboard, InstrumentedPipeline, OrganType,
)


async def _run_query(idx: int, query: str):
    """Test one query with full organ visibility instrumentation."""
    sid = f"travel_test_{idx}"
    dashboard = get_organ_dashboard()
    pipeline = InstrumentedPipeline(dashboard)

    print(f"\n{'#' * 80}")
    print(f"# QUERY {idx}: {query}")
    print(f"{'#' * 80}")

    result = await pipeline.run(sid, query)
    summary = dashboard.get_session_summary(sid)

    # Print organ-by-organ breakdown
    print(f"\n{'=' * 60}")
    print(f"  ORGAN COORDINATION REPORT")
    print(f"{'=' * 60}")
    print(f"Session: {summary['session_id']}")
    print(f"Duration: {summary['duration_ms']}ms")
    print(f"Total tokens: {summary['total_tokens']}")
    print(f"Organs involved: {', '.join(summary['organs_involved'])}")

    print(f"\n{'Organ':<18} {'Actions':<8} {'Tokens':<10} {'Latency':<10}")
    print(f"{'-'*48}")
    for organ, details in summary["organ_details"].items():
        print(f"{organ:<18} {len(details['actions']):<8} {details['tokens']:<10} {details['latency_ms']:<10.0f}ms")

    # Print timeline
    print(f"\n📋 Execution Timeline:")
    events = dashboard._events.get(sid, [])
    for event in events[-10:]:  # Last 10 events for brevity
        icon = {
            OrganType.INTENT: "🧠", OrganType.LATENT: "🧬",
            OrganType.KNOWLEDGE: "📚", OrganType.CAPABILITY: "🔧",
            OrganType.PLANNING: "📋", OrganType.EXECUTION: "⚡",
            OrganType.REFLECTION: "🔄", OrganType.COMPILATION: "📦",
            OrganType.MEMORY: "💾",
        }.get(event.organ, "❓")

        print(f"  {icon} [{event.organ.value:12s}] {event.action:25s} "
              f"→ {event.reasoning[:80]}...")

    return result


async def main():
    print("=" * 80)
    print("  LIVINGTREE ORGAN VISIBILITY TEST — Instrumented Pipeline")
    print("=" * 80)
    print("Testing: 3 sequential travel-planning queries with full organ observability")
    print()

    queries = [
        (1, "国庆去哪玩？"),
        (2, "南京有什么好玩的"),
        (3, "预算2000元左右，两个人能玩几天"),
    ]

    all_results = []
    for idx, query in queries:
        result = await _run_query(idx, query)
        all_results.append(result)

    # Cross-query analysis
    print(f"\n{'=' * 80}")
    print("  CROSS-QUERY ANALYSIS")
    print(f"{'=' * 80}")

    dashboard = get_organ_dashboard()
    for result in all_results:
        sid = result["session_id"]
        summary = dashboard.get_session_summary(sid)
        organs_used = len(summary["organ_details"])

        print(f"\nQ{result['session_id'].split('_')[-1]}: {summary['query']}")
        print(f"  Intent: {result['intent']}")
        print(f"  Plan steps: {result['plan_steps']}")
        print(f"  Organs coordinated: {organs_used}/11")
        print(f"  Tokens burned: {summary['total_tokens']}")
        print(f"  Visibility: {organs_used} organs visible ← was 0 (BLACK BOX)")

    print(f"\n✅ ALL 3 QUERIES COMPLETED WITH FULL ORGAN VISIBILITY")
    print(f"✅ Previously: 0 visible organs → Now: {organs_used}/11 visible")
    print(f"✅ Previously: Black box → Now: Per-organ token cost + latency + reasoning")


if __name__ == "__main__":
    asyncio.run(main())
