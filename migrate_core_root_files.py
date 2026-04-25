#!/usr/bin/env python3
"""
批量迁移 core/ 根目录中的独立 Python 文件到 client/src/business/
"""
import os
import re
import shutil
from pathlib import Path

# 工作目录
WORKSPACE = Path("f:/mhzyapp/LivingTreeAlAgent")
CORE_DIR = WORKSPACE / "core"
TARGET_DIR = WORKSPACE / "client/src/business"

# 需要跳过的文件（特殊文件）
SKIP_FILES = {"__init__.py", "__pycache__"}

def get_python_files(directory):
    """获取目录中的所有 Python 文件"""
    py_files = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix == ".py" and f.name not in SKIP_FILES:
            py_files.append(f.name)
    return sorted(py_files)

def find_external_imports(filename):
    """查找项目中哪些文件导入了指定的 core 模块"""
    module_name = filename.replace(".py", "")
    pattern1 = f"from core.{module_name} import"
    pattern2 = f"import core.{module_name}"

    results = []
    for root, dirs, files in os.walk(WORKSPACE):
        # 跳过 .git 和 __pycache__
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]

        for file in files:
            if file.endswith(".py"):
                filepath = Path(root) / file
                # 跳过文件自身
                if filepath == CORE_DIR / filename:
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if re.search(pattern1, content) or re.search(pattern2, content):
                            results.append(filepath)
                except Exception as e:
                    pass

    return results

def update_imports_in_file(filepath, filename):
    """更新单个文件中的导入语句"""
    module_name = filename.replace(".py", "")
    old_pattern1 = f"from core.{module_name} import"
    old_pattern2 = f"import core.{module_name}"

    new_replacement1 = f"from client.src.business.{module_name} import"
    new_replacement2 = f"import client.src.business.{module_name}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换导入语句
        content = re.sub(old_pattern1, new_replacement1, content)
        content = re.sub(old_pattern2, new_replacement2, content)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to update {filepath}: {e}")
        return False

def migrate_file(filename):
    """迁移单个文件"""
    print(f"\n[INFO] Processing: {filename}")

    # 1. 查找外部引用
    external_files = find_external_imports(filename)
    print(f"[INFO] Found {len(external_files)} external references")

    # 2. 更新外部引用
    for ext_file in external_files:
        if update_imports_in_file(ext_file, filename):
            print(f"  [OK] Updated: {ext_file}")
        else:
            print(f"  [ERROR] Failed to update: {ext_file}")
            return False

    # 3. 复制文件到目标目录
    src_file = CORE_DIR / filename
    dst_file = TARGET_DIR / filename

    try:
        shutil.copy2(src_file, dst_file)
        print(f"  [OK] Copied to: {dst_file}")
    except Exception as e:
        print(f"  [ERROR] Failed to copy: {e}")
        return False

    # 4. 删除原文件
    try:
        os.remove(src_file)
        print(f"  [OK] Deleted original: {src_file}")
    except Exception as e:
        print(f"  [ERROR] Failed to delete: {e}")
        return False

    return True

def main():
    print("=" * 60)
    print("Batch Migrating core/ Root Files to client/src/business/")
    print("=" * 60)

    # 获取所有 Python 文件
    py_files = get_python_files(CORE_DIR)
    print(f"\n[INFO] Found {len(py_files)} Python files to migrate")

    success_count = 0
    failed_files = []

    for filename in py_files:
        if migrate_file(filename):
            success_count += 1
        else:
            failed_files.append(filename)

    print("\n" + "=" * 60)
    print(f"[SUMMARY] Migration Complete")
    print(f"  Success: {success_count}/{len(py_files)}")
    if failed_files:
        print(f"  Failed: {len(failed_files)}")
        for f in failed_files:
            print(f"    - {f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
