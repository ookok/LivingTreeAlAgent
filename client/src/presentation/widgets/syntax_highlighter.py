"""
语法高亮器
支持多种编程语言的语法高亮
"""
from PyQt6.QtCore import QRegExp, Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Python 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 关键字格式
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'True', 'try', 'while', 'with', 'yield'
        ]
        
        for keyword in keywords:
            pattern = QRegExp(f"\\b{keyword}\\b")
            self.highlighting_rules.append((pattern, keyword_format))
        
        # 内置函数格式
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#dcdcaa"))
        
        builtins = [
            'print', 'len', 'range', 'int', 'str', 'float', 'list',
            'dict', 'set', 'tuple', 'type', 'isinstance', 'hasattr',
            'getattr', 'setattr', 'open', 'close', 'read', 'write'
        ]
        
        for builtin in builtins:
            pattern = QRegExp(f"\\b{builtin}\\b")
            self.highlighting_rules.append((pattern, builtin_format))
        
        # 字符串格式
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        
        # 单引号字符串
        self.highlighting_rules.append((QRegExp("'[^'\\\\]*(\\\\.[^'\\\\]*)*'"), string_format))
        # 双引号字符串
        self.highlighting_rules.append((QRegExp("\"[^\"\\\\]*(\\\\.[^\"\\\\]*)*\""), string_format))
        
        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        
        self.highlighting_rules.append((QRegExp("#[^\n]*"), comment_format))
        
        # 数字格式
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        
        self.highlighting_rules.append((QRegExp("\\b\\d+\\.?\\d*\\b"), number_format))
        
        # 函数定义格式
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#dcdcaa"))
        
        self.highlighting_rules.append((QRegExp("\\bdef\\s+(\\w+)"), function_format))
        
        # 类名格式
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#4ec9b0"))
        class_format.setFontWeight(QFont.Weight.Bold)
        
        self.highlighting_rules.append((QRegExp("\\bclass\\s+(\\w+)"), class_format))
        
        # 装饰器格式
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#dcdcaa"))
        
        self.highlighting_rules.append((QRegExp("@\\w+"), decorator_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


class JavaScriptSyntaxHighlighter(QSyntaxHighlighter):
    """JavaScript/TypeScript 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 关键字格式
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = [
            'abstract', 'arguments', 'await', 'boolean', 'break', 'byte',
            'case', 'catch', 'char', 'class', 'const', 'continue', 'debugger',
            'default', 'delete', 'do', 'double', 'else', 'enum', 'eval',
            'export', 'extends', 'false', 'final', 'finally', 'float',
            'for', 'function', 'goto', 'if', 'implements', 'import', 'in',
            'instanceof', 'int', 'interface', 'let', 'long', 'native', 'new',
            'null', 'package', 'private', 'protected', 'public', 'return',
            'short', 'static', 'super', 'switch', 'synchronized', 'this',
            'throw', 'throws', 'transient', 'true', 'try', 'typeof',
            'var', 'void', 'volatile', 'while', 'with', 'yield'
        ]
        
        for keyword in keywords:
            pattern = QRegExp(f"\\b{keyword}\\b")
            self.highlighting_rules.append((pattern, keyword_format))
        
        # 字符串格式
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        
        self.highlighting_rules.append((QRegExp("'[^'\\\\]*(\\\\.[^'\\\\]*)*'"), string_format))
        self.highlighting_rules.append((QRegExp("\"[^\"\\\\]*(\\\\.[^\"\\\\]*)*\""), string_format))
        self.highlighting_rules.append((QRegExp("`[^`\\\\]*(\\\\.[^`\\\\]*)*`"), string_format))
        
        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        
        self.highlighting_rules.append((QRegExp("//[^\n]*"), comment_format))
        
        # 数字格式
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        
        self.highlighting_rules.append((QRegExp("\\b\\d+\\.?\\d*\\b"), number_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


class HTMLSyntaxHighlighter(QSyntaxHighlighter):
    """HTML 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 标签格式
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#569cd6"))
        
        self.highlighting_rules.append((QRegExp("<[^>]*>"), tag_format))
        
        # 属性格式
        attribute_format = QTextCharFormat()
        attribute_format.setForeground(QColor("#9cdcfe"))
        
        self.highlighting_rules.append((QRegExp("\\w+="), attribute_format))
        
        # 属性值格式
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#ce9178"))
        
        self.highlighting_rules.append((QRegExp("=\"[^\"]*\""), value_format))
        
        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        
        self.highlighting_rules.append((QRegExp("<!--[^-]*-->"), comment_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


def get_highlighter(language, parent=None):
    """
    根据语言获取语法高亮器
    
    Args:
        language: 语言名称
        parent: 父对象
        
    Returns:
        QSyntaxHighlighter: 语法高亮器
    """
    language = language.lower()
    
    if language in ['python', 'py']:
        return PythonSyntaxHighlighter(parent)
    elif language in ['javascript', 'js', 'typescript', 'ts']:
        return JavaScriptSyntaxHighlighter(parent)
    elif language in ['html', 'htm']:
        return HTMLSyntaxHighlighter(parent)
    elif language in ['css']:
        return CSSSyntaxHighlighter(parent)
    elif language in ['json']:
        return JSONSyntaxHighlighter(parent)
    elif language in ['yaml', 'yml']:
        return YAMLSyntaxHighlighter(parent)
    else:
        return None


class CSSSyntaxHighlighter(QSyntaxHighlighter):
    """CSS 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 选择器
        selector_format = QTextCharFormat()
        selector_format.setForeground(QColor("#d7ba7a"))
        selector_format.setFontWeight(QFont.Weight.Bold)
        
        self.highlighting_rules.append((QRegExp("[a-zA-Z][a-zA-Z0-9]*"), selector_format))
        
        # 属性
        property_format = QTextCharFormat()
        property_format.setForeground(QColor("#9cdcfe"))
        
        self.highlighting_rules.append((QRegExp("[a-zA-Z-]+(?=\\s*:)"), property_format))
        
        # 值
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#ce9178"))
        
        self.highlighting_rules.append((QRegExp(":(.*?)(;|})"), value_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        
        self.highlighting_rules.append((QRegExp("/\\*[^*]*\\*+([^/][^*]*\\*+)*/"), comment_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        
        self.highlighting_rules.append((QRegExp("\\b\\d+\\.?\\d*\\w*\\b"), number_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


class JSONSyntaxHighlighter(QSyntaxHighlighter):
    """JSON 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 键
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        
        self.highlighting_rules.append((QRegExp("\"[^\"]+\":"), key_format))
        
        # 字符串值
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        
        self.highlighting_rules.append((QRegExp(":\s*\"[^\"]+\""), string_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        
        self.highlighting_rules.append((QRegExp(":\\s*\\d+\\.?\\d*"), number_format))
        
        # 布尔值
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569cd6"))
        boolean_format.setFontWeight(QFont.Weight.Bold)
        
        self.highlighting_rules.append((QRegExp(":\\s*(true|false)"), boolean_format))
        
        # null
        null_format = QTextCharFormat()
        null_format.setForeground(QColor("#569cd6"))
        null_format.setFontWeight(QFont.Weight.Bold)
        
        self.highlighting_rules.append((QRegExp(":\\s*null"), null_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


class YAMLSyntaxHighlighter(QSyntaxHighlighter):
    """YAML 语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 键
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        
        self.highlighting_rules.append((QRegExp("^[a-zA-Z_][a-zA-Z0-9_]*:")), key_format))
        
        # 值
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#ce9178"))
        
        self.highlighting_rules.append((QRegExp(":\\s+.+")), value_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        
        self.highlighting_rules.append((QRegExp("#[^\n]*")), comment_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        
        self.highlighting_rules.append((QRegExp("\\b\\d+\\.?\\d*\\b")), number_format))
        
        # 布尔值
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569cd6"))
        boolean_format.setFontWeight(QFont.Weight.Bold)
        
        self.highlighting_rules.append((QRegExp(":\\s*(true|false|yes|no|on|off)")), boolean_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)
