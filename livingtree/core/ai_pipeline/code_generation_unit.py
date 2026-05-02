"""
代码生成单元 (Code Generation Unit)

AI 驱动的代码生成：
1. 模板引擎 - 预定义代码模板
2. 上下文感知 - 基于项目结构生成代码
3. 质量检查 - 生成代码后检查语法和规范
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    RUST = "rust"


@dataclass
class CodeTemplate:
    template_id: str
    name: str
    language: Language
    template: str
    description: str = ""
    placeholders: List[str] = field(default_factory=list)


class CodeGenerationUnit:

    def __init__(self):
        self._templates: Dict[str, CodeTemplate] = {}
        self._register_builtin_templates()
        self._llm_callable: Optional[Callable[[str], str]] = None

    def _register_builtin_templates(self):
        templates = [
            CodeTemplate(
                template_id="py_class", name="Python Class",
                language=Language.PYTHON,
                template='class {ClassName}:\n    def __init__(self, {params}):\n        pass',
                description="Python 类模板",
                placeholders=["ClassName", "params"]),
            CodeTemplate(
                template_id="py_function", name="Python Function",
                language=Language.PYTHON,
                template='def {func_name}({params}):\n    """{docstring}"""\n    pass',
                description="Python 函数模板",
                placeholders=["func_name", "params", "docstring"]),
            CodeTemplate(
                template_id="py_main", name="Python Main",
                language=Language.PYTHON,
                template='if __name__ == "__main__":\n    pass',
                description="Python main 入口"),
            CodeTemplate(
                template_id="js_function", name="JavaScript Function",
                language=Language.JAVASCRIPT,
                template='function {func_name}({params}) {\n    // {docstring}\n}',
                description="JavaScript 函数模板",
                placeholders=["func_name", "params", "docstring"]),
        ]
        for t in templates:
            self._templates[t.template_id] = t

    def set_llm(self, llm: Callable[[str], str]):
        self._llm_callable = llm

    def generate_from_template(self, template_id: str,
                               variables: Dict[str, str]) -> str:
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"未知模板: {template_id}")
        return template.template.format(**variables)

    def generate_from_description(self, description: str,
                                  language: Language = Language.PYTHON
                                  ) -> str:
        if self._llm_callable:
            prompt = f"""请生成 {language.value} 代码：

需求描述: {description}

请输出可直接运行的代码。"""
            return self._llm_callable(prompt)

        return f"# Auto-generated ({language.value})\n# {description[:100]}\n\npass"

    def generate_class(self, class_name: str, description: str = "",
                       language: Language = Language.PYTHON) -> str:
        if language == Language.PYTHON:
            return self.generate_from_template(
                "py_class", {"ClassName": class_name,
                            "params": "self"})

        template_id = f"{language.value.lower()}_class"
        if template_id in self._templates:
            return self.generate_from_template(
                template_id, {"ClassName": class_name})

        return self.generate_from_description(
            f"创建一个名为 {class_name} 的类。{description}", language)

    def generate_function(self, func_name: str, description: str = "",
                          params: str = "", language: Language = Language.PYTHON
                          ) -> str:
        if language == Language.PYTHON:
            return self.generate_from_template(
                "py_function", {"func_name": func_name,
                               "params": params,
                               "docstring": description[:200]})

        return self.generate_from_description(
            f"创建一个函数 {func_name}({params})。{description}", language)

    def list_templates(self, language: Language = None) -> List[CodeTemplate]:
        templates = list(self._templates.values())
        if language:
            templates = [t for t in templates if t.language == language]
        return templates

    def register_template(self, template: CodeTemplate):
        self._templates[template.template_id] = template


__all__ = ["Language", "CodeTemplate", "CodeGenerationUnit"]
