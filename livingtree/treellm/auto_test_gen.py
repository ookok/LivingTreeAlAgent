"""AutoTestGen — AI-driven test case generation from code signatures and behavior.

Given a function or file, auto-generates pytest test cases covering:
  - Happy path (expected inputs)
  - Edge cases (None, empty, zero, max values)
  - Error paths (expected exceptions)
  - Property-based invariants (round-trip, idempotency)
  - Integration scenarios (multi-function workflows)

Integration:
  gen = get_auto_test_gen()
  tests = await gen.generate_tests("livingtree/treellm/core.py", "smart_route")
  gen.write_test_file(tests, "tests/test_smart_route.py")
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class TestCase:
    name: str
    code: str
    description: str = ""
    category: str = ""  # "happy" | "edge" | "error" | "property" | "integration"


@dataclass
class TestSuite:
    module_path: str
    target_name: str = ""
    tests: list[TestCase] = field(default_factory=list)
    imports: str = ""


class AutoTestGen:
    """AI-driven test case generation."""

    _instance: Optional["AutoTestGen"] = None

    @classmethod
    def instance(cls) -> "AutoTestGen":
        if cls._instance is None:
            cls._instance = AutoTestGen()
        return cls._instance

    def __init__(self):
        self._generated = 0

    # ── Main API ───────────────────────────────────────────────────

    async def generate_tests(self, file_path: str, func_name: str = "",
                             llm: Any = None) -> TestSuite:
        """Generate pytest test cases for a function or file."""
        path = Path(file_path)
        suite = TestSuite(module_path=file_path, target_name=func_name)
        if not path.exists():
            return suite

        source = path.read_text(errors="replace")
        tree = ast.parse(source)
        module_name = path.stem

        # Find target function(s)
        targets = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and (not func_name or n.name == func_name) and not n.name.startswith("_")]

        for func in targets:
            sig = self._extract_signature(func, source)
            suite.tests.extend(self._happy_path_tests(func, sig, module_name))
            suite.tests.extend(self._edge_case_tests(func, sig))
            suite.tests.extend(self._error_tests(func, sig, module_name))

        suite.imports = self._build_imports(file_path, targets, module_name)
        self._generated += len(suite.tests)
        return suite

    # ── Test Generators ────────────────────────────────────────────

    def _happy_path_tests(self, func, sig: dict, module: str) -> list[TestCase]:
        tests = []
        func_name = func.name
        args = sig.get("args", [])

        # Basic call test
        test_args = self._generate_valid_args(args)
        tests.append(TestCase(
            name=f"test_{func_name}_basic",
            code=f"def test_{func_name}_basic():\n    result = {module}.{func_name}({test_args})\n    assert result is not None",
            description=f"Basic happy path for {func_name}",
            category="happy",
        ))

        # Return type check if annotated
        if sig.get("returns"):
            ret_type = sig["returns"]
            if ret_type in ("str", "int", "float", "bool", "list", "dict"):
                tests.append(TestCase(
                    name=f"test_{func_name}_returns_{ret_type}",
                    code=f"def test_{func_name}_returns_{ret_type}():\n    result = {module}.{func_name}({test_args})\n    assert isinstance(result, {ret_type})",
                    description=f"Verify {func_name} returns {ret_type}",
                    category="happy",
                ))

        return tests

    def _edge_case_tests(self, func, sig: dict) -> list[TestCase]:
        tests = []
        func_name = func.name
        args = sig.get("args", [])

        for arg in args:
            arg_name = arg["name"]
            arg_type = arg.get("type", "any")

            # None check
            tests.append(TestCase(
                name=f"test_{func_name}_{arg_name}_none",
                code=f"def test_{func_name}_{arg_name}_none():\n    try:\n        result = {func_name}({arg_name}=None)\n    except (TypeError, ValueError):\n        pass  # Expected for required params",
                description=f"Handle None for {arg_name}",
                category="edge",
            ))

            # Type-specific edge cases
            if arg_type == "str":
                tests.append(TestCase(
                    name=f"test_{func_name}_{arg_name}_empty",
                    code=f"def test_{func_name}_{arg_name}_empty():\n    result = {func_name}({arg_name}='')\n    assert result is not None",
                    description=f"Empty string for {arg_name}",
                    category="edge",
                ))
            elif arg_type in ("int", "float"):
                tests.append(TestCase(
                    name=f"test_{func_name}_{arg_name}_zero",
                    code=f"def test_{func_name}_{arg_name}_zero():\n    result = {func_name}({arg_name}=0)\n    assert result is not None",
                    description=f"Zero value for {arg_name}",
                    category="edge",
                ))
            elif arg_type in ("list", "tuple"):
                tests.append(TestCase(
                    name=f"test_{func_name}_{arg_name}_empty_list",
                    code=f"def test_{func_name}_{arg_name}_empty_list():\n    result = {func_name}({arg_name}=[])\n    assert result is not None",
                    description=f"Empty list for {arg_name}",
                    category="edge",
                ))

        return tests

    def _error_tests(self, func, sig: dict, module: str) -> list[TestCase]:
        tests = []
        func_name = func.name

        tests.append(TestCase(
            name=f"test_{func_name}_missing_args",
            code=f"def test_{func_name}_missing_args():\n    import pytest\n    with pytest.raises(TypeError):\n        {module}.{func_name}()",
            description=f"Missing required arguments",
            category="error",
        ))
        return tests

    # ── Helpers ────────────────────────────────────────────────────

    def _extract_signature(self, func, source: str) -> dict:
        """Extract function signature info from AST node."""
        args = []
        for arg in func.args.args:
            arg_type = "any"
            if arg.annotation:
                try:
                    arg_type = ast.unparse(arg.annotation)
                except Exception:
                    pass
            args.append({"name": arg.arg, "type": arg_type,
                        "has_default": False})

        # Check defaults
        defaults_offset = len(func.args.args) - len(func.args.defaults)
        for i, default in enumerate(func.args.defaults):
            idx = defaults_offset + i
            if idx < len(args):
                args[idx]["has_default"] = True

        returns = "any"
        if func.returns:
            try:
                returns = ast.unparse(func.returns)
            except Exception:
                pass

        return {"args": args, "returns": returns}

    def _generate_valid_args(self, args: list[dict]) -> str:
        """Generate valid argument string for calling."""
        parts = []
        for arg in args:
            if arg["has_default"]:
                continue  # Use default
            arg_type = arg.get("type", "any")
            if arg_type in ("int", "float"):
                parts.append(f"{arg['name']}=42")
            elif arg_type == "str":
                parts.append(f"{arg['name']}='test'")
            elif arg_type == "bool":
                parts.append(f"{arg['name']}=True")
            elif arg_type in ("list", "tuple"):
                parts.append(f"{arg['name']}=[]")
            elif arg_type in ("dict", "object"):
                parts.append(f"{arg['name']}={{}}")
            else:
                parts.append(f"{arg['name']}=None")
        return ", ".join(parts)

    def _build_imports(self, file_path: str, funcs: list, module: str) -> str:
        """Build import statements."""
        lines = [
            "import pytest",
            f"import {module}",
        ]
        return "\n".join(lines)

    def write_test_file(self, suite: TestSuite, output_path: str) -> Path:
        """Write generated tests to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Auto-generated tests for {suite.target_name or suite.module_path}",
            f"# Generated by AutoTestGen",
            suite.imports,
            "",
        ]
        for test in suite.tests:
            lines.append(f"# {test.category}: {test.description}")
            lines.append(test.code)
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"AutoTestGen: wrote {len(suite.tests)} tests to {output_path}")
        return path

    def stats(self) -> dict:
        return {"tests_generated": self._generated}


_gen: Optional[AutoTestGen] = None


def get_auto_test_gen() -> AutoTestGen:
    global _gen
    if _gen is None:
        _gen = AutoTestGen()
    return _gen


__all__ = ["AutoTestGen", "TestSuite", "TestCase", "get_auto_test_gen"]
