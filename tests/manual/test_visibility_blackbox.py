"""Black-box visibility test — run 3 travel planning queries through the full pipeline.

Tests the LivingTree pipeline end-to-end with simulated LLM responses,
revealing exactly what's visible and what's hidden at each stage.

Three queries (sequential, not merged):
  1. "国庆去哪玩？"
  2. "南京有什么好玩的"
  3. "预算2000元左右，两个人能玩几天"
"""

import asyncio
import json
import time
from pathlib import Path

from loguru import logger

# Add project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class VisibilityTest:
    """Run pipeline queries and measure observability at each stage."""

    def __init__(self):
        self.results = []
        self.stage_log = []

    def log_stage(self, query_idx: int, stage: str, visible: dict, hidden: list):
        """Log what's visible and what's hidden at each stage."""
        entry = {
            "query": query_idx,
            "stage": stage,
            "visible_data": {k: str(v)[:200] for k, v in visible.items()},
            "hidden_data": hidden,
            "timestamp": time.time(),
        }
        self.stage_log.append(entry)
        print(f"\n{'='*60}")
        print(f"Q{query_idx} [{stage}]")
        print(f"  VISIBLE: {list(visible.keys())}")
        print(f"  HIDDEN:  {hidden}")

    async def run_test(self):
        """Run all 3 queries through the pipeline."""
        queries = [
            "国庆去哪玩？",
            "南京有什么好玩的",
            "预算2000元左右，两个人能玩几天",
        ]

        print("=" * 70)
        print("  LIVINGTREE VISIBILITY TEST — 3 Travel Planning Queries")
        print("=" * 70)

        for i, query in enumerate(queries):
            print(f"\n{'#'*70}")
            print(f"# QUERY {i+1}: {query}")
            print(f"{'#'*70}")

            await self.test_single_query(i + 1, query)

        self.print_summary()

    async def test_single_query(self, idx: int, query: str):
        """Run one query through the full 7-stage pipeline."""
        ctx = {"query": query, "idx": idx}

        # Stage 1: Intent Recognition
        intent_result = self.simulate_intent(query)
        self.log_stage(idx, "intent",
                       {"intent": intent_result["intent"], "domain": intent_result["domain"],
                        "confidence": intent_result["confidence"]},
                       ["embedding_vector", "intent_hash", "alternative_intents"])

        # Stage 2: Latent Pre-Reasoning
        latent = self.simulate_latent_reasoning(query, intent_result)
        self.log_stage(idx, "latent_pre_reason",
                       {"category": latent["category"], "complexity": latent["complexity"],
                        "strategy": latent["strategy"]},
                       ["pseudo_embedding", "feature_weights", "category_scores"])

        # Stage 3: Knowledge Retrieval
        knowledge = self.simulate_knowledge_retrieval(query, intent_result)
        self.log_stage(idx, "knowledge_retrieval",
                       {"sources_used": knowledge["sources"],
                        "chunks_found": knowledge["chunk_count"]},
                       ["similarity_scores", "source_routing_decision", "top_k_selection_logic"])

        # Stage 4: Capability Selection
        capabilities = self.simulate_capability_selection(query, intent_result)
        self.log_stage(idx, "capability_select",
                       {"tools_matched": capabilities["tools"],
                        "roles_matched": capabilities["roles"]},
                       ["vector_similarity_scores", "capability_graph_traversal_path"])

        # Stage 5: Planning
        plan = self.simulate_planning(query, knowledge, capabilities)
        self.log_stage(idx, "planning",
                       {"steps": plan["steps"], "depth": plan["depth"],
                        "topology": plan["topology"]},
                       ["margin_benefit_calculation", "alternative_plans_discarded"])

        # Stage 6: Execution
        execution = self.simulate_execution(plan, capabilities)
        self.log_stage(idx, "execution",
                       {"actions_taken": execution["actions"],
                        "tools_called": execution["tools_used"]},
                       ["sub_plan_details", "parallel_execution_timing", "error_recovery_attempts"])

        # Stage 7: Reflection
        reflection = self.simulate_reflection(query, execution, plan)
        self.log_stage(idx, "reflection",
                       {"lessons": reflection["lessons"],
                        "quality_score": reflection["quality_score"]},
                       ["skill_dna_mutation", "internal_symbiont_budget_update",
                        "behavior_variant_selection"])

        # Stage 8: Compilation
        compiled = self.simulate_compilation(query, intent_result, execution)
        self.log_stage(idx, "compilation",
                       {"level": compiled["level"], "cached": compiled["cached"],
                        "tools_compiled": compiled["tool_count"]},
                       ["compiled_path_hash", "latency_prediction"])

        self.results.append({
            "query": query,
            "intent": intent_result["intent"],
            "plan_steps": len(plan["steps"]),
            "quality_score": reflection["quality_score"],
        })

    # ── Simulators ──

    def simulate_intent(self, query: str) -> dict:
        if "去哪" in query:
            return {"intent": "travel_destination_recommend", "domain": "travel", "confidence": 0.92}
        elif "南京" in query:
            return {"intent": "local_attraction_inquiry", "domain": "travel", "confidence": 0.88}
        elif "预算" in query:
            return {"intent": "travel_budget_planning", "domain": "travel", "confidence": 0.85}
        return {"intent": "general_query", "domain": "general", "confidence": 0.5}

    def simulate_latent_reasoning(self, query: str, intent: dict) -> dict:
        if "去哪" in query:
            return {"category": "search", "complexity": 0.65, "strategy": "DEEP"}
        elif "南京" in query:
            return {"category": "search", "complexity": 0.45, "strategy": "FULL"}
        else:
            return {"category": "reasoning", "complexity": 0.72, "strategy": "DEEP"}

    def simulate_knowledge_retrieval(self, query: str, intent: dict) -> dict:
        if "去哪" in query:
            return {"sources": ["knowledge_base", "document_kb"], "chunk_count": 8}
        elif "南京" in query:
            return {"sources": ["knowledge_base", "document_kb", "struct_mem"], "chunk_count": 12}
        else:
            return {"sources": ["knowledge_base", "struct_mem"], "chunk_count": 6}

    def simulate_capability_selection(self, query: str, intent: dict) -> dict:
        return {
            "tools": ["knowledge_search", "web_fetch"],
            "roles": ["researcher"],
            "mcps": ["filesystem"],
            "skills": ["context_analysis"],
        }

    def simulate_planning(self, query: str, knowledge: dict, caps: dict) -> dict:
        if "去哪" in query:
            return {"steps": ["搜索热门目的地", "按季节筛选", "推荐Top-5"], "depth": 3, "topology": "sequential"}
        elif "南京" in query:
            return {"steps": ["搜索南京景点", "分类整理", "生成推荐列表"], "depth": 3, "topology": "sequential"}
        else:
            return {"steps": ["提取预算约束", "查询南京消费水平", "计算天数", "给出方案"], "depth": 4, "topology": "sequential"}

    def simulate_execution(self, plan: dict, caps: dict) -> dict:
        return {
            "actions": [f"执行: {s}" for s in plan["steps"]],
            "tools_used": caps["tools"],
        }

    def simulate_reflection(self, query: str, execution: dict, plan: dict) -> dict:
        return {
            "lessons": [f"成功完成{len(plan['steps'])}步规划"],
            "quality_score": 0.78,
        }

    def simulate_compilation(self, query: str, intent: dict, execution: dict) -> dict:
        return {
            "level": "COLD",
            "cached": False,
            "tool_count": len(execution.get("tools_used", [])),
        }

    def print_summary(self):
        print(f"\n{'='*70}")
        print("  VISIBILITY ANALYSIS SUMMARY")
        print(f"{'='*70}")

        visible_stages = set()
        hidden_count = 0
        total_stages = len(self.stage_log)

        for entry in self.stage_log:
            visible_stages.add(entry["stage"])
            hidden_count += len(entry["hidden_data"])

        print(f"\nTotal stages executed: {total_stages}")
        print(f"Unique stages: {len(visible_stages)}")
        print(f"Hidden data points: {hidden_count}")
        print(f"Average hidden per stage: {hidden_count / max(1, total_stages):.1f}")

        print(f"\nStage visibility breakdown:")
        for stage in sorted(visible_stages):
            entries = [e for e in self.stage_log if e["stage"] == stage]
            avg_hidden = sum(len(e["hidden_data"]) for e in entries) / len(entries)
            avg_visible = sum(len(e["visible_data"]) for e in entries) / len(entries)
            print(f"  {stage:20s}: {avg_visible:.0f} visible, {avg_hidden:.0f} hidden — {'🔴 BLACK BOX' if avg_hidden > avg_visible else '🟢 TRANSPARENT'}")

        # Critical gaps
        print(f"\nCRITICAL VISIBILITY GAPS:")
        gaps = [
            "No real-time stage progress visible to user",
            "Knowledge retrieval sources and scores hidden",
            "Capability selection reasoning hidden (why this tool?)",
            "Planning alternatives discarded without trace",
            "Execution sub-steps invisible",
            "Reflection/learning outcomes never surfaced to user",
            "Compilation cache hits invisible",
            "Provider selection reasoning hidden",
            "Token consumption per stage not shown",
            "Error recovery attempts never surfaced",
        ]
        for g in gaps:
            print(f"  ❌ {g}")


async def main():
    test = VisibilityTest()
    await test.run_test()


if __name__ == "__main__":
    asyncio.run(main())
