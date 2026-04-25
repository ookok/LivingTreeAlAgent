#!/usr/bin/env python3
"""迁移 core/world_model_simulator 到 client/src/business/world_model_simulator"""
import os
import shutil
import re

SRC_DIR = "core/world_model_simulator"
DST_DIR = "client/src/business/world_model_simulator"

def copy_directory():
    """复制目录到新位置"""
    if os.path.exists(DST_DIR):
        print(f"[SKIP] Destination already exists: {DST_DIR}")
        return False
    
    os.makedirs(os.path.dirname(DST_DIR), exist_ok=True)
    shutil.copytree(SRC_DIR, DST_DIR)
    print(f"[OK] Copied: {SRC_DIR} -> {DST_DIR}")
    return True

def update_internal_imports():
    """更新目标目录中的内部导入"""
    updated_count = 0
    
    for filename in os.listdir(DST_DIR):
        filepath = os.path.join(DST_DIR, filename)
        if not filename.endswith('.py'):
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换 from core.world_model_simulator 为 from client.src.business.world_model_simulator
        pattern = r'from\s+core\.world_model_simulator\s+import'
        replacement = 'from client.src.business.world_model_simulator import'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[OK] Updated internal imports: {filename}")
            updated_count += 1
        else:
            print(f"[SKIP] No internal imports to update: {filename}")
    
    return updated_count

if __name__ == "__main__":
    print("=" * 60)
    print("Migrating core/world_model_simulator to client/src/business/")
    print("=" * 60)
    
    # Step 1: Copy directory
    if copy_directory():
        # Step 2: Update internal imports
        internal_count = update_internal_imports()
        print(f"\nInternal imports updated: {internal_count}")
        
        print("\n[OK] Migration prepared. Please review and delete old directory.")
    else:
        print("\n[ERROR] Copy failed or already exists.")
    
    print("\nDone!")
