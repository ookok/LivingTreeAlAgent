# Project Matcher - 项目匹配度分析引擎

## 概述

项目匹配度分析器是一个三层认知匹配系统，用于比较 GitHub 项目与本地项目的匹配程度，输出量化的匹配度评分和可操作的迁移建议。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ProjectMatcherEngine                          │
├─────────────────────────────────────────────────────────────────┤
│  输入: GitHub URL + 本地路径                                     │
│       ↓                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            ProjectAnalyzer (信息采集)                    │    │
│  │  GitHubAnalyzer ← GitHub API + README + 文件结构         │    │
│  │  LocalAnalyzer  ← 本地代码 + 依赖 + 架构                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│       ↓                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              三层匹配引擎                                 │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │ [表层] SurfaceMatcher     技术栈、依赖、文件结构  权重30% │    │
│  │ [结构] ArchitecturalMatcher 架构模式、组件组织   权重40% │    │
│  │ [语义] SemanticMatcher     业务功能、用户需求     权重30% │    │
│  └─────────────────────────────────────────────────────────┘    │
│       ↓                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        ComprehensiveEvaluator (综合评估)                  │    │
│  │  • 加权评分                                             │    │
│  │  • 迁移建议生成                                         │    │
│  │  • 风险预警                                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│       ↓                                                          │
│  输出: 匹配度报告 + 可视化面板                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
core/project_matcher/
├── __init__.py                    # 包初始化
├── project_analyzer.py             # 项目信息采集器
│   ├── GitHubAnalyzer              # GitHub 项目分析
│   └── LocalAnalyzer               # 本地项目分析
├── surface_matcher.py              # 表层技术栈匹配
│   ├── 语言匹配
│   ├── 框架匹配
│   ├── 数据库匹配
│   └── 依赖重叠计算
├── architectural_matcher.py        # 架构模式匹配
│   ├── 架构模式识别
│   ├── 组件相似度计算
│   └── 迁移复杂度评估
├── semantic_matcher.py             # 语义业务匹配
│   ├── 功能覆盖分析
│   ├── 需求满足评估
│   └── 可复用功能提取
├── comprehensive_evaluator.py      # 综合评估引擎
│   ├── 加权评分
│   ├── 迁移建议生成
│   └── 风险预警
└── test_matcher.py                 # 测试脚本

ui/
└── project_match_panel.py          # PyQt6 可视化面板
```

## 使用方法

### 1. Python API

```python
import asyncio
from core.project_matcher import analyze_projects

async def main():
    result = await analyze_projects(
        github_url='https://github.com/user/repo',
        local_path='f:/my-project'
    )
    
    print(f"Total Score: {result.total_score:.1f}")
    print(f"Match Level: {result.match_level.value}")
    print(f"Surface Score: {result.surface_score:.1f}")
    print(f"Architectural Score: {result.architectural_score:.1f}")
    print(f"Semantic Score: {result.semantic_score:.1f}")
    
    # 洞察
    for insight in result.insights:
        print(f"  - {insight}")
    
    # 建议
    for suggestion in result.migration_suggestions:
        print(f"[{suggestion.priority}] {suggestion.title}")
    
    # 风险
    for warning in result.risk_warnings:
        print(f"[{warning.severity}] {warning.message}")

asyncio.run(main())
```

### 2. CLI

```bash
python core/project_matcher/test_matcher.py
```

### 3. GUI 面板

```python
from ui.project_match_panel import create_match_panel

panel = create_match_panel()
panel.show()
```

## 评分体系

### 总体评分

```
Total Score = Surface × 0.30 + Architectural × 0.40 + Semantic × 0.30
```

### 匹配级别

| 级别 | 分数范围 | 建议 |
|------|----------|------|
| Excellent | 80-100 | 可直接复用 |
| Good | 60-80 | 较好匹配 |
| Moderate | 40-60 | 部分匹配，需适配 |
| Poor | 20-40 | 差异较大，参考为主 |
| Incompatible | 0-20 | 不建议迁移 |

### 表层匹配 (30%)

- 编程语言 (30分)
- 框架 (25分)
- 数据库 (15分)
- 依赖重叠 (20分)
- 文件结构 (10分)

### 架构匹配 (40%)

- 架构模式 (40分)
- 组件组织 (35分)
- 通信方式 (15分)
- 设计质量差距 (10分)

### 语义匹配 (30%)

- 功能覆盖 (50%)
- 需求满足 (50%)

## 数据类型

### ProjectData

```python
@dataclass
class ProjectData:
    project_type: ProjectType          # 项目类型
    languages: Set[str]                # 编程语言
    frameworks: Set[str]               # 框架
    databases: Set[str]                 # 数据库
    structure: CodeStructure           # 文件结构
    architecture: ArchitectureInfo      # 架构信息
    business: BusinessInfo             # 业务信息
    dependencies: List[DependencyInfo]  # 依赖
```

### MatchLevel

```python
class MatchLevel(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    INCOMPATIBLE = "incompatible"
```

## 输出示例

```
============================================================
项目匹配度分析报告
============================================================

GitHub 项目: example/ai-ide
  Stars: 5000
  语言: Python

本地项目类型: ide_plugin

总体匹配度: 57.6/100
匹配级别: moderate

分层评分:
  表层技术栈: 59.3%
  架构模式: 61.0%
  语义业务: 51.3%

关键洞察:
  - 两个项目有部分相似，需要适配工作
  - GitHub 项目较受欢迎 (5000 stars)
  - GitHub 独有框架: Transformers, PyQt6

迁移建议:
  [HIGH] 设计参考
    建议参考 GitHub 项目的架构设计，而非直接复制代码
  [LOW] 学习机会 1
    学习 user_management 的最佳实践

风险预警:
  [CRITICAL] 架构迁移复杂度: high
============================================================
```

## 设计原则

1. **模块化** - 每层匹配器独立，可单独测试
2. **可扩展** - 支持添加新的匹配维度和评分规则
3. **实用优先** - 关注可操作的建议，而非纯理论评分
4. **渐进式** - 从简单匹配到深度分析

## TODO

- [ ] 支持更多项目类型分析
- [ ] 添加 CI/CD 配置对比
- [ ] 实现代码相似度检测
- [ ] 添加团队协作评估
- [ ] 集成到主 UI
