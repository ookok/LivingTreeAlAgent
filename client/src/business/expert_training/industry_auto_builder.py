"""
行业训练体系自动构建器 (Industry Auto Builder)

实现配置驱动的行业训练体系构建：
1. 通用行业数据模板
2. JSON/YAML配置文件支持
3. 自动注册机制
4. 无需编码即可扩展新行业

核心原则：配置驱动 > 代码编写
"""

import json
import yaml
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class IndustryConfig:
    """行业配置类"""
    industry_name: str
    industry_code: str
    description: str = ""
    parent_industry: Optional[str] = None  # 继承父行业
    
    # 术语词典配置
    terms: Dict[str, List[str]] = field(default_factory=dict)
    
    # 标准/规范配置
    standards: Dict[str, str] = field(default_factory=dict)
    
    # 训练样本配置
    training_samples: List[Dict[str, Any]] = field(default_factory=list)
    
    # 思维链模板配置
    reasoning_templates: Dict[str, List[str]] = field(default_factory=dict)
    
    # 任务定义配置
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    
    # 评估指标配置
    evaluation_metrics: List[str] = field(default_factory=list)
    
    # 关联的工具/模型
    tools: List[str] = field(default_factory=list)


@dataclass
class IndustryTemplate:
    """行业模板"""
    template_name: str
    description: str
    base_config: IndustryConfig
    customization_points: List[str] = field(default_factory=list)


class IndustryAutoBuilder:
    """
    行业训练体系自动构建器
    
    功能：
    1. 从配置文件自动加载行业定义
    2. 提供通用行业模板
    3. 支持行业继承机制
    4. 自动注册到训练系统
    
    使用方式：
    1. 创建YAML/JSON配置文件定义行业
    2. 调用 load_industry() 加载
    3. 调用 register_to_trainer() 注册到训练管理器
    """
    
    def __init__(self):
        # 已加载的行业配置
        self.industries: Dict[str, IndustryConfig] = {}
        
        # 行业模板库
        self.templates: Dict[str, IndustryTemplate] = {}
        
        # 注册的训练管理器
        self.trainer = None
        
        # 默认行业模板
        self._register_default_templates()
        
        print("[IndustryAutoBuilder] 初始化完成")
    
    def _register_default_templates(self):
        """注册默认行业模板"""
        # 通用工业模板
        general_industry = IndustryConfig(
            industry_name="通用工业",
            industry_code="general",
            description="适用于所有工业领域的通用配置",
            terms={
                "设备类型": [],
                "材料": [],
                "标准": [],
                "参数": []
            },
            standards={},
            reasoning_templates={
                "selection": [
                    "分析需求条件",
                    "筛选符合条件的选项",
                    "评估各选项优缺点",
                    "综合比较得出结论"
                ],
                "diagnosis": [
                    "收集现象信息",
                    "列举可能原因",
                    "逐一排除不可能选项",
                    "确定根本原因",
                    "提出解决方案"
                ],
                "calculation": [
                    "明确计算目标",
                    "收集输入参数",
                    "选择合适公式/模型",
                    "执行计算",
                    "验证结果合理性"
                ]
            },
            tasks=[
                {
                    "task_id": "selection",
                    "name": "选型任务",
                    "description": "根据条件选择合适的设备/材料",
                    "stage": 2,
                    "difficulty": 2
                },
                {
                    "task_id": "diagnosis",
                    "name": "故障诊断",
                    "description": "分析故障原因并提出解决方案",
                    "stage": 2,
                    "difficulty": 3
                },
                {
                    "task_id": "calculation",
                    "name": "工程计算",
                    "description": "进行工程相关计算",
                    "stage": 2,
                    "difficulty": 3
                }
            ],
            evaluation_metrics=["accuracy", "reasoning_correctness", "completion_rate"]
        )
        
        self.templates["general_industry"] = IndustryTemplate(
            template_name="通用工业模板",
            description="适用于所有工业领域的基础模板",
            base_config=general_industry,
            customization_points=["terms", "standards", "training_samples", "tasks"]
        )
        
        # 流程工业模板
        process_industry = IndustryConfig(
            industry_name="流程工业",
            industry_code="process",
            description="适用于化工、能源等流程工业",
            parent_industry="general",
            terms={
                "工艺参数": ["温度", "压力", "流量", "浓度"],
                "设备类型": ["反应器", "换热器", "泵", "压缩机"],
                "环保设施": ["废气处理", "废水处理", "脱硫脱硝"]
            },
            reasoning_templates={
                "process_design": [
                    "分析工艺需求",
                    "选择工艺流程",
                    "计算物料平衡",
                    "设计设备参数",
                    "评估安全风险"
                ]
            },
            tasks=[
                {
                    "task_id": "process_design",
                    "name": "工艺设计",
                    "description": "设计工艺流程和设备参数",
                    "stage": 3,
                    "difficulty": 4
                }
            ]
        )
        
        self.templates["process_industry"] = IndustryTemplate(
            template_name="流程工业模板",
            description="适用于化工、能源等流程工业",
            base_config=process_industry,
            customization_points=["terms", "standards", "training_samples"]
        )
        
        print(f"[IndustryAutoBuilder] 已注册 {len(self.templates)} 个行业模板")
    
    def load_industry_from_file(self, filepath: str) -> IndustryConfig:
        """
        从配置文件加载行业定义
        
        支持格式：JSON、YAML
        
        Args:
            filepath: 配置文件路径
            
        Returns:
            IndustryConfig 对象
        """
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        # 读取文件
        content = path.read_text(encoding='utf-8')
        
        # 根据扩展名解析
        if filepath.endswith('.yaml') or filepath.endswith('.yml'):
            data = yaml.safe_load(content)
        elif filepath.endswith('.json'):
            data = json.loads(content)
        else:
            raise ValueError("不支持的文件格式，仅支持 JSON 和 YAML")
        
        # 创建行业配置
        config = IndustryConfig(
            industry_name=data["industry_name"],
            industry_code=data.get("industry_code", data["industry_name"].lower()),
            description=data.get("description", ""),
            parent_industry=data.get("parent_industry"),
            terms=data.get("terms", {}),
            standards=data.get("standards", {}),
            training_samples=data.get("training_samples", []),
            reasoning_templates=data.get("reasoning_templates", {}),
            tasks=data.get("tasks", []),
            evaluation_metrics=data.get("evaluation_metrics", []),
            tools=data.get("tools", [])
        )
        
        # 如果有父行业，继承配置
        if config.parent_industry and config.parent_industry in self.industries:
            self._inherit_from_parent(config)
        
        # 保存到已加载列表
        self.industries[config.industry_code] = config
        
        print(f"[IndustryAutoBuilder] 已加载行业: {config.industry_name}")
        return config
    
    def _inherit_from_parent(self, config: IndustryConfig):
        """继承父行业配置"""
        parent = self.industries[config.parent_industry]
        
        # 继承术语
        for term_type, terms in parent.terms.items():
            if term_type not in config.terms:
                config.terms[term_type] = []
            config.terms[term_type].extend(terms)
        
        # 继承标准
        config.standards.update(parent.standards)
        
        # 继承思维链模板
        for task_type, steps in parent.reasoning_templates.items():
            if task_type not in config.reasoning_templates:
                config.reasoning_templates[task_type] = steps
        
        # 继承任务
        config.tasks.extend(parent.tasks)
        
        print(f"[IndustryAutoBuilder] {config.industry_name} 已继承 {parent.industry_name} 的配置")
    
    def create_industry_from_template(self, template_name: str, 
                                     custom_config: Dict[str, Any]) -> IndustryConfig:
        """
        从模板创建行业配置
        
        Args:
            template_name: 模板名称
            custom_config: 自定义配置
            
        Returns:
            自定义后的行业配置
        """
        if template_name not in self.templates:
            raise ValueError(f"模板不存在: {template_name}")
        
        template = self.templates[template_name]
        base_config = template.base_config
        
        # 创建新配置（深拷贝）
        config = IndustryConfig(
            industry_name=custom_config.get("industry_name", base_config.industry_name),
            industry_code=custom_config.get("industry_code", base_config.industry_code),
            description=custom_config.get("description", base_config.description),
            parent_industry=custom_config.get("parent_industry", base_config.parent_industry),
            terms=dict(base_config.terms),
            standards=dict(base_config.standards),
            training_samples=list(base_config.training_samples),
            reasoning_templates=dict(base_config.reasoning_templates),
            tasks=list(base_config.tasks),
            evaluation_metrics=list(base_config.evaluation_metrics),
            tools=list(base_config.tools)
        )
        
        # 应用自定义配置
        if "terms" in custom_config:
            config.terms.update(custom_config["terms"])
        
        if "standards" in custom_config:
            config.standards.update(custom_config["standards"])
        
        if "training_samples" in custom_config:
            config.training_samples.extend(custom_config["training_samples"])
        
        if "reasoning_templates" in custom_config:
            config.reasoning_templates.update(custom_config["reasoning_templates"])
        
        if "tasks" in custom_config:
            config.tasks.extend(custom_config["tasks"])
        
        if "evaluation_metrics" in custom_config:
            config.evaluation_metrics.extend(custom_config["evaluation_metrics"])
        
        # 保存
        self.industries[config.industry_code] = config
        
        print(f"[IndustryAutoBuilder] 从模板 {template_name} 创建行业: {config.industry_name}")
        return config
    
    def register_to_trainer(self, trainer, industry_code: str):
        """
        将行业配置注册到训练管理器
        
        Args:
            trainer: TrainingManager实例
            industry_code: 行业代码
        """
        if industry_code not in self.industries:
            raise ValueError(f"行业未加载: {industry_code}")
        
        config = self.industries[industry_code]
        
        # 1. 添加术语到数据构造器
        for term_type, terms in config.terms.items():
            for term in terms:
                trainer.data_constructor.governance.load_synonym_table(config.industry_name, {term: term})
        
        # 2. 添加训练样本
        for sample in config.training_samples:
            trainer.data_constructor.add_entry(
                instruction=sample["instruction"],
                input_data=sample["input"],
                output=sample["output"],
                reasoning=sample.get("reasoning"),
                uncertainty=sample.get("uncertainty"),
                task_type=sample.get("task_type", "general"),
                stage=sample.get("stage", 2),
                source=f"industry_{industry_code}"
            )
        
        # 3. 添加思维链模板
        for task_type, steps in config.reasoning_templates.items():
            trainer.reasoning_builder.add_domain_rules(config.industry_name, [
                {"condition": task_type, "conclusion": steps}
            ])
        
        # 4. 添加任务
        for task in config.tasks:
            trainer.task_framework.add_task(
                task_id=task["task_id"],
                name=task["name"],
                description=task["description"],
                stage=task["stage"],
                difficulty=task["difficulty"]
            )
        
        # 5. 设置目标行业
        trainer.config.target_industry = config.industry_name
        
        print(f"[IndustryAutoBuilder] 已将 {config.industry_name} 注册到训练管理器")
    
    def export_industry_config(self, industry_code: str, filepath: str):
        """
        导出行业配置为文件
        
        Args:
            industry_code: 行业代码
            filepath: 输出文件路径
        """
        if industry_code not in self.industries:
            raise ValueError(f"行业不存在: {industry_code}")
        
        config = self.industries[industry_code]
        
        data = {
            "industry_name": config.industry_name,
            "industry_code": config.industry_code,
            "description": config.description,
            "parent_industry": config.parent_industry,
            "terms": config.terms,
            "standards": config.standards,
            "training_samples": config.training_samples,
            "reasoning_templates": config.reasoning_templates,
            "tasks": config.tasks,
            "evaluation_metrics": config.evaluation_metrics,
            "tools": config.tools
        }
        
        path = Path(filepath)
        
        if filepath.endswith('.yaml') or filepath.endswith('.yml'):
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, indent=2)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[IndustryAutoBuilder] 行业配置已导出到: {filepath}")
    
    def get_industry_config(self, industry_code: str) -> Optional[IndustryConfig]:
        """获取已加载的行业配置"""
        return self.industries.get(industry_code)
    
    def list_industries(self) -> List[str]:
        """列出已加载的行业"""
        return list(self.industries.keys())
    
    def list_templates(self) -> List[str]:
        """列出可用模板"""
        return list(self.templates.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "loaded_industries": len(self.industries),
            "available_templates": len(self.templates),
            "industries": self.list_industries(),
            "templates": self.list_templates()
        }


def create_industry_auto_builder() -> IndustryAutoBuilder:
    """创建行业自动构建器实例"""
    return IndustryAutoBuilder()


# 示例配置文件内容
EXAMPLE_CONFIG = """
# 行业配置示例 (YAML格式)
industry_name: "食品加工"
industry_code: "food_processing"
description: "食品加工行业专家训练配置"
parent_industry: "process"  # 继承流程工业模板

terms:
  食品类别: ["乳制品", "肉制品", "烘焙食品", "饮料"]
  工艺类型: ["灭菌", "冷冻", "干燥", "发酵"]
  质量标准: ["GB 2760", "GB 2762", "GB 2763"]

standards:
  GB 2760-2021: "食品安全国家标准 食品添加剂使用标准"
  GB 2762-2022: "食品安全国家标准 食品中污染物限量"
  GB 2763-2021: "食品安全国家标准 食品中农药最大残留限量"

training_samples:
  - instruction: "分析食品加工项目的污染物排放"
    input: "项目：新建乳制品加工厂，日处理鲜奶100吨，采用巴氏杀菌工艺"
    output: "主要污染源包括：清洗废水（COD、BOD）、锅炉废气（颗粒物、SO2）、包装废弃物。需执行GB 8978-1996污水综合排放标准。"
    reasoning:
      - "1. 分析生产工艺：巴氏杀菌需要蒸汽锅炉"
      - "2. 清洗工序产生大量清洗废水"
      - "3. 锅炉燃烧产生废气"
      - "4. 包装材料产生固体废弃物"
    uncertainty: "需确认具体工艺参数和废水处理方案。"
    task_type: "pollutant_identification"
    stage: 2

reasoning_templates:
  food_safety:
    - "确认产品类别和适用标准"
    - "分析原料和加工过程"
    - "识别潜在食品安全风险"
    - "制定控制措施"

tasks:
  - task_id: "food_safety_assessment"
    name: "食品安全评估"
    description: "评估食品加工项目的食品安全风险"
    stage: 3
    difficulty: 4

evaluation_metrics:
  - "standard_compliance"
  - "risk_identification_rate"

tools:
  - "haccp_analysis"
"""


__all__ = [
    "IndustryAutoBuilder",
    "IndustryConfig",
    "IndustryTemplate",
    "create_industry_auto_builder",
    "EXAMPLE_CONFIG"
]