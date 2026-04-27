"""
代码补全组件
提供智能代码补全功能
"""
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtWidgets import QCompleter, QTextEdit
from PyQt6.QtGui import QTextCursor


class CodeCompleter(QCompleter):
    """代码补全器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setMaxVisibleItems(10)
    
    def set_completions(self, completions):
        """
        设置补全列表
        
        Args:
            completions: 补全字符串列表
        """
        model = QStringListModel(completions, self)
        self.setModel(model)
    
    def get_completion_prefix(self):
        """
        获取当前补全前缀
        
        Returns:
            str: 补全前缀
        """
        text = self.widget().toPlainText()
        cursor = self.widget().textCursor()
        pos = cursor.position()
        
        # 向前查找单词边界
        start = pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == '_'):
            start -= 1
        
        return text[start:pos]


class PythonCodeCompleter(CodeCompleter):
    """Python 代码补全器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Python 关键字
        self.keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'True', 'try', 'while', 'with', 'yield'
        ]
        
        # Python 内置函数
        self.builtins = [
            'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'callable',
            'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict',
            'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter',
            'float', 'format', 'frozenset', 'getattr', 'globals',
            'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int',
            'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals',
            'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct',
            'open', 'ord', 'pow', 'print', 'property', 'range', 'repr',
            'reversed', 'round', 'set', 'setattr', 'slice', 'sorted',
            'staticmethod', 'str', 'sum', 'super', 'tuple', 'type',
            'vars', 'zip'
        ]
        
        # Python 常用模块
        self.modules = [
            'os', 'sys', 'math', 'random', 'datetime', 'time', 'json',
            're', 'collections', 'itertools', 'functools', 'pathlib',
            'subprocess', 'shutil', 'tempfile', 'typing', 'dataclasses',
            'PyQt6', 'numpy', 'pandas', 'matplotlib', 'requests'
        ]
        
        # 合并所有补全
        all_completions = self.keywords + self.builtins + self.modules
        self.set_completions(all_completions)


class JavaScriptCodeCompleter(CodeCompleter):
    """JavaScript/TypeScript 代码补全器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # JavaScript 关键字
        self.keywords = [
            'abstract', 'arguments', 'await', 'boolean', 'break', 'byte',
            'case', 'catch', 'char', 'class', 'const', 'continue',
            'debugger', 'default', 'delete', 'do', 'double', 'else',
            'enum', 'eval', 'export', 'extends', 'false', 'final',
            'finally', 'float', 'for', 'function', 'goto', 'if',
            'implements', 'import', 'in', 'instanceof', 'int', 'interface',
            'let', 'long', 'native', 'new', 'null', 'package', 'private',
            'protected', 'public', 'return', 'short', 'static', 'super',
            'switch', 'synchronized', 'this', 'throw', 'throws',
            'transient', 'true', 'try', 'typeof', 'var', 'void',
            'volatile', 'while', 'with', 'yield'
        ]
        
        # JavaScript 内置对象
        self.builtins = [
            'console', 'document', 'window', 'Array', 'Boolean', 'Date',
            'Error', 'Function', 'JSON', 'Math', 'Number', 'Object',
            'RegExp', 'String', 'Symbol', 'Map', 'Set', 'Promise',
            'Proxy', 'Reflect', 'parseInt', 'parseFloat', 'isNaN',
            'isFinite', 'setTimeout', 'setInterval', 'clearTimeout',
            'clearInterval', 'fetch', 'XMLHttpRequest'
        ]
        
        # 合并所有补全
        all_completions = self.keywords + self.builtins
        self.set_completions(all_completions)


def get_completer(language, parent=None):
    """
    根据语言获取代码补全器
    
    Args:
        language: 语言名称
        parent: 父对象
        
    Returns:
        CodeCompleter: 代码补全器
    """
    language = language.lower()
    
    if language in ['python', 'py']:
        return PythonCodeCompleter(parent)
    elif language in ['javascript', 'js', 'typescript', 'ts']:
        return JavaScriptCodeCompleter(parent)
    else:
        return CodeCompleter(parent)
