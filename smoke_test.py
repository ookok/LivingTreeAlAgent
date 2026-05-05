"""Smoke test: verify client + relay can start without crashing."""
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).parent


def test_import_client():
    """Verify all client modules import without error."""
    print("[1/4] Client import...")
    start = time.monotonic()
    from livingtree.tui.app import LivingTreeTuiApp
    from livingtree.integration.hub import IntegrationHub
    elapsed = time.monotonic() - start
    print(f"  ✅ Client imports OK ({elapsed:.1f}s)")
    return True


def test_import_relay():
    """Verify relay server imports without error."""
    print("[2/4] Relay import...")
    start = time.monotonic()
    from relay_server import P2PRelayServer, _hash_password, _ensure_accounts
    elapsed = time.monotonic() - start
    print(f"  ✅ Relay imports OK ({elapsed:.1f}s)")
    return True


def test_relay_start_stop():
    """Verify relay server initializes correctly."""
    print("[3/4] Relay init...")
    from relay_server import P2PRelayServer, _hash_password, _ensure_accounts, ACCOUNT_STORE
    server = P2PRelayServer(port=0)
    app = server._app

    route_count = len(list(app.router.routes()))
    assert route_count >= 20, f"Expected >=20 routes, got {route_count}"
    assert "admin" in ACCOUNT_STORE
    assert _hash_password("x") == _hash_password("x")
    print(f"  ✅ Relay OK ({route_count} routes, {len(ACCOUNT_STORE)} accounts)")
    return True


def test_tool_imports():
    """Verify key tool modules import."""
    print("[4/4] Tool imports...")
    modules = [
        "livingtree.capability.document_editor",
        "livingtree.capability.tool_executor",
        "livingtree.capability.universal_parser",
        "livingtree.capability.data_lineage",
        "livingtree.observability.trust_scoring",
        "livingtree.treellm.session_binding",
        "livingtree.capability.self_modifier",
        "livingtree.capability.tool_synthesis",
        "livingtree.capability.remote_assist",
        "livingtree.network.proxy_fetcher",
        "livingtree.network.service_discovery",
        "livingtree.capability.network_brain",
        "livingtree.capability.conversation_branch",
        "livingtree.capability.semantic_diff",
        "livingtree.capability.self_documentation",
        "livingtree.observability.error_replay",
        "livingtree.capability.agent_marketplace",
        "livingtree.capability.idle_consolidator",
        "livingtree.capability.session_continuity",
        "livingtree.capability.template_engine",
        "livingtree.capability.content_dedup",
        "livingtree.capability.patch_manager",
        "livingtree.capability.semantic_backup",
        "livingtree.capability.file_watcher",
        "livingtree.network.external_access",
        "livingtree.tui.layout_engine",
    ]
    failed = []
    for mod_name in modules:
        try:
            __import__(mod_name)
        except Exception as e:
            failed.append(f"{mod_name}: {e}")

    if failed:
        print(f"  ❌ {len(failed)} modules failed:")
        for f in failed:
            print(f"     {f}")
        return False
    print(f"  ✅ {len(modules)} modules OK")
    return True


def main():
    print("=" * 60)
    print("  LivingTree Smoke Test")
    print("=" * 60)
    print(f"  Python: {sys.version}")
    print(f"  Project: {PROJECT}")
    print()

    results = [
        ("Client import", test_import_client()),
        ("Relay import", test_import_relay()),
        ("Relay start/stop", test_relay_start_stop()),
        ("Tool imports", test_tool_imports()),
    ]

    print()
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
    print(f"  {passed}/{total} passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
