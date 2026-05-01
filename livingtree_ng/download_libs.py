import urllib.request
import os

# 文件下载链接
libs = {
    'vue.global.prod.js': 'https://unpkg.com/vue@3.4.21/dist/vue.global.prod.js',
    'vue-router.global.prod.js': 'https://unpkg.com/vue-router@4.3.0/dist/vue-router.global.prod.js',
    'pinia.iife.prod.js': 'https://unpkg.com/pinia@2.1.7/dist/pinia.iife.prod.js',
    'qtwebchannel.js': 'https://unpkg.com/qtwebchannel@6.6.0/dist/qtwebchannel.js',
    'mdi.css': 'https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css'
}

target_dir = 'frontend/libs'

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

print('开始下载库文件...')

for filename, url in libs.items():
    filepath = os.path.join(target_dir, filename)
    print(f'正在下载 {filename}...')
    try:
        urllib.request.urlretrieve(url, filepath)
        print(f'✅ {filename} 下载成功')
    except Exception as e:
        print(f'❌ {filename} 下载失败: {e}')

print('\n下载完成！')
