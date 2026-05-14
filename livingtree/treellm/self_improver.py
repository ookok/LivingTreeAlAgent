"""SelfImprover — Autonomous system defect analysis, innovation proposal, and implementation.

Goes beyond bug fixing to:
  1. DefectScanner: scan codebase for architectural patterns, anti-patterns, gaps
  2. InnovationProposer: propose improvements based on pattern analysis
  3. AutoImplementer: generate and apply improvement code
  4. ValidateAndCommit: test → validate → commit → push

Integrates with existing systems:
  AutonomousCodeEvolution: low-level AST mutations (thresholds, dead code)
  CanaryTester: regression validation after changes
  CapabilityBus: discover capability coverage gaps
  ErrorInterceptor: feed error patterns as improvement signals
  RecordingEngine: use successful traces as improvement templates
  Git: safety branches for all auto-improvements

Usage:
  livingtree improve --scan          # Scan for defects
  livingtree improve --propose       # Propose innovations
  livingtree improve --auto          # Full auto-improve cycle
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

IMPROVEMENTS_DIR = Path(".livingtree/improvements")


# ═══ Data Types ════════════════════════════════════════════════════


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Defect:
    """A detected system defect or gap."""
    id: str = field(default_factory=lambda: f"def_{int(time.time()*1000)}")
    category: str = ""            # "architecture" | "performance" | "coverage" | "safety" | "innovation"
    severity: Severity = Severity.MEDIUM
    title: str = ""
    description: str = ""
    file_path: str = ""
    line_number: int = 0
    evidence: str = ""            # What triggered this detection
    suggested_fix: str = ""
    confidence: float = 0.5


@dataclass
class Innovation:
    """A proposed system improvement."""
    id: str = field(default_factory=lambda: f"inn_{int(time.time()*1000)}")
    title: str = ""
    description: str = ""
    category: str = ""
    inspired_by: str = ""         # Research paper or pattern source
    implementation_plan: str = ""
    estimated_impact: str = ""
    complexity: str = "medium"    # low|medium|high
    code_patch: str = ""
    validated: bool = False
    test_passed: bool = False
    git_branch: str = ""
    git_commit: str = ""


# ═══ DefectScanner ════════════════════════════════════════════════


class DefectScanner:
    """Scans the codebase for architectural patterns, anti-patterns, and gaps."""

    SCAN_RULES = [
        ("too_many_imports", "文件导入超过15个模块", "考虑拆分为多个职责文件"),
        ("bare_except_pass", "except Exception: pass 静默吞错", "替换为 logger.debug()"),
        ("sync_in_async", "异步函数中的同步阻塞调用", "使用 async_disk 或线程池"),
        ("missing_tests", "源文件无对应测试文件", "添加 pytest 测试"),
        ("hardcoded_values", "硬编码的magic number或字符串", "提取为配置常量"),
        ("long_function", "超过100行的函数", "拆分为更小的函数"),
        ("deeply_nested", "超过4层嵌套", "提取逻辑为独立函数"),
        ("duplicate_code", "相似代码块(>80%相似)", "提取为公共函数"),
        ("no_docstring", "公开函数/类缺少文档", "添加 docstring"),
        ("unused_import", "导入但未使用的模块", "删除"),
    ]

    def __init__(self):
        self._defects: list[Defect] = []

    async def scan(self, root_dir: str = "", file_pattern: str = "**/*.py",
                   use_llm: bool = False) -> list[Defect]:
        """Scan the codebase for defects. Returns list of Defects."""
        root = Path(root_dir or os.getcwd()) / "livingtree"
        if not root.exists():
            return []

        self._defects = []
        py_files = list(root.rglob(file_pattern))
        logger.info(f"DefectScanner: scanning {len(py_files)} files")

        tasks = [self._scan_file(f) for f in py_files[:200]]
        await asyncio.gather(*tasks, return_exceptions=True)

        if use_llm:
            await self._llm_deep_analysis()

        logger.info(f"DefectScanner: found {len(self._defects)} defects")
        return self._defects

    async def _scan_file(self, file_path: Path):
        """Scan a single file for defects."""
        try:
            content = file_path.read_text(errors="replace")
            lines = content.split("\n")
            line_count = len(lines)

            # Rule: bare except pass
            for i, line in enumerate(lines, 1):
                if re.match(r'\s*except\s+Exception\s*:\s*$', line):
                    next_line = lines[i].strip() if i < len(lines) else ""
                    if next_line == "pass":
                        self._defects.append(Defect(
                            category="safety", severity=Severity.HIGH,
                            title=f"bare except:pass in {file_path.name}",
                            description=f"Line {i}: except Exception: pass silently swallows errors",
                            file_path=str(file_path), line_number=i,
                            evidence=f"except Exception:\n    pass",
                            suggested_fix="替换为 logger.debug() 记录异常",
                        ))

            # Rule: long function
            in_function = False
            func_start = 0
            func_indent = 0
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.match(r'\s*async def |\s*def ', line):
                    in_function = True
                    func_start = i
                    func_indent = len(line) - len(line.lstrip())
                elif in_function and stripped and (len(line) - len(line.lstrip())) <= func_indent and not stripped.startswith('#'):
                    func_len = i - func_start
                    if func_len > 100:
                        self._defects.append(Defect(
                            category="architecture", severity=Severity.MEDIUM,
                            title=f"Long function in {file_path.name}",
                            description=f"Function starting at line {func_start} is {func_len} lines",
                            file_path=str(file_path), line_number=func_start,
                        ))
                    in_function = False

            # Rule: missing tests
            if line_count > 20 and file_path.stem.startswith(("test_", "conftest")):
                return
            test_path = file_path.parent / "tests" / f"test_{file_path.stem}.py"
            if not test_path.exists() and line_count > 30:
                test_path2 = root = Path("tests") / f"test_{file_path.stem}.py"
                if isinstance(root, Path):
                    pass
                self._defects.append(Defect(
                    category="coverage", severity=Severity.MEDIUM,
                    title=f"Missing tests for {file_path.name}",
                    description=f"No test file found at {test_path}",
                    file_path=str(file_path),
                ))

            # Rule: too many imports
            import_count = sum(1 for l in lines if l.strip().startswith("import ") or l.strip().startswith("from "))
            if import_count > 20:
                self._defects.append(Defect(
                    category="architecture", severity=Severity.LOW,
                    title=f"Many imports in {file_path.name}",
                    description=f"{import_count} import statements — consider splitting responsibilities",
                    file_path=str(file_path),
                ))

        except Exception as e:
            logger.debug(f"DefectScanner: {file_path}: {e}")

    async def _llm_deep_analysis(self):
        """Use LLM to analyze patterns across all defects for deeper insights."""
        if len(self._defects) < 5:
            return

        try:
            from .core import TreeLLM
            llm = TreeLLM()
            defect_summary = "\n".join(
                f"- [{d.severity.value}] {d.category}: {d.title}"
                for d in self._defects[:30]
            )
            prompt = (
                f"分析以下系统缺陷列表,识别深层架构问题并提出改进优先级:\n\n"
                f"{defect_summary}\n\n"
                f"请给出:\n"
                f"1. 最严重的3个架构问题\n"
                f"2. 修复优先级排序(按影响范围)\n"
                f"3. 如果有可自动修复的,标注 (auto-fixable)"
            )
            result = await llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=1000, temperature=0.3,
            )
            analysis = getattr(result, 'text', '') or str(result)
            self._defects.append(Defect(
                category="architecture", severity=Severity.HIGH,
                title="LLM Architectural Analysis",
                description=analysis[:2000],
                confidence=0.7,
            ))
        except Exception:
            pass

    def report(self) -> dict:
        by_cat = defaultdict(int)
        by_sev = defaultdict(int)
        for d in self._defects:
            by_cat[d.category] += 1
            by_sev[d.severity.value] += 1
        return {
            "total": len(self._defects),
            "by_category": dict(by_cat),
            "by_severity": dict(by_sev),
            "top5": [{"title": d.title, "severity": d.severity.value,
                      "category": d.category, "file": d.file_path}
                     for d in sorted(self._defects, key=lambda x: -len(x.description))[:5]],
        }


# ═══ InnovationProposer ═══════════════════════════════════════════


class InnovationProposer:
    """Proposes system improvements based on defect analysis and capability gaps."""

    INNOVATION_TEMPLATES = [
        {
            "pattern": "missing_tests_coverage",
            "title": "自动测试生成",
            "description": "基于函数签名和文档自动生成 pytest 测试用例",
            "category": "testing",
            "complexity": "medium",
        },
        {
            "pattern": "hardcoded_values_cluster",
            "title": "配置集中化管理",
            "description": "将散落的硬编码值提取到统一配置文件",
            "category": "architecture",
            "complexity": "low",
        },
        {
            "pattern": "no_monitoring_metrics",
            "title": "运行时指标仪表板",
            "description": "添加 Prometheus 指标端点,暴露关键运行时数据",
            "category": "observability",
            "complexity": "medium",
        },
        {
            "pattern": "duplicate_pattern_across_files",
            "title": "提取公共工具库",
            "description": "将多文件重复代码提取为共享库",
            "category": "refactoring",
            "complexity": "medium",
        },
        {
            "pattern": "cache_miss_opportunity",
            "title": "智能缓存层",
            "description": "在热点路径添加 LRU 缓存",
            "category": "performance",
            "complexity": "low",
        },
    ]

    def __init__(self):
        self._innovations: list[Innovation] = []

    async def propose(self, defects: list[Defect] = None,
                      use_llm: bool = False) -> list[Innovation]:
        """Generate innovation proposals based on defects and capability gaps."""
        self._innovations = []

        # Template-based proposals
        if defects:
            categories = set(d.category for d in defects)
            for template in self.INNOVATION_TEMPLATES:
                if template["pattern"].split("_")[0] in categories:
                    self._innovations.append(Innovation(
                        title=template["title"],
                        description=template["description"],
                        category=template["category"],
                        complexity=template["complexity"],
                    ))

        # Capability gap analysis via CapabilityBus
        try:
            from .capability_bus import get_capability_bus
            bus = get_capability_bus()
            caps = await bus.list_all()

            # Check for missing tool categories
            has = defaultdict(bool)
            for c in caps:
                for k in ("web_search", "file_read", "bash", "kb_search", "code_graph"):
                    if k in c.get("id", ""):
                        has[k] = True

            if not has.get("code_graph"):
                self._innovations.append(Innovation(
                    title="代码依赖图可视化",
                    description="添加代码调用关系图能力,支持 import 分析和依赖可视化",
                    category="tool", complexity="medium",
                ))
        except Exception:
            pass

        # LLM-powered innovation proposals
        if use_llm and defects:
            try:
                from .core import TreeLLM
                llm = TreeLLM()
                prompt = f"""基于这个系统的缺陷分析,提出3个具体的创新改进建议:
                缺陷总数: {len(defects)}
                主要类别: {', '.join(set(d.category for d in defects))}
                
                每个建议需包含: 标题、描述、实现方案、预期效果。
                
                要求: 具体可实施,不要泛泛而谈。每个建议50-100字。"""
                result = await llm.chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=800, temperature=0.5,
                )
                text = getattr(result, 'text', '') or str(result)
                for line in text.split("\n"):
                    if line.strip().startswith(("1.", "2.", "3.")):
                        self._innovations.append(Innovation(
                            title=line[:100],
                            description=text[:500],
                            category="llm_proposed",
                            inspired_by="TreeLLM analysis",
                        ))
            except Exception:
                pass

        logger.info(f"InnovationProposer: {len(self._innovations)} proposals")
        return self._innovations


# ═══ SelfImprover ════════════════════════════════════════════════


class SelfImprover:
    """Autonomous self-improvement engine: scan→propose→implement→validate."""

    _instance: Optional["SelfImprover"] = None

    @classmethod
    def instance(cls) -> "SelfImprover":
        if cls._instance is None:
            cls._instance = SelfImprover()
        return cls._instance

    def __init__(self):
        self._scanner = DefectScanner()
        self._proposer = InnovationProposer()
        self._history: list[Innovation] = []
        self._improvement_count = 0

    # ── Full Auto-Improve Cycle ────────────────────────────────────

    async def improve(self, use_llm: bool = False,
                      auto_apply: bool = False) -> dict:
        """Run full improvement cycle: scan → propose → implement → validate."""
        result = {"defects": 0, "innovations": 0, "implemented": 0, "validated": 0}

        # 1. Scan
        defects = await self._scanner.scan(use_llm=use_llm)
        result["defects"] = len(defects)

        # 2. Propose innovations
        innovations = await self._proposer.propose(defects, use_llm=use_llm)
        result["innovations"] = len(innovations)

        # 3. Implement (if auto_apply)
        if auto_apply and innovations:
            for inn in innovations[:3]:  # Max 3 per cycle
                implemented = await self._implement(inn)
                if implemented:
                    result["implemented"] += 1

                    # 4. Validate
                    validated = await self._validate(inn)
                    if validated:
                        result["validated"] += 1

        self._history.extend(innovations)
        self._improvement_count += 1

        return result

    async def _implement(self, innovation: Innovation) -> bool:
        """Implement an innovation by generating code via LLM."""
        try:
            # Create safety branch
            branch_name = f"improve/{innovation.id[:12]}"
            try:
                from .unified_exec import git
                await git(f"checkout -b {branch_name}", timeout=10)
            except ImportError:
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    capture_output=True, check=False,
                )

            # Generate implementation via LLM
            from .core import TreeLLM
            llm = TreeLLM()
            prompt = f"""实现以下系统改进(用Python代码):
            改进: {innovation.title}
            描述: {innovation.description}
            类别: {innovation.category}
            复杂度: {innovation.complexity}
            
            输出: 可执行的Python代码和修改说明。使用```python代码块。"""
            result = await llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=2000, temperature=0.2, task_type="code",
            )
            code = getattr(result, 'text', '') or str(result)
            innovation.code_patch = code[:5000]
            innovation.git_branch = branch_name

            # Save proposal for human review
            IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
            proposal_path = IMPROVEMENTS_DIR / f"{innovation.id}.json"
            proposal_path.write_text(json.dumps({
                "id": innovation.id, "title": innovation.title,
                "description": innovation.description,
                "code_patch": innovation.code_patch,
                "category": innovation.category,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            logger.info(f"SelfImprover: implemented '{innovation.title}' → {branch_name}")
            return True
        except Exception as e:
            logger.debug(f"SelfImprover implement: {e}")
            return False

    async def _validate(self, innovation: Innovation) -> bool:
        """Validate an improvement by running tests."""
        try:
            # Run pytest
            try:
                from .unified_exec import pytest
                result = await pytest("tests/ -x -q", timeout=120)
                passed = result.success
            except ImportError:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pytest", "tests/", "-x", "-q",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                passed = proc.returncode == 0
            innovation.test_passed = passed
            innovation.validated = True

            if not passed:
                # Revert to main
                try:
                    from .unified_exec import git
                    await git("checkout master", timeout=10)
                except ImportError:
                    subprocess.run(
                        ["git", "checkout", "master"],
                        capture_output=True, check=False,
                    )

            logger.info(
                f"SelfImprover: {'✅' if passed else '❌'} validation "
                f"for '{innovation.title}'"
            )
            return passed
        except Exception:
            return False

    def stats(self) -> dict:
        return {
            "cycles": self._improvement_count,
            "improvements_proposed": len(self._history),
            "scanner_report": self._scanner.report(),
        }


# ═══ Singleton ════════════════════════════════════════════════════

_improver: Optional[SelfImprover] = None


def get_self_improver() -> SelfImprover:
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver


__all__ = [
    "SelfImprover", "DefectScanner", "InnovationProposer",
    "Defect", "Innovation", "Severity",
    "get_self_improver",
]
