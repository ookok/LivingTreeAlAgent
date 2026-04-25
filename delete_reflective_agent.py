"""
删除 core/reflective_agent/ 目录
"""
import os, shutil

dir_path = 'core/reflective_agent'
if os.path.exists(dir_path):
    shutil.rmtree(dir_path)
    print(f'[OK] Deleted: {dir_path}/')
else:
    print(f'[SKIP] Not found: {dir_path}/')
