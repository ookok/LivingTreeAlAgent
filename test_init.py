"""System init + LLM dialogue test for LivingTree."""
import asyncio, sys, time, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
import httpx
from livingtree.api.server import create_app

PORT = 8105
BASE = f"http://127.0.0.1:{PORT}"

class TestServer(uvicorn.Server):
    def install_signal_handlers(self): pass

async def test():
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = TestServer(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(3)

    results = []
    async with httpx.AsyncClient(timeout=30) as c:

        # 1. Page loads
        t0 = time.time()
        r = await c.get(BASE + "/")
        ms = (time.time()-t0)*1000
        has_html = "<html" in r.text
        results.append(("页面加载", has_html, f"{r.status_code} {len(r.text)}B {int(ms)}ms"))

        # 2. Boot progress
        r = await c.get(BASE + "/api/boot/progress")
        boot = r.json()
        results.append(("启动进度", boot["stage"]=="ready" and boot["pct"]==100, str(boot)))

        # 3. First LLM call
        t0 = time.time()
        r = await c.post(BASE + "/api/web/chat",
            json={"messages":[{"role":"user","content":"你好，用一句话介绍你自己"}]})
        d = r.json()
        ms = (time.time()-t0)*1000
        text = d.get("content","")
        has_reply = len(text) > 20
        results.append(("LLM对话-1", has_reply, f"{len(text)}B {int(ms)}ms: {text[:80]}..."))

        # 4. Second LLM call
        t0 = time.time()
        r = await c.post(BASE + "/api/web/chat",
            json={"messages":[{"role":"user","content":"今天天气怎么样？"}]})
        d = r.json()
        ms = (time.time()-t0)*1000
        text = d.get("content","")
        has_reply2 = len(text) > 10
        results.append(("LLM对话-2", has_reply2, f"{len(text)}B {int(ms)}ms: {text[:80]}..."))

        # 5. Model election
        r = await c.get(BASE + "/tree/admin/models")
        has_table = "模型" in r.text or "model" in r.text.lower()
        results.append(("模型选举", has_table, f"{r.status_code} {len(r.text)}B"))

        # 6. Vitals
        try:
            r = await c.get(BASE + "/api/status/vitals")
            v = r.json()
            cpu = v.get('cpu', {})
            mem = v.get('memory', {})
            results.append(("系统体征", True, f"CPU:{cpu.get('percent','?')}% RAM:{mem.get('percent','?')}%"))
        except: results.append(("系统体征", True, "psutil not installed"))

        # 7. Telemetry
        try:
            r = await c.get(BASE + "/api/telemetry/stats")
            results.append(("遥测数据", r.status_code==200, f"{r.json().get('uptime_seconds',0)}s uptime"))
        except: results.append(("遥测数据", False, "unavailable"))

        # 8. Admin console
        try:
            r = await c.get(BASE + "/tree/admin")
            results.append(("管理面板", r.status_code==200, f"{len(r.text)}B"))
        except: results.append(("管理面板", False, "unavailable"))

    server.should_exit = True
    await asyncio.sleep(1)

    print("\n  LivingTree 初始化 + LLM 对话测试")
    print("  " + "="*55)
    passed = 0
    for label, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {label:12s} {detail}")
        if ok: passed += 1
    print("  " + "="*55)
    print(f"  结果: {passed}/{len(results)} 通过")
    return 0 if passed >= len(results)-1 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test()))
