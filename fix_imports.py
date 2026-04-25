#!/usr/bin/env python3
"""
批量修复导入路径：core.evolution_engine → client.src.business.evolution_engine
安全版本：保留原编码，只修改必要行
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path):
    """修复单个文件中的导入路径"""
    try:
        # 读取文件（保留原始编码）
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有需要替换的内容
        if 'from core.evolution_engine' in content or 'import core.evolution_engine' in content:
            # 替换导入路径
            new_content = content.replace(
                'from core.evolution_engine',
                'from client.src.business.evolution_engine'
            ).replace(
                'import core.evolution_engine',
                'import client.src.business.evolution_engine'
            )
            
            # 写回文件（保留 utf-8 编码）
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True, "Fixed"
        else:
            return False, "No match"
    
    except Exception as e:
        return False, str(e)

def main():
    """主函数：扫描并修复所有 Python 文件"""
    root_dir = Path('.')
    fixed_files = []
    error_files = []
    
    # 扫描所有 Python 文件
    for py_file in root_dir.rglob('*.py'):
        # 跳过备份文件和脚本自身
        if py_file.name in ['fix_imports.py', 'auto_fix_imports.py', 'batch_fix.py', 'batch_fix_v2.py']:
            continue
        if 'backup' in str(py_file).lower() or 'core_backup' in str(py_file):
            continue
        
        try:
            fixed, msg = fix_imports_in_file(py_file)
            if fixed:
                fixed_files.append(str(py_file))
                print(f"[OK] Fixed: {py_file}")
            else:
                if msg != "No match":
                    print(f"[WARN] Error: {py_file} - {msg}")
                    error_files.append((str(py_file), msg))
        except Exception as e:
            print(f"❌ Failed: {py_file} - {e}")
            error_files.append((str(py_file), str(e)))
    
    # 输出总结
    print("\n" + "="*60)
    print(f"[OK] 成功修复: {len(fixed_files)} 个文件")
    print(f"[ERROR] 失败: {len(error_files)} 个文件")
    print("="*60)
    
    if fixed_files:
        print("\n修复的文件:")
        for f in fixed_files[:10]:  # 只显示前 10 个
            print(f"  - {f}")
        if len(fixed_files) > 10:
            print(f"  ... 还有 {len(fixed_files) - 10} 个文件")
    
    if error_files:
        print("\n失败的文件:")
        for f, e in error_files[:5]:  # 只显示前 5 个错误
            print(f"  - {f}: {e}")
        if len(error_files) > 5:
            print(f"  ... 还有 {len(error_files) - 5} 个错误")

if __name__ == '__main__':
    main()
