"""
Smart Module Scheduler

Intelligent module scheduler that integrates ontology reasoning for enhanced query routing.
"""

from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ModuleType(Enum):
    FUSION_RAG = "fusion_rag"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    ENTITY_MANAGEMENT = "entity_management"
    AI_ASSISTANT = "ai_assistant"

@dataclass
class QueryContext:
    query: str
    entities: List[str]
    intent: str
    confidence: float
    context: Dict[str, Any]

@dataclass
class ModuleResult:
    module_type: ModuleType
    result: Any
    confidence: float
    processing_time: float

class SmartModuleScheduler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        from .ontology_reasoner import get_ontology_reasoner
        from .entity_embedding import get_entity_embedding_service
        
        self.reasoner = get_ontology_reasoner()
        self.embedding_service = get_entity_embedding_service()
        self.reasoner.initialize()
        self.embedding_service.initialize()
        
        self.module_registry = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = True
    
    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def register_module(self, module_type: ModuleType, handler: Callable):
        self.module_registry[module_type] = handler
    
    def unregister_module(self, module_type: ModuleType):
        if module_type in self.module_registry:
            del self.module_registry[module_type]
    
    def analyze_query(self, query: str) -> QueryContext:
        self.ensure_initialized()
        
        entities = self.extract_entities(query)
        intent = self.determine_intent(query, entities)
        
        class_hierarchy = self.reasoner.get_class_hierarchy()
        entity_types = {}
        for entity in entities:
            entity_types[entity] = self.reasoner.classify_instance(entity)
        
        return QueryContext(
            query=query,
            entities=entities,
            intent=intent,
            confidence=0.85,
            context={
                "entity_types": entity_types,
                "class_hierarchy": class_hierarchy,
                "ontology_consistent": self.reasoner.check_consistency()
            }
        )
    
    def extract_entities(self, query: str) -> List[str]:
        if self.reasoner._mock_mode:
            import re
            return re.findall(r'\b[A-Z][a-z]+\b', query)
        return self.reasoner.infer_relations(query, "")
    
    def determine_intent(self, query: str, entities: List[str]) -> str:
        if "what is" in query.lower() or "define" in query.lower():
            return "definition"
        if "how" in query.lower():
            return "procedure"
        if any(op in query.lower() for op in ["find", "search", "lookup"]):
            return "search"
        if any(e.lower() in query.lower() for e in entities):
            return "entity_query"
        return "general"
    
    def select_modules(self, query_context: QueryContext) -> List[ModuleType]:
        self.ensure_initialized()
        
        modules = []
        intent = query_context.intent
        entities = query_context.entities
        
        if intent == "search" or intent == "entity_query":
            if entities:
                modules.append(ModuleType.ENTITY_MANAGEMENT)
            
            modules.append(ModuleType.FUSION_RAG)
            modules.append(ModuleType.KNOWLEDGE_GRAPH)
        
        elif intent == "definition":
            modules.append(ModuleType.KNOWLEDGE_GRAPH)
            modules.append(ModuleType.FUSION_RAG)
        
        elif intent == "procedure":
            modules.append(ModuleType.FUSION_RAG)
            modules.append(ModuleType.AI_ASSISTANT)
        
        else:
            modules.append(ModuleType.FUSION_RAG)
            modules.append(ModuleType.AI_ASSISTANT)
        
        return modules
    
    async def execute_query(self, query: str) -> List[ModuleResult]:
        self.ensure_initialized()
        
        query_context = self.analyze_query(query)
        selected_modules = self.select_modules(query_context)
        
        tasks = []
        for module_type in selected_modules:
            if module_type in self.module_registry:
                tasks.append(self.execute_module(module_type, query_context))
        
        results = await asyncio.gather(*tasks)
        return sorted(results, key=lambda x: x.confidence, reverse=True)
    
    async def execute_module(self, module_type: ModuleType, query_context: QueryContext) -> ModuleResult:
        import time
        
        start_time = time.time()
        
        def run_handler():
            handler = self.module_registry[module_type]
            return handler(query_context)
        
        result = await asyncio.get_event_loop().run_in_executor(
            self.executor, run_handler
        )
        
        processing_time = time.time() - start_time
        
        entity_scores = []
        for entity in query_context.entities:
            if query_context.context.get("entity_types", {}).get(entity):
                entity_scores.append(0.9)
            else:
                entity_scores.append(0.7)
        
        confidence = sum(entity_scores) / len(entity_scores) if entity_scores else 0.8
        
        return ModuleResult(
            module_type=module_type,
            result=result,
            confidence=confidence,
            processing_time=processing_time
        )
    
    def optimize_routing(self, query_context: QueryContext) -> List[ModuleType]:
        modules = self.select_modules(query_context)
        
        if query_context.context.get("ontology_consistent", False):
            return modules
        
        return [m for m in modules if m != ModuleType.KNOWLEDGE_GRAPH]
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        return {
            "total_queries": 0,
            "module_usage": {},
            "avg_processing_time": 0.0
        }

def get_smart_module_scheduler() -> SmartModuleScheduler:
    return SmartModuleScheduler()