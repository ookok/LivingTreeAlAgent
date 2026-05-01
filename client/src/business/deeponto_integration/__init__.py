"""
DeepOnto Integration Module

Provides ontology reasoning, entity embedding, ontology alignment,
and ontology completion capabilities using DeepOnto library.
"""

from .ontology_reasoner import OntologyReasoner, get_ontology_reasoner
from .entity_embedding import EntityEmbeddingService, get_entity_embedding_service
from .ontology_alignment import OntologyAlignmentService, get_alignment_service
from .ontology_completion import OntologyCompletionService, get_completion_service
from .smart_module_scheduler import SmartModuleScheduler, get_smart_module_scheduler

__all__ = [
    'OntologyReasoner',
    'get_ontology_reasoner',
    'EntityEmbeddingService',
    'get_entity_embedding_service',
    'OntologyAlignmentService',
    'get_alignment_service',
    'OntologyCompletionService',
    'get_completion_service',
    'SmartModuleScheduler',
    'get_smart_module_scheduler',
]