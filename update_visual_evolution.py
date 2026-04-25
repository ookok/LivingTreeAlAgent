"""
更新外部文件中的 core.visual_evolution_engine 导入到 client.src.business.visual_evolution_engine
"""
import os
import re

# 需要更新的外部文件
files_to_update = [
    'test_visual_evolution_engine.py',
    'test_smart_router.py',
]

count = 0
for file_path in files_to_update:
    if not os.path.exists(file_path):
        print(f'[SKIP] Not found: {file_path}')
        continue
        
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
            print(f'[OK] Updated: {file_path}')
    except Exception as e:
        print(f'[ERROR] {file_path}: {e}')

print(f'\nTotal: {count} files updated (external imports)')

# 删除 core/visual_evolution_engine/ 目录
import shutil
dir_path = 'core/visual_evolution_engine'
if os.path.exists(dir_path):
    shutil.rmtree(dir_path)
    print(f'\n[OK] Deleted: {dir_path}/')
else:
    print(f'\n[SKIP] Not found: {dir_path}/')
