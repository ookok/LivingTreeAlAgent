"""Inspect OpenCode provider model metadata — how is 'free' marked?"""
import urllib.request, json

r = urllib.request.urlopen('http://localhost:4096/config/providers', timeout=5)
data = json.loads(r.read())

for p in data.get('providers', []):
    if p.get('id') != 'opencode': continue
    print(f"Provider: {p.get('id')}")
    for mid, mdata in p.get('models', {}).items():
        print(f"\n  Model: {mid}")
        print(f"  Metadata: {json.dumps(mdata, indent=4, ensure_ascii=False)}")
