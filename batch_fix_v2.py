#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复 logger import 错误 v2
"""

import re
from pathlib import Path

def fix_file(filepath: Path) -> bool:
    """修复单个文件"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return False
    
    original = content
    
    # 提取所有 logger 初始化语句
    logger_inits = re.findall(r"logger = get_logger\('([^']+)'\)", content)
    
    if not logger_inits:
        return False
    
    logger_name = logger_inits[0]  # 使用第一个作为默认名
    
    # 检查 logger import 是否在错误位置
    # 错误模式: 在函数内部，紧跟在另一个 import 后面但没有缩进
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    has_misplaced_logger = False
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测错误模式: logger import/init 没有缩进但前一行有缩进的 import
        if i > 0:
            prev = lines[i-1]
            prev_stripped = prev.strip()
            
            # 模式: logger import/init 没有缩进，但前一行有缩进（是函数内的 import）
            if (stripped.startswith('from core.logger import get_logger') or 
                stripped.startswith('logger = get_logger')):
                
                # 检查前一行是否有缩进（如果是函数内）
                prev_indent = len(prev) - len(prev.lstrip())
                curr_indent = len(line) - len(line.lstrip())
                
                if prev_indent > 0 and curr_indent == 0:
                    # 这是错误位置！前一行在函数内但这一行没有
                    has_misplaced_logger = True
                    i += 1
                    continue
        
        new_lines.append(line)
        i += 1
    
    if has_misplaced_logger:
        content = '\n'.join(new_lines)
        
        # 检查是否已有 logger import
        if 'from core.logger import get_logger' not in content:
            # 在顶部添加 logger import
            # 找到 docstring 或 import 区结尾
            import_end = 0
            in_docstring = False
            docstring_depth = 0
            
            for idx, line in enumerate(content.split('\n')):
                stripped = line.strip()
                
                # 检测 docstring
                if '"""' in stripped or "'''" in stripped:
                    d_count = stripped.count('"""') + stripped.count("'''")
                    if d_count == 1:
                        if in_docstring:
                            in_docstring = False
                            import_end = idx
                            break
                        else:
                            in_docstring = True
                    elif d_count == 2:
                        import_end = idx
                        break
                
                # 如果在 import 区
                if not in_docstring:
                    if stripped.startswith('import ') or stripped.startswith('from '):
                        import_end = idx
            
            lines = content.split('\n')
            insert_pos = import_end + 1
            
            # 添加 import 和 logger 初始化
            import_stmt = 'from core.logger import get_logger'
            logger_stmt = f'logger = get_logger(\'{logger_name}\')'
            
            # 在适当位置插入
            lines.insert(insert_pos, '')
            lines.insert(insert_pos + 1, import_stmt)
            lines.insert(insert_pos + 2, logger_stmt)
            
            content = '\n'.join(lines)
        
        filepath.write_text(content, encoding='utf-8')
        return True
    
    return False

def main():
    base = Path(r'F:\mhzyapp\LivingTreeAlAgent\core')
    fixed = []
    
    for pyfile in base.rglob('*.py'):
        try:
            if fix_file(pyfile):
                fixed.append(str(pyfile.relative_to(base)))
        except Exception as e:
            print(f"Error: {pyfile}: {e}")
    
    print(f"Fixed {len(fixed)} files:")
    for f in fixed[:30]:
        print(f"  - {f}")
    if len(fixed) > 30:
        print(f"  ... and {len(fixed) - 30} more")

if __name__ == '__main__':
    main()
