"""
Ontology Reasoner Module

Provides DL-based reasoning capabilities using DeepOnto's OWLAPI integration.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from deeponto.onto import Ontology
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False

@dataclass
class ReasoningResult:
    is_consistent: bool
    inferred_axioms: List[str]
    class_hierarchy: Dict[str, List[str]]
    instance_types: Dict[str, List[str]]

class OntologyReasoner:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self, ontology_path: Optional[str] = None):
        if not HAS_DEEPONTO:
            self._mock_mode = True
            self._initialized = True
            return
        
        self._mock_mode = False
        if ontology_path:
            self.ontology = Ontology(ontology_path)
        else:
            self.ontology = Ontology()
        self.reasoner = DLReasoner(self.ontology)
        self._initialized = True
    
    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def check_consistency(self) -> bool:
        self.ensure_initialized()
        if self._mock_mode:
            return True
        return self.reasoner.is_consistent()
    
    def infer_axioms(self, query: str) -> List[str]:
        self.ensure_initialized()
        if self._mock_mode:
            return [f"Inferred: {query} related axiom"]
        return self.reasoner.infer(query)
    
    def get_class_hierarchy(self) -> Dict[str, List[str]]:
        self.ensure_initialized()
        if self._mock_mode:
            return {
                "Entity": ["Person", "Organization", "Location"],
                "Person": ["User", "Agent"],
                "Organization": ["Company", "Institution"]
            }
        return self.reasoner.get_class_hierarchy()
    
    def classify_instance(self, instance_name: str) -> List[str]:
        self.ensure_initialized()
        if self._mock_mode:
            return ["Entity", "Person"]
        return self.reasoner.classify(instance_name)
    
    def infer_relations(self, entity1: str, entity2: str) -> List[str]:
        self.ensure_initialized()
        if self._mock_mode:
            return ["relatedTo", "similarTo"]
        return self.reasoner.infer_relations(entity1, entity2)
    
    def reason(self, query: Dict[str, Any]) -> ReasoningResult:
        self.ensure_initialized()
        if self._mock_mode:
            return ReasoningResult(
                is_consistent=True,
                inferred_axioms=[f"Reasoned about: {query}"],
                class_hierarchy=self.get_class_hierarchy(),
                instance_types={"test": ["Entity"]}
            )
        
        result = self.reasoner.reason(query)
        return ReasoningResult(
            is_consistent=result.is_consistent,
            inferred_axioms=result.inferred_axioms,
            class_hierarchy=result.class_hierarchy,
            instance_types=result.instance_types
        )

def get_ontology_reasoner() -> OntologyReasoner:
    return OntologyReasoner()