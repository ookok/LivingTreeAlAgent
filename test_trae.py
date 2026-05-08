import urllib.request, json

key = '5b66b2c6-ef09-4d50-bb62-fd8f8293ab4a'

# Get all active models first
r = urllib.request.urlopen(urllib.request.Request(
    'https://ark.cn-beijing.volces.com/api/v3/models',
    headers={'Authorization': f'Bearer {key}'}
), timeout=10)
models = data = json.loads(r.read()).get('data', [])
# Filter to text models (skip embedding, vision, image, video)
text_models = [m for m in models if m.get('status') != 'Shutdown' and 
    'embedding' not in m.get('id','') and 'vision' not in m.get('id','') and
    'seedance' not in m.get('id','') and 'seedream' not in m.get('id','')]

print(f"Text models: {len(text_models)}")
for m in text_models:
    mid = m.get('id')
    body = json.dumps({
        'model': mid,
        'messages': [{'role': 'user', 'content': 'say hi'}],
        'max_tokens': 10
    }).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            data=body,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        ), timeout=10)
        data = json.loads(r.read())
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '?')
        print(f'  {mid}: ✅ {content}')
    except Exception as e:
        err = str(e)[:60]
        print(f'  {mid}: {err}')
