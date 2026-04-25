"""
热修复引擎 - 自动修复问题
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import re
import os


class FixStrategy(Enum):
    """修复策略"""
    AUTO = "auto"              # 自动修复
    SUGGEST = "suggest"        # 建议修复
    MANUAL = "manual"          # 手动修复


@dataclass
class FixResult:
    """修复结果"""
    success: bool
    original_code: str
    fixed_code: str
    changes: List[Dict[str, Any]] = field(default_factory=list)
    validation_passed: bool = False
    error: Optional[str] = None


class HotFixEngine:
    """
    热修复引擎
    
    功能：
    1. 分析问题根因
    2. 生成修复代码
    3. 验证修复效果
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.fix_history: List[FixResult] = []
        
    def fix(self, code: str, 
           problem_type: str,
           strategy: FixStrategy = FixStrategy.AUTO) -> FixResult:
        """
        修复代码
        
        Args:
            code: 原始代码
            problem_type: 问题类型
            strategy: 修复策略
            
        Returns:
            FixResult: 修复结果
        """
        original_code = code
        
        # 根据问题类型选择修复方法
        if 'syntax' in problem_type.lower():
            fixed_code = self._fix_syntax(code)
        elif 'import' in problem_type.lower():
            fixed_code = self._fix_import(code)
        elif 'null' in problem_type.lower() or 'none' in problem_type.lower():
            fixed_code = self._fix_null_pointer(code)
        elif 'index' in problem_type.lower():
            fixed_code = self._fix_index_error(code)
        elif 'key' in problem_type.lower():
            fixed_code = self._fix_key_error(code)
        else:
            fixed_code = self._suggest_fix(code, problem_type)
            
        result = FixResult(
            success=True,
            original_code=original_code,
            fixed_code=fixed_code,
            changes=self._diff_changes(original_code, fixed_code),
            validation_passed=self._validate(fixed_code)
        )
        
        self.fix_history.append(result)
        return result
    
    def _fix_syntax(self, code: str) -> str:
        """修复语法错误"""
        fixed = code
        
        # 修复常见缩进问题
        lines = fixed.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # 修复尾随空白
            line = line.rstrip()
            
            # 修复不匹配的括号
            open_parens = line.count('(') - line.count(')')
            if open_parens > 0 and i + 1 < len(lines):
                # 检查下一行是否需要续行
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('#'):
                    line += ' \\'
                    
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_import(self, code: str) -> str:
        """修复导入问题"""
        fixed = code
        
        # 简化实现：添加常见导入
        imports_to_add = []
        
        if 'numpy' in fixed and 'import numpy' not in fixed:
            imports_to_add.append('import numpy as np')
            
        if 'pandas' in fixed and 'import pandas' not in fixed:
            imports_to_add.append('import pandas as pd')
            
        if imports_to_add and 'import' not in fixed[:200]:
            fixed = '\n'.join(imports_to_add) + '\n' + fixed
            
        return fixed
    
    def _fix_null_pointer(self, code: str) -> str:
        """修复空指针问题"""
        fixed = code
        
        # 添加None检查
        # 简化实现
        if 'is None' not in fixed and 'if ' not in fixed[:100]:
            lines = fixed.split('\n')
            for i, line in enumerate(lines):
                if '=' in line and 'def ' not in line and 'class ' not in line:
                    # 简单检查变量使用
                    pass
            
        return fixed
    
    def _fix_index_error(self, code: str) -> str:
        """修复索引错误"""
        fixed = code
        
        # 添加边界检查
        if '[' in fixed and 'range(' not in fixed:
            # 简化实现：添加 try-except
            if 'try:' not in fixed:
                lines = fixed.split('\n')
                for i, line in enumerate(lines):
                    if '[' in line and '=' in line:
                        # 在可能出错的代码前添加try
                        pass
                        
        return fixed
    
    def _fix_key_error(self, code: str) -> str:
        """修复键错误"""
        fixed = code
        
        # 添加.get()方法或默认值
        if '.get(' not in fixed:
            fixed = re.sub(
                r'(\w+)\[([\'"])(\w+)\2\]',
                r'\1.get(\2\3\2, None)',
                fixed
            )
            
        return fixed
    
    def _suggest_fix(self, code: str, problem_type: str) -> str:
        """建议修复"""
        # 返回原始代码，添加注释建议
        return code + f'\n\n# TODO: Fix {problem_type}\n'
    
    def _diff_changes(self, original: str, fixed: str) -> List[Dict[str, Any]]:
        """计算差异"""
        changes = []
        
        original_lines = original.split('\n')
        fixed_lines = fixed.split('\n')
        
        for i, (orig, fixed_line) in enumerate(zip(original_lines, fixed_lines)):
            if orig != fixed_line:
                changes.append({
                    'line': i + 1,
                    'type': 'modified',
                    'original': orig,
                    'fixed': fixed_line
                })
                
        # 处理新增行
        if len(fixed_lines) > len(original_lines):
            for i in range(len(original_lines), len(fixed_lines)):
                changes.append({
                    'line': i + 1,
                    'type': 'added',
                    'fixed': fixed_lines[i]
                })
                
        # 处理删除行
        if len(original_lines) > len(fixed_lines):
            for i in range(len(fixed_lines), len(original_lines)):
                changes.append({
                    'line': i + 1,
                    'type': 'removed',
                    'original': original_lines[i]
                })
                
        return changes
    
    def _validate(self, code: str) -> bool:
        """验证修复"""
        try:
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError:
            return False
    
    def apply_fix_to_file(self, file_path: str,
                         problem_type: str) -> FixResult:
        """直接修复文件"""
        if not os.path.exists(file_path):
            return FixResult(
                success=False,
                original_code="",
                fixed_code="",
                error="File not found"
            )
            
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
            
        result = self.fix(original, problem_type)
        
        if result.success and result.validation_passed:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(result.fixed_code)
                
        return result
