# -*- coding: utf-8 -*-
"""Context glossary for LivingTree Agents.

DomainTerm defines a vocabulary item used to align language models with
project-specific terminology. ContextGlossary provides utilities to seed,
persist, and query terms, and to export context blocks for prompts.
"""

from __future__ import annotations

import re
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger
from pydantic import BaseModel, Field


class DomainTerm(BaseModel):
    term: str
    category: str
    definition: str
    aliases: List[str] = Field(default_factory=list)
    related_terms: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    priority: int = 0

    class Config:
        extra = "ignore"


class ContextGlossary:
    BASE_DIR = Path(".livingtree")
    GLOSSARY_DIR = BASE_DIR / "glossary"
    GLOSSARY_FILE = GLOSSARY_DIR / "glossary.json"

    def __init__(self) -> None:
        # Ensure storage directories exist
        self.GLOSSARY_DIR.mkdir(parents=True, exist_ok=True)
        # Internal storage: term -> DomainTerm
        self._terms: Dict[str, DomainTerm] = {}
        self._load_glossary()
        if not self._terms:
            self._seed_defaults()
            self._save_glossary()

        # Simple alias index for quick lookups: alias -> canonical term
        self._aliases: Dict[str, str] = {}
        self._rebuild_alias_index()

    # Persistence
    def _load_glossary(self) -> None:
        if self.GLOSSARY_FILE.exists():
            try:
                import json
                data = json.loads(self.GLOSSARY_FILE.read_text(encoding="utf-8"))
                terms = data.get("terms", {})
                for key, val in terms.items():
                    try:
                        self._terms[key] = DomainTerm(**val)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Skipping invalid term during load: %s", key, exc)
            except Exception as exc:
                logger.warning("Failed to load glossary: %s", exc)

    def _save_glossary(self) -> None:
        try:
            import json
            data = {
                "terms": {term.term: term.dict() for term in self._terms.values()}
            }
            self.GLOSSARY_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Failed to save glossary: %s", exc)

    def _seed_defaults(self) -> None:
        logger.info("Seeding default glossary terms...")
        self.register(
            term="SOLID",
            definition="A set of five design principles for object-oriented software design: Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
            category="architecture",
            aliases=["s.o.l.i.d."],
            related_terms=["Dependency Injection", "Monolith", "Microservices"],
            examples=["A SOLID class should have a single reason to change.", "SOLID helps modularize software."],
            priority=3,
        )
        self.register(
            term="Dependency Injection",
            definition="A pattern where an object receives its dependencies from an external source rather than creating them itself.",
            category="architecture",
            related_terms=["Inversion of Control"],
            examples=["Use constructor injection to provide a repository."],
            priority=3,
        )
        self.register(
            term="Monolith",
            definition="A single, unified codebase and deployment unit where components are interdependent.",
            category="architecture",
            aliases=["monolith"] ,
            related_terms=["Microservices"],
            priority=2,
        )
        self.register(
            term="Microservices",
            definition="Architecture style that builds an app as a collection of small services, each running in its own process.",
            category="architecture",
            related_terms=["Monolith"],
            priority=2,
        )
        self.register(
            term="Event-Driven",
            definition="Architecture where services communicate via events, enabling loose coupling.",
            category="architecture",
            related_terms=["Message Bus"],
            priority=2,
        )
        # Testing terms
        self.register(
            term="Unit Test",
            definition="A test of a small, isolated piece of code (a function or method).",
            category="testing",
            aliases=["unit tests"],
            priority=2,
        )
        self.register(
            term="Integration Test",
            definition="Tests that verify interactions between components or services.",
            category="testing",
            priority=2,
        )
        self.register(
            term="TDD",
            definition="Test-Driven Development: write tests before implementation to drive design.",
            category="testing",
            priority=1,
        )
        self.register(
            term="BDD",
            definition="Behavior-Driven Development: focuses on user behavior specifications.",
            category="testing",
            priority=1,
        )
        self.register(
            term="Code Coverage",
            definition="A measure of how much source code is executed when tests run.",
            category="testing",
            priority=1,
        )
        # Data terms
        self.register(
            term="ORM",
            definition="Object-Relational Mapping: maps between in-memory objects and database tables.",
            category="data",
            aliases=["Object Relational Mapper"],
            priority=2,
        )
        self.register(
            term="Migration",
            definition="Database schema evolution tooling to apply, rollback, or track changes.",
            category="data",
            priority=2,
        )
        self.register(
            term="Schema",
            definition="Database schema: tables, columns, types, constraints; describes data shape.",
            category="data",
            priority=2,
        )
        self.register(
            term="ACID",
            definition="Atomicity, Consistency, Isolation, Durability: guarantees for transactions.",
            category="data",
            priority=2,
        )
        self.register(
            term="Eventual Consistency",
            definition="Consistency model where updates propagate over time until all nodes converge.",
            category="data",
            priority=1,
        )
        # AI / Agent terms
        self.register(
            term="Prompt",
            definition="Instruction or query given to an AI model to elicit a response.",
            category="ai",
            priority=2,
        )
        self.register(
            term="Context Window",
            definition="The amount of text the model can consider when generating a response.",
            category="ai",
            priority=2,
        )
        self.register(
            term="Hallucination",
            definition="When a model generates plausible-sounding but incorrect or ungrounded information.",
            category="ai",
            priority=2,
        )
        self.register(
            term="RAG",
            definition="Retrieval-Augmented Generation: uses external data retrieval to improve answers.",
            category="ai",
            priority=2,
        )
        self.register(
            term="Embedding",
            definition="Vector representation of text used for similarity search and retrieval.",
            category="ai",
            priority=2,
        )
        # Networking terms
        self.register(
            term="REST",
            definition="Representational State Transfer: architectural style for networked services.",
            category="networking",
            priority=2,
        )
        self.register(
            term="GraphQL",
            definition="Query language and runtime for APIs enabling clients to request exact data.",
            category="networking",
            priority=2,
        )
        self.register(
            term="WebSocket",
            definition="Protocol providing full-duplex communication channels over a single TCP connection.",
            category="networking",
            priority=1,
        )
        self.register(
            term="gRPC",
            definition="RPC framework that uses HTTP/2 for high-performance communication.",
            category="networking",
            priority=1,
        )
        self.register(
            term="CORS",
            definition="Cross-Origin Resource Sharing: allows restricted resources on a web page to be requested from another domain.",
            category="networking",
            priority=1,
        )

    # Public API
    def register(self, term: str, definition: str, category: str, **kwargs) -> DomainTerm:
        data = {
            "term": term,
            "category": category,
            "definition": definition,
            "aliases": kwargs.get("aliases", []),
            "related_terms": kwargs.get("related_terms", []),
            "examples": kwargs.get("examples", []),
            "priority": kwargs.get("priority", 0),
        }
        t = DomainTerm(**data)
        self._terms[term] = t
        self._rebuild_alias_index()
        self._save_glossary()
        return t

    def get(self, term: str) -> Optional[DomainTerm]:
        key = None
        for k in self._terms:
            if k.lower() == term.lower():
                key = k
                break
        if key and key in self._terms:
            return self._terms[key]
        alias = self._aliases.get(term.lower())
        if alias:
            return self._terms.get(alias)
        return None

    def search(self, query: str) -> List[DomainTerm]:
        q = query.lower()
        results: List[tuple[int, DomainTerm]] = []
        for t in self._terms.values():
            score = 0
            if q in t.term.lower():
                score += 6
            if any(q in a.lower() for a in t.aliases):
                score += 4
            if q in t.definition.lower():
                score += 5
            if any(q in r.lower() for r in t.related_terms):
                score += 2
            if score:
                results.append((score, t))
        results.sort(key=lambda x: (x[0], x[1].priority), reverse=True)
        return [t for _, t in results]

    def list_by_category(self, category: str) -> List[DomainTerm]:
        cat = category.lower()
        return [t for t in self._terms.values() if t.category.lower() == cat]

    def get_context_for_task(self, task_description: str) -> str:
        relevant = self.search(task_description)
        lines = ["## Domain Context"]
        for t in relevant[:5]:
            aliases = f" (aliases: {', '.join(t.aliases)})" if t.aliases else ""
            line = f"- {t.term} [{t.category}]: {t.definition}{aliases}"
            lines.append(line)
        return "\n".join(lines)

    def export_for_agent(self, terms: List[str]) -> str:
        blocks: List[str] = []
        for name in terms:
            t = self.get(name)
            if not t:
                continue
            aliases = f"Aliases: {', '.join(t.aliases)}" if t.aliases else "Aliases: none"
            blocks.append(f"- {t.term} ({t.category}): {t.definition} [{aliases}]")
        if not blocks:
            return ""
        return "## Domain Glossary Block\n" + "\n".join(blocks)

    def add_alias(self, term: str, alias: str) -> bool:
        t = self.get(term)
        if not t:
            return False
        if alias not in t.aliases:
            t.aliases.append(alias)
            self._save_glossary()
        return True

    def add_relationship(self, term_a: str, term_b: str) -> bool:
        ta = self.get(term_a)
        tb = self.get(term_b)
        if not ta or not tb:
            return False
        if tb.term not in ta.related_terms:
            ta.related_terms.append(tb.term)
        if ta.term not in tb.related_terms:
            tb.related_terms.append(ta.term)
        self._save_glossary()
        return True

    def get_glossary_graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for t in self._terms.values():
            graph[t.term] = list(t.related_terms)
        return graph

    def remove(self, term: str) -> bool:
        if term in self._terms:
            del self._terms[term]
            # Clean up aliases
            self._rebuild_alias_index()
            # Remove appearances in other terms' relationships
            for t in self._terms.values():
                if term in t.related_terms:
                    t.related_terms.remove(term)
            self._save_glossary()
            return True
        return False

    def clear(self) -> None:
        self._terms = {}
        self._rebuild_alias_index()
        self._save_glossary()

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for t in self._terms.values():
            counts[t.category] = counts.get(t.category, 0) + 1
        return counts

    # ── Incremental & Regex Search (Clibor-inspired) ──

    def search_incremental(self, query: str) -> List[DomainTerm]:
        """Incremental search — returns terms whose term/definition starts with query prefix.

        Useful for real-time filtering as user types character by character.
        Each additional character narrows results.
        """
        if not query:
            return []
        qlower = query.lower()
        results: List[tuple[int, DomainTerm]] = []
        for t in self._terms.values():
            score = 0
            if t.term.lower().startswith(qlower):
                score = 10
            elif qlower in t.term.lower():
                score = 6
            elif any(a.lower().startswith(qlower) for a in t.aliases):
                score = 5
            elif qlower in t.definition.lower():
                score = 3
            if score:
                results.append((score, t))
        results.sort(key=lambda x: (x[0], x[1].priority), reverse=True)
        return [t for _, t in results]

    def search_regex(self, pattern: str, fields: List[str] | None = None) -> List[DomainTerm]:
        """Regex search across term fields.

        fields: which fields to search (default: ["term", "definition", "aliases", "related_terms"])
        Returns terms matching the regex pattern.
        """
        import re as _re
        try:
            regex = _re.compile(pattern, _re.IGNORECASE)
        except _re.error as e:
            logger.warning(f"Invalid regex '{pattern}': {e}")
            return []
        targets = fields or ["term", "definition", "aliases", "related_terms"]
        results: List[DomainTerm] = []
        for t in self._terms.values():
            for field in targets:
                if field == "aliases":
                    texts = t.aliases
                elif field == "related_terms":
                    texts = t.related_terms
                elif field == "examples":
                    texts = t.examples
                else:
                    texts = [getattr(t, field, "")]
                for text in texts:
                    if regex.search(text):
                        results.append(t)
                        break
                else:
                    continue
                break
        return results

    def search_combined(self, query: str, use_regex: bool = False,
                        fields: List[str] | None = None) -> List[DomainTerm]:
        """Unified search: regex if use_regex=True, otherwise incremental then fuzzy fallback."""
        if use_regex:
            return self.search_regex(query, fields)
        inc = self.search_incremental(query)
        if inc:
            return inc
        return self.search(query)

    # Helpers
    def _rebuild_alias_index(self) -> None:
        self._aliases = {}
        for t in self._terms.values():
            for a in t.aliases:
                self._aliases[a.lower()] = t.term

    def __repr__(self) -> str:  # pragma: no cover
        return f"ContextGlossary(terms={len(self._terms)})"


# Singleton instance for convenient import
GLOSSARY = ContextGlossary()
