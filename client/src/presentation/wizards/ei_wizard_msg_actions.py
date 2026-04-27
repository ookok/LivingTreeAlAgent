"""
EIWizard 消息操作（复制、删除、重新发送）
==========================================
P2 功能：添加消息操作 - 复制、删除、重新发送
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QMenu, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QPoint
from PySide6.QtGui import QAction, QCursor, QClipboard
import logging

logger = logging.getLogger(__name__)


class MessageActions:
    """消息操作管理器（工具类）"""
    
    @staticmethod
    def show_context_menu(bubble_widget, event, message_data: dict):
        """
        显示消息上下文菜单（右键菜单）
        
        Args:
            bubble_widget: 消息气泡组件
            event: 鼠标事件
            message_data: 消息数据字典，包含：
                - 'role': 'user' 或 'assistant'
                - 'content': 消息内容
                - 'type': 'text', 'image', 'file', 'video', 'audio'
                - 'path': 文件路径（如果是文件/图片/视频/音频）
        """
        menu = QMenu(bubble_widget)
        
        # 复制操作（对所有消息类型都可用）
        copy_action = QAction("📋 复制内容", bubble_widget)
        copy_action.triggered.connect(lambda: MessageActions.copy_message(message_data))
        menu.addAction(copy_action)
        
        # 删除操作
        delete_action = QAction("🗑️ 删除消息", bubble_widget)
        delete_action.triggered.connect(lambda: MessageActions.delete_message(bubble_widget, message_data))
        menu.addAction(delete_action)
        
        # 重新发送（仅对用户消息可用）
        if message_data.get('role') == 'user':
            resend_action = QAction("🔁 重新发送", bubble_widget)
            resend_action.triggered.connect(lambda: MessageActions.resend_message(bubble_widget, message_data))
            menu.addAction(resend_action)
        
        # 打开文件（对文件/图片/视频/音频消息可用）
        if message_data.get('type') in ['image', 'file', 'video', 'audio'] and message_data.get('path'):
            menu.addSeparator()
            open_action = QAction("📂 打开文件", bubble_widget)
            open_action.triggered.connect(lambda: MessageActions.open_file(message_data.get('path')))
            menu.addAction(open_action)
        
        # 显示菜单
        menu.exec(QCursor.pos())
    
    @staticmethod
    def copy_message(message_data: dict):
        """
        复制消息内容到剪贴板
        
        Args:
            message_data: 消息数据字典
        """
        try:
            content = message_data.get('content', '')
            
            # 对于文件/图片消息，复制文件路径或描述
            if message_data.get('type') in ['image', 'file', 'video', 'audio']:
                path = message_data.get('path', '')
                if path:
                    content = f"[{message_data.get('type').upper()}: {path}]"
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            
            logger.info(f"消息已复制: {content[:50]}...")
            
        except Exception as e:
            logger.error(f"复制消息失败: {e}")
    
    @staticmethod
    def delete_message(bubble_widget, message_data: dict):
        """
        删除消息（从 UI 和消息历史中删除）
        
        Args:
            bubble_widget: 消息气泡组件
            message_data: 消息数据字典
        """
        try:
            # 确认对话框
            msg_box = QMessageBox(bubble_widget)
            msg_box.setWindowTitle("确认删除")
            msg_box.setText("确定要删除这条消息吗？")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                # 从布局中移除气泡
                layout = bubble_widget.parentWidget().layout()
                if layout:
                    for i in range(layout.count()):
                        if layout.itemAt(i).widget() == bubble_widget:
                            layout.takeAt(i)
                            bubble_widget.deleteLater()
                            break
                
                # TODO: 从消息历史中删除
                # 这需要在 EIWizardChat 类中实现
                
                logger.info(f"消息已删除: {message_data.get('content', '')[:50]}...")
                
        except Exception as e:
            logger.error(f"删除消息失败: {e}")
    
    @staticmethod
    def resend_message(bubble_widget, message_data: dict):
        """
        重新发送消息
        
        Args:
            bubble_widget: 消息气泡组件
            message_data: 消息数据字典
        """
        try:
            content = message_data.get('content', '')
            
            # TODO: 调用 EIWizardChat 的 _send_message() 方法
            # 这需要通过信号或回调函数来实现
            
            logger.info(f"重新发送消息: {content[:50]}...")
            
            # 临时实现：打印到控制台
            print(f"[重新发送] {content}")
            
        except Exception as e:
            logger.error(f"重新发送消息失败: {e}")
    
    @staticmethod
    def open_file(file_path: str):
        """
        打开文件（使用系统默认应用）
        
        Args:
            file_path: 文件路径
        """
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            
            logger.info(f"打开文件: {file_path}")
            
        except Exception as e:
            logger.error(f"打开文件失败: {e}")


# 为 MessageBubble 添加右键菜单支持
def patch_message_bubble(bubble_class):
    """
    为 MessageBubble 类添加右键菜单支持
    
    Args:
        bubble_class: MessageBubble 类
        
    Returns:
        修改后的类
    """
    original_init = bubble_class.init_ui
    
    def new_init_ui(self):
        original_init(self)
        
        # 启用鼠标跟踪和上下文菜单策略
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # 存储消息数据（需要在创建气泡时设置）
        self._message_data = {}
    
    def _show_context_menu(self, pos):
        """显示上下文菜单"""
        if hasattr(self, '_message_data') and self._message_data:
            MessageActions.show_context_menu(self, None, self._message_data)
    
    # 替换方法
    bubble_class.init_ui = new_init_ui
    bubble_class._show_context_menu = _show_context_menu
    
    return bubble_class


# 使用示例
if __name__ == "__main__":
    # 测试代码
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    # 创建测试数据
    test_message = {
        'role': 'user',
        'content': '这是一条测试消息',
        'type': 'text'
    }
    
    # 显示上下文菜单（测试）
    print("右键菜单功能已定义，需要在实际组件中集成。")
    
    sys.exit(0)
