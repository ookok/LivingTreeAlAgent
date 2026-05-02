"""
业务规则引擎
============

Full migration from client/src/business/formal_verification/rules_engine.py

实现业务规则的定义和执行。
"""
import logging
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BusinessRule:
    id: str
    name: str
    condition: str
    description: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    severity: str = "medium"
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
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
        if not any(r.id == rule.id for r in self.rules):
            self.rules.append(rule)
            logger.info(f"Rule added: {rule.id}")
        else:
            logger.warning(f"Rule already exists: {rule.id}")

    def remove_rule(self, rule_id: str):
        self.rules = [r for r in self.rules if r.id != rule_id]

    def execute_rules(self, context: Dict[str, Any]) -> List[RuleExecutionResult]:
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
        try:
            condition_result = self._evaluate_condition(rule.condition, context)

            if condition_result:
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
        safe_globals = {
            '__builtins__': {},
            'True': True,
            'False': False,
            'None': None,
        }

        safe_locals = context.copy()

        try:
            tree = ast.parse(condition, mode='eval')

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call, ast.Subscript)):
                    raise ValueError("不允许的操作")

            result = eval(compile(tree, '<string>', 'eval'), safe_globals, safe_locals)
            return bool(result)

        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False

    def _execute_actions(self, actions: List[str], context: Dict[str, Any]) -> int:
        executed = 0

        for action in actions:
            try:
                if action.startswith("set:"):
                    parts = action[4:].split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        try:
                            val_tree = ast.parse(value, mode='eval')
                            context[key] = eval(compile(val_tree, '<string>', 'eval'), {}, context)
                        except Exception:
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
        conflicts = []

        for i, rule1 in enumerate(self.rules):
            for j, rule2 in enumerate(self.rules):
                if i >= j:
                    continue

                if self._rules_might_conflict(rule1, rule2):
                    conflicts.append({
                        "rule1": rule1.id,
                        "rule2": rule2.id,
                        "reason": "可能存在冲突",
                    })

        return conflicts

    def _rules_might_conflict(self, rule1: BusinessRule, rule2: BusinessRule) -> bool:
        cond1 = rule1.condition.lower()
        cond2 = rule2.condition.lower()

        shared_vars = set()
        for var in rule1.condition.split():
            if var.isidentifier():
                shared_vars.add(var)

        for var in rule2.condition.split():
            if var.isidentifier() and var in shared_vars:
                return True

        return False


class EIA_Rules:
    """环评业务规则"""

    @staticmethod
    def get_rules() -> List[BusinessRule]:
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
