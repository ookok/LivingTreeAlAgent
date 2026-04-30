#!/usr/bin/env python
"""
详细调试样式表解析问题
"""

import sys
sys.path.insert(0, 'client/src')

def debug_stylesheet():
    """详细调试样式表解析"""
    from presentation.theme.dracula_theme import get_dracula_stylesheet, DRACULA
    
    print('📦 获取样式表...')
    stylesheet = get_dracula_stylesheet()
    
    # 检查样式表长度
    print(f'\n📋 样式表长度: {len(stylesheet)} 字符')
    print(f'📋 样式表行数: {stylesheet.count("\\n")} 行')
    
    # 逐行检查可能的问题
    lines = stylesheet.split('\n')
    for i, line in enumerate(lines):
        # 检查空行
        if not line.strip():
            continue
            
        # 检查是否有未闭合的字符串
        if line.count('"') % 2 != 0 or line.count("'") % 2 != 0:
            print(f'⚠️ 第{i+1}行可能有未闭合的字符串: {line[:60]}...')
        
        # 检查可能的语法错误
        if ';' in line and line.strip()[-1] != ';' and not line.strip().endswith('}'):
            # 检查是否是属性值
            parts = line.split(':')
            if len(parts) >= 2:
                value_part = parts[1].strip()
                if not value_part.endswith(';') and not value_part.endswith('}'):
                    print(f'⚠️ 第{i+1}行可能缺少分号: {line[:60]}...')
    
    # 测试Qt解析
    from PyQt6.QtWidgets import QApplication, QWidget
    
    app = QApplication([])
    widget = QWidget()
    
    print('\n🔍 测试Qt样式表解析...')
    try:
        widget.setStyleSheet(stylesheet)
        print('✅ 样式表解析成功')
    except Exception as e:
        print(f'❌ 样式表解析失败: {e}')
        
        # 逐步测试找到问题位置
        print('\n🔍 逐步测试找到问题位置...')
        chunk_size = 500
        for i in range(0, len(stylesheet), chunk_size):
            chunk = stylesheet[:i+chunk_size]
            try:
                widget.setStyleSheet(chunk)
                print(f'   ✅ 前 {i+chunk_size} 字符正常')
            except Exception as e:
                print(f'   ❌ 在 {i+chunk_size} 字符处失败: {e}')
                print(f'   问题片段:\n{stylesheet[i:i+chunk_size]}')
                break
    
    return stylesheet

if __name__ == "__main__":
    debug_stylesheet()