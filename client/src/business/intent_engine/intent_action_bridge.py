# -*- coding: utf-8 -*-
"""
意图→执行桥接器 - IntentActionBridge
======================================

这是连接 IntentEngine（意图识别）和 ActionHandler（动作执行）的核心桥接。

**解决的问题**：
当前 IntentEngine 只能 parse() 出意图，但不会真正执行任务。
IntentActionBridge 在 parse 之后提供 execute() 方法，让意图引擎真正"动起来"。

**架构**：
```
用户输入 → IntentEngine.parse() → Intent → IntentActionBridge.execute() → ActionResult
                                         ↑
                                   ActionHandler (自动路由)
                                   ├── CodeGenerationHandler
                                   ├── CodeReviewHandler
                                   ├── CodeDebugHandler
                                   ├── KnowledgeQueryHandler
                                   ├── ConceptExplainerHandler
                                   └── FileOperationHandler
```

**使用方式**：
```python
from client.src.business.intent_engine import IntentEngine
from client.src.business.intent_engine.intent_action_bridge import IntentActionBridge

engine = IntentEngine()
bridge = IntentActionBridge(engine)

# 一行代码：意图 → 执行
intent = engine.parse("帮我写一个用户登录接口，用 FastAPI")
result = bridge.execute(intent)

print(result.output)        # 生成的代码
print(result.suggestions)    # 后续建议
print(result.artifacts)      # 产出物（文件路径等）

# 或者更简洁：parse_and_execute()
result = bridge.parse_and_execute("修复这个空指针异常")
```

Author: LivingTreeAI Team
Version: 1.0.0
from __future__ import annotations
"""


import time
import logging
from typing import Any, Dict, List, Optional, Type

from .intent_types import Intent, IntentType
from .action_handlers.base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
)
from .action_handlers import (
    CodeGenerationHandler,
    CodeReviewHandler,
    CodeDebugHandler,
    KnowledgeQueryHandler,
    ConceptExplainerHandler,
    FileOperationHandler,
)

logger = logging.getLogger(__name__)


def _get_system_defaults() -> Dict[str, str]:
    """从系统配置读取默认值，失败时回退到安全默认值"""
    try:
        from client.src.business.config_provider import get_ollama_url, get_l3_model
        return {
            "ollama_url": get_ollama_url(),
            "model_name": get_l3_model(),
        }
    except Exception as e:
        logger.warning(f"读取系统配置失败，使用默认值: {e}")
        return {
            "ollama_url": "http://www.mogoo.com.cn:8899/v1",
            "model_name": "qwen3.5:4b",
        }


class IntentActionBridge:
    """
    意图→执行桥接器
    
    职责：
    1. 管理所有已注册的 ActionHandler
    2. 根据 IntentType 自动路由到正确的 Handler
    3. 提供统一的执行入口（execute / parse_and_execute）
    4. 支持自定义 Handler 注册
    5. 执行日志和统计
    
    设计原则：
    - 开放封闭：内置 Handler 可被覆盖，新的 Handler 可随时注册
    - 单一入口：一个 execute() 搞定所有
    - 优雅降级：没有匹配的 Handler 时返回有用的信息而非报错
    """
    
    # 默认内置的处理器
    BUILTIN_HANDLERS = [
        CodeDebugHandler,          # P0: Bug修复（最高优先级）
        CodeGenerationHandler,     # P1: 代码生成
        CodeReviewHandler,         # P2: 代码审查
        FileOperationHandler,      # P3: 文件操作
        KnowledgeQueryHandler,     # P4: 知识查询
        ConceptExplainerHandler,   # P5: 概念解释
    ]
    
    def __init__(
        self,
        intent_engine=None,
        ollama_url: str = "",
        model_name: str = "",
        working_dir: str = ".",
        project_root: str = "",
        auto_register: bool = True,
    ):
        """
        初始化桥接器
        
        Args:
            intent_engine: IntentEngine 实例（可选，为 None 时延迟创建）
            ollama_url: LLM 服务地址（空字符串=从系统配置读取）
            model_name: 默认模型名称（空字符串=从系统配置读取 L3）
            working_dir: 工作目录
            project_root: 项目根目录
            auto_register: 是否自动注册内置处理器
        """
        # 从系统配置读取默认值（未显式传入时）
        _defaults = _get_system_defaults()
        self._intent_engine = intent_engine
        self._ollama_url = ollama_url or _defaults["ollama_url"]
        self._model_name = model_name or _defaults["model_name"]
        self._working_dir = working_dir
        self._project_root = project_root
        
        # 处理器注册表 {IntentType: [BaseActionHandler, ...]}
        self._handlers: Dict[IntentType, List[BaseActionHandler]] = {}
        # 所有处理器列表（用于遍历）
        self._all_handlers: List[BaseActionHandler] = []
        
        # 统计
        self._stats = {
            "total_executions": 0,
            "success_count": 0,
            "failed_count": 0,
            "clarify_count": 0,
            "no_handler_count": 0,
            "total_time": 0.0,
        }
        
        # 自动注册内置处理器
        if auto_register:
            for handler_class in self.BUILTIN_HANDLERS:
                self.register_handler(handler_class())
    
    @property
    def intent_engine(self):
        """获取 IntentEngine（延迟创建）"""
        if self._intent_engine is None:
            from .intent_engine import IntentEngine
            self._intent_engine = IntentEngine()
        return self._intent_engine
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        avg_time = (
            self._stats["total_time"] / self._stats["total_executions"]
            if self._stats["total_executions"] > 0
            else 0
        )
        return {
            **self._stats,
            "avg_time": f"{avg_time:.2f}s",
            "success_rate": (
                f"{self._stats['success_count'] / self._stats['total_executions']:.1%}"
                if self._stats["total_executions"] > 0
                else "N/A"
            ),
            "registered_handlers": len(self._all_handlers),
            "supported_intents": len(self._handlers),
        }
    
    # ── 注册管理 ────────────────────────────────────────────────────────
    
    def register_handler(self, handler: BaseActionHandler, override: bool = False):
        """
        注册动作处理器
        
        Args:
            handler: 处理器实例
            override: 是否覆盖已有处理器（按名称匹配）
        """
        handler_name = handler.name
        
        # 检查是否需要覆盖
        if override:
            self._all_handlers = [
                h for h in self._all_handlers if h.name != handler_name
            ]
            for intent_type in self._handlers:
                self._handlers[intent_type] = [
                    h for h in self._handlers[intent_type] if h.name != handler_name
                ]
        
        # 检查重复
        existing_names = {h.name for h in self._all_handlers}
        if handler_name in existing_names and not override:
            logger.warning(f"处理器 '{handler_name}' 已存在，使用 override=True 覆盖")
            return
        
        self._all_handlers.append(handler)
        
        for intent_type in handler.supported_intents:
            if intent_type not in self._handlers:
                self._handlers[intent_type] = []
            self._handlers[intent_type].append(handler)
        
        # 按优先级排序（数值越小越靠前）
        for intent_type in self._handlers:
            self._handlers[intent_type].sort(key=lambda h: h.priority)
        
        logger.debug(f"注册处理器: {handler_name} -> {[it.value for it in handler.supported_intents]}")
    
    def unregister_handler(self, name: str):
        """取消注册处理器"""
        self._all_handlers = [h for h in self._all_handlers if h.name != name]
        for intent_type in self._handlers:
            self._handlers[intent_type] = [
                h for h in self._handlers[intent_type] if h.name != name
            ]
    
    def get_handler(self, intent_type: IntentType) -> Optional[BaseActionHandler]:
        """获取处理指定意图类型的处理器（优先级最高的）"""
        handlers = self._handlers.get(intent_type, [])
        return handlers[0] if handlers else None
    
    def list_handlers(self) -> List[Dict[str, Any]]:
        """列出所有已注册的处理器"""
        return [
            {
                "name": h.name,
                "priority": h.priority,
                "supported_intents": [it.value for it in h.supported_intents],
            }
            for h in self._all_handlers
        ]
    
    # ── 核心执行 ──────────────────────────────────────────────────────────
    
    def execute(
        self,
        intent: Intent,
        **kwargs,
    ) -> ActionResult:
        """
        执行意图
        
        这是核心方法：接收一个 Intent，自动路由到正确的 Handler 并执行。
        
        Args:
            intent: IntentEngine.parse() 的返回结果
            **kwargs: 覆盖 ActionContext 的参数（如 model_name, temperature 等）
            
        Returns:
            ActionResult: 执行结果
            
        使用示例：
            engine = IntentEngine()
            bridge = IntentActionBridge(engine)
            
            intent = engine.parse("帮我写一个排序算法")
            result = bridge.execute(intent)
            print(result.output)
        """
        start = time.time()
        self._stats["total_executions"] += 1
        
        # 1. 构建执行上下文
        ctx = self._build_context(intent, **kwargs)
        
        # 2. 处理复合意图
        if intent.is_composite and intent.sub_intents:
            return self._execute_composite(ctx)
        
        # 3. 路由到处理器
        handler = self.get_handler(intent.intent_type)
        
        if handler is None:
            self._stats["no_handler_count"] += 1
            return self._no_handler_result(intent)
        
        # 4. 执行
        logger.info(
            f"[Bridge] 执行意图: {intent.intent_type.value} "
            f"(handler={handler.name}, action={intent.action}, target={intent.target})"
        )
        
        try:
            result = handler.handle(ctx)
        except Exception as e:
            logger.error(f"[Bridge] 处理器执行异常: {e}")
            result = ActionResult(
                status=ActionResultStatus.FAILED,
                error=f"处理器 '{handler.name}' 执行异常: {e}",
            )
        
        # 5. 更新统计
        execution_time = time.time() - start
        result.execution_time = execution_time
        self._stats["total_time"] += execution_time
        
        if result.is_success():
            self._stats["success_count"] += 1
        elif result.status == ActionResultStatus.NEED_CLARIFY:
            self._stats["clarify_count"] += 1
        else:
            self._stats["failed_count"] += 1

        # 6. 反馈到 EvolutionEngine（静默失败，不影响主流程）
        self._report_to_evolution(intent, result, execution_time)

        return result
    
    def parse_and_execute(
        self,
        query: str,
        **kwargs,
    ) -> ActionResult:
        """
        一站式：解析 + 执行
        
        Args:
            query: 用户自然语言查询
            **kwargs: 覆盖 ActionContext 的参数
            
        Returns:
            ActionResult: 执行结果
            
        使用示例：
            bridge = IntentActionBridge(engine)
            result = bridge.parse_and_execute("帮我写一个用户登录接口")
        """
        intent = self.intent_engine.parse(query)
        return self.execute(intent, **kwargs)
    
    def _build_context(self, intent: Intent, **kwargs) -> ActionContext:
        """
        构建动作执行上下文
        
        模型选择优先级：
        1. kwargs 显式传入的 model_name（最高）
        2. suggest_model() 根据意图自动路由
        3. 系统配置的默认模型（L3）
        """
        # 模型路由：根据意图复杂度自动选择模型
        routed_model = kwargs.get("model_name")
        if not routed_model:
            try:
                routed_model = self.suggest_model(intent)
                logger.debug(f"[Bridge] 模型路由: {intent.intent_type.value} → {routed_model}")
            except Exception as e:
                logger.debug(f"[Bridge] 模型路由失败，使用默认: {e}")
                routed_model = self._model_name

        return ActionContext(
            intent=intent,
            ollama_url=kwargs.get("ollama_url", self._ollama_url),
            model_name=routed_model,
            temperature=kwargs.get("temperature", 0.3),
            working_dir=kwargs.get("working_dir", self._working_dir),
            project_root=kwargs.get("project_root", self._project_root),
            timeout=kwargs.get("timeout", 300.0),
            stream=kwargs.get("stream", False),
            use_cache=kwargs.get("use_cache", True),
            extra=kwargs.get("extra", {}),
        )
    
    def _execute_composite(self, ctx: ActionContext) -> ActionResult:
        """执行复合意图"""
        intent = ctx.intent
        logger.info(f"[Bridge] 检测到复合意图，子意图数: {len(intent.sub_intents)}")
        
        results = []
        for i, sub_intent in enumerate(intent.sub_intents):
            logger.info(f"[Bridge] 执行子意图 {i+1}/{len(intent.sub_intents)}: {sub_intent.intent_type.value}")
            
            handler = self.get_handler(sub_intent.intent_type)
            if handler:
                # 子意图也走模型路由
                try:
                    sub_model = self.suggest_model(sub_intent)
                except Exception:
                    sub_model = ctx.model_name
                sub_ctx = ActionContext(
                    intent=sub_intent,
                    ollama_url=ctx.ollama_url,
                    model_name=sub_model,
                    temperature=ctx.temperature,
                    working_dir=ctx.working_dir,
                    project_root=ctx.project_root,
                    timeout=ctx.timeout,
                    extra=ctx.extra,
                )
                result = handler.handle(sub_ctx)
                results.append(result)
            else:
                results.append(self._no_handler_result(sub_intent))
        
        # 合并结果
        all_success = all(r.is_success() for r in results)
        outputs = []
        for i, r in enumerate(results):
            prefix = f"### 子任务 {i+1}: {intent.sub_intents[i].get_summary()}\n\n"
            outputs.append(prefix + str(r.output or r.error or "未执行"))
        
        combined_output = "\n\n---\n\n".join(outputs)
        
        return ActionResult(
            status=ActionResultStatus.SUCCESS if all_success else ActionResultStatus.PARTIAL,
            output=combined_output,
            output_type="text",
            steps=[{"name": "复合意图", "detail": f"执行 {len(results)} 个子任务", "duration": 0}],
            suggestions=["检查每个子任务的执行结果"],
        )
    
    # ── Evolution 联动 ──────────────────────────────────────────────────────

    def _report_to_evolution(self, intent: Intent, result: ActionResult, execution_time: float):
        """
        将执行结果反馈给 EvolutionEngine（闭环学习）

        静默失败，不影响主执行流程。
        """
        try:
            from client.src.business.evolution_engine.bridge import (
                EvolutionIntentBridge,
                ExecutionFeedback,
            )
            bridge = getattr(self, '_evolution_bridge', None)
            if bridge is None:
                # 延迟创建（第一次使用时）
                try:
                    from client.src.business.evolution_engine.bridge import create_bridge
                    from client.src.business.evolution_engine import create_evolution_engine
                    engine = create_evolution_engine(project_root=self._project_root or ".")
                    bridge = create_bridge(self._intent_engine, engine)
                    self._evolution_bridge = bridge
                except Exception:
                    logger.debug("EvolutionBridge 不可用，跳过反馈")
                    return

            feedback = ExecutionFeedback(
                intent_id=f"{intent.intent_type.value}_{intent.raw_input[:30]}",
                success=result.is_success(),
                duration_ms=execution_time * 1000,
                output=str(result.output)[:200] if result.output else "",
                errors=[result.error] if result.error else [],
                quality_score=1.0 if result.is_success() else 0.0,
            )
            bridge.report_execution_result(feedback)
            logger.debug("已向 EvolutionEngine 反馈执行结果")
        except Exception as e:
            logger.debug(f"Evolution 反馈跳过: {e}")

    # ── 无处理器回退 ────────────────────────────────────────────────────────

    def _no_handler_result(self, intent: Intent) -> ActionResult:
        """无匹配处理器时的回退结果"""
        # 根据意图类型给出有用建议
        suggestions = []
        
        if intent.intent_type == IntentType.UNKNOWN:
            suggestions = [
                "请更详细地描述您的需求",
                "例如：'帮我写一个 Python 函数' 或 '解释一下什么是异步编程'",
            ]
        else:
            suggestions = [
                f"意图类型 '{intent.intent_type.value}' 暂无内置处理器",
                "您可以通过 bridge.register_handler() 注册自定义处理器",
            ]
        
        return ActionResult(
            status=ActionResultStatus.NEED_CLARIFY,
            output=f"已识别意图: **{intent.intent_type.value}**\n\n"
                   f"动作: {intent.action or '未识别'}\n"
                   f"目标: {intent.target or '未识别'}\n"
                   f"技术栈: {', '.join(intent.tech_stack) or '未检测到'}\n"
                   f"置信度: {intent.confidence:.0%}",
            output_type="text",
            clarification_prompt=f"已理解您的意图是 {intent.intent_type.value}，但需要更多信息。",
            suggestions=suggestions,
        )
    
    # ── 便捷方法 ──────────────────────────────────────────────────────────
    
    def suggest_model(self, intent: Intent) -> str:
        """
        根据意图建议模型
        
        复用 IntentEngine.suggest_model() 的逻辑。
        """
        return self.intent_engine.suggest_model(intent)
    
    def explain(self, result: ActionResult) -> str:
        """
        生成执行结果的可读解释
        
        Args:
            result: 执行结果
            
        Returns:
            str: Markdown 格式的执行报告
        """
        lines = [
            "## 执行结果",
            "",
            f"| 属性 | 值 |",
            f"|------|-----|",
            f"| 状态 | {result.status.value} |",
            f"| 输出类型 | {result.output_type} |",
            f"| 执行时间 | {result.execution_time:.2f}s |",
            f"| 执行步骤 | {len(result.steps)} |",
        ]
        
        if result.error:
            lines.append(f"| 错误 | {result.error} |")
        
        if result.artifacts:
            lines.append(f"| 产出物 | {', '.join(result.artifacts)} |")
        
        if result.suggestions:
            lines.append("")
            lines.append("### 后续建议")
            for s in result.suggestions:
                lines.append(f"- {s}")
        
        return "\n".join(lines)


# ── 全局单例 ─────────────────────────────────────────────────────────────


_bridge_instance: Optional[IntentActionBridge] = None


def get_bridge() -> IntentActionBridge:
    """获取全局桥接器单例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = IntentActionBridge()
    return _bridge_instance
