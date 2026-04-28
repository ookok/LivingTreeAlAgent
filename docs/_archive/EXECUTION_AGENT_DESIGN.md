# Execution Agent - 工具执行集成

## 概述

将 LivingTreeAI 已有的 `core/ai_script_generator/script_sandbox.py` 能力整合到 Evolution Engine 框架中，提供统一的代码执行接口。

## 架构

```
EvolutionExecutor
    └── ExecutionAgent
            ├── SandboxExecutor (script_sandbox)
            │       ├── ResourceMonitor
            │       ├── RestrictedBuiltins
            │       └── DangerPatternDetector
            │
            └── ScriptSandbox
                    ├── 实例池
                    ├── 热重载
                    └── 执行历史
```

## 执行级别

| 级别 | 文件读取 | 文件写入 | 网络访问 | 内存限制 | 时间限制 |
|------|---------|---------|---------|---------|---------|
| SANDBOX | ✓ | ✗ | ✗ | 512MB | 30s |
| RESTRICTED | ✓ | ✓ | ✗ | 1024MB | 60s |
| FULL | ✓ | ✓ | ✓ | 2048MB | 120s |

## 核心组件

### ExecutionAgent

```python
from core.evolution_engine.execution_agent import create_execution_agent

# 创建执行代理
agent = create_execution_agent('sandbox')

# 执行代码
report = agent.execute_code("""
result = 2 ** 10
print(f"2^10 = {result}")
""")

print(f"Success: {report.success}")
print(f"Output: {report.output}")
```

### 快捷函数

```python
from core.evolution_engine.execution_agent import quick_execute

result = quick_execute("""
data = [1, 2, 3, 4, 5]
print(f"Sum: {sum(data)}")
""")

print(result['success'], result['output'])
```

## 功能特性

### 1. 安全隔离

- AST 语法检查
- 危险模式检测 (eval/exec/os.system/subprocess)
- 受限内置函数
- 资源限制 (CPU/内存/时间)

### 2. 执行上下文

```python
report = agent.execute_code(code, context={'radius': 5})
# 代码中可使用 radius 变量
```

### 3. 危险模式警告

```python
report = agent.execute_code("""
import os
os.system("rm -rf /")
""")

print(report.warnings)
# ['os.system() 可能执行危险命令']
```

### 4. 执行钩子

```python
def pre_hook(task):
    print(f"执行前: {task.task_id}")

def post_hook(task, report):
    print(f"执行后: {report.success}")

agent.add_pre_hook(pre_hook)
agent.add_post_hook(post_hook)
```

## 测试结果

```
[Test 1] 简单计算
[PASS] Success: True
  Output: 2^10 = 1024

[Test 2] 带上下文执行
[PASS] Success: True
  Output: 半径 5 的圆面积: 78.50

[Test 3] 危险代码检测
  Success: False (正确阻止)

[Test 4] 快速执行
[PASS] Success: True
  Output: Sum: 15, Avg: 3.0

[Test 5] 语法错误检测
  Success: False (正确捕获)
```

## 文件清单

| 文件 | 功能 |
|------|------|
| `core/evolution_engine/execution_agent.py` | 执行代理主模块 |
| `core/ai_script_generator/script_sandbox.py` | 底层沙箱实现 |
| `test_execution_standalone_v2.py` | 独立测试 |
| `docs/EXECUTION_AGENT_DESIGN.md` | 本文档 |

## 集成计划

### Phase 1: 基础集成 ✅

- [x] ExecutionAgent 实现
- [x] 三个执行级别
- [x] 危险代码检测
- [x] 资源监控

### Phase 2: Evolution 集成 (待做)

- [ ] EvolutionExecutor 调用 ExecutionAgent
- [ ] 提案验证使用执行能力
- [ ] 自动化测试验证

### Phase 3: 高级特性 (规划中)

- [ ] 异步执行
- [ ] 执行缓存
- [ ] 增量执行
