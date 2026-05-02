"""
AI流水线测试脚本 - 验证所有模块功能
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from livingtree.core.ai_pipeline import (
    get_ai_workflow_engine,
    get_task_decomposition_engine,
    get_code_generation_unit,
    get_auto_test_system,
    get_smart_fix_engine,
    get_quality_gates,
    get_knowledge_management,
    get_context_manager,
    get_pipeline_panel,
    get_integration_orchestrator,
    get_conversation_orchestrator,
    get_progressive_thinking_engine,
    AutomationMode
)


async def test_all_modules():
    """测试所有模块"""
    print("🚀 开始测试AI流水线系统...")
    
    tests = [
        ("任务分解引擎", test_task_decomposition),
        ("代码生成单元", test_code_generation),
        ("自动测试系统", test_auto_test),
        ("智能修复引擎", test_smart_fix),
        ("质量门禁系统", test_quality_gates),
        ("知识管理", test_knowledge_management),
        ("上下文管理器", test_context_manager),
        ("流水线面板", test_pipeline_panel),
        ("对话编排器", test_conversation_orchestrator),
        ("渐进式思考引擎", test_progressive_thinking),
        ("集成编排器", test_integration_orchestrator)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n📋 测试 {name}...")
        try:
            await test_func()
            print(f"✅ {name} 测试通过")
            passed += 1
        except Exception as e:
            print(f"❌ {name} 测试失败: {e}")
            failed += 1
    
    print(f"\n📊 测试结果: {passed} 通过, {failed} 失败")
    
    return passed == len(tests)


async def test_task_decomposition():
    """测试任务分解引擎"""
    engine = get_task_decomposition_engine()
    
    requirement = "开发用户登录功能，支持用户名密码登录和第三方OAuth登录"
    result = await engine.decompose(requirement)
    
    assert result.epic is not None
    assert len(result.epic.user_stories) > 0
    assert result.execution_plan is not None
    
    print(f"  - 生成了 {len(result.epic.user_stories)} 个User Story")
    print(f"  - 预估时间: {result.epic.total_estimated_hours} 小时")


async def test_code_generation():
    """测试代码生成单元"""
    code_gen = get_code_generation_unit()
    
    requirement = "创建一个用户认证服务，支持JWT令牌生成和验证"
    result = await code_gen.generate_code(requirement)
    
    assert result.files is not None
    assert len(result.files) > 0
    assert result.status == "success"
    
    print(f"  - 生成了 {len(result.files)} 个文件")
    print(f"  - 质量评分: {result.quality_score}")


async def test_auto_test():
    """测试自动测试系统"""
    test_system = get_auto_test_system()
    
    code = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
    
    tests = await test_system.generate_unit_tests(code, "math_utils.py")
    
    assert len(tests) > 0
    print(f"  - 生成了 {len(tests)} 个测试用例")
    
    results = await test_system.run_tests(tests)
    print(f"  - 执行了 {len(results)} 个测试")


async def test_smart_fix():
    """测试智能修复引擎"""
    fix_engine = get_smart_fix_engine()
    
    test_result = {
        "test_id": "TEST-001",
        "error_message": "AssertionError: 预期值为5，实际值为3",
        "stack_trace": "File 'test.py', line 10, in test_add\n    assert add(2, 2) == 5"
    }
    
    issue = await fix_engine.analyze_failure(test_result)
    
    assert issue is not None
    assert issue.priority is not None
    
    fix = await fix_engine.generate_fix(issue, "def add(a, b): return a + b")
    assert fix is not None
    
    print(f"  - 分析出问题: {issue.title}")
    print(f"  - 生成修复方案: {fix.description}")


async def test_quality_gates():
    """测试质量门禁系统"""
    quality_gates = get_quality_gates()
    
    project_info = {
        "project_name": "Test Project",
        "branch": "main",
        "commit_hash": "abc123"
    }
    
    report = await quality_gates.run_all_gates(project_info)
    
    assert report is not None
    assert report.overall_status is not None
    
    print(f"  - 质量门禁状态: {report.overall_status.value}")
    print(f"  - 执行了 {len(report.gates)} 个门禁检查")


async def test_knowledge_management():
    """测试知识管理"""
    knowledge = get_knowledge_management()
    
    # 测试架构决策记录
    decision = await knowledge.generate_decision(
        "选择数据库类型",
        ["MySQL", "PostgreSQL", "SQLite"]
    )
    
    assert decision is not None
    print(f"  - 创建架构决策: {decision.title}")
    
    # 测试故障分析
    bug = await knowledge.analyze_bug("NullPointerException at UserService.login()")
    assert bug is not None
    print(f"  - 分析故障: {bug.title}")
    
    stats = knowledge.get_knowledge_stats()
    print(f"  - 知识库统计: {stats}")


async def test_context_manager():
    """测试上下文管理器"""
    context_manager = get_context_manager()
    
    # 创建任务上下文
    task_id = context_manager.create_task_context(
        workflow_id="test_workflow",
        variables={"requirement": "test requirement"}
    )
    
    assert task_id is not None
    
    # 更新上下文
    context_manager.update_task_context(task_id, {"status": "running"})
    
    # 获取上下文
    context = context_manager.get_task_context(task_id)
    assert context is not None
    assert context.variables.get("status") == "running"
    
    print(f"  - 创建任务上下文: {task_id}")
    
    stats = context_manager.get_context_stats()
    print(f"  - 上下文统计: {stats}")


async def test_pipeline_panel():
    """测试流水线面板"""
    panel = get_pipeline_panel()
    
    pipeline_id = panel.create_pipeline(
        workflow_id="test_workflow",
        name="测试流水线"
    )
    
    assert pipeline_id is not None
    
    # 更新任务状态
    panel.update_task_status(pipeline_id, "task_1", "in_progress", 50)
    
    status = panel.get_pipeline_status(pipeline_id)
    assert status is not None
    
    print(f"  - 创建流水线: {pipeline_id}")
    print(f"  - 流水线状态: {status.get('status')}")


async def test_conversation_orchestrator():
    """测试对话编排器"""
    orchestrator = get_conversation_orchestrator()
    
    conversation_id = orchestrator.start_conversation("test_user")
    assert conversation_id is not None
    print(f"  - 创建对话: {conversation_id}")
    
    # 发送初始需求
    result = await orchestrator.process_user_input(conversation_id, "开发一个用户管理系统")
    assert result is not None
    assert "response" in result
    print(f"  - 助手响应: {result['response'][:50]}...")
    
    # 获取状态
    state = orchestrator.get_conversation_state(conversation_id)
    assert state is not None
    print(f"  - 对话状态: {state.value}")
    
    # 获取上下文
    context = orchestrator.get_conversation_context(conversation_id)
    assert context is not None
    print(f"  - 功能需求数量: {len(context.functional)}")


async def test_progressive_thinking():
    """测试渐进式思考引擎"""
    engine = get_progressive_thinking_engine()
    
    problem = "如何设计一个高可用的微服务架构？"
    trace = await engine.think(problem)
    
    assert trace is not None
    assert trace.id is not None
    assert len(trace.thoughts) > 0
    print(f"  - 思考步骤: {len(trace.thoughts)}")
    print(f"  - 置信度: {trace.confidence.value}")
    
    # 格式化输出
    formatted = engine.format_trace(trace)
    assert formatted is not None
    print(f"  - 最终答案: {trace.final_answer[:50]}..." if trace.final_answer else "  - 无最终答案")


async def test_integration_orchestrator():
    """测试集成编排器"""
    orchestrator = get_integration_orchestrator()
    
    requirement = "开发一个简单的待办事项管理系统，支持添加、删除、标记完成功能"
    
    run_id = await orchestrator.start_pipeline(
        requirement,
        automation_mode=AutomationMode.FULL_AUTO
    )
    
    assert run_id is not None
    
    # 测试需求澄清功能
    clarify_result = await orchestrator.clarify_requirement(run_id, "这是一个内部工具，用户量约100人")
    assert clarify_result is not None
    assert "response" in clarify_result
    print(f"  - 需求澄清响应: {clarify_result['response'][:50]}...")
    
    # 测试渐进式思考功能
    thinking_result = await orchestrator.think_progressive("如何优化待办事项系统的性能？")
    assert thinking_result is not None
    assert "thoughts" in thinking_result
    print(f"  - 思考步骤数: {len(thinking_result['thoughts'])}")
    
    # 等待流水线完成
    for _ in range(10):
        status = await orchestrator.get_pipeline_status(run_id)
        print(f"  - 流水线状态: {status.get('status')}")
        
        if status.get('status') in ['completed', 'failed']:
            break
        
        await asyncio.sleep(0.5)
    
    stats = orchestrator.get_orchestrator_stats()
    print(f"  - 编排器统计: {stats}")


if __name__ == "__main__":
    success = asyncio.run(test_all_modules())
    sys.exit(0 if success else 1)