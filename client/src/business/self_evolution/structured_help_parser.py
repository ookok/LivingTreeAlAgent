"""
StructuredHelpParser - 结构化帮助文档解析器

功能：
1. 解析 argparse/optparse 格式的 --help 输出
2. 解析 Rust clap 格式的帮助
3. 解析 npm/Yarn/Go 等自由格式帮助
4. 提取子命令、参数、类型、默认值、必需标记
5. 生成 JSON Schema 格式的参数定义
6. 对 Python 包：通过 help() / __doc__ / dir() 自动学习 API

输出格式：
```json
{
    "name": "tool_name",
    "description": "...",
    "subcommands": {"run": {"description": "...", "params": [...]}},
    "parameters": [
        {"name": "--input", "type": "string", "required": true, "description": "..."},
        {"name": "--verbose", "type": "boolean", "default": false, "description": "..."}
    ],
    "examples": ["..."],
    "json_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```
"""

import os
import re
import asyncio
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


@dataclass
class ParsedParameter:
    """解析出的参数"""
    name: str                    # 参数名（如 --input, -i）
    short_name: Optional[str] = None   # 短名（如 -i）
    param_type: str = "string"   # 类型：string, integer, number, boolean, array, object
    required: bool = False
    default: Any = None
    description: str = ""
    choices: Optional[List[str]] = None
    nargs: Optional[str] = None  # ?, *, +, N


@dataclass
class ParsedSubcommand:
    """解析出的子命令"""
    name: str
    description: str = ""
    parameters: List[ParsedParameter] = field(default_factory=list)


@dataclass
class ParsedHelp:
    """解析结果"""
    name: str = ""
    description: str = ""
    usage: str = ""
    parameters: List[ParsedParameter] = field(default_factory=list)
    subcommands: Dict[str, ParsedSubcommand] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    raw_help: str = ""
    format: str = "unknown"  # argparse, clap, npm, freeform, python
    json_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "usage": self.usage,
            "parameters": [
                {
                    "name": p.name,
                    "short_name": p.short_name,
                    "type": p.param_type,
                    "required": p.required,
                    "default": p.default,
                    "description": p.description,
                    "choices": p.choices,
                }
                for p in self.parameters
            ],
            "subcommands": {
                k: {
                    "name": v.name,
                    "description": v.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.param_type,
                            "required": p.required,
                            "description": p.description,
                        }
                        for p in v.parameters
                    ]
                }
                for k, v in self.subcommands.items()
            },
            "examples": self.examples,
            "format": self.format,
            "json_schema": self.json_schema,
        }


class StructuredHelpParser:
    """
    结构化帮助文档解析器

    支持的格式：
    - argparse: Python argparse 标准输出
    - optparse: Python optparse 格式
    - clap: Rust clap 框架格式
    - npm: npm/Yarn 帮助格式
    - freeform: 自由格式（通用正则提取）
    - python: Python 包（help() / __doc__ / dir()）

    用法：
        parser = StructuredHelpParser()
        result = parser.parse_help_text(help_text, tool_name)
        print(result.json_schema)
    """

    # 类型推断正则
    TYPE_PATTERNS = {
        "integer": re.compile(r"\b(int(eger)?|INT)\b"),
        "number": re.compile(r"\b(float|double|num|NUM|decimal|DECIMAL)\b"),
        "boolean": re.compile(r"\b(bool(ean)?|flag|FLAG|switch)\b"),
        "array": re.compile(r"\b(list|array|ARRAY|List|Array|\[.*\])\b"),
        "object": re.compile(r"\b(dict|object|json|JSON|map|MAP)\b"),
    }

    # argparse 格式检测
    ARGPARSE_PATTERNS = {
        "optional": re.compile(
            r"^\s{0,4}(-{1,2}[\w\-]+(?:\s*,\s*-[\w\-]+)?"
            r"(?:\s+([\w\[\]<>\.]+))?"
            r"(?:\s*=\s*(.+?))?\s*$",
            re.MULTILINE
        ),
        "positional": re.compile(
            r"^\s{0,4}([\w]+)"
            r"(?:\s+([\w\[\]<>\.]+))?"
            r"\s*$",
            re.MULTILINE
        ),
        "subcommand_section": re.compile(
            r"^([\w\-]+)\s{2,}(.+)$",
            re.MULTILINE
        ),
        "description_block": re.compile(
            r"^(?:description|描述|说明)[:\s]*\n?(.+?)(?:\n\n|\n[A-Z\-])",
            re.DOTALL | re.IGNORECASE
        ),
    }

    # clap 格式检测
    CLAP_PATTERN = re.compile(r"USAGE:|FLAGS:|OPTIONS:|ARGS:|SUBCOMMANDS:")

    # 子命令分割
    SUBCOMMAND_SECTION = re.compile(
        r"^(?:commands|子命令|subcommands)[:\s]*\n([\s\S]+?)(?:\n\n[A-Z]|\Z)",
        re.IGNORECASE
    )

    def parse_help_text(
        self,
        help_text: str,
        tool_name: str = "",
    ) -> ParsedHelp:
        """
        解析帮助文档（自动检测格式）

        Args:
            help_text: 原始帮助文本
            tool_name: 工具名

        Returns:
            ParsedHelp 解析结果
        """
        if not help_text:
            return ParsedHelp(name=tool_name)

        result = ParsedHelp(name=tool_name, raw_help=help_text)

        # 检测格式
        result.format = self._detect_format(help_text)

        # 按格式解析
        if result.format == "argparse":
            self._parse_argparse(help_text, result)
        elif result.format == "clap":
            self._parse_clap(help_text, result)
        elif result.format == "npm":
            self._parse_npm(help_text, result)
        else:
            self._parse_freeform(help_text, result)

        # 生成 JSON Schema
        result.json_schema = self._generate_json_schema(result)

        return result

    def _detect_format(self, text: str) -> str:
        """检测帮助文档格式"""
        # argparse: 通常是 -h/--help 后接描述
        if re.search(r"^\s{2,}(-{1,2}[\w\-]+.*?(?:\n\s{2,}(-{1,2}[\w\-]+|[\w]+))*", text, re.MULTILINE):
            if not self.CLAP_PATTERN.search(text):
                return "argparse"

        # clap: USAGE:, FLAGS:, OPTIONS: 等大写标题
        if self.CLAP_PATTERN.search(text):
            return "clap"

        # npm: 通常包含 npm 命令关键词
        if re.search(r"npm|yarn|pnpm|npx", text, re.IGNORECASE):
            return "npm"

        return "freeform"

    def _parse_argparse(self, text: str, result: ParsedHelp):
        """解析 argparse 格式"""
        # 提取描述（第一个非空段落）
        desc_match = self.ARGPARSE_PATTERNS["description_block"].search(text)
        if desc_match:
            result.description = desc_match.group(1).strip()[:500]

        # 提取 usage
        usage_match = re.search(r"^usage:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if usage_match:
            result.usage = usage_match.group(1).strip()

        # 提取参数（逐行解析）
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # 匹配 -x, --xxx [TYPE]  Description
            param_match = re.match(
                r"^\s{0,4}((-[\w])\s*,\s*)?(-{2}[\w][\w\-]*)"
                r"(?:\s+([\w\[\]<>\.]+(?:\.\.\.)?))?"
                r"(?:\s*,?\s*(.+))?$",
                line
            )

            if param_match:
                short_name = param_match.group(2)  # -x
                long_name = param_match.group(3)    # --xxx
                type_hint = param_match.group(4)    # FILE, INT, etc.
                description = (param_match.group(5) or "").strip()

                # 多行描述
                while i + 1 < len(lines) and lines[i + 1].startswith(" " * 10) and lines[i + 1].strip():
                    i += 1
                    description += " " + lines[i].strip()

                param = ParsedParameter(
                    name=long_name or short_name,
                    short_name=short_name if long_name else None,
                    param_type=self._infer_type(type_hint or "", description),
                    description=description[:200],
                )

                # 检测 [required] 标记
                if re.search(r"\[required\]|必需|必填", description, re.IGNORECASE):
                    param.required = True

                # 检测默认值
                default_match = re.search(r"(?:default|默认)[:=]\s*(\S+)", description, re.IGNORECASE)
                if default_match:
                    param.default = self._parse_value(default_match.group(1), param.param_type)

                # 检测选项列表
                choices_match = re.search(r"\{([^}]+)\}", description)
                if choices_match:
                    param.choices = [c.strip() for c in choices_match.group(1).split(",")]

                # 检测 nargs
                nargs_match = re.search(r"\.\.\.(?!\s)", type_hint or "")
                if nargs_match:
                    param.nargs = "+"

                result.parameters.append(param)
            i += 1

        # 提取子命令
        subcommand_match = self.SUBCOMMAND_SECTION.search(text)
        if subcommand_match:
            for line in subcommand_match.group(1).strip().split("\n"):
                parts = re.match(r"^\s{0,4}([\w][\w\-]*)\s{2,}(.+)$", line)
                if parts:
                    result.subcommands[parts.group(1)] = ParsedSubcommand(
                        name=parts.group(1),
                        description=parts.group(2).strip(),
                    )

        # 提取示例
        examples_section = re.search(
            r"(?:examples?|示例|用法)[:\s]*\n([\s\S]+?)(?:\n\n[A-Z\-]|\Z)",
            text, re.IGNORECASE
        )
        if examples_section:
            result.examples = [
                line.strip()
                for line in examples_section.group(1).strip().split("\n")
                if line.strip() and not line.strip().startswith("#")
            ][:5]

    def _parse_clap(self, text: str, result: ParsedHelp):
        """解析 Rust clap 格式"""
        # 提取 USAGE
        usage_match = re.search(r"USAGE:\s*(.+?)(?:\n\n|\n[A-Z])", text)
        if usage_match:
            result.usage = usage_match.group(1).strip()

        # 提取 FLAGS（布尔参数）
        flags_section = re.search(r"FLAGS:\s*\n([\s\S]+?)(?:\n\n[A-Z]|\Z)", text)
        if flags_section:
            for line in flags_section.group(1).split("\n"):
                param = self._parse_clap_line(line, is_flag=True)
                if param:
                    result.parameters.append(param)

        # 提取 OPTIONS（有值参数）
        options_section = re.search(r"OPTIONS:\s*\n([\s\S]+?)(?:\n\n[A-Z]|\Z)", text)
        if options_section:
            for line in options_section.group(1).split("\n"):
                param = self._parse_clap_line(line, is_flag=False)
                if param:
                    result.parameters.append(param)

        # 提取 ARGS（位置参数）
        args_section = re.search(r"ARGS:\s*\n([\s\S]+?)(?:\n\n[A-Z]|\Z)", text)
        if args_section:
            for line in args_section.group(1).split("\n"):
                param = self._parse_clap_line(line, is_flag=False, is_arg=True)
                if param:
                    result.parameters.append(param)

        # 提取 SUBCOMMANDS
        subs_section = re.search(r"SUBCOMMANDS:\s*\n([\s\S]+?)(?:\n\n[A-Z]|\Z)", text)
        if subs_section:
            for line in subs_section.group(1).split("\n"):
                parts = re.match(r"\s{0,4}([\w][\w\-]*)\s{2,}(.+)$", line)
                if parts:
                    result.subcommands[parts.group(1)] = ParsedSubcommand(
                        name=parts.group(1),
                        description=parts.group(2).strip(),
                    )

    def _parse_clap_line(
        self, line: str, is_flag: bool = False, is_arg: bool = False
    ) -> Optional[ParsedParameter]:
        """解析 clap 单行"""
        if is_flag:
            match = re.match(
                r"\s{0,4}(-[\w])\s*,\s*(-{2}[\w][\w\-]*)\s+(.+)",
                line
            )
            if match:
                desc = match.group(3).strip()
                return ParsedParameter(
                    name=match.group(2),
                    short_name=match.group(1),
                    param_type="boolean",
                    description=desc[:200],
                )
        elif is_arg:
            match = re.match(r"\s{0,4}<([\w]+)>\s+(.+)", line)
            if match:
                desc = match.group(2).strip()
                return ParsedParameter(
                    name=match.group(1),
                    param_type=self._infer_type("", desc),
                    required=True,
                    description=desc[:200],
                )
        else:
            match = re.match(
                r"\s{0,4}(-[\w])\s*,\s*(-{2}[\w][\w\-]*)\s+<([\w]+)>\s+(.+)",
                line
            )
            if match:
                desc = match.group(4).strip()
                return ParsedParameter(
                    name=match.group(2),
                    short_name=match.group(1),
                    param_type=self._infer_type(match.group(3), desc),
                    description=desc[:200],
                )
        return None

    def _parse_npm(self, text: str, result: ParsedHelp):
        """解析 npm 格式（通用自由格式 + npm 关键词）"""
        # npm 帮助通常是自由格式
        self._parse_freeform(text, result)

    def _parse_freeform(self, text: str, result: ParsedHelp):
        """解析自由格式帮助文本"""
        # 提取描述（前几行非选项行）
        lines = text.split("\n")
        desc_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("-") or stripped.startswith("Usage"):
                break
            if stripped:
                desc_lines.append(stripped)
        if desc_lines:
            result.description = " ".join(desc_lines[:3])[:500]

        # 提取 usage
        for line in lines:
            if re.match(r"(?:usage|用法)\s*:", line, re.IGNORECASE):
                result.usage = line.split(":", 1)[1].strip()
                break

        # 通用参数提取：匹配 --xxx / -x 模式
        for line in lines:
            # 匹配 -x, --xxx  DESCRIPTION
            match = re.match(r"\s{0,4}(-[\w])\s*,\s*(-{2}[\w][\w\-]*)\s+(.+)", line)
            if match:
                desc = match.group(3).strip()
                result.parameters.append(ParsedParameter(
                    name=match.group(2),
                    short_name=match.group(1),
                    param_type=self._infer_type("", desc),
                    description=desc[:200],
                ))
                continue

            # 匹配 --xxx=VALUE  DESCRIPTION
            match = re.match(r"\s{0,4}(-{2}[\w][\w\-]+)(?:\[?=\s*(\w+))?\s+(.+)", line)
            if match:
                desc = match.group(3).strip()
                result.parameters.append(ParsedParameter(
                    name=match.group(1),
                    param_type=self._infer_type(match.group(2) or "", desc),
                    description=desc[:200],
                ))
                continue

            # 匹配 -x DESCRIPTION（短选项）
            match = re.match(r"\s{0,4}(-[\w])\s{2,}(.+)", line)
            if match and not match.group(1) in ("-h",):
                desc = match.group(2).strip()
                # 跳过看起来不是参数的行
                if desc and not desc.startswith("-"):
                    result.parameters.append(ParsedParameter(
                        name=match.group(1),
                        param_type="boolean" if "flag" in desc.lower() else self._infer_type("", desc),
                        description=desc[:200],
                    ))

        # 提取示例
        examples_section = re.search(
            r"(?:examples?|示例)[:\s]*\n([\s\S]+?)(?:\n\n|\Z)",
            text, re.IGNORECASE
        )
        if examples_section:
            result.examples = [
                line.strip()
                for line in examples_section.group(1).strip().split("\n")
                if line.strip() and not line.strip().startswith("#")
            ][:5]

    # ── 类型推断 ─────────────────────────────────────────

    def _infer_type(self, type_hint: str, description: str = "") -> str:
        """从类型提示和描述推断参数类型"""
        combined = (type_hint + " " + description).lower()

        # 先检查类型提示
        if type_hint:
            type_lower = type_hint.lower()
            if type_lower in ("int", "integer"):
                return "integer"
            if type_lower in ("float", "double", "num", "number"):
                return "number"
            if type_lower in ("bool", "boolean", "flag"):
                return "boolean"
            if type_lower in ("list", "array"):
                return "array"
            if type_lower in ("dict", "object", "json", "map"):
                return "object"
            # 文件类型 → string
            if type_lower in ("file", "path", "dir", "directory"):
                return "string"

        # 从描述推断
        for type_name, pattern in self.TYPE_PATTERNS.items():
            if pattern.search(combined):
                return type_name

        # 默认 string
        return "string"

    def _parse_value(self, value_str: str, type_hint: str) -> Any:
        """解析默认值"""
        value_str = value_str.strip().strip("'\"")
        if type_hint == "integer":
            try:
                return int(value_str)
            except ValueError:
                pass
        elif type_hint == "number":
            try:
                return float(value_str)
            except ValueError:
                pass
        elif type_hint == "boolean":
            return value_str.lower() in ("true", "1", "yes")
        return value_str

    # ── JSON Schema 生成 ─────────────────────────────────

    def _generate_json_schema(self, parsed: ParsedHelp) -> Dict[str, Any]:
        """从 ParsedHelp 生成 JSON Schema"""
        properties = {}
        required = []

        for param in parsed.parameters:
            prop = {"type": param.param_type, "description": param.description}

            if param.default is not None:
                prop["default"] = param.default
            if param.choices:
                prop["enum"] = param.choices
            if param.description:
                prop["description"] = param.description

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return schema

    # ── Python 包学习 ────────────────────────────────────

    async def learn_python_package(
        self,
        package_name: str,
        help_commands: Optional[List[str]] = None,
        depth: str = "full",
    ) -> Dict[str, Any]:
        """
        自动学习 Python 包的用法

        Args:
            package_name: 包名
            help_commands: 获取帮助的命令列表
            depth: quick / full / deep

        Returns:
            学习结果字典
        """
        result = {
            "name": package_name,
            "format": "python",
            "parameters": [],
            "api_methods": [],
            "description": "",
            "version": "",
            "classes": [],
            "examples": [],
            "json_schema": {},
        }

        if help_commands is None:
            help_commands = [
                f"python -c \"import {package_name}; print({package_name}.__doc__)\"",
                f"python -c \"import {package_name}; print(dir({package_name}))\"",
                f"python -c \"import {package_name}; help({package_name})\"",
            ]

        # 执行帮助命令
        raw_outputs = []
        for cmd in help_commands:
            try:
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(
                    None,
                    lambda c=cmd: subprocess.run(
                        c,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                )
                out = (output.stdout or "").strip()
                if out:
                    raw_outputs.append(out[:3000])
            except Exception:
                continue

        # 解析 __doc__
        for out in raw_outputs:
            if len(out) > 50 and not out.startswith("["):
                result["description"] = out[:1000]
                result["raw_help"] = out
                break

        # 解析 dir() → 提取 API 方法
        for out in raw_outputs:
            if out.startswith("["):
                try:
                    items = eval(out)
                    if isinstance(items, list):
                        # 过滤掉内置方法和私有方法
                        public = [
                            item for item in items
                            if not item.startswith("_")
                            and any(c.isupper() for c in item[0:1])
                        ]
                        result["api_methods"] = public[:50]

                        # 提取类（首字母大写）
                        result["classes"] = [
                            item for item in public
                            if item[0].isupper() and not item.isupper()
                        ][:20]
                except Exception:
                    pass

        # 尝试获取版本
        try:
            loop = asyncio.get_event_loop()
            ver_output = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    f"python -c \"import {package_name}; print({package_name}.__version__)\"",
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )
            if ver_output.returncode == 0:
                result["version"] = ver_output.stdout.strip()
        except Exception:
            pass

        # 生成 JSON Schema（从 API 方法推断）
        if result["api_methods"]:
            properties = {}
            for method in result["api_methods"][:20]:
                properties[method] = {
                    "type": "object",
                    "description": f"{package_name}.{method} 方法调用",
                }
            result["json_schema"] = {
                "type": "object",
                "properties": properties,
            }

        return result


# ── 便捷函数 ─────────────────────────────────────────────

def parse_help(help_text: str, tool_name: str = "") -> ParsedHelp:
    """快速解析帮助文本"""
    parser = StructuredHelpParser()
    return parser.parse_help_text(help_text, tool_name)


def help_to_json_schema(help_text: str, tool_name: str = "") -> Dict[str, Any]:
    """帮助文本转 JSON Schema"""
    result = parse_help(help_text, tool_name)
    return result.json_schema
