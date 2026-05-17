"""
Ontology-aware Prompt Builder — 本体感知的 Prompt 构建器。

遍历 SkillGraph 路径和 KnowledgeGraph 实体，自动注入概念链到 Prompt 中。
基于 EntityRegistry 实现跨层实体解析。

Usage:
    from livingtree.treellm.onto_prompt_builder import get_onto_prompt_builder
    builder = get_onto_prompt_builder()
    result = builder.build_prompt("Summarize code review findings")
    print(result["system_prompt"])
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

# Stopwords for keyword extraction (Chinese + English)
_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "and",
    "but", "or", "nor", "not", "so", "yet", "both", "either", "neither",
    "each", "every", "all", "any", "few", "more", "most", "other", "some",
    "such", "no", "only", "own", "same", "than", "too", "very", "just",
    "about", "also", "if", "then", "else", "when", "where", "why", "how",
    "this", "that", "these", "those", "what", "which", "who", "whom",
    "please", "help", "need", "want", "like", "use", "using", "make",
    "get", "find", "check", "tell", "show", "give", "explain", "write",
    "run", "test", "build", "create", "add", "remove", "update", "delete",
}


class OntoPromptBuilder:
    """Build ontology-enriched prompts by traversing LivingTree's semantic layers."""

    def __init__(
        self,
        skill_graph=None,
        knowledge_graph=None,
        glossary=None,
        entity_registry=None,
    ):
        self._skill_graph = skill_graph
        self._knowledge_graph = knowledge_graph
        self._glossary = glossary
        self._entity_registry = entity_registry
        self._deps_loaded = False

    def _ensure_dependencies(self) -> None:
        """Lazy-load ontology backends. Graceful degradation on ImportError."""
        if self._deps_loaded:
            return
        self._deps_loaded = True

        if self._glossary is None:
            try:
                from livingtree.knowledge.context_glossary import GLOSSARY
                self._glossary = GLOSSARY
            except ImportError:
                logger.debug("Glossary not available for onto-prompt")

        if self._skill_graph is None:
            try:
                from livingtree.bridge.registry import get_tool_registry  # migrated
                self._skill_graph = get_tool_registry().get('skill_buckets')
            except ImportError:
                logger.debug("SkillCatalog not available for onto-prompt")

        if self._knowledge_graph is None:
            try:
                from livingtree.knowledge.knowledge_graph import KnowledgeGraph
                self._knowledge_graph = KnowledgeGraph()
            except ImportError:
                logger.debug("KnowledgeGraph not available for onto-prompt")

        if self._entity_registry is None:
            try:
                from livingtree.core.entity_registry import ENTITY_REGISTRY
                self._entity_registry = ENTITY_REGISTRY
            except ImportError:
                logger.debug("EntityRegistry not available for onto-prompt")

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords using heuristic stopword filtering."""
        # Split on non-word characters (keep Chinese chars and alphanumeric)
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())
        keywords = []
        for token in tokens:
            if token not in _STOPWORDS and len(token) > 1:
                keywords.append(token)
        # Deduplicate while preserving order
        seen = set()
        result = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result[:20]  # Cap at 20 keywords

    def build_prompt(self, task: str, topic_kb: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Build an ontology-enriched prompt for the given task.

        Returns:
            {"system_prompt": str, "user_prompt": str, "concept_chain": list, "entities_used": list}
        """
        self._ensure_dependencies()

        keywords = self._extract_keywords(task)
        logger.debug(f"Onto-prompt keywords: {keywords}")

        entities_used: list[str] = []
        concept_chain: list[str] = []

        # Step 1: Glossary lookup
        glossary_terms: list[dict[str, str]] = []
        if self._glossary and hasattr(self._glossary, "search_incremental"):
            try:
                for kw in keywords:
                    results = self._glossary.search_incremental(kw)
                    for r in results[:3]:
                        term_name = r.get("term") or r.get("name", "")
                        if term_name and term_name not in concept_chain:
                            concept_chain.append(term_name)
                            glossary_terms.append(r)
                            entities_used.append(f"glossary:{term_name}")
            except Exception as e:
                logger.debug(f"Glossary query error: {e}")

        # Step 2: SkillGraph traversal
        skill_names: list[str] = []
        if self._skill_graph and hasattr(self._skill_graph, "search"):
            try:
                for kw in keywords:
                    skills = self._skill_graph.search(kw)
                    for s in skills[:3]:
                        name = s.get("name") or str(s)
                        if name not in concept_chain:
                            concept_chain.append(name)
                            skill_names.append(name)
                            entities_used.append(f"skill:{name}")
            except Exception as e:
                logger.debug(f"SkillGraph query error: {e}")

        # Step 3: KnowledgeGraph entities
        kg_entities: list[str] = []
        if self._knowledge_graph and hasattr(self._knowledge_graph, "entity_linking"):
            try:
                for kw in keywords[:5]:
                    entities = self._knowledge_graph.entity_linking(kw, top_k=3)
                    if isinstance(entities, list):
                        for ent in entities[:2]:
                            name = ent.get("label") or ent.get("name") or str(ent)
                            if name not in concept_chain:
                                concept_chain.append(name)
                                kg_entities.append(name)
                                entities_used.append(f"kg:{name}")
            except Exception as e:
                logger.debug(f"KnowledgeGraph query error: {e}")

        # Step 4: EntityRegistry cross-layer resolution
        if self._entity_registry and hasattr(self._entity_registry, "search"):
            try:
                for kw in keywords[:5]:
                    results = self._entity_registry.search(kw)
                    for ent in results[:2]:
                        if ent.name not in concept_chain:
                            concept_chain.append(ent.name)
                            entities_used.append(ent.id)
                        # Also pull linked entities
                        refs = self._entity_registry.get_references(ent.id)
                        for ref_id in refs:
                            ref_ent = self._entity_registry.resolve(ref_id)
                            if ref_ent and ref_ent.name not in concept_chain:
                                concept_chain.append(ref_ent.name)
                                entities_used.append(ref_ent.id)
            except Exception as e:
                logger.debug(f"EntityRegistry query error: {e}")

        # Step 5: Build system prompt
        parts = [f"## Goal\n{task}\n"]

        if concept_chain:
            parts.append("## Domain Context (from ontology)")
            parts.append(" → ".join(concept_chain) + "\n")

        if skill_names:
            parts.append("## Relevant Skills")
            for s in skill_names[:8]:
                parts.append(f"- {s}")
            parts.append("")

        if glossary_terms:
            parts.append("## Key Terminology")
            for t in glossary_terms[:5]:
                name = t.get("term") or t.get("name", "")
                desc = t.get("definition") or t.get("description", "")
                parts.append(f"- **{name}**: {desc}")
            parts.append("")

        system_prompt = "\n".join(parts)

        return {
            "system_prompt": system_prompt,
            "user_prompt": task,
            "concept_chain": concept_chain,
            "entities_used": entities_used,
        }

    def build_skill_context(self, task: str) -> str:
        """Shortcut: return skill chain text only."""
        self._ensure_dependencies()
        parts: list[str] = []
        if self._skill_graph and hasattr(self._skill_graph, "search"):
            try:
                for kw in self._extract_keywords(task):
                    skills = self._skill_graph.search(kw)
                    for s in skills[:5]:
                        name = s.get("name") or str(s)
                        parts.append(name)
            except Exception as e:
                logger.debug(f"SkillContext error: {e}")
        return ", ".join(parts[:10]) if parts else "(no relevant skills)"

    def build_glossary_context(self, task: str) -> str:
        """Shortcut: return glossary terminology text only."""
        self._ensure_dependencies()
        terms: list[str] = []
        if self._glossary and hasattr(self._glossary, "search_incremental"):
            try:
                for kw in self._extract_keywords(task):
                    results = self._glossary.search_incremental(kw)
                    for r in results[:3]:
                        name = r.get("term") or r.get("name", "")
                        definition = r.get("definition", "")
                        terms.append(f"**{name}**: {definition}" if definition else name)
            except Exception as e:
                logger.debug(f"GlossaryContext error: {e}")
        return "\n".join(terms[:8]) if terms else "(no relevant terms)"

    def enrich_prompt_template(self, template_name: str, task: str) -> dict[str, str]:
        """Merge ontology context into an existing prompt template."""
        self._ensure_dependencies()

        # Try to get existing template
        template = None
        try:
            from livingtree.treellm.prompt_versioning import PROMPT_VERSION_MANAGER
            template = PROMPT_VERSION_MANAGER.get(template_name)
        except ImportError:
            pass

        # Build ontology context
        onto = self.build_prompt(task)
        onto_context = f"## Domain Context (from ontology)\n{' → '.join(onto['concept_chain'])}\n" if onto["concept_chain"] else ""

        if template:
            system_prompt = f"{template.system_prompt}\n\n{onto_context}" if template.system_prompt else onto_context
            user_prompt = template.content.format(**{"task": task} if "{" in template.content else {})
            return {"system_prompt": system_prompt, "user_prompt": user_prompt}

        # Fallback: minimal template
        return {
            "system_prompt": onto["system_prompt"],
            "user_prompt": task,
        }

    def get_suggested_skills(self, task: str, top_k: int = 5) -> list[str]:
        """Return top-k skill names most relevant to the task."""
        self._ensure_dependencies()
        skills: list[str] = []
        if self._skill_graph and hasattr(self._skill_graph, "suggest_skills"):
            try:
                suggestions = self._skill_graph.suggest_skills(task)
                skills = [s.get("name") or str(s) for s in suggestions[:top_k]]
            except Exception as e:
                logger.debug(f"SkillSuggestion error: {e}")
        elif self._skill_graph and hasattr(self._skill_graph, "search"):
            try:
                for kw in self._extract_keywords(task):
                    results = self._skill_graph.search(kw)
                    for r in results:
                        name = r.get("name") or str(r)
                        if name not in skills:
                            skills.append(name)
            except Exception as e:
                logger.debug(f"SkillSearch error: {e}")
        return skills[:top_k]


# Singleton
ONTO_PROMPT_BUILDER = OntoPromptBuilder()


def get_onto_prompt_builder() -> OntoPromptBuilder:
    """Get the global OntoPromptBuilder singleton."""
    return ONTO_PROMPT_BUILDER
