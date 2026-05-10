"""LivingTree SPA integration test — all frontend APIs in one shot."""
import asyncio, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn, httpx
from livingtree.api.server import create_app

PORT = 8111
BASE = f"http://127.0.0.1:{PORT}"

class Server(uvicorn.Server):
    def install_signal_handlers(self): pass

async def test():
    app = create_app()
    srv = Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error"))
    task = asyncio.create_task(srv.serve())
    await asyncio.sleep(3)

    ok, fail = 0, 0
    async with httpx.AsyncClient(timeout=30) as c:

        def check(label, cond, detail=""):
            nonlocal ok, fail
            if cond: ok += 1; print(f"  ✅ {label}")
            else: fail += 1; print(f"  ❌ {label}: {detail}")

        # 1. Page loads
        r = await c.get(BASE + "/")
        check("SPA首页", r.status_code==200 and len(r.text)>1000, f"{r.status_code} {len(r.text)}B")

        # 2. Boot API
        r = await c.get(BASE + "/api/boot/progress")
        d = r.json()
        check("启动进度", d.get("stage")=="ready", d.get("detail",""))

        # 3. Chat API — simulates SPA sending user message
        r = await c.post(BASE + "/api/web/chat",
            json={"messages":[{"role":"user","content":"你好"}]})
        d = r.json()
        content = d.get("content","")
        has_reply = len(content)>10 and content != "DeepSeek暂时不可用"
        check("LLM对话", has_reply, content[:80] if not has_reply else f"{len(content)} chars")

        # 4. Model election panel
        r = await c.get(BASE + "/tree/admin/models")
        check("模型选举面板", r.status_code==200 and len(r.text)>1000, f"{r.status_code} {len(r.text)}B")

        # 5. Vitals API (may fail without psutil)
        try:
            r = await c.get(BASE + "/api/status/vitals")
            check("系统体征", r.status_code==200, str(r.json().get("cpu",{}).get("percent","?"))+"%")
        except: check("系统体征", None, "psutil not installed")

        # 6. Shield status
        try:
            r = await c.get(BASE + "/api/shield/status")
            check("防护状态", r.status_code==200, str(r.json().get("hitl_pending","?")))
        except: check("防护状态", False)

        # 7. Video search
        r = await c.post(BASE + "/api/video/search", json={"keyword":"Python","limit":2})
        d = r.json()
        check("视频搜索(B站)", d.get("ok")==True, f"{d.get('total',0)} results")

        # 8. City data
        r = await c.post(BASE + "/api/city/call", json={"tool":"nanjing_traffic","params":{"district":"玄武区"}})
        d = r.json()
        check("城市数据", d.get("congestion_index",0)>0, d.get("status",""))

        # 9. File upload
        import base64
        b64 = base64.b64encode(b"# Test\nHello world").decode()
        r = await c.post(BASE + "/api/knowledge/ingest", json={"data":b64,"filename":"test.md","mime_type":"text/markdown"})
        check("文件伪上传", r.json().get("ok")==True, r.json().get("title",""))

        # 10. Theme CSS
        r = await c.get(BASE + "/tree/theme/dark")
        check("主题CSS", r.status_code==200 and len(r.text)>500, f"{len(r.text)}B")

        # 11. Admin console
        r = await c.get(BASE + "/tree/admin")
        check("管理控制台", r.status_code==200 and len(r.text)>500, f"{len(r.text)}B")

        # 12. Creative viz (any tab)
        try:
            r = await c.get(BASE + "/tree/creative/timeline")
            check("创意可视化", r.status_code==200)
        except: check("创意可视化", False)

    srv.should_exit = True
    await asyncio.sleep(1)

    print(f"\n  {'='*40}")
    print(f"  Results: {ok}/{ok+fail} passed")
    return 0 if fail==0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test()))
