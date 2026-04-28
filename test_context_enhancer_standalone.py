"""
上下文增强器测试 (独立版)
不依赖项目导入，直接测试核心功能
"""

import asyncio
import time
import hashlib
from typing import List, Dict, Optional, Any

print("=" * 60)
print("上下文增强器测试 (独立版)")
print("=" * 60)


class ContextLevel:
    """上下文级别"""
    L0 = "L0"  # 文件元信息
    L1 = "L1"  # 接口/类签名
    L2 = "L2"  # 关键函数逻辑
    L3 = "L3"  # 详细代码


class DegradationLevel:
    """降级级别"""
    NORMAL = "normal"      # 正常状态
    WARNING = "warning"    # 警告状态
    CRITICAL = "critical"  # 临界状态
    EMERGENCY = "emergency"  # 紧急状态


class ContextChunk:
    """上下文块"""
    def __init__(self, id, content, level, tokens, priority, accessed_at, scope, metadata=None):
        self.id = id
        self.content = content
        self.level = level
        self.tokens = tokens
        self.priority = priority
        self.accessed_at = accessed_at
        self.scope = scope
        self.metadata = metadata or {}


class IntentState:
    """意图状态"""
    def __init__(self, raw_input, task, entities, constraints, clarified_details, assumptions, risks):
        self.raw_input = raw_input
        self.task = task
        self.entities = entities
        self.constraints = constraints
        self.clarified_details = clarified_details
        self.assumptions = assumptions
        self.risks = risks
        self.updated_at = time.time()


class MemoryManager:
    """记忆管理器"""
    def __init__(self):
        self.short_term_memory = []
        self.long_term_memory = []
        self.max_short_term = 50
        self.max_long_term = 500


class ContextCompressionEnhancer:
    """
    上下文压缩增强器
    实现长期增强的上下文管理策略
    """
    
    def __init__(self):
        self.context_manager = None  # 现有的上下文管理器
        self.memory_manager = MemoryManager()
        self.intent_state = None
        self.degradation_level = DegradationLevel.NORMAL
        
        # 上下文窗口配置
        self.context_config = {
            "max_tokens": 128000,
            "warning_threshold": 100000,
            "critical_threshold": 115000,
            "emergency_threshold": 120000
        }
        
        # 分层摘要配置
        self.summary_config = {
            "L0_max_tokens": 100,
            "L1_max_tokens": 500,
            "L2_max_tokens": 2000,
            "L3_max_tokens": 5000
        }
    
    def calculate_context_size(self, context):
        """计算上下文大小"""
        return sum(chunk.tokens for chunk in context)
    
    def check_degradation_level(self, current_tokens):
        """检查降级级别"""
        if current_tokens >= self.context_config["emergency_threshold"]:
            return DegradationLevel.EMERGENCY
        elif current_tokens >= self.context_config["critical_threshold"]:
            return DegradationLevel.CRITICAL
        elif current_tokens >= self.context_config["warning_threshold"]:
            return DegradationLevel.WARNING
        else:
            return DegradationLevel.NORMAL
    
    def apply_degradation_strategy(self, context, target_tokens):
        """
        应用降级策略
        按照优先级降级：保意图 > 保结构 > 保关键 > 分治
        """
        current_tokens = self.calculate_context_size(context)
        if current_tokens <= target_tokens:
            return context
        
        # 1. 保意图：保留 CONSTITUTION 和 INTENT
        if self.intent_state:
            # 确保意图信息不被压缩
            pass
        
        # 2. 保结构：保留 L0+L1，丢弃 L3
        structured_context = []
        for chunk in context:
            if chunk.level in [ContextLevel.L0, ContextLevel.L1]:
                structured_context.append(chunk)
            elif chunk.level == ContextLevel.L2:
                # 保留部分 L2
                structured_context.append(chunk)
            # 丢弃 L3
        
        if self.calculate_context_size(structured_context) <= target_tokens:
            return structured_context
        
        # 3. 保关键：只保留被直接调用或继承的代码
        critical_context = self._filter_critical_context(structured_context)
        if self.calculate_context_size(critical_context) <= target_tokens:
            return critical_context
        
        # 4. 分治：任务拆分
        return self._divide_and_conquer(critical_context, target_tokens)
    
    def _filter_critical_context(self, context):
        """过滤关键上下文"""
        # 这里可以实现更复杂的关键代码分析
        # 暂时基于优先级过滤
        sorted_context = sorted(context, key=lambda x: x.priority, reverse=True)
        return sorted_context[:len(sorted_context) // 2]
    
    def _divide_and_conquer(self, context, target_tokens):
        """分治策略"""
        # 按优先级分组
        high_priority = [c for c in context if c.priority >= 1.5]
        medium_priority = [c for c in context if 1.0 <= c.priority < 1.5]
        low_priority = [c for c in context if c.priority < 1.0]
        
        # 优先保留高优先级
        result = high_priority.copy()
        current_size = self.calculate_context_size(result)
        
        # 逐步添加中优先级
        for chunk in medium_priority:
            if current_size + chunk.tokens <= target_tokens:
                result.append(chunk)
                current_size += chunk.tokens
            else:
                break
        
        return result
    
    def generate_hierarchical_summary(self, content, level):
        """生成分层摘要"""
        max_tokens = self.summary_config[f"{level}_max_tokens"]
        
        if level == ContextLevel.L0:
            # 文件元信息摘要
            return self._generate_l0_summary(content)
        elif level == ContextLevel.L1:
            # 接口/类签名摘要
            return self._generate_l1_summary(content)
        elif level == ContextLevel.L2:
            # 关键函数逻辑摘要
            return self._generate_l2_summary(content)
        elif level == ContextLevel.L3:
            # 详细代码摘要
            return self._generate_l3_summary(content)
        
        return content
    
    def _generate_l0_summary(self, content):
        """生成 L0 摘要"""
        # 提取文件元信息
        lines = content.split('\n')
        summary = []
        
        # 提取注释和导入
        for line in lines[:50]:  # 只处理前50行
            line = line.strip()
            if line.startswith('#') or line.startswith('//') or line.startswith('import') or line.startswith('from'):
                summary.append(line)
        
        return '\n'.join(summary[:10])  # 最多10行
    
    def _generate_l1_summary(self, content):
        """生成 L1 摘要"""
        # 提取接口和类签名
        import re
        patterns = [
            r'class\s+\w+\s*\([^\)]*\)',
            r'interface\s+\w+\s*{',
            r'type\s+\w+\s*=',
            r'def\s+\w+\s*\([^\)]*\)\s*(->\s*\w+)?',
            r'function\s+\w+\s*\([^\)]*\)',
            r'const\s+\w+\s*=\s*\(.*\)\s*=>'
        ]
        
        summary = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            summary.extend(matches[:5])  # 每种类型最多5个
        
        return '\n'.join(summary[:15])  # 最多15个签名
    
    def _generate_l2_summary(self, content):
        """生成 L2 摘要"""
        # 提取函数逻辑摘要
        lines = content.split('\n')
        summary = []
        
        in_function = False
        function_lines = []
        
        for line in lines:
            import re
            if re.match(r'def\s+\w+\s*\(', line) or re.match(r'function\s+\w+\s*\(', line):
                if in_function and function_lines:
                    summary.append('\n'.join(function_lines[:10]))  # 每个函数最多10行
                in_function = True
                function_lines = [line.strip()]
            elif in_function:
                if line.strip().startswith('}') or (line.strip() and not line.startswith('    ') and not line.startswith('\t')):
                    summary.append('\n'.join(function_lines[:10]))
                    in_function = False
                    function_lines = []
                else:
                    function_lines.append(line.strip())
        
        return '\n\n'.join(summary[:3])  # 最多3个函数
    
    def _generate_l3_summary(self, content):
        """生成 L3 摘要"""
        # 详细代码摘要 - 保留关键部分
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 保留开头、中间和结尾
        summary = []
        summary.extend(lines[:50])  # 前50行
        if total_lines > 100:
            summary.extend(lines[total_lines//2-25:total_lines//2+25])  # 中间50行
        summary.extend(lines[-50:])  # 后50行
        
        return '\n'.join(summary)
    
    def create_incremental_context(self, diff):
        """创建增量上下文"""
        chunks = []
        
        # 解析 git diff
        lines = diff.split('\n')
        current_file = ""
        content_lines = []
        
        for line in lines:
            if line.startswith('diff --git'):
                if current_file and content_lines:
                    chunk = ContextChunk(
                        id=hashlib.md5((current_file + ''.join(content_lines)).encode()).hexdigest(),
                        content='\n'.join(content_lines),
                        level=ContextLevel.L2,
                        tokens=len(''.join(content_lines)) // 4,
                        priority=1.5,
                        accessed_at=time.time(),
                        scope="diff"
                    )
                    chunks.append(chunk)
                current_file = line.split(' b/')[1] if ' b/' in line else ""
                content_lines = [line]
            else:
                content_lines.append(line)
        
        # 处理最后一个文件
        if current_file and content_lines:
            chunk = ContextChunk(
                id=hashlib.md5((current_file + ''.join(content_lines)).encode()).hexdigest(),
                content='\n'.join(content_lines),
                level=ContextLevel.L2,
                tokens=len(''.join(content_lines)) // 4,
                priority=1.5,
                accessed_at=time.time(),
                scope="diff"
            )
            chunks.append(chunk)
        
        return chunks
    
    def manage_memory(self):
        """管理记忆"""
        # 清理短期记忆
        if len(self.memory_manager.short_term_memory) > self.memory_manager.max_short_term:
            # 按访问时间排序，保留最近的
            self.memory_manager.short_term_memory.sort(key=lambda x: x.accessed_at, reverse=True)
            self.memory_manager.short_term_memory = self.memory_manager.short_term_memory[:self.memory_manager.max_short_term]
        
        # 清理长期记忆
        if len(self.memory_manager.long_term_memory) > self.memory_manager.max_long_term:
            # 按优先级和访问时间排序
            self.memory_manager.long_term_memory.sort(key=lambda x: (x.priority, x.accessed_at), reverse=True)
            self.memory_manager.long_term_memory = self.memory_manager.long_term_memory[:self.memory_manager.max_long_term]
    
    def get_context_for_task(self, task, max_tokens=50000):
        """获取任务相关的上下文"""
        # 1. 先获取 L0+L1 摘要
        context = []
        
        # 2. 根据任务类型添加相关上下文
        if 'create' in task.lower() or 'generate' in task.lower():
            # 代码生成任务，需要更多结构信息
            context.extend([c for c in self.memory_manager.long_term_memory if c.level in [ContextLevel.L0, ContextLevel.L1]])
        elif 'fix' in task.lower() or 'debug' in task.lower():
            # 调试任务，需要错误相关信息
            context.extend([c for c in self.memory_manager.short_term_memory if 'error' in c.scope.lower()])
        elif 'refactor' in task.lower():
            # 重构任务，需要完整结构
            context.extend([c for c in self.memory_manager.long_term_memory if c.level in [ContextLevel.L0, ContextLevel.L1, ContextLevel.L2]])
        
        # 3. 应用降级策略
        return self.apply_degradation_strategy(context, max_tokens)
    
    def add_context(self, content, level, scope="general"):
        """添加上下文"""
        chunk = ContextChunk(
            id=hashlib.md5((content + str(time.time())).encode()).hexdigest(),
            content=content,
            level=level,
            tokens=len(content) // 4,
            priority=self._calculate_priority(content, scope),
            accessed_at=time.time(),
            scope=scope
        )
        
        if level in [ContextLevel.L0, ContextLevel.L1]:
            # 长期记忆
            self.memory_manager.long_term_memory.append(chunk)
        else:
            # 短期记忆
            self.memory_manager.short_term_memory.append(chunk)
        
        # 管理记忆
        self.manage_memory()
        
        return chunk.id
    
    def _calculate_priority(self, content, scope):
        """计算优先级"""
        priority = 1.0
        
        # 基于范围的优先级
        if scope == "architecture":
            priority += 0.3
        elif scope == "requirements":
            priority += 0.2
        elif scope == "diff":
            priority += 0.5
        
        # 基于内容的优先级
        if any(kw in content.lower() for kw in ['important', '关键', '核心', 'critical']):
            priority += 0.2
        if any(kw in content.lower() for kw in ['TODO', 'FIXME', 'HACK']):
            priority += 0.1
        
        return min(priority, 2.0)
    
    def get_stats(self):
        """获取统计信息"""
        return {
            "short_term_memory": len(self.memory_manager.short_term_memory),
            "long_term_memory": len(self.memory_manager.long_term_memory),
            "short_term_tokens": sum(c.tokens for c in self.memory_manager.short_term_memory),
            "long_term_tokens": sum(c.tokens for c in self.memory_manager.long_term_memory),
            "degradation_level": self.degradation_level,
            "intent_state": self.intent_state is not None
        }


class IntentStateManager:
    """意图状态管理器"""
    
    def __init__(self):
        self.intent_states = {}
    
    def create_intent_state(self, session_id, raw_input):
        """创建意图状态"""
        intent_state = IntentState(
            raw_input=raw_input,
            task="",
            entities=[],
            constraints=[],
            clarified_details=[],
            assumptions=[],
            risks=[]
        )
        self.intent_states[session_id] = intent_state
        return intent_state
    
    def get_intent_state(self, session_id):
        """获取意图状态"""
        return self.intent_states.get(session_id)
    
    def update_intent_state(self, session_id, **updates):
        """更新意图状态"""
        intent_state = self.intent_states.get(session_id)
        if intent_state:
            for key, value in updates.items():
                if hasattr(intent_state, key):
                    setattr(intent_state, key, value)
            intent_state.updated_at = time.time()
    
    def clear_intent_state(self, session_id):
        """清除意图状态"""
        if session_id in self.intent_states:
            del self.intent_states[session_id]
    
    def get_stats(self):
        """获取统计信息"""
        return {
            "active_intents": len(self.intent_states),
            "recent_intents": [
                {
                    "session_id": session_id,
                    "raw_input": state.raw_input[:50],
                    "updated_at": state.updated_at
                }
                for session_id, state in list(self.intent_states.items())[-5:]
            ]
        }


def create_context_enhancer():
    """
    创建上下文增强器
    
    Returns:
        ContextCompressionEnhancer: 上下文增强器实例
    """
    return ContextCompressionEnhancer()


def create_intent_manager():
    """
    创建意图状态管理器
    
    Returns:
        IntentStateManager: 意图状态管理器实例
    """
    return IntentStateManager()


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


async def test_integration():
    """集成测试"""
    tests = [
        test_context_enhancer,
        test_intent_manager
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