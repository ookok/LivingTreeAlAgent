import urllib.request, json, uuid

TOKEN = '6b3suL7Ek4bYjNEQkCtb6ofXZLuJAqcRn7OSe/DsbqqY2VgVF5wsH+jRzukazuXU'

# Try with token in cookie instead of Authorization
body = json.dumps({
    'messages': [{'role': 'user', 'content': '一句话介绍你自己'}],
    'model': 'deepseek-chat',
    'stream': False,
}).encode()

r = urllib.request.urlopen(urllib.request.Request(
    'https://chat.deepseek.com/api/v0/chat/completion',
    data=body,
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Origin': 'https://chat.deepseek.com',
        'Referer': 'https://chat.deepseek.com/',
        'Cookie': f'userToken={TOKEN}',
        'X-Device-Id': str(uuid.uuid4()),
    }
), timeout=30)

data = json.loads(r.read())
print(f'Status: {r.status}')
print(json.dumps(data, indent=2, ensure_ascii=False)[:800])
