"""EntityBridge — Unified domain glossary + ontology mapping.

Consolidates two previously separate knowledge modules:
  - ContextGlossary: domain terminology, entity definitions, term expansion
  - OntoBridge: schema.org, Wikidata, industry ontology mapping

Both handle entity identification and mapping. This module provides a
unified import path.

Usage:
    from livingtree.knowledge.entity_bridge import (
        DomainTerm, ContextGlossary, GLOSSARY,
        OntoBridge, ExternalBinding, SchemaOrgMapper, WikidataMapper,
        IndustryOntology, ONTO_BRIDGE, get_onto_bridge,
    )
"""

from .context_glossary import DomainTerm, ContextGlossary, GLOSSARY
from .onto_bridge import (
    OntoBridge, ExternalBinding, SchemaOrgMapper, WikidataMapper,
    IndustryOntology, ONTO_BRIDGE, get_onto_bridge,
)

__all__ = [
    "DomainTerm", "ContextGlossary", "GLOSSARY",
    "OntoBridge", "ExternalBinding", "SchemaOrgMapper", "WikidataMapper",
    "IndustryOntology", "ONTO_BRIDGE", "get_onto_bridge",
]
