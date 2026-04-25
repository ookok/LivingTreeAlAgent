"""
意图验证器 - 验证意图的完整性和可行性
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ValidationLevel(Enum):
    """验证级别"""
    STRICT = "strict"      # 严格验证
    NORMAL = "normal"     # 普通验证
    LENIENT = "lenient"   # 宽松验证


@dataclass
class ValidationError:
    """验证错误"""
    field: str
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def add_error(self, field: str, message: str):
        """添加错误"""
        self.errors.append(ValidationError(field=field, message=message))
        self.is_valid = False
        
    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)
        
    def add_suggestion(self, suggestion: str):
        """添加建议"""
        self.suggestions.append(suggestion)


class IntentValidator:
    """
    意图验证器
    
    功能：
    1. 意图完整性验证
    2. 参数合法性验证
    3. 约束条件检查
    4. 可执行性评估
    """
    
    # 意图类型与所需实体映射
    REQUIRED_ENTITIES = {
        'CODE_GENERATION': ['language'],  # 代码生成需要指定语言
        'BUG_FIX': ['error_message', 'file_path'],  # Bug修复需要错误信息和文件
        'REFACTORING': ['file_path'],  # 重构需要文件路径
        'QUERY': ['query_text'],  # 查询需要查询文本
    }
    
    # 意图类型与参数数量约束
    PARAM_CONSTRAINTS = {
        'CODE_GENERATION': {'min': 1, 'max': 10},
        'BUG_FIX': {'min': 1, 'max': 5},
        'QUERY': {'min': 0, 'max': 3},
    }
    
    def __init__(self, level: ValidationLevel = ValidationLevel.NORMAL):
        self.level = level
        
    def validate(self, intent: 'ParsedIntent', category: 'IntentCategory') -> ValidationResult:
        """
        验证意图
        
        Args:
            intent: 解析后的意图
            category: 意图分类
            
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(is_valid=True)
        
        # 1. 基本验证
        self._validate_basic(intent, result)
        
        # 2. 实体验证
        self._validate_entities(intent, result)
        
        # 3. 参数验证
        self._validate_parameters(intent, result)
        
        # 4. 约束验证
        self._validate_constraints(intent, result)
        
        # 5. 可执行性评估
        self._validate_executability(intent, category, result)
        
        # 严格模式下检查置信度
        if self.level == ValidationLevel.STRICT and intent.confidence < 0.5:
            result.add_error("confidence", f"置信度过低: {intent.confidence}")
            
        return result
    
    def _validate_basic(self, intent: 'ParsedIntent', result: ValidationResult):
        """验证基本字段"""
        if not intent.raw_text or len(intent.raw_text.strip()) == 0:
            result.add_error("raw_text", "意图文本不能为空")
            
        if len(intent.raw_text) > 10000:
            result.add_warning("意图文本过长，可能影响处理效率")
            
        if intent.intent_type.value == 'UNKNOWN':
            if self.level == ValidationLevel.STRICT:
                result.add_error("intent_type", "无法识别意图类型")
            else:
                result.add_warning("意图类型不明确，建议明确表述")
                
    def _validate_entities(self, intent: 'ParsedIntent', result: ValidationResult):
        """验证实体"""
        intent_type_str = intent.intent_type.value.upper()
        required = self.REQUIRED_ENTITIES.get(intent_type_str, [])
        
        for req_entity in required:
            if req_entity == 'language':
                if 'language' not in intent.parameters:
                    result.add_error("language", "代码生成需要指定编程语言")
            elif req_entity == 'error_message':
                if not intent.parameters.get('error_message'):
                    result.add_error("error_message", "Bug修复需要提供错误信息")
            elif req_entity == 'file_path':
                if 'file_paths' not in intent.entities or not intent.entities['file_paths']:
                    result.add_error("file_path", "需要提供文件路径")
            elif req_entity == 'query_text':
                if len(intent.raw_text) < 3:
                    result.add_error("query_text", "查询内容过短")
                    
    def _validate_parameters(self, intent: 'ParsedIntent', result: ValidationResult):
        """验证参数"""
        param_count = len(intent.parameters)
        intent_type_str = intent.intent_type.value.upper()
        constraints = self.PARAM_CONSTRAINTS.get(intent_type_str, {'min': 0, 'max': 10})
        
        if param_count < constraints['min']:
            result.add_warning(f"参数数量较少，可能需要补充更多信息")
            
        if param_count > constraints['max']:
            result.add_warning(f"参数数量过多，可能存在冗余")
            
        # 检查参数合法性
        for key, value in intent.parameters.items():
            if not self._is_valid_parameter(key, value):
                result.add_error(f"param.{key}", f"参数值无效: {value}")
                
    def _validate_constraints(self, intent: 'ParsedIntent', result: ValidationResult):
        """验证约束条件"""
        constraints = intent.constraints
        
        # 检查冲突的约束
        has_performance = any('performance' in c for c in constraints)
        has_security = any('security' in c for c in constraints)
        
        if has_performance and has_security:
            result.add_warning("性能和安全性约束可能存在冲突，需要权衡")
            
        # 检查不合理的约束
        for constraint in constraints:
            if ':' not in constraint:
                result.add_warning(f"约束格式不规范: {constraint}")
                
    def _validate_executability(self, intent: 'ParsedIntent', 
                                category: 'IntentCategory', 
                                result: ValidationResult):
        """验证可执行性"""
        # 检查复杂度与资源的匹配
        if category.complexity.value >= 3:  # COMPLEX or higher
            if category.estimated_tokens > 10000:
                result.add_warning("任务复杂度过高，可能需要拆分为多个子任务")
                result.add_suggestion("建议使用任务分解器将任务拆分")
                
        # 检查所需能力是否满足
        if not category.required_capabilities:
            result.add_warning("未识别到所需能力，可能无法正确执行")
            
        # 检查建议的模型是否合适
        if category.suggested_model == "ultra-model" and self.level == ValidationLevel.LENIENT:
            result.add_warning("建议使用超大规模模型，成本较高")
            result.add_suggestion("考虑是否可以使用较小规模的模型")
            
    def _is_valid_parameter(self, key: str, value: Any) -> bool:
        """检查参数是否有效"""
        if value is None:
            return False
            
        if isinstance(value, str) and len(value) > 1000:
            return False
            
        return True
    
    def validate_and_fix(self, intent: 'ParsedIntent', 
                         category: 'IntentCategory') -> Tuple[ValidationResult, 'ParsedIntent']:
        """
        验证并尝试修复意图
        
        Returns:
            (验证结果, 修复后的意图)
        """
        result = self.validate(intent, category)
        
        # 自动修复一些简单问题
        fixed_intent = intent
        
        # 修复空实体
        if not intent.entities:
            fixed_intent.entities = {}
            
        # 修复空参数
        if not intent.parameters:
            fixed_intent.parameters = {}
            
        return result, fixed_intent
