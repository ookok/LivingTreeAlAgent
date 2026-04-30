# -*- coding: utf-8 -*-
"""
批量修复 core 模块引用
将 from core.xxx 替换为 from client.src.business.xxx
"""

import os
import re

def fix_core_imports(root_dir):
    """修复指定目录下所有文件的 core 引用"""
    pattern = re.compile(r'from core\.')
    replacement = 'from client.src.business.'
    
    count = 0
    fixed_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 跳过备份目录和测试文件
        if 'backup' in dirpath.lower():
            continue
            
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
    # 修复业务层的 core 引用
    fix_core_imports('client/src/business')
    
    # 修复表示层的 core 引用（排除备份目录）
    fix_core_imports('client/src/presentation')