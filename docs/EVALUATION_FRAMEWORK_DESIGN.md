# Evolution Engine - Evaluation Framework Design Document

## 概述

Evaluation Framework 是 LivingTreeAI Evolution Engine 的核心组件，提供量化的 Agent 能力评估机制。

**价值**: 引入客观评估指标，量化 Agent 能力提升，替代原有的启发式评估。

## 架构设计

```
core/evolution_engine/evaluator/
├── __init__.py              # 模块导出
├── base_evaluator.py        # 基类和指标体系
├── dclm_evaluator.py        # DCLM CORE 评分器
├── bpb_evaluator.py         # BPB 评估器
├── benchmark_evaluator.py   # 标准任务评测器
└── evolution_evaluator.py   # 主控制器
```

## 评估维度

### 1. DCLM CORE (代码生成质量)

基于 DCLM 数据集的代码质量评估，从多个子维度打分：

| 维度 | 权重 | 说明 |
|------|------|------|
| 正确性 | 50% | 代码能否正确执行 |
| 语法质量 | 30% | 缩进、括号匹配等 |
| 语义质量 | - | 关键字、函数/类定义 |
| 风格评分 | 20% | 文档字符串、类型注解 |

**参考基准**:
- DCLM Data: 0.89 (平均通过率)

### 2. BPB (Bits Per Byte)

语言模型压缩效率指标，衡量模型对代码的压缩能力。

**公式**: `BPB = -log(P(x)) / bytes(x)`

| 模型 | BPB |
|------|-----|
| GPT-4 | 0.85 |
| Claude | 0.88 |
| Codex | 0.90 |
| Llama3 | 0.95 |

**越低越好**

### 3. Standard Benchmarks

标准任务性能评测:

| 任务 | 描述 | 参考 GPT-4 |
|------|------|-----------|
| ARC | AI2 推理挑战 | 96.3% |
| GSM8K | 数学推理 | 94.8% |
| MMLU | 多任务理解 | 86.4% |
| HumanEval | 代码生成 | 90.2% |
| MBPP | Python 编程 | 81.7% |

## 评估模式

```python
class EvaluationMode(Enum):
    FULL = "full"       # 完整评估 (所有评估器)
    QUICK = "quick"     # 快速评估 (DCLM + Benchmark)
    TARGETED = "targeted" # 定向评估 (指定评估器)
    CONTINUOUS = "continuous" # 持续监控
```

## 能力维度

```python
class CapabilityDimension(Enum):
    CODE_GENERATION = "code_generation"  # 代码生成
    REASONING = "reasoning"              # 推理能力
    KNOWLEDGE = "knowledge"              # 知识储备
    COMPRESSION = "compression"           # 压缩效率
    ACCURACY = "accuracy"                # 准确性
    SAFETY = "safety"                    # 安全性
```

## 使用示例

### 快速评估
```python
from core.evolution_engine.evaluator import EvolutionEvaluator, EvaluationMode

evaluator = EvolutionEvaluator(project_root=".")
result = evaluator.evaluate(mode=EvaluationMode.QUICK)
print(result.get_overall_score())
```

### 获取能力报告
```python
report = evaluator.get_capability_report()
print(f"能力等级: {report['capability_level']}")
print(f"综合分数: {report['overall_score']:.2f}")
```

### 定向评估
```python
result = evaluator.evaluate(
    mode=EvaluationMode.TARGETED,
    target=['dclm', 'bpb']
)
```

## 数据持久化

评估历史存储在 `.evolution_db/evaluation_history.json`:

```json
{
  "history": [
    {
      "evaluator_name": "dclm",
      "metrics": {...},
      "timestamp": "2026-04-25T14:44:00",
      "duration_ms": 125.5
    }
  ],
  "metrics": {
    "total_evaluations": 10,
    "successful_evaluations": 9,
    "average_score": 78.5
  }
}
```

## 趋势追踪

每次评估后自动计算趋势:

- **up**: 分数提升 > 5%
- **down**: 分数下降 > 5%
- **stable**: 变化 < 5%

## 集成计划

Phase 1: 独立评估器 (已完成)
- ✅ DCLM CORE 评分器
- ✅ BPB 评估器
- ✅ Benchmark 评测器
- ✅ Evolution Evaluator 主控制器

Phase 2: 与 Evolution Engine 集成
- EvolutionEngine 主循环调用 evaluator
- 触发条件: 代码提交、性能回归检测

Phase 3: 可视化报告
- Web Dashboard 展示能力趋势
- 与 Git 历史集成

## 扩展评估器

创建新的评估器只需:

1. 继承 `BaseEvaluator` 或实现相同接口
2. 实现 `evaluate()` 方法
3. 返回 `EvaluationResult`
4. 注册到 `EvolutionEvaluator._init_evaluators()`

```python
class MyEvaluator:
    def __init__(self, project_root: str, config: dict = None):
        self.name = "my_evaluator"
        self.project_root = project_root
        self.config = config or {}
    
    def evaluate(self, custom_prompts=None) -> EvaluationResult:
        # 实现评估逻辑
        return EvaluationResult(...)
```
