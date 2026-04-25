"""
意图分类器 - 对意图进行细粒度分类和优先级评估
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import re


class IntentPriority(Enum):
    """意图优先级"""
    P0_CRITICAL = 0  # 关键任务
    P1_HIGH = 1      # 高优先级
    P2_MEDIUM = 2    # 中优先级
    P3_LOW = 3       # 低优先级


class IntentComplexity(Enum):
    """意图复杂度"""
    TRIVIAL = 0      # 简单（单行代码）
    SIMPLE = 1       # 简单（单个函数）
    MODERATE = 2     # 中等（多个函数/类）
    COMPLEX = 3      # 复杂（模块级别）
    VERY_COMPLEX = 4 # 非常复杂（系统级别）


@dataclass
class IntentCategory:
    """意图分类结果"""
    category: str                           # 分类名称
    subcategory: Optional[str] = None       # 子分类
    priority: IntentPriority = IntentPriority.P2_MEDIUM
    complexity: IntentComplexity = IntentComplexity.MODERATE
    estimated_tokens: int = 0               # 预估token消耗
    required_capabilities: List[str] = field(default_factory=list)  # 所需能力
    suggested_model: str = "auto"           # 建议模型


class IntentClassifier:
    """
    意图分类器
    
    功能：
    1. 意图优先级评估
    2. 复杂度评估
    3. 资源预估
    4. 能力需求匹配
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._init_category_rules()
        
    def _init_category_rules(self):
        """初始化分类规则"""
        # 优先级规则
        self.priority_rules = {
            'urgent': IntentPriority.P0_CRITICAL,
            'critical': IntentPriority.P0_CRITICAL,
            '立即': IntentPriority.P0_CRITICAL,
            '紧急': IntentPriority.P0_CRITICAL,
            'important': IntentPriority.P1_HIGH,
            '重要': IntentPriority.P1_HIGH,
        }
        
        # 复杂度关键词
        self.complexity_keywords = {
            IntentComplexity.TRIVIAL: ['一行', 'one line', '单行', '简单'],
            IntentComplexity.SIMPLE: ['函数', 'function', 'method', 'def ', 'func'],
            IntentComplexity.MODERATE: ['类', 'class', '模块', 'module', '文件'],
            IntentComplexity.COMPLEX: ['系统', 'system', '架构', 'architecture', '重写'],
            IntentComplexity.VERY_COMPLEX: ['整个', '完整', '全套', 'entire', 'full'],
        }
        
        # 能力需求映射
        self.capability_mapping = {
            'code_generation': ['code_write', 'syntax_check'],
            'code_review': ['code_analysis', 'best_practices'],
            'bug_fix': ['debugging', 'error_analysis'],
            'refactoring': ['code_analysis', 'pattern_recognition'],
            'query': ['knowledge_search', 'context_retrieval'],
            'execution': ['tool_execution', 'system_command'],
        }
        
    def classify(self, intent: 'ParsedIntent') -> IntentCategory:
        """
        对意图进行分类
        
        Args:
            intent: 解析后的意图对象
            
        Returns:
            IntentCategory: 分类结果
        """
        # 1. 确定优先级
        priority = self._assess_priority(intent)
        
        # 2. 评估复杂度
        complexity = self._assess_complexity(intent)
        
        # 3. 预估资源
        estimated_tokens = self._estimate_tokens(intent, complexity)
        
        # 4. 确定所需能力
        required_capabilities = self._determine_capabilities(intent.intent_type)
        
        # 5. 选择模型
        suggested_model = self._select_model(complexity, estimated_tokens)
        
        # 6. 确定分类名称
        category = self._get_category_name(intent)
        
        return IntentCategory(
            category=category,
            priority=priority,
            complexity=complexity,
            estimated_tokens=estimated_tokens,
            required_capabilities=required_capabilities,
            suggested_model=suggested_model
        )
    
    def _assess_priority(self, intent: 'ParsedIntent') -> IntentPriority:
        """评估优先级"""
        text = intent.raw_text.lower()
        
        for keyword, priority in self.priority_rules.items():
            if keyword in text:
                return priority
                
        # 根据意图类型默认优先级
        type_priority_map = {
            'BUG_FIX': IntentPriority.P0_CRITICAL,
            'CODE_GENERATION': IntentPriority.P1_HIGH,
            'CODE_REVIEW': IntentPriority.P2_MEDIUM,
            'QUERY': IntentPriority.P3_LOW,
        }
        
        return type_priority_map.get(intent.intent_type.value.upper(), IntentPriority.P2_MEDIUM)
    
    def _assess_complexity(self, intent: 'ParsedIntent') -> IntentComplexity:
        """评估复杂度"""
        text = intent.raw_text.lower()
        
        # 检查复杂度关键词
        for complexity, keywords in self.complexity_keywords.items():
            if any(kw.lower() in text for kw in keywords):
                return complexity
                
        # 根据意图类型和实体数量推断
        entity_count = len(intent.entities)
        if entity_count == 0:
            return IntentComplexity.SIMPLE
        elif entity_count <= 2:
            return IntentComplexity.MODERATE
        else:
            return IntentComplexity.COMPLEX
            
    def _estimate_tokens(self, intent: 'ParsedIntent', complexity: IntentComplexity) -> int:
        """预估Token消耗"""
        base_tokens = len(intent.raw_text) // 4  # 粗略估算
        
        # 根据复杂度加成
        complexity_multiplier = {
            IntentComplexity.TRIVIAL: 0.5,
            IntentComplexity.SIMPLE: 1.0,
            IntentComplexity.MODERATE: 2.0,
            IntentComplexity.COMPLEX: 4.0,
            IntentComplexity.VERY_COMPLEX: 8.0,
        }
        
        return int(base_tokens * complexity_multiplier.get(complexity, 1.0))
    
    def _determine_capabilities(self, intent_type: 'IntentType') -> List[str]:
        """确定所需能力"""
        return self.capability_mapping.get(intent_type.value, ['general'])
    
    def _select_model(self, complexity: IntentComplexity, tokens: int) -> str:
        """选择合适的模型"""
        # 基于复杂度和token消耗选择模型
        if complexity == IntentComplexity.TRIVIAL or tokens < 500:
            return "fast-model"
        elif complexity in [IntentComplexity.SIMPLE, IntentComplexity.MODERATE] or tokens < 2000:
            return "standard-model"
        elif complexity == IntentComplexity.COMPLEX or tokens < 8000:
            return "advanced-model"
        else:
            return "ultra-model"
    
    def _get_category_name(self, intent: 'ParsedIntent') -> str:
        """获取分类名称"""
        return f"{intent.intent_type.value}"
