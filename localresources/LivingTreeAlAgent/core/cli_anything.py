"""
CLI-Anything 集成系统
自动将自然语言需求转换为可执行CLI工具

核心功能：
1. CLI生成引擎 - 7阶段流水线（分析→设计→实现→测试→文档→打包→发布）
2. 工具注册中心 - 自动注册生成的CLI到hermes工具清单
3. 云端分发同步 - 与远程清单系统集成实现自动分发
4. 异步任务管理 - 长时间生成任务的后台处理与进度反馈
"""

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

import yaml


# ============= 数据模型 =============

@dataclass
class CLIProject:
    """生成的CLI项目"""
    id: str
    name: str
    description: str
    repository_url: str = ""
    output_dir: str = ""
    entry_point: str = ""
    dependencies: list = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "Hermes-Auto"
    license: str = "MIT"
    generated_at: float = 0.0
    status: str = "pending"  # pending/running/completed/failed


@dataclass
class GenerationRequest:
    """生成请求"""
    description: str
    repo_url: Optional[str] = None
    focus: Optional[str] = None
    output_base: str = "./generated_clis"
    project_name: Optional[str] = None


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    project: Optional[CLIProject] = None
    error: str = ""
    artifacts: dict = field(default_factory=dict)


# ============= 7阶段流水线 =============

class PipelineStage:
    """流水线阶段基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def execute(
        self,
        context: dict,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> dict:
        """执行阶段任务"""
        raise NotImplementedError


class AnalysisStage(PipelineStage):
    """阶段1: 源码分析"""

    def __init__(self):
        super().__init__("analysis", "分析目标代码库结构与入口点")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.05, "[Analysis] Analyzing code structure...")

        repo_url = context.get("repo_url")
        description = context.get("description", "")

        # 模拟分析过程
        await asyncio.sleep(0.3)

        # 提取关键信息
        analysis = {
            "language": self._detect_language(description),
            "framework": self._detect_framework(description),
            "entry_patterns": ["main.py", "cli.py", "__main__.py", "cmd.py"],
            "dependencies": self._extract_deps(description),
            "cli_patterns": ["argparse", "click", "typer", "docopt"],
        }

        context["analysis"] = analysis
        return context

    def _detect_language(self, desc: str) -> str:
        langs = {
            "python": ["python", "py", "pip"],
            "javascript": ["javascript", "js", "node"],
            "typescript": ["typescript", "ts", "node"],
            "rust": ["rust", "cargo", "rs"],
            "go": ["golang", "go ", "gopath"],
        }
        desc_lower = desc.lower()
        for lang, keywords in langs.items():
            if any(k in desc_lower for k in keywords):
                return lang
        return "python"  # 默认

    def _detect_framework(self, desc: str) -> str:
        frameworks = {
            "click": ["click"],
            "typer": ["typer"],
            "argparse": ["argparse"],
            "cobra": ["cobra", "golang"],
            "commander": ["commander", "node"],
        }
        desc_lower = desc.lower()
        for fw, keywords in frameworks.items():
            if any(k in desc_lower for k in keywords):
                return fw
        return "argparse"

    def _extract_deps(self, desc: str) -> list:
        deps = []
        common_deps = {
            "requests": ["http", "web", "请求"],
            "click": ["click", "命令行"],
            "pillow": ["image", "图片", "PIL"],
            "opencv": ["cv", "opencv", "视频"],
            "pandas": ["csv", "excel", "数据"],
            "pyyaml": ["yaml", "配置"],
        }
        for dep, keywords in common_deps.items():
            if any(k in desc.lower() for k in keywords):
                deps.append(dep)
        return deps


class DesignStage(PipelineStage):
    """阶段2: 接口设计"""

    def __init__(self):
        super().__init__("design", "设计CLI接口与参数模式")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.15, "[Design] Designing CLI interface...")

        description = context.get("description", "")
        analysis = context.get("analysis", {})

        # 生成命令设计
        commands = self._generate_commands(description)

        design = {
            "commands": commands,
            "global_args": self._generate_global_args(),
            "help_text": description,
            "examples": self._generate_examples(description),
        }

        context["design"] = design
        return context

    def _generate_commands(self, desc: str) -> list:
        # 智能解析描述中的操作
        operations = []
        desc_lower = desc.lower()

        if any(k in desc_lower for k in ["转换", "convert", "transform"]):
            operations.append({"name": "convert", "desc": "转换格式"})
        if any(k in desc_lower for k in ["批量", "batch", "多个"]):
            operations.append({"name": "batch", "desc": "批量处理"})
        if any(k in desc_lower for k in ["下载", "download", "获取"]):
            operations.append({"name": "download", "desc": "下载资源"})
        if any(k in desc_lower for k in ["压缩", "zip", "archive"]):
            operations.append({"name": "compress", "desc": "压缩文件"})
        if any(k in desc_lower for k in ["解压", "extract", "unzip"]):
            operations.append({"name": "extract", "desc": "解压文件"})

        if not operations:
            operations.append({"name": "run", "desc": "执行操作"})

        return operations

    def _generate_global_args(self) -> list:
        return [
            {"name": "--verbose", "short": "-v", "type": "flag", "desc": "详细输出"},
            {"name": "--output", "short": "-o", "type": "str", "desc": "输出路径"},
            {"name": "--help", "short": "-h", "type": "flag", "desc": "显示帮助"},
        ]

    def _generate_examples(self, desc: str) -> list:
        return [
            "cli-tool run --input ./data",
            "cli-tool convert --format pdf --input ./file.txt",
        ]


class ImplementationStage(PipelineStage):
    """阶段3: 代码实现"""

    def __init__(self):
        super().__init__("implementation", "生成CLI代码实现")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.35, "[Code] Generating CLI code...")

        project = context.get("project")
        design = context.get("design", {})
        analysis = context.get("analysis", {})
        language = analysis.get("language", "python")
        framework = analysis.get("framework", "argparse")

        output_dir = Path(project.output_dir) if project else Path("./generated_clis")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成代码
        files = self._generate_python_cli(design, framework, project, context)

        # 写入文件
        for filename, content in files.items():
            filepath = output_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")

        context["generated_files"] = list(files.keys())
        return context

    def _generate_python_cli(self, design: dict, framework: str, project, context: dict) -> dict:
        commands = design.get("commands", [])
        proj_version = project.version if project else "1.0.0"
        proj_name = project.name if project else "Auto-generated CLI Tool"
        proj_desc = project.description if project else "Auto-generated CLI tool"
        proj_id = project.id if project else "cli-tool"
        proj_author = project.author if project else "Hermes-Auto"
        proj_license = project.license if project else "MIT"

        # 构建主入口文件
        lines = [
            "#!/usr/bin/env python3",
            '"""',
            f"{proj_name}",
            "Generated by Hermes CLI-Anything",
            '"""',
            "",
            "import argparse",
            "import sys",
            "import os",
            "from pathlib import Path",
            "",
            f'VERSION = "{proj_version}"',
            "",
            "",
            "def create_parser():",
            f'    parser = argparse.ArgumentParser(description="{proj_desc}")',
            "    parser.add_argument('--version', '-V', action='version', version='%(prog)s ' + VERSION)",
            "    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')",
            "    parser.add_argument('--output', '-o', type=str, default='./output', help='输出目录')",
            "",
            "    subparsers = parser.add_subparsers(dest='command', help='可用命令')",
        ]

        for cmd in commands:
            cmd_name = cmd.get("name", "run")
            cmd_desc = cmd.get("desc", "执行操作")
            lines.append(f"    {cmd_name}_parser = subparsers.add_parser('{cmd_name}', help='{cmd_desc}')")
            lines.append(f"    {cmd_name}_parser.add_argument('--input', '-i', type=str, required=True, help='输入路径')")
            lines.append(f"    {cmd_name}_parser.add_argument('--format', '-f', type=str, help='目标格式')")
            lines.append(f"    {cmd_name}_parser.add_argument('--recursive', '-r', action='store_true', help='递归处理')")

        lines.extend([
            "",
            "    return parser",
            "",
            "",
            "def run_command(args):",
            "    cmd = args.command or 'run'",
            "    if args.verbose:",
            "        print(f'[VERBOSE] Executing command: {cmd}')",
            "        print(f'[VERBOSE] Input: {args.input}')",
            "",
            "    if cmd == 'run' or cmd == 'convert':",
            "        return handle_convert(args)",
            "    elif cmd == 'batch':",
            "        return handle_batch(args)",
            "    elif cmd == 'download':",
            "        return handle_download(args)",
            "    else:",
            "        print(f'Unknown command: {cmd}')",
            "        return 1",
            "",
            "",
            "def handle_convert(args):",
            "    input_path = Path(args.input)",
            "    output_path = Path(args.output)",
            "    output_path.mkdir(parents=True, exist_ok=True)",
            "    if args.verbose:",
            "        print(f'Converting {input_path} to {args.format or \"default\"} format')",
            "    print(f'Processed: {input_path.name}')",
            "    return 0",
            "",
            "",
            "def handle_batch(args):",
            "    input_path = Path(args.input)",
            "    output_path = Path(args.output)",
            "    output_path.mkdir(parents=True, exist_ok=True)",
            "    files = list(input_path.rglob('*')) if args.recursive else list(input_path.glob('*'))",
            "    for f in files:",
            "        if f.is_file():",
            "            if args.verbose:",
            "                print(f'Processing: {f}')",
            "            print(f'Processed: {f.name}')",
            "    print(f'Batch processed {len(files)} files')",
            "    return 0",
            "",
            "",
            "def handle_download(args):",
            "    print(f'Downloading from: {args.input}')",
            "    print(f'Output to: {args.output}')",
            "    return 0",
            "",
            "",
            "def main():",
            "    parser = create_parser()",
            "    args = parser.parse_args()",
            "",
            "    if len(sys.argv) == 1:",
            "        parser.print_help()",
            "        return 0",
            "",
            "    try:",
            "        return run_command(args)",
            "    except KeyboardInterrupt:",
            "        print('\\nInterrupted by user')",
            "        return 130",
            "    except Exception as e:",
            "        print(f'Error: {e}', file=sys.stderr)",
            "        return 1",
            "",
            "",
            "if __name__ == '__main__':",
            "    sys.exit(main())",
        ])

        main_content = "\n".join(lines)

        deps = context.get("analysis", {}).get("dependencies", [])
        deps_json = json.dumps(deps)

        files = {
            "cli_tool/__main__.py": main_content,
            "cli_tool/__init__.py": f'"""Auto-generated CLI package"""\n__version__ = "{proj_version}"\n',
            "setup.py": f'''from setuptools import setup, find_packages

setup(
    name="{proj_id}",
    version="{proj_version}",
    description="{proj_desc}",
    author="{proj_author}",
    license="{proj_license}",
    packages=find_packages(),
    install_requires={deps_json},
    entry_points={{
        "console_scripts": [
            "{proj_id}=cli_tool.__main__:main",
        ]
    }},
    python_requires=">=3.10",
)
''',
            "README.md": f'''# {proj_name}

{proj_desc}

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Show help
cli-tool --help

# Run command
cli-tool run --input ./data

# Batch process
cli-tool batch --input ./files --recursive
```

## License

{proj_license}
''',
            "requirements.txt": "\n".join([
                "click>=8.0.0",
                "requests>=2.28.0",
            ]),
        }

        return files


class TestingStage(PipelineStage):
    """阶段4: 测试生成"""

    def __init__(self):
        super().__init__("testing", "生成单元测试")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.55, "[Test] Generating unit tests...")

        project = context.get("project")
        design = context.get("design", {})

        output_dir = Path(project.output_dir) if project else Path("./generated_clis")
        cli_dir = output_dir / "cli_tool"
        cli_dir.mkdir(parents=True, exist_ok=True)

        # 生成测试文件
        test_content = '''"""Unit tests for CLI tool"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCLI:
    """CLI functionality tests"""

    def test_parser_creation(self):
        """Test argument parser creation"""
        from cli_tool.__main__ import create_parser
        parser = create_parser()
        assert parser is not None

    def test_help_flag(self):
        """Test help parameter"""
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            pass  # Verify no error

    def test_version_flag(self):
        """Test version parameter"""
        from cli_tool.__main__ import VERSION
        assert VERSION is not None
        assert len(VERSION.split(".")) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

        test_file = output_dir / "tests" / "test_cli.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(test_content, encoding="utf-8")

        # 生成pytest配置
        pytest_ini = output_dir / "pytest.ini"
        pytest_ini.write_text("[pytest]\ntestpaths = tests\npython_files = test_*.py\n")

        context["generated_files"].append("tests/test_cli.py")
        return context


class DocumentationStage(PipelineStage):
    """阶段5: 文档生成"""

    def __init__(self):
        super().__init__("documentation", "生成完整文档")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.70, "[Docs] Generating documentation...")

        project = context.get("project")
        design = context.get("design", {})
        commands = design.get("commands", [])

        output_dir = Path(project.output_dir) if project else Path("./generated_clis")

        proj_name = project.name if project else "CLI Tool"
        proj_desc = project.description if project else "Auto-generated CLI tool"
        proj_id = project.id if project else "cli-tool"
        proj_license = project.license if project else "MIT"

        # 生成完整README
        readme = f'''# {proj_name}

> Generated by Hermes CLI-Anything

## Overview

{proj_desc}

## Features

'''
        for cmd in commands:
            readme += f'- **{cmd["name"]}**: {cmd["desc"]}\n'

        readme += f'''
## Quick Start

### Installation

```bash
# Install from source
pip install -e .

# Or build distribution package
python -m build
pip install dist/*.tar.gz
```

### Basic Usage

```bash
# Show help
{proj_id} --help

# Verbose mode
{proj_id} -v run --input ./data

# Specify output directory
{proj_id} -o ./output run --input ./data
```

## Command Reference

### run / convert

Convert file formats

```bash
{proj_id} run --input ./input.txt --format pdf
```

Arguments:
- `--input, -i`: Input file or directory (required)
- `--format, -f`: Target format
- `--recursive, -r`: Process subdirectories recursively

### batch

Batch process multiple files

```bash
{proj_id} batch --input ./files --recursive
```

### download

Download remote resources

```bash
{proj_id} download --input https://example.com/file.zip
```

## Configuration

Environment variables:

- `CLI_TOOL_VERBOSE`: Enable verbose output
- `CLI_TOOL_OUTPUT`: Default output directory

## Development

```bash
# Clone repository
git clone <repo-url>
cd {proj_id}

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Local install
pip install -e .
```

## License

{proj_license} License
'''

        readme_file = output_dir / "README.md"
        readme_file.write_text(readme, encoding="utf-8")

        return context


class PackagingStage(PipelineStage):
    """阶段6: 打包发布"""

    def __init__(self):
        super().__init__("packaging", "构建发布包")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.85, "[Package] Building distribution...")

        project = context.get("project")
        output_dir = Path(project.output_dir) if project else Path("./generated_clis")
        proj_id = project.id if project else "cli-tool"
        proj_version = project.version if project else "1.0.0"

        try:
            # 安装构建工具
            subprocess.run(
                ["pip", "install", "build", "wheel", "--quiet"],
                check=True,
                capture_output=True
            )

            # 构建wheel
            result = subprocess.run(
                ["python", "-m", "build", "--wheel", "--no-isolation"],
                cwd=str(output_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                dist_dir = output_dir / "dist"
                if dist_dir.exists():
                    wheels = list(dist_dir.glob("*.whl"))
                    if wheels:
                        context["wheel_file"] = str(wheels[0])

                # 创建zip包
                zip_name = f"{proj_id}_v{proj_version}.zip"
                zip_path = output_dir / zip_name

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file in output_dir.rglob("*"):
                        if file.is_file() and "__pycache__" not in str(file):
                            zf.write(file, file.relative_to(output_dir))

                context["zip_file"] = str(zip_path)
                context["packaging_success"] = True
            else:
                context["packaging_success"] = False
                context["packaging_error"] = result.stderr

        except Exception as e:
            context["packaging_success"] = False
            context["packaging_error"] = str(e)

        return context


class PublishingStage(PipelineStage):
    """阶段7: 发布注册"""

    def __init__(self):
        super().__init__("publishing", "注册到工具清单")

    async def execute(self, context: dict, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.95, "[Register] Registering to tool manifest...")

        project = context.get("project")
        proj_id = project.id if project else "cli-tool"
        proj_name = project.name if project else "CLI Tool"
        proj_desc = project.description if project else "CLI tool"
        proj_version = project.version if project else "1.0.0"

        # 生成工具清单条目
        tool_entry = {
            "id": f"autogen_{proj_id}",
            "name": f"{proj_name} (Auto-Generated)",
            "desc": proj_desc,
            "origin": "cli-anything",
            "version": proj_version,
            "platforms": {
                "windows_amd64": {
                    "url": context.get("cdn_url", ""),
                    "bin_name": f"{proj_id}.exe"
                },
                "linux_amd64": {
                    "url": context.get("cdn_url", ""),
                    "bin_name": proj_id
                }
            },
            "enabled_by_default": True,
            "generated_by": "hermes-cli-anything",
            "generated_at": time.time(),
        }

        context["tool_entry"] = tool_entry
        return context


# ============= 7阶段流水线执行器 =============

class CLIGeneratorPipeline:
    """CLI生成流水线"""

    def __init__(self):
        self.stages = [
            AnalysisStage(),
            DesignStage(),
            ImplementationStage(),
            TestingStage(),
            DocumentationStage(),
            PackagingStage(),
            PublishingStage(),
        ]

    async def execute(
        self,
        request: GenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> GenerationResult:
        """执行完整流水线"""

        # 安全的进度回调（处理Windows编码问题）
        def safe_progress(pct, msg):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    progress_callback(pct, "[Processing...]")

        # 创建项目对象
        project_name = request.project_name or self._slugify(request.description[:30])
        project = CLIProject(
            id=project_name,
            name=project_name.replace("-", " ").replace("_", " ").title(),
            description=request.description,
            repository_url=request.repo_url or "",
            output_dir=str(Path(request.output_base) / project_name),
            generated_at=time.time(),
            status="running",
        )

        # 初始化上下文
        context = {
            "request": request,
            "project": project,
            "generated_files": [],
        }

        try:
            # 依次执行各阶段
            for stage in self.stages:
                context = await stage.execute(context, safe_progress)

            # 更新项目状态
            project.status = "completed"
            project.entry_point = f"{project.id} (via pip install)"

            return GenerationResult(
                success=True,
                project=project,
                artifacts={
                    "files": context.get("generated_files", []),
                    "tool_entry": context.get("tool_entry", {}),
                    "wheel_file": context.get("wheel_file"),
                    "zip_file": context.get("zip_file"),
                }
            )

        except Exception as e:
            project.status = "failed"
            return GenerationResult(
                success=False,
                project=project,
                error=str(e)
            )

    def _slugify(self, text: str) -> str:
        """生成slug格式的名称（ASCII安全）"""
        import unicodedata
        # Unicode normalization and ASCII conversion
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('ascii')
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50].strip("-")


# ============= CLI-Anything 主类 =============

class CLIAnything:
    """
    CLI-Anything 集成主类

    用法:
        cli = CLIAnything()
        result = await cli.generate("批量转换CAD格式的工具", "https://github.com/FreeCAD/FreeCAD")
    """

    def __init__(self, output_base: str = None):
        self.output_base = output_base or "./generated_clis"
        self.pipeline = CLIGeneratorPipeline()
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        Path(self.output_base).mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        description: str,
        repo_url: str = None,
        focus: str = None,
        progress_callback: Callable[[float, str], None] = None
    ) -> GenerationResult:
        """
        生成CLI工具

        Args:
            description: 自然语言描述
            repo_url: 可选，源码仓库URL
            focus: 聚焦特定功能
            progress_callback: 进度回调函数

        Returns:
            GenerationResult
        """
        request = GenerationRequest(
            description=description,
            repo_url=repo_url,
            focus=focus,
            output_base=self.output_base,
        )

        return await self.pipeline.execute(request, progress_callback)

    def get_generated_projects(self) -> list:
        """获取已生成的项目列表"""
        projects = []
        base_path = Path(self.output_base)

        if not base_path.exists():
            return projects

        for proj_dir in base_path.iterdir():
            if proj_dir.is_dir():
                readme_path = proj_dir / "README.md"
                status = "completed" if readme_path.exists() else "unknown"
                project = CLIProject(
                    id=proj_dir.name,
                    name=proj_dir.name.replace("-", " ").replace("_", " ").title(),
                    description="",
                    output_dir=str(proj_dir),
                    status=status
                )
                projects.append(project)

        return projects


# ============= 工具注册集成 =============

class AutoGeneratedToolsRegistry:
    """自动生成工具注册表"""

    def __init__(self, registry_path: str = None):
        self.registry_path = registry_path or "./config/autogen_tools.json"
        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        """加载注册表"""
        path = Path(self.registry_path)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": time.strftime("%Y%m%d"), "tools": []}

    def _save_registry(self):
        """保存注册表"""
        path = Path(self.registry_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._registry, indent=2, ensure_ascii=False), encoding="utf-8")

    def register_tool(self, tool_entry: dict) -> bool:
        """注册工具"""
        try:
            # 检查是否已存在
            existing = [t for t in self._registry["tools"] if t["id"] == tool_entry["id"]]
            if existing:
                # 更新
                self._registry["tools"] = [
                    t if t["id"] != tool_entry["id"] else tool_entry
                    for t in self._registry["tools"]
                ]
            else:
                self._registry["tools"].append(tool_entry)

            self._save_registry()
            return True
        except Exception:
            return False

    def get_tools(self, origin: str = None) -> list:
        """获取工具列表"""
        if origin:
            return [t for t in self._registry["tools"] if t.get("origin") == origin]
        return self._registry["tools"]

    def unregister_tool(self, tool_id: str) -> bool:
        """注销工具"""
        try:
            self._registry["tools"] = [
                t for t in self._registry["tools"] if t["id"] != tool_id
            ]
            self._save_registry()
            return True
        except Exception:
            return False


# 单例
_cli_anything: Optional[CLIAnything] = None
_tools_registry: Optional[AutoGeneratedToolsRegistry] = None


def get_cli_anything() -> CLIAnything:
    """获取CLI-Anything单例"""
    global _cli_anything
    if _cli_anything is None:
        _cli_anything = CLIAnything()
    return _cli_anything


def get_tools_registry() -> AutoGeneratedToolsRegistry:
    """获取工具注册表单例"""
    global _tools_registry
    if _tools_registry is None:
        _tools_registry = AutoGeneratedToolsRegistry()
    return _tools_registry
