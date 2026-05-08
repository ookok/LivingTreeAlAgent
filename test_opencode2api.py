import urllib.request, json

try:
    r = urllib.request.urlopen('http://localhost:10000/v1/models', timeout=5)
    data = json.loads(r.read())
    models = data.get('data', data) if isinstance(data, dict) else data
    if isinstance(models, list):
        print(f"OpenCode2API models: {len(models)}")
        for m in models[:15]:
            print(f"  {m.get('id', '?')}")
    else:
        print(f"Response type: {type(models)}")
        print(json.dumps(models, indent=2)[:500])
except Exception as e:
    print(f"OpenCode2API not running: {e}")
    print("Run: npx opencode2api or docker compose up -d")
