# Optimal Config Design Document

## 概述

**Priority 3: 极简设计理念** - 基于 nanochat "计算最优配置" 理念的 LivingTreeAI 简化配置系统。

**核心价值**: 一行代码搞定所有配置，无需记忆几十个参数。

## 问题分析

### LivingTreeAI 现状

`unified_config.py` 存在的问题:

| 问题 | 现状 | 影响 |
|------|------|------|
| 参数爆炸 | 600+ 行默认值 | 配置复杂度高 |
| 学习成本 | 50+ 个 `get_*` 方法 | API 难以记忆 |
| 手动调优 | 每个参数单独设置 | 容易出错 |
| 不一致 | 各模块独立配置 | 参数不协调 |

### nanochat 理念

```python
# 只需传入 depth，其他全部自动计算
def compute_optimal_config(depth):
    width = depth * 64
    heads = depth // 2
    lr = 0.0003 / (depth ** 0.5)
    return {...}
```

## 设计方案

### 核心思想

**单参数调优**: 输入一个 `depth` (1-10)，自动计算所有相关参数。

### 参数映射表

| 类别 | 参数 | 公式 | 理由 |
|------|------|------|------|
| **超时** | timeout | `30 * (1 + 0.3 * depth^0.7)` | 对数增长，避免无限膨胀 |
| **重试** | max_retries | `max(1, 2 + log2(depth))` | 复杂度增加时重试更重要 |
| **Token** | max_tokens | `2048 * depth^1.5` | 指数增长支持复杂任务 |
| **并发** | max_workers | `max(1, 2 * sqrt(depth))` | 资源有限，平方根增长 |
| **轮询** | polling | `base * sqrt(depth)` | 平衡响应速度与资源 |
| **LLM** | temperature | `0.5 + 0.05 * depth` | 复杂度高时保持创造性 |

### Depth 等级

| Depth | 场景 | 示例任务 |
|-------|------|---------|
| 1-2 | 极简单 | ping, health_check, list |
| 3-4 | 普通 | code_complete, analyze, search |
| 5-6 | 复杂 | refactor, architect, build |
| 7-8 | 极复杂 | auto_fix, evolve, self_improve |
| 9-10 | 极限 | autonomous, full_auto |

## 使用示例

### 1. 基本使用

```python
from core.config.optimal_config import compute_optimal_config

# 简单任务
config = compute_optimal_config(depth=2)

# 复杂任务
config = compute_optimal_config(depth=8)
```

### 2. 任务类型自动推断

```python
from core.config.optimal_config import compute_optimal_config_for_task

# 自动推断 depth
config = compute_optimal_config_for_task("code_fix")  # depth=3
config = compute_optimal_config_for_task("architect")  # depth=6
```

### 3. 预设配置

```python
from core.config.optimal_config import get_preset

config = get_preset("minimal")  # depth=1
config = get_preset("heavy")     # depth=7
```

### 4. 便捷函数

```python
from core.config.optimal_config import quick_config, normal_config, heavy_config

config = quick_config()   # depth=1
config = normal_config()   # depth=3
config = heavy_config()    # depth=7
```

### 5. 与 UnifiedConfig 集成

```python
from core.config.optimal_config import sync_to_unified_config

# 将计算最优配置同步到 UnifiedConfig
sync_to_unified_config(depth=5)
```

## API 参考

### `compute_optimal_config(depth: int = 3) -> OptimalConfig`

根据任务复杂度自动计算最优配置。

**参数**:
- `depth`: 任务复杂度 (1-10)

**返回**:
- `OptimalConfig`: 包含所有计算得到的配置

### `get_depth_from_task(task_type: str) -> int`

根据任务类型推断复杂度。

**参数**:
- `task_type`: 任务类型描述

**返回**:
- `int`: 推荐 depth (1-10)

### `compute_optimal_config_for_task(task_type: str) -> OptimalConfig`

一步到位: 根据任务类型获取最优配置。

### `get_preset(name: str) -> Optional[OptimalConfig]`

获取预设配置 (minimal/light/normal/medium/heavy/extreme)。

## 配置输出示例

```python
>>> from core.config.optimal_config import compute_optimal_config
>>> config = compute_optimal_config(depth=5)
>>> config.to_dict()
{
    'depth': 5,
    'timeout': 39.0,
    'long_timeout': 78.0,
    'quick_timeout': 7.8,
    'retry_delay': 1.12,
    'max_retries': 4,
    'exponential_base': 2.0,
    'polling_short': 0.45,
    'polling_medium': 1.12,
    'polling_long': 1.0,
    'wait_short': 1.12,
    'wait_long': 5.0,
    'max_tokens': 2048,
    'max_context': 4096,
    'max_workers': 4,
    'batch_size': 72,
    'llm_temperature': 0.75,
    'llm_top_p': 0.85,
    'agent_init_timeout': 11.18,
    'agent_max_iterations': 150
}
```

## 与 UnifiedConfig 的关系

```
                    LivingTreeAI Config
------------------------------------------------------------
|                                                              |
|  +---------------------+    +---------------------------+ |
|  |  unified_config.py  |    |    optimal_config.py     | |
|  |  (手动精细控制)      |    |    (自动计算最优)         | |
|  |                     |    |                           | |
|  |  - 50+ get_* 方法  |    |  - compute_optimal_config| |
|  |  - 600+ 默认值     |    |  - get_depth_from_task    | |
|  |  - 复杂层级结构    |    |  - 单一 depth 参数        | |
|  +---------------------+    +---------------------------+ |
|              |                           |                 |
|              |     sync_to_unified_config()                 |
|              +---------------+---------------------------+
|                              |
|                              V
|              +---------------------------+
|              |   运行时生效的配置        |
|              |   (两者的结合)            |
|              +---------------------------+
```

## 适用场景

### 推荐使用 optimal_config

- 快速原型开发
- 任务复杂度不确定
- 希望简化配置管理
- 不想记忆大量参数

### 继续使用 unified_config

- 需要精确控制每个参数
- 有特殊的硬件/网络环境
- 需要复杂的配置层级
- 需要配置持久化

## 文件清单

| 文件 | 路径 | 功能 |
|------|------|------|
| optimal_config.py | core/config/ | 计算最优配置模块 |
| 测试 | test_optimal_config.py | 单元测试 |

## 后续计划

1. **Phase 2**: 与 EvolutionEngine 集成
   - 根据评估结果自动调整 depth
   - 学习最优 depth 映射

2. **Phase 3**: 与 Agent Pipeline 集成
   - 自动推断任务类型
   - 动态调整配置

3. **Phase 4**: 可视化配置面板
   - depth 滑块调节
   - 实时预览参数变化
