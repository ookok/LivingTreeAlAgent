# EIA 模块架构分析与改造升级方案

**文档版本**: v1.0  
**创建日期**: 2026-04-27  
**负责人**: LivingTree AI Agent Team

---

## 一、当前架构概览

### 1.1 模块分布地图

```
EIA 模块文件分布（按目录分类）
├── client/src/business/eia_process/          # 流程管理层
│   ├── eia_process_manager.py              # 中央协调器 (444行)
│   ├── agents/
│   │   ├── process_parser.py              # 4层代理协作
│   │   ├── process_expander.py            # 流程扩展
│   │   ├── eia_analyst.py                #  pollutant分析 (575行)
│   │   └── visualization_agent.py         # 可视化代理
│   └── utils/
│
├── client/src/business/env_lifecycle/       # 环境生命周期
│   └── eia_40.py                          # EIA 4.0智能引擎 (706行)
│
├── client/src/business/living_tree_ai/eia_system/  # 核心工作流
│   ├── workbench.py                       # 端到端报告生成 (499行)
│   ├── spatial_intelligence/
│   │   └── spatial_engine.py             # 空间智能引擎 (626行)
│   ├── source_calculator.py              # 污染源计算 (444行)
│   ├── compliance_checker.py             # 合规性检查 (528行)
│   ├── report_completeness_auditor.py    # 报告完整性审计 (839行)
│   └── smart_form/universal_doc/
│       └── universal_template_engine.py  # Word模板引擎 (608行)
│
├── client/src/business/ei_agent/           # EIAgent 适配器
│   └── ei_agent_adapter.py               # Agent集成适配器 (456行)
│
├── client/src/presentation/wizards/
│   └── ei_wizard.py                      # 6步向导UI (815行)
│
└── client/src/presentation_backup_20260426/panels/
    └── eia_process_panel.py              # EIA流程面板 (备份状态)
```

### 1.2 核心组件职责矩阵

| 组件 | 主要职责 | 状态 | 完整性 |
|------|---------|------|--------|
| **EIAProcessManager** | 4层代理协作编排 | ✅ 活跃 | 85% |
| **EIAAnalyst** | 污染物识别与风险分析 | ✅ 活跃 | 70% |
| **EIA40Engine** | 3D时空模拟与方案比选 | ⚠️ 模拟中 | 40% |
| **EIAWorkbench** | 端到端报告生成工作流 | ✅ 活跃 | 75% |
| **RiskManagementEngine** | 预测性风险评估 | ⚠️ 部分实现 | 50% |
| **SpatialIntelligenceEngine** | POI识别与敏感区分析 | ✅ 活跃 | 80% |
| **ReportCompletenessAuditor** | 缺失信息检测 | ✅ 活跃 | 90% |
| **UniversalDocumentTemplate** | Word模板引擎 | ⚠️ 部分实现 | 60% |
| **ComplianceChecker** | 标准合规验证 | ✅ 活跃 | 70% |
| **EIAgentAdapter** | Agent编排集成 | ⚠️ TODO较多 | 45% |

---

## 二、架构问题分析

### 2.1 🔴 严重问题（需立即修复）

#### 问题 1: 导入路径不一致
**影响范围**: `eia_process_manager.py` 及多个关联文件  
**问题描述**:
```python
# 当前错误写法
from core.eia_process.agents.process_parser import ProcessParser
from core.eia_process.agents.eia_analyst import EIAAnalyst

# 正确写法（遵循项目规范）
from client.src.business.eia_process.agents.process_parser import ProcessParser
from client.src.business.eia_process.agents.eia_analyst import EIAAnalyst
```

**修复优先级**: P0（阻塞功能）  
**工作量估计**: 2-3小时（批量替换+测试）

---

#### 问题 2: 模块分散导致依赖混乱
**影响范围**: 整个 EIA 功能  
**问题描述**:
- EIA 相关代码分散在 3 个不同业务目录
- `living_tree_ai/eia_system/` 与 `eia_process/` 功能重叠
- 导入路径交叉，难以维护

**建议方案**:
```
方案A: 合并到统一目录
client/src/business/eia_system/
├── process/          # 从 eia_process/ 迁移
├── engine/           # 从 env_lifecycle/ 迁移 eia_40.py
├── workbench/        # 从 living_tree_ai/eia_system/ 迁移
├── agents/           # EIAAnalyst 等代理
└── utils/            # 共享工具函数

方案B: 保持现状，明确职责边界（推荐）
- eia_process/: 流程编排（向导+任务分配）
- eia_system/: 核心算法（计算+模拟+检查）
- ei_agent/: Agent集成层（与外部系统对接）
```

**修复优先级**: P1（技术债务）  
**工作量估计**: 1-2天（方案B）

---

#### 问题 3: UI 组件在备份目录
**影响范围**: `eia_process_panel.py`  
**问题描述**:
- `presentation_backup_20260426/panels/eia_process_panel.py` 是备份状态
- 主 `presentation/panels/` 目录中无对应文件
- `ei_wizard.py` 引用了备份路径（部分导入）

**修复方案**:
1. 将 `eia_process_panel.py` 迁移到 `client/src/presentation/panels/`
2. 更新 `ei_wizard.py` 中的导入路径
3. 删除 `presentation_backup_20260426/` 目录

**修复优先级**: P1  
**工作量估计**: 1小时

---

### 2.2 🟡 中等问题（影响功能完整性）

#### 问题 4: 计算模型简化/模拟实现
**影响文件**:
- `source_calculator.py` - 简化高斯 plume 模型
- `eia_40.py` - 3D 模拟为占位实现
- `spatial_engine.py` - 高程数据（SRTM）未实现

**缺失功能**:
- ❌ AERMOD 模型集成
- ❌ CALPUFF 模型集成
- ❌ Mike21 水动力模型
- ❌ CadnaA 噪声模型
- ❌ SRTM 高程数据接口

**建议方案**:
```python
# 创建模型接口抽象层
class AirDispersionModel(ABC):
    @abstractmethod
    def run(self, emission_source, met_data, receptor_grid):
        pass

class AERMODModel(AirDispersionModel):
    # 实际 AERMOD 可执行文件调用
    pass

class SimplifiedGaussianModel(AirDispersionModel):
    # 当前简化实现（用于快速预估）
    pass
```

**修复优先级**: P2（功能增强）  
**工作量估计**: 3-5天（含测试）

---

#### 问题 5: Word 模板学习能力缺失
**影响文件**: `universal_template_engine.py`  
**问题描述**:
- 模板定义依赖手动编写 JSON
- 无法从现有 Word 报告自动学习格式
- 缺少 `.docx` 解析引擎

**建议方案**:
```python
class DocxTemplateLearner:
    """从 Word 报告学习模板"""
    def learn_from_docx(self, docx_path: str) -> Template:
        # 1. 解析 docx XML 结构
        # 2. 识别标题层级、样式、表格格式
        # 3. 提取章节结构
        # 4. 生成 Template JSON
        pass
```

**修复优先级**: P2  
**工作量估计**: 2-3天

---

#### 问题 6: EIAgentAdapter 功能不完整
**影响文件**: `ei_agent_adapter.py`  
**问题描述**:
- 6个 TODO 标记未完成
- 报告生成逻辑为占位实现
- 附件解析未实现
- 风险评估调用链路未打通

**缺失功能清单**:
```python
# ei_agent_adapter.py 中的 TODO
TODO 1: 实现 _generate_report()           # 报告生成
TODO 2: 实现 _parse_attachments()         # 附件解析
TODO 3: 打通 _assess_risks() 调用链路    # 风险评估
TODO 4: 实现 expert_training_integration  # 专家训练集成
TODO 5: 完善 FusionRAG 检索策略          # 知识库检索
TODO 6: 添加报告质量评估模块             # 质量打分
```

**修复优先级**: P1  
**工作量估计**: 3-4天

---

### 2.3 🟢 轻微问题（代码质量）

#### 问题 7: 硬编码 API Key 和配置
**影响文件**: `spatial_engine.py`  
**问题描述**:
```python
# 当前写法（不安全）
self.amap_key = "YOUR_AMAP_API_KEY"
self.tianditu_key = "YOUR_TIANDITU_KEY"

# 正确写法
from client.src.business.nanochat_config import config
self.amap_key = config.api_keys.amap
```

**修复优先级**: P2  
**工作量估计**: 1小时

---

#### 问题 8: 缺少单元测试
**影响范围**: 整个 EIA 模块  
**问题描述**:
- `tests/` 目录中无 EIA 相关测试
- 核心计算逻辑缺乏验证

**建议方案**:
```
tests/
├── test_eia_process/
│   ├── test_eia_process_manager.py
│   ├── test_eia_analyst.py
│   └── test_process_parser.py
├── test_eia_system/
│   ├── test_workbench.py
│   ├── test_source_calculator.py
│   └── test_compliance_checker.py
└── test_ei_agent/
    └── test_ei_agent_adapter.py
```

**修复优先级**: P2  
**工作量估计**: 2-3天（编写核心测试用例）

---

## 三、改造升级方案

### 3.1 架构优化方案（推荐）

#### 方案: 分层解耦 + 接口标准化

```
目标架构图
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ EIWizard     │  │ EIAPanel     │  │ EIAReportView│   │
│  │ (6-step UI)  │  │ (流程监控)    │  │ (报告预览)    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ EIAgentAdapter (Agent编排集成)                      │   │
│  │  - FusionRAG知识检索                                 │   │
│  │  - TrainingAgent专家训练                             │   │
│  │  - 任务分发与结果聚合                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ EIAProcess   │  │ EIASystem    │  │ EIAAnalytics │   │
│  │ Manager      │  │ Workbench    │  │ Engine       │   │
│  │ (编排)        │  │ (工作流)      │  │ (分析)        │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Compliance   │  │ Risk         │  │ Spatial      │   │
│  │ Checker      │  │ Management   │  │ Intelligence │   │
│  │ (合规)        │  │ (风险)        │  │ (空间)        │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Model & Data Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ AERMOD      │  │ CALPUFF      │  │ Mike21       │   │
│  │ (大气)       │  │ (大气)        │  │ (水动力)      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ CadnaA      │  │ SRTM         │  │ GB Standards │   │
│  │ (噪声)       │  │ (高程)        │  │ (国标库)      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.2 关键技术升级点

#### 升级 1: 模型集成接口标准化
**目标**: 支持真实扩散模型调用，同时保留简化模型用于快速预估

**实现方案**:
```python
# client/src/business/eia_system/models/model_factory.py
class ModelFactory:
    """模型工厂 - 根据精度需求选择模型"""
    
    @staticmethod
    def create_air_dispersion_model(model_type: str = "simplified"):
        if model_type == "aermod":
            return AERMODModel()
        elif model_type == "calpuff":
            return CALPUFFModel()
        elif model_type == "simplified":
            return SimplifiedGaussianModel()
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    @staticmethod
    def create_water_model(model_type: str = "simplified"):
        if model_type == "mike21":
            return Mike21Model()
        elif model_type == "simplified":
            return SimplifiedWaterModel()
        else:
            raise ValueError(f"Unknown model type: {model_type}")
```

---

#### 升级 2: Word 模板学习引擎
**目标**: 从现有环评报告自动学习格式，生成模板定义

**实现方案**:
```python
# client/src/business/eia_system/template/template_learner.py
class DocxTemplateLearner:
    """Word 模板学习器"""
    
    def __init__(self):
        self.styles = {}
        self.structure = []
        self.tables = []
    
    def learn_from_docx(self, docx_path: str) -> dict:
        """
        从 Word 文件学习模板
        
        返回:
        {
            "metadata": {...},
            "styles": {...},
            "structure": [...],
            "fields": [...]
        }
        """
        # 1. 使用 python-docx 解析
        from docx import Document
        doc = Document(docx_path)
        
        # 2. 提取样式
        self._extract_styles(doc)
        
        # 3. 识别章节结构
        self._identify_structure(doc)
        
        # 4. 提取表格模板
        self._extract_tables(doc)
        
        # 5. 生成 Template JSON
        return self._generate_template()
    
    def _extract_styles(self, doc):
        """提取段落样式"""
        for para in doc.paragraphs:
            if para.style.name not in self.styles:
                self.styles[para.style.name] = {
                    "font": para.style.font.name,
                    "size": para.style.font.size,
                    "bold": para.style.font.bold,
                    "alignment": para.alignment
                }
    
    def _identify_structure(self, doc):
        """识别文档结构（标题层级）"""
        for para in doc.paragraphs:
            if para.style.name.startswith("Heading"):
                level = int(para.style.name[-1])
                self.structure.append({
                    "level": level,
                    "text": para.text,
                    "style": para.style.name
                })
```

---

#### 升级 3: 风险评估引擎增强
**目标**: 集成预测性风险分析，支持蒙特卡洛模拟

**实现方案**:
```python
# client/src/business/eia_system/risk/advanced_risk_engine.py
import numpy as np
from scipy.stats import norm, lognorm

class AdvancedRiskEngine:
    """增强型风险评估引擎"""
    
    def __init__(self):
        self.uncertainty_params = {}
        self.monte_carlo_results = None
    
    def monte_carlo_simulation(self, n_simulations: int = 10000):
        """
        蒙特卡洛模拟 - 评估污染物浓度不确定性
        """
        results = []
        
        for _ in range(n_simulations):
            # 1. 采样输入参数（考虑不确定性）
            emission_rate = self._sample_emission_rate()
            wind_speed = self._sample_wind_speed()
            stability = self._sample_atmospheric_stability()
            
            # 2. 运行扩散模型
            concentration = self._run_dispersion_model(
                emission_rate, wind_speed, stability
            )
            
            # 3. 记录结果
            results.append(concentration)
        
        # 4. 统计分析
        self.monte_carlo_results = {
            "mean": np.mean(results),
            "std": np.std(results),
            "p95": np.percentile(results, 95),
            "p99": np.percentile(results, 99),
            "exceedance_probability": self._calculate_exceedance(results)
        }
        
        return self.monte_carlo_results
    
    def _calculate_exceedance(self, concentrations: list, threshold: float = 1.0):
        """计算超标概率"""
        exceedances = [c for c in concentrations if c > threshold]
        return len(exceedances) / len(concentrations)
```

---

#### 升级 4: 合规检查规则库扩展
**目标**: 建立完整的 GB 标准规则库，支持自动更新

**实现方案**:
```python
# client/src/business/eia_system/compliance/rule_repository.py
class ComplianceRuleRepository:
    """合规规则库 - 支持 GB 标准自动更新"""
    
    def __init__(self):
        self.rules = {}
        self._load_builtin_rules()
    
    def _load_builtin_rules(self):
        """加载内置 GB 标准规则"""
        # 大气污染物综合排放标准 (GB 16297-1996)
        self.rules["GB16297-1996"] = {
            "name": "大气污染物综合排放标准",
            "pollutants": {
                "SO2": {"day": 0.40, "night": 0.20, "unit": "mg/m³"},
                "NOx": {"day": 0.24, "night": 0.12, "unit": "mg/m³"},
                "PM10": {"day": 0.45, "night": 0.15, "unit": "mg/m³"}
            }
        }
        
        # 污水综合排放标准 (GB 8978-1996)
        self.rules["GB8978-1996"] = {
            "name": "污水综合排放标准",
            "pollutants": {
                "COD": {"primary": 100, "secondary": 150, "unit": "mg/L"},
                "BOD5": {"primary": 30, "secondary": 60, "unit": "mg/L"},
                "NH3-N": {"primary": 15, "secondary": 25, "unit": "mg/L"}
            }
        }
        
        # 工业企业厂界环境噪声排放标准 (GB 12348-2008)
        self.rules["GB12348-2008"] = {
            "name": "工业企业厂界环境噪声排放标准",
            "daytime": {"Class I": 55, "Class II": 60, "Class III": 65, "Class IV": 70},
            "nighttime": {"Class I": 45, "Class II": 50, "Class III": 55, "Class IV": 55},
            "unit": "dB(A)"
        }
    
    def fetch_latest_standards(self):
        """
        从生态环境部官网获取最新标准
        
        注意: 需要实现网页爬虫或 API 接口
        """
        # TODO: 实现标准自动更新
        pass
    
    def check_compliance(self, pollutant: str, concentration: float, standard: str):
        """检查合规性"""
        if standard not in self.rules:
            raise ValueError(f"Unknown standard: {standard}")
        
        rule = self.rules[standard]
        
        if pollutant in rule["pollutants"]:
            limit = rule["pollutants"][pollutant]["day"]  # 默认日间标准
            compliant = concentration <= limit
            
            return {
                "compliant": compliant,
                "concentration": concentration,
                "limit": limit,
                "unit": rule["pollutants"][pollutant]["unit"],
                "exceedance": max(0, concentration - limit)
            }
        
        return None
```

---

## 四、待办任务清单（Prioritized TODO List）

### P0 - 紧急修复（本周完成）

- [ ] **TODO 1**: 修复导入路径不一致问题  
  **文件**: `eia_process_manager.py` 及关联文件  
  **工作量**: 2-3小时  
  **负责人**: @dev-team  
  **验收标准**: 所有导入路径使用 `client.src.business.` 前缀

- [ ] **TODO 2**: 迁移 `eia_process_panel.py` 到正确目录  
  **文件**: `presentation_backup_20260426/panels/eia_process_panel.py` → `client/src/presentation/panels/`  
  **工作量**: 1小时  
  **负责人**: @dev-team  
  **验收标准**: UI 面板正常显示，无导入错误

---

### P1 - 重要功能（2周内完成）

- [ ] **TODO 3**: 完善 EIAgentAdapter 核心功能  
  **文件**: `ei_agent_adapter.py`  
  **子任务**:
    - [ ] 实现 `_generate_report()` 方法
    - [ ] 实现 `_parse_attachments()` 方法
    - [ ] 打通 `_assess_risks()` 调用链路
    - [ ] 集成 ExpertTrainingWidget
    - [ ] 集成 ComplianceCheckWidget
  **工作量**: 3-4天  
  **负责人**: @dev-team  
  **验收标准**: 能通过 EIAgentAdapter 完成完整报告生成流程

- [ ] **TODO 4**: 实现 Word 模板学习引擎  
  **文件**: 新建 `client/src/business/eia_system/template/template_learner.py`  
  **工作量**: 2-3天  
  **负责人**: @dev-team  
  **验收标准**: 能从现有 `.docx` 报告自动学习格式并生成 Template JSON

- [ ] **TODO 5**: 扩展合规检查规则库  
  **文件**: `compliance_checker.py`  
  **子任务**:
    - [ ] 添加更多 GB 标准（GB 3095, GB 3838, GB 14554 等）
    - [ ] 实现标准自动更新机制
    - [ ] 添加行业专项标准（火电、化工、钢铁等）
  **工作量**: 2天  
  **负责人**: @dev-team  
  **验收标准**: 支持至少 10 个常用 GB 标准的合规检查

---

### P2 - 功能增强（1个月内完成）

- [ ] **TODO 6**: 集成真实扩散模型（AERMOD/CALPUFF）  
  **文件**: 新建 `client/src/business/eia_system/models/`  
  **子任务**:
    - [ ] 创建模型接口抽象层
    - [ ] 实现 AERMOD 模型调用接口
    - [ ] 实现 CALPUFF 模型调用接口
    - [ ] 编写模型输入输出适配器
  **工作量**: 3-5天  
  **负责人**: @dev-team @modeling-expert  
  **验收标准**: 能调用真实 AERMOD 可执行文件进行计算

- [ ] **TODO 7**: 实现 3D 时空模拟可视化  
  **文件**: `eia_40.py`  
  **子任务**:
    - [ ] 集成 PyQtGraph 3D 绘图
    - [ ] 实现污染物扩散动画
    - [ ] 添加地形叠加显示
  **工作量**: 3天  
  **负责人**: @dev-team  
  **验收标准**: 能在 UI 中显示 3D 污染物扩散过程

- [ ] **TODO 8**: 添加 SRTM 高程数据接口  
  **文件**: `spatial_engine.py`  
  **工作量**: 1-2天  
  **负责人**: @dev-team  
  **验收标准**: 能自动获取项目区域高程数据并用于地形分析

- [ ] **TODO 9**: 编写单元测试  
  **文件**: `tests/test_eia_*.py`  
  **工作量**: 2-3天  
  **负责人**: @dev-team @qa-team  
  **验收标准**: 核心模块测试覆盖率 > 70%

---

### P3 - 长期优化（3个月内完成）

- [ ] **TODO 10**: 优化计算性能（并行计算 + GPU 加速）  
  **工作量**: 5天  
  **负责人**: @dev-team @hpc-expert

- [ ] **TODO 11**: 添加报告质量自动评估模块  
  **工作量**: 3天  
  **负责人**: @dev-team

- [ ] **TODO 12**: 实现多语言支持（英文报告生成）  
  **工作量**: 2天  
  **负责人**: @dev-team

- [ ] **TODO 13**: 创建 EIA 模块使用文档和教程  
  **工作量**: 2天  
  **负责人**: @dev-team @docs-team

---

## 五、实施路线图

### Phase 1: 紧急修复（Week 1）
```
Day 1-2: TODO 1 (导入路径修复)
Day 3:   TODO 2 (UI 面板迁移)
Day 4-5: 测试验证 + 提交
```

### Phase 2: 核心功能完善（Week 2-3）
```
Week 2: TODO 3 (EIAgentAdapter 完善)
Week 3: TODO 4 (Word 模板学习) + TODO 5 (合规规则扩展)
```

### Phase 3: 功能增强（Week 4-6）
```
Week 4-5: TODO 6 (真实模型集成)
Week 6:   TODO 7 (3D 可视化) + TODO 8 (高程数据)
```

### Phase 4: 测试与优化（Week 7-8）
```
Week 7: TODO 9 (单元测试) + 性能测试
Week 8: TODO 10 (性能优化) + 文档编写 (TODO 13)
```

---

## 六、风险评估

| 风险项 | 概率 | 影响 | 缓解措施 |
|--------|------|------|----------|
| AERMOD 模型集成难度大 | 高 | 高 | 先完成接口定义，模型调用可延后 |
| Word 模板学习精度不足 | 中 | 中 | 提供手动编辑模板的兜底方案 |
| 合规规则库不完整 | 高 | 中 | 提供规则自定义界面，用户可补充 |
| 性能不满足大数据量需求 | 中 | 高 | 采用分块计算 + 异步任务队列 |
| 3D 可视化性能问题 | 中 | 中 | 提供 2D 备选方案 |

---

## 七、总结与建议

### 7.1 核心问题总结
1. **架构层面**: 模块分散，导入路径不一致，需统一规范
2. **功能层面**: 核心计算依赖简化模型，真实模型集成缺失
3. **数据层面**: 合规规则库不完整，模板学习能力缺失
4. **测试层面**: 无单元测试，质量保障不足

### 7.2 改造原则
1. **优先修复 P0 问题**，确保代码可运行
2. **分阶段实施**，每个 Phase 可独立交付
3. **保留简化模型**，作为快速预估的备选方案
4. **建立测试体系**，确保重构不破坏现有功能

### 7.3 预期成果
完成改造后，EIA 模块将具备：
- ✅ 完整的端到端报告生成能力
- ✅ 支持真实扩散模型计算
- ✅ 自动从 Word 报告学习模板
- ✅ 全面的 GB 标准合规检查
- ✅ 3D 时空模拟可视化
- ✅ 完善的测试覆盖率

---

**文档状态**: 草稿  
**下次评审日期**: 2026-05-04  
**联系人**: @dev-team @project-manager
