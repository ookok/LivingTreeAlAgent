#!/usr/bin/env python3
"""
批量修复导入路径：core.xxx → client.src.business.xxx
 Usage: python fix_imports_v2.py [--dry-run]
"""

import os
import re
import argparse
from pathlib import Path

# 定义需要修复的模块映射
MODULE_MAPPINGS = {
    'core.task_decomposer': 'client.src.business.task_decomposer',
    'core.agent': 'client.src.business.agent',
    'core.system_brain': 'client.src.business.system_brain',
    'core.evolution_engine': 'client.src.business.evolution_engine',
}

def fix_imports_in_file(file_path, dry_run=False):
    """修复单个文件中的导入路径"""
    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 替换所有映射
        for old_module, new_module in MODULE_MAPPINGS.items():
            # 替换 "from old_module import"
            content = re.sub(
                rf'from\s+{re.escape(old_module)}\s+import',
                f'from {new_module} import',
                content
            )
            # 替换 "import old_module"
            content = re.sub(
                rf'^import\s+{re.escape(old_module)}\s*$',
                f'import {new_module}',
                content,
                flags=re.MULTILINE
            )
        
        # 检查是否有修改
        if content != original_content:
            if not dry_run:
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True, "Fixed"
            else:
                return True, "Would fix (dry-run)"
        else:
            return False, "No match"
    
    except Exception as e:
        return False, str(e)

def main():
    """主函数"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='试运行（不实际修改文件）')
    args = parser.parse_args()
    
    root_dir = Path('.')
    fixed_files = []
    error_files = []
    
    print(f"[INFO] {'试运行模式（不实际修改文件）' if args.dry_run else '正式修复模式'}")
    print("="*60)
    
    # 扫描所有 Python 文件
    for py_file in root_dir.rglob('*.py'):
        # 跳过备份文件和脚本自身
        if py_file.name in ['fix_imports.py', 'fix_imports_v2.py', 'auto_fix_imports.py']:
            continue
        if 'backup' in str(py_file).lower() or 'core_backup' in str(py_file):
            continue
        
        try:
            fixed, msg = fix_imports_in_file(py_file, dry_run=args.dry_run)
            if fixed:
                fixed_files.append(str(py_file))
                print(f"[OK] {msg}: {py_file}")
        except Exception as e:
            print(f"[ERROR] Failed: {py_file} - {e}")
            error_files.append((str(py_file), str(e)))
    
    # 输出总结
    print("\n" + "="*60)
    print(f"[OK] 成功修复: {len(fixed_files)} 个文件")
    print(f"[ERROR] 失败: {len(error_files)} 个文件")
    print("="*60)
    
    if fixed_files:
        print("\n修复的文件（前 15 个）:")
        for f in fixed_files[:15]:
            print(f"  - {f}")
        if len(fixed_files) > 15:
            print(f"  ... 还有 {len(fixed_files) - 15} 个文件")
    
    if error_files:
        print("\n失败的文件:")
        for f, e in error_files[:5]:
            print(f"  - {f}: {e}")

if __name__ == '__main__':
    main()
