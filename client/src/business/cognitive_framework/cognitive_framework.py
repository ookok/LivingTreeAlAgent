"""
CognitiveFramework - 认知框架主类

集成所有认知中间件组件，提供统一的认知能力接口。

架构设计：
- MentalModelBuilder: 心理表征
- AttentionController: 注意力控制
- MetaReasoningEngine: 元认知监控
- ExperienceManager: 经验档案
- IdeaGenerator: 创意引擎

核心工作流：
1. 输入处理 → MentalModelBuilder → 概念图
2. 任务调度 → AttentionController → 优先级调度
3. 质量监控 → MetaReasoningEngine → 置信度评估
4. 经验积累 → ExperienceManager → 案例存储
5. 创意生成 → IdeaGenerator → 多模型投票

使用示例：
    cf = CognitiveFramework()
    
    # 处理用户请求
    result = cf.process_request(
        query="如何提高工作效率",
        context={"user_id": "123", "session_id": "abc"}
    )
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from .mental_model_builder import MentalModelBuilder, ConceptGraph
from .attention_controller import AttentionController, PriorityLevel
from .meta_reasoning_engine import MetaReasoningEngine, VerificationReport
from .experience_manager import ExperienceManager, CaseRecord
from .idea_generator import IdeaGenerator, GenerationResult

# 长任务管理集成（延迟导入避免循环依赖）
try:
    from client.src.business.long_task import get_long_task_integration, LongTaskIntegration
    _long_task_available = True
except ImportError:
    _long_task_available = False
    LongTaskIntegration = None


@dataclass
class ProcessingResult:
    """处理结果"""
    success: bool = False
    content: str = ""
    confidence: float = 0.0
    mental_model: Optional[ConceptGraph] = None
    verification_report: Optional[VerificationReport] = None
    related_cases: List[CaseRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "confidence": self.confidence,
            "mental_model": self.mental_model.to_dict() if self.mental_model else None,
            "verification_report": self.verification_report.to_dict() if self.verification_report else None,
            "related_cases": [case.to_dict() for case in self.related_cases],
            "metadata": self.metadata,
            "processing_time_ms": self.processing_time_ms
        }


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    name: str
    handler: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    priority: str = "medium"
    requires_attention: bool = False


class CognitiveFramework:
    """认知框架主类"""
    
    def __init__(self):
        self._logger = logger.bind(component="CognitiveFramework")
        
        # 初始化认知组件
        self._mental_model_builder = MentalModelBuilder()
        self._attention_controller = AttentionController()
        self._meta_reasoning_engine = MetaReasoningEngine()
        self._experience_manager = ExperienceManager()
        self._idea_generator = IdeaGenerator()
        
        # 集成长任务管理系统
        self._long_task_integration = None
        self._init_long_task_integration()
        
        # 运行状态
        self._running = False
        
        # 事件回调
        self._on_result_callback = None
        self._on_fallback_callback = None
        
        self._logger.info("认知框架初始化完成")
    
    def _init_long_task_integration(self):
        """初始化长任务管理系统集成"""
        if _long_task_available:
            try:
                self._long_task_integration = get_long_task_integration()
                self._logger.info("✓ 集成 LongTaskIntegration")
            except Exception as e:
                self._logger.warning(f"LongTaskIntegration 集成失败: {e}")
        else:
            self._logger.debug("LongTaskIntegration 不可用")
    
    async def start(self):
        """启动认知框架"""
        if self._running:
            return
        
        self._running = True
        self._logger.info("启动认知框架")
        
        # 启动注意力控制器
        await self._attention_controller.start()
        
        # 注册事件监听器
        self._attention_controller.add_listener(self._on_task_event)
    
    async def stop(self):
        """停止认知框架"""
        self._running = False
        await self._attention_controller.stop()
        self._logger.info("停止认知框架")
    
    def set_result_callback(self, callback: Callable):
        """设置结果回调"""
        self._on_result_callback = callback
    
    def set_fallback_callback(self, callback: Callable):
        """设置降级处理回调"""
        self._on_fallback_callback = callback
        self._meta_reasoning_engine.set_fallback_callback(callback)
    
    async def process_request(self, query: str, context: Dict = None) -> ProcessingResult:
        """
        处理用户请求（完整工作流）
        
        Args:
            query: 用户查询
            context: 上下文信息
        
        Returns:
            处理结果
        """
        start_time = datetime.now()
        context = context or {}
        
        try:
            # Step 1: 构建心理模型
            self._logger.debug("Step 1: 构建心理模型")
            mental_model = self._mental_model_builder.build_from_text(
                text=query,
                domain=context.get("domain", ""),
                source="user_query"
            )
            
            # Step 2: 检索相关经验
            self._logger.debug("Step 2: 检索相关经验")
            related_cases = self._experience_manager.retrieve_similar(
                query=query,
                limit=3,
                domain=context.get("domain")
            )
            
            # Step 3: 生成回答（简化版）
            self._logger.debug("Step 3: 生成回答")
            content = self._generate_response(query, mental_model, related_cases)
            
            # Step 4: 元认知评估
            self._logger.debug("Step 4: 元认知评估")
            verification_report = await self._meta_reasoning_engine.evaluate(
                text=content,
                context={"query": query, "related_cases": len(related_cases)}
            )
            
            # Step 5: 存储经验
            if verification_report.confidence.overall >= 0.5:
                self._logger.debug("Step 5: 存储经验")
                self._experience_manager.store_case({
                    "problem": query,
                    "problem_type": "query",
                    "domain": context.get("domain", "general"),
                    "solution": content,
                    "outcome": "success" if verification_report.confidence.overall >= 0.7 else "partial",
                    "confidence": verification_report.confidence.overall,
                    "tags": ["auto", "query"]
                })
            
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = ProcessingResult(
                success=True,
                content=content,
                confidence=verification_report.confidence.overall,
                mental_model=mental_model,
                verification_report=verification_report,
                related_cases=related_cases,
                metadata={
                    "domain": context.get("domain"),
                    "user_id": context.get("user_id"),
                    "session_id": context.get("session_id")
                },
                processing_time_ms=processing_time_ms
            )
            
            # 触发回调
            if self._on_result_callback:
                self._on_result_callback(result)
            
            return result
        
        except Exception as e:
            self._logger.error(f"请求处理失败: {e}")
            
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ProcessingResult(
                success=False,
                content=f"处理失败: {str(e)}",
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                metadata={"error": str(e)}
            )
    
    def _generate_response(self, query: str, mental_model: ConceptGraph, related_cases: List[CaseRecord]) -> str:
        """生成回答（简化版）"""
        # 检查是否有相关案例
        if related_cases:
            # 使用最相关的案例
            best_case = related_cases[0]
            if best_case.confidence >= 0.7:
                return f"根据经验，{best_case.solution}"
        
        # 如果没有案例，生成简单回答
        concepts = mental_model.search(query, limit=5)
        concept_labels = [c.label for c in concepts]
        
        if concept_labels:
            return f"关于 '{query}'，我识别到以下关键概念：{', '.join(concept_labels)}。这是一个需要深入分析的问题。"
        else:
            return f"我来分析一下 '{query}' 这个问题..."
    
    def submit_task(self, task_info: TaskInfo) -> str:
        """
        提交任务
        
        Args:
            task_info: 任务信息
        
        Returns:
            任务ID
        """
        return self._attention_controller.submit_task(
            name=task_info.name,
            handler=task_info.handler,
            params=task_info.params,
            priority=task_info.priority,
            task_id=task_info.task_id
        )
    
    def get_task(self, task_id: str):
        """获取任务"""
        return self._attention_controller.get_task(task_id)
    
    async def generate_ideas(self, prompt: str, num_ideas: int = 5) -> GenerationResult:
        """
        生成创意
        
        Args:
            prompt: 创意提示
            num_ideas: 创意数量
        
        Returns:
            生成结果
        """
        return await self._idea_generator.generate(prompt, num_ideas)
    
    def store_case(self, case_data: Dict) -> str:
        """存储案例"""
        return self._experience_manager.store_case(case_data)
    
    def retrieve_cases(self, query: str, limit: int = 5) -> List[CaseRecord]:
        """检索案例"""
        return self._experience_manager.retrieve_similar(query, limit)
    
    def build_mental_model(self, text: str, domain: str = "") -> ConceptGraph:
        """构建心理模型"""
        return self._mental_model_builder.build_from_text(text, domain)
    
    async def evaluate_content(self, text: str, context: Dict = None) -> VerificationReport:
        """评估内容"""
        return await self._meta_reasoning_engine.evaluate(text, context)
    
    def _on_task_event(self, event: Dict):
        """处理任务事件"""
        event_type = event.get("type")
        data = event.get("data", {})
        
        self._logger.debug(f"任务事件: {event_type} - {data}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "mental_model_builder": {
                "name": "MentalModelBuilder",
                "description": "心理表征模块"
            },
            "attention_controller": self._attention_controller.get_stats(),
            "meta_reasoning_engine": self._meta_reasoning_engine.get_stats(),
            "experience_manager": self._experience_manager.get_statistics(),
            "idea_generator": self._idea_generator.get_statistics(),
            "running": self._running
        }
    
    def add_knowledge(self, key: str, value: Any):
        """添加知识到元认知引擎"""
        self._meta_reasoning_engine.add_knowledge(key, value)
    
    def register_idea_model(self, model_name: str, generator: Callable):
        """注册创意生成模型"""
        self._idea_generator.register_model(model_name, generator)
    
    # ===== 长任务处理方法 =====
    
    def has_long_task_support(self) -> bool:
        """检查是否支持长任务"""
        return self._long_task_integration is not None
    
    async def process_long_document(self, file_path: str, context: Dict = None) -> Dict:
        """
        处理超长文档（自动调用长任务管理系统）
        
        Args:
            file_path: 文件路径
            context: 上下文信息
        
        Returns:
            处理结果
        """
        context = context or {}
        
        if not self._long_task_integration:
            return {
                "success": False,
                "error": "长任务管理系统未集成"
            }
        
        try:
            # 使用长任务系统处理文档
            result = await self._long_task_integration.execute_long_task(
                "document_processing",
                file_path=file_path,
                **context
            )
            
            # 如果成功，构建心理模型并存储经验
            if result.get("status") == "completed":
                # 构建心理模型
                model = self.build_mental_model(result.get("summary", ""))
                
                # 存储到经验档案
                self.store_case({
                    "problem": f"处理文档: {file_path}",
                    "problem_type": "document_processing",
                    "domain": context.get("domain", "document"),
                    "solution": result.get("summary", ""),
                    "outcome": "success",
                    "confidence": 0.8,
                    "tags": ["document", "long_task"]
                })
                
                result["mental_model_stats"] = model.get_statistics()
            
            return result
        
        except Exception as e:
            self._logger.error(f"长文档处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_long_conversation(self, messages: List[Dict], context: Dict = None) -> Dict:
        """
        处理超长对话（自动调用长任务管理系统）
        
        Args:
            messages: 对话消息列表
            context: 上下文信息
        
        Returns:
            处理结果
        """
        context = context or {}
        
        if not self._long_task_integration:
            return {
                "success": False,
                "error": "长任务管理系统未集成"
            }
        
        try:
            # 使用长任务系统处理长对话
            result = await self._long_task_integration.handle_long_conversation(
                messages,
                **context
            )
            
            # 提取关键信息构建心理模型
            full_text = "\n".join([msg.get("content", "") for msg in messages])
            model = self.build_mental_model(full_text, domain=context.get("domain", "conversation"))
            
            # 存储经验
            self.store_case({
                "problem": f"处理长对话 ({len(messages)} 条消息)",
                "problem_type": "conversation",
                "domain": context.get("domain", "conversation"),
                "solution": result.get("response", ""),
                "outcome": "success",
                "confidence": 0.75,
                "tags": ["conversation", "long_task"]
            })
            
            result["mental_model_stats"] = model.get_statistics()
            
            return result
        
        except Exception as e:
            self._logger.error(f"长对话处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_long_task(self, task_type: str, **kwargs) -> Dict:
        """
        执行长任务（统一接口）
        
        Args:
            task_type: 任务类型
                - document_processing: 文档处理
                - knowledge_retrieval: 知识检索
                - model_training: 模型训练
                - data_analysis: 数据分析
                - report_generation: 报告生成
        
        Returns:
            任务执行结果
        """
        if not self._long_task_integration:
            return {
                "success": False,
                "error": "长任务管理系统未集成"
            }
        
        try:
            result = await self._long_task_integration.execute_long_task(task_type, **kwargs)
            
            # 如果是知识检索，将结果添加到经验档案
            if task_type == "knowledge_retrieval":
                query = kwargs.get("query", "")
                result_count = len(result.get("results", []))
                
                self.store_case({
                    "problem": query,
                    "problem_type": "knowledge_retrieval",
                    "domain": kwargs.get("domain", "knowledge"),
                    "solution": f"检索到 {result_count} 条相关结果",
                    "outcome": "success",
                    "confidence": 0.7,
                    "tags": ["knowledge", "retrieval"]
                })
            
            # 如果是报告生成，评估报告质量
            if task_type == "report_generation":
                report = result.get("report", "")
                if report:
                    verification = await self.evaluate_content(report)
                    result["quality_score"] = verification.confidence.overall
            
            return result
        
        except Exception as e:
            self._logger.error(f"长任务执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_long_task_status(self, task_id: str) -> Optional[Dict]:
        """获取长任务状态"""
        if not self._long_task_integration:
            return None
        
        return self._long_task_integration.get_task_status(task_id)
    
    def cancel_long_task(self, task_id: str):
        """取消长任务"""
        if self._long_task_integration:
            self._long_task_integration.cancel_task(task_id)


# 全局单例
_cognitive_framework: Optional[CognitiveFramework] = None


def get_cognitive_framework() -> CognitiveFramework:
    """获取认知框架单例"""
    global _cognitive_framework
    if _cognitive_framework is None:
        _cognitive_framework = CognitiveFramework()
    return _cognitive_framework


async def init_cognitive_framework() -> CognitiveFramework:
    """初始化认知框架"""
    cf = get_cognitive_framework()
    await cf.start()
    return cf
