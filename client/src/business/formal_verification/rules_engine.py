"""
业务规则引擎

实现业务规则的定义和执行。
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class BusinessRule:
    """业务规则"""
    id: str
    name: str
    condition: str  # Python表达式
    description: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    severity: str = "medium"  # high, medium, low
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "actions": self.actions,
            "severity": self.severity,
            "enabled": self.enabled,
        }


@dataclass
class RuleExecutionResult:
    """规则执行结果"""
    rule_id: str
    rule_name: str
    triggered: bool
    actions_executed: int = 0
    errors: List[str] = field(default_factory=list)


class RulesEngine:
    """
    业务规则引擎
    
    核心能力：
    1. 规则定义和注册
    2. 规则执行
    3. 规则冲突检测
    """
    
    def __init__(self):
        self.rules: List[BusinessRule] = []
    
    def add_rule(self, rule: BusinessRule):
        """添加规则"""
        if not any(r.id == rule.id for r in self.rules):
            self.rules.append(rule)
            logger.info(f"Rule added: {rule.id}")
        else:
            logger.warning(f"Rule already exists: {rule.id}")
    
    def remove_rule(self, rule_id: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.id != rule_id]
    
    def execute_rules(self, context: Dict[str, Any]) -> List[RuleExecutionResult]:
        """
        执行所有规则
        
        Args:
            context: 执行上下文
        
        Returns:
            执行结果列表
        """
        results = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            result = self.execute_rule(rule, context)
            results.append(result)
            
            if result.triggered:
                logger.info(f"Rule triggered: {rule.id}")
        
        return results
    
    def execute_rule(self, rule: BusinessRule, context: Dict[str, Any]) -> RuleExecutionResult:
        """
        执行单个规则
        
        Args:
            rule: 规则
            context: 执行上下文
        
        Returns:
            RuleExecutionResult
        """
        try:
            # 评估条件
            condition_result = self._evaluate_condition(rule.condition, context)
            
            if condition_result:
                # 执行动作
                executed_count = self._execute_actions(rule.actions, context)
                return RuleExecutionResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered=True,
                    actions_executed=executed_count,
                )
            else:
                return RuleExecutionResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered=False,
                )
        
        except Exception as e:
            logger.error(f"Rule execution failed: {e}")
            return RuleExecutionResult(
                rule_id=rule.id,
                rule_name=rule.name,
                triggered=False,
                errors=[str(e)],
            )
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        评估条件表达式
        
        Args:
            condition: 条件表达式
            context: 上下文数据
        
        Returns:
            条件是否成立
        """
        # 创建安全的执行环境
        safe_globals = {
            '__builtins__': {},
            'True': True,
            'False': False,
            'None': None,
        }
        
        # 将上下文数据添加到局部变量
        safe_locals = context.copy()
        
        try:
            # 安全评估表达式
            import ast
            tree = ast.parse(condition, mode='eval')
            
            # 检查危险操作
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call, ast.Subscript)):
                    raise ValueError("不允许的操作")
            
            result = eval(compile(tree, '<string>', 'eval'), safe_globals, safe_locals)
            return bool(result)
        
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False
    
    def _execute_actions(self, actions: List[str], context: Dict[str, Any]) -> int:
        """
        执行动作列表
        
        Args:
            actions: 动作列表
            context: 上下文数据
        
        Returns:
            成功执行的动作数量
        """
        executed = 0
        
        for action in actions:
            try:
                # 简单的动作执行：设置上下文变量
                if action.startswith("set:"):
                    parts = action[4:].split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # 尝试评估值表达式
                        try:
                            import ast
                            val_tree = ast.parse(value, mode='eval')
                            context[key] = eval(compile(val_tree, '<string>', 'eval'), {}, context)
                        except:
                            context[key] = value
                        executed += 1
                
                elif action.startswith("log:"):
                    message = action[4:]
                    logger.info(f"Rule action: {message}")
                    executed += 1
                
                elif action.startswith("warn:"):
                    message = action[5:]
                    logger.warning(f"Rule warning: {message}")
                    executed += 1
                
                else:
                    logger.warning(f"Unknown action type: {action}")
            
            except Exception as e:
                logger.error(f"Action execution failed: {e}")
        
        return executed
    
    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """
        检测规则冲突
        
        Returns:
            冲突列表
        """
        conflicts = []
        
        for i, rule1 in enumerate(self.rules):
            for j, rule2 in enumerate(self.rules):
                if i >= j:
                    continue
                
                # 检查是否可能冲突（条件相似但动作不同）
                if self._rules_might_conflict(rule1, rule2):
                    conflicts.append({
                        "rule1": rule1.id,
                        "rule2": rule2.id,
                        "reason": "可能存在冲突",
                    })
        
        return conflicts
    
    def _rules_might_conflict(self, rule1: BusinessRule, rule2: BusinessRule) -> bool:
        """
        判断两个规则是否可能冲突
        
        Args:
            rule1: 规则1
            rule2: 规则2
        
        Returns:
            是否可能冲突
        """
        # 简单的冲突检测：检查条件是否有重叠
        # 实际应用中可以使用更复杂的逻辑
        cond1 = rule1.condition.lower()
        cond2 = rule2.condition.lower()
        
        # 如果条件包含相同的变量引用，可能存在冲突
        shared_vars = set()
        for var in rule1.condition.split():
            if var.isidentifier():
                shared_vars.add(var)
        
        for var in rule2.condition.split():
            if var.isidentifier() and var in shared_vars:
                return True
        
        return False


# 预设规则库
class EIA_Rules:
    """环评业务规则"""
    
    @staticmethod
    def get_rules() -> List[BusinessRule]:
        """获取环评规则"""
        return [
            BusinessRule(
                id="eia_emission_exceed",
                name="排放量超标预警",
                description="当实际排放量超过限值时触发",
                condition="actual_emission > emission_limit",
                actions=[
                    "set:status='warning'",
                    "warn:排放量超过限值",
                ],
                severity="high",
            ),
            BusinessRule(
                id="eia_efficiency_low",
                name="处理效率过低",
                description="当处理效率低于60%时触发",
                condition="treatment_efficiency < 60",
                actions=[
                    "set:efficiency_warning=True",
                    "warn:处理效率低于60%，建议检查设备",
                ],
                severity="medium",
            ),
            BusinessRule(
                id="eia_data_incomplete",
                name="数据不完整",
                description="当关键数据缺失时触发",
                condition="project_name is None or project_name == ''",
                actions=[
                    "set:status='incomplete'",
                    "warn:项目名称缺失",
                ],
                severity="high",
            ),
        ]


class FinancialRules:
    """财务分析规则"""
    
    @staticmethod
    def get_rules() -> List[BusinessRule]:
        """获取财务规则"""
        return [
            BusinessRule(
                id="fin_npv_negative",
                name="NPV为负",
                description="当净现值为负时触发",
                condition="npv < 0",
                actions=[
                    "set:feasible=False",
                    "warn:项目净现值为负，需重新评估",
                ],
                severity="high",
            ),
            BusinessRule(
                id="fin_irr_low",
                name="IRR过低",
                description="当内部收益率低于基准收益率时触发",
                condition="irr < benchmark_rate",
                actions=[
                    "set:irr_warning=True",
                    "warn:内部收益率低于基准收益率",
                ],
                severity="medium",
            ),
            BusinessRule(
                id="fin_payback_long",
                name="回收期过长",
                description="当投资回收期超过预期时触发",
                condition="payback_period > expected_payback",
                actions=[
                    "set:payback_warning=True",
                    "warn:投资回收期超过预期",
                ],
                severity="medium",
            ),
        ]