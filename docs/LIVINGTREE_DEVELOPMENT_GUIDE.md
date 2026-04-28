# LivingTreeAlAgent 功能开发指南

**文档版本**: v1.0  
**创建日期**: 2026-04-28  
**状态**: 📋 **规划中**

---

## 文档结构

1. [一、项目现状](#一项目现状)
2. [二、功能模块匹配度分析](#二功能模块匹配度分析)
3. [三、待开发功能清单](#三待开发功能清单)
4. [四、阶段开发计划](#四阶段开发计划)
5. [五、优先级矩阵](#五优先级矩阵)
6. [六、技术选型建议](#六技术选型建议)

---

## 一、项目现状

### 1.1 已完成的核心能力

| 类别 | 能力 | 匹配度 |
|------|------|--------|
| **LLM分层** | L0-L4分层推理、GlobalModelRouter统一调用 | 93% ✅ |
| **环评系统** | 35个模块完整（计算、审查、生成、绘图） | 96% ✅ |
| **文档引擎** | plugin_framework完整、多格式解析 | 92% ✅ |
| **自我进化** | 工具自修复、双数据飞轮、增量学习 | 85% ✅ |
| **技能系统** | 220+专家角色（agency+mattpocock） | 90% ✅ |

### 1.2 需要增强的领域

| 领域 | 当前状态 | 目标 | 差距 |
|------|----------|------|------|
| 专业地图引擎 | 需新增ProgressiveUIRenderer | 82% | +18% |
| 会话式渐进UI | 已有状态机，需增强 | 82% | +18% |
| 增量学习 | 部分实现，需集成 | 75% | +25% |
| 报告生成 | 工作流完整，AI增强不足 | 80% | +20% |

---

## 二、功能模块匹配度分析

### 2.1 环评专业地图引擎 (82%)

**现状分析**：
- ✅ pyproj、shapely、geopandas 已集成
- ✅ cartopy、contextily 地图底图
- ✅ drawing_engine.py 绘图引擎
- ❌ 缺乏 CGCS2000 专业地图渲染
- ❌ 缺乏坐标转换向导 UI

**待开发功能**：
1. **ProgressiveUIRenderer** - 分步式地图生成向导
2. **CGCS2000坐标转换器** - WGS84 ↔ CGCS2000 批量转换
3. **专业底图叠加** - 卫星图/地形图/行政区划图

### 2.2 会话式渐进UI (82%)

**现状分析**：
- ✅ EIAWorkbench 已有完整状态机
- ✅ 进度反馈 (agent_progress.py)
- ❌ 缺乏意图→澄清→UI 渐进流程
- ❌ 缺乏自然语言配置界面

**待开发功能**：
1. **IntentionClarifier** - 用户意图澄清对话
2. **ProgressiveFormBuilder** - 动态表单生成
3. **ContextAwareRenderer** - 上下文感知UI渲染

### 2.3 内置LLM方案 (93%)

**现状分析**：
- ✅ nanoGPT 源码完整 (llmcore/_nanogpt_src/)
- ✅ L0-L4 分层推理
- ✅ GlobalModelRouter 统一调用
- ❌ 增量学习未与 nanoGPT 集成
- ❌ 缺乏模型微调 Pipeline

**待开发功能**：
1. **IncrementalFineTuner** - 增量微调管道
2. **KnowledgeDistiller** - 知识蒸馏模块
3. **ModelVersionManager** - 模型版本管理

### 2.4 文档引擎 (92%)

**现状分析**：
- ✅ plugin_framework 完整
- ✅ document_parser 多格式支持
- ✅ intelligent_ocr PDF处理
- ❌ 缺乏 Markdown 输出
- ❌ 缺乏模板系统

**待开发功能**：
1. **MarkdownExporter** - Markdown 格式导出
2. **TemplateEngine** - 文档模板引擎
3. **StylePreserver** - 样式保持转换

### 2.5 环评报告生成系统 (96%)

**现状分析**：
- ✅ workbench.py 完整工作流
- ✅ compliance_checker 五合一审查
- ✅ collaborative_generator 人机协同
- ✅ export_manager 多格式导出
- ❌ 缺乏 AI 增强的章节生成
- ❌ 缺乏智能模板推荐

**待开发功能**：
1. **AISectionGenerator** - AI 增强章节生成
2. **SmartTemplateRecommender** - 智能模板推荐
3. **AutoComplianceChecker** - 自动合规检查

---

## 三、待开发功能清单

### 3.1 P0 - 紧急 (需2周内完成)

| 功能ID | 功能名称 | 所属模块 | 依赖 | 工时 |
|--------|----------|----------|------|------|
| F001 | ProgressiveUIRenderer | 专业地图 | drawing_engine | 3天 |
| F002 | CGCS2000Converter | 坐标转换 | pyproj | 2天 |
| F003 | IntentionClarifier | 渐进UI | hermes_agent | 2天 |
| F004 | MarkdownExporter | 文档引擎 | markdown库 | 1天 |

### 3.2 P1 - 重要 (需1个月内完成)

| 功能ID | 功能名称 | 所属模块 | 依赖 | 工时 |
|--------|----------|----------|------|------|
| F005 | IncrementalFineTuner | LLM | nanoGPT, intelligent_learning | 5天 |
| F006 | AISectionGenerator | 报告生成 | GlobalModelRouter | 3天 |
| F007 | ProgressiveFormBuilder | 渐进UI | IntentionClarifier | 2天 |
| F008 | TemplateEngine | 文档引擎 | MarkdownExporter | 2天 |

### 3.3 P2 - 优化 (1-2个月)

| 功能ID | 功能名称 | 所属模块 | 依赖 | 工时 |
|--------|----------|----------|------|------|
| F009 | KnowledgeDistiller | LLM | IncrementalFineTuner | 5天 |
| F010 | SmartTemplateRecommender | 报告生成 | AI增强 | 3天 |
| F011 | ContextAwareRenderer | 渐进UI | ProgressiveFormBuilder | 3天 |
| F012 | ModelVersionManager | LLM | IncrementalFineTuner | 2天 |

---

## 四、阶段开发计划

### 阶段1：地图引擎增强 (第1-2周)

```
目标: 环评专业地图生成能力达到 95%
任务:
  1. 实现 ProgressiveUIRenderer
     - 步骤1: 设计UI状态机
     - 步骤2: 实现坐标选择组件
     - 步骤3: 集成底图服务
  2. 实现 CGCS2000Converter
     - 步骤1: 配置 pyproj 转换参数
     - 步骤2: 批量转换工具
     - 步骤3: 可视化预览
  3. 集成测试
     - 端到端地图生成测试
     - 性能基准测试
```

### 阶段2：渐进UI增强 (第3-4周)

```
目标: 会话式渐进UI达到 90%
任务:
  1. 实现 IntentionClarifier
     - 步骤1: 定义澄清对话模板
     - 步骤2: 实现多轮对话管理
     - 步骤3: 意图置信度计算
  2. 实现 ProgressiveFormBuilder
     - 步骤1: 动态表单DSL
     - 步骤2: 表单验证规则
     - 步骤3: 表单填充辅助
  3. 集成到 EIAWorkbench
     - 替换现有静态表单
     - 添加语音输入支持
```

### 阶段3：LLM增强 (第5-7周)

```
目标: 内置LLM方案达到 98%
任务:
  1. 实现 IncrementalFineTuner
     - 步骤1: 数据集格式化工具
     - 步骤2: LoRA 微调管道
     - 步骤3: 增量训练调度器
  2. 实现 KnowledgeDistiller
     - 步骤1: 教师-学生模型架构
     - 步骤2: 蒸馏损失函数
     - 步骤3: 知识迁移验证
  3. 与 GlobalModelRouter 集成
     - 本地模型注册
     - 动态模型切换
```

### 阶段4：报告生成AI增强 (第8-10周)

```
目标: 环评报告生成达到 99%
任务:
  1. 实现 AISectionGenerator
     - 步骤1: 章节模板库
     - 步骤2: LLM 生成管道
     - 步骤3: 人工审核界面
  2. 实现 SmartTemplateRecommender
     - 步骤1: 项目类型分类器
     - 步骤2: 历史模板匹配
     - 步骤3: 推荐理由生成
  3. 端到端集成测试
```

---

## 五、优先级矩阵

```
                 高价值
                    │
     ┌──────────────┼──────────────┐
     │  F005        │  F001 F006   │
     │  Incremental │  地图   AI章节│
低紧急───────────────┼───────────────高紧急
     │  F008        │  F002 F003   │
     │  模板引擎    │  CGCS  意图  │
     └──────────────┼──────────────┘
                    │
                 低价值
```

**优先开发区域**: 右上象限 (高价值+高紧急)
- F001: ProgressiveUIRenderer
- F002: CGCS2000Converter
- F003: IntentionClarifier
- F006: AISectionGenerator

---

## 六、技术选型建议

### 6.1 地图与坐标

| 组件 | 推荐方案 | 备选 |
|------|----------|------|
| 坐标转换 | pyproj | direct_geod.py |
| 地图渲染 | cartopy + contextily | folium (Web) |
| 地理数据 | geopandas + shapely | fiona |
| 底图服务 | 高德/天地图 WMTS | OSM |

### 6.2 UI框架

| 组件 | 推荐方案 | 说明 |
|------|----------|------|
| 渐进表单 | 自定义DSL | 灵活控制 |
| 对话管理 | 对话状态机 | 已有基础 |
| 表单验证 | pydantic | 类型安全 |

### 6.3 LLM微调

| 组件 | 推荐方案 | 说明 |
|------|----------|------|
| 微调框架 | LoRA (peft) | 低资源 |
| 训练框架 | PyTorch | 已有基础 |
| 蒸馏方法 | 知识蒸馏 | 需实现 |

---

## 附录：开发检查清单

### 新功能开发

- [ ] 需求澄清完成
- [ ] 技术方案评审通过
- [ ] 接口设计文档
- [ ] 单元测试覆盖 > 80%
- [ ] 集成测试通过
- [ ] 文档更新完成

### 代码规范

- [ ] 遵循 AGENTS.md 架构
- [ ] 放在 `client/src/business/` 或 `client/src/presentation/`
- [ ] 通过 GlobalModelRouter 调用 LLM
- [ ] 使用 BaseTool 基类
- [ ] 注册到 ToolRegistry

---

**下一步行动**: 选择阶段1中的 F001 作为首个开发任务
