"""模型路由创新模块 - 智能选择与动态组合"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class ModelType(Enum):
    LLM = "llm"
    RAG = "rag"
    SEARCH = "search"
    TOOL = "tool"
    CUSTOM = "custom"

@dataclass
class ModelDescriptor:
    """模型描述符"""
    id: str
    name: str
    type: ModelType
    capabilities: List[str]
    cost_per_token: float
    max_tokens: int
    latency: float
    quality_score: float

@dataclass
class RoutingDecision:
    """路由决策"""
    model_id: str
    confidence: float
    reason: str
    estimated_cost: float
    estimated_latency: float

@dataclass
class PipelineStep:
    """流水线步骤"""
    model_id: str
    input_key: str
    output_key: str
    parameters: Dict[str, Any] = field(default_factory=dict)

class SmartModelSelector:
    """智能模型选择器"""
    
    def __init__(self):
        self._models: Dict[str, ModelDescriptor] = {}
        self._performance_history: Dict[str, List[float]] = {}
    
    def register_model(self, descriptor: ModelDescriptor):
        """注册模型"""
        self._models[descriptor.id] = descriptor
        if descriptor.id not in self._performance_history:
            self._performance_history[descriptor.id] = []
    
    async def select(self, query: str, context: Dict[str, Any]) -> RoutingDecision:
        """选择最佳模型"""
        features = self._extract_features(query, context)
        scores = await self._score_models(features)
        
        if not scores:
            return RoutingDecision(
                model_id="default",
                confidence=0.5,
                reason="No models available",
                estimated_cost=0.0,
                estimated_latency=0.0
            )
        
        best_model_id = max(scores, key=scores.get)
        best_model = self._models[best_model_id]
        
        return RoutingDecision(
            model_id=best_model_id,
            confidence=scores[best_model_id],
            reason=f"Best match for query features",
            estimated_cost=self._estimate_cost(query, best_model),
            estimated_latency=best_model.latency
        )
    
    def _extract_features(self, query: str, context: Dict[str, Any]) -> Dict[str, float]:
        """提取查询特征"""
        features = {
            'length': min(len(query) / 1000, 1.0),
            'is_code': 1.0 if any(word in query for word in ['代码', '编程', 'function', 'def']) else 0.0,
            'is_search': 1.0 if any(word in query for word in ['搜索', '查找', '查询']) else 0.0,
            'is_complex': 1.0 if len(query) > 100 else 0.5,
        }
        return features
    
    async def _score_models(self, features: Dict[str, float]) -> Dict[str, float]:
        """为每个模型打分"""
        scores = {}
        
        for model_id, model in self._models.items():
            compatibility = self._calculate_compatibility(model, features)
            performance = self._get_performance_score(model_id)
            scores[model_id] = 0.7 * compatibility + 0.3 * performance
        
        return scores
    
    def _calculate_compatibility(self, model: ModelDescriptor, features: Dict[str, float]) -> float:
        """计算模型兼容性"""
        compatibility = 0.5
        
        if features.get('is_code', 0) > 0.5 and 'code' in model.capabilities:
            compatibility += 0.2
        
        if features.get('is_search', 0) > 0.5 and 'search' in model.capabilities:
            compatibility += 0.2
        
        if features.get('is_complex', 0) > 0.5 and model.type == ModelType.LLM:
            compatibility += 0.1
        
        return min(1.0, compatibility)
    
    def _get_performance_score(self, model_id: str) -> float:
        """获取性能分数"""
        history = self._performance_history.get(model_id, [])
        if not history:
            return 0.7
        
        return sum(history[-10:]) / len(history[-10:])
    
    def _estimate_cost(self, query: str, model: ModelDescriptor) -> float:
        """估算成本"""
        tokens = len(query) / 4
        return tokens * model.cost_per_token / 1000
    
    def record_performance(self, model_id: str, score: float):
        """记录性能"""
        if model_id not in self._performance_history:
            self._performance_history[model_id] = []
        self._performance_history[model_id].append(score)
        
        if len(self._performance_history[model_id]) > 100:
            self._performance_history[model_id] = self._performance_history[model_id][-100:]
    
    def get_models(self) -> List[ModelDescriptor]:
        """获取所有模型"""
        return list(self._models.values())

class DynamicModelComposer:
    """动态模型组合器"""
    
    def __init__(self):
        self._selector = SmartModelSelector()
    
    async def compose(self, query: str) -> List[PipelineStep]:
        """组合多个模型"""
        required_capabilities = self._analyze_requirements(query)
        models = await self._find_models(required_capabilities)
        
        return self._build_pipeline(models)
    
    def _analyze_requirements(self, query: str) -> List[str]:
        """分析需求能力"""
        capabilities = []
        
        if any(word in query for word in ['搜索', '查找', '查询']):
            capabilities.append('search')
        
        if any(word in query for word in ['代码', '编程']):
            capabilities.append('code')
        
        if any(word in query for word in ['总结', '分析', '报告']):
            capabilities.append('analyze')
        
        if not capabilities:
            capabilities.append('general')
        
        return capabilities
    
    async def _find_models(self, capabilities: List[str]) -> List[str]:
        """查找符合能力要求的模型"""
        model_ids = []
        
        for capability in capabilities:
            for model in self._selector.get_models():
                if capability in model.capabilities and model.id not in model_ids:
                    model_ids.append(model.id)
        
        return model_ids
    
    def _build_pipeline(self, model_ids: List[str]) -> List[PipelineStep]:
        """构建模型流水线"""
        steps = []
        input_key = "input"
        
        for i, model_id in enumerate(model_ids):
            step = PipelineStep(
                model_id=model_id,
                input_key=input_key,
                output_key=f"output_{i}"
            )
            steps.append(step)
            input_key = step.output_key
        
        return steps

class CostQualityRouter:
    """成本-质量感知路由器"""
    
    def __init__(self):
        self._model_selector = SmartModelSelector()
    
    async def route(self, query: str, budget: Optional[float] = None) -> RoutingDecision:
        """基于成本和质量路由"""
        all_models = self._model_selector.get_models()
        
        if budget:
            options = [m for m in all_models if self._estimate_cost(query, m) <= budget]
        else:
            options = all_models
        
        if not options:
            return RoutingDecision(
                model_id="default",
                confidence=0.5,
                reason="No models within budget",
                estimated_cost=0.0,
                estimated_latency=0.0
            )
        
        return self._select_pareto_optimal(options, query)
    
    def _estimate_cost(self, query: str, model: ModelDescriptor) -> float:
        """估算成本"""
        tokens = len(query) / 4
        return tokens * model.cost_per_token / 1000
    
    def _select_pareto_optimal(self, models: List[ModelDescriptor], query: str) -> RoutingDecision:
        """选择帕累托最优模型"""
        if len(models) == 1:
            model = models[0]
            return RoutingDecision(
                model_id=model.id,
                confidence=0.8,
                reason="Only one option",
                estimated_cost=self._estimate_cost(query, model),
                estimated_latency=model.latency
            )
        
        best_model = max(models, key=lambda m: m.quality_score - m.cost_per_token)
        
        return RoutingDecision(
            model_id=best_model.id,
            confidence=0.85,
            reason="Pareto optimal selection",
            estimated_cost=self._estimate_cost(query, best_model),
            estimated_latency=best_model.latency
        )

# 全局单例
_smart_model_selector = SmartModelSelector()
_dynamic_model_composer = DynamicModelComposer()
_cost_quality_router = CostQualityRouter()

# 注册默认模型
default_models = [
    ModelDescriptor(
        id="claude-3-sonnet",
        name="Claude 3 Sonnet",
        type=ModelType.LLM,
        capabilities=["general", "code", "analyze"],
        cost_per_token=0.0015,
        max_tokens=200000,
        latency=0.5,
        quality_score=0.95
    ),
    ModelDescriptor(
        id="claude-3-haiku",
        name="Claude 3 Haiku",
        type=ModelType.LLM,
        capabilities=["general", "search"],
        cost_per_token=0.00025,
        max_tokens=200000,
        latency=0.2,
        quality_score=0.85
    ),
    ModelDescriptor(
        id="rag-system",
        name="RAG System",
        type=ModelType.RAG,
        capabilities=["search", "knowledge"],
        cost_per_token=0.0001,
        max_tokens=100000,
        latency=0.8,
        quality_score=0.8
    ),
]

for model in default_models:
    _smart_model_selector.register_model(model)
    _cost_quality_router._model_selector.register_model(model)

def get_smart_model_selector() -> SmartModelSelector:
    return _smart_model_selector

def get_dynamic_model_composer() -> DynamicModelComposer:
    return _dynamic_model_composer

def get_cost_quality_router() -> CostQualityRouter:
    return _cost_quality_router