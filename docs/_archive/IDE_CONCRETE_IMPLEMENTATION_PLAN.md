# LivingTreeAI IDE 模块具体实施方案

## 一、目标定位

**愿景**：从"辅助工具"进化为"AI原生工程体"——用户描述需求，AI完成从设计到部署的全过程。

**当前基线**：综合匹配度约 **42%**。基础架构已搭建，但距离"零代码编程"愿景仍有较大差距。

---

## 二、实施路线图

```
阶段1（1-2周）：基础增强 ── 缩小高优先级差距
阶段2（1个月）  ：核心功能 ── 构建完整能力
阶段3（2-3个月）：高级特性 ── 差异化竞争
```

---

## 三、阶段1：基础增强（1-2周）

### 1.1 强化 IntentEngine（现有90% → 95%）

**目标**：将意图理解从"规则匹配"升级为"语义理解"。

**具体任务**：

| 任务 | 现状 | 改进方案 | 优先级 |
|------|------|----------|--------|
| LLM意图增强 | `use_llm_enhancement=True` 但未实现 | 实现LLM fallback，当规则置信度<0.6时调用LLM | 🔴 |
| 意图学习闭环 | 无反馈机制 | 接入SelfEvolution的意图预测，更新规则权重 | 🟡 |
| 中文语义优化 | 依赖正则，中文理解弱 | 增加中文意图关键词库（200+） | 🟡 |

**代码示例**：

```python
# intent_engine.py 第42行修改
def parse(self, query: str) -> Intent:
    # 1. 规则快速通道
    intent = self.parser.parse(query)
    
    # 2. LLM 增强（新增）
    if intent.confidence < 0.6 and self.use_llm_enhancement:
        intent = self._enhance_with_llm(query, intent)
    
    # 3. 技术栈检测
    tech_stack, tech_confidence = self.tech_detector.detect(query)
    ...
```

**文件**：`core/intent_engine/intent_engine.py`

---

### 1.2 代码补全增强（现有50% → 65%）

**目标**：从"前缀匹配"升级为"上下文感知补全"。

**具体任务**：

| 任务 | 现状 | 改进方案 | 优先级 |
|------|------|----------|--------|
| 项目上下文补全 | 仅当前文件变量 | 扫描项目所有文件，建立符号索引 | 🔴 |
| 测试代码生成 | 无 | 接入Agent生成测试用例 | 🟡 |
| Snippet扩展 | Python/JS各10个 | 扩展到30+模板（FastAPI/React/Vue等） | 🟡 |

**代码示例**：

```python
# ide_enhancer.py 新增 ProjectContextCompleter
class ProjectContextCompleter:
    """基于项目上下文的智能补全"""
    
    def __init__(self, project_root: str):
        self.symbol_index = {}  # {symbol_name: [(file, line, type)]}
        self._build_index(project_root)
    
    def _build_index(self, project_root: str):
        """扫描项目建立符号索引"""
        for root, _, files in os.walk(project_root):
            for f in files:
                if f.endswith(('.py', '.js', '.ts')):
                    self._index_file(os.path.join(root, f))
    
    def _index_file(self, filepath: str):
        """索引单个文件中的符号"""
        # 使用正则提取 def/class/const/function 等
        # 存入 symbol_index
    
    def complete(self, prefix: str, context: str) -> List[Completion]:
        """上下文感知补全"""
        results = []
        for name, locations in self.symbol_index.items():
            if name.startswith(prefix):
                # 去重，选最高分的
                results.append(Completion(...))
        return sorted(results, key=lambda x: x.score, reverse=True)[:15]
```

**文件**：`core/ide_enhancer.py`

---

### 1.3 GitHub 集成增强（现有80% → 90%）

**目标**：从"项目管理"扩展为"代码模式学习"。

**具体任务**：

| 任务 | 现状 | 改进方案 | 优先级 |
|------|------|----------|--------|
| 克隆代码模式学习 | 无 | 克隆后自动索引代码模式存入KnowledgeGraph | 🔴 |
| 最佳实践库 | 无 | 基于GitHub trending生成最佳实践知识库 | 🟡 |

---

## 四、阶段2：核心功能（1个月）

### 2.1 全栈生成引擎（最关键 🔴🔴🔴）

**目标**：用户说"做一个博客系统"，AI自动生成完整项目。

**架构设计**：

```
用户输入: "做一个博客系统"
     ↓
IntentEngine: 识别为 CODE_GENERATION + 目标="博客系统"
     ↓
IdeaClarifier: 确认技术栈、功能范围
     ↓
┌─────────────────────────────────────────────┐
│ 全栈生成协调器 (FullStackGenerator)          │
├─────────────────────────────────────────────┤
│ ├─ FrontendAgent: 生成 React/Vue 组件        │
│ ├─ BackendAgent: 生成 FastAPI/Django 接口    │
│ ├─ DatabaseAgent: 生成 数据库模型+迁移脚本    │
│ └─ DevOpsAgent: 生成 Dockerfile/CI配置       │
└─────────────────────────────────────────────┘
     ↓
ProjectManager: 整合为完整项目
     ↓
SmartIDEPanel: 预览→用户确认→应用
```

**核心文件**：

```
core/full_stack_generator/
├── __init__.py
├── generator_coordinator.py     # 协调器
├── frontend_agent.py           # 前端智能体
├── backend_agent.py           # 后端智能体
├── database_agent.py          # 数据库智能体
├── devops_agent.py            # DevOps智能体
└── template_registry.py       # 模板注册表
```

**核心代码框架**：

```python
# core/full_stack_generator/generator_coordinator.py
class FullStackGenerator:
    """
    全栈生成协调器
    
    输入: 用户意图 (Intent)
    输出: 完整项目文件结构
    """
    
    def __init__(self, agent: HermesAgent):
        self.agent = agent
        self.frontend = FrontendAgent(agent)
        self.backend = BackendAgent(agent)
        self.database = DatabaseAgent(agent)
        self.devops = DevOpsAgent(agent)
    
    async def generate(self, intent: Intent) -> Dict[str, str]:
        """
        生成完整项目
        
        Example:
            intent = IntentEngine().parse("做一个博客系统，用FastAPI+Vue")
            project = await generator.generate(intent)
            # project = {"main.py": "...", "App.vue": "...", ...}
        """
        project = {}
        
        # 1. 分解任务
        subtasks = self._decompose_intent(intent)
        
        # 2. 并行生成各层
        results = await asyncio.gather(
            self.frontend.generate(intent),
            self.backend.generate(intent),
            self.database.generate(intent),
            self.devops.generate(intent),
        )
        
        # 3. 合并结果
        for layer_result in results:
            project.update(layer_result)
        
        return project
    
    def _decompose_intent(self, intent: Intent) -> List[Dict]:
        """将意图分解为各层子任务"""
        # 根据技术栈推断需要的层次
        tech_stack = intent.tech_stack
        layers = ["backend"]  # 基础
        if any(t in tech_stack for t in ["vue", "react", "nextjs"]):
            layers.append("frontend")
        if any(t in tech_stack for t in ["postgresql", "mysql", "mongodb"]):
            layers.append("database")
        if "docker" in tech_stack:
            layers.append("devops")
        return layers
```

**前端智能体示例**：

```python
# core/full_stack_generator/frontend_agent.py
class FrontendAgent:
    """前端生成智能体"""
    
    PROMPT_TEMPLATE = """
你是一个专业的前端工程师。请根据以下需求生成 {framework} 代码：

需求：{intent.target}
技术栈：{tech_stack}
约束：{constraints}

要求：
1. 生成完整的组件代码（不是片段）
2. 包含必要的样式
3. 响应式设计
4. 包含必要的错误处理

请生成以下文件：
1. 主组件 ({target}.{ext})
2. API 调用模块 (api.js)
3. 类型定义（如需要）(types.{ext})
"""
    
    async def generate(self, intent: Intent) -> Dict[str, str]:
        framework = self._detect_framework(intent.tech_stack)
        prompt = self.PROMPT_TEMPLATE.format(
            framework=framework,
            intent=intent.target,
            tech_stack=", ".join(intent.tech_stack),
            constraints=", ".join(str(c.value) for c in intent.constraints)
        )
        
        # 调用LLM生成
        response = ""
        async for chunk in self.agent._llm_chat([ChatMessage(role="user", content=prompt)]):
            if chunk.delta:
                response += chunk.delta
        
        return self._parse_to_files(response, framework)
```

---

### 2.2 架构规划引擎（现有60% → 80%）

**目标**：将IdeaClarifier从"问答流程"升级为"自动架构设计"。

**改进方案**：

| 改进点 | 现状 | 改进方案 |
|--------|------|----------|
| 架构模式推荐 | 手动问答 | 基于技术栈自动推荐架构模式（MVVM/MVC/微服务等） |
| 架构图生成 | 无 | 自动生成架构图（Mermaid格式） |
| 依赖关系设计 | 无 | 自动分析并设计模块依赖 |

**新增文件**：`core/architecture_planner.py`

```python
class ArchitecturePlanner:
    """架构规划引擎"""
    
    ARCHITECTURE_PATTERNS = {
        ("fastapi", "react"): "前后端分离 + REST API",
        ("django", "vue"): "Django MTV + Vue SPA",
        ("fastapi", "vue"): "前后端分离 + BFF",
        ("flask", "react"): "前后端分离 + Redux",
    }
    
    def plan(self, intent: Intent) -> ArchitecturePlan:
        """生成架构规划"""
        # 1. 匹配架构模式
        pattern = self._match_pattern(intent.tech_stack)
        
        # 2. 生成模块划分
        modules = self._generate_modules(intent)
        
        # 3. 生成架构图
        diagram = self._generate_mermaid_diagram(pattern, modules)
        
        return ArchitecturePlan(
            pattern=pattern,
            modules=modules,
            diagram=diagram,
            confidence=0.85
        )
```

---

### 2.3 应用级部署系统（现有30% → 60%）

**目标**：从"模型部署"扩展到"应用全生命周期管理"。

**具体任务**：

| 任务 | 现状 | 改进方案 | 优先级 |
|------|------|----------|--------|
| 云服务API集成 | DeploymentEngine仅服务模型 | 新增CloudDeployAgent | 🔴 |
| 容器化模板 | 无 | 接入项目模板生成Dockerfile/docker-compose | 🟡 |
| 域名/SSL配置 | 无 | 集成Let's Encrypt | 🟢 |

---

## 五、阶段3：高级特性（2-3个月）

### 3.1 自适应架构进化（现有30% → 70%）

**目标**：AI主动监控代码质量并提出优化建议。

**架构**：

```
PerformanceSensor ──┐
CodeSmellSensor ────┼──→ SignalAggregator ──→ ProposalGenerator ──→ 用户审批
ResourceMonitor ────┤                         ↓
ErrorPatternSensor ──┘                    SandboxExecutor
                                          ↓
                                    Git Branch (测试)
                                          ↓
                                    自动合并/回滚
```

**新增文件**：

```
core/evolution_engine/
├── sensors/
│   ├── performance_sensor.py
│   ├── code_smell_sensor.py
│   └── error_pattern_sensor.py
├── aggregator.py
├── proposal_generator.py
├── executor.py
└── evolution_dashboard.py  # UI集成
```

**核心代码**：

```python
# core/evolution_engine/proposal_generator.py
@dataclass
class EvolutionProposal:
    """进化提案"""
    proposal_id: str
    title: str
    trigger_signals: List[Signal]
    expected_benefits: Dict[str, float]  # {"性能提升": 0.3, "代码质量": 0.2}
    implementation_steps: List[str]
    risk_level: str  # LOW / MEDIUM / HIGH
    auto_executable: bool
    estimated_hours: float

class ProposalGenerator:
    """提案生成器"""
    
    def generate(self, signals: List[Signal]) -> List[EvolutionProposal]:
        proposals = []
        
        # 按信号类型匹配提案模板
        for signal in signals:
            if signal.type == "performance_degradation":
                proposals.append(self._propose_performance_fix(signal))
            elif signal.type == "code_smell":
                proposals.append(self._propose_refactor(signal))
            elif signal.type == "repeated_error":
                proposals.append(self._propose_error_handling(signal))
        
        return sorted(proposals, key=lambda p: sum(p.expected_benefits.values()), reverse=True)
    
    def _propose_performance_fix(self, signal: Signal) -> EvolutionProposal:
        """性能优化提案"""
        return EvolutionProposal(
            proposal_id=f"PERF-{int(time.time())}",
            title=f"优化 {signal.target} 性能",
            trigger_signals=[signal],
            expected_benefits={
                "响应时间": signal.impact_score * 0.6,
                "吞吐量": signal.impact_score * 0.4
            },
            implementation_steps=[
                "1. 性能瓶颈定位（自动）",
                "2. 添加缓存层（需审批）",
                "3. 性能验证测试（自动）"
            ],
            risk_level="MEDIUM" if signal.impact_score > 0.5 else "LOW",
            auto_executable=signal.impact_score <= 0.3,
            estimated_hours=2.0
        )
```

---

### 3.2 预测性开发（新增功能）

**目标**：基于趋势分析预判开发需求。

**功能设计**：

| 功能 | 说明 |
|------|------|
| 代码趋势分析 | 分析项目代码变化趋势，预测可能的瓶颈 |
| 需求预判 | 基于用户历史习惯，提前准备可能的代码模板 |
| 技术债预警 | 自动检测累积的技术债并提醒 |

---

### 3.3 无感技术栈迁移（新增功能）

**目标**：自动化技术栈升级（如Python 2→3，Vue 2→3）。

**功能设计**：

| 功能 | 说明 |
|------|------|
| 技术栈检测 | 自动检测项目使用的框架版本 |
| 迁移路径规划 | 生成迁移步骤和风险评估 |
| 自动化迁移 | 执行安全的自动迁移（有限场景） |

---

## 六、UI集成方案

### 6.1 Evolution Panel（进化面板）

**文件**：`ui/evolution_panel.py`

```python
class EvolutionPanel(QWidget):
    """进化引擎控制面板"""
    
    def __init__(self, engine: ProposalGenerator):
        self.engine = engine
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 信号监控
        self.signal_monitor = QTableWidget()
        self.signal_monitor.setHeaders(["信号", "类型", "强度", "时间"])
        
        # 提案列表
        self.proposal_list = QListWidget()
        self.proposal_list.itemClicked.connect(self._show_proposal_detail)
        
        # 提案详情
        self.proposal_detail = QTextEdit(readOnly=True)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.approve_btn = QPushButton("✅ 执行提案")
        self.reject_btn = QPushButton("❌ 拒绝提案")
        self.auto_toggle = QCheckBox("🤖 自动执行低风险提案")
```

### 6.2 FullStackGenerator 面板集成

**在SmartIDEPanel中新增按钮**：

```python
# ui/smart_ide_panel.py
class SmartIDEPanel:
    def _setup_ui(self):
        # ... 现有代码 ...
        
        # 新增：全栈生成工具栏
        fullstack_toolbar = QFrame()
        fullstack_layout = QHBoxLayout(fullstack_toolbar)
        
        generate_project_btn = QPushButton("🚀 生成完整项目")
        generate_project_btn.clicked.connect(self._on_generate_project)
        
        # 新增：进化引擎状态
        evolution_status = QLabel("🧬 进化引擎: 监控中")
        evolution_btn = QPushButton("📊 查看提案")
        evolution_btn.clicked.connect(self._show_evolution_panel)
```

---

## 七、文件变更清单

### 新增文件

| 文件路径 | 说明 | 优先级 |
|----------|------|--------|
| `core/full_stack_generator/__init__.py` | 全栈生成器 | 🔴🔴🔴 |
| `core/full_stack_generator/generator_coordinator.py` | 生成协调器 | 🔴🔴🔴 |
| `core/full_stack_generator/frontend_agent.py` | 前端智能体 | 🔴🔴 |
| `core/full_stack_generator/backend_agent.py` | 后端智能体 | 🔴🔴 |
| `core/full_stack_generator/database_agent.py` | 数据库智能体 | 🟡 |
| `core/full_stack_generator/devops_agent.py` | DevOps智能体 | 🟡 |
| `core/architecture_planner.py` | 架构规划引擎 | 🔴 |
| `core/evolution_engine/__init__.py` | 进化引擎 | 🟡 |
| `core/evolution_engine/sensors/__init__.py` | 传感器层 | 🟢 |
| `core/evolution_engine/sensors/performance_sensor.py` | 性能传感器 | 🟢 |
| `core/evolution_engine/sensors/code_smell_sensor.py` | 代码异味传感器 | 🟢 |
| `core/evolution_engine/aggregator.py` | 信号聚合器 | 🟢 |
| `core/evolution_engine/proposal_generator.py` | 提案生成器 | 🟢 |
| `core/evolution_engine/executor.py` | 执行引擎 | 🟢 |
| `ui/evolution_panel.py` | 进化面板UI | 🟢 |

### 修改文件

| 文件路径 | 修改内容 | 优先级 |
|----------|----------|--------|
| `core/ide_enhancer.py` | 新增ProjectContextCompleter | 🔴 |
| `core/intent_engine/intent_engine.py` | 实现LLM意图增强 | 🔴 |
| `ui/smart_ide_panel.py` | 集成全栈生成按钮 | 🔴 |
| `core/github_project_manager.py` | 克隆后自动学习代码模式 | 🟡 |
| `core/agent.py` | 注册全栈生成工具 | 🟡 |

---

## 八、里程碑计划

| 周次 | 目标 | 交付物 |
|------|------|---------|
| 第1周 | IntentEngine LLM增强 + ProjectContextCompleter | `core/intent_engine/intent_engine.py` + `core/ide_enhancer.py` 增强版 |
| 第2周 | FullStackGenerator基础架构 | `core/full_stack_generator/` 基础框架 + 演示 |
| 第3周 | 前后端智能体 + UI集成 | FrontendAgent + BackendAgent + SmartIDEPanel集成 |
| 第4周 | 架构规划引擎 | `core/architecture_planner.py` + 架构图生成 |
| 第5-8周 | 进化引擎Phase1 | PerformanceSensor + ProposalGenerator |
| 第9-12周 | 应用级部署 + 云服务集成 | CloudDeployAgent + 容器化模板 |

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM生成代码质量不稳定 | 高 | 限制生成范围，提供用户审批环节 |
| 多智能体并行生成冲突 | 中 | 使用VFS隔离，每个智能体独立目录 |
| 大型项目生成超时 | 中 | 分步骤生成，支持断点续传 |
| 进化引擎误判 | 低 | HIGH风险提案强制用户审批 |

---

## 十、测试计划

| 测试场景 | 验收标准 |
|----------|----------|
| "做一个Todo应用" | 5分钟内生成可运行前后端完整项目 |
| "优化API响应时间" | 进化引擎检测到慢API并生成提案 |
| IntentEngine LLM fallback | 规则置信度<0.6时正确调用LLM |
| 架构图生成 | Mermaid格式架构图正确渲染 |
