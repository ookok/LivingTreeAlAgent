from loguru import logger
from pydantic import BaseModel, Field, validator
from enum import StrEnum
from typing import List, Dict, Optional


class CapabilityBucket(StrEnum):
    REASONING = "reasoning"
    CODE = "code"
    DOCUMENT = "document"
    KNOWLEDGE = "knowledge"
    NETWORK = "network"
    TOOL = "tool"
    EVOLUTION = "evolution"
    INTEGRATION = "integration"
    QUALITY = "quality"
    SYSTEM = "system"


class SkillEntry(BaseModel):
    module_name: str
    bucket: CapabilityBucket
    description: str
    keywords: List[str] = Field(default_factory=list)
    maturity: str = "stable"
    dependencies: List[str] = Field(default_factory=list)
    enabled_by_default: bool = True

    @validator("maturity")
    def _validate_maturity(cls, v: str) -> str:
        allowed = {"experimental", "stable", "core"}
        if v not in allowed:
            raise ValueError(f"maturity must be one of {allowed}, got: {v}")
        return v


class SkillCatalog:
    def __init__(self) -> None:
        self._entries: List[SkillEntry] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        def add(module_name: str, bucket: CapabilityBucket, description: str,
                keywords: List[str], maturity: str = "stable",
                dependencies: Optional[List[str]] = None,
                enabled_by_default: bool = True) -> None:
            if dependencies is None:
                dependencies = []
            self._entries.append(
                SkillEntry(
                    module_name=module_name,
                    bucket=bucket,
                    description=description,
                    keywords=keywords,
                    maturity=maturity,
                    dependencies=dependencies,
                    enabled_by_default=enabled_by_default,
                )
            )

        # REASONING
        add("adaptive_practice", CapabilityBucket.REASONING,
            "Adaptive practice for planning and strategic thinking.",
            ["planning", "strategy", "analysis"], maturity="stable")
        add("progressive_trust", CapabilityBucket.REASONING,
            "Incremental trust & verification for decisions.",
            ["trust", "verification", "decision"], maturity="stable")
        add("idle_consolidator", CapabilityBucket.REASONING,
            "Consolidates idle thoughts into actionable plans.",
            ["consolidate", "planning"], maturity="stable")
        add("self_modifier", CapabilityBucket.REASONING,
            "Self-improvement and policy adjustment for agents.",
            ["self", "modify", "adapt"], maturity="stable")

        # CODE
        add("ast_parser", CapabilityBucket.CODE,
            "Abstract syntax tree parser and code analysis tools.",
            ["parser", "AST", "syntax"], maturity="stable")
        add("code_engine", CapabilityBucket.CODE,
            "Code generation and transformation engine.",
            ["generator", "transformation"], maturity="stable")
        add("code_graph", CapabilityBucket.CODE,
            "Code graph analytics for dependencies and impact.",
            ["graph", "dependencies"], maturity="stable")
        add("content_dedup", CapabilityBucket.CODE,
            "Deduplication and normalization for code content.",
            ["dedup", "normalization"], maturity="stable")
        add("semantic_diff", CapabilityBucket.CODE,
            "Semantic diffing for code changes and reviews.",
            ["diff", "diffing"], maturity="stable")
        add("tool_synthesis", CapabilityBucket.CODE,
            "Synthesize tools for code-related automation.",
            ["tools", "automation"], maturity="stable")

        # DOCUMENT
        add("doc_engine", CapabilityBucket.DOCUMENT,
            "Document processing engine for templates and reports.",
            ["document", "template", "report"], maturity="stable")
        add("document_editor", CapabilityBucket.DOCUMENT,
            "Rich document editor integration and rendering.",
            ["edit", "editors"], maturity="stable")
        add("document_processor", CapabilityBucket.DOCUMENT,
            "Document processing and normalization pipelines.",
            ["processor", "pipeline"], maturity="stable")
        add("industrial_doc_engine", CapabilityBucket.DOCUMENT,
            "Industrial-grade docs pipeline for enterprise templates.",
            ["enterprise", "templates"], maturity="stable")
        add("template_engine", CapabilityBucket.DOCUMENT,
            "Template engine for standardized documents.",
            ["template", "render"], maturity="stable")

        # KNOWLEDGE
        add("knowledge_quality", CapabilityBucket.KNOWLEDGE,
            "Knowledge quality metrics and governance.",
            ["knowledge", "governance"], maturity="stable")
        add("extraction_engine", CapabilityBucket.KNOWLEDGE,
            "Extract structured data from unstructured sources.",
            ["extract", "NER", "parsing"], maturity="stable")
        add("data_lineage", CapabilityBucket.KNOWLEDGE,
            "Track data lineage across pipelines.",
            ["lineage", "traceability"], maturity="stable")
        add("universal_parser", CapabilityBucket.KNOWLEDGE,
            "Unified parser for multiple data formats.",
            ["parser", "universal"], maturity="stable")
        add("multimodal_parser", CapabilityBucket.KNOWLEDGE,
            "Parse multimodal inputs for knowledge graphs.",
            ["multimodal", "parser"], maturity="stable")

        # NETWORK
        add("network_brain", CapabilityBucket.NETWORK,
            "Distributed coordination and network reasoning.",
            ["network", "coordination"], maturity="stable")
        add("remote_assist", CapabilityBucket.NETWORK,
            "Remote assistance and collaboration framework.",
            ["remote", "assist"], maturity="stable")

        # TOOL
        add("tool_executor", CapabilityBucket.TOOL,
            "Execute and orchestrate tools dynamically.",
            ["execute", "orchestrate"], maturity="stable")
        add("tool_market", CapabilityBucket.TOOL,
            "Marketplace for tools and integrations.",
            ["market", "integration"], maturity="stable")
        add("tool_meta", CapabilityBucket.TOOL,
            "Tool metadata and discovery layer.",
            ["metadata", "discovery"], maturity="stable")
        add("tool_orchestrator", CapabilityBucket.TOOL,
            "Orchestration layer for complex toolchains.",
            ["orchestrate", "pipeline"], maturity="stable")
        add("skill_factory", CapabilityBucket.TOOL,
            "Factory for skill composition and wiring.",
            ["factory", "composition"], maturity="stable")
        add("skill_discovery", CapabilityBucket.TOOL,
            "Discover and map skill capabilities.",
            ["discover", "mapping"], maturity="stable")
        add("unified_file_tool", CapabilityBucket.TOOL,
            "Unified tooling for file operations.",
            ["file", "tooling"], maturity="stable")
        add("patch_manager", CapabilityBucket.TOOL,
            "Patch management for tooling updates.",
            ["patch", "update"], maturity="stable")
        add("file_watcher", CapabilityBucket.TOOL,
            "Watch files for changes and trigger tooling.",
            ["watcher", "filesystem"], maturity="stable")

        # EVOLUTION
        add("self_discovery", CapabilityBucket.EVOLUTION,
            "Self-discovery loop for capabilities.",
            ["self", "discovery"], maturity="stable")
        add("self_documentation", CapabilityBucket.EVOLUTION,
            "Auto-documentation of capabilities.",
            ["documentation", "auto"], maturity="stable")
        add("domain_transfer", CapabilityBucket.EVOLUTION,
            "Transfer domain knowledge between contexts.",
            ["transfer", "domain"], maturity="stable")
        add("memory_pipeline", CapabilityBucket.EVOLUTION,
            "Memory-driven pipeline for learning.",
            ["memory", "learning"], maturity="stable")
        add("conversation_branch", CapabilityBucket.EVOLUTION,
            "Branching strategies for conversations.",
            ["branch", "dialogue"], maturity="stable")
        add("session_continuity", CapabilityBucket.EVOLUTION,
            "Maintain session continuity across tasks.",
            ["session", "continuity"], maturity="stable")

        # INTEGRATION
        add("ddg_search", CapabilityBucket.INTEGRATION,
            "DuckDuckGo search integration.",
            ["search", "web"], maturity="stable")
        add("spark_search", CapabilityBucket.INTEGRATION,
            "Spark-based search and indexing.",
            ["search", "index"], maturity="stable")
        add("tianditu", CapabilityBucket.INTEGRATION,
            "Tianditu mapping integration.",
            ["maps", "maps api"], maturity="stable")
        add("web_reach", CapabilityBucket.INTEGRATION,
            "Web reachability and crawling utilities.",
            ["crawl", "web"], maturity="stable")
        add("unified_search", CapabilityBucket.INTEGRATION,
            "Unified search across sources.",
            ["search", "integration"], maturity="stable")

        # QUALITY
        add("semantic_backup", CapabilityBucket.QUALITY,
            "Backup strategies focused on semantic context.",
            ["backup", "semantic"], maturity="stable")
        add("pipeline_engine", CapabilityBucket.QUALITY,
            "Pipeline engine for quality assurance tasks.",
            ["pipeline", "quality"], maturity="stable")

        # SYSTEM
        add("material_collector", CapabilityBucket.SYSTEM,
            "Collect and organize materials for processing.",
            ["collection", "material"], maturity="stable")

        logger.debug("SkillCatalog initialized with {} entries.", len(self._entries))

    def get_bucket(self, bucket: CapabilityBucket) -> List[SkillEntry]:
        return [e for e in self._entries if e.bucket == bucket]

    def get_skill(self, module_name: str) -> Optional[SkillEntry]:
        for e in self._entries:
            if e.module_name == module_name:
                return e
        return None

    def search(self, query: str) -> List[SkillEntry]:
        q = query.lower()
        results: List[SkillEntry] = []
        for e in self._entries:
            if q in e.module_name.lower() or q in e.description.lower() or any(q in kw.lower() for kw in e.keywords):
                results.append(e)
        return results

    def get_bucket_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {b.value: 0 for b in CapabilityBucket}
        for e in self._entries:
            summary[e.bucket.value] = summary.get(e.bucket.value, 0) + 1
        return summary

    def get_routing_priority(self, task_description: str) -> List[CapabilityBucket]:
        text = task_description.lower()
        bucket_keywords = {
            CapabilityBucket.REASONING: ["plan", "design", "strategy", "analysis", "decision"],
            CapabilityBucket.CODE: ["code", "generate", "parser", "ast", "compile", "refactor"],
            CapabilityBucket.DOCUMENT: ["document", "report", "template", "edit"],
            CapabilityBucket.KNOWLEDGE: ["knowledge", "search", "graph", "data", "lineage"],
            CapabilityBucket.NETWORK: ["network", "remote", "communication", "peer"],
            CapabilityBucket.TOOL: ["tool", "execute", "automation", "orchestrate", "pipeline"],
            CapabilityBucket.EVOLUTION: ["learn", "adapt", "self", "memory"],
            CapabilityBucket.INTEGRATION: ["api", "integration", "service", "web"],
            CapabilityBucket.QUALITY: ["test", "validate", "quality", "verify"],
            CapabilityBucket.SYSTEM: ["config", "setup", "initialize", "bootstrap"],
        }
        scores: Dict[CapabilityBucket, int] = {b: 0 for b in bucket_keywords}
        for bucket, keys in bucket_keywords.items():
            for kw in keys:
                if kw in text:
                    scores[bucket] += text.count(kw)
        ranked = [b for b, s in sorted(scores.items(), key=lambda kv: kv[1], reverse=True) if s > 0]
        if not ranked:
            ranked = [CapabilityBucket.KNOWLEDGE, CapabilityBucket.CODE]
        return ranked

    def get_module_names_for_bucket(self, bucket: CapabilityBucket) -> List[str]:
        return [e.module_name for e in self._entries if e.bucket == bucket]

    def suggest_skills(self, task_description: str, top_k: int = 5) -> List[SkillEntry]:
        ranking = self.get_routing_priority(task_description)
        text = task_description.lower()
        scored: List[tuple[int, SkillEntry]] = []
        for e in self._entries:
            score = 0
            if e.bucket in ranking:
                score += 10
            if e.module_name.lower() in text:
                score += 20
            for kw in e.keywords:
                if kw.lower() in text:
                    score += 5
            if e.description.lower() in text:
                score += 2
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def export_manifest(self) -> Dict:
        return {
            "catalog_version": "0.1",
            "skills": [e.dict() for e in self._entries],
        }


# Singleton export
SKILL_CATALOG = SkillCatalog()
