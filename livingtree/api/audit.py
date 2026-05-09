"""Audit logging — records all code mode operations with full traceability.

Log format (JSON Lines, daily rotation):
    data/audit/audit_2026-05-08.jsonl

Each entry:
    {
      "event_id": "evt_<uuid>",
      "timestamp": 1746700000.123,
      "user_id": "dev_xxx",
      "user_name": "张三",
      "operation": "project.create",
      "project": "my-project",
      "agent_id": "agent_xxx" | null,
      "trace_id": "tr_xxx" | null,
      "file_path": "src/main.py" | null,
      "details": "Created project 'my-project'",
      "metadata": {}
    }
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from loguru import logger

from livingtree.api.auth import get_current_user, is_admin

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DIR = PROJECT_ROOT / "data" / "audit"
_write_lock = threading.Lock()

OPERATION_TEMPLATES = {
    "project.create":        {"action": "创建项目",           "risk": "low"},
    "project.delete":        {"action": "删除项目",           "risk": "high"},
    "project.sync":          {"action": "Git 同步项目",       "risk": "low"},
    "repo.clone":            {"action": "克隆 GitHub 仓库",   "risk": "medium"},
    "file.write":            {"action": "写入文件",            "risk": "medium"},
    "file.delete":           {"action": "删除文件",            "risk": "high"},
    "file.diff_apply":       {"action": "应用代码差异",        "risk": "medium"},
    "auth.github_login":     {"action": "GitHub 登录",         "risk": "low"},
    "security.scan":         {"action": "安全扫描",            "risk": "low"},
    "workspace.create":      {"action": "创建工作空间",        "risk": "low"},
    "workspace.delete":      {"action": "删除工作空间",        "risk": "high"},
    "workspace.invite":      {"action": "邀请工作空间成员",    "risk": "medium"},
    "workspace.remove_member":{"action": "移除工作空间成员",   "risk": "medium"},
}


def _today_log_path() -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit_{date_str}.jsonl"


def _log_entry(entry: dict) -> None:
    with _write_lock:
        path = _today_log_path()
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")


def log_operation(
    user_id: str,
    user_name: str,
    operation: str,
    *,
    project: str = "",
    agent_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    file_path: str = "",
    details: str = "",
    metadata: Optional[dict] = None,
) -> str:
    """Record a code mode operation. Returns the event_id."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    if not trace_id:
        trace_id = f"tr_{uuid.uuid4().hex[:12]}"

    template = OPERATION_TEMPLATES.get(operation, {"action": operation, "risk": "info"})
    entry = {
        "event_id": event_id,
        "timestamp": time.time(),
        "user_id": user_id,
        "user_name": user_name,
        "operation": operation,
        "action_cn": template["action"],
        "risk": template["risk"],
        "project": project,
        "agent_id": agent_id,
        "trace_id": trace_id,
        "file_path": file_path,
        "details": details or f"{user_name} {template['action']}: {project or file_path}",
        "metadata": metadata or {},
    }
    _log_entry(entry)
    logger.info(f"Audit: [{operation}] {user_name}({user_id}) — {details or project or file_path}")
    return event_id


def query_logs(
    *,
    user_id: Optional[str] = None,
    operation: Optional[str] = None,
    risk: Optional[str] = None,
    project: Optional[str] = None,
    trace_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Query audit logs with optional filters. Reads all available daily files."""
    results = []
    if not AUDIT_DIR.exists():
        return results

    for log_file in sorted(AUDIT_DIR.glob("audit_*.jsonl"), reverse=True):
        try:
            for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if user_id and entry.get("user_id") != user_id:
                    continue
                if operation and entry.get("operation") != operation:
                    continue
                if risk and entry.get("risk") != risk:
                    continue
                if project and entry.get("project") != project:
                    continue
                if trace_id and entry.get("trace_id") != trace_id:
                    continue

                results.append(entry)
                if len(results) >= offset + limit:
                    return results[offset:offset + limit]
        except Exception:
            continue

    return results[offset:offset + limit]


def get_trace_chain(trace_id: str) -> list[dict]:
    """Get the full operation chain for a given trace_id."""
    return query_logs(trace_id=trace_id, limit=1000)


def get_metrics() -> dict:
    """Aggregate metrics for the observability dashboard."""
    now = time.time()
    today_cutoff = now - 86400
    week_cutoff = now - 86400 * 7

    today_logs = []
    all_logs = []
    if AUDIT_DIR.exists():
        for log_file in AUDIT_DIR.glob("audit_*.jsonl"):
            try:
                for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        all_logs.append(entry)
                        if entry.get("timestamp", 0) >= today_cutoff:
                            today_logs.append(entry)
                    except json.JSONDecodeError:
                        continue
            except Exception:
                continue

    def _count_by(entries: list[dict], key: str) -> dict:
        counts = {}
        for e in entries:
            val = e.get(key, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts

    def _count_by_user(entries: list[dict]) -> dict:
        counts = {}
        for e in entries:
            uid = e.get("user_id", "unknown")
            counts[uid] = counts.get(uid, {"name": e.get("user_name", ""), "count": 0})
            counts[uid]["count"] += 1
        return counts

    return {
        "total_operations": len(all_logs),
        "today_operations": len(today_logs),
        "ops_by_type": _count_by(today_logs, "operation"),
        "ops_by_risk": _count_by(today_logs, "risk"),
        "ops_by_project": _count_by(today_logs, "project"),
        "active_users": _count_by_user(today_logs),
        "high_risk_today": [e for e in today_logs if e.get("risk") == "high"][-20:],
    }


# ═══ Route Registration ═══


def setup_audit_routes(app: FastAPI) -> None:
    """Register audit log query & metrics endpoints."""

    @app.get("/api/audit/logs")
    async def audit_logs(
        user: dict = Depends(get_current_user),
        operation: str = Query(default=""),
        risk: str = Query(default=""),
        project: str = Query(default=""),
        trace_id: str = Query(default=""),
        limit: int = Query(default=100, le=500),
        offset: int = Query(default=0),
    ):
        """Query audit logs. Admin sees all; user sees own."""
        user_id = user["user_id"]
        admin = is_admin(user_id)
        query_user = user_id if not admin else None
        logs = query_logs(
            user_id=query_user,
            operation=operation or None,
            risk=risk or None,
            project=project or None,
            trace_id=trace_id or None,
            limit=limit,
            offset=offset,
        )
        return {"total": len(logs), "logs": logs}

    @app.get("/api/audit/trace/{trace_id}")
    async def audit_trace(
        trace_id: str,
        user: dict = Depends(get_current_user),
    ):
        """Get the full operation chain for a trace."""
        chain = get_trace_chain(trace_id)
        return {"trace_id": trace_id, "chain": chain, "length": len(chain)}

    @app.get("/api/audit/metrics")
    async def audit_metrics(
        user: dict = Depends(get_current_user),
    ):
        """Get code mode observability metrics. Admin only."""
        if not is_admin(user["user_id"]):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        return get_metrics()

    @app.get("/api/code/projects/{name}/scan")
    async def scan_project(
        name: str,
        user: dict = Depends(get_current_user),
    ):
        """Security scan a project for common vulnerabilities."""
        findings = scan_project_security(user["user_id"], name)
        log_operation(user["user_id"], user.get("name", ""), "security.scan",
                      project=name,
                      details=f"扫描项目 '{name}' 安全: {len(findings)} 条发现")
        return {
            "project": name,
            "findings": findings,
            "total": len(findings),
            "passed": len(findings) == 0,
        }

    logger.info("Audit API routes registered")


# ═══ Security Scanner ═══

SECURITY_PATTERNS = {
    "hardcoded_secret": {
        "pattern": r'(?:password|passwd|secret|api_key|apikey|token|auth)\s*[:=]\s*["\'](?!.*\{).{6,}["\']',
        "severity": "high",
        "message": "发现硬编码凭据/密钥",
        "remediation": "使用环境变量或配置文件存储敏感信息",
    },
    "sql_injection": {
        "pattern": r'(?:execute|cursor\.execute)\([\s\S]*?f["\']',
        "severity": "high",
        "message": "发现潜在的 SQL 注入风险 (f-string SQL)",
        "remediation": "使用参数化查询替代字符串拼接",
    },
    "os_command_injection": {
        "pattern": r'os\.system\(.*\+|subprocess\.(?:call|run|Popen)\(.*\+',
        "severity": "high",
        "message": "发现潜在的命令注入风险",
        "remediation": "使用列表参数或 shlex.quote() 转义用户输入",
    },
    "eval_exec": {
        "pattern": r'\b(?:eval|exec|compile)\s*\(\s*[^)]*\b(?:user|input|request|param)',
        "severity": "critical",
        "message": "发现 eval/exec 使用用户输入",
        "remediation": "避免使用 eval/exec 处理用户输入",
    },
    "unsafe_deserialize": {
        "pattern": r'(?:pickle|yaml\.load|marshal)\.(?:loads?|dump)',
        "severity": "medium",
        "message": "发现不安全的反序列化",
        "remediation": "使用 yaml.safe_load() 或避免 pickle 反序列化不可信数据",
    },
    "debug_mode": {
        "pattern": r'(?:DEBUG|debug)\s*=\s*True',
        "severity": "medium",
        "message": "发现 DEBUG 模式开启",
        "remediation": "生产环境关闭 DEBUG 模式",
    },
    "weak_crypto": {
        "pattern": r'\b(?:md5|sha1|DES|RC4)\b',
        "severity": "low",
        "message": "发现弱加密算法",
        "remediation": "使用 SHA-256 或 bcrypt/scrypt 替代",
    },
}


def scan_project_security(user_id: str, project: str) -> list[dict]:
    """Quick security scan of a project directory. Returns list of findings."""
    from .code_api import _get_project_dir

    proj_dir = _get_project_dir(user_id, project)
    if not proj_dir.is_dir():
        return []

    findings = []
    text_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bat", ".ps1", ".yaml", ".yml", ".toml", ".json", ".xml", ".html", ".php", ".rb", ".java", ".go", ".rs", ".env"}

    for file_path in proj_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in text_extensions:
            continue
        if file_path.stat().st_size > 500 * 1024:
            continue
        if ".git" in file_path.parts:
            continue
        if "node_modules" in file_path.parts:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(file_path.relative_to(proj_dir)).replace("\\", "/")
        for rule_name, rule in SECURITY_PATTERNS.items():
            import re as re_module
            matches = re_module.findall(rule["pattern"], content, re_module.IGNORECASE)
            for match in matches[:3]:
                line_no = 1
                for i, line in enumerate(content.split("\n"), 1):
                    if isinstance(match, str) and match in line:
                        line_no = i
                        break
                findings.append({
                    "rule": rule_name,
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "remediation": rule["remediation"],
                    "file": rel_path,
                    "line": line_no,
                    "snippet": str(match)[:120],
                })
            if len(findings) >= 30:
                return findings[:30]

    return sorted(findings, key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f["severity"], 4))
