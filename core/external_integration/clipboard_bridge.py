"""
剪贴板桥接器 - 实现无感知调用
==============================

核心思路：
1. 监控剪贴板内容变化
2. 智能检测用户意图（如复制了一段文字）
3. 在后台调用 AI OS 处理
4. 提供快捷操作（如快捷键替换、生成侧边栏建议）

用户场景：
- 用户在 Word 中选中一段文字，复制
- 剪贴板监控检测到这是"文档内容"
- AI OS 自动分析并提供：摘要/润色/翻译选项
- 用户按 Ctrl+Shift+A 插入摘要，Ctrl+Shift+P 润色

这种方式对 Office/WPS 完全无侵入，用户无感知！
"""

import time
import threading
from typing import Optional, Callable, Dict, Any, List

# pyperclip 可选依赖
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    pyperclip = None
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class ClipboardAction(Enum):
    """剪贴板操作"""
    COPY = "copy"
    CUT = "cut"
    PASTE = "paste"


class SuggestionType(Enum):
    """建议类型"""
    SUMMARIZE = ("summarize", "Ctrl+Shift+S", "生成摘要")
    POLISH = ("polish", "Ctrl+Shift+P", "润色")
    TRANSLATE = ("translate", "Ctrl+Shift+T", "翻译")
    CORRECT = ("correct", "Ctrl+Shift+C", "纠正错别字")
    SEARCH = ("search", "Ctrl+Shift+Q", "知识库查询")

    def __init__(self, id: str, shortcut: str, label: str):
        self.id = id
        self.shortcut = shortcut
        self.label = label


@dataclass
class ClipboardEntry:
    """剪贴板条目"""
    content: str
    timestamp: float
    action: ClipboardAction
    char_count: int
    suggestions: List[SuggestionType] = field(default_factory=list)
    processed_result: Optional[str] = None


class ClipboardBridge:
    """
    剪贴板桥接器

    监控剪贴板，智能检测意图，提供快捷操作建议
    """

    def __init__(
        self,
        poll_interval: float = 0.5,  # 轮询间隔（秒）
        min_chars: int = 20,  # 最小字符数才处理
        max_chars: int = 10000,  # 最大字符数
    ):
        self.poll_interval = poll_interval
        self.min_chars = min_chars
        self.max_chars = max_chars

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content = ""
        self._last_hash = ""

        # 回调函数
        self._callbacks: Dict[str, Callable] = {
            'on_copy': None,
            'on_suggestion': None,
            'on_result': None,
        }

        # 历史记录（保留最近 50 条）
        self._history: deque = deque(maxlen=50)

        # 智能检测规则
        self._intent_patterns = {
            'long_text': (lambda c: len(c) > 500, [SuggestionType.SUMMARIZE]),
            'formal_text': (lambda c: any(w in c for w in ['请', '贵司', '兹', '特此']), [SuggestionType.POLISH, SuggestionType.CORRECT]),
            'english': (lambda c: len([w for w in c.split() if w.isascii()]) > len(c.split()) * 0.3, [SuggestionType.TRANSLATE]),
            'numbers': (lambda c: any(cnt in c for cnt in ['%', '元', '万', '亿']) and len(c) < 200, [SuggestionType.ANALYZE]),
        }

    def start(self):
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[ClipboardBridge] 已启动剪贴板监控")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        print("[ClipboardBridge] 已停止剪贴板监控")

    def register_callback(self, event: str, callback: Callable):
        """注册回调"""
        if event in self._callbacks:
            self._callbacks[event] = callback

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self._check_clipboard()
            except Exception as e:
                print(f"[ClipboardBridge] 监控错误: {e}")
            time.sleep(self.poll_interval)

    def _check_clipboard(self):
        """检查剪贴板"""
        if not PYPERCLIP_AVAILABLE:
            return

        try:
            content = pyperclip.paste()

            # 忽略空内容或相同内容
            if not content or content == self._last_content:
                return

            # 忽略非文本内容
            if not isinstance(content, str):
                return

            self._last_content = content
            content_hash = hash(content)

            # 忽略相同内容
            if content_hash == self._last_hash:
                return
            self._last_hash = content_hash

            # 长度检查
            if len(content) < self.min_chars or len(content) > self.max_chars:
                return

            # 检测意图并创建条目
            entry = self._process_content(content)
            self._history.append(entry)

            # 触发回调
            if self._callbacks['on_copy']:
                self._callbacks['on_copy'](entry)

        except Exception as e:
            # pyperclip 可能不支持某些环境
            pass

    def _process_content(self, content: str) -> ClipboardEntry:
        """处理内容，检测意图"""
        entry = ClipboardEntry(
            content=content,
            timestamp=time.time(),
            action=ClipboardAction.COPY,
            char_count=len(content),
        )

        # 智能检测
        for name, (check_fn, suggestions) in self._intent_patterns.items():
            if check_fn(content):
                entry.suggestions.extend(suggestions)

        # 默认建议
        if not entry.suggestions:
            entry.suggestions = [SuggestionType.SEARCH]

        # 去重
        entry.suggestions = list(dict.fromkeys(entry.suggestions))

        return entry

    def get_last_entry(self) -> Optional[ClipboardEntry]:
        """获取最后一条记录"""
        if self._history:
            return self._history[-1]
        return None

    def get_history(self, limit: int = 10) -> List[ClipboardEntry]:
        """获取历史记录"""
        return list(self._history)[-limit:]

    def process_action(self, action: SuggestionType) -> Optional[str]:
        """
        处理用户选择的操作

        Args:
            action: 用户选择的操作类型

        Returns:
            处理结果
        """
        entry = self.get_last_entry()
        if not entry:
            return None

        # TODO: 调用 AI OS 处理
        result = self._mock_process(entry.content, action)
        entry.processed_result = result

        # 触发回调
        if self._callbacks['on_result']:
            self._callbacks['on_result'](action, result)

        return result

    def _mock_process(self, content: str, action: SuggestionType) -> str:
        """模拟处理（实际应调用 AI OS）"""
        if action == SuggestionType.SUMMARIZE:
            return f"[摘要] {content[:100]}..."
        elif action == SuggestionType.POLISH:
            return f"[润色] {content}"
        elif action == SuggestionType.TRANSLATE:
            return f"[翻译] {content[:50]}..."
        elif action == SuggestionType.CORRECT:
            return f"[已纠正] {content}"
        elif action == SuggestionType.SEARCH:
            return f"[知识库] 相关内容..."
        return content

    def copy_to_clipboard(self, text: str):
        """写入剪贴板"""
        if PYPERCLIP_AVAILABLE:
            pyperclip.copy(text)
        else:
            print("[ClipboardBridge] pyperclip not available, skipping clipboard write")

    def show_suggestions(self) -> List[Dict[str, str]]:
        """获取当前建议列表（用于 UI 显示）"""
        entry = self.get_last_entry()
        if not entry:
            return []

        return [
            {
                "type": s.id,
                "shortcut": s.shortcut,
                "label": s.label,
            }
            for s in entry.suggestions
        ]


# ============== 快捷键全局监听 ==============

class GlobalHotkeyBridge:
    """
    全局快捷键桥接

    注册全局快捷键，让用户在任意应用中触发 AI OS 操作
    """

    # 默认快捷键
    DEFAULT_HOTKEYS = {
        'ctrl+shift+s': 'summarize',
        'ctrl+shift+p': 'polish',
        'ctrl+shift+t': 'translate',
        'ctrl+shift+c': 'correct',
        'ctrl+shift+q': 'query',
    }

    def __init__(self, clipboard_bridge: ClipboardBridge):
        self.clipboard_bridge = clipboard_bridge
        self._running = False
        self._hotkeys: Dict[str, str] = self.DEFAULT_HOTKEYS.copy()

        # 注册回调
        self.clipboard_bridge.register_callback(
            'on_result',
            self._on_result
        )

    def register_hotkey(self, key_combo: str, action: str):
        """
        注册快捷键

        Args:
            key_combo: 快捷键组合，如 'ctrl+shift+s'
            action: 操作类型
        """
        self._hotkeys[key_combo.lower()] = action

    def start(self):
        """启动快捷键监听"""
        # TODO: 使用 pynput 或 keyboard 库实现全局监听
        # 这里先打印提示
        print("[GlobalHotkeyBridge] 快捷键已配置:")
        for combo, action in self._hotkeys.items():
            print(f"  {combo.upper().replace('+', ' + ')} -> {action}")

    def stop(self):
        """停止快捷键监听"""
        self._running = False

    def _on_result(self, action: SuggestionType, result: str):
        """处理结果回调"""
        # 将结果复制到剪贴板
        self.clipboard_bridge.copy_to_clipboard(result)
        print(f"[GlobalHotkeyBridge] 结果已复制到剪贴板")


# ============== 便捷函数 ==============

_bridge_instance: Optional[ClipboardBridge] = None


def get_clipboard_bridge() -> ClipboardBridge:
    """获取剪贴板桥接器单例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ClipboardBridge()
    return _bridge_instance


def start_clipboard_monitoring():
    """启动剪贴板监控（快捷方式）"""
    bridge = get_clipboard_bridge()
    bridge.start()
    return bridge


# ============== Python for Office 集成示例 ==============
# Microsoft Office 和 WPS 都支持 Python，以下是集成示例：
#
# === Word/VBA 调用示例 ===
# Sub CallAIOS()
#     Dim selectedText As String
#     selectedText = Selection.Text
#     Dim http As Object
#     Set http = CreateObject("MSXML2.ServerXMLHTTP")
#     http.Open "POST", "http://127.0.0.1:8898/api/v1/summarize", False
#     http.setRequestHeader "Content-Type", "application/json"
#     http.Send "{\"text\": \"\" & selectedText & \"\"\"}"
#     Selection.Text = http.ResponseText
# End Sub
#
# === Python for Word ===
# pip install python-docx requests
# from docx import Document
# import requests
# def summarize_selection():
#     doc = Document()
#     pass
#
# === WPS Python 宏 ===
# import requests
# def summarize():
#     selection = wps.Selection()
#     text = selection.Text
#     response = requests.post(
#         'http://127.0.0.1:8898/api/v1/summarize',
#         json={'text': text}
#     )
#     result = response.json()
#     selection.Text = result['data']['summary']
