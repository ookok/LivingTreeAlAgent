import urllib.request, json, time

MODEL = "big-pickle"
BASE = "http://localhost:4096"
QUESTION = "hello"

print(f"Model: {MODEL}")

# Create session
body = json.dumps({"providerID": "opencode", "modelID": MODEL}).encode()
r = urllib.request.urlopen(urllib.request.Request(f"{BASE}/session",
    data=body, headers={"Content-Type":"application/json"}, method="POST"), timeout=10)
sid = json.loads(r.read())["id"]
print(f"Session: {sid}")

# Send prompt
body = json.dumps({"parts": [{"type":"text","text":QUESTION}]}).encode()
urllib.request.urlopen(urllib.request.Request(f"{BASE}/session/{sid}/prompt",
    data=body, headers={"Content-Type":"application/json"}, method="POST"), timeout=10)
print("Prompt sent")

# Try messages endpoint with different formats
for i in range(15):
    try:
        r = urllib.request.urlopen(f"{BASE}/session/{sid}/messages", timeout=5)
        raw = r.read()
        ct = r.headers.get("content-type","")
        print(f"  t+{i}s: status={r.status} ct={ct[:30]} len={len(raw)}")
        if raw and ct and "json" in ct:
            msgs = json.loads(raw)
            if isinstance(msgs, list):
                for msg in reversed(msgs[-3:]):
                    role = msg.get("info",{}).get("role","?")
                    text = "".join(p.get("text","") for p in msg.get("parts",[]) if p.get("type")=="text")
                    print(f"    {role}: {text[:100]}")
    except Exception as e:
        print(f"  t+{i}s: {e}")
    time.sleep(2)
