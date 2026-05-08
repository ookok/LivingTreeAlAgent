import urllib.request, json, time

MODELS = ["big-pickle", "minimax-m2.5-free", "hy3-preview-free", "nemotron-3-super-free"]
BASE = "http://localhost:4096"

for model in MODELS:
    print(f"\n--- {model} ---")
    try:
        body = json.dumps({"providerID": "opencode", "modelID": model}).encode()
        r = urllib.request.urlopen(urllib.request.Request(f"{BASE}/session",
            data=body, headers={"Content-Type":"application/json"}, method="POST"), timeout=10)
        sid = json.loads(r.read())["id"]

        body = json.dumps({"parts": [{"type":"text","text":"一句话介绍你自己"}]}).encode()
        urllib.request.urlopen(urllib.request.Request(f"{BASE}/session/{sid}/message",
            data=body, headers={"Content-Type":"application/json"}, method="POST"), timeout=10)

        for _ in range(30):
            r = urllib.request.urlopen(f"{BASE}/session/{sid}/message", timeout=10)
            msgs = json.loads(r.read())
            if isinstance(msgs, dict): msgs = msgs.get("data", [])
            for msg in reversed(msgs if isinstance(msgs, list) else []):
                info = msg.get("info", {})
                if info.get("role") != "assistant": continue
                text = "".join(p.get("text","") for p in msg.get("parts",[]) if p.get("type")=="text")
                if text and info.get("finish"):
                    print(f"  Response: {text[:200]}")
                    break
            else:
                time.sleep(1)
                continue
            break
    except Exception as e:
        print(f"  Error: {e}")
