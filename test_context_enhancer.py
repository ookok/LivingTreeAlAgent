"""
上下文增强器测试
验证长期增强的上下文压缩策略
"""

import asyncio
import time
from client.src.business.context_enhancer import create_context_enhancer, create_intent_manager, ContextLevel, DegradationLevel
from client.src.business.smart_ide_enhanced import create_smart_ide_system

print("=" * 60)
print("上下文增强器测试")
print("=" * 60)


async def test_context_enhancer():
    """测试上下文增强器"""
    print("=== 测试上下文增强器 ===")
    
    enhancer = create_context_enhancer()
    
    # 测试添加上下文
    test_code = """
class User:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
    
    def get_full_name(self) -> str:
        return self.name
    
    def update_name(self, new_name: str) -> None:
        self.name = new_name
"""
    
    chunk_id = enhancer.add_context(test_code, ContextLevel.L3, "code")
    print(f"添加上下文成功，chunk_id: {chunk_id}")
    
    # 测试分层摘要
    l0_summary = enhancer.generate_hierarchical_summary(test_code, ContextLevel.L0)
    print(f"L0 摘要: {l0_summary[:100]}...")
    
    l1_summary = enhancer.generate_hierarchical_summary(test_code, ContextLevel.L1)
    print(f"L1 摘要: {l1_summary[:100]}...")
    
    l2_summary = enhancer.generate_hierarchical_summary(test_code, ContextLevel.L2)
    print(f"L2 摘要: {l2_summary[:100]}...")
    
    # 测试增量上下文
    git_diff = """
diff --git a/src/User.ts b/src/User.ts
-    id: string;
+    id: number;
"""
    incremental_context = enhancer.create_incremental_context(git_diff)
    print(f"创建增量上下文，块数: {len(incremental_context)}")
    
    # 测试记忆管理
    enhancer.manage_memory()
    stats = enhancer.get_stats()
    print(f"记忆管理后统计: {stats}")
    
    # 测试降级策略
    large_context = [
        enhancer.add_context("""import React from 'react';
import { useState, useEffect } from 'react';

const Component = () => {
    const [state, setState] = useState(0);
    
    useEffect(() => {
        console.log('Component mounted');
    }, []);
    
    return (
        <div>
            <h1>Hello World</h1>
            <p>State: {state}</p>
            <button onClick={() => setState(state + 1)}>Increment</button>
        </div>
    );
};

export default Component;""", ContextLevel.L3, "code") for _ in range(10)
    ]
    
    # 测试获取任务相关上下文
    task_context = enhancer.get_context_for_task("create React component", max_tokens=10000)
    print(f"任务相关上下文块数: {len(task_context)}")
    
    return True


async def test_intent_manager():
    """测试意图管理器"""
    print("\n=== 测试意图管理器 ===")
    
    intent_manager = create_intent_manager()
    
    # 创建意图状态
    session_id = "test_session"
    intent_state = intent_manager.create_intent_state(session_id, "创建一个React组件")
    print(f"创建意图状态成功，raw_input: {intent_state.raw_input}")
    
    # 更新意图状态
    intent_manager.update_intent_state(
        session_id,
        task="CREATE_COMPONENT",
        entities=[{"type": "FILE", "value": "Component.tsx"}],
        constraints=["使用TypeScript", "遵循React最佳实践"]
    )
    
    # 获取意图状态
    updated_state = intent_manager.get_intent_state(session_id)
    print(f"更新后意图状态: task={updated_state.task}, entities={updated_state.entities}")
    
    # 获取统计信息
    stats = intent_manager.get_stats()
    print(f"意图管理器统计: {stats}")
    
    return True


async def test_smart_ide_enhanced():
    """测试增强的智能IDE系统"""
    print("\n=== 测试增强的智能IDE系统 ===")
    
    ide_system = create_smart_ide_system()
    
    # 测试系统状态
    status = ide_system.get_system_status()
    print(f"系统状态: {list(status.keys())}")
    print(f"上下文状态: {status.get('context', {})}")
    print(f"意图状态: {status.get('intent', {})}")
    
    # 测试自然语言处理
    result = await ide_system.process_natural_language(
        "创建一个Python函数，计算斐波那契数列",
        {"language": "python"},
        "test_session"
    )
    print(f"自然语言处理结果: {'成功' if result['success'] else '失败'}")
    if result['success']:
        print(f"生成结果数量: {len(result['results'])}")
        print(f"上下文统计: {result.get('context_stats', {})}")
    
    # 测试代码补全
    code = "def hello():\n    print('Hello '); return"
    completions = await ide_system.get_code_completion(code, len(code), "python")
    print(f"代码补全建议数量: {len(completions)}")
    
    # 测试错误诊断
    error_message = "NameError: name 'x' is not defined"
    diagnosis = await ide_system.diagnose_error(error_message, "print(x)", "python")
    print(f"错误诊断结果数量: {len(diagnosis)}")
    
    # 再次检查系统状态
    status = ide_system.get_system_status()
    print(f"最终上下文状态: {status.get('context', {})}")
    
    return True


async def test_integration():
    """集成测试"""
    tests = [
        test_context_enhancer,
        test_intent_manager,
        test_smart_ide_enhanced
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！上下文增强器集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())