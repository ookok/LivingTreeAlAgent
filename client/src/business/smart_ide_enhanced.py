"""
智能IDE系统与上下文增强器集成
实现长期增强的上下文管理策略
"""

from typing import Optional, Dict, List, Any, AsyncGenerator

# 导入现有组件
from business.smart_ide_game.ai_coding_assistant import AICodingAssistant, TaskType, AITask
from business.model_hub.manager import ModelHubManager
from business.model_store.store_manager import ModelStoreManager
from business.rag_anything import MultimodalRAGPipeline, CrossModalKnowledgeGraph
from business.multimodal_support import MultimodalManager
from business.tier_model.intelligent_router import IntelligentRouter
from business.fusion_rag.l4_aware_router import L4AwareRouter
from business.smolllm2.l0_integration import L0Router

# 导入增强组件
from business.context_enhancer import ContextCompressionEnhancer, IntentStateManager, ContextLevel
from business.enhanced_intent_classifier import EnhancedIntentClassifier, IntentType, SecondaryIntent, IntentResult
from business.constitutional_prompt import ConstitutionalPromptBuilder, HierarchicalSummarizer
from business.task_planning import TaskPlanner, TaskExecutor
from business.git_intelligent import GitManager
from business.performance_optimization import PerformanceOptimizer, ModelLoadBalancer
from business.transparent_reasoning import ReasoningManager
from business.personalized_learning import PersonalizedLearningSystem


class SmartIDESystem:
    """
    智能IDE系统
    整合现有组件，实现本地大模型前端智能IDE功能
    """
    
    def __init__(self):
        # 初始化现有组件
        self.ai_coding_assistant = AICodingAssistant()
        self.model_hub = ModelHubManager()
        self.model_store = ModelStoreManager()
        self.multimodal_manager = MultimodalManager()
        self.intelligent_router = IntelligentRouter()
        self.l4_aware_router = L4AwareRouter()
        self.l0_router = L0Router()
        
        # 初始化增强组件
        self.context_enhancer = ContextCompressionEnhancer()
        self.intent_manager = IntentStateManager()
        self.intent_classifier = EnhancedIntentClassifier()
        self.prompt_builder = ConstitutionalPromptBuilder()
        self.summarizer = HierarchicalSummarizer()
        self.task_planner = TaskPlanner()
        self.task_executor = TaskExecutor(self.task_planner)
        self.git_manager = GitManager()
        self.performance_optimizer = PerformanceOptimizer()
        self.model_load_balancer = ModelLoadBalancer()
        self.reasoning_manager = ReasoningManager()
        self.personalized_learning = PersonalizedLearningSystem()
        
        # 初始化RAG系统
        self.knowledge_graph = CrossModalKnowledgeGraph()
        self.rag_pipeline = MultimodalRAGPipeline(self.knowledge_graph, None)
        
        # 注册任务执行回调
        self._register_task_executors()
        
        # 启动服务
        self._start_services()
    
    def _register_task_executors(self):
        """注册任务执行回调"""
        # 代码生成任务
        self.task_executor.register_callback(
            TaskType.CODE_GENERATION,
            self._execute_code_generation
        )
        
        # 代码补全任务
        self.task_executor.register_callback(
            TaskType.CODE_COMPLETION,
            self._execute_code_completion
        )
        
        # 错误诊断任务
        self.task_executor.register_callback(
            TaskType.ERROR_DIAGNOSIS,
            self._execute_error_diagnosis
        )
        
        # 性能优化任务
        self.task_executor.register_callback(
            TaskType.PERFORMANCE_OPTIMIZATION,
            self._execute_performance_optimization
        )
        
        # 文档生成任务
        self.task_executor.register_callback(
            TaskType.DOCUMENTATION,
            self._execute_documentation
        )
        
        # 测试生成任务
        self.task_executor.register_callback(
            TaskType.TEST_GENERATION,
            self._execute_test_generation
        )
    
    async def _execute_code_generation(self, task: AITask) -> str:
        """执行代码生成任务"""
        return await self.ai_coding_assistant.code_generator.generate_code(
            task.prompt,
            task.context.get("language", "python"),
            task.context
        )
    
    async def _execute_code_completion(self, task: AITask) -> str:
        """执行代码补全任务"""
        return await self.ai_coding_assistant.code_generator.complete_code(
            task.context.get("code", ""),
            task.context.get("position", 0),
            task.context.get("language", "python")
        )
    
    async def _execute_error_diagnosis(self, task: AITask) -> List[Dict]:
        """执行错误诊断任务"""
        return self.ai_coding_assistant.error_diagnoser.diagnose(
            task.prompt,
            task.context.get("code", ""),
            task.context.get("language", "python")
        )
    
    async def _execute_performance_optimization(self, task: AITask) -> List[Dict]:
        """执行性能优化任务"""
        return await self.ai_coding_assistant.performance_analyzer.analyze(
            task.context.get("code", ""),
            task.context.get("language", "python")
        )
    
    async def _execute_documentation(self, task: AITask) -> str:
        """执行文档生成任务"""
        return await self.ai_coding_assistant.doc_generator.generate_docstring(
            task.context.get("code", ""),
            task.context.get("language", "python")
        )
    
    async def _execute_test_generation(self, task: AITask) -> List[Dict]:
        """执行测试生成任务"""
        return await self.ai_coding_assistant.test_generator.generate_tests(
            task.context.get("code", ""),
            task.context.get("language", "python")
        )
    
    def _start_services(self):
        """启动服务"""
        # 启动AI助手
        import asyncio
        asyncio.create_task(self.ai_coding_assistant.start())
        
        # 注册默认模型
        self._register_default_models()
    
    def _register_default_models(self):
        """注册默认模型"""
        # 注册模型到负载均衡器
        models = [
            {
                "id": "llama3.1:8b",
                "info": {
                    "supported_tasks": ["code_generation", "code_completion", "error_diagnosis"],
                    "max_context_size": 8192,
                    "performance_score": 0.85
                }
            },
            {
                "id": "gemma2:2b",
                "info": {
                    "supported_tasks": ["code_completion", "error_diagnosis"],
                    "max_context_size": 4096,
                    "performance_score": 0.7
                }
            },
            {
                "id": "llama3.1:70b",
                "info": {
                    "supported_tasks": ["code_generation", "documentation", "test_generation"],
                    "max_context_size": 32768,
                    "performance_score": 0.95
                }
            }
        ]
        
        for model in models:
            self.model_load_balancer.register_model(model["id"], model["info"])
    
    def _build_constitutional_prompt(self, intent: str, context: str, clarified_details: List[str] = None, assumptions: List[str] = None, risks: List[str] = None) -> str:
        """
        构建宪法式Prompt
        """
        return self.prompt_builder.build_prompt(
            intent=intent,
            context=context,
            role_type="frontend",
            clarified_details=clarified_details,
            assumptions=assumptions,
            risks=risks
        )
    
    def _enhance_context(self, context: str, scope: str = "general") -> str:
        """
        增强上下文
        """
        # 添加上下文到增强器
        self.context_enhancer.add_context(context, ContextLevel.L3, scope)
        
        # 生成分层摘要
        l0_summary = self.summarizer.generate_summary(context, "L0")
        l1_summary = self.summarizer.generate_summary(context, "L1")
        l2_summary = self.summarizer.generate_summary(context, "L2")
        
        # 构建分层上下文
        enhanced_context = f"""
## L0 文件元信息
{l0_summary}

## L1 接口/类签名
{l1_summary}

## L2 关键函数逻辑
{l2_summary}

## L3 详细代码（按需加载）
[详细代码已压缩，如需查看请明确请求]
        """
        
        return enhanced_context
    
    async def process_natural_language(self, prompt: str, context: Dict[str, Any] = None, session_id: str = "default") -> Dict[str, Any]:
        """
        处理自然语言请求
        
        Args:
            prompt: 自然语言请求
            context: 上下文信息
            session_id: 会话ID
            
        Returns:
            Dict: 处理结果
        """
        # 开始推理过程
        tree_id = self.reasoning_manager.start_reasoning()
        
        try:
            # 创建或更新意图状态
            intent_state = self.intent_manager.get_intent_state(session_id)
            if not intent_state:
                intent_state = self.intent_manager.create_intent_state(session_id, prompt)
            
            # 分析用户意图（增强L0意图分类能力）
            self.reasoning_manager.add_thought(
                f"分析用户意图: {prompt}",
                parent_id=tree_id
            )
            
            # 使用增强的意图分类器
            intent_result = self.intent_classifier.classify_intent(prompt)
            self.reasoning_manager.add_decision(
                f"意图分类结果: {intent_result.primary_intent.value}",
                parent_id=tree_id,
                confidence=intent_result.confidence
            )
            
            # 更新意图状态
            self.intent_manager.update_intent_state(
                session_id,
                task=intent_result.primary_intent.value,
                entities=intent_result.entities,
                constraints=intent_result.constraints
            )
            
            # 路由决策
            route_result = self.intelligent_router.route(prompt, context or {})
            self.reasoning_manager.add_decision(
                f"路由决策: {route_result.decision.value}",
                parent_id=tree_id,
                confidence=route_result.confidence
            )
            
            # 增强上下文
            if context and "code" in context:
                enhanced_context = self._enhance_context(context["code"], "code")
                context["enhanced_context"] = enhanced_context
            
            # 构建宪法式Prompt（实现宪法式Prompt结构）
            constitutional_prompt = self._build_constitutional_prompt(
                prompt,
                context.get("enhanced_context", ""),
                clarified_details=intent_state.clarified_details,
                assumptions=intent_state.assumptions,
                risks=intent_state.risks
            )
            
            # 任务规划
            self.reasoning_manager.add_thought(
                "生成任务计划",
                parent_id=tree_id
            )
            task_tree = await self.task_planner.plan_from_natural_language(constitutional_prompt)
            
            # 执行任务
            self.reasoning_manager.add_action(
                "执行任务计划",
                parent_id=tree_id
            )
            success = await self.task_executor.execute_task_tree(task_tree.root_task.id)
            
            # 收集结果
            results = {}
            for task_id, task in task_tree.tasks.items():
                if task.status == TaskStatus.COMPLETED and task.result:
                    results[task.title] = task.result
            
            # 记录学习
            self.personalized_learning.learn_from_action(
                "user",
                TaskType.CODE_GENERATION if "生成" in prompt else TaskType.CODE_COMPLETION,
                prompt,
                **(context or {})
            )
            
            return {
                "success": success,
                "results": results,
                "reasoning_tree": tree_id,
                "context_stats": self.context_enhancer.get_stats(),
                "intent_result": {
                    "primary_intent": intent_result.primary_intent.value,
                    "secondary_intent": intent_result.secondary_intent.value if intent_result.secondary_intent else None,
                    "confidence": intent_result.confidence,
                    "entities": intent_result.entities,
                    "constraints": intent_result.constraints
                }
            }
            
        except Exception as e:
            self.reasoning_manager.add_error(
                f"处理失败: {str(e)}",
                parent_id=tree_id
            )
            return {
                "success": False,
                "error": str(e),
                "reasoning_tree": tree_id
            }
    
    async def process_screenshot(self, image_path: str, framework: str = "react", session_id: str = "default") -> Dict[str, Any]:
        """
        处理截图并生成代码
        
        Args:
            image_path: 截图路径
            framework: 目标框架
            session_id: 会话ID
            
        Returns:
            Dict: 生成结果
        """
        # 开始推理过程
        tree_id = self.reasoning_manager.start_reasoning()
        
        try:
            # 分析截图
            self.reasoning_manager.add_thought(
                "分析UI截图",
                parent_id=tree_id
            )
            
            # 生成代码
            self.reasoning_manager.add_action(
                f"生成{framework}代码",
                parent_id=tree_id
            )
            result = await self.multimodal_manager.process_image(image_path, framework)
            
            if result:
                self.reasoning_manager.add_observation(
                    "代码生成成功",
                    parent_id=tree_id
                )
                
                # 添加上下文
                self.context_enhancer.add_context(result.code, ContextLevel.L3, "generated_code")
                
                return {
                    "success": True,
                    "code": result.code,
                    "language": result.language,
                    "framework": result.framework,
                    "elements": [{
                        "type": elem.element_type.value,
                        "text": elem.text
                    } for elem in result.elements],
                    "reasoning_tree": tree_id,
                    "context_stats": self.context_enhancer.get_stats()
                }
            else:
                self.reasoning_manager.add_error(
                    "代码生成失败",
                    parent_id=tree_id
                )
                return {
                    "success": False,
                    "error": "代码生成失败",
                    "reasoning_tree": tree_id
                }
                
        except Exception as e:
            self.reasoning_manager.add_error(
                f"处理失败: {str(e)}",
                parent_id=tree_id
            )
            return {
                "success": False,
                "error": str(e),
                "reasoning_tree": tree_id
            }
    
    async def generate_commit_message(self) -> Optional[str]:
        """
        生成语义化提交信息
        
        Returns:
            str: 提交信息
        """
        # 获取Git变更
        repo_info = self.git_manager.analyze_repo()
        if "status" in repo_info:
            # 创建增量上下文
            diff_context = "\n".join(repo_info.get("status", []))
            if diff_context:
                # 添加上下文
                self.context_enhancer.add_context(diff_context, ContextLevel.L2, "git_diff")
        
        return self.git_manager.get_semantic_commit_suggestion()
    
    async def get_code_completion(self, code: str, position: int, language: str) -> List[Dict]:
        """
        获取代码补全建议
        
        Args:
            code: 代码
            position: 光标位置
            language: 语言
            
        Returns:
            List[Dict]: 补全建议
        """
        # 添加上下文
        self.context_enhancer.add_context(code, ContextLevel.L3, "code_edit")
        
        return await self.ai_coding_assistant.get_completion_suggestions(code, position, language)
    
    async def diagnose_error(self, error_message: str, code: str, language: str) -> List[Dict]:
        """
        诊断错误
        
        Args:
            error_message: 错误信息
            code: 代码
            language: 语言
            
        Returns:
            List[Dict]: 诊断结果
        """
        # 添加上下文
        error_context = f"Error: {error_message}\nCode: {code}"
        self.context_enhancer.add_context(error_context, ContextLevel.L3, "error")
        
        return await self.ai_coding_assistant.diagnose_error(error_message, code, language)
    
    async def get_performance_suggestions(self, code: str, language: str) -> List[Dict]:
        """
        获取性能优化建议
        
        Args:
            code: 代码
            language: 语言
            
        Returns:
            List[Dict]: 优化建议
        """
        # 添加上下文
        self.context_enhancer.add_context(code, ContextLevel.L3, "performance")
        
        return await self.ai_coding_assistant.analyze_performance(code, language)
    
    async def generate_documentation(self, code: str, language: str, style: str = "google") -> str:
        """
        生成文档
        
        Args:
            code: 代码
            language: 语言
            style: 文档风格
            
        Returns:
            str: 文档字符串
        """
        # 添加上下文
        self.context_enhancer.add_context(code, ContextLevel.L3, "documentation")
        
        return await self.ai_coding_assistant.generate_documentation(code, language, style)
    
    async def generate_tests(self, code: str, language: str, framework: str = "pytest") -> List[Dict]:
        """
        生成测试用例
        
        Args:
            code: 代码
            language: 语言
            framework: 测试框架
            
        Returns:
            List[Dict]: 测试用例
        """
        # 添加上下文
        self.context_enhancer.add_context(code, ContextLevel.L3, "testing")
        
        tests = await self.ai_coding_assistant.generate_tests(code, language, framework)
        return [{
            "name": test.name,
            "code": test.code,
            "input_data": test.input_data,
            "expected_output": test.expected_output
        } for test in tests]
    
    def get_recommendations(self, user_id: str) -> List[Dict]:
        """
        获取学习推荐
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Dict]: 推荐列表
        """
        recommendations = self.personalized_learning.get_recommendations(user_id)
        return [{
            "id": item.id,
            "title": item.title,
            "difficulty": item.difficulty,
            "estimated_time": item.estimated_time,
            "categories": item.categories
        } for item in recommendations]
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态
        
        Returns:
            Dict: 系统状态
        """
        return {
            "ai_assistant": self.ai_coding_assistant.get_assistant_stats(),
            "model_load_balancer": self.model_load_balancer.get_model_stats(),
            "performance": self.performance_optimizer.get_performance_stats(),
            "git": self.git_manager.analyze_repo(),
            "learning": self.personalized_learning.get_user_stats("user"),
            "reasoning": self.reasoning_manager.get_stats(),
            "context": self.context_enhancer.get_stats(),
            "intent": self.intent_manager.get_stats()
        }
    
    def visualize_reasoning(self, tree_id: str) -> Optional[str]:
        """
        可视化推理过程
        
        Args:
            tree_id: 推理树ID
            
        Returns:
            str: HTML可视化
        """
        return self.reasoning_manager.visualize(tree_id)


def create_smart_ide_system() -> SmartIDESystem:
    """
    创建智能IDE系统
    
    Returns:
        SmartIDESystem: 智能IDE系统实例
    """
    return SmartIDESystem()