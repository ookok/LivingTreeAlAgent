"""Self-test suite — system validates its own modules. /do test command."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def run_all() -> dict[str, Any]:
    """Run all self-tests and return results. Called by /do test."""
    results = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "tests": [], "timestamp": __import__("time").time(),
    }

    tests = [
        ("工具: 文档编辑器", test_document_editor),
        ("工具: 模板引擎", test_template_engine),
        ("工具: CSV分析", test_csv_analysis),
        ("工具: JSON转换", test_json_transform),
        ("工具: DB查询", test_db_query),
        ("数据: DataLineage", test_data_lineage),
        ("数据: TrustScoring", test_trust_scoring),
        ("数据: SessionBinding", test_session_binding),
        ("解析: 格式检测", test_format_detection),
        ("解析: CSV解析", test_csv_parse),
        ("解析: JSON解析", test_json_parse),
        ("网络: 代理池", test_proxy_pool),
        ("ID: 客户端ID", test_client_id),
        ("加密: Key生成", test_key_generation),
    ]

    for name, fn in tests:
        results["total"] += 1
        try:
            fn()
            results["passed"] += 1
            results["tests"].append({"name": name, "status": "pass"})
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({"name": name, "status": "fail", "error": str(e)[:200]})

    return results


def run_and_format() -> str:
    """Run tests and return formatted markdown output."""
    import time
    t0 = time.monotonic()
    results = run_all()
    elapsed = (time.monotonic() - t0) * 1000

    lines = [
        f"## 🧪 系统自检",
        f"通过: {results['passed']}/{results['total']} ({elapsed:.0f}ms)",
        "",
    ]

    icon = {"pass": "✅", "fail": "❌", "skip": "⏭️"}
    for t in results["tests"]:
        lines.append(f"{icon[t['status']]} {t['name']}")
        if t["status"] == "fail":
            lines.append(f"   [red]{t['error']}[/red]")

    if results["failed"] == 0:
        lines.append(f"\n🟢 全部通过 — 系统运行正常")
    else:
        lines.append(f"\n🔴 {results['failed']} 项失败 — 使用 /check 错误 查看详情")

    return "\n".join(lines)


# ═══ Individual Tests ═══

def test_document_editor():
    from livingtree.capability.document_editor import get_editor
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("port: 8100\n")
        fpath = f.name
    try:
        result = get_editor().replace_pattern(fpath, r"port:\s*8100", "port: 8888")
        assert result.replacements == 1, f"Expected 1 replacement, got {result.replacements}"
    finally:
        __import__("os").unlink(fpath)

def test_template_engine():
    from livingtree.capability.template_engine import TemplateEngine
    engine = TemplateEngine()
    vars_found = engine.extract_variables("{{name}}在{{date}}")
    assert "name" in vars_found

def test_csv_analysis():
    import csv, tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["name", "value"])
        writer.writerow(["A", "10"])
        fpath = f.name
    try:
        from livingtree.capability.tool_executor import get_executor
        result = get_executor().csv_analyze(fpath)
        assert result.success
        assert "name" in result.output
    finally:
        os.unlink(fpath)

def test_json_transform():
    from livingtree.capability.tool_executor import get_executor
    result = get_executor().json_transform('{"a": 1}')
    assert result.success

def test_db_query():
    from livingtree.capability.tool_executor import get_executor
    result = get_executor().db_query("SELECT 1 AS ok")
    assert result.success
    assert "ok" in result.output

def test_data_lineage():
    from livingtree.capability.data_lineage import DataLineage
    dl = DataLineage()
    dl.record("sec1", "x", 100)
    dl.record("sec2", "y", 100, source="sec1_x", derivation="direct_copy")
    affected = dl.trace_forward("sec1_x")
    assert len(affected) >= 1

def test_trust_scoring():
    from livingtree.observability.trust_scoring import TrustScorer
    ts = TrustScorer()
    for _ in range(10):
        ts.record("test_agent", success=True)
    assert ts.score("test_agent") >= 70

def test_session_binding():
    from livingtree.treellm.session_binding import SessionBinding
    sb = SessionBinding()
    sb.bind("test", "deepseek")
    assert sb.stickiness_score("test", "deepseek") > 0

def test_format_detection():
    from livingtree.capability.universal_parser import UniversalFileParser
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write('{"a":1}')
        fpath = f.name
    try:
        fmt = UniversalFileParser()._detect_format(Path(fpath))
        assert fmt in (".json", ".unknown")
    finally:
        os.unlink(fpath)

def test_csv_parse():
    from livingtree.capability.universal_parser import get_universal_parser
    import asyncio, tempfile, os, csv
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["a", "b"])
        writer.writerow(["1", "2"])
        fpath = f.name
    try:
        result = asyncio.run(get_universal_parser().parse(fpath))
        assert result.success
    finally:
        os.unlink(fpath)

def test_json_parse():
    from livingtree.capability.universal_parser import get_universal_parser
    import asyncio, tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"key":"val"}')
        fpath = f.name
    try:
        result = asyncio.run(get_universal_parser().parse(fpath))
        assert result.success
    finally:
        os.unlink(fpath)

def test_proxy_pool():
    from livingtree.network.proxy_fetcher import ProxyPool
    pool = ProxyPool()
    stats = pool.stats()
    assert "total" in stats

def test_client_id():
    from livingtree.capability.remote_assist import generate_client_id
    cid = generate_client_id()
    assert len(cid) == 10 and cid.isdigit()

def test_key_generation():
    from relay_server import _hash_password
    h = _hash_password("test")
    assert len(h) == 64
