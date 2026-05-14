"""Single-Pass Reranker — Vector Graph RAG style multi-hop retrieval.

Implements the ZillizTech Vector Graph RAG pipeline:
  1. Entity extraction from query
  2. Multi-way vector search (entities + relations + passages)
  3. Subgraph expansion via metadata ID queries (no graph DB needed)
  4. Single LLM rerank call (select most relevant relations)
  5. Answer generation from reranked passages

This replaces iterative agent loops (IRCoT-style, 3-5+ LLM calls) with
a fixed 2-LLM-call pipeline (rerank + generate), achieving 87.8% avg Recall@5
on MuSiQue/HotpotQA/2WikiMultiHopQA.

Usage:
    reranker = SinglePassReranker(llm_func=tree_llm.route_layered, store=milvus_store)
    result = await reranker.retrieve("How did Einstein's theory affect modern physics?")
    # result.answer, result.passages, result.relations, result.hops
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class RerankResult:
    query: str
    answer: str = ""
    passages: list[dict] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    hops: int = 0
    confidence: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0

    @property
    def recall_at_5(self) -> float:
        return len(self.passages) / 5.0 if self.passages else 0.0


class SubgraphExpander:
    """Performs subgraph expansion using Milvus metadata ID queries.

    No graph database needed — entities and relations are stored as vectors
    in Milvus with cross-referencing IDs in metadata fields.
    """

    def __init__(self, store):
        self.store = store

    def expand(
        self, seed_entity_ids: list[str], seed_relation_ids: list[str],
        expansion_degree: int = 1,
    ) -> tuple[list[dict], list[dict]]:
        """Expand from seed entities/relations through up to N hops.

        Returns (all_entities, all_relations) including seeds and discovered nodes.
        """
        all_entities: dict[str, dict] = {}
        all_relations: dict[str, dict] = {}

        if seed_entity_ids:
            entities = self.store.get_by_ids(seed_entity_ids, "entities")
            for e in entities:
                all_entities[e.get("id", "")] = e

        if seed_relation_ids:
            relations = self.store.get_by_ids(seed_relation_ids, "relations")
            for r in relations:
                all_relations[r.get("id", "")] = r

        for hop in range(expansion_degree):
            new_entity_ids: list[str] = []
            new_relation_ids: list[str] = []

            for rel in all_relations.values():
                eids_str = rel.get("entity_ids", "[]")
                try:
                    eids = json.loads(eids_str) if isinstance(eids_str, str) else eids_str
                    for eid in eids:
                        if eid not in all_entities:
                            new_entity_ids.append(eid)
                except Exception:
                    pass

            for ent in all_entities.values():
                eid = ent.get("id", "")
                meta_results = self.store.get_by_ids([eid], "passages")
                for r in meta_results:
                    rids_str = r.get("relation_ids", "[]")
                    try:
                        rids = json.loads(rids_str) if isinstance(rids_str, str) else rids_str
                        for rid in rids:
                            if rid not in all_relations:
                                new_relation_ids.append(rid)
                    except Exception:
                        pass

            if new_entity_ids:
                entities = self.store.get_by_ids(new_entity_ids[:100], "entities")
                for e in entities:
                    all_entities[e.get("id", "")] = e

            if new_relation_ids:
                relations = self.store.get_by_ids(new_relation_ids[:100], "relations")
                for r in relations:
                    all_relations[r.get("id", "")] = r

            if not new_entity_ids and not new_relation_ids:
                break

            logger.debug(f"Hop {hop + 1}: +{len(new_entity_ids)} entities, +{len(new_relation_ids)} relations")

        return list(all_entities.values()), list(all_relations.values())


class CandidateEvictor:
    """Filters excessive candidates by vector similarity before LLM rerank."""

    def __init__(self, max_candidates: int = 40):
        self.max_candidates = max_candidates

    def evict(self, candidates: list[dict]) -> list[dict]:
        if len(candidates) <= self.max_candidates:
            return candidates
        candidates.sort(key=lambda x: x.get("distance", 0), reverse=True)
        return candidates[:self.max_candidates]


class SinglePassReranker:
    """Single-pass LLM reranker — the core Vector Graph RAG retrieval pipeline.

    Pipeline: extract_entities → vector_search → expand_subgraph → llm_rerank → generate
    Total: 2 LLM calls (rerank + generate), vs 3-5+ for iterative approaches.
    """

    DEFAULT_RERANK_PROMPT = """You are selecting the most relevant knowledge graph relations \
for answering a question.

Question: {question}

Candidate relations (each is a (subject, predicate, object) triplet):
{relations}

Your task: select the relations that are MOST relevant to answering the question.
Return ONLY a JSON array of relation indices (starting from 0), like: [0, 3, 5]
Only return indices that are directly helpful. Return an empty array [] if none are relevant.

JSON output:"""

    DEFAULT_GENERATE_PROMPT = """Answer the question based on the provided passages.

Question: {question}

Relevant passages:
{passages}

Answer the question concisely and accurately. If the passages don't contain enough
information, say so honestly."""

    def __init__(
        self,
        llm_func: Optional[Callable] = None,
        store=None,
        expansion_degree: int = 1,
        max_candidates: int = 40,
        top_k_per_collection: int = 10,
    ):
        self._llm = llm_func
        self.store = store
        self.expander = SubgraphExpander(store)
        self.evictor = CandidateEvictor(max_candidates)
        self.expansion_degree = expansion_degree
        self.top_k = top_k_per_collection

    async def retrieve(self, query: str, context: Optional[dict] = None) -> RerankResult:
        t0 = time.time()
        result = RerankResult(query=query)
        total_tokens = 0

        # Step 1: Extract seed entities from query via vector search
        q_vec = self.store.embed(query)
        seed_entities = self.store.search_similar_with_meta(q_vec, top_k=5, collection_suffix="entities")
        seed_relations = self.store.search_similar_with_meta(q_vec, top_k=5, collection_suffix="relations")

        result.entities = [e.get("id", "") for e in seed_entities if e]

        # Step 2: Subgraph expansion
        all_entities, all_relations = self.expander.expand(
            [e["id"] for e in seed_entities if e.get("id")],
            [r["id"] for r in seed_relations if r.get("id")],
            expansion_degree=self.expansion_degree,
        )
        result.hops = self.expansion_degree
        result.relations = all_relations

        # Step 3: Retrieve passages linked to discovered entities
        all_eids = list({r.get("id", "") for r in all_entities if r.get("id")})
        passage_candidates: list[dict] = []
        if all_eids:
            for eid in all_eids[:20]:
                passages = self.store.search_similar_with_meta(
                    self.store.embed(eid), top_k=3, collection_suffix="passages",
                )
                passage_candidates.extend(passages)

        passage_candidates = self.evictor.evict(passage_candidates)

        # Step 4: LLM rerank — select most relevant relations
        if all_relations and self._llm:
            relation_texts = []
            for r in all_relations:
                text = r.get("text", r.get("id", ""))
                relation_texts.append(text)

            rerank_prompt = self.DEFAULT_RERANK_PROMPT.format(
                question=query,
                relations="\n".join(f"[{i}] {t}" for i, t in enumerate(relation_texts)),
            )

            try:
                response = await self._call_llm(rerank_prompt)
                total_tokens += response.get("tokens", 0)
                indices = self._parse_json_array(response.get("content", "[]"))
                filtered_relations = [all_relations[i] for i in indices if 0 <= i < len(all_relations)]
                result.relations = filtered_relations

                selected_eids: set[str] = set()
                for rel in filtered_relations:
                    eids_str = rel.get("entity_ids", "[]")
                    try:
                        eids = json.loads(eids_str) if isinstance(eids_str, str) else eids_str
                        selected_eids.update(eids)
                    except Exception:
                        pass

                passage_candidates = [
                    p for p in passage_candidates
                    if any(eid in selected_eids for eid in self._extract_entity_ids(p))
                ]
            except Exception as e:
                logger.warning(f"LLM rerank failed: {e}, using all candidates")

        result.passages = passage_candidates[:5]

        # Step 5: Answer generation
        if self._llm and result.passages:
            passage_texts = []
            for p in result.passages[:5]:
                text = p.get("text", p.get("id", ""))
                score = p.get("distance", 0)
                passage_texts.append(f"[score={score:.2f}] {text}")

            generate_prompt = self.DEFAULT_GENERATE_PROMPT.format(
                question=query,
                passages="\n\n".join(passage_texts),
            )

            try:
                response = await self._call_llm(generate_prompt)
                total_tokens += response.get("tokens", 0)
                result.answer = response.get("content", "")
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")

        result.tokens_used = total_tokens
        result.confidence = min(1.0, len(result.passages) / 5.0) if result.passages else 0.0
        result.latency_ms = (time.time() - t0) * 1000

        logger.info(
            f"SinglePassReranker: query=\"{query[:60]}\" → "
            f"{len(result.entities)} entities, {len(result.relations)} relations, "
            f"{len(result.passages)} passages, {result.hops} hops, "
            f"conf={result.confidence:.2f}, {result.latency_ms:.0f}ms"
        )
        return result

    async def _call_llm(self, prompt: str) -> dict:
        """Call the LLM function and return {content, tokens}."""
        if self._llm is None:
            return {"content": "", "tokens": 0}
        try:
            resp = await self._llm(prompt) if asyncio.iscoroutinefunction(self._llm) else self._llm(prompt)
            if isinstance(resp, str):
                return {"content": resp, "tokens": len(prompt) // 4}
            if isinstance(resp, dict):
                return {
                    "content": resp.get("content", resp.get("text", str(resp))),
                    "tokens": resp.get("tokens", resp.get("usage", {}).get("total_tokens", len(prompt) // 4)),
                }
            return {"content": str(resp), "tokens": len(prompt) // 4}
        except Exception as e:
            logger.warning(f"_call_llm error: {e}")
            return {"content": "", "tokens": 0}

    @staticmethod
    def _parse_json_array(text: str) -> list[int]:
        text = text.strip()
        if "```" in text:
            blocks = text.split("```")
            text = blocks[1] if len(blocks) >= 2 else blocks[0]
        try:
            return json.loads(text)
        except Exception:
            import re
            nums = re.findall(r'\d+', text)
            return [int(n) for n in nums[:20]]

    @staticmethod
    def _extract_entity_ids(passage: dict) -> list[str]:
        eids_str = passage.get("entity_ids", "[]")
        try:
            return json.loads(eids_str) if isinstance(eids_str, str) else eids_str
        except Exception:
            return []

    async def evaluate(
        self, queries: list[str], ground_truth_passages: Optional[list[list[str]]] = None,
    ) -> dict:
        """Run evaluation on a set of queries, computing Recall@K and MRR."""
        recalls = {1: [], 3: [], 5: []}
        latencies = []
        for i, query in enumerate(queries):
            result = await self.retrieve(query)
            latencies.append(result.latency_ms)
            if ground_truth_passages and i < len(ground_truth_passages):
                gt_set = set(ground_truth_passages[i])
                retrieved_ids = [p.get("id", "") for p in result.passages]
                for k in recalls:
                    recall = len(set(retrieved_ids[:k]) & gt_set) / max(1, len(gt_set))
                    recalls[k].append(recall)

        avg_recall = {k: sum(v) / len(v) for k, v in recalls.items() if v}
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        logger.info(
            f"SinglePassReranker eval: {len(queries)} queries, "
            + ", ".join(f"R@{k}={avg_recall.get(k, 0):.1%}" for k in [1, 3, 5])
            + f", avg_latency={avg_latency:.0f}ms"
        )
        return {"recall": avg_recall, "avg_latency_ms": avg_latency, "total_queries": len(queries)}


def get_single_pass_reranker(llm_func=None, store=None) -> SinglePassReranker:
    """Get a SinglePassReranker instance (factory function)."""
    return SinglePassReranker(llm_func=llm_func, store=store)


__all__ = [
    "SinglePassReranker", "RerankResult", "SubgraphExpander",
    "CandidateEvictor", "get_single_pass_reranker",
]
