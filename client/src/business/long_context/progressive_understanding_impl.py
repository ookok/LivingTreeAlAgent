"""
Phase 4: 渐进式理解实现
========================

整合 Phase 1-3 的所有能力，实现真正的迭代式深度理解。
"""

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    TYPE_CHECKING, Dict, List, Optional, Any, Callable, Iterator, 
    Set, Tuple, Union
)
from collections import defaultdict

# Phase 1-3 组件（运行时导入）
PHASE1_AVAILABLE = False
PHASE2_AVAILABLE = False
PHASE3_AVAILABLE = False

# 类型占位符
AdaptiveCompressor = None
SemanticChunker = None
LayeredHybridAnalyzer = None
MultiAgentCoordinator = None
CompressionResult = None
Chunk = None
# ChunkStrategy 已被移除
AnalysisDepth = None
LayeredAnalysisResult = None
Layer1Summary = None
Layer2ChunkAnalysis = None
Layer3RelationNetwork = None
Layer4Synthesis = None
AgentType = None
AgentResult = None
AgentMessage = None
MessageBus = None


def _import_phase_components():
    """延迟导入 Phase 组件"""
    global PHASE1_AVAILABLE, PHASE2_AVAILABLE, PHASE3_AVAILABLE
    global AdaptiveCompressor, SemanticChunker, LayeredHybridAnalyzer, MultiAgentCoordinator
    global CompressionResult, Chunk
    global AnalysisDepth, LayeredAnalysisResult
    global Layer1Summary, Layer2ChunkAnalysis, Layer3RelationNetwork, Layer4Synthesis
    global AgentType, AgentResult, AgentMessage, MessageBus
    
    if PHASE1_AVAILABLE:
        return
    
    try:
        from .adaptive_compressor import AdaptiveCompressor, CompressionResult
        from .semantic_chunker import SemanticChunker, Chunk
        from .layered_analyzer import (
            LayeredHybridAnalyzer, AnalysisDepth, LayeredAnalysisResult,
            Layer1Summary, Layer2ChunkAnalysis, Layer3RelationNetwork, Layer4Synthesis
        )
        from .multi_agent_analyzer import (
            MultiAgentCoordinator, AgentType, AgentResult,
            AgentMessage, MessageBus
        )
        PHASE1_AVAILABLE = True
        PHASE2_AVAILABLE = True
        PHASE3_AVAILABLE = True
    except ImportError as e:
        import logging
        logging.getLogger(__name__).warning(f"Phase 1-3 components not available: {e}")


# ============================================================================
# 数据类型定义
# ============================================================================

class UnderstandingDepth(Enum):
    """理解深度级别"""
    QUICK = "quick"           # 快速概览 (< 1s)
    STANDARD = "standard"     # 标准分析 (1-3s)
    DEEP = "deep"             # 深度理解 (3-10s)
    COMPREHENSIVE = "comprehensive"  # 全面分析 (> 10s)


class ComprehensionPhase(Enum):
    """理解阶段"""
    INITIAL = "initial"       # 初始阶段：快速扫描
    SURFACE = "surface"       # 表层理解：初步分析
    DEEP = "deep"             # 深度理解：多角度分析
    INTEGRATED = "integrated" # 整合理解：综合所有信息
    VALIDATED = "validated"   # 验证完成：确认理解正确


class ComprehensionState(Enum):
    """理解状态"""
    IDLE = "idle"
    COMPRESSING = "compressing"      # 压缩中
    CHUNKING = "chunking"           # 分块中
    ANALYZING = "analyzing"          # 分析中
    INTEGRATING = "integrating"       # 整合中
    VALIDATING = "validating"        # 验证中
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class UnderstandingConfig:
    """理解配置"""
    # 深度设置
    depth: UnderstandingDepth = UnderstandingDepth.STANDARD
    
    # Phase 启用
    use_compression: bool = True        # Phase 1
    use_layered: bool = True           # Phase 2
    use_multi_agent: bool = True        # Phase 3
    
    # 迭代设置
    max_iterations: int = 3            # 最大迭代次数
    convergence_threshold: float = 0.85 # 收敛阈值
    
    # 性能设置
    timeout_seconds: float = 30.0
    enable_streaming: bool = True
    
    # 知识积累
    enable_knowledge_accumulation: bool = True
    max_knowledge_items: int = 100
    
    # 缓存设置
    enable_caching: bool = True
    cache_ttl_seconds: int = 300


@dataclass
class ComprehensionProgress:
    """理解进度"""
    phase: ComprehensionPhase = ComprehensionPhase.INITIAL
    state: ComprehensionState = ComprehensionState.IDLE
    
    # 进度百分比
    overall_progress: float = 0.0
    
    # 各阶段进度
    compression_progress: float = 0.0
    chunking_progress: float = 0.0
    analysis_progress: float = 0.0
    integration_progress: float = 0.0
    
    # 迭代进度
    current_iteration: int = 1
    total_iterations: int = 1
    iteration_progress: float = 0.0
    
    # 收敛度
    convergence: float = 0.0
    
    # 时间
    elapsed_seconds: float = 0.0
    estimated_remaining: float = 0.0
    
    # 消息
    current_step: str = ""
    insights: List[str] = field(default_factory=list)


@dataclass
class KnowledgeItem:
    """知识条目"""
    id: str
    content: str
    category: str  # concept/fact/relationship/pattern/insight
    confidence: float
    source_chunk: Optional[int] = None
    learned_at: float = field(default_factory=time.time)
    usage_count: int = 0
    related_items: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    verified: bool = False


@dataclass
class UnderstandingContext:
    """理解上下文（跨轮次）"""
    # 会话ID
    session_id: str = ""
    
    # 原始文本历史
    text_history: List[str] = field(default_factory=list)
    
    # 已分析块
    analyzed_chunks: List[str] = field(default_factory=list)
    
    # 知识积累
    knowledge_base: Dict[str, KnowledgeItem] = field(default_factory=dict)
    
    # 关键发现
    key_findings: List[str] = field(default_factory=list)
    
    # 理解轨迹
    comprehension_trace: List[Dict[str, Any]] = field(default_factory=list)
    
    # 收敛状态
    converged_findings: Set[str] = field(default_factory=set)
    
    # 统计
    total_text_length: int = 0
    total_analysis_time: float = 0.0
    
    def add_knowledge(self, item: KnowledgeItem) -> None:
        """添加知识条目"""
        self.knowledge_base[item.id] = item
    
    def get_knowledge_by_category(self, category: str) -> List[KnowledgeItem]:
        """按类别获取知识"""
        return [k for k in self.knowledge_base.values() if k.category == category]
    
    def merge_findings(self, new_findings: List[str]) -> int:
        """合并发现，返回新增数量"""
        old_count = len(self.converged_findings)
        self.converged_findings.update(new_findings)
        return len(self.converged_findings) - old_count


@dataclass
class UnderstandingSession:
    """理解会话"""
    session_id: str
    config: UnderstandingConfig
    context: UnderstandingContext
    
    # 状态
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    
    # 进度
    progress: ComprehensionProgress = field(default_factory=ComprehensionProgress)
    
    # 结果
    current_result: Optional['ProgressiveResult'] = None
    
    # 组件状态
    compressor_state: Optional[CompressionResult] = None
    chunks: List[Chunk] = field(default_factory=list)
    layered_result: Optional[LayeredAnalysisResult] = None
    agent_results: Dict[str, AgentResult] = field(default_factory=dict)
    
    # 迭代状态
    iteration_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProgressiveResult:
    """渐进式理解结果"""
    session_id: str
    
    # 阶段结果
    compression_result: Optional[CompressionResult] = None
    chunking_result: List[Chunk] = field(default_factory=list)
    layered_result: Optional[LayeredAnalysisResult] = None
    agent_result: Optional[Dict[str, Any]] = None
    
    # 综合理解
    primary_understanding: str = ""
    key_insights: List[str] = field(default_factory=list)
    knowledge_graph: Dict[str, List[str]] = field(default_factory=dict)
    
    # 验证
    confidence: float = 0.0
    validation_notes: List[str] = field(default_factory=list)
    
    # 收敛信息
    converged: bool = False
    convergence_score: float = 0.0
    iterations_needed: int = 1
    
    # 进度
    progress: ComprehensionProgress = field(default_factory=ComprehensionProgress)
    
    # 元数据
    execution_time: float = 0.0
    phases_completed: int = 0
    total_phases: int = 3
    
    # 新积累的知识
    new_knowledge: List[KnowledgeItem] = field(default_factory=list)


# ============================================================================
# 进度追踪器
# ============================================================================

class ProgressTracker:
    """理解进度追踪器"""
    
    def __init__(self, total_phases: int = 3, max_iterations: int = 3):
        self.total_phases = total_phases
        self.max_iterations = max_iterations
        self.start_time = time.time()
        self.last_update = self.start_time
        
        # 阶段权重
        self.phase_weights = {
            "compression": 0.1,
            "chunking": 0.15,
            "analysis": 0.55,
            "integration": 0.2
        }
        
        # 阶段进度
        self.phase_progress = {
            "compression": 0.0,
            "chunking": 0.0,
            "analysis": 0.0,
            "integration": 0.0
        }
        
        # 迭代进度
        self.current_iteration = 1
        self.iteration_progress = 0.0
        
        # 洞察
        self.insights: List[str] = []
    
    def update_phase(self, phase: str, progress: float, insight: Optional[str] = None) -> None:
        """更新阶段进度"""
        self.phase_progress[phase] = min(1.0, max(0.0, progress))
        self.last_update = time.time()
        
        if insight:
            self.insights.append(insight)
    
    def update_iteration(self, iteration: int, progress: float = 0.0) -> None:
        """更新迭代进度"""
        self.current_iteration = iteration
        self.iteration_progress = progress
    
    def get_overall_progress(self) -> float:
        """计算总进度"""
        weighted = sum(
            w * p for w, p in zip(
                self.phase_weights.values(),
                self.phase_progress.values()
            )
        )
        
        # 加入迭代因子
        if self.max_iterations > 1:
            iter_factor = (self.current_iteration - 1 + self.iteration_progress) / self.max_iterations
            weighted = weighted * 0.7 + iter_factor * 0.3
        
        return min(1.0, weighted)
    
    def get_progress_snapshot(self) -> ComprehensionProgress:
        """获取进度快照"""
        elapsed = time.time() - self.start_time
        overall = self.get_overall_progress()
        
        # 估算剩余时间
        if overall > 0.01:
            estimated = elapsed / overall - elapsed
        else:
            estimated = 0.0
        
        return ComprehensionProgress(
            overall_progress=overall,
            compression_progress=self.phase_progress["compression"],
            chunking_progress=self.phase_progress["chunking"],
            analysis_progress=self.phase_progress["analysis"],
            integration_progress=self.phase_progress["integration"],
            current_iteration=self.current_iteration,
            total_iterations=self.max_iterations,
            iteration_progress=self.iteration_progress,
            elapsed_seconds=elapsed,
            estimated_remaining=max(0, estimated),
            current_step=self._get_current_step(),
            insights=self.insights[-5:]  # 最近5个洞察
        )
    
    def _get_current_step(self) -> str:
        """获取当前步骤描述"""
        if self.phase_progress["compression"] < 1.0:
            return "正在进行文本压缩..."
        elif self.phase_progress["chunking"] < 1.0:
            return "正在进行语义分块..."
        elif self.phase_progress["analysis"] < 0.5:
            return "正在进行深度分析..."
        elif self.phase_progress["analysis"] < 1.0:
            return "正在进行多角度分析..."
        elif self.phase_progress["integration"] < 1.0:
            return "正在进行知识整合..."
        else:
            return "理解完成"


# ============================================================================
# 知识积累器
# ============================================================================

class KnowledgeAccumulator:
    """知识积累器"""
    
    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        self.items: Dict[str, KnowledgeItem] = {}
        self.categories = ["concept", "fact", "relationship", "pattern", "insight"]
    
    def add(self, content: str, category: str, 
            confidence: float = 0.8, source: Optional[int] = None,
            tags: Optional[Set[str]] = None) -> KnowledgeItem:
        """添加知识条目"""
        item_id = str(uuid.uuid4())[:8]
        
        item = KnowledgeItem(
            id=item_id,
            content=content,
            category=category,
            confidence=confidence,
            source_chunk=source,
            tags=tags or set()
        )
        
        # 合并相似条目
        existing = self._find_similar(item)
        if existing:
            existing.usage_count += 1
            existing.confidence = max(existing.confidence, confidence)
            return existing
        
        # 添加新条目
        self.items[item_id] = item
        
        # 清理超限条目
        self._cleanup()
        
        return item
    
    def _find_similar(self, item: KnowledgeItem) -> Optional[KnowledgeItem]:
        """查找相似条目"""
        content_lower = item.content.lower()
        
        for existing in self.items.values():
            if existing.category != item.category:
                continue
            
            # 简单相似度检查：包含关系
            existing_lower = existing.content.lower()
            if content_lower in existing_lower or existing_lower in content_lower:
                return existing
            
            # 关键词重叠
            new_words = set(content_lower.split())
            old_words = set(existing_lower.split())
            overlap = len(new_words & old_words)
            if overlap >= 3 and overlap / max(len(new_words), len(old_words)) > 0.5:
                return existing
        
        return None
    
    def _cleanup(self) -> None:
        """清理超限条目"""
        if len(self.items) <= self.max_items:
            return
        
        # 按置信度和使用次数排序
        sorted_items = sorted(
            self.items.values(),
            key=lambda x: (x.confidence * 0.7 + x.usage_count * 0.3),
            reverse=True
        )
        
        # 保留前 max_items 个
        self.items = {item.id: item for item in sorted_items[:self.max_items]}
    
    def get_all(self) -> List[KnowledgeItem]:
        """获取所有知识条目"""
        return list(self.items.values())
    
    def get_by_category(self, category: str) -> List[KnowledgeItem]:
        """按类别获取"""
        return [i for i in self.items.values() if i.category == category]
    
    def get_by_tag(self, tag: str) -> List[KnowledgeItem]:
        """按标签获取"""
        return [i for i in self.items.values() if tag in i.tags]
    
    def get_knowledge_graph(self) -> Dict[str, List[str]]:
        """构建知识图谱"""
        graph: Dict[str, List[str]] = defaultdict(list)
        
        for item in self.items.values():
            key = item.category
            graph[key].append(item.content[:50])
        
        return dict(graph)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_items": len(self.items),
            "by_category": {},
            "avg_confidence": 0.0,
            "total_usage": 0
        }
        
        for cat in self.categories:
            cat_items = self.get_by_category(cat)
            stats["by_category"][cat] = len(cat_items)
        
        if self.items:
            stats["avg_confidence"] = sum(
                i.confidence for i in self.items.values()
            ) / len(self.items)
            stats["total_usage"] = sum(
                i.usage_count for i in self.items.values()
            )
        
        return stats


# ============================================================================
# 会话管理器
# ============================================================================

class SessionManager:
    """会话管理器"""
    
    def __init__(self, max_sessions: int = 100, ttl_seconds: float = 3600):
        self.sessions: Dict[str, UnderstandingSession] = {}
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
    
    def create_session(self, config: UnderstandingConfig) -> UnderstandingSession:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:12]
        
        session = UnderstandingSession(
            session_id=session_id,
            config=config,
            context=UnderstandingContext(session_id=session_id)
        )
        
        self.sessions[session_id] = session
        self._cleanup()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[UnderstandingSession]:
        """获取会话"""
        session = self.sessions.get(session_id)
        
        if session:
            session.last_active = time.time()
        
        return session
    
    def update_session(self, session: UnderstandingSession) -> None:
        """更新会话"""
        session.last_active = time.time()
        self.sessions[session.session_id] = session
    
    def close_session(self, session_id: str) -> None:
        """关闭会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def _cleanup(self) -> None:
        """清理过期会话"""
        now = time.time()
        
        expired = [
            sid for sid, s in self.sessions.items()
            if now - s.last_active > self.ttl_seconds
        ]
        
        for sid in expired:
            del self.sessions[sid]
        
        # 限制最大数量
        if len(self.sessions) > self.max_sessions:
            oldest = sorted(
                self.sessions.values(),
                key=lambda s: s.last_active
            )[:len(self.sessions) - self.max_sessions]
            
            for s in oldest:
                del self.sessions[s.session_id]
    
    def get_active_sessions(self) -> List[str]:
        """获取活跃会话ID列表"""
        return list(self.sessions.keys())
    
    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self.sessions)


# ============================================================================
# 渐进式理解主类
# ============================================================================

class ProgressiveUnderstanding:
    """
    渐进式理解器
    
    整合 Phase 1-3 的所有能力，实现真正的迭代式深度理解。
    """
    
    def __init__(self, config: Optional[UnderstandingConfig] = None):
        self.config = config or UnderstandingConfig()
        
        # 初始化 Phase 组件
        self._init_phase_components()
        
        # 会话管理器
        self.session_manager = SessionManager()
        
        # 全局知识积累（跨会话）
        self.global_knowledge = KnowledgeAccumulator(
            max_items=self.config.max_knowledge_items * 2
        )
    
    def _init_phase_components(self) -> None:
        """初始化 Phase 组件"""
        # 延迟导入 Phase 组件
        _import_phase_components()
        
        # Phase 1: 压缩和分块
        if PHASE1_AVAILABLE and self.config.use_compression:
            self.compressor = AdaptiveCompressor()
            self.chunker = SemanticChunker(chunk_size=1500)
        else:
            self.compressor = None
            self.chunker = None
        
        # Phase 2: 分层分析
        if PHASE2_AVAILABLE and self.config.use_layered:
            self.layered_analyzer = LayeredHybridAnalyzer()
        else:
            self.layered_analyzer = None
        
        # Phase 3: 多智能体
        if PHASE3_AVAILABLE and self.config.use_multi_agent:
            self.multi_agent = MultiAgentCoordinator()
        else:
            self.multi_agent = None
    
    def understand(
        self,
        text: str,
        task: str = "理解内容",
        session_id: Optional[str] = None,
        previous_findings: Optional[List[str]] = None
    ) -> ProgressiveResult:
        """
        执行渐进式理解
        
        Args:
            text: 要理解的文本
            task: 理解任务描述
            session_id: 会话ID（可选，用于跨轮次理解）
            previous_findings: 之前的发现（用于验证）
        
        Returns:
            ProgressiveResult: 理解结果
        """
        start_time = time.time()
        
        # 获取或创建会话
        if session_id:
            session = self.session_manager.get_session(session_id)
            if not session:
                session = self.session_manager.create_session(self.config)
        else:
            session = self.session_manager.create_session(self.config)
        
        # 添加到文本历史
        session.context.text_history.append(text)
        session.context.total_text_length += len(text)
        
        # 初始化进度追踪
        tracker = ProgressTracker(
            total_phases=sum([
                self.config.use_compression,
                self.config.use_layered,
                self.config.use_multi_agent
            ]),
            max_iterations=self.config.max_iterations
        )
        
        # 初始化结果
        result = ProgressiveResult(session_id=session.session_id)
        result.progress = tracker.get_progress_snapshot()
        
        try:
            # ===== Phase 1: 压缩和分块 =====
            if self.config.use_compression and self.compressor:
                result = self._execute_compression_phase(text, result, tracker)
                session.compressor_state = result.compression_result
            
            # ===== Phase 2: 分层分析 =====
            if self.config.use_layered and self.layered_analyzer:
                result = self._execute_layered_phase(
                    text, task, result, tracker, 
                    previous_findings, session.context
                )
                session.layered_result = result.layered_result
            
            # ===== Phase 3: 多智能体协同 =====
            if self.config.use_multi_agent and self.multi_agent:
                result = self._execute_multi_agent_phase(
                    text, task, result, tracker, session.context
                )
            
            # ===== 整合结果 =====
            result = self._integrate_results(result, session.context)
            
            # ===== 计算收敛度 =====
            result.convergence_score = self._calculate_convergence(
                result, previous_findings, session.context
            )
            result.converged = result.convergence_score >= self.config.convergence_threshold
            
            # ===== 更新会话 =====
            session.current_result = result
            session.progress = tracker.get_progress_snapshot()
            self.session_manager.update_session(session)
            
        except Exception as e:
            result.progress.state = ComprehensionState.FAILED
            result.validation_notes.append(f"理解失败: {str(e)}")
        
        # 统计
        result.execution_time = time.time() - start_time
        session.context.total_analysis_time += result.execution_time
        
        return result
    
    def _execute_compression_phase(
        self,
        text: str,
        result: ProgressiveResult,
        tracker: ProgressTracker
    ) -> ProgressiveResult:
        """执行压缩阶段"""
        tracker.update_phase("compression", 0.3, "开始文本压缩")
        
        # 根据深度选择压缩率
        target_ratio = {
            UnderstandingDepth.QUICK: 0.3,
            UnderstandingDepth.STANDARD: 0.5,
            UnderstandingDepth.DEEP: 0.7,
            UnderstandingDepth.COMPREHENSIVE: 0.9
        }.get(self.config.depth, 0.5)
        
        try:
            compression_result = self.compressor.compress(
                text, 
                target_ratio=target_ratio,
                preserve_structure=True
            )
            result.compression_result = compression_result
            tracker.update_phase("compression", 1.0, "压缩完成")
        except Exception as e:
            # 压缩失败，使用原文
            compression_result = CompressionResult(
                original_text=text,
                compressed_text=text,
                compression_ratio=1.0,
                preserved_key_points=[]
            )
            result.compression_result = compression_result
            tracker.update_phase("compression", 0.5, f"压缩失败: {str(e)}")
        
        return result
    
    def _execute_layered_phase(
        self,
        text: str,
        task: str,
        result: ProgressiveResult,
        tracker: ProgressTracker,
        previous_findings: Optional[List[str]],
        context: UnderstandingContext
    ) -> ProgressiveResult:
        """执行分层分析阶段"""
        tracker.update_phase("chunking", 0.3, "开始语义分块")
        
        # 压缩后的文本
        working_text = (
            result.compression_result.compressed_text 
            if result.compression_result else text
        )
        
        # 分块
        try:
            if self.chunker:
                chunks = self.chunker.chunk(
                    working_text, 
                    strategy=self._get_chunk_strategy()
                )
                result.chunking_result = chunks
                context.analyzed_chunks.extend([c.text for c in chunks])
            else:
                # 无分块器，使用简单分块
                chunks = self._simple_chunk(working_text)
                result.chunking_result = chunks
        except Exception as e:
            chunks = self._simple_chunk(working_text)
            result.chunking_result = chunks
        
        tracker.update_phase("chunking", 1.0, f"分块完成: {len(chunks)} 个块")
        tracker.update_phase("analysis", 0.2, "开始分层分析")
        
        # 分层分析
        try:
            # 选择分析深度
            depth_map = {
                UnderstandingDepth.QUICK: "quick",
                UnderstandingDepth.STANDARD: "standard",
                UnderstandingDepth.DEEP: "deep",
                UnderstandingDepth.COMPREHENSIVE: "comprehensive"
            }
            
            depth = AnalysisDepth(depth_map.get(self.config.depth, "standard"))
            
            layered_result = self.layered_analyzer.analyze(
                working_text,
                task=task,
                depth=depth
            )
            result.layered_result = layered_result
            
            # 提取关键洞察
            result.key_insights.extend(layered_result.layer4_synthesis.key_findings)
            
            tracker.update_phase("analysis", 1.0, "分层分析完成")
        except Exception as e:
            tracker.update_phase("analysis", 0.5, f"分层分析失败: {str(e)}")
        
        return result
    
    def _execute_multi_agent_phase(
        self,
        text: str,
        task: str,
        result: ProgressiveResult,
        tracker: ProgressTracker,
        context: UnderstandingContext
    ) -> ProgressiveResult:
        """执行多智能体阶段"""
        tracker.update_phase("analysis", 0.7, "开始多智能体分析")
        
        try:
            agent_result = self.multi_agent.analyze(
                text=text,
                task=task
            )
            result.agent_result = agent_result
            
            # 提取洞察
            if "final_report" in agent_result:
                final = agent_result["final_report"]
                result.key_insights.extend(final.get("key_findings", []))
            
            tracker.update_phase("analysis", 1.0, "多智能体分析完成")
        except Exception as e:
            tracker.update_phase("analysis", 0.8, f"多智能体分析失败: {str(e)}")
        
        return result
    
    def _integrate_results(
        self,
        result: ProgressiveResult,
        context: UnderstandingContext
    ) -> ProgressiveResult:
        """整合所有结果"""
        tracker = ProgressTracker()
        tracker.update_phase("integration", 0.5, "开始整合")
        
        # 综合主要理解
        understanding_parts = []
        
        # Layer 4 综合
        if result.layered_result:
            synthesis = result.layered_result.layer4_synthesis
            if synthesis.summary:
                understanding_parts.append(synthesis.summary)
        
        # Agent 最终报告
        if result.agent_result and "final_report" in result.agent_result:
            final = result.agent_result["final_report"]
            if final.get("summary"):
                understanding_parts.append(final["summary"])
        
        # 去重合并
        result.primary_understanding = self._merge_understandings(understanding_parts)
        
        # 构建知识图谱
        if self.config.enable_knowledge_accumulation:
            self._accumulate_knowledge(result, context)
        
        # 更新收敛发现
        context.merge_findings(result.key_insights)
        
        tracker.update_phase("integration", 1.0, "整合完成")
        result.progress = tracker.get_progress_snapshot()
        result.progress.phase = ComprehensionPhase.INTEGRATED
        
        return result
    
    def _calculate_convergence(
        self,
        result: ProgressiveResult,
        previous_findings: Optional[List[str]],
        context: UnderstandingContext
    ) -> float:
        """计算收敛度"""
        if not previous_findings:
            return 0.3  # 首次理解，收敛度较低
        
        # 检查新发现与之前发现的重叠
        new_findings = set(result.key_insights)
        old_findings = set(previous_findings)
        
        if not old_findings:
            return 0.3
        
        overlap = len(new_findings & old_findings)
        union = len(new_findings | old_findings)
        
        if union == 0:
            return 0.5
        
        jaccard = overlap / union
        
        # 考虑知识积累
        knowledge_factor = min(1.0, len(context.knowledge_base) / 20)
        
        return jaccard * 0.6 + knowledge_factor * 0.4
    
    def _accumulate_knowledge(
        self,
        result: ProgressiveResult,
        context: UnderstandingContext
    ) -> None:
        """积累知识"""
        accumulator = KnowledgeAccumulator(max_items=self.config.max_knowledge_items)
        
        # 从分层结果提取知识
        if result.layered_result:
            # 概念
            for concept in result.layered_result.layer2_chunks:
                if concept.main_topic:
                    item = accumulator.add(
                        content=concept.main_topic,
                        category="concept",
                        confidence=0.8,
                        source=concept.chunk_index
                    )
                    context.add_knowledge(item)
                    result.new_knowledge.append(item)
            
            # 关系
            for relation in result.layered_result.layer3_network.relations:
                item = accumulator.add(
                    content=f"{relation.source} -> {relation.relation_type.value} -> {relation.target}",
                    category="relationship",
                    confidence=0.7
                )
                context.add_knowledge(item)
                result.new_knowledge.append(item)
        
        # 从 Agent 结果提取洞察
        if result.agent_result and "final_report" in result.agent_result:
            for finding in result.agent_result["final_report"].get("key_findings", []):
                item = accumulator.add(
                    content=finding,
                    category="insight",
                    confidence=0.9
                )
                context.add_knowledge(item)
                result.new_knowledge.append(item)
        
        # 更新置信度
        result.confidence = sum(
            k.confidence for k in result.new_knowledge
        ) / max(1, len(result.new_knowledge))
    
    def _get_chunk_strategy(self) -> str:
        """获取分块策略"""
        return {
            UnderstandingDepth.QUICK: "sentence",
            UnderstandingDepth.STANDARD: "paragraph",
            UnderstandingDepth.DEEP: "topic",
            UnderstandingDepth.COMPREHENSIVE: "semantic"
        }.get(self.config.depth, "auto")
    
    def _simple_chunk(self, text: str) -> List[Chunk]:
        """简单分块（无 LLM 时使用）"""
        # 按段落分块
        paragraphs = text.split("\n\n")
        chunks = []
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                chunks.append(Chunk(
                    text=para.strip(),
                    chunk_index=i,
                    chunk_type="paragraph",
                    key_points=[],
                    summary=""
                ))
        
        return chunks if chunks else [Chunk(
            text=text,
            chunk_index=0,
            chunk_type="full",
            key_points=[],
            summary=""
        )]
    
    def _merge_understandings(self, parts: List[str]) -> str:
        """合并多个理解结果"""
        if not parts:
            return ""
        
        if len(parts) == 1:
            return parts[0]
        
        # 去重
        unique_parts = []
        seen = set()
        for part in parts:
            part_lower = part.lower()[:100]
            if part_lower not in seen:
                seen.add(part_lower)
                unique_parts.append(part)
        
        # 简单拼接
        return " | ".join(unique_parts[:3])
    
    def understand_streaming(
        self,
        text: str,
        task: str = "理解内容",
        session_id: Optional[str] = None
    ) -> Iterator[Tuple[str, ProgressiveResult, float]]:
        """
        流式理解
        
        Yields:
            (step_name, partial_result, progress)
        """
        result = self.understand(text, task, session_id)
        
        phases = []
        if self.config.use_compression:
            phases.append("compression")
        if self.config.use_layered:
            phases.append("layered")
        if self.config.use_multi_agent:
            phases.append("multi_agent")
        
        for i, phase in enumerate(phases):
            progress = (i + 1) / len(phases)
            yield (phase, result, progress)
            
            # 模拟延迟以支持流式展示
            if self.config.enable_streaming:
                time.sleep(0.1)
        
        yield ("complete", result, 1.0)
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "progress": session.progress.overall_progress,
            "total_text_length": session.context.total_text_length,
            "total_analysis_time": session.context.total_analysis_time,
            "knowledge_count": len(session.context.knowledge_base),
            "findings_count": len(session.context.converged_findings),
            "last_active": session.last_active
        }
    
    def get_knowledge_graph(self, session_id: Optional[str] = None) -> Dict[str, List[str]]:
        """获取知识图谱"""
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session:
                return {
                    cat: [k.content for k in session.context.get_knowledge_by_category(cat)]
                    for cat in ["concept", "fact", "relationship", "pattern", "insight"]
                }
        
        return self.global_knowledge.get_knowledge_graph()
    
    def close_session(self, session_id: str) -> None:
        """关闭会话"""
        self.session_manager.close_session(session_id)


# ============================================================================
# 便捷函数
# ============================================================================

def create_progressive_understander(
    depth: str = "standard",
    **kwargs
) -> ProgressiveUnderstanding:
    """
    创建渐进式理解器
    
    Args:
        depth: 理解深度 ("quick", "standard", "deep", "comprehensive")
        **kwargs: 其他配置参数
    
    Returns:
        ProgressiveUnderstanding 实例
    """
    depth_map = {
        "quick": UnderstandingDepth.QUICK,
        "standard": UnderstandingDepth.STANDARD,
        "deep": UnderstandingDepth.DEEP,
        "comprehensive": UnderstandingDepth.COMPREHENSIVE
    }
    
    config = UnderstandingConfig(
        depth=depth_map.get(depth, UnderstandingDepth.STANDARD),
        **kwargs
    )
    
    return ProgressiveUnderstanding(config)


def quick_understand(
    text: str,
    task: str = "理解",
    depth: str = "standard"
) -> Dict[str, Any]:
    """
    快速理解
    
    Args:
        text: 文本
        task: 任务
        depth: 深度
    
    Returns:
        简化的理解结果
    """
    understander = create_progressive_understander(depth=depth)
    result = understander.understand(text, task)
    
    return {
        "session_id": result.session_id,
        "understanding": result.primary_understanding,
        "insights": result.key_insights[:5],
        "confidence": result.confidence,
        "converged": result.converged,
        "knowledge_count": len(result.new_knowledge),
        "execution_time": result.execution_time
    }


# ============================================================================
# Chunk 数据类（兼容 Phase 1）
# ============================================================================

@dataclass
class Chunk:
    """文本块（兼容 Phase 1）"""
    text: str
    chunk_index: int
    chunk_type: str = "general"
    key_points: List[str] = field(default_factory=list)
    summary: str = ""
    entities: List[str] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)
    main_topic: Optional[str] = None


@dataclass
class CompressionResult:
    """压缩结果"""
    original_text: str
    compressed_text: str
    compression_ratio: float
    preserved_key_points: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
