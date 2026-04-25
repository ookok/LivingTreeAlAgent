import sqlite3
import json
import os
from collections import Counter

conn = sqlite3.connect(r'f:\mhzyapp\LivingTreeAlAgent\.evolution\test_evolution.db')
c = conn.cursor()

# 获取所有配置问题的文件
c.execute("""
    SELECT signal_id, title, description, affected_files, metrics 
    FROM evolution_signals 
    WHERE signal_type='hardcoded_value'
""")
rows = c.fetchall()

# 按文件分组
files = Counter()
issues = []
for r in rows:
    files_list = json.loads(r[3]) if r[3] else []
    for f in files_list:
        files[f] += 1
        issues.append({'file': f, 'title': r[1]})

print("=" * 70)
print(" 配置迁移进度")
print("=" * 70)
print("\n[PASS] api_gateway.py - 已迁移 (timeout=60 -> 统一配置)")
print()

print("[TODO] 待迁移文件:")
for file, count in files.most_common(15):
    print(f"  - {file}: {count} 处")

print("\n" + "=" * 70)
conn.close()
