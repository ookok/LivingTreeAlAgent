"""
批量修复导入路径问题（版本3）

修复 presentation 目录下的相对导入问题
"""

import os
import re

def fix_presentation_imports():
    """修复 presentation 目录下的导入"""
    presentation_dir = os.path.join(os.path.dirname(__file__), 'client', 'src', 'presentation')
    
    print("修复 presentation 目录下的导入...")
    
    for dirpath, dirnames, filenames in os.walk(presentation_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                file_path = os.path.join(dirpath, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # 将 from .business 替换为 from business
                    content = content.replace('from .business.', 'from business.')
                    
                    # 将 from .infrastructure 替换为 from infrastructure
                    content = content.replace('from .infrastructure.', 'from infrastructure.')
                    
                    # 将 from .shared 替换为 from shared
                    content = content.replace('from .shared.', 'from shared.')
                    
                    # 将 from .presentation 替换为 from presentation
                    content = content.replace('from .presentation.', 'from presentation.')
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✓ 修复: {file_path}")
                
                except Exception as e:
                    print(f"✗ 错误处理 {file_path}: {e}")
    
    print("\n修复完成!")

def fix_business_imports():
    """修复 business 目录下的导入"""
    business_dir = os.path.join(os.path.dirname(__file__), 'client', 'src', 'business')
    
    print("修复 business 目录下的导入...")
    
    for dirpath, dirnames, filenames in os.walk(business_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                file_path = os.path.join(dirpath, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # 将 from .business 替换为 from business
                    content = content.replace('from .business.', 'from business.')
                    
                    # 将 from .infrastructure 替换为 from infrastructure
                    content = content.replace('from .infrastructure.', 'from infrastructure.')
                    
                    # 将 from .shared 替换为 from shared
                    content = content.replace('from .shared.', 'from shared.')
                    
                    # 将 from .presentation 替换为 from presentation
                    content = content.replace('from .presentation.', 'from presentation.')
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✓ 修复: {file_path}")
                
                except Exception as e:
                    print(f"✗ 错误处理 {file_path}: {e}")
    
    print("\n修复完成!")

if __name__ == "__main__":
    fix_presentation_imports()
    fix_business_imports()