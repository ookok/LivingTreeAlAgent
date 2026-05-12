"""Architecture Feedback Bridge — Close the loop between isolated modules.

Three feedback loops that were missing:
  1. Quality Checker → Task Planner: quality scores feed back to improve planning
  2. Evolution Store → Life Engine: stored lessons are retrieved for future runs
  3. Market/Pricing → TreeLLM Routing: economic signals influence provider election
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger


class FeedbackBridge:
    """Connect previously isolated modules into closed feedback loops."""

    # ── Loop 1: Quality → Planner ──

    @staticmethod
    def feed_quality_to_planner(
        quality_result: dict, planner, task_type: str = "general"
    ) -> None:
        """Feed quality assessment results back to the task planner.

        High-quality tasks → planner learns to use similar strategies.
        Low-quality tasks → planner adjusts depth/complexity.
        """
        try:
            score = quality_result.get("overall_score", 0.5)
            issues = quality_result.get("issues", [])

            if hasattr(planner, 'quality_feedback'):
                planner.quality_feedback.append({
                    "task_type": task_type,
                    "score": score,
                    "issue_count": len(issues),
                })

            # Adjust planning depth based on quality history
            if score < 0.3 and hasattr(planner, 'max_depth'):
                planner.max_depth = min(planner.max_depth + 1, 12)
                logger.debug(f"FeedbackBridge: low quality ({score:.2f}) → increase depth to {planner.max_depth}")
            elif score > 0.8 and hasattr(planner, 'max_depth'):
                planner.max_depth = max(planner.max_depth - 1, 1)
                logger.debug(f"FeedbackBridge: high quality ({score:.2f}) → decrease depth to {planner.max_depth}")
        except Exception as e:
            logger.debug(f"FeedbackBridge quality→planner: {e}")

    # ── Loop 2: Evolution → Life Engine ──

    @staticmethod
    def inject_evolution_lessons(life_engine, session_id: str) -> list[str]:
        """Inject stored evolution lessons from previous runs into the current context.

        This closes the evolution_store → life_engine loop:
        lessons extracted by evolution_store are now actively used.
        """
        try:
            if not hasattr(life_engine, 'world'):
                return []
            world = life_engine.world
            if not hasattr(world, 'evolution_store'):
                return []

            store = world.evolution_store
            if not hasattr(store, 'query_by_task_type'):
                return []

            # Query relevant lessons based on current task
            task_type = getattr(life_engine, '_current_task_type', 'general')
            lessons = store.query_by_task_type(task_type, limit=3) if hasattr(store, 'query_by_task_type') else []

            injected = []
            for lesson in lessons[:3]:
                content = getattr(lesson, 'lesson', '') or str(lesson)
                if content and len(content) > 10:
                    injected.append(f"[Evolution Lesson] {content[:300]}")
                    logger.debug(f"FeedbackBridge: injected evolution lesson for {task_type}")

            return injected
        except Exception as e:
            logger.debug(f"FeedbackBridge evolution→life_engine: {e}")
            return []

    # ── Loop 3: Market → Routing ──

    @staticmethod
    def feed_market_to_routing(market_engine, election_system) -> dict:
        """Feed economic pricing signals into the TreeLLM provider election.

        Market prices should influence which providers are preferred:
        - Expensive providers get lower election weight when budget is tight
        - Free/cheap providers get boosted when cost is a priority
        """
        try:
            if not hasattr(market_engine, 'get_pricing'):
                return {}

            pricing = market_engine.get_pricing()
            election_weights = {}

            for provider, price_info in pricing.items():
                cost_per_1k = price_info.get("cost_per_1k", 0.002)
                # Economic gate: if daily budget > 80% used, heavily penalize expensive providers
                budget_used = price_info.get("budget_used_pct", 0.0)

                if budget_used > 0.8:
                    weight = 0.1 if cost_per_1k > 0.002 else 0.5
                elif budget_used > 0.5:
                    weight = 0.3 if cost_per_1k > 0.002 else 0.7
                else:
                    weight = 0.8

                election_weights[provider] = weight
                logger.debug(f"FeedbackBridge market→routing: {provider} weight={weight:.2f} (budget={budget_used:.0%})")

            # Inject into election system
            if hasattr(election_system, 'economic_weights'):
                election_system.economic_weights = election_weights

            return election_weights
        except Exception as e:
            logger.debug(f"FeedbackBridge market→routing: {e}")
            return {}


# ── Singleton ──

_bridge: Optional[FeedbackBridge] = None


def get_feedback_bridge() -> FeedbackBridge:
    global _bridge
    if _bridge is None:
        _bridge = FeedbackBridge()
    return _bridge
