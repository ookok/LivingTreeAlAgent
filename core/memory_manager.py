"""
记忆管理器
参考 hermes-agent 的双层记忆架构
- 文件层：MEMORY.md（长期记忆）、USER.md（用户画像）
"""

import os
import re
from pathlib import Path
from typing import Optional


def _get_hermes_dir() -> Path:
    p = Path.home() / ".hermes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_memory_dir() -> Path:
    p = _get_hermes_dir() / "memory"
    p.mkdir(parents=True, exist_ok=True)
    return p


class MemoryManager:
    """
    记忆管理：
    - MEMORY.md：Agent 长期记忆（跨会话积累）
    - USER.md：用户画像和偏好
    """

    def __init__(self):
        self._mem_dir = _get_memory_dir()
        self._mem_file = self._mem_dir / "MEMORY.md"
        self._user_file = _get_hermes_dir() / "USER.md"
        self._ensure_files()

    def _ensure_files(self):
        if not self._mem_file.exists():
            self._mem_file.write_text(
                "# Hermes Memory\n\n> 这里是 Hermes 的长期记忆。每次会话结束后，重要信息会自动追加到这里。\n\n",
                encoding="utf-8"
            )
        if not self._user_file.exists():
            self._user_file.write_text(
                "# User Profile\n\n> 用户信息将在此记录。\n\n## 基本信息\n- 姓名：\n- 偏好：\n- 常用语言：中文\n\n## 项目背景\n\n",
                encoding="utf-8"
            )

    # ── 读取 ────────────────────────────────────────────────────

    def get_memory(self) -> str:
        """获取全部记忆文本"""
        if self._mem_file.exists():
            return self._mem_file.read_text(encoding="utf-8")
        return ""

    def get_user_profile(self) -> str:
        """获取用户画像"""
        if self._user_file.exists():
            return self._user_file.read_text(encoding="utf-8")
        return ""

    def get_combined_context(self) -> str:
        """获取合并后的上下文（供系统提示使用）"""
        mem = self.get_memory()
        user = self.get_user_profile()
        parts = []
        if mem.strip():
            parts.append(f"## 长期记忆\n{mem}")
        if user.strip():
            parts.append(f"## 用户画像\n{user}")
        return "\n\n".join(parts)

    # ── 写入 ────────────────────────────────────────────────────

    def append_memory(self, text: str):
        """追加记忆（追加到 MEMORY.md）"""
        if not text.strip():
            return
        timestamp = self._timestamp()
        entry = f"\n\n---\n**[{timestamp}]**\n\n{text.strip()}\n"
        self._mem_file.write_text(
            self._mem_file.read_text(encoding="utf-8") + entry,
            encoding="utf-8"
        )

    def update_user_profile(self, section: str, value: str):
        """更新用户画像中的特定 section"""
        content = self.get_user_profile()
        # 简单替换：匹配 ## section 标题到下一个 ## 之间的内容
        pattern = rf"(## {re.escape(section)}\s*\n)(.*?)(\n## )"
        replacement = f"## {section}\n{value}\n\\3"
        new_content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)
        if new_content == content:
            # 找不到则追加
            new_content += f"\n## {section}\n{value}\n"
        self._user_file.write_text(new_content, encoding="utf-8")

    def save_session_memory(self, session_summary: str, important_facts: list[str] | None = None):
        """
        保存会话记忆（会话结束时由 Agent 调用）
        - session_summary：会话摘要
        - important_facts：重要事实列表
        """
        parts = [f"## 会话摘要\n{session_summary}"]
        if important_facts:
            parts.append(f"## 关键事实\n" + "\n".join(f"- {f}" for f in important_facts))
        self.append_memory("\n\n".join(parts))

    # ── 工具 ────────────────────────────────────────────────────

    def read_memory_tool(self, context: dict) -> dict:
        """read_memory 工具处理器"""
        return {"success": True, "memory": self.get_memory()}

    def write_memory_tool(self, context: dict, content: str) -> dict:
        """write_memory 工具处理器"""
        self.append_memory(content)
        return {"success": True, "message": "记忆已保存"}

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")
