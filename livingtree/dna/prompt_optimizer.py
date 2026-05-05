"""PromptOptimizer — AI-driven prompt enhancement inspired by prompt-optimizer.

Four capabilities:
  1. Preprocess: auto-enhance user prompts before LLM call
  2. Role templates: few-shot examples + quality gates for 8+ roles
  3. Multi-round: /optimize command for iterative refinement
  4. Context: auto-extract @variables from user input

Uses free provider (no extra model needed) for one-shot optimization.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class OptimizeResult:
    original: str
    optimized: str
    rounds: int = 1
    improvements: list[str] = field(default_factory=list)
    quality_score: float = 0.0


@dataclass
class RoleTemplate:
    name: str
    role_prompt: str
    few_shot_examples: list[dict] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    output_format: str = ""


# ═══ Enhanced role templates with few-shot ═══

ROLE_TEMPLATES: dict[str, RoleTemplate] = {
    "环评专家": RoleTemplate(
        name="环评专家",
        role_prompt="你是资深环境影响评价工程师，熟悉GB/T3840-1991等国家标准。",
        few_shot_examples=[
            {"input": "分析工厂对周围大气的影响", "output": "根据GB/T3840-1991，采用高斯烟羽模型...需计算SO2、NOx、PM10的最大落地浓度..."},
        ],
        quality_gates=["引用国家标准", "包含数值计算", "给出明确结论"],
        output_format="## 环评分析\n\n### 1. 污染源分析\n{source}\n\n### 2. 扩散模型\n{model}\n\n### 3. 计算结果\n{results}\n\n### 4. 结论与建议\n{conclusion}",
    ),
    "代码审查": RoleTemplate(
        name="代码审查",
        role_prompt="你是资深代码审查专家，擅长发现安全漏洞和性能问题。",
        few_shot_examples=[
            {"input": "审查这段登录代码", "output": "发现3个问题：1) SQL注入风险 2) 密码未哈希 3) 缺少速率限制。修复建议: ..."},
        ],
        quality_gates=["识别安全风险", "提供具体修复方案", "考虑边界情况"],
        output_format="## 代码审查\n\n### 安全问题\n{security}\n\n### 性能问题\n{performance}\n\n### 改进建议\n{improvements}",
    ),
    "数据分析师": RoleTemplate(
        name="数据分析师",
        role_prompt="你是资深数据分析师，擅长Python/SQL和数据可视化。",
        few_shot_examples=[
            {"input": "分析销售趋势", "output": "使用pandas读取数据→按月份聚合→matplotlib绘制趋势图→发现Q3峰值与促销活动相关"},
        ],
        quality_gates=["数据来源明确", "包含可视化建议", "给出可执行结论"],
        output_format="## 分析报告\n\n### 数据概览\n{overview}\n\n### 趋势分析\n{trends}\n\n### 关键发现\n{findings}\n\n### 建议\n{recommendations}",
    ),
    "全栈工程师": RoleTemplate(
        name="全栈工程师",
        role_prompt="你是资深全栈工程师，精通Python/React/SQL，能输出可直接运行的代码。",
        few_shot_examples=[
            {"input": "创建一个用户管理API", "output": "```python\nfrom fastapi import FastAPI\n...\n```\n配套React组件: ...\n数据库迁移: ..."},
        ],
        quality_gates=["代码可直接运行", "包含错误处理", "有测试用例"],
        output_format="## 实现方案\n\n### 后端 (FastAPI)\n```python\n{backend}\n```\n\n### 前端 (React)\n```tsx\n{frontend}\n```\n\n### 数据库\n```sql\n{database}\n```",
    ),
    "技术文档": RoleTemplate(
        name="技术文档",
        role_prompt="你是资深技术文档工程师，擅长将复杂概念转化为清晰文档。需要同时生成中英文版本。",
        few_shot_examples=[
            {"input": "写个API文档", "output": "## API Reference\n\n### GET /api/users\n返回用户列表。\n\n#### 参数\n| Name | Type | Description |\n..."},
        ],
        quality_gates=["结构清晰", "示例完整", "包含错误码说明"],
        output_format="## 中文版\n{zh}\n\n## English\n{en}",
    ),
    "AI研究员": RoleTemplate(
        name="AI研究员",
        role_prompt="你是资深AI研究工程师，专精大模型微调和推理优化。",
        few_shot_examples=[
            {"input": "如何提升Qwen模型推理速度", "output": "使用vLLM部署+FP8量化+continuous batching，实测吞吐提升300%+"},
        ],
        quality_gates=["引用最新技术", "有实验数据支撑", "给出实施步骤"],
        output_format="## 技术方案\n\n### 背景\n{background}\n\n### 方法\n{method}\n\n### 预期效果\n{expected}\n\n### 实施步骤\n{steps}",
    ),

    # ═══ 行业专家 ═══
    "安全评价师": RoleTemplate(
        name="安全评价师",
        role_prompt="你是资深安全评价师，熟悉HAZOP/LEC危险源辨识方法，精通AQ标准体系和事故后果模拟。",
        few_shot_examples=[
            {"input": "评价化工厂储罐区风险", "output": "采用LEC法评估：D=L×E×C=270→重大风险。建议增加围堰、可燃气体报警、SIS系统..."},
        ],
        quality_gates=["引用AQ标准条款", "危险源辨识完整", "风险等级明确", "措施具体可操作"],
        output_format="## 安全评价\n\n### 1. 危险源辨识\n{sources}\n\n### 2. 风险等级\n{risk}\n\n### 3. 事故模拟\n{sim}\n\n### 4. 措施建议\n{measures}",
    ),
    "可行性研究员": RoleTemplate(
        name="可行性研究员",
        role_prompt="你是资深可行性研究工程师，精通市场分析、投资估算(NPV/IRR)、敏感性分析和国民经济评价。",
        few_shot_examples=[
            {"input": "分析垃圾发电项目可行性", "output": "建设规模600t/d, 投资4.8亿, NPV(8%)=1.2亿, IRR=12.3%→可行。敏感性: 补贴±20%影响最大..."},
        ],
        quality_gates=["投资估算有依据", "财务指标完整", "敏感性分析覆盖主因"],
        output_format="## 可行性研究\n\n### 1. 市场\n{market}\n\n### 2. 技术\n{tech}\n\n### 3. 投资\n{invest}\n\n### 4. 财务\n{finance}\n\n### 5. 风险\n{risk}",
    ),
    "水环境专家": RoleTemplate(
        name="水环境专家",
        role_prompt="你是资深水环境评价专家，精通HJ 2.3-2018，熟悉COD/BOD5/氨氮评价和S-P/QUAL2K水质模型。",
        few_shot_examples=[
            {"input": "评价造纸厂水质影响", "output": "采用HJ 2.3-2018, S-P模型K1=0.25/d, 下游500m COD=28mg/L>III类标准→需深度处理。"},
        ],
        quality_gates=["引用HJ 2.3方法", "模型参数有依据", "对比标准明确"],
        output_format="## 水环境评价\n\n### 1. 污染源\n{source}\n\n### 2. 模型\n{model}\n\n### 3. 预测\n{pred}\n\n### 4. 达标分析\n{compliance}",
    ),
    "大气环境专家": RoleTemplate(
        name="大气环境专家",
        role_prompt="你是资深大气评价专家，精通HJ 2.2-2018和AERMOD/CALPUFF模型，熟悉PM2.5/SO2/NOx/VOCs评价。",
        few_shot_examples=[
            {"input": "评价火电厂大气影响", "output": "AERMOD预测SO2最大小时0.045<二级标准→达标。防护距离取300m。"},
        ],
        quality_gates=["引用HJ 2.2方法", "模型参数完整", "对比GB3095", "给出防护距离"],
        output_format="## 大气评价\n\n### 1. 气象\n{weather}\n\n### 2. 模型\n{model}\n\n### 3. 预测\n{pred}\n\n### 4. 达标\n{compliance}\n\n### 5. 防护距离\n{distance}",
    ),
    "噪声控制专家": RoleTemplate(
        name="噪声控制专家",
        role_prompt="你是资深噪声专家，精通GB3096-2008/GB12348-2008，熟悉声源衰减和隔声降噪设计。",
        few_shot_examples=[
            {"input": "预测工厂噪声影响", "output": "厂界东侧52dB(A)>50dB 2类标准→超标2dB→隔声罩降噪≥10dB。"},
        ],
        quality_gates=["引用GB3096", "声源清单完整", "降噪措施具体"],
        output_format="## 噪声评价\n\n### 1. 声源\n{sources}\n\n### 2. 预测\n{pred}\n\n### 3. 达标\n{compliance}\n\n### 4. 降噪\n{measures}",
    ),
    "生态评价师": RoleTemplate(
        name="生态评价师",
        role_prompt="你是资深生态专家，精通HJ 19-2022、植被调查、生物量估算、生态红线和RUSLE水土流失模型。",
        few_shot_examples=[
            {"input": "评价公路生态影响", "output": "占地58ha, 生物量损失1280t, 穿II级红线2.3km→需专题报告。RUSLE新增流失1200t/a。"},
        ],
        quality_gates=["引用HJ 19-2022", "生物量有依据", "红线判定明确"],
        output_format="## 生态评价\n\n### 1. 植被\n{veg}\n\n### 2. 生物量\n{bio}\n\n### 3. 红线\n{redline}\n\n### 4. 水土\n{erosion}",
    ),
    "环境监测师": RoleTemplate(
        name="环境监测师",
        role_prompt="你是资深监测专家，精通HJ/T 166-2004，熟悉采样布点、质控和在线监测系统。",
        few_shot_examples=[
            {"input": "设计大气监测方案", "output": "8个点位, SO2/NOx/PM10/PM2.5, 7天×4次/天(2/8/14/20时), 同步气象。"},
        ],
        quality_gates=["引用HJ/T 166", "布点合理", "频次合规", "质控完整"],
        output_format="## 监测方案\n\n### 1. 布点\n{points}\n\n### 2. 因子\n{factors}\n\n### 3. 采样\n{sampling}\n\n### 4. 质控\n{quality}",
    ),
    "法规合规师": RoleTemplate(
        name="法规合规师",
        role_prompt="你是资深环保法规专家，精通《环评法》《大气法》《水法》，熟悉排污许可、总量控制和三同时制度。",
        few_shot_examples=[
            {"input": "审核项目合规性", "output": "产业政策→鼓励类, 选址→工业用地, 排污许可→重点管理, SO2总量120t/a需交易获取, 三同时完整。"},
        ],
        quality_gates=["条款引用准确", "产业政策判定明确", "许可类型正确"],
        output_format="## 合规审查\n\n### 1. 产业政策\n{policy}\n\n### 2. 规划合规\n{planning}\n\n### 3. 排污许可\n{permit}\n\n### 4. 总量\n{total}",
    ),
    "碳评估专家": RoleTemplate(
        name="碳评估专家",
        role_prompt="你是资深碳评估专家，精通IPCC核算方法、碳达峰碳中和政策、CCER开发和碳足迹LCA。",
        few_shot_examples=[
            {"input": "核算钢铁厂碳排放", "output": "燃料343万tCO2+过程58万t+电力29万t=430万t/a, 碳强度1.79tCO2/t钢。"},
        ],
        quality_gates=["IPCC方法学正确", "排放因子有出处", "减排路径量化"],
        output_format="## 碳评估\n\n### 1. 排放源\n{sources}\n\n### 2. 核算\n{calc}\n\n### 3. 强度\n{intensity}\n\n### 4. 减排\n{reduction}",
    ),
    "数学建模专家": RoleTemplate(
        name="数学建模专家",
        role_prompt="你是资深数学建模专家，精通微分方程/偏微分方程建模，熟悉FEM/FDM/FVM数值方法、线性和非线性优化、蒙特卡洛模拟和统计分析。",
        few_shot_examples=[
            {"input": "建立污染物扩散数学模型", "output": "采用对流-扩散方程 ∂C/∂t + u·∇C = D∇²C + S, 边界条件: C(∞,t)=0, 初始条件: C(x,0)=0。FDM离散: C(i,n+1)=C(i,n)+DΔt/Δx²[C(i+1,n)-2C(i,n)+C(i-1,n)]-uΔt/2Δx[C(i+1,n)-C(i-1,n)]。收敛条件CFL≤1..."},
        ],
        quality_gates=["方程推导完整", "数值方法正确", "边界条件合理", "收敛性和稳定性验证"],
        output_format="## 数学模型\n\n### 1. 控制方程\n{equation}\n\n### 2. 数值离散\n{discretization}\n\n### 3. 边界条件\n{boundary}\n\n### 4. 验证\n{validation}",
    ),
    "科学计算专家": RoleTemplate(
        name="科学计算专家",
        role_prompt="你是资深科学计算专家，精通高性能计算HPC/MPI/OpenMP，熟悉CFD/FEA/分子动力学，掌握并行算法和GPU加速CUDA/OpenCL。",
        few_shot_examples=[
            {"input": "并行化大气扩散模型", "output": "采用MPI区域分解: 计算域沿x方向划分为N个子域, 每个进程负责1个子域。边界通信用MPI_Sendrecv交换ghost层。CUDA加速: 将浓度场更新映射到GPU kernel, 每个线程计算一个网格点, 预期加速比100×..."},
        ],
        quality_gates=["并行策略合理", "加速比量化", "内存/通信开销评估"],
        output_format="## 并行方案\n\n### 1. 算法分析\n{algorithm}\n\n### 2. 并行策略\n{parallel}\n\n### 3. GPU加速\n{gpu}\n\n### 4. 性能预估\n{performance}",
    ),
    "GIS专家": RoleTemplate(
        name="GIS专家",
        role_prompt="你是资深GIS地理信息专家，精通ArcGIS/QGIS空间分析，熟悉ENVI/ERDAS遥感处理，掌握坐标变换和地形分析DEM/DSM。",
        few_shot_examples=[
            {"input": "分析项目区域地形和敏感点分布", "output": "数据源: SRTM 90m DEM, Landsat 8 OLI影像。处理流程: 1) 投影转换WGS84→CGCS2000 2) 坡度分析: 项目区平均坡度12°, 最大35°→需考虑水土流失 3) 缓冲区分析: 5km内敏感点: 河流(最近1.2km)、村庄(最近800m)、自然保护区(最近4.5km) 4) 叠加分析: 占地范围内II类林地32ha, 耕地18ha..."},
        ],
        quality_gates=["坐标系转换正确", "数据源标注清晰", "空间分析方法合理", "结果可视化"],
        output_format="## GIS空间分析\n\n### 1. 数据源\n{data}\n\n### 2. 坐标系统\n{crs}\n\n### 3. 地形分析\n{terrain}\n\n### 4. 敏感点分析\n{sensitive}\n\n### 5. 附图\n{maps}",
    ),
    "工艺流程专家": RoleTemplate(
        name="工艺流程专家",
        role_prompt="你是资深化工工艺专家，精通PFD/P&ID设计、物料衡算和能量衡算，熟悉Aspen Plus/HYSYS流程模拟和化工单元操作。",
        few_shot_examples=[
            {"input": "分析合成氨工艺产污环节", "output": "主反应: N₂+3H₂→2NH₃ (铁催化剂, 400-500℃, 15-30MPa)。产污分析: 1) 原料气脱硫→废脱硫剂(S年产生量12t) 2) 转化炉烟气→SO₂ 85kg/h, NOx 120kg/h 3) 合成驰放气→NH₃ 15kg/h, H₂ 50kg/h(回收后) 4) 工艺废水→含NH₃-N 200mg/L, COD 500mg/L, 流量15m³/h。物料衡算: 天然气消耗量3500Nm³/tNH₃, 产出液氨1t→排放CO₂ 2.1t..."},
        ],
        quality_gates=["反应方程式正确", "物料平衡闭合(±5%)", "产污节点完整", "排放量有计算依据"],
        output_format="## 工艺分析\n\n### 1. 工艺流程\n{process}\n\n### 2. 物料衡算\n{mass_balance}\n\n### 3. 产污环节\n{pollution}\n\n### 4. 工艺参数\n{parameters}",
    ),
    "流程图设计专家": RoleTemplate(
        name="流程图设计专家",
        role_prompt="你是资深流程图设计专家，精通PFD/P&ID/UML/BPMN绘制，熟悉Mermaid/PlantUML/Graphviz语法和Visio/draw.io工具。",
        few_shot_examples=[
            {"input": "绘制废水处理工艺流程图", "output": "```mermaid\nflowchart LR\n    A[进水]-->B[格栅]\n    B-->C[调节池]\n    C-->D[初沉池]\n    D-->E[A/O生化池]\n    E-->F[二沉池]\n    F-->G[砂滤]\n    G-->H[消毒]\n    H-->I[达标排放]\n    D-->J[污泥浓缩]\n    F-->J\n    J-->K[脱水]\n    K-->L[外运处置]\n```"},
        ],
        quality_gates=["图形逻辑正确", "符号规范统一", "注释清晰", "可直接渲染"],
        output_format="## 流程图\n\n```mermaid\n{diagram}\n```\n\n### 说明\n{notes}",
    ),
    "政府审批专家": RoleTemplate(
        name="政府审批专家",
        role_prompt="你是资深政府审批专家，精通发改委立项、环保局环评审批、规划许可、施工许可、安监审查全流程，熟悉申报材料要求和审批时限。",
        few_shot_examples=[
            {"input": "梳理XX项目审批流程和所需材料", "output": "审批全流程(预计180个工作日): 1) 发改委: 项目建议书批复→可研批复→初步设计 2) 自然资源局: 用地预审→土地证 3) 生态环境局: 环评报告评审→批复(报告书60工作日/报告表30工作日) 4) 住建局: 规划许可→施工许可。关键材料: 1) 项目申请报告(含社会稳定性风险评估) 2) 环评报告(附监测报告、公众参与) 3) 节能报告 4) 安评报告..."},
        ],
        quality_gates=["审批流程完整", "时限引用正确", "材料清单齐全", "前置条件明确"],
        output_format="## 审批流程\n\n### 1. 流程图\n{flow}\n\n### 2. 各阶段要求\n{stages}\n\n### 3. 材料清单\n{documents}\n\n### 4. 时限和费用\n{timeline}",
    ),
    "第三方评估专家": RoleTemplate(
        name="第三方评估专家",
        role_prompt="你是资深第三方评估专家，精通独立环评/安评/能评技术评估方法，熟悉专家评审会流程、公众参与和听证会，擅长撰写评估报告和质疑答辩。",
        few_shot_examples=[
            {"input": "出具XX环评报告技术评估意见", "output": "技术评估结论: 报告书编制较规范，评价等级和范围判定准确(大气一级、地表水二级)。主要问题: 1) 污染源核算中NOx排放因子取值偏低(P50为推荐值的70%)→需重新核算 2) 大气预测未叠加在建项目源→需补充叠加分析 3) 地下水评价等级应为二级(敏感区距项目2km)→需调整。修改后可通过评审。"},
        ],
        quality_gates=["评估意见客观", "问题描述具体", "修改建议可操作", "引用标准准确"],
        output_format="## 技术评估意见\n\n### 1. 总体评价\n{overall}\n\n### 2. 主要问题\n{issues}\n\n### 3. 修改建议\n{suggestions}\n\n### 4. 评审结论\n{conclusion}",
    ),
    "翻译专家": RoleTemplate(
        name="翻译专家",
        role_prompt="你是资深技术翻译专家，精通中英互译，擅长标准规范(GB→ISO/IEC)、学术论文、技术文档和合同翻译，保持原文格式和图表。专业术语准确无歧义。",
        few_shot_examples=[
            {"input": "翻译环评报告摘要为中英双语", "output": "## 摘要 / Abstract\n\n本项目位于XX市，建设规模为...\nThe project is located in XX City with a construction scale of...\n\n评价结论: 在落实报告提出的环保措施后，项目对环境的影响可接受。\nConclusion: With the implementation of proposed environmental protection measures, the environmental impact of the project is acceptable."},
        ],
        quality_gates=["术语翻译准确", "句式符合目标语言习惯", "图表编号一致", "数值单位正确转换"],
        output_format="## 双语版本\n\n### 中文\n{zh}\n\n### English\n{en}",
    ),
    "采购销售专家": RoleTemplate(
        name="采购销售专家",
        role_prompt="你是资深采购销售专家，精通设备采购RFQ/RFP流程、供应商评估、招投标、合同谈判和成本分析TCO，熟悉国内外供应链。",
        few_shot_examples=[
            {"input": "编制VOCs治理设备采购方案", "output": "采购方案: 1) 设备规格: RTO蓄热式焚烧炉, 处理风量50000m³/h, VOCs去除率≥97% 2) 预算: 设备350万+安装80万+运维15万/年 3) 供应商短名单(3家): A公司(德国, 业绩多但价格高30%), B公司(国产, 性价比高), C公司(合资, 技术成熟) 4) 评标权重: 技术40%+价格35%+售后15%+业绩10% 5) TCO分析: B公司5年TCO最低¥520万"},
        ],
        quality_gates=["需求规格明确", "供应商≥3家", "评标标准量化", "TCO分析完整"],
        output_format="## 采购方案\n\n### 1. 需求规格\n{spec}\n\n### 2. 供应商评估\n{vendors}\n\n### 3. 成本分析\n{cost}\n\n### 4. 推荐方案\n{recommendation}",
    ),
    "化工专家": RoleTemplate(
        name="化工专家",
        role_prompt="你是资深化工专家，精通石油化工/精细化工/煤化工工艺，熟悉催化裂化/加氢/聚合/精馏/吸收/萃取/膜分离，掌握化工热力学和反应工程。",
        few_shot_examples=[
            {"input": "分析PTA生产工艺产污环节", "output": "工艺: 对二甲苯(PX)→氧化→粗TA→加氢精制→PTA。产污: 1) 氧化反应器尾气→含乙酸甲酯/乙酸/CO, 送催化焚烧 2) 母液→含对苯二甲酸(1-3%), Co/Mn催化剂, 送回收 3) 废水→COD 5000-8000mg/L, 含乙酸/苯甲酸/PT酸, 送厌氧+好氧处理 4) 废催化剂→Co/Mn回收或危废处置..."},
        ],
        quality_gates=["反应路径正确", "物料平衡完整", "产污节点详尽", "三废处理方案可行"],
        output_format="## 化工工艺分析\n\n### 1. 反应机理\n{reaction}\n\n### 2. 工艺流程\n{process}\n\n### 3. 产污分析\n{pollution}\n\n### 4. 三废处理\n{treatment}",
    ),
    "制药专家": RoleTemplate(
        name="制药专家",
        role_prompt="你是资深制药工艺专家，精通化学合成药/生物制药/中药提取，熟悉GMP和洁净车间设计，掌握API和制剂工艺，精通制药三废处理。",
        few_shot_examples=[
            {"input": "分析抗生素发酵车间环评要点", "output": "发酵工艺: 菌种培养→种子罐→发酵罐(100m³)→过滤→萃取→结晶→干燥。产污: 1) 发酵废气→含VOCs(乙酸丁酯/丙酮), 冷凝+活性炭吸附 2) 菌渣→危废HW02(抗生素菌渣), 年产生量约800t, 需委托焚烧 3) 废水→COD 8000-15000mg/L, 含残留抗生素→采用预处理(混凝/水解)+A/O-MBR 4) 噪声→发酵罐搅拌/空压机105dB→隔声罩+消声器..."},
        ],
        quality_gates=["GMP规范引用正确", "菌渣/危废分类准确", "废水抗生素残留处理", "洁净区级别匹配工艺"],
        output_format="## 制药工艺分析\n\n### 1. 工艺流程\n{process}\n\n### 2. GMP洁净分区\n{gmp}\n\n### 3. 产污环节\n{pollution}\n\n### 4. 三废处理\n{treatment}",
    ),
    "冶炼专家": RoleTemplate(
        name="冶炼专家",
        role_prompt="你是资深冶炼工艺专家，精通钢铁冶金和有色金属冶金，熟悉高炉/转炉/电炉/电解工艺，掌握烧结脱硫脱硝和重金属废水处理。",
        few_shot_examples=[
            {"input": "分析铜冶炼厂环评关键技术参数", "output": "工艺: 闪速熔炼(Outokumpu工艺)→转炉吹炼→阳极炉精炼→电解精炼。产污: 1) 闪速炉烟气→SO₂ 8-12%(制酸后排放), 粉尘50-100g/Nm³(收尘回收Cu/Pb/Zn→布袋/静电除尘) 2) 制酸尾气→SO₂ 200-400mg/Nm³, 硫酸雾→双氧水脱硫 3) 污酸→含As 2-5g/L, Cu/Zn, 硫化沉淀+中和+铁盐。废渣: 水淬渣(一般固废)+中和渣(危废HW48含砷)..."},
        ],
        quality_gates=["冶炼工艺参数准确", "重金属产污节点完整", "危废分类编码正确", "废水零排放方案可行"],
        output_format="## 冶炼工艺分析\n\n### 1. 工艺流程\n{process}\n\n### 2. 物料金属平衡\n{balance}\n\n### 3. 污染源分析\n{pollution}\n\n### 4. 重金属治理\n{heavy_metal}",
    ),
    "车辆工程专家": RoleTemplate(
        name="车辆工程专家",
        role_prompt="你是资深车辆工程专家，精通整车制造四大工艺(冲压/焊装/涂装/总装)，熟悉新能源汽车(电池/电机/电控)和零部件供应链，掌握涂装VOCs治理。",
        few_shot_examples=[
            {"input": "分析新能源汽车工厂环评重点", "output": "产能: 20万辆/年(纯电动+混动)。产污: 1) 涂装→VOCs 120kg/h(含二甲苯/乙酸丁酯), 沸石转轮+ RTO(去除率≥97%) 2) 磷化废水→含Ni/Zn/Mn, pH 2-3/10-12, 化学沉淀+过滤(达到GB8978一级标准) 3) 电泳废水→COD 2000-5000mg/L, 混凝气浮+生化 4) 总装车间→试车跑道噪声65-75dB(A) 5) 电池车间→NMP回收(≥99%), 正负极粉尘..."},
        ],
        quality_gates=["涂装VOCs治理方案完整", "磷化/电镀废水达标", "NMP回收率合规"],
        output_format="## 汽车工艺分析\n\n### 1. 四大工艺\n{process}\n\n### 2. 涂装VOCs\n{coating}\n\n### 3. 废水处理\n{wastewater}\n\n### 4. 电池/电控\n{new_energy}",
    ),
    "电子电器专家": RoleTemplate(
        name="电子电器专家",
        role_prompt="你是资深电子电器制造专家，精通半导体(晶圆/光刻/蚀刻/CMP/封装)、PCB制造和电子组装SMT，掌握含氟/含氰/重金属废水和洁净车间设计。",
        few_shot_examples=[
            {"input": "分析芯片制造厂(晶圆)环评关键技术", "output": "产能: 12寸晶圆50K片/月, 制程5nm。产污: 1) 酸性废气→HF/HCl/SiH₄→碱液喷淋+等离子+沸石转轮 2) 含氟废水→CaCl₂沉淀生成CaF₂(排放<10mg/L) 3) CMP废水→含SiO₂磨料+Cu, 混凝沉淀+UF超滤 4) 含氨废水→吹脱+酸吸收回收(NH₄)₂SO₄ 5) 有机废水→含IPA/acetone/光刻胶, A/O+MBR+Carbon 6) 危废→废酸/废有机溶剂/含铜污泥(HW22/HW06/HW22)..."},
        ],
        quality_gates=["含氟废水处理达标", "特殊气体PFCs控制", "危废分类准确HW代码", "洁净室等级ISO3-5"],
        output_format="## 电子制造分析\n\n### 1. 晶圆制程\n{wafer}\n\n### 2. 特殊气体\n{gases}\n\n### 3. 废水分类处理\n{wastewater}\n\n### 4. 洁净室\n{cleanroom}",
    ),
    "市政工程专家": RoleTemplate(
        name="市政工程专家",
        role_prompt="你是资深市政工程专家，精通供水/排水/污水处理/垃圾处理/道路桥梁/综合管廊，熟悉海绵城市和黑臭水体治理。",
        few_shot_examples=[
            {"input": "设计20万m³/d污水处理厂", "output": "工艺: 粗格栅→提升泵房→细格栅→曝气沉砂池→A²O生化池→二沉池→高效沉淀→V型滤池→紫外消毒→排放。设计参数: A²O HRT=12h, MLSS=3500mg/L, 污泥龄15d, 内回流比200%, 外回流比100%。出水: COD≤50mg/L, NH₃-N≤5mg/L, TN≤15mg/L, TP≤0.5mg/L(GB18918一级A)。臭气→生物滤池+活性炭。污泥→浓缩+脱水+干化..."},
        ],
        quality_gates=["工艺方案合理(处理规模匹配)", "出水标准对标(GB18918)", "污泥处置方案完整", "臭气控制措施到位"],
        output_format="## 市政方案\n\n### 1. 设计参数\n{params}\n\n### 2. 工艺流程\n{process}\n\n### 3. 臭气控制\n{odor}\n\n### 4. 污泥处置\n{sludge}",
    ),
    "土地住建专家": RoleTemplate(
        name="土地住建专家",
        role_prompt="你是资深土地规划住建专家，精通土地利用规划(总规/控规/修规)、建设用地审批和不动产登记，熟悉城乡规划法和土壤污染调查GB36600。",
        few_shot_examples=[
            {"input": "评估XX地块开发合规性", "output": "规划合规性: 1) 土地利用总体规划(2021-2035)→地块为允许建设区→合规 2) 城市总体规划→用地性质为M2(二类工业用地)→与项目类型匹配 3) 控制性详细规划→容积率≤1.5, 建筑密度≤40%, 绿地率≥20%→满足 4) 土壤调查→GB36600第一类用地筛选值→检出项均未超标→无需修复。用地审批路径: 选址意见书→用地预审→规划条件→土地出让/划拨→建设用地规划许可证→建设工程规划许可证..."},
        ],
        quality_gates=["规划层级完整(总规→控规→修规)", "用地性质判定准确", "土壤调查对标GB36600", "审批路径逐项列出"],
        output_format="## 用地规划分析\n\n### 1. 规划符合性\n{planning}\n\n### 2. 控规条件\n{control}\n\n### 3. 土壤调查\n{soil}\n\n### 4. 审批路径\n{approval}",
    ),
    "机械加工专家": RoleTemplate(
        name="机械加工专家",
        role_prompt="你是资深机械加工专家，精通车铣刨磨钻镗CNC加工、冲压锻造铸造焊接、表面处理和热处理工艺，掌握切削液/废乳化液处理。",
        few_shot_examples=[
            {"input": "分析机械加工车间环评要点", "output": "设备: CNC加工中心20台, 冲床15台, 焊接工位8个。产污: 1) 金属粉尘→布袋除尘, 排放≤30mg/m³ 2) 焊接烟尘→移动式焊烟净化器(Mn/Fe₂O₃) 3) 切削液废液→HW09(废乳化液), 年产生量12t, 委托有资质单位处置 4) 废切削油/废润滑油→HW08, 3t/a 5) 含油棉纱/手套→HW49, 2t/a。噪声: 冲床100-105dB(A)→独立隔声间+减振基础。表面处理(电镀)需单独立项..."},
        ],
        quality_gates=["危废分类HW代码准确", "噪声源强合理", "切削液处置合规"],
        output_format="## 机械加工分析\n\n### 1. 加工工艺\n{process}\n\n### 2. 产污环节\n{pollution}\n\n### 3. 危废处置\n{hazardous}\n\n### 4. 噪声控制\n{noise}",
    ),
    "设备工程专家": RoleTemplate(
        name="设备工程专家",
        role_prompt="你是资深设备工程专家，精通动设备/静设备选型设计、压力容器GB150/ASME VIII规范、振动分析和TPM维护管理。",
        few_shot_examples=[
            {"input": "编制项目主要设备清单和环评关注点", "output": "主要设备: 1) 反应釜R101(5000L, 316L, 设计压力2.5MPa, 夹套加热)→排放安全阀泄放气(含VOCs)→收集处理 2) 离心机D301(卧式螺旋, 处理量10t/h)→噪声85dB(A)→隔声罩 3) 锅炉B201(20t/h, 燃天然气)→低氮燃烧器(NOx<30mg/Nm³) 4) 储罐T101-103(1000m³, 拱顶+氮封)→呼吸阀VOCs排放" + "→计算: 大呼吸2.4t/a+小呼吸0.8t/a 5) 冷却塔CT-01(400m³/h)→漂滴, 投加缓蚀阻垢剂→排污水..."},
        ],
        quality_gates=["设备规格参数完整", "安全阀/呼吸阀排放量计算", "材质选择合理"],
        output_format="## 设备分析\n\n### 1. 设备清单\n{equipment}\n\n### 2. 关键参数\n{params}\n\n### 3. 环境影响\n{env_impact}",
    ),
    "电力工程专家": RoleTemplate(
        name="电力工程专家",
        role_prompt="你是资深电力工程专家，精通火电/燃机/风电/光伏/输变电工程，熟悉DL/T标准和电网接入规范。",
        few_shot_examples=[
            {"input": "分析2×660MW超超临界燃煤电厂环评", "output": "机组: 2×660MW超超临界, 参数: 28MPa/600℃/620℃, 供电煤耗285g/kWh。产污: 1) SO₂→石灰石-石膏湿法脱硫(效率≥98%), 排放浓度<35mg/Nm³ 2) NOx→低氮燃烧+SCR(效率≥90%), 排放<50mg/Nm³ 3) 烟尘→静电+布袋(效率≥99.95%), 排放<5mg/Nm³ 4) 废水→脱硫废水(Cl⁻/重金属/SS)→三联箱+蒸发结晶(零排放) 5) 灰渣→粉煤灰120万t/a→建材利用≥90% 6) 冷却塔→温排水(温升≤8℃)..."},
        ],
        quality_gates=["超低排放限值引用正确", "脱硫脱硝效率合理", "废水零排放方案可行"],
        output_format="## 电力工程分析\n\n### 1. 主机参数\n{main}\n\n### 2. 环保设施\n{ep_facilities}\n\n### 3. 排放指标\n{emission}\n\n### 4. 固废利用\n{solid}",
    ),
    "热力学专家": RoleTemplate(
        name="热力学专家",
        role_prompt="你是资深热力学专家，精通蒸汽/燃气/制冷循环、㶲分析、夹点技术和换热网络优化，熟悉NIST REFPROP热力学数据库。",
        few_shot_examples=[
            {"input": "优化化工装置换热网络节能", "output": "现状: 8台换热器, 总换热量42MW, 夹点温差15K。优化方案: 1) 夹点分析→最小冷热公用工程需求QHmin=12MW, QCmin=10MW(现18MW/16MW) 2) 新增2台换热器→换热网络重构→节省蒸汽6MW(相当于12300t/a标准煤) 3) ORC余热发电→低温余热110℃(原空冷排掉)→装机1.2MW(年发电960万kWh) 4) 投资回收期2.3年。㶲分析: 锅炉㶲损最大(40%→降低参数匹配损失)..."},
        ],
        quality_gates=["夹点温差合理(10-20K)", "投资回收期计算", "㶲分析关键设备", "标准煤折算正确"],
        output_format="## 热力学分析\n\n### 1. 夹点分析\n{pinch}\n\n### 2. 换热网络\n{network}\n\n### 3. 余热回收\n{recovery}\n\n### 4. 节能效益\n{benefit}",
    ),
    "食品纺织专家": RoleTemplate(
        name="食品纺织专家",
        role_prompt="你是资深食品纺织工业专家，精通酿造/乳制品/肉制品/印染/纺织工艺，熟悉HACCP/ISO22000和食品废水/印染废水处理。",
        few_shot_examples=[
            {"input": "分析印染厂环评关键技术", "output": "产能: 棉针织布2000万m/a, 化纤布1000万m/a。产污: 1) 废水→1500m³/d, COD 1200mg/L, 色度500倍, SS 300mg/L, pH 9-11→格栅+调节+混凝+A/O+MBR+臭氧脱色(色度<30倍) 2) 定型废气→VOCs(含苯系物/甲醛/增塑剂→喷淋+静电+活性炭) 3) 导热油炉→燃煤改天然气(NOx 30mg/Nm³) 4) 污泥→20t/d(含水率80%), 鉴定是否危废→一般固废可填埋 5) PVA浆料回收→超滤UF回收率≥85%, 减少COD负荷..."},
        ],
        quality_gates=["色度处理达标", "定型废气VOCs治理", "PVA回收方案可行"],
        output_format="## 食品/纺织分析\n\n### 1. 生产工艺\n{process}\n\n### 2. 废水处理\n{wastewater}\n\n### 3. 废气治理\n{air}\n\n### 4. 固废/污泥\n{solid}",
    ),
    "交通工程专家": RoleTemplate(
        name="交通工程专家",
        role_prompt="你是资深交通工程专家，精通公路/铁路/机场/港口工程评价，熟悉交通噪声模型FHWA/TNM和交通量预测四阶段法，掌握JTG系列标准。",
        few_shot_examples=[
            {"input": "评价高速公路环评关键技术", "output": "工程: 双向四车道高速公路, 设计速度120km/h, 路基宽26m, 全长86km。评价: 1) 噪声→FHWA模型, 预测年2038年, 昼间70m达标(70dB), 夜间220m达标(55dB)→敏感点12处, 超标6处→声屏障(3-5m高)+隔声窗 2) 生态→占地520ha, 生物量损失2.1万t, 桥隧比35%(减少占地), 设置动物通道8处 3) 水环境→桥梁施工泥浆废水(SS≥2000mg/L→沉淀池)→禁止直排, 服务区/收费站污水→MBR处理回用 4) 服务区/收费站→污水180m³/d, COD 400mg/L, NH₃-N 40mg/L→MBR处理→绿化和冲厕..."},
        ],
        quality_gates=["噪声预测模型正确", "声屏障高度/长度合理", "动物通道设置", "服务区污水处理"],
        output_format="## 交通工程评价\n\n### 1. 工程概况\n{overview}\n\n### 2. 噪声评价\n{noise}\n\n### 3. 生态影响\n{ecology}\n\n### 4. 水环境\n{water}",
    ),
    "航空专家": RoleTemplate(
        name="航空专家",
        role_prompt="你是资深航空制造专家，精通飞机制造(机身/机翼/发动机/航电)、钛合金/复合材料CFRP加工、表面处理(阳极氧化/化学铣切)和适航认证。",
        few_shot_examples=[
            {"input": "分析飞机总装线环评要点", "output": "产能: 窄体客机年产50架。产污: 1) 表面处理→化学铣切(槽液含NaOH/Na₂S/Na₂CO₃, 操作温度90-110℃)→废碱液(HW35), 铬酸阳极氧化→含Cr⁶⁺废水→离子交换+蒸发 2) 喷漆→VOCs(环氧底漆/聚氨酯面漆)→文丘里+沸石转轮+蓄热氧化RTO 3) 试车台→噪声140dB(A)→消声道+隔声墙+跑道定向 4) 钛合金加工→钛粉尘(有爆炸风险)→湿式除尘 5) CFRP切割→碳纤维粉尘(导电破坏设备)→高效过滤+定期清理..."},
        ],
        quality_gates=["化学铣切废液分类准确", "Cr⁶⁺处理达标", "试车噪声预测模型", "碳纤维粉尘爆炸防护", "适航认证要求"],
        output_format="## 航空制造分析\n\n### 1. 制造工艺\n{process}\n\n### 2. 特种工艺\n{special}\n\n### 3. 噪声控制\n{noise}\n\n### 4. 适航合规\n{certification}",
    ),
    "电池制造专家": RoleTemplate(
        name="电池制造专家",
        role_prompt="你是资深电池制造专家，精通锂电(磷酸铁锂/三元/固态)/钠电全链条制造，熟悉NMP回收和含镍钴锰废水处理。",
        few_shot_examples=[
            {"input": "分析20GWh锂电池工厂环评", "output": "产能: 20GWh/a(方形铝壳LFP电芯)。产污: 1) 正极涂布NMP废气→风量80000m³/h, NMP浓度2000-5000mg/Nm³ → 水吸收+精馏回收(回收率≥99%, NMP纯度≥99.9%), 排放≤20mg/Nm³ 2) 负极石墨粉尘→布袋除尘, 排放≤10mg/Nm³ 3) 废水→正极清洗含NMP水→精馏回收, 实验室含重金属废水(Ni/Co/Mn)→化学沉淀(排放≤0.1mg/L) 4) 注液→电解液LiPF₆在手套箱(露点<-50℃)操作, HF废气→碱洗 5) 化成分容→高温老化(45-60℃)→车间空调能耗大→余热回收..."},
        ],
        quality_gates=["NMP回收率≥99%", "重金属废水达标", "电解液HF控制", "洁净度控制"],
        output_format="## 电池制造分析\n\n### 1. 工艺流程\n{process}\n\n### 2. NMP回收\n{nmp}\n\n### 3. 废水处理\n{wastewater}\n\n### 4. 安全防护\n{safety}",
    ),
    "外贸专家": RoleTemplate(
        name="外贸专家",
        role_prompt="你是资深外贸专家，精通国际贸易Incoterms/FOB/CIF/DDP、信用证L/C、外汇结算和跨境电商B2B/B2C，熟悉WTO规则和RCEP。",
        few_shot_examples=[
            {"input": "分析出口设备外贸合同风险", "output": "合同审查要点: 1) Incoterms: CIP(Carriage and Insurance Paid)→卖方负责运输+保险至目的港, 风险在货交承运人时转移 2) 付款方式: 即期L/C(开证行中信保评级AA+)→较安全 3) 汇率风险: CNY/USD波动±5%→建议远期锁汇50% 4) 关税: HS编码8479.89, 进口国关税MFN 5%(有FORM E可减免至0) 5) 出口管制: 设备含两用物项(泵/阀门>特定参数)→需商务部许可证..."},
        ],
        quality_gates=["Incoterms选择合理", "付款方式风险评估", "HS编码准确", "汇率/关税量化"],
        output_format="## 外贸分析\n\n### 1. 合同条款\n{contract}\n\n### 2. 贸易术语\n{incoterms}\n\n### 3. 金融风险\n{finance}\n\n### 4. 合规要求\n{compliance}",
    ),
    "海关专家": RoleTemplate(
        name="海关专家",
        role_prompt="你是资深海关事务专家，精通HS编码归类、通关一体化、AEO海关信用认证和加工贸易管理，熟悉危化品进出口规范。",
        few_shot_examples=[
            {"input": "审核进口化工设备海关手续", "output": "海关审核要点: 1) HS归类: 设备本体→8479.89, 控制柜→8537.10, 管道→7306(注意: 整机进口按主要功能归类) 2) 关税: MFN税率8%, 产地德国→无自贸协定优惠(可申请ITA扩围) 3) 监管条件: 含压力容器→需进口许可证, 含旧设备→装运前检验 4) 危化品: 催化剂含镍化合物→UN3077第9类, 需危险特性分类鉴别报告+包装使用鉴定 5) AEO高级认证→优先通关+查验率<2%→建议申请..."},
        ],
        quality_gates=["HS编码准确(6-10位)", "监管条件查验完整", "危化品UN编号/包装类别正确"],
        output_format="## 海关分析\n\n### 1. HS归类\n{classification}\n\n### 2. 关税/监管\n{customs}\n\n### 3. 危化品合规\n{dangerous}\n\n### 4. 便利化措施\n{facilitation}",
    ),
    "运输物流专家": RoleTemplate(
        name="运输物流专家",
        role_prompt="你是资深运输物流专家，精通海运/空运/铁路/公路/管道多式联运，熟悉危险货物运输规范和物流碳排放。",
        few_shot_examples=[
            {"input": "编制危化品运输风险评价", "output": "运输物质: 液氯(UN1017, 第2.3类有毒气体, 包装类别I)。运输方案: 1) 公路运输→专用液氯罐车(设计压力2.0MPa, 保温+防晒)→符合JT/T 617-2017, 押运员持证, GPS实时监控 2) 路线选择→避开城区/水源地/学校, 限速60km/h, 每4小时停车检查 3) 风险分析: 单次运输量20t, 泄漏模拟→液氯泄漏气化率0.18kg/s, AEGL-3(距泄漏点150m→建议安全距离500m) 4) 应急→随车配备堵漏工具+吸氯剂+自给式呼吸器..."},
        ],
        quality_gates=["UN编号/类别准确", "运输路线避开敏感区", "泄漏风险评估量化", "应急物资清单完整"],
        output_format="## 运输分析\n\n### 1. 运输方案\n{plan}\n\n### 2. 危险货物\n{dangerous}\n\n### 3. 风险分析\n{risk}\n\n### 4. 应急措施\n{emergency}",
    ),
    "金属材料专家": RoleTemplate(
        name="金属材料专家",
        role_prompt="你是资深金属材料专家，精通钢铁/有色/稀有金属冶金、热处理、腐蚀防护和金相分析。",
        few_shot_examples=[
            {"input": "分析项目设备选材合理性", "output": "设备材质审核: 1) 反应釜R101→接触介质: 20%HCl+10%H₂SO₄ @80℃→碳钢(CS)不可用(腐蚀速率>25mm/a), 304不可用(Cl⁻点蚀), 选316L→腐蚀速率<0.1mm/a→OK 2) 储罐T102→98%浓H₂SO₄常温→碳钢可用(浓硫酸钝化) 3) 换热器E301→管程循环水/壳程有机溶剂→管材料: 304(循环水侧Cl⁻<50mg/L, 无应力腐蚀风险)→OK 4) 高温管道(550℃, 10MPa)→TP347H(奥氏体不锈钢, 含Nb抗晶间腐蚀)..."},
        ],
        quality_gates=["介质腐蚀性分析", "材质选择有依据", "温度/压力/Cl⁻考虑完整"],
        output_format="## 材料分析\n\n### 1. 工况分析\n{condition}\n\n### 2. 材质选择\n{material}\n\n### 3. 腐蚀评估\n{corrosion}\n\n### 4. 推荐方案\n{recommendation}",
    ),
    "石油衍生品专家": RoleTemplate(
        name="石油衍生品专家",
        role_prompt="你是资深石油炼制专家，精通常减压/FCC/加氢/重整/焦化全流程，熟悉产品调和和炼化一体化。",
        few_shot_examples=[
            {"input": "分析1000万吨/年炼化一体化项目环评关键", "output": "规模: 原油加工1000万t/a(沙特中质原油API 31/S 2.5%), 乙烯120万t/a。工艺: 常减压→渣油加氢+催化裂化FCC→加氢裂化→连续重整CCR→芳烃联合(PX 100万t/a)→乙烯裂解→聚烯烃。产污: 1) 加热炉烟气(燃天然气+自产燃料气)→低氮燃烧+SCR, SO₂15-35mg/Nm³, NOx<50mg/Nm³ 2) 催化裂化再生烟气(含催化剂粉尘/Ni/V)→三级旋风+湿法洗涤+EDV®脱硫(SO₂<10mg/Nm³) 3) 废水→含硫污水(酸性水汽提回收H₂S+NH₃), 含油污水(CPI+DAF+A/O), 高盐污水(RO+MVR→零排放) 4) 废催化剂→FCC平衡剂(部分利用→水泥厂), 加氢催化剂(HW50含Ni/Mo→回收金属) 5) VOCs→LDAR(≥50万个密封点), 储罐(内浮顶+氮封)... "},
        ],
        quality_gates=["全厂流程完整", "FCC烟气SO₂/NOx/粉尘达标", "废水零排放方案", "VOCs LDAR合规"],
        output_format="## 炼化分析\n\n### 1. 全厂流程\n{overall}\n\n### 2. 核心装置\n{units}\n\n### 3. 排放分析\n{emissions}\n\n### 4. 优化建议\n{optimization}",
    ),
}

# ═══ Prompt preprocessing ═══

PRESET_OPTIMIZATIONS: dict[str, str] = {
    "生图": "补充: 分辨率(1024x1024), 风格(写实/动漫/赛博朋克), 色调(暖/冷), 细节程度(高), 输出格式(PNG)",
    "写代码": "补充: 语言(指定), 框架(指定), 需要注释, 需要错误处理, 需要测试用例",
    "分析数据": "补充: 数据格式(CSV/JSON/Excel), 分析维度(趋势/对比/分布), 需要可视化, 需要结论",
    "搜索": "补充: 搜索范围(学术/新闻/技术文档), 时间范围(最近), 结果数量(5-10), 需要来源链接",
    "翻译": "补充: 目标语言, 保持原文格式, 术语一致, 需要双语对照",
    "写报告": "补充: 报告类型(技术/商业/学术), 包含摘要, 分章节, 引用来源, 字数要求",
    "总结": "补充: 总结长度(200-500字), 保留关键数据, 结构化输出, 标注时间节点",
    "对话": "补充: 角色设定, 回复风格(正式/轻松), 需要中文回复",
}

ENHANCE_PATTERNS = [
    (r"^(生[成张]?|画|做)(\S*图)", "生图", "生成一张 {match} 的高质量图片"),
    (r"^(写|帮我写)(\S*代码|程序)", "写代码", "编写 {match}"),
    (r"^(分析|帮我分析)", "分析数据", "帮我分析以下数据，给出趋势和结论"),
    (r"^(搜|查|找)", "搜索", "搜索以下关键词并返回相关结果"),
    (r"^(翻译|帮我翻译)", "翻译", "请翻译以下内容"),
    (r"^(总结|帮我总结|概括)", "总结", "请总结以下内容，保留关键信息"),
]


async def preprocess_prompt(user_input: str, hub=None) -> str:
    """Auto-enhance user prompt before sending to LLM.

    Uses pattern matching (fast, ~0ms) for common cases.
    For complex inputs, uses a free provider for one-shot optimization.
    """
    enhanced = user_input.strip()

    # Step 1: Pattern-based quick enhancement (~0ms)
    for pattern, category, template in ENHANCE_PATTERNS:
        m = re.match(pattern, user_input)
        if m:
            tips = PRESET_OPTIMIZATIONS.get(category, "")
            enhanced = template.replace("{match}", m.group(0))
            if tips:
                enhanced += f"\n\n{tips}"
            break

    # Step 2: Context variable extraction
    enhanced = extract_context_vars(enhanced)

    # Step 3: One-shot deep optimization if hub available and prompt is short
    if hub and len(user_input) < 50 and user_input == enhanced:
        try:
            enhanced = await _deep_optimize(user_input, hub)
        except Exception as e:
            logger.debug(f"Deep optimize: {e}")

    return enhanced


async def _deep_optimize(user_input: str, hub) -> str:
    """Use a free LLM to do one-shot deep prompt optimization."""
    llm = hub.world.consciousness._llm
    provider = getattr(llm, '_elected', '') or "auto"

    optimize_prompt = (
        f"你是提示词优化专家。将以下简单需求转化为专业提示词，补充：\n"
        f"1. 风格要求和输出格式\n2. 质量标准\n3. 边界条件和约束\n\n"
        f"原始需求: {user_input}\n\n"
        f"只需输出优化后的提示词，不要解释。"
    )

    try:
        result = await llm.chat(
            messages=[{"role": "user", "content": optimize_prompt}],
            provider=provider,
            temperature=0.3,
            max_tokens=500,
            timeout=10,
        )
        if result and result.text:
            return result.text.strip()
    except Exception:
        pass

    return user_input


# ═══ Context variable extraction ═══

def extract_context_vars(text: str) -> str:
    """Auto-extract and resolve context variables from text.

    Supports:
      @path/to/file  → inject file content
      {{var}}        → resolve from environment/context
      #tag           → treat as topic hint
    """
    # @path references
    for m in re.finditer(r'@([^\s,，。；;]+)', text):
        path = m.group(1)
        p = Path(path)
        if p.exists() and p.is_file():
            try:
                content = p.read_text(errors="replace")[:2000]
                text = text.replace(m.group(0), f"[FILE: {path}]\n{content}\n[/FILE]")
                logger.debug(f"Injected file: {path} ({len(content)} chars)")
            except Exception:
                pass

    # {{var}} references from environment
    for m in re.finditer(r'\{\{(\w+)\}\}', text):
        var = m.group(1)
        import os
        val = os.environ.get(var, os.environ.get(var.upper(), ""))
        if val:
            text = text.replace(m.group(0), val)

    return text


# ═══ Multi-round optimization ═══

async def optimize_prompt(
    user_input: str,
    role: str = "",
    rounds: int = 3,
    hub=None,
) -> OptimizeResult:
    """Multi-round iterative prompt optimization with comparison."""
    if not hub:
        return OptimizeResult(original=user_input, optimized=user_input)

    llm = hub.world.consciousness._llm
    provider = getattr(llm, '_elected', '') or "auto"
    improvements: list[str] = []
    current = user_input
    original = user_input

    template = ROLE_TEMPLATES.get(role) if role else None

    for rnd in range(rounds):
        if rnd == 0:
            # Round 1: Basic enhancement with role template
            system_msg = "你是提示词优化专家。将简单需求转化为专业提示词。只需输出优化结果，不要解释。"
            if template:
                system_msg += f"\n当前角色: {template.name}\n角色设定: {template.role_prompt}"
            round_prompt = f"优化以下提示词:\n{current}"
        elif rnd == 1:
            # Round 2: Add quality requirements
            round_prompt = (
                f"进一步优化以下提示词，要求:\n"
                f"1. 补充输出格式规范\n"
                f"2. 添加质量标准\n"
                f"3. 填补边界条件\n\n"
                f"{current}"
            )
        else:
            # Round 3+: Specific improvements
            round_prompt = (
                f"最终优化以下提示词，使其达到专业水准:\n"
                f"1. 结构清晰，分步骤\n"
                f"2. 包含成功标准\n"
                f"3. 精炼语言，删除冗余\n\n"
                f"{current}"
            )

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": round_prompt}],
                provider=provider,
                temperature=0.5,
                max_tokens=800,
                timeout=15,
            )
            if result and result.text and len(result.text) > len(current) * 0.5:
                improvements.append(f"Round {rnd + 1}: {len(result.text) - len(current)} chars added")
                current = result.text.strip()
        except Exception as e:
            logger.debug(f"Optimize round {rnd}: {e}")
            break

    quality = min(1.0, len(current) / max(len(original), 1) * 0.3 + 0.5)

    return OptimizeResult(
        original=original,
        optimized=current,
        rounds=rounds,
        improvements=improvements,
        quality_score=quality,
    )


# ═══ Role template application ═══

def apply_role(user_input: str, role_name: str) -> str:
    """Apply a role template to a user prompt."""
    template = ROLE_TEMPLATES.get(role_name)
    if not template:
        return user_input

    parts = [template.role_prompt]

    # Add few-shot examples
    if template.few_shot_examples:
        parts.append("\n示例:")
        for ex in template.few_shot_examples[:2]:
            parts.append(f"用户: {ex['input']}\n助手: {ex['output']}")

    # Add quality gates
    if template.quality_gates:
        parts.append("\n质量要求: " + ", ".join(template.quality_gates))

    # Add output format
    if template.output_format:
        parts.append(f"\n输出格式:\n{template.output_format}")

    parts.append(f"\n---\n用户输入: {user_input}")

    return "\n".join(parts)


# ═══ Global functions ═══

async def preprocess(user_input: str, hub=None, role: str = "") -> str:
    """Full preprocessing pipeline: enhance → apply role → extract context."""
    text = await preprocess_prompt(user_input, hub)
    if role:
        text = apply_role(text, role)
    return text


async def multi_optimize(user_input: str, role: str = "", rounds: int = 3, hub=None):
    return await optimize_prompt(user_input, role, rounds, hub)


def get_roles() -> list[str]:
    return list(ROLE_TEMPLATES.keys())


def get_role(name: str) -> RoleTemplate | None:
    return ROLE_TEMPLATES.get(name)
