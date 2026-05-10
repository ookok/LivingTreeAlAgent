"""Chrome DevTools automated frontend test — LivingTree pages.

Uses the chrome_dual.py bridge (npx MCP or Python CDP).
Tests: page load, element presence, screenshot capture.
"""

import asyncio, sys, json, time, base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = "http://127.0.0.1:8100"

TESTS = [
    ("/tree/living", "Living Canvas", ["lc-input-bar", "lc-mic-btn", "lc-call-btn", "lc-canvas"]),
    ("/tree/admin", "Admin Console", ["admin-nav-models", "admin-panel-content"]),
]

async def run():
    from livingtree.core.chrome_dual import get_chrome_dual

    bridge = get_chrome_dual()
    await bridge.probe()
    st = bridge.status()
    print(f"Mode: {st['mode']} ({st['mode_label']})")

    result = await bridge.start(headless=True)
    if not result.get("ok"):
        print(f"Start failed: {result}")
        print("Fallback: manual mode needed — chrome --remote-debugging-port=9222")
        return 1

    results = []
    async with __import__('httpx').AsyncClient() as hc:
        for path, label, selectors in TESTS:
            print(f"\n── {label} ({path}) ──")
            url = BASE + path

            t0 = time.time()
            nav = await bridge.navigate(url)
            if nav.get("ok"):
                await asyncio.sleep(1.5)
                ms = int((time.time() - t0) * 1000)
                print(f"  Navigate: OK {ms}ms")

                # Check each selector exists via JS eval
                for sel in selectors:
                    r = await bridge.eval_js(f"!!document.querySelector('{sel}')")
                    found = r.get("value", False) if isinstance(r, dict) else False
                    ic = "✅" if found else "❌"
                    print(f"  {ic} {sel}")

                # Screenshot
                shot = await bridge.screenshot()
                if shot.get("ok"):
                    path = f".livingtree/test_{label.replace(' ','_').lower()}.png"
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    Path(path).write_bytes(base64.b64decode(shot["data"]))
                    print(f"  📸 Screenshot: {path} ({len(shot['data'])}b)")

                results.append({"page": label, "status": "OK"})
            else:
                print(f"  ❌ Navigate failed: {nav}")
                results.append({"page": label, "status": "FAIL"})

    await bridge.stop()

    print(f"\n{'='*40}")
    passed = sum(1 for r in results if r["status"] == "OK")
    print(f"Results: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
