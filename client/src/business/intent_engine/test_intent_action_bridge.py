# -*- coding: utf-8 -*-
"""
IntentActionBridge 桥接器测试
==============================

测试意图→执行的核心流程。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from client.src.business.intent_engine.intent_types import Intent, IntentType, IntentConstraint, IntentPriority
from client.src.business.intent_engine.intent_action_bridge import IntentActionBridge
from client.src.business.intent_engine.action_handlers.base import (
    BaseActionHandler, ActionContext, ActionResult, ActionResultStatus
)


# ── 测试用自定义 Handler ──────────────────────────────────────────────────


class EchoHandler(BaseActionHandler):
    """测试用回声处理器：原样返回用户输入"""
    
    @property
    def name(self) -> str:
        return "echo"
    
    @property
    def supported_intents(self) -> list:
        return [IntentType.UNKNOWN]
    
    @property
    def priority(self) -> int:
        return 1  # 最低优先级
    
    def handle(self, ctx: ActionContext) -> ActionResult:
        return self._make_result(
            output=f"[Echo] {ctx.intent.raw_input}",
            output_type="text",
        )


class FailingHandler(BaseActionHandler):
    """测试用失败处理器"""
    
    @property
    def name(self) -> str:
        return "always_fail"
    
    @property
    def supported_intents(self) -> list:
        return [IntentType.UNKNOWN]
    
    def handle(self, ctx: ActionContext) -> ActionResult:
        return self._make_error("模拟的执行错误")


# ── 测试用例 ────────────────────────────────────────────────────────────


def test_bridge_init():
    """1. 桥接器初始化"""
    bridge = IntentActionBridge(auto_register=False)
    assert len(bridge._all_handlers) == 0
    
    # 注册内置处理器
    bridge.register_handler(EchoHandler())
    assert len(bridge._all_handlers) == 1
    assert bridge.get_handler(IntentType.UNKNOWN) is not None
    print("  ✅ test_bridge_init")


def test_bridge_auto_register():
    """2. 自动注册内置处理器"""
    bridge = IntentActionBridge(auto_register=True)
    handlers = bridge.list_handlers()
    handler_names = {h["name"] for h in handlers}
    
    assert "code_generation" in handler_names
    assert "code_review" in handler_names
    assert "code_debug" in handler_names
    assert "knowledge_query" in handler_names
    assert "concept_explainer" in handler_names
    assert "file_operation" in handler_names
    assert len(handlers) >= 6
    print("  ✅ test_bridge_auto_register")


def test_bridge_handler_routing():
    """3. 意图路由到正确的处理器"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())
    
    # UNKNOWN 意图 → EchoHandler
    intent = Intent(raw_input="随便说点什么")
    intent.intent_type = IntentType.UNKNOWN
    
    result = bridge.execute(intent)
    assert result.is_success()
    assert "Echo" in str(result.output)
    print("  ✅ test_bridge_handler_routing")


def test_bridge_code_generation():
    """4. 代码生成意图路由"""
    bridge = IntentActionBridge(auto_register=True)
    
    intent = Intent(raw_input="帮我写一个快速排序")
    intent.intent_type = IntentType.CODE_GENERATION
    intent.action = "编写"
    intent.target = "快速排序"
    intent.tech_stack = ["python"]
    
    handler = bridge.get_handler(intent.intent_type)
    assert handler is not None
    assert handler.name == "code_generation"
    print("  ✅ test_bridge_code_generation")


def test_bridge_code_debug_priority():
    """5. Bug修复处理器优先级高于代码生成"""
    bridge = IntentActionBridge(auto_register=True)
    
    # CODE_MODIFICATION 同时被 code_generation 和 code_review 支持
    # 但 code_generation 优先级 (10) > code_review 优先级 (20)
    handler = bridge.get_handler(IntentType.CODE_GENERATION)
    assert handler is not None
    assert handler.name == "code_generation"
    
    # DEBUGGING → code_debug (优先级 5, 最高)
    handler = bridge.get_handler(IntentType.DEBUGGING)
    assert handler is not None
    assert handler.name == "code_debug"
    print("  ✅ test_bridge_code_debug_priority")


def test_bridge_unknown_intent():
    """6. 未知意图的处理"""
    bridge = IntentActionBridge(auto_register=False)
    # 不注册任何处理器
    
    intent = Intent(raw_input="帮我写代码")
    intent.intent_type = IntentType.UNKNOWN
    
    result = bridge.execute(intent)
    assert result.status == ActionResultStatus.NEED_CLARIFY
    assert len(result.suggestions) > 0
    print("  ✅ test_bridge_unknown_intent")


def test_bridge_no_handler_fallback():
    """7. 无匹配处理器时的优雅降级"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())  # 只注册 UNKNOWN
    
    # CODE_GENERATION 没有注册的处理器
    intent = Intent(raw_input="生成代码")
    intent.intent_type = IntentType.CODE_GENERATION
    
    result = bridge.execute(intent)
    assert result.status == ActionResultStatus.NEED_CLARIFY
    assert "code_generation" in result.output
    print("  ✅ test_bridge_no_handler_fallback")


def test_bridge_handler_override():
    """8. 处理器覆盖"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())
    
    # 用 FailingHandler 覆盖
    bridge.register_handler(FailingHandler(), override=True)
    
    intent = Intent(raw_input="test")
    intent.intent_type = IntentType.UNKNOWN
    
    result = bridge.execute(intent)
    assert result.is_failed()
    assert "模拟的执行错误" in result.error
    print("  ✅ test_bridge_handler_override")


def test_bridge_stats():
    """9. 执行统计"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())
    
    intent = Intent(raw_input="hello")
    intent.intent_type = IntentType.UNKNOWN
    
    bridge.execute(intent)
    bridge.execute(intent)
    
    stats = bridge.stats
    assert stats["total_executions"] == 2
    assert stats["success_count"] == 2
    assert stats["failed_count"] == 0
    print(f"  ✅ test_bridge_stats (执行2次, 统计: {stats})")


def test_bridge_context_building():
    """10. 执行上下文构建"""
    bridge = IntentActionBridge(
        ollama_url="http://custom:8080",
        model_name="my-model",
        working_dir="/tmp/test",
    )
    
    intent = Intent(raw_input="test")
    intent.intent_type = IntentType.UNKNOWN
    intent.tech_stack = ["python", "fastapi"]
    intent.constraints = [IntentConstraint(
        constraint_type="performance", name="响应时间", value="<100ms", required=True
    )]
    
    ctx = bridge._build_context(intent)
    assert ctx.ollama_url == "http://custom:8080"
    assert ctx.model_name == "my-model"
    assert ctx.working_dir == "/tmp/test"
    assert ctx.intent.tech_stack == ["python", "fastapi"]
    print("  ✅ test_bridge_context_building")


def test_bridge_unregistration():
    """11. 处理器注销"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())
    assert bridge.get_handler(IntentType.UNKNOWN) is not None
    
    bridge.unregister_handler("echo")
    assert bridge.get_handler(IntentType.UNKNOWN) is None
    print("  ✅ test_bridge_unregistration")


def test_bridge_list_handlers():
    """12. 列出所有处理器"""
    bridge = IntentActionBridge(auto_register=False)
    bridge.register_handler(EchoHandler())
    
    handlers = bridge.list_handlers()
    assert len(handlers) == 1
    assert handlers[0]["name"] == "echo"
    assert "unknown" in handlers[0]["supported_intents"]
    print("  ✅ test_bridge_list_handlers")


def test_bridge_explain():
    """13. 执行结果解释"""
    bridge = IntentActionBridge()
    
    result = ActionResult(
        status=ActionResultStatus.SUCCESS,
        output="生成的代码内容",
        output_type="code",
        execution_time=1.5,
        artifacts=["main.py"],
        suggestions=["运行测试"],
    )
    
    explanation = bridge.explain(result)
    assert "SUCCESS" in explanation
    assert "代码内容" in explanation
    assert "main.py" in explanation
    print("  ✅ test_bridge_explain")


# ── 运行 ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("IntentActionBridge 桥接器测试")
    print("=" * 60)
    
    test_bridge_init()
    test_bridge_auto_register()
    test_bridge_handler_routing()
    test_bridge_code_generation()
    test_bridge_code_debug_priority()
    test_bridge_unknown_intent()
    test_bridge_no_handler_fallback()
    test_bridge_handler_override()
    test_bridge_stats()
    test_bridge_context_building()
    test_bridge_unregistration()
    test_bridge_list_handlers()
    test_bridge_explain()
    
    print("\n" + "=" * 60)
    print("✅ 全部 13 项测试通过！")
    print("=" * 60)
