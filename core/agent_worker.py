"""
AgentWorker — 在 QThread 中直接调用本地安装的 hermes-agent AIAgent。

hermes-agent-windows 通过 pip install -e 安装到本地，这里直接 import 调用，
完全不走 HTTP，就像 cli.py 那样使用 AIAgent。
"""

import asyncio
import traceback
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


class AgentWorker(QThread):
    """
    在后台线程中运行 AIAgent.run_conversation()。
    通过 Qt 信号将 token / 工具调用事件 / 错误 推送到 UI 线程。

    信号说明
    --------
    token_received(str)
        流式 token，每次收到一个或多个字符
    tool_started(str, str)
        工具开始执行，参数：(tool_name, json_args)
    tool_finished(str, str, bool)
        工具执行完毕，参数：(tool_name, result_preview, success)
    message_done(str)
        完整助手消息，参数：(full_text)
    error_occurred(str)
        异常，参数：(error_message)
    approval_requested(str, str, str)
        需要用户审批，参数：(task_id, tool_name, args_json)
    """

    token_received     = pyqtSignal(str)
    tool_started       = pyqtSignal(str, str)
    tool_finished      = pyqtSignal(str, str, bool)
    message_done       = pyqtSignal(str)
    error_occurred     = pyqtSignal(str)
    approval_requested = pyqtSignal(str, str, str)

    def __init__(self, agent, user_message: str, conversation_history: list, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._user_message = user_message
        self._conversation_history = conversation_history
        self._approve_result: Optional[bool] = None
        self._approval_event = asyncio.Event()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def approve(self, approved: bool):
        """UI 线程调用：告知工具审批结果"""
        self._approve_result = approved
        self._approval_event.set()

    def interrupt(self):
        """UI 线程调用：中断当前会话"""
        try:
            self._agent.interrupt()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # QThread 入口
    # ------------------------------------------------------------------

    def run(self):
        """在独立线程中运行异步 Agent 循环"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async())
        except Exception as exc:
            self.error_occurred.emit(f"AgentWorker 异常: {traceback.format_exc()}")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _run_async(self):
        """
        调用 AIAgent.run_conversation()。

        hermes-agent 的 run_conversation 是一个 async generator，
        每次 yield 一个 event dict，格式参考 streaming.py / display.py。

        如果你安装的版本 API 不同（如返回 str 而非 async gen），
        在这里做适配即可，其余 UI 代码不需要改。
        """
        agent = self._agent
        full_text = []

        try:
            result = agent.run_conversation(
                self._user_message,
                conversation_history=self._conversation_history,
            )

            # ── 情况1：async generator ──────────────────────────────
            if hasattr(result, "__aiter__"):
                async for event in result:
                    await self._handle_event(event, full_text)

            # ── 情况2：普通 coroutine ────────────────────────────────
            elif asyncio.iscoroutine(result):
                final = await result
                await self._handle_event(final, full_text)

            # ── 情况3：同步返回（兜底）──────────────────────────────
            else:
                await self._handle_event(result, full_text)

        except Exception as exc:
            self.error_occurred.emit(traceback.format_exc())
            return

        self.message_done.emit("".join(full_text))

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    async def _handle_event(self, event, full_text: list):
        """
        解析 hermes-agent 的事件格式。

        事件是 dict，常见 type：
          {"type": "token",        "content": "..."}
          {"type": "tool_start",   "name": "...", "args": "..."}
          {"type": "tool_end",     "name": "...", "result": "...", "success": True}
          {"type": "approval",     "task_id": "...", "name": "...", "args": "..."}
          {"type": "content",      "content": "..."}   # 非流式完整消息
          str  —— 直接是 token 字符串（部分版本）
        """
        if event is None:
            return

        if isinstance(event, str):
            self.token_received.emit(event)
            full_text.append(event)
            return

        if not isinstance(event, dict):
            return

        etype = event.get("type", "")

        if etype == "token":
            tok = event.get("content", "")
            self.token_received.emit(tok)
            full_text.append(tok)

        elif etype in ("content", "message"):
            text = event.get("content", event.get("text", ""))
            self.token_received.emit(text)
            full_text.append(text)

        elif etype == "tool_start":
            import json
            name = event.get("name", event.get("tool", ""))
            args = event.get("args", event.get("arguments", {}))
            args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
            self.tool_started.emit(name, args_str)

        elif etype == "tool_end":
            import json
            name = event.get("name", event.get("tool", ""))
            result = event.get("result", "")
            success = bool(event.get("success", True))
            preview = str(result)[:200] if result else ""
            self.tool_finished.emit(name, preview, success)

        elif etype == "approval":
            import json
            task_id = event.get("task_id", "")
            name = event.get("name", "")
            args = event.get("args", {})
            args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
            self.approval_requested.emit(task_id, name, args_str)

            # 等待 UI 线程给出审批结果
            self._approval_event.clear()
            await self._approval_event.wait()
            approved = self._approve_result if self._approve_result is not None else True

            # 将结果回传给 agent（如果 agent 支持 approval callback）
            if hasattr(self._agent, "submit_approval"):
                self._agent.submit_approval(task_id, approved)
