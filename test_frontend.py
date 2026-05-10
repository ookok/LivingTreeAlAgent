"""Frontend smoke tests — async server, automated page validation.

Usage: python test_frontend.py
"""

import asyncio, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
import httpx
from livingtree.api.server import create_app

PORT = 8102
BASE = f"http://127.0.0.1:{PORT}"

PAGES = [
    ("/", "Root redirect"),
    ("/tree/living", "Living Canvas"),
    ("/tree/admin", "Admin Console"),
    ("/tree/chat", "Chat panel"),
    ("/tree/dashboard", "Dashboard"),
    ("/tree/knowledge", "Knowledge"),
    ("/tree/chrome/panel", "Chrome panel"),
    ("/tree/sse", "SSE heartbeat"),
]

API = [
    ("GET", "/api/status/vitals", "Vitals"),
    ("GET", "/api/merge/status", "Merge status"),
    ("GET", "/api/shield/status", "Shield"),
    ("GET", "/api/telemetry/stats", "Telemetry"),
    ("GET", "/api/scheduler/status", "Scheduler"),
    ("GET", "/api/city/tools", "City MCP"),
    ("POST", "/api/video/search", "Video search"),
]

async def test_once(client, method, path, label):
    t0 = time.time()
    try:
        if method == "GET":
            r = await client.get(BASE + path, timeout=10)
        else:
            r = await client.post(BASE + path, json={"keyword": "test"}, timeout=10)
        ms = (time.time() - t0) * 1000
        ok = r.status_code in (200, 307)
        size = len(r.text or "")
        return ok, f"{'✅' if ok else '❌'} {label:20s} {r.status_code} {size:>5}B {int(ms):>4}ms", r.status_code
    except Exception as e:
        ms = (time.time() - t0) * 1000
        return False, f"❌ {label:20s} ERR  {str(e)[:50]:>50s} {int(ms):>4}ms", 0

class ServerRunner(uvicorn.Server):
    def install_signal_handlers(self): pass

async def main():
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = ServerRunner(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(1.5)

    results = []
    async with httpx.AsyncClient() as client:
        print(f"\n  PAGE TESTS ({len(PAGES)})")
        print("  " + "─" * 50)
        for path, label in PAGES:
            ok, msg, code = await test_once(client, "GET", path, label)
            print(f"  {msg}")
            results.append(("page", label, ok, code))

        print(f"\n  API TESTS ({len(API)})")
        print("  " + "─" * 50)
        for method, path, label in API:
            ok, msg, code = await test_once(client, method, path, label)
            print(f"  {msg}")
            results.append(("api", label, ok, code))

    server.should_exit = True
    await asyncio.sleep(0.5)

    passed = sum(1 for _, _, ok, _ in results if ok)
    failed = [(label, code) for _, label, ok, code in results if not ok]

    print(f"\n  RESULTS: {passed}/{len(results)} passed")
    if failed:
        print(f"  FAILED:")
        for label, code in failed:
            print(f"    {label}: HTTP {code}")

    if "/tree/living" in [l for _, l, ok, _ in results if not ok and l == "Living Canvas"]:
        print(f"\n  DIAGNOSIS: Living Canvas returned 500.")
        print(f"  This is a Jinja2 template cache issue in the file system.")
        print(f"  Check livingtree/templates/living.html for syntax or path issues.")
        print(f"  Try: Remove __pycache__, restart with fresh Python process.")

    return 0 if not failed else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
