"""EnhancedToolCall — Toad ToolCall widget + system tools/skills/MCP/roles + election badge.

Display per-message L0-L3 election badge. Integrates 22 MCP tools,
4 physical models, 8 expert roles, and skill discovery into Toad's
native ToolCall rendering pipeline.
"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static
from textual.binding import Binding
from textual import on
from textual.message import Message


class ToolInvokeRequest(Message):
    """Request to invoke a system tool."""
    def __init__(self, tool_name: str, params: dict):
        super().__init__()
        self.tool_name = tool_name
        self.params = params


class ElectionBadge(Static):
    """A compact badge showing L0-L3 per-message election status.

    Single line when merged:  ⚡siliconflow-flash
    Per-layer when different: L0:longcat · L1:deepseek · L3:opencode-serve
    """

    def set_election(self, badge_text: str):
        if badge_text:
            self.update(badge_text)
            self.display = True
        else:
            self.display = False


# ═══ System tool registry ═══

SYSTEM_TOOLS: dict[str, dict] = {
    # ── File operations ──
    "file_read": {
        "name": "读取文件",
        "category": "file",
        "description": "读取文件内容（支持超大文件流式读取）",
        "params": {"path": "文件路径", "max_chars": "最大字符数(默认10000)"},
        "icon": "📖",
    },
    "file_write": {
        "name": "写入文件",
        "category": "file",
        "description": "写入/保存文件（自动选择目录: .py→src/ .docx→output/ .md→docs/）",
        "params": {"filename": "文件名", "content": "文件内容"},
        "icon": "💾",
    },
    "file_replace": {
        "name": "替换文件内容",
        "category": "file",
        "description": "精准替换文件内容（正则/章节/行范围/JSON路径），原子写入",
        "params": {"path": "文件路径", "mode": "pattern|section|lines|json", "target": "替换目标", "replacement": "新内容"},
        "icon": "✏️",
    },
    "file_find": {
        "name": "搜索文件",
        "category": "file",
        "description": "全域文件搜索（文件系统+代码+文档+历史+知识库 6路并行）",
        "params": {"query": "搜索关键词"},
        "icon": "🔍",
    },

    # ── Physical models (EIA) ──
    "gaussian_plume": {
        "name": "高斯烟羽模型",
        "category": "physics",
        "description": "大气污染物扩散高斯烟羽模型 (GB/T3840-1991)",
        "formula": "C(x,y,z) = Q/(2π·u·σy·σz) · exp(-y²/2σy²) · [exp(-(z-He)²/2σz²) + exp(-(z+He)²/2σz²)]",
        "params": {"Q": "排放速率 g/s", "u": "风速 m/s", "x": "下风向距离 m",
                   "y": "横向距离 m", "z": "受体高度 m", "stability": "稳定度 A-F",
                   "He": "有效源高 m"},
        "output": "落地浓度 C (g/m³)",
        "standard": "对比GB3095-2012环境空气质量标准",
        "icon": "🌫",
    },
    "noise_attenuation": {
        "name": "噪声衰减模型",
        "category": "physics",
        "description": "点声源几何发散衰减计算 (GB/T 17247)",
        "formula": "Lp(r) = Lw - 20·log₁₀(r) - 11  (自由场半球面)",
        "params": {"Lw": "声功率级 dB", "r": "距离 m", "ground_type": "地面类型 hard/soft"},
        "output": "声压级 Lp (dB)",
        "standard": "对比GB3096-2008声环境质量标准",
        "icon": "🔊",
    },
    "dispersion_coeff": {
        "name": "扩散系数",
        "category": "physics",
        "description": "Pasquill-Gifford 扩散系数 (σy, σz) 计算",
        "formula": "σy = a₁·x^b₁  (a₁=f(stability, x)); σz = a₂·x^b₂  (a₂=f(stability))",
        "params": {"x": "距离 m", "stability": "稳定度 A-F"},
        "output": "σy, σz (m)",
        "standard": "GB/T3840-1991 附录B 扩散参数",
        "icon": "📐",
    },

    # ── Code analysis ──
    "build_code_graph": {
        "name": "代码图谱",
        "category": "code",
        "description": "构建/重建代码知识图谱",
        "params": {"path": "项目路径"},
        "icon": "🕸",
    },
    "blast_radius": {
        "name": "影响范围",
        "category": "code",
        "description": "分析代码变更的波及范围",
        "params": {"files": "变更文件列表"},
        "icon": "💥",
    },
    "search_code": {
        "name": "代码搜索",
        "category": "code",
        "description": "按名称/路径搜索代码实体",
        "params": {"query": "搜索关键词"},
        "icon": "🔍",
    },

    # ── Knowledge ──
    "search_knowledge": {
        "name": "知识搜索",
        "category": "knowledge",
        "description": "搜索知识库",
        "params": {"query": "搜索内容"},
        "icon": "📚",
    },
    "detect_knowledge_gaps": {
        "name": "知识缺口检测",
        "category": "knowledge",
        "description": "自动检测知识空白领域",
        "params": {},
        "icon": "🔬",
    },

    # ── Cell training ──
    "train_cell": {
        "name": "训练细胞",
        "category": "cell",
        "description": "在领域数据上训练 AI 细胞",
        "params": {"cell_name": "细胞名称", "data": "训练数据"},
        "icon": "🧬",
    },
    "drill_train": {
        "name": "深度训练",
        "category": "cell",
        "description": "MS-SWIFT 自动化训练 (LoRA/QLoRA/全参数)",
        "params": {"cell_name": "细胞名称", "model_name": "模型名", "training_type": "lora/full/distill"},
        "icon": "🔧",
    },
    "absorb_codebase": {
        "name": "吸收代码库",
        "category": "cell",
        "description": "吸收代码模式到 AI 细胞",
        "params": {"path": "代码路径"},
        "icon": "🧠",
    },

    # ── Generation ──
    "generate_code": {
        "name": "代码生成",
        "category": "gen",
        "description": "AI 生成带注释的代码",
        "params": {"name": "名称", "description": "描述", "language": "编程语言", "domain": "领域"},
        "icon": "💻",
    },
    "generate_diagram": {
        "name": "图表生成",
        "category": "gen",
        "description": "AI 生成流程图/架构图/时序图 (ASCII)",
        "params": {"description": "图表描述"},
        "icon": "📊",
    },

    # ── Search ──
    "unified_search": {
        "name": "聚合搜索",
        "category": "search",
        "description": "多引擎搜索 (SparkSearch → DDGSearch)",
        "params": {"query": "搜索关键词", "limit": "结果数量"},
        "icon": "🔎",
    },

    # ── System ──
    "get_status": {
        "name": "系统状态",
        "category": "system",
        "description": "获取系统运行状态",
        "params": {},
        "icon": "📡",
    },
    "chat": {
        "name": "AI 对话",
        "category": "chat",
        "description": "发送消息到 LivingTree AI",
        "params": {"message": "消息内容"},
        "icon": "💬",
    },
    "analyze": {
        "name": "深度分析",
        "category": "chat",
        "description": "链式推理深度分析",
        "params": {"topic": "分析主题"},
        "icon": "🧪",
    },

    # ── Expert roles ──
    "full_stack_engineer": {
        "name": "全栈工程师",
        "category": "role",
        "description": "Python/JS/React/SQL 全栈开发",
        "params": {"task": "任务描述"},
        "icon": "👨‍💻",
    },
    "data_analyst": {
        "name": "数据分析师",
        "category": "role",
        "description": "数据分析、Python、SQL",
        "params": {"task": "任务描述"},
        "icon": "📈",
    },
    "ai_researcher": {
        "name": "AI研究员",
        "category": "role",
        "description": "ML、Python、算法研究",
        "params": {"task": "任务描述"},
        "icon": "🤖",
    },

    # ── Web tools ──
    "url_fetch": {
        "name": "网页获取",
        "category": "web",
        "description": "获取网页内容并提取结构化信息（文本/表格/列表/段落）",
        "params": {"url": "网页URL", "format": "markdown|text|html"},
        "icon": "🌐",
    },
    "api_call": {
        "name": "API调用",
        "category": "web",
        "description": "调用外部API（支持GET/POST/JSON鉴权）",
        "params": {"url": "API地址", "method": "GET|POST", "headers": "请求头JSON", "body": "请求体"},
        "icon": "📡",
    },

    # ── Database tools ──
    "db_query": {
        "name": "数据库查询",
        "category": "database",
        "description": "执行SQL查询（支持SQLite/PostgreSQL/MySQL）",
        "params": {"sql": "SQL语句", "db_path": "数据库路径或URI"},
        "icon": "🗄",
    },
    "db_schema": {
        "name": "数据库结构",
        "category": "database",
        "description": "读取数据库表结构/索引/关系",
        "params": {"db_path": "数据库路径或URI", "table": "表名（可选，空=全部）"},
        "icon": "📋",
    },

    # ── Git tools ──
    "git_diff": {
        "name": "Git差异",
        "category": "git",
        "description": "查看文件差异（unstaged/staged/committed）",
        "params": {"path": "文件路径（可选）", "staged": "是否只看staged"},
        "icon": "📊",
    },
    "git_log": {
        "name": "Git历史",
        "category": "git",
        "description": "查看提交历史（带作者/日期/消息）",
        "params": {"n": "显示N条", "path": "文件路径（可选）"},
        "icon": "📜",
    },
    "git_blame": {
        "name": "Git溯源",
        "category": "git",
        "description": "查看每行代码的作者和提交信息",
        "params": {"path": "文件路径", "start_line": "起始行", "end_line": "结束行"},
        "icon": "🔎",
    },

    # ── Shell tools ──
    "run_command": {
        "name": "执行命令",
        "category": "shell",
        "description": "执行shell命令/脚本并返回输出（带超时/沙箱）",
        "params": {"command": "命令", "workdir": "工作目录", "timeout": "超时秒数"},
        "icon": "⚡",
    },

    # ── Notification tools ──
    "send_email": {
        "name": "发送邮件",
        "category": "notify",
        "description": "发送邮件（SMTP）",
        "params": {"to": "收件人", "subject": "主题", "body": "正文"},
        "icon": "📧",
    },

    # ── Multimedia tools ──
    "pdf_parse": {
        "name": "PDF解析",
        "category": "multimedia",
        "description": "解析PDF文档内容（文本/表格/图片描述）",
        "params": {"path": "PDF文件路径", "pages": "页码范围（可选，如1-5）"},
        "icon": "📑",
    },
    "ocr_extract": {
        "name": "OCR识别",
        "category": "multimedia",
        "description": "图片文字识别OCR（中英文）",
        "params": {"path": "图片路径", "language": "识别语言 chi_sim|eng"},
        "icon": "👁",
    },

    # ── Data tools ──
    "csv_analyze": {
        "name": "CSV分析",
        "category": "data",
        "description": "分析CSV文件（统计/图表/异常检测）",
        "params": {"path": "CSV文件路径", "columns": "分析列（可选）"},
        "icon": "📈",
    },
    "json_transform": {
        "name": "JSON转换",
        "category": "data",
        "description": "JSON结构转换/过滤/合并/JMESPath查询",
        "params": {"input": "JSON输入", "expression": "JMESPath表达式或转换规则"},
        "icon": "🔄",
    },
    "excel_export": {
        "name": "Excel导出",
        "category": "data",
        "description": "导出数据到Excel/CSV（带格式/图表）",
        "params": {"data": "导出数据", "path": "输出路径", "format": "xlsx|csv"},
        "icon": "📥",
    },

    # ── Meta tools ──
    "snapshot": {
        "name": "状态快照",
        "category": "meta",
        "description": "保存/恢复完整智能体状态（回滚点）",
        "params": {"action": "save|restore|list", "name": "快照名称"},
        "icon": "📸",
    },
    "debate": {
        "name": "多智能体辩论",
        "category": "meta",
        "description": "多角色辩论决策（不单点判断）",
        "params": {"topic": "辩论主题", "roles": "参与角色列表", "rounds": "辩论轮数"},
        "icon": "🗣",
    },
    "self_evolve": {
        "name": "自我进化",
        "category": "meta",
        "description": "工具执行失败3次后LLM自动重写工具代码",
        "params": {"tool_name": "失败的工具名", "error_log": "错误日志"},
        "icon": "🧬",
    },
}

EXPERT_ROLES = {
    # ── IT (original) ──
    "full_stack_engineer": "全栈工程师 — Python/JS/React/SQL 全栈开发",
    "ui_designer": "UI 设计师 — 界面设计、原型、样式指南",
    "product_manager": "产品经理 — PRD、用户故事、路线图",
    "data_analyst": "数据分析师 — 分析报告、可视化、洞察",
    "marketing_specialist": "营销专家 — 营销计划、内容策略",
    "ai_researcher": "AI 研究员 — 算法模型、技术报告、论文",
    "devops_engineer": "DevOps 工程师 — 部署脚本、监控配置",
    "qa_engineer": "QA 工程师 — 测试计划、测试报告、Bug列表",

    # ── 环评专业 ──
    "eia_engineer": "环评工程师 — GB3095/3096/3838/3840 标准, 高斯模型, AERMOD, CALPUFF, 污染源核算, 防护距离",
    "air_quality_expert": "大气环境专家 — 气象数据分析, 扩散模型, AERSCREEN估算, 环境空气监测, PM2.5/PM10/O3/SO2/NOx/VOCs",
    "water_env_expert": "水环境专家 — 地表水/地下水评价, COD/BOD5/氨氮, 水质模型, HJ 2.3-2018, 水文地质参数",
    "noise_expert": "噪声控制专家 — GB3096-2008, 点/线/面声源, 隔声降噪, 厂界噪声预测, 交通噪声模型",
    "ecology_expert": "生态评价师 — 植被调查, 生物量估算, 生态红线, 水土保持, 景观生态学, HJ 19-2022",
    "env_monitoring_expert": "环境监测师 — 监测方案设计, 采样规范HJ/T 166, 实验室质控, 在线监测, 数据审核",
    "regulatory_expert": "法规合规师 — 产业政策, 环保法律法规, 排污许可, 总量控制, 三同时制度, 环境税",
    "safety_assessor": "安全评价师 — 危险源辨识HAZOP/LEC, 重大危险源, 事故后果模拟, 安全距离, AQ标准",
    "feasibility_analyst": "可行性研究员 — 市场分析, 技术方案比选, 投资估算, 财务评价NPV/IRR, 敏感性分析, 国民经济评价",
    "carbon_expert": "碳评估专家 — 碳排放核算IPCC, 碳达峰碳中和, CCER, 碳交易, 碳足迹LCA, 绿色建筑评价",

    # ── 科学计算 ──
    "math_modeler": "数学建模专家 — 微分方程/偏微分, 数值方法(FEM/FDM/FVM), 优化(线性/非线性/整数), 蒙特卡洛, 统计分析, MATLAB/NumPy/SciPy",
    "scientific_computing": "科学计算专家 — 高性能计算(HPC/MPI/OpenMP), CFD计算流体力学, FEA有限元, 分子动力学, 量子化学Gaussian/VASP, 并行算法",
    "gis_expert": "GIS地理信息专家 — ArcGIS/QGIS, 空间分析(缓冲区/叠加/插值), 遥感ENVI/ERDAS, 坐标转换, 地形分析DEM/DSM, GeoJSON/Shapefile/GeoDatabase",
    "process_engineer": "工艺流程专家 — PFD/P&ID, 物料衡算, 能量衡算, 化工单元操作, Aspen Plus/HYSYS, 设备选型, 管道仪表, 工艺安全HAZOP",
    "flowchart_designer": "流程图设计专家 — 工艺流程图PFD, 管道仪表图P&ID, 组织结构图, 数据流图DFD, UML, BPMN, Visio/draw.io/Mermaid/PlantUML",

    # ── 审批/评估/学术 ──
    "gov_reviewer": "政府审批专家 — 发改委立项, 环保局环评审批, 规划局用地规划许可, 建设局施工许可, 安监局安全审查, 审批流程, 申报材料, 补正通知",
    "third_party_evaluator": "第三方评估专家 — 独立环评/安评/能评, 专家评审会, 技术评估报告, 公众参与, 听证会, 质疑与答辩, 评估标准和规范",
    "university_professor": "高校教授 — 环境工程/化学工程/安全工程/生态学, 学术论文, 实验设计, 研究生指导, 基金申请, SCI/EI期刊, 学术伦理, 交叉学科",
    "translator_en_cn": "翻译专家 — 中英互译, 技术文档翻译, 标准规范翻译(GB/ISO/IEC), 论文翻译, 合同翻译, 专业术语准确, 保持原文格式和图表",
    "procurement_sales": "采购销售专家 — 设备采购(RFQ/RFP), 供应商评估, 招投标, 合同谈判, 成本分析TCO, 供应链管理, 进出口报关, 定价策略, 销售方案",

    # ── 行业工艺 ──
    "chemical_expert": "化工专家 — 石油化工/精细化工/煤化工, 催化裂化/加氢/重整/聚合, 反应工程, 分离工程(精馏/吸收/萃取/膜分离), 化工热力学, 化工安全(反应风险/热风险评估), 化工环保",
    "pharma_expert": "制药专家 — 化学合成药/生物制药/中药提取, GMP规范, 洁净车间(ISO 5-8), 原料药API/制剂, 发酵工艺, 层析分离, 冻干工艺, 制药废水(高COD/抗生素/毒性), 制药废气(VOCs/溶剂)",
    "smelting_expert": "冶炼专家 — 钢铁(高炉/转炉/电炉), 有色冶金(铜/铝/铅/锌), 烧结/球团, 焦化, 电解铝, 湿法冶金, 火法冶金, 冶炼废渣(高炉渣/钢渣/赤泥), 烟气脱硫脱硝, 重金属废水处理",
    "automotive_expert": "车辆工程专家 — 整车制造(冲压/焊装/涂装/总装), 发动机/变速箱, 新能源汽车(电池/电机/电控), 涂装VOCs治理, 磷化废水, 试车场噪声, 零部件供应链",
    "electronics_expert": "电子电器专家 — 半导体(晶圆/光刻/蚀刻/封装), PCB印制电路板, 电子组装SMT, 电镀(镀铜/镀金/镀镍), 面板LCD/OLED, 电子废水(含氟/含氰/重金属), 洁净车间FFU, 电子级化学品",
    "municipal_expert": "市政工程专家 — 供水工程(水厂/管网), 排水工程(雨污分流/泵站), 污水处理厂(A²O/MBR/SBR), 垃圾填埋/焚烧/餐厨处理, 道路桥梁隧道, 综合管廊, 海绵城市, 黑臭水体治理",
    "land_urban_expert": "土地住建专家 — 土地利用规划(总规/控规/修规), 征地拆迁, 土壤污染调查(GB36600), 建设用地审批, 规划选址, 城乡规划法, 土地管理法, 不动产登记, 海绵城市规划, 城市设计, 历史建筑保护",

    # ── 制造与能源 ──
    "machining_expert": "机械加工专家 — 车/铣/刨/磨/钻/镗/线切割, CNC五轴加工, 冲压/锻造/铸造/焊接, 表面处理(电镀/阳极氧化/喷涂/喷砂), 切削液/废乳化液处理, 热处理(淬火/回火/渗碳/氮化), GD&T形位公差, 三坐标测量",
    "equipment_expert": "设备工程专家 — 动设备(泵/压缩机/风机/搅拌/离心机), 静设备(塔/换热器/反应釜/储罐/锅炉), 设备选型/材质选择/防腐, 振动分析/故障诊断, 压力容器GB150/ASME VIII, 设备安装/试车/验收, 备品备件管理, TPM全员生产维护",
    "power_expert": "电力工程专家 — 火电(超临界/超超临界/CFB循环流化床), 燃气发电, 新能源(风电/光伏/光热), 输变电(变电站/输电线路/电磁环境), 生物质发电, 垃圾焚烧发电, 热电联产CHP, 电网接入, 电力平衡, DL/T标准",
    "thermodynamics_expert": "热力学专家 — 热力学三大定律, 蒸汽动力循环(朗肯/再热/回热), 燃气轮机循环(布雷顿), 制冷循环(压缩/吸收), 热泵, 㶲分析, 夹点技术, 换热网络优化, 余热回收(ORC有机朗肯循环/热电联产), 热力学数据库(NIST REFPROP)",
    "food_textile_expert": "食品纺织专家 — 食品: 酿造/乳制品/肉制品/饮料/粮油加工, HACCP/ISO22000, CIP清洗, 食品废水(高COD/高SS/高油脂), 锅炉烟气, 冷库制冷(氨/氟利昂)。纺织: 纺纱/织造/印染/后整理, 印染废水(高色度/高COD/含染料/助剂), 定型废气(含VOCs/颗粒物/臭味), 浆纱废水PVA回收",
    "traffic_expert": "交通工程专家 — 公路(高速/国道/省道/农村公路), 铁路(普速/高速/城际/地铁/轻轨), 机场(跑道/航站楼/航空噪声), 港口(码头/航道/疏浚/溢油), 交通噪声(FHWA/TNM模型), 交通安全(视距/标志标线/防护), 交通量预测(四阶段法), 交通规划(JTG B01/公路工程技术标准)",

    # ── 尖端制造 ──
    "aviation_expert": "航空专家 — 飞机制造(机身/机翼/航电/发动机), 航空发动机(涡轮风扇/涡桨/涡轴), 钛合金/复合材料(CFRP), 表面处理(阳极氧化/化学铣切/喷漆), 试车台噪声(120-140dB), 航空燃料(航煤储运/加油), 适航认证FAA/EASA/CAAC, 机场噪声(Ldn/DNL), 空中交通管理, 无人机/低空经济",
    "battery_expert": "电池制造专家 — 锂电池(磷酸铁锂LFP/三元NCM/固态), 钠离子电池, 前驱体(共沉淀/煅烧), 正极(LFP/NCM/LCO), 负极(石墨/硅碳), 电解液(LiPF₆/碳酸酯), 隔膜(PP/PE/涂覆), 化成分容, NMP回收, 含镍钴锰废水, 电极涂布废气, 注液手套箱, 电池回收(湿法/火法), GB/T 34014/动力蓄电池编码",

    # ── 贸易物流 ──
    "trade_expert": "外贸专家 — 国际贸易术语Incoterms(FOB/CIF/DDP), 进出口合同, 信用证L/C, 外汇结算, 关税/增值税/消费税, 原产地证, 贸易壁垒/反倾销, 国际仲裁, 外贸跟单, 跨境电商(B2B/B2C), 外贸英语函电, WTO规则, 区域自贸协定(RCEP/CPTPP)",
    "customs_expert": "海关专家 — HS编码归类, 海关估价, 关税征管, 通关一体化, AEO认证(海关信用), 加工贸易手册(电子账册), 保税区/综保区, 海关稽核查, 固体废物进口禁令, 濒危物种CITES公约, 危化品进出口(危险货物UN编号/包装类别), 海关行政处罚, 电子口岸",
    "logistics_expert": "运输物流专家 — 海运(集装箱/散货/滚装), 空运(IATA), 铁路(中欧班列/大陆桥), 公路运输(危化品ADR/危险货物), 多式联运, 仓储(普通/危化品/冷链), 物流园区, 危险货物运输(GB 6944分类/UN包装), LNG/液氨/液氯公路运输风险, 管道运输(原油/天然气), 物流碳排放",
    "metals_expert": "金属材料专家 — 钢铁(碳钢/合金钢/不锈钢/工具钢), 有色金属(铜/铝/钛/镁/镍/锌/铅), 稀有金属(钨/钼/稀土), 粉末冶金, 热处理(淬火/回火/退火/渗碳/氮化), 腐蚀与防护(阴极保护/涂层), 金相分析(SEM/EDS/XRD), 力学性能(拉伸/冲击/硬度/疲劳), 焊接冶金, 金属回收(废钢/再生铝)",
    "petroleum_expert": "石油及衍生品专家 — 原油(轻质/中质/重质/API度/硫含量), 常减压蒸馏, 催化裂化FCC, 加氢裂化/加氢精制, 延迟焦化, 重整(连续重整CCR), 烷基化, MTBE/烷基化油, 汽/柴/煤油调和, 润滑油基础油, 沥青/石油焦/硫磺, 储运(油罐/管道/码头/VOCs), 石化厂火炬, 炼化一体化, 原油价格(布伦特/WTI/迪拜)",
}

MCP_METHODS = {
    "build_code_graph": "构建代码图谱",
    "blast_radius": "影响分析",
    "get_callers": "查找调用者",
    "get_callees": "查找被调用者",
    "search_code": "搜索代码",
    "search_knowledge": "搜索知识库",
    "generate_code": "生成代码",
    "train_cell": "训练细胞",
    "absorb_codebase": "吸收代码库",
    "get_status": "系统状态",
}


def get_tool(tool_name: str) -> dict | None:
    return SYSTEM_TOOLS.get(tool_name)


def get_all_tools(category: str = "") -> list[dict]:
    tools = list(SYSTEM_TOOLS.values())
    if category:
        return [t for t in tools if t["category"] == category]
    return tools


def format_tool_list() -> str:
    """Format all available tools for display."""
    categories: dict[str, list[dict]] = {}
    for t in SYSTEM_TOOLS.values():
        cat = t["category"]
        categories.setdefault(cat, []).append(t)

    lines = ["## 🛠 System Tools & Roles", ""]
    for cat, tools in sorted(categories.items()):
        lines.append(f"### {cat}")
        for t in tools:
            lines.append(f"- {t['icon']} **{t['name']}** — {t['description']}")
        lines.append("")
    return "\n".join(lines)
