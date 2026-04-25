#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动语法修复器 v3
针对 LivingTreeAI 项目的大量 import 缩进错误
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple

def fix_file(filepath: Path) -> Tuple[bool, str]:
    """修复单个文件"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return False, f"读取失败: {e}"
    
    original = content
    lines = content.split('\n')
    
    # 检测错误的 import 模式
    # 模式1: from core.logger import get_logger 在函数/try块内但没有正确缩进
    # 查找: 行不以4空格开头但应该是 (即在 try: 后面但缩进错误)
    
    i = 0
    new_lines = []
    fix_count = 0
    
    while i < len(lines):
        line = lines[i]
        
        # 检测错误模式: from core.logger 前面有代码但缩进不足
        if line.strip().startswith('from core.logger import get_logger') or \
           line.strip().startswith('logger = get_logger'):
            
            # 检查是否是错误放置
            # 错误模式: 在 try: 后的下一行但没有缩进
            if i > 0:
                prev_line = lines[i-1]
                if prev_line.strip() == 'try:' or prev_line.strip().endswith('try:'):
                    # 这是错误模式，跳过并记录
                    fix_count += 1
                    i += 1
                    continue
                # 也检查前面的代码行
                for j in range(i-1, -1, -1):
                    p = lines[j]
                    if not p.strip() or p.strip().startswith('#'):
                        continue
                    # 如果在 try 块内
                    if 'try:' in p:
                        # 检查缩进
                        prev_indent = len(p) - len(p.lstrip())
                        curr_indent = len(line) - len(line.lstrip())
                        if curr_indent <= prev_indent:
                            fix_count += 1
                            i += 1
                            continue
                    break
        
        new_lines.append(line)
        i += 1
    
    if fix_count > 0:
        content = '\n'.join(new_lines)
        
        # 添加 logger import 到顶部（如果还没有）
        if 'from core.logger import get_logger' not in content:
            # 找到导入区
            import_lines = []
            other_lines = []
            in_import = True
            
            for line in content.split('\n'):
                stripped = line.strip()
                if in_import:
                    if stripped.startswith('import ') or stripped.startswith('from '):
                        import_lines.append(line)
                    elif stripped and not stripped.startswith('#'):
                        in_import = False
                        other_lines.append(line)
                    else:
                        import_lines.append(line)
                else:
                    other_lines.append(line)
            
            # 添加 logger import
            if import_lines:
                import_lines.append('from core.logger import get_logger')
            
            # 重建文件
            content = '\n'.join(import_lines + other_lines)
        
        # 添加 logger 初始化到顶部（如果需要）
        if 'logger = get_logger' not in content:
            # 从错误位置提取 logger 名称
            match = re.search(r"logger = get_logger\('([^']+)'\)", original)
            if match:
                logger_name = match.group(1)
                # 在导入后添加
                content = content.replace(
                    'from core.logger import get_logger',
                    f'from core.logger import get_logger\n\nlogger = get_logger(\'{logger_name}\')'
                )
        
        filepath.write_text(content, encoding='utf-8')
        return True, f"修复 {fix_count} 处"
    
    return False, "无需修复"

def main():
    base = Path(r'F:\mhzyapp\LivingTreeAlAgent\core')
    
    # 获取所有 py 文件
    py_files = list(base.rglob('*.py'))
    
    fixed = []
    errors = []
    
    for f in py_files:
        try:
            ok, msg = fix_file(f)
            if ok:
                fixed.append((f.relative_to(base), msg))
        except Exception as e:
            errors.append((f.relative_to(base), str(e)))
    
    print(f"扫描完成: {len(py_files)} 个文件")
    print(f"修复: {len(fixed)} 个")
    print(f"错误: {len(errors)} 个")
    
    for rel, msg in fixed[:20]:
        print(f"  ✓ {rel}: {msg}")
    
    if errors:
        print("\n错误列表:")
        for rel, err in errors[:10]:
            print(f"  ✗ {rel}: {err}")

if __name__ == '__main__':
    main()
