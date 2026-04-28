# Optimal Config 后续计划

## 概述

基于 "计算最优配置" 理念，将 optimal_config 逐步集成到 LivingTreeAI 的核心系统中。

## 当前状态

✅ **Phase 1: 核心实现** - 已完成
✅ **Phase 2: EvolutionEngine 集成** - 已完成
✅ **Phase 3: Agent Pipeline 集成** - 已完成
✅ **Phase 4: 可视化配置面板** - 已完成
- `ui/optimal_config_panel.py` - PyQt6 配置面板
- `ui/optimal_config_visualization.py` - 可视化组件
- `core/evolution_engine/config_persistence.py` - 持久化模块

---

## Phase 2 + 3: 已完成功能

### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| EvolutionDepthOptimizer | `evolution_depth_optimizer.py` | 评估驱动 depth 调整 |
| DepthHintLearner | `depth_hint_learner.py` | 任务类型→depth 映射学习 |
| EvolutionIntegrator | `evolution_integrator.py` | 统一配置接口 |
| PipelineOptimizer | `pipeline_optimizer.py` | 任务分类 + Pipeline 配置 |
| DynamicConfigAdjuster | `dynamic_config_adjuster.py` | 实时性能监控 + 动态调整 |
| AgentPipelineIntegrator | `agent_integrator.py` | 完整执行闭环 |

### 意图推断

```
修复这个bug    → CODE_FIX      → depth=3, timeout=60s
重构函数       → REFACTOR      → depth=6, timeout=180s
设计架构       → ARCHITECTURE  → depth=8, timeout=300s
写排序算法     → CODE_GENERATION → depth=5, timeout=120s
什么是装饰器   → QUERY         → depth=2, timeout=30s
```

### 执行闭环

```
意图 → 任务分类 → Evolution 配置 → Pipeline 配置 → 动态调整 → 执行 → 结果
```

---

## Phase 3 详细实现

### PipelineOptimizer

```python
from core.evolution_engine.pipeline_optimizer import create_pipeline_optimizer

optimizer = create_pipeline_optimizer()
task_type = optimizer.classify_task("修复这个bug")
# → CODE_FIX

config = optimizer.get_optimal_config(task_type)
# → max_depth=3, timeout=60s
```

### DynamicConfigAdjuster

```python
from core.evolution_engine.dynamic_config_adjuster import create_dynamic_adjuster

adjuster = create_dynamic_adjuster()
adjuster.set_config({'max_depth': 5, 'timeout': 60.0})

# 监控 CPU 过高
metrics = PerformanceMetrics(cpu_percent=90.0)
adjustments = adjuster.monitor(metrics)
# → DEPTH: 5 → 4, CONTEXT: 8192 → 6553
```

### AgentPipelineIntegrator

```python
from core.evolution_engine.agent_integrator import create_agent_integrator

integrator = create_agent_integrator()
result = integrator.execute("重构这个函数")

print(f"Task Type: {result.task_type.name}")
print(f"Config: depth={result.pipeline_config.max_depth}")
print(f"Adjustments: {len(result.adjustments)}")
```

---

## Phase 4: 可视化配置面板 ✅ 已完成

### 新增文件

| 文件 | 功能 |
|------|------|
| `ui/optimal_config_panel.py` | PyQt6 配置面板组件 |
| `ui/optimal_config_visualization.py` | 配置可视化组件 |
| `core/evolution_engine/config_persistence.py` | 配置持久化模块 |

### 功能

#### OptimalConfigPanel
- Depth 滑块 (1-10)
- 快速预设 (快速/平衡/深度/专家)
- 基础配置 (timeout, retries, context_limit)
- 高级配置 (tokens, temperature, features)
- 实时预览
- QSettings 持久化

#### ConfigVisualizer
- 雷达图数据生成
- 进度条可视化
- 历史趋势跟踪
- ASCII 仪表盘

#### ConfigStorage
- JSON 文件存储
- QSettings 存储
- 环境变量存储
- 内存存储

### 使用示例

```python
# 创建面板
from ui.optimal_config_panel import create_config_panel
panel = create_config_panel()
panel.config_changed.connect(lambda cfg: print(cfg))

# 可视化
from ui.optimal_config_visualization import create_dashboard
dashboard = create_dashboard()
print(dashboard.render_full_dashboard(config, history))

# 持久化
from core.evolution_engine.config_persistence import create_manager
manager = create_manager()
manager.set('depth', 8)
manager.export('config.json')
```

---

## Phase 2 详细实现

### EvolutionDepthOptimizer

```python
from core.evolution_engine.evolution_depth_optimizer import create_optimizer

optimizer = create_optimizer(initial_depth=5, strategy="moderate")

# 记录评估
optimizer.record_evaluation(0.5, "code_fix")

# 分析并调整
result = optimizer.analyze_and_adjust()
# depth: 5 → 7 (低分自动增加)
```

### DepthHintLearner

```python
from core.evolution_engine.depth_hint_learner import DepthHintLearner

learner = DepthHintLearner()

# 记录学习数据
learner.record('refactor', 5, 0.7)
learner.record('refactor', 6, 0.85)
learner.record('refactor', 7, 0.9)

# 获取建议
hint = learner.get_hint('refactor')
print(hint.recommended_depth)  # 7 (基于历史数据)
```

### EvolutionIntegrator

```python
from core.evolution_engine.evolution_integrator import EvolutionConfigIntegrator

integrator = EvolutionConfigIntegrator()

# 意图→配置
result = integrator.get_config_for_intent("重构函数")
print(result.depth)  # 5
print(result.config['timeout'])  # 57s

# 学习闭环
config_result, opt_result = integrator.record_and_adjust('code_fix', 0.5)
```
    'auto_fix': 7,           # 自动修复 → depth=7
    'architecture': 8,       # 架构设计 → depth=8
}

# 贝叶斯更新
def update_depth_hint(task_type: str, success_rate: float):
    """根据成功率更新 depth 映射"""
    current = DEPTH_HINTS.get(task_type, 5)
    if success_rate > 0.9:
        DEPTH_HINTS[task_type] = max(1, current - 1)
    elif success_rate < 0.7:
        DEPTH_HINTS[task_type] = min(10, current + 1)
```

### 任务清单

- [ ] `evolution_depth_optimizer.py` - Evolution 深度优化器
- [ ] `depth_hint_learner.py` - 任务类型→depth 映射学习器
- [ ] `evolution_integrator.py` - Evolution 集成入口
- [ ] 单元测试

---

## Phase 3: 与 Agent Pipeline 集成

**目标**: 自动推断任务类型，动态调整配置

### 实现方案

```python
# core/agent/pipeline_optimizer.py

class PipelineOptimizer:
    """Agent Pipeline 优化器"""
    
    def infer_task_type(self, intent: str) -> str:
        """从意图推断任务类型"""
        patterns = {
            'fix|bug|错误': 'code_fix',
            'refactor|重构|优化': 'refactor',
            '设计|架构|architecture': 'architecture',
            '写|创建|生成': 'code_generate',
        }
        for pattern, task_type in patterns.items():
            if re.search(pattern, intent, re.IGNORECASE):
                return task_type
        return 'general'
    
    def get_optimal_config(self, intent: str) -> dict:
        """根据意图获取最优配置"""
        task_type = self.infer_task_type(intent)
        depth = DEPTH_HINTS.get(task_type, 5)
        return compute_optimal_config(depth)
```

### 动态调整策略

```python
# 执行过程中动态调整

class DynamicConfigAdjuster:
    def __init__(self, initial_config: dict):
        self.config = initial_config
        self.signals = []
        
    def add_signal(self, signal_type: str, value: float):
        """添加监控信号"""
        self.signals.append({'type': signal_type, 'value': value, 'time': time.time()})
        
    def should_adjust(self) -> bool:
        """判断是否需要调整"""
        if len(self.signals) < 10:
            return False
        recent = self.signals[-10:]
        error_rate = sum(1 for s in recent if s['type'] == 'error') / len(recent)
        return error_rate > 0.3
    
    def adjust(self) -> dict:
        """动态调整配置"""
        if self.should_adjust():
            # 增加 depth
            new_depth = min(10, self.config['depth'] + 1)
            self.config = compute_optimal_config(new_depth)
        return self.config
```

### 任务清单

- [ ] `task_type_inferrer.py` - 任务类型推断器
- [ ] `pipeline_optimizer.py` - Pipeline 优化器
- [ ] `dynamic_config_adjuster.py` - 动态调整器
- [ ] `agent_integration.py` - Agent 集成入口

---

## Phase 4: 可视化配置面板

**目标**: depth 滑块调节，实时预览参数变化

### UI 设计

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ Optimal Config 配置面板                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Depth: ━━━━━━━●━━━━━━━━━━  [5]                        │
│          ↑                                        ↑     │
│        简单                                   复杂      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  📊 当前配置预览                                         │
│  ┌─────────────────┬─────────────────┐                 │
│  │ timeout         │ 39s             │                 │
│  │ max_retries     │ 4               │                 │
│  │ max_tokens      │ 2048            │                 │
│  │ max_workers     │ 4               │                 │
│  │ memory_limit    │ 512MB           │                 │
│  └─────────────────┴─────────────────┘                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  📈 参数公式                                             │
│                                                         │
│  timeout = 30 * (1 + 0.3 * depth^0.7)                   │
│  max_retries = 2 + log2(depth)                         │
│  max_tokens = 2048 * depth^1.5                         │
│  max_workers = 2 * sqrt(depth)                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [保存为默认配置]    [重置为推荐]    [应用当前配置]      │
└─────────────────────────────────────────────────────────┘
```

### 实现方案

```python
# ui/optimal_config_panel.py

class OptimalConfigPanel(QWidget):
    def __init__(self):
        self.current_depth = 5
        self.config = compute_optimal_config(5)
        
    def setup_ui(self):
        # Depth 滑块
        self.depth_slider = QSlider(Qt.Horizontal)
        self.depth_slider.setRange(1, 10)
        self.depth_slider.setValue(5)
        self.depth_slider.valueChanged.connect(self.on_depth_changed)
        
        # 配置预览表格
        self.config_table = QTableWidget(5, 2)
        
        # 保存按钮
        self.save_btn = QPushButton("保存为默认配置")
        self.save_btn.clicked.connect(self.save_config)
        
    def on_depth_changed(self, value):
        self.current_depth = value
        self.config = compute_optimal_config(value)
        self.update_preview()
```

### 任务清单

- [ ] `ui/optimal_config_panel.py` - 配置面板 UI
- [ ] `core/config/config_registry.py` - 配置注册表
- [ ] 配置持久化 (JSON/YAML)
- [ ] 面板测试

---

## 实施时间表

| Phase | 工作量 | 优先级 |
|-------|--------|--------|
| Phase 1 | 1天 | ✅ 已完成 |
| Phase 2 | 2天 | P1 |
| Phase 3 | 3天 | P2 |
| Phase 4 | 2天 | P2 |

---

## 技术债务

- [ ] script_sandbox.py 的 `_restrict_print` 错误已修复
- [ ] 需要处理循环导入问题 (core/__init__.py)
- [ ] 添加配置验证和回滚机制
