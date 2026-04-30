#!/usr/bin/env python
"""
调试样式表解析问题
"""

import sys
sys.path.insert(0, 'client/src')

def debug_stylesheet():
    """调试样式表解析"""
    from presentation.theme.theme_manager import theme_manager
    from presentation.theme.dracula_theme import get_dracula_stylesheet
    
    print('📦 获取样式表...')
    stylesheet = get_dracula_stylesheet()
    
    print(f'\n📋 样式表长度: {len(stylesheet)} 字符')
    print(f'📋 样式表行数: {stylesheet.count("\\n")} 行')
    
    # 逐行检查
    lines = stylesheet.split('\n')
    for i, line in enumerate(lines):
        # 检查可能的问题
        if '#' in line and ';' not in line and i > 0:
            # 检查是否是颜色值（颜色值以#开头但不需要分号）
            parts = line.strip().split()
            if parts and parts[0] == '#':
                print(f'⚠️ 第{i+1}行可能有问题: {line[:50]}...')
    
    # 测试样式表是否能被Qt解析
    from PyQt6.QtWidgets import QApplication, QWidget
    
    app = QApplication([])
    widget = QWidget()
    
    try:
        widget.setStyleSheet(stylesheet)
        print('\n✅ 样式表解析成功')
    except Exception as e:
        print(f'\n❌ 样式表解析失败: {e}')
    
    return stylesheet

if __name__ == "__main__":
    debug_stylesheet()