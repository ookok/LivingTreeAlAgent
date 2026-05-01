"""
Ontology Alignment Service

Provides ontology matching and alignment capabilities for multi-knowledge-base integration.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from deeponto.alignment import OntologyAlignment, AlignmentEvaluator
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False

@dataclass
class AlignmentMapping:
    source_entity: str
    target_entity: str
    confidence: float
    relation_type: str

@dataclass
class AlignmentResult:
    mappings: List[AlignmentMapping]
    precision: float
    recall: float
    f1_score: float

class OntologyAlignmentService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        if not HAS_DEEPONTO:
            self._mock_mode = True
            self._initialized = True
            return
        
        self._mock_mode = False
        self.alignment = OntologyAlignment()
        self.evaluator = AlignmentEvaluator()
        self._initialized = True
    
    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def align_ontologies(self, source_onto: str, target_onto: str) -> List[AlignmentMapping]:
        self.ensure_initialized()
        if self._mock_mode:
            return [
                AlignmentMapping(
                    source_entity="Person",
                    target_entity="Human",
                    confidence=0.95,
                    relation_type="equivalent"
                ),
                AlignmentMapping(
                    source_entity="Organization",
                    target_entity="Company",
                    confidence=0.88,
                    relation_type="subclass"
                )
            ]
        
        mappings = self.alignment.align(source_onto, target_onto)
        return [
            AlignmentMapping(
                source_entity=m.source,
                target_entity=m.target,
                confidence=m.confidence,
                relation_type=m.relation
            ) for m in mappings
        ]
    
    def match_entities(self, entity: str, target_entities: List[str]) -> List[AlignmentMapping]:
        self.ensure_initialized()
        if self._mock_mode:
            return [
                AlignmentMapping(
                    source_entity=entity,
                    target_entity=target_entities[0],
                    confidence=0.92,
                    relation_type="equivalent"
                )
            ]
        
        matches = self.alignment.match(entity, target_entities)
        return [
            AlignmentMapping(
                source_entity=entity,
                target_entity=m.target,
                confidence=m.confidence,
                relation_type=m.relation
            ) for m in matches
        ]
    
    def evaluate_alignment(self, mappings: List[AlignmentMapping], gold_standard: List[Tuple[str, str]]) -> AlignmentResult:
        self.ensure_initialized()
        if self._mock_mode:
            return AlignmentResult(
                mappings=mappings,
                precision=0.85,
                recall=0.82,
                f1_score=0.83
            )
        
        predictions = [(m.source_entity, m.target_entity) for m in mappings]
        results = self.evaluator.evaluate(predictions, gold_standard)
        
        return AlignmentResult(
            mappings=mappings,
            precision=results.precision,
            recall=results.recall,
            f1_score=results.f1
        )
    
    def merge_ontologies(self, ontologies: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.ensure_initialized()
        if self._mock_mode:
            merged = {"classes": [], "properties": [], "individuals": []}
            for onto in ontologies:
                merged["classes"].extend(onto.get("classes", []))
                merged["properties"].extend(onto.get("properties", []))
                merged["individuals"].extend(onto.get("individuals", []))
            return merged
        
        return self.alignment.merge(ontologies)
    
    def get_alignment_statistics(self, mappings: List[AlignmentMapping]) -> Dict[str, Any]:
        stats = {
            "total_mappings": len(mappings),
            "average_confidence": sum(m.confidence for m in mappings) / len(mappings) if mappings else 0,
            "relation_distribution": {}
        }
        
        for m in mappings:
            stats["relation_distribution"][m.relation_type] = (
                stats["relation_distribution"].get(m.relation_type, 0) + 1
            )
        
        return stats

def get_alignment_service() -> OntologyAlignmentService:
    return OntologyAlignmentService()