#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
追加第三十七章到统一架构层改造方案文档
"""

import os

chapter37_content = """

---

# 第三十七章 简洁版环评图表自动生成方案 —— 与LivingTree项目匹配度分析

## 37.1 方案概述

### 37.1.1 背景与设计理念

用户提出的**简洁实用版图表自动生成方案**，核心设计理念：
1. **全自动**：用户提供数据/描述 → AI自动生成图表
2. **专业风格**：符合环评报告规范，不花哨
3. **简洁实用**：不追求复杂编辑，生成即用
4. **可微调**：简单调整，不是复杂编辑

### 37.1.2 核心原则：专业自动生成

**设计理念**：
- 不追求炫技，追求实用性
- 不追求复杂编辑，追求自动生成
- 不追求花哨效果，追求专业规范
- 不追求功能堆砌，追求解决问题

**用户工作流程**：
- 用户提供：场地数据（CAD/坐标/描述）、工艺描述、监测数据
- 系统自动：解析数据、生成专业图表、插入报告、格式化
- 输出：完整报告（含图表）、图表文件包、图表目录

### 37.1.3 六大核心组件

| 组件 | 功能 | 核心价值 |
|------|------|---------|
| **AutoLayoutGenerator** | 自动平面布局图生成 | 生成专业总平面布置图 |
| **AutoProcessFlowGenerator** | 自动工艺流程图生成 | 从描述自动生成标准流程图 |
| **DocumentStyleGenerator** | 文档风格生成器 | 保持图表与文档风格一致 |
| **SimpleAutoGenerator** | 简化自动生成器 | 一键生成所有图表 |
| **SimpleAdjuster** | 简单调整功能 | 基本调整，非复杂编辑 |
| **AutoFigureGenerationPipeline** | 自动图表生成流水线 | 集成到报告生成流程 |

---

## 37.2 组件级匹配度分析

### 37.2.1 AutoLayoutGenerator（自动平面布局图生成器）

#### 核心功能

- 从场地数据自动生成总平面布置图
- 支持standard/simplified/detailed三种模板
- 专业颜色方案和标注样式

#### 类设计

核心类：AutoLayoutGenerator

主要方法：
- generate_site_plan(site_data, drawing_type="standard")：自动生成总平面布置图
- parse_site_data(site_data)：解析场地数据
- load_standard_template()：加载标准模板
- create_professional_drawing(elements)：创建专业绘图
- add_necessary_annotations(drawing, site_info)：添加必要标注
- check_compliance(drawing)：检查规范符合性

#### 专业颜色方案

| 元素类型 | 颜色代码 | 说明 |
|---------|---------|------|
| **建筑** | #4A6FA5 | 深蓝色 |
| **道路** | #666666 | 灰色 |
| **绿地** | #7CB342 | 绿色 |
| **水体** | #4FC3F7 | 浅蓝色 |
| **设施** | #FF9800 | 橙色 |

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 平面布局图需求 | 匹配度 | 备注 |
|-------------------|---------------|--------|------|
| **GlobalModelRouter** | 场地数据解析 | 5/5 | 可调用LLM解析场地描述 |
| **Python生态** (matplotlib) | 绘图渲染 | 5/5 | matplotlib完全满足需求 |
| **KnowledgeGraph** | 场地数据存储 | 4/5 | 可存储场地坐标、元素关系 |
| **EIA工具包** | 地理坐标处理 | 3/5 | 已有坐标处理基础 |
| **Template系统** | 布局模板管理 | 4/5 | 可复用模板系统 |

**匹配度评分**：**4.4/5** （4星）

#### 需要增强的功能

1. **AutoArranger自动布局算法**（难度：中等）
   - 基于约束的布局算法
   - 可参考CAD自动布局算法
   - 预计时间：2-3周

2. **环评布局规范库**（难度：低）
   - 建筑/道路/绿地/水体/设施的标准颜色和符号
   - 基于国家标准
   - 预计时间：1周

3. **LayoutRules规范检查**（难度：低）
   - 间距规范、安全距离等
   - 可基于规则引擎
   - 预计时间：1周

#### 集成方案

- Phase 1（1-2周）：matplotlib绘图基础 + 标准颜色方案
- Phase 2（2-3周）：AutoArranger布局算法
- Phase 3（3-4周）：LayoutRules规范检查 + 三种模板

#### 实施价值

5星（极高 - 解决环评报告最耗时的图表之一）

---

### 37.2.2 AutoProcessFlowGenerator（自动工艺流程图生成器）

#### 核心功能

- 从工艺描述自动生成标准工艺流程图
- 支持eia_standard/simplified/detailed三种风格
- Graphviz专业绘图

#### 类设计

核心类：AutoProcessFlowGenerator

主要方法：
- generate_process_flow(process_description, style="eia_standard")：从描述自动生成工艺流程图
- parse_process_description(description)：解析工艺描述
- standardize_process(parsed)：标准化流程结构
- create_professional_flowchart(layout, style)：创建专业流程图

#### 标准节点样式

| 节点类型 | 形状 | 颜色 | 说明 |
|---------|------|------|------|
| **物料** | 椭圆 | #D3E3FD（浅蓝） | 原材料、产品 |
| **工序** | 圆角矩形 | #FFE5CC（浅橙） | 加工、处理 |
| **设备** | 矩形 | #E6F7D3（浅绿） | 设备、机械 |
| **污染物** | 菱形 | #FFCCCC（浅红） | 废气、废水、固废 |
| **控制** | 矩形 | #E6D3FF（浅紫） | 控制措施 |

#### Graphviz专业配置

- rankdir: 'LR'（从左到右）
- splines: 'ortho'（直角连线）
- fontname: 'SimSun'（宋体）
- fontsize: 12pt

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 工艺流程图需求 | 匹配度 | 备注 |
|-------------------|---------------|--------|------|
| **GlobalModelRouter** | 工艺描述解析 | 5/5 | 可调用LLM解析工艺流程 |
| **Python生态** (graphviz) | 流程图绘制 | 5/5 | graphviz完全满足需求 |
| **KnowledgeGraph** | 工艺数据存储 | 4/5 | 可存储设备、污染物关系 |
| **Template系统** | 流程图模板 | 4/5 | 可创建标准模板 |

**匹配度评分**：**4.5/5** （4.5星）

#### 需要增强的功能

1. **ProcessFlowRules规范库**（难度：低）
   - 标准节点样式（物料/工序/设备/污染物/控制）
   - 标准连线样式
   - 预计时间：1周

2. **FlowAutoLayout布局算法**（难度：中等）
   - 层次布局（从左到右/从上到下）
   - 节点自动排序
   - 预计时间：2-3周

3. **parse_process_description解析器**（难度：中等）
   - LLM辅助解析工艺描述
   - 识别设备、物料、污染物
   - 预计时间：2-3周

#### 集成方案

- Phase 1（1-2周）：Graphviz基础 + 标准节点样式
- Phase 2（2-3周）：FlowAutoLayout布局算法
- Phase 3（3-4周）：parse_process_description解析器 + 三种风格

#### 实施价值

5星（极高 - 自动生成专业流程图，大幅提升效率）

---

### 37.2.3 DocumentStyleGenerator（文档风格生成器）

#### 核心功能

- 从参考文档提取样式规则
- 保持图表与文档风格一致
- 应用字体、颜色、线条等样式

#### 类设计

核心类：DocumentStyleGenerator

主要方法：
- extract_style_rules(doc)：从参考文档提取样式规则
- apply_document_style(figure, element_type)：将文档样式应用到图表
- apply_site_plan_style(figure, rules)：应用总平面图样式
- apply_process_flow_style(dot_graph, rules)：应用工艺流程图样式
- apply_chart_style(figure, rules)：应用统计图表样式

#### 默认环评样式规则

| 样式元素 | 规则 |
|---------|------|
| **正文字体** | 宋体，12pt |
| **标题字体** | 黑体，16pt，加粗 |
| **表格字体** | 仿宋，10.5pt |
| **主色调** | #2C3E50（深蓝灰） |
| **辅助色** | #7F8C8D（中灰） |
| **强调色** | #3498DB（蓝色） |
| **线条宽度** | 1.0pt |
| **网格透明度** | 0.3 |

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 文档风格需求 | 匹配度 | 备注 |
|-------------------|-------------|--------|------|
| **Template系统** | 样式模板管理 | 5/5 | 完全契合 |
| **ReportGenerator** | 报告生成 | 5/5 | 可集成样式系统 |
| **GlobalModelRouter** | 样式规则提取 | 4/5 | 可调用LLM分析文档样式 |
| **KnowledgeGraph** | 样式数据存储 | 4/5 | 可存储样式规则 |

**匹配度评分**：**4.5/5** （4.5星）

#### 需要增强的功能

1. **extract_style_rules提取器**（难度：低）
   - 字体、颜色、线条宽度提取
   - 基于python-docx
   - 预计时间：1周

2. **apply_document_style应用器**（难度：低）
   - matplotlib样式应用
   - Graphviz样式应用
   - 预计时间：1周

3. **默认环评样式库**（难度：低）
   - 预设专业样式规则
   - 宋体/黑体/仿宋
   - 预计时间：1周

#### 集成方案

- Phase 1（1周）：默认环评样式库
- Phase 2（1-2周）：extract_style_rules提取器
- Phase 3（2-3周）：apply_document_style应用器

#### 实施价值

5星（极高 - 确保图表与文档风格完全一致）

---

### 37.2.4 SimpleAutoGenerator（简化自动生成器）

#### 核心功能

- 自动生成所有需要的图表（总平面图/工艺流程图/影响范围图/监测点位图）
- 完全自动化，无需用户干预
- 集成到报告生成流程

#### 类设计

核心类：SimpleAutoGenerator

主要方法：
- auto_generate_all_figures(project_data)：自动生成所有图表
- generate_impact_map(impact_data)：生成影响范围图
- generate_monitoring_map(monitoring_data)：生成监测点位图

#### 生成图表类型

| 图表类型 | 数据来源 | 核心功能 |
|---------|---------|---------|
| **总平面布置图** | site_data | 场地布局、建筑物位置、设施标注 |
| **工艺流程图** | process_description | 工艺描述解析、流程自动生成 |
| **影响范围图** | impact_data | 等值线图、敏感点标注 |
| **监测点位图** | monitoring_data | 点位分布、数据标注 |

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 简化自动生成需求 | 匹配度 | 备注 |
|-------------------|-----------------|--------|------|
| **AutoLayoutGenerator** | 总平面图生成 | 5/5 | 已在上面定义 |
| **AutoProcessFlowGenerator** | 工艺流程图生成 | 5/5 | 已在上面定义 |
| **ToolChainOrchestrator** | 多图表并行生成 | 5/5 | 可编排多图表生成 |
| **GlobalModelRouter** | 数据解析协调 | 5/5 | 完全契合 |
| **EIA工具包** | 影响范围图数据 | 4/5 | 可提供模拟数据 |

**匹配度评分**：**4.5/5** （4.5星）

#### 需要增强的功能

1. **generate_impact_map影响范围图**（难度：中等）
   - 等值线图绘制
   - 敏感点标注
   - 基于matplotlib/tricontourf
   - 预计时间：2-3周

2. **generate_monitoring_map监测点位图**（难度：低）
   - 点位标注
   - 地图底图
   - 预计时间：1-2周

3. **auto_generate_all_figures总控**（难度：低）
   - 工作流编排
   - 错误处理
   - 预计时间：1周

#### 集成方案

- Phase 1（1周）：auto_generate_all_figures总控
- Phase 2（1-2周）：generate_monitoring_map监测点位图
- Phase 3（2-3周）：generate_impact_map影响范围图

#### 实施价值

5星（极高 - 一键生成所有图表，完全自动化）

---

### 37.2.5 SimpleAdjuster（简单调整功能）

#### 核心功能

- 简单图表调整（大小/方向/样式/标注）
- 不是完整编辑器，只是基本调整
- 保持简单实用

#### 类设计

核心类：SimpleAdjuster

主要方法：
- simple_adjust(figure, adjustments)：简单调整图表
- adjust_size(figure, size)：调整大小
- adjust_orientation(figure, orientation)：调整方向
- adjust_style(figure, style)：调整样式
- adjust_annotations(figure, show_hide)：调整标注显示

#### 调整选项

| 调整类型 | 选项 | 说明 |
|---------|------|------|
| **size** | small/medium/large | 图表尺寸预设 |
| **orientation** | portrait/landscape | 图表方向 |
| **style** | standard/simplified/detailed | 图表详细程度 |
| **annotations** | show/hide | 标注显示/隐藏 |

#### 尺寸预设

| 尺寸 | 英寸 |
|------|------|
| **small** | 8x6 |
| **medium** | 10x8 |
| **large** | 12x9 |

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 简单调整需求 | 匹配度 | 备注 |
|-------------------|-------------|--------|------|
| **Python生态** (PIL/Pillow) | 图像大小调整 | 5/5 | 完全满足 |
| **matplotlib** | 图表样式调整 | 5/5 | 完全满足 |
| **Template系统** | 预设样式切换 | 5/5 | 完全契合 |

**匹配度评分**：**4.5/5** （4.5星）

#### 需要增强的功能

1. **adjust_size大小调整**（难度：低）
   - 预设尺寸（small/medium/large）
   - 基于matplotlib
   - 预计时间：1周

2. **adjust_orientation方向调整**（难度：低）
   - portrait/landscape切换
   - 基于matplotlib
   - 预计时间：1周

3. **adjust_annotations标注调整**（难度：低）
   - show/hide切换
   - 基于matplotlib
   - 预计时间：1周

#### 集成方案

- Phase 1（1周）：adjust_size大小调整
- Phase 2（1周）：adjust_orientation方向调整
- Phase 3（1-2周）：adjust_annotations标注调整

#### 实施价值

4星（高 - 提供基本调整能力，无需复杂编辑）

---

### 37.2.6 AutoFigureGenerationPipeline（自动图表生成流水线）

#### 核心功能

- 集成到报告生成流程
- 自动将图表插入文档
- 自动生成图表目录

#### 类设计

核心类：AutoFigureGenerationPipeline

主要方法：
- generate_report_with_figures(project_data)：生成包含自动图表的报告
- insert_figures_into_document(document, figures)：将图表插入文档
- insert_figure(doc, figure, name)：插入单个图表
- generate_figure_list(figures)：生成图表目录
- format(document_with_figures)：最终格式化

#### 流水线工作流程

1. 生成文本内容（text_generator）
2. 自动生成图表（figure_generator）
3. 插入图表到文档（insert_figures_into_document）
4. 生成图表目录（generate_figure_list）
5. 最终格式化（formatter）

#### 图表插入功能

- 自动编号（图1、图2...）
- 自动生成图标题
- 智能判断插入位置
- 图表位置优化

#### 图表目录格式

| 图号 | 图表名称 | 类型 | 页码 |
|------|---------|------|------|
| 图1 | 总平面布置图 | site_plan | TBD |
| 图2 | 工艺流程图 | process_flow | TBD |
| 图3 | 影响范围图 | impact_map | TBD |
| 图4 | 监测点位图 | monitoring_map | TBD |

#### 与LivingTree匹配度分析

| LivingTree现有能力 | 流水线需求 | 匹配度 | 备注 |
|-------------------|-----------|--------|------|
| **ReportGenerator** | 报告生成 | 5/5 | 完全契合 |
| **ToolChainOrchestrator** | 流程编排 | 5/5 | 完全契合 |
| **SimpleAutoGenerator** | 图表生成 | 5/5 | 已在上面定义 |
| **Template系统** | 文档模板 | 5/5 | 完全契合 |
| **python-docx** | Word文档操作 | 5/5 | 完全满足 |

**匹配度评分**：**4.8/5** （4.8星，最高评级）

#### 需要增强的功能

1. **insert_figures_into_document插入器**（难度：低）
   - 图表自动编号
   - 图标题生成
   - 插入位置判断
   - 预计时间：1-2周

2. **generate_figure_list目录生成**（难度：低）
   - 图表清单自动生成
   - 格式：图号-图表名称-页码
   - 预计时间：1周

3. **formatter最终格式化**（难度：低）
   - 图表位置优化
   - 页面布局
   - 预计时间：1周

#### 集成方案

- Phase 1（1-2周）：insert_figures_into_document插入器
- Phase 2（1周）：generate_figure_list目录生成
- Phase 3（1周）：formatter最终格式化

#### 实施价值

5星（极高 - 无缝集成到报告生成流程）

---

## 37.3 综合匹配度汇总

### 37.3.1 六大组件匹配度评分

| 组件 | 匹配度评分 | 评级 | 集成难度 | 核心价值 |
|------|----------|------|---------|---------|
| **AutoLayoutGenerator** | 4.4/5 | 4星 | 中等 | 极高 |
| **AutoProcessFlowGenerator** | 4.5/5 | 4.5星 | 中等 | 极高 |
| **DocumentStyleGenerator** | 4.5/5 | 4.5星 | 低 | 极高 |
| **SimpleAutoGenerator** | 4.5/5 | 4.5星 | 中等 | 极高 |
| **SimpleAdjuster** | 4.5/5 | 4.5星 | 低 | 高 |
| **AutoFigureGenerationPipeline** | **4.8/5** | 4.8星 | 低 | 极高 |

**平均匹配度评分**：**4.5/5** （4.5星，极高）

### 37.3.2 与LivingTree现有模块的融合分析

| 现有模块 | 融合方式 | 融合深度 |
|---------|---------|---------|
| **GlobalModelRouter** | LLM辅助数据解析、工艺描述解析 | 5星 |
| **KnowledgeGraph** | 场地数据、工艺数据、样式规则存储 | 4星 |
| **ReportGenerator** | 图表插入、报告生成集成 | 5星 |
| **Template系统** | 布局模板、流程图模板、文档样式 | 5星 |
| **ToolChainOrchestrator** | 多图表并行生成流程编排 | 5星 |
| **EIA工具包** | 影响范围图数据、地理坐标处理 | 3星 |
| **fusion_rag** | 图表相关知识检索 | 3星 |

---

## 37.4 与上一版本（36章）的对比分析

### 37.4.1 方案对比

| 对比维度 | 36章方案（颠覆性创新） | 37章方案（简洁实用） |
|---------|---------------------|---------------------|
| **设计理念** | 颠覆性、创新性强 | 实用性、稳扎稳打 |
| **功能复杂度** | 高（交互式沙盒、GAN等） | 低（自动生成+简单调整） |
| **平均匹配度** | 3.9/5 | **4.5/5** |
| **实施周期** | 12+个月 | **4-6周** |
| **技术风险** | 高 | **低** |
| **用户价值** | 颠覆行业 | **快速落地** |
| **与LivingTree契合度** | 中等 | **极高** |

### 37.4.2 功能互补建议

| 36章方案（颠覆性） | 37章方案（实用性） | 互补关系 |
|------------------|------------------|---------|
| 多模型投票生成 | 已包含（LLM解析） | 互补 |
| 实时数据驱动 | 已包含（流式生成） | 替代 |
| 智能图表故事线 | 已包含（专业图表） | 替代 |
| 交互式报告沙盒 | 不需要（简单实用） | 不互补 |
| 报告生成对抗网络 | 不需要（专业规范） | 不互补 |

**结论**：37章方案更务实，与LivingTree项目高度契合，可快速落地实施。

---

## 37.5 实施路径与时间规划

### 37.5.1 推荐实施路径：敏捷迭代（4-6周）

**Week 1-2：基础建设**
- DocumentStyleGenerator（默认样式库 + 提取器）
- SimpleAdjuster（大小/方向调整）
- 基础Template系统

**Week 3-4：核心功能**
- AutoProcessFlowGenerator（工艺流程图生成）
- AutoLayoutGenerator（总平面图生成基础）
- 环评规范库（颜色/符号/标注标准）

**Week 5-6：集成上线**
- SimpleAutoGenerator（多图表并行生成）
- AutoFigureGenerationPipeline（插入文档+目录生成）
- 与ReportGenerator集成

### 37.5.2 预期成果

| 指标 | 预期效果 |
|------|---------|
| **开发周期** | 4-6周完成核心功能 |
| **图表类型** | 5种专业图表一键生成 |
| **自动化程度** | 100%自动，无需手动编辑 |
| **规范符合度** | 100%符合环评报告专业规范 |
| **时间节省** | 图表生成时间缩短90%+ |

---

## 37.6 核心优势总结

### 37.6.1 四大核心优势

#### 1. 完全自动
- 用户只提供数据/描述
- 自动生成专业图表
- 自动编号和标注

#### 2. 专业风格
- 符合环评报告规范
- 不使用花哨效果
- 保持文档风格一致

#### 3. 简单实用
- 不需要复杂编辑功能
- 生成即用
- 可做简单调整

#### 4. 集成无缝
- 自动插入报告
- 自动生成目录
- 保持格式统一

### 37.6.2 与LivingTree集成的独特优势

| 优势 | 说明 |
|-----|------|
| **LLM辅助解析** | GlobalModelRouter驱动，智能解析场地数据、工艺描述 |
| **知识图谱支撑** | KnowledgeGraph存储场地/工艺/样式数据，支持历史复用 |
| **工具链编排** | ToolChainOrchestrator实现多图表并行生成，效率提升 |
| **模板系统复用** | Template系统统一管理图表模板和文档样式 |
| **EIA工具包协同** | 模拟数据直接用于影响范围图生成 |

### 37.6.3 实施价值评估

| 价值维度 | 评估 | 说明 |
|---------|------|------|
| **效率提升** | 5星 | 图表生成时间从数天缩短到数分钟 |
| **质量保证** | 5星 | 100%符合专业规范，避免人为错误 |
| **一致性** | 5星 | 图表与文档风格完全统一 |
| **易用性** | 5星 | 零学习成本，一键生成 |
| **可扩展性** | 4星 | 模块化设计，易于扩展新图表类型 |

---

## 37.7 核心结论

### 37.7.1 方案评估

| 评估维度 | 评分 | 说明 |
|---------|------|------|
| **方案实用性** | 5星（极高） | 不追求花哨，追求实用 |
| **与LivingTree匹配度** | **4.5/5** | 所有组件完全契合 |
| **实施可行性** | **极高** | 4-6周完成，技术风险低 |
| **用户价值** | **极高** | 解决实际问题，快速产生价值 |

### 37.7.2 核心结论

1. **方案实用性**：5星（极高）
   - 不追求花哨，追求实用
   - 解决实际问题（图表生成耗时）
   - 符合环评报告专业规范

2. **与LivingTree匹配度**：**4.5/5**（极高）
   - 6个组件平均匹配度4.5/5
   - 所有组件都可以复用LivingTree现有能力
   - 无需额外基础设施

3. **实施可行性**：极高
   - 4-6周完成核心功能
   - 技术风险低
   - 可快速迭代上线

4. **价值**：极高
   - 图表生成时间缩短90%+
   - 零学习成本，零编辑负担
   - 与报告生成无缝集成

### 37.7.3 最终推荐

**推荐实施优先级**：5星（最高）

核心信息：
- 与LivingTree匹配度：4.5/5（极高）
- 实施周期：4-6周（快速落地）
- 技术风险：低（完全基于现有能力）
- 用户价值：极高（解决实际问题）

**推荐立即启动！**

**核心价值**：
1. 用户只需提供数据，系统自动生成符合专业规范的图表
2. 一键生成5种图表，自动插入报告，自动生成目录
3. 4-6周完成开发，快速上线，立即产生价值

---

## 37.8 小结

本章分析了**简洁版环评图表自动生成方案**与LivingTree项目的匹配度。

**主要结论**：
1. **平均匹配度评分**：**4.5/5**（极高）
2. **最高匹配度**：AutoFigureGenerationPipeline（4.8/5）
3. **实施周期**：4-6周（快速落地）
4. **技术风险**：低（完全基于现有能力）

**六大核心组件**：
1. AutoLayoutGenerator - 自动平面布局图生成（4.4/5）
2. AutoProcessFlowGenerator - 自动工艺流程图生成（4.5/5）
3. DocumentStyleGenerator - 文档风格生成器（4.5/5）
4. SimpleAutoGenerator - 简化自动生成器（4.5/5）
5. SimpleAdjuster - 简单调整功能（4.5/5）
6. AutoFigureGenerationPipeline - 自动图表生成流水线（4.8/5）

**与36章方案对比**：
- 37章方案更务实，与LivingTree契合度更高
- 实施周期缩短80%+（从12个月到4-6周）
- 技术风险大幅降低
- 建议以37章方案为核心，选择性吸收36章精华

**让环评报告图表生成从"耗时数天"进化到"一键生成"！**
"""

def main():
    # 查找文档文件（在docs/子目录下）
    docs_dir = "docs"
    doc_file = os.path.join(docs_dir, "统一架构层改造方案_完整版_v3.md")
    
    # 如果找不到，尝试其他可能的文件名
    if not os.path.exists(doc_file):
        possible_files = [
            os.path.join(docs_dir, "统一架构层改造方案_完整版_v3.md"),
            os.path.join(docs_dir, "统一架构层改造方案_完整版.md"),
            os.path.join(docs_dir, "统一架构层改造方案.md"),
            "统一架构层改造方案_完整版_v3.md",
            "统一架构层改造方案_完整版.md",
            "统一架构层改造方案.md"
        ]
        for f in possible_files:
            if os.path.exists(f):
                doc_file = f
                break
        else:
            print("错误：找不到文档文件")
            return
    
    print(f"找到文档：{doc_file}")
    
    # 读取现有内容
    with open(doc_file, 'r', encoding='utf-8') as f:
        existing_content = f.read()
    
    print(f"现有文档长度：{len(existing_content)} 字符")
    
    # 追加第三十七章
    new_content = existing_content + chapter37_content
    
    # 写回文件
    with open(doc_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"第三十七章已追加到文档")
    print(f"新文档长度：{len(new_content)} 字符")
    print(f"第三十七章长度：{len(chapter37_content)} 字符")

if __name__ == "__main__":
    main()
