#!/usr/bin/env python3
"""迁移 core/error_memory 到 client/src/business/error_memory"""
import os
import shutil
import re

SRC_DIR = "core/error_memory"
DST_DIR = "client/src/business/error_memory"

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
        
        # 替换 from core.error_memory 为 from client.src.business.error_memory
        pattern = r'from\s+core\.error_memory\s+import'
        replacement = 'from client.src.business.error_memory import'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[OK] Updated internal imports: {filename}")
            updated_count += 1
        else:
            print(f"[SKIP] No internal imports to update: {filename}")
    
    return updated_count

def update_external_imports():
    """更新外部文件中的导入引用"""
    external_files = [
        "core/unified_memory.py",
        "core/self_evolving/test_self_evolving.py",
        "core/self_evolving/self_evolving_system.py",
        "core/self_evolving/agent_integration.py"
    ]
    
    updated_count = 0
    
    for filepath in external_files:
        if not os.path.exists(filepath):
            print(f"[SKIP] File not found: {filepath}")
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换 from core.error_memory 为 from client.src.business.error_memory
        pattern = r'from\s+core\.error_memory\s+import'
        replacement = 'from client.src.business.error_memory import'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[OK] Updated external imports: {filepath}")
            updated_count += 1
        else:
            print(f"[SKIP] No changes needed: {filepath}")
    
    return updated_count

if __name__ == "__main__":
    print("=" * 60)
    print("Migrating core/error_memory to client/src/business/")
    print("=" * 60)
    
    # Step 1: Copy directory
    if copy_directory():
        # Step 2: Update internal imports
        internal_count = update_internal_imports()
        print(f"\nInternal imports updated: {internal_count}")
        
        # Step 3: Update external imports
        external_count = update_external_imports()
        print(f"External imports updated: {external_count}")
        
        print("\n[OK] Migration prepared. Please review and delete old directory.")
    else:
        print("\n[ERROR] Copy failed or already exists.")
    
    print("\nDone!")
