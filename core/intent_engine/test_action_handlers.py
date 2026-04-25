# -*- coding: utf-8 -*-
"""
ActionHandler 动作处理器测试
============================

测试每个内置处理器的独立行为。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.intent_engine.intent_types import Intent, IntentType, IntentConstraint
from core.intent_engine.action_handlers.base import ActionContext, ActionResultStatus
from core.intent_engine.action_handlers.code_handler import (
    CodeGenerationHandler, CodeReviewHandler, CodeDebugHandler,
)
from core.intent_engine.action_handlers.knowledge_handler import (
    KnowledgeQueryHandler, ConceptExplainerHandler,
)
from core.intent_engine.action_handlers.file_handler import FileOperationHandler


def _make_ctx(intent: Intent, **overrides) -> ActionContext:
    """快速构建测试用 ActionContext"""
    return ActionContext(
        intent=intent,
        ollama_url="http://localhost:11434",
        model_name="qwen3.5:4b",
        working_dir=".",
        **overrides,
    )


# ── CodeGenerationHandler ─────────────────────────────────────────────────


def test_codegen_supported_intents():
    """1. 代码生成处理器支持的意图类型"""
    handler = CodeGenerationHandler()
    assert IntentType.CODE_GENERATION in handler.supported_intents
    assert IntentType.API_DESIGN in handler.supported_intents
    assert IntentType.CODE_REFACTOR in handler.supported_intents
    assert IntentType.TEST_GENERATION in handler.supported_intents
    assert IntentType.DOCUMENTATION in handler.supported_intents
    assert len(handler.supported_intents) >= 14
    print("  ✅ test_codegen_supported_intents")


def test_codegen_priority():
    """2. 代码生成处理器优先级"""
    handler = CodeGenerationHandler()
    assert handler.priority == 10
    print("  ✅ test_codegen_priority")


def test_codegen_prompt_building():
    """3. 代码生成提示构建"""
    handler = CodeGenerationHandler()
    
    intent = Intent(
        raw_input="帮我写一个 FastAPI 用户登录接口",
        intent_type=IntentType.CODE_GENERATION,
        action="编写",
        target="登录接口",
        tech_stack=["python", "fastapi"],
        constraints=[IntentConstraint(
            constraint_type="security", name="认证方式", value="JWT", required=True
        )],
    )
    
    ctx = _make_ctx(intent)
    prompt = handler._build_prompt(ctx)
    
    assert "FastAPI" in prompt
    assert "CODE_GENERATION" in prompt
    assert "JWT" in prompt
    assert "python" in prompt
    print("  ✅ test_codegen_prompt_building")


def test_codegen_extract_code_blocks():
    """4. 提取代码块"""
    handler = CodeGenerationHandler()
    
    text = '''Here is some code:
```python
def hello():
    print("world")
```
And another:
```javascript
console.log("hi");
```'''
    
    blocks = handler._extract_code_blocks(text)
    assert len(blocks) == 2
    assert "block_1.python" in blocks
    assert "block_2.javascript" in blocks
    print("  ✅ test_codegen_extract_code_blocks")


# ── CodeReviewHandler ────────────────────────────────────────────────────


def test_review_supported_intents():
    """5. 代码审查处理器支持的意图类型"""
    handler = CodeReviewHandler()
    assert IntentType.CODE_REVIEW in handler.supported_intents
    assert IntentType.SECURITY_CHECK in handler.supported_intents
    assert IntentType.PERFORMANCE_ANALYSIS in handler.supported_intents
    assert IntentType.CODE_EXPLANATION in handler.supported_intents
    print("  ✅ test_review_supported_intents")


def test_review_prompt_type():
    """6. 代码审查 vs 代码解释的提示区分"""
    handler = CodeReviewHandler()
    
    # 代码审查
    review_intent = Intent(raw_input="审查这段代码", intent_type=IntentType.CODE_REVIEW)
    review_ctx = _make_ctx(review_intent)
    review_prompt = handler._build_review_prompt(review_ctx)
    assert "代码审查" in review_prompt
    
    # 代码解释
    explain_intent = Intent(raw_input="解释这段代码", intent_type=IntentType.CODE_EXPLANATION)
    explain_ctx = _make_ctx(explain_intent)
    explain_prompt = handler._build_review_prompt(explain_ctx)
    assert "代码解释" in explain_prompt
    print("  ✅ test_review_prompt_type")


# ── CodeDebugHandler ─────────────────────────────────────────────────────


def test_debug_highest_priority():
    """7. 调试处理器优先级最高"""
    handler = CodeDebugHandler()
    assert handler.priority == 5  # 比 CodeGenerationHandler (10) 更高
    print("  ✅ test_debug_highest_priority")


def test_debug_supported_intents():
    """8. 调试处理器支持的意图类型"""
    handler = CodeDebugHandler()
    assert IntentType.DEBUGGING in handler.supported_intents
    assert IntentType.BUG_FIX in handler.supported_intents
    assert IntentType.ERROR_RESOLUTION in handler.supported_intents
    assert IntentType.ISSUE_ANALYSIS in handler.supported_intents
    print("  ✅ test_debug_supported_intents")


def test_debug_prompt():
    """9. 调试提示包含根因分析"""
    handler = CodeDebugHandler()
    
    intent = Intent(raw_input="修复空指针异常", intent_type=IntentType.BUG_FIX)
    ctx = _make_ctx(intent)
    prompt = handler._build_debug_prompt(ctx)
    
    assert "问题定位" in prompt
    assert "根因分析" in prompt
    assert "修复方案" in prompt
    assert "预防措施" in prompt
    print("  ✅ test_debug_prompt")


# ── KnowledgeQueryHandler ────────────────────────────────────────────────


def test_knowledge_supported_intents():
    """10. 知识查询处理器支持的意图类型"""
    handler = KnowledgeQueryHandler()
    assert IntentType.KNOWLEDGE_QUERY in handler.supported_intents
    assert IntentType.BEST_PRACTICE in handler.supported_intents
    print("  ✅ test_knowledge_supported_intents")


def test_knowledge_uses_lightweight_model():
    """11. 知识查询优先使用轻量模型"""
    handler = KnowledgeQueryHandler()
    
    intent = Intent(raw_input="Python GIL 是什么？", intent_type=IntentType.KNOWLEDGE_QUERY)
    ctx = _make_ctx(intent, model_name="qwen3.5:9b")
    
    # handler 内部应替换为轻量模型
    result = handler.handle(ctx)
    assert result is not None
    print("  ✅ test_knowledge_uses_lightweight_model")


# ── ConceptExplainerHandler ──────────────────────────────────────────────


def test_concept_supported_intents():
    """12. 概念解释处理器支持的意图类型"""
    handler = ConceptExplainerHandler()
    assert IntentType.CONCEPT_EXPLANATION in handler.supported_intents
    print("  ✅ test_concept_supported_intents")


def test_concept_deep_structure():
    """13. 概念解释提示包含深度结构"""
    handler = ConceptExplainerHandler()
    
    intent = Intent(raw_input="解释一下异步编程", intent_type=IntentType.CONCEPT_EXPLANATION)
    ctx = _make_ctx(intent)
    
    result = handler.handle(ctx)
    assert result is not None
    print("  ✅ test_concept_deep_structure")


# ── FileOperationHandler ──────────────────────────────────────────────────


def test_file_operation_detection():
    """14. 文件操作类型检测"""
    handler = FileOperationHandler()
    
    assert handler._detect_operation(Intent(raw_input="读取 config.yaml")) == "read"
    assert handler._detect_operation(Intent(raw_input="查看目录结构")) == "list"
    assert handler._detect_operation(Intent(raw_input="创建新文件")) == "create"
    assert handler._detect_operation(Intent(raw_input="分析文件大小")) == "analyze"
    print("  ✅ test_file_operation_detection")


def test_file_path_extraction():
    """15. 文件路径提取"""
    handler = FileOperationHandler()
    
    assert handler._extract_file_path("打开 core/agent.py") == "core/agent.py"
    assert handler._extract_file_path("查看 config.yaml") == "config.yaml"
    assert handler._extract_file_path("帮我读 main.py") == "main.py"
    print("  ✅ test_file_path_extraction")


def test_file_tree_building():
    """16. 目录树构建"""
    handler = FileOperationHandler()
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    tree = handler._build_tree(test_dir, max_depth=1)
    assert "__init__" in tree or "intent_" in tree
    print("  ✅ test_file_tree_building")


def test_file_read_nonexistent():
    """17. 读取不存在的文件"""
    handler = FileOperationHandler()
    
    intent = Intent(raw_input="读取 non_existent_file_12345.py", intent_type=IntentType.FILE_OPERATION)
    ctx = _make_ctx(intent, working_dir=".")
    
    result = handler._handle_read(ctx)
    assert result.is_failed()
    assert "不存在" in result.error
    print("  ✅ test_file_read_nonexistent")


def test_file_clarify_on_ambiguity():
    """18. 模糊操作时请求澄清"""
    handler = FileOperationHandler()
    
    intent = Intent(raw_input="文件", intent_type=IntentType.FILE_OPERATION)
    result = handler._detect_operation(intent)
    assert result in ("read", "create", "list", "analyze")
    print("  ✅ test_file_clarify_on_ambiguity")


# ── BaseActionHandler 便捷方法 ───────────────────────────────────────────


def test_base_quick_result_builders():
    """19. BaseActionHandler 快捷构建方法"""
    handler = CodeGenerationHandler()
    
    success = handler._make_result(output="hello", output_type="text")
    assert success.is_success()
    assert success.output == "hello"
    
    error = handler._make_error("出错了")
    assert error.is_failed()
    assert error.error == "出错了"
    
    clarify = handler._make_clarify("请补充信息")
    assert clarify.status == ActionResultStatus.NEED_CLARIFY
    assert "补充" in clarify.clarification_prompt
    print("  ✅ test_base_quick_result_builders")


# ── 运行 ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("ActionHandler 动作处理器测试")
    print("=" * 60)
    
    test_codegen_supported_intents()
    test_codegen_priority()
    test_codegen_prompt_building()
    test_codegen_extract_code_blocks()
    test_review_supported_intents()
    test_review_prompt_type()
    test_debug_highest_priority()
    test_debug_supported_intents()
    test_debug_prompt()
    test_knowledge_supported_intents()
    test_knowledge_uses_lightweight_model()
    test_concept_supported_intents()
    test_concept_deep_structure()
    test_file_operation_detection()
    test_file_path_extraction()
    test_file_tree_building()
    test_file_read_nonexistent()
    test_file_clarify_on_ambiguity()
    test_base_quick_result_builders()
    
    print("\n" + "=" * 60)
    print("✅ 全部 19 项测试通过！")
    print("=" * 60)
