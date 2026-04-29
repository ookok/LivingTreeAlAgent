"""
远程代操作处理器
Remote Assistance Handler

通过DataChannel传输操作指令，卖家远程执行脚本/命令
"""

from typing import Dict, Any, Optional, List
import asyncio
import logging
import time
import uuid
import json
import os
import subprocess

from .base import BaseServiceHandler, HandlerConfig, HandlerCapability

logger = logging.getLogger(__name__)


class RemoteAssistHandler(BaseServiceHandler):
    """
    远程代操作处理器

    功能:
    - 屏幕共享 (查看买家屏幕)
    - 接收操作指令 (键盘/鼠标)
    - 执行本地脚本/命令
    - 白名单安全控制
    """

    def __init__(self, config: Optional[HandlerConfig] = None):
        if config is None:
            config = HandlerConfig(
                max_concurrent=1,
                capabilities=[
                    HandlerCapability.DATACHANNEL.value,
                    HandlerCapability.EXECUTION.value,
                    HandlerCapability.SCREEN_SHARE.value,
                ]
            )
        super().__init__(config)

        # 命令白名单
        self._allowed_commands = {
            # 文档处理
            "convert_docx_to_pdf": ["python", "-m", "scripts.doc_converter", "--to", "pdf"],
            "convert_pdf_to_docx": ["python", "-m", "scripts.doc_converter", "--to", "docx"],
            "merge_pdf": ["python", "-m", "scripts.pdf_merger"],
            "split_pdf": ["python", "-m", "scripts.pdf_splitter"],

            # 格式转换
            "convert_image": ["python", "-m", "scripts.image_converter"],
            "compress_image": ["python", "-m", "scripts.image_compress"],

            # 系统信息
            "system_info": ["python", "-m", "scripts.system_info"],
            "disk_usage": ["df", "-h"],
        }

        # 执行中的命令
        self._running_commands: Dict[str, asyncio.subprocess.Process] = {}

        # 会话数据
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def service_type(self) -> str:
        return "remote_assist"

    async def create_session(
        self,
        listing_id: str,
        seller_id: str,
        buyer_id: str,
        allowed_operations: List[str] = None,
        **kwargs
    ) -> str:
        """创建远程协助会话"""
        session_id = f"ra_{uuid.uuid4().hex[:12]}"

        room_id = f"ra_{uuid.uuid4().hex[:8]}"
        room_password = str(uuid.uuid4().hex[:6])

        if allowed_operations is None:
            allowed_operations = list(self._allowed_commands.keys())

        session_data = {
            "listing_id": listing_id,
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "room_id": room_id,
            "room_password": room_password,
            "allowed_operations": allowed_operations,
            "is_viewing": False,
            "created_at": time.time(),
            "last_heartbeat": {},
            "command_log": [],
        }

        self._sessions[session_id] = session_data

        logger.info(f"[RemoteAssist] Created session {session_id} for seller {seller_id}")
        return session_id

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """加入远程协助会话"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        return {
            "session_id": session_id,
            "room_id": session["room_id"],
            "room_password": session["room_password"],
            "allowed_operations": session["allowed_operations"],
            "ice_servers": kwargs.get("ice_servers", []),
        }

    async def end_session(self, session_id: str) -> None:
        """结束远程协助"""
        if session_id not in self._sessions:
            return

        # 终止所有运行中的命令
        for cmd_id in list(self._running_commands.keys()):
            if cmd_id.startswith(session_id):
                await self._kill_command(cmd_id)

        del self._sessions[session_id]
        logger.info(f"[RemoteAssist] Ended session {session_id}")

    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """处理心跳"""
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 检查对方心跳
        other_id = session["seller_id"] if user_id == session["buyer_id"] else session["buyer_id"]
        last_hb = session["last_heartbeat"].get(other_id, 0)

        if time.time() - last_hb > self.config.heartbeat_timeout_seconds:
            return False

        return True

    async def execute_command(
        self,
        session_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行远程命令

        Args:
            session_id: 会话ID
            command: 命令ID (必须在白名单中)
            parameters: 命令参数

        Returns:
            执行结果
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]

        # 检查命令是否在白名单
        if command not in session["allowed_operations"]:
            return {
                "success": False,
                "error": f"Command '{command}' is not allowed",
            }

        if command not in self._allowed_commands:
            return {
                "success": False,
                "error": f"Command '{command}' not found",
            }

        # 获取命令模板
        cmd_template = self._allowed_commands[command]
        parameters = parameters or {}

        # 构建命令
        cmd_list = cmd_template.copy()
        for key, value in parameters.items():
            cmd_list.extend([f"--{key}", str(value)])

        cmd_id = f"{session_id}_{uuid.uuid4().hex[:6]}"

        try:
            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self._running_commands[cmd_id] = process

            # 异步等待结果
            asyncio.create_task(self._wait_for_command(cmd_id, session_id, command, cmd_list))

            return {
                "success": True,
                "cmd_id": cmd_id,
                "command": command,
                "status": "running",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _wait_for_command(
        self,
        cmd_id: str,
        session_id: str,
        command: str,
        cmd_list: List[str]
    ) -> None:
        """等待命令完成"""
        process = self._running_commands.get(cmd_id)
        if not process:
            return

        try:
            stdout, stderr = await process.communicate()

            result = {
                "cmd_id": cmd_id,
                "command": command,
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
            }

            # 记录到会话日志
            if session_id in self._sessions:
                self._sessions[session_id]["command_log"].append(result)

            logger.info(f"[RemoteAssist] Command {cmd_id} completed: {process.returncode}")

        except Exception as e:
            logger.error(f"[RemoteAssist] Command {cmd_id} error: {e}")

        finally:
            if cmd_id in self._running_commands:
                del self._running_commands[cmd_id]

    async def _kill_command(self, cmd_id: str) -> bool:
        """终止命令"""
        process = self._running_commands.get(cmd_id)
        if not process:
            return False

        try:
            process.terminate()
            await process.wait()
            del self._running_commands[cmd_id]
            return True
        except Exception:
            return False

    async def get_command_result(self, cmd_id: str) -> Optional[Dict[str, Any]]:
        """获取命令结果"""
        for session in self._sessions.values():
            for log in session.get("command_log", []):
                if log.get("cmd_id") == cmd_id:
                    return log
        return None

    async def on_session_data(self, session_id: str, user_id: str, data: bytes) -> Optional[bytes]:
        """
        处理DataChannel数据

        期望格式:
        - 执行命令: {"type": "execute", "command": "convert_docx_to_pdf", "parameters": {...}}
        - 命令结果: {"type": "result", "cmd_id": "...", "returncode": 0, "stdout": "..."}
        """
        try:
            msg = json.loads(data.decode("utf-8"))

            if msg.get("type") == "execute":
                result = await self.execute_command(
                    session_id=session_id,
                    command=msg.get("command"),
                    parameters=msg.get("parameters"),
                )
                return json.dumps({
                    "type": "execute_ack",
                    **result
                }).encode("utf-8")

            elif msg.get("type") == "result":
                # 命令完成通知
                return json.dumps({
                    "type": "command_completed",
                    "cmd_id": msg.get("cmd_id"),
                    "returncode": msg.get("returncode"),
                }).encode("utf-8")

        except json.JSONDecodeError:
            pass

        return None