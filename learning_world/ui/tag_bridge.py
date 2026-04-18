"""
标签点击桥
JS-Python 通信桥
"""

from PyQt6.QtCore import QObject, pyqtSlot
import json


class TagClickBridge(QObject):
    """JS-Python 通信桥"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
    
    @pyqtSlot(str, str)
    def onTagClick(self, tag_text: str, tag_data_json: str):
        """处理标签点击"""
        try:
            tag_data = json.loads(tag_data_json)
        except Exception:
            tag_data = {"text": tag_text}
        
        if self.parent_widget:
            self.parent_widget.tag_clicked.emit(tag_text, tag_data)
    
    @pyqtSlot(str)
    def onSuggestionClick(self, suggestion: str):
        """处理建议问题点击"""
        if self.parent_widget:
            self.parent_widget.query_submitted.emit(suggestion)
