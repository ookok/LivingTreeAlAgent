"""
批量删除 core/ 中已有新实现的文件
"""
import os
import json

core_dir = "core"
business_dir = "client/src/business"

# 获取 core/ 根目录的所有 .py 文件（排除 __init__.py）
core_files = [f for f in os.listdir(core_dir) if f.endswith('.py') and f != '__init__.py']

deleted_files = []
kept_files = []

for f in core_files:
    name = f[:-3]  # 去掉 .py
    new_path = os.path.join(business_dir, f)
    
    if os.path.exists(new_path):
        # 有新实现，删除旧文件
        old_path = os.path.join(core_dir, f)
        try:
            os.remove(old_path)
            deleted_files.append(f)
            print(f"[OK] Deleted: core/{f}")
        except Exception as e:
            print(f"[ERROR] Failed to delete core/{f}: {e}")
    else:
        # 没有新实现，保留
        kept_files.append(f)
        print(f"[SKIP] Keep: core/{f} (no equivalent in client/src/business/)")

# 输出总结
print("\n" + "="*60)
print(f"Total core/ files: {len(core_files)}")
print(f"Deleted: {len(deleted_files)}")
print(f"Kept: {len(kept_files)}")
print("="*60)

if deleted_files:
    print("\nDeleted files:")
    for f in deleted_files:
        print(f"  - core/{f}")

if kept_files:
    print("\nKept files (no equivalent in client/src/business/):")
    for f in kept_files:
        print(f"  - core/{f}")
