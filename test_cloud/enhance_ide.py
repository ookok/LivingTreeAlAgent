#!/usr/bin/env python3
"""
IDE 功能增强 - 智能代码补全和分析
"""

import re
import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))


class CodeAnalyzer:
    """代码分析器"""
    
    def __init__(self):
        self._keywords = {
            "python": [
                "def", "class", "if", "else", "elif", "for", "while", "return", 
                "import", "from", "as", "try", "except", "finally", "with", 
                "True", "False", "None", "and", "or", "not", "in", "is"
            ],
            "javascript": [
                "function", "const", "let", "var", "if", "else", "for", "while", 
                "return", "import", "export", "try", "catch", "finally", 
                "true", "false", "null", "undefined", "&&", "||", "!"
            ],
            "cpp": [
                "int", "float", "double", "char", "bool", "void", "class", 
                "struct", "if", "else", "for", "while", "return", "include", 
                "namespace", "using", "try", "catch", "true", "false"
            ]
        }
        
        self._patterns = {
            "python": {
                "function": r"def\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)",
                "class": r"class\s+([a-zA-Z_]\w*)\s*(?:\(([^)]*)\))?",
                "import": r"import\s+([\w\.]+)"
            }
        }
    
    def analyze_code(self, code, language="python"):
        """分析代码"""
        if language not in self._keywords:
            language = "python"
        
        analysis = {
            "functions": [],
            "classes": [],
            "imports": [],
            "variables": [],
            "suggestions": []
        }
        
        # 分析函数
        if language == "python" and "function" in self._patterns[language]:
            for match in re.finditer(self._patterns[language]["function"], code):
                func_name = match.group(1)
                params = match.group(2)
                analysis["functions"].append({
                    "name": func_name,
                    "params": params,
                    "line": code[:match.start()].count('\n') + 1
                })
        
        # 分析类
        if language == "python" and "class" in self._patterns[language]:
            for match in re.finditer(self._patterns[language]["class"], code):
                class_name = match.group(1)
                bases = match.group(2) or ""
                analysis["classes"].append({
                    "name": class_name,
                    "bases": bases,
                    "line": code[:match.start()].count('\n') + 1
                })
        
        # 分析导入
        if language == "python" and "import" in self._patterns[language]:
            for match in re.finditer(self._patterns[language]["import"], code):
                module = match.group(1)
                analysis["imports"].append(module)
        
        # 生成建议
        analysis["suggestions"] = self._generate_suggestions(code, language)
        
        return analysis
    
    def _generate_suggestions(self, code, language):
        """生成代码建议"""
        suggestions = []
        
        # 检查未使用的导入
        if language == "python":
            imports = re.findall(r"import\s+([\w\.]+)", code)
            for imp in imports:
                if imp not in code[code.find(f"import {imp}") + len(f"import {imp}"):]:
                    suggestions.append({
                        "type": "warning",
                        "message": f"未使用的导入: {imp}",
                        "severity": "low"
                    })
        
        # 检查代码风格
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            # 检查行长度
            if len(line) > 80:
                suggestions.append({
                    "type": "style",
                    "message": f"第 {i} 行长度超过 80 字符",
                    "severity": "low"
                })
            
            # 检查缩进
            if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                suggestions.append({
                    "type": "style",
                    "message": f"第 {i} 行缺少缩进",
                    "severity": "medium"
                })
        
        return suggestions


class CodeCompleter:
    """代码补全器"""
    
    def __init__(self):
        self._keywords = {
            "python": [
                "def", "class", "if", "else", "elif", "for", "while", "return", 
                "import", "from", "as", "try", "except", "finally", "with", 
                "True", "False", "None", "and", "or", "not", "in", "is"
            ],
            "javascript": [
                "function", "const", "let", "var", "if", "else", "for", "while", 
                "return", "import", "export", "try", "catch", "finally", 
                "true", "false", "null", "undefined", "&&", "||", "!"
            ],
            "cpp": [
                "int", "float", "double", "char", "bool", "void", "class", 
                "struct", "if", "else", "for", "while", "return", "include", 
                "namespace", "using", "try", "catch", "true", "false"
            ]
        }
        
        self._snippets = {
            "python": {
                "for": "for ${var} in ${iterable}:\n    ${indent}",
                "def": "def ${function}(${params}):\n    ${indent}",
                "class": "class ${name}(${bases}):\n    ${indent}",
                "if": "if ${condition}:\n    ${indent}",
                "try": "try:\n    ${indent}\nexcept ${exception}:\n    ${indent}",
                "with": "with ${context} as ${var}:\n    ${indent}"
            },
            "javascript": {
                "function": "function ${name}(${params}) {\n    ${indent}\n}",
                "if": "if (${condition}) {\n    ${indent}\n}",
                "for": "for (${var} in ${iterable}) {\n    ${indent}\n}",
                "const": "const ${name} = ${value};",
                "let": "let ${name} = ${value};",
                "try": "try {\n    ${indent}\n} catch (${error}) {\n    ${indent}\n}"
            }
        }
    
    def get_completions(self, prefix, language="python", context=""):
        """获取代码补全建议"""
        completions = []
        
        if language not in self._snippets:
            language = "python"
        
        # 关键字补全
        for keyword in self._keywords.get(language, []):
            if keyword.startswith(prefix):
                completions.append({
                    "type": "keyword",
                    "text": keyword,
                    "score": 0.9
                })
        
        # 代码片段补全
        for trigger, snippet in self._snippets[language].items():
            if trigger.startswith(prefix):
                completions.append({
                    "type": "snippet",
                    "text": trigger,
                    "snippet": snippet,
                    "score": 0.8
                })
        
        # 基于上下文的补全
        if context:
            # 从上下文中提取变量和函数
            variables = self._extract_variables(context, language)
            for var in variables:
                if var.startswith(prefix):
                    completions.append({
                        "type": "variable",
                        "text": var,
                        "score": 0.7
                    })
        
        # 按分数排序
        completions.sort(key=lambda x: x["score"], reverse=True)
        
        return completions[:10]  # 返回前10个
    
    def _extract_variables(self, context, language):
        """从上下文中提取变量"""
        variables = set()
        
        if language == "python":
            # 简单的变量提取
            for match in re.finditer(r"\b([a-zA-Z_]\w*)\s*=", context):
                variables.add(match.group(1))
        
        return list(variables)


class IDEEnhancer:
    """IDE 增强器"""
    
    def __init__(self):
        self.analyzer = CodeAnalyzer()
        self.completer = CodeCompleter()
    
    def analyze_code(self, code, language="python"):
        """分析代码"""
        return self.analyzer.analyze_code(code, language)
    
    def get_completions(self, prefix, language="python", context=""):
        """获取代码补全"""
        return self.completer.get_completions(prefix, language, context)
    
    def format_code(self, code, language="python"):
        """格式化代码"""
        if language == "python":
            return self._format_python(code)
        return code
    
    def _format_python(self, code):
        """格式化 Python 代码"""
        lines = code.split('\n')
        formatted = []
        indent_level = 0
        indent_size = 4
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted.append('')
                continue
            
            # 减少缩进
            if stripped.startswith('except') or stripped.startswith('elif') or stripped.startswith('else'):
                indent_level = max(0, indent_level - 1)
            
            # 添加缩进
            formatted.append(' ' * indent_level * indent_size + stripped)
            
            # 增加缩进
            if stripped.endswith(':'):
                indent_level += 1
        
        return '\n'.join(formatted)


def test_ide_enhancer():
    """测试 IDE 增强器"""
    print("=== 测试 IDE 功能增强 ===")
    
    enhancer = IDEEnhancer()
    
    # 测试代码
    test_code = """
import os
import sys

def hello():
print("Hello, world!")

class MyClass:
def __init__(self, name):
self.name = name

def greet(self):
return f"Hello, {self.name}!"

x = 10
y = 20
    """
    
    print("1. 测试代码分析")
    analysis = enhancer.analyze_code(test_code)
    print(f"  函数数量: {len(analysis['functions'])}")
    print(f"  类数量: {len(analysis['classes'])}")
    print(f"  导入模块: {analysis['imports']}")
    print(f"  建议数量: {len(analysis['suggestions'])}")
    
    if analysis['suggestions']:
        print("  代码建议:")
        for i, suggestion in enumerate(analysis['suggestions'], 1):
            print(f"    {i}. [{suggestion['type']}] {suggestion['message']}")
    
    print("\n2. 测试代码补全")
    test_prefixes = ["de", "fo", "if"]
    for prefix in test_prefixes:
        completions = enhancer.get_completions(prefix, context=test_code)
        print(f"  前缀 '{prefix}':")
        for i, comp in enumerate(completions[:3], 1):
            print(f"    {i}. {comp['text']} (类型: {comp['type']})")
    
    print("\n3. 测试代码格式化")
    formatted_code = enhancer.format_code(test_code)
    print("  格式化后的代码:")
    print("  " + formatted_code.replace('\n', '\n  '))
    
    print("\nIDE 功能增强测试完成！")


if __name__ == "__main__":
    test_ide_enhancer()