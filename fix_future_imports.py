#!/usr/bin/env python3
"""
批量修复 from __future__ import annotations 位置错误
"""
import os
import sys
import re

def fix_future_annotations(file_path):
    """修复单个文件中的 from __future__ import annotations 位置错误"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找 from __future__ import annotations 的行号
        future_line = None
        for i, line in enumerate(lines):
            if re.match(r'^from\s+__future__\s+import\s+annotations\s*$', line.strip()):
                future_line = i
                break
        
        if future_line is None:
            # 没有 from __future__ import annotations，跳过
            return False, "没有 from __future__ import annotations"
        
        # 检查是否已经在文件开头（在 docstring 之后，在其他 import 之前）
        # 简单判断：如果前面有非注释、非空行的代码行，则位置错误
        has_code_before = False
        for i in range(future_line):
            line_stripped = lines[i].strip()
            if line_stripped and not line_stripped.startswith('#'):
                # 可能是 docstring 的开始或结束
                if line_stripped.startswith('"""') or line_stripped.startswith("'''"):
                    continue
                # 可能是 docstring 的内容
                if line_stripped.endswith('"""') or line_stripped.endswith("'''"):
                    continue
                # 其他代码，位置错误
                has_code_before = True
                break
        
        if not has_code_before:
            return False, "位置正确，无需修复"
        
        # 修复：将 from __future__ import annotations 移动到文件开头
        future_line_content = lines[future_line]
        del lines[future_line]  # 删除原有行
        
        # 查找插入位置：在 docstring 之后，在其他 import 之前
        insert_pos = 0
        in_docstring = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('"""') or line_stripped.startswith("'''"):
                in_docstring = not in_docstring
            if not in_docstring and line_stripped and not line_stripped.startswith('#'):
                if not line_stripped.startswith('from __future__'):
                    insert_pos = i
                    break
            insert_pos = i + 1
        
        # 插入 from __future__ import annotations
        lines.insert(insert_pos, future_line_content)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return True, f"已修复：将 from __future__ import annotations 移动到行 {insert_pos + 1}"
        
    except Exception as e:
        return False, f"修复失败: {e}"

def main():
    if len(sys.argv) < 2:
        print("用法: python fix_future_imports.py <file_or_directory>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    if os.path.isfile(target):
        # 修复单个文件
        success, msg = fix_future_annotations(target)
        print(f"{'✅' if success else '⚠️'} {target}: {msg}")
    elif os.path.isdir(target):
        # 递归修复目录中的所有 .py 文件
        fixed = 0
        failed = 0
        
        for root, dirs, files in os.walk(target):
            # 跳过某些目录
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', '.venv', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    success, msg = fix_future_annotations(file_path)
                    if success:
                        print(f"✅ {file_path}: {msg}")
                        fixed += 1
                    # else:
                    #     print(f"⚠️ {file_path}: {msg}")
        
        print(f"\n📊 修复完成: {fixed} 个文件已修复")

if __name__ == '__main__':
    main()
