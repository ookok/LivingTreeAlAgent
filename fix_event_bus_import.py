"""
修复 event_bus 导入问题

将 `from shared.event_bus` 替换为 `from business.shared.event_bus`
"""

import os
import re

def fix_event_bus_imports():
    """修复所有 event_bus 导入"""
    src_dir = os.path.join(os.path.dirname(__file__), 'client', 'src')
    
    print("修复 event_bus 导入...")
    
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                file_path = os.path.join(dirpath, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # 将 from shared.event_bus 替换为 from business.shared.event_bus
                    content = content.replace(
                        'from shared.event_bus', 
                        'from business.shared.event_bus'
                    )
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✓ 修复: {file_path}")
                
                except Exception as e:
                    print(f"✗ 错误处理 {file_path}: {e}")
    
    print("\n修复完成!")

if __name__ == "__main__":
    fix_event_bus_imports()