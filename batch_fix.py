#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复 logger import 错误
"""

import re
from pathlib import Path

def fix_all_files():
    base = Path(r'F:\mhzyapp\LivingTreeAlAgent\core')
    fixed_files = []
    
    for pyfile in base.rglob('*.py'):
        try:
            content = pyfile.read_text(encoding='utf-8')
            lines = content.split('\n')
            new_lines = []
            i = 0
            modified = False
            
            while i < len(lines):
                line = lines[i]
                
                # 检查是否紧跟在 try: 后面但没有缩进
                if i > 0:
                    prev = lines[i-1]
                    stripped = line.strip()
                    prev_stripped = prev.strip()
                    
                    # 模式: 前一行是 'try:' 且当前行是 logger import 但没有缩进
                    if prev_stripped == 'try:' and (stripped.startswith('from core.logger') or stripped.startswith('logger = get_logger')):
                        # 这是错误位置，需要跳过
                        modified = True
                        i += 1
                        continue
                
                new_lines.append(line)
                i += 1
            
            if modified:
                content = '\n'.join(new_lines)
                
                # 检查是否已有 logger import，没有则添加
                if 'from core.logger import get_logger' not in content:
                    # 在 import 区添加
                    import_end = 0
                    for idx, line in enumerate(content.split('\n')):
                        stripped = line.strip()
                        if stripped.startswith('import ') or stripped.startswith('from '):
                            import_end = idx
                    
                    lines = content.split('\n')
                    lines.insert(import_end + 1, 'from core.logger import get_logger')
                    content = '\n'.join(lines)
                    
                    # 添加 logger 初始化 - 提取原来的 logger 名称
                    logger_name_match = re.search(r"logger = get_logger\('([^']+)'\)", pyfile.read_text(encoding='utf-8'))
                    if logger_name_match:
                        name = logger_name_match.group(1)
                        content = content.replace('from core.logger import get_logger', 
                                               f'from core.logger import get_logger\n\nlogger = get_logger(\'{name}\')')
                
                pyfile.write_text(content, encoding='utf-8')
                fixed_files.append(str(pyfile.relative_to(base)))
                
        except Exception as e:
            print(f"Error processing {pyfile}: {e}")
    
    print(f'Fixed {len(fixed_files)} files:')
    for f in fixed_files[:30]:
        print(f'  - {f}')

if __name__ == '__main__':
    fix_all_files()
