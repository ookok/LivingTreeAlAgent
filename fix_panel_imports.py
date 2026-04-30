# -*- coding: utf-8 -*-
"""
批量修复 panels 目录中的相对导入路径问题
将 from .components.xxx 替换为 from ..components.xxx
"""

import os
import re

def fix_panel_imports(root_dir):
    """修复指定目录下所有文件的导入路径"""
    # 匹配 from .components.xxx 的模式
    pattern = re.compile(r'from \.components(\.\w+)')
    replacement = r'from ..components\1'
    
    count = 0
    fixed_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
                
            filepath = os.path.join(dirpath, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content, num_replacements = pattern.subn(replacement, content)
                
                if num_replacements > 0:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    count += num_replacements
                    fixed_files.append((filepath, num_replacements))
                    print(f"✅ 修复: {filepath} ({num_replacements}处)")
                    
            except Exception as e:
                print(f"❌ 错误: {filepath} - {str(e)}")
    
    print(f"\n📊 总计修复: {count} 处引用")
    return fixed_files

if __name__ == '__main__':
    # 修复 panels 目录中的导入
    fix_panel_imports('client/src/presentation/panels')