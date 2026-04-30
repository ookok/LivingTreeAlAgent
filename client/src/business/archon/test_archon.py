"""
Archon + OpenDataLoader + Kronos 集成测试
"""
import sys
import os
import asyncio

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    prefix = "[OK]" if ok else "[FAIL]"
    print(f"{prefix} {msg}")


def test_archon_import():
    """测试 Archon 导入"""
    print("\n" + "=" * 50)
    print("Archon Import Test")
    print("=" * 50)
    try:
        from business.archon import (
            ArchonAgent,
            ArchonCore,
            PermissionLevel,
            WorkspaceBounds,
            get_archon
        )
        log("Archon module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_opendataloader_import():
    """测试 OpenDataLoader 导入"""
    print("\n" + "=" * 50)
    print("OpenDataLoader Import Test")
    print("=" * 50)
    try:
        from business.opendataloader import (
            OpenDataLoader,
            ParsedDocument,
            PDFPage,
            ParseMode,
            get_opendataloader
        )
        log("OpenDataLoader module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_kronos_import():
    """测试 Kronos 导入"""
    print("\n" + "=" * 50)
    print("Kronos Import Test")
    print("=" * 50)
    try:
        from business.kronos import (
            KronosAnalyzer,
            KronosRouter,
            FinancialMetrics,
            RiskAssessment,
            RiskLevel,
            get_kronos_analyzer
        )
        log("Kronos module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


async def test_archon_execution():
    """测试 Archon 执行"""
    print("\n" + "=" * 50)
    print("Archon Execution Test")
    print("=" * 50)

    from business.archon import get_archon, PermissionLevel

    archon = get_archon()

    # 设置权限
    archon.core.set_permission("dir_list", PermissionLevel.READ)
    archon.core.set_permission("file_read", PermissionLevel.READ)

    # 测试列出目录
    result = await archon.core.execute("dir_list", {"path": "."})
    log(f"List directory: {result.get('success')}")
    if result.get("success"):
        print(f"  Found {len(result.get('items', []))} items")

    return True


async def test_opendataloader_parse():
    """测试 OpenDataLoader 解析"""
    print("\n" + "=" * 50)
    print("OpenDataLoader Parse Test")
    print("=" * 50)

    from business.opendataloader import get_opendataloader, ParseMode

    loader = get_opendataloader()

    # 模拟解析
    doc = await loader.parse("test.pdf", mode=ParseMode.MARKDOWN)
    log(f"Parsed document: {doc.title}")
    print(f"  Pages: {len(doc.pages)}")
    print(f"  Tables: {len(doc.pages[0].tables) if doc.pages else 0}")

    # 测试发票提取
    invoice = await loader.extract_invoice_data("invoice.pdf")
    log(f"Invoice extraction: {invoice.get('confidence', 0) * 100:.0f}% confidence")

    return True


async def test_kronos_analysis():
    """测试 Kronos 分析"""
    print("\n" + "=" * 50)
    print("Kronos Analysis Test")
    print("=" * 50)

    from business.kronos import (
        get_kronos_analyzer,
        FinancialMetrics,
        RiskLevel
    )

    kronos = get_kronos_analyzer()

    # 创建测试财务数据
    metrics = FinancialMetrics(
        revenue=1000000,
        net_profit=150000,
        gross_margin=0.35,
        debt_ratio=0.55,
        current_ratio=1.8,
        roe=0.12
    )

    # 分析健康度
    health = await kronos.analyze_financial_health(metrics)
    log(f"Financial health score: {health.score}/100")
    print(f"  Risk level: {health.level.value}")

    # 现金流分析
    cash_flow = await kronos.analyze_cash_flow(
        operating=200000,
        investing=-50000,
        financing=-30000
    )
    log(f"Cash flow health: {cash_flow.health_score}/100")

    # 信用评估
    credit = await kronos.credit_assessment(metrics, cash_flow)
    print(f"  Credit tier: {credit['tier']}")
    print(f"  Suggested limit: {credit['suggested_limit']:,.0f}")
    log(f"Approval recommended: {credit['approval_recommended']}")

    return True


async def run_async_tests():
    """运行异步测试"""
    await test_archon_execution()
    await test_opendataloader_parse()
    await test_kronos_analysis()


if __name__ == "__main__":
    results = []

    results.append(("Archon Import", test_archon_import()))
    results.append(("OpenDataLoader Import", test_opendataloader_import()))
    results.append(("Kronos Import", test_kronos_import()))

    asyncio.run(run_async_tests())

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "OK" if ok else "X"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} passed")
    if passed == total:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed")
