"""
迁移 core/visual_evolution_engine/ 到 client/src/business/visual_evolution_engine/
"""
import os
import shutil
import re

# 1. 复制目录
src = 'core/visual_evolution_engine'
dst = 'client/src/business/visual_evolution_engine'

os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copytree(src, dst, dirs_exist_ok=True)
print(f'[OK] Copied {src}/ to {dst}/')

# 2. 更新内部导入
count = 0
for root, dirs, files in os.walk(dst):
    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original = content
                content = re.sub(r'from core\.visual_evolution_engine', 'from client.src.business.visual_evolution_engine', content)
                content = re.sub(r'import core\.visual_evolution_engine', 'import client.src.business.visual_evolution_engine', content)
            
                if content != original:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    count += 1
            except Exception as e:
                print(f'[ERROR] {file_path}: {e}')

print(f'[OK] Updated {count} files (internal imports)')
