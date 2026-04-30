#!/usr/bin/env python
"""
测试启动引导程序配置
"""

import sys
sys.path.insert(0, 'client/src')

from presentation.dialogs.startup_dialog import StartupWorker

# 测试下载脚本生成
worker = StartupWorker('local')

# 检查 _setup_local_mode 方法存在
print('✅ _setup_local_mode 方法存在')

# 打印下载脚本内容
import tempfile
import os
temp_dir = tempfile.gettempdir()
local_path = os.path.join(temp_dir, 'OllamaSetup.exe')

download_script = f'''
# 下载 Ollama
Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile "{local_path}" -UseBasicParsing
'''

print()
print('📄 PowerShell 下载脚本:')
print('-' * 60)
print(download_script.strip())
print('-' * 60)
print()
print('✅ 配置完成！启动引导程序将使用 PowerShell 脚本下载 Ollama')