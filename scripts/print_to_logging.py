"""
print 语句批量替换工具
=====================

自动将 print 语句替换为 logging 模块

使用方法:
    python scripts/print_to_logging.py --dry-run  # 预览
    python scripts/print_to_logging.py --execute   # 执行替换
    python scripts/print_to_logging.py --file core/example.py  # 单文件
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# 替换规则定义
# ═══════════════════════════════════════════════════════════════════════════════

# 导入语句
IMPORT_LOGGING = '''import logging
logger = logging.getLogger(__name__)'''

# 替换模式
REPLACEMENTS = [
    # print("...") → logger.info("...")
    (r'print\(f?"([^"]*)"\)', r'logger.info(r"\1")'),
    
    # print(f"...") → logger.info("...")
    (r'print\(f"([^"]*)"\)', r'logger.info(r"\1")'),
    
    # print(f'...') → logger.info('...')
    (r"print\(f'([^']*)'\)", r"logger.info(r'\1')"),
    
    # print("...", ...) → logger.info("...", ...)
    (r'print\(([^)]+)\)', r'logger.info(\1)'),
]

# 跳过模式（不改动的代码）
SKIP_PATTERNS = [
    r'# print',  # 注释掉的print
    r'""".*print.*"""',  # 文档字符串中的print
    r"'''.*print.*'''",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 核心替换逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def should_skip(content: str) -> bool:
    """检查是否应该跳过文件"""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, content, re.DOTALL):
            return True
    return False


def add_logging_import(content: str) -> str:
    """添加 logging 导入"""
    if 'import logging' in content:
        return content
    
    # 找到合适的位置插入导入
    # 策略1: 在其他 import 之后
    import_match = re.search(r'(^import \w+.*$)', content, re.MULTILINE)
    if import_match:
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('import '):
                insert_idx = i + 1
        
        lines.insert(insert_idx, 'import logging')
        lines.insert(insert_idx + 1, 'logger = logging.getLogger(__name__)')
        return '\n'.join(lines)
    
    # 策略2: 在文件开头
    return "import logging\nlogger = logging.getLogger(__name__)\n\n" + content


def replace_print_statements(content: str) -> Tuple[str, int]:
    """替换 print 语句，返回 (替换后内容, 替换数量)"""
    original = content
    count = 0
    
    # 替换 print() 空打印（换行）
    content = re.sub(r'print\(\)', 'logger.info("")', content)
    
    # 替换 print("message")
    content = re.sub(r'print\(f?"([^"]*)"\)', r'logger.info("\1")', content)
    
    # 替换 print(f"...")
    def fix_fstring(match):
        fstring = match.group(1)
        return f'logger.info("{fstring}")'
    
    content = re.sub(r'print\(f"([^"]*)"\)', fix_fstring, content)
    content = re.sub(r"print\(f'([^']*)'\)", fix_fstring, content)
    
    # 替换 print(variable)
    content = re.sub(r'print\((\w+)\)', r'logger.info("%s", \1)', content)
    
    # 替换 print(a, b, c)
    content = re.sub(r'print\(([^)]+)\)', r'logger.info("%s", \1)', content)
    
    # 统计替换数量
    count = original.count('print(') - content.count('print(')
    
    return content, count


def process_file(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """
    处理单个文件
    
    Returns:
        (是否成功, 消息)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有 print
        if 'print(' not in content:
            return False, "No print statements found"
        
        # 检查是否应该跳过
        if should_skip(content):
            return False, "Skipped (docstring or comment)"
        
        # 替换
        new_content, count = replace_print_statements(content)
        
        if count == 0:
            return False, "No replacements made"
        
        # 添加导入
        new_content = add_logging_import(new_content)
        
        if dry_run:
            return True, f"[DRY RUN] Would replace {count} print statements"
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True, f"Replaced {count} print statements"
            
    except Exception as e:
        return False, f"Error: {e}"


def process_directory(dirpath: str, dry_run: bool = True, 
                      exclude_dirs: List[str] = None) -> List[Tuple[str, str]]:
    """
    处理目录中的所有 Python 文件
    
    Returns:
        [(文件路径, 消息), ...]
    """
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.git', 'node_modules', '.venv', 'venv']
    
    results = []
    
    for root, dirs, files in os.walk(dirpath):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for f in files:
            if f.endswith('.py'):
                filepath = os.path.join(root, f)
                success, msg = process_file(filepath, dry_run)
                if success or 'No print' not in msg:
                    results.append((filepath, msg))
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='print → logging 替换工具')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不执行替换')
    parser.add_argument('--execute', action='store_true', help='执行替换')
    parser.add_argument('--file', help='处理单个文件')
    parser.add_argument('--dir', help='处理目录')
    parser.add_argument('--core', action='store_true', help='处理 core 目录')
    parser.add_argument('--tests', action='store_true', help='处理 tests 目录')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if args.file:
        # 单文件
        success, msg = process_file(args.file, dry_run)
        print(f"{'✓' if success else '✗'} {args.file}: {msg}")
        
    elif args.dir:
        # 指定目录
        results = process_directory(args.dir, dry_run)
        for filepath, msg in results:
            print(f"{filepath}: {msg}")
        print(f"\nTotal: {len(results)} files processed")
        
    elif args.core:
        # core 目录
        results = process_directory('core', dry_run)
        for filepath, msg in results:
            print(f"{filepath}: {msg}")
        print(f"\nTotal: {len(results)} files processed")
        
    elif args.tests:
        # tests 目录
        if os.path.exists('tests'):
            results = process_directory('tests', dry_run)
            for filepath, msg in results:
                print(f"{filepath}: {msg}")
            print(f"\nTotal: {len(results)} files processed")
        else:
            print("tests directory not found")
            
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python print_to_logging.py --dry-run --core")
        print("  python print_to_logging.py --execute --tests")
        print("  python print_to_logging.py --file core/example.py")


if __name__ == '__main__':
    main()
