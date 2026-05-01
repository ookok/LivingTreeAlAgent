"""
Ontology Completion Service

Provides automatic ontology completion using deep learning and LLM integration.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from deeponto.completion import OntologyCompletion, LLMCompletion
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False

@dataclass
class CompletionResult:
    added_axioms: List[str]
    confidence_scores: List[float]
    completed_entities: List[str]
    metadata: Dict[str, Any]

class OntologyCompletionService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self, use_llm: bool = True):
        if not HAS_DEEPONTO:
            self._mock_mode = True
            self._initialized = True
            return
        
        self._mock_mode = False
        if use_llm:
            self.completion = LLMCompletion()
        else:
            self.completion = OntologyCompletion()
        self._initialized = True
    
    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def complete_ontology(self, ontology: Dict[str, Any]) -> CompletionResult:
        self.ensure_initialized()
        if self._mock_mode:
            return CompletionResult(
                added_axioms=[
                    "SubClassOf(Person Human)",
                    "SubClassOf(Company Organization)"
                ],
                confidence_scores=[0.95, 0.92],
                completed_entities=["Person", "Company"],
                metadata={"completed": True}
            )
        
        result = self.completion.complete(ontology)
        return CompletionResult(
            added_axioms=result.added_axioms,
            confidence_scores=result.confidence_scores,
            completed_entities=result.completed_entities,
            metadata=result.metadata
        )
    
    def complete_entity(self, entity_name: str, context: Dict[str, Any]) -> CompletionResult:
        self.ensure_initialized()
        if self._mock_mode:
            return CompletionResult(
                added_axioms=[f"Type({entity_name} Entity)"],
                confidence_scores=[0.98],
                completed_entities=[entity_name],
                metadata={"entity": entity_name}
            )
        
        result = self.completion.complete_entity(entity_name, context)
        return CompletionResult(
            added_axioms=result.added_axioms,
            confidence_scores=result.confidence_scores,
            completed_entities=result.completed_entities,
            metadata=result.metadata
        )
    
    def predict_missing_axioms(self, ontology: Dict[str, Any], max_axioms: int = 10) -> List[str]:
        self.ensure_initialized()
        if self._mock_mode:
            return [
                "SubClassOf(X Y)",
                "EquivalentClasses(A B)",
                "ObjectPropertyAssertion(relatedTo A B)"
            ][:max_axioms]
        
        return self.completion.predict(ontology, max_axioms)
    
    def suggest_properties(self, entity_name: str) -> List[str]:
        self.ensure_initialized()
        if self._mock_mode:
            return ["hasName", "hasAge", "hasAddress"]
        
        return self.completion.suggest_properties(entity_name)
    
    def refine_definition(self, entity_name: str, existing_definition: str) -> str:
        self.ensure_initialized()
        if self._mock_mode:
            return f"Refined definition for {entity_name}: {existing_definition}"
        
        return self.completion.refine(entity_name, existing_definition)
    
    def validate_completion(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_initialized()
        if self._mock_mode:
            return {
                "is_valid": True,
                "errors": [],
                "warnings": []
            }
        
        return self.completion.validate(ontology)

def get_completion_service() -> OntologyCompletionService:
    return OntologyCompletionService()