# LivingTreeAI Programming OS - 系统性实施方案

> **文档版本**: v1.1  
> **创建日期**: 2026-04-24  
> **更新日期**: 2026-04-24 (范式革命洞察)  
> **愿景来源**: 用户创意提案 + 范式革命思考  
> **项目**: LivingTreeAI Agent  

---

## 🔥 范式革命：重新定义 IDE 的本质

### 传统 IDE vs AI-IDE 的根本差异

| 维度 | 传统 IDE | AI-IDE (我们的目标) |
|------|----------|---------------------|
| **核心假设** | 程序员手写每一行代码 | 程序员表达意图，AI 生成优化代码 |
| **主要输入** | 键盘敲击 | 自然语言意图 |
| **工作流** | 键盘 → 编辑器 → 文件系统 | 意图 → 处理器 → 验证 → 版本控制 |
| **用户关注点** | "怎么写" | "做什么" |
| **文件操作** | 用户手动管理 | AI 自动管理，用户只关心功能 |
| **错误处理** | 用户调试 | AI 自我修复 |

### 🚨 必须抛弃的 6 个传统组件

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         传统 IDE 组件 → AI-IDE 新范式                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ❌ 传统组件                    ✅ AI-IDE 替代                              │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│   1. 文件浏览器                  → 功能模块视图                              │
│      (src/components/...)            (用户认证系统 / 订单管理)               │
│                                                                             │
│   2. 代码编辑器                  → 意图工作台                                │
│      (主要创作窗口)                  (需求描述 / 方案对比 / 预览)            │
│                                                                             │
│   3. 命令行终端                  → 自然语言执行                               │
│      (npm run dev)                   ("启动开发服务器")                      │
│                                                                             │
│   4. Git 手动操作               → 变更容器                                   │
│      (git add/commit/merge)          (AI 自动追踪，一键应用/撤销)             │
│                                                                             │
│   5. 测试运行                   → 质量管道                                   │
│      (pytest / npm test)             (自动运行，质量报告)                    │
│                                                                             │
│   6. 配置文件/设置菜单           → 自动检测 + 意图配置                        │
│      (.eslintrc, webpack)             ("用 TypeScript" → AI 应用配置)        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 🎯 核心范式：意图处理器架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI-IDE 核心架构：意图处理器                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                         ┌─────────────────────┐                            │
│                         │     用户意图输入      │                            │
│                         │  自然语言 / 语音 /   │                            │
│                         │  草图 / 代码选中     │                            │
│                         └──────────┬──────────┘                            │
│                                    │                                       │
│                                    ▼                                       │
│                    ┌───────────────────────────────┐                       │
│                    │      意图理解层 (Intent)       │                       │
│                    │  ┌─────────────────────────┐  │                       │
│                    │  │ • 意图分类              │  │                       │
│                    │  │ • 实体识别              │  │                       │
│                    │  │ • 约束提取              │  │                       │
│                    │  │ • 技术栈推断            │  │                       │
│                    │  │ • 质量要求              │  │                       │
│                    │  └─────────────────────────┘  │                       │
│                    └───────────────┬───────────────┘                       │
│                                    │                                       │
│                                    ▼                                       │
│                    ┌───────────────────────────────┐                       │
│                    │      策略规划层 (Strategy)      │                       │
│                    │  ┌─────────────────────────┐  │                       │
│                    │  │ • 任务分解 (DAG)       │  │                       │
│                    │  │ • 资源分配             │  │                       │
│                    │  │ • 执行顺序规划         │  │                       │
│                    │  │ • 依赖分析             │  │                       │
│                    │  └─────────────────────────┘  │                       │
│                    └───────────────┬───────────────┘                       │
│                                    │                                       │
│                                    ▼                                       │
│                    ┌───────────────────────────────┐                       │
│                    │      代码生成层 (Generate)      │                       │
│                    │  ┌─────────────────────────┐  │                       │
│                    │  │ • 多路径并行生成        │  │                       │
│                    │  │ • 方案对比              │  │                       │
│                    │  │ • 模板填充              │  │                       │
│                    │  │ • 架构合规校验          │  │                       │
│                    │  └─────────────────────────┘  │                       │
│                    └───────────────┬───────────────┘                       │
│                                    │                                       │
│                                    ▼                                       │
│                    ┌───────────────────────────────┐                       │
│                    │      质量验证层 (Quality)       │                       │
│                    │  ┌─────────────────────────┐  │                       │
│                    │  │ • 语法检查              │  │                       │
│                    │  │ • 类型检查              │  │                       │
│                    │  │ • 安全扫描              │  │                       │
│                    │  │ • 性能预检              │  │                       │
│                    │  │ • 测试生成 + 运行        │  │                       │
│                    │  │ • 风格一致性            │  │                       │
│                    │  └─────────────────────────┘  │                       │
│                    └───────────────┬───────────────┘                       │
│                                    │                                       │
│                                    ▼                                       │
│                    ┌───────────────────────────────┐                       │
│                    │      变更管理层 (Change)       │                       │
│                    │  ┌─────────────────────────┐  │                       │
│                    │  │ • VFS 草稿区            │  │                       │
│                    │  │ • 变更容器              │  │                       │
│                    │  │ • 快照回滚              │  │                       │
│                    │  │ • 部署预览              │  │                       │
│                    │  └─────────────────────────┘  │                       │
│                    └───────────────────────────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

用户的"编程操作系统"愿景具有极高的战略价值。经过对现有架构的深度分析，我发现：

| 评估维度 | 状态 | 说明 |
|---------|------|------|
| **核心循环** | ✅ 完整 | ReflectiveAgentLoop 已实现 |
| **多路径探索** | ✅ 完整 | MultiPathExplorer 已实现 |
| **世界模型** | ✅ 完整 | WorldModelSimulator 已实现 |
| **错误处理** | ✅ 完整 | ErrorHandlerRegistry 已实现 |
| **集体智能** | ✅ 完整 | CollectiveIntelligence 已实现 |
| **IDE增强** | ⚠️ 基础 | ide_enhancer.py 需大幅增强 |
| **沙盘环境** | ⚠️ 基础 | sandbox_runtimes.py 需集成 |
| **VFS层** | ❌ 缺失 | **需要新增** |
| **架构守护者** | ❌ 缺失 | **需要新增** |
| **依赖图谱** | ❌ 缺失 | **需要新增** |
| **安全分级** | ❌ 缺失 | **需要新增** |
| **因果链调试** | ❌ 缺失 | **需要新增** |

---

## 🎯 愿景与架构映射

### 用户愿景 → 现有能力 → 实施计划

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Programming OS 愿景架构                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    交互革命层 (Phase 3)                               │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                   │   │
│  │  │  意图草图    │ │  代码沙盘    │ │  语音/手势    │                   │   │
│  │  │  (Sketch)    │ │  (Sandbox)   │ │  编程层       │                   │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                   │   │
│  │         ↓                ↓                ↓                          │   │
│  │  core/ide_enhancer   core/sandbox    core/multimodal                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    协作扩展层 (Phase 2)                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │   │
│  │  │ 多会话进程   │ │ RAG私有知识库│ │ 架构守护者   │ │ 竞品代码对比 │   │   │
│  │  │ 管理        │ │             │ │ (Guard)     │ │              │   │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │   │
│  │         ↓                ↓                ↓                ↓        │   │
│  │  HermesAgent   fusion_rag/    archon/       expert_learning/         │   │
│  │  (增强)       knowledge_vec  (新增)        multi_model              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    稳定内核层 (Phase 1) ⭐ 当前重点                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │   │
│  │  │  意图识别   │ │  VFS虚拟    │ │  安全分级   │ │  因果链     │   │   │
│  │  │  (Intent)   │ │  文件系统   │ │  权限控制   │ │  调试器     │   │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │   │
│  │         ↓                ↓                ↓                ↓        │   │
│  │  ChatIntent    virtual_fs/     permission/    causal_debug/          │   │
│  │  Classifier    (新增)          engine/        (新增)                 │   │
│  │                               (新增)                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    基础支撑层 (已有)                                  │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │   │
│  │  │ 反思式执行  │ │ 多路径探索  │ │ 世界模型   │ │ 集体智能   │   │   │
│  │  │ Reflective  │ │ MultiPath   │ │ WorldModel │ │ Collective  │   │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │   │
│  │         ↓                ↓                ↓                ↓        │   │
│  │  reflective_   multi_path_    world_model_  collective_               │   │
│  │  agent/       explorer/     simulator/    intelligence/              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 大型工程性能优化：上下文经济学

> **核心理念**: 不要追求"全知全能"，而是"按需加载"

### 核心矛盾

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         无限上下文 vs 有限资源                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   📈 代码库增长                    📉 可用资源                               │
│   ──────────────                   ──────────────                            │
│   │                               │                                         │
│   │ 1000 文件                     │  LLM 上下文窗口 (32K-128K)              │
│   │ 10万 行代码                   │  Token 成本                             │
│   │ 100+ 依赖                     │  网络延迟                                │
│   │ ...                           │  内存限制                               │
│   │                               │                                         │
│   └───────────────────────────────┴─────────────────────────────────────     │
│                                                                             │
│   ❌ 问题: AI 无法一次性理解整个代码库                                       │
│   ✅ 解决: 精准加载"当前任务"相关的局部上下文                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. 分层级上下文管理 (Context Triage)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         意图类型 → 上下文策略                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  意图类型           上下文策略              加载内容                          │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  局部修改           仅当前文件 + 接口定义     • 当前 .py/.js 文件              │
│                                       • 导入的接口/类型                      │
│                                       • 忽略: 第三方库、测试文件             │
│                                                                             │
│  模块级             当前模块 + 依赖图        • UserService 及其直接依赖       │
│                                       • API 接口定义                        │
│                                       • DTO/Schema                          │
│                                                                             │
│  架构级             关键抽象层 + 配置        • 目录结构                       │
│                                       • 核心接口                            │
│                                       • 配置文件                            │
│                                                                             │
│  代码审查           变更集 + 影响分析        • Diff 内容                      │
│                                       • 受影响的模块列表                    │
│                                       • 相关测试用例                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```python
# core/context_triage/ (新增)

"""
分层级上下文管理器

根据意图类型，动态决定"看什么"
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from enum import Enum
import hashlib

class ContextLevel(Enum):
    """上下文层级"""
    LOCAL = "local"           # 局部：单个文件
    MODULE = "module"         # 模块级
    ARCHITECTURE = "arch"     # 架构级
    REVIEW = "review"         # 审查级
    GLOBAL = "global"         # 全局（最后手段）

@dataclass
class ContextBudget:
    """
    上下文预算
    
    为每次请求设定 Token 上限
    """
    max_tokens: int = 8192        # 默认 8K Token
    max_files: int = 10           # 最多加载文件数
    max_lines_per_file: int = 500 # 每文件最多行数
    
    # 优先级排序
    priority_order: List[str] = field(default_factory=lambda: [
        "interface",      # 接口定义优先
        "type_def",      # 类型定义
        "config",         # 配置
        "core_logic",     # 核心逻辑
        "test",          # 测试文件
        "third_party",   # 第三方（最后）
    ])

@dataclass
class ContextChunk:
    """上下文块"""
    file_path: str
    content: str
    chunk_type: str           # "interface" / "implementation" / "test"
    token_count: int
    relevance_score: float    # 与当前意图的相关性
    lines: tuple[int, int]   # 行号范围

class ContextTriageEngine:
    """
    上下文分诊引擎
    
    核心决策：根据意图，决定加载哪些上下文
    
    使用示例：
    ```python
    triage = ContextTriageEngine(project_root)
    
    # 用户说"修改用户登录逻辑"
    intent = await intent_engine.parse("修改用户登录逻辑")
    
    # 获取精准上下文
    context = await triage.triage(
        intent=intent,
        budget=ContextBudget(max_tokens=8192)
    )
    
    # 仅返回相关文件，而非整个项目
    print(context.loaded_files)  # ['auth/login.py', 'auth/schemas.py']
    ```
    """
    
    def __init__(
        self,
        project_root: str,
        symbol_index: 'SymbolIndex',
        dependency_graph: 'DependencyGraph'
    ):
        self.project_root = project_root
        self.symbol_index = symbol_index
        self.dependency_graph = dependency_graph
        
        # 文件类型优先级
        self.file_priority = {
            "interface": 1,
            "type": 1,
            "schema": 1,
            "model": 2,
            "service": 2,
            "controller": 3,
            "config": 3,
            "test": 4,
            "util": 5,
            "third_party": 10,
        }
    
    async def triage(
        self,
        intent: 'ParsedIntent',
        budget: ContextBudget
    ) -> List[ContextChunk]:
        """
        上下文分诊
        
        1. 分析意图类型
        2. 确定需要加载的文件范围
        3. 按优先级填充预算
        """
        chunks: List[ContextChunk] = []
        total_tokens = 0
        
        # 1. 确定目标文件
        target_files = await self._find_target_files(intent)
        
        # 2. 确定依赖文件
        dependency_files = []
        for file in target_files:
            deps = await self.dependency_graph.get_direct_dependencies(file)
            dependency_files.extend(deps)
        
        # 3. 合并并排序
        all_files = self._merge_and_sort_files(
            target_files, 
            dependency_files,
            budget
        )
        
        # 4. 加载文件内容（遵守预算）
        for file_path in all_files:
            if total_tokens >= budget.max_tokens:
                break
            if len(chunks) >= budget.max_files:
                break
            
            chunk = await self._load_file_chunk(file_path, intent, budget)
            if chunk:
                chunks.append(chunk)
                total_tokens += chunk.token_count
        
        return chunks
    
    async def _find_target_files(
        self, 
        intent: 'ParsedIntent'
    ) -> List[str]:
        """根据意图找到目标文件"""
        # 使用符号索引快速定位
        symbol_name = intent.target_name
        
        files = await self.symbol_index.find_files_containing(symbol_name)
        
        # 如果没找到，尝试路径推断
        if not files:
            inferred_path = self._infer_path(intent)
            files = [inferred_path] if inferred_path else []
        
        return files
    
    def _merge_and_sort_files(
        self,
        targets: List[str],
        dependencies: List[str],
        budget: ContextBudget
    ) -> List[str]:
        """合并并按优先级排序"""
        # 去重
        all_files = list(set(targets + dependencies))
        
        # 优先级排序
        def file_priority(file_path: str) -> tuple[int, int]:
            # 第一优先级：类型
            ext_priority = self.file_priority.get(
                self._get_file_semantic_type(file_path), 5
            )
            # 第二优先级：是否在目标列表
            target_priority = 0 if file_path in targets else 1
            return (ext_priority, target_priority)
        
        return sorted(all_files, key=file_priority)
    
    async def _load_file_chunk(
        self,
        file_path: str,
        intent: 'ParsedIntent',
        budget: ContextBudget
    ) -> Optional[ContextChunk]:
        """加载文件块（可截断）"""
        from pathlib import Path
        
        full_path = Path(self.project_root) / file_path
        if not full_path.exists():
            return None
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 如果文件太大，截断到必要部分
        if total_lines > budget.max_lines_per_file:
            # 找到与意图最相关的部分
            relevant_range = self._find_relevant_range(lines, intent)
            content = '\n'.join(lines[relevant_range[0]:relevant_range[1]])
        else:
            relevant_range = (0, total_lines)
        
        # 计算 Token（简单估计：1 Token ≈ 4 字符）
        token_count = len(content) // 4
        
        return ContextChunk(
            file_path=file_path,
            content=content,
            chunk_type=self._get_file_semantic_type(file_path),
            token_count=token_count,
            relevance_score=1.0 if file_path in intent.context_used.get('targets', []) else 0.5,
            lines=relevant_range
        )
    
    def _find_relevant_range(
        self,
        lines: List[str],
        intent: 'ParsedIntent'
    ) -> tuple[int, int]:
        """找到与意图最相关的代码范围"""
        target = intent.target_name.lower()
        
        for i, line in enumerate(lines):
            if target in line.lower():
                # 找到相关行，扩展上下文
                start = max(0, i - 10)
                end = min(len(lines), i + 50)
                return (start, end)
        
        # 没找到，返回开头部分
        return (0, min(len(lines), 200))
    
    def _infer_path(self, intent: 'ParsedIntent') -> Optional[str]:
        """推断文件路径"""
        # 基于意图推断可能路径
        path_map = {
            "page": "pages/",
            "component": "components/",
            "api": "api/",
            "service": "services/",
            "model": "models/",
        }
        prefix = path_map.get(intent.target_type, "")
        name = intent.target_name.replace(" ", "_").lower()
        return f"{prefix}{name}"
```

### 2. 语义索引系统 (Symbol Index)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         语义索引 vs 全文检索                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  全文检索 (grep)                    语义索引                                  │
│  ─────────────────                   ──────────                              │
│                                                                             │
│  "调用用户服务"                    "调用用户服务"                             │
│       ↓                                 ↓                                  │
│  grep "用户服务"                   查 Symbol Index                          │
│       ↓                                 ↓                                  │
│  搜索所有文件                       直接定位:                                │
│  耗时: O(n * m)                    - UserService.java                     │
│  n=文件数, m=文件大小              - location: src/services/UserService.java│
│                                   耗时: O(1)                                │
│                                                                             │
│  ❌ 每次都要扫描整个代码库         ✅ 预建索引，即时查找                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```python
# core/semantic_index/ (新增)

"""
语义索引系统

O(1) 符号查找，替代全文检索
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import ast

@dataclass
class Symbol:
    """符号"""
    name: str
    symbol_type: str              # "class" / "function" / "interface" / "method"
    file_path: str
    line: int
    end_line: int
    signature: str = ""          # 函数签名
    docstring: str = ""
    imports: List[str] = field(default_factory=list)
    exported: bool = True

@dataclass
class SymbolIndex:
    """
    符号索引
    
    预建函数名、类名、接口的映射表
    支持 O(1) 的符号查找
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._symbols: Dict[str, List[Symbol]] = {}  # name -> symbols
        self._file_symbols: Dict[str, List[str]] = {}  # file -> symbol names
        self._type_index: Dict[str, List[str]] = {}   # type -> symbol names
        
        self._last_build: Optional[datetime] = None
    
    def build_index(self, languages: List[str] = None):
        """
        构建索引
        
        遍历项目文件，提取所有符号
        """
        languages = languages or ["py", "js", "ts", "java", "go"]
        
        for ext in languages:
            for file_path in self.project_root.rglob(f"*.{ext}"):
                # 跳过第三方库
                if self._is_third_party(file_path):
                    continue
                
                self._index_file(file_path)
        
        self._last_build = datetime.now()
    
    def _index_file(self, file_path: Path):
        """索引单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            rel_path = str(file_path.relative_to(self.project_root))
            symbols = self._extract_symbols(content, file_path.suffix, rel_path)
            
            # 存储
            self._file_symbols[rel_path] = [s.name for s in symbols]
            
            for symbol in symbols:
                if symbol.name not in self._symbols:
                    self._symbols[symbol.name] = []
                self._symbols[symbol.name].append(symbol)
                
                # 类型索引
                if symbol.symbol_type not in self._type_index:
                    self._type_index[symbol.symbol_type] = []
                self._type_index[symbol.symbol_type].append(symbol.name)
        
        except Exception as e:
            pass  # 忽略无法解析的文件
    
    def _extract_symbols(
        self, 
        content: str, 
        ext: str,
        file_path: str
    ) -> List[Symbol]:
        """提取符号"""
        symbols = []
        
        if ext == ".py":
            symbols = self._extract_python_symbols(content, file_path)
        elif ext in [".js", ".ts", ".jsx", ".tsx"]:
            symbols = self._extract_js_symbols(content, file_path)
        elif ext == ".java":
            symbols = self._extract_java_symbols(content, file_path)
        
        return symbols
    
    def _extract_python_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """提取 Python 符号"""
        symbols = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append(Symbol(
                        name=node.name,
                        symbol_type="class",
                        file_path=file_path,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=ast.get_docstring(node) or ""
                    ))
                elif isinstance(node, ast.FunctionDef):
                    # 只记录顶层函数
                    symbols.append(Symbol(
                        name=node.name,
                        symbol_type="function",
                        file_path=file_path,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        signature=self._get_func_signature(node)
                    ))
        except:
            pass
        
        return symbols
    
    def _extract_js_symbols(self, content: str, file_path: str) -> List[Symbol]:
        """提取 JS/TS 符号"""
        symbols = []
        
        # 类声明
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{'
        for match in re.finditer(class_pattern, content):
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type="class",
                file_path=file_path,
                line=content[:match.start()].count('\n') + 1,
                end_line=0
            ))
        
        # 函数声明
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, content):
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type="function",
                file_path=file_path,
                line=content[:match.start()].count('\n') + 1,
                end_line=0
            ))
        
        # 组件 (React)
        comp_pattern = r'function\s+(\w+[A-Z]\w*)\s*\('
        for match in re.finditer(comp_pattern, content):
            symbols.append(Symbol(
                name=match.group(1),
                symbol_type="component",
                file_path=file_path,
                line=content[:match.start()].count('\n') + 1,
                end_line=0
            ))
        
        return symbols
    
    def find_files_containing(self, symbol_name: str) -> List[str]:
        """
        查找包含符号的文件
        
        O(1) 查找
        """
        symbols = self._symbols.get(symbol_name, [])
        return list(set([s.file_path for s in symbols]))
    
    def find_by_prefix(self, prefix: str) -> List[Symbol]:
        """
        前缀搜索
        
        例如: "User" → ["UserService", "UserController", "UserModel"]
        """
        results = []
        for name, symbols in self._symbols.items():
            if name.lower().startswith(prefix.lower()):
                results.extend(symbols)
        return results
    
    def find_by_type(self, symbol_type: str) -> List[Symbol]:
        """按类型查找"""
        names = self._type_index.get(symbol_type, [])
        results = []
        for name in names:
            results.extend(self._symbols.get(name, []))
        return results
    
    def _is_third_party(self, path: Path) -> bool:
        """判断是否是第三方库"""
        third_party_dirs = [
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
            ".next",
            "vendor",
        ]
        return any(part in path.parts for part in third_party_dirs)
    
    def save(self, path: Optional[str] = None):
        """保存索引"""
        path = path or str(self.project_root / ".symbol_index.json")
        
        data = {
            "symbols": {
                name: [
                    {"name": s.name, "type": s.symbol_type, 
                     "file": s.file_path, "line": s.line}
                    for s in symbols
                ]
                for name, symbols in self._symbols.items()
            },
            "last_build": self._last_build.isoformat() if self._last_build else None
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load(self, path: Optional[str] = None) -> bool:
        """加载索引"""
        path = path or str(self.project_root / ".symbol_index.json")
        
        if not Path(path).exists():
            return False
        
        # 增量构建而非加载（索引需要实时更新）
        return False
```

### 3. 意图感知的索引预热

```python
# core/intent_aware_cache/ (新增)

"""
意图感知缓存系统

核心思想：
- 高频意图 → 预热对应索引
- 意图结果 → 边缘缓存
"""

from typing import Dict, Optional
from dataclasses import dataclass
import hashlib
import time

@dataclass
class CachedIntent:
    """缓存的意图结果"""
    intent_key: str
    code_template: str
    created_at: float
    hit_count: int = 0
    ttl: int = 86400  # 24小时

class IntentAwareCache:
    """
    意图感知缓存
    
    策略：
    1. 意图结果缓存：相同意图直接返回模板
    2. 索引预热：基于历史意图模式预加载索引
    3. 增量上下文：保留上轮对话的上下文
    """
    
    # 高频意图模板库
    HIGH_FREQUENCY_TEMPLATES = {
        # 代码生成
        "create_crud": "CRUD 操作模板",
        "create_component": "React/Vue 组件模板",
        "create_api": "REST API 模板",
        "create_model": "数据模型模板",
        
        # 修复
        "fix_null_pointer": "空指针检查模板",
        "fix_async": "异步处理模板",
        "fix_error": "错误处理模板",
        
        # 日志
        "add_logging": "日志记录模板",
        "add_metrics": "监控指标模板",
    }
    
    def __init__(self):
        # 意图结果缓存
        self._intent_cache: Dict[str, CachedIntent] = {}
        
        # 增量上下文
        self._incremental_context: Optional[dict] = None
        self._context_ttl: int = 3600  # 1小时
    
    def get_cached_intent(
        self,
        intent_type: str,
        tech_stack: str,
        params_hash: str
    ) -> Optional[str]:
        """
        获取缓存的意图结果
        
        Key: intent_type + tech_stack + params_hash
        """
        key = self._make_intent_key(intent_type, tech_stack, params_hash)
        
        cached = self._intent_cache.get(key)
        if cached:
            # 检查 TTL
            if time.time() - cached.created_at < cached.ttl:
                cached.hit_count += 1
                return cached.code_template
            else:
                # 过期，删除
                del self._intent_cache[key]
        
        return None
    
    def cache_intent(
        self,
        intent_type: str,
        tech_stack: str,
        params_hash: str,
        code_template: str
    ):
        """缓存意图结果"""
        key = self._make_intent_key(intent_type, tech_stack, params_hash)
        
        self._intent_cache[key] = CachedIntent(
            intent_key=key,
            code_template=code_template,
            created_at=time.time()
        )
    
    def _make_intent_key(
        self, 
        intent_type: str, 
        tech_stack: str, 
        params_hash: str
    ) -> str:
        """生成意图缓存 Key"""
        return hashlib.md5(
            f"{intent_type}:{tech_stack}:{params_hash}".encode()
        ).hexdigest()
    
    # === 增量上下文 ===
    
    def update_incremental_context(
        self,
        new_context: dict,
        keep_previous: bool = True
    ):
        """
        更新增量上下文
        
        - keep_previous=True: 保留上轮上下文，累加
        - keep_previous=False: 完全替换
        """
        if keep_previous and self._incremental_context:
            # 合并上下文
            self._incremental_context = self._merge_context(
                self._incremental_context,
                new_context
            )
        else:
            self._incremental_context = new_context
        
        # 更新 TTL
        self._context_ttl = time.time()
    
    def get_incremental_context(self) -> Optional[dict]:
        """获取增量上下文"""
        if self._incremental_context:
            # 检查是否过期
            if time.time() - self._context_ttl > 3600:
                return None
            return self._incremental_context
        return None
    
    def _merge_context(
        self, 
        old: dict, 
        new: dict
    ) -> dict:
        """合并上下文"""
        merged = old.copy()
        
        # 保留上轮的通用上下文
        # 新增本轮的特定上下文
        for key, value in new.items():
            if key not in merged:
                merged[key] = value
        
        return merged
    
    # === 索引预热 ===
    
    def warmup_indexes(
        self,
        recent_intents: list,
        project_context: dict
    ):
        """
        索引预热
        
        基于最近意图模式，提前加载相关索引
        """
        warmup_plan = {
            "symbols": set(),
            "files": set(),
        }
        
        # 分析最近意图
        for intent in recent_intents:
            if "create" in intent or "generate" in intent:
                # 代码生成 → 预热接口规范
                warmup_plan["symbols"].add("interface")
                warmup_plan["symbols"].add("schema")
            
            elif "refactor" in intent or "rebuild" in intent:
                # 重构 → 预热依赖图谱
                warmup_plan["files"].add("dependency_graph")
                warmup_plan["files"].add("test_cases")
            
            elif "fix" in intent or "debug" in intent:
                # 修复 → 预热相关测试
                warmup_plan["files"].add("test_files")
        
        # 执行预热
        # ... (交给索引系统)
```

---

## 📁 MVP: 最小可行产品 (2-3周) ⭐⭐⭐

> **核心理念**: 先做一件事，做极致！不要试图一步到位。

### MVP 定义：意图驱动的组件生成器

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MVP 界面                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │   💬 输入你的需求：                                                  │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │ 做个登录页面，现代简约风格，需要微信登录                      │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  │   [ 🎤 语音输入 ]  [ 📷 草图 ]  [ ⌨️ 键盘输入 ]                    │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────┬───────────────────────────────────────────┐   │
│  │   🧠 AI 思考过程        │   📄 代码预览                              │   │
│  │   ─────────────────     │   ─────────────────                       │   │
│  │                         │                                           │   │
│  │   🔍 理解意图...        │   diff: LoginPage.jsx                    │   │
│  │   ✅ 主操作: 创建       │   + import React from 'react';           │   │
│  │   ✅ 目标: 登录页面     │   + ...                                   │   │
│  │   ✅ 技术栈: React      │   + const LoginPage = () => {             │   │
│  │   ✅ 风格: 现代简约     │   +   return <div>...</div>               │   │
│  │                         │   + };                                    │   │
│  │   📋 任务分解:          │                                           │   │
│  │   ├─ 登录表单组件       │   ─────────────────────────────           │   │
│  │   ├─ 微信登录按钮       │                                           │   │
│  │   ├─ API 接口           │   📊 质量报告:                            │   │
│  │   └─ 样式文件           │   ✅ 语法检查: 通过                        │   │
│  │                         │   ✅ 类型检查: 通过                        │   │
│  │   ⚡ 正在生成代码...     │   ✅ 安全扫描: 通过                        │   │
│  │                         │   ✅ 测试: 自动生成中...                   │   │
│  │                         │                                           │   │
│  └─────────────────────────┴───────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │        [ ❌ 取消 ]                    [ ✅ 应用到项目 ]                │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MVP 核心功能清单

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **意图输入** | P0 | 自然语言描述需求 |
| **意图理解** | P0 | 解析主操作、目标、技术栈 |
| **代码生成** | P0 | 基于模板生成符合规范的代码 |
| **代码预览** | P0 | diff 展示变更内容 |
| **一键应用** | P0 | 确认后写入 VFS |
| **质量报告** | P0 | 语法检查、类型检查、安全扫描 |
| **撤销回滚** | P1 | 支持撤销已应用的变更 |
| **历史记录** | P2 | 查看之前的生成记录 |

### MVP 技术实现路径

```python
# MVP 最小代码量实现

# 1. 意图引擎（复用/简化 IntentEngine）
intent_engine = IntentEngine()

# 2. 模板系统（基于项目已有组件模板）
template_system = ComponentTemplateSystem()

# 3. VFS 草稿区（简化版）
vfs = SimpleDraftVFS(project_root)

# 4. 质量检查（基础版）
quality_checker = BasicQualityChecker()

# 5. UI 界面（单页面应用）
# 使用 Streamlit 或 简单 PyQt6
```

### MVP 验证假设

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            核心验证问题                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  假设 1: 用户是否接受"只描述需求，AI 生成代码"的模式？                         │
│  → 验证方法：用户测试 MVP，记录成功率                                        │
│                                                                             │
│  假设 2: 意图理解的准确率是否足够？                                         │
│  → 验证方法：统计需要澄清的次数                                               │
│                                                                             │
│  假设 3: 生成的代码质量是否可用？                                            │
│  → 验证方法：用户应用率 + 后续修改率                                          │
│                                                                             │
│  假设 4: 用户是否愿意放弃手动编辑？                                          │
│  → 验证方法：手动编辑次数 vs AI 生成应用次数                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Phase 1: 稳定内核 (4-6周)

> **目标**: 构建可靠的核心执行引擎，这是所有高级功能的基础

### 1.1 意图理解引擎 (Intent Engine) ⭐⭐⭐ **核心创新**

这是"意图处理器"的核心！不再简单分类，而是完整理解用户想要什么。

```python
# core/intent_engine/ (新增核心模块)

"""
意图理解引擎

不再只是"对话 vs 编程"的简单分类，
而是对用户意图的完整语义理解。

输入: "做个登录页面，现代简约风格，需要微信登录和邮箱密码"
输出: 完整的结构化意图描述
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import re

class IntentAction(Enum):
    """意图主操作类型"""
    CREATE = "create"           # 创建新功能
    MODIFY = "modify"          # 修改现有
    DELETE = "delete"          # 删除
    QUERY = "query"            # 查询/解释
    REFACTOR = "refactor"      # 重构
    DEBUG = "debug"            # 调试
    DEPLOY = "deploy"          # 部署
    EXPLAIN = "explain"        # 解释
    OPTIMIZE = "optimize"     # 优化
    REVIEW = "review"          # 审查

class TechnologyStack(Enum):
    """技术栈"""
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    NEXTJS = "nextjs"
    NUXT = "nuxt"
    FLUTTER = "flutter"
    REACT_NATIVE = "react_native"
    PYTHON = "python"
    NODE = "node"
    GO = "go"
    RUST = "rust"
    TYPESCRIPT = "typescript"
    PYTHON_FASTAPI = "python_fastapi"
    PYTHON_DJANGO = "python_django"
    UNKNOWN = "unknown"

@dataclass
class IntentConstraint:
    """意图约束"""
    key: str                    # 约束类型
    value: Any                  # 约束值
    confidence: float = 1.0     # 置信度
    source: str = "inferred"   # 来源：explicit/inferred

@dataclass
class QualityRequirements:
    """质量要求"""
    performance: Optional[str] = None    # "A", "B", "high", "low"
    tests_required: bool = True
    accessibility: bool = False
    seo: bool = False
    browser_support: List[str] = field(default_factory=list)

@dataclass
class ParsedIntent:
    """
    解析后的完整意图
    
    这是 Intent Engine 的核心输出结构
    """
    # 主操作
    primary_action: IntentAction
    
    # 目标
    target_name: str                    # "用户登录" / "支付功能"
    target_type: str                    # "component" / "api" / "service" / "page"
    target_path: Optional[str] = None   # AI 推断的路径
    
    # 技术栈推断
    technology: TechnologyStack = TechnologyStack.UNKNOWN
    technology_confidence: float = 0.0
    
    # 风格/约束
    style: Optional[str] = None        # "modern_glass" / "minimalist"
    constraints: List[IntentConstraint] = field(default_factory=list)
    
    # 质量要求
    quality: QualityRequirements = field(default_factory=QualityRequirements)
    
    # 子功能（复合意图）
    sub_intents: List['ParsedIntent'] = field(default_factory=list)
    
    # 澄清需求
    needs_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    
    # 元数据
    confidence: float = 0.0
    raw_input: str = ""
    context_used: Dict[str, Any] = field(default_factory=dict)

class IntentEngine:
    """
    意图理解引擎
    
    核心能力：
    1. 完整的意图解析（不只是分类）
    2. 约束自动推断
    3. 技术栈自动检测
    4. 澄清对话生成
    5. 复合意图分解
    
    使用示例：
    ```python
    engine = IntentEngine(project_context)
    
    # 解析用户意图
    intent = await engine.parse(
        "做个登录页面，现代简约风格"
    )
    
    # 输出结构化意图
    print(intent.primary_action)  # CREATE
    print(intent.target_name)      # "登录页面"
    print(intent.target_type)     # "page"
    print(intent.style)           # "modern_glass"
    
    # 如果需要澄清
    if intent.needs_clarification:
        for q in intent.clarification_questions:
            print(q)  # "需要哪些登录方式？"
    ```
    """
    
    def __init__(self, project_context: Optional[dict] = None):
        self.project_context = project_context or {}
        self.conversation_history: List[ParsedIntent] = []
        
        # 技术栈关键词
        self.tech_keywords = {
            "react": ["react", "reactjs", "jsx"],
            "vue": ["vue", "vuejs", "vue3", "nuxt"],
            "angular": ["angular"],
            "typescript": ["typescript", "ts", "tsx"],
            "python": ["python", "py"],
            "fastapi": ["fastapi"],
            "django": ["django"],
            "flutter": ["flutter"],
            "rust": ["rust", "cargo"],
        }
        
        # 风格关键词
        self.style_keywords = {
            "modern_glass": ["玻璃", "glass", "毛玻璃", "frosted", "现代", "modern"],
            "minimalist": ["极简", "minimal", "简约", "simple", "clean"],
            "material": ["material", "材质", "material design"],
            "brutalist": ["brutalist", "粗野", "大胆"],
            "dark": ["dark", "暗色", "深色", "night"],
        }
        
        # 动作关键词
        self.action_keywords = {
            "create": ["做", "创建", "新建", "生成", "做一个", "add", "create", "new", "make"],
            "modify": ["修改", "改动", "调整", "改变", "修改", "update", "modify", "change"],
            "delete": ["删除", "移除", "去掉", "delete", "remove"],
            "refactor": ["重构", "重写", "优化代码", "refactor"],
            "debug": ["调试", "bug", "修复", "fix"],
            "deploy": ["部署", "发布", "上线", "deploy", "release"],
            "query": ["查询", "搜索", "查找", "query", "search", "find"],
            "explain": ["解释", "说明", "这是什么", "explain", "what is"],
        }
        
        # 约束关键词
        self.constraint_patterns = {
            "responsive": [r"响应式", r"自适应", r"responsive"],
            "accessible": [r"无障碍", r"盲人", r"键盘", r"accessible", r"a11y"],
            "performance": [r"高性能", r"快速", r"performance"],
            "seo": [r"seo", r"搜索引擎", r"优化"],
            "animation": [r"动画", r"动效", r"animation"],
        }
    
    async def parse(
        self,
        user_input: str,
        context: Optional[dict] = None
    ) -> ParsedIntent:
        """
        解析用户意图
        
        完整流程：
        1. 基础分词和清洗
        2. 主操作识别
        3. 目标提取
        4. 技术栈推断
        5. 风格/约束提取
        6. 复合意图检测
        7. 澄清需求判断
        """
        # 合并上下文
        context = {**self.project_context, **(context or {})}
        
        # 1. 基础解析
        tokens = self._tokenize(user_input)
        
        # 2. 识别主操作
        primary_action = self._identify_action(user_input, tokens)
        
        # 3. 提取目标
        target_name, target_type = self._extract_target(user_input, context)
        
        # 4. 推断技术栈
        technology, tech_conf = self._infer_technology(user_input, context)
        
        # 5. 提取风格
        style = self._extract_style(user_input)
        
        # 6. 提取约束
        constraints = self._extract_constraints(user_input)
        
        # 7. 质量要求
        quality = self._extract_quality(user_input, constraints)
        
        # 8. 检测复合意图
        sub_intents = self._detect_compound_intent(user_input)
        
        # 9. 判断是否需要澄清
        needs_clarification, questions = self._check_clarification(
            primary_action, target_type, constraints, quality
        )
        
        # 构建结果
        intent = ParsedIntent(
            primary_action=primary_action,
            target_name=target_name,
            target_type=target_type,
            technology=technology,
            technology_confidence=tech_conf,
            style=style,
            constraints=constraints,
            quality=quality,
            sub_intents=sub_intents,
            needs_clarification=needs_clarification,
            clarification_questions=questions,
            confidence=self._calculate_confidence(
                primary_action, target_name, technology, tech_conf
            ),
            raw_input=user_input,
            context_used=context
        )
        
        # 记录历史
        self.conversation_history.append(intent)
        
        return intent
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单分词：按空格和标点
        tokens = re.split(r'[\s,，。、]+', text)
        return [t for t in tokens if t]
    
    def _identify_action(self, text: str, tokens: List[str]) -> IntentAction:
        """识别主操作"""
        text_lower = text.lower()
        
        for action, keywords in self.action_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return IntentAction(action)
        
        # 默认：如果是"这个"等指代词，可能是修改
        if any(t in text for t in ["这个", "这个功能", "这里", "it", "this"]):
            return IntentAction.MODIFY
        
        # 默认：创建
        return IntentAction.CREATE
    
    def _extract_target(self, text: str, context: dict) -> tuple[str, str]:
        """
        提取目标
        
        推断目标类型：component / api / service / page / model
        """
        text_lower = text.lower()
        
        # 页面类
        page_keywords = ["页面", "page", "界面", "screen", "登录页", "首页", "列表页"]
        for kw in page_keywords:
            if kw in text_lower:
                return self._extract_target_name(text), "page"
        
        # 组件类
        component_keywords = ["组件", "component", "按钮", "表单", "卡片", "modal", "弹窗"]
        for kw in component_keywords:
            if kw in text_lower:
                return self._extract_target_name(text), "component"
        
        # API 类
        api_keywords = ["api", "接口", "endpoint", "rest", "graphql"]
        for kw in api_keywords:
            if kw in text_lower:
                return self._extract_target_name(text), "api"
        
        # Service 类
        service_keywords = ["服务", "service", "service层", "业务逻辑"]
        for kw in service_keywords:
            if kw in text_lower:
                return self._extract_target_name(text), "service"
        
        # 模型类
        model_keywords = ["模型", "model", "数据库表", "entity", "schema"]
        for kw in model_keywords:
            if kw in text_lower:
                return self._extract_target_name(text), "model"
        
        # 默认：根据上下文推断
        if "project_type" in context:
            project_type = context["project_type"]
            if "page" in project_type.lower():
                return self._extract_target_name(text), "page"
        
        return self._extract_target_name(text), "feature"
    
    def _extract_target_name(self, text: str) -> str:
        """提取目标名称"""
        # 去掉动作词
        action_words = ["做个", "创建", "做", "修改", "添加", "做个", "做一个"]
        for word in action_words:
            text = text.replace(word, "")
        
        # 去掉风格词
        style_words = ["现代", "简约", "现代简约", "material", "dark"]
        for word in style_words:
            text = text.replace(word, "")
        
        return text.strip() or "未命名"
    
    def _infer_technology(
        self, 
        text: str, 
        context: dict
    ) -> tuple[TechnologyStack, float]:
        """推断技术栈"""
        text_lower = text.lower()
        
        # 1. 显式提及
        for tech, keywords in self.tech_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return TechnologyStack(tech), 1.0
        
        # 2. 上下文推断
        if "technology" in context:
            tech = context["technology"]
            return TechnologyStack(tech), 0.9
        
        # 3. 项目类型推断
        if "project_type" in context:
            pt = context["project_type"].lower()
            if "react" in pt:
                return TechnologyStack.REACT, 0.8
            elif "vue" in pt:
                return TechnologyStack.VUE, 0.8
            elif "flutter" in pt:
                return TechnologyStack.FLUTTER, 0.8
        
        return TechnologyStack.UNKNOWN, 0.0
    
    def _extract_style(self, text: str) -> Optional[str]:
        """提取风格"""
        text_lower = text.lower()
        
        for style, keywords in self.style_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return style
        
        return None
    
    def _extract_constraints(self, text: str) -> List[IntentConstraint]:
        """提取约束"""
        constraints = []
        text_lower = text.lower()
        
        for constraint_type, patterns in self.constraint_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    constraints.append(IntentConstraint(
                        key=constraint_type,
                        value=True,
                        confidence=1.0,
                        source="explicit"
                    ))
                    break
        
        return constraints
    
    def _extract_quality(
        self, 
        text: str, 
        constraints: List[IntentConstraint]
    ) -> QualityRequirements:
        """提取质量要求"""
        quality = QualityRequirements()
        
        # 从约束推断
        constraint_keys = [c.key for c in constraints]
        
        if "responsive" in constraint_keys:
            quality.accessibility = True
        if "accessible" in constraint_keys:
            quality.accessibility = True
        if "performance" in constraint_keys:
            quality.performance = "high"
        
        # 显式提及
        if "测试" in text or "test" in text.lower():
            quality.tests_required = True
        
        return quality
    
    def _detect_compound_intent(self, text: str) -> List[ParsedIntent]:
        """检测复合意图"""
        # TODO: 实现复合意图分解
        # 例如："登录+注册" → [登录意图, 注册意图]
        return []
    
    def _check_clarification(
        self,
        action: IntentAction,
        target_type: str,
        constraints: List[IntentConstraint],
        quality: QualityRequirements
    ) -> tuple[bool, List[str]]:
        """判断是否需要澄清"""
        questions = []
        
        # 目标不明确
        if target_type == "feature" and action == IntentAction.CREATE:
            questions.append("这个功能是前端组件、后端API、还是完整的服务？")
        
        # 技术栈未知
        if not self.conversation_history:
            # 第一个意图，可能需要澄清技术栈
            questions.append("这个项目用的是什么技术栈？（React/Vue/其他）")
        
        # 质量要求不完整
        if action == IntentAction.CREATE and target_type in ["page", "component"]:
            if not any(c.key == "responsive" for c in constraints):
                questions.append("需要响应式设计吗？")
        
        return len(questions) > 0, questions
    
    def _calculate_confidence(
        self,
        action: IntentAction,
        target: str,
        technology: TechnologyStack,
        tech_conf: float
    ) -> float:
        """计算整体置信度"""
        confidence = 0.5  # 基础置信度
        
        # 目标明确 +0.2
        if target and target != "未命名":
            confidence += 0.2
        
        # 技术栈明确 +0.2
        if technology != TechnologyStack.UNKNOWN:
            confidence += tech_conf * 0.2
        
        # 主操作明确 +0.1
        if action in [IntentAction.CREATE, IntentAction.DELETE]:
            confidence += 0.1
        
        return min(confidence, 1.0)


# core/intent_engine/conversation_manager.py

class ClarificationConversation:
    """
    澄清对话管理器
    
    处理多轮澄清对话
    """
    
    def __init__(self):
        self.pending_intents: Dict[str, ParsedIntent] = {}  # session_id -> intent
        self.conversations: Dict[str, List[dict]] = {}     # session_id -> history
    
    async def process_clarification(
        self,
        session_id: str,
        user_response: str,
        current_intent: ParsedIntent
    ) -> ParsedIntent:
        """
        处理澄清回复
        
        用户回答澄清问题 → 更新意图
        """
        history = self.conversations.get(session_id, [])
        
        # 分析回答
        if "前端" in user_response or "react" in user_response.lower():
            current_intent.target_type = "component"
            current_intent.technology = TechnologyStack.REACT
        elif "后端" in user_response or "api" in user_response.lower():
            current_intent.target_type = "api"
        elif "无所谓" in user_response or "随便" in user_response:
            # 使用默认配置
            pass
        
        # 移除已澄清的问题
        current_intent.clarification_questions = []
        current_intent.needs_clarification = False
        
        # 更新置信度
        current_intent.confidence = min(1.0, current_intent.confidence + 0.2)
        
        return current_intent
```

```python
# core/intent_enhancer.py (新增)

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from core.fusion_rag.intent_classifier import Intent, QueryIntentClassifier

@dataclass
class IntentResult:
    """增强的意图识别结果"""
    primary: Intent
    confidence: float
    secondary: Optional[List[Intent]] = None
    ambiguity_score: float = 0.0  # 歧义度
    requires_clarification: bool = False

class EnhancedIntentClassifier:
    """
    增强型意图识别器
    
    能力：
    1. 复合意图识别
    2. 歧义检测与澄清请求
    3. 意图置信度动态阈值
    4. 意图历史追踪（因果链）
    """
    
    def __init__(self):
        self.classifier = QueryIntentClassifier()
        self.history: List[IntentResult] = []
        self.intent_patterns: dict = {}
    
    async def classify(
        self, 
        query: str, 
        context: Optional[dict] = None
    ) -> IntentResult:
        """增强的意图分类"""
        
        # 1. 基础分类
        base_intents = await self.classifier.classify(query)
        
        # 2. 歧义检测
        ambiguity = self._detect_ambiguity(base_intents)
        
        # 3. 复合意图识别
        if len(base_intents) > 1:
            combined = self._detect_compound_intent(base_intents)
            if combined:
                return combined
        
        # 4. 构建结果
        result = IntentResult(
            primary=base_intents[0].intent,
            confidence=base_intents[0].confidence,
            secondary=[i.intent for i in base_intents[1:]] if len(base_intents) > 1 else None,
            ambiguity_score=ambiguity,
            requires_clarification=ambiguity > 0.7
        )
        
        # 5. 记录历史（用于因果链）
        self.history.append(result)
        
        return result
    
    def _detect_compound_intent(self, intents: list) -> Optional[IntentResult]:
        """检测复合意图"""
        # 例如：代码生成 + 解释 = 生成代码并解释
        compound_map = {
            ('code_generation', 'explanation'): 'code_with_explanation',
            ('debugging', 'fix'): 'auto_fix',
            ('refactor', 'optimization'): 'smart_refactor',
        }
        key = tuple(sorted([i.intent.value for i in intents]))
        # ...
```

### 1.2 虚拟文件系统 (VFS) ⭐⭐⭐ **核心新增**

这是用户愿景的核心创新点，需要优先实现。

```python
# core/virtual_fs/ (新增目录)

"""
虚拟文件系统 (Virtual File System)

核心概念：
- Draft Space: AI 生成代码的暂存区
- Snapshot: 版本快照，回滚无忧
- Staging: 签入审核流程
- Real FS: 真实文件系统（只读视图）

架构：
┌─────────────────────────────────────────────────────────┐
│                    User / AI                           │
│                         │                               │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │              VFS Mount Point                     │   │
│  │   (统一的文件访问接口)                            │   │
│  └─────────────────────────────────────────────────┘   │
│           │                    │                       │
│           ↓                    ↓                       │
│  ┌─────────────────┐    ┌─────────────────┐             │
│  │  Virtual Layer  │    │   Real Layer    │             │
│  │  (Draft/Snap)  │    │   (Project FS)  │             │
│  └─────────────────┘    └─────────────────┘             │
└─────────────────────────────────────────────────────────┘
"""

# core/virtual_fs/vfs_manager.py

import os
import uuid
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class FileState(Enum):
    """文件状态"""
    REAL = "real"           # 真实文件
    DRAFT = "draft"         # 草稿（AI生成）
    STAGED = "staged"       # 待签入
    COMMITTED = "committed" # 已签入
    DELETED = "deleted"     # 已删除
    CONFLICT = "conflict"   # 冲突

@dataclass
class DraftFile:
    """草稿文件"""
    file_id: str
    path: Path                    # 虚拟路径
    content: str                  # 内容
    created_at: datetime
    created_by: str = "ai"        # "ai" 或 "user"
    parent_snapshot: Optional[str] = None
    status: FileState = FileState.DRAFT
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 因果链元数据
    causal_id: Optional[str] = None
    intent: Optional[str] = None
    parent_operation: Optional[str] = None

@dataclass
class Snapshot:
    """快照"""
    snapshot_id: str
    created_at: datetime
    description: str
    files: Dict[str, DraftFile]   # file_id -> content hash
    parent_snapshot: Optional[str] = None
    is_auto: bool = True          # 自动快照 vs 手动

class VirtualFileSystem:
    """
    虚拟文件系统管理器
    
    核心能力：
    1. 草稿区管理（Draft Space）
    2. 版本快照（Snapshot）
    3. 签入审核（Staging）
    4. 因果链追踪（Causal Metadata）
    
    使用示例：
    ```python
    vfs = VirtualFileSystem(project_root="./myproject")
    
    # AI 生成代码 → 进入草稿区
    draft = await vfs.create_draft(
        path="src/utils/helper.py",
        content="# AI generated code...",
        intent="添加用户认证辅助函数",
        created_by="ai"
    )
    
    # 用户审核 → 签入真实文件系统
    await vfs.stage(draft.file_id)
    await vfs.commit(draft.file_id)  # 需要用户确认
    
    # 回滚 → 切换快照
    await vfs.rollback(snapshot_id="snap_abc123")
    ```
    """
    
    def __init__(
        self, 
        project_root: str | Path,
        drafts_dir: str | Path = ".vfs/drafts",
        snapshots_dir: str | Path = ".vfs/snapshots",
        auto_snapshot: bool = True
    ):
        self.project_root = Path(project_root)
        self.drafts_dir = self.project_root / drafts_dir
        self.snapshots_dir = self.project_root / snapshots_dir
        
        # 存储
        self._drafts: Dict[str, DraftFile] = {}
        self._snapshots: Dict[str, Snapshot] = {}
        self._real_files: Dict[str, str] = {}  # path -> content hash
        
        # 配置
        self.auto_snapshot = auto_snapshot
        self.max_snapshots = 50
        
        # 初始化目录
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载已有数据
        self._load_state()
    
    async def create_draft(
        self,
        path: str | Path,
        content: str,
        intent: str,
        created_by: str = "ai",
        parent_operation: Optional[str] = None
    ) -> DraftFile:
        """
        创建草稿文件
        
        AI 生成的代码都应通过此方法创建草稿
        """
        # 1. 自动快照（保护当前状态）
        if self.auto_snapshot:
            await self._create_auto_snapshot(f"Before draft: {path}")
        
        # 2. 创建草稿
        draft = DraftFile(
            file_id=str(uuid.uuid4()),
            path=Path(path),
            content=content,
            created_at=datetime.now(),
            created_by=created_by,
            parent_snapshot=self._get_current_snapshot_id(),
            status=FileState.DRAFT,
            causal_id=str(uuid.uuid4()),
            intent=intent,
            parent_operation=parent_operation
        )
        
        # 3. 保存草稿
        self._drafts[draft.file_id] = draft
        await self._save_draft(draft)
        
        return draft
    
    async def stage(self, file_id: str) -> bool:
        """
        将草稿标记为待签入
        
        用户审核后可以将草稿移入签入区
        """
        if file_id not in self._drafts:
            return False
        
        draft = self._drafts[file_id]
        draft.status = FileState.STAGED
        await self._save_state()
        
        return True
    
    async def commit(
        self, 
        file_id: str, 
        author: str = "user",
        message: Optional[str] = None
    ) -> bool:
        """
        签入文件到真实文件系统
        
        这是唯一的写入口，需要用户显式确认
        """
        if file_id not in self._drafts:
            return False
        
        draft = self._drafts[file_id]
        
        if draft.status != FileState.STAGED:
            raise PermissionError(
                f"Cannot commit file in state: {draft.status}. "
                "File must be staged first."
            )
        
        # 写入真实文件
        real_path = self.project_root / draft.path
        real_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(real_path, 'w', encoding='utf-8') as f:
            f.write(draft.content)
        
        # 更新状态
        draft.status = FileState.COMMITTED
        self._real_files[str(draft.path)] = self._hash_content(draft.content)
        
        await self._save_state()
        
        return True
    
    async def rollback(self, snapshot_id: str) -> bool:
        """
        回滚到指定快照
        
        回滚整个文件系统状态
        """
        if snapshot_id not in self._snapshots:
            return False
        
        snapshot = self._snapshots[snapshot_id]
        
        # 恢复每个文件
        for file_id, content_hash in snapshot.files.items():
            draft = self._drafts.get(file_id)
            if draft:
                real_path = self.project_root / draft.path
                with open(real_path, 'w', encoding='utf-8') as f:
                    f.write(draft.content)
        
        return True
    
    async def _create_auto_snapshot(self, description: str) -> Snapshot:
        """创建自动快照"""
        snapshot = Snapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(),
            description=description,
            files={file_id: self._hash_content(d.content) 
                   for file_id, d in self._drafts.items()},
            is_auto=True
        )
        
        self._snapshots[snapshot.snapshot_id] = snapshot
        await self._save_snapshot(snapshot)
        
        # 清理旧快照
        await self._cleanup_old_snapshots()
        
        return snapshot
    
    # === 辅助方法 ===
    
    def get_draft_view(self) -> Dict[str, DraftFile]:
        """获取草稿区视图（AI 可见的虚拟状态）"""
        return self._drafts.copy()
    
    def get_real_view(self) -> Dict[str, str]:
        """获取真实文件系统视图"""
        return {
            path: self.project_root / path
            for path in self._real_files.keys()
        }
    
    def get_causal_chain(self, file_id: str) -> List[Dict]:
        """获取文件的因果链"""
        chain = []
        current_id = file_id
        
        while current_id:
            draft = self._drafts.get(current_id)
            if not draft:
                break
            
            chain.append({
                "file_id": draft.file_id,
                "intent": draft.intent,
                "parent_operation": draft.parent_operation,
                "created_at": draft.created_at.isoformat(),
                "created_by": draft.created_by
            })
            
            current_id = draft.parent_operation
        
        return chain
    
    def _hash_content(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()
    
    async def _save_state(self):
        # 保存到磁盘
        pass
    
    async def _load_state(self):
        # 从磁盘加载
        pass

# core/virtual_fs/vfs_integration.py

class VFSIntegratedAgent:
    """
    VFS 集成的 Agent
    
    在 HermesAgent 基础上集成 VFS
    """
    
    def __init__(self, project_root: str):
        self.vfs = VirtualFileSystem(project_root)
        # ... 其他初始化
    
    async def generate_code(self, intent: str, spec: str) -> DraftFile:
        """
        生成代码（草稿模式）
        
        1. 分析需求
        2. 生成代码
        3. 保存到 VFS 草稿区
        """
        # 调用 LLM 生成代码
        code = await self._llm_generate(spec)
        
        # 保存到草稿区
        draft = await self.vfs.create_draft(
            path=self._infer_path(intent),
            content=code,
            intent=intent,
            created_by="ai"
        )
        
        return draft
    
    async def review_and_commit(self, draft_id: str) -> bool:
        """
        用户审核并签入
        """
        # 显示差异
        diff = await self._show_diff(draft_id)
        
        # 用户确认后签入
        return await self.vfs.commit(draft_id)
```

### 1.3 安全模式分级 ⭐⭐⭐ **核心新增**

```python
# core/permission_engine/ (新增目录)

"""
安全模式分级系统

权限等级：
- L1 观察者：仅分析、建议，不写文件
- L2 草稿者：生成代码到草稿区，需人工确认
- L3 协作者：允许自动修复 lint 错误、格式化
- L4 管理者：允许重构、重命名文件（需二次确认）
- L5 自治模式：完全自主运行（仅高级用户）
"""

from enum import Enum
from dataclasses import dataclass
from typing import Set, Optional, Callable
from core.virtual_fs import VirtualFileSystem

class PermissionLevel(Enum):
    """权限等级"""
    OBSERVER = 1       # L1: 观察者
    DRAFTER = 2       # L2: 草稿者
    COLLABORATOR = 3  # L3: 协作者
    MANAGER = 4       # L4: 管理者
    AUTONOMOUS = 5    # L5: 自治模式

@dataclass
class PermissionScope:
    """权限范围"""
    # 文件操作
    can_read_files: bool = False
    can_write_draft: bool = False  # 草稿区
    can_write_real: bool = False   # 真实文件
    can_delete_files: bool = False
    can_rename_files: bool = False
    
    # 代码操作
    can_auto_fix: bool = False
    can_format: bool = False
    can_refactor: bool = False
    
    # 执行操作
    can_execute_code: bool = False
    can_execute_terminal: bool = False
    
    # 危险操作
    can_force_overwrite: bool = False
    can_bulk_operations: bool = False

class PermissionEngine:
    """
    权限引擎
    
    控制 AI 的操作权限，防止意外破坏
    """
    
    # 权限等级定义
    LEVEL_PERMISSIONS = {
        PermissionLevel.OBSERVER: PermissionScope(
            can_read_files=True,
            can_write_draft=False,
            can_write_real=False,
            can_delete_files=False,
            can_rename_files=False,
            can_auto_fix=False,
            can_format=False,
            can_refactor=False,
            can_execute_code=False,
            can_execute_terminal=False,
            can_force_overwrite=False,
            can_bulk_operations=False
        ),
        PermissionLevel.DRAFTER: PermissionScope(
            can_read_files=True,
            can_write_draft=True,  # 草稿区
            can_write_real=False,
            can_delete_files=False,
            can_rename_files=False,
            can_auto_fix=False,
            can_format=False,
            can_refactor=False,
            can_execute_code=True,
            can_execute_terminal=False,
            can_force_overwrite=False,
            can_bulk_operations=False
        ),
        PermissionLevel.COLLABORATOR: PermissionScope(
            can_read_files=True,
            can_write_draft=True,
            can_write_real=False,
            can_delete_files=False,
            can_rename_files=False,
            can_auto_fix=True,     # 自动修复
            can_format=True,       # 格式化
            can_refactor=False,
            can_execute_code=True,
            can_execute_terminal=False,
            can_force_overwrite=False,
            can_bulk_operations=False
        ),
        PermissionLevel.MANAGER: PermissionScope(
            can_read_files=True,
            can_write_draft=True,
            can_write_real=True,    # 需确认
            can_delete_files=True, # 需确认
            can_rename_files=True,  # 需确认
            can_auto_fix=True,
            can_format=True,
            can_refactor=True,     # 需确认
            can_execute_code=True,
            can_execute_terminal=True,
            can_force_overwrite=False,
            can_bulk_operations=False
        ),
        PermissionLevel.AUTONOMOUS: PermissionScope(
            can_read_files=True,
            can_write_draft=True,
            can_write_real=True,
            can_delete_files=True,
            can_rename_files=True,
            can_auto_fix=True,
            can_format=True,
            can_refactor=True,
            can_execute_code=True,
            can_execute_terminal=True,
            can_force_overwrite=True,
            can_bulk_operations=True
        )
    }
    
    def __init__(self, level: PermissionLevel = PermissionLevel.DRAFTER):
        self.current_level = level
        self._scope = self.LEVEL_PERMISSIONS[level]
        
        # 待确认的操作
        self._pending_confirmations: list = []
    
    def check_permission(self, action: str) -> bool:
        """检查是否有权限执行操作"""
        action_map = {
            "read_file": "can_read_files",
            "write_draft": "can_write_draft",
            "write_real": "can_write_real",
            "delete_file": "can_delete_files",
            "rename_file": "can_rename_files",
            "auto_fix": "can_auto_fix",
            "format": "can_format",
            "refactor": "can_refactor",
            "execute_code": "can_execute_code",
            "execute_terminal": "can_execute_terminal",
        }
        
        attr = action_map.get(action)
        if attr:
            return getattr(self._scope, attr, False)
        
        return False
    
    def request_confirmation(
        self, 
        action: str, 
        details: dict,
        callback: Callable
    ):
        """请求用户确认危险操作"""
        if self.current_level == PermissionLevel.AUTONOMOUS:
            # 自治模式：直接执行
            callback()
        else:
            # 加入待确认队列
            self._pending_confirmations.append({
                "action": action,
                "details": details,
                "callback": callback
            })
            # 发送通知给 UI
    
    def approve_action(self, confirmation_id: int) -> bool:
        """用户批准操作"""
        if 0 <= confirmation_id < len(self._pending_confirmations):
            action = self._pending_confirmations[confirmation_id]
            action["callback"]()
            del self._pending_confirmations[confirmation_id]
            return True
        return False
    
    def set_level(self, level: PermissionLevel):
        """设置权限等级"""
        self.current_level = level
        self._scope = self.LEVEL_PERMISSIONS[level]
```

### 1.4 因果链调试器 ⭐⭐⭐ **核心新增**

```python
# core/causal_debug/ (新增目录)

"""
因果链调试器

核心概念：
- 每个 AI 操作都携带因果元数据
- 可以追溯任意代码块的来源
- 支持一键回滚整个因果链

元数据格式：
// @ai-generated: true
// @causal-id: abc123
// @intent: "优化用户列表查询性能"
// @parent-operation: commit:xyz789
// @timestamp: 2026-04-24T10:30:00Z
// @confidence: 0.85
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class CausalNodeType(Enum):
    """因果节点类型"""
    USER_INTENT = "user_intent"      # 用户意图
    AI_GENERATION = "ai_generation"  # AI 生成
    USER_CONFIRMATION = "user_conf"  # 用户确认
    SYSTEM_ACTION = "system_action" # 系统操作
    ERROR = "error"                 # 错误

@dataclass
class CausalMetadata:
    """因果元数据"""
    causal_id: str
    node_type: CausalNodeType
    intent: str
    timestamp: datetime
    
    # 上下文
    parent_id: Optional[str] = None
    file_path: Optional[str] = None
    line_range: Optional[tuple[int, int]] = None
    code_snippet: Optional[str] = None
    
    # 质量指标
    confidence: float = 1.0
    verification_status: str = "unverified"  # unverified/verified/failed
    
    # 关联
    related_nodes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class CausalChain:
    """
    因果链
    
    记录整个操作的历史，用于调试和回溯
    """
    
    def __init__(self):
        self.nodes: Dict[str, CausalMetadata] = {}
        self.root_id: Optional[str] = None
    
    def add_node(self, metadata: CausalMetadata) -> str:
        """添加因果节点"""
        if not self.root_id:
            self.root_id = metadata.causal_id
        
        # 更新父子关系
        if metadata.parent_id and metadata.parent_id in self.nodes:
            parent = self.nodes[metadata.parent_id]
            if metadata.causal_id not in parent.related_nodes:
                parent.related_nodes.append(metadata.causal_id)
        
        self.nodes[metadata.causal_id] = metadata
        return metadata.causal_id
    
    def get_lineage(self, causal_id: str) -> List[CausalMetadata]:
        """获取溯源链"""
        lineage = []
        current_id = causal_id
        
        while current_id and current_id in self.nodes:
            node = self.nodes[current_id]
            lineage.insert(0, node)
            current_id = node.parent_id
        
        return lineage
    
    def get_affected_files(self, causal_id: str) -> List[str]:
        """获取因果链影响的所有文件"""
        affected = set()
        
        for node_id in self._traverse_subtree(causal_id):
            node = self.nodes.get(node_id)
            if node and node.file_path:
                affected.add(node.file_path)
        
        return list(affected)
    
    def _traverse_subtree(self, root_id: str) -> List[str]:
        """遍历子树"""
        result = [root_id]
        node = self.nodes.get(root_id)
        if node:
            for child_id in node.related_nodes:
                result.extend(self._traverse_subtree(child_id))
        return result

class CausalDebugManager:
    """
    因果调试管理器
    
    管理整个项目的因果链
    """
    
    def __init__(self):
        self.chains: Dict[str, CausalChain] = {}  # session_id -> chain
        self.current_session: Optional[str] = None
    
    def start_session(self, session_id: str):
        """开始新的调试会话"""
        self.current_session = session_id
        if session_id not in self.chains:
            self.chains[session_id] = CausalChain()
    
    def record_operation(
        self,
        intent: str,
        node_type: CausalNodeType,
        file_path: Optional[str] = None,
        code: Optional[str] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """记录操作"""
        if not self.current_session:
            self.start_session(f"session_{uuid.uuid4().hex[:8]}")
        
        chain = self.chains[self.current_session]
        
        metadata = CausalMetadata(
            causal_id=f"causal_{uuid.uuid4().hex[:8]}",
            node_type=node_type,
            intent=intent,
            timestamp=datetime.now(),
            parent_id=parent_id,
            file_path=file_path,
            code_snippet=code,
            **kwargs
        )
        
        return chain.add_node(metadata)
    
    def trace_error(self, error_msg: str) -> Dict[str, Any]:
        """
        追踪错误来源
        
        当 BUG 发生时，追溯可能的触发点
        """
        if not self.current_session:
            return {"error": "No active session"}
        
        chain = self.chains[self.current_session]
        
        # 找到所有 ERROR 节点
        error_nodes = [
            node for node in chain.nodes.values()
            if node.node_type == CausalNodeType.ERROR
        ]
        
        # 追溯每个错误的来源
        traces = []
        for error_node in error_nodes:
            lineage = chain.get_lineage(error_node.causal_id)
            
            # 生成报告
            report = {
                "error_node": {
                    "id": error_node.causal_id,
                    "intent": error_node.intent,
                    "timestamp": error_node.timestamp.isoformat()
                },
                "causal_chain": [
                    {
                        "id": n.causal_id,
                        "type": n.node_type.value,
                        "intent": n.intent,
                        "file": n.file_path,
                        "confidence": n.confidence
                    }
                    for n in lineage
                ],
                "affected_files": chain.get_affected_files(error_node.causal_id),
                "possible_causes": self._analyze_causes(lineage),
                "rollback_options": self._suggest_rollback(lineage)
            }
            traces.append(report)
        
        return {"traces": traces}
    
    def suggest_rollback(self, causal_id: str) -> Dict[str, Any]:
        """建议回滚方案"""
        if not self.current_session:
            return {"error": "No active session"}
        
        chain = self.chains[self.current_session]
        lineage = chain.get_lineage(causal_id)
        
        # 找到用户确认之前的最后一个节点
        safe_point = None
        for node in reversed(lineage):
            if node.node_type == CausalNodeType.USER_CONFIRMATION:
                break
            safe_point = node
        
        return {
            "current_point": causal_id,
            "safe_point": safe_point.causal_id if safe_point else None,
            "rollback_chain": [n.causal_id for n in lineage],
            "affected_files": chain.get_affected_files(causal_id)
        }
    
    def _analyze_causes(self, lineage: List[CausalMetadata]) -> List[str]:
        """分析可能的错误原因"""
        causes = []
        
        # 检查置信度
        low_confidence = [n for n in lineage if n.confidence < 0.7]
        if low_confidence:
            causes.append(
                f"存在 {len(low_confidence)} 个低置信度节点，可能是错误源头"
            )
        
        # 检查未验证的代码
        unverified = [n for n in lineage if n.verification_status == "unverified"]
        if unverified:
            causes.append(
                f"存在 {len(unverified)} 个未验证的 AI 生成代码"
            )
        
        return causes
    
    def _suggest_rollback(self, lineage: List[CausalMetadata]) -> List[Dict]:
        """建议回滚选项"""
        options = []
        
        # 回滚到每个父节点
        for i, node in enumerate(lineage):
            if i == 0:
                continue  # 跳过根节点
            
            options.append({
                "target_id": node.causal_id,
                "description": f"回滚到: {node.intent[:50]}",
                "affected_files": len(set(n.file_path for n in lineage[:i] if n.file_path))
            })
        
        return options
```

---

## 📁 Phase 2: 协作扩展 (6-8周)

> **目标**: 构建多会话管理和架构守护能力

### 2.1 多会话进程管理 ⭐⭐⭐

```python
# core/multi_session_manager.py (新增)

"""
多会话进程管理器

概念：
- Session Bus: 会话间消息总线
- Frontend Session: 专注 UI/前端
- Backend Session: 专注 API/后端
- DevOps Session: 专注部署/配置
- Coordinator: 会话协调器
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import asyncio

class SessionType(Enum):
    """会话类型"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEVOPS = "devops"
    GENERAL = "general"

@dataclass
class Session:
    """会话"""
    session_id: str
    session_type: SessionType
    name: str
    status: str = "idle"  # idle/running/waiting/blocked
    context: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)

class SessionBus:
    """
    会话总线
    
    进程间通信中枢
    """
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def register_session(self, session: Session):
        """注册会话"""
        self._sessions[session.session_id] = session
    
    async def send_message(
        self,
        from_session: str,
        to_session: str,
        message: dict
    ):
        """发送消息"""
        target = self._sessions.get(to_session)
        if target:
            # 直接传递
            await self._deliver_message(target, message)
        else:
            # 加入队列
            await self._message_queue.put({
                "from": from_session,
                "to": to_session,
                "message": message
            })
    
    async def broadcast(
        self,
        from_session: str,
        message: dict,
        target_types: Optional[List[SessionType]] = None
    ):
        """广播消息"""
        for session in self._sessions.values():
            if session.session_id == from_session:
                continue
            if target_types and session.session_type not in target_types:
                continue
            await self._deliver_message(session, message)

class MultiSessionCoordinator:
    """
    多会话协调器
    
    协调多个专业会话协作完成任务
    """
    
    def __init__(self):
        self.session_bus = SessionBus()
        self._sessions: Dict[SessionType, Session] = {}
    
    async def create_team_session(self, task: str) -> str:
        """创建团队会话"""
        team_id = f"team_{uuid.uuid4().hex[:8]}"
        
        # 创建专业会话
        sessions = [
            Session(
                session_id=f"{team_id}_frontend",
                session_type=SessionType.FRONTEND,
                name="前端专家",
                capabilities=["ui_generation", "state_management", "styling"]
            ),
            Session(
                session_id=f"{team_id}_backend",
                session_type=SessionType.BACKEND,
                name="后端专家",
                capabilities=["api_design", "database", "auth"]
            ),
            Session(
                session_id=f"{team_id}_devops",
                session_type=SessionType.DEVOPS,
                name="DevOps专家",
                capabilities=["deployment", "ci_cd", "monitoring"]
            ),
        ]
        
        for session in sessions:
            self._sessions[session.session_type] = session
            self.session_bus.register_session(session)
        
        # 注册跨会话回调
        self._setup_cross_session_callbacks()
        
        return team_id
    
    async def execute_distributed_task(self, task: str) -> Dict[str, Any]:
        """执行分布式任务"""
        # 分析任务，确定参与会话
        participants = self._analyze_task(task)
        
        # 并行执行子任务
        results = await asyncio.gather(*[
            self._execute_in_session(session_type, task)
            for session_type in participants
        ])
        
        # 协调结果
        return self._coordinate_results(results)
```

### 2.2 架构守护者 (ArchGuard) ⭐⭐⭐

```python
# core/archon/ (已有部分，增强)

"""
架构守护者系统

功能：
1. 声明式架构规则
2. 生成前校验
3. 违规检测与阻止
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# core/archon/arch_guard.py

class RuleType(Enum):
    """规则类型"""
    LAYER_ACCESS = "layer_access"      # 层访问约束
    RESPONSE_FORMAT = "response_format" # 响应格式约束
    NAMING_CONVENTION = "naming"        # 命名规范
    DEPENDENCY = "dependency"          # 依赖约束
    CODE_STYLE = "code_style"          # 代码风格

@dataclass
class ArchRule:
    """架构规则"""
    id: str
    name: str
    rule_type: RuleType
    pattern: str           # 正则或路径模式
    message: str           # 违规提示
    severity: str = "error"  # error/warning/info
    enabled: bool = True

@dataclass
class Violation:
    """违规"""
    rule_id: str
    rule_name: str
    file_path: str
    line: int
    message: str
    severity: str

class ArchRuleEngine:
    """
    架构规则引擎
    
    在代码生成前校验架构合规性
    """
    
    def __init__(self):
        self.rules: List[ArchRule] = []
        self._load_default_rules()
    
    def _load_default_rules(self):
        """加载默认规则"""
        self.rules = [
            ArchRule(
                id="layer_db_access",
                name="Service层不能直接访问数据库",
                rule_type=RuleType.LAYER_ACCESS,
                pattern=r"service/.*\.(py|js|ts).*mysql|sqlite|mongodb",
                message="Service层应通过DAO访问数据库，不应直接连接",
                severity="error"
            ),
            ArchRule(
                id="response_format",
                name="API响应必须符合BaseResponse格式",
                rule_type=RuleType.RESPONSE_FORMAT,
                pattern=r"return\s*\{[^}]*(?!success|data|message)[^}]*\}",
                message="API响应必须包含 { success, data, message } 字段",
                severity="error"
            ),
            ArchRule(
                id="no_circular_dep",
                name="禁止循环依赖",
                rule_type=RuleType.DEPENDENCY,
                pattern=r"from\s+\.\.(\w+).*import.*from\s+\.\.(\w+)",
                message="检测到可能的循环依赖",
                severity="error"
            ),
        ]
    
    def load_project_rules(self, project_root: Path):
        """加载项目特定规则 (.archguard)"""
        rules_file = project_root / ".archguard"
        if rules_file.exists():
            # 解析 YAML/JSON 格式的规则文件
            import yaml
            with open(rules_file) as f:
                config = yaml.safe_load(f)
            
            for rule_def in config.get("rules", []):
                rule = ArchRule(
                    id=rule_def["id"],
                    name=rule_def["name"],
                    rule_type=RuleType(rule_def.get("type", "code_style")),
                    pattern=rule_def["pattern"],
                    message=rule_def["message"],
                    severity=rule_def.get("severity", "warning")
                )
                self.rules.append(rule)
    
    def validate_file(
        self, 
        file_path: str, 
        content: str
    ) -> List[Violation]:
        """验证单个文件"""
        violations = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # 检查规则类型
            if rule.rule_type == RuleType.LAYER_ACCESS:
                # 层访问检查
                if self._check_layer_access(file_path, content, rule):
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        file_path=file_path,
                        line=0,
                        message=rule.message,
                        severity=rule.severity
                    ))
            
            elif rule.rule_type == RuleType.RESPONSE_FORMAT:
                # 响应格式检查
                if not self._check_response_format(content, rule):
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        file_path=file_path,
                        line=0,
                        message=rule.message,
                        severity=rule.severity
                    ))
            
            else:
                # 正则匹配
                matches = re.finditer(rule.pattern, content, re.MULTILINE)
                for match in matches:
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        file_path=file_path,
                        line=content[:match.start()].count('\n') + 1,
                        message=rule.message,
                        severity=rule.severity
                    ))
        
        return violations
    
    def validate_before_generation(
        self,
        intent: str,
        proposed_code: str,
        file_path: str
    ) -> Tuple[bool, List[Violation]]:
        """
        生成前校验
        
        这是核心接口：AI 生成代码前先校验
        """
        violations = self.validate_file(file_path, proposed_code)
        
        # 严重违规阻止生成
        errors = [v for v in violations if v.severity == "error"]
        
        if errors:
            return False, violations
        
        return True, violations
    
    def _check_layer_access(
        self, 
        file_path: str, 
        content: str, 
        rule: ArchRule
    ) -> bool:
        """检查层访问"""
        # service 层检查
        if "service" in file_path.lower():
            # 检查是否直接访问数据库
            db_patterns = ["mysql", "sqlite", "mongodb", "redis", "psycopg"]
            for pattern in db_patterns:
                if pattern in content.lower():
                    return True
        return False
    
    def _check_response_format(
        self, 
        content: str, 
        rule: ArchRule
    ) -> bool:
        """检查响应格式"""
        # 检查是否有 return 语句
        return_matches = re.finditer(r'return\s*\{([^}]+)\}', content)
        for match in return_matches:
            ret_content = match.group(1)
            # 检查是否包含必需字段
            if not all(p in ret_content for p in ["success", "data", "message"]):
                return False
        return True

class VFSIntegratedArchGuard:
    """
    VFS 集成的架构守护者
    
    在 VFS 草稿生成前进行架构校验
    """
    
    def __init__(self, project_root: Path):
        self.vfs = VirtualFileSystem(project_root)
        self.rule_engine = ArchRuleEngine()
        self.rule_engine.load_project_rules(project_root)
    
    async def generate_with_guard(
        self,
        intent: str,
        spec: str,
        target_path: str
    ) -> Tuple[bool, str, List[Violation]]:
        """
        受保护的代码生成
        
        1. 生成代码
        2. 架构校验
        3. 通过则进入草稿区
        4. 失败则返回违规信息
        """
        # 1. 生成代码
        code = await self._llm_generate(spec)
        
        # 2. 架构校验
        valid, violations = self.rule_engine.validate_before_generation(
            intent, code, target_path
        )
        
        if not valid:
            return False, "", violations
        
        # 3. 进入草稿区
        draft = await self.vfs.create_draft(
            path=target_path,
            content=code,
            intent=intent
        )
        
        return True, draft.file_id, violations
```

### 2.3 竞品代码对比增强 ⭐⭐⭐

扩展现有的 `multi_model_comparison.py`：

```python
# core/compare_engine.py (增强)

class SolutionCompareEngine:
    """
    方案对比引擎
    
    用户给需求，AI 同时生成多种实现方案并对比
    """
    
    # 实现模式库
    IMPLEMENTATION_PATTERNS = {
        "python": {
            "class": "基于类的面向对象实现",
            "functional": "函数式编程实现",
            "dataclass": "数据类实现",
        },
        "javascript": {
            "class": "ES6 Class 实现",
            "hooks": "React Hooks 实现",
            "signal": "Signal 响应式实现",
        }
    }
    
    async def generate_comparison(
        self,
        requirement: str,
        language: str,
        max_patterns: int = 3
    ) -> Dict[str, Any]:
        """
        生成多方案对比
        
        返回：
        {
            "patterns": [
                {"name": "Class", "code": "...", "metrics": {...}},
                {"name": "Hooks", "code": "...", "metrics": {...}},
            ],
            "comparison": {...},
            "recommendation": "..."
        }
        """
        patterns = self.IMPLEMENTATION_PATTERNS.get(language, {})
        
        # 并行生成
        results = await asyncio.gather(*[
            self._generate_pattern(requirement, pattern, language)
            for pattern in list(patterns.keys())[:max_patterns]
        ])
        
        # 多维评估
        evaluations = [self._evaluate_pattern(r) for r in results]
        
        # 生成对比报告
        comparison = self._generate_comparison_report(results, evaluations)
        
        # 推荐方案
        recommendation = self._recommend_pattern(evaluations)
        
        return {
            "patterns": results,
            "evaluations": evaluations,
            "comparison": comparison,
            "recommendation": recommendation
        }
    
    def _evaluate_pattern(self, result: dict) -> dict:
        """多维评估"""
        code = result["code"]
        
        return {
            "correctness": self._check_correctness(code),
            "readability": self._score_readability(code),
            "performance": self._estimate_performance(code),
            "maintainability": self._score_maintainability(code),
            "lines_of_code": len(code.split('\n')),
            "cyclomatic_complexity": self._calc_complexity(code)
        }
```

---

## 📁 Phase 3: 交互革命 (8-12周)

### 3.1 意图草图模式 ⭐⭐

```python
# core/sketch_mode/ (新增)

"""
意图草图模式

支持非代码输入：
- 拖拽设计稿（Figma/Sketch）
- 流程图绘制
- 草图识别
"""

class SketchIntentParser:
    """
    草图意图解析器
    
    将视觉输入转换为代码意图
    """
    
    async def parse_design_drag(self, image_bytes: bytes) -> dict:
        """解析拖入的设计稿"""
        # 调用视觉模型识别 UI 结构
        structure = await self._vision_model.analyze(image_bytes)
        
        # 转换为组件规范
        components = self._extract_components(structure)
        
        return {
            "components": components,
            "layout": structure["layout"],
            "styles": structure["styles"],
            "interactions": structure["interactions"]
        }
    
    async def parse_flowchart(self, nodes: list, edges: list) -> dict:
        """解析流程图生成状态机代码"""
        # 转换为状态机规范
        state_machine = self._flowchart_to_state_machine(nodes, edges)
        
        return {
            "states": state_machine["states"],
            "transitions": state_machine["transitions"],
            "initial_state": state_machine["initial"],
            "code": await self._generate_state_machine(state_machine)
        }
```

### 3.2 代码沙盘增强 ⭐⭐

扩展现有的 `sandbox_runtimes.py`：

```python
# core/sandbox_manager.py (增强)

class SandboxExperiment:
    """
    代码沙盘实验
    
    用户说"试试重构"，AI 在沙盘中生成方案，用户预览后再合并
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.sandbox_dir = project_root / ".sandbox"
        self.sandbox_vfs = VirtualFileSystem(
            project_root=self.sandbox_dir,
            auto_snapshot=True
        )
    
    async def create_experiment(
        self,
        instruction: str,
        target_files: List[str]
    ) -> ExperimentResult:
        """
        创建沙盘实验
        
        1. 复制目标文件到沙盘
        2. 在沙盘执行重构
        3. 生成差异预览
        """
        # 1. 准备沙盘
        await self._prepare_sandbox(target_files)
        
        # 2. 生成方案
        plan = await self._analyze_and_plan(instruction, target_files)
        
        # 3. 在沙盘执行
        for step in plan.steps:
            await self._execute_in_sandbox(step)
        
        # 4. 生成预览
        preview = await self._generate_preview(target_files)
        
        return ExperimentResult(
            plan=plan,
            preview=preview,
            can_merge=True,
            merge_preview=preview
        )
    
    async def merge_experiment(self, experiment_id: str) -> bool:
        """
        合并沙盘实验到主分支
        
        将沙盘的修改同步到真实 VFS
        """
        # 1. 再次确认
        confirm = await self._user_confirm_merge(experiment_id)
        if not confirm:
            return False
        
        # 2. 同步到主 VFS
        await self.sandbox_vfs.merge_to(self.main_vfs, experiment_id)
        
        return True
```

---

## 📁 Phase 4: 自主进化 (12+周)

### 4.1 自动依赖图维护 ⭐⭐⭐

```python
# core/dependency_graph/ (新增)

"""
自动依赖图谱

功能：
- 实时维护模块依赖图
- 删除函数时提示引用
- 可视化依赖关系
"""

import ast
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

@dataclass
class DependencyNode:
    """依赖节点"""
    path: str                    # 文件路径
    name: str                    # 模块名
    type: str                    # module/class/function
    imports: Set[str] = field(default_factory=set)    # 导入的模块
    imported_by: Set[str] = field(default_factory=set) # 被谁导入
    calls: Set[str] = field(default_factory=set)      # 调用的函数
    called_by: Set[str] = field(default_factory=set)  # 被谁调用

class DependencyGraph:
    """
    依赖图谱管理器
    
    实时维护项目的依赖关系
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.nodes: Dict[str, DependencyNode] = {}
        self._build_initial_graph()
    
    def update_node(self, file_path: str, content: str):
        """更新节点（文件修改后调用）"""
        node = self._parse_file(file_path, content)
        self.nodes[file_path] = node
        
        # 更新反向索引
        for imported in node.imports:
            if imported in self.nodes:
                self.nodes[imported].imported_by.add(file_path)
    
    def get_delete_impact(self, file_path: str) -> Dict[str, Any]:
        """
        获取删除文件的影响
        
        删除前必须调用的安全检查
        """
        node = self.nodes.get(file_path)
        if not node:
            return {"safe": True, "impact": []}
        
        # 检查被引用情况
        impacted_files = list(node.imported_by)
        impacted_functions = list(node.called_by)
        
        return {
            "safe": len(impacted_files) == 0,
            "impact": {
                "files": impacted_files,
                "functions": impacted_functions,
                "total_impact": len(impacted_files) + len(impacted_functions)
            },
            "warning": self._generate_warning(node)
        }
    
    def suggest_refactor_targets(self, file_path: str) -> List[Dict]:
        """建议重构目标"""
        node = self.nodes.get(file_path)
        if not node:
            return []
        
        suggestions = []
        
        # 高扇出：被很多文件引用，可以考虑拆分
        if len(node.imported_by) > 10:
            suggestions.append({
                "type": "high_fanout",
                "message": f"此模块被 {len(node.imported_by)} 个文件引用",
                "recommendation": "考虑拆分为更小的模块"
            })
        
        # 循环依赖检测
        if self._has_circular_dependency(file_path):
            suggestions.append({
                "type": "circular_dep",
                "message": "检测到循环依赖",
                "recommendation": "重构依赖关系"
            })
        
        return suggestions
```

### 4.2 情绪感知与疲劳干预 ⭐⭐

扩展现有的 `digital_twin/`：

```python
# core/developer_wellness/ (新增)

"""
开发者状态感知

功能：
- 检测开发者状态（专注/疲劳/压力）
- 在低效时刻主动干预
- 提供适当的休息建议
"""

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

class DeveloperState(Enum):
    """开发者状态"""
    FOCUSED = "focused"         # 专注
    TIRED = "tired"             # 疲劳
    FRUSTRATED = "frustrated"   # 受挫
    FLOW = "flow"               # 心流
    BURNOUT = "burnout"         # 倦怠

@dataclass
class WellnessMetrics:
    """健康指标"""
    keystroke_rate: float       # 键盘速率
    undo_frequency: float       # 撤销频率
    error_rate: float            # 错误率
    session_duration: int       # 会话时长(分钟)
    time_since_break: int       # 距离上次休息
    context_switches: int        # 上下文切换次数

class DeveloperWellnessMonitor:
    """
    开发者健康监控器
    
    通过行为模式判断开发者状态
    """
    
    def __init__(self):
        self.metrics_history: list[WellnessMetrics] = []
        self._current_state = DeveloperState.FOCUSED
    
    def record_action(self, action_type: str, timestamp: datetime):
        """记录开发者行为"""
        # 更新指标
        pass
    
    def assess_state(self) -> DeveloperState:
        """
        评估当前状态
        
        基于历史指标判断开发者状态
        """
        if not self.metrics_history:
            return DeveloperState.FOCUSED
        
        recent = self.metrics_history[-10:]
        
        # 分析模式
        avg_undo = sum(m.undo_frequency for m in recent) / len(recent)
        avg_keystroke = sum(m.keystroke_rate for m in recent) / len(recent)
        
        # 判断逻辑
        if avg_undo > 0.3:  # 高撤销率
            return DeveloperState.TIRED
        elif avg_keystroke < 20:  # 低输入速率
            return DeveloperState.FRUSTRATED
        else:
            return DeveloperState.FOCUSED
    
    def should_intervene(self) -> Optional[Dict]:
        """
        判断是否应该干预
        
        返回干预建议
        """
        state = self.assess_state()
        
        if state == DeveloperState.TIRED:
            return {
                "intervene": True,
                "type": "break_suggestion",
                "message": "检测到高频撤销，建议休息5分钟",
                "suggestion": "站起来活动一下，看看远处"
            }
        
        if state == DeveloperState.FRUSTRATED:
            return {
                "intervene": True,
                "type": "simplify_task",
                "message": "检测到可能的困难",
                "suggestion": "这个重构涉及面较广，建议明天再继续"
            }
        
        return None
```

---

## 📁 文件结构规划

```
core/
├── virtual_fs/                    # ⭐ Phase 1: 虚拟文件系统
│   ├── __init__.py
│   ├── vfs_manager.py             # VFS 核心
│   ├── draft_space.py             # 草稿区
│   ├── snapshot.py                # 快照管理
│   ├── staging.py                 # 签入流程
│   └── vfs_integration.py        # Agent 集成
│
├── permission_engine/             # ⭐ Phase 1: 权限控制
│   ├── __init__.py
│   ├── permission_engine.py       # 权限引擎
│   ├── security_levels.py         # 安全等级
│   └── confirmation_manager.py   # 确认管理
│
├── causal_debug/                  # ⭐ Phase 1: 因果链调试
│   ├── __init__.py
│   ├── causal_metadata.py         # 元数据模型
│   ├── causal_chain.py            # 因果链
│   ├── debug_manager.py           # 调试管理器
│   └── trace_viewer.py            # 追踪可视化
│
├── intent_enhancer/                # ⭐ Phase 1: 意图增强
│   ├── __init__.py
│   ├── enhanced_classifier.py     # 增强分类器
│   ├── compound_intent.py         # 复合意图
│   └── intent_history.py          # 意图历史
│
├── archon/                         # Phase 2: 架构守护者
│   ├── arch_guard.py              # 规则引擎
│   ├── rule_library.py            # 规则库
│   └── integration.py             # VFS 集成
│
├── multi_session/                 # Phase 2: 多会话管理
│   ├── __init__.py
│   ├── session_bus.py             # 会话总线
│   ├── session_manager.py         # 会话管理
│   └── coordinator.py            # 协调器
│
├── sketch_mode/                   # Phase 3: 意图草图
│   ├── __init__.py
│   ├── design_parser.py          # 设计稿解析
│   ├── flowchart_parser.py        # 流程图解析
│   └── sketch_to_code.py         # 草图转代码
│
├── sandbox_manager/               # Phase 3: 沙盘管理
│   ├── sandbox_experiment.py      # 实验管理
│   ├── merge_engine.py           # 合并引擎
│   └── preview_generator.py      # 预览生成
│
├── dependency_graph/              # Phase 4: 依赖图谱
│   ├── __init__.py
│   ├── graph_builder.py          # 图谱构建
│   ├── impact_analyzer.py        # 影响分析
│   └── refactor_suggestor.py     # 重构建议
│
├── developer_wellness/            # Phase 4: 开发者健康
│   ├── __init__.py
│   ├── wellness_monitor.py       # 健康监控
│   ├── state_classifier.py       # 状态分类
│   └── intervention_engine.py    # 干预引擎
│
├── compare_engine/                # Phase 2: 方案对比
│   ├── solution_compare.py        # 方案对比
│   ├── metrics_calculator.py     # 指标计算
│   └── recommendation_engine.py  # 推荐引擎
│
├── reflective_agent/              # ✅ 已有: 反思式Agent
│   ├── reflective_loop.py
│   ├── reflection_engine.py
│   └── ...
│
├── multi_path_explorer/           # ✅ 已有: 多路径探索
│   ├── multi_path_explorer.py
│   └── ...
│
├── world_model_simulator/         # ✅ 已有: 世界模型
│   ├── world_model.py
│   └── ...
│
├── collective_intelligence/       # ✅ 已有: 集体智能
│   └── ...
│
└── expert_learning/               # ✅ 已有: 专家学习
    └── ...
```

---

## 🚀 实施优先级

### 紧急重要 (P0) - 立即开始

| 模块 | 工作量 | 依赖 | 说明 |
|------|--------|------|------|
| VFS 核心 | 3-4周 | 无 | 核心创新，必须优先 |
| 权限引擎 | 1-2周 | 无 | 安全保障 |
| 意图增强 | 1周 | IntentClassifier | 复用现有 |
| 因果链基础 | 2周 | VFS | 调试基础 |

### 重要 (P1) - 第二个冲刺

| 模块 | 工作量 | 依赖 | 说明 |
|------|--------|------|------|
| ArchGuard 集成 | 2周 | VFS, 权限 | 架构保障 |
| 沙盘实验 | 2-3周 | VFS | 用户核心需求 |
| 依赖图谱 | 2周 | 无 | 工程化必备 |
| 方案对比 | 1周 | expert_learning | 复用现有 |

### 扩展 (P2) - 后续迭代

| 模块 | 工作量 | 依赖 |
|------|--------|------|
| 多会话管理 | 3-4周 | Agent |
| 意图草图 | 4-6周 | Vision Model |
| 开发者健康 | 2-3周 | 行为分析 |

---

## 📊 资源估算

| 阶段 | 周期 | 主要工作 |
|------|------|----------|
| Phase 1 | 4-6周 | VFS + 权限 + 因果链 + 意图增强 |
| Phase 2 | 6-8周 | ArchGuard + 沙盘 + 依赖图 + 方案对比 |
| Phase 3 | 8-12周 | 多会话 + 意图草图 + 沙盘增强 |
| Phase 4 | 12+周 | 开发者健康 + 完整进化 |

---

## 🎯 关键成功因素

1. **VFS 是核心** - 这是"编程操作系统"与传统 IDE 的本质区别
2. **渐进式交付** - 每个 Phase 都交付可用功能
3. **安全第一** - 权限系统和架构守护防止破坏
4. **用户控制** - 始终保持人对 AI 的最终控制权

---

## 🔄 革命性的交互模式

### 模式 1: 需求澄清对话

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         需求澄清对话流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  👤 用户: 做个登录页面                                                       │
│                                                                             │
│  🤖 AI:  需要了解几个细节：                                                 │
│         • 你需要什么风格？（现代简约 / 企业级 / 创意设计）                    │
│         • 需要哪些登录方式？（邮箱密码 / 社交登录 / 多因素认证）              │
│         • 技术栈是？（React / Vue / 其他）                                   │
│                                                                             │
│  👤 用户: 现代简约，邮箱+微信登录，React                                     │
│                                                                             │
│  🤖 AI:  明白了！正在生成...                                                 │
│                                                                             │
│  👤 用户: 需要记住登录状态吗？                                               │
│                                                                             │
│  👤 用户: 需要，7天有效                                                     │
│                                                                             │
│  🤖 AI:  完美！生成完成                                                      │
│                                                                             │
│  ✅ 自动完成：                                                               │
│     • LoginPage.jsx 登录页面组件                                            │
│     • WechatLoginButton.jsx 微信登录按钮                                    │
│     • useAuth hook 认证状态管理                                             │
│     • authAPI.js 后端接口                                                   │
│     • LoginPage.css 样式文件                                                │
│     • LoginPage.test.js 测试文件                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 模式 2: 可视化意图表达

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         可视化意图输入                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  方式 1: 拖拽设计稿                                                         │
│  ─────────────────                                                         │
│  用户: 将 Figma/Sketch 设计稿拖入 IDE                                      │
│        ↓                                                                   │
│  AI:   自动解析布局、组件、样式                                              │
│        ↓                                                                   │
│  AI:   生成对应的代码组件                                                   │
│                                                                             │
│  方式 2: 流程图绘制                                                         │
│  ─────────────────                                                         │
│  用户: 绘制流程图                                                           │
│        ┌─────┐                                                             │
│        │开始 │                                                             │
│        └──┬──┘                                                             │
│           ↓                                                                │
│        ┌──────┐                                                            │
│        │输入？├────否──→ 显示错误                                           │
│        └──┬──┘                                                            │
│           ↓是                                                              │
│        ┌──────┐                                                            │
│        │验证？├────否──→ 提示错误                                          │
│        └──┬──┘                                                            │
│           ↓是                                                              │
│        ┌──────┐                                                            │
│        │登录成功│                                                          │
│        └──┬──┘                                                            │
│           ↓                                                                │
│        ┌─────┐                                                             │
│        │结束 │                                                             │
│        └─────┘                                                             │
│        ↓                                                                   │
│  AI:   生成状态机代码                                                       │
│                                                                             │
│  方式 3: 代码选中 + 自然语言                                                │
│  ─────────────────────────                                                 │
│  用户: 选中一段代码 → 说"优化这个"                                          │
│        ↓                                                                   │
│  AI:   提供多种优化方案并解释差异                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 模式 3: 自然语言替代命令行

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         自然语言操作替代传统命令                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ❌ 传统命令                      ✅ AI-IDE 自然语言                         │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  npm install xxx                   "安装 xxx 库"                             │
│  npm run dev                       "启动开发服务器"                          │
│  git add . && git commit -m "xxx"  "提交这些修改"                           │
│  git push                          "推送到远程仓库"                         │
│  git merge feature/login           "合并登录分支"                           │
│  pytest -v                         "运行测试"                               │
│  docker build -t app .             "构建 Docker 镜像"                       │
│  docker-compose up                 "启动服务"                               │
│  curl -X POST ...                  "测试这个接口"                           │
│                                                                             │
│  💡 用户不需要记忆任何命令！                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏠 本地网关架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         本地网关 (Local Gateway)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     ┌──────────────┐                                                         │
│     │  IDE Plugin  │                                                        │
│     └──────┬───────┘                                                         │
│            │                                                                  │
│            ▼                                                                  │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │                    Local Gateway (本地网关)                         │   │
│     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │   │
│     │  │  索引管理   │  │  上下文压缩  │  │  响应缓存   │  │ 降级策略 │ │   │
│     │  │ SymbolIdx  │  │  Compress   │  │ IntentCache │  │ Fallback │ │   │
│     │  │ DepGraph   │  │            │  │             │  │          │ │   │
│     │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │   │
│     └─────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                           │
│                                   ▼                                          │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │                       LLM API (远程)                               │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 网关核心职责

| 职责 | 说明 | 优先级 |
|------|------|--------|
| **索引管理** | 维护符号索引、依赖图谱 | P0 |
| **上下文压缩** | 将代码上下文压缩为语义描述 | P0 |
| **响应缓存** | 缓存高频意图结果 | P1 |
| **降级策略** | LLM 超时时返回模板兜底 | P1 |

---

## 💎 "足够好"的上下文哲学

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     核心洞察：追求"足够好"而非"完美"                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ❌ 错误思维:                                                                │
│  ──────────                                                                 │
│  "AI 必须理解整个代码库才能正确修改"                                         │
│  "上下文越完整，代码质量越高"                                                │
│                                                                             │
│  ✅ 正确思维:                                                                │
│  ──────────                                                                 │
│  "AI 不需要理解 1000 个文件才能修复一个 Bug"                                  │
│  "提供'足够好'的上下文，而非'完美'的上下文"                                   │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  🎯 性能本身就是用户体验:                                                     │
│                                                                             │
│  • 等待 30 秒的 AI → 即使准确，也会被用户抛弃                                  │
│  • 3 秒响应的 AI → 用户体验更佳，即使需要澄清                                 │
│                                                                             │
│  📊 优先级: 快 (Fast) → 稳 (Stable) → 聪明 (Smart)                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔥 意图保持型压缩：信息密度革命

> **核心理念**：不是"压缩"，而是"信息密度革命"。用 1% 的 Token 传递 99% 的意图。

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                     "无损压缩" vs "意图保持型压缩"                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  传统压缩：                                                                  │
│  ─────────                                                                  │
│  • 丢失意图、丢失语义、丢失上下文                                              │
│  • "帮我优化这个函数的性能" → 模糊，需要大量额外上下文                          │
│                                                                             │
│  意图保持型压缩：                                                            │
│  ────────────────────                                                        │
│  • 保留意图、保留接口、保留依赖关系                                            │
│  • "帮我优化这个函数的性能" → 精确，可执行，所需上下文最少                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. 代码"签名化"而非"全文化"

```python
# 原始代码（200 tokens）
def process_user_order(user_id: int, items: List[Item], payment_method: str) -> Order:
    """处理用户订单，包含库存检查、支付验证、订单创建"""
    if not validate_user(user_id):
        raise ValueError("用户不存在")
    for item in items:
        if not check_inventory(item.id, item.quantity):
            raise InsufficientStockError(item.name)
    payment_result = process_payment(user_id, items, payment_method)
    order = create_order(user_id, items, payment_result.transaction_id)
    send_confirmation_email(user_id, order.id)
    return order

# 压缩后的"签名"（20 tokens）≈ 10:1 压缩比
<Function: process_user_order>
Params: (user_id: int, items: List[Item], payment_method: str) -> Order
Purpose: 处理用户订单（库存检查、支付验证、订单创建、邮件通知）
Dependencies: [validate_user, check_inventory, process_payment, create_order, send_confirmation_email]
```

**压缩原则**：
- ✅ 保留：函数签名、目的描述、依赖关系
- ❌ 丢弃：实现细节、样板代码、空白行

---

### 2. 分层上下文金字塔

```python
class ContextPyramid:
    """根据任务粒度，提供不同精度的上下文"""
    
    def build_for_intent(self, intent, target_code):
        pyramid = {
            # Level 1: 一句话概括（5 tokens）
            "summary": self.generate_one_line_summary(target_code),
            
            # Level 2: 函数签名/类定义（20 tokens）
            "interface": self.extract_interface(target_code),
            
            # Level 3: 关键代码块（100 tokens）
            "hotspots": self.identify_hotspots(target_code),
            
            # Level 4: 依赖关系图（50 tokens）
            "dependencies": self.list_dependencies(target_code),
            
            # Level 5: 完整代码（最后选项，200 tokens）
            "full_code": target_code
        }
        
        # 🎯 根据意图类型智能选择
        if intent.type == "code_review":
            return pyramid["summary"] + pyramid["hotspots"]
        elif intent.type == "refactor":
            return pyramid["interface"] + pyramid["dependencies"]
        elif intent.type == "bug_fix":
            return pyramid["full_code"]  # 需要完整上下文
        elif intent.type == "quick_query":
            return pyramid["summary"]
        
        return pyramid["summary"] + pyramid["interface"]
```

**分层策略表**：

| 意图类型 | 需要的层级 | 典型 Token 消耗 |
|---------|----------|----------------|
| 简单询问 | L1 | ~10 tokens |
| 接口变更 | L1 + L2 | ~30 tokens |
| 代码审查 | L1 + L3 | ~150 tokens |
| 重构 | L2 + L4 | ~100 tokens |
| Bug 修复 | L5（全量） | ~300 tokens |

---

### 3. "意图编码"技术

```python
# 原始意图（模糊，需要大量上下文）
"帮我优化这个函数的性能，特别是数据库查询部分"

# 编码后的意图（精确，可执行）
{
    "action": "optimize_performance",
    "target": "function:process_user_order",
    "focus_areas": ["database_queries"],
    "constraints": {
        "keep_interface": True,
        "backward_compatible": True
    },
    "metrics": ["execution_time", "memory_usage"],
    "expected_improvement": ">20% faster"
}
```

**意图编码器实现**：

```python
class IntentEncoder:
    """将自然语言意图编码为结构化查询"""
    
    # 常见意图模式库
    INTENT_PATTERNS = {
        "optimize_performance": {
            "keywords": ["优化", "性能", "加速", "提升速度"],
            "required_fields": ["target", "focus_areas"],
            "optional_fields": ["metrics", "expected_improvement"]
        },
        "fix_bug": {
            "keywords": ["修复", "bug", "错误", "崩溃"],
            "required_fields": ["target", "symptoms"],
            "optional_fields": ["error_log", "reproduction_steps"]
        },
        "add_feature": {
            "keywords": ["添加", "新增", "实现", "功能"],
            "required_fields": ["feature_description"],
            "optional_fields": ["dependencies", "constraints"]
        },
        "refactor": {
            "keywords": ["重构", "优化代码", "清理"],
            "required_fields": ["target", "goal"],
            "optional_fields": ["constraints", "keep_apis"]
        }
    }
    
    def encode(self, natural_language_intent: str) -> dict:
        # 1. 识别意图类型
        intent_type = self.classify_intent(natural_language_intent)
        
        # 2. 提取关键实体
        entities = self.extract_entities(natural_language_intent)
        
        # 3. 构建结构化查询
        encoded = {
            "type": intent_type,
            "original": natural_language_intent,
            **entities
        }
        
        # 4. 添加意图类型特定的字段
        if intent_type in self.INTENT_PATTERNS:
            pattern = self.INTENT_PATTERNS[intent_type]
            for field in pattern.get("required_fields", []):
                if field not in encoded:
                    encoded[field] = None  # 标记为需要补充
        
        return encoded
```

---

### 4. 增量式上下文加载

```python
class IncrementalContextLoader:
    """懒加载 + 按需扩展的上下文加载"""
    
    async def load(self, initial_intent):
        # 🚀 第一步：加载核心文件（必须的）
        core_files = self.identify_core_files(initial_intent)
        context = self.load_files(core_files)
        
        # 🤖 第二步：让 AI 分析还缺少什么
        ai_response = await self.llm.ask(
            f"基于这些上下文，还需要看什么文件来完成任务？\n"
            f"意图：{initial_intent}\n"
            f"已有：{list(core_files)}\n"
            f"请列出还需要的关键文件（最多 5 个）。"
        )
        
        # 📦 第三步：加载 AI 请求的额外文件
        additional_files = self.parse_ai_request(ai_response)
        context += self.load_files(additional_files[:5])  # 限制数量
        
        # ⚡ 第四步：检查是否还需要更多（递归，但限制深度）
        if len(additional_files) > 5:
            remaining = await self.identify_critical_files(
                context, initial_intent
            )
            context += self.load_files(remaining)
        
        return context
```

---

### 5. 上下文摘要生成器

```python
class ContextSummarizer:
    """在本地生成高质量的代码摘要"""
    
    def summarize_codebase(self, file_paths: List[str]) -> str:
        summaries = []
        
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 🔍 生成结构化摘要
            summary = {
                "file": file_path,
                "size_kb": len(code) / 1024,
                "exports": self.extract_exports(code),
                "imports": self.extract_imports(code),
                "key_functions": self.extract_key_functions(code),
                "complexity": self.calculate_complexity(code),
                "purpose": self.infer_purpose(code)
            }
            summaries.append(summary)
        
        return self.format_summaries(summaries)
    
    def extract_exports(self, code: str) -> List[str]:
        """提取导出的函数/类"""
        # 支持多语言
        patterns = [
            r'def (\w+)',           # Python
            r'function (\w+)',      # JavaScript
            r'class (\w+)',         # Python/JavaScript
            r'export (?:default )?(\w+)',  # ES6
        ]
        exports = []
        for pattern in patterns:
            exports.extend(re.findall(pattern, code))
        return exports
    
    def calculate_complexity(self, code: str) -> dict:
        """计算代码复杂度"""
        return {
            "cyclomatic": self.count_branches(code),  # 分支复杂度
            "cognitive": self.estimate_cognitive(code),  # 认知复杂度
            "lines": len(code.splitlines()),
            "score": self.weighted_score(code)  # 综合评分
        }
```

---

### 6. 语义分块与重要性排序

```python
class SemanticChunker:
    """按语义重要性分块，而非简单按行分块"""
    
    def chunk_by_importance(self, code: str, max_tokens: int = 1000) -> str:
        # 1. 解析 AST，识别不同节点的重要性
        tree = self.parse_ast(code)
        
        # 2. 为每个节点打分
        nodes_with_scores = []
        for node in self.walk_ast(tree):
            score = self.score_node_importance(node)
            nodes_with_scores.append((
                node, 
                score, 
                self.node_to_text(node)
            ))
        
        # 3. 按重要性排序，优先保留高分节点
        nodes_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 4. 从高分到低分填充，直到达到 token 限制
        selected_chunks = []
        token_count = 0
        
        for node, score, text in nodes_with_scores:
            node_tokens = self.count_tokens(text)
            if token_count + node_tokens <= max_tokens:
                selected_chunks.append(text)
                token_count += node_tokens
            else:
                break  # 达到限制
        
        return "\n\n".join(selected_chunks)
    
    def score_node_importance(self, node: dict) -> float:
        """根据节点类型和位置计算重要性分数"""
        base_scores = {
            "function_def": 1.0,
            "class_def": 0.9,
            "if_statement": 0.3,
            "for_loop": 0.3,
            "while_loop": 0.3,
            "try_block": 0.4,
            "comment": 0.1,
            "docstring": 0.5
        }
        
        score = base_scores.get(node["type"], 0.2)
        
        # 📍 位置加权：越靠前越重要
        position_factor = 1.0 / (node.get("line", 0) + 1)
        score *= (1 + position_factor)
        
        # 🔗 引用次数加权：被引用越多越重要
        if node.get("is_exported"):
            score *= 1.5
        
        return score
```

---

### 7. 无损压缩关键技术

#### 技术 1：保持接口，丢弃实现

```python
# 压缩前（200 tokens）
def calculate_price(items, tax_rate, discount=0):
    subtotal = sum(item.price * item.quantity for item in items)
    tax = subtotal * tax_rate
    total = subtotal + tax
    if discount:
        total *= (1 - discount)
    return total

# 压缩后（30 tokens）✅ 保留接口和目的
<Function: calculate_price>
Input: items(List[Item]), tax_rate(float), discount(float)=0
Output: float
Description: 计算订单总价（小计+税费-折扣）
Complexity: O(n)
```

#### 技术 2：保持依赖图，丢弃调用细节

```python
# 不传输调用细节，只传输调用关系
<Call Graph>
calculate_price → [sum, Item.price, Item.quantity]
process_order → [calculate_price, validate_items, create_invoice]
main → [process_order, log_result]
```

#### 技术 3：保持设计模式，丢弃样板代码

```python
# 识别代码中的模式，用模式名替代代码
<Design Pattern: Observer>
Subject: OrderSystem
Observers: [EmailNotifier, InventoryUpdater, AnalyticsTracker]
Event: order_created
```

---

## 💰 上下文经济学：Token 即货币

> 把 Token 当作货币，建立一套"价值判断体系"。

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Token 价值评估体系                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  📈 高价值 Token（必须保留）：                                                │
│  ───────────────────────────                                                 │
│  • 接口定义（函数签名、类定义）                                               │
│  • 依赖关系（import/export）                                                 │
│  • 意图信息（任务类型、约束条件）                                             │
│                                                                             │
│  📊 中等价值 Token（尽量保留）：                                              │
│  ──────────────────────────                                                  │
│  • 核心逻辑（关键算法、业务规则）                                             │
│  • 错误处理（异常处理、边界条件）                                             │
│                                                                             │
│  📉 低价值 Token（可丢弃）：                                                  │
│  ──────────────────                                                          │
│  • 样板代码（getter/setter、空行）                                           │
│  • 重复模式（相似代码块）                                                     │
│                                                                             │
│  💨 零价值 Token（必须丢弃）：                                                 │
│  ──────────────────                                                          │
│  • 注释和空白                                                                 │
│  • 调试代码（console.log、print）                                             │
│  • 废弃代码（deprecated、TODO 未完成）                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Token 预算制度

```python
class TokenBudget:
    """Token 预算分配器"""
    
    BUDGETS = {
        "quick_query": 512,      # 简单询问
        "simple_task": 2048,     # 中等任务
        "complex_task": 8192,    # 复杂任务
        "deep_analysis": 16384,  # 深度分析
    }
    
    def should_include(self, code_chunk: str, intent: dict) -> bool:
        """计算这个代码块对当前意图的投资回报率"""
        relevance = self.calculate_relevance(code_chunk, intent)
        token_cost = self.count_tokens(code_chunk)
        
        # 💡 ROI = 相关性 / Token 成本
        roi = relevance / token_cost
        
        # 只保留高 ROI 的代码块
        return roi > 0.001  # 阈值可调


class TokenAllocator:
    """Token 预算动态分配"""
    
    def allocate(self, intent: str, available_budget: int) -> dict:
        """根据意图类型分配 Token 预算"""
        
        base_allocation = {
            # 基础分配：接口层（必须）
            "interface": 100,
            
            # 意图相关：核心逻辑（按意图类型）
            "intent_specific": self.BUDGETS.get(intent, 500),
            
            # 上下文：相关文件摘要（可压缩）
            "context": 300,
            
            # 缓冲：边界情况处理
            "buffer": 50
        }
        
        total = sum(base_allocation.values())
        
        # 如果超出预算，等比压缩
        if total > available_budget:
            scale = available_budget / total
            base_allocation = {
                k: int(v * scale) for k, v in base_allocation.items()
            }
        
        return base_allocation
```

---

### 工作流优化：预处理 + 后处理

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完整预处理管道                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户请求                                                                   │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ 意图分析器   │ → 确定任务类型                                              │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ 上下文选择器 │ → 选择相关文件                                              │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ 代码压缩器   │ → 压缩为摘要（签名化）                                      │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ 意图编码器   │ → 编码为结构化查询                                          │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ LLM API     │ → 生成代码                                                  │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  ┌─────────────┐                                                            │
│  │ 后处理器    │ → 补全引用、检查完整性                                      │
│  └─────────────┘                                                            │
│      │                                                                     │
│      ▼                                                                     │
│  输出结果                                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**后处理器实现**：

```python
class PostProcessor:
    """补全 LLM 输出的不完整引用"""
    
    def complete_partial_code(self, ai_response: str, original_context: dict) -> str:
        """AI 可能生成了不完整的代码（引用未传输的函数）"""
        
        # 1. 提取 AI 响应中引用的符号
        referenced_symbols = self.extract_references(ai_response)
        
        # 2. 检查每个符号是否已在响应中定义
        defined_symbols = self.extract_definitions(ai_response)
        
        # 3. 补全缺失的符号
        for symbol in referenced_symbols:
            if symbol not in defined_symbols:
                # 从原始代码库中找到这个符号的实现
                implementation = self.find_implementation(
                    symbol, 
                    original_context["codebase"]
                )
                # 注入实现（可以是签名形式）
                ai_response = self.inject_signature(
                    ai_response, 
                    symbol, 
                    implementation
                )
        
        return ai_response
```

---

## 🔮 端到端体验优化：弥合本地与云端的差距

> **核心洞察**：本地部署有强大的模型，但缺少"AI原生开发环境"的端到端体验。这就像有一台顶配发动机，却没有方向盘、仪表盘和悬挂系统。

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                    "体验鸿沟" vs "端到端优化"                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  本地部署的"慢"，不是因为模型弱，而是因为交互充满了"摩擦"：                        │
│                                                                             │
│  1. 上下文切换摩擦：在IDE、浏览器、终端、聊天窗口之间来回切换                      │
│  2. 等待摩擦："提问 -> 等待 -> 验证 -> 再提问"的漫长循环                        │
│  3. 执行摩擦：模型只能"说"，不能"做"，你手动实现它的每个建议                      │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  云端IDE的优势不是模型更强，而是整个交互流程没有"摩擦"：                          │
│  • 项目上下文自动附加                                                         │
│  • 预测性预加载（零等待）                                                     │
│  • 模型可以直接执行代码、调用工具                                               │
│  • 从使用中持续学习你的偏好                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 🧠 1. 上下文感知与项目管理

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                      上下文感知优化矩阵                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优化方向               云/现代IDE的做法           本地部署缺失               │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  项目级上下文注入        自动分析 package.json、      模型对项目全局一无所知    │
│                         requirements.txt、Makefile   每次都要手动说明        │
│                         作为系统提示的一部分                                      │
│                                                                             │
│  活跃文件感知           自动附加当前文件、光标附近      需要手动复制粘贴代码     │
│                         代码、错误信息                打断工作流               │
│                                                                             │
│  智能断点注入           模型可被注入调试会话，         调试和模型帮助完全割裂    │
│                         分析变量状态、解释崩溃原因                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：Project Context Injector**

```python
class ProjectContextInjector:
    """自动为模型注入项目级上下文"""
    
    async def inject_project_context(self, workspace_root: str) -> dict:
        """分析项目结构，生成上下文"""
        
        # 1. 分析技术栈
        tech_stack = {
            "language": self.detect_language(workspace_root),
            "framework": self.detect_framework(workspace_root),
            "build_tools": self.detect_build_tools(workspace_root),
            "dependencies": self.load_dependencies(workspace_root)
        }
        
        # 2. 分析项目结构
        structure = {
            "dirs": self.list_dirs(workspace_root, depth=2),
            "entry_points": self.find_entry_points(workspace_root),
            "config_files": self.find_configs(workspace_root)
        }
        
        # 3. 分析编码规范
        conventions = {
            "naming": self.infer_naming_conventions(workspace_root),
            "import_style": self.infer_import_style(workspace_root),
            "patterns": self.find_common_patterns(workspace_root)
        }
        
        return {
            "tech_stack": tech_stack,
            "structure": structure,
            "conventions": conventions,
            "project_description": await self.generate_description(workspace_root)
        }
    
    async def inject_active_file_context(self, editor_state: EditorState) -> str:
        """注入当前编辑状态"""
        
        return f"""
当前文件: {editor_state.file_path}
光标位置: Line {editor_state.cursor_line}, Column {editor_state.cursor_column}
选中代码:
```{editor_state.language}
{editor_state.selected_code}
```

附近代码:
```{editor_state.language}
{editor_state.nearby_code}
```
"""
```

---

### ⚡ 2. 延迟优化与交互模式

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                        延迟优化技术矩阵                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优化方向               云/现代IDE的做法           本地部署缺失               │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  预测性预加载           识别编码模式（如输入 def），    每次触发都要从零开始     │
│                         提前加载模型到GPU显存         有可感知的延迟            │
│                                                                             │
│  渐进式输出             以"区块"为单位生成代码，       要么等很久得到完整代码     │
│                         生成一块确认一块             要么流式但无法中途干预      │
│                                                                             │
│  离线优先模式           本地小型模型处理简单任务，     所有请求都由同一大模型处理  │
│                         复杂任务转发云端大模型        杀鸡用牛刀               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：Predictive Preloader**

```python
class PredictivePreloader:
    """预测性预加载，减少等待时间"""
    
    # 常见编码模式 → 预加载触发器
    CODE_PATTERNS = {
        r"^def\s+\w+\(.*\):$": "completion_model",
        r"^class\s+\w+.*:$": "completion_model",
        r"^import\s+": "completion_model",
        r"^from\s+\w+\s+import": "completion_model",
        r"# TODO|FIXME|XXX": "analysis_model",
        r"raise\s+\w+Error": "debug_model",
    }
    
    def __init__(self, models: dict):
        self.models = models
        self.warm_models = {}  # 已预热的模型
        self.predictor = load_prediction_model()
    
    def on_keystroke(self, buffer: str):
        """检测编码模式，预测性预加载"""
        
        # 1. 模式匹配
        for pattern, model_name in self.CODE_PATTERNS.items():
            if re.search(pattern, buffer):
                self._warm_up_model(model_name)
                break
        
        # 2. 使用预测模型
        next_tokens = self.predictor.predict(buffer)
        if next_tokens.confidence > 0.9:
            self._preload_tokens(next_tokens.tokens)


class ProgressiveOutputRenderer:
    """渐进式输出渲染"""
    
    async def stream_progressive(
        self, 
        llm_stream, 
        block_size: int = 3  # 每3个token一个块
    ):
        """以块为单位输出，用户可以中途干预"""
        
        buffer = []
        for token in llm_stream:
            buffer.append(token)
            
            # 当积累到一块时输出
            if len(buffer) >= block_size:
                yield self._render_block(buffer)
                buffer = []
                
                # 检查用户是否干预
                if self.check_user_intervention():
                    yield self._render_pause()
                    return
        
        # 输出剩余
        if buffer:
            yield self._render_block(buffer)
```

**解决方案：Hierarchical Model Router**

```python
class HierarchicalModelRouter:
    """分层模型路由 — 简单任务用小模型"""
    
    def __init__(self):
        # L0: 边缘模型（快速响应）
        self.edge_model = OllamaClient("smollm2:latest")
        
        # L1: 轻量模型（日常任务）
        self.light_model = OllamaClient("qwen2.5:1.5b")
        
        # L3: 推理模型（复杂任务）
        self.reasoning_model = OllamaClient("qwen3.5:4b")
        
        # L4: 深度模型（专家级）
        self.deep_model = OllamaClient("qwen3.5:9b")
    
    def route(self, intent: str, context: dict) -> str:
        """智能路由到最合适的模型"""
        
        # 简单任务 → 边缘模型
        if self._is_simple(intent):
            return self.edge_model
        
        # 补全/重命名 → 轻量模型
        if self._is_completion(intent):
            return self.light_model
        
        # 推理/调试 → 推理模型
        if self._needs_reasoning(intent):
            return self.reasoning_model
        
        # 架构/设计 → 深度模型
        if self._needs_expertise(intent, context):
            return self.deep_model
    
    def _is_simple(self, intent: str) -> bool:
        """判断是否为简单任务"""
        simple_patterns = [
            r"^这是什么", r"^怎么用", r"^告诉我",
            r"帮我翻译", r"解释一下"
        ]
        return any(re.search(p, intent) for p in simple_patterns)
```

---

### 🔧 3. 工具与执行集成

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                        工具执行集成矩阵                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优化方向               云/现代IDE的做法           本地部署缺失               │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  内置代码解释器         模型代码可在沙箱中自动运行，    需要手动复制运行        │
│                         验证结果并自动修复错误         循环往复                │
│                                                                             │
│  工具调用               模型可执行终端命令、读写文件、   只是一个聊天机器人      │
│                         查询数据库、Git操作          没有执行能力             │
│                                                                             │
│  调试器集成             模型直接读取调用堆栈、变量，     调试是调试，AI是AI      │
│                         给出修复建议并热重载          没有连接               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：Function Calling Framework**

```python
class ToolEnabledAgent:
    """具备工具调用能力的Agent"""
    
    def __init__(self, llm: OllamaClient):
        self.llm = llm
        self.tools = ToolRegistry()
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        
        # 文件操作
        self.tools.register("read_file", {
            "description": "读取文件内容",
            "params": {"file_path": "str"},
            "execute": lambda p: self._read_file(p["file_path"])
        })
        
        self.tools.register("write_file", {
            "description": "写入文件内容",
            "params": {"file_path": "str", "content": "str"},
            "execute": lambda p: self._write_file(p["file_path"], p["content"])
        })
        
        # 终端命令
        self.tools.register("run_command", {
            "description": "执行终端命令",
            "params": {"command": "str", "cwd": "str?"},
            "execute": lambda p: self._run_command(p["command"], p.get("cwd"))
        })
        
        # Git操作
        self.tools.register("git_commit", {
            "description": "Git提交",
            "params": {"message": "str", "files": "list[str]?"},
            "execute": lambda p: self._git_commit(p["message"], p.get("files"))
        })
        
        # 调试器集成
        self.tools.register("debugger_query", {
            "description": "查询调试器状态",
            "params": {"frame": "int?", "expression": "str"},
            "execute": lambda p: self._query_debugger(p.get("frame"), p["expression"])
        })
    
    async def chat(self, user_message: str) -> str:
        """带工具调用的对话"""
        
        # 1. 构建工具描述
        tools_prompt = self._build_tools_description()
        
        # 2. LLM决定是否调用工具
        response = await self.llm.chat([
            {"role": "system", "content": tools_prompt},
            {"role": "user", "content": user_message}
        ])
        
        # 3. 执行工具调用
        while response.tool_calls:
            for call in response.tool_calls:
                result = await self.tools.execute(call.name, call.arguments)
                response = await self.llm.continue_chat(
                    f"Tool result: {result}"
                )
        
        return response.content
```

**解决方案：Sandbox Code Executor**

```python
class SandboxExecutor:
    """安全沙箱代码执行"""
    
    def __init__(self, container_manager):
        self.container_manager = container_manager
    
    async def execute_code(
        self, 
        code: str, 
        language: str,
        timeout: int = 30
    ) -> ExecutionResult:
        """在沙箱中安全执行代码"""
        
        # 1. 创建隔离容器
        container = await self.container_manager.create(
            image=f"sandbox-{language}",
            timeout=timeout,
            memory_limit="256MB",
            network="none"  # 完全隔离
        )
        
        try:
            # 2. 执行代码
            result = await container.run(code)
            
            # 3. 收集结果
            return ExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                execution_time=result.duration
            )
        
        finally:
            # 4. 清理容器
            await container.destroy()
    
    async def execute_with_verification(
        self, 
        original_code: str,
        ai_fixed_code: str,
        test_cases: List[TestCase]
    ) -> VerificationResult:
        """执行并验证修复"""
        
        # 1. 先运行原始代码
        original_result = await self.execute_code(original_code)
        
        # 2. 运行AI修复代码
        fixed_result = await self.execute_code(ai_fixed_code)
        
        # 3. 运行测试用例
        test_results = []
        for test in test_cases:
            result = await self.execute_code(test.code)
            test_results.append({
                "name": test.name,
                "passed": result.exit_code == 0,
                "output": result.stdout
            })
        
        return VerificationResult(
            original_passed=original_result.exit_code == 0,
            fixed_passed=fixed_result.exit_code == 0,
            tests=test_results,
            suggestion=self._generate_suggestion(original_result, fixed_result)
        )
```

---

### 📊 4. 数据与反馈循环

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                        反馈循环系统矩阵                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优化方向               云/现代IDE的做法           本地部署缺失               │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  实时偏好学习           观察代码接受/修改行为，        模型是"通用"的           │
│                         学习编码风格、命名习惯         不会为你个人优化         │
│                                                                             │
│  质量评分与迭代         默默收集满意度（采纳/修改），  没有反馈机制            │
│                         持续优化底层模型             模型不会从使用中改进       │
│                                                                             │
│  知识库检索增强         结合内部文档、API手册、         模型只依赖通用知识       │
│                         优秀代码案例进行检索增强        不了解团队规范          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：Preference Learning System**

```python
class PreferenceLearningSystem:
    """从使用中学习用户偏好"""
    
    def __init__(self, db: SQLiteDB):
        self.db = db
        self.preference_model = load_preference_model()
    
    def record_interaction(self, interaction: CodeInteraction):
        """记录每次代码交互"""
        
        # 1. 记录原始生成
        self.db.insert("interactions", {
            "timestamp": datetime.now(),
            "generated_code": interaction.generated_code,
            "user_action": interaction.action,  # accepted/modified/rejected
            "modifications": interaction.modifications,
            "context": interaction.context,
            "intent": interaction.intent
        })
        
        # 2. 分析修改模式
        if interaction.action == "modified":
            self._learn_from_modification(interaction)
    
    def _learn_from_modification(self, interaction: CodeInteraction):
        """从修改中学习偏好"""
        
        # 提取命名偏好
        naming_patterns = self._extract_naming_patterns(
            interaction.modifications
        )
        
        # 提取风格偏好
        style_preferences = self._extract_style_preferences(
            interaction.generated_code,
            interaction.modifications
        )
        
        # 提取库偏好
        library_preferences = self._extract_library_preferences(
            interaction.modifications
        )
        
        # 更新偏好模型
        self.preference_model.update(
            naming=naming_patterns,
            style=style_preferences,
            libraries=library_preferences
        )
    
    def get_personalized_context(self, intent: str) -> dict:
        """获取个性化上下文"""
        
        preferences = self.preference_model.get_preferences()
        
        return {
            "naming_convention": preferences.naming,
            "code_style": preferences.style,
            "preferred_libraries": preferences.libraries,
            "common_patterns": preferences.patterns
        }
```

**解决方案：Quality Feedback Loop**

```python
class QualityFeedbackLoop:
    """质量评分与持续改进"""
    
    def __init__(self):
        self.quality_db = SQLiteDB("quality_metrics.db")
    
    async def record_quality(
        self, 
        request: str, 
        response: str, 
        user_action: str
    ):
        """记录质量指标"""
        
        quality_score = self._calculate_quality(
            request=request,
            response=response,
            action=user_action
        )
        
        await self.quality_db.insert("quality_log", {
            "request_hash": hash(request),
            "response_hash": hash(response),
            "score": quality_score,
            "action": user_action,
            "timestamp": datetime.now()
        })
    
    def _calculate_quality(
        self, 
        request: str, 
        response: str, 
        action: str
    ) -> float:
        """计算质量分数"""
        
        # 1. 采纳率（0-1）
        adoption_score = 1.0 if action == "accepted" else 0.0
        
        # 2. 修改程度（0-1，越小越好）
        modification_score = self._calculate_modification_ratio(
            request, response
        )
        
        # 3. 可执行性（0-1）
        executability_score = self._estimate_executability(response)
        
        # 综合分数
        return (
            adoption_score * 0.4 +
            (1 - modification_score) * 0.3 +
            executability_score * 0.3
        )
    
    async def get_improvement_suggestions(self) -> List[str]:
        """获取改进建议"""
        
        # 分析近期质量趋势
        recent_scores = await self.quality_db.query("""
            SELECT score FROM quality_log 
            ORDER BY timestamp DESC LIMIT 100
        """)
        
        if np.mean(recent_scores) < 0.7:
            return [
                "考虑使用更小的模型处理简单任务",
                "增加更多上下文信息",
                "调整提示词模板"
            ]
        
        return []
```

---

### 🧩 5. 多模态与扩展

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                        多模态能力矩阵                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优化方向               云/现代IDE的做法           本地部署缺失               │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  截图/白板集成           理解UI截图、架构图，           只能处理文本            │
│                          生成对应代码或文档                                     │
│                                                                             │
│  语音交互               语音自然描述需求，              纯键盘输入              │
│                          模型理解并执行                                          │
│                                                                             │
│  插件生态系统           专用AI插件市场，               功能固定，难以扩展        │
│                          扩展模型能力边界                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：Multimodal Pipeline**

```python
class MultimodalPipeline:
    """多模态输入处理"""
    
    def __init__(self, vision_model, audio_model):
        self.vision = vision_model
        self.audio = AudioProcessor()
        self.audio_model = audio_model
    
    async def process_image(self, image_path: str, intent: str) -> str:
        """处理图片输入"""
        
        # 1. 视觉理解
        visual_description = await self.vision.analyze(
            image_path,
            intent=intent
        )
        
        # 2. 结合意图生成代码
        prompt = f"""
        图片内容: {visual_description}
        用户意图: {intent}
        
        请生成对应的代码实现。
        """
        
        return await self.llm.generate(prompt)
    
    async def process_voice(self, audio_path: str) -> str:
        """处理语音输入"""
        
        # 1. 语音转文字
        transcription = await self.audio.transcribe(audio_path)
        
        # 2. 意图理解
        intent = await self.intent_engine.parse(transcription)
        
        return intent
```

---

### 🎯 完整工作流：从"聊天对象"到"副驾驶"

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                        目标工作流：端到端副驾驶                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户输入: "帮我修复这个bug"                                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 1: 上下文自动附加                                                 │   │
│  │ • 自动附上当前文件和错误堆栈                                            │   │
│  │ • 项目级上下文注入（技术栈、编码规范）                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 2: 智能模型路由                                                   │   │
│  │ • 简单任务 → 边缘模型（毫秒响应）                                        │   │
│  │ • 复杂任务 → 深度模型                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 3: 工具调用执行                                                   │   │
│  │ • 模型调用调试器获取变量值                                              │   │
│  │ • 分析错误原因                                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 4: 沙箱验证                                                       │   │
│  │ • 生成修复代码                                                          │   │
│  │ • 在沙箱中运行测试                                                      │   │
│  │ • 测试通过后询问用户                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 5: 用户确认                                                       │   │
│  │ • 展示diff                                                             │   │
│  │ • 用户一键应用                                                          │   │
│  │ • 自动提交到Git                                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  结果: 全程无需离开编辑器，无需手动复制粘贴                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 🚀 落地路线图

| 阶段 | 时间 | 功能 | 复杂度 |
|------|------|------|--------|
| **Phase 1** | 第1周 | 工具注册 + 函数调用 | 中 |
| **Phase 2** | 第2周 | 项目上下文注入器 | 中 |
| **Phase 3** | 第3周 | 分层模型路由 + 预加载 | 高 |
| **Phase 4** | 第4周 | 沙箱代码执行 | 高 |
| **Phase 5** | 第5-6周 | 偏好学习 + 反馈循环 | 高 |
| **Phase 6** | 第7-8周 | 多模态输入 | 中 |

---

## 🚀 立即行动清单（意图保持型压缩）

| 优先级 | 任务 | 说明 | 预期收益 |
|-------|------|------|---------|
| **P0** | 函数签名提取器 | 提取函数签名、目的、依赖 | 5:1 压缩比 |
| **P0** | 意图编码器 | 将自然语言编码为结构化查询 | 减少 50% 上下文需求 |
| **P1** | 分层上下文金字塔 | 实现 L1-L5 分层加载 | 按需加载，极致优化 |
| **P1** | 语义重要性排序 | AST 分析 + 重要性打分 | 保留关键信息，丢弃噪声 |
| **P2** | Token ROI 计算器 | 评估每个 Token 的价值 | 智能裁剪，最大化信息密度 |
| **P2** | 后处理器 | 补全 LLM 输出的引用 | 提高输出可用性 |

---

### 核心技术指标

```python
# 压缩效果评估
COMPRESSION_METRICS = {
    "signature_extraction": {
        "compression_ratio": "10:1",
        "intent_retention": ">95%",
        "use_case": ["接口变更", "快速审查"]
    },
    "context_pyramid": {
        "compression_ratio": "5:1 - 50:1",
        "intent_retention": "根据层级变化",
        "use_case": ["所有场景"]
    },
    "intent_encoding": {
        "compression_ratio": "3:1",
        "intent_retention": ">99%",
        "use_case": ["精确任务", "自动化执行"]
    },
    "semantic_chunking": {
        "compression_ratio": "3:1 - 10:1",
        "intent_retention": ">90%",
        "use_case": ["复杂任务", "深度分析"]
    }
}
```

---

## 🧠 推理式编程助手：透明AI + Git工作流

> **核心设计理念**：推理引擎 + 可视化轨迹 + Git工作流三大支柱，打造超越代码补全的全流程开发伙伴。

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                   推理式编程助手架构                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        开发者界面层                                    │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │   │
│  │   │任务分解 │  │推导过程 │  │代码对比 │  │Git历史 │               │   │
│  │   │可视化   │  │可视化   │  │视图     │  │可视化   │               │   │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    推理引擎与任务管理                                   │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │  任务分解器  │ 代码分析器  │  依赖分析器  │  项目图谱    │   │   │
│  │   │ (OpenCode风格)│  (AST分析)  │  (项目理解)  │  (全链路)    │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │  推导链追踪  │   验证器   │  回滚管理器  │  操作栈     │   │   │
│  │   │  (思维链记录)│  (测试/编译)│  (Git集成)   │  (可回退)   │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    工具执行与Git集成层                                 │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │   │
│  │   │ 代码修改 │  │ 文件操作 │  │ 终端执行 │  │ Git操作  │               │   │
│  │   │ 工具    │  │ 工具     │  │ 工具     │  │ 工具     │               │   │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 🔄 核心工作流程：推理-分解-执行-提交

#### 阶段 1：意图分析与任务分解（OpenCode风格）

```python
# 用户输入示例
user_input = "我想在用户详情页添加一个订单历史tab"

# AI 推理过程展示
"""
1. 分析意图
   ├─ 需要修改前端页面
   ├─ 需要新增API接口
   └─ 需要更新数据库查询

2. 分解任务
   ├─ 任务1: 在前端添加Tab组件
   │   ├─ 子任务1.1: 修改路由配置
   │   ├─ 子任务1.2: 创建OrderHistory组件
   │   └─ 子任务1.3: 添加样式
   │
   ├─ 任务2: 后端API支持
   │   ├─ 子任务2.1: 新增GET /api/users/{id}/orders
   │   ├─ 子任务2.2: 添加数据层逻辑
   │   └─ 子任务2.3: 更新API文档
   │
   └─ 任务3: 数据库优化
       ├─ 子任务3.1: 添加订单查询索引
       └─ 子任务3.2: 优化关联查询
"""

class TaskDecomposer:
    """任务分解器 - OpenCode风格"""
    
    def __init__(self, llm, project_analyzer):
        self.llm = llm
        self.project_analyzer = project_analyzer
        
    async def decompose_task(self, user_input: str) -> TaskGraph:
        # 1. 分析代码结构
        project_structure = await self.project_analyzer.get_structure()
        
        # 2. LLM 推理分解
        decomposition_prompt = f"""
        任务: {user_input}
        项目结构: {project_structure}
        
        请分解这个任务，考虑：
        1. 需要修改哪些文件
        2. 依赖关系是什么
        3. 每个子任务的预期产出
        4. 可能的难点和解决方案
        
        返回JSON格式的任务树。
        """
        
        # 3. 构建任务图
        task_graph = await self.build_task_graph(llm_response)
        
        # 4. 评估依赖和执行顺序
        await self.calculate_dependencies(task_graph)
        
        return task_graph
```

---

### 🎨 可视化推导过程（Trae风格）

```python
# 界面布局：任务分解 + 推导过程 + 代码对比

┌─────────────────────────────────────────────────────────────────────────────┐
│ 任务分解视图 (左侧)              │ 推导过程详情 (中间)                       │
│                                  │                                          │
│  ├─ 📁 任务1: 前端修改           │  🔍 当前聚焦: 创建组件                    │
│  │   ├─ 📄 修改路由               │                                          │
│  │   ├─ 📄 创建组件               │  💭 思考过程:                            │
│  │   └─ 🎨 添加样式               │  - 需要复用现有UI组件库                   │
│  │                                │  - 遵循团队TypeScript规范                 │
│  ├─ 📁 任务2: 后端API            │  - 考虑移动端响应式                       │
│  │   └─ 📄 新增接口               │                                          │
│  │                                │  📝 决策记录:                            │
│  └─ 📁 任务3: 数据库优化          │  ✅ 使用Grid布局而非Flex                   │
│      └─ 📄 添加索引               │  ✅ 使用useQuery管理状态                   │
│                                  │  ❌ 不添加新的依赖库                       │
├──────────────────────────────────┴─────────────────────────────────────────┤
│ 代码对比视图 (底部)                                                          │
│ ┌─────────────────┐  ┌─────────────────┐                                       │
│ │ 原文件          │  │ 修改后           │                                       │
│ │ function Old() {│  │ function New() {│                                       │
│ │   return ...    │  │   return ...    │                                       │
│ │ }               │  │   // AI添加     │                                       │
│ │                 │  │   return ...    │                                       │
│ │                 │  │ }               │                                       │
│ └─────────────────┘  └─────────────────┘                                       │
│ [应用更改] [修改建议] [跳过此文件]                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**推理过程记录数据结构**：

```python
class ReasoningStep:
    """每个推理步骤的完整记录"""
    
    def __init__(self):
        self.id = uuid.uuid4()
        self.timestamp = datetime.now()
        self.thought = ""           # 思考过程
        self.alternatives = []      # 考虑的替代方案
        self.decision = ""          # 最终决定
        self.reason = ""            # 决策原因
        self.artifacts = []         # 相关代码片段
        self.validation = None      # 验证结果
        
    def to_markdown(self) -> str:
        """导出为可读的推理链"""
        return f"""
## 思考过程 ({self.timestamp})

**想法**: {self.thought}

**考虑过的方案**:
{self._format_alternatives()}

**最终选择**: {self.decision}
**原因**: {self.reason}

**相关代码**:
```{self.language}
{self.artifacts}
```
"""
```

---

### 📊 智能Git集成

```python
class GitManager:
    """AI增强的Git操作"""
    
    def __init__(self, repo_path: str):
        self.repo = git.Repo(repo_path)
        
    async def create_intelligent_commit(
        self, 
        task_graph: TaskGraph, 
        changes: List[Change]
    ) -> CommitResult:
        """根据任务结构创建有意义的提交"""
        
        # 1. 为每个逻辑单元创建提交
        for subtask in task_graph.get_logical_units():
            related_changes = self.group_changes_by_subtask(changes, subtask)
            
            # 2. 生成有意义的提交信息
            commit_message = await self.generate_commit_message(
                subtask, 
                related_changes
            )
            
            # 3. 创建提交，附带推导过程
            self.repo.index.add([c.file_path for c in related_changes])
            self.repo.index.commit(
                commit_message,
                message_encoding='utf-8'
            )
            
            # 4. 将推导过程存储在 commit body 中
            self.add_reasoning_to_commit(subtask.reasoning)
        
        # 5. 推送前验证
        if self.run_tests():
            self.repo.remote().push()
            return self.create_pr_description(task_graph)
    
    async def generate_commit_message(
        self, 
        task: SubTask, 
        changes: List[Change]
    ) -> str:
        """AI生成约定式提交信息"""
        prompt = f"""
        任务: {task.title}
        描述: {task.description}
        变更文件: {[c.file_path for c in changes]}
        变更类型: {[c.change_type for c in changes]}
        
        使用约定式提交格式：
        <type>(<scope>): <subject>
        
        示例：
        feat(user-detail): add order history tab
        fix(api): handle null user orders
        refactor(component): extract order table
        """
        return await self.llm.generate(prompt)
```

---

### 🔮 时间旅行调试

```python
class TimeTravelDebugger:
    """回到任意决策点，重新选择不同方案"""
    
    async def time_travel(self, commit_hash: str) -> TimeTravelState:
        """时间旅行：回到某个决策点"""
        
        # 1. 检出到指定提交
        self.repo.git.checkout(commit_hash)
        
        # 2. 从 commit body 中恢复推导过程
        commit = self.repo.commit(commit_hash)
        reasoning = ReasoningSession.from_commit_body(commit.message)
        
        # 3. 重新打开会话
        return TimeTravelState(
            code_state=self.get_code_at_commit(commit_hash),
            reasoning=reasoning,
            can_resume=True  # 可从此点继续开发
        )
    
    async def replay_reasoning(self, session: ReasoningSession):
        """回放推理过程"""
        for step in session.timeline:
            yield ReasoningSnapshot(
                step=step,
                code_state=step.code_state,
                decision=step.decision,
                alternatives=step.alternatives
            )
```

---

### 🚀 多模型协作架构

```python
class ReasoningOrchestrator:
    """三个专用模型协同工作"""
    
    def __init__(self):
        self.analyzer = CodeAnalyzerModel()   # 代码分析
        self.planner = TaskPlannerModel()     # 任务规划
        self.coder = CoderModel()             # 代码生成
        self.verifier = VerifierModel()       # 验证
        
    async def process_request(self, user_input: str):
        # 1. 分析阶段
        context = await self.analyzer.analyze_project()
        
        # 2. 规划阶段
        plan = await self.planner.create_plan(user_input, context)
        
        # 3. 执行阶段（流式输出）
        async for step in self.execute_plan(plan):
            # 记录推导过程
            await self.recorder.record_step(step)
            
            # 生成代码
            code = await self.coder.generate(step)
            
            # 验证
            is_valid = await self.verifier.verify(code)
            
            yield ExecutionStep(
                step=step,
                code=code,
                status="success" if is_valid else "needs_review"
            )
        
        # 4. 总结阶段
        return await self.create_summary()
```

---

### 💡 创新亮点

```python
┌─────────────────────────────────────────────────────────────────────────────┐
│                         推理式编程助手的创新点                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 🎯 透明的AI                                                               │
│     每个决策都可追溯，不再是"黑箱"                                              │
│                                                                             │
│  2. ⏸️  可中断的工作流                                                         │
│     在任何步骤都可以介入、修改方向                                              │
│                                                                             │
│  3. ⏪ 时间旅行调试                                                            │
│     回到任意决策点，重新选择不同方案                                            │
│                                                                             │
│  4. 📜 Git作为记忆                                                             │
│     推导过程存储在Git历史中，永久可追溯                                        │
│                                                                             │
│  5. 📈 渐进式采纳                                                             │
│     代码生成 → 任务分解 → 完整功能开发                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 📋 版本路线图

| 版本 | 功能 | 目标用户 |
|------|------|---------|
| **v1.0 MVP** | 基础任务分解 + 简单推导显示 + 手动Git提交 | 早期采用者 |
| **v1.5** | 多模型协作 + 推导时间旅行 + 智能提交分组 | 进阶用户 |
| **v2.0** | 从错误中学习 + 团队协作 + 性能预测 | 团队使用 |
| **v2.5+** | 跨项目迁移 + 架构建议 + 自动重构 | 企业用户 |

---

### 🎯 从何开始（第一周）

```python
# 第一周实现最小闭环
PHASE_1_TASKS = [
    "创建基础IDE插件框架",
    "实现简单的任务分解（硬编码规则）",
    "显示基础推导过程",
    "手动触发Git提交"
]

# 然后逐步增强
PHASE_2_ENHANCEMENTS = [
    "用LLM替换硬编码的任务分解",
    "添加推导过程可视化",
    "实现智能Git提交",
    "添加时间旅行功能"
]
```

**核心原则**：确保开发者始终在控制中，AI只是增强了能力，而不是接管了控制权。

---

## 📋 大型工程落地清单

| Phase | 任务 | 说明 |
|-------|------|------|
| **P0 生存** | Token 上限 | 设置 8K 硬性上限 |
| **P0 生存** | 文件类型过滤 | `.py` 不加载 `.js` |
| **P0 生存** | 意图模板库 | 高频意图缓存 |
| **P1 优化** | Symbol Index | O(1) 符号查找 |
| **P1 优化** | 脏区域锁定 | 仅锁定当前文件 |
| **P1 优化** | 响应缓存 | 意图结果缓存 |
| **P2 卓越** | 本地模型路由 | 简单意图用小模型 |
| **P2 卓越** | 影响范围分析 | 仅重跑受影响测试 |

---

## 🚨 必须避免的陷阱

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              陷阱与正确做法                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  陷阱 1: 试图兼容传统开发流程                                                │
│  ───────────────────────────────                                           │
│  ❌ 错误:  让用户既可以用 AI 生成，也可以手动编辑                              │
│  ✅ 正确: 强制纯 AI 驱动。手动编辑是"逃生舱"，不是常规操作                     │
│                                                                             │
│  陷阱 2: 提供太多选项                                                        │
│  ────────────────────                                                       │
│  ❌ 错误:  让用户选择"用哪个 AI 模型"、"生成风格"                            │
│  ✅ 正确:  自动选择最优方案。用户只关心结果，不关心实现细节                   │
│                                                                             │
│  陷阱 3: 暴露技术复杂性                                                     │
│  ───────────────────────                                                    │
│  ❌ 错误:  显示 Token 使用量、API 调用次数、向量检索过程                      │
│  ✅ 正确:  一切透明在背后。用户看到"思考中..."、"生成完成"                   │
│                                                                             │
│  陷阱 4: 试图一步到位做完整系统                                              │
│  ──────────────────────────────                                            │
│  ❌ 错误:  一次性实现所有功能，交付遥遥无期                                   │
│  ✅ 正确:  MVP 优先，每个功能做到极致再扩展                                   │
│                                                                             │
│  陷阱 5: 忽视用户教育                                                       │
│  ──────────────────                                                         │
│  ❌ 错误:  默认用户知道怎么用                                                │
│  ✅ 正确:  首次使用引导 + 渐进式功能揭示                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌈 最终愿景：编程的"自动驾驶"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         自动驾驶级别 vs IDE 能力                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🚗 汽车自动驾驶        →    💻 AI-IDE                                       │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  L1 辅助驾驶            →    代码补全、语法检查                              │
│     驾驶员操作           →    用户手写代码                                     │
│     系统提示             →    AI 提示补全                                     │
│                                                                             │
│  L2 部分自动化          →    生成简单函数、修复拼写错误                        │
│     自适应巡航           →    AI 生成简单代码                                  │
│     车道保持             →    AI 修复简单错误                                  │
│                                                                             │
│  L3 条件自动化    ⭐⭐⭐   →    明确场景下完全接管  ← 你在这里！              │
│     驾驶员监督           →    用户描述需求，AI 生成完整功能                    │
│     复杂路况退出         →    AI 遇到难题，请求人类帮助                       │
│                                                                             │
│  L4 高度自动化          →    处理复杂任务，人类偶尔干预                        │
│     大多数场景自动驾驶   →    AI 处理端到端功能开发                            │
│     极端情况接管         →    仅边界情况需要人工                               │
│                                                                             │
│  L5 完全自动化          →    描述需求，AI 完成从设计到部署的全过程            │
│     任何场景无需人      →    用户只负责验收和决策                              │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  🎯 我们正在构建 L3 级别的 IDE：                                              │
│     用户给出明确指令 → AI 完成从需求到代码的全过程 → 人类负责验收和决策       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ 立即行动指南

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            立即行动清单                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 彻底放弃"编辑器思维"                                                     │
│     ─────────────────────────                                               │
│     □ 删除"新建文件"菜单                                                    │
│     □ 删除"保存"按钮（自动保存）                                            │
│     □ 删除"查找替换"功能（AI 智能重构）                                      │
│     □ 删除"文件树"（改为功能模块视图）                                       │
│                                                                             │
│  2. 从"单功能原型"开始                                                      │
│     ──────────────────────                                                 │
│     □ 只做"创建 React/Vue 组件"这一个功能                                    │
│     □ 做到极致：用户描述，AI 生成完美组件                                    │
│     □ 验证核心假设：用户是否接受这种模式                                     │
│                                                                             │
│  3. 建立反馈循环                                                            │
│     ────────────                                                           │
│     □ 记录每个意图的成功/失败                                               │
│     □ 持续优化意图理解                                                      │
│     □ 让 AI 在失败时主动询问澄清                                            │
│                                                                             │
│  4. 第一周目标                                                              │
│     ──────────                                                             │
│     □ Day 1-2: IntentEngine 核心实现                                       │
│     □ Day 3-4: 简单模板系统和 VFS                                           │
│     □ Day 5:   Streamlit UI 原型                                            │
│     □ Day 6-7: 用户测试 + 迭代                                              │
│                                                                             │
│  5. 成功标准                                                                │
│     ────────                                                               │
│     □ 10 个测试意图中，7 个能直接生成可用代码                                │
│     □ 用户测试满意度 > 80%                                                  │
│     □ 无需手动编辑即可完成简单组件                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 💎 核心原则总结

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          范式革命的核心原则                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  你不是在造一个"更好的 VSCode"                                               │
│  你是在造编程的"iPhone 时刻"                                                  │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  📌 原则 1: 用户不应该关心文件、目录、命令行                                  │
│     → 只关心"我想要什么功能"                                                 │
│                                                                             │
│  📌 原则 2: 代码编辑器是"预览窗口"，不是"创作窗口"                            │
│     → 主要创作发生在意图工作台                                               │
│                                                                             │
│  📌 原则 3: 一切都是自然语言                                                  │
│     → 键盘敲击降级为"逃生舱"                                                │
│                                                                             │
│  📌 原则 4: AI 负责执行，人类负责决策                                          │
│     → 从"人想方案 → 人敲代码"变为"人表达意图 → AI 执行"                     │
│                                                                             │
│  📌 原则 5: 自动驾驶模式                                                      │
│     → 像特斯拉一样，用户只负责监督和干预                                     │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  🎯 终极目标:                                                                │
│     用户从未写过一行代码，但完成了整个功能开发                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*文档创建时间: 2026-04-24*  
*最后更新: 2026-04-24 (范式革命 + MVP + 交互模式 + 自动驾驶愿景 + 意图保持型压缩 + 推理式编程助手 + 端到端体验优化)*
