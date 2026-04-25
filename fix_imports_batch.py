#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量语法错误修复脚本 v2
自动检测并修复 core 目录中所有文件的 import 缩进问题
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

def find_and_fix_file(filepath: Path) -> Tuple[bool, List[str]]:
    """检测并修复单个文件的语法错误"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return False, [f"读取失败: {e}"]
    
    original = content
    changes = []
    
    # 模式1: 查找 "try:\n" 后紧跟着 "from client.src.business.logger import" 但没有正确缩进
    # 匹配: try:\nfrom client.src.business.logger import get_logger\nlogger = get_logger
    patterns = [
        # Pattern: try: 块内的 logger import
        (r'(\n    try:\n)(from core\.logger import get_logger\n)(logger = get_logger)',
         r'\1# logger import moved to top\n\3'),
        
        # Pattern: function 内的 logger import
        (r'(\n    def \w+.*?:\n)(.*?)(\n)(from core\.logger import get_logger\n)(logger = get_logger\([^)]+\))',
         r'\1\2\3# logger import moved to top\n\5'),
    ]
    
    # 更简单的方法：直接查找所有 from core.logger 的位置
    # 检查它们是否在正确的缩进级别
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    found_logger_import = False
    logger_import_line = None
    logger_init_line = None
    
    while i < len(lines):
        line = lines[i]
        
        # 检测 logger 相关 import
        if line.strip().startswith('from client.src.business.logger import get_logger'):
            # 检查是否在 try 块内但缩进错误
            # 获取前一行
            if i > 0:
                prev_line = lines[i-1]
                # 如果前一行是 try: 且当前行没有缩进或缩进不足
                if 'try:' in prev_line or prev_line.strip() == 'try:':
                    logger_import_line = i
                    # 跳过这行，稍后处理
                    i += 1
                    continue
                # 如果在前一个 try 块内
                for j in range(i-1, -1, -1):
                    prev = lines[j]
                    if not prev.strip() or prev.strip().startswith('#'):
                        continue
                    indent = len(prev) - len(prev.lstrip())
                    if prev.strip() in ['except:', 'except Exception:', 'except (']:
                        if indent > 0:  # 在 try 块内
                            logger_import_line = i
                            i += 1
                            continue
                    break
        
        # 检测 logger 初始化
        if 'logger = get_logger' in line:
            # 检查是否紧跟在 logger import 后面
            if i > 0 and logger_import_line == i - 1:
                logger_init_line = i
                i += 1
                continue
        
        new_lines.append(line)
        i += 1
    
    if logger_import_line is not None:
        # 找到 logger import，需要修复
        # 重新解析
        content = '\n'.join(new_lines)
        
        # 检查是否已经在顶部导入了
        top_import_pattern = r'^from core\.logger import get_logger'
        if not re.search(top_import_pattern, content, re.MULTILINE):
            # 需要在顶部添加 import
            # 找到合适的位置（import 区段末尾）
            import_section_end = 0
            for idx, line in enumerate(content.split('\n')):
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    import_section_end = idx
            
            if import_section_end > 0:
                lines = content.split('\n')
                lines.insert(import_section_end + 1, 'from client.src.business.logger import get_logger')
                content = '\n'.join(lines)
                changes.append("添加 logger import 到顶部")
        
        # 移除函数内的 logger import（现在不需要了，因为我们已经在 try 块内了）
        # 实际上，如果 logger import 在 try 块内但缩进正确，那可能是正常的
        # 问题是缩进不正确的
        pass
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return True, changes
    
    return False, []

def main():
    base_path = Path(r'F:\mhzyapp\LivingTreeAlAgent\core')
    
    # 获取所有 Python 文件
    py_files = list(base_path.rglob('*.py'))
    
    print(f"扫描 {len(py_files)} 个 Python 文件...")
    
    fixed = []
    errors = []
    
    for py_file in py_files:
        try:
            fixed_ok, changes = find_and_fix_file(py_file)
            if fixed_ok:
                rel_path = py_file.relative_to(base_path)
                fixed.append((str(rel_path), changes))
        except Exception as e:
            errors.append((str(py_file.relative_to(base_path)), str(e)))
    
    print(f"\n修复完成:")
    print(f"  修复: {len(fixed)} 个文件")
    if errors:
        print(f"  错误: {len(errors)} 个文件")
        for path, err in errors[:5]:
            print(f"    - {path}: {err}")
    
    for path, changes in fixed[:10]:
        print(f"  + {path}")

if __name__ == '__main__':
    main()
