# LivingTree AI API 文档

## 📚 目录

1. [概述](#概述)
2. [快速开始](#快速开始)
3. [核心模块 API](#核心模块-api)
   - [生命引擎](#生命引擎)
   - [自我意识系统](#自我意识系统)
   - [免疫系统](#免疫系统)
   - [代谢系统](#代谢系统)
   - [细胞框架](#细胞框架)
   - [自主进化系统](#自主进化系统)
4. [集成指南](#集成指南)
5. [最佳实践](#最佳实践)
6. [性能优化](#性能优化)

---

## 🌲 概述

LivingTree AI 是一个革命性的细胞AI框架，提供以下核心能力：

- **主动推理**: 基于自由能原理的推理引擎
- **自我意识**: 元认知和反思能力
- **免疫系统**: 异常检测和自我修复
- **代谢系统**: 资源管理和能量效率
- **自主进化**: 持续学习和优化

---

## 🚀 快速开始

### 安装

```bash
# 安装客户端
pip install -e ./client

# 安装服务器
pip install -e ./server/relay_server
```

### 基本用法

```python
from cell_framework import LifeEngine, SelfConsciousness, ImmuneSystem, MetabolicSystem

# 创建核心组件
life_engine = LifeEngine()
self_con = SelfConsciousness()
immune = ImmuneSystem()
metabolic = MetabolicSystem()

# 设置目标
life_engine.set_goal({'name': '完成任务', 'description': '实现目标'})

# 运行推理循环
result = await life_engine.run_inference_cycle()

# 内省
introspection = await self_con.introspect()
```

---

## 🧠 核心模块 API

### 生命引擎 (LifeEngine)

#### 初始化

```python
life_engine = LifeEngine()
```

#### 方法

| 方法 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `set_goal(goal)` | 设置目标 | `goal`: Dict - 目标描述 | None |
| `run_inference_cycle()` | 运行推理循环 | 无 | Dict - 推理结果 |
| `reflect()` | 反思当前状态 | 无 | Dict - 反思结果 |
| `get_system_status()` | 获取系统状态 | 无 | Dict - 系统状态 |
| `learn_from_experience(experience)` | 从经验学习 | `experience`: Dict - 经验数据 | None |

#### 使用示例

```python
# 设置目标
life_engine.set_goal({
    'name': '学习Python',
    'description': '掌握Python编程'
})

# 运行推理循环
result = await life_engine.run_inference_cycle()
print(f"自由能: {result['free_energy']}")
print(f"预测误差: {result['prediction_error']}")
print(f"意识水平: {result['awareness_level']}")

# 获取系统状态
status = life_engine.get_system_status()
print(f"系统健康: {status['health']}")
print(f"当前目标: {status['current_goal']}")
```

---

### 自我意识系统 (SelfConsciousness)

#### 初始化

```python
self_con = SelfConsciousness()
```

#### 方法

| 方法 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `introspect()` | 内省 | 无 | Dict - 内省结果 |
| `reflect_on_decision(decision)` | 反思决策 | `decision`: Dict - 决策记录 | Dict - 反思结果 |
| `set_goal(goal)` | 设置长期目标 | `goal`: Dict - 目标 | None |
| `get_self_narrative()` | 获取自我叙事 | 无 | str - 自我叙事 |
| `evaluate_self_worth()` | 评估自我价值 | 无 | float - 自我价值 |

#### 使用示例

```python
# 内省
introspection = await self_con.introspect()
print(f"意识水平: {introspection['consciousness_level']}")
print(f"情绪状态: {introspection['mood']}")

# 获取自我叙事
narrative = self_con.get_self_narrative()
print(f"自我叙事: {narrative}")

# 评估自我价值
self_worth = self_con.evaluate_self_worth()
print(f"自我价值: {self_worth}")
```

---

### 免疫系统 (ImmuneSystem)

#### 初始化

```python
immune = ImmuneSystem()
```

#### 方法

| 方法 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `monitor()` | 监控系统 | 无 | Dict - 监控报告 |
| `detect_threat(data)` | 检测威胁 | `data`: Dict - 待检测数据 | Threat |
| `heal()` | 自我修复 | 无 | Dict - 修复结果 |
| `get_immune_status()` | 获取免疫状态 | 无 | Dict - 免疫状态 |
| `add_antibody(pattern, response)` | 添加抗体 | `pattern`: str, `response`: Callable | None |

#### 使用示例

```python
# 监控系统
monitor = await immune.monitor()
print(f"活跃威胁: {monitor['active_threats']}")

# 检测威胁
threat = await immune.detect_threat({
    'source': 'external',
    'input': '可疑输入'
})

# 自我修复
result = await immune.heal()
print(result['message'])
```

---

### 代谢系统 (MetabolicSystem)

#### 初始化

```python
metabolic = MetabolicSystem()
```

#### 方法

| 方法 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `manage_resources()` | 管理资源 | 无 | Dict - 代谢报告 |
| `allocate_resources(requester_id, priority)` | 分配资源 | `requester_id`: str, `priority`: str | bool |
| `release_resources(requester_id)` | 释放资源 | `requester_id`: str | None |
| `get_metabolic_report()` | 获取代谢报告 | 无 | Dict - 代谢报告 |
| `optimize_efficiency()` | 优化效率 | 无 | None |
| `enter_dormancy()` | 进入休眠 | 无 | None |
| `wake_up()` | 唤醒系统 | 无 | None |

#### 使用示例

```python
# 管理资源
report = await metabolic.manage_resources()
print(f"能量级别: {report['energy_level']}")

# 分配资源
success = await metabolic.allocate_resources('task_1', 'high')
print(f"资源分配: {'成功' if success else '失败'}")

# 优化效率
metabolic.optimize_efficiency()
```

---

### 细胞框架 (CellFramework)

#### 细胞类型

| 细胞类型 | 描述 | 类名 |
|----------|------|------|
| 推理细胞 | 逻辑推理能力 | `ReasoningCell` |
| 记忆细胞 | 知识存储和检索 | `MemoryCell` |
| 学习细胞 | 持续学习能力 | `LearningCell` |
| 感知细胞 | 输入处理和意图识别 | `PerceptionCell` |
| 行动细胞 | 输出执行和工具调用 | `ActionCell` |
| 预测细胞 | 未来预测能力 | `PredictionCell` |

#### 创建细胞

```python
from cell_framework import (
    ReasoningCell, MemoryCell, LearningCell,
    PerceptionCell, ActionCell, PredictionCell,
    create_cell
)

# 方式1: 直接创建
reasoner = ReasoningCell()
memory = MemoryCell()

# 方式2: 使用工厂函数
cell = create_cell('reasoning')
cell = create_cell('memory')
cell = create_cell('prediction')
```

#### 细胞通信

```python
from cell_framework import Signal

# 创建信号
signal = Signal(
    type='reason',
    data={'query': '什么是细胞AI?'},
    priority='high'
)

# 发送信号
result = await reasoner.process(signal)
```

---

### 自主进化系统 (AutonomousEvolution)

#### 初始化

```python
from cell_framework import AutonomousEvolution

evolution = AutonomousEvolution(evolution_interval=30.0)
```

#### 方法

| 方法 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `evolve()` | 执行一次进化 | 无 | Dict - 进化结果 |
| `start_evolution_loop()` | 启动进化循环 | 无 | None |
| `get_evolution_stats()` | 获取进化统计 | 无 | Dict - 统计数据 |

#### 使用示例

```python
# 执行一次进化
result = await evolution.evolve()
print(f"进化代数: {result['generation']}")
print(f"成功: {result['success']}")

# 获取统计
stats = evolution.get_evolution_stats()
print(f"成功率: {stats['success_rate']}")
print(f"最佳性能: {stats['best_performance']}")
```

---

## 🔗 集成指南

### 与 RAG 引擎集成

```python
from life_integration import LifeIntegration
from enhanced_rag import EnhancedRAGEngine

# 创建集成层
integration = LifeIntegration(life_engine)
await integration.initialize()

# 创建增强RAG引擎
enhanced_rag = EnhancedRAGEngine(integration)

# 执行增强查询
result = await enhanced_rag.query("什么是细胞AI?")
print(f"结果: {result.content}")
print(f"置信度: {result.confidence}")
```

### 与 LLM Wiki 集成

```python
from llm_wiki.enhanced_wiki import EnhancedWiki
from llm_wiki.wiki_core import WikiCore

# 创建增强Wiki
wiki_core = WikiCore()
enhanced_wiki = EnhancedWiki(wiki_core, integration)

# 智能搜索
results = await enhanced_wiki.smart_search("细胞AI")

# 获取推荐
recommendations = await enhanced_wiki.get_recommendations(user_id)
```

---

## 💡 最佳实践

### 1. 资源管理

```python
# 合理分配资源
async def process_task(task, priority='normal'):
    # 分配资源
    success = await metabolic.allocate_resources(task.id, priority)
    
    if success:
        try:
            # 执行任务
            result = await execute_task(task)
            return result
        finally:
            # 释放资源
            metabolic.release_resources(task.id)
```

### 2. 错误处理

```python
async def safe_execute(task):
    try:
        # 检测威胁
        threat = await immune.detect_threat({'task': task})
        
        if threat:
            print(f"检测到威胁: {threat.description}")
            await immune.heal()
            return None
        
        # 执行任务
        return await execute_task(task)
    
    except Exception as e:
        # 记录错误并自我修复
        await immune.heal()
        raise
```

### 3. 持续学习

```python
async def learn_from_interaction(user_id, query, response, feedback):
    # 更新用户画像
    await integration.enhance_user_profile(user_id, {
        'query': query,
        'response': response,
        'feedback': feedback
    })
    
    # 学习经验
    life_engine.learn_from_experience({
        'user_id': user_id,
        'query': query,
        'response': response,
        'feedback': feedback
    })
```

---

## ⚡ 性能优化

### 缓存策略

```python
# 自适应缓存
optimizer = PerformanceOptimizer(life_engine)

# 根据命中率调整策略
hit_rate = get_cache_hit_rate()
optimizer.optimize_cache(hit_rate)
```

### 并行度优化

```python
# 根据任务数量调整并行度
task_count = get_pending_tasks()
optimizer.optimize_parallelism(task_count)
```

### 定期优化

```python
async def optimization_loop():
    optimizer = PerformanceOptimizer(life_engine)
    
    while True:
        # 监控性能
        metrics = await optimizer.monitor()
        
        # 执行优化
        results = await optimizer.optimize()
        
        for result in results:
            print(f"优化: {result.action} (改进 {result.improvement*100:.1f}%)")
        
        await asyncio.sleep(60)  # 每分钟检查一次
```

---

## 📊 监控指标

### 核心指标

| 指标 | 描述 | 目标值 |
|------|------|--------|
| `free_energy` | 自由能 | < 0.5 |
| `prediction_error` | 预测误差 | < 0.1 |
| `awareness_level` | 意识水平 | > 0.7 |
| `cpu_usage` | CPU使用率 | < 0.7 |
| `memory_usage` | 内存使用率 | < 0.75 |
| `response_time` | 响应时间 | < 2.0s |

### 系统状态检查

```python
def check_system_health():
    status = {
        'life_engine': life_engine.get_system_status(),
        'immune': immune.get_immune_status(),
        'metabolic': metabolic.get_metabolic_report()
    }
    
    issues = []
    
    if status['life_engine']['health'] < 0.8:
        issues.append("生命引擎健康状态不佳")
    
    if status['immune']['status'] != 'normal':
        issues.append("免疫系统异常")
    
    if status['metabolic']['energy_level'] == 'critical':
        issues.append("能量不足")
    
    return {
        'status': 'healthy' if not issues else 'warning',
        'issues': issues
    }
```

---

## 🔧 配置参考

### 配置文件位置

```
config/life_system.yaml
```

### 配置示例

```yaml
life_engine:
  learning_rate: 0.01
  inference_interval: 1.0
  free_energy_threshold: 0.5

self_consciousness:
  introspection_interval: 5.0
  meditation_duration: 30

immune_system:
  monitoring_interval: 2.0
  threat_threshold: 0.7

metabolic_system:
  dormancy_timeout: 300
  energy_regeneration_rate: 0.5

autonomous_evolution:
  evolution_interval: 30.0
  mutation_rate: 0.1
  selection_pressure: 0.7
```

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-01 | 初始版本 |
| v1.1 | 2026-05-02 | 添加自主进化系统 |
| v1.2 | 2026-05-03 | 添加性能优化器 |

---

## 📞 支持

如有问题或建议，请提交 Issue 到项目仓库。

---

*LivingTree AI - 让AI像生命一样思考* 🚀
