import sqlite3
import json
conn = sqlite3.connect(r'f:\mhzyapp\LivingTreeAlAgent\.evolution\test_evolution.db')
c = conn.cursor()
c.execute("SELECT signal_id, title, description, affected_files, metrics FROM evolution_signals WHERE signal_type='hardcoded_value' LIMIT 25")
rows = c.fetchall()
print("=" * 70)
print(" 统一配置迁移 - 待修复清单")
print("=" * 70)
for r in rows:
    print(f"\n[{r[0]}] {r[1]}")
    print(f"  File: {r[3]}")
    m = json.loads(r[4]) if r[4] else {}
    print(f"  Type: {m.get('type', 'N/A')}")
conn.close()
