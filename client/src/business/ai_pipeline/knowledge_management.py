"""
知识管理体系 - 架构决策记录与代码模式库

核心功能：
1. 架构决策记录：记录每个技术决策的原因
2. 代码模式库：积累团队的最佳实践模式
3. 故障知识库：记录问题和解决方案
4. 业务规则库：领域逻辑和业务规则
5. 持续学习机制：从成功案例提取通用模式
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


@dataclass
class ArchitectureDecision:
    """架构决策记录"""
    id: str
    title: str
    context: str
    decision: str
    rationale: str
    alternatives: List[str] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    status: str = "accepted"
    author: Optional[str] = None
    date: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


@dataclass
class CodePattern:
    """代码模式"""
    id: str
    name: str
    description: str
    pattern_type: str
    code_example: str
    context: str
    benefits: List[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 0.0


@dataclass
class BugRecord:
    """故障记录"""
    id: str
    title: str
    description: str
    error_type: str
    stack_trace: Optional[str] = None
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    status: str = "resolved"
    severity: str = "medium"
    date: datetime = field(default_factory=datetime.now)


@dataclass
class BusinessRule:
    """业务规则"""
    id: str
    name: str
    description: str
    rule_type: str
    expression: Optional[str] = None
    priority: int = 0
    effective_date: Optional[datetime] = None


class KnowledgeManagement:
    """
    知识管理体系
    
    核心特性：
    1. 架构决策记录（ADR）
    2. 代码模式库
    3. 故障知识库
    4. 业务规则库
    5. 持续学习机制
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/knowledge"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._decisions: Dict[str, ArchitectureDecision] = {}
        self._patterns: Dict[str, CodePattern] = {}
        self._bugs: Dict[str, BugRecord] = {}
        self._rules: Dict[str, BusinessRule] = {}
        
        self._load_knowledge()

    def _load_knowledge(self):
        """加载所有知识库"""
        self._decisions = self._load_objects("decisions", ArchitectureDecision)
        self._patterns = self._load_objects("patterns", CodePattern)
        self._bugs = self._load_objects("bugs", BugRecord)
        self._rules = self._load_objects("rules", BusinessRule)

    def _load_objects(self, dir_name: str, cls):
        """从目录加载对象"""
        obj_dir = self._storage_path / dir_name
        obj_dir.mkdir(exist_ok=True)
        
        objects = {}
        for filepath in obj_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    obj = self._deserialize_object(data, cls)
                    objects[obj.id] = obj
            except Exception as e:
                print(f"加载 {dir_name} 失败 {filepath}: {e}")
        
        return objects

    def _save_objects(self, dir_name: str, objects: Dict[str, Any]):
        """保存对象到目录"""
        obj_dir = self._storage_path / dir_name
        obj_dir.mkdir(exist_ok=True)
        
        for obj_id, obj in objects.items():
            filepath = obj_dir / f"{obj_id}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._serialize_object(obj), f, ensure_ascii=False, indent=2)

    def _serialize_object(self, obj) -> Dict[str, Any]:
        """序列化对象"""
        data = obj.__dict__.copy()
        
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        
        return data

    def _deserialize_object(self, data: Dict[str, Any], cls):
        """反序列化对象"""
        for key, value in data.items():
            if key in ["date", "effective_date"] and isinstance(value, str):
                data[key] = datetime.fromisoformat(value)
        
        return cls(**data)

    async def record_decision(self, decision: ArchitectureDecision):
        """记录架构决策"""
        print(f"📝 记录架构决策: {decision.title}")
        
        self._decisions[decision.id] = decision
        self._save_objects("decisions", self._decisions)

    async def generate_decision(self, context: str, decision_options: List[str]) -> ArchitectureDecision:
        """生成架构决策记录"""
        prompt = f"""
作为一个经验丰富的架构师，帮助记录以下架构决策。

决策背景: {context}

可选方案:
{chr(10).join(f"{i+1}. {opt}" for i, opt in enumerate(decision_options))}

输出格式（JSON）:
{{
    "id": "ADR-XXX",
    "title": "决策标题",
    "context": "决策背景",
    "decision": "最终决策",
    "rationale": "决策理由",
    "alternatives": ["方案1", "方案2"],
    "consequences": ["后果1", "后果2"],
    "tags": ["标签1", "标签2"]
}}

要求：
1. 分析每个可选方案的优缺点
2. 给出最终决策
3. 说明决策理由
4. 列出可能的后果
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.3
        )

        try:
            result = json.loads(response)
            
            decision = ArchitectureDecision(
                id=result["id"],
                title=result["title"],
                context=result["context"],
                decision=result["decision"],
                rationale=result["rationale"],
                alternatives=result.get("alternatives", []),
                consequences=result.get("consequences", []),
                tags=result.get("tags", [])
            )
            
            await self.record_decision(decision)
            return decision
            
        except Exception as e:
            print(f"❌ 决策记录生成失败: {e}")
            return self._fallback_decision(context)

    def _fallback_decision(self, context: str) -> ArchitectureDecision:
        """兜底决策记录"""
        return ArchitectureDecision(
            id=f"ADR-{int(datetime.now().timestamp())}",
            title=f"架构决策: {context[:30]}",
            context=context,
            decision="待评估",
            rationale="需要进一步分析",
            alternatives=[],
            consequences=[]
        )

    async def add_code_pattern(self, pattern: CodePattern):
        """添加代码模式"""
        print(f"📚 添加代码模式: {pattern.name}")
        
        self._patterns[pattern.id] = pattern
        self._save_objects("patterns", self._patterns)

    async def learn_pattern(self, code: str, context: str = ""):
        """从代码中学习模式"""
        print(f"🔍 学习代码模式")
        
        prompt = f"""
作为一个代码模式识别专家，分析以下代码并提取设计模式。

代码:
```python
{code}
```

上下文: {context}

输出格式（JSON）:
{{
    "id": "PATTERN-XXX",
    "name": "模式名称",
    "description": "模式描述",
    "pattern_type": "模式类型（如: Factory, Singleton, Strategy等）",
    "code_example": "代码示例",
    "context": "适用场景",
    "benefits": ["好处1", "好处2"]
}}

要求：
1. 识别代码中的设计模式
2. 描述模式的适用场景
3. 列出使用该模式的好处
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            pattern = CodePattern(
                id=result["id"],
                name=result["name"],
                description=result["description"],
                pattern_type=result["pattern_type"],
                code_example=result.get("code_example", code[:200]),
                context=result.get("context", context),
                benefits=result.get("benefits", [])
            )
            
            await self.add_code_pattern(pattern)
            return pattern
            
        except Exception as e:
            print(f"❌ 模式学习失败: {e}")
            return None

    async def record_bug(self, bug: BugRecord):
        """记录故障"""
        print(f"🔴 记录故障: {bug.title}")
        
        self._bugs[bug.id] = bug
        self._save_objects("bugs", self._bugs)

    async def analyze_bug(self, error_message: str, stack_trace: str = "") -> BugRecord:
        """分析故障并记录"""
        prompt = f"""
作为一个专业的调试工程师，分析以下故障并提供解决方案。

错误信息: {error_message}
堆栈追踪: {stack_trace}

输出格式（JSON）:
{{
    "id": "BUG-XXX",
    "title": "故障标题",
    "description": "故障描述",
    "error_type": "错误类型",
    "root_cause": "根本原因",
    "solution": "解决方案",
    "severity": "critical|high|medium|low"
}}

要求：
1. 识别错误类型
2. 分析根本原因
3. 提供解决方案
4. 评估严重程度
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            bug = BugRecord(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                error_type=result.get("error_type", "Unknown"),
                stack_trace=stack_trace,
                root_cause=result.get("root_cause"),
                solution=result.get("solution"),
                severity=result.get("severity", "medium")
            )
            
            await self.record_bug(bug)
            return bug
            
        except Exception as e:
            print(f"❌ 故障分析失败: {e}")
            return BugRecord(
                id=f"BUG-{int(datetime.now().timestamp())}",
                title=f"故障: {error_message[:30]}",
                description=error_message,
                error_type="Unknown",
                severity="medium"
            )

    async def add_business_rule(self, rule: BusinessRule):
        """添加业务规则"""
        print(f"📋 添加业务规则: {rule.name}")
        
        self._rules[rule.id] = rule
        self._save_objects("rules", self._rules)

    async def extract_rules(self, requirements: str) -> List[BusinessRule]:
        """从需求中提取业务规则"""
        prompt = f"""
作为一个业务分析师，从以下需求中提取业务规则。

需求: {requirements}

输出格式（JSON）:
{{
    "rules": [
        {{
            "id": "RULE-XXX",
            "name": "规则名称",
            "description": "规则描述",
            "rule_type": "规则类型",
            "expression": "规则表达式（可选）",
            "priority": 1
        }}
    ]
}}

要求：
1. 识别所有业务规则
2. 分类规则类型
3. 设置优先级
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            rules = []
            for rule_data in result.get("rules", []):
                rule = BusinessRule(
                    id=rule_data["id"],
                    name=rule_data["name"],
                    description=rule_data["description"],
                    rule_type=rule_data.get("rule_type", "business"),
                    expression=rule_data.get("expression"),
                    priority=rule_data.get("priority", 0)
                )
                await self.add_business_rule(rule)
                rules.append(rule)
            
            return rules
            
        except Exception as e:
            print(f"❌ 规则提取失败: {e}")
            return []

    def search_patterns(self, query: str) -> List[CodePattern]:
        """搜索代码模式"""
        results = []
        for pattern in self._patterns.values():
            if query.lower() in pattern.name.lower() or query.lower() in pattern.description.lower():
                results.append(pattern)
        return results

    def search_decisions(self, query: str) -> List[ArchitectureDecision]:
        """搜索架构决策"""
        results = []
        for decision in self._decisions.values():
            if query.lower() in decision.title.lower() or query.lower() in decision.context.lower():
                results.append(decision)
        return results

    def get_similar_bugs(self, error_message: str) -> List[BugRecord]:
        """查找相似故障"""
        results = []
        for bug in self._bugs.values():
            if any(keyword in error_message.lower() for keyword in bug.title.lower().split()):
                results.append(bug)
        return results

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        return {
            "decisions": len(self._decisions),
            "patterns": len(self._patterns),
            "bugs": len(self._bugs),
            "rules": len(self._rules)
        }


def get_knowledge_management() -> KnowledgeManagement:
    """获取知识管理体系单例"""
    global _knowledge_manager_instance
    if _knowledge_manager_instance is None:
        _knowledge_manager_instance = KnowledgeManagement()
    return _knowledge_manager_instance


_knowledge_manager_instance = None