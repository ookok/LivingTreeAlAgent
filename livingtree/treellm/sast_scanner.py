"""SASTScanner — Static Application Security Testing via Bandit integration.

Wraps Bandit as a living tool with:
  - Full repository or targeted file scanning
  - Severity classification (HIGH/MEDIUM/LOW)
  - CWE mapping for each finding
  - Configurable skip lists (test IDs to ignore)
  - CI-friendly structured reports
  - Negative caching for fast re-scans (file hash based)
  - Auto-install of bandit if missing

Integration:
  scanner = get_sast_scanner()
  report = await scanner.scan()                          # full repo
  report = await scanner.scan_file("livingtree/treellm/core.py")
  report = await scanner.scan_diff()                      # staged changes only
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .unified_exec import run, pip_install
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



class SASTSeverity(IntEnum):
    UNDEFINED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SASTConfidence(IntEnum):
    UNDEFINED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


BANDIT_CWE_MAP: dict[str, str] = {
    "B101": "CWE-703",   # assert_used
    "B102": "CWE-78",    # exec_used
    "B103": "CWE-242",   # set_bad_file_permissions
    "B104": "CWE-200",   # hardcoded_bind_all_interfaces
    "B105": "CWE-259",   # hardcoded_password_string
    "B106": "CWE-259",   # hardcoded_password_funcarg
    "B107": "CWE-259",   # hardcoded_password_default
    "B108": "CWE-22",    # hardcoded_tmp_directory
    "B201": "CWE-78",    # subprocess_popen_with_shell_equals_true
    "B301": "CWE-502",   # pickle
    "B302": "CWE-502",   # marshal
    "B303": "CWE-327",   # md5
    "B304": "CWE-327",   # cipher_modes
    "B305": "CWE-327",   # cipher_modes
    "B306": "CWE-502",   # mktemp_q
    "B307": "CWE-78",    # eval
    "B308": "CWE-327",   # md5 (markup_safe)
    "B309": "CWE-79",    # httpsconnection
    "B310": "CWE-79",    # urllib_urlopen
    "B311": "CWE-330",   # random
    "B312": "CWE-79",    # telnetlib
    "B313": "CWE-20",    # xml_bad_cElementTree
    "B314": "CWE-20",    # xml_bad_ElementTree
    "B315": "CWE-20",    # xml_bad_expatreader
    "B316": "CWE-20",    # xml_bad_expatbuilder
    "B317": "CWE-20",    # xml_bad_sax
    "B318": "CWE-20",    # xml_bad_minidom
    "B319": "CWE-20",    # xml_bad_pulldom
    "B320": "CWE-20",    # xml_bad_etree
    "B321": "CWE-20",    # ftplib
    "B323": "CWE-327",   # unverified_context
    "B324": "CWE-327",   # hashlib_new_insecure_functions
    "B325": "CWE-327",   # tempnam
    "B401": "CWE-327",   # import_telnetlib
    "B402": "CWE-327",   # import_ftplib
    "B403": "CWE-327",   # import_pickle
    "B404": "CWE-78",    # import_subprocess
    "B405": "CWE-327",   # import_xml_etree
    "B406": "CWE-327",   # import_xml_sax
    "B407": "CWE-327",   # import_xml_expat
    "B408": "CWE-327",   # import_xml_minidom
    "B409": "CWE-327",   # import_xml_pulldom
    "B410": "CWE-20",    # import_lxml
    "B411": "CWE-327",   # import_xmlrpclib
    "B412": "CWE-400",   # import_httpoxy
    "B413": "CWE-327",   # import_pycrypto
    "B501": "CWE-295",   # request_with_no_cert_validation
    "B502": "CWE-295",   # ssl_with_bad_version
    "B503": "CWE-295",   # ssl_with_bad_defaults
    "B504": "CWE-295",   # ssl_with_no_version
    "B505": "CWE-327",   # weak_cryptographic_key
    "B506": "CWE-798",   # yaml_load
    "B507": "CWE-354",   # ssh_no_host_key_verification
    "B508": "CWE-354",   # snmp_insecure_version_check
    "B509": "CWE-400",   # snmp_crypto_check
    "B601": "CWE-78",    # paramiko_calls
    "B602": "CWE-78",    # subprocess_popen_with_shell_equals_true
    "B603": "CWE-78",    # subprocess_without_shell_equals_true
    "B604": "CWE-78",    # any_other_function_with_shell_equals_true
    "B605": "CWE-78",    # start_process_with_a_shell
    "B606": "CWE-78",    # start_process_with_no_shell
    "B607": "CWE-78",    # start_process_with_partial_path
    "B608": "CWE-89",    # hardcoded_sql_expressions
    "B609": "CWE-400",   # linux_commands_wildcard_injection
    "B610": "CWE-78",    # django_extra_used
    "B611": "CWE-400",   # django_rawsql_used
    "B701": "CWE-94",    # jinja2_autoescape_false
    "B702": "CWE-94",    # use_of_mako_templates
    "B703": "CWE-79",    # django_mark_safe
}


@dataclass
class SASTIssue:
    file: str
    line: int = 0
    col: int = 0
    test_id: str = ""          # B101, B102, etc.
    test_name: str = ""
    severity: SASTSeverity = SASTSeverity.UNDEFINED
    confidence: SASTConfidence = SASTConfidence.UNDEFINED
    message: str = ""
    code_snippet: str = ""
    cwe_id: str = ""
    recommendation: str = ""


@dataclass
class SASTReport:
    issues: list[SASTIssue] = field(default_factory=list)
    summary: str = ""
    files_scanned: int = 0
    loc_scanned: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    passed: bool = False
    score: int = 0
    scan_time_s: float = 0.0


class SASTScanner:
    """Bandit-based SAST scanner as a living tool."""

    _instance: Optional["SASTScanner"] = None

    DEFAULT_SKIP: tuple[str, ...] = ("B101", "B104", "B311")   # assert, bind_all, random
    DEFAULT_EXCLUDE: tuple[str, ...] = ("/tests/", "/test_", "/venv/",
                                         "/.venv/", "/node_modules/", "/.git/",
                                         "/__pycache__/", "/.tox/", "/.mypy_cache/")

    @classmethod
    def instance(cls) -> "SASTScanner":
        if cls._instance is None:
            cls._instance = SASTScanner()
        return cls._instance

    def __init__(self):
        self._skip: set[str] = set(self.DEFAULT_SKIP)
        self._exclude: set[str] = set(self.DEFAULT_EXCLUDE)
        self._reports: list[SASTReport] = []
        self._cache: dict[str, SASTReport] = {}     # file-hash → cached report
        self._bandit_available: bool | None = None

    def configure(self, skip: set[str] | None = None,
                  exclude: set[str] | None = None) -> None:
        if skip is not None:
            self._skip = skip
        if exclude is not None:
            self._exclude = exclude

    async def _ensure_bandit(self) -> bool:
        if self._bandit_available is not None:
            return self._bandit_available
        result = await run("bandit --version", timeout=15)
        self._bandit_available = result.success
        if not self._bandit_available:
            installed = await pip_install("bandit", timeout=60)
            self._bandit_available = installed
        return self._bandit_available is True

    # ── Scan APIs ──────────────────────────────────────────────

    async def scan(self, target: str = "livingtree/") -> SASTReport:
        if not await self._ensure_bandit():
            return SASTReport(summary="Bandit not available; install with: pip install bandit")

        target_path = Path(target)
        cache_key = self._hash_target(target_path)
        if cache_key and cache_key in self._cache:
            logger.debug(f"SAST cache hit: {target}")
            return self._cache[cache_key]

        import time
        t0 = time.time()

        skip_args = " ".join(f"--skip {s}" for s in self._skip)
        exclude_args = " ".join(f"--exclude {e}" for e in self._exclude)
        cmd = f"bandit -r {target} -f json {skip_args} {exclude_args} 2>&1"
        result = await run(cmd, timeout=300)

        elapsed = time.time() - t0
        report = self._parse_bandit_json(result, elapsed)

        if cache_key:
            self._cache[cache_key] = report
        self._reports.append(report)
        return report

    async def scan_file(self, file_path: str) -> SASTReport:
        path = Path(file_path)
        if not path.exists():
            return SASTReport(summary=f"File not found: {file_path}")
        return await self.scan(str(path.resolve()))

    async def scan_diff(self, base: str = "HEAD~1",
                        current: str = "HEAD") -> SASTReport:
        import tempfile
        diff_result = await run(f"git diff --name-only {base} {current}", timeout=15)
        if not diff_result.success:
            return SASTReport(summary=f"Git diff failed: {diff_result.stderr[:200]}")

        files = [f.strip() for f in diff_result.stdout.split("\n")
                 if f.strip() and f.strip().endswith(".py")]

        if not files:
            return SASTReport(summary="No Python files changed", passed=True, score=100)

        merged = SASTReport(summary=f"Diff scan: {len(files)} files")
        for f in files:
            file_report = await self.scan_file(f)
            merged.issues.extend(file_report.issues)
            merged.files_scanned += file_report.files_scanned

        merged.high_count = sum(1 for i in merged.issues if i.severity == SASTSeverity.HIGH)
        merged.medium_count = sum(1 for i in merged.issues if i.severity == SASTSeverity.MEDIUM)
        merged.low_count = sum(1 for i in merged.issues if i.severity == SASTSeverity.LOW)
        merged.passed = merged.high_count == 0
        merged.score = max(0, 100 - (merged.high_count * 20) - (merged.medium_count * 5) - (merged.low_count * 1))
        merged.summary = self._build_summary(merged)
        self._reports.append(merged)
        return merged

    # ── Parsing ──────────────────────────────────────────────

    def _parse_bandit_json(self, result: "ExecResult",
                           elapsed: float) -> SASTReport:
        report = SASTReport(scan_time_s=elapsed)

        if not result.stdout.strip():
            report.passed = True
            report.score = 100
            report.summary = "No findings."
            return report

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            report.summary = f"Bandit output parse error. stderr: {result.stderr[:200]}"
            return report

        metrics = data.get("metrics", {})
        report.files_scanned = len(data.get("results", []))
        if "_totals" in metrics:
            report.loc_scanned = metrics["_totals"].get("loc", 0)

        for finding in data.get("results", []):
            test_id = finding.get("test_id", "")
            issue = SASTIssue(
                file=finding.get("filename", ""),
                line=finding.get("line_number", 0),
                col=finding.get("col_offset", 0),
                test_id=test_id,
                test_name=finding.get("test_name", ""),
                severity=SASTSeverity(finding.get("issue_severity", "low").lower()),
                confidence=SASTConfidence(finding.get("issue_confidence", "low").lower()),
                message=finding.get("issue_text", "")[:300],
                code_snippet=finding.get("code", "")[:200],
                cwe_id=BANDIT_CWE_MAP.get(test_id, ""),
                recommendation=self._recommendation_for(test_id),
            )
            report.issues.append(issue)

            if issue.severity == SASTSeverity.HIGH:
                report.high_count += 1
            elif issue.severity == SASTSeverity.MEDIUM:
                report.medium_count += 1
            else:
                report.low_count += 1

        report.passed = report.high_count == 0
        report.score = max(0, 100 - (report.high_count * 20) -
                           (report.medium_count * 5) - (report.low_count * 1))
        report.summary = self._build_summary(report)
        return report

    @staticmethod
    def _build_summary(report: SASTReport) -> str:
        parts = [
            f"SAST scan: {report.files_scanned} files, {report.loc_scanned} LOC",
            f"HIGH: {report.high_count}, MEDIUM: {report.medium_count}, LOW: {report.low_count}",
            f"Result: {'PASS' if report.passed else 'FAIL'} (score: {report.score}/100)",
            f"Time: {report.scan_time_s:.1f}s",
        ]
        return " | ".join(parts)

    @staticmethod
    def _recommendation_for(test_id: str) -> str:
        recs = {
            "B102": "Use subprocess.run() without shell=True or list arguments",
            "B103": "Use os.chmod() with explicit permission masks",
            "B105": "Use environment variables or secret manager, not hardcoded values",
            "B106": "Use environment variables or secret manager for passwords",
            "B107": "Use environment variables or secret manager for defaults",
            "B108": "Use tempfile.gettempdir() + tempfile.mkdtemp()",
            "B201": "Never use shell=True; list arguments only",
            "B202": "Never use shell=True; pass args as list",
            "B301": "Use json instead of pickle for serialization",
            "B303": "Use hashlib.sha256() instead of md5()",
            "B304": "Use AES-GCM instead of ECB/CBC modes",
            "B307": "Avoid eval(); use ast.literal_eval() or json.loads()",
            "B506": "Use yaml.safe_load() instead of yaml.load()",
            "B601": "Use context manager for SSH connection",
            "B608": "Use parameterized queries; never string formatting for SQL",
            "B701": "Set autoescape=True in Jinja2 Environment",
        }
        return recs.get(test_id, "Review finding and apply secure coding best practices")

    def _hash_target(self, target: Path) -> str:
        if not target.exists():
            return ""
        if target.is_file():
            try:
                return hashlib.sha256(
                    target.read_bytes()[:4096]
                ).hexdigest()[:16]
            except Exception:
                return ""
        if target.is_dir():
            try:
                py_files = sorted(target.rglob("*.py"))[:50]
                combined = b"".join(
                    f.read_bytes()[:1024] for f in py_files
                    if f.exists() and f.suffix == ".py"
                )
                return hashlib.sha256(combined).hexdigest()[:16]
            except Exception:
                return ""
        return ""

    def stats(self) -> dict:
        return {"scans": len(self._reports), "cache_hits": len(self._cache)}

    def clear_cache(self) -> None:
        self._cache.clear()

    # ── Markdown output ──────────────────────────────────────

    def format_markdown(self, report: SASTReport) -> str:
        lines = [
            f"## SAST Scan — Score: {report.score}/100",
            "",
            report.summary,
            "",
        ]
        if report.issues:
            lines.append("| File | Line | Severity | Confidence | CWE | Issue |")
            lines.append("|------|------|----------|------------|-----|-------|")
            for i in report.issues:
                sev = i.severity.name
                conf = i.confidence.name
                lines.append(
                    f"| {i.file[:35]} | L{i.line} | {sev} | {conf} "
                    f"| {i.cwe_id} | {i.message[:60]} |"
                )

            by_sev = {}
            for i in report.issues:
                by_sev.setdefault(i.severity, []).append(i)

            for sev in (SASTSeverity.HIGH, SASTSeverity.MEDIUM, SASTSeverity.LOW):
                if sev in by_sev:
                    lines.append(f"\n### {sev.name} Severity Findings")
                    for i in by_sev[sev]:
                        lines.append(f"- **{i.file}:L{i.line}** [{i.test_id}] {i.message}")
                        if i.code_snippet:
                            lines.append(f"  ```\n  {i.code_snippet[:100]}\n  ```")
                        if i.recommendation:
                            lines.append(f"  → {i.recommendation}")

        lines.append("")
        return "\n".join(lines)


_scanner: Optional[SASTScanner] = None


def get_sast_scanner() -> SASTScanner:
    global _scanner
    if _scanner is None:
        _scanner = SASTScanner()
    return _scanner


__all__ = ["SASTScanner", "SASTReport", "SASTIssue",
           "SASTSeverity", "SASTConfidence", "get_sast_scanner"]
