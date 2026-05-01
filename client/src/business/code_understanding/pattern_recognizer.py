"""
模式识别器 - 代码模式识别与匹配

核心功能：
1. 设计模式识别
2. 代码反模式检测
3. 代码重复检测
4. 最佳实践匹配
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from pathlib import Path


class PatternType(Enum):
    """模式类型"""
    DESIGN_PATTERN = "design_pattern"
    ANTI_PATTERN = "anti_pattern"
    CODE_SMELL = "code_smell"
    BEST_PRACTICE = "best_practice"


@dataclass
class PatternMatch:
    """模式匹配结果"""
    pattern_name: str
    pattern_type: PatternType
    confidence: float
    locations: List[Tuple[int, int]]  # (line, column)
    code_snippet: str
    suggestion: Optional[str] = None


class PatternRecognizer:
    """
    模式识别器 - 代码模式识别与匹配
    
    核心特性：
    1. 设计模式识别
    2. 代码反模式检测
    3. 代码重复检测
    4. 最佳实践匹配
    """

    def __init__(self):
        self._patterns = self._load_patterns()

    def _load_patterns(self) -> List[Dict[str, Any]]:
        """加载模式定义"""
        return [
            # 设计模式
            {
                "name": "Singleton",
                "type": PatternType.DESIGN_PATTERN,
                "patterns": [
                    r'class\s+\w+\s*:\s*\n.*__instance\s*=\s*None',
                    r'def\s+get[_]?instance\s*\(',
                    r'if\s+not\s+cls\.instance'
                ],
                "suggestion": "考虑使用依赖注入替代单例模式"
            },
            {
                "name": "Factory Method",
                "type": PatternType.DESIGN_PATTERN,
                "patterns": [
                    r'def\s+create_\w+\s*\(',
                    r'class\s+Factory',
                    r'return\s+\w+\(\)'
                ],
                "suggestion": None
            },
            {
                "name": "Observer",
                "type": PatternType.DESIGN_PATTERN,
                "patterns": [
                    r'add[_]?observer',
                    r'remove[_]?observer',
                    r'notify[_]?observers'
                ],
                "suggestion": None
            },
            {
                "name": "Strategy",
                "type": PatternType.DESIGN_PATTERN,
                "patterns": [
                    r'class\s+\w+\s*\(\s*\w+\s*\)',
                    r'self\.strategy',
                    r'strategy\.execute'
                ],
                "suggestion": None
            },
            
            # 反模式
            {
                "name": "God Class",
                "type": PatternType.ANTI_PATTERN,
                "patterns": [
                    r'class\s+\w+\s*:\s*\n(\s+def\s+\w+\s*\(\s*self[^)]*\).*\n){10,}'
                ],
                "suggestion": "God Class 反模式：类职责过多，建议拆分"
            },
            {
                "name": "Spaghetti Code",
                "type": PatternType.ANTI_PATTERN,
                "patterns": [
                    r'\n(\s+(if|for|while|try|except)\s+.*\n){8,}'
                ],
                "suggestion": "代码嵌套过深，建议重构"
            },
            {
                "name": "Magic Numbers",
                "type": PatternType.ANTI_PATTERN,
                "patterns": [
                    r'(==|!=|<|>|<=|>=)\s*[0-9]+[^_a-zA-Z]'
                ],
                "suggestion": "魔法数字：考虑使用常量替代字面量"
            },
            {
                "name": "Copy-Paste Programming",
                "type": PatternType.ANTI_PATTERN,
                "patterns": [
                    r'(def\s+\w+\s*\(.*\):\s*\n(\s+.*\n)+){2,}'
                ],
                "suggestion": "重复代码：考虑提取为函数"
            },
            
            # 代码异味
            {
                "name": "Long Method",
                "type": PatternType.CODE_SMELL,
                "patterns": [
                    r'def\s+\w+\s*\([^)]*\):\s*\n(\s+.*\n){50,}'
                ],
                "suggestion": "方法过长，建议拆分"
            },
            {
                "name": "Deep Nesting",
                "type": PatternType.CODE_SMELL,
                "patterns": [
                    r'(\s+)(if|for|while|try)\s+'
                ],
                "suggestion": "嵌套过深，建议简化逻辑"
            },
            {
                "name": "Large Class",
                "type": PatternType.CODE_SMELL,
                "patterns": [
                    r'class\s+\w+\s*:\s*\n(\s+def\s+\w+\s*\([^)]*\):.*\n){15,}'
                ],
                "suggestion": "类过大，建议拆分"
            },
            
            # 最佳实践
            {
                "name": "Type Hints",
                "type": PatternType.BEST_PRACTICE,
                "patterns": [
                    r'def\s+\w+\s*\([^)]*\)\s*->\s*\w+:',
                    r'from\s+typing\s+import'
                ],
                "suggestion": None
            },
            {
                "name": "Docstrings",
                "type": PatternType.BEST_PRACTICE,
                "patterns": [
                    r'def\s+\w+\s*\([^)]*\):\s*\n\s+"""'
                ],
                "suggestion": None
            },
            {
                "name": "Error Handling",
                "type": PatternType.BEST_PRACTICE,
                "patterns": [
                    r'try:\s*\n.*\n\s+except',
                    r'except\s+\w+\s+as\s+\w+:'
                ],
                "suggestion": None
            }
        ]

    def recognize_patterns(self, code: str) -> List[PatternMatch]:
        """识别代码中的模式"""
        matches = []
        lines = code.split('\n')
        
        for pattern_def in self._patterns:
            pattern_name = pattern_def["name"]
            pattern_type = pattern_def["type"]
            suggestion = pattern_def.get("suggestion")
            
            for pattern_str in pattern_def["patterns"]:
                pattern = re.compile(pattern_str, re.MULTILINE | re.DOTALL)
                
                for match in pattern.finditer(code):
                    start_pos = match.start()
                    line_num = code[:start_pos].count('\n') + 1
                    col_num = start_pos - code[:start_pos].rfind('\n')
                    
                    # 提取匹配的代码片段
                    snippet_start = max(0, start_pos - 20)
                    snippet_end = min(len(code), start_pos + 60)
                    snippet = code[snippet_start:snippet_end]
                    
                    match_result = PatternMatch(
                        pattern_name=pattern_name,
                        pattern_type=pattern_type,
                        confidence=self._calculate_confidence(pattern_def, code),
                        locations=[(line_num, col_num)],
                        code_snippet=snippet.strip(),
                        suggestion=suggestion
                    )
                    
                    matches.append(match_result)
        
        # 去重
        unique_matches = []
        seen = set()
        for match in matches:
            key = f"{match.pattern_name}_{match.locations[0][0]}"
            if key not in seen:
                seen.add(key)
                unique_matches.append(match)
        
        return unique_matches

    def _calculate_confidence(self, pattern_def: Dict[str, Any], code: str) -> float:
        """计算匹配置信度"""
        matched_patterns = 0
        total_patterns = len(pattern_def["patterns"])
        
        for pattern_str in pattern_def["patterns"]:
            if re.search(pattern_str, code, re.MULTILINE | re.DOTALL):
                matched_patterns += 1
        
        return matched_patterns / total_patterns

    def find_duplicate_code(self, code: str, min_length: int = 3) -> List[Tuple[str, List[int]]]:
        """查找重复代码"""
        lines = code.split('\n')
        line_groups = {}
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if len(stripped) > 20:
                if stripped not in line_groups:
                    line_groups[stripped] = []
                line_groups[stripped].append(i)
        
        duplicates = []
        for line_text, occurrences in line_groups.items():
            if len(occurrences) >= min_length:
                duplicates.append((line_text, occurrences))
        
        return duplicates

    def suggest_refactoring(self, code: str) -> List[str]:
        """生成重构建议"""
        patterns = self.recognize_patterns(code)
        suggestions = []
        
        for pattern in patterns:
            if pattern.suggestion:
                suggestions.append(f"[{pattern.pattern_type.value}] {pattern.pattern_name}: {pattern.suggestion}")
        
        # 添加重复代码建议
        duplicates = self.find_duplicate_code(code)
        if duplicates:
            suggestions.append(f"检测到 {len(duplicates)} 处重复代码模式，建议提取为函数")
        
        return suggestions


def get_pattern_recognizer() -> PatternRecognizer:
    """获取模式识别器实例"""
    return PatternRecognizer()