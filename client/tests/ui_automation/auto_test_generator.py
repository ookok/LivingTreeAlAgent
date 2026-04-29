"""
自动测试代码生成器

根据业务逻辑代码自动生成测试代码：
- 分析目标类的结构（属性、方法、信号）
- 生成对应的单元测试
- 自动查找测试数据文件
- 支持自定义测试模板

核心功能：
1. 代码解析 - 分析类结构
2. 测试生成 - 根据结构生成测试
3. 数据绑定 - 自动关联测试数据
"""

import os
import re
import ast
import inspect
from typing import (
    List, Dict, Any, Optional, Callable, Type,
    get_type_hints, get_origin, get_args
)
from dataclasses import dataclass, field
from enum import Enum

from .resource_locator import ResourceLocator, get_resource_locator, find_test_data_file


# ─────────────────────────────────────────────────────────────────────────────
# 代码分析
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MethodInfo:
    """方法信息"""
    name: str
    signature: str
    parameters: List[str]
    return_type: str = ""
    docstring: str = ""
    is_async: bool = False
    is_property: bool = False
    decorators: List[str] = field(default_factory=list)


@dataclass
class SignalInfo:
    """Qt 信号信息"""
    name: str
    signature: str
    types: List[str] = field(default_factory=list)


@dataclass
class PropertyInfo:
    """属性信息"""
    name: str
    type_hint: str = ""
    default_value: Any = None
    readonly: bool = False


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    module: str
    bases: List[str]
    methods: List[MethodInfo] = field(default_factory=list)
    signals: List[SignalInfo] = field(default_factory=list)
    properties: List[PropertyInfo] = field(default_factory=list)
    docstring: str = ""
    file_path: str = ""


class CodeAnalyzer:
    """
    代码分析器

    分析 Python 类结构，提取：
    - 方法定义
    - Qt 信号
    - 属性定义
    - 类型注解
    """

    def __init__(self):
        self._class_cache: Dict[str, ClassInfo] = {}

    def analyze_class(self, cls: Type) -> ClassInfo:
        """
        分析类结构

        Args:
            cls: 要分析的类

        Returns:
            类信息
        """
        cache_key = f"{cls.__module__}.{cls.__name__}"
        if cache_key in self._class_cache:
            return self._class_cache[cache_key]

        info = ClassInfo(
            name=cls.__name__,
            module=cls.__module__,
            bases=[b.__name__ for b in getattr(cls, '__bases__', [])],
            docstring=inspect.getdoc(cls) or "",
        )

        # 分析方法
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith('_') and not name.startswith('__'):
                continue  # 跳过私有方法

            try:
                sig = inspect.signature(method)
                params = [p.name for p in sig.parameters.values()]

                method_info = MethodInfo(
                    name=name,
                    signature=str(sig),
                    parameters=params,
                    is_async=inspect.iscoroutinefunction(method),
                    docstring=inspect.getdoc(method) or "",
                )

                # 获取装饰器
                try:
                    source = inspect.getsource(method)
                    decos = re.findall(r'@(\w+)', source[:source.find('def ')])
                    method_info.decorators = decos
                except Exception:
                    pass

                info.methods.append(method_info)
            except (ValueError, TypeError):
                continue

        # 分析 Qt 信号
        for name in dir(cls):
            if name.startswith('_'):
                continue
            attr = getattr(cls, name, None)
            if isinstance(attr, pyqtSignal) if 'pyqtSignal' in dir() else False:
                # 获取信号的签名
                try:
                    sig_info = SignalInfo(name=name, signature="")
                    info.signals.append(sig_info)
                except Exception:
                    pass

        # 分析属性（通过 type hints）
        try:
            hints = get_type_hints(cls)
            for name, hint in hints.items():
                hint_str = self._format_type_hint(hint)
                info.properties.append(PropertyInfo(
                    name=name,
                    type_hint=hint_str
                ))
        except Exception:
            pass

        self._class_cache[cache_key] = info
        return info

    def analyze_file(self, file_path: str) -> List[ClassInfo]:
        """分析文件中的所有类"""
        classes = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = self._parse_ast_class(node, file_path)
                    classes.append(class_info)

        except Exception:
            pass

        return classes

    def _parse_ast_class(self, node: ast.ClassDef, file_path: str) -> ClassInfo:
        """解析 AST 节点"""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)

        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                if not item.name.startswith('_'):
                    params = [arg.arg for arg in item.args.args]
                    methods.append(MethodInfo(
                        name=item.name,
                        signature=f"({', '.join(params)})",
                        parameters=params,
                        is_async=isinstance(item, ast.AsyncFunctionDef),
                    ))

        return ClassInfo(
            name=node.name,
            module="",
            bases=bases,
            methods=methods,
            file_path=file_path
        )

    def _format_type_hint(self, hint) -> str:
        """格式化类型提示"""
        origin = get_origin(hint)
        args = get_args(hint)

        if origin is None:
            return getattr(hint, '__name__', str(hint))

        if origin is list:
            return f"List[{self._format_type_hint(args[0]) if args else 'Any'}]"
        if origin is dict:
            return f"Dict[{self._format_type_hint(args[0]) if args else 'Any'}, {self._format_type_hint(args[1]) if len(args) > 1 else 'Any'}]"
        if origin is tuple:
            return f"Tuple[{', '.join(self._format_type_hint(a) for a in args)}]"
        if origin is type(None):
            return "None"

        return str(hint)


# 导入 PyQt6 信号类型（延迟）
try:
    from PyQt6.QtCore import pyqtSignal
except ImportError:
    pyqtSignal = None


# ─────────────────────────────────────────────────────────────────────────────
# 测试代码生成器
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeGenerator:
    """
    测试代码生成器

    根据类信息自动生成测试代码：
    - 单元测试
    - 组件测试
    - 集成测试

    Usage:
        generator = TestCodeGenerator()
        generator.set_template("pytest")

        # 生成测试
        code = generator.generate_tests(class_info)
        print(code)
    """

    TEMPLATES = {
        "pytest": "pytest",
        "unittest": "unittest",
        "qtest": "qtest",  # PyQt6 测试
    }

    def __init__(
        self,
        template: str = "pytest",
        resource_locator: ResourceLocator = None
    ):
        self.template = template
        self._resource_locator = resource_locator
        self._analyzer = CodeAnalyzer()

    @property
    def resource_locator(self) -> ResourceLocator:
        """获取资源定位器"""
        if self._resource_locator is None:
            self._resource_locator = get_resource_locator()
        return self._resource_locator

    def set_template(self, template: str):
        """设置测试模板"""
        if template in self.TEMPLATES:
            self.template = template

    def generate_tests(
        self,
        class_info: ClassInfo,
        test_data_files: List[str] = None,
        include_signals: bool = True,
        include_properties: bool = True
    ) -> str:
        """
        生成测试代码

        Args:
            class_info: 类信息
            test_data_files: 关联的测试数据文件
            include_signals: 是否包含信号测试
            include_properties: 是否包含属性测试

        Returns:
            生成的测试代码
        """
        template = self.template

        if template == "pytest":
            return self._generate_pytest_tests(class_info, test_data_files, include_signals, include_properties)
        elif template == "unittest":
            return self._generate_unittest_tests(class_info, test_data_files)
        elif template == "qtest":
            return self._generate_qtest_tests(class_info, test_data_files)
        else:
            return self._generate_pytest_tests(class_info, test_data_files, include_signals, include_properties)

    def _generate_pytest_tests(
        self,
        class_info: ClassInfo,
        test_data_files: List[str] = None,
        include_signals: bool = True,
        include_properties: bool = True
    ) -> str:
        """生成 pytest 格式测试"""
        lines = []
        lines.append('"""')
        lines.append(f"自动生成的 {class_info.name} 测试")
        lines.append(f'"""\n')

        lines.append("import pytest")
        lines.append("from unittest.mock import Mock, MagicMock\n")
        lines.append(f"from {class_info.module} import {class_info.name}\n" if class_info.module else "\n")

        # 测试数据文件
        if test_data_files:
            lines.append("# 测试数据文件")
            for f in test_data_files:
                lines.append(f"# - {f}")
            lines.append("")

        lines.append(f"class Test{class_info.name}:")
        lines.append(f'    """{class_info.name} 测试类"""\n')

        # setup
        lines.append("    @pytest.fixture")
        lines.append("    def instance(self):")
        lines.append(f"        return {class_info.name}()\n")

        # 测试方法
        for method in class_info.methods:
            lines.append(self._generate_method_test(method))

        # 测试信号
        if include_signals and class_info.signals:
            lines.append(self._generate_signal_tests(class_info.signals))

        # 测试属性
        if include_properties and class_info.properties:
            lines.append(self._generate_property_tests(class_info.properties))

        return '\n'.join(lines)

    def _generate_method_test(self, method: MethodInfo) -> str:
        """生成单个方法测试"""
        lines = []

        # 方法文档
        if method.docstring:
            lines.append(f'    def test_{method.name}(self, instance):')
            lines.append(f'        """{method.docstring[:50]}..."""')
        else:
            lines.append(f'    def test_{method.name}(self, instance):')

        # 参数处理
        if len(method.parameters) > 1:  # 排除 self
            params = method.parameters[1:]  # 跳过 self
            lines.append(f"        # {method.signature}")

            # 查找测试数据
            test_data = self._find_test_data_for_method(method.name, params)

            if test_data:
                lines.append(f"        test_input = {test_data}")
            else:
                lines.append("        # TODO: 添加测试数据")
                lines.append("        pass")
        else:
            lines.append("        result = instance." + method.name + "()")
            lines.append("        assert result is not None  # TODO: 验证结果")

        lines.append("")
        return '\n'.join(lines)

    def _generate_signal_tests(self, signals: List[SignalInfo]) -> str:
        """生成信号测试"""
        lines = []
        lines.append("    def test_signals(self, instance):")
        lines.append('        """测试 Qt 信号"""')

        for signal in signals:
            lines.append(f"        # Signal: {signal.name}")
            lines.append(f"        # 连接到 mock")
            lines.append(f"        callback = Mock()")
            lines.append(f"        instance.{signal.name}.connect(callback)")
            lines.append(f"        # TODO: 触发信号并验证")
            lines.append("")

        lines.append("        # assert callback.called")
        lines.append("")
        return '\n'.join(lines)

    def _generate_property_tests(self, properties: List[PropertyInfo]) -> str:
        """生成属性测试"""
        lines = []
        lines.append("    def test_properties(self, instance):")
        lines.append('        """测试属性"""')

        for prop in properties:
            lines.append(f"        # Property: {prop.name} ({prop.type_hint})")
            lines.append(f"        # value = instance.{prop.name}")
            lines.append(f"        # assert value is not None  # TODO: 验证")

        lines.append("")
        return '\n'.join(lines)

    def _find_test_data_for_method(self, method_name: str, params: List[str]) -> Optional[str]:
        """为方法查找测试数据"""
        # 尝试查找相关的测试数据文件
        keywords = [method_name] + params[:2]  # 方法名 + 前两个参数

        files = self.resource_locator.find_test_data(
            related_file=method_name,
            limit=1
        )

        if files:
            resource = files[0]
            if resource.category.value in ["json", "text"]:
                return f'"{resource.full_path}"  # {resource.path}'

        return None

    def _generate_unittest_tests(self, class_info: ClassInfo, test_data_files: List[str] = None) -> str:
        """生成 unittest 格式测试"""
        lines = []
        lines.append('"""')
        lines.append(f"自动生成的 {class_info.name} 测试")
        lines.append('"""\n')

        lines.append("import unittest\n")
        lines.append(f"from {class_info.module} import {class_info.name}\n" if class_info.module else "\n")

        lines.append(f"class Test{class_info.name}(unittest.TestCase):")
        lines.append(f'    """{class_info.name} 测试类"""\n')

        lines.append("    def setUp(self):")
        lines.append(f"        self.instance = {class_info.name}()\n")

        for method in class_info.methods:
            lines.append(f"    def test_{method.name}(self):")
            lines.append(f"        result = self.instance.{method.name}()")
            lines.append("        self.assertIsNotNone(result)  # TODO")
            lines.append("")

        return '\n'.join(lines)

    def _generate_qtest_tests(self, class_info: ClassInfo, test_data_files: List[str] = None) -> str:
        """生成 PyQt6 QTest 格式测试"""
        lines = []
        lines.append('"""')
        lines.append(f"自动生成的 {class_info.name} PyQt6 测试")
        lines.append('"""\n')

        lines.append("import sys")
        lines.append("from PyQt6.QtWidgets import QApplication")
        lines.append("from PyQt6.QtCore import Qt")
        lines.append("from PyQt6.QtTest import QTest")
        lines.append("import unittest\n")
        lines.append(f"from {class_info.module} import {class_info.name}\n" if class_info.module else "\n")

        lines.append("class TestQ{}(unittest.TestCase):".format(class_info.name))
        lines.append(f'    """{class_info.name} PyQt6 测试类"""\n')

        lines.append("    @classmethod")
        lines.append("    def setUpClass(cls):")
        lines.append("        cls.app = QApplication.instance() or QApplication(sys.argv)\n")

        lines.append("    def setUp(self):")
        lines.append(f"        self.widget = {class_info.name}()\n")

        for method in class_info.methods:
            lines.append(f"    def test_{method.name}(self):")
            lines.append(f'        """{method.docstring}"""')
            lines.append(f"        # 验证 widget 可见")
            lines.append("        self.assertTrue(self.widget.isVisible())")
            lines.append("")

        return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 完整测试套件生成器
# ─────────────────────────────────────────────────────────────────────────────

class TestSuiteGenerator:
    """
    完整测试套件生成器

    分析整个模块，生成完整的测试套件：
    - 测试所有公开类
    - 自动关联测试数据
    - 生成测试运行器
    """

    def __init__(
        self,
        project_root: str = None,
        resource_locator: ResourceLocator = None
    ):
        self._project_root = project_root
        self._resource_locator = resource_locator
        self._analyzer = CodeAnalyzer()
        self._generator = TestCodeGenerator(resource_locator=resource_locator)

    @property
    def resource_locator(self) -> ResourceLocator:
        if self._resource_locator is None:
            self._resource_locator = get_resource_locator(self._project_root)
        return self._resource_locator

    def generate_module_tests(
        self,
        module_path: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        生成模块测试

        Args:
            module_path: 模块路径（如 opencode_ide_panel.py）
            output_dir: 输出目录

        Returns:
            {文件名: 测试代码} 字典
        """
        results = {}

        # 分析文件中的所有类
        classes = self._analyzer.analyze_file(module_path)

        for cls_info in classes:
            if not cls_info.name.startswith('_'):
                # 查找测试数据
                test_data = self._find_test_data(cls_info)

                # 生成测试代码
                test_code = self._generator.generate_tests(
                    cls_info,
                    test_data_files=test_data
                )

                # 确定输出文件名
                test_name = f"test_{cls_info.name.lower()}.py"
                results[test_name] = test_code

        return results

    def _find_test_data(self, class_info: ClassInfo) -> List[str]:
        """查找测试数据文件"""
        keywords = [class_info.name]

        # 添加方法名作为关键词
        for method in class_info.methods[:5]:  # 最多5个
            keywords.append(method.name)

        files = self.resource_locator.find_test_data(
            related_to=class_info.name,
            limit=3
        )

        return [f.full_path for f in files]

    def generate_test_runner(
        self,
        module_path: str,
        test_names: List[str] = None
    ) -> str:
        """生成测试运行器"""
        module_name = os.path.splitext(os.path.basename(module_path))[0]

        lines = []
        lines.append('"""')
        lines.append(f"自动生成的测试运行器 - {module_name}")
        lines.append('"""\n')

        lines.append("import sys")
        lines.append("import unittest\n")

        lines.append(f"# 测试模块")
        if test_names:
            for name in test_names:
                lines.append(f"from .{name.replace('.py', '')} import *")
        else:
            lines.append(f"from . import *")

        lines.append("\nif __name__ == '__main__':")
        lines.append("    # 创建测试套件")
        lines.append("    loader = unittest.TestLoader()")
        lines.append("    suite = unittest.TestSuite()\n")

        if test_names:
            for name in test_names:
                test_class = f"Test{''.join(w.title() for w in name.replace('test_', '').replace('.py', '').split('_'))}"
                lines.append(f"    suite.addTests(loader.loadTestsFromTestCase({test_class}))")
        else:
            lines.append("    suite.addTests(loader.discover('.'))")

        lines.append("\n    # 运行测试")
        lines.append("    runner = unittest.TextTestRunner(verbosity=2)")
        lines.append("    result = runner.run(suite)")
        lines.append("    sys.exit(0 if result.wasSuccessful() else 1)")

        return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────────────────────────────────────

def auto_generate_tests(
    class_or_module,
    template: str = "pytest",
    project_root: str = None
) -> str:
    """
    便捷函数：自动生成测试代码

    Args:
        class_or_module: 类或模块
        template: 测试模板
        project_root: 项目根目录

    Returns:
        生成的测试代码
    """
    generator = TestCodeGenerator(template=template)
    analyzer = CodeAnalyzer()

    if inspect.isclass(class_or_module):
        class_info = analyzer.analyze_class(class_or_module)
    else:
        class_info = analyzer.analyze_file(class_or_module)[0]

    return generator.generate_tests(class_info)


def generate_opencode_ide_tests(
    panel_file: str = None,
    output_dir: str = None
) -> Dict[str, str]:
    """
    为 OpenCode IDE 面板生成测试

    Args:
        panel_file: 面板文件路径
        output_dir: 输出目录

    Returns:
        {文件名: 测试代码}
    """
    if panel_file is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        panel_file = os.path.join(project_root, "src", "presentation", "modules", "ide", "opencode_ide_panel.py")

    generator = TestSuiteGenerator(project_root=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(panel_file)))))

    return generator.generate_module_tests(panel_file, output_dir)
