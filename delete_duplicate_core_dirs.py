"""
批量删除 core/ 中和 client/src/business/ 重叠的子目录
"""
import os
import shutil

core_dir = "core"
business_dir = "client/src/business"

# 获取 core/ 的所有子目录
core_subdirs = [d for d in os.listdir(core_dir) 
              if os.path.isdir(os.path.join(core_dir, d)) and d != '__pycache__']

deleted_dirs = []
kept_dirs = []

for d in core_subdirs:
    business_path = os.path.join(business_dir, d)
    
    if os.path.exists(business_path):
        # 在 client/src/business/ 有对应目录，删除 core/ 中的旧版本
        core_path = os.path.join(core_dir, d)
        try:
            shutil.rmtree(core_path)
            deleted_dirs.append(d)
            print(f"[OK] Deleted directory: core/{d}")
        except Exception as e:
            print(f"[ERROR] Failed to delete core/{d}: {e}")
    else:
        # 在 client/src/business/ 没有对应目录，保留
        kept_dirs.append(d)
        print(f"[SKIP] Keep: core/{d} (no equivalent in client/src/business/)")

# 输出总结
print("\n" + "="*60)
print(f"Total core/ subdirectories: {len(core_subdirs)}")
print(f"Deleted: {len(deleted_dirs)}")
print(f"Kept: {len(kept_dirs)}")
print("="*60)

if deleted_dirs:
    print("\nDeleted directories:")
    for d in deleted_dirs:
        print(f"  - core/{d}")

if kept_dirs:
    print("\nKept directories (no equivalent in client/src/business/):")
    for d in kept_dirs:
        print(f"  - core/{d}")
