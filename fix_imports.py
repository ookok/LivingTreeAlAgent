"""
批量修复导入路径问题

将 `from client.src.xxx` 替换为相对导入
"""

import os
import re

def fix_imports_in_file(file_path):
    """修复单个文件的导入路径"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 找出所有需要修复的导入
        imports = re.findall(r'from client\.src\.(business|presentation|infrastructure|shared)\.(.*)', content)
        
        if not imports:
            return False
        
        # 替换导入路径
        new_content = content
        
        # 对于 business 模块的导入
        new_content = re.sub(
            r'from client\.src\.business\.',
            r'from .business.',
            new_content
        )
        
        # 对于 presentation 模块的导入（需要处理相对导入）
        new_content = re.sub(
            r'from client\.src\.presentation\.',
            r'from .presentation.',
            new_content
        )
        
        # 对于 infrastructure 模块的导入
        new_content = re.sub(
            r'from client\.src\.infrastructure\.',
            r'from .infrastructure.',
            new_content
        )
        
        # 对于 shared 模块的导入
        new_content = re.sub(
            r'from client\.src\.shared\.',
            r'from .shared.',
            new_content
        )
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✓ 修复: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"✗ 错误处理 {file_path}: {e}")
        return False

def fix_all_imports(root_dir):
    """修复所有文件的导入路径"""
    print("开始修复导入路径...")
    fixed_count = 0
    total_files = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                file_path = os.path.join(dirpath, filename)
                total_files += 1
                
                if fix_imports_in_file(file_path):
                    fixed_count += 1
    
    print(f"\n修复完成!")
    print(f"处理文件: {total_files}")
    print(f"修复文件: {fixed_count}")

if __name__ == "__main__":
    fix_all_imports(os.path.join(os.path.dirname(__file__), 'client', 'src'))