"""
BusinessParser - 业务解析器
==========================

核心功能：
1. 业务实体识别
2. 业务流程推断
3. 业务规则抽取
4. 权限体系构建

使用方式：
    parser = BusinessParser()
    model = parser.parse("实现供应商管理系统，包括招标、签约、付款流程")
    print(model.entities)
"""

import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.logger import get_logger
from core.config.unified_config import UnifiedConfig

logger = get_logger('business_os.parser')


class EntityType(Enum):
    """业务实体类型"""
    PERSON = "person"           # 人员角色
    DOCUMENT = "document"       # 文档单据
    PROCESS = "process"         # 业务流程
    ASSET = "asset"            # 资产资源
    EVENT = "event"            # 业务事件
    ABSTRACT = "abstract"       # 抽象概念


class RuleType(Enum):
    """业务规则类型"""
    APPROVAL = "approval"       # 审批规则
    VALIDATION = "validation"   # 验证规则
    NOTIFICATION = "notification"  # 通知规则
    CALCULATION = "calculation"  # 计算规则
    CONSTRAINT = "constraint"    # 约束规则


class PermissionLevel(Enum):
    """权限级别"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    EXECUTE = "execute"


@dataclass
class BusinessEntity:
    """业务实体"""
    name: str                           # 实体名称
    entity_type: EntityType              # 实体类型
    attributes: List[str] = field(default_factory=list)   # 属性列表
    relationships: List[str] = field(default_factory=list)  # 关联关系
    description: str = ""               # 描述
    confidence: float = 0.8             # 识别置信度


@dataclass
class BusinessProcess:
    """业务流程"""
    name: str                            # 流程名称
    steps: List[str] = field(default_factory=list)    # 步骤列表
    participants: List[str] = field(default_factory=list)  # 参与者
    triggers: List[str] = field(default_factory=list)  # 触发条件
    preconditions: List[str] = field(default_factory=list)  # 前置条件
    postconditions: List[str] = field(default_factory=list)  # 后置条件
    timeout: int = 86400                # 超时时间（秒）
    description: str = ""


@dataclass
class BusinessRule:
    """业务规则"""
    name: str                            # 规则名称
    rule_type: RuleType                   # 规则类型
    condition: str                        # 条件表达式
    action: str                          # 动作表达式
    priority: int = 2                    # 优先级 1=高, 2=中, 3=低
    category: str = ""                    # 规则分类
    description: str = ""                # 描述
    applicable_entities: List[str] = field(default_factory=list)  # 适用实体


@dataclass
class Permission:
    """权限定义"""
    role: str                            # 角色
    resource: str                        # 资源
    level: PermissionLevel               # 权限级别
    conditions: List[str] = field(default_factory=list)  # 条件


@dataclass
class BusinessModel:
    """完整业务模型"""
    domain: str = ""                      # 业务领域
    entities: List[BusinessEntity] = field(default_factory=list)    # 实体列表
    processes: List[BusinessProcess] = field(default_factory=list)   # 流程列表
    rules: List[BusinessRule] = field(default_factory=list)         # 规则列表
    permissions: List[Permission] = field(default_factory=list)      # 权限列表
    metadata: Dict[str, Any] = field(default_factory=dict)          # 元数据
    
    def to_dict(self) -> Dict:
        """转换为可序列化格式"""
        return {
            "domain": self.domain,
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type.value,
                    "attributes": e.attributes,
                    "relationships": e.relationships,
                    "description": e.description,
                    "confidence": e.confidence,
                }
                for e in self.entities
            ],
            "processes": [
                {
                    "name": p.name,
                    "steps": p.steps,
                    "participants": p.participants,
                    "triggers": p.triggers,
                    "description": p.description,
                }
                for p in self.processes
            ],
            "rules": [
                {
                    "name": r.name,
                    "type": r.rule_type.value,
                    "condition": r.condition,
                    "action": r.action,
                    "priority": r.priority,
                    "category": r.category,
                }
                for r in self.rules
            ],
            "permissions": [
                {
                    "role": p.role,
                    "resource": p.resource,
                    "level": p.level.value,
                }
                for p in self.permissions
            ],
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def summary(self) -> str:
        """生成摘要"""
        return f"""
业务领域: {self.domain}
实体数量: {len(self.entities)}
流程数量: {len(self.processes)}
规则数量: {len(self.rules)}
权限数量: {len(self.permissions)}
"""


class BusinessParser:
    """
    业务解析器
    
    将自然语言业务描述转换为结构化的业务模型
    
    核心能力：
    1. 业务实体识别 - 从描述中识别业务实体
    2. 业务流程推断 - 推断业务流程和步骤
    3. 业务规则抽取 - 抽取业务规则
    4. 权限体系构建 - 构建权限模型
    """
    
    # 预定义的领域知识库
    DOMAIN_KB = {
        "采购": {
            "entities": ["供应商", "采购员", "采购申请", "采购订单", "合同", "付款单", "招标文件", "投标文件"],
            "processes": ["需求提出", "供应商选择", "价格谈判", "合同签订", "收货验收", "付款"],
            "rules": ["金额审批", "供应商准入", "比价规则"],
        },
        "人力资源": {
            "entities": ["员工", "岗位", "招聘需求", "简历", "面试记录", "offer", "劳动合同", "考勤记录"],
            "processes": ["招聘需求", "简历筛选", "面试", "录用", "入职", "转正", "离职"],
            "rules": ["试用期规则", "考勤规则", "薪资规则"],
        },
        "项目管理": {
            "entities": ["项目", "任务", "里程碑", "资源", "风险", "变更", "验收报告"],
            "processes": ["项目立项", "任务分配", "进度跟踪", "风险管理", "变更管理", "项目验收"],
            "rules": ["立项审批", "变更审批", "验收标准"],
        },
        "财务管理": {
            "entities": ["发票", "付款申请", "报销单", "银行流水", "对账单"],
            "processes": ["发票录入", "付款审批", "报销审批", "对账"],
            "rules": ["发票验证", "金额限制", "审批流程"],
        },
        "客户管理": {
            "entities": ["客户", "联系人", "商机", "报价", "合同", "售后服务"],
            "processes": ["线索跟进", "商机转化", "报价", "合同签订", "售后服务"],
            "rules": ["客户分级", "报价规则", "服务级别"],
        },
    }
    
    # 流程步骤模板
    PROCESS_TEMPLATES = {
        "审批": ["申请", "初审", "复审", "批准", "执行"],
        "采购": ["需求确认", "供应商选择", "价格谈判", "合同签订", "执行", "验收"],
        "招聘": ["需求发布", "简历筛选", "面试", "录用审批", "offer发送", "入职"],
        "项目": ["立项", "计划", "执行", "监控", "收尾", "验收"],
        "付款": ["申请", "初审", "复核", "批准", "支付", "确认"],
        "招标": ["发布公告", "投标", "开标", "评标", "定标", "公示", "签约"],
        "签约": ["发起", "审核", "会签", "签署", "归档"],
    }
    
    # 实体关键词映射
    ENTITY_KEYWORDS = {
        EntityType.PERSON: ["员", "经理", "总监", "客户", "供应商", "采购员", "财务", "管理员"],
        EntityType.DOCUMENT: ["合同", "订单", "申请", "报告", "审批", "发票", "凭证", "文件"],
        EntityType.PROCESS: ["流程", "审批", "招标", "签约", "付款", "采购", "招聘"],
        EntityType.ASSET: ["资产", "设备", "库存", "资金", "资源"],
        EntityType.EVENT: ["事件", "活动", "会议", "培训"],
    }
    
    # 规则关键词
    RULE_KEYWORDS = {
        RuleType.APPROVAL: ["审批", "批准", "审核", "确认"],
        RuleType.VALIDATION: ["验证", "校验", "检查", "必须", "不能"],
        RuleType.NOTIFICATION: ["通知", "提醒", "发送", "抄送"],
        RuleType.CALCULATION: ["计算", "合计", "汇总", "统计"],
        RuleType.CONSTRAINT: ["限制", "不能超过", "不能低于", "必须大于"],
    }
    
    def __init__(self, llm_client=None):
        """
        初始化业务解析器
        
        Args:
            llm_client: LLM客户端，用于复杂业务理解
        """
        self.llm = llm_client
        
        # 加载配置
        config = UnifiedConfig.get_instance()
        self.config = config.get("business_os", {})
        
        # 知识库
        self.entity_db = self.DOMAIN_KB
        self.process_templates = self.PROCESS_TEMPLATES
        self.entity_keywords = self.ENTITY_KEYWORDS
        self.rule_keywords = self.RULE_KEYWORDS
        
        logger.info("[BusinessParser] 初始化完成")
    
    def parse(self, business_description: str) -> BusinessModel:
        """
        解析业务描述
        
        Args:
            business_description: 业务需求描述
            
        Returns:
            BusinessModel: 完整的业务模型
        """
        logger.info(f"[BusinessParser] 开始解析: {business_description[:50]}...")
        
        # 0. 领域识别
        domain = self._identify_domain(business_description)
        
        # 1. 实体识别
        entities = self._recognize_entities(business_description, domain)
        
        # 2. 流程推断
        processes = self._infer_processes(business_description, entities, domain)
        
        # 3. 规则抽取
        rules = self._extract_rules(business_description, entities, processes)
        
        # 4. 权限构建
        permissions = self._build_permissions(entities, processes)
        
        # 5. 构建完整模型
        model = BusinessModel(
            domain=domain,
            entities=entities,
            processes=processes,
            rules=rules,
            permissions=permissions,
            metadata={
                "source": business_description,
                "parsed_at": datetime.now().isoformat(),
            }
        )
        
        logger.info(f"[BusinessParser] 解析完成: {len(entities)}实体, {len(processes)}流程, {len(rules)}规则")
        
        return model
    
    def _identify_domain(self, description: str) -> str:
        """识别业务领域"""
        description_lower = description.lower()
        
        domain_scores = {}
        for domain, kb in self.entity_db.items():
            score = 0
            # 计算关键词匹配分数
            for entity in kb.get("entities", []):
                if entity in description:
                    score += 1
            for process in kb.get("processes", []):
                if process in description:
                    score += 1
            
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            best_domain = max(domain_scores, key=domain_scores.get)
            logger.info(f"[BusinessParser] 识别领域: {best_domain} (分数: {domain_scores[best_domain]})")
            return best_domain
        
        return "通用"
    
    def _recognize_entities(self, description: str, domain: str) -> List[BusinessEntity]:
        """
        识别业务实体
        
        Args:
            description: 业务描述
            domain: 业务领域
            
        Returns:
            业务实体列表
        """
        entities = []
        
        # 1. 从知识库获取领域相关实体
        if domain in self.entity_db:
            domain_entities = self.entity_db[domain].get("entities", [])
            for entity_name in domain_entities:
                if entity_name in description:
                    entity_type = self._infer_entity_type(entity_name)
                    entities.append(BusinessEntity(
                        name=entity_name,
                        entity_type=entity_type,
                        attributes=self._infer_attributes(entity_name),
                        confidence=0.9,
                    ))
        
        # 2. 从描述中提取新的实体
        # 匹配 "XXX管理"、"XXX流程" 等模式
        patterns = [
            r'([\u4e00-\u9fa5]{2,10})(?:管理|系统|流程|模块)',
            r'([\u4e00-\u9fa5]{2,10})(?:信息|数据|记录)',
            r'([\u4e00-\u9fa5]{2,10})(?:申请|审批|处理)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                # 避免重复
                if not any(e.name == match for e in entities):
                    entity_type = self._infer_entity_type(match)
                    entities.append(BusinessEntity(
                        name=match,
                        entity_type=entity_type,
                        attributes=self._infer_attributes(match),
                        confidence=0.7,
                    ))
        
        # 3. 识别角色实体
        role_patterns = [
            r'([\u4e00-\u9fa5]{1,4})(?:员|经理|主管|总监|长)',
            r'由([\u4e00-\u9fa5]{1,4})发起',
            r'([\u4e00-\u9fa5]{1,4})(?:审批|审核|批准)',
        ]
        
        for pattern in role_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                if not any(e.name == match for e in entities):
                    entities.append(BusinessEntity(
                        name=match,
                        entity_type=EntityType.PERSON,
                        attributes=["角色", "部门"],
                        confidence=0.8,
                    ))
        
        # 4. 识别文档实体
        doc_patterns = [
            r'([\u4e00-\u9fa5]{2,8})(?:单|表|单据|凭证|证明)',
            r'([\u4e00-\u9fa5]{2,8})(?:合同|协议|文件|报告)',
        ]
        
        for pattern in doc_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                if not any(e.name == match for e in entities):
                    entities.append(BusinessEntity(
                        name=match,
                        entity_type=EntityType.DOCUMENT,
                        attributes=["编号", "状态", "创建时间"],
                        confidence=0.75,
                    ))
        
        logger.debug(f"[BusinessParser] 识别实体: {[e.name for e in entities]}")
        return entities
    
    def _infer_entity_type(self, entity_name: str) -> EntityType:
        """根据实体名称推断类型"""
        for entity_type, keywords in self.entity_keywords.items():
            for keyword in keywords:
                if keyword in entity_name:
                    return entity_type
        return EntityType.ABSTRACT
    
    def _infer_attributes(self, entity_name: str) -> List[str]:
        """推断实体属性"""
        common_attrs = ["编号", "名称", "状态", "创建时间", "更新时间", "创建人"]
        
        specific_attrs = {
            "合同": ["甲方", "乙方", "金额", "期限", "签署日期", "生效日期"],
            "订单": ["订单号", "客户", "商品", "数量", "金额", "下单时间"],
            "供应商": ["编码", "名称", "联系人", "电话", "地址", "评级"],
            "员工": ["工号", "姓名", "部门", "岗位", "入职日期"],
            "项目": ["项目编号", "名称", "负责人", "开始日期", "结束日期", "状态"],
            "付款": ["付款单号", "金额", "付款方式", "收款方", "付款时间"],
            "审批": ["审批人", "审批时间", "审批意见", "审批状态"],
        }
        
        # 返回通用属性 + 特定属性
        attrs = list(common_attrs)
        for key, value in specific_attrs.items():
            if key in entity_name:
                attrs.extend(value)
                break
        
        return list(set(attrs))
    
    def _infer_processes(self, description: str, entities: List[BusinessEntity], 
                         domain: str) -> List[BusinessProcess]:
        """
        推断业务流程
        
        Args:
            description: 业务描述
            entities: 识别的实体
            domain: 业务领域
            
        Returns:
            业务流程列表
        """
        processes = []
        
        # 1. 从知识库获取领域相关流程
        if domain in self.entity_db:
            domain_processes = self.entity_db[domain].get("processes", [])
            for process_name in domain_processes:
                if process_name in description:
                    # 使用模板构建流程
                    steps = self._build_process_steps(process_name)
                    processes.append(BusinessProcess(
                        name=process_name,
                        steps=steps,
                        participants=self._infer_participants(process_name),
                        description=f"{domain}领域的{process_name}流程",
                    ))
        
        # 2. 从描述中识别流程
        # 匹配 "XXX→YYY→ZZZ" 模式
        arrow_pattern = r'([\u4e00-\u9fa5]{2,6})(?:→|->|→)([\u4e00-\u9fa5]{2,6})(?:→|->|→)?([\u4e00-\u9fa5]{2,6})?'
        matches = re.findall(arrow_pattern, description)
        for match in matches:
            steps = [s for s in match if s]
            if len(steps) >= 2:
                process_name = f"{steps[0]}到{steps[-1]}流程"
                processes.append(BusinessProcess(
                    name=process_name,
                    steps=steps,
                    participants=self._infer_participants(process_name),
                ))
        
        # 3. 识别"包括"后面的流程
        include_pattern = r'包括[：:](.+?)(?:，|。|$)'
        matches = re.findall(include_pattern, description)
        for match in matches:
            # 分割各个子流程
            sub_processes = re.split(r'[、，]', match)
            for sp in sub_processes:
                sp = sp.strip()
                if len(sp) >= 2:
                    # 检查是否是已识别实体的流程
                    for entity in entities:
                        if entity.name in sp or sp in entity.name:
                            steps = self._build_process_steps(sp)
                            processes.append(BusinessProcess(
                                name=sp,
                                steps=steps,
                                participants=self._infer_participants(sp),
                            ))
                            break
        
        # 4. 去重
        seen = set()
        unique_processes = []
        for p in processes:
            if p.name not in seen:
                seen.add(p.name)
                unique_processes.append(p)
        
        logger.debug(f"[BusinessParser] 推断流程: {[p.name for p in unique_processes]}")
        return unique_processes
    
    def _build_process_steps(self, process_name: str) -> List[str]:
        """构建流程步骤"""
        # 查找模板
        for template_name, steps in self.process_templates.items():
            if template_name in process_name:
                return steps.copy()
        
        # 默认步骤
        default_steps = ["申请", "审批", "执行", "完成"]
        
        # 根据流程名称推断
        if "招标" in process_name:
            return ["发布公告", "投标", "开标", "评标", "定标", "签约"]
        elif "签约" in process_name:
            return ["发起", "审核", "签署", "归档"]
        elif "付款" in process_name:
            return ["申请", "复核", "批准", "支付", "确认"]
        elif "采购" in process_name:
            return ["需求确认", "供应商选择", "合同签订", "执行", "验收"]
        elif "招聘" in process_name:
            return ["需求发布", "简历筛选", "面试", "录用", "入职"]
        elif "项目" in process_name:
            return ["立项", "计划", "执行", "监控", "验收"]
        
        return default_steps
    
    def _infer_participants(self, process_name: str) -> List[str]:
        """推断流程参与者"""
        participants = []
        
        # 根据流程名称推断
        if "审批" in process_name or "付款" in process_name:
            participants = ["申请人", "审批人", "财务"]
        elif "采购" in process_name:
            participants = ["采购员", "供应商", "仓库管理员"]
        elif "招聘" in process_name:
            participants = ["HR", "面试官", "部门经理"]
        elif "项目" in process_name:
            participants = ["项目经理", "团队成员", "客户"]
        elif "招标" in process_name:
            participants = ["招标方", "投标方", "评标委员会"]
        
        return participants
    
    def _extract_rules(self, description: str, entities: List[BusinessEntity],
                       processes: List[BusinessProcess]) -> List[BusinessRule]:
        """
        抽取业务规则
        
        Args:
            description: 业务描述
            entities: 实体列表
            processes: 流程列表
            
        Returns:
            业务规则列表
        """
        rules = []
        
        # 1. 从描述中提取显式规则
        # 匹配 "金额超过XXX需要YYY审批" 模式
        amount_pattern = r'金额超过(\d+)(?:万|元)(?:需要|须)?([\u4e00-\u9fa5]{1,4})(?:审批|批准)'
        matches = re.findall(amount_pattern, description)
        for amount, approver in matches:
            rules.append(BusinessRule(
                name=f"大额{approver}审批规则",
                rule_type=RuleType.APPROVAL,
                condition=f"amount > {int(amount) * 10000}",
                action=f"require_approval(role='{approver}')",
                priority=1,
                category="金额审批",
                applicable_entities=["付款", "合同", "订单"],
            ))
        
        # 匹配 "XXX不能超过Y个" 模式
        limit_pattern = r'([\u4e00-\u9fa5]{1,6})不能超过(\d+)个'
        matches = re.findall(limit_pattern, description)
        for item, limit in matches:
            rules.append(BusinessRule(
                name=f"{item}数量限制规则",
                rule_type=RuleType.CONSTRAINT,
                condition=f"count({item}) > {limit}",
                action="block_operation()",
                priority=2,
                category="数量限制",
                applicable_entities=[item],
            ))
        
        # 匹配 "必须在X天内完成" 模式
        deadline_pattern = r'必须在(\d+)天内完成'
        matches = re.findall(deadline_pattern, description)
        for days in matches:
            rules.append(BusinessRule(
                name="时间限制规则",
                rule_type=RuleType.CONSTRAINT,
                condition=f"time_elapsed > {days}",
                action="send_reminder()",
                priority=2,
                category="时间限制",
            ))
        
        # 匹配 "需要YYY审核" 模式
        approval_pattern = r'需要([\u4e00-\u9fa5]{1,4})(?:审核|审批|确认)'
        matches = re.findall(approval_pattern, description)
        for approver in matches:
            rules.append(BusinessRule(
                name=f"{approver}审核规则",
                rule_type=RuleType.APPROVAL,
                condition="True",
                action=f"require_approval(role='{approver}')",
                priority=2,
                category="审批规则",
            ))
        
        # 2. 生成默认规则
        # 基于实体生成验证规则
        for entity in entities:
            if entity.entity_type == EntityType.DOCUMENT:
                rules.append(BusinessRule(
                    name=f"{entity.name}必填验证",
                    rule_type=RuleType.VALIDATION,
                    condition="not entity",
                    action="raise ValidationError()",
                    priority=3,
                    category="数据验证",
                    applicable_entities=[entity.name],
                ))
        
        # 3. 基于流程生成规则
        for process in processes:
            if process.timeout:
                rules.append(BusinessRule(
                    name=f"{process.name}超时规则",
                    rule_type=RuleType.NOTIFICATION,
                    condition=f"time_elapsed > {process.timeout}",
                    action="send_reminder()",
                    priority=2,
                    category="超时提醒",
                    applicable_entities=[process.name],
                ))
        
        logger.debug(f"[BusinessParser] 抽取规则: {[r.name for r in rules]}")
        return rules
    
    def _build_permissions(self, entities: List[BusinessEntity],
                          processes: List[BusinessProcess]) -> List[Permission]:
        """
        构建权限体系
        
        Args:
            entities: 实体列表
            processes: 流程列表
            
        Returns:
            权限列表
        """
        permissions = []
        
        # 默认角色
        default_roles = ["管理员", "经理", "员工"]
        
        # 管理员拥有所有权限
        for entity in entities:
            for level in PermissionLevel:
                permissions.append(Permission(
                    role="管理员",
                    resource=entity.name,
                    level=level,
                ))
        
        # 基于实体类型分配权限
        for entity in entities:
            if entity.entity_type == EntityType.PERSON:
                # 人员实体：经理可以管理，员工只能查看
                for level in PermissionLevel:
                    permissions.append(Permission(
                        role="经理",
                        resource=entity.name,
                        level=level,
                    ))
                permissions.append(Permission(
                    role="员工",
                    resource=entity.name,
                    level=PermissionLevel.READ,
                ))
            elif entity.entity_type == EntityType.DOCUMENT:
                # 文档实体：员工可以创建和查看，经理可以审批
                permissions.append(Permission(
                    role="员工",
                    resource=entity.name,
                    level=PermissionLevel.CREATE,
                ))
                permissions.append(Permission(
                    role="经理",
                    resource=entity.name,
                    level=PermissionLevel.APPROVE,
                ))
        
        # 基于流程分配权限
        for process in processes:
            for participant in process.participants:
                # 流程参与者拥有执行权限
                permissions.append(Permission(
                    role=participant,
                    resource=process.name,
                    level=PermissionLevel.EXECUTE,
                ))
        
        logger.debug(f"[BusinessParser] 构建权限: {len(permissions)}条")
        return permissions
    
    def parse_with_llm(self, business_description: str) -> BusinessModel:
        """
        使用LLM增强的业务解析
        
        Args:
            business_description: 业务描述
            
        Returns:
            BusinessModel: 业务模型
        """
        if not self.llm:
            logger.warning("[BusinessParser] 未配置LLM，使用规则解析")
            return self.parse(business_description)
        
        # 构建提示
        prompt = f"""
你是一个业务分析师。请从以下业务描述中提取：
1. 业务实体（带类型和属性）
2. 业务流程（带步骤和参与者）
3. 业务规则（带条件和动作）
4. 权限要求

业务描述：
{business_description}

请以JSON格式输出：
{{
    "entities": [
        {{"name": "实体名", "type": "person/document/process/asset/event", "attributes": ["属性1", "属性2"]}}
    ],
    "processes": [
        {{"name": "流程名", "steps": ["步骤1", "步骤2"], "participants": ["参与者1"]}}
    ],
    "rules": [
        {{"name": "规则名", "type": "approval/validation/notification", "condition": "条件", "action": "动作"}}
    ]
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            data = json.loads(response)
            
            # 转换为BusinessModel
            entities = [
                BusinessEntity(
                    name=e["name"],
                    entity_type=EntityType(e.get("type", "abstract")),
                    attributes=e.get("attributes", []),
                    confidence=0.9,
                )
                for e in data.get("entities", [])
            ]
            
            processes = [
                BusinessProcess(
                    name=p["name"],
                    steps=p.get("steps", []),
                    participants=p.get("participants", []),
                )
                for p in data.get("processes", [])
            ]
            
            rules = [
                BusinessRule(
                    name=r["name"],
                    rule_type=RuleType(r.get("type", "validation")),
                    condition=r.get("condition", ""),
                    action=r.get("action", ""),
                )
                for r in data.get("rules", [])
            ]
            
            return BusinessModel(
                domain=self._identify_domain(business_description),
                entities=entities,
                processes=processes,
                rules=rules,
                permissions=self._build_permissions(entities, processes),
            )
            
        except Exception as e:
            logger.error(f"[BusinessParser] LLM解析失败: {e}")
            return self.parse(business_description)


# ============ 便捷函数 ============

def parse_business(description: str) -> BusinessModel:
    """
    解析业务描述的便捷函数
    
    Args:
        description: 业务需求描述
        
    Returns:
        BusinessModel: 业务模型
    """
    parser = BusinessParser()
    return parser.parse(description)


# ============ 测试 ============

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        # 供应商管理
        "实现供应商管理系统，包括招标流程、合同管理、付款审批。金额超过10万需要总经理审批。",
        
        # 人力资源
        "实现员工管理系统，包括招聘流程、入职流程、考勤管理、离职流程。试用期不能超过6个月。",
        
        # 项目管理
        "实现项目管理系统，包括项目立项、任务分配、进度跟踪、风险管理、项目验收。",
    ]
    
    parser = BusinessParser()
    
    for i, description in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试用例 {i}")
        print(f"{'='*60}")
        print(f"描述: {description}")
        
        model = parser.parse(description)
        print(model.summary())
        print(f"实体详情:")
        for e in model.entities:
            print(f"  - {e.name} ({e.entity_type.value})")
        print(f"流程详情:")
        for p in model.processes:
            print(f"  - {p.name}: {' -> '.join(p.steps[:3])}...")
        print(f"规则详情:")
        for r in model.rules:
            print(f"  - {r.name} ({r.rule_type.value})")
