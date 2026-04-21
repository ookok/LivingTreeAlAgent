"""
AI编程助手模块
提供代码生成、错误诊断、性能优化、文档生成等功能
"""
import re
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib


class TaskType(Enum):
    """AI任务类型"""
    CODE_COMPLETION = "code_completion"
    CODE_GENERATION = "code_generation"
    ERROR_DIAGNOSIS = "error_diagnosis"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    TEST_GENERATION = "test_generation"
    EXPLANATION = "explanation"
    DEBUG_ASSIST = "debug_assist"
    ARCHITECTURE_SUGGESTION = "architecture_suggestion"


@dataclass
class AITask:
    """AI任务"""
    id: str
    task_type: TaskType
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 0
    timeout: int = 30


@dataclass
class AIRecommendation:
    """AI推荐/建议"""
    type: str  # completion, suggestion, warning, error, refactor
    message: str
    code_snippet: Optional[str] = None
    line: Optional[int] = None
    confidence: float = 0.0
    explanation: str = ""
    quick_fix: Optional[str] = None


@dataclass
class CodeAnalysis:
    """代码分析结果"""
    complexity: float = 0.0  # 圈复杂度
    maintainability: float = 0.0  # 可维护性指数
    lines_of_code: int = 0
    comment_ratio: float = 0.0
    duplication: float = 0.0  # 代码重复率
    issues: List[AIRecommendation] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class RefactorPlan:
    """重构计划"""
    original_code: str
    suggested_code: str
    changes: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)


@dataclass
class TestCase:
    """测试用例"""
    name: str
    code: str
    input_data: Any = None
    expected_output: Any = None
    is_parametrized: bool = False


class CodeGenerator:
    """代码生成器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.templates: Dict[str, str] = {}
        self._init_templates()

    def _init_templates(self):
        """初始化代码模板"""
        self.templates = {
            "python_class": '''class {class_name}:
    """类的文档字符串"""
    
    def __init__(self{params}):
        """初始化方法"""
{init_body}
    
    def __str__(self):
        return f"{self.__class__.__name__}"''',
            "python_function": '''def {function_name}({params}) -> {return_type}:
    """函数的文档字符串
    
    Args:
{args_doc}
    
    Returns:
        {return_type}: 返回值描述
    
    Raises:
        Exception: 异常描述
    """
{body}''',
            "javascript_class": '''class {class_name} {{
    constructor({params}) {{
{init_body}
    }}
    
    {methods}
}}''',
            "api_endpoint": '''@app.{method}("{path}")
async def {endpoint_name}({params}):
    """端点描述"""
{body}
    return {response}''',
        }

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成代码"""
        context = context or {}

        # 如果有LLM客户端，使用LLM生成
        if self.llm_client:
            full_prompt = self._build_generation_prompt(prompt, language, context)
            return await self.llm_client.generate(full_prompt)

        # 否则使用模板
        return self._generate_from_template(prompt, language, context)

    def _build_generation_prompt(
        self,
        prompt: str,
        language: str,
        context: Dict[str, Any]
    ) -> str:
        """构建生成提示"""
        template = f"""生成{language}代码。

要求：{prompt}

上下文：
- 文件路径：{context.get('file_path', 'unknown')}
- 相关代码：{context.get('related_code', 'N/A')}
- 导入语句：{context.get('imports', 'N/A')}

请只返回代码，不要包含解释。"""

        return template

    def _generate_from_template(
        self,
        prompt: str,
        language: str,
        context: Dict[str, Any]
    ) -> str:
        """从模板生成代码"""
        # 简单的模板匹配
        if "class" in prompt.lower():
            template = self.templates.get(f"{language}_class", self.templates["python_class"])
            return template.format(
                class_name=context.get("class_name", "NewClass"),
                params=context.get("params", ""),
                init_body=context.get("init_body", "        pass"),
                methods=""
            )
        elif "function" in prompt.lower() or "def" in prompt.lower():
            template = self.templates.get(f"{language}_function", self.templates["python_function"])
            return template.format(
                function_name=context.get("function_name", "new_function"),
                params=context.get("params", ""),
                return_type=context.get("return_type", "None"),
                args_doc=context.get("args_doc", "        pass"),
                body=context.get("body", "    pass")
            )

        return f"# Generated code for: {prompt}"

    async def complete_code(
        self,
        code: str,
        position: int,
        language: str,
        max_tokens: int = 100
    ) -> str:
        """代码补全"""
        if self.llm_client:
            prompt = f"""补全以下{language}代码，只返回补全部分：

{code[:position]}
<<<CURSOR>>>
{code[position:]}

请只返回补全的代码，不要包含解释。"""

            return await self.llm_client.generate(prompt, max_tokens=max_tokens)

        return ""


class ErrorDiagnoser:
    """错误诊断器"""

    def __init__(self):
        self.error_patterns: Dict[str, Dict[str, Any]] = {}
        self._init_error_patterns()

    def _init_error_patterns(self):
        """初始化错误模式"""
        self.error_patterns = {
            # Python错误
            "SyntaxError": {
                "patterns": [
                    r"SyntaxError: .*",
                    r"invalid syntax",
                ],
                "severity": "error",
                "suggestions": [
                    "检查括号、引号是否匹配",
                    "确保缩进正确",
                    "检查关键字拼写",
                ]
            },
            "NameError": {
                "patterns": [
                    r"NameError: name '(\w+)' is not defined",
                ],
                "severity": "error",
                "suggestions": [
                    "检查变量名拼写是否正确",
                    "确保在使用前已赋值",
                    "检查是否导入了所需的模块",
                ]
            },
            "TypeError": {
                "patterns": [
                    r"TypeError: .*",
                ],
                "severity": "error",
                "suggestions": [
                    "检查参数类型是否正确",
                    "确保操作符两侧类型兼容",
                    "检查函数调用参数数量",
                ]
            },
            "ImportError": {
                "patterns": [
                    r"ImportError: .*",
                    r"ModuleNotFoundError: .*",
                ],
                "severity": "error",
                "suggestions": [
                    "检查模块是否已安装 (pip install)",
                    "检查模块名拼写",
                    "检查__init__.py是否存在",
                ]
            },
            # JavaScript错误
            "ReferenceError": {
                "patterns": [
                    r"ReferenceError: .* is not defined",
                ],
                "severity": "error",
                "suggestions": [
                    "检查变量是否已声明",
                    "检查变量名拼写",
                ]
            },
            "TypeError: undefined": {
                "patterns": [
                    r"TypeError: .* is undefined",
                ],
                "severity": "error",
                "suggestions": [
                    "检查对象是否已初始化",
                    "检查属性是否存在",
                    "使用可选链 (?.) 避免错误",
                ]
            },
        }

    def diagnose(
        self,
        error_message: str,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """诊断错误"""
        recommendations = []

        for error_type, pattern_info in self.error_patterns.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, error_message, re.IGNORECASE):
                    # 提取关键信息
                    match = re.search(pattern, error_message)
                    details = match.group(0) if match else error_message

                    # 生成建议
                    suggestions = pattern_info["suggestions"].copy()

                    # 根据错误类型添加代码片段
                    quick_fix = None
                    if "NameError" in error_type:
                        var_match = re.search(r"name '(\w+)'", error_message)
                        if var_match:
                            var_name = var_match.group(1)
                            quick_fix = f"# Define the variable\n{var_name} = None"

                    recommendations.append(AIRecommendation(
                        type="error",
                        message=f"{error_type}: {details}",
                        confidence=0.9,
                        explanation=f"这是一个{error_type}，通常由代码中的错误引起。",
                        quick_fix=quick_fix
                    ))
                    break

        if not recommendations:
            recommendations.append(AIRecommendation(
                type="warning",
                message=error_message,
                confidence=0.5,
                explanation="无法识别具体错误类型，请检查代码逻辑。"
            ))

        return recommendations

    def analyze_potential_issues(
        self,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """分析潜在问题"""
        recommendations = []

        # 检查常见问题
        lines = code.split('\n')

        for line_num, line in enumerate(lines, 1):
            # 检查 TODO/FIXME
            if 'TODO' in line or 'FIXME' in line:
                recommendations.append(AIRecommendation(
                    type="suggestion",
                    message=f"发现未完成的任务: {line.strip()}",
                    line=line_num,
                    confidence=0.8
                ))

            # 检查过于复杂的函数
            if language == "python" and line.strip().startswith('def '):
                # 简单检查函数长度
                func_lines = self._get_function_body(lines, line_num - 1)
                if len(func_lines) > 50:
                    recommendations.append(AIRecommendation(
                        type="suggestion",
                        message=f"函数可能过于复杂 ({len(func_lines)} 行)",
                        line=line_num,
                        confidence=0.7,
                        explanation="建议将大函数拆分为多个小函数。"
                    ))

        return recommendations

    def _get_function_body(self, lines: List[str], func_line_idx: int) -> List[str]:
        """获取函数体"""
        body = []
        base_indent = len(lines[func_line_idx]) - len(lines[func_line_idx].lstrip())

        for i in range(func_line_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() == '':
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent and line.strip():
                break
            body.append(line)

        return body


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self):
        self.heuristics: Dict[str, List[Dict[str, Any]]] = {}
        self._init_heuristics()

    def _init_heuristics(self):
        """初始化性能启发式规则"""
        self.heuristics = {
            "python": [
                {
                    "pattern": r"for .* in .*:\s*.*\.append\(",
                    "issue": "列表推导式可能更快",
                    "suggestion": "考虑使用列表推导式或生成器表达式",
                    "severity": "info"
                },
                {
                    "pattern": r"\+\s*\[.*\]",
                    "issue": "列表拼接在循环中效率低",
                    "suggestion": "考虑使用列表推导式或 extend()",
                    "severity": "warning"
                },
                {
                    "pattern": r"\.get\([^,]+, None\)",
                    "issue": "使用 get() 默认值",
                    "suggestion": "如果需要默认值，dict.get() 是正确的方法",
                    "severity": "info"
                },
                {
                    "pattern": r"isinstance\([^,]+, \(.*\)\)",
                    "issue": "多次类型检查",
                    "suggestion": "考虑使用多态或协议",
                    "severity": "info"
                },
            ],
            "javascript": [
                {
                    "pattern": r"for\s*\(.+\)\s*\{\s*.*push\(",
                    "issue": "循环中使用 push()",
                    "suggestion": "考虑使用 map(), filter(), reduce()",
                    "severity": "info"
                },
                {
                    "pattern": r"document\.getElementById\(.+\).+document\.getElementById\(",
                    "issue": "重复查询 DOM",
                    "suggestion": "将 DOM 元素缓存到变量中",
                    "severity": "warning"
                },
            ]
        }

    async def analyze(
        self,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """分析代码性能"""
        recommendations = []
        heuristics = self.heuristics.get(language, [])

        for heuristic in heuristics:
            if re.search(heuristic["pattern"], code, re.MULTILINE):
                recommendations.append(AIRecommendation(
                    type="suggestion",
                    message=heuristic["issue"],
                    confidence=0.7,
                    explanation=heuristic["suggestion"]
                ))

        return recommendations

    def estimate_complexity(self, code: str) -> CodeAnalysis:
        """估算代码复杂度"""
        analysis = CodeAnalysis()

        lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
        analysis.lines_of_code = len(lines)

        # 统计注释
        all_lines = code.split('\n')
        comment_lines = [l for l in all_lines if l.strip().startswith('#') or l.strip().startswith('//')]
        analysis.comment_ratio = len(comment_lines) / max(len(all_lines), 1)

        # 简单的圈复杂度估计
        complexity_indicators = [
            r'\bif\b', r'\bfor\b', r'\bwhile\b', r'\band\b', r'\bor\b',
            r'\bcatch\b', r'\bcase\b', r'\?', r'&&', r'\|\|'
        ]

        complexity = 1
        for pattern in complexity_indicators:
            complexity += len(re.findall(pattern, code))

        analysis.complexity = min(complexity, 100)
        analysis.maintainability = max(100 - complexity * 2, 0)

        return analysis


class DocumentationGenerator:
    """文档生成器"""

    def __init__(self):
        self.doc_formats: Dict[str, Callable] = {
            "google": self._google_style,
            "numpy": self._numpy_style,
            "sphinx": self._sphinx_style,
        }

    async def generate_docstring(
        self,
        code: str,
        language: str,
        style: str = "google"
    ) -> str:
        """生成文档字符串"""
        formatter = self.doc_formats.get(style, self._google_style)

        # 解析代码结构
        if language == "python":
            return await self._generate_python_doc(code, formatter)
        elif language == "javascript":
            return await self._generate_jsdoc(code)
        else:
            return '"""Documentation"""'

    def _google_style(self, params: Dict, returns: str, raises: List[str]) -> str:
        """Google风格文档"""
        lines = ['"""']
        if params:
            lines.append("Args:")
            for name, desc in params.items():
                lines.append(f"    {name} ({desc.get('type', 'Any')}): {desc.get('desc', '')}")
        if returns:
            lines.append(f"\nReturns:\n    {returns}")
        if raises:
            lines.append("\nRaises:")
            for exc in raises:
                lines.append(f"    {exc}: ")
        lines.append('"""')
        return '\n'.join(lines)

    def _numpy_style(self, params: Dict, returns: str, raises: List[str]) -> str:
        """NumPy风格文档"""
        lines = ['"""']
        if params:
            lines.append("")
            lines.append("Parameters")
            lines.append("----------")
            for name, desc in params.items():
                lines.append(f"{name} : {desc.get('type', 'Any')}")
                lines.append(f"    {desc.get('desc', '')}")
        if returns:
            lines.append("")
            lines.append("Returns")
            lines.append("-------")
            lines.append(f"{returns}")
        if raises:
            lines.append("")
            lines.append("Raises")
            lines.append("------")
            for exc in raises:
                lines.append(f"{exc}")
        lines.append('"""')
        return '\n'.join(lines)

    def _sphinx_style(self, params: Dict, returns: str, raises: List[str]) -> str:
        """Sphinx风格文档"""
        lines = ['"""']
        if params:
            lines.append("\n:param params:")
            for name, desc in params.items():
                lines.append(f"    {name}: {desc.get('desc', '')}")
        if returns:
            lines.append(f"\n:returns: {returns}")
        if raises:
            lines.append("\n:raises:")
            for exc in raises:
                lines.append(f"    {exc}")
        lines.append('"""')
        return '\n'.join(lines)

    async def _generate_python_doc(self, code: str, formatter: Callable) -> str:
        """生成Python文档"""
        # 简单的函数解析
        if match := re.search(r'def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\w+))?', code):
            func_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3) or "None"

            # 解析参数
            params = {}
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param:
                        name = re.sub(r'[:=].*', '', param).strip()
                        params[name] = {'type': 'Any', 'desc': ''}

            return formatter(params, return_type, [])

        elif match := re.search(r'class\s+(\w+)', code):
            class_name = match.group(1)
            return f'"""{class_name}类"""'

        return '"""Documentation"""'

    async def _generate_jsdoc(self, code: str) -> str:
        """生成JSDoc"""
        if match := re.search(r'function\s+(\w+)\s*\((.*?)\)', code):
            func_name = match.group(1)
            params = match.group(2)

            lines = ['/**']
            lines.append(f' * {func_name}函数')
            for param in params.split(','):
                param = param.strip()
                if param:
                    lines.append(f' * @param {{{self._infer_js_type(param)}}} {param}')
            lines.append(' * @returns {*}')
            lines.append(' */')

            return '\n'.join(lines)

        elif match := re.search(r'class\s+(\w+)', code):
            class_name = match.group(1)
            return f'/**\n * {class_name}类\n */'

        return '/** Documentation */'

    def _infer_js_type(self, param: str) -> str:
        """推断JS参数类型"""
        if param.startswith('_'):
            return 'private'
        if 'Callback' in param or 'cb' in param.lower():
            return 'function'
        if 'Array' in param or 'List' in param:
            return 'Array'
        if 'Object' in param or 'Dict' in param:
            return 'Object'
        return '*'


class TestGenerator:
    """测试用例生成器"""

    def __init__(self):
        self.frameworks: Dict[str, Dict[str, str]] = {
            "python": {
                "unittest": "unittest.TestCase",
                "pytest": "pytest",
            },
            "javascript": {
                "jest": "jest",
                "mocha": "mocha",
            }
        }

    async def generate_tests(
        self,
        code: str,
        language: str,
        framework: str = "pytest"
    ) -> List[TestCase]:
        """生成测试用例"""
        tests = []

        if language == "python":
            tests = await self._generate_python_tests(code, framework)
        elif language == "javascript":
            tests = await self._generate_js_tests(code, framework)

        return tests

    async def _generate_python_tests(
        self,
        code: str,
        framework: str
    ) -> List[TestCase]:
        """生成Python测试"""
        tests = []

        # 检测函数
        func_pattern = r'def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\w+))?'
        for match in re.finditer(func_pattern, code):
            func_name = match.group(1)
            params = match.group(2)
            return_type = match.group(3) or "Any"

            if framework == "pytest":
                test_code = f'''import pytest
from your_module import {func_name}

def test_{func_name}():
    # TODO: Add test inputs
    result = {func_name}()
    assert result is not None'''
            else:
                test_code = f'''import unittest
from your_module import {func_name}

class Test{func_name.title()}(unittest.TestCase):
    def test_{func_name}(self):
        result = {func_name}()
        self.assertIsNotNone(result)'''

            tests.append(TestCase(
                name=f"test_{func_name}",
                code=test_code
            ))

        # 检测类
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)

            if framework == "pytest":
                test_code = f'''import pytest
from your_module import {class_name}

def test_{class_name.lower()}_creation():
    instance = {class_name}()
    assert instance is not None'''
            else:
                test_code = f'''import unittest
from your_module import {class_name}

class Test{class_name}(unittest.TestCase):
    def test_creation(self):
        instance = {class_name}()
        self.assertIsNotNone(instance)'''

            tests.append(TestCase(
                name=f"test_{class_name.lower()}_creation",
                code=test_code
            ))

        return tests

    async def _generate_js_tests(
        self,
        code: str,
        framework: str
    ) -> List[TestCase]:
        """生成JavaScript测试"""
        tests = []

        # 检测函数
        func_pattern = r'(?:function|const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?(.*?)\)?\s*=>|function\s+(\w+)\s*\(?(.*?)\)?'
        for match in re.finditer(func_pattern, code):
            func_name = match.group(1) or match.group(3)
            params = match.group(2) or match.group(4)

            if framework == "jest":
                test_code = f'''describe('{func_name}', () => {{
    test('should work', () => {{
        const result = {func_name}();
        expect(result).toBeDefined();
    }});
}});'''
            else:
                test_code = f'''describe('{func_name}', function() {{
    it('should work', function() {{
        const result = {func_name}();
        assert(result !== undefined);
    }});
}});'''

            tests.append(TestCase(
                name=f"test_{func_name}",
                code=test_code
            ))

        return tests


class AICodingAssistant:
    """AI编程助手核心"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.code_generator = CodeGenerator(llm_client)
        self.error_diagnoser = ErrorDiagnoser()
        self.performance_analyzer = PerformanceAnalyzer()
        self.doc_generator = DocumentationGenerator()
        self.test_generator = TestGenerator()
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        """启动AI助手"""
        self._running = True
        asyncio.create_task(self._process_tasks())

    async def stop(self):
        """停止AI助手"""
        self._running = False

    async def _process_tasks(self):
        """处理任务队列"""
        while self._running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                await self._execute_task(task)
            except asyncio.TimeoutError:
                continue

    async def _execute_task(self, task: AITask):
        """执行任务"""
        try:
            if task.task_type == TaskType.CODE_GENERATION:
                result = await self.code_generator.generate_code(
                    task.prompt,
                    task.context.get("language", "python"),
                    task.context
                )
            elif task.task_type == TaskType.CODE_COMPLETION:
                result = await self.code_generator.complete_code(
                    task.context.get("code", ""),
                    task.context.get("position", 0),
                    task.context.get("language", "python")
                )
            elif task.task_type == TaskType.ERROR_DIAGNOSIS:
                result = self.error_diagnoser.diagnose(
                    task.prompt,
                    task.context.get("code", ""),
                    task.context.get("language", "python")
                )
            elif task.task_type == TaskType.PERFORMANCE_OPTIMIZATION:
                result = await self.performance_analyzer.analyze(
                    task.context.get("code", ""),
                    task.context.get("language", "python")
                )
            elif task.task_type == TaskType.DOCUMENTATION:
                result = await self.doc_generator.generate_docstring(
                    task.context.get("code", ""),
                    task.context.get("language", "python")
                )
            elif task.task_type == TaskType.TEST_GENERATION:
                result = await self.test_generator.generate_tests(
                    task.context.get("code", ""),
                    task.context.get("language", "python")
                )
            else:
                result = None

            return result

        except Exception as e:
            return {"error": str(e)}

    async def submit_task(self, task: AITask) -> Any:
        """提交任务"""
        await self.task_queue.put(task)
        return task.id

    async def get_completion_suggestions(
        self,
        code: str,
        position: int,
        language: str
    ) -> List[AIRecommendation]:
        """获取补全建议"""
        # 使用补全引擎获取建议
        completions = await self.code_generator.complete_code(
            code, position, language
        )

        suggestions = []
        if completions:
            suggestions.append(AIRecommendation(
                type="completion",
                message="代码补全",
                code_snippet=completions,
                confidence=0.8
            ))

        return suggestions

    async def diagnose_error(
        self,
        error_message: str,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """诊断错误"""
        return self.error_diagnoser.diagnose(error_message, code, language)

    async def analyze_performance(
        self,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """分析性能"""
        return await self.performance_analyzer.analyze(code, language)

    async def generate_documentation(
        self,
        code: str,
        language: str,
        style: str = "google"
    ) -> str:
        """生成文档"""
        return await self.doc_generator.generate_docstring(code, language, style)

    async def generate_tests(
        self,
        code: str,
        language: str,
        framework: str = "pytest"
    ) -> List[TestCase]:
        """生成测试"""
        return await self.test_generator.generate_tests(code, language, framework)

    async def suggest_refactoring(
        self,
        code: str,
        language: str
    ) -> Optional[RefactorPlan]:
        """建议重构"""
        # 简单的重构建议
        plan = RefactorPlan(
            original_code=code,
            suggested_code=code,
            changes=[],
            risks=["重构可能引入新错误"],
            benefits=["提高代码可读性", "减少复杂度"]
        )

        # 检查长函数
        lines = code.split('\n')
        if len(lines) > 100:
            plan.changes.append({
                "type": "extract_function",
                "description": "将长函数拆分为多个小函数"
            })

        # 检查重复代码
        # ... (简化实现)

        return plan

    def get_assistant_stats(self) -> Dict[str, Any]:
        """获取助手统计"""
        return {
            "queue_size": self.task_queue.qsize(),
            "running": self._running,
            "capabilities": [
                "code_completion",
                "code_generation",
                "error_diagnosis",
                "performance_analysis",
                "documentation_generation",
                "test_generation",
                "refactoring_suggestion"
            ]
        }
