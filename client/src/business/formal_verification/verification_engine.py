"""
形式化验证引擎 - 核心实现

实现约束验证、数值范围检查、公式验证等功能。
"""
import ast
import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Callable

import logging

logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    """约束类型"""
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="
    BETWEEN = "between"
    IN_SET = "in_set"
    REGEX = "regex"
    REQUIRED = "required"


class VerificationStatus(Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class Constraint:
    """约束定义"""
    id: str
    name: str
    type: ConstraintType
    left_operand: str  # 字段名或表达式
    right_operand: Union[str, int, float, List]
    description: Optional[str] = None
    severity: str = "high"  # high, medium, low
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "left_operand": self.left_operand,
            "right_operand": self.right_operand,
            "description": self.description,
            "severity": self.severity,
            "error_message": self.error_message,
        }


@dataclass
class VerificationResult:
    """验证结果"""
    constraint_id: str
    constraint_name: str
    status: VerificationStatus
    message: str = ""
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    severity: str = "high"


@dataclass
class VerificationReport:
    """验证报告"""
    success: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    results: List[VerificationResult] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        """通过率"""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100


class FormalVerifier:
    """
    形式化验证器
    
    核心能力：
    1. 约束验证
    2. 数值范围检查
    3. 公式验证
    4. 一致性检查
    """
    
    def __init__(self):
        self.operators = {
            ConstraintType.GREATER_THAN: operator.gt,
            ConstraintType.GREATER_EQUAL: operator.ge,
            ConstraintType.LESS_THAN: operator.lt,
            ConstraintType.LESS_EQUAL: operator.le,
            ConstraintType.EQUAL: operator.eq,
            ConstraintType.NOT_EQUAL: operator.ne,
        }
    
    def verify_constraints(self, data: Dict[str, Any], constraints: List[Constraint]) -> VerificationReport:
        """
        验证一组约束
        
        Args:
            data: 待验证的数据
            constraints: 约束列表
        
        Returns:
            VerificationReport
        """
        results = []
        passed = 0
        failed = 0
        warnings = 0
        
        for constraint in constraints:
            result = self.verify_constraint(data, constraint)
            results.append(result)
            
            if result.status == VerificationStatus.PASSED:
                passed += 1
            elif result.status == VerificationStatus.FAILED:
                failed += 1
            elif result.status == VerificationStatus.WARNING:
                warnings += 1
        
        return VerificationReport(
            success=failed == 0,
            total_checks=len(constraints),
            passed_checks=passed,
            failed_checks=failed,
            warnings=warnings,
            results=results,
        )
    
    def verify_constraint(self, data: Dict[str, Any], constraint: Constraint) -> VerificationResult:
        """
        验证单个约束
        
        Args:
            data: 数据字典
            constraint: 约束
        
        Returns:
            VerificationResult
        """
        try:
            # 获取左操作数的值
            left_value = self._evaluate_expression(constraint.left_operand, data)
            
            if constraint.type == ConstraintType.REQUIRED:
                return self._verify_required(left_value, constraint)
            
            # 获取右操作数的值（可能是字段引用或常量）
            right_value = self._evaluate_expression(constraint.right_operand, data)
            
            # 根据约束类型进行验证
            if constraint.type in self.operators:
                return self._verify_comparison(left_value, right_value, constraint)
            elif constraint.type == ConstraintType.BETWEEN:
                return self._verify_between(left_value, right_value, constraint)
            elif constraint.type == ConstraintType.IN_SET:
                return self._verify_in_set(left_value, right_value, constraint)
            elif constraint.type == ConstraintType.REGEX:
                return self._verify_regex(left_value, right_value, constraint)
            
        except Exception as e:
            logger.error(f"Constraint verification failed: {e}")
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.UNKNOWN,
                message=f"验证过程出错: {str(e)}",
                severity=constraint.severity,
            )
        
        return VerificationResult(
            constraint_id=constraint.id,
            constraint_name=constraint.name,
            status=VerificationStatus.UNKNOWN,
            message=f"未知约束类型: {constraint.type}",
            severity=constraint.severity,
        )
    
    def _evaluate_expression(self, expr: Union[str, int, float, List], data: Dict[str, Any]) -> Any:
        """
        评估表达式
        
        Args:
            expr: 表达式（可以是字段名、数学表达式或常量）
            data: 数据字典
        
        Returns:
            表达式的值
        """
        if isinstance(expr, (int, float, list)):
            return expr
        
        if isinstance(expr, str):
            # 尝试作为字段名获取
            if expr in data:
                return data[expr]
            
            # 尝试作为简单数学表达式评估
            try:
                return self._eval_math_expression(expr, data)
            except:
                pass
        
        return expr
    
    def _eval_math_expression(self, expr: str, data: Dict[str, Any]) -> float:
        """
        安全地评估数学表达式
        
        Args:
            expr: 数学表达式
            data: 数据字典（用于变量替换）
        
        Returns:
            计算结果
        """
        # 创建安全的全局命名空间
        safe_globals = {
            '__builtins__': {},
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'pow': pow,
        }
        
        # 将数据变量添加到局部命名空间
        safe_locals = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                safe_locals[key] = value
        
        # 替换表达式中的变量引用
        processed_expr = expr
        for key in data:
            if isinstance(data[key], (int, float)) and key in processed_expr:
                processed_expr = processed_expr.replace(key, str(data[key]))
        
        # 使用ast进行安全评估
        try:
            tree = ast.parse(processed_expr, mode='eval')
            
            # 检查是否有危险操作
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                    raise ValueError("不允许的表达式操作")
            
            return eval(compile(tree, '<string>', 'eval'), safe_globals, safe_locals)
        except Exception as e:
            raise ValueError(f"表达式评估失败: {e}")
    
    def _verify_required(self, value: Any, constraint: Constraint) -> VerificationResult:
        """验证必填字段"""
        if value is None or value == "" or value == [] or value == {}:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.FAILED,
                message=constraint.error_message or f"字段 '{constraint.left_operand}' 为必填项",
                severity=constraint.severity,
            )
        return VerificationResult(
            constraint_id=constraint.id,
            constraint_name=constraint.name,
            status=VerificationStatus.PASSED,
            message=f"字段 '{constraint.left_operand}' 已填写",
        )
    
    def _verify_comparison(self, left: Any, right: Any, constraint: Constraint) -> VerificationResult:
        """验证比较约束"""
        op = self.operators.get(constraint.type)
        if op is None:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.UNKNOWN,
                message=f"未知操作符: {constraint.type}",
                severity=constraint.severity,
            )
        
        try:
            result = op(left, right)
            if result:
                return VerificationResult(
                    constraint_id=constraint.id,
                    constraint_name=constraint.name,
                    status=VerificationStatus.PASSED,
                    message=f"{left} {constraint.type.value} {right} ✓",
                    actual_value=left,
                    expected_value=right,
                    severity=constraint.severity,
                )
            else:
                return VerificationResult(
                    constraint_id=constraint.id,
                    constraint_name=constraint.name,
                    status=VerificationStatus.FAILED,
                    message=constraint.error_message or f"{left} {constraint.type.value} {right} ✗",
                    actual_value=left,
                    expected_value=right,
                    severity=constraint.severity,
                )
        except (TypeError, ValueError) as e:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.WARNING,
                message=f"比较失败: {e}",
                severity=constraint.severity,
            )
    
    def _verify_between(self, value: Any, bounds: List, constraint: Constraint) -> VerificationResult:
        """验证值是否在范围内"""
        if not isinstance(bounds, list) or len(bounds) != 2:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.UNKNOWN,
                message="BETWEEN约束需要两个边界值",
                severity=constraint.severity,
            )
        
        min_val, max_val = bounds
        
        if min_val <= value <= max_val:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.PASSED,
                message=f"{value} 在 [{min_val}, {max_val}] 范围内 ✓",
                actual_value=value,
                expected_value=bounds,
                severity=constraint.severity,
            )
        else:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.FAILED,
                message=constraint.error_message or f"{value} 不在 [{min_val}, {max_val}] 范围内 ✗",
                actual_value=value,
                expected_value=bounds,
                severity=constraint.severity,
            )
    
    def _verify_in_set(self, value: Any, allowed_set: List, constraint: Constraint) -> VerificationResult:
        """验证值是否在允许的集合中"""
        if not isinstance(allowed_set, list):
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.UNKNOWN,
                message="IN_SET约束需要列表值",
                severity=constraint.severity,
            )
        
        if value in allowed_set:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.PASSED,
                message=f"{value} 在允许集合中 ✓",
                actual_value=value,
                expected_value=allowed_set,
                severity=constraint.severity,
            )
        else:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.FAILED,
                message=constraint.error_message or f"{value} 不在允许集合中，允许值: {allowed_set}",
                actual_value=value,
                expected_value=allowed_set,
                severity=constraint.severity,
            )
    
    def _verify_regex(self, value: str, pattern: str, constraint: Constraint) -> VerificationResult:
        """验证字符串是否匹配正则表达式"""
        import re
        
        if not isinstance(value, str):
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.WARNING,
                message="REGEX约束需要字符串值",
                severity=constraint.severity,
            )
        
        if re.match(pattern, value):
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.PASSED,
                message=f"{value} 匹配模式 {pattern} ✓",
                actual_value=value,
                expected_value=pattern,
                severity=constraint.severity,
            )
        else:
            return VerificationResult(
                constraint_id=constraint.id,
                constraint_name=constraint.name,
                status=VerificationStatus.FAILED,
                message=constraint.error_message or f"{value} 不匹配模式 {pattern} ✗",
                actual_value=value,
                expected_value=pattern,
                severity=constraint.severity,
            )
    
    def verify_eia_data(self, eia_data: Dict[str, Any]) -> VerificationReport:
        """
        验证环评数据
        
        Args:
            eia_data: 环评数据
        
        Returns:
            VerificationReport
        """
        constraints = [
            # 排放量约束
            Constraint(
                id="emission_positive",
                name="排放量非负",
                type=ConstraintType.GREATER_EQUAL,
                left_operand="emission_amount",
                right_operand=0,
                description="污染物排放量必须大于等于0",
                severity="high",
            ),
            # 处理效率约束
            Constraint(
                id="efficiency_range",
                name="处理效率范围",
                type=ConstraintType.BETWEEN,
                left_operand="treatment_efficiency",
                right_operand=[0, 100],
                description="处理效率必须在0-100%之间",
                severity="high",
            ),
            # 排放限值约束
            Constraint(
                id="emission_limit",
                name="排放限值",
                type=ConstraintType.LESS_EQUAL,
                left_operand="actual_emission",
                right_operand="emission_limit",
                description="实际排放量必须小于等于排放标准限值",
                severity="high",
            ),
            # 完整性约束
            Constraint(
                id="project_name_required",
                name="项目名称必填",
                type=ConstraintType.REQUIRED,
                left_operand="project_name",
                right_operand=True,
                description="项目名称为必填字段",
                severity="high",
            ),
        ]
        
        return self.verify_constraints(eia_data, constraints)
    
    def verify_financial_data(self, financial_data: Dict[str, Any]) -> VerificationReport:
        """
        验证财务数据
        
        Args:
            financial_data: 财务数据
        
        Returns:
            VerificationReport
        """
        constraints = [
            # 投资约束
            Constraint(
                id="investment_positive",
                name="投资额为正",
                type=ConstraintType.GREATER_THAN,
                left_operand="total_investment",
                right_operand=0,
                description="总投资额必须大于0",
                severity="high",
            ),
            # 现金流约束
            Constraint(
                id="npv_calculation",
                name="NPV逻辑验证",
                type=ConstraintType.GREATER_EQUAL,
                left_operand="npv",
                right_operand=0,
                description="净现值应大于等于0（项目可行）",
                severity="medium",
            ),
            # IRR约束
            Constraint(
                id="irr_range",
                name="IRR范围",
                type=ConstraintType.BETWEEN,
                left_operand="irr",
                right_operand=[0, 100],
                description="内部收益率应在合理范围内",
                severity="high",
            ),
            # 折现率约束
            Constraint(
                id="discount_rate_range",
                name="折现率范围",
                type=ConstraintType.BETWEEN,
                left_operand="discount_rate",
                right_operand=[0, 50],
                description="折现率应在0-50%之间",
                severity="medium",
            ),
        ]
        
        return self.verify_constraints(financial_data, constraints)