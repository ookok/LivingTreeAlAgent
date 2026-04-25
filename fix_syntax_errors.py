# -*- coding: utf-8 -*-
"""
批量语法错误修复脚本
自动修复 core 目录中的 import 语句缩进问题
"""

import os
import re
from pathlib import Path

def fix_file_syntax(filepath: Path) -> bool:
    """
    修复单个文件的语法错误
    模式: 在 try 块内错误放置的 import 语句
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  [SKIP] 无法读取: {e}")
        return False
    
    original_content = content
    changes_made = 0
    
    # 模式1: from client.src.business.logger import get_logger 后跟 logger = get_logger(...) 
    # 在 try/except 块内但没有正确缩进
    pattern1 = r'(\n    try:\n)(.*?)(\n)(from core\.logger import get_logger\n)(logger = get_logger\([^)]+\)\n)'
    
    # 检查是否已经导入了 core.logger
    if 'from client.src.business.logger import get_logger' not in content:
        # 模式: 在 try 块内的 import 语句没有正确缩进
        # 查找 "    try:" 后紧跟着 "from core.logger" 但没有正确缩进的情况
        lines = content.split('\n')
        new_lines = []
        i = 0
        logger_import_added = False
        
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是 try: 后面跟着 logger 相关的 import
            if line.strip() == 'try:' and i + 1 < len(lines):
                next_line = lines[i + 1]
                # 检查是否有 from core.logger 在错误位置
                if 'from client.src.business.logger import get_logger' in next_line or \
                   'from core import logger' in next_line or \
                   'import logging' in next_line and i + 2 < len(lines) and \
                   'logger' in lines[i + 2]:
                    # 这是问题模式，找到 try 块之前的正确位置添加 import
                    # 先收集 try 块的内容
                    try_block_lines = [line]
                    i += 1
                    indent_level = len(line) - len(line.lstrip())
                    
                    while i < len(lines):
                        curr = lines[i]
                        if curr.strip() and not curr.strip().startswith('#'):
                            curr_indent = len(curr) - len(curr.lstrip())
                            if curr_indent <= indent_level and curr.strip() not in ['except:', 'except Exception:', 'except (']:
                                # 超出 try 块了
                                break
                        try_block_lines.append(curr)
                        i += 1
                    
                    # 在 try_block_lines 中找到并移除 logger 相关的 import
                    fixed_block = []
                    for bl in try_block_lines:
                        stripped = bl.strip()
                        if stripped.startswith('from core.logger') or \
                           stripped.startswith('import logger') or \
                           stripped.startswith('logger = get_logger'):
                            if 'from client.src.business.logger import get_logger' in bl:
                                if not logger_import_added:
                                    # 添加到顶部
                                    new_lines.append(bl)  # 先添加这行，稍后排序
                                    logger_import_added = True
                                changes_made += 1
                                continue
                            changes_made += 1
                            continue
                        fixed_block.append(bl)
                    
                    new_lines.extend(fixed_block)
                    continue
            
            new_lines.append(line)
            i += 1
        
        if changes_made > 0:
            content = '\n'.join(new_lines)
    
    # 模式2: 简单的 "from core.logger" 紧跟在 try: 之后但缩进错误
    # 匹配: try:\nfrom client.src.business.logger import get_logger\n
    pattern2 = r'(\n    try:\n)(from core\.logger import get_logger\n)(logger = get_logger)'
    
    # 先检查是否需要添加 logger import
    if 'logger = get_logger' in content and 'from client.src.business.logger import get_logger' not in content:
        # 需要添加 import
        # 找一个合适的位置添加
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') and not line.startswith('    '):
                insert_pos = i + 1
            if line.startswith('from ') and not line.startswith('    '):
                insert_pos = i + 1
        
        # 在 import 区段添加 logger import
        import_lines = []
        for line in lines[:insert_pos]:
            if line.startswith('import ') or line.startswith('from '):
                import_lines.append(line)
        
        if import_lines:
            last_import_idx = -1
            for i, line in enumerate(lines):
                if (line.startswith('import ') or line.startswith('from ')) and not line.startswith('    '):
                    last_import_idx = i
            
            if last_import_idx >= 0:
                lines.insert(last_import_idx + 1, 'from client.src.business.logger import get_logger')
                content = '\n'.join(lines)
                changes_made += 1
    
    if content != original_content:
        filepath.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    """主函数"""
    base_path = Path(r'F:\mhzyapp\LivingTreeAlAgent\core')
    
    # 获取所有 Python 文件
    py_files = list(base_path.rglob('*.py'))
    
    print(f"找到 {len(py_files)} 个 Python 文件")
    
    fixed_count = 0
    error_count = 0
    
    for py_file in py_files:
        try:
            result = fix_file_syntax(py_file)
            if result:
                print(f"  [FIXED] {py_file.relative_to(base_path)}")
                fixed_count += 1
        except Exception as e:
            print(f"  [ERROR] {py_file.relative_to(base_path)}: {e}")
            error_count += 1
    
    print(f"\n修复完成: {fixed_count} 个文件")
    if error_count > 0:
        print(f"错误: {error_count} 个文件")

if __name__ == '__main__':
    main()
