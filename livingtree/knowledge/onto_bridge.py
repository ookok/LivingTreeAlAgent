"""
External Ontology Bridge — 外部本体绑定。

将 LivingTree 内部实体映射到外部标准本体：
- Schema.org（通用类型）
- Wikidata（实体 Q-ID）
- 行业标准（HJ/T 环保、ISO、IEEE 等）

Usage:
    from livingtree.knowledge.onto_bridge import ONTO_BRIDGE
    result = ONTO_BRIDGE.bind_entity("code:livingtree-main", "code", "LivingTreeAlAgent")
"""
from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ExternalBinding(BaseModel):
    """Binding from a LivingTree entity to an external ontology entry."""

    source_entity_id: str
    ontology: str  # schema.org, wikidata, hj_standard, iso_standard
    external_id: str
    label: str
    confidence: float = 1.0
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SchemaOrgMapper:
    """Map LivingTree entity types to Schema.org types."""

    STANDARD_TYPES: dict[str, str] = {
        "code": "SoftwareSourceCode",
        "dataset": "Dataset",
        "model": "SoftwareApplication",
        "document": "CreativeWork",
        "person": "Person",
        "organization": "Organization",
        "event": "Event",
        "api": "WebAPI",
        "skill": "HowTo",
        "knowledge": "ScholarlyArticle",
    }

    def map_entity(self, entity_type: str) -> ExternalBinding | None:
        """Direct type mapping. Returns None if no match."""
        so_type = self.STANDARD_TYPES.get(entity_type)
        if so_type:
            return ExternalBinding(
                source_entity_id="",
                ontology="schema.org",
                external_id=so_type,
                label=so_type,
                confidence=1.0,
                verified=True,
            )
        return None

    def suggest_binding(self, entity_name: str, entity_type: str) -> ExternalBinding | None:
        """Fuzzy match: try type map first, then name heuristic."""
        binding = self.map_entity(entity_type)
        if binding:
            binding.source_entity_id = entity_name
            return binding

        # Heuristic: check name for known keywords
        name_lower = entity_name.lower()
        for key, so_type in self.STANDARD_TYPES.items():
            if key in name_lower:
                return ExternalBinding(
                    source_entity_id=entity_name,
                    ontology="schema.org",
                    external_id=so_type,
                    label=f"{so_type} (heuristic)",
                    confidence=0.6,
                )

        return None


class WikidataMapper:
    """Resolve entity labels to Wikidata Q-IDs."""

    def __init__(self):
        self._cache: dict[str, str | None] = {}

    def resolve_qid(self, label: str) -> str | None:
        """Look up Wikidata Q-ID for a label. Cached. Uses API on first miss."""
        if label in self._cache:
            return self._cache[label]

        try:
            import urllib.request
            import urllib.parse

            encoded = urllib.parse.quote(label)
            url = (
                f"https://www.wikidata.org/w/api.php"
                f"?action=wbsearchentities&search={encoded}&language=en&format=json&limit=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                results = data.get("search", [])
                if results:
                    qid = results[0]["id"]
                    self._cache[label] = qid
                    return qid
        except Exception as e:
            logger.debug(f"Wikidata lookup failed for '{label}': {e}")

        self._cache[label] = None
        return None

    def get_description(self, qid: str) -> str | None:
        """Fetch entity description from Wikidata. Cached."""
        try:
            import urllib.request

            url = (
                f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                entity = data.get("entities", {}).get(qid, {})
                labels = entity.get("labels", {})
                desc = entity.get("descriptions", {})
                en_label = labels.get("en", {}).get("value", "")
                en_desc = desc.get("en", {}).get("value", "")
                return f"{en_label}: {en_desc}" if en_desc else en_label
        except Exception as e:
            logger.debug(f"Wikidata description failed for '{qid}': {e}")
        return None


class IndustryOntology:
    """Map entities to industry standards and regulations."""

    DOMAINS: dict[str, list[str]] = {
        "environmental": [
            "HJ/T 2.1-2016", "HJ/T 2.2-2018", "HJ/T 2.3-2018",
            "HJ 2.4-2021", "HJ 19-2022", "HJ 169-2018",
            "GB 3095-2012", "GB 3838-2002", "GB 3096-2008",
        ],
        "software": ["ISO/IEC 25010", "ISO/IEC 12207", "IEEE 829"],
        "ai": ["ISO/IEC 22989", "ISO/IEC 42001", "EU AI Act"],
        "data": ["DCAT", "Dublin Core", "ISO 19115"],
        "safety": ["ISO 26262", "IEC 61508", "DO-178C"],
        "quality": ["ISO 9001", "Six Sigma", "CMMI"],
    }

    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "environmental": ["环境", "大气", "水质", "噪声", "排放", "污染", "环保", "生态"],
        "software": ["代码", "软件", "测试", "部署", "devops", "编程"],
        "ai": ["ai", "机器学习", "深度学习", "模型", "神经网络", "llm", "大模型"],
        "data": ["数据", "数据库", "dataset", "etl", "分析"],
        "safety": ["安全", "防护", "safety", "security", "风险"],
        "quality": ["质量", "标准", "规范", "best practice", "最佳实践"],
    }

    def get_standards(self, domain: str) -> list[str]:
        """Get standards for a given domain."""
        return self.DOMAINS.get(domain, [])

    def suggest_domain(self, entity_name: str) -> str | None:
        """Keyword-based domain suggestion."""
        name_lower = entity_name.lower()
        scores: dict[str, int] = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in name_lower)
            if score > 0:
                scores[domain] = score
        if scores:
            return max(scores, key=scores.get)
        return None

    def bind_to_standard(self, entity_name: str, domain: str | None = None) -> ExternalBinding | None:
        """Create a binding to the most relevant industry standard."""
        if domain is None:
            domain = self.suggest_domain(entity_name)
        if not domain:
            return None

        standards = self.get_standards(domain)
        if standards:
            return ExternalBinding(
                source_entity_id=entity_name,
                ontology="industry",
                external_id=standards[0],
                label=f"{domain}: {standards[0]}",
                confidence=0.7,
            )
        return None


class OntoBridge:
    """Unified facade for external ontology binding."""

    def __init__(self):
        self.schema_org = SchemaOrgMapper()
        self.wikidata = WikidataMapper()
        self.industry = IndustryOntology()
        self._bindings: dict[str, ExternalBinding] = {}

    def bind_entity(self, entity_id: str, entity_type: str, entity_name: str) -> dict[str, Any]:
        """Bind an entity to all available external ontologies.

        Returns:
            {"schema_org": binding|None, "wikidata": binding|None, "industry": binding|None}
        """
        result: dict[str, Any] = {"schema_org": None, "wikidata": None, "industry": None}

        # Schema.org
        so = self.schema_org.suggest_binding(entity_name, entity_type)
        if so:
            so.source_entity_id = entity_id
            result["schema_org"] = so.model_dump()
            self._bindings[f"{entity_id}@schema.org"] = so

        # Wikidata
        qid = self.wikidata.resolve_qid(entity_name)
        if qid:
            wd = ExternalBinding(
                source_entity_id=entity_id,
                ontology="wikidata",
                external_id=qid,
                label=f"{entity_name} (Q-ID: {qid})",
                confidence=0.8,
            )
            result["wikidata"] = wd.model_dump()
            self._bindings[f"{entity_id}@wikidata"] = wd

        # Industry
        ind = self.industry.bind_to_standard(entity_name)
        if ind:
            ind.source_entity_id = entity_id
            result["industry"] = ind.model_dump()
            self._bindings[f"{entity_id}@industry"] = ind

        return result

    def auto_bind_all(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        """Batch bind multiple entities."""
        results = []
        for eid in entity_ids:
            # Try to resolve from EntityRegistry
            from livingtree.core.entity_registry import ENTITY_REGISTRY
            entry = ENTITY_REGISTRY.resolve(eid)
            if entry:
                results.append(self.bind_entity(entry.id, entry.entity_type, entry.name))
                continue
            # Fallback: use eid as name
            parts = eid.split(":", 1)
            results.append(self.bind_entity(eid, parts[0] if len(parts) > 1 else "entity", parts[-1]))
        return results

    def get_enrichment(self, entity_id: str) -> str:
        """Return formatted text describing external bindings for prompt injection."""
        parts: list[str] = []
        if entity_id in self._bindings:
            mapping = self._bindings[entity_id]
            parts.append(f"External: [{mapping.ontology}] {mapping.label}")
        return " | ".join(parts) if parts else ""

    def export_bindings(self) -> str:
        """Serialize all bindings to JSON."""
        data = {
            key: binding.model_dump()
            for key, binding in self._bindings.items()
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def load_bindings(self, json_str: str) -> None:
        """Restore bindings from serialized JSON."""
        try:
            data = json.loads(json_str)
            for key, item in data.items():
                self._bindings[key] = ExternalBinding(**item)
        except Exception as e:
            logger.warning(f"Failed to load bindings: {e}")


# Singleton
ONTO_BRIDGE = OntoBridge()


def get_onto_bridge() -> OntoBridge:
    """Get the global OntoBridge singleton."""
    return ONTO_BRIDGE
