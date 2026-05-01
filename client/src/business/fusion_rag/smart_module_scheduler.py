"""
智能模块调度器 (Smart Module Scheduler)
========================================

实现 FusionRAG、LLM Wiki 和记忆模块的自动化、自适应调用。

核心功能：
1. 模块自动发现与注册
2. 上下文感知的模块选择
3. 自适应任务调度（资源感知）
4. 优先级任务队列
5. ML驱动模块选择
6. 多模块协作执行
7. 智能故障恢复与降级
8. 持续学习与反馈优化

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 2.0.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger

# 导入增强模块
try:
    from business.fusion_rag.resource_aware_scheduler import ResourceAwareScheduler
    from business.fusion_rag.priority_task_queue import PriorityTaskQueue, TaskPriority
    from business.fusion_rag.ml_module_selector import MLModuleSelector
    from business.fusion_rag.dynamic_module_manager import DynamicModuleManager
    from business.fusion_rag.data_flow_optimizer import DataFlowOptimizer, ExecutionPlan
    from business.fusion_rag.learning_feedback_system import (
        LearningFeedbackSystem, ExecutionLog, FeedbackRecord, FeedbackType
    )
    HAS_ENHANCEMENTS = True
except ImportError:
    HAS_ENHANCEMENTS = False
    logger.warning("[SmartModuleScheduler] 增强模块导入失败，使用基础功能")


class ModuleType(Enum):
    """模块类型"""
    RETRIEVER = "retriever"
    PARSER = "parser"
    MEMORY = "memory"
    REASONER = "reasoner"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    FEEDBACK = "feedback"
    GOVERNANCE = "governance"
    INTEGRATION = "integration"


class TaskType(Enum):
    """任务类型"""
    DOCUMENT_ANALYSIS = "document_analysis"
    QUESTION_ANSWERING = "question_answering"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    GRAPH_BUILDING = "graph_building"
    FEEDBACK_LEARNING = "feedback_learning"
    INDUSTRY_GOVERNANCE = "industry_governance"
    MULTI_MODAL_ANALYSIS = "multi_modal_analysis"


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    module_type: ModuleType
    priority: float = 0.5
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    instance: Any = None
    last_used: float = 0.0
    success_rate: float = 1.0
    avg_latency: float = 0.0


@dataclass
class TaskContext:
    """任务上下文"""
    task_type: TaskType
    query: Optional[str] = None
    document_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    preferred_modules: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    module_name: str
    result: Any = None
    error: Optional[str] = None
    latency: float = 0.0
    confidence: float = 0.0
    evidence_ids: List[str] = field(default_factory=list)
    reasoning_steps: List[Dict] = field(default_factory=list)


class SmartModuleScheduler:
    """
    智能模块调度器 (V2)
    
    实现自动化、自适应的模块调用：
    1. 自动发现系统中的模块
    2. 根据任务上下文选择最佳模块
    3. 资源感知调度
    4. 优先级任务队列
    5. ML驱动模块选择
    6. 多模块协作完成复杂任务
    7. 智能故障恢复与降级
    8. 持续学习与反馈优化
    """
    
    def __init__(self):
        """初始化调度器"""
        self._modules: Dict[str, ModuleInfo] = {}
        self._modules_by_type: Dict[ModuleType, List[str]] = defaultdict(list)
        self._module_registry = {}
        self._task_handlers: Dict[TaskType, List[str]] = defaultdict(list)
        self._load_balancing = {}
        self._enable_adaptive = True
        
        # 初始化增强模块
        self._resource_scheduler = None
        self._priority_queue = None
        self._ml_selector = None
        self._dynamic_manager = None
        self._data_flow_optimizer = None
        self._feedback_system = None
        
        if HAS_ENHANCEMENTS:
            self._init_enhancements()
        
        logger.info("[SmartModuleScheduler] V2 初始化完成")
        
    def _init_enhancements(self):
        """初始化增强模块"""
        try:
            # 资源感知调度器
            self._resource_scheduler = ResourceAwareScheduler()
            
            # 优先级任务队列
            self._priority_queue = PriorityTaskQueue(max_pending=500)
            
            # ML模块选择器
            self._ml_selector = MLModuleSelector()
            
            # 动态模块管理器
            self._dynamic_manager = DynamicModuleManager()
            
            # 数据流优化器
            self._data_flow_optimizer = DataFlowOptimizer()
            
            # 学习反馈系统
            self._feedback_system = LearningFeedbackSystem(update_interval=30)
            
            # 注册模块权重
            self._register_module_weights()
            
            # 注册数据流节点
            self._register_data_flow_nodes()
            
            # 注册反馈优化回调
            self._feedback_system.register_optimization_callback(self._on_optimization)
            
            logger.info("[SmartModuleScheduler] 增强模块初始化完成")
        except Exception as e:
            logger.warning(f"[SmartModuleScheduler] 增强模块初始化失败: {e}")
            
    def _register_module_weights(self):
        """注册模块权重（轻量级/重量级）"""
        if not self._resource_scheduler:
            return
            
        lightweight_modules = [
            'EvidenceMemory',
            'DocumentNavigator',
            'VisualDocumentParser',
            'RelevanceScorer'
        ]
        
        for module_name in lightweight_modules:
            self._resource_scheduler.register_module_weight(module_name, is_lightweight=True)
            
    def _register_data_flow_nodes(self):
        """注册数据流节点"""
        if not self._data_flow_optimizer:
            return
            
        # 定义模块间的数据依赖
        data_nodes = [
            ('DocumentNavigator', {'document_path'}, {'document_structure', 'pages'}),
            ('VisualDocumentParser', {'document_structure'}, {'parsed_content', 'elements'}),
            ('EvidenceMemory', {'parsed_content', 'query'}, {'evidences', 'reasoning_chain'}),
            ('DeepSeekIntegration', {'query', 'evidences'}, {'answer', 'confidence'}),
            ('RAGFlowDocVFusion', {'document_path', 'query'}, {'fusion_result', 'knowledge_graph'})
        ]
        
        for module_name, input_keys, output_keys in data_nodes:
            self._data_flow_optimizer.register_node(module_name, input_keys, output_keys)
            
    async def _on_optimization(self, metrics: Dict[str, Dict[str, float]]):
        """优化回调"""
        logger.info(f"[SmartModuleScheduler] 执行优化，模块指标: {metrics}")
    
    def register_module(
        self,
        name: str,
        module_type: ModuleType,
        instance: Any = None,
        priority: float = 0.5,
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None
    ):
        """
        注册模块
        
        Args:
            name: 模块名称
            module_type: 模块类型
            instance: 模块实例
            priority: 优先级 (0-1)
            capabilities: 功能列表
            dependencies: 依赖模块列表
        """
        module_info = ModuleInfo(
            name=name,
            module_type=module_type,
            priority=priority,
            capabilities=capabilities or [],
            dependencies=dependencies or [],
            instance=instance
        )
        
        self._modules[name] = module_info
        self._modules_by_type[module_type].append(name)
        
        # 根据模块类型自动注册任务处理器
        self._auto_register_task_handler(name, module_type)
        
        logger.info(f"[SmartModuleScheduler] 模块注册成功: {name} ({module_type.value})")
    
    def _auto_register_task_handler(self, module_name: str, module_type: ModuleType):
        """根据模块类型自动注册任务处理器"""
        task_mapping = {
            ModuleType.RETRIEVER: [TaskType.KNOWLEDGE_RETRIEVAL, TaskType.QUESTION_ANSWERING],
            ModuleType.PARSER: [TaskType.DOCUMENT_ANALYSIS, TaskType.MULTI_MODAL_ANALYSIS],
            ModuleType.MEMORY: [TaskType.QUESTION_ANSWERING, TaskType.KNOWLEDGE_RETRIEVAL],
            ModuleType.REASONER: [TaskType.QUESTION_ANSWERING, TaskType.DOCUMENT_ANALYSIS],
            ModuleType.KNOWLEDGE_GRAPH: [TaskType.GRAPH_BUILDING, TaskType.KNOWLEDGE_RETRIEVAL],
            ModuleType.FEEDBACK: [TaskType.FEEDBACK_LEARNING],
            ModuleType.GOVERNANCE: [TaskType.INDUSTRY_GOVERNANCE],
            ModuleType.INTEGRATION: [TaskType.DOCUMENT_ANALYSIS, TaskType.QUESTION_ANSWERING]
        }
        
        for task_type in task_mapping.get(module_type, []):
            if module_name not in self._task_handlers[task_type]:
                self._task_handlers[task_type].append(module_name)
    
    def discover_modules(self):
        """自动发现系统中的模块"""
        logger.info("[SmartModuleScheduler] 开始自动发现模块...")
        
        # 发现 FusionRAG 模块
        self._discover_fusionrag_modules()
        
        # 发现 LLM Wiki 模块
        self._discover_llm_wiki_modules()
        
        # 发现记忆模块
        self._discover_memory_modules()
        
        logger.info(f"[SmartModuleScheduler] 模块发现完成，共 {len(self._modules)} 个模块")
    
    def _discover_fusionrag_modules(self):
        """发现 FusionRAG 模块"""
        try:
            # 逐个导入，避免单个导入失败影响其他模块
            modules_to_import = []
            
            # 导入记忆模块
            try:
                from business.fusion_rag.evidence_memory import EvidenceMemory, get_evidence_memory
                modules_to_import.append(('EvidenceMemory', EvidenceMemory, get_evidence_memory))
            except ImportError:
                pass
            
            try:
                from business.fusion_rag.document_navigator import DocumentNavigator, get_document_navigator
                modules_to_import.append(('DocumentNavigator', DocumentNavigator, get_document_navigator))
            except ImportError:
                pass
            
            try:
                from business.fusion_rag.visual_document_parser import VisualDocumentParser, get_visual_document_parser
                modules_to_import.append(('VisualDocumentParser', VisualDocumentParser, get_visual_document_parser))
            except ImportError:
                pass
            
            try:
                from business.fusion_rag.docv_llm_wiki_integration import DocVLLMWikiIntegration, get_docv_llm_wiki_integration
                modules_to_import.append(('DocVLLMWikiIntegration', DocVLLMWikiIntegration, get_docv_llm_wiki_integration))
            except ImportError:
                pass
            
            # 注册模块
            for name, module_class, get_instance in modules_to_import:
                try:
                    instance = get_instance()
                    
                    capabilities_map = {
                        'EvidenceMemory': ["evidence_storage", "reasoning_chain", "attention_mechanism"],
                        'DocumentNavigator': ["semantic_navigation", "targeted_fetch", "overview_scan"],
                        'VisualDocumentParser': ["layout_analysis", "element_detection", "multi_modal_extraction"],
                        'DocVLLMWikiIntegration': ["document_processing", "knowledge_indexing", "graph_building"]
                    }
                    
                    priority_map = {
                        'EvidenceMemory': 0.9,
                        'DocumentNavigator': 0.85,
                        'VisualDocumentParser': 0.8,
                        'DocVLLMWikiIntegration': 0.95
                    }
                    
                    module_type_map = {
                        'EvidenceMemory': ModuleType.MEMORY,
                        'DocumentNavigator': ModuleType.PARSER,
                        'VisualDocumentParser': ModuleType.PARSER,
                        'DocVLLMWikiIntegration': ModuleType.INTEGRATION
                    }
                    
                    self.register_module(
                        name,
                        module_type_map.get(name, ModuleType.INTEGRATION),
                        instance=instance,
                        priority=priority_map.get(name, 0.5),
                        capabilities=capabilities_map.get(name, [])
                    )
                except Exception as e:
                    logger.warning(f"注册 FusionRAG 模块 {name} 失败: {e}")
            
            # 尝试导入其他 FusionRAG 组件（不带实例的组件）
            other_components = [
                ("HybridRetriever", ModuleType.RETRIEVER, 0.85, ["hybrid_search", "semantic_retrieval", "path_finding"]),
                ("TripleChainEngine", ModuleType.REASONER, 0.9, ["triple_chain_verification", "reasoning", "validation"]),
                ("IndustryGovernance", ModuleType.GOVERNANCE, 0.8, ["term_normalization", "data_governance", "industry_filtering"]),
                ("KnowledgeTierManager", ModuleType.GOVERNANCE, 0.75, ["knowledge_tiering", "hierarchical_storage"]),
                ("IndustryFilter", ModuleType.GOVERNANCE, 0.7, ["domain_filtering", "re_ranking"]),
                ("RelevanceScorer", ModuleType.REASONER, 0.75, ["multi_dimension_scoring", "confidence_calculation"]),
                ("FeedbackLearner", ModuleType.FEEDBACK, 0.8, ["negative_feedback", "continuous_learning"]),
                ("IndustryDialectDict", ModuleType.GOVERNANCE, 0.7, ["term_management", "dialect_normalization"])
            ]
            
            # 发现新添加的模块
            self._discover_new_fusionrag_modules()
            
            logger.info("[SmartModuleScheduler] FusionRAG 模块发现完成")
            
        except Exception as e:
            logger.warning(f"发现 FusionRAG 模块时出错: {e}")
    
    def _discover_new_fusionrag_modules(self):
        """发现新添加的 FusionRAG 模块"""
        try:
            # RAGFlow-DocV* 融合模块
            try:
                from business.fusion_rag.ragflow_docv_fusion import RAGFlowDocVFusion, get_ragflow_docv_fusion
                self.register_module(
                    "RAGFlowDocVFusion",
                    ModuleType.INTEGRATION,
                    instance=get_ragflow_docv_fusion(),
                    priority=0.95,
                    capabilities=["document_fusion", "multi_modal_analysis", "hierarchical_retrieval"]
                )
                logger.info("[SmartModuleScheduler] 发现 RAGFlowDocVFusion")
            except ImportError as e:
                logger.debug(f"跳过 RAGFlowDocVFusion: {e}")
            
            # Anda 代理网络模块
            try:
                from business.fusion_rag.anda_agent_network import AndaAgentNetwork, get_anda_agent_network
                self.register_module(
                    "AndaAgentNetwork",
                    ModuleType.INTEGRATION,
                    instance=get_anda_agent_network(),
                    priority=0.9,
                    capabilities=["agent_network", "task_coordination", "distributed_execution", "shared_memory"]
                )
                logger.info("[SmartModuleScheduler] 发现 AndaAgentNetwork")
            except ImportError as e:
                logger.debug(f"跳过 AndaAgentNetwork: {e}")
            
            # DeepSeek 集成模块
            try:
                from business.fusion_rag.deepseek_integration import DeepSeekIntegration, get_deepseek_integration
                self.register_module(
                    "DeepSeekIntegration",
                    ModuleType.RETRIEVER,
                    instance=get_deepseek_integration(),
                    priority=0.9,
                    capabilities=["model_routing", "code_generation", "chat", "vision"]
                )
                logger.info("[SmartModuleScheduler] 发现 DeepSeekIntegration")
            except ImportError as e:
                logger.debug(f"跳过 DeepSeekIntegration: {e}")
            
            # Solana 区块链集成模块
            try:
                from business.fusion_rag.solana_integration import SolanaIntegration, get_solana_integration
                self.register_module(
                    "SolanaIntegration",
                    ModuleType.INTEGRATION,
                    instance=get_solana_integration(),
                    priority=0.7,
                    capabilities=["blockchain", "crypto_transaction", "smart_contract", "decentralized"]
                )
                logger.info("[SmartModuleScheduler] 发现 SolanaIntegration")
            except ImportError as e:
                logger.debug(f"跳过 SolanaIntegration: {e}")
            
            # ESFT 微调模块
            try:
                from business.fusion_rag.esft_finetuning import ESFTFineTuning, get_esft_finetuning
                self.register_module(
                    "ESFTFineTuning",
                    ModuleType.REASONER,
                    instance=get_esft_finetuning(),
                    priority=0.85,
                    capabilities=["fine_tuning", "transfer_learning", "domain_adaptation", "expert_model"]
                )
                logger.info("[SmartModuleScheduler] 发现 ESFTFineTuning")
            except ImportError as e:
                logger.debug(f"跳过 ESFTFineTuning: {e}")
                
        except Exception as e:
            logger.warning(f"[SmartModuleScheduler] 发现新模块失败: {e}")
            
        except ImportError as e:
            logger.warning(f"[SmartModuleScheduler] FusionRAG 模块发现失败: {e}")
    
    def _discover_llm_wiki_modules(self):
        """发现 LLM Wiki 模块"""
        try:
            from business.llm_wiki import (
                LLMDocumentParser,
                PaperParser,
                CodeExtractor,
                LLMWikiIntegration,
                LLMWikiKnowledgeGraphIntegratorV4,
                FeedbackManager,
                KnowledgeGraphSelfEvolver,
                HybridRetriever as WikiHybridRetriever
            )
            
            # 注册文档解析器
            self.register_module(
                "LLMDocumentParser",
                ModuleType.PARSER,
                instance=LLMDocumentParser(),
                priority=0.85,
                capabilities=["markdown_parsing", "code_extraction", "api_documentation"]
            )
            
            # 注册论文解析器
            self.register_module(
                "PaperParser",
                ModuleType.PARSER,
                instance=PaperParser(),
                priority=0.8,
                capabilities=["pdf_parsing", "paper_analysis", "metadata_extraction"]
            )
            
            # 注册代码提取器
            self.register_module(
                "CodeExtractor",
                ModuleType.PARSER,
                instance=CodeExtractor(),
                priority=0.75,
                capabilities=["code_detection", "function_extraction", "language_detection"]
            )
            
            # 注册 LLM Wiki 集成器
            self.register_module(
                "LLMWikiIntegration",
                ModuleType.INTEGRATION,
                instance=LLMWikiIntegration(),
                priority=0.85,
                capabilities=["wiki_indexing", "knowledge_integration", "fusionrag_integration"]
            )
            
            # 注册知识图谱集成器 V4
            self.register_module(
                "LLMWikiKnowledgeGraphIntegratorV4",
                ModuleType.KNOWLEDGE_GRAPH,
                priority=0.9,
                capabilities=["graph_integration", "entity_linking", "cross_document_reference"]
            )
            
            # 注册反馈管理器
            self.register_module(
                "FeedbackManager",
                ModuleType.FEEDBACK,
                priority=0.85,
                capabilities=["feedback_recording", "utility_scoring", "backpropagation"]
            )
            
            # 注册知识图谱自进化器
            self.register_module(
                "KnowledgeGraphSelfEvolver",
                ModuleType.KNOWLEDGE_GRAPH,
                priority=0.85,
                capabilities=["self_evolution", "path_learning", "graph_optimization"]
            )
            
            logger.info("[SmartModuleScheduler] LLM Wiki 模块发现完成")
            
        except ImportError as e:
            logger.warning(f"[SmartModuleScheduler] LLM Wiki 模块发现失败: {e}")
    
    def _discover_memory_modules(self):
        """发现记忆模块"""
        try:
            # 逐个导入，避免单个导入失败
            try:
                from business.memory_graph_engine import MemoryGraphEngine, get_memory_graph_engine
            except ImportError:
                logger.warning("[SmartModuleScheduler] MemoryGraphEngine 导入失败")
                return
            
            # 尝试导入 NodeType（忽略 EdgeType 导入失败）
            try:
                from business.memory_graph_engine import NodeType
            except ImportError:
                pass
            
            # 注册记忆图引擎
            self.register_module(
                "MemoryGraphEngine",
                ModuleType.MEMORY,
                instance=get_memory_graph_engine(),
                priority=0.9,
                capabilities=["memory_graph", "context_management", "association_learning"]
            )
            
            logger.info("[SmartModuleScheduler] 记忆模块发现完成")
            
        except Exception as e:
            logger.warning(f"[SmartModuleScheduler] 记忆模块发现失败: {e}")
    
    def select_modules(self, context: TaskContext) -> List[str]:
        """
        根据上下文选择最合适的模块
        
        Args:
            context: 任务上下文
            
        Returns:
            排序后的模块名称列表
        """
        candidates = []
        
        # 获取该任务类型的所有处理器
        handlers = self._task_handlers.get(context.task_type, [])
        
        for module_name in handlers:
            module_info = self._modules.get(module_name)
            if not module_info:
                continue
            
            # 检查依赖是否满足
            if not self._check_dependencies(module_info):
                continue
            
            # 检查功能是否匹配
            if context.required_capabilities:
                has_capabilities = all(
                    cap in module_info.capabilities
                    for cap in context.required_capabilities
                )
                if not has_capabilities:
                    continue
            
            # 计算综合得分
            score = self._calculate_module_score(module_info, context)
            candidates.append((module_name, score))
        
        # 按得分排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 如果有偏好模块，优先考虑
        if context.preferred_modules:
            result = []
            preferred_set = set(context.preferred_modules)
            # 先添加偏好模块
            for name, score in candidates:
                if name in preferred_set:
                    result.append(name)
            # 再添加其他模块
            for name, score in candidates:
                if name not in preferred_set:
                    result.append(name)
            return result
        
        return [name for name, score in candidates]
    
    def _check_dependencies(self, module_info: ModuleInfo) -> bool:
        """检查模块依赖是否满足"""
        for dep_name in module_info.dependencies:
            if dep_name not in self._modules:
                logger.warning(f"[SmartModuleScheduler] 模块 {module_info.name} 缺少依赖: {dep_name}")
                return False
        return True
    
    def _calculate_module_score(self, module_info: ModuleInfo, context: TaskContext) -> float:
        """计算模块综合得分"""
        score = module_info.priority
        
        # 考虑成功率
        score *= module_info.success_rate
        
        # 考虑延迟（延迟越低越好）
        if module_info.avg_latency > 0:
            latency_factor = max(0.1, 1.0 - module_info.avg_latency / 10.0)
            score *= latency_factor
        
        # 如果有偏好模块，加分
        if context.preferred_modules and module_info.name in context.preferred_modules:
            score *= 1.2
        
        return score
    
    async def execute(self, context: TaskContext) -> ExecutionResult:
        """
        执行任务，自动选择并调用最佳模块（集成增强功能）
        
        Args:
            context: 任务上下文
            
        Returns:
            执行结果
        """
        import time
        
        logger.info(f"[SmartModuleScheduler] 开始执行任务: {context.task_type.value}")
        
        # 选择模块（集成资源感知和ML选择）
        modules = self._enhanced_module_selection(context)
        if not modules:
            return ExecutionResult(
                success=False,
                module_name="",
                error="没有找到合适的模块"
            )
        
        # 依次尝试模块，支持故障降级
        for module_name in modules[:3]:  # 最多尝试3个模块
            start_time = time.time()
            
            try:
                module_info = self._modules[module_name]
                
                # 执行任务
                result = await self._execute_module(module_info, context)
                
                latency = time.time() - start_time
                
                # 更新模块统计
                self._update_module_stats(module_name, latency, success=True)
                
                # 记录执行日志
                self._record_execution_log(module_name, context.task_type.value, True, latency, module_info.priority)
                
                return ExecutionResult(
                    success=True,
                    module_name=module_name,
                    result=result,
                    latency=latency,
                    confidence=module_info.priority
                )
                
            except Exception as e:
                latency = time.time() - start_time
                
                # 更新模块统计
                self._update_module_stats(module_name, latency, success=False)
                
                # 记录执行日志（失败）
                self._record_execution_log(module_name, context.task_type.value, False, latency, 0.0, str(e))
                
                logger.warning(f"[SmartModuleScheduler] 模块 {module_name} 执行失败: {e}")
                
                # 如果还有其他模块，继续尝试
                if module_name != modules[-1]:
                    continue
                
                # 所有模块都失败了
                return ExecutionResult(
                    success=False,
                    module_name=module_name,
                    error=str(e),
                    latency=latency
                )
        
        return ExecutionResult(
            success=False,
            module_name="",
            error="所有模块执行失败"
        )
        
    def _enhanced_module_selection(self, context: TaskContext) -> List[str]:
        """
        增强版模块选择（集成资源感知和ML选择）
        
        Args:
            context: 任务上下文
            
        Returns:
            排序后的模块列表
        """
        # 基础选择
        modules = self.select_modules(context)
        
        if not modules:
            return []
            
        # 资源感知过滤
        if self._resource_scheduler:
            try:
                modules = self._resource_scheduler.filter_modules_by_resource(modules)
            except Exception as e:
                logger.warning(f"[SmartModuleScheduler] 资源感知过滤失败: {e}")
                
        # ML驱动优化
        if self._ml_selector:
            try:
                # 获取资源信息
                resource_info = {}
                if self._resource_scheduler:
                    resources = self._resource_scheduler.get_resource_status()
                    resource_info = {
                        'cpu_usage': resources.cpu_usage,
                        'memory_usage': resources.memory_usage,
                        'gpu_available': resources.gpu_available
                    }
                
                # 提取特征
                features = self._ml_selector.extract_features(context, resource_info)
                
                # 使用ML选择器优化顺序
                modules = self._ml_selector.predict(features, modules)
            except Exception as e:
                logger.warning(f"[SmartModuleScheduler] ML选择失败: {e}")
                
        return modules
        
    def _record_execution_log(self, module_name: str, task_type: str, success: bool, latency: float, confidence: float, error_message: Optional[str] = None):
        """
        记录执行日志到反馈系统
        
        Args:
            module_name: 模块名称
            task_type: 任务类型
            success: 是否成功
            latency: 延迟
            confidence: 置信度
            error_message: 错误消息
        """
        if self._feedback_system:
            try:
                log = ExecutionLog(
                    module_name=module_name,
                    task_type=task_type,
                    success=success,
                    latency=latency,
                    confidence=confidence,
                    error_message=error_message
                )
                self._feedback_system.record_execution(log)
            except Exception as e:
                logger.warning(f"[SmartModuleScheduler] 记录执行日志失败: {e}")
    
    async def _execute_module(self, module_info: ModuleInfo, context: TaskContext) -> Any:
        """执行单个模块"""
        module = module_info.instance
        
        if module is None:
            raise ValueError(f"模块 {module_info.name} 没有实例")
        
        # 根据任务类型调用不同方法
        if context.task_type == TaskType.DOCUMENT_ANALYSIS:
            return await self._execute_document_analysis(module, context)
        elif context.task_type == TaskType.QUESTION_ANSWERING:
            return await self._execute_question_answering(module, context)
        elif context.task_type == TaskType.KNOWLEDGE_RETRIEVAL:
            return await self._execute_knowledge_retrieval(module, context)
        elif context.task_type == TaskType.GRAPH_BUILDING:
            return await self._execute_graph_building(module, context)
        elif context.task_type == TaskType.FEEDBACK_LEARNING:
            return await self._execute_feedback_learning(module, context)
        elif context.task_type == TaskType.INDUSTRY_GOVERNANCE:
            return await self._execute_industry_governance(module, context)
        elif context.task_type == TaskType.MULTI_MODAL_ANALYSIS:
            return await self._execute_multi_modal_analysis(module, context)
        
        raise ValueError(f"未知任务类型: {context.task_type}")
    
    async def _execute_document_analysis(self, module, context):
        """执行文档分析"""
        if hasattr(module, 'process_document'):
            return await module.process_document(
                context.document_path,
                query=context.query,
                auto_index=True,
                build_knowledge_graph=True
            )
        elif hasattr(module, 'parse_document'):
            return await module.parse_document(context.document_path)
        elif hasattr(module, 'parse_markdown'):
            return module.parse_markdown(context.document_path)
        else:
            raise NotImplementedError(f"模块不支持文档分析")
    
    async def _execute_question_answering(self, module, context):
        """执行问答"""
        if hasattr(module, 'query_with_context'):
            return module.query_with_context(context.query)
        elif hasattr(module, 'retrieve_by_query'):
            return module.retrieve_by_query(context.query, {})
        elif hasattr(module, 'aggregate_reasoning'):
            return module.aggregate_reasoning(context.query)
        else:
            raise NotImplementedError(f"模块不支持问答")
    
    async def _execute_knowledge_retrieval(self, module, context):
        """执行知识检索"""
        if hasattr(module, 'retrieve_by_query'):
            return module.retrieve_by_query(context.query, {})
        elif hasattr(module, 'search'):
            return module.search(context.query)
        elif hasattr(module, 'get_top_evidences'):
            return module.get_top_evidences(query=context.query)
        else:
            raise NotImplementedError(f"模块不支持知识检索")
    
    async def _execute_graph_building(self, module, context):
        """执行知识图谱构建"""
        if hasattr(module, '_build_knowledge_graph'):
            return await module._build_knowledge_graph(context.metadata.get('document_info'))
        else:
            raise NotImplementedError(f"模块不支持知识图谱构建")
    
    async def _execute_feedback_learning(self, module, context):
        """执行反馈学习"""
        if hasattr(module, 'record'):
            from business.llm_wiki import FeedbackRecord
            feedback = FeedbackRecord(
                query=context.query,
                response="",
                paths=[],
                feedback_score=5.0
            )
            return module.record(feedback)
        else:
            raise NotImplementedError(f"模块不支持反馈学习")
    
    async def _execute_industry_governance(self, module, context):
        """执行行业治理"""
        if hasattr(module, 'validate'):
            return module.validate(context.query, context.metadata.get('source', ''))
        elif hasattr(module, 'normalize_terms'):
            return module.normalize_terms([context.query])
        else:
            raise NotImplementedError(f"模块不支持行业治理")
    
    async def _execute_multi_modal_analysis(self, module, context):
        """执行多模态分析"""
        if hasattr(module, 'parse_document'):
            return await module.parse_document(context.document_path)
        elif hasattr(module, 'extract_text_content'):
            return module.extract_text_content()
        else:
            raise NotImplementedError(f"模块不支持多模态分析")
    
    def _update_module_stats(self, module_name: str, latency: float, success: bool):
        """更新模块统计信息"""
        module_info = self._modules.get(module_name)
        if not module_info:
            return
        
        module_info.last_used = latency
        
        # 更新成功率（简单滑动窗口）
        if success:
            module_info.success_rate = min(1.0, module_info.success_rate * 0.9 + 0.1)
        else:
            module_info.success_rate = max(0.0, module_info.success_rate * 0.9 - 0.1)
        
        # 更新平均延迟
        module_info.avg_latency = (module_info.avg_latency * 0.9 + latency * 0.1)
    
    def get_module_status(self) -> Dict[str, Any]:
        """获取所有模块状态"""
        status = {}
        for name, module_info in self._modules.items():
            status[name] = {
                "type": module_info.module_type.value,
                "priority": module_info.priority,
                "success_rate": module_info.success_rate,
                "avg_latency": round(module_info.avg_latency, 2),
                "capabilities": module_info.capabilities
            }
        return status
    
    def enable_adaptive(self, enable: bool):
        """启用/禁用自适应调度"""
        self._enable_adaptive = enable
        logger.info(f"[SmartModuleScheduler] 自适应调度 {'启用' if enable else '禁用'}")


# 单例模式
_scheduler_instance = None

def get_smart_scheduler() -> SmartModuleScheduler:
    """获取全局智能调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SmartModuleScheduler()
        _scheduler_instance.discover_modules()
    return _scheduler_instance


# 便捷函数
async def analyze_document(document_path: str, query: Optional[str] = None) -> ExecutionResult:
    """
    分析文档（便捷函数）
    
    Args:
        document_path: 文档路径
        query: 用户查询
        
    Returns:
        执行结果
    """
    scheduler = get_smart_scheduler()
    context = TaskContext(
        task_type=TaskType.DOCUMENT_ANALYSIS,
        query=query,
        document_path=document_path,
        required_capabilities=["document_processing"]
    )
    return await scheduler.execute(context)


async def answer_question(query: str) -> ExecutionResult:
    """
    回答问题（便捷函数）
    
    Args:
        query: 用户查询
        
    Returns:
        执行结果
    """
    scheduler = get_smart_scheduler()
    context = TaskContext(
        task_type=TaskType.QUESTION_ANSWERING,
        query=query,
        required_capabilities=["reasoning", "knowledge_retrieval"]
    )
    return await scheduler.execute(context)


async def retrieve_knowledge(query: str) -> ExecutionResult:
    """
    检索知识（便捷函数）
    
    Args:
        query: 用户查询
        
    Returns:
        执行结果
    """
    scheduler = get_smart_scheduler()
    context = TaskContext(
        task_type=TaskType.KNOWLEDGE_RETRIEVAL,
        query=query,
        required_capabilities=["semantic_retrieval"]
    )
    return await scheduler.execute(context)