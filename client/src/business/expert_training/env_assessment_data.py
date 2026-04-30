"""
环评行业数据模块 (Environmental Impact Assessment Data)

专为环评行业定制的训练数据和知识：
1. 环评行业术语词典
2. 环评专用训练样本
3. 环评思维链模板
4. 环评任务定义

核心内容覆盖：
- 环境现状调查
- 污染源识别
- 环境影响预测
- 环保措施论证
- 公众参与
- 环评报告编制
"""

from typing import Dict, List, Optional, Any, Tuple


# ==================== 环评行业术语词典 ====================

EIA_TERMS = {
    "环境要素": [
        "大气环境", "水环境", "地下水环境", "声环境", "土壤环境",
        "生态环境", "固体废物", "环境风险"
    ],
    "评价等级": [
        "一级评价", "二级评价", "三级评价", "简单分析"
    ],
    "评价标准": [
        "环境空气质量标准", "地表水环境质量标准", "地下水质量标准",
        "声环境质量标准", "土壤环境质量标准", "大气污染物综合排放标准",
        "污水综合排放标准", "工业企业厂界环境噪声排放标准"
    ],
    "污染源类型": [
        "废气污染源", "废水污染源", "噪声污染源", "固废污染源",
        "工艺废气", "无组织排放", "生活污水", "生产废水"
    ],
    "预测模型": [
        "AERMOD", "CALPUFF", "ADMS", "SWMM", "MIKE", "QUAL2K", "高斯模型"
    ],
    "环保措施": [
        "废气治理", "废水处理", "噪声控制", "固废处置",
        "脱硫脱硝", "除尘设施", "污水处理站", "隔声屏障"
    ],
    "环境敏感区": [
        "自然保护区", "风景名胜区", "饮用水水源保护区",
        "基本农田保护区", "文物保护单位", "生态红线区域"
    ],
    "环评文件类型": [
        "环境影响报告书", "环境影响报告表", "环境影响登记表"
    ]
}


# ==================== 环评标准号与标准名称映射 ====================

EIA_STANDARDS = {
    "GB 3095-2012": "环境空气质量标准",
    "GB 3838-2002": "地表水环境质量标准",
    "GB/T 14848-2017": "地下水质量标准",
    "GB 3096-2008": "声环境质量标准",
    "GB 15618-2018": "土壤环境质量 农用地土壤污染风险管控标准",
    "GB 36600-2018": "土壤环境质量 建设用地土壤污染风险管控标准",
    "GB 16297-1996": "大气污染物综合排放标准",
    "GB 8978-1996": "污水综合排放标准",
    "GB 12348-2008": "工业企业厂界环境噪声排放标准",
    "GB 18597-2001": "危险废物贮存污染控制标准",
    "GB 18599-2001": "一般工业固体废物贮存和填埋污染控制标准",
    "HJ 2.1-2016": "环境影响评价技术导则 总纲",
    "HJ 2.2-2018": "环境影响评价技术导则 大气环境",
    "HJ 2.3-2018": "环境影响评价技术导则 地表水环境",
    "HJ 610-2016": "环境影响评价技术导则 地下水环境",
    "HJ 2.4-2009": "环境影响评价技术导则 声环境",
    "HJ 964-2018": "环境影响评价技术导则 土壤环境",
    "HJ 19-2022": "环境影响评价技术导则 生态影响",
    "HJ 169-2018": "建设项目环境风险评价技术导则"
}


# ==================== 环评训练样本 ====================

EIA_TRAINING_SAMPLES = [
    {
        "instruction": "分析建设项目概况，识别环境影响评价工作等级",
        "input": "项目名称：年产10万吨化工原料生产线建设项目\n项目性质：新建\n行业类别：化学原料和化学制品制造业\n占地面积：50亩\n总投资：5亿元\n地理位置：位于省级经济开发区内，周边500米内有村庄",
        "output": "根据HJ 2.1-2016《环境影响评价技术导则 总纲》，结合项目规模、行业类别和周边环境敏感程度，建议开展二级评价。重点关注大气环境、水环境和环境风险影响。",
        "reasoning": [
            "1. 项目规模：年产10万吨，属于中型化工项目",
            "2. 行业类别：化学原料制造业，属于重污染行业",
            "3. 周边敏感点：500米内有村庄，属于环境敏感区",
            "4. 根据导则，中型项目+敏感区 → 二级评价",
            "5. 重点评价要素：大气（工艺废气）、水（生产废水）、风险（化学品泄漏）"
        ],
        "uncertainty": "需进一步确认项目具体工艺路线和污染物排放清单，以确定准确评价等级。",
        "task_type": "evaluation_level",
        "domain": "环评"
    },
    {
        "instruction": "识别建设项目的主要污染源和污染物",
        "input": "项目：新建汽车零部件喷漆生产线\n主要工艺：钣金加工→表面处理→喷漆→烘干→装配\n使用涂料：溶剂型涂料，含二甲苯、乙酸乙酯",
        "output": "主要污染源及污染物识别如下：\n\n**废气污染源：**\n- 喷漆工序：颗粒物、二甲苯、乙酸乙酯、VOCs\n- 烘干工序：VOCs、颗粒物\n- 表面处理：酸雾（硫酸雾、盐酸雾）\n\n**废水污染源：**\n- 表面处理废水：pH、SS、COD、重金属（锌、铬）\n- 清洗废水：COD、BOD、SS\n\n**固体废物：**\n- 漆渣（危险废物，HW12）\n- 废酸液（危险废物，HW34）\n- 一般工业固体废物",
        "reasoning": [
            "1. 喷漆工序使用溶剂型涂料 → 产生VOCs和颗粒物",
            "2. 烘干过程溶剂挥发 → VOCs排放",
            "3. 表面处理使用酸碱 → 酸雾和重金属废水",
            "4. 漆渣属于危险废物，需按HW12管理",
            "5. 废酸液属于HW34类危险废物"
        ],
        "uncertainty": "需确认涂料具体成分和用量，以及表面处理工艺的详细流程。",
        "task_type": "pollutant_identification",
        "domain": "环评"
    },
    {
        "instruction": "进行大气环境影响预测分析",
        "input": "项目废气排放：SO₂ 50kg/h，NOₓ 30kg/h，颗粒物 20kg/h\n排放高度：30m\n排气筒直径：1.5m\n所在区域：平原地区，年主导风向：东南风",
        "output": "根据HJ 2.2-2018《环境影响评价技术导则 大气环境》，建议采用AERMOD模型进行预测。预测内容包括正常排放情况下各污染物的小时/日均/年均浓度分布、最大落地浓度及出现位置、对周边敏感点的影响、非正常排放工况的环境影响。预测结果表明，各污染物浓度均满足GB 3095-2012二级标准要求。",
        "reasoning": [
            "1. 项目位于平原地区 → 选用AERMOD模型",
            "2. 排放高度30m，属于中高架源",
            "3. 根据排放速率计算最大落地浓度",
            "4. 对比GB 3095-2012二级标准进行达标分析",
            "5. 需关注非正常排放工况"
        ],
        "uncertainty": "预测结果基于估算的排放参数，实际影响需根据监测数据验证。",
        "task_type": "atmospheric_prediction",
        "domain": "环评"
    },
    {
        "instruction": "论证环保措施的技术经济可行性",
        "input": "项目废气：VOCs排放量约100kg/h，要求排放浓度达标（GB 16297-1996）\n可选方案：A. 活性炭吸附+催化燃烧（RCO） B. 沸石转轮+催化燃烧 C. 直接燃烧（TO）",
        "output": "推荐采用方案B（沸石转轮+催化燃烧）。理由：沸石转轮适合大风量低浓度VOCs处理，浓缩后再进行催化燃烧，能耗较低；RCO适合中小风量，TO能耗高。方案B处理效率高（≥98%），运行成本适中，满足达标要求。",
        "reasoning": [
            "1. 分析各方案技术特点：A适合中小风量，B适合大风量低浓度，C能耗高",
            "2. 项目VOCs排放属于大风量低浓度 → B方案更合适",
            "3. 处理效率要求：需达到98%以上，B方案可满足",
            "4. 经济分析：B方案初期投资较高但运行成本低",
            "5. 综合技术经济比选 → 推荐B方案"
        ],
        "uncertainty": "需进一步核算各方案的投资和运行成本数据。",
        "task_type": "measure_argumentation",
        "domain": "环评"
    },
    {
        "instruction": "分析建设项目的环境风险",
        "input": "项目：化工原料生产项目\n涉及危险化学品：甲醇、甲苯、硫酸\n储罐容量：甲醇500m³，甲苯300m³\n周边环境：东侧500m有河流（饮用水水源保护区）",
        "output": "环境风险评价结论：\n\n**风险识别：**\n- 重大危险源：甲醇储罐（500m³）、甲苯储罐（300m³）\n- 风险类型：泄漏、火灾、爆炸\n- 敏感目标：东侧500m河流为饮用水水源保护区\n\n**风险预测：**\n- 甲醇泄漏后可能进入河流，影响饮用水安全\n- 火灾产生的有毒烟气可能影响周边环境\n\n**风险防范措施：**\n- 储罐区设置围堰和应急池\n- 配备泄漏检测和报警系统\n- 制定应急预案，定期演练\n\n**结论：** 在采取有效风险防范措施后，项目环境风险可接受。",
        "reasoning": [
            "1. 根据HJ 169-2018识别重大危险源",
            "2. 分析可能发生的风险事故类型",
            "3. 评估对周边敏感目标的影响",
            "4. 制定针对性的风险防范措施",
            "5. 综合判断风险是否可接受"
        ],
        "uncertainty": "风险预测基于模拟计算，实际风险需通过应急预案演练验证。",
        "task_type": "risk_assessment",
        "domain": "环评"
    }
]


# ==================== 环评思维链模板 ====================

EIA_REASONING_TEMPLATES = {
    "evaluation_level": [
        "分析项目规模和行业类别",
        "识别周边环境敏感点",
        "对照相应技术导则确定评价等级",
        "明确重点评价要素"
    ],
    "pollutant_identification": [
        "梳理项目生产工艺流程图",
        "分析每个工序的污染物产生环节",
        "识别污染物种类和形态",
        "确定污染物排放方式（有组织/无组织）",
        "分类统计污染物产生量和排放量"
    ],
    "impact_prediction": [
        "选择适用的预测模型",
        "确定预测参数（排放源强、气象条件等）",
        "设置预测情景（正常排放、非正常排放）",
        "计算环境影响范围和程度",
        "对比评价标准进行达标分析"
    ],
    "measure_argumentation": [
        "梳理可行的环保治理技术",
        "从技术可行性角度分析各方案",
        "从经济合理性角度分析各方案",
        "综合比选确定推荐方案",
        "论证推荐方案的达标可靠性"
    ],
    "risk_assessment": [
        "识别重大危险源",
        "分析可能发生的风险事故类型",
        "评估风险事故对环境的影响",
        "制定风险防范措施和应急预案",
        "综合判断环境风险是否可接受"
    ]
}


# ==================== 环评任务定义 ====================

EIA_TASKS = [
    {
        "task_id": "eia_evaluation_level",
        "name": "评价等级判定",
        "description": "根据项目规模、行业类别和周边环境敏感程度，确定环评工作等级",
        "stage": 2,
        "difficulty": 2,
        "examples": ["确定化工项目的环评等级", "判定新建工厂的评价级别"]
    },
    {
        "task_id": "eia_pollutant_identification",
        "name": "污染源识别",
        "description": "识别项目生产过程中产生的各类污染源和污染物",
        "stage": 2,
        "difficulty": 2,
        "examples": ["识别喷漆生产线的污染源", "分析化工项目的污染物排放"]
    },
    {
        "task_id": "eia_impact_prediction",
        "name": "环境影响预测",
        "description": "采用合适模型预测项目对各环境要素的影响",
        "stage": 3,
        "difficulty": 4,
        "examples": ["大气环境影响预测", "地表水环境影响预测"]
    },
    {
        "task_id": "eia_measure_argumentation",
        "name": "环保措施论证",
        "description": "论证环保治理措施的技术经济可行性",
        "stage": 3,
        "difficulty": 4,
        "examples": ["废气处理方案比选", "污水处理工艺论证"]
    },
    {
        "task_id": "eia_risk_assessment",
        "name": "环境风险评价",
        "description": "识别重大危险源，评估环境风险并提出防范措施",
        "stage": 3,
        "difficulty": 5,
        "examples": ["化工项目风险评价", "危化品储罐风险分析"]
    },
    {
        "task_id": "eia_report_generation",
        "name": "环评报告编制",
        "description": "编制完整的环境影响评价文件",
        "stage": 4,
        "difficulty": 5,
        "examples": ["编制环境影响报告书", "编写环境影响报告表"]
    }
]


# ==================== 工具函数 ====================

def get_eia_terms() -> Dict[str, List[str]]:
    """获取环评行业术语词典"""
    return EIA_TERMS


def get_eia_standards() -> Dict[str, str]:
    """获取环评标准号映射"""
    return EIA_STANDARDS


def get_eia_training_samples() -> List[Dict[str, Any]]:
    """获取环评训练样本"""
    return EIA_TRAINING_SAMPLES


def get_eia_reasoning_templates() -> Dict[str, List[str]]:
    """获取环评思维链模板"""
    return EIA_REASONING_TEMPLATES


def get_eia_tasks() -> List[Dict[str, Any]]:
    """获取环评任务定义"""
    return EIA_TASKS


def add_eia_data_to_trainer(trainer):
    """
    将环评数据添加到训练管理器中
    
    Args:
        trainer: TrainingManager实例
    """
    # 添加环评行业术语到数据构造器
    for term_type, terms in EIA_TERMS.items():
        for term in terms:
            trainer.data_constructor.governance.load_synonym_table("环评", {term: term})
    
    # 添加环评训练样本
    for sample in EIA_TRAINING_SAMPLES:
        trainer.data_constructor.add_entry(
            instruction=sample["instruction"],
            input_data=sample["input"],
            output=sample["output"],
            reasoning=sample.get("reasoning"),
            uncertainty=sample.get("uncertainty"),
            task_type=sample["task_type"],
            stage=sample.get("stage", 2),
            source="eia_module"
        )
    
    # 添加环评任务到任务框架
    for task in EIA_TASKS:
        trainer.task_framework.add_task(
            task_id=task["task_id"],
            name=task["name"],
            description=task["description"],
            stage=task["stage"],
            difficulty=task["difficulty"]
        )
    
    print(f"[EIA Module] 已添加 {len(EIA_TRAINING_SAMPLES)} 条环评训练样本")
    print(f"[EIA Module] 已添加 {len(EIA_TASKS)} 个环评任务")


__all__ = [
    "EIA_TERMS",
    "EIA_STANDARDS",
    "EIA_TRAINING_SAMPLES",
    "EIA_REASONING_TEMPLATES",
    "EIA_TASKS",
    "get_eia_terms",
    "get_eia_standards",
    "get_eia_training_samples",
    "get_eia_reasoning_templates",
    "get_eia_tasks",
    "add_eia_data_to_trainer"
]