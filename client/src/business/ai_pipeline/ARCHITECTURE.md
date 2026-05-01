# AI-Centric 自动化研发流水线架构

## 项目概述

本项目实现了一个基于AI的自动化研发流水线系统，支持从自然语言需求到代码发布的完整软件开发生命周期。

## 架构层次

### 三层架构模型

```
┌─────────────────────────────────────────────┐
│           交互层 (Conversation Layer)        │
│  • 自然语言对话接口                        │
│  • 意图识别与任务分解                      │
│  • 进度可视化与审批点                      │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│           协调层 (Orchestration Layer)       │
│  • 工作流引擎 (AI Workflow Engine)          │
│  • 上下文管理器 (Context Manager)           │
│  • 质量门禁 (Quality Gates)                  │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│           执行层 (Execution Layer)           │
│  ├─ 开发单元 (Development Unit)             │
│  ├─ 测试单元 (Testing Unit)                 │
│  ├─ 运维单元 (Operations Unit)              │
│  └─ 知识单元 (Knowledge Unit)               │
└─────────────────────────────────────────────┘
```

## 核心组件

### 1. AI工作流引擎 (ai_workflow_engine.py)

**核心功能：**
- 从自然语言需求自动生成工作流
- 支持动态决策和持续学习
- 工作流状态管理和执行
- 支持多种工作流模式

**关键类：**
- `AIWorkflowEngine` - 主引擎类
- `WorkflowDefinition` - 工作流定义
- `ExecutionContext` - 执行上下文
- `WorkflowNode` - 工作流节点

### 2. 任务分解引擎 (task_decomposition_engine.py)

**核心功能：**
- 意图识别：区分任务类型（新功能/修复/优化）
- 复杂度评估：估算工作量、依赖项、风险
- 任务拆解：自动生成 EPIC → User Story → Task
- 技术选型：基于代码库现状推荐技术栈

**关键类：**
- `TaskDecompositionEngine` - 主引擎类
- `Epic` - 史诗级需求
- `UserStory` - 用户故事
- `Task` - 任务定义

### 3. 智能代码生成单元 (code_generation_unit.py)

**核心功能：**
- 上下文感知生成：读取现有代码风格和架构模式
- 渐进式生成：接口定义 → 核心逻辑 → 异常处理和日志
- 安全校验：自动检测敏感信息、安全漏洞
- 代码风格学习：从代码库中学习团队编码规范

**关键类：**
- `CodeGenerationUnit` - 主单元类
- `CodeContext` - 代码上下文
- `GenerationResult` - 生成结果
- `CodeFile` - 代码文件

### 4. 自主测试系统 (auto_test_system.py)

**测试流水线：**
1. 单元测试生成 → 基于代码逻辑自动生成测试用例
2. 覆盖率驱动 → 识别未覆盖分支，补充测试
3. 集成测试规划 → 分析模块依赖，生成集成场景
4. E2E 测试脚本 → 模拟用户操作流
5. 性能测试注入 → 自动添加负载测试

**关键类：**
- `AutoTestSystem` - 主系统类
- `TestCase` - 测试用例
- `TestResult` - 测试结果
- `TestSuite` - 测试套件

### 5. 智能修复引擎 (smart_fix_engine.py)

**核心功能：**
- 问题诊断：测试失败时自动分析根本原因
- 修复策略：快速修复 > 重构 > 架构调整
- 安全边界：确保修复不引入新问题
- 回滚机制：修复失败自动回退

**关键类：**
- `SmartFixEngine` - 主引擎类
- `Issue` - 问题描述
- `Fix` - 修复方案
- `FixResult` - 修复结果

### 6. 质量门禁系统 (quality_gates.py)

**四级质量门禁体系：**

| 门禁级别 | 检查内容 |
|---------|---------|
| 门禁1：代码质量 | 静态分析、安全扫描、架构规范检查 |
| 门禁2：功能正确性 | 单元测试覆盖率 > 80%、集成测试通过、关键路径验证 |
| 门禁3：非功能需求 | 性能基准测试、兼容性测试、可访问性测试 |
| 门禁4：发布就绪 | 文档完整性、监控就绪、回滚预案 |

**关键类：**
- `QualityGates` - 主系统类
- `GateCheck` - 门禁检查项
- `GateResult` - 门禁检查结果
- `QualityReport` - 质量报告

### 7. 知识管理体系 (knowledge_management.py)

**知识库组成：**
- 架构决策记录：记录每个技术决策的原因
- 代码模式库：积累团队的最佳实践模式
- 故障知识库：记录问题和解决方案
- 业务规则库：领域逻辑和业务规则

**关键类：**
- `KnowledgeManagement` - 主管理类
- `ArchitectureDecision` - 架构决策记录
- `CodePattern` - 代码模式
- `BugRecord` - 故障记录
- `BusinessRule` - 业务规则

### 8. 上下文管理器 (context_manager.py)

**核心功能：**
- 任务上下文管理
- 代码库上下文感知
- 用户会话管理
- 任务状态追踪

**关键类：**
- `ContextManager` - 主管理器类
- `TaskContext` - 任务上下文
- `CodebaseContext` - 代码库上下文
- `UserSession` - 用户会话

### 9. IDE流水线面板 (ide_pipeline_panel.py)

**核心功能：**
- 任务进度可视化
- 工作流状态监控
- 审批点管理
- 交互式任务管理
- 实时更新通知

**关键类：**
- `PipelinePanel` - 主面板类
- `PipelineStage` - 流水线阶段
- `PipelineTask` - 流水线任务
- `ApprovalPoint` - 审批点

### 10. 集成编排器 (integration_orchestrator.py)

**核心功能：**
- 统一调度所有模块
- 协调模块间的数据流转
- 实现完整的研发工作流
- 支持多种自动化模式

**自动化模式：**
1. **全自动模式**：AI 完成从需求到发布的全流程
2. **监督模式**：每个关键节点需人工确认
3. **协同模式**：AI 生成，人类修改，AI 优化
4. **学习模式**：记录人类决策，优化 AI 策略

**关键类：**
- `IntegrationOrchestrator` - 主编排器类
- `PipelineRun` - 流水线运行实例

## 模块交互流程

```
用户输入 → 任务分解引擎 → 工作流引擎
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
        代码生成单元                    测试系统
              ↓                               ↓
              └───────────────┬───────────────┘
                              ↓
                       质量门禁系统
                              ↓
                      智能修复引擎 (如需要)
                              ↓
                        知识管理体系
```

## 安装与使用

### 导入方式

```python
from client.src.business.ai_pipeline import (
    get_ai_workflow_engine,
    get_task_decomposition_engine,
    get_code_generation_unit,
    get_auto_test_system,
    get_smart_fix_engine,
    get_quality_gates,
    get_knowledge_management,
    get_context_manager,
    get_pipeline_panel,
    get_integration_orchestrator,
    AutomationMode
)

# 使用集成编排器启动完整流水线
orchestrator = get_integration_orchestrator()
run_id = await orchestrator.start_pipeline(
    requirement="开发用户登录功能",
    automation_mode=AutomationMode.FULL_AUTO
)
```

### 测试

```bash
cd client/src/business/ai_pipeline
python test_pipeline.py
```

## 设计原则

1. **渐进增强**：保留现有模块的核心能力，在其基础上扩展AI-Centric特性
2. **层次分离**：交互层、协调层、执行层清晰分离
3. **学习机制**：所有模块都具备从执行中学习的能力
4. **容错设计**：所有LLM调用都有兜底方案

## 未来规划

1. **短期目标**：实现60%常规功能的自动化开发
2. **中期目标**：形成领域特定语言（DSL）用于需求描述
3. **长期愿景**：自演进系统，能够自我优化架构