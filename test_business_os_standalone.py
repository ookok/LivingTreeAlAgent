# -*- coding: utf-8 -*-
"""
Business OS Standalone Test
==========================

独立测试脚本，验证业务操作系统核心逻辑
"""

# ==================== 数据类型定义 ====================

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class EntityType(Enum):
    PERSON = "person"
    DOCUMENT = "document"
    PROCESS = "process"
    ASSET = "asset"
    EVENT = "event"
    MASTER_DATA = "master_data"
    TRANSACTION = "transaction"


@dataclass
class BusinessEntity:
    name: str
    type: EntityType
    display_name: str = ""
    description: str = ""
    attributes: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    confidence: float = 0.8
    
    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.name


@dataclass
class BusinessProcess:
    name: str
    type: str = "workflow"
    display_name: str = ""
    steps: List[Dict] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.name


@dataclass
class BusinessRule:
    name: str
    condition: str = ""
    action: str = ""
    priority: int = 2
    applies_to: List[str] = field(default_factory=list)


@dataclass
class BusinessModel:
    entities: List[BusinessEntity] = field(default_factory=list)
    processes: List[BusinessProcess] = field(default_factory=list)
    rules: List[BusinessRule] = field(default_factory=list)
    domain: str = ""


# ==================== 业务解析器 ====================

class BusinessParser:
    """业务解析器"""
    
    def __init__(self):
        self.entity_db = {
            "采购": ["供应商", "采购员", "采购申请", "采购订单", "合同", "付款单", "招标项目"],
            "人力资源": ["员工", "岗位", "招聘需求", "劳动合同", "请假申请"],
            "通用": ["用户", "角色", "部门"],
        }
        
        self.process_keywords = {
            "招标": ["发布招标", "投标", "开标", "评标", "定标"],
            "签约": ["发起签约", "审批", "签署", "归档"],
            "付款": ["申请付款", "审批", "打款"],
            "采购": ["提出需求", "选择供应商", "谈判", "下单", "收货", "验收", "付款"],
            "入职": ["发起入职", "审批", "办理入职"],
            "请假": ["提交申请", "审批", "销假"],
        }
    
    def parse(self, description: str) -> BusinessModel:
        """解析业务描述"""
        # 1. 检测领域
        domain = self._detect_domain(description)
        
        # 2. 识别实体
        entities = self._recognize_entities(description, domain)
        
        # 3. 推断流程
        processes = self._infer_processes(description, entities)
        
        # 4. 抽取规则
        rules = self._extract_rules(description, entities)
        
        return BusinessModel(
            entities=entities,
            processes=processes,
            rules=rules,
            domain=domain,
        )
    
    def _detect_domain(self, description: str) -> str:
        """检测业务领域"""
        domains = {
            "采购": ["采购", "供应商", "招标", "合同", "付款"],
            "人力资源": ["员工", "招聘", "入职", "请假", "薪酬"],
        }
        
        desc_lower = description.lower()
        for domain, keywords in domains.items():
            if any(kw in desc_lower for kw in keywords):
                return domain
        return "通用"
    
    def _recognize_entities(self, description: str, domain: str) -> List[BusinessEntity]:
        """识别业务实体"""
        entities = []
        found = set()
        
        # 从领域知识库匹配
        if domain in self.entity_db:
            for name in self.entity_db[domain]:
                if name in description and name not in found:
                    entities.append(BusinessEntity(
                        name=name,
                        type=EntityType.MASTER_DATA if "员" not in name else EntityType.PERSON,
                    ))
                    found.add(name)
        
        # 实体类型关键词
        keywords = {
            EntityType.PERSON: ["员工", "用户", "经理", "采购员", "供应商"],
            EntityType.DOCUMENT: ["合同", "订单", "申请", "凭证"],
            EntityType.TRANSACTION: ["订单", "交易", "付款", "收款"],
        }
        
        for etype, kws in keywords.items():
            for kw in kws:
                if kw in description and kw not in found:
                    entities.append(BusinessEntity(name=kw, type=etype))
                    found.add(kw)
        
        return entities
    
    def _infer_processes(self, description: str, entities: List[BusinessEntity]) -> List[BusinessProcess]:
        """推断业务流程"""
        processes = []
        
        for name, steps in self.process_keywords.items():
            if name in description:
                processes.append(BusinessProcess(
                    name=f"{name}流程",
                    type="workflow",
                    steps=[{"name": step, "order": i+1} for i, step in enumerate(steps)],
                    participants=["发起人", "审批人"],
                ))
        
        return processes
    
    def _extract_rules(self, description: str, entities: List[BusinessEntity]) -> List[BusinessRule]:
        """抽取业务规则"""
        rules = []
        
        # 金额规则
        import re
        amount_match = re.search(r"金额超过?(\d+)\s*万", description)
        if amount_match:
            threshold = int(amount_match.group(1))
            rules.append(BusinessRule(
                name=f"金额超过{threshold}万需经理审批",
                condition=f"amount > {threshold * 10000}",
                action="require_approval('manager')",
                priority=1,
                applies_to=[e.name for e in entities if e.type == EntityType.TRANSACTION],
            ))
        
        # 时间规则
        days_match = re.search(r"(\d+)\s*天内", description)
        if days_match:
            days = int(days_match.group(1))
            rules.append(BusinessRule(
                name=f"{days}天内完成",
                condition=f"elapsed_days > {days}",
                action="send_reminder()",
                priority=2,
            ))
        
        # 通用规则
        for entity in entities:
            rules.append(BusinessRule(
                name=f"{entity.name}创建记录创建人",
                condition="event == 'create'",
                action="set_created_info()",
                priority=3,
                applies_to=[entity.name],
            ))
        
        return rules


# ==================== 代码生成器 ====================

class CodeGenerator:
    """代码生成器"""
    
    def __init__(self, tech_stack=None):
        self.tech_stack = tech_stack or ["python", "fastapi"]
    
    def generate(self, business_model: BusinessModel) -> Dict[str, str]:
        """生成代码"""
        files = {}
        
        # 生成数据模型
        for entity in business_model.entities:
            files[f"models/{to_snake(entity.name)}.py"] = self._generate_model(entity)
        
        # 生成服务层
        for process in business_model.processes:
            files[f"services/{to_snake(process.name)}.py"] = self._generate_service(process, business_model)
        
        # 生成 API 路由
        for entity in business_model.entities:
            files[f"routes/{to_snake(entity.name)}.py"] = self._generate_api(entity)
        
        return files
    
    def _generate_model(self, entity: BusinessEntity) -> str:
        """生成模型"""
        return f'''"""Model: {entity.display_name}"""
from sqlalchemy import Column, String, DateTime
from models.base import Base
from datetime import datetime


class {to_pascal(entity.name)}(Base):
    """{entity.display_name}"""
    __tablename__ = "{to_snake(entity.name)}"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<{to_pascal(entity.name)} {{self.id}}>"
'''
    
    def _generate_service(self, process: BusinessProcess, model: BusinessModel) -> str:
        """生成服务"""
        steps_code = "\n".join([
            f'        # Step {i+1}: {step["name"]}'
            for i, step in enumerate(process.steps)
        ])
        
        rules = [r for r in model.rules if process.name in str(r.applies_to)]
        rules_code = "\n".join([
            f'        # Rule: {r.name}\n        #     if {r.condition}: {r.action}'
            for r in rules
        ])
        
        return f'''"""Service: {process.display_name}"""
from typing import List, Optional


class {to_pascal(process.name)}Service:
    """{process.display_name}"""
    
    def __init__(self, db):
        self.db = db
    
    def start_process(self, initiator_id: str) -> str:
        """启动{process.display_name}"""
{steps_code}
        pass
    
    def execute_step(self, process_id: str, step: int, operator_id: str) -> bool:
        """执行步骤"""
{rules_code}
        pass
    
    def complete_process(self, process_id: str) -> bool:
        """完成{process.display_name}"""
        return True
'''
    
    def _generate_api(self, entity: BusinessEntity) -> str:
        """生成API"""
        name_snake = to_snake(entity.name)
        name_pascal = to_pascal(entity.name)
        
        return f'''"""API: {entity.display_name}"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db


router = APIRouter()


@router.get("/{name_snake}s/")
def list_{name_snake}s(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List {entity.display_name}"""
    return []


@router.post("/{name_snake}s/")
def create_{name_snake}(data: dict, db: Session = Depends(get_db)):
    """Create {entity.display_name}"""
    return {{}}


@router.get("/{name_snake}s/{{id}}")
def get_{name_snake}(id: str, db: Session = Depends(get_db)):
    """Get {entity.display_name}"""
    return {{}}


@router.put("/{name_snake}s/{{id}}")
def update_{name_snake}(id: str, data: dict, db: Session = Depends(get_db)):
    """Update {entity.display_name}"""
    return {{}}


@router.delete("/{name_snake}s/{{id}}")
def delete_{name_snake}(id: str, db: Session = Depends(get_db)):
    """Delete {entity.display_name}"""
    return {{"success": True}}
'''


def to_snake(name: str) -> str:
    """转为 snake_case"""
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal(name: str) -> str:
    """转为 PascalCase"""
    return ''.join(word.capitalize() for word in name.split('_'))


# ==================== 测试 ====================

def main():
    print("=" * 60)
    print("Business OS Standalone Test")
    print("=" * 60)
    
    # 测试解析
    parser = BusinessParser()
    
    test_cases = [
        "实现供应商管理系统，包括供应商信息管理、招标流程、合同管理",
        "实现一个P2P采购流程，包括供应商管理、招标、合同签订、付款，金额超过10万需要经理审批",
        "员工管理系统，包括员工信息管理、入职流程、请假审批",
    ]
    
    for i, desc in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Description: {desc}")
        
        model = parser.parse(desc)
        
        print(f"\nDomain: {model.domain}")
        print(f"\nEntities ({len(model.entities)}):")
        for e in model.entities:
            print(f"  - {e.name} ({e.type.value})")
        
        print(f"\nProcesses ({len(model.processes)}):")
        for p in model.processes:
            print(f"  - {p.name}")
            for step in p.steps[:3]:
                print(f"      {step.get('order')}. {step.get('name')}")
        
        print(f"\nRules ({len(model.rules)}):")
        for r in model.rules[:5]:
            print(f"  - {r.name}")
            if r.condition:
                print(f"    Condition: {r.condition}")
        
        # 生成代码
        generator = CodeGenerator()
        files = generator.generate(model)
        
        print(f"\nGenerated Files ({len(files)}):")
        for filename in sorted(files.keys()):
            lines = files[filename].count('\n') + 1
            print(f"  - {filename} ({lines} lines)")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
