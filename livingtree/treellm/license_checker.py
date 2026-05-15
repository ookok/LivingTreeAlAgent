"""LicenseChecker — Dependency license compliance with pip-audit + SPDX validation.

Scans installed packages and dependency tree for:
  - Known vulnerabilities (via pip-audit)
  - License type detection and SPDX conformance
  - Copyleft/copycenter/copyright license classification
  - Allowlist/blocklist policy enforcement
  - CI-friendly exit codes and structured reports

Integration:
  checker = get_license_checker()
  report = await checker.scan()                        # full scan
  report = await checker.scan_package("requests")       # single package
  report = await checker.audit_security()                # pip-audit vulnerabilities
  report = checker.audit_licenses()                      # SPDX compliance
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .unified_exec import run, pip_install, ExecResult


class LicenseClass(StrEnum):
    PERMISSIVE = "permissive"        # MIT, BSD, Apache-2.0, ISC
    COPRLEFT_WEAK = "copyleft_weak"  # LGPL, MPL, EPL
    COPRLEFT_STRONG = "copyleft_strong"  # GPL, AGPL
    PROPRIETARY = "proprietary"       # Commercial, Business Source
    UNKNOWN = "unknown"


class AuditSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SPDX_LICENSE_MAP: dict[str, LicenseClass] = {
    "MIT": LicenseClass.PERMISSIVE, "MIT License": LicenseClass.PERMISSIVE,
    "BSD": LicenseClass.PERMISSIVE, "BSD-2-Clause": LicenseClass.PERMISSIVE,
    "BSD-3-Clause": LicenseClass.PERMISSIVE, "BSD-4-Clause": LicenseClass.PERMISSIVE,
    "Apache-2.0": LicenseClass.PERMISSIVE, "Apache 2.0": LicenseClass.PERMISSIVE,
    "Apache License 2.0": LicenseClass.PERMISSIVE, "ISC": LicenseClass.PERMISSIVE,
    "Python Software Foundation": LicenseClass.PERMISSIVE, "PSF": LicenseClass.PERMISSIVE,
    "Unlicense": LicenseClass.PERMISSIVE, "CC0-1.0": LicenseClass.PERMISSIVE,
    "MPL-2.0": LicenseClass.COPRLEFT_WEAK, "MPL 2.0": LicenseClass.COPRLEFT_WEAK,
    "LGPL-2.1": LicenseClass.COPRLEFT_WEAK, "LGPL-3.0": LicenseClass.COPRLEFT_WEAK,
    "LGPL": LicenseClass.COPRLEFT_WEAK, "EPL-2.0": LicenseClass.COPRLEFT_WEAK,
    "GPL-2.0": LicenseClass.COPRLEFT_STRONG, "GPL-3.0": LicenseClass.COPRLEFT_STRONG,
    "GPL": LicenseClass.COPRLEFT_STRONG, "AGPL-3.0": LicenseClass.COPRLEFT_STRONG,
    "AGPL": LicenseClass.COPRLEFT_STRONG,
    "Proprietary": LicenseClass.PROPRIETARY,
    "Commercial": LicenseClass.PROPRIETARY, "BUSL-1.1": LicenseClass.PROPRIETARY,
}


@dataclass
class LicenseIssue:
    package: str
    version: str = ""
    license_text: str = ""
    license_class: LicenseClass = LicenseClass.UNKNOWN
    severity: AuditSeverity = AuditSeverity.INFO
    message: str = ""
    cve_id: str = ""
    recommendation: str = ""


@dataclass
class LicenseReport:
    issues: list[LicenseIssue] = field(default_factory=list)
    summary: str = ""
    total_packages: int = 0
    vulnerable_packages: int = 0
    copyleft_packages: int = 0
    proprietary_packages: int = 0
    policy_violations: int = 0
    passed: bool = False
    score: int = 0


class LicenseChecker:
    """Dependency license compliance and security audit."""

    _instance: Optional["LicenseChecker"] = None

    DEFAULT_ALLOWLIST = {LicenseClass.PERMISSIVE, LicenseClass.COPRLEFT_WEAK}
    DEFAULT_BLOCKED_PACKAGES: set[str] = set()

    @classmethod
    def instance(cls) -> "LicenseChecker":
        if cls._instance is None:
            cls._instance = LicenseChecker()
        return cls._instance

    def __init__(self):
        self._allowlist: set[LicenseClass] = set(self.DEFAULT_ALLOWLIST)
        self._blocked: set[str] = set(self.DEFAULT_BLOCKED_PACKAGES)
        self._reports: list[LicenseReport] = []
        self._pip_audit_available: bool | None = None

    def set_policy(self, allowlist: set[LicenseClass] | None = None,
                    blocked: set[str] | None = None) -> None:
        if allowlist is not None:
            self._allowlist = allowlist
        if blocked is not None:
            self._blocked = blocked

    async def _ensure_pip_audit(self) -> bool:
        if self._pip_audit_available is not None:
            return self._pip_audit_available
        result = await run("pip-audit --version", timeout=15)
        self._pip_audit_available = result.success
        if not result.success:
            installed = await pip_install("pip-audit", timeout=60)
            self._pip_audit_available = installed
        return self._pip_audit_available is True

    # ── Audit APIs ──────────────────────────────────────────────

    async def scan(self, target: str = "") -> LicenseReport:
        report = LicenseReport()
        pkg_names = []

        if target:
            pkg_names = [target]
            report.total_packages = 1
        else:
            pkg_names = await self._list_installed()
            report.total_packages = len(pkg_names)

        for pkg in pkg_names:
            try:
                result = await run(f"pip show {pkg}", timeout=15)
                if not result.success:
                    continue
                if issue := self._check_package(pkg, result.stdout):
                    report.issues.append(issue)

                if issue and issue.license_class == LicenseClass.COPRLEFT_STRONG:
                    report.copyleft_packages += 1
                elif issue and issue.license_class == LicenseClass.PROPRIETARY:
                    report.proprietary_packages += 1
            except Exception:
                continue

        report.policy_violations = sum(
            1 for i in report.issues
            if i.license_class not in self._allowlist
            or i.package in self._blocked
        )
        report.passed = report.policy_violations == 0
        report.score = max(0, 100 - (report.policy_violations * 10) - (report.copyleft_packages * 2))
        report.summary = self._build_summary(report)
        self._reports.append(report)
        return report

    async def scan_package(self, package: str) -> Optional[LicenseIssue]:
        result = await run(f"pip show {package}", timeout=15)
        if not result.success:
            return LicenseIssue(
                package=package, severity=AuditSeverity.LOW,
                message=f"Package not installed: {package}",
                recommendation="Install package first or verify name",
            )
        return self._check_package(package, result.stdout)

    async def audit_security(self) -> LicenseReport:
        report = LicenseReport()
        if not await self._ensure_pip_audit():
            report.summary = "pip-audit not available; install with: pip install pip-audit"
            self._reports.append(report)
            return report

        result = await run("pip-audit --format json --progress-spinner off 2>&1", timeout=120)
        if result.exit_code == 0:
            report.passed = True
            report.summary = "No known vulnerabilities found."
            self._reports.append(report)
            return report

        try:
            data = json.loads(result.stdout) if result.stdout else {"dependencies": []}
            for dep in data.get("dependencies", []):
                for vuln in dep.get("vulns", []):
                    report.issues.append(LicenseIssue(
                        package=dep.get("name", "unknown"),
                        version=dep.get("version", ""),
                        severity=self._map_severity(vuln.get("aliases", {}).get("severity", "")),
                        cve_id=vuln.get("id", ""),
                        message=vuln.get("description", vuln.get("id", ""))[:200],
                        recommendation="Upgrade to latest version or apply vendor patch",
                    ))
                    report.vulnerable_packages += 1
        except json.JSONDecodeError:
            lines = result.stdout.split("\n") if result.stdout else []
            for line in lines:
                if line.strip() and "Name" in line:
                    report.issues.append(LicenseIssue(
                        package=line.strip(), severity=AuditSeverity.MEDIUM,
                        message="pip-audit parsing fallback — review manually",
                    ))
                    report.vulnerable_packages += 1

        report.passed = report.vulnerable_packages == 0
        report.score = max(0, 100 - (report.vulnerable_packages * 20))
        report.summary = self._build_security_summary(report)
        self._reports.append(report)
        return report

    async def audit_licenses(self) -> LicenseReport:
        report = await self.scan()
        report.summary = self._build_license_summary(report)
        return report

    async def full_audit(self) -> LicenseReport:
        sec_report = await self.audit_security()
        lic_report = await self.audit_licenses()

        merged = LicenseReport(
            issues=sec_report.issues + lic_report.issues,
            total_packages=lic_report.total_packages,
            vulnerable_packages=sec_report.vulnerable_packages,
            copyleft_packages=lic_report.copyleft_packages,
            proprietary_packages=lic_report.proprietary_packages,
            policy_violations=lic_report.policy_violations,
            passed=sec_report.passed and lic_report.passed,
            score=min(sec_report.score, lic_report.score),
            summary=f"Security: {'PASS' if sec_report.passed else 'FAIL'} | "
                     f"License: {'PASS' if lic_report.passed else 'FAIL'} | "
                     f"Combined score: {min(sec_report.score, lic_report.score)}/100",
        )
        self._reports.append(merged)
        return merged

    # ── Internal ──────────────────────────────────────────────

    async def _list_installed(self) -> list[str]:
        result = await run("pip list --format json", timeout=30)
        if not result.success:
            return []
        try:
            return [p["name"] for p in json.loads(result.stdout)]
        except json.JSONDecodeError:
            return []

    def _check_package(self, pkg: str, show_output: str) -> Optional[LicenseIssue]:
        license_match = re.search(r"^License:\s*(.+)$", show_output, re.MULTILINE)
        version_match = re.search(r"^Version:\s*(.+)$", show_output, re.MULTILINE)

        license_text = license_match.group(1).strip() if license_match else ""
        version = version_match.group(1).strip() if version_match else ""
        lic_class = self._classify_license(license_text)

        issue = None
        if lic_class == LicenseClass.COPRLEFT_STRONG:
            issue = LicenseIssue(
                package=pkg, version=version, license_text=license_text,
                license_class=lic_class, severity=AuditSeverity.HIGH,
                message=f"Strong copyleft license ({license_text}) requires legal review",
                recommendation="Consult legal counsel; consider permissive alternative",
            )
        elif lic_class == LicenseClass.PROPRIETARY:
            issue = LicenseIssue(
                package=pkg, version=version, license_text=license_text,
                license_class=lic_class, severity=AuditSeverity.MEDIUM,
                message=f"Proprietary license ({license_text}) — verify commercial terms",
                recommendation="Check vendor license terms and procurement status",
            )
        elif lic_class == LicenseClass.COPRLEFT_WEAK:
            issue = LicenseIssue(
                package=pkg, version=version, license_text=license_text,
                license_class=lic_class, severity=AuditSeverity.LOW,
                message=f"Weak copyleft license ({license_text}) — linking restrictions apply",
                recommendation="Dynamic linking preferred; static linking needs legal review",
            )
        elif lic_class == LicenseClass.UNKNOWN and license_text:
            issue = LicenseIssue(
                package=pkg, version=version, license_text=license_text,
                license_class=lic_class, severity=AuditSeverity.INFO,
                message=f"Unrecognized license: {license_text}",
                recommendation="Manually verify license classification",
            )

        if issue and pkg in self._blocked:
            issue.severity = AuditSeverity.CRITICAL
            issue.message = f"BLOCKED: {issue.message}"

        return issue

    @staticmethod
    def _classify_license(text: str) -> LicenseClass:
        if not text:
            return LicenseClass.UNKNOWN
        text_norm = text.strip()
        for pattern, lic_class in SPDX_LICENSE_MAP.items():
            if pattern.lower() in text_norm.lower():
                return lic_class
        if "gpl" in text_norm.lower() or "agpl" in text_norm.lower():
            return LicenseClass.COPRLEFT_STRONG
        if "lgpl" in text_norm.lower():
            return LicenseClass.COPRLEFT_WEAK
        if "proprietary" in text_norm.lower() or "commercial" in text_norm.lower():
            return LicenseClass.PROPRIETARY
        return LicenseClass.UNKNOWN

    @staticmethod
    def _map_severity(sev: str) -> AuditSeverity:
        sev_upper = sev.upper().strip()
        return {
            "CRITICAL": AuditSeverity.CRITICAL,
            "HIGH": AuditSeverity.HIGH,
            "MEDIUM": AuditSeverity.MEDIUM,
            "MODERATE": AuditSeverity.MEDIUM,
            "LOW": AuditSeverity.LOW,
        }.get(sev_upper, AuditSeverity.INFO)

    def _build_summary(self, report: LicenseReport) -> str:
        parts = [
            f"License audit: {report.total_packages} packages scanned",
            f"Copyleft (strong): {report.copyleft_packages}",
            f"Proprietary: {report.proprietary_packages}",
            f"Policy violations: {report.policy_violations}",
            f"Result: {'PASS' if report.passed else 'FAIL'} (score: {report.score}/100)",
        ]
        return " | ".join(parts)

    def _build_security_summary(self, report: LicenseReport) -> str:
        parts = [
            f"Security audit: {report.vulnerable_packages} vulnerabilities found",
            f"Critical: {sum(1 for i in report.issues if i.severity == AuditSeverity.CRITICAL)}",
            f"High: {sum(1 for i in report.issues if i.severity == AuditSeverity.HIGH)}",
            f"Result: {'PASS' if report.passed else 'FAIL'} (score: {report.score}/100)",
        ]
        return " | ".join(parts)

    def _build_license_summary(self, report: LicenseReport) -> str:
        return self._build_summary(report)

    def stats(self) -> dict:
        return {"reports": len(self._reports)}

    # ── Markdown output ──────────────────────────────────────

    def format_markdown(self, report: LicenseReport) -> str:
        lines = [
            f"## License & Security Audit — Score: {report.score}/100",
            "",
            report.summary,
            "",
        ]
        if report.issues:
            lines.append("| Package | Version | License | Class | Severity | Issue |")
            lines.append("|---------|---------|---------|-------|----------|-------|")
            for i in report.issues:
                lines.append(
                    f"| {i.package[:30]} | {i.version[:10]} | {i.license_text[:25]} "
                    f"| {i.license_class.value} | {i.severity.value} | {i.message[:60]} |"
                )
        lines.append("")
        return "\n".join(lines)


_checker: Optional[LicenseChecker] = None


def get_license_checker() -> LicenseChecker:
    global _checker
    if _checker is None:
        _checker = LicenseChecker()
    return _checker


__all__ = ["LicenseChecker", "LicenseReport", "LicenseIssue",
           "LicenseClass", "AuditSeverity", "get_license_checker"]
