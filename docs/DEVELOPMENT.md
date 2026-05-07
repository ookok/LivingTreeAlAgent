# LivingTree 开发手册

> v2.1 | 2026-05

---

## 1. 环境要求

| 组件 | 版本 | 必需 |
|------|------|------|
| Python | 3.10+ | ✅ |
| Git | 2.x | ✅ |
| pip | latest | ✅ |
| python-docx | latest | 文档功能 |
| openpyxl | latest | Excel 功能 |
| vLLM | latest | 本地模型（可选） |

---

## 2. 快速开始

```bash
# 克隆
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent

# 安装
pip install -e .

# 配置 API Key
mkdir -p config
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入 DeepSeek/Qwen API key

# 启动
python -m livingtree tui
```

### 2.1 本地模型部署（可选）

```bash
# Ubuntu + GPU
chmod +x deploy_local_model.sh
./deploy_local_model.sh       # 默认 Qwen3.5-4B
./deploy_local_model.sh 8B    # Qwen3.5-8B
```

---

## 3. 项目结构

```
LivingTreeAlAgent/
├── livingtree/
│   ├── dna/               # 数字生命核心
│   │   ├── life_engine.py     # 7阶段生命循环
│   │   ├── life_daemon.py     # 自主后台守护
│   │   ├── autonomous_core.py # 主动工作发现
│   │   ├── reasoning_chain.py # 决策溯源
│   │   ├── skill_progression.py # 技能成长
│   │   ├── local_intelligence.py # 边缘智能
│   │   └── gradual_agent.py   # 渐进智能
│   ├── economy/           # 经济引擎
│   ├── treellm/           # LLM 路由
│   ├── knowledge/         # RAG 2.0
│   ├── execution/         # 执行层
│   ├── capability/        # 文档智能 + 工具
│   ├── integration/       # 集成中枢
│   ├── network/           # P2P 网络
│   └── tui/               # 终端UI
├── tests/                 # 单元测试
├── docs/                  # 文档
├── deploy_local_model.sh  # 本地模型部署
└── pyproject.toml
```

---

## 4. 模块开发指南

### 4.1 添加新模块

```python
# livingtree/dna/my_module.py
"""MyModule — description."""

class MyModule:
    def __init__(self):
        pass

# Singleton
_my_module = None
def get_my_module() -> MyModule:
    global _my_module
    if _my_module is None:
        _my_module = MyModule()
    return _my_module
```

### 4.2 注册到系统

```python
# 1. livingtree/dna/__init__.py
from .my_module import MyModule, get_my_module

# 2. livingtree/__init__.py (root lazy imports)
_LAZY["MyModule"] = ".dna"
__all__.append("MyModule")

# 3. 自动集成点（可选）:
#    - LifeDaemon._run_cycle() → 自主循环
#    - LifeEngine._execute() → 任务执行管道
#    - Hub._init_async() → 系统启动
```

### 4.3 编写测试

```python
# tests/dna/test_my_module.py
import pytest
from livingtree.dna.my_module import MyModule

def test_basic():
    m = MyModule()
    assert m is not None
```

运行测试: `python -m pytest tests/ -v`

---

## 5. API 约定

### 5.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块文件 | snake_case | `my_module.py` |
| 类名 | PascalCase | `MyClass` |
| 函数/方法 | snake_case | `my_function()` |
| 常量 | UPPER_SNAKE | `MAX_SIZE` |
| 私有属性 | `_prefix` | `self._cache` |

### 5.2 Import 规范

```python
# 顶层模块间用绝对导入
from livingtree.dna.life_engine import LifeEngine

# 同层用相对导入
from .reasoning_chain import ReasoningChain

# 跨层委托（避免循环）
from ..execution.fitness_landscape import get_fitness_landscape
```

### 5.3 错误处理

```python
# 优雅降级，不阻断主流程
try:
    from .optional_module import OptionalFeature
    OptionalFeature().use()
except Exception as e:
    logger.debug(f"Optional feature unavailable: {e}")
```

---

## 6. 经济引擎使用

```python
from livingtree.economy import EconomicPolicy, ROIModel, get_economic_orchestrator

# 策略选择
policy = EconomicPolicy.quality()  # 环评报告用质量优先
model = policy.select_model(task_complexity=0.8)

# ROI 评估
roi = ROIModel()
result = roi.evaluate(
    task_id="proj_001", task_type="environmental_report",
    estimated_tokens=50000, model=model,
    complexity=0.8, user_priority=0.9, predicted_quality=0.85,
)
if result.approved:
    print(f"ROI: {result.roi_estimate:.1f}x, 成本≈¥{result.estimated_cost_yuan:.3f}")
```

---

## 7. 文档智能 API

```python
from livingtree.capability import (
    DocumentIntelligence, DocumentUnderstanding, IncrementalDoc,
)

# 读取 Word 结构
di = DocumentIntelligence()
structure = di.read_docx("report.docx")
print(structure.outline)

# 语义理解（专家级分析）
du = DocumentUnderstanding(consciousness=llm)
analysis = await du.analyze("report.docx")
for f in analysis.findings:
    print(f.one_line())

# 增量处理（大文档重复提交）
inc = IncrementalDoc(consciousness=llm)
v1 = await inc.submit("report_v1.docx", session="proj_x")
v2 = await inc.submit("report_v2.docx", session="proj_x")  # 只处理变更段落
```

---

## 8. 自主智能 API

```python
from livingtree.dna import (
    AutonomousCore, ReasoningChain, SkillProgression, LocalIntelligence,
)

# 自主循环
core = get_autonomous_core(world, consciousness)
result = await core.cycle()
# → 发现 3 项待办，自动执行 2 项，审计发现 1 处问题

# 决策溯源
chain = get_reasoning_chain()
chain.decide("model_selection", "AERSCREEN",
    reasoning="地形平坦，高斯烟羽足够",
    alternatives=["ADMS", "CALPUFF"])
chain.validate(decision_id, "预测偏差<15%", correct=True)

# 技能追踪
prog = get_skill_progression()
prog.record_outcome("regulatory_compliance", success=True)
print(prog.progress_report().summary)

# 边缘智能
li = get_local_intelligence(consciousness=remote_llm)
await li.auto_connect_local()  # 自动检测本地模型
response, tier = await li.respond("GB3095 SO2限值")
print(f"Tier: {tier.value}")  # DIRECT | LOCAL | REMOTE
```
