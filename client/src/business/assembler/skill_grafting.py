"""
🛠️ 技能嫁接 (Skill Grafting)
=============================

从代码库/API文档生成可用的Skill

输入：代码库 URL（Go/Rust/Node/Python）或 API 文档
动作：分析库能力 → 生成统一 Skill YAML + 适配函数 → 注入技能库

生成物：
• skills/pdf_extract.skill.yml：定义命令、参数、示例
• skills/adapters/pdf_extract.py：封装库调用（复用装配园的适配器）
"""

import re
import ast
from typing import Optional, Callable, Any, List
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from .knowledge_incubator import GeneratedSkill, KnowledgeBank


# ==================== 代码分析器 ====================

@dataclass
class CodeFunction:
    """代码函数"""
    name: str
    signature: str
    docstring: str
    parameters: List[str]
    return_type: str
    is_async: bool = False


@dataclass
class CodeAnalysis:
    """代码分析结果"""
    language: str
    module_name: str
    functions: List[CodeFunction]
    classes: List[str]
    imports: List[str]
    exports: List[str]


class CodeAnalyzer:
    """代码分析器"""

    LANG_PATTERNS = {
        "python": {
            "function": r'(?:async\s+)?def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\w+))?:',
            "class": r'class\s+(\w+)(?:\([^)]*\))?:',
            "import": r'(?:from\s+(\S+)\s+)?import\s+([^\n]+)',
        },
        "javascript": {
            "function": r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\((.*?)\)',
            "arrow": r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\((.*?)\)\s*=>',
            "method": r'(?:async\s+)?(\w+)\s*\((.*?)\)\s*\{',
            "class": r'class\s+(\w+)(?:\s+extends\s+\w+)?',
            "import": r'(?:import|export)\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
        },
        "typescript": {
            "function": r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]',
            "interface": r'interface\s+(\w+)',
            "type": r'type\s+(\w+)\s*=',
        },
        "go": {
            "function": r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\((.*?)\)',
            "struct": r'type\s+(\w+)\s+struct\s*\{',
            "import": r'import\s+(?:"([^"]+)"|\(\s*([\s\S]*?)\s*\))',
        },
        "rust": {
            "function": r'pub\s+(?:async\s+)?fn\s+(\w+)\s*<.*?>\s*\((.*?)\)\s*(?:->\s*.+?)?\{',
            "struct": r'struct\s+(\w+)',
            "impl": r'impl(?:\s+\w+)?\s*(?:for\s+\w+)?\s*\{',
            "use": r'use\s+([\w:]+)',
        },
    }

    def analyze(self, code: str, language: str) -> CodeAnalysis:
        """分析代码"""
        language = language.lower()

        if language == "python":
            return self._analyze_python(code)
        elif language in ("javascript", "typescript"):
            return self._analyze_javascript(code, language)
        elif language == "go":
            return self._analyze_go(code)
        elif language == "rust":
            return self._analyze_rust(code)
        else:
            return self._analyze_generic(code, language)

    def _analyze_python(self, code: str) -> CodeAnalysis:
        """分析Python代码"""
        functions = []
        classes = []
        imports = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    docstring = ast.get_docstring(node) or ""
                    params = [arg.arg for arg in node.args.args]
                    return_type = "None"
                    if node.returns:
                        return_type = ast.unparse(node.returns)

                    functions.append(CodeFunction(
                        name=node.name,
                        signature=self._format_python_sig(node.name, params, return_type),
                        docstring=docstring[:200],
                        parameters=params,
                        return_type=return_type,
                        is_async=isinstance(node, ast.AsyncFunctionDef)
                    ))

                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    else:
                        imports.append(node.module or "")

        except SyntaxError:
            functions = self._analyze_python_regex(code)

        return CodeAnalysis(
            language="python",
            module_name=self._extract_module_name(code),
            functions=functions,
            classes=classes,
            imports=imports,
            exports=[f.name for f in functions]
        )

    def _analyze_python_regex(self, code: str) -> List[CodeFunction]:
        """用正则表达式分析Python代码"""
        functions = []
        func_pattern = r'(?:async\s+)?def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*.+?)?:'
        for match in re.finditer(func_pattern, code):
            name = match.group(1)
            params_str = match.group(2)
            params = [p.strip().split(':')[0].strip() for p in params_str.split(',') if p.strip()]

            functions.append(CodeFunction(
                name=name,
                signature=f"def {name}({params_str})",
                docstring="",
                parameters=params,
                return_type="Any",
                is_async="async def" in code[match.start()-10:match.start()]
            ))

        return functions

    def _format_python_sig(self, name: str, params: List[str], return_type: str) -> str:
        """格式化Python签名"""
        params_str = ", ".join(params)
        return f"def {name}({params_str}) -> {return_type}"

    def _extract_module_name(self, code: str) -> str:
        """提取模块名"""
        if "__name__" in code:
            match = re.search(r["']__main__["']", code)
            if match:
                return "main"
        return "module"

    def _analyze_javascript(self, code: str, language: str) -> CodeAnalysis:
        """分析JavaScript/TypeScript代码"""
        functions = []
        classes = []
        imports = []

        patterns = self.LANG_PATTERNS.get(language, self.LANG_PATTERNS["javascript"])

        for pattern_name, pattern in [("function", patterns.get("function", "")),
                                       ("arrow", patterns.get("arrow", "")),
                                       ("method", patterns.get("method", ""))]:
            if not pattern:
                continue
            for match in re.finditer(pattern, code):
                if pattern_name == "function":
                    name = match.group(1)
                    params_str = match.group(2) if match.lastindex >= 2 else ""
                elif pattern_name == "arrow":
                    name = match.group(1)
                    params_str = match.group(2) if match.lastindex >= 2 else ""
                else:
                    name = match.group(1)
                    params_str = match.group(2) if match.lastindex >= 2 else ""

                params = [p.strip().split(':')[0].strip() for p in params_str.split(',') if p.strip()]

                functions.append(CodeFunction(
                    name=name,
                    signature=f"{name}({params_str})",
                    docstring="",
                    parameters=params,
                    return_type="any"
                ))

        class_pattern = patterns.get("class", "")
        for match in re.finditer(class_pattern, code):
            classes.append(match.group(1))

        import_pattern = patterns.get("import", "")
        for match in re.finditer(import_pattern, code):
            module = match.group(1) if match.lastindex >= 1 else match.group(0)
            imports.append(module)

        return CodeAnalysis(
            language=language,
            module_name="module",
            functions=functions,
            classes=classes,
            imports=imports,
            exports=[f.name for f in functions]
        )

    def _analyze_go(self, code: str) -> CodeAnalysis:
        """分析Go代码"""
        functions = []
        classes = []

        func_pattern = r'func\s+(?:\(\w+\s+\*?(\w+)\)\s+)?(\w+)\s*\((.*?)\)(?:\s*(\w+))?\s*\{'
        for match in re.finditer(func_pattern, code):
            receiver = match.group(1)
            name = match.group(2)
            params_str = match.group(3)
            return_type = match.group(4) or ""

            params = []
            for p in params_str.split(','):
                p = p.strip()
                if p:
                    parts = p.split()
                    if len(parts) >= 2:
                        params.append(parts[1].replace('*', ''))

            if receiver:
                name = f"{receiver}.{name}"

            functions.append(CodeFunction(
                name=name,
                signature=f"func {name}({params_str}) {return_type}",
                docstring="",
                parameters=params,
                return_type=return_type
            ))

        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        for match in re.finditer(struct_pattern, code):
            classes.append(match.group(1))

        return CodeAnalysis(
            language="go",
            module_name="module",
            functions=functions,
            classes=classes,
            imports=[],
            exports=[f.name for f in functions]
        )

    def _analyze_rust(self, code: str) -> CodeAnalysis:
        """分析Rust代码"""
        functions = []
        classes = []

        func_pattern = r'pub\s+(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]+>)?\s*\((.*?)\)(?:\s*->\s*(.+?))?\s*\{'
        for match in re.finditer(func_pattern, code):
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3) or ""

            params = []
            for p in params_str.split(','):
                p = p.strip()
                if p:
                    parts = p.split(':')
                    if len(parts) >= 2:
                        params.append(parts[0].strip())

            functions.append(CodeFunction(
                name=name,
                signature=f"fn {name}({params_str}) -> {return_type}",
                docstring="",
                parameters=params,
                return_type=return_type
            ))

        struct_pattern = r'struct\s+(\w+)'
        for match in re.finditer(struct_pattern, code):
            classes.append(match.group(1))

        return CodeAnalysis(
            language="rust",
            module_name="crate",
            functions=functions,
            classes=classes,
            imports=[],
            exports=[f.name for f in functions if not f.name.startswith('_')]
        )

    def _analyze_generic(self, code: str, language: str) -> CodeAnalysis:
        """通用代码分析（基于正则）"""
        functions = []
        patterns = self.LANG_PATTERNS.get(language, {})

        for pattern_name, pattern in patterns.items():
            if not pattern:
                continue
            for match in re.finditer(pattern, code):
                name = match.group(1)
                functions.append(CodeFunction(
                    name=name,
                    signature=name,
                    docstring="",
                    parameters=[],
                    return_type="unknown"
                ))

        return CodeAnalysis(
            language=language,
            module_name="module",
            functions=functions,
            classes=[],
            imports=[],
            exports=[f.name for f in functions]
        )


class SkillGrafting:
    """
    技能嫁接器

    从代码分析结果生成Skill
    """

    def __init__(self, knowledge_bank: KnowledgeBank, code_analyzer: CodeAnalyzer = None):
        self.knowledge_bank = knowledge_bank
        self.code_analyzer = code_analyzer or CodeAnalyzer()

    async def graft(
        self,
        code: str,
        repo_url: str = "",
        language: str = "python",
        repo_name: str = "",
        progress_callback: Optional[Callable] = None,
    ) -> tuple[bool, str, GeneratedSkill]:
        """
        执行技能嫁接

        Args:
            code: 代码内容
            repo_url: 仓库URL
            language: 编程语言
            repo_name: 仓库名
            progress_callback: 进度回调

        Returns:
            (success, message, skill)
        """
        if progress_callback:
            await progress_callback("🛠️ 开始技能嫁接...")

        try:
            if progress_callback:
                await progress_callback("🔍 分析代码结构...")
            analysis = self.code_analyzer.analyze(code, language)

            if progress_callback:
                await progress_callback(f"📊 发现 {len(analysis.functions)} 个函数, {len(analysis.classes)} 个类...")

            if progress_callback:
                await progress_callback("⚙️ 生成Skill配置...")
            skill = self._generate_skill(
                analysis=analysis,
                repo_url=repo_url,
                repo_name=repo_name or analysis.module_name,
                language=language
            )

            if progress_callback:
                await progress_callback("🔌 生成适配器代码...")
            skill = self._generate_adapter(skill, analysis)

            if progress_callback:
                await progress_callback("💾 保存Skill...")
            success, message = self.knowledge_bank.save_skill(skill)

            if success:
                if progress_callback:
                    await progress_callback(f"✅ {message}")
                return True, message, skill
            else:
                if progress_callback:
                    await progress_callback(f"⚠️ {message}")
                return False, message, skill

        except Exception as e:
            error_msg = f"嫁接失败: {e}"
            if progress_callback:
                await progress_callback(f"❌ {error_msg}")
            return False, error_msg, None

    def _generate_skill(
        self,
        analysis: CodeAnalysis,
        repo_url: str,
        repo_name: str,
        language: str,
    ) -> GeneratedSkill:
        """生成Skill元数据"""
        name = self._to_skill_name(repo_name)
        description = self._generate_description(analysis)
        triggers = self._generate_triggers(name, analysis)
        capabilities = [f.name for f in analysis.functions[:10]]
        parameters = self._generate_parameters(analysis)
        examples = self._generate_examples(analysis, language)

        skill = GeneratedSkill(
            name=name,
            description=description,
            version="1.0.0",
            category=self._detect_category(analysis),
            language=language,
            source_repo=repo_url,
            triggers=triggers,
            capabilities=capabilities,
            dependencies=analysis.imports[:5],
            parameters=parameters,
            examples=examples,
            created_at=datetime.now().isoformat(),
        )

        return skill

    def _to_skill_name(self, repo_name: str) -> str:
        """将仓库名转换为Skill名"""
        name = repo_name.lower()
        name = re.sub(r'^(lib|module|package|sdk)-?', '', name)
        name = re.sub(r'-?(js|ts|py|go|rs)$', '', name)
        name = re.sub(r'[^a-z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name)
        return name.strip('_')

    def _generate_description(self, analysis: CodeAnalysis) -> str:
        """生成描述"""
        parts = [f"一个{analysis.language}库"]

        if analysis.classes:
            parts.append(f"提供{len(analysis.classes)}个核心类")

        if analysis.functions:
            parts.append(f"包含{len(analysis.functions)}个函数")

        if analysis.exports:
            main_funcs = ", ".join(analysis.exports[:3])
            parts.append(f"主要导出: {main_funcs}")

        return "，".join(parts)

    def _generate_triggers(self, name: str, analysis: CodeAnalysis) -> list:
        """生成触发词"""
        triggers = [name.replace('_', ' ')]

        for func in analysis.functions[:5]:
            triggers.append(func.name.replace('_', ' '))

        for cls in analysis.classes[:3]:
            triggers.append(cls.replace('_', ' '))

        return list(set(triggers))[:15]

    def _generate_parameters(self, analysis: CodeAnalysis) -> dict:
        """生成参数定义"""
        params = {}

        for func in analysis.functions[:5]:
            param_def = {}
            for i, param in enumerate(func.parameters):
                param_def[param] = {
                    "type": "string",
                    "description": f"参数 {i+1}",
                    "required": i < 2
                }
            if param_def:
                params[func.name] = param_def

        return params

    def _generate_examples(self, analysis: CodeAnalysis, language: str) -> list:
        """生成使用示例"""
        examples = []

        for func in analysis.functions[:3]:
            if language == "python":
                example = f"```python\nfrom {analysis.module_name} import {func.name}\nresult = {func.name}({', '.join(func.parameters[:2]) if func.parameters else ''})\n```"
            elif language in ("javascript", "typescript"):
                example = f"```javascript\nconst {{ {func.name} }} = require('./{analysis.module_name}');\nconst result = await {func.name}({', '.join(func.parameters[:2]) if func.parameters else ''});\n```"
            elif language == "go":
                example = f"```go\nimport \"{analysis.module_name}\"\nresult := {analysis.module_name}.{func.name}({', '.join(func.parameters[:2]) if func.parameters else ''})\n```"
            elif language == "rust":
                example = f"```rust\nuse {analysis.module_name}::{{{func.name}}};\nlet result = {func.name}({', '.join(func.parameters[:2]) if func.parameters else ''});\n```"
            else:
                example = f"```\n{func.name}({', '.join(func.parameters[:2]) if func.parameters else ''})\n```"

            examples.append(example)

        return examples

    def _detect_category(self, analysis: CodeAnalysis) -> str:
        """检测分类"""
        keywords = {
            "network": ["http", "request", "fetch", "socket", "api", "client", "server"],
            "database": ["db", "sql", "query", "store", "connection", "redis", "mongo"],
            "file": ["file", "path", "read", "write", "parse", "upload", "download"],
            "auth": ["auth", "login", "jwt", "token", "password", "encrypt"],
            "utils": ["util", "helper", "format", "parse", "convert"],
            "data": ["data", "json", "xml", "encode", "decode", "transform"],
        }

        text = " ".join([
            " ".join(analysis.imports),
            " ".join([f.name for f in analysis.functions]),
            " ".join(analysis.classes)
        ]).lower()

        for category, kws in keywords.items():
            if any(kw in text for kw in kws):
                return category

        return "utils"

    def _generate_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> GeneratedSkill:
        """生成适配器代码"""

        if skill.language == "python":
            skill.adapter_content = self._generate_python_adapter(skill, analysis)
        elif skill.language in ("javascript", "typescript"):
            skill.adapter_content = self._generate_js_adapter(skill, analysis)
        elif skill.language == "go":
            skill.adapter_content = self._generate_go_adapter(skill, analysis)
        elif skill.language == "rust":
            skill.adapter_content = self._generate_rust_adapter(skill, analysis)
        else:
            skill.adapter_content = self._generate_generic_adapter(skill, analysis)

        return skill

    def _generate_python_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> str:
        """生成Python适配器"""
        lines = [
            f'"""',
            f'{skill.name} 适配器',
            f'由技能嫁接器自动生成',
            f'"""',
            f'',
            f'import json',
            f'from typing import Any, Dict, List, Optional',
            f'',
        ]

        if analysis.imports:
            for imp in analysis.imports[:5]:
                if imp:
                    lines.append(f"import {imp}")

        lines.extend([
            "",
            "",
            f"class {skill.name.title().replace('_', '')}Adapter:",
            f'    """',
            f'    {skill.description}',
            f'    """',
            f"",
            f"    def __init__(self):",
            f'        self.name = "{skill.name}"',
            f"        self.version = \"{skill.version}\"",
            f"",
        ])

        for func in analysis.functions[:10]:
            params_str = ", ".join(func.parameters)
            lines.extend([
                f"    def {func.name}(self, {params_str}) -> Any:",
                f'        """{func.docstring[:100] if func.docstring else "调用 " + func.name}"""',
                f"        pass",
                f"",
            ])

        lines.extend([
            f"    def invoke(self, action: str, params: Dict[str, Any]) -> Any:",
            f'        """统一调用入口"""',
            f"        if hasattr(self, action):",
            f"            return getattr(self, action)(**params)",
            f"        raise ValueError(f\"Unknown action: {{action}}\")",
            f"",
            f"    def list_actions(self) -> List[str]:",
            f'        """列出所有可用操作"""',
            f"        return [",
        ])

        for func in analysis.functions[:10]:
            lines.append(f'            "{func.name}",')

        lines.extend([
            f"        ]",
            f"",
        ])

        return "\n".join(lines)

    def _generate_js_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> str:
        """生成JavaScript适配器"""
        lines = [
            f"// {skill.name} 适配器",
            f"// 由技能嫁接器自动生成",
            f"",
            f"class {skill.name.replace('_', '').title()}Adapter {{",
            f"  constructor() {{",
            f'    this.name = "{skill.name}";',
            f'    this.version = "{skill.version}";',
            f"  }}",
            f"",
        ]

        for func in analysis.functions[:10]:
            lines.append(f"  async {func.name}({', '.join(func.parameters)}) {{")
            lines.append(f"    // TODO: 实现 {func.name}")
            lines.append(f"    throw new Error('Not implemented');")
            lines.append(f"  }}")
            lines.append(f"")

        lines.extend([
            f"  async invoke(action, params) {{",
            f"    if (typeof this[action] === 'function') {{",
            f"      return this[action](...Object.values(params));",
            f"    }}",
            f'    throw new Error(`Unknown action: ${{action}}`);',
            f"  }}",
            f"",
            f"  listActions() {{",
            f"    return [",
        ])

        for func in analysis.functions[:10]:
            lines.append(f'      "{func.name}",')

        lines.extend([
            f"    ];",
            f"  }}",
            f"}}",
            f"",
            f"module.exports = {skill.name.replace('_', '').title()}Adapter;",
        ])

        return "\n".join(lines)

    def _generate_go_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> str:
        """生成Go适配器"""
        lines = [
            f"// {skill.name} 适配器",
            f"// 由技能嫁接器自动生成",
            f"package main",
            f"",
        ]

        for func in analysis.functions[:10]:
            lines.append(f"func {func.name}({func.signature}) {{")
            lines.append(f"    // TODO: 实现 {func.name}")
            lines.append(f"}}")
            lines.append(f"")

        lines.append(f"// invoke 统一调用入口")
        lines.append(f"func invoke(action string) {{}}")

        return "\n".join(lines)

    def _generate_rust_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> str:
        """生成Rust适配器"""
        lines = [
            f"// {skill.name} 适配器",
            f"// 由技能嫁接器自动生成",
            f"",
            f"use std::error::Error;",
            f"",
        ]

        for func in analysis.functions[:10]:
            ret = f" -> ()" if not func.return_type or func.return_type == "()" else f" -> {func.return_type}"
            params = ", ".join(func.parameters) if func.parameters else ""
            lines.append(f"pub async fn {func.name}({params}){ret} {{")
            lines.append(f"    // TODO: 实现 {func.name}")
            lines.append(f"    todo!()")
            lines.append(f"}}")
            lines.append(f"")

        return "\n".join(lines)

    def _generate_generic_adapter(self, skill: GeneratedSkill, analysis: CodeAnalysis) -> str:
        """生成通用适配器"""
        import json
        return f"""// {skill.name} 适配器
// 由技能嫁接器自动生成
// 语言: {skill.language}

// 可用函数:
// {chr(10).join([f"// - {f.name}: {f.signature}" for f in analysis.functions[:10]])}

class {skill.name}Adapter {{
    constructor() {{
        this.name = "{skill.name}";
        this.version = "{skill.version}";
    }}

    listActions() {{
        return {json.dumps([f.name for f in analysis.functions[:10]])};
    }}
}}

module.exports = {skill.name}Adapter;
"""
