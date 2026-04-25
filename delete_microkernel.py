"""
删除 core/microkernel/ 目录
"""
import os, shutil

dir_path = 'core/microkernel'
if os.path.exists(dir_path):
    shutil.rmtree(dir_path)
    print(f'[OK] Deleted: {dir_path}/')
else:
    print(f'[SKIP] Not found: {dir_path}/')
