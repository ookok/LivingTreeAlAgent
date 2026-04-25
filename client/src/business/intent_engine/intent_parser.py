"""
意图解析器 - 将自然语言解析为结构化意图
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import re


class IntentType(Enum):
    """意图类型枚举"""
    CODE_GENERATION = "code_generation"        # 代码生成
    CODE_COMPLETION = "code_completion"        # 代码补全
    CODE_REVIEW = "code_review"                # 代码审查
    BUG_FIX = "bug_fix"                        # Bug修复
    REFACTORING = "refactoring"                # 重构
    QUERY = "query"                            # 查询
    EXECUTION = "execution"                    # 执行
    EXPLANATION = "explanation"                # 解释
    CREATION = "creation"                      # 创建
    MODIFICATION = "modification"              # 修改
    DELETION = "deletion"                      # 删除
    SEARCH = "search"                         # 搜索
    ANALYSIS = "analysis"                     # 分析
    UNKNOWN = "unknown"                       # 未知


@dataclass
class ParsedIntent:
    """解析后的意图对象"""
    raw_text: str                              # 原始文本
    intent_type: IntentType = IntentType.UNKNOWN  # 意图类型
    entities: Dict[str, Any] = field(default_factory=dict)  # 实体提取
    parameters: Dict[str, Any] = field(default_factory=dict)  # 参数
    confidence: float = 0.0                    # 置信度
    constraints: List[str] = field(default_factory=list)     # 约束条件
    context: Dict[str, Any] = field(default_factory=dict)    # 上下文


class IntentParser:
    """
    意图解析器
    
    核心功能：
    1. 文本预处理（分词、规范化）
    2. 实体提取（文件路径、函数名、变量等）
    3. 意图类型识别
    4. 参数解析
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._init_patterns()
        
    def _init_patterns(self):
        """初始化正则表达式模式"""
        # 代码相关模式
        self.patterns = {
            'file_path': r'[\w./\\]+\.\w+',  # 文件路径
            'function_name': r'def\s+(\w+)|(\w+)\s*\(' ,  # 函数名
            'class_name': r'class\s+(\w+)',   # 类名
            'variable': r'(\w+)\s*=',         # 变量
            'import_statement': r'import\s+(\w+)|from\s+(\w+)',  # 导入语句
            'comment': r'#\s*(.+)',            # 注释
        }
        
        # 意图关键词映射
        self.intent_keywords = {
            IntentType.CODE_GENERATION: ['生成', '创建', '编写', '写', '实现', 'build', 'create', 'generate', 'write'],
            IntentType.CODE_COMPLETION: ['补全', '完成', '填充', 'complete', 'fill', 'autocomplete'],
            IntentType.CODE_REVIEW: ['审查', 'review', '检查', 'check', 'lint'],
            IntentType.BUG_FIX: ['修复', 'fix', 'bug', '错误', 'error', '问题'],
            IntentType.REFACTORING: ['重构', 'refactor', '优化', 'optimize', '重写'],
            IntentType.QUERY: ['查询', 'query', '查找', 'find', '搜索', 'search'],
            IntentType.EXECUTION: ['执行', 'run', '运行', 'execute', 'start'],
            IntentType.EXPLANATION: ['解释', 'explain', '说明', '什么是', 'how'],
            IntentType.CREATION: ['新建', 'new', '新增', 'add'],
            IntentType.MODIFICATION: ['修改', 'edit', 'change', '更新', 'update'],
            IntentType.DELETION: ['删除', 'delete', 'remove', '清除'],
            IntentType.SEARCH: ['搜索', 'search', '查找', 'find', 'locate'],
            IntentType.ANALYSIS: ['分析', 'analyze', '分析', '评估', 'evaluate'],
        }
        
    def parse(self, text: str, context: Optional[Dict[str, Any]] = None) -> ParsedIntent:
        """
        解析自然语言文本为结构化意图
        
        Args:
            text: 自然语言输入
            context: 上下文信息
            
        Returns:
            ParsedIntent: 解析后的意图对象
        """
        # 1. 文本预处理
        processed_text = self._preprocess(text)
        
        # 2. 实体提取
        entities = self._extract_entities(processed_text)
        
        # 3. 意图类型识别
        intent_type, confidence = self._classify_intent(processed_text)
        
        # 4. 参数解析
        parameters = self._extract_parameters(processed_text, intent_type)
        
        # 5. 约束条件提取
        constraints = self._extract_constraints(processed_text)
        
        return ParsedIntent(
            raw_text=text,
            intent_type=intent_type,
            entities=entities,
            parameters=parameters,
            confidence=confidence,
            constraints=constraints,
            context=context or {}
        )
    
    def _preprocess(self, text: str) -> str:
        """文本预处理"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 转小写（用于关键词匹配）
        return text.lower()
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体信息"""
        entities = {}
        
        # 提取文件路径
        file_paths = re.findall(self.patterns['file_path'], text)
        if file_paths:
            entities['file_paths'] = file_paths
            
        # 提取函数名
        function_names = re.findall(self.patterns['function_name'], text)
        if function_names:
            entities['function_names'] = [f for f in function_names if f]
            
        # 提取类名
        class_names = re.findall(self.patterns['class_name'], text)
        if class_names:
            entities['class_names'] = class_names
            
        return entities
    
    def _classify_intent(self, text: str) -> tuple[IntentType, float]:
        """识别意图类型"""
        scores = {}
        
        for intent_type, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score > 0:
                scores[intent_type] = score / len(keywords)
                
        if not scores:
            return IntentType.UNKNOWN, 0.0
            
        # 返回最高分的意图类型
        best_intent = max(scores.items(), key=lambda x: x[1])
        return best_intent[0], min(best_intent[1], 1.0)
    
    def _extract_parameters(self, text: str, intent_type: IntentType) -> Dict[str, Any]:
        """提取参数"""
        params = {}
        
        # 根据意图类型提取不同参数
        if intent_type == IntentType.CODE_GENERATION:
            # 提取语言/框架信息
            languages = ['python', 'javascript', 'java', 'cpp', 'go', 'rust']
            for lang in languages:
                if lang in text:
                    params['language'] = lang
                    
        elif intent_type == IntentType.BUG_FIX:
            # 提取错误信息
            if 'error' in text or '错误' in text:
                error_match = re.search(r'(error|错误)[:\s]+(.+)', text)
                if error_match:
                    params['error_message'] = error_match.group(2)
                    
        elif intent_type == IntentType.EXECUTION:
            # 提取命令
            if 'run' in text or '执行' in text:
                cmd_match = re.search(r'run\s+(.+)', text)
                if cmd_match:
                    params['command'] = cmd_match.group(1)
                    
        return params
    
    def _extract_constraints(self, text: str) -> List[str]:
        """提取约束条件"""
        constraints = []
        
        # 提取性能约束
        if '快' in text or 'fast' in text or 'quick' in text:
            constraints.append('performance:high')
            
        # 提取安全约束
        if '安全' in text or 'secure' in text:
            constraints.append('security:required')
            
        # 提取兼容性约束
        if '兼容' in text or 'compatible' in text:
            constraints.append('compatibility:required')
            
        return constraints
