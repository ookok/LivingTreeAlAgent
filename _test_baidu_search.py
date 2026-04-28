import urllib.request
import urllib.parse
import re

query = '吉奥环朋'
encoded = urllib.parse.quote(query)
url = f'https://www.baidu.com/s?wd={encoded}&rn=5'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cookie': 'BD_UPN=12314753; BAIDUID=xxx',  # 简化 cookie
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        print(f'获取到 {len(content)} bytes')
        
        # 保存原始内容以便分析
        with open('_baidu_response.html', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 尝试多种模式解析
        patterns = [
            (r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', 'h3+t模式'),
            (r'<div[^>]*class="[^"]*result[^"]*"[^>]*>.*?<h3[^>]*>.*?<a[^>]*>([^<]+)</a>', 'result+h3模式'),
            (r'class="t[^"]*"[^>]*>.*?<em>([^<]+)</em>', 'em模式'),
        ]
        
        for pattern, name in patterns:
            titles = re.findall(pattern, content, re.DOTALL)
            if titles:
                print(f'\n{name}: 找到 {len(titles)} 个标题')
                for i, t in enumerate(titles[:5]):
                    clean_t = re.sub(r'<[^>]+>', '', t).strip()
                    print(f'  {i+1}. {clean_t}')
                    
except Exception as e:
    print(f'错误: {e}')
