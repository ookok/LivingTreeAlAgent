"""
OntologyBuilder - 本体构建器

实现本体建模系统的第一层：本体构建

核心功能：
- 从非结构化数据中提取概念、属性、关系
- 构建本体模型
- 验证本体一致性
- 存储到图数据库

借鉴哲学本体论：对存在本质的研究

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import json
import os


class OntologyElementType(Enum):
    """本体元素类型"""
    CLASS = "class"
    PROPERTY = "property"
    RELATION = "relation"
    RULE = "rule"
    INSTANCE = "instance"


@dataclass
class OntologyClass:
    """
    本体类（概念）
    
    代表一个分类概念，如"项目"、"任务"、"资源"等。
    """
    name: str
    label: str = ""
    description: str = ""
    parent: Optional[str] = None  # 父类名称
    subclasses: List[str] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": "class",
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "parent": self.parent,
            "subclasses": self.subclasses,
            "properties": self.properties
        }


@dataclass
class OntologyProperty:
    """
    本体属性
    
    代表概念的特征，如"项目有预算"、"任务有优先级"等。
    """
    name: str
    label: str = ""
    description: str = ""
    domain: str = ""  # 定义域（所属类）
    range: str = ""   # 值域（值的类型）
    cardinality: str = "0..*"  # 基数（0到多）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": "property",
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "domain": self.domain,
            "range": self.range,
            "cardinality": self.cardinality
        }


@dataclass
class OntologyRelation:
    """
    本体关系
    
    代表概念之间的联系，如"项目包含任务"、"用户负责项目"等。
    """
    name: str
    label: str = ""
    description: str = ""
    source: str  # 源概念
    target: str  # 目标概念
    relation_type: str = "object"  # object / data
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": "relation",
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type
        }


@dataclass
class OntologyRule:
    """
    本体规则
    
    代表逻辑推理的约束，如"若任务优先级为高，则必须分配负责人"。
    """
    name: str
    label: str = ""
    description: str = ""
    antecedent: List[str] = field(default_factory=list)  # 前提条件
    consequent: str = ""  # 结论
    confidence: float = 1.0  # 置信度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": "rule",
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "antecedent": self.antecedent,
            "consequent": self.consequent,
            "confidence": self.confidence
        }


@dataclass
class OntologyInstance:
    """
    本体实例
    
    代表具体对象，如"项目A"、"任务B"等。
    """
    name: str
    class_name: str  # 所属类
    properties: Dict[str, Any] = field(default_factory=dict)
    relations: Dict[str, List[str]] = field(default_factory=dict)  # relation_name -> [targets]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": "instance",
            "name": self.name,
            "class_name": self.class_name,
            "properties": self.properties,
            "relations": self.relations
        }


class OntologyBuilder:
    """
    本体构建器
    
    功能：
    1. 从非结构化数据中提取概念、属性、关系
    2. 构建本体模型
    3. 验证本体一致性
    4. 存储到文件/数据库
    """
    
    def __init__(self, ontology_name: str = "livingtree"):
        self._logger = logger.bind(component="OntologyBuilder")
        
        # 本体名称
        self._ontology_name = ontology_name
        
        # 本体元素存储
        self._classes: Dict[str, OntologyClass] = {}
        self._properties: Dict[str, OntologyProperty] = {}
        self._relations: Dict[str, OntologyRelation] = {}
        self._rules: Dict[str, OntologyRule] = {}
        self._instances: Dict[str, OntologyInstance] = {}
        
        # 初始化默认本体
        self._init_default_ontology()
        
        self._logger.info(f"✅ OntologyBuilder 初始化完成: {ontology_name}")
    
    def _init_default_ontology(self):
        """初始化默认本体（核心概念）"""
        # === 核心类 ===
        # 项目类
        self.add_class(OntologyClass(
            name="Project",
            label="项目",
            description="一个有明确目标的工作单元",
            properties=["hasBudget", "hasConstraint", "hasStatus"]
        ))
        
        # 任务类
        self.add_class(OntologyClass(
            name="Task",
            label="任务",
            description="项目中的具体工作项",
            properties=["hasPriority", "hasStatus", "consumes"]
        ))
        
        # 资源类
        self.add_class(OntologyClass(
            name="Resource",
            label="资源",
            description="完成任务所需的资源",
            properties=["hasAmount", "hasUnit"]
        ))
        
        # 成本类
        self.add_class(OntologyClass(
            name="Cost",
            label="成本",
            description="执行任务或项目的消耗",
            properties=["hasAmount", "hasType"]
        ))
        
        # 约束类
        self.add_class(OntologyClass(
            name="Constraint",
            label="约束",
            description="项目或任务的限制条件",
            properties=["hasLimit", "hasType"]
        ))
        
        # === 子类 ===
        # 项目子类
        self.add_class(OntologyClass(
            name="SoftwareProject",
            label="软件项目",
            description="开发软件的项目",
            parent="Project"
        ))
        
        self.add_class(OntologyClass(
            name="EIAProject",
            label="环评项目",
            description="环境影响评价项目",
            parent="Project"
        ))
        
        # 任务子类
        self.add_class(OntologyClass(
            name="CodingTask",
            label="编码任务",
            description="编写代码的任务",
            parent="Task"
        ))
        
        self.add_class(OntologyClass(
            name="TestingTask",
            label="测试任务",
            description="软件测试任务",
            parent="Task"
        ))
        
        # 资源子类
        self.add_class(OntologyClass(
            name="Money",
            label="金钱",
            description="货币资源",
            parent="Resource"
        ))
        
        self.add_class(OntologyClass(
            name="Time",
            label="时间",
            description="时间资源",
            parent="Resource"
        ))
        
        self.add_class(OntologyClass(
            name="Compute",
            label="算力",
            description="计算资源",
            parent="Resource"
        ))
        
        # === 属性 ===
        self.add_property(OntologyProperty(
            name="hasBudget",
            label="有预算",
            description="项目的预算金额",
            domain="Project",
            range="Money"
        ))
        
        self.add_property(OntologyProperty(
            name="consumes",
            label="消耗",
            description="任务消耗的资源",
            domain="Task",
            range="Resource"
        ))
        
        self.add_property(OntologyProperty(
            name="hasConstraint",
            label="有约束",
            description="项目或任务的约束条件",
            domain="Project",
            range="Constraint"
        ))
        
        self.add_property(OntologyProperty(
            name="hasPriority",
            label="有优先级",
            description="任务的优先级",
            domain="Task",
            range="string"
        ))
        
        # === 关系 ===
        self.add_relation(OntologyRelation(
            name="contains",
            label="包含",
            description="项目包含任务",
            source="Project",
            target="Task"
        ))
        
        self.add_relation(OntologyRelation(
            name="belongsTo",
            label="属于",
            description="任务属于项目",
            source="Task",
            target="Project"
        ))
        
        self.add_relation(OntologyRelation(
            name="requires",
            label="需要",
            description="任务需要资源",
            source="Task",
            target="Resource"
        ))
        
        # === 规则 ===
        self.add_rule(OntologyRule(
            name="highRiskTask",
            label="高风险任务",
            description="任务消耗超过项目预算的50%则为高风险",
            antecedent=[
                "consumes(Task, Cost)",
                "hasBudget(Project, Budget)",
                "Cost > Budget * 0.5"
            ],
            consequent="highRisk(Task)",
            confidence=0.9
        ))
        
        self.add_rule(OntologyRule(
            name="costOverrunWarning",
            label="成本超支预警",
            description="项目已消耗超过预算的80%则触发预警",
            antecedent=[
                "totalConsumed(Project, Total)",
                "hasBudget(Project, Budget)",
                "Total > Budget * 0.8"
            ],
            consequent="costOverrunWarning(Project)",
            confidence=0.95
        ))
        
        self.add_rule(OntologyRule(
            name="highPriorityTask",
            label="高优先级任务",
            description="属于紧急项目且未完成的任务为高优先级",
            antecedent=[
                "belongsTo(Task, Project)",
                "isUrgent(Project)",
                "not(completed(Task))"
            ],
            consequent="highPriority(Task)",
            confidence=0.85
        ))
    
    def add_class(self, cls: OntologyClass):
        """添加类"""
        self._classes[cls.name] = cls
        
        # 更新父类的子类列表
        if cls.parent and cls.parent in self._classes:
            if cls.name not in self._classes[cls.parent].subclasses:
                self._classes[cls.parent].subclasses.append(cls.name)
        
        self._logger.debug(f"➕ 添加类: {cls.name}")
    
    def get_class(self, name: str) -> Optional[OntologyClass]:
        """获取类"""
        return self._classes.get(name)
    
    def add_property(self, prop: OntologyProperty):
        """添加属性"""
        self._properties[prop.name] = prop
        
        # 更新类的属性列表
        if prop.domain and prop.domain in self._classes:
            if prop.name not in self._classes[prop.domain].properties:
                self._classes[prop.domain].properties.append(prop.name)
        
        self._logger.debug(f"➕ 添加属性: {prop.name}")
    
    def get_property(self, name: str) -> Optional[OntologyProperty]:
        """获取属性"""
        return self._properties.get(name)
    
    def add_relation(self, relation: OntologyRelation):
        """添加关系"""
        self._relations[relation.name] = relation
        self._logger.debug(f"➕ 添加关系: {relation.name}")
    
    def get_relation(self, name: str) -> Optional[OntologyRelation]:
        """获取关系"""
        return self._relations.get(name)
    
    def add_rule(self, rule: OntologyRule):
        """添加规则"""
        self._rules[rule.name] = rule
        self._logger.debug(f"➕ 添加规则: {rule.name}")
    
    def get_rule(self, name: str) -> Optional[OntologyRule]:
        """获取规则"""
        return self._rules.get(name)
    
    def add_instance(self, instance: OntologyInstance):
        """添加实例"""
        self._instances[instance.name] = instance
        self._logger.debug(f"➕ 添加实例: {instance.name}")
    
    def get_instance(self, name: str) -> Optional[OntologyInstance]:
        """获取实例"""
        return self._instances.get(name)
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        从文本中提取本体元素（简化实现）
        
        Args:
            text: 文本内容
            
        Returns:
            提取的本体元素
        """
        extracted = {
            "classes": [],
            "properties": [],
            "relations": []
        }
        
        # 简单的关键词匹配提取
        class_keywords = ["项目", "任务", "资源", "成本", "约束", "用户"]
        property_keywords = ["预算", "优先级", "状态", "时间", "金额"]
        relation_keywords = ["包含", "属于", "需要", "负责"]
        
        for keyword in class_keywords:
            if keyword in text:
                extracted["classes"].append(keyword)
        
        for keyword in property_keywords:
            if keyword in text:
                extracted["properties"].append(keyword)
        
        for keyword in relation_keywords:
            if keyword in text:
                extracted["relations"].append(keyword)
        
        self._logger.info(f"🔍 从文本中提取了 {len(extracted['classes'])} 个类")
        return extracted
    
    def validate(self) -> List[str]:
        """
        验证本体一致性
        
        Returns:
            错误信息列表（空列表表示验证通过）
        """
        errors = []
        
        # 检查类的父类是否存在
        for cls in self._classes.values():
            if cls.parent and cls.parent not in self._classes:
                errors.append(f"类 {cls.name} 的父类 {cls.parent} 不存在")
        
        # 检查属性的定义域是否存在
        for prop in self._properties.values():
            if prop.domain and prop.domain not in self._classes:
                errors.append(f"属性 {prop.name} 的定义域 {prop.domain} 不存在")
        
        # 检查关系的源和目标是否存在
        for relation in self._relations.values():
            if relation.source not in self._classes:
                errors.append(f"关系 {relation.name} 的源 {relation.source} 不存在")
            if relation.target not in self._classes:
                errors.append(f"关系 {relation.name} 的目标 {relation.target} 不存在")
        
        if errors:
            self._logger.warning(f"❌ 本体验证失败: {len(errors)} 个错误")
        else:
            self._logger.info("✅ 本体验证通过")
        
        return errors
    
    def save_to_file(self, filepath: str):
        """
        保存本体到文件（JSON格式）
        
        Args:
            filepath: 文件路径
        """
        ontology_data = {
            "name": self._ontology_name,
            "classes": {name: cls.to_dict() for name, cls in self._classes.items()},
            "properties": {name: prop.to_dict() for name, prop in self._properties.items()},
            "relations": {name: rel.to_dict() for name, rel in self._relations.items()},
            "rules": {name: rule.to_dict() for name, rule in self._rules.items()},
            "instances": {name: inst.to_dict() for name, inst in self._instances.items()}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ontology_data, f, ensure_ascii=False, indent=2)
        
        self._logger.info(f"📥 本体已保存到: {filepath}")
    
    def load_from_file(self, filepath: str):
        """
        从文件加载本体
        
        Args:
            filepath: 文件路径
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            ontology_data = json.load(f)
        
        # 清空现有数据
        self._classes.clear()
        self._properties.clear()
        self._relations.clear()
        self._rules.clear()
        self._instances.clear()
        
        # 加载类
        for name, data in ontology_data.get("classes", {}).items():
            self.add_class(OntologyClass(
                name=data["name"],
                label=data.get("label", ""),
                description=data.get("description", ""),
                parent=data.get("parent"),
                subclasses=data.get("subclasses", []),
                properties=data.get("properties", [])
            ))
        
        # 加载属性
        for name, data in ontology_data.get("properties", {}).items():
            self.add_property(OntologyProperty(
                name=data["name"],
                label=data.get("label", ""),
                description=data.get("description", ""),
                domain=data.get("domain", ""),
                range=data.get("range", ""),
                cardinality=data.get("cardinality", "0..*")
            ))
        
        # 加载关系
        for name, data in ontology_data.get("relations", {}).items():
            self.add_relation(OntologyRelation(
                name=data["name"],
                label=data.get("label", ""),
                description=data.get("description", ""),
                source=data.get("source", ""),
                target=data.get("target", ""),
                relation_type=data.get("relation_type", "object")
            ))
        
        # 加载规则
        for name, data in ontology_data.get("rules", {}).items():
            self.add_rule(OntologyRule(
                name=data["name"],
                label=data.get("label", ""),
                description=data.get("description", ""),
                antecedent=data.get("antecedent", []),
                consequent=data.get("consequent", ""),
                confidence=data.get("confidence", 1.0)
            ))
        
        # 加载实例
        for name, data in ontology_data.get("instances", {}).items():
            self.add_instance(OntologyInstance(
                name=data["name"],
                class_name=data.get("class_name", ""),
                properties=data.get("properties", {}),
                relations=data.get("relations", {})
            ))
        
        self._logger.info(f"📤 本体已从文件加载: {filepath}")
    
    def get_stats(self) -> Dict[str, int]:
        """获取本体统计信息"""
        return {
            "classes": len(self._classes),
            "properties": len(self._properties),
            "relations": len(self._relations),
            "rules": len(self._rules),
            "instances": len(self._instances)
        }


# 创建全局实例
ontology_builder = OntologyBuilder()


def get_ontology_builder() -> OntologyBuilder:
    """获取本体构建器实例"""
    return ontology_builder


# 测试函数
async def test_ontology_builder():
    """测试本体构建器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 OntologyBuilder")
    print("=" * 60)
    
    builder = OntologyBuilder()
    
    # 1. 检查初始化的本体
    print("\n[1] 检查初始化本体...")
    stats = builder.get_stats()
    print(f"    ✓ 类数量: {stats['classes']}")
    print(f"    ✓ 属性数量: {stats['properties']}")
    print(f"    ✓ 关系数量: {stats['relations']}")
    print(f"    ✓ 规则数量: {stats['rules']}")
    
    # 2. 添加新类
    print("\n[2] 添加新类...")
    builder.add_class(OntologyClass(
        name="ResearchProject",
        label="研究项目",
        description="学术研究项目",
        parent="Project"
    ))
    print(f"    ✓ 添加类: ResearchProject")
    
    # 3. 验证本体
    print("\n[3] 验证本体...")
    errors = builder.validate()
    print(f"    ✓ 验证结果: {'通过' if not errors else f'失败 ({len(errors)}个错误)'}")
    
    # 4. 从文本提取
    print("\n[4] 从文本提取本体...")
    text = "项目A包含三个任务：编码、测试和文档。项目预算为10000元。"
    extracted = builder.extract_from_text(text)
    print(f"    ✓ 提取的类: {extracted['classes']}")
    print(f"    ✓ 提取的属性: {extracted['properties']}")
    
    # 5. 添加实例
    print("\n[5] 添加实例...")
    builder.add_instance(OntologyInstance(
        name="ProjectA",
        class_name="SoftwareProject",
        properties={"hasBudget": 10000, "hasStatus": "active"},
        relations={"contains": ["Task1", "Task2"]}
    ))
    print(f"    ✓ 添加实例: ProjectA")
    
    # 6. 保存本体
    print("\n[6] 保存本体...")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        builder.save_to_file(f.name)
        print(f"    ✓ 本体已保存到临时文件")
    
    # 7. 获取规则
    print("\n[7] 获取规则...")
    rule = builder.get_rule("highRiskTask")
    print(f"    ✓ 规则名称: {rule.name}")
    print(f"    ✓ 规则描述: {rule.description}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ontology_builder())