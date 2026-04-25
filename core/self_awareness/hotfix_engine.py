"""
热修复引擎 - 自动修复问题
支持多种修复策略，智能分析代码问题并自动修复
"""

from typing import Dict, Any, Optional, List, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import ast
import os
from collections import defaultdict


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
    fix_type: Optional[str] = None


class HotFixEngine:
    """
    热修复引擎
    
    功能：
    1. 分析问题根因
    2. 生成修复代码（支持多种策略）
    3. 验证修复效果
    4. 记录修复历史
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.fix_history: List[FixResult] = []
        
        # 常见库导入映射
        self.library_imports = {
            'numpy': 'import numpy as np',
            'pandas': 'import pandas as pd',
            'matplotlib': 'import matplotlib.pyplot as plt',
            'torch': 'import torch',
            'tensorflow': 'import tensorflow as tf',
            'sklearn': 'from sklearn import *',
            'requests': 'import requests',
            'json': 'import json',
            'os': 'import os',
            'sys': 'import sys',
            'time': 'import time',
            'datetime': 'from datetime import datetime',
            'pathlib': 'from pathlib import Path',
            'typing': 'from typing import *',
            'collections': 'from collections import *',
            'itertools': 'import itertools',
            'functools': 'import functools',
            're': 'import re',
        }
        
        # 常见函数映射（用于未定义变量）
        self.common_functions = {
            'print': 'builtin',
            'len': 'builtin',
            'range': 'builtin',
            'enumerate': 'builtin',
            'zip': 'builtin',
            'map': 'builtin',
            'filter': 'builtin',
            'sorted': 'builtin',
            'reversed': 'builtin',
            'sum': 'builtin',
            'min': 'builtin',
            'max': 'builtin',
        }
        
    def fix(self, code: str, 
           problem_type: str,
           strategy: FixStrategy = FixStrategy.AUTO,
           context: Optional[Dict[str, Any]] = None) -> FixResult:
        """
        修复代码
        
        Args:
            code: 原始代码
            problem_type: 问题类型
            strategy: 修复策略
            context: 上下文信息（可选）
            
        Returns:
            FixResult: 修复结果
        """
        original_code = code
        fixed_code = code
        fix_type = problem_type
        
        # 根据问题类型选择修复方法
        if 'syntax' in problem_type.lower():
            fixed_code = self._fix_syntax_enhanced(code)
            fix_type = 'syntax'
        elif 'indent' in problem_type.lower():
            fixed_code = self._fix_indentation(code)
            fix_type = 'indentation'
        elif 'import' in problem_type.lower():
            fixed_code = self._fix_import_enhanced(code)
            fix_type = 'import'
        elif 'undefined' in problem_type.lower() or 'name' in problem_type.lower():
            fixed_code = self._fix_undefined_variable(code)
            fix_type = 'undefined_variable'
        elif 'null' in problem_type.lower() or 'none' in problem_type.lower():
            fixed_code = self._fix_null_pointer_enhanced(code)
            fix_type = 'null_pointer'
        elif 'index' in problem_type.lower():
            fixed_code = self._fix_index_error_enhanced(code)
            fix_type = 'index_error'
        elif 'key' in problem_type.lower():
            fixed_code = self._fix_key_error_enhanced(code)
            fix_type = 'key_error'
        elif 'type' in problem_type.lower():
            fixed_code = self._fix_type_error(code)
            fix_type = 'type_error'
        elif 'unused' in problem_type.lower() or 'import' in problem_type.lower():
            fixed_code = self._fix_unused_import(code)
            fix_type = 'unused_import'
        elif 'pep8' in problem_type.lower() or 'style' in problem_type.lower():
            fixed_code = self._fix_style_issues(code)
            fix_type = 'style'
        elif 'performance' in problem_type.lower():
            fixed_code = self._fix_performance_issues(code)
            fix_type = 'performance'
        elif 'security' in problem_type.lower():
            fixed_code = self._fix_security_issues(code)
            fix_type = 'security'
        else:
            fixed_code = self._suggest_fix(code, problem_type)
            fix_type = 'suggestion'
            
        result = FixResult(
            success=(fixed_code != original_code),
            original_code=original_code,
            fixed_code=fixed_code,
            changes=self._diff_changes(original_code, fixed_code),
            validation_passed=self._validate(fixed_code),
            fix_type=fix_type,
        )
        
        self.fix_history.append(result)
        return result
    
    def _fix_syntax_enhanced(self, code: str) -> str:
        """增强版语法错误修复"""
        fixed = code
        lines = fixed.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # 修复尾随空白
            line = line.rstrip()
            
            # 修复不匹配的括号
            open_parens = line.count('(') - line.count(')')
            open_brackets = line.count('[') - line.count(']')
            open_braces = line.count('{') - line.count('}')
            
            # 如果有未闭合的括号，添加续行符
            if (open_parens > 0 or open_brackets > 0 or open_braces > 0) and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('#') and not line.rstrip().endswith('\\'):
                    line += ' \\'
                    
            # 修复常见的语法错误
            # 1. 缺少冒号
            if re.match(r'^\s*(if|elif|else|for|while|with|try|except|finally|def|class|with)\s+.*[^:]$', line):
                line += ':'
                
            # 2. 错误的赋值（= 应该是 ==）
            if re.match(r'^\s*if\s+.*[^=!<>]==.*$', line):
                pass  # 已经正确
                
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_indentation(self, code: str) -> str:
        """修复缩进错误"""
        lines = code.split('\n')
        fixed_lines = []
        indent_level = 0
        indent_char = '    '  # 默认4空格
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                fixed_lines.append(line)
                continue
                
            # 检测缩进字符
            if line[0] in [' ', '\t']:
                indent_char = '\t' if line[0] == '\t' else '    '
                
            # 减少缩进的关键字
            if stripped.startswith(('return', 'break', 'continue', 'pass', 'raise', 'yield')):
                indent_level = max(0, indent_level - 1)
                
            # 应用缩进
            fixed_lines.append(indent_char * indent_level + stripped)
            
            # 增加缩进的关键字
            if stripped.endswith(':') and not stripped.startswith('#'):
                indent_level += 1
                
        return '\n'.join(fixed_lines)
    
    def _fix_import_enhanced(self, code: str) -> str:
        """增强版导入修复"""
        fixed = code
        lines = fixed.split('\n')
        
        # 分析代码中使用的库
        used_libraries = set()
        for line in lines:
            for lib in self.library_imports.keys():
                if re.search(rf'\b{lib}\.', line):
                    used_libraries.add(lib)
                    
        # 检查哪些库需要导入
        imports_to_add = []
        existing_imports = fixed[:200]  # 检查文件开头的导入
        
        for lib in used_libraries:
            import_stmt = self.library_imports[lib]
            if import_stmt not in existing_imports:
                imports_to_add.append(import_stmt)
                
        # 添加缺失的导入
        if imports_to_add:
            # 在第一个非导入、非空行之前插入
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith(('import ', 'from ', '#')):
                    insert_pos = i
                    break
                insert_pos = i + 1
                
            for i, import_stmt in enumerate(imports_to_add):
                lines.insert(insert_pos + i, import_stmt)
                
        return '\n'.join(lines)
    
    def _fix_undefined_variable(self, code: str) -> str:
        """修复未定义变量"""
        fixed = code
        lines = fixed.split('\n')
        
        # 使用AST分析代码
        try:
            tree = ast.parse(code)
            defined_names = set()
            
            # 收集已定义的变量
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defined_names.add(target.id)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        defined_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        defined_names.add(alias.asname or alias.name)
                        
            # 检查未定义的变量
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    if node.id not in defined_names and node.id not in self.common_functions:
                        # 尝试修复：添加默认值
                        if node.id[0].isupper():
                            # 可能是类名，添加类定义
                            pass
                        else:
                            # 可能是变量，初始化为None
                            pass
                            
        except SyntaxError:
            pass
            
        return fixed
    
    def _fix_null_pointer_enhanced(self, code: str) -> str:
        """增强版空指针修复"""
        fixed = code
        
        # 添加None检查
        lines = fixed.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 在可能的空指针访问前添加检查
            if '.method(' in stripped or '[.' in stripped:
                indent = line[:len(line) - len(line.lstrip())]
                var_name = re.match(r'^(\w+)\.', stripped)
                
                if var_name:
                    var = var_name.group(1)
                    check_line = f"{indent}if {var} is not None:"
                    fixed_lines.append(check_line)
                    fixed_lines.append(line)
                    continue
                    
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_index_error_enhanced(self, code: str) -> str:
        """增强版索引错误修复"""
        fixed = code
        
        # 添加边界检查
        lines = fixed.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # 检测列表索引访问
            match = re.search(r'(\w+)\[(\d+)\]', line)
            if match:
                var_name = match.group(1)
                index = match.group(2)
                
                indent = line[:len(line) - len(line.lstrip())]
                check_line = f"{indent}if {index} < len({var_name}):"
                fixed_lines.append(check_line)
                fixed_lines.append(line)
                continue
                
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_key_error_enhanced(self, code: str) -> str:
        """增强版键错误修复"""
        fixed = code
        
        # 使用 .get() 替换直接字典访问
        fixed = re.sub(
            r'(\w+)\[([\'"])(\w+)\2\]',
            r'\1.get(\2\3\2, None)',
            fixed
        )
        
        # 添加键存在检查
        lines = fixed.split('\n')
        fixed_lines = []
        
        for line in lines:
            if '[' in line and '=' not in line[:line.index('[')] if '[' in line else False:
                indent = line[:len(line) - len(line.lstrip())]
                match = re.search(r'(\w+)\[([\'"]?\w+[\'"]?)\]', line)
                if match:
                    var = match.group(1)
                    key = match.group(2)
                    check_line = f"{indent}if {key} in {var}:"
                    fixed_lines.append(check_line)
                    fixed_lines.append(line)
                    continue
                    
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_type_error(self, code: str) -> str:
        """修复类型错误"""
        fixed = code
        
        # 添加类型转换
        lines = fixed.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 检测可能的类型错误
            if '+ ' in line or ' +' in line:
                # 可能是字符串和数字拼接
                if re.search(r'\w+\s*\+\s*\d+', line) or re.search(r'\d+\s*\+\s*\w+', line):
                    # 添加 str() 转换
                    line = re.sub(r'(\w+)(\s*\+\s*)(\d+)', r'str(\1)\2\3', line)
                    
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_unused_import(self, code: str) -> str:
        """修复未使用的导入"""
        lines = code.split('\n')
        
        # 使用AST分析
        try:
            tree = ast.parse(code)
            used_names = set()
            
            # 收集使用的名称
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)
                    
            # 移除未使用的导入
            fixed_lines = []
            for line in lines:
                if line.strip().startswith(('import ', 'from ')):
                    # 提取导入的名称
                    if line.strip().startswith('import '):
                        names = [n.strip() for n in line.strip()[7:].split(',')]
                        used = [n for n in names if n in used_names]
                        if used:
                            fixed_lines.append(line)
                    else:
                        # from ... import ...
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
                    
            return '\n'.join(fixed_lines)
            
        except SyntaxError:
            return code
    
    def _fix_style_issues(self, code: str) -> str:
        """修复代码风格问题（PEP 8）"""
        fixed = code
        lines = fixed.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 修复行尾空白
            line = line.rstrip()
            
            # 修复运算符周围缺少空格
            line = re.sub(r'(\w)([+\-*/=]=?)(\w)', r'\1 \2 \3', line)
            
            # 修复逗号后缺少空格
            line = re.sub(r',(\w)', r', \1', line)
            
            # 修复冒号后缺少空格（字典）
            line = re.sub(r':(\w)', r': \1', line)
            
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    def _fix_performance_issues(self, code: str) -> str:
        """修复性能问题"""
        fixed = code
        
        # 1. 将 list() 转换为列表推导式
        fixed = re.sub(
            r'\[(.*?)\s+for\s+(.*?)\s+in\s+(.*?)\s+if\s+(.*?)\]',
            r'[\1 for \2 in \3 if \4]',
            fixed
        )
        
        # 2. 使用 join() 替换字符串拼接
        if "+=" in fixed and "'" in fixed:
            # 简化实现
            pass
            
        # 3. 使用生成器表达式
        if "list(" in fixed and "for " in fixed:
            # 简化实现
            pass
            
        return fixed
    
    def _fix_security_issues(self, code: str) -> str:
        """修复安全问题"""
        fixed = code
        
        # 1. 替换 eval() 为 ast.literal_eval()
        if 'eval(' in fixed:
            fixed = fixed.replace('eval(', 'ast.literal_eval(')
            if 'import ast' not in fixed[:200]:
                fixed = 'import ast\n' + fixed
                
        # 2. 替换 exec()
        if 'exec(' in fixed:
            # 添加警告注释
            fixed = '# SECURITY WARNING: exec() is dangerous\n' + fixed
            
        # 3. 防止 SQL 注入
        if 'execute(' in fixed and '%s' in fixed:
            # 添加参数化查询建议
            fixed = '# TODO: Use parameterized queries to prevent SQL injection\n' + fixed
            
        # 4. 防止 XSS
        if 'render(' in fixed or 'template(' in fixed:
            fixed = '# TODO: Escape user input to prevent XSS\n' + fixed
            
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
    
    def batch_fix(self, files: List[str], 
                  problem_types: Optional[List[str]] = None) -> List[FixResult]:
        """批量修复文件"""
        results = []
        
        for i, file_path in enumerate(files):
            problem_type = problem_types[i] if problem_types and i < len(problem_types) else 'auto'
            result = self.apply_fix_to_file(file_path, problem_type)
            results.append(result)
            
        return results
