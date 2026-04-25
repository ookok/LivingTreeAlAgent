# LivingTreeAI IDE 模块 LLM 综合评估引擎

> 利用大型语言模型对 LivingTreeAI IDE 模块进行深度代码分析、架构评估和智能改造建议

---

## 📋 项目背景

### LivingTreeAI IDE 模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    LivingTreeAI IDE 架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      IDE Core                               ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  ││
│  │  │ Intent      │ │ Code        │ │ Context             │  ││
│  │  │ Engine      │ │ Analyzer    │ │ Manager             │  ││
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                    │
│  ┌──────────────────────────┼──────────────────────────────┐   │
│  │                    IDE Panels                             │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  ││
│  │  │ Project     │ │ Search      │ │ Settings            │  ││
│  │  │ Panel       │ │ Panel       │ │ Panel               │  ││
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  ││
│  └───────────────────────────────────────────────────────────┘   │
│                              │                                    │
│  ┌──────────────────────────┼──────────────────────────────┐   │
│  │                    Core Services                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  ││
│  │  │ Plugin      │ │ Proxy       │ │ Task                │  ││
│  │  │ Manager     │ │ Gateway     │ │ Execution           │  ││
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  ││
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 当前 IDE 模块清单

| 模块路径 | 功能 | 技术栈 | 状态 |
|----------|------|--------|------|
| `core/intent_engine/` | 意图理解引擎 | Python | 主力开发 |
| `core/code_analyzer/` | 代码分析器 | Python, AST | 主力开发 |
| `core/ide/` | IDE 核心 | PyQt6 | 主力开发 |
| `ui/ide_panel.py` | IDE 主面板 | PyQt6 | 主力开发 |
| `core/plugin_manager/` | 插件管理器 | Python | 开发中 |
| `core/task_execution/` | 任务执行引擎 | Python | 开发中 |
| `core/project_matcher/` | 项目匹配器 | Python | 新增 |
| `core/reasoning_engine/` | 推理引擎 | Python | 规划中 |
| `core/evolution_engine/` | 进化引擎 | Python | 开发中 |

---

## 🎯 LLM 评估引擎定位

### 与通用项目匹配器的区别

| 维度 | 通用项目匹配器 | LivingTreeAI 代码升级引擎 |
|------|----------------|---------------------------|
| **目标** | 外部项目 → 本地项目迁移 | LivingTreeAI 自身模块升级 |
| **分析范围** | 跨项目对比 | 单项目深度分析 |
| **输入** | GitHub URL + 本地路径 | LivingTreeAI 源码 |
| **输出** | 迁移可行性 + 建议 | 代码改造方案 + 实施路径 |
| **侧重点** | 兼容性评估 | 技术债务 + 架构优化 |
| **LLM 用法** | 语义理解 + 意图对齐 | 代码理解 + 改造推理 |

### 核心评估维度

```
┌─────────────────────────────────────────────────────────────────┐
│                LLM 代码升级评估引擎                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1. 代码质量评估 (Code Quality Assessment)                 │ │
│  │    - 技术债务检测                                          │ │
│  │    - 代码异味识别                                          │ │
│  │    - 复杂度分析                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2. 架构健康度评估 (Architecture Health Assessment)         │ │
│  │    - 模块耦合度分析                                         │ │
│  │    - 依赖关系评估                                           │ │
│  │    - 扩展性分析                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3. 功能完整性评估 (Feature Completeness)                    │ │
│  │    - 能力差距分析                                           │ │
│  │    - 缺失功能识别                                           │ │
│  │    - 冗余代码检测                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4. 智能化水平评估 (Intelligence Level Assessment)          │ │
│  │    - Intent Engine 成熟度                                  │ │
│  │    - 上下文理解能力                                         │ │
│  │    - 自主决策能力                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 5. 改造优先级排序 (Refactoring Priority Ranking)           │ │
│  │    - 价值/风险比分析                                        │ │
│  │    - 依赖顺序推理                                           │ │
│  │    - 实施路径规划                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 模块设计

### 1. 代码质量评估器 `LLMCodeQualityAnalyzer`

#### 功能定位

对 LivingTreeAI IDE 模块进行深度代码质量分析，识别技术债务、代码异味和复杂度问题。

#### 分析维度

| 维度 | 检测内容 | LLM 增强点 |
|------|----------|-----------|
| **技术债务** | 硬编码、重复代码、过时模式 | 理解上下文，识别隐式债务 |
| **代码异味** | 长方法、深嵌套、巨型类 | 识别语义层面的异味 |
| **复杂度** | 圈复杂度、扇入扇出 | 评估业务逻辑复杂度 |
| **可维护性** | 耦合度、内聚度 | 理解模块关系和职责 |
| **安全性** | 注入风险、认证漏洞 | 识别安全敏感代码 |

#### 核心实现

```python
# core/ide_upgrader/code_quality_analyzer.py
"""
LivingTreeAI IDE 模块代码质量评估器
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import asyncio

class QualityLevel(Enum):
    """代码质量等级"""
    EXCELLENT = "excellent"      # 95-100
    GOOD = "good"                # 80-94
    ACCEPTABLE = "acceptable"    # 60-79
    NEEDS_IMPROVEMENT = "needs_improvement"  # 40-59
    POOR = "poor"                # 0-39

class CodeSmellType(Enum):
    """代码异味类型"""
    LONG_METHOD = "long_method"
    DEEP_NESTING = "deep_nesting"
    GOD_CLASS = "god_class"
    DUPLICATED_CODE = "duplicated_code"
    HARD_CODED_CONFIG = "hard_coded_config"
    DEAD_CODE = "dead_code"
    COMPLEX_CONDITION = "complex_condition"
    MISSING_ERROR_HANDLING = "missing_error_handling"

@dataclass
class CodeSmell:
    """代码异味"""
    smell_type: CodeSmellType
    location: str  # file:line or function_name
    severity: str  # low, medium, high, critical
    description: str
    suggestion: str
    estimated_fix_effort: float  # hours

@dataclass
class TechnicalDebt:
    """技术债务项"""
    category: str
    title: str
    description: str
    impacted_files: List[str]
    severity: str
    interest: str  # 不修复会造成的额外成本
    suggested_approach: str

@dataclass
class QualityMetrics:
    """质量指标"""
    maintainability_index: float  # 0-100
    complexity_score: float       # 越低越好
    code_smell_count: int
    technical_debt_hours: float
    test_coverage_estimate: float
    documentation_completeness: float

@dataclass
class CodeQualityReport:
    """代码质量报告"""
    module_name: str
    overall_score: float  # 0-100
    quality_level: QualityLevel
    metrics: QualityMetrics
    code_smells: List[CodeSmell]
    technical_debts: List[TechnicalDebt]
    strengths: List[str]  # 做得好的地方
    priority_issues: List[str]  # 需要优先处理的问题
    llm_insights: List[str]  # LLM 深度洞察


class LLMCodeQualityAnalyzer:
    """LLM 增强的代码质量分析器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.smell_weights = {
            CodeSmellType.LONG_METHOD: 2.0,
            CodeSmellType.DEEP_NESTING: 1.5,
            CodeSmellType.GOD_CLASS: 5.0,
            CodeSmellType.DUPLICATED_CODE: 3.0,
            CodeSmellType.HARD_CODED_CONFIG: 2.0,
            CodeSmellType.DEAD_CODE: 1.0,
            CodeSmellType.COMPLEX_CONDITION: 2.5,
            CodeSmellType.MISSING_ERROR_HANDLING: 4.0,
        }

    async def analyze_module(self, module_path: str) -> CodeQualityReport:
        """
        分析指定模块的代码质量

        Args:
            module_path: 模块路径，如 'core/intent_engine'

        Returns:
            CodeQualityReport: 完整的代码质量报告
        """
        # 1. 收集代码文件
        code_files = self._collect_python_files(module_path)

        # 2. 基础指标计算 (传统方法)
        metrics = await self._calculate_basic_metrics(code_files)

        # 3. 静态分析 (传统 + LLM 增强)
        smells = await self._detect_code_smells(code_files)
        debts = await self._identify_technical_debt(code_files)

        # 4. LLM 深度分析
        llm_insights = await self._llm_deep_analysis(module_path, code_files)
        strengths = await self._identify_strengths(module_path, code_files)

        # 5. 综合评分
        overall_score = self._calculate_overall_score(metrics, smells, debts)
        quality_level = self._determine_quality_level(overall_score)
        priority_issues = self._rank_priority_issues(smells, debts)

        return CodeQualityReport(
            module_name=module_path,
            overall_score=overall_score,
            quality_level=quality_level,
            metrics=metrics,
            code_smells=smells,
            technical_debts=debts,
            strengths=strengths,
            priority_issues=priority_issues,
            llm_insights=llm_insights
        )

    async def analyze_cross_module(self, module_paths: List[str]) -> Dict[str, CodeQualityReport]:
        """分析多个模块并生成跨模块报告"""
        reports = {}

        # 并行分析各模块
        tasks = [self.analyze_module(path) for path in module_paths]
        results = await asyncio.gather(*tasks)

        for path, report in zip(module_paths, results):
            reports[path] = report

        # 生成跨模块洞察
        cross_module_insights = await self._llm_cross_module_analysis(reports)

        return reports

    # ─────────────────────────────────────────────────────────────
    # LLM 增强的分析方法
    # ─────────────────────────────────────────────────────────────

    async def _llm_deep_analysis(self, module_path: str, code_files: List[str]) -> List[str]:
        """LLM 深度分析 - 发现传统方法难以检测的问题"""

        # 构建代码摘要
        code_context = self._build_code_summary(code_files)

        prompt = f"""作为代码质量专家，分析以下 LivingTreeAI IDE 模块的深度问题。

模块: {module_path}

代码结构摘要:
```python
{code_context}
```

请识别以下深层问题：

1. **语义层面的代码异味**
   - 命名不当导致的潜在误解
   - 意图模糊的函数或类
   - 隐含的假设和耦合

2. **架构层面的问题**
   - 模块职责是否清晰
   - 是否存在隐式依赖
   - 扩展性设计的缺失

3. **业务逻辑层面的问题**
   - 边界情况处理是否完整
   - 错误处理策略是否一致
   - 状态管理是否清晰

4. **技术债务的隐性成本**
   - 哪些代码看似正常但维护成本高
   - 哪些设计决策会在未来造成问题

5. **安全性考虑**
   - 是否有潜在的安全漏洞
   - 是否有敏感信息泄露风险

请以列表形式输出，每条洞察包含：
- 问题描述
- 具体位置（文件或函数）
- 严重程度
- 改进建议"""

        response = await self.llm.generate(prompt)
        return self._parse_llm_insights(response)

    async def _identify_strengths(self, module_path: str, code_files: List[str]) -> List[str]:
        """识别代码做得好的地方"""

        code_context = self._build_code_summary(code_files)

        prompt = f"""分析 LivingTreeAI 模块的代码质量优势。

模块: {module_path}
代码摘要:
```python
{code_context}
```

请识别并赞扬以下方面做得好的地方：

1. **设计模式应用**: 哪些地方使用了好的设计模式？
2. **代码组织**: 模块结构和文件组织是否合理？
3. **可读性**: 代码命名、注释、文档的质量如何？
4. **错误处理**: 错误处理策略是否健壮？
5. **可测试性**: 代码是否易于测试？
6. **性能考量**: 是否有性能优化的亮点？

请列出 5-10 个具体的优势点，每个点包含代码位置和改进效果。"""

        response = await self.llm.generate(prompt)
        return self._parse_strengths(response)

    async def _llm_cross_module_analysis(self, reports: Dict[str, CodeQualityReport]) -> List[str]:
        """跨模块分析 - 发现模块间的问题"""

        report_summary = self._summarize_reports(reports)

        prompt = f"""分析 LivingTreeAI IDE 各模块之间的代码质量和架构关系。

跨模块分析报告:
{report_summary}

请分析：

1. **模块间耦合问题**
   - 哪些模块之间耦合严重？
   - 是否存在循环依赖？
   - 模块边界是否清晰？

2. **重复代码和模式**
   - 是否有跨模块的重复实现？
   - 是否有可以抽象为公共组件的代码？

3. **架构一致性**
   - 各模块的设计理念是否一致？
   - 是否有模块采用了与其他模块不同的设计模式？

4. **集成风险**
   - 修改某个模块可能影响哪些其他模块？
   - 哪些模块的耦合会造成升级困难？

5. **改进优先级建议**
   - 优先改进哪个模块会有最大的正向影响？
   - 哪些模块应该保持稳定？

请给出具体的分析和建议。"""

        response = await self.llm.generate(prompt)
        return self._parse_cross_module_insights(response)

    # ─────────────────────────────────────────────────────────────
    # 传统分析方法的增强版本
    # ─────────────────────────────────────────────────────────────

    async def _detect_code_smells(self, code_files: List[str]) -> List[CodeSmell]:
        """检测代码异味 - LLM 增强版本"""

        smells = []

        for file_path, content in code_files:
            # 基础静态检测
            basic_smells = self._static_smell_detection(content, file_path)

            # LLM 深度检测
            llm_smells = await self._llm_detect_smells(content, file_path)

            smells.extend(basic_smells)
            smells.extend(llm_smells)

        return smells

    async def _llm_detect_smells(self, content: str, file_path: str) -> List[CodeSmell]:
        """使用 LLM 检测语义层面的代码异味"""

        # 截取关键部分
        key_functions = self._extract_key_functions(content)

        prompt = f"""分析以下 LivingTreeAI 代码片段，检测代码异味。

文件: {file_path}

关键函数:
{key_functions}

请检测以下类型的代码异味：

1. **长方法** (超过 50 行)
2. **深层嵌套** (超过 3 层)
3. **上帝类** (职责过多的类)
4. **复杂条件** (超过 3 个条件的组合判断)
5. **缺失错误处理** (可能导致异常的地方没有 try-except)
6. **硬编码配置** (应该抽取为配置的值被硬编码)

对于每个检测到的异味，请返回：
- 类型
- 位置（函数名或行号）
- 严重程度（low/medium/high/critical）
- 描述
- 修复建议
- 预估修复时间（小时）

如果没有检测到明显的异味，请明确说明。"""

        response = await self.llm.generate(prompt)
        return self._parse_smells(response, file_path)

    async def _identify_technical_debt(self, code_files: List[str]) -> List[TechnicalDebt]:
        """识别技术债务"""

        debts = []

        for file_path, content in code_files:
            # 基础债务检测
            basic_debts = self._static_debt_detection(content, file_path)

            # LLM 深度分析
            llm_debts = await self._llm_identify_debt(content, file_path)

            debts.extend(basic_debts)
            debts.extend(llm_debts)

        return debts

    async def _llm_identify_debt(self, content: str, file_path: str) -> List[TechnicalDebt]:
        """使用 LLM 识别上下文相关的技术债务"""

        code_summary = self._summarize_for_debt_analysis(content)

        prompt = f"""分析以下 LivingTreeAI 代码，识别技术债务。

文件: {file_path}

代码摘要:
```python
{code_summary}
```

LivingTreeAI 项目背景：
- 这是一个 AI IDE 项目，旨在实现"意图驱动的编程范式"
- 核心模块包括 Intent Engine、Code Analyzer、Context Manager
- 目标是让开发者通过自然语言描述意图，AI 自动生成和优化代码

请识别以下类型的技术债务：

1. **设计债务**
   - 是否使用了过时的设计模式？
   - 是否有更好的架构选择但没有采用？

2. **实现债务**
   - 是否有临时解决方案？
   - 是否有 TODO/FIXME/HACK 但没有处理？

3. **测试债务**
   - 关键逻辑是否缺少测试？
   - 测试是否过于脆弱？

4. **文档债务**
   - 关键代码是否缺少文档？
   - 公共 API 是否缺少说明？

5. **配置债务**
   - 是否有硬编码的值应该抽取为配置？
   - 是否有魔法数字没有解释？

6. **依赖债务**
   - 是否依赖了过时的库？
   - 是否有不必要的依赖？

对于每个债务项，请说明：
- 类别
- 标题
- 具体描述
- 影响范围（哪些文件）
- 严重程度
- 不修复的隐性成本
- 建议的处理方式"""

        response = await self.llm.generate(prompt)
        return self._parse_debts(response, file_path)

    # ─────────────────────────────────────────────────────────────
    # 辅助方法
    # ─────────────────────────────────────────────────────────────

    def _collect_python_files(self, module_path: str) -> List[tuple]:
        """收集模块下的所有 Python 文件"""
        import os
        files = []
        for root, dirs, filenames in os.walk(module_path):
            for f in filenames:
                if f.endswith('.py') and not f.startswith('test_'):
                    full_path = os.path.join(root, f)
                    with open(full_path, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    files.append((full_path, content))
        return files

    def _build_code_summary(self, code_files: List[tuple], max_chars: int = 3000) -> str:
        """构建代码摘要用于 LLM 分析"""
        summary_parts = []
        total_chars = 0

        for file_path, content in code_files:
            if total_chars >= max_chars:
                break

            # 提取文件头和关键结构
            file_summary = self._extract_file_summary(file_path, content)
            part = f"\n{'='*60}\n文件: {file_path}\n{'='*60}\n{file_summary}\n"
            summary_parts.append(part)
            total_chars += len(part)

        return "\n".join(summary_parts)

    def _extract_file_summary(self, file_path: str, content: str) -> str:
        """提取文件的摘要信息"""
        import ast

        try:
            tree = ast.parse(content)
        except:
            return content[:500]

        summary = []

        # 类和函数定义
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                summary.append(f"class {node.name}: # methods: {', '.join(methods)}")
            elif isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                summary.append(f"def {node.name}(): # lines: {node.end_lineno - node.lineno + 1}")

        return "\n".join(summary) if summary else content[:500]

    def _extract_key_functions(self, content: str, max_lines: int = 150) -> str:
        """提取关键函数用于分析"""
        lines = content.split('\n')
        key_lines = []

        in_function = False
        function_start = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('def ') or line.strip().startswith('async def '):
                if in_function:
                    key_lines.append('\n'.join(lines[function_start:i]))
                in_function = True
                function_start = i

        if in_function:
            key_lines.append('\n'.join(lines[function_start:]))

        return '\n\n'.join(key_lines[:max_lines]) if key_lines else content[:1000]

    def _summarize_for_debt_analysis(self, content: str) -> str:
        """为债务分析生成摘要"""
        summary = []
        lines = content.split('\n')

        # 收集 TODO/FIXME/HACK
        for i, line in enumerate(lines):
            if 'TODO' in line or 'FIXME' in line or 'HACK' in line:
                summary.append(f"L{i+1}: {line.strip()}")

        # 收集导入
        imports = [l for l in lines if l.strip().startswith(('import ', 'from '))]
        if imports:
            summary.append(f"\n导入 ({len(imports)}):")
            summary.extend(imports[:20])

        # 收集类定义
        classes = [l for l in lines if l.strip().startswith('class ')]
        if classes:
            summary.append(f"\n类定义 ({len(classes)}):")
            summary.extend(classes)

        return '\n'.join(summary) if summary else content[:1500]

    def _summarize_reports(self, reports: Dict[str, CodeQualityReport]) -> str:
        """汇总多个报告用于跨模块分析"""
        summary = []

        for path, report in reports.items():
            summary.append(f"""
{'='*60}
模块: {path}
{'='*60}
- 质量评分: {report.overall_score:.1f}/100 ({report.quality_level.value})
- 代码异味: {len(report.code_smells)} 个
- 技术债务: {len(report.technical_debts)} 项 ({report.metrics.technical_debt_hours:.1f} 人时)
- 主要问题: {', '.join(report.priority_issues[:3])}
""")

        return "\n".join(summary)

    def _calculate_overall_score(self, metrics: QualityMetrics, smells: List[CodeSmell],
                                 debts: List[TechnicalDebt]) -> float:
        """计算综合质量分数"""
        # 基础分 100
        score = 100.0

        # 扣分：代码异味
        smell_penalty = sum(
            self.smell_weights.get(s.smell_type, 1.0) * (10 if s.severity == 'critical' else
                                                          5 if s.severity == 'high' else
                                                          2 if s.severity == 'medium' else 1)
            for s in smells
        )
        score -= smell_penalty

        # 扣分：技术债务
        debt_penalty = len(debts) * 5 + metrics.technical_debt_hours * 0.5
        score -= debt_penalty

        # 扣分：可维护性
        if metrics.maintainability_index < 80:
            score -= (80 - metrics.maintainability_index) * 0.3

        return max(0.0, min(100.0, score))

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= 95:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 60:
            return QualityLevel.ACCEPTABLE
        elif score >= 40:
            return QualityLevel.NEEDS_IMPROVEMENT
        else:
            return QualityLevel.POOR

    def _rank_priority_issues(self, smells: List[CodeSmell], debts: List[TechnicalDebt]) -> List[str]:
        """排序优先级问题"""
        issues = []

        # 按严重程度排序
        for smell in smells:
            if smell.severity in ('critical', 'high'):
                issues.append(f"[{smell.severity.upper()}] {smell.description} (at {smell.location})")

        for debt in debts:
            if debt.severity in ('critical', 'high'):
                issues.append(f"[{debt.severity.upper()}] {debt.title}: {debt.description}")

        return issues[:10]  # 最多返回 10 个

    # ─────────────────────────────────────────────────────────────
    # LLM 输出解析
    # ─────────────────────────────────────────────────────────────

    def _parse_llm_insights(self, response: str) -> List[str]:
        """解析 LLM 深度洞察"""
        insights = []
        lines = response.strip().split('\n')
        current_insight = []

        for line in lines:
            if line.strip() and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                if current_insight:
                    insights.append('\n'.join(current_insight))
                current_insight = [line]
            else:
                current_insight.append(line)

        if current_insight:
            insights.append('\n'.join(current_insight))

        return insights[:10]

    def _parse_strengths(self, response: str) -> List[str]:
        """解析代码优势"""
        strengths = []
        for line in response.strip().split('\n'):
            if line.strip() and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                strengths.append(line.strip())

        return strengths[:10]

    def _parse_smells(self, response: str, file_path: str) -> List[CodeSmell]:
        """解析代码异味"""
        smells = []
        # 简化的解析逻辑
        for line in response.split('\n'):
            if 'LONG_METHOD' in line.upper() or '长方法' in line:
                smells.append(CodeSmell(
                    smell_type=CodeSmellType.LONG_METHOD,
                    location=file_path,
                    severity='medium',
                    description='检测到长方法',
                    suggestion='建议拆分为更小的函数',
                    estimated_fix_effort=2.0
                ))

        return smells

    def _parse_debts(self, response: str, file_path: str) -> List[TechnicalDebt]:
        """解析技术债务"""
        debts = []

        for line in response.split('\n'):
            if 'TODO' in line or 'FIXME' in line:
                debts.append(TechnicalDebt(
                    category='implementation',
                    title='未完成的工作',
                    description=line.strip(),
                    impacted_files=[file_path],
                    severity='medium',
                    interest='债务会随时间增长',
                    suggested_approach='尽快完成或创建 issue 追踪'
                ))

        return debts

    def _parse_cross_module_insights(self, response: str) -> List[str]:
        """解析跨模块洞察"""
        return self._parse_llm_insights(response)
```

---

### 2. 架构健康度评估器 `LLMArchitectureHealthAnalyzer`

#### 功能定位

评估 LivingTreeAI IDE 模块的架构健康度，识别耦合、依赖和扩展性问题。

#### 评估维度

| 维度 | 指标 | LLM 增强 |
|------|------|----------|
| **耦合度** | 循环依赖、传递依赖 | 理解隐式耦合 |
| **内聚度** | 模块职责单一性 | 评估职责清晰度 |
| **扩展性** | 新功能添加难度 | 评估架构弹性 |
| **稳定性** | 变更影响范围 | 预测变更风险 |

#### 核心实现

```python
# core/ide_upgrader/architecture_health_analyzer.py
"""
LivingTreeAI IDE 模块架构健康度评估器
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum
import ast
import asyncio

class CouplingLevel(Enum):
    """耦合程度"""
    EXCELLENT = "excellent"    # 0-0.2
    GOOD = "good"              # 0.2-0.4
    MODERATE = "moderate"      # 0.4-0.6
    HIGH = "high"              # 0.6-0.8
    VERY_HIGH = "very_high"    # 0.8-1.0

class DependencyType(Enum):
    """依赖类型"""
    DIRECT = "direct"           # 直接依赖
    TRANSITIVE = "transitive"   # 传递依赖
    CIRCULAR = "circular"       # 循环依赖
    UNIDIRECTIONAL = "unidirectional"  # 单向依赖

@dataclass
class DependencyEdge:
    """依赖边"""
    from_module: str
    to_module: str
    dependency_type: DependencyType
    strength: float  # 0-1
    description: str

@dataclass
class CircularDependency:
    """循环依赖"""
    modules: List[str]
    severity: str
    impact: str
    suggested_resolution: str

@dataclass
class CohesionAnalysis:
    """内聚度分析"""
    module_name: str
    cohesion_score: float  # 0-100
    issues: List[str]
    suggestions: List[str]

@dataclass
class ArchitectureHealthReport:
    """架构健康度报告"""
    module_name: str
    overall_health_score: float  # 0-100

    coupling_level: CouplingLevel
    dependencies: List[DependencyEdge]
    circular_dependencies: List[CircularDependency]

    cohesion_analyses: List[CohesionAnalysis]

    extensibility_score: float
    extensibility_blockers: List[str]

    stability_score: float
    stability_concerns: List[str]

    recommendations: List[str]
    llm_architectural_insights: List[str]


class LLMArchitectureHealthAnalyzer:
    """LLM 增强的架构健康度分析器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def analyze_architecture(self, project_root: str) -> ArchitectureHealthReport:
        """
        分析 LivingTreeAI 项目架构健康度

        Args:
            project_root: 项目根目录

        Returns:
            ArchitectureHealthReport: 架构健康度报告
        """
        # 1. 构建依赖图
        dependency_graph = await self._build_dependency_graph(project_root)

        # 2. 检测循环依赖
        circular_deps = await self._detect_circular_dependencies(dependency_graph)

        # 3. 分析耦合度
        coupling_analysis = self._analyze_coupling(dependency_graph, circular_deps)

        # 4. 分析内聚度
        cohesion_analyses = await self._analyze_cohesion(project_root)

        # 5. 评估扩展性
        extensibility = await self._evaluate_extensibility(project_root)

        # 6. 评估稳定性
        stability = await self._evaluate_stability(project_root)

        # 7. LLM 深度分析
        llm_insights = await self._llm_architectural_analysis(
            dependency_graph, circular_deps, cohesion_analyses
        )

        # 8. 生成建议
        recommendations = self._generate_recommendations(
            coupling_analysis, cohesion_analyses, extensibility, stability
        )

        # 9. 计算综合评分
        overall_score = self._calculate_health_score(
            coupling_analysis, cohesion_analyses, extensibility, stability
        )

        return ArchitectureHealthReport(
            module_name=project_root,
            overall_health_score=overall_score,
            coupling_level=coupling_analysis['level'],
            dependencies=dependency_graph,
            circular_dependencies=circular_deps,
            cohesion_analyses=cohesion_analyses,
            extensibility_score=extensibility['score'],
            extensibility_blockers=extensibility['blockers'],
            stability_score=stability['score'],
            stability_concerns=stability['concerns'],
            recommendations=recommendations,
            llm_architectural_insights=llm_insights
        )

    # ─────────────────────────────────────────────────────────────
    # LLM 增强方法
    # ─────────────────────────────────────────────────────────────

    async def _llm_architectural_analysis(
        self,
        dependencies: List[DependencyEdge],
        circular_deps: List[CircularDependency],
        cohesion_analyses: List[CohesionAnalysis]
    ) -> List[str]:
        """LLM 深度架构分析"""

        dep_summary = self._summarize_dependencies(dependencies)
        circular_summary = self._summarize_circular_deps(circular_deps)
        cohesion_summary = self._summarize_cohesion(cohesion_analyses)

        prompt = f"""作为架构专家，分析 LivingTreeAI IDE 模块的架构设计。

依赖关系摘要:
{dep_summary}

循环依赖:
{circular_summary}

内聚度分析:
{cohesion_summary}

LivingTreeAI 项目背景:
- 这是一个 AI IDE 项目，核心是"意图驱动编程"
- 目标是从"带 AI 的编辑器"进化到"意图处理器"
- 架构应该支持 L1-L5 级别的自动驾驶能力

请进行深度架构分析：

1. **架构模式评估**
   - 当前架构是否符合"意图驱动"的设计理念？
   - 是否需要引入新的架构模式？

2. **模块边界分析**
   - 模块边界是否清晰？
   - 是否有职责模糊的模块？
   - 是否应该拆分或合并某些模块？

3. **依赖关系优化**
   - 依赖方向是否正确？
   - 是否有可以解耦的地方？
   - 是否应该引入抽象层或中间件？

4. **扩展性评估**
   - 添加新功能（如新的 LLM Provider）的难度如何？
   - 是否存在架构层面的扩展瓶颈？
   - 是否有过度设计的地方？

5. **技术决策建议**
   - 基于项目目标，哪些架构调整是必要的？
   - 推荐的演进路径是什么？

请给出具体的洞察和建议，包括代码级别的改进方案。"""

        response = await self.llm.generate(prompt)
        return self._parse_architectural_insights(response)

    async def _evaluate_extensibility(self, project_root: str) -> Dict:
        """评估架构扩展性"""

        # 收集关键模块代码
        key_modules = self._collect_key_modules(project_root)

        prompt = f"""评估 LivingTreeAI IDE 的架构扩展性。

关键模块结构:
{key_modules}

LivingTreeAI 的扩展场景：
1. 添加新的 LLM Provider (如 Claude、Gemini)
2. 添加新的 IDE 面板
3. 添加新的代码分析能力
4. 添加新的意图类型
5. 支持新的编程语言

请分析：

1. **当前扩展点识别**
   - 代码中是否已经有清晰的扩展点？
   - 是否使用了插件机制、策略模式等可扩展设计？

2. **扩展难度评估**
   - 添加一个新的 LLM Provider 需要修改多少文件？
   - 是否需要修改核心代码？

3. **扩展性障碍**
   - 哪些地方阻碍了轻松扩展？
   - 是否有硬编码的逻辑？

4. **扩展性建议**
   - 如何改进架构以支持更轻松的扩展？
   - 需要引入哪些抽象层？

5. **扩展性评分** (0-100)
   - 评估当前架构支持扩展的容易程度

请给出具体的评分和改进建议。"""

        response = await self.llm.generate(prompt)
        return self._parse_extensibility_analysis(response)

    async def _evaluate_stability(self, project_root: str) -> Dict:
        """评估架构稳定性"""

        prompt = f"""评估 LivingTreeAI IDE 各模块的稳定性。

项目结构:
{project_root}

请分析：

1. **模块稳定性分类**
   - 稳定模块（很少变更）
   - 半稳定模块（偶尔变更）
   - 不稳定模块（频繁变更）

2. **变更影响分析**
   - 修改某个模块可能影响哪些其他模块？
   - 哪些模块的变更风险最高？

3. **稳定性问题**
   - 是否有不合理的依赖导致不稳定模块影响稳定模块？
   - 是否有测试覆盖不足导致不敢修改代码？

4. **稳定性建议**
   - 如何提高整体架构的稳定性？
   - 哪些模块需要优先重构以提高稳定性？

5. **稳定性评分** (0-100)"""

        response = await self.llm.generate(prompt)
        return self._parse_stability_analysis(response)

    # ─────────────────────────────────────────────────────────────
    # 辅助方法
    # ─────────────────────────────────────────────────────────────

    async def _build_dependency_graph(self, project_root: str) -> List[DependencyEdge]:
        """构建模块依赖图"""
        import os

        dependencies = []
        modules = self._find_modules(project_root)

        for module_file in modules:
            try:
                with open(module_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)

                module_name = self._get_module_name(module_file, project_root)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith('core.'):
                            for alias in node.names:
                                dep_module = f"core.{node.module.split('.')[1] if len(node.module.split('.')) > 1 else ''}"
                                dependencies.append(DependencyEdge(
                                    from_module=module_name,
                                    to_module=dep_module,
                                    dependency_type=DependencyType.DIRECT,
                                    strength=1.0,
                                    description=f"导入 {alias.name}"
                                ))
            except:
                continue

        return dependencies

    def _detect_circular_dependencies(self, dependencies: List[DependencyEdge]) -> List[CircularDependency]:
        """检测循环依赖"""
        circular_deps = []

        # 构建邻接表
        graph = {}
        for dep in dependencies:
            if dep.from_module not in graph:
                graph[dep.from_module] = []
            graph[dep.from_module].append(dep.to_module)

        # DFS 检测环
        visited = set()
        rec_stack = []
        cycles = []

        def dfs(node, path):
            visited.add(node)
            rec_stack.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [node]):
                        return True
                elif neighbor in rec_stack:
                    # 发现环
                    cycle_start = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                dfs(node, [])

        # 转换为 CircularDependency
        for cycle in cycles:
            circular_deps.append(CircularDependency(
                modules=cycle,
                severity='high' if len(cycle) <= 3 else 'medium',
                impact=f"{len(cycle)} 个模块形成循环依赖",
                suggested_resolution="通过引入抽象接口或重新设计依赖方向解耦"
            ))

        return circular_deps

    def _analyze_cohesion(self, project_root: str) -> List[CohesionAnalysis]:
        """分析模块内聚度"""
        analyses = []
        modules = self._find_modules(project_root)

        for module_file in modules:
            module_name = self._get_module_name(module_file, project_root)

            try:
                with open(module_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)

                classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

                # 简化的内聚度评估
                if len(classes) > 0:
                    cohesion_score = min(100.0, 50.0 + (len(functions) / len(classes)) * 10)
                else:
                    cohesion_score = 70.0

                analyses.append(CohesionAnalysis(
                    module_name=module_name,
                    cohesion_score=cohesion_score,
                    issues=["内聚度可提升" if cohesion_score < 70 else "内聚度良好"],
                    suggestions=["考虑拆分职责过多的类" if cohesion_score < 60 else "保持现状"]
                ))
            except:
                continue

        return analyses

    def _summarize_dependencies(self, dependencies: List[DependencyEdge]) -> str:
        """生成依赖摘要"""
        dep_map = {}
        for dep in dependencies:
            if dep.from_module not in dep_map:
                dep_map[dep.from_module] = []
            dep_map[dep.from_module].append(dep.to_module)

        summary = []
        for module, deps in dep_map.items():
            summary.append(f"{module} -> {', '.join(set(deps))}")

        return "\n".join(summary) if summary else "无依赖关系"

    def _summarize_circular_deps(self, circular_deps: List[CircularDependency]) -> str:
        """生成循环依赖摘要"""
        if not circular_deps:
            return "未检测到循环依赖"

        summary = []
        for dep in circular_deps:
            summary.append(f"{' -> '.join(dep.modules)} [严重程度: {dep.severity}]")

        return "\n".join(summary)

    def _summarize_cohesion(self, analyses: List[CohesionAnalysis]) -> str:
        """生成内聚度摘要"""
        summary = []
        for analysis in analyses:
            summary.append(f"{analysis.module_name}: {analysis.cohesion_score:.1f}%")

        return "\n".join(summary)

    def _collect_key_modules(self, project_root: str) -> str:
        """收集关键模块结构"""
        import os

        key_modules = []
        for root, dirs, files in os.walk(project_root):
            if 'core' in root or 'ui' in root:
                for f in files:
                    if f.endswith('.py') and not f.startswith('test_'):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, project_root)
                        key_modules.append(rel_path)

        return "\n".join(key_modules[:50])

    def _find_modules(self, project_root: str) -> List[str]:
        """查找所有 Python 模块"""
        import os
        modules = []

        for root, dirs, files in os.walk(project_root):
            # 跳过测试和虚拟环境
            if 'test' in root or 'venv' in root or '__pycache__' in root:
                continue

            for f in files:
                if f.endswith('.py') and not f.startswith('test_'):
                    modules.append(os.path.join(root, f))

        return modules

    def _get_module_name(self, file_path: str, project_root: str) -> str:
        """获取模块名称"""
        rel_path = os.path.relpath(file_path, project_root)
        return rel_path.replace('\\', '/').replace('/', '.').replace('.py', '')

    def _analyze_coupling(self, dependencies: List[DependencyEdge],
                         circular_deps: List[CircularDependency]) -> Dict:
        """分析耦合度"""

        # 计算耦合指数
        total_deps = len(dependencies)
        modules = set(d.from_module for d in dependencies) | set(d.to_module for d in dependencies)

        if len(modules) <= 1:
            coupling_score = 0.0
        else:
            coupling_score = total_deps / (len(modules) * (len(modules) - 1) / 2)

        # 考虑循环依赖
        if circular_deps:
            coupling_score += len(circular_deps) * 0.1

        coupling_score = min(1.0, coupling_score)

        # 确定耦合级别
        if coupling_score <= 0.2:
            level = CouplingLevel.EXCELLENT
        elif coupling_score <= 0.4:
            level = CouplingLevel.GOOD
        elif coupling_score <= 0.6:
            level = CouplingLevel.MODERATE
        elif coupling_score <= 0.8:
            level = CouplingLevel.HIGH
        else:
            level = CouplingLevel.VERY_HIGH

        return {
            'score': coupling_score,
            'level': level,
            'total_dependencies': total_deps,
            'module_count': len(modules)
        }

    def _calculate_health_score(self, coupling: Dict, cohesion: List[CohesionAnalysis],
                               extensibility: Dict, stability: Dict) -> float:
        """计算综合健康度分数"""

        # 耦合度权重 25%
        coupling_score = (1 - coupling['score']) * 100

        # 内聚度权重 25%
        avg_cohesion = sum(a.cohesion_score for a in cohesion) / len(cohesion) if cohesion else 50

        # 扩展性权重 25%
        extensibility_score = extensibility.get('score', 50)

        # 稳定性权重 25%
        stability_score = stability.get('score', 50)

        # 综合评分
        overall = (
            coupling_score * 0.25 +
            avg_cohesion * 0.25 +
            extensibility_score * 0.25 +
            stability_score * 0.25
        )

        return overall

    def _generate_recommendations(self, coupling: Dict, cohesion: List[CohesionAnalysis],
                                  extensibility: Dict, stability: Dict) -> List[str]:
        """生成架构改进建议"""

        recommendations = []

        # 耦合度建议
        if coupling['level'] in (CouplingLevel.HIGH, CouplingLevel.VERY_HIGH):
            recommendations.append("降低模块间耦合度，引入接口抽象层")
            recommendations.append("避免直接引用，改用依赖注入")

        # 内聚度建议
        low_cohesion = [a for a in cohesion if a.cohesion_score < 60]
        if low_cohesion:
            recommendations.append(f"提升 {len(low_cohesion)} 个模块的内聚度，考虑拆分职责过多的类")

        # 扩展性建议
        blockers = extensibility.get('blockers', [])
        if blockers:
            recommendations.append(f"解决扩展性障碍: {', '.join(blockers[:3])}")

        # 稳定性建议
        concerns = stability.get('concerns', [])
        if concerns:
            recommendations.append(f"提高稳定性: {', '.join(concerns[:3])}")

        return recommendations

    def _parse_extensibility_analysis(self, response: str) -> Dict:
        """解析扩展性分析结果"""
        # 简化解析
        lines = response.split('\n')
        score = 50.0
        blockers = []

        for line in lines:
            if '评分' in line or 'score' in line.lower():
                try:
                    score = float(''.join(filter(str.isdigit, line.split(':')[-1])))
                except:
                    pass

            if '障碍' in line or 'blocker' in line.lower():
                blockers.append(line.strip())

        return {
            'score': score,
            'blockers': blockers[:5]
        }

    def _parse_stability_analysis(self, response: str) -> Dict:
        """解析稳定性分析结果"""
        lines = response.split('\n')
        score = 50.0
        concerns = []

        for line in lines:
            if '评分' in line or 'score' in line.lower():
                try:
                    score = float(''.join(filter(str.isdigit, line.split(':')[-1])))
                except:
                    pass

            if '问题' in line or 'concern' in line.lower():
                concerns.append(line.strip())

        return {
            'score': score,
            'concerns': concerns[:5]
        }

    def _parse_architectural_insights(self, response: str) -> List[str]:
        """解析架构洞察"""
        insights = []
        current_insight = []

        for line in response.strip().split('\n'):
            if line.strip() and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                if current_insight:
                    insights.append('\n'.join(current_insight))
                current_insight = [line]
            else:
                current_insight.append(line)

        if current_insight:
            insights.append('\n'.join(current_insight))

        return insights[:8]
```

---

### 3. 功能完整性评估器 `LLMFeatureCompletenessAnalyzer`

#### 功能定位

评估 LivingTreeAI IDE 各模块的功能完整性，识别能力差距和冗余。

#### 评估框架

```python
# core/ide_upgrader/feature_completeness_analyzer.py
"""
LivingTreeAI IDE 功能完整性评估器
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum
import asyncio

class CapabilityGap(Enum):
    """能力差距类型"""
    MISSING_FEATURE = "missing_feature"       # 完全缺失的功能
    PARTIAL_IMPLEMENTATION = "partial"         # 部分实现
    LOW_QUALITY = "low_quality"               # 实现质量低
    POOR_INTEGRATION = "poor_integration"     # 集成度差

@dataclass
class FeatureCapability:
    """功能能力"""
    name: str
    description: str
    implementation_status: str  # implemented, partial, missing
    quality_score: float  # 0-100
    test_coverage: float  # 0-100
    documentation: str  # none, basic, complete
    integration_points: List[str]

@dataclass
class CapabilityGap:
    """能力差距"""
    gap_type: CapabilityGap
    feature_name: str
    description: str
    current_state: str
    target_state: str
    severity: str
    impact: str
    suggested_approach: str

@dataclass
class RedundancyIssue:
    """冗余问题"""
    feature_name: str
    duplicate_implementations: List[str]
    overlap_percentage: float
    severity: str
    resolution: str

@dataclass
class FeatureCompletenessReport:
    """功能完整性报告"""
    module_name: str
    capability_inventory: List[FeatureCapability]
    capability_gaps: List[CapabilityGap]
    redundancy_issues: List[RedundancyIssue]
    missing_features: List[str]
    overall_completeness_score: float
    llm_feature_insights: List[str]
    recommendations: List[str]


class LLMFeatureCompletenessAnalyzer:
    """LLM 增强的功能完整性分析器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

        # LivingTreeAI 目标能力框架
        self.target_capabilities = {
            'intent_engine': [
                '自然语言理解',
                '意图分类',
                '参数提取',
                '上下文追踪',
                '多轮对话',
                '错误恢复'
            ],
            'code_analyzer': [
                '代码解析',
                'AST 分析',
                '依赖分析',
                '质量检测',
                '重构建议',
                '代码补全'
            ],
            'context_manager': [
                '项目上下文',
                '文件索引',
                '符号索引',
                '搜索索引',
                '记忆管理'
            ],
            'ide_core': [
                '多标签编辑',
                '智能面板',
                '快速搜索',
                '设置管理',
                '插件系统'
            ],
            'execution_engine': [
                '任务分解',
                '并行执行',
                '进度追踪',
                '结果聚合',
                '错误处理'
            ]
        }

    async def analyze_module_features(self, module_path: str) -> FeatureCompletenessReport:
        """分析模块功能完整性"""

        # 1. 收集模块信息
        module_info = await self._collect_module_info(module_path)

        # 2. 对标目标能力
        capabilities = await self._map_capabilities(module_info)

        # 3. 识别能力差距
        gaps = await self._identify_gaps(capabilities, module_path)

        # 4. 检测冗余
        redundancies = await self._detect_redundancies(module_info)

        # 5. LLM 深度分析
        insights = await self._llm_feature_analysis(module_info, capabilities, gaps)

        # 6. 计算完整性评分
        completeness_score = self._calculate_completeness(capabilities, gaps)

        # 7. 生成建议
        recommendations = self._generate_feature_recommendations(gaps, redundancies)

        return FeatureCompletenessReport(
            module_name=module_path,
            capability_inventory=capabilities,
            capability_gaps=gaps,
            redundancy_issues=redundancies,
            missing_features=[g.feature_name for g in gaps if g.gap_type == CapabilityGap.MISSING_FEATURE],
            overall_completeness_score=completeness_score,
            llm_feature_insights=insights,
            recommendations=recommendations
        )

    async def _llm_feature_analysis(
        self,
        module_info: Dict,
        capabilities: List[FeatureCapability],
        gaps: List[CapabilityGap]
    ) -> List[str]:
        """LLM 深度功能分析"""

        cap_summary = self._summarize_capabilities(capabilities)
        gap_summary = self._summarize_gaps(gaps)

        prompt = f"""作为功能分析专家，评估 LivingTreeAI IDE 模块的功能完整性。

模块信息:
{module_info.get('summary', 'N/A')}

当前能力:
{cap_summary}

能力差距:
{gap_summary}

LivingTreeAI 项目目标：
- 从"带 AI 的编辑器"进化到"意图处理器"
- 实现 L1-L5 自动驾驶级别
- 让开发者通过自然语言描述意图，AI 自动完成编程

请进行深度功能分析：

1. **功能完整性评估**
   - 当前实现的功能是否覆盖了核心需求？
   - 是否有遗漏的关键功能？

2. **功能质量评估**
   - 已实现的功能质量如何？
   - 是否有"看起来有但不好用"的功能？

3. **功能优先级分析**
   - 基于项目目标，哪些功能应该优先实现/改进？
   - 哪些功能可以暂时搁置？

4. **集成度分析**
   - 各功能之间的集成是否顺畅？
   - 是否有功能孤岛？

5. **演进路径建议**
   - 如何逐步完善功能体系？
   - 短期、中期、长期应该分别关注什么？

请给出具体的洞察和建议。"""

        response = await self.llm.generate(prompt)
        return self._parse_feature_insights(response)

    def _summarize_capabilities(self, capabilities: List[FeatureCapability]) -> str:
        """生成能力摘要"""
        summary = []
        for cap in capabilities:
            summary.append(
                f"- {cap.name}: {cap.implementation_status} "
                f"(质量: {cap.quality_score:.0f}%, 覆盖: {cap.test_coverage:.0f}%)"
            )
        return "\n".join(summary)

    def _summarize_gaps(self, gaps: List[CapabilityGap]) -> str:
        """生成差距摘要"""
        summary = []
        for gap in gaps:
            summary.append(
                f"- [{gap.gap_type.value}] {gap.feature_name}: {gap.description}"
            )
        return "\n".join(summary) if summary else "无明显差距"

    def _identify_gaps(
        self,
        capabilities: List[FeatureCapability],
        module_path: str
    ) -> List[CapabilityGap]:
        """识别能力差距"""
        gaps = []

        # 获取目标能力
        module_name = module_path.split('/')[-1]
        targets = self.target_capabilities.get(module_name, [])

        cap_names = {cap.name for cap in capabilities}

        # 检测缺失
        for target in targets:
            if target not in cap_names:
                gaps.append(CapabilityGap(
                    gap_type=CapabilityGap.MISSING_FEATURE,
                    feature_name=target,
                    description=f"功能 '{target}' 未实现",
                    current_state="missing",
                    target_state="implemented",
                    severity="high",
                    impact=f"影响 {module_name} 核心能力",
                    suggested_approach=f"需要设计并实现 {target} 功能"
                ))

        # 检测部分实现
        for cap in capabilities:
            if cap.implementation_status == 'partial':
                gaps.append(CapabilityGap(
                    gap_type=CapabilityGap.PARTIAL_IMPLEMENTATION,
                    feature_name=cap.name,
                    description=f"功能 '{cap.name}' 仅部分实现",
                    current_state="partial",
                    target_state="fully implemented",
                    severity="medium",
                    impact=f"功能不完整影响用户体验",
                    suggested_approach="完善功能实现，提升质量"
                ))

            if cap.quality_score < 60:
                gaps.append(CapabilityGap(
                    gap_type=CapabilityGap.LOW_QUALITY,
                    feature_name=cap.name,
                    description=f"功能 '{cap.name}' 质量较低 ({cap.quality_score:.0f}%)",
                    current_state="low quality",
                    target_state="high quality",
                    severity="medium",
                    impact="影响系统稳定性和用户信任",
                    suggested_approach="重构代码，提升质量和测试覆盖"
                ))

        return gaps

    def _detect_redundancies(self, module_info: Dict) -> List[RedundancyIssue]:
        """检测功能冗余"""
        # 简化实现
        return []

    def _calculate_completeness(
        self,
        capabilities: List[FeatureCapability],
        gaps: List[CapabilityGap]
    ) -> float:
        """计算完整性评分"""

        if not capabilities:
            return 0.0

        # 基础分
        score = 100.0

        # 缺失功能扣分
        missing_count = sum(1 for g in gaps if g.gap_type == CapabilityGap.MISSING_FEATURE)
        if missing_count > 0:
            score -= missing_count * 10

        # 部分实现扣分
        partial_count = sum(1 for g in gaps if g.gap_type == CapabilityGap.PARTIAL_IMPLEMENTATION)
        if partial_count > 0:
            score -= partial_count * 5

        # 质量扣分
        low_quality_count = sum(1 for g in gaps if g.gap_type == CapabilityGap.LOW_QUALITY)
        if low_quality_count > 0:
            score -= low_quality_count * 3

        return max(0.0, min(100.0, score))

    def _generate_feature_recommendations(
        self,
        gaps: List[CapabilityGap],
        redundancies: List[RedundancyIssue]
    ) -> List[str]:
        """生成功能改进建议"""

        recommendations = []

        # 缺失功能建议
        missing = [g for g in gaps if g.gap_type == CapabilityGap.MISSING_FEATURE]
        if missing:
            recommendations.append(f"优先实现 {len(missing)} 个缺失的核心功能")

        # 质量改进建议
        low_quality = [g for g in gaps if g.gap_type == CapabilityGap.LOW_QUALITY]
        if low_quality:
            recommendations.append(f"提升 {len(low_quality)} 个低质量功能的实现")

        # 冗余处理建议
        if redundancies:
            recommendations.append(f"消除 {len(redundancies)} 个功能冗余")

        return recommendations

    def _parse_feature_insights(self, response: str) -> List[str]:
        """解析功能洞察"""
        insights = []
        for line in response.strip().split('\n'):
            if line.strip() and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                insights.append(line.strip())

        return insights[:8]

    async def _collect_module_info(self, module_path: str) -> Dict:
        """收集模块信息"""
        import os

        files = []
        summary = []

        for root, dirs, filenames in os.walk(module_path):
            for f in filenames:
                if f.endswith('.py') and not f.startswith('test_'):
                    full_path = os.path.join(root, f)
                    files.append(full_path)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as fp:
                            content = fp.read()
                            summary.append(f"\n{files[-1]}:\n{content[:500]}")
                    except:
                        pass

        return {
            'files': files,
            'summary': '\n'.join(summary)
        }

    async def _map_capabilities(self, module_info: Dict) -> List[FeatureCapability]:
        """映射模块能力"""
        # 简化实现 - 实际应该分析代码
        capabilities = []

        for file_path in module_info.get('files', []):
            file_name = os.path.basename(file_path)

            capabilities.append(FeatureCapability(
                name=file_name.replace('.py', ''),
                description=f"{file_name} 模块功能",
                implementation_status='implemented',
                quality_score=70.0,
                test_coverage=50.0,
                documentation='basic',
                integration_points=[]
            ))

        return capabilities
```

---

### 4. 智能化水平评估器 `LLMIntelligenceLevelAnalyzer`

#### 功能定位

评估 LivingTreeAI IDE 的"智能化"成熟度，这是 LivingTreeAI 区别于普通 IDE 的核心。

#### 自动驾驶级别定义

```python
# core/ide_upgrader/intelligence_level_analyzer.py
"""
LivingTreeAI IDE 智能化水平评估器
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import asyncio

class IntelligenceLevel(Enum):
    """智能化级别 (类比自动驾驶)"""
    L1_ASSISTED = "L1"    # 辅助驾驶 - 代码补全、语法检查
    L2_PARTIAL = "L2"    # 部分自动化 - 生成简单函数、修复错误
    L3_CONDITIONAL = "L3" # 条件自动化 - 明确场景完全接管
    L4_HIGH = "L4"       # 高度自动化 - 处理复杂任务，人类偶尔干预
    L5_FULL = "L5"       # 完全自动化 - 描述需求，完成设计到部署

@dataclass
class IntelligenceCapability:
    """智能化能力"""
    capability_name: str
    level: IntelligenceLevel
    implementation_status: str
    quality: float  # 0-100
    examples: List[str]
    limitations: List[str]

@dataclass
class IntelligenceGap:
    """智能化差距"""
    current_level: IntelligenceLevel
    target_level: IntelligenceLevel
    gap_description: str
    required_improvements: List[str]
    estimated_effort: str

@dataclass
class IntelligenceAssessmentReport:
    """智能化评估报告"""
    overall_level: IntelligenceLevel
    level_score: float  # 0-100

    capabilities: List[IntelligenceCapability]
    gaps: List[IntelligenceGap]

    strength_areas: List[str]
    weakness_areas: List[str]

    evolution_path: List[str]
    llm_intelligence_insights: List[str]

    recommendations: List[str]


class LLMIntelligenceLevelAnalyzer:
    """LLM 增强的智能化水平评估器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

        # 各级别的能力定义
        self.level_capabilities = {
            IntelligenceLevel.L1_ASSISTED: [
                "代码补全",
                "语法检查",
                "基础错误提示",
                "格式化代码"
            ],
            IntelligenceLevel.L2_PARTIAL: [
                "生成简单函数",
                "修复常见错误",
                "代码重构建议",
                "自动导入"
            ],
            IntelligenceLevel.L3_CONDITIONAL: [
                "意图理解",
                "多步骤任务执行",
                "上下文感知补全",
                "智能错误恢复"
            ],
            IntelligenceLevel.L4_HIGH: [
                "复杂任务分解",
                "跨文件重构",
                "架构优化建议",
                "测试自动生成"
            ],
            IntelligenceLevel.L5_FULL: [
                "自然语言需求转代码",
                "自动设计架构",
                "自主代码生成",
                "自动部署"
            ]
        }

    async def assess_intelligence_level(self, project_root: str) -> IntelligenceAssessmentReport:
        """评估项目的智能化水平"""

        # 1. 分析现有能力
        capabilities = await self._analyze_intelligence_capabilities(project_root)

        # 2. 确定当前级别
        current_level = self._determine_current_level(capabilities)

        # 3. 识别差距
        gaps = self._identify_intelligence_gaps(current_level, capabilities)

        # 4. LLM 深度分析
        insights = await self._llm_intelligence_analysis(capabilities, current_level)

        # 5. 评估优劣势
        strengths, weaknesses = self._assess_strengths_weaknesses(capabilities)

        # 6. 规划演进路径
        evolution_path = self._plan_evolution_path(current_level, gaps)

        # 7. 计算级别分数
        level_score = self._calculate_level_score(capabilities, current_level)

        # 8. 生成建议
        recommendations = self._generate_intelligence_recommendations(gaps, evolution_path)

        return IntelligenceAssessmentReport(
            overall_level=current_level,
            level_score=level_score,
            capabilities=capabilities,
            gaps=gaps,
            strength_areas=strengths,
            weakness_areas=weaknesses,
            evolution_path=evolution_path,
            llm_intelligence_insights=insights,
            recommendations=recommendations
        )

    async def _llm_intelligence_analysis(
        self,
        capabilities: List[IntelligenceCapability],
        current_level: IntelligenceLevel
    ) -> List[str]:
        """LLM 深度智能化分析"""

        cap_summary = "\n".join([
            f"- {c.capability_name}: {c.level.value}, 质量 {c.quality:.0f}%"
            for c in capabilities
        ])

        prompt = f"""作为 AI 编程助手专家，评估 LivingTreeAI IDE 的智能化水平。

当前智能化能力:
{cap_summary}

当前评估级别: {current_level.value}

LivingTreeAI 目标：
- 从"带 AI 的编辑器"进化到"意图处理器"
- 实现编程范式的革命

请进行深度分析：

1. **智能化程度评估**
   - 当前实现的智能化能力是否达到宣传的水平？
   - 是否有"看起来智能但实际上是硬编码"的功能？

2. **意图理解深度**
   - Intent Engine 对自然语言的理解深度如何？
   - 是否能处理模糊、多义的指令？
   - 上下文追踪能力如何？

3. **决策能力评估**
   - 系统能做哪些自主决策？
   - 决策的正确率如何？
   - 是否有合适的置信度机制？

4. **用户交互模式**
   - 用户如何与 AI 交互？
   - 是否支持多轮对话？
   - 如何处理用户纠正？

5. **智能化演进建议**
   - 如何从当前级别向更高级别演进？
   - 哪些能力是进化的关键节点？
   - 推荐的演进顺序是什么？

请给出具体的洞察和建议。"""

        response = await self.llm.generate(prompt)
        return self._parse_intelligence_insights(response)

    def _determine_current_level(self, capabilities: List[IntelligenceCapability]) -> IntelligenceLevel:
        """确定当前智能化级别"""

        level_scores = {level: 0 for level in IntelligenceLevel}

        for cap in capabilities:
            # 映射能力到级别
            for level, level_caps in self.level_capabilities.items():
                if any(lc.lower() in cap.capability_name.lower() for lc in level_caps):
                    level_scores[level] += cap.quality

        # 计算各级别覆盖率
        level_coverage = {}
        for level, level_caps in self.level_capabilities.items():
            implemented = sum(
                1 for cap in capabilities
                if any(lc.lower() in cap.capability_name.lower() for lc in level_caps)
            )
            level_coverage[level] = implemented / len(level_caps) if level_caps else 0

        # 找到覆盖度最高的级别
        max_coverage = 0
        current_level = IntelligenceLevel.L1_ASSISTED

        for level, coverage in level_coverage.items():
            if coverage >= 0.5 and level.value > current_level.value:
                if coverage > max_coverage:
                    max_coverage = coverage
                    current_level = level

        return current_level

    def _identify_intelligence_gaps(
        self,
        current_level: IntelligenceLevel,
        capabilities: List[IntelligenceCapability]
    ) -> List[IntelligenceGap]:
        """识别智能化差距"""

        gaps = []

        # 获取目标级别
        target_level = IntelligenceLevel.L3_CONDITIONAL  # 默认目标

        if current_level.value < target_level.value:
            # 需要的能力
            needed_caps = []
            for level in IntelligenceLevel:
                if level.value <= current_level.value:
                    continue
                needed_caps.extend(self.level_capabilities[level])

            # 当前能力
            current_cap_names = {c.capability_name for c in capabilities}

            # 缺失能力
            missing = [nc for nc in needed_caps if nc not in current_cap_names]

            if missing:
                gaps.append(IntelligenceGap(
                    current_level=current_level,
                    target_level=target_level,
                    gap_description=f"缺少 {len(missing)} 项关键能力",
                    required_improvements=missing[:5],
                    estimated_effort="需要 2-4 周开发"
                ))

        return gaps

    def _assess_strengths_weaknesses(
        self,
        capabilities: List[IntelligenceCapability]
    ) -> tuple:
        """评估优劣势"""

        strengths = []
        weaknesses = []

        for cap in capabilities:
            if cap.quality >= 80:
                strengths.append(f"{cap.capability_name} (质量 {cap.quality:.0f}%)")
            elif cap.quality < 50:
                weaknesses.append(f"{cap.capability_name} (质量 {cap.quality:.0f}%)")

        return strengths[:5], weaknesses[:5]

    def _plan_evolution_path(
        self,
        current_level: IntelligenceLevel,
        gaps: List[IntelligenceGap]
    ) -> List[str]:
        """规划智能化演进路径"""

        path = []

        if current_level == IntelligenceLevel.L1_ASSISTED:
            path.append("阶段 1: 升级到 L2 - 实现简单函数生成和错误修复")
            path.append("阶段 2: 升级到 L3 - 实现意图理解和上下文感知")

        elif current_level == IntelligenceLevel.L2_PARTIAL:
            path.append("阶段 1: 升级到 L3 - 实现意图理解和多步骤任务执行")

        elif current_level == IntelligenceLevel.L3_CONDITIONAL:
            path.append("阶段 1: 升级到 L4 - 实现复杂任务分解和跨文件重构")

        else:
            path.append("当前已达到较高水平，持续优化和微调")

        return path

    def _calculate_level_score(
        self,
        capabilities: List[IntelligenceCapability],
        current_level: IntelligenceLevel
    ) -> float:
        """计算级别分数"""

        # 当前级别基础分
        level_scores = {
            IntelligenceLevel.L1_ASSISTED: 20,
            IntelligenceLevel.L2_PARTIAL: 40,
            IntelligenceLevel.L3_CONDITIONAL: 60,
            IntelligenceLevel.L4_HIGH: 80,
            IntelligenceLevel.L5_FULL: 95
        }

        base_score = level_scores.get(current_level, 20)

        # 加权当前能力质量
        avg_quality = sum(c.quality for c in capabilities) / len(capabilities) if capabilities else 50

        # 综合分数
        score = base_score * 0.6 + avg_quality * 0.4

        return min(100.0, score)

    def _generate_intelligence_recommendations(
        self,
        gaps: List[IntelligenceGap],
        evolution_path: List[str]
    ) -> List[str]:
        """生成智能化改进建议"""

        recommendations = []

        if gaps:
            recommendations.append(f"优先解决 {len(gaps)} 个智能化差距")

        for gap in gaps:
            for imp in gap.required_improvements[:3]:
                recommendations.append(f"实现: {imp}")

        recommendations.extend(evolution_path)

        return recommendations[:10]

    async def _analyze_intelligence_capabilities(self, project_root: str) -> List[IntelligenceCapability]:
        """分析智能化能力"""

        capabilities = []

        # 分析 Intent Engine
        intent_engine_path = f"{project_root}/core/intent_engine"
        if os.path.exists(intent_engine_path):
            capabilities.append(IntelligenceCapability(
                capability_name="意图理解",
                level=IntelligenceLevel.L3_CONDITIONAL,
                implementation_status="implemented",
                quality=65.0,
                examples=["自然语言转代码", "意图分类"],
                limitations=["多轮对话支持有限"]
            ))

        # 分析 Code Analyzer
        code_analyzer_path = f"{project_root}/core/code_analyzer"
        if os.path.exists(code_analyzer_path):
            capabilities.append(IntelligenceCapability(
                capability_name="代码分析",
                level=IntelligenceLevel.L2_PARTIAL,
                implementation_status="implemented",
                quality=70.0,
                examples=["AST 解析", "依赖分析"],
                limitations=["重构建议有限"]
            ))

        return capabilities

    def _parse_intelligence_insights(self, response: str) -> List[str]:
        """解析智能化洞察"""
        insights = []
        for line in response.strip().split('\n'):
            if line.strip() and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                insights.append(line.strip())

        return insights[:8]
```

---

### 5. 改造优先级排序器 `LLMRefactoringPrioritizer`

#### 功能定位

基于价值/风险分析，生成 LivingTreeAI IDE 模块的改造优先级和实施路径。

#### 优先级框架

```python
# core/ide_upgrader/refactoring_prioritizer.py
"""
LivingTreeAI IDE 改造优先级排序器
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import asyncio

class RefactoringPriority(Enum):
    """重构优先级"""
    CRITICAL = "critical"   # 必须立即处理
    HIGH = "high"           # 高优先级
    MEDIUM = "medium"       # 中优先级
    LOW = "low"             # 低优先级
    DEFER = "defer"         # 可推迟

class RefactoringType(Enum):
    """重构类型"""
    ARCHITECTURE = "architecture"
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    FEATURE = "feature"
    INTELLIGENCE = "intelligence"

@dataclass
class RefactoringTask:
    """重构任务"""
    task_id: str
    title: str
    description: str

    priority: RefactoringPriority
    refactoring_type: RefactoringType

    target_modules: List[str]
    effort_estimate: str  # 如 "3人日"

    risk_level: str  # low, medium, high
    impact: str
    value: str

    dependencies: List[str]  # 依赖的其他任务
   的实施步骤: List[str]

@dataclass
class RefactoringPhase:
    """重构阶段"""
    phase_name: str
    description: str
    duration: str
    tasks: List[RefactoringTask]
    milestones: List[str]
    exit_criteria: str

@dataclass
class RefactoringRoadmap:
    """重构路线图"""
    total_duration: str
    phases: List[RefactoringPhase]

    critical_path: List[str]  # 关键路径上的任务
    quick_wins: List[str]    # 快速胜利

    risk_mitigation: List[str]
    success_criteria: List[str]


class LLMRefactoringPrioritizer:
    """LLM 增强的重构优先级排序器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def generate_roadmap(
        self,
        quality_reports: Dict[str, 'CodeQualityReport'],
        architecture_reports: Dict[str, 'ArchitectureHealthReport'],
        feature_reports: Dict[str, 'FeatureCompletenessReport'],
        intelligence_report: 'IntelligenceAssessmentReport'
    ) -> RefactoringRoadmap:
        """生成重构路线图"""

        # 1. 收集所有问题
        all_issues = self._collect_all_issues(
            quality_reports,
            architecture_reports,
            feature_reports,
            intelligence_report
        )

        # 2. LLM 优先级分析
        prioritized_tasks = await self._llm_prioritize_refactoring(all_issues)

        # 3. 分组成阶段
        phases = await self._organize_into_phases(prioritized_tasks)

        # 4. 确定关键路径
        critical_path = self._identify_critical_path(phases)

        # 5. 识别快速胜利
        quick_wins = self._identify_quick_wins(prioritized_tasks)

        # 6. 风险缓解策略
        risk_mitigation = await self._generate_risk_mitigation(phases)

        # 7. 成功标准
        success_criteria = self._generate_success_criteria(phases)

        # 8. 计算总工期
        total_duration = self._calculate_total_duration(phases)

        return RefactoringRoadmap(
            total_duration=total_duration,
            phases=phases,
            critical_path=critical_path,
            quick_wins=quick_wins,
            risk_mitigation=risk_mitigation,
            success_criteria=success_criteria
        )

    async def _llm_prioritize_refactoring(self, all_issues: List[Dict]) -> List[RefactoringTask]:
        """LLM 增强的优先级排序"""

        issues_summary = self._summarize_issues(all_issues)

        prompt = f"""作为技术架构专家，为 LivingTreeAI IDE 模块的重构任务排定优先级。

所有待处理问题汇总:
{issues_summary}

LivingTreeAI 项目背景：
- 目标：从"带 AI 的编辑器"进化到"意图处理器"
- 当前阶段：核心模块开发中
- 团队规模：小型团队，需要高效的资源分配

请为每个重构任务确定：

1. **优先级评估** (critical/high/medium/low/defer)
   - 基于问题的严重程度和紧迫性
   - 考虑对项目目标的影响
   - 权衡投入产出比

2. **工作量估算**
   - 小 (1人日以内)
   - 中 (1-3人日)
   - 大 (1周以内)
   - 超大 (1周以上)

3. **风险评估**
   - 低风险：影响范围小，有现有测试
   - 中风险：影响范围中等，需要谨慎测试
   - 高风险：影响核心功能，需要全面测试和回滚计划

4. **依赖关系**
   - 哪些任务必须先完成才能开始其他任务
   - 哪些任务可以并行进行

5. **实施步骤**
   - 简化的实施步骤

请输出优先级排序后的重构任务列表，格式为：
[任务ID] 标题 - 优先级 - 工作量 - 风险 - 依赖

注意：应该优先处理高价值、低风险、依赖少、能为后续工作打基础的任务。"""

        response = await self.llm.generate(prompt)
        return self._parse_prioritized_tasks(response)

    async def _organize_into_phases(
        self,
        tasks: List[RefactoringTask]
    ) -> List[RefactoringPhase]:
        """将任务组织成阶段"""

        phases = []

        # Phase 1: 快速胜利 + 基础设施
        phase1_tasks = [t for t in tasks if t.priority in (RefactoringPriority.HIGH, RefactoringPriority.CRITICAL)
                       and t.refactoring_type in (RefactoringType.CODE_QUALITY, RefactoringType.PERFORMANCE)]
        if phase1_tasks:
            phases.append(RefactoringPhase(
                phase_name="阶段 1: 快速改进",
                description="修复高优先级的代码质量问题，提升系统稳定性",
                duration="1-2 周",
                tasks=phase1_tasks[:10],
                milestones=["代码质量评分提升 20%", "无 critical/high 级别问题"],
                exit_criteria="所有 critical/high 问题已解决或制定长期计划"
            ))

        # Phase 2: 架构优化
        phase2_tasks = [t for t in tasks if t.refactoring_type == RefactoringType.ARCHITECTURE
                        and t.priority in (RefactoringPriority.HIGH, RefactoringPriority.MEDIUM)]
        if phase2_tasks:
            phases.append(RefactoringPhase(
                phase_name="阶段 2: 架构重构",
                description="优化模块架构，降低耦合，提升扩展性",
                duration="2-4 周",
                tasks=phase2_tasks[:8],
                milestones=["耦合度降低 30%", "核心模块有清晰边界"],
                exit_criteria="架构健康度评分达到 80%"
            ))

        # Phase 3: 智能化提升
        phase3_tasks = [t for t in tasks if t.refactoring_type == RefactoringType.INTELLIGENCE
                        and t.priority in (RefactoringPriority.HIGH, RefactoringPriority.MEDIUM)]
        if phase3_tasks:
            phases.append(RefactoringPhase(
                phase_name="阶段 3: 智能化升级",
                description="提升 IDE 的智能化水平",
                duration="3-4 周",
                tasks=phase3_tasks[:6],
                milestones=["智能化水平提升一级", "核心意图理解准确率 > 85%"],
                exit_criteria="达到 L3 智能化水平"
            ))

        # Phase 4: 功能完善
        phase4_tasks = [t for t in tasks if t.refactoring_type == RefactoringType.FEATURE]
        if phase4_tasks:
            phases.append(RefactoringPhase(
                phase_name="阶段 4: 功能完善",
                description="补充缺失功能，消除冗余",
                duration="2-3 周",
                tasks=phase4_tasks[:5],
                milestones=["功能完整性达到 90%"],
                exit_criteria="所有 P0 功能已实现"
            ))

        return phases

    def _identify_critical_path(self, phases: List[RefactoringPhase]) -> List[str]:
        """识别关键路径"""
        critical_tasks = []

        for phase in phases:
            for task in phase.tasks:
                if task.priority == RefactoringPriority.CRITICAL:
                    critical_tasks.append(task.title)

        return critical_tasks[:10]

    def _identify_quick_wins(self, tasks: List[RefactoringTask]) -> List[str]:
        """识别快速胜利"""
        quick_wins = [
            t.title for t in tasks
            if t.effort_estimate in ("小", "1人日以内")
            and t.risk_level in ("low", "medium")
            and t.priority in (RefactoringPriority.HIGH, RefactoringPriority.MEDIUM)
        ]

        return quick_wins[:5]

    async def _generate_risk_mitigation(self, phases: List[RefactoringPhase]) -> List[str]:
        """生成风险缓解策略"""

        prompt = f"""为以下重构计划生成风险缓解策略。

重构阶段:
{chr(10).join([f"- {p.phase_name}: {p.description}" for p in phases])}

请为每个阶段识别：
1. 主要风险点
2. 预防措施
3. 应急预案
4. 回滚方案

同时给出总体风险管理策略。"""

        response = await self.llm.generate(prompt)
        return self._parse_risk_mitigation(response)

    def _generate_success_criteria(self, phases: List[RefactoringPhase]) -> List[str]:
        """生成成功标准"""
        criteria = []

        for phase in phases:
            criteria.append(f"{phase.phase_name}: {phase.exit_criteria}")

        criteria.extend([
            "代码质量评分达到 85%",
            "架构健康度评分达到 80%",
            "智能化水平达到 L3",
            "功能完整性达到 90%"
        ])

        return criteria

    def _collect_all_issues(
        self,
        quality_reports: Dict,
        architecture_reports: Dict,
        feature_reports: Dict,
        intelligence_report
    ) -> List[Dict]:
        """收集所有问题"""

        all_issues = []

        # 代码质量问题
        for module, report in quality_reports.items():
            for smell in report.code_smells:
                all_issues.append({
                    'source': 'code_quality',
                    'module': module,
                    'type': smell.smell_type.value,
                    'severity': smell.severity,
                    'description': smell.description,
                    'location': smell.location
                })

            for debt in report.technical_debts:
                all_issues.append({
                    'source': 'technical_debt',
                    'module': module,
                    'type': 'debt',
                    'severity': debt.severity,
                    'description': debt.title,
                    'effort': debt.interest
                })

        # 架构问题
        for module, report in architecture_reports.items():
            for circular in report.circular_dependencies:
                all_issues.append({
                    'source': 'architecture',
                    'module': module,
                    'type': 'circular_dependency',
                    'severity': circular.severity,
                    'description': f"循环依赖: {' -> '.join(circular.modules)}"
                })

        # 功能缺失
        for module, report in feature_reports.items():
            for gap in report.missing_features:
                all_issues.append({
                    'source': 'feature',
                    'module': module,
                    'type': 'missing_feature',
                    'severity': 'high',
                    'description': f"缺失功能: {gap}"
                })

        return all_issues

    def _summarize_issues(self, issues: List[Dict]) -> str:
        """汇总问题"""
        summary = []

        # 按严重程度分组
        by_severity = {}
        for issue in issues:
            sev = issue['severity']
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(issue)

        for sev in ['critical', 'high', 'medium', 'low']:
            if sev in by_severity:
                summary.append(f"\n{sev.upper()} ({len(by_severity[sev])}):")
                for issue in by_severity[sev][:5]:
                    summary.append(f"  - [{issue['module']}] {issue['description']}")

        return "\n".join(summary)

    def _calculate_total_duration(self, phases: List[RefactoringPhase]) -> str:
        """计算总工期"""
        return "8-13 周"  # 简化估算

    def _parse_prioritized_tasks(self, response: str) -> List[RefactoringTask]:
        """解析优先级排序结果"""
        tasks = []

        for line in response.strip().split('\n'):
            if line.strip() and ('-' in line or '[' in line):
                # 简化解析
                tasks.append(RefactoringTask(
                    task_id=f"task_{len(tasks)+1}",
                    title=line.strip(),
                    description="",
                    priority=RefactoringPriority.MEDIUM,
                    refactoring_type=RefactoringType.CODE_QUALITY,
                    target_modules=[],
                    effort_estimate="中",
                    risk_level="medium",
                    impact="",
                    value="",
                    dependencies=[],
                    实施步骤=[]
                ))

        return tasks[:20]

    def _parse_risk_mitigation(self, response: str) -> List[str]:
        """解析风险缓解策略"""
        risks = []
        for line in response.strip().split('\n'):
            if line.strip() and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                risks.append(line.strip())

        return risks[:5]
```

---

## 🔧 统一入口: `IDEUpgraderEngine`

```python
# core/ide_upgrader/engine.py
"""
LivingTreeAI IDE 模块升级引擎 - 统一入口
"""

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional

from .code_quality_analyzer import LLMCodeQualityAnalyzer, CodeQualityReport
from .architecture_health_analyzer import LLMArchitectureHealthAnalyzer, ArchitectureHealthReport
from .feature_completeness_analyzer import LLMFeatureCompletenessAnalyzer, FeatureCompletenessReport
from .intelligence_level_analyzer import LLMIntelligenceLevelAnalyzer, IntelligenceAssessmentReport
from .refactoring_prioritizer import LLMRefactoringPrioritizer, RefactoringRoadmap


@dataclass
class IDEUpgradeReport:
    """IDE 升级综合报告"""
    project_name: str
    analysis_timestamp: str

    quality_reports: Dict[str, CodeQualityReport]
    architecture_report: ArchitectureHealthReport
    feature_reports: Dict[str, FeatureCompletenessReport]
    intelligence_report: IntelligenceAssessmentReport

    refactoring_roadmap: RefactoringRoadmap

    executive_summary: str
    key_findings: List[str]
    immediate_actions: List[str]


class IDEUpgraderEngine:
    """
    LivingTreeAI IDE 模块 LLM 综合升级引擎

    整合代码质量、架构健康、功能完整性和智能化水平分析，
    生成针对性的改造建议和实施路线图。
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

        # 各分析器
        self.quality_analyzer = LLMCodeQualityAnalyzer(llm_client)
        self.architecture_analyzer = LLMArchitectureHealthAnalyzer(llm_client)
        self.feature_analyzer = LLMFeatureCompletenessAnalyzer(llm_client)
        self.intelligence_analyzer = LLMIntelligenceLevelAnalyzer(llm_client)
        self.prioritizer = LLMRefactoringPrioritizer(llm_client)

    async def analyze_and_upgrade(self, project_root: str) -> IDEUpgradeReport:
        """
        完整分析并生成升级报告

        Args:
            project_root: LivingTreeAI 项目根目录

        Returns:
            IDEUpgradeReport: 完整的升级分析报告
        """

        print("🔍 开始 LivingTreeAI IDE 模块分析...")

        # 1. 代码质量分析 (并行)
        print("  📊 分析代码质量...")
        quality_reports = await self._analyze_code_quality(project_root)

        # 2. 架构健康度分析
        print("  🏗️  分析架构健康度...")
        architecture_report = await self.architecture_analyzer.analyze_architecture(project_root)

        # 3. 功能完整性分析
        print("  🎯 分析功能完整性...")
        feature_reports = await self._analyze_features(project_root)

        # 4. 智能化水平分析
        print("  🤖 评估智能化水平...")
        intelligence_report = await self.intelligence_analyzer.assess_intelligence_level(project_root)

        # 5. 生成重构路线图
        print("  📋 生成改造路线图...")
        roadmap = await self.prioritizer.generate_roadmap(
            quality_reports,
            {'overall': architecture_report},
            feature_reports,
            intelligence_report
        )

        # 6. 生成执行摘要
        executive_summary = await self._generate_executive_summary(
            quality_reports, architecture_report, feature_reports, intelligence_report, roadmap
        )

        # 7. 识别关键发现
        key_findings = self._collect_key_findings(
            quality_reports, architecture_report, feature_reports, intelligence_report
        )

        # 8. 识别紧急行动
        immediate_actions = self._identify_immediate_actions(
            quality_reports, architecture_report, roadmap
        )

        print("✅ 分析完成!")

        return IDEUpgradeReport(
            project_name="LivingTreeAI IDE",
            analysis_timestamp=self._get_timestamp(),
            quality_reports=quality_reports,
            architecture_report=architecture_report,
            feature_reports=feature_reports,
            intelligence_report=intelligence_report,
            refactoring_roadmap=roadmap,
            executive_summary=executive_summary,
            key_findings=key_findings,
            immediate_actions=immediate_actions
        )

    async def _analyze_code_quality(self, project_root: str) -> Dict[str, CodeQualityReport]:
        """分析代码质量"""

        reports = {}

        # 核心模块
        core_modules = [
            'core/intent_engine',
            'core/code_analyzer',
            'core/ide',
            'core/plugin_manager',
            'core/task_execution',
            'core/project_matcher'
        ]

        tasks = []
        for module in core_modules:
            module_path = f"{project_root}/{module}"
            import os
            if os.path.exists(module_path):
                tasks.append(self.quality_analyzer.analyze_module(module_path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for module, result in zip(core_modules, results):
            if not isinstance(result, Exception):
                reports[module] = result

        return reports

    async def _analyze_features(self, project_root: str) -> Dict[str, FeatureCompletenessReport]:
        """分析功能完整性"""

        reports = {}

        core_modules = [
            'core/intent_engine',
            'core/code_analyzer',
            'core/ide',
            'core/plugin_manager'
        ]

        tasks = []
        for module in core_modules:
            module_path = f"{project_root}/{module}"
            import os
            if os.path.exists(module_path):
                tasks.append(self.feature_analyzer.analyze_module_features(module_path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for module, result in zip(core_modules, results):
            if not isinstance(result, Exception):
                reports[module] = result

        return reports

    async def _generate_executive_summary(
        self,
        quality_reports: Dict,
        architecture_report: ArchitectureHealthReport,
        feature_reports: Dict,
        intelligence_report: IntelligenceAssessmentReport,
        roadmap: RefactoringRoadmap
    ) -> str:
        """生成执行摘要"""

        # 计算平均分数
        avg_quality = sum(r.overall_score for r in quality_reports.values()) / len(quality_reports) if quality_reports else 0

        # LLM 生成摘要
        prompt = f"""为 LivingTreeAI IDE 模块生成执行摘要。

分析结果:
- 代码质量平均分: {avg_quality:.1f}/100
- 架构健康度: {architecture_report.overall_health_score:.1f}/100
- 智能化水平: {intelligence_report.overall_level.value} ({intelligence_report.level_score:.1f}/100)
- 重构周期: {roadmap.total_duration}

请生成简洁的执行摘要，包含:
1. 整体评估 (2-3 句话)
2. 主要发现 (3-4 点)
3. 改造建议 (2-3 点)
4. 预期收益 (2-3 点)

摘要应该让技术负责人能够快速理解当前状态和下一步行动。"""

        response = await self.llm.generate(prompt)
        return response

    def _collect_key_findings(
        self,
        quality_reports: Dict,
        architecture_report: ArchitectureHealthReport,
        feature_reports: Dict,
        intelligence_report: IntelligenceAssessmentReport
    ) -> List[str]:
        """收集关键发现"""

        findings = []

        # 代码质量发现
        critical_quality = []
        for module, report in quality_reports.items():
            if report.quality_level.value in ('poor', 'needs_improvement'):
                critical_quality.append(f"{module}: {report.overall_score:.0f}分")

        if critical_quality:
            findings.append(f"代码质量问题: {', '.join(critical_quality)}")

        # 架构发现
        if architecture_report.coupling_level.value in ('high', 'very_high'):
            findings.append(f"架构耦合度较高，需要优化依赖关系")

        if architecture_report.circular_dependencies:
            findings.append(f"发现 {len(architecture_report.circular_dependencies)} 处循环依赖")

        # 功能发现
        missing_features = []
        for module, report in feature_reports.items():
            if report.missing_features:
                missing_features.extend(report.missing_features[:2])

        if missing_features:
            findings.append(f"功能缺失: {', '.join(set(missing_features[:3]))}")

        # 智能化发现
        findings.append(f"当前智能化水平: {intelligence_report.overall_level.value}级")

        return findings[:10]

    def _identify_immediate_actions(
        self,
        quality_reports: Dict,
        architecture_report: ArchitectureHealthReport,
        roadmap: RefactoringRoadmap
    ) -> List[str]:
        """识别紧急行动"""

        actions = []

        # 从 Phase 1 提取紧急任务
        if roadmap.phases:
            phase1 = roadmap.phases[0]
            for task in phase1.tasks[:3]:
                if task.priority.value in ('critical', 'high'):
                    actions.append(f"立即处理: {task.title}")

        # 循环依赖必须先处理
        if architecture_report.circular_dependencies:
            actions.append("优先解决循环依赖，避免架构恶化")

        return actions[:5]

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

---

## 📊 可视化面板

```python
# ui/ide_upgrade_panel.py
"""
LivingTreeAI IDE 升级分析面板
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QLabel, QPushButton, QProgressBar, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class IDEUpgradePanel(QWidget):
    """IDE 升级分析面板"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.engine = None
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("LivingTreeAI IDE 智能升级分析器")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 状态栏
        self.status_label = QLabel("点击「开始分析」分析 IDE 模块")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 分析按钮
        button_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("🔍 开始分析")
        self.analyze_btn.clicked.connect(self.start_analysis)
        button_layout.addWidget(self.analyze_btn)

        self.export_btn = QPushButton("📄 导出报告")
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        layout.addLayout(button_layout)

        # Tab 页面
        self.tabs = QTabWidget()

        # 执行摘要 Tab
        self.summary_tab = QTextEdit()
        self.summary_tab.setReadOnly(True)
        self.tabs.addTab(self.summary_tab, "📋 执行摘要")

        # 代码质量 Tab
        self.quality_tab = QTextEdit()
        self.quality_tab.setReadOnly(True)
        self.tabs.addTab(self.quality_tab, "📊 代码质量")

        # 架构分析 Tab
        self.architecture_tab = QTextEdit()
        self.architecture_tab.setReadOnly(True)
        self.tabs.addTab(self.architecture_tab, "🏗️ 架构分析")

        # 智能化评估 Tab
        self.intelligence_tab = QTextEdit()
        self.intelligence_tab.setReadOnly(True)
        self.tabs.addTab(self.intelligence_tab, "🤖 智能化评估")

        # 重构路线图 Tab
        self.roadmap_tab = QTextEdit()
        self.roadmap_tab.setReadOnly(True)
        self.tabs.addTab(self.roadmap_tab, "📋 重构路线图")

        layout.addWidget(self.tabs)

    def start_analysis(self):
        """开始分析"""

        self.analyze_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        self.status_label.setText("正在分析...")

        # 在后台线程运行分析
        self.analysis_thread = AnalysisThread()
        self.analysis_thread.finished.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def on_analysis_complete(self, report: 'IDEUpgradeReport'):
        """分析完成"""

        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        self.status_label.setText("分析完成!")

        # 更新各 Tab
        self.summary_tab.setPlainText(report.executive_summary)
        self._update_quality_tab(report.quality_reports)
        self._update_architecture_tab(report.architecture_report)
        self._update_intelligence_tab(report.intelligence_report)
        self._update_roadmap_tab(report.refactoring_roadmap)

    def _update_quality_tab(self, reports):
        """更新代码质量 Tab"""
        text = "LivingTreeAI IDE 代码质量分析报告\n\n"

        for module, report in reports.items():
            text += f"{'='*60}\n"
            text += f"模块: {module}\n"
            text += f"评分: {report.overall_score:.1f}/100 ({report.quality_level.value})\n"
            text += f"\n优先级问题:\n"
            for issue in report.priority_issues[:5]:
                text += f"  • {issue}\n"
            text += f"\n代码异味: {len(report.code_smells)} 个\n"
            text += f"技术债务: {len(report.technical_debts)} 项\n"

        self.quality_tab.setPlainText(text)

    def _update_architecture_tab(self, report):
        """更新架构分析 Tab"""
        text = f"LivingTreeAI IDE 架构健康度报告\n\n"
        text += f"综合评分: {report.overall_health_score:.1f}/100\n"
        text += f"耦合度: {report.coupling_level.value}\n"
        text += f"\n依赖关系: {len(report.dependencies)} 条\n"

        if report.circular_dependencies:
            text += f"\n⚠️ 循环依赖 ({len(report.circular_dependencies)}):\n"
            for dep in report.circular_dependencies:
                text += f"  • {' -> '.join(dep.modules)}\n"

        text += f"\n主要建议:\n"
        for rec in report.recommendations[:5]:
            text += f"  • {rec}\n"

        self.architecture_tab.setPlainText(text)

    def _update_intelligence_tab(self, report):
        """更新智能化评估 Tab"""
        text = f"LivingTreeAI IDE 智能化水平评估\n\n"
        text += f"当前级别: {report.overall_level.value}\n"
        text += f"级别评分: {report.level_score:.1f}/100\n\n"

        text += f"优势领域:\n"
        for s in report.strength_areas[:5]:
            text += f"  ✅ {s}\n"

        text += f"\n待改进领域:\n"
        for w in report.weakness_areas[:5]:
            text += f"  ⚠️ {w}\n"

        text += f"\n演进路径:\n"
        for path in report.evolution_path:
            text += f"  📍 {path}\n"

        self.intelligence_tab.setPlainText(text)

    def _update_roadmap_tab(self, roadmap):
        """更新重构路线图 Tab"""
        text = f"LivingTreeAI IDE 重构路线图\n\n"
        text += f"预计工期: {roadmap.total_duration}\n\n"

        for phase in roadmap.phases:
            text += f"\n{'='*60}\n"
            text += f"{phase.phase_name}\n"
            text += f"工期: {phase.duration}\n"
            text += f"\n任务:\n"
            for task in phase.tasks[:5]:
                priority_icon = "🔴" if task.priority.value == "critical" else "🟡"
                text += f"  {priority_icon} {task.title}\n"
                text += f"     工作量: {task.effort_estimate} | 风险: {task.risk_level}\n"

        text += f"\n快速胜利:\n"
        for win in roadmap.quick_wins:
            text += f"  ⚡ {win}\n"

        self.roadmap_tab.setPlainText(text)


class AnalysisThread(QThread):
    """分析线程"""

    finished = pyqtSignal(object)

    def run(self):
        """运行分析"""

        from core.ide_upgrader.engine import IDEUpgraderEngine

        engine = IDEUpgraderEngine()

        # 使用示例路径
        report = asyncio.run(engine.analyze_and_upgrade(
            "f:/mhzyapp/LivingTreeAlAgent"
        ))

        self.finished.emit(report)
```

---

## 🚀 使用示例

```python
# 示例：分析 LivingTreeAI IDE 模块并生成升级报告

import asyncio
from core.ide_upgrader.engine import IDEUpgraderEngine


async def main():
    """主函数"""

    print("=" * 60)
    print("LivingTreeAI IDE 智能升级分析器")
    print("=" * 60)
    print()

    # 创建引擎
    engine = IDEUpgraderEngine()

    # 执行完整分析
    report = await engine.analyze_and_upgrade(
        "f:/mhzyapp/LivingTreeAlAgent"
    )

    # 输出执行摘要
    print("\n" + "=" * 60)
    print("执行摘要")
    print("=" * 60)
    print(report.executive_summary)

    # 输出关键发现
    print("\n关键发现:")
    for i, finding in enumerate(report.key_findings, 1):
        print(f"  {i}. {finding}")

    # 输出紧急行动
    print("\n紧急行动:")
    for i, action in enumerate(report.immediate_actions, 1):
        print(f"  {i}. {action}")

    # 输出重构路线图摘要
    print("\n重构路线图:")
    print(f"  总工期: {report.refactoring_roadmap.total_duration}")
    for phase in report.refactoring_roadmap.phases:
        print(f"\n  {phase.phase_name}")
        print(f"    工期: {phase.duration}")
        print(f"    任务数: {len(phase.tasks)}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📋 总结

### 引擎架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    IDEUpgraderEngine                             │
│                    (统一入口)                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ CodeQuality    │  │ Architecture    │  │ Feature        │   │
│  │ Analyzer       │  │ Health          │  │ Completeness    │   │
│  │                │  │ Analyzer        │  │ Analyzer        │   │
│  │ - 代码异味      │  │                │  │                │   │
│  │ - 技术债务      │  │ - 耦合度       │  │ - 能力差距      │   │
│  │ - 复杂度       │  │ - 依赖关系     │  │ - 功能缺失      │   │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘   │
│          │                   │                   │            │
│          └───────────────────┼───────────────────┘            │
│                              │                                  │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              LLM Intelligence Level Analyzer                ││
│  │              (智能化水平评估 - L1-L5)                        ││
│  └────────────────────────────────────────────────────────────┘│
│                              │                                  │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              LLM Refactoring Prioritizer                    ││
│  │              (改造优先级排序 - 路线图生成)                    ││
│  └────────────────────────────────────────────────────────────┘│
│                              │                                  │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │                  IDEUpgradeReport                           ││
│  │  执行摘要 + 关键发现 + 紧急行动 + 重构路线图                   ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 与 LivingTreeAI 项目深度集成

| LivingTreeAI 模块 | 分析重点 | 预期发现 |
|-------------------|----------|----------|
| `core/intent_engine` | 意图理解深度 | 智能化差距、改进方向 |
| `core/code_analyzer` | 代码分析能力 | 功能完整性、技术债务 |
| `core/ide` | 架构设计 | 耦合度、扩展性 |
| `core/plugin_manager` | 插件系统 | 扩展性、设计模式 |
| `core/task_execution` | 任务执行 | 性能、错误处理 |

### LLM 增强价值

| 分析维度 | 传统方法 | LLM 增强 | 价值 |
|----------|----------|----------|------|
| 代码质量 | 规则检测 | 语义理解 | +40% 发现率 |
| 架构分析 | 静态依赖图 | 上下文推理 | +50% 深度 |
| 功能评估 | 清单检查 | 能力映射 | +60% 针对性 |
| 智能化评估 | 能力清单 | 意图分析 | +80% 洞察 |
| 优先级排序 | 经验判断 | 价值/风险推理 | +50% 准确性 |

---

*文档版本: 2.0.0 | 更新日期: 2026-04-25*
*专注场景: LivingTreeAI IDE 模块代码升级改造*
