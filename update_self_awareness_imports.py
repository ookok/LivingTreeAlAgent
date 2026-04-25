#!/usr/bin/env python3
"""更新 core.self_awareness 到 client.src.business.self_awareness 的导入引用"""
import os
import re

# 要更新的文件列表
files_to_update = [
    "tests/test_phase1_integration.py",
    "tests/test_phase1_complete.py"
]

def update_imports(filepath):
    """更新文件中的导入引用"""
    if not os.path.exists(filepath):
        print(f"[SKIP] File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换 from core.self_awareness import 为 from client.src.business.self_awareness import
    pattern = r'from\s+core\.self_awareness\s+import'
    replacement = 'from client.src.business.self_awareness import'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        print(f"[OK] No changes needed: {filepath}")
        return False
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"[OK] Updated: {filepath}")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Updating core.self_awareness imports")
    print("=" * 60)
    
    updated_count = 0
    for filepath in files_to_update:
        if update_imports(filepath):
            updated_count += 1
    
    print("=" * 60)
    print(f"Total files updated: {updated_count}")
    print("Done!")
