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
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync


IMPROVEMENTS_DIR = Path(".livingtree/improvements")


def _extract_json(text: str) -> str | None:
    """Extract balanced JSON object from text. Returns None if not found."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


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

        # Fast file discovery via FastFileSystem (MFT/mtime cached) or fallback
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            fast_entries = ffs.scan_tree(str(root), max_depth=10, extensions=[".py"])
            py_files = [Path(e.full_path) for e in fast_entries
                       if not any(p in e.full_path for p in ("__pycache__", ".venv", "venv"))]
            if len(py_files) < 50:  # Fallback: scan_tree may not be available
                py_files = list(root.rglob("*.py"))
        except Exception:
            py_files = list(root.rglob("*.py"))
        logger.info(f"DefectScanner: scanning {len(py_files)} files")

        # Fast regex pass (parallel)
        tasks = [self._scan_file(f) for f in py_files[:200]]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Ripgrep-accelerated pattern search (targeted, 100x faster)
        await self._scan_with_ripgrep(root)

        # Deep analysis via CodeGraph + ASTParser
        await self._code_graph_analysis(root)

        # LLM-powered deep architectural analysis (mandatory when defects found)
        await self._llm_deep_analysis()

        logger.info(f"DefectScanner: found {len(self._defects)} defects")
        return self._defects

    async def _scan_with_ripgrep(self, root: Path):
        """Use FastFileSystem.grep() for pattern search (rg if available, otherwise mmap+regex).

        Falls back to Python-native mmap + compiled regex + ThreadPoolExecutor when rg unavailable.
        """
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            root_str = str(root)
            for pattern, category, severity, title_fmt in [
                (r"except\s+Exception\s*:\s*\n\s+pass", "safety", Severity.HIGH,
                 "bare except:pass in {}"),
                (r"except\s*:\s*\n\s+pass", "safety", Severity.HIGH,
                 "bare except:pass in {}"),
                (r"TODO|FIXME|HACK|XXX", "coverage", Severity.LOW,
                 "Unresolved marker in {}"),
                (r"pass\s*$", "architecture", Severity.LOW,
                 "Empty block in {}"),
            ]:
                matches = ffs.grep(root_str, pattern, file_glob="*.py",
                                   max_results=100, ignore_case=False)
                for m in matches[:30]:
                    self._defects.append(Defect(
                        category=category, severity=severity,
                        title=title_fmt.format(Path(m.file_path).name),
                        description=f"Line {m.line_number}: {m.line_text[:100]}",
                        file_path=m.file_path, line_number=m.line_number,
                        evidence=m.line_text[:200],
                    ))
        except Exception as e:
            logger.debug(f"ripgrep scan: {e}")

    async def _code_graph_analysis(self, root: Path):
        """Deep analysis using CodeGraph (call graph, deps) + ASTParser (tree-sitter)
        + CodeAnalyzer (complexity, dead code, impact scores)."""
        try:
            from ..capability.code_graph import CodeGraph  # TODO(bridge): via bridge.ToolRegistry
            from ..capability.ast_parser import ASTParser
            from .code_analyzer import CodeAnalyzer

            cg = CodeGraph()
            ast = ASTParser()
            analyzer = CodeAnalyzer()

            # Load cached graph if available, else full index
            cache_path = root / "../.livingtree/code_graph.pickle"
            if cache_path.exists():
                try:
                    cg.load(str(cache_path))
                    logger.info("CodeGraph: loaded from cache")
                except Exception:
                    pass

            if cg.stats().total_entities < 1000:
                stats = cg.index(str(root), patterns=["**/*.py"])
                try:
                    cg.save(str(cache_path))
                except Exception:
                    pass
            else:
                stats = cg.stats()

            # Circular dependency detection via graph traversal
            cycles = self._find_dependency_cycles(cg)
            for cycle in cycles[:10]:
                self._defects.append(Defect(
                    category="architecture", severity=Severity.HIGH,
                    title=f"Circular dependency: {cycle[0]}",
                    description=f"Module cycle ({len(cycle)} nodes): {' → '.join(cycle[:4])}",
                    file_path=cycle[0],
                    evidence=f"Cycle length: {len(cycle)}",
                ))

            # Uncovered functions (no callers = potential dead code)
            uncovered = cg.find_uncovered()
            for entity in uncovered[:20]:
                self._defects.append(Defect(
                    category="coverage", severity=Severity.MEDIUM,
                    title=f"Unreferenced function: {entity.name}",
                    description=f"No callers in codebase — potential dead code in {entity.file}",
                    file_path=entity.file,
                    line_number=entity.line,
                ))

            # Hub detection (architectural bottlenecks)
            hubs = cg.find_hubs(10)
            for entity in hubs[:5]:
                total_conn = len(entity.dependents) + len(entity.dependencies)
                self._defects.append(Defect(
                    category="architecture", severity=Severity.MEDIUM,
                    title=f"Architectural hub: {entity.name}",
                    description=f"{entity.file} — {len(entity.dependents)} dependents + {len(entity.dependencies)} deps (total {total_conn})",
                    file_path=entity.file,
                ))

            # CodeAnalyzer: complexity + dead code on top risk files only
            # Target hub files (>20 connections) + files flagged by regex scanner
            hub_files = {e.file for e in hubs if (len(e.dependents) + len(e.dependencies)) > 20}
            flagged_files = {d.file_path for d in self._defects
                           if d.category == "architecture"}
            target_files = list(hub_files | flagged_files)[:20]

            for fpath in target_files:
                if not Path(fpath).exists():
                    continue
                try:
                    result = analyzer.analyze_file(fpath, call_graph=cg)
                    # Complexity: only report high/critical
                    for r in result.complexity:
                        if r.risk in ("high", "critical"):
                            self._defects.append(Defect(
                                category="architecture", severity=Severity.MEDIUM,
                                title=f"Complex function: {r.name} (CC={r.cyclomatic}, Cog={r.cognitive})",
                                description=f"{r.file}:{r.line} — {r.lines} lines, {r.param_count} params",
                                file_path=r.file, line_number=r.line,
                                evidence=f"cyclomatic={r.cyclomatic} cognitive={r.cognitive}",
                            ))
                    # Dead code
                    for dc in result.dead_code[:10]:
                        self._defects.append(Defect(
                            category="coverage", severity=Severity.LOW,
                            title=f"Dead code: {dc.name} ({dc.reason})",
                            description=f"{dc.file}:{dc.line}",
                            file_path=dc.file, line_number=dc.line,
                        ))
                    for go in result.god_objects[:3]:
                        self._defects.append(Defect(
                            category="architecture", severity=Severity.HIGH,
                            title=go, description="Too many methods — split into smaller classes",
                            file_path=fpath,
                        ))
                except Exception:
                    pass

            logger.info(
                f"CodeAnalyzer: {len(target_files)} target files analyzed, "
                f"{len(self._defects)} total defects"
            )

            # AST-based: unused imports in top 100 files
            for py_file in list(root.rglob("**/*.py"))[:100]:
                try:
                    imports = ast.extract_imports(str(py_file), "python")
                    functions = ast.extract_functions(str(py_file), "python")
                    imported_names = {i.name.split(".")[0] for i in imports}
                    used_names = set()
                    for f in functions:
                        for edge in f.get("edges", []):
                            if edge.type == "calls":
                                used_names.add(edge.target.split(".")[0])
                    unused = imported_names - used_names - {"__future__", "sys", "os", "typing", "logging", "json", "time", "re", "asyncio"}
                    for name in unused:
                        self._defects.append(Defect(
                            category="architecture", severity=Severity.LOW,
                            title=f"Unused import: {name}",
                            description=f"Imported but never referenced in {py_file.name}",
                            file_path=str(py_file),
                        ))
                except Exception:
                    pass

            gs = cg.stats()
            logger.info(
                f"CodeGraph+ASTParser: {len(cycles)} cycles, {len(uncovered)} dead, "
                f"{len(hubs)} hubs (entities={gs.total_entities}, edges={gs.total_edges})"
            )

        except ImportError as e:
            logger.debug(f"CodeGraph/ASTParser skipped: {e}")
        except Exception as e:
            logger.debug(f"CodeGraph analysis: {e}")

    @staticmethod
    def _find_dependency_cycles(cg) -> list[list[str]]:
        """Detect cycles in the CodeGraph entity dependency graph via DFS."""
        visited: set[str] = set()
        stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]):
            if node in stack:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            path.append(node)
            entity = cg._entities.get(node)
            if entity:
                for dep_id in entity.dependencies:
                    dfs(dep_id, list(path))
            stack.discard(node)

        for eid in list(cg._entities.keys())[:500]:
            if eid not in visited:
                dfs(eid, [])
        return [c for c in cycles if 2 <= len(c) <= 10]

    async def _scan_file(self, file_path: Path):
        """Scan a single file for defects."""
        try:
            # Fast read via FastFileSystem, fallback to direct I/O
            try:
                from ..infrastructure.fast_fs import get_fast_fs
                content = get_fast_fs().read_text(str(file_path))
            except Exception:
                content = file_path.read_text(errors="replace")
            if not content:
                return
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
        """LLM-powered architectural analysis (mandatory when defects found).

        Uses TreeLLM + ContextMoE for context-aware deep analysis:
          1. ContextMoE: enrich defect list with project memory
          2. TreeLLM: multi-provider reasoning across defect patterns
          3. HolisticElection: pick best provider for analysis task

        Produces: architectural insights, cross-defect patterns, fix priorities.
        """
        if len(self._defects) < 3:
            return

        try:
            from .core import TreeLLM
            from .context_moe import get_context_moe
            from .holistic_election import get_election

            llm = TreeLLM.from_config()
            moe = await get_context_moe("improve_scanner")

            # Build defect summary for LLM
            by_category: dict[str, list[Defect]] = {}
            for d in self._defects:
                by_category.setdefault(d.category, []).append(d)

            # Enrich with ContextMoE project memory
            summary_parts = []
            for cat, defs in sorted(by_category.items(), key=lambda x: -len(x[1])):
                top = defs[:5]
                summary_parts.append(
                    f"**{cat}** ({len(defs)} total):\n" +
                    "\n".join(f"  - [{d.severity.value}] {d.title[:100]}" for d in top)
                )
            defect_summary = "\n".join(summary_parts)
            enriched = moe.build_enriched_message(
                f"代码质量分析：{len(self._defects)} 个缺陷", 
                await moe.query(defect_summary, "code_analysis"),
            )

            # Elect best provider for analysis
            provider = await llm.smart_route(defect_summary, task_type="code")

            prompt = (
                f"你是一个资深代码审查架构师。分析以下 LivingTree 项目的缺陷扫描结果，"
                f"提供深度架构分析和可执行的修复方案。\n\n"
                f"## 缺陷汇总 ({len(self._defects)} total)\n{defect_summary[:3000]}\n\n"
                f"{enriched}\n\n"
                f"请输出 JSON 格式的分析报告:\n"
                f'{{"top_issues": [{{"title": "", "impact": "", "files": [], "fix": ""}}],'
                f'"patterns": [{{"name": "", "affected_count": 0, "root_cause": ""}}],'
                f'"priority_order": ["file1.py", "file2.py"],'
                f'"architecture_score": 1-10,'
                f'"auto_fixable": ["defect_id1", "defect_id2"]}}'
            )
            result = await llm.chat(
                [{"role": "user", "content": prompt}],
                provider=provider, max_tokens=2000, temperature=0.3,
                task_type="code",
            )
            analysis_text = getattr(result, 'text', '') or str(result)

            # Parse JSON response
            analysis_text_clean = analysis_text
            code_block_m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', analysis_text_clean, re.DOTALL)
            if code_block_m:
                analysis_text_clean = code_block_m.group(1)
            json_obj = _extract_json(analysis_text_clean)
            try:
                analysis = json.loads(json_obj or "{}")
            except json.JSONDecodeError:
                analysis = {}

            # Add architectural insights as defects
            for issue in analysis.get("top_issues", [])[:3]:
                self._defects.append(Defect(
                    category="architecture", severity=Severity.HIGH,
                    title=f"[LLM] {issue.get('title', '')[:100]}",
                    description=issue.get("impact", "")[:500],
                    file_path=", ".join(issue.get("files", [])),
                    suggested_fix=issue.get("fix", ""),
                    confidence=0.8,
                ))

            # Add pattern insights
            for pattern in analysis.get("patterns", [])[:3]:
                self._defects.append(Defect(
                    category="architecture", severity=Severity.MEDIUM,
                    title=f"[Pattern] {pattern.get('name', '')}: {pattern.get('root_cause', '')}",
                    description=f"Affects {pattern.get('affected_count', 0)} files",
                    confidence=0.7,
                ))

            # Cross-defect correlation
            patterns = analysis.get("patterns", [])
            score = analysis.get("architecture_score", 0)
            self._defects.append(Defect(
                category="architecture", severity=Severity.HIGH,
                title=f"Architecture Score: {score}/10",
                description=f"LLM identified {len(patterns)} cross-cutting patterns across {len(self._defects)} defects",
                confidence=0.75,
            ))

            logger.info(
                f"LLM Deep Analysis: architecture={score}/10, "
                f"{len(patterns)} patterns, "
                f"provider={provider}"
            )

        except Exception as e:
            logger.warning(f"LLM deep analysis: {e}")

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

        # External learning patterns (from GitHub/arXiv/Nature → livingtree learn)
        self._ingest_external_patterns()

        logger.info(f"InnovationProposer: {len(self._innovations)} proposals")
        return self._innovations

    def _ingest_external_patterns(self):
        """Ingest patterns from ExternalLearningDriver (livingtree learn → persisted proposals)."""
        try:
            proposals_file = Path(".livingtree/learned_proposals.json")
            if not proposals_file.exists():
                return
            data = json.loads(proposals_file.read_text(encoding="utf-8"))
            for entry in data:
                if entry.get("confidence", 0) < 0.5:
                    continue
                self._innovations.append(Innovation(
                    title=f"[external:{entry.get('source','?')}] {entry.get('title','')[:80]}",
                    description=entry.get("description", "") or entry.get("suggested_change", ""),
                    category=entry.get("category", "pattern"),
                    inspired_by=entry.get("source_url", ""),
                    complexity="low",
                ))
            if data:
                logger.info(f"InnovationProposer: ingested {len(data)} external patterns")
        except Exception as e:
            logger.debug(f"InnovationProposer external: {e}")

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
        """Implement an innovation by generating code via LLM.

        Atomic modification protocol:
          1. Create git safety branch
          2. LLM generates code → write to temp file
          3. Atomic rename temp → target (OS-level atomic)
          4. git add + commit on safety branch
          5. On validation failure → git checkout master (automatic rollback)
        """
        try:
            from .unified_exec import git
            branch_name = f"improve/{innovation.id[:12]}"
            await git(f"checkout -b {branch_name}", timeout=10)

            # Build context-aware prompt using CodeContext (sliding window + compressed)
            from .core import TreeLLM
            from .code_context import get_code_context
            llm = TreeLLM()
            code_ctx = get_code_context()

            context = code_ctx.build(
                task_description=f"{innovation.title}\n{innovation.description}",
                max_tokens=6000,
            )
            prompt = (
                f"根据以下代码上下文,实现系统改进:\n\n"
                f"{context}\n\n"
                f"## 改进要求\n"
                f"标题: {innovation.title}\n"
                f"描述: {innovation.description}\n"
                f"类别: {innovation.category}\n"
                f"复杂度: {innovation.complexity}\n\n"
                f"输出: 具体可执行的Python代码修改。标注修改的文件路径。使用```python代码块。"
            )
            result = await llm.chat(
                [{"role": "user", "content": prompt[:8000]}],
                max_tokens=3000, temperature=0.2, task_type="code",
            )
            code = getattr(result, 'text', '') or str(result)
            innovation.code_patch = code[:5000]
            innovation.git_branch = branch_name

            # Atomic write to target file(s) via temp + rename
            applied = await self._atomic_apply(innovation)

            # Save proposal for human review
            IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
            proposal_path = IMPROVEMENTS_DIR / f"{innovation.id}.json"
            proposal_path.write_text(json.dumps({
                "id": innovation.id, "title": innovation.title,
                "description": innovation.description,
                "code_patch": innovation.code_patch,
                "category": innovation.category,
                "applied": applied,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            if applied:
                await git("add -A", timeout=10)
                await git(f'commit -m "improve: {innovation.title[:72]}"', timeout=10)

            logger.info(
                f"SelfImprover: {'applied' if applied else 'generated'} "
                f"'{innovation.title}' → {branch_name}"
            )
            return True
        except Exception as e:
            logger.debug(f"SelfImprover implement: {e}")
            try:
                await git("checkout master", timeout=10)
            except Exception:
                pass
            return False

    async def _atomic_apply(self, innovation: Innovation) -> bool:
        """Atomically write LLM-generated code to target files.
        
        Protocol: write to {file}.tmp → os.rename(tmp, file) → atomic on same filesystem.
        Backup preserved as {file}.bak for manual recovery.
        """
        applied = False
        code = innovation.code_patch
        if not code:
            return False

        targets = re.findall(r'#\s*(?:file|target|modify):\s*(\S+\.py)', code, re.IGNORECASE)
        if not targets:
            # Try extracting file path from markdown code blocks
            targets = re.findall(r'```python.*?\n.*?(?:#|//)\s*(?:in|file|path):\s*(\S+\.py)', code, re.DOTALL)

        for target in targets[:3]:
            try:
                tpath = Path(target)
                # Skip if target doesn't exist (new file)
                if not tpath.exists():
                    continue

                # Backup original
                bak = tpath.with_suffix(tpath.suffix + ".bak")
                shutil.copy2(str(tpath), str(bak))

                # Extract the specific code block for this file
                file_code = self._extract_code_for_file(code, target)
                if not file_code:
                    continue

                # Atomic write: temp → rename
                fd, tmp = tempfile.mkstemp(
                    dir=str(tpath.parent), prefix="." + tpath.name + ".",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(file_code)
                    os.replace(tmp, str(tpath))  # Atomic on same filesystem
                    applied = True
                    logger.info(f"Atomic write: {target} ({len(file_code)} bytes)")
                except Exception:
                    os.unlink(tmp)
                    raise
            except Exception as e:
                logger.debug(f"Atomic apply {target}: {e}")

        return applied

    @staticmethod
    def _extract_code_for_file(code: str, target: str) -> str:
        """Extract the code section intended for a specific target file from LLM output."""
        fname = Path(target).name
        # Look for ```python blocks mentioning the file
        pattern = rf'```python.*?(?:#.*?{re.escape(fname)}.*?\n)(.*?)```'
        m = re.search(pattern, code, re.DOTALL)
        if m:
            return m.group(1).strip()
        # Fallback: first ```python block
        m = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        return m.group(1).strip() if m else code[:5000]

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
