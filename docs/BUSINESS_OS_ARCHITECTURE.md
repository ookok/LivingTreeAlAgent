# Business OS 架构设计
## 从"代码生成工具"到"业务实体映射系统"

---

## 1. 核心范式转变

### 传统 AI IDE vs Business OS

| 维度 | 传统 AI IDE | Business OS |
|------|-------------|-------------|
| **输入** | "写一个用户登录接口" | "实现完整的供应商管理流程：招标→签约→付款" |
| **理解** | 代码级别的意图分类 | 业务级别的实体关系 |
| **生成** | 单个文件/函数 | 完整的业务系统（数据+逻辑+权限） |
| **输出** | 代码片段 | 可运行的业务系统 + 业务规则引擎 |
| **演进** | 手动迭代 | 系统自进化 |

### 核心理念

**Business OS 不是写代码，而是"建模"**：

```
业务描述（What） → 业务实体图谱（Entity Map） → 完整系统（System）
```

用户描述"供应商招标流程"，系统自动：
1. 识别业务实体：供应商、招标项目、投标文件、评标委员会、合同、付款单
2. 推断业务关系：一对多（供应商→投标）、多对一（投标→招标）
3. 生成业务规则：投标截止时间、评标标准、付款触发条件
4. 构建权限体系：采购员发起→经理审批→财务付款

---

## 2. 三大核心能力

### 2.1 业务语义理解（Business Semantics Understanding）

**目标**：理解业务意图，而非技术实现

**实现层次**：

```
Level 1: 关键词匹配
         "登录" → login()
         
Level 2: 意图分类
         "登录" → CODE_GENERATION
         
Level 3: 业务语义理解 ← 我们的目标
         "实现供应商管理，包括招标、评标、签约流程"
         → BusinessIntent {
             entities: [供应商, 招标, 投标, 评标, 合同],
             processes: [招标流程, 评标流程, 签约流程],
             rules: [投标截止时间, 评标标准, 签约审批]
           }
```

**核心组件**：

| 组件 | 功能 | 技术 |
|------|------|------|
| BusinessEntityRecognizer | 业务实体识别 | LLM + 知识图谱 |
| ProcessInferrer | 业务流程推断 | 时序推理 + 模式匹配 |
| RuleExtractor | 业务规则抽取 | NLP + 约束求解 |
| DomainClassifier | 领域分类 | 行业知识库 |

### 2.2 流程推理（Process Inference）

**目标**：从模糊描述推断完整流程

**输入示例**：
> "完成一个P2P采购流程，包括供应商管理、招标、合同签订、付款"

**推断过程**：

```
1. 实体识别
   供应商管理 → [供应商实体]
   招标 → [招标项目, 招标文件, 投标]
   合同签订 → [合同实体]
   付款 → [付款申请, 付款凭证]

2. 流程推断
   招标 → 开标 → 评标 → 定标 → 签约 → 付款
   
3. 角色推断
   采购员（发起招标）
   供应商（投标）
   评标委员会（评标）
   经理（审批签约）
   财务（执行付款）

4. 规则推断
   投标截止时间：招标发布后14天
   评标方式：综合评分法
   付款条件：合同已签订 + 验收合格
```

### 2.3 规则内化（Rules Internalization）

**目标**：生成的代码自带业务逻辑，而非空壳

**示例**：

```python
# ❌ 传统生成（空壳）
def create_contract(contract_id, supplier_id, amount):
    contract = Contract(id=contract_id, supplier_id=supplier_id, amount=amount)
    db.save(contract)
    return contract

# ✅ Business OS 生成（带规则）
def create_contract(contract_id, supplier_id, amount):
    # 规则1: 金额超过10万需要经理审批
    if amount > 100000:
        require_approval(role="manager", reason="大额合同")
    
    # 规则2: 供应商必须在白名单中
    supplier = get_supplier(supplier_id)
    if not supplier.is_whitelisted:
        raise BusinessRuleViolation("供应商不在白名单中")
    
    # 规则3: 不能与同一供应商连续签约超过3次
    recent_contracts = get_recent_contracts(supplier_id, days=90)
    if len(recent_contracts) >= 3:
        raise BusinessRuleViolation("需要重新招标")
    
    contract = Contract(id=contract_id, supplier_id=supplier_id, amount=amount)
    db.save(contract)
    return contract
```

---

## 3. 系统架构设计

### 3.1 模块总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Business OS Core                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │   Intent    │  │  Business   │  │     Business RAG        ││
│  │   Engine    │→ │   Parser    │→ │  (业务知识检索增强)      ││
│  │ (已有→增强) │  │  (新增)     │  │                         ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
│         │                │                      │               │
│         └────────────────┼──────────────────────┘               │
│                          ▼                                      │
│              ┌─────────────────────┐                           │
│              │   Entity Mapper     │                           │
│              │   (业务实体映射)    │                           │
│              └─────────────────────┘                           │
│                          │                                      │
│         ┌────────────────┼────────────────┐                    │
│         ▼                ▼                ▼                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │   Data      │  │   Process   │  │     Rules Engine        ││
│  │   Model     │  │   Generator │  │     (规则引擎)          ││
│  │  Generator  │  │             │  │                         ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
│                          │                                      │
│                          ▼                                      │
│              ┌─────────────────────┐                           │
│              │   Code Generator    │                           │
│              │   (代码生成器)      │                           │
│              └─────────────────────┘                           │
│                          │                                      │
│                          ▼                                      │
│              ┌─────────────────────┐                           │
│              │   Self-Evolution   │                           │
│              │   Engine           │                           │
│              └─────────────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块详细设计

#### 3.2.1 BusinessParser（业务解析器）

**位置**：`core/business_os/business_parser.py`

**功能**：将业务描述转换为结构化的业务模型

```python
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum

class EntityType(Enum):
    """业务实体类型"""
    PERSON = "person"           # 人员角色
    DOCUMENT = "document"       # 文档单据
    PROCESS = "process"         # 业务流程
    ASSET = "asset"            # 资产资源
    EVENT = "event"            # 业务事件

@dataclass
class BusinessEntity:
    """业务实体"""
    name: str
    type: EntityType
    attributes: List[str]
    relationships: List[str]
    confidence: float

@dataclass
class BusinessProcess:
    """业务流程"""
    name: str
    steps: List[str]
    participants: List[str]
    triggers: List[str]
    preconditions: List[str]
    postconditions: List[str]

@dataclass
class BusinessRule:
    """业务规则"""
    name: str
    condition: str
    action: str
    priority: int  # 1=高, 2=中, 3=低
    category: str  # 审批/验证/通知/计算

@dataclass
class BusinessModel:
    """完整业务模型"""
    entities: List[BusinessEntity]
    processes: List[BusinessProcess]
    rules: List[BusinessRule]
    permissions: Dict[str, List[str]]  # role -> allowed_actions
    
    def to_dict(self) -> Dict:
        """转换为可序列化格式"""
        return {
            "entities": [e.__dict__ for e in self.entities],
            "processes": [p.__dict__ for p in self.processes],
            "rules": [r.__dict__ for r in self.rules],
            "permissions": self.permissions,
        }

class BusinessParser:
    """
    业务解析器
    
    核心能力：
    1. 业务实体识别
    2. 业务流程推断
    3. 业务规则抽取
    4. 权限体系构建
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.entity_db = self._load_entity_db()
        self.rule_templates = self._load_rule_templates()
    
    def parse(self, business_description: str) -> BusinessModel:
        """
        解析业务描述
        
        Args:
            business_description: 业务需求描述
            
        Returns:
            BusinessModel: 完整的业务模型
        """
        # 1. 实体识别
        entities = self._recognize_entities(business_description)
        
        # 2. 流程推断
        processes = self._infer_processes(business_description, entities)
        
        # 3. 规则抽取
        rules = self._extract_rules(business_description, processes)
        
        # 4. 权限构建
        permissions = self._build_permissions(entities, processes)
        
        return BusinessModel(
            entities=entities,
            processes=processes,
            rules=rules,
            permissions=permissions,
        )
    
    def _recognize_entities(self, description: str) -> List[BusinessEntity]:
        """
        识别业务实体
        
        使用 LLM + 知识图谱 进行实体识别
        """
        # 构建提示
        prompt = f"""
从以下业务描述中识别所有业务实体，并标注类型：

业务描述：{description}

输出格式（JSON数组）：
[
  {{"name": "实体名", "type": "person|document|process|asset|event", 
    "attributes": ["属性1", "属性2"], "relationships": ["关联实体"]}}
]
"""
        # 调用 LLM
        response = self.llm.generate(prompt)
        
        # 解析响应
        import json
        entities_data = json.loads(response)
        
        entities = []
        for e in entities_data:
            entities.append(BusinessEntity(
                name=e["name"],
                type=EntityType(e["type"]),
                attributes=e.get("attributes", []),
                relationships=e.get("relationships", []),
                confidence=0.8,
            ))
        
        return entities
    
    def _infer_processes(self, description: str, entities: List[BusinessEntity]) -> List[BusinessProcess]:
        """
        推断业务流程
        
        基于实体和描述推断业务流程
        """
        # 识别流程关键词
        process_keywords = {
            "招标": ["发布招标", "投标", "开标", "评标", "定标"],
            "签约": ["发起", "审批", "签署", "归档"],
            "付款": ["申请", "审批", "打款", "确认"],
        }
        
        processes = []
        
        # 基于关键词推断流程
        for entity in entities:
            if entity.name in process_keywords:
                processes.append(BusinessProcess(
                    name=f"{entity.name}流程",
                    steps=process_keywords[entity.name],
                    participants=self._infer_participants(entity),
                    triggers=self._infer_triggers(entity),
                    preconditions=[],
                    postconditions=[],
                ))
        
        return processes
    
    def _extract_rules(self, description: str, processes: List[BusinessProcess]) -> List[BusinessRule]:
        """
        抽取业务规则
        
        从描述中提取隐含规则，或从规则模板生成
        """
        rules = []
        
        # 1. 从描述中提取显式规则
        explicit_rules = self._extract_explicit_rules(description)
        rules.extend(explicit_rules)
        
        # 2. 从规则模板生成隐式规则
        for process in processes:
            template_rules = self._generate_rule_from_template(process)
            rules.extend(template_rules)
        
        return rules
    
    def _build_permissions(self, entities: List[BusinessEntity], 
                          processes: List[BusinessProcess]) -> Dict[str, List[str]]:
        """
        构建权限体系
        
        基于实体和流程推断权限
        """
        permissions = {
            "admin": ["*"],  # 管理员拥有所有权限
            "manager": [],   # 经理
            "staff": [],     # 员工
        }
        
        # 基于角色推断权限
        for entity in entities:
            if entity.type == EntityType.PERSON:
                role = entity.name
                permissions[role] = self._infer_role_permissions(entity, processes)
        
        return permissions
    
    def _load_entity_db(self) -> Dict:
        """加载业务实体数据库"""
        # 预定义常见业务实体
        return {
            "采购": {
                "entities": ["供应商", "采购员", "采购申请", "采购订单", "合同", "付款单"],
                "processes": ["需求提出", "供应商选择", "价格谈判", "合同签订", "收货验收", "付款"],
            },
            "人力资源": {
                "entities": ["员工", "岗位", "招聘需求", "面试记录", "offer", "劳动合同"],
                "processes": ["招聘需求", "简历筛选", "面试", "录用", "入职", "转正"],
            },
            "项目管理": {
                "entities": ["项目", "任务", "里程碑", "资源", "风险", "变更"],
                "processes": ["项目立项", "任务分配", "进度跟踪", "风险管理", "项目验收"],
            },
        }
    
    def _load_rule_templates(self) -> Dict:
        """加载规则模板"""
        return {
            "金额审批": {
                "condition": "amount > threshold",
                "action": "require_approval(role)",
                "priority": 1,
            },
            "时间限制": {
                "condition": "time_elapsed > deadline",
                "action": "send_reminder()",
                "priority": 2,
            },
            "黑名单检查": {
                "condition": "entity in blacklist",
                "action": "block_operation()",
                "priority": 1,
            },
        }
```

#### 3.2.2 EntityMapper（实体映射器）

**位置**：`core/business_os/entity_mapper.py`

**功能**：将业务实体映射为技术实现

```python
class EntityMapper:
    """
    业务实体映射器
    
    将业务实体映射为：
    1. 数据模型（数据库表/API schema）
    2. 业务逻辑（Service层）
    3. 权限控制（Permission）
    """
    
    def __init__(self, tech_stack: List[str] = None):
        self.tech_stack = tech_stack or ["python", "fastapi", "postgresql"]
        self.template_registry = self._load_templates()
    
    def map(self, business_model: BusinessModel) -> TechnicalModel:
        """
        将业务模型映射为技术模型
        """
        # 1. 映射数据模型
        data_models = self._map_data_models(business_model.entities)
        
        # 2. 映射服务层
        services = self._map_services(business_model)
        
        # 3. 映射API
        apis = self._map_apis(business_model)
        
        # 4. 映射权限
        permissions = self._map_permissions(business_model)
        
        return TechnicalModel(
            data_models=data_models,
            services=services,
            apis=apis,
            permissions=permissions,
            business_model=business_model,
        )
    
    def _map_data_models(self, entities: List[BusinessEntity]) -> List[DataModel]:
        """将业务实体映射为数据模型"""
        data_models = []
        
        for entity in entities:
            # 确定主键
            primary_key = f"{entity.name.lower()}_id"
            
            # 映射属性
            fields = []
            for attr in entity.attributes:
                field = self._map_attribute(attr)
                fields.append(field)
            
            # 添加标准字段
            fields.extend([
                Field("id", FieldType.UUID, required=True),
                Field("created_at", FieldType.DATETIME),
                Field("updated_at", FieldType.DATETIME),
                Field("created_by", FieldType.STRING),
            ])
            
            data_models.append(DataModel(
                name=self._to_pascal_case(entity.name),
                table_name=self._to_snake_case(entity.name),
                fields=fields,
                primary_key=primary_key,
            ))
        
        return data_models
    
    def _map_services(self, business_model: BusinessModel) -> List[Service]:
        """将业务流程映射为服务"""
        services = []
        
        for process in business_model.processes:
            service = Service(
                name=f"{process.name}Service",
                methods=self._map_process_to_methods(process),
                business_rules=process.name,
            )
            services.append(service)
        
        return services
    
    def _map_apis(self, business_model: BusinessModel) -> List[APIEndpoint]:
        """映射API端点"""
        apis = []
        
        for entity in business_model.entities:
            # CRUD API
            apis.extend([
                APIEndpoint(f"/{entity.name.lower()}s", "GET", "list"),
                APIEndpoint(f"/{entity.name.lower()}s", "POST", "create"),
                APIEndpoint(f"/{entity.name.lower()}s/{{id}}", "GET", "get"),
                APIEndpoint(f"/{entity.name.lower()}s/{{id}}", "PUT", "update"),
                APIEndpoint(f"/{entity.name.lower()}s/{{id}}", "DELETE", "delete"),
            ])
        
        return apis
    
    def _map_permissions(self, business_model: BusinessModel) -> List[Permission]:
        """映射权限控制"""
        permissions = []
        
        for role, actions in business_model.permissions.items():
            for action in actions:
                permissions.append(Permission(
                    role=role,
                    resource=action.split(":")[0] if ":" in action else "*",
                    action=action.split(":")[1] if ":" in action else action,
                ))
        
        return permissions
```

#### 3.2.3 BusinessRAG（业务知识检索）

**位置**：`core/business_os/business_rag.py`

**功能**：为业务生成提供领域知识检索

```python
class BusinessRAG:
    """
    业务知识检索增强
    
    不同于普通 RAG（检索代码片段），
    Business RAG 检索：
    1. 行业最佳实践
    2. 业务流程模板
    3. 法规合规要求
    4. 历史成功案例
    """
    
    def __init__(self, vector_store=None):
        self.vector_store = vector_store or VectorStore()
        self.industry_kb = self._load_industry_kb()
        self.compliance_kb = self._load_compliance_kb()
    
    def retrieve(self, query: str, business_domain: str) -> List[KnowledgeChunk]:
        """
        检索相关业务知识
        """
        chunks = []
        
        # 1. 检索行业最佳实践
        industry_chunks = self._retrieve_industry_practices(query, business_domain)
        chunks.extend(industry_chunks)
        
        # 2. 检索合规要求
        compliance_chunks = self._retrieve_compliance(query, business_domain)
        chunks.extend(compliance_chunks)
        
        # 3. 检索流程模板
        template_chunks = self._retrieve_templates(query, business_domain)
        chunks.extend(template_chunks)
        
        # 4. 检索历史案例
        case_chunks = self._retrieve_similar_cases(query, business_domain)
        chunks.extend(case_chunks)
        
        return chunks
    
    def _retrieve_industry_practices(self, query: str, domain: str) -> List[KnowledgeChunk]:
        """检索行业最佳实践"""
        # 预定义的行业知识
        industry_practices = {
            "采购": [
                {"practice": "供应商分级管理", "description": "将供应商分为战略/优选/合格等级别"},
                {"practice": "三权分立", "description": "需求权/采购权/验收权分离"},
                {"practice": "价格数据库", "description": "建立历史采购价格数据库进行比价"},
            ],
            "人力资源": [
                {"practice": "岗位价值评估", "description": "使用海氏评估法或美世评估法"},
                {"practice": "人才九宫格", "description": "按绩效和潜力对人才分类"},
                {"practice": "继任者计划", "description": "关键岗位必须有B角"},
            ],
        }
        
        # 简单关键词匹配
        return industry_practices.get(domain, [])
    
    def _retrieve_compliance(self, query: str, domain: str) -> List[KnowledgeChunk]:
        """检索合规要求"""
        compliance_rules = {
            "采购": [
                {"rule": "招标法", "requirement": "公开招标必须发布公告20天"},
                {"rule": "政府采购法", "requirement": "政府采购需备案审批"},
            ],
            "财务": [
                {"rule": "发票管理", "requirement": "发票必须真实合规"},
                {"rule": "资金管理", "requirement": "大额资金需集体决策"},
            ],
        }
        
        return compliance_rules.get(domain, [])
```

#### 3.2.4 CodeGenerator（代码生成器）

**位置**：`core/business_os/code_generator.py`

**功能**：基于技术模型生成代码

```python
class CodeGenerator:
    """
    代码生成器
    
    基于技术模型和模板生成完整代码
    """
    
    def __init__(self, tech_stack: List[str]):
        self.tech_stack = tech_stack
        self.templates = self._load_templates()
    
    def generate(self, technical_model: TechnicalModel) -> GeneratedCode:
        """
        生成完整代码
        """
        files = {}
        
        # 1. 生成数据模型
        if "python" in self.tech_stack:
            files.update(self._generate_python_models(technical_model.data_models))
            files.update(self._generate_fastapi_models(technical_model))
        
        # 2. 生成服务层
        files.update(self._generate_services(technical_model))
        
        # 3. 生成API层
        files.update(self._generate_api_layer(technical_model))
        
        # 4. 生成权限层
        files.update(self._generate_permission_layer(technical_model))
        
        # 5. 生成数据库迁移
        files.update(self._generate_migrations(technical_model))
        
        # 6. 生成测试
        files.update(self._generate_tests(technical_model))
        
        return GeneratedCode(files=files)
    
    def _generate_python_models(self, data_models: List[DataModel]) -> Dict[str, str]:
        """生成 Python 数据模型"""
        files = {}
        
        for model in data_models:
            content = f'''"""数据模型：{model.name}"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class {model.name}(Base):
    """{model.name}数据模型"""
    __tablename__ = "{model.table_name}"
    
    # 主键
    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
    
'''
            # 添加字段
            for field in model.fields:
                if field.name not in ["id", "created_at", "updated_at", "created_by"]:
                    column_type = self._map_field_type(field)
                    nullable = "" if field.required else ", nullable=True"
                    content += f'    {field.name} = Column({column_type}{nullable})\n'
            
            # 添加业务规则
            content += '''
    def __repr__(self):
        return f"<{name} {{self.id}}>"
'''.format(name=model.name)
            
            files[f"{model.table_name}.py"] = content
        
        return files
    
    def _generate_services(self, technical_model: TechnicalModel) -> Dict[str, str]:
        """生成服务层代码"""
        files = {}
        
        for service in technical_model.services:
            content = f'''"""服务层：{service.name}"""
from typing import List, Optional
from datetime import datetime
import uuid

class {service.name}:
    """{service.name}业务服务"""
    
    def __init__(self, db_session):
        self.db = db_session
    
'''
            for method in service.methods:
                content += self._generate_method(method, service)
            
            files[f"{service.name.lower()}.py"] = content
        
        return files
    
    def _generate_method(self, method: Method, service: Service) -> str:
        """生成单个方法"""
        # 从规则模板生成
        rules_code = ""
        if service.business_rules:
            rules_code = self._generate_rule_validation(service.business_rules)
        
        return f'''
    def {method.name}(self{method.params}) -> {method.return_type}:
        """{method.description}"""
        {rules_code}
        # TODO: 实现业务逻辑
        pass
'''
    
    def _generate_rule_validation(self, rule_name: str) -> str:
        """生成规则验证代码"""
        # 基于规则模板生成验证代码
        return f'''
        # 规则验证：{rule_name}
        if not self._validate_{rule_name.lower().replace(" ", "_")}():
            raise BusinessRuleViolation("{rule_name}验证失败")
'''
```

---

## 4. 实施路径

### 4.1 MVP 定义（4周）

**目标**：实现一个完整的"供应商管理"业务系统

**输入示例**：
> "实现供应商管理系统，包括：供应商信息管理、招标流程、合同管理、付款审批"

**输出**：
- 完整的 FastAPI 后端（数据模型 + API + 服务层）
- 权限控制系统
- 业务流程引擎
- 单元测试

**验收标准**：
- 生成的代码可直接运行
- 业务流程符合业务描述
- 包含基本的业务规则验证

### 4.2 实施计划

| 周次 | 任务 | 产出 |
|------|------|------|
| 第1周 | BusinessParser 核心 | 业务描述→结构化模型 |
| 第2周 | EntityMapper | 业务模型→技术模型 |
| 第3周 | CodeGenerator | 技术模型→完整代码 |
| 第4周 | 集成与测试 | 端到端流程验证 |

### 4.3 技术栈选择

**后端**：Python + FastAPI + SQLAlchemy
**前端**：可选（MVP 专注后端）
**数据库**：PostgreSQL
**AI**：qwen3.5:9b（复杂业务理解）

---

## 5. 与现有系统的集成

### 5.1 复用现有 IntentEngine

```python
# 现有 IntentEngine → 增强为 BusinessIntentEngine

class BusinessIntentEngine(IntentEngine):
    """业务意图引擎"""
    
    def __init__(self):
        super().__init__()
        self.business_parser = BusinessParser()
        self.entity_mapper = EntityMapper()
        self.code_generator = CodeGenerator(tech_stack=["python", "fastapi"])
    
    def parse_business_intent(self, query: str) -> BusinessModel:
        """解析业务意图"""
        # 1. 使用 IntentEngine 进行基础解析
        intent = self.parse(query)
        
        # 2. 如果是业务级意图，交给 BusinessParser
        if self._is_business_intent(intent):
            return self.business_parser.parse(query)
        
        # 3. 否则使用传统代码生成
        return self._generate_code(intent)
    
    def _is_business_intent(self, intent) -> bool:
        """判断是否为业务级意图"""
        business_keywords = [
            "流程", "管理", "系统", "招标", "签约", "审批",
            "供应商", "合同", "采购", "人力资源", "项目管理"
        ]
        return any(kw in intent.raw_input for kw in business_keywords)
```

### 5.2 集成到 UI

```python
# 在 AIDrivenIDEPanel 中添加业务模式

class AIDrivenIDEPanel:
    def _setup_chat_mode(self):
        """设置聊天模式"""
        # 添加模式切换
        self.mode_switch = QComboBox()
        self.mode_switch.addItems(["代码模式", "业务模式"])
        self.mode_switch.currentTextChanged.connect(self._on_mode_changed)
        
        # 业务模式
        if self.mode_switch.currentText() == "业务模式":
            self.business_engine = BusinessIntentEngine()
            self._setup_business_chat()
    
    def _on_business_query(self, query: str):
        """处理业务查询"""
        # 解析业务意图
        business_model = self.business_engine.parse_business_intent(query)
        
        # 生成代码
        technical_model = self.business_engine.entity_mapper.map(business_model)
        generated_code = self.business_engine.code_generator.generate(technical_model)
        
        # 显示生成的代码
        self._display_generated_code(generated_code)
```

---

## 6. 自进化机制

### 6.1 业务知识积累

```python
class BusinessEvolution:
    """
    业务自进化引擎
    
    1. 记录成功的业务模式
    2. 分析失败的模式
    3. 优化实体映射规则
    4. 更新规则模板库
    """
    
    def record_success(self, business_model: BusinessModel, 
                       generated_code: GeneratedCode):
        """记录成功案例"""
        # 1. 存储业务模型
        self.business_db.save(business_model)
        
        # 2. 建立业务→代码映射
        self.mapping_db.save({
            "business": business_model.to_dict(),
            "code": generated_code.files,
            "success_rate": 0.9,
        })
        
        # 3. 更新规则模板
        for rule in business_model.rules:
            self.rule_templates.upsert(rule)
    
    def analyze_failures(self, business_query: str, 
                         error: Exception):
        """分析失败案例"""
        # 1. 记录失败案例
        self.failure_db.save({
            "query": business_query,
            "error": str(error),
            "timestamp": datetime.now(),
        })
        
        # 2. 分析失败原因
        if "entity" in str(error).lower():
            self.entity_recognizer.add_missing_entity(business_query)
        elif "rule" in str(error).lower():
            self.rule_extractor.add_missing_rule(business_query)
```

---

## 7. 挑战与应对

### 7.1 业务DSL设计

**挑战**：如何设计一个既能表达业务意图又易于LLM理解的描述语言？

**方案**：不设计固定DSL，而是使用自然语言的约束子集

```
# 接受的输入格式
"实现[流程名]，包括[步骤1]→[步骤2]→[步骤3]，由[角色]执行，需要[规则]"

# 示例
"实现采购审批流程，包括提交申请→部门审批→财务复核→总经理审批，
 由采购员发起，金额超过10万需要总经理审批"
```

### 7.2 责任边界

**挑战**：核心业务逻辑（如财务计算）需要人工确认

**方案**：风险分级机制

| 风险等级 | 示例 | 处理方式 |
|----------|------|----------|
| L1 低 | UI调整 | 自动生成 |
| L2 中 | 新增字段 | 生成 + 用户确认 |
| L3 高 | 金额计算 | 生成 + 人工审核 |
| L4 关键 | 财务凭证 | 禁止自动生成 |

### 7.3 领域适配

**挑战**：不同行业有不同业务模式

**方案**：行业知识库 + 可插拔模板

```python
# 注册行业模板
BusinessRAG.register_industry_template(
    "制造业", 
    manufacturing_templates
)

BusinessRAG.register_industry_template(
    "服务业",
    service_templates
)
```

---

## 8. 总结

Business OS 的核心理念是**从"写代码"到"建模"的转变**：

1. **输入**：自然语言业务描述
2. **理解**：业务语义理解（实体、流程、规则）
3. **映射**：业务实体→技术实现
4. **生成**：完整可运行系统
5. **进化**：从实践中学习优化

**下一步行动**：

1. 实现 `BusinessParser` 核心模块
2. 在 `AIDrivenIDEPanel` 中添加业务模式
3. 用"供应商管理"场景进行端到端测试

---

*设计日期：2026-04-25*
*版本：v1.0*
