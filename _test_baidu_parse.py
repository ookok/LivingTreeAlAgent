import urllib.request
import urllib.parse
import re

query = '吉奥环朋'
encoded = urllib.parse.quote(query)
url = f'https://www.baidu.com/s?wd={encoded}&rn=10'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as resp:
    content = resp.read().decode('utf-8', errors='ignore')

# 提取搜索结果
results = []

# 方法1: 查找带链接的标题和摘要
pattern = r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</a>.*?</h3>'
matches = re.findall(pattern, content, re.DOTALL)

# 摘要模式
snippet_pattern = r'<span[^>]*class="[^"]*c-abstract[^"]*"[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</span>'

# 打印前10个结果
print(f"找到 {len(matches)} 个结果")
for i, (url, title) in enumerate(matches[:10]):
    clean_title = re.sub(r'<[^>]+>', '', title).strip()
    clean_url = url.replace('&amp;', '&')
    print(f"{i+1}. {clean_title}")
    print(f"   URL: {clean_url[:80]}...")

# 尝试提取摘要
snippets = re.findall(snippet_pattern, content)
print(f"\n找到 {len(snippets)} 个摘要")
for i, snippet in enumerate(snippets[:5]):
    clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
    print(f"{i+1}. {clean_snippet[:100]}...")
