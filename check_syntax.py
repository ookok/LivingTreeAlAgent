#!/usr/bin/env python3
"""
批量检查 Python 文件的语法错误
"""
import py_compile
import sys
import os
from pathlib import Path

def check_syntax(file_path):
    """检查单个文件的语法"""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def scan_directory(root_dir, extensions=['.py']):
    """扫描目录，检查所有 Python 文件的语法"""
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for root, dirs, files in os.walk(root_dir):
        # 跳过某些目录
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', '.venv', 'node_modules']]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                results['total'] += 1
                
                success, error = check_syntax(file_path)
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'file': file_path,
                        'error': error
                    })
    
    return results

if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    print(f"🔍 扫描目录: {root}")
    print("=" * 60)
    
    results = scan_directory(root)
    
    print(f"\n📊 扫描完成:")
    print(f"  总文件数: {results['total']}")
    print(f"  成功: {results['success']}")
    print(f"  失败: {results['failed']}")
    
    if results['errors']:
        print(f"\n❌ 发现语法错误:")
        print("=" * 60)
        for item in results['errors'][:20]:  # 只显示前20个错误
            print(f"\n文件: {item['file']}")
            print(f"错误: {item['error']}")
        
        if len(results['errors']) > 20:
            print(f"\n... 还有 {len(results['errors']) - 20} 个错误未显示")
    else:
        print("\n✅ 没有发现语法错误")
