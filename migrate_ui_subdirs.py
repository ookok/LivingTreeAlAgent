#!/usr/bin/env python3
"""
迁移 ui/ 中的子目录到 client/src/presentation/ 的适当位置
- components/ -> client/src/presentation/components/
- dialogs/ -> client/src/presentation/dialogs/
- widgets/ -> client/src/presentation/widgets/
- 其他面板包 -> client/src/presentation/panels/
- 其他子模块 -> client/src/presentation/{module}/
"""
import os
import re
import shutil
from pathlib import Path

# 工作目录
WORKSPACE = Path("f:/mhzyapp/LivingTreeAlAgent")
UI_DIR = WORKSPACE / "ui"
PRESENTATION_DIR = WORKSPACE / "client/src/presentation"

# 映射规则：ui/ 子目录 -> client/src/presentation/ 目标目录
MAPPING = {
    "components": "components",
    "dialogs": "dialogs",
    "widgets": "widgets",
    "modules": "modules",
}

def get_subdirs(directory):
    """获取目录中的所有子目录"""
    return [d for d in directory.iterdir() if d.is_dir() and d.name not in {"__pycache__"}]

def find_external_imports(module_name):
    """查找项目中哪些文件导入了指定的 ui 模块"""
    pattern1 = f"from ui.{module_name} import"
    pattern2 = f"import ui.{module_name}"
    pattern3 = f"from ui import {module_name}"

    results = []
    for root, dirs, files in os.walk(WORKSPACE):
        # 跳过 .git 和 __pycache__
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "ui"}]

        for file in files:
            if file.endswith(".py"):
                filepath = Path(root) / file
                # 跳过 ui 目录中的文件
                if filepath.is_relative_to(UI_DIR):
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if (re.search(pattern1, content) or
                            re.search(pattern2, content) or
                            re.search(pattern3, content)):
                            results.append(filepath)
                except Exception as e:
                    pass

    return results

def update_imports_in_file(filepath, old_module, new_module):
    """更新单个文件中的导入语句"""
    old_pattern1 = f"from ui.{old_module} import"
    old_pattern2 = f"import ui.{old_module}"
    old_pattern3 = f"from ui import {old_module}"

    new_replacement1 = f"from client.src.presentation.{new_module} import"
    new_replacement2 = f"import client.src.presentation.{new_module}"
    new_replacement3 = f"from client.src.presentation import {new_module.split('.')[-1]}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换导入语句
        content = re.sub(old_pattern1, new_replacement1, content)
        content = re.sub(old_pattern2, new_replacement2, content)
        content = re.sub(old_pattern3, new_replacement3, content)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to update {filepath}: {e}")
        return False

def migrate_subdir(subdir_path):
    """迁移单个子目录"""
    subdir_name = subdir_path.name
    print(f"\n[INFO] Processing: {subdir_name}/")

    # 确定目标目录
    if subdir_name in MAPPING:
        target_subdir = MAPPING[subdir_name]
    elif subdir_name.endswith("_panel"):
        target_subdir = f"panels/{subdir_name}"
    else:
        target_subdir = subdir_name

    target_path = PRESENTATION_DIR / target_subdir

    # 查找外部引用
    external_files = find_external_imports(subdir_name)
    print(f"[INFO] Found {len(external_files)} external references")

    # 更新外部引用
    for ext_file in external_files:
        if update_imports_in_file(ext_file, subdir_name, target_subdir):
            print(f"  [OK] Updated: {ext_file}")
        else:
            print(f"  [ERROR] Failed to update: {ext_file}")
            return False

    # 复制目录到目标位置
    try:
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(subdir_path, target_path)
        print(f"  [OK] Copied to: {target_path}")
    except Exception as e:
        print(f"  [ERROR] Failed to copy: {e}")
        return False

    # 删除原目录
    try:
        shutil.rmtree(subdir_path)
        print(f"  [OK] Deleted original: {subdir_path}")
    except Exception as e:
        print(f"  [ERROR] Failed to delete: {e}")
        return False

    return True

def main():
    print("=" * 60)
    print("Migrating ui/ Subdirectories to client/src/presentation/")
    print("=" * 60)

    # 获取所有子目录
    subdirs = get_subdirs(UI_DIR)
    print(f"\n[INFO] Found {len(subdirs)} subdirectories to migrate")

    success_count = 0
    failed_dirs = []

    for subdir_path in subdirs:
        if migrate_subdir(subdir_path):
            success_count += 1
        else:
            failed_dirs.append(subdir_path.name)

    print("\n" + "=" * 60)
    print(f"[SUMMARY] Migration Complete")
    print(f"  Success: {success_count}/{len(subdirs)}")
    if failed_dirs:
        print(f"  Failed: {len(failed_dirs)}")
        for d in failed_dirs:
            print(f"    - {d}")
    print("=" * 60)

if __name__ == "__main__":
    main()
