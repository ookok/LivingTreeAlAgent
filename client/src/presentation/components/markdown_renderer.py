"""
Markdown渲染组件 - 优美渲染AI消息

支持将Markdown格式文本渲染为美观的富文本内容，重点突出关键信息。
"""

import re
from typing import Optional, List, Dict
from loguru import logger

from PyQt6.QtWidgets import (
    QWidget, QLabel, QTextEdit, QFrame, QVBoxLayout,
    QHBoxLayout, QScrollArea, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QBrush


class MarkdownRenderer:
    """
    Markdown渲染器
    
    支持的Markdown特性：
    - 标题 (# ~ ######)
    - 粗体/斜体 (**text** / *text*)
    - 链接 ([text](url))
    - 代码块 (```code```)
    - 内联代码 (`code`)
    - 列表 (有序/无序)
    - 表格
    - 引用 (> text)
    - 分割线 (---)
    """
    
    link_clicked = pyqtSignal(str)  # 链接点击信号
    
    def __init__(self):
        self._logger = logger.bind(component="MarkdownRenderer")
    
    def render(self, markdown_text: str, parent: QWidget = None) -> QWidget:
        """
        渲染Markdown文本为Qt控件
        
        Args:
            markdown_text: Markdown格式文本
            parent: 父控件
            
        Returns:
            渲染后的控件
        """
        # 创建滚动容器
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 解析并渲染各部分
        blocks = self._parse_markdown(markdown_text)
        
        for block in blocks:
            widget = self._render_block(block, content_widget)
            if widget:
                layout.addWidget(widget)
        
        scroll_area.setWidget(content_widget)
        
        return scroll_area
    
    def _parse_markdown(self, text: str) -> List[Dict[str, str]]:
        """解析Markdown文本为块列表"""
        blocks = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 标题
            if line.startswith('#'):
                level = min(len(line) - len(line.lstrip('#')), 6)
                content = line.lstrip('#').strip()
                blocks.append({"type": "heading", "level": level, "content": content})
                i += 1
                continue
            
            # 代码块
            if line.startswith('```'):
                code = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code.append(lines[i])
                    i += 1
                blocks.append({"type": "code", "content": '\n'.join(code)})
                i += 1
                continue
            
            # 引用
            if line.startswith('>'):
                quote_lines = []
                while i < len(lines) and (lines[i].startswith('>') or lines[i].strip() == ''):
                    if lines[i].startswith('>'):
                        quote_lines.append(lines[i][1:].strip())
                    i += 1
                blocks.append({"type": "quote", "content": '\n'.join(quote_lines)})
                continue
            
            # 分割线
            if re.match(r'^[-*_]{3,}$', line):
                blocks.append({"type": "hr"})
                i += 1
                continue
            
            # 表格
            if i + 2 < len(lines) and line.startswith('|') and lines[i+1].startswith('|'):
                header = line.split('|')[1:-1]
                separator = lines[i+1]
                rows = []
                
                j = i + 2
                while j < len(lines) and lines[j].startswith('|'):
                    rows.append(lines[j].split('|')[1:-1])
                    j += 1
                
                blocks.append({
                    "type": "table",
                    "header": [h.strip() for h in header],
                    "rows": [[cell.strip() for cell in row] for row in rows]
                })
                i = j
                continue
            
            # 列表项
            if line.startswith(('-', '*', '+')) or re.match(r'^\d+[\.\uff0e]', line):
                list_items = []
                while i < len(lines):
                    current_line = lines[i]
                    if current_line.startswith(('-', '*', '+')):
                        list_items.append({"type": "unordered", "content": current_line[1:].strip()})
                        i += 1
                    elif re.match(r'^\d+[\.\uff0e]', current_line):
                        match = re.match(r'^(\d+)[\.\uff0e]\s*(.*)', current_line)
                        list_items.append({"type": "ordered", "content": match.group(2)})
                        i += 1
                    elif current_line.strip() == '':
                        i += 1
                    else:
                        break
                
                blocks.append({"type": "list", "items": list_items})
                continue
            
            # 段落
            if line.strip():
                paragraph = []
                while i < len(lines) and lines[i].strip():
                    paragraph.append(lines[i])
                    i += 1
                blocks.append({"type": "paragraph", "content": '\n'.join(paragraph)})
            else:
                i += 1
        
        return blocks
    
    def _render_block(self, block: Dict, parent: QWidget) -> Optional[QWidget]:
        """渲染单个块"""
        block_type = block.get("type")
        
        if block_type == "heading":
            return self._render_heading(block, parent)
        elif block_type == "paragraph":
            return self._render_paragraph(block, parent)
        elif block_type == "code":
            return self._render_code(block, parent)
        elif block_type == "quote":
            return self._render_quote(block, parent)
        elif block_type == "hr":
            return self._render_hr(parent)
        elif block_type == "table":
            return self._render_table(block, parent)
        elif block_type == "list":
            return self._render_list(block, parent)
        
        return None
    
    def _render_heading(self, block: Dict, parent: QWidget) -> QLabel:
        """渲染标题"""
        level = block.get("level", 1)
        content = block.get("content", "")
        
        label = QLabel(content, parent)
        
        # 根据级别设置样式
        font_sizes = [24, 20, 18, 16, 14, 12]
        font_size = font_sizes[min(level - 1, 5)]
        
        label.setStyleSheet(f"""
            QLabel {{
                font-size: {font_size}px;
                font-weight: bold;
                color: #1e40af;
                margin-top: 12px;
                margin-bottom: 4px;
            }}
        """)
        
        return label
    
    def _render_paragraph(self, block: Dict, parent: QWidget) -> QTextEdit:
        """渲染段落（支持内联格式）"""
        content = block.get("content", "")
        
        text_edit = QTextEdit(parent)
        text_edit.setReadOnly(True)
        text_edit.setFrameStyle(QFrame.Shape.NoFrame)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                font-size: 14px;
                color: #e0e0e0;
                padding: 0;
                margin: 0;
            }
        """)
        
        # 解析内联格式
        formatted_text = self._parse_inline_formatting(content)
        text_edit.setHtml(formatted_text)
        
        # 自适应高度
        text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_edit.setMaximumHeight(text_edit.document().size().height() + 20)
        
        return text_edit
    
    def _parse_inline_formatting(self, text: str) -> str:
        """解析内联格式为HTML"""
        # 转义特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        # 粗体 **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #2563eb;">\1</strong>', text)
        
        # 斜体 *text*
        text = re.sub(r'(?<!\*)\*(.+?)\*(?!\*)', r'<em>\1</em>', text)
        
        # 内联代码 `code`
        text = re.sub(r'`(.+?)`', r'<code style="background-color: #1e293b; padding: 2px 6px; border-radius: 4px; font-family: monospace;">\1</code>', text)
        
        # 链接 [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #3b82f6; text-decoration: underline;">\1</a>', text)
        
        # 表情符号保持原样
        # 重点标记 ==text==
        text = re.sub(r'==(.+?)==', r'<mark style="background-color: #fef08a; color: #1e293b; padding: 2px 4px; border-radius: 4px;">\1</mark>', text)
        
        return text
    
    def _render_code(self, block: Dict, parent: QWidget) -> QFrame:
        """渲染代码块"""
        content = block.get("content", "")
        
        frame = QFrame(parent)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 8px;
                padding: 12px;
                margin: 8px 0;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                color: #e2e8f0;
                border: none;
            }
        """)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        layout.addWidget(text_edit)
        
        # 添加复制按钮
        copy_btn = QPushButton("复制")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                align-self: flex-end;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(content))
        layout.addWidget(copy_btn)
        
        return frame
    
    def _render_quote(self, block: Dict, parent: QWidget) -> QFrame:
        """渲染引用"""
        content = block.get("content", "")
        
        frame = QFrame(parent)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e3a5f;
                border-left: 4px solid #3b82f6;
                border-radius: 0 8px 8px 0;
                padding: 12px 16px;
                margin: 8px 0;
            }
        """)
        
        label = QLabel(content)
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #93c5fd;
                font-style: italic;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.addWidget(label)
        
        return frame
    
    def _render_hr(self, parent: QWidget) -> QFrame:
        """渲染分割线"""
        line = QFrame(parent)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("""
            QFrame {
                color: #3d3d54;
                margin: 16px 0;
            }
        """)
        return line
    
    def _render_table(self, block: Dict, parent: QWidget) -> QTableWidget:
        """渲染表格"""
        header = block.get("header", [])
        rows = block.get("rows", [])
        
        table = QTableWidget(len(rows), len(header), parent)
        table.setHorizontalHeaderLabels(header)
        
        # 设置样式
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1e293b;
                border-radius: 8px;
                border: 1px solid #3d3d54;
            }
            QTableWidget::item {
                padding: 8px 12px;
                color: #e0e0e0;
                border-bottom: 1px solid #3d3d54;
            }
            QTableWidget::item:selected {
                background-color: #3b82f6;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #3b82f6;
            }
        """)
        
        # 填充数据
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                item = QTableWidgetItem(cell)
                table.setItem(i, j, item)
        
        table.resizeColumnsToContents()
        
        # 限制最大宽度
        max_width = min(table.horizontalHeader().length() + 40, 600)
        table.setMaximumWidth(max_width)
        
        return table
    
    def _render_list(self, block: Dict, parent: QWidget) -> QListWidget:
        """渲染列表"""
        items = block.get("items", [])
        
        list_widget = QListWidget(parent)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 4px 8px;
                color: #e0e0e0;
                font-size: 14px;
            }
        """)
        
        for item in items:
            content = item.get("content", "")
            list_item = QListWidgetItem(content)
            list_widget.addItem(list_item)
        
        return list_widget
    
    def _copy_to_clipboard(self, text: str):
        """复制文本到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
    
    def render_to_html(self, markdown_text: str) -> str:
        """
        将Markdown渲染为HTML字符串
        
        Args:
            markdown_text: Markdown格式文本
            
        Returns:
            HTML字符串
        """
        blocks = self._parse_markdown(markdown_text)
        html_parts = []
        
        for block in blocks:
            html = self._block_to_html(block)
            if html:
                html_parts.append(html)
        
        return '\n'.join(html_parts)
    
    def _block_to_html(self, block: Dict) -> Optional[str]:
        """将块转换为HTML"""
        block_type = block.get("type")
        
        if block_type == "heading":
            level = block.get("level", 1)
            content = self._parse_inline_formatting(block.get("content", ""))
            return f'<h{level} style="color: #1e40af; margin-top: 12px; margin-bottom: 4px;">{content}</h{level}>'
        
        elif block_type == "paragraph":
            content = self._parse_inline_formatting(block.get("content", ""))
            return f'<p style="font-size: 14px; color: #e0e0e0; margin: 4px 0;">{content}</p>'
        
        elif block_type == "code":
            content = block.get("content", "").replace('<', '&lt;').replace('>', '&gt;')
            return f'''
                <div style="background-color: #1e293b; border-radius: 8px; padding: 12px; margin: 8px 0;">
                    <pre style="font-family: monospace; font-size: 13px; color: #e2e8f0; margin: 0;">{content}</pre>
                </div>
            '''
        
        elif block_type == "quote":
            content = self._parse_inline_formatting(block.get("content", ""))
            return f'<blockquote style="background-color: #1e3a5f; border-left: 4px solid #3b82f6; border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 8px 0; font-style: italic; color: #93c5fd;">{content}</blockquote>'
        
        elif block_type == "hr":
            return '<hr style="border: none; border-top: 1px solid #3d3d54; margin: 16px 0;">'
        
        elif block_type == "table":
            header = block.get("header", [])
            rows = block.get("rows", [])
            
            header_html = ''.join([f'<th style="background-color: #0f172a; color: #94a3b8; padding: 8px 12px; border-bottom: 2px solid #3b82f6;">{h}</th>' for h in header])
            rows_html = ''
            
            for row in rows:
                cells_html = ''.join([f'<td style="padding: 8px 12px; color: #e0e0e0; border-bottom: 1px solid #3d3d54;">{cell}</td>' for cell in row])
                rows_html += f'<tr>{cells_html}</tr>'
            
            return f'''
                <table style="background-color: #1e293b; border-radius: 8px; border: 1px solid #3d3d54; margin: 8px 0;">
                    <thead><tr>{header_html}</tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            '''
        
        elif block_type == "list":
            items = block.get("items", [])
            list_type = "ol" if items and items[0].get("type") == "ordered" else "ul"
            
            items_html = ''
            for item in items:
                content = self._parse_inline_formatting(item.get("content", ""))
                items_html += f'<li style="padding: 4px 0; color: #e0e0e0;">{content}</li>'
            
            return f'<{list_type} style="margin: 4px 0; padding-left: 24px;">{items_html}</{list_type}>'
        
        return None