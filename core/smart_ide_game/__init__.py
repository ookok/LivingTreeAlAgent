"""
智能IDE与游戏分享系统 - 统一调度器
整合代码编辑器、AI助手、调试器、游戏客户端、游戏房间等功能
"""
import asyncio
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .models import (
    LanguageType, GameType, RoomType, RoomStatus, ShareMode, SyncMode,
    IDESettings, GameSettings, UserPreferences
)
from .code_editor import CodeEditorCore, CodePosition, CompletionItem, Diagnostic, Symbol
from .ai_coding_assistant import AICodingAssistant, TaskType, AIRecommendation
from .debugger import DebuggerManager, DebugSession, PerformanceProfiler, Breakpoint
from .memory_enhanced_editor import MemoryEnhancedEditor, Snippet, ProjectMemory
from .collab_editor import CollabEditor, CollabDocument, Participant, Cursor
from .game_client import GameClient, GameConfig, GamePlayer, GameSettings as GCGameSettings
from .game_room import RoomManager, GameRoom, RoomSettings, MatchRequest
from .game_share import GameShare, ShareLink, ShareMode as SSShareMode
from .game_sync import GameSync, GameState, InputState, NetworkQualityMonitor


class SmartIDEGameSystem:
    """智能IDE与游戏分享系统核心"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/smart_ide_game")
        os.makedirs(self.storage_path, exist_ok=True)

        # IDE 组件
        self.code_editor = CodeEditorCore()
        self.ai_assistant = AICodingAssistant()
        self.debugger = DebuggerManager()
        self.memory_editor = MemoryEnhancedEditor(self.storage_path)
        self.collab_editor = CollabEditor()

        # 游戏组件
        self.game_client = GameClient()
        self.room_manager = RoomManager()
        self.game_share = GameShare(self.storage_path)
        self.game_sync = GameSync()
        self.network_monitor = NetworkQualityMonitor()

        # 用户设置
        self.ide_settings = IDESettings()
        self.game_settings = GCGameSettings()

        # 运行状态
        self._running = False
        self._event_callbacks: Dict[str, List[Callable]] = {}

    async def start(self):
        """启动系统"""
        self._running = True

        # 启动各组件
        await self.ai_assistant.start()
        await self.collab_editor.start()
        await self.room_manager.start()

        # 设置游戏分享服务器
        self.game_share.set_relay_server("https://share.hermes.local")

    async def stop(self):
        """停止系统"""
        self._running = False

        await self.ai_assistant.stop()
        await self.collab_editor.stop()
        await self.room_manager.stop()

    # ========== IDE 功能 ==========

    async def open_file(self, file_path: str) -> bool:
        """打开文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检测语言
            ext = os.path.splitext(file_path)[1]
            language_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.go': 'go',
                '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.swift': 'swift',
                '.html': 'html', '.css': 'css', '.json': 'json', '.yaml': 'yaml',
                '.md': 'markdown',
            }
            language = language_map.get(ext.lower(), 'plaintext')

            await self.code_editor.open_document(file_path, content, language)
            return True

        except Exception as e:
            print(f"Failed to open file: {e}")
            return False

    def get_completions(self, uri: str, line: int, column: int) -> List[CompletionItem]:
        """获取代码补全"""
        position = CodePosition(line=line, column=column, offset=0)
        return self.code_editor.get_completions(uri, position)

    def get_diagnostics(self, uri: str) -> List[Diagnostic]:
        """获取诊断信息"""
        return self.code_editor.get_diagnostics(uri)

    def find_symbols(self, uri: str, kind: str = None) -> List[Symbol]:
        """查找符号"""
        return self.code_editor.find_symbols(uri, kind)

    # ========== AI 助手 ==========

    async def diagnose_error(
        self,
        error_message: str,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """诊断错误"""
        return await self.ai_assistant.diagnose_error(error_message, code, language)

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: Dict[str, Any] = None
    ) -> str:
        """生成代码"""
        task = {
            "task_type": TaskType.CODE_GENERATION,
            "prompt": prompt,
            "context": {"language": language, **(context or {})}
        }
        return await self.ai_assistant.submit_task(task)

    async def analyze_performance(
        self,
        code: str,
        language: str
    ) -> List[AIRecommendation]:
        """分析性能"""
        return await self.ai_assistant.analyze_performance(code, language)

    async def generate_tests(
        self,
        code: str,
        language: str,
        framework: str = "pytest"
    ) -> List:
        """生成测试"""
        return await self.ai_assistant.generate_tests(code, language, framework)

    # ========== 调试 ==========

    async def start_debugging(
        self,
        file_path: str,
        language: str
    ) -> bool:
        """启动调试"""
        return await self.debugger.start_debugging(file_path, language)

    async def add_breakpoint(
        self,
        file: str,
        line: int,
        condition: str = None
    ) -> Optional[Breakpoint]:
        """添加断点"""
        return await self.debugger.add_breakpoint(file, line, condition)

    async def evaluate_expression(self, expression: str) -> Any:
        """计算表达式"""
        return await self.debugger.evaluate_expression(expression)

    # ========== 记忆系统 ==========

    def remember_code(
        self,
        code: str,
        context: str,
        language: str,
        tags: List[str] = None
    ):
        """记忆代码"""
        return self.memory_editor.remember_code(code, context, language, tags)

    def recall_similar(self, query: str, language: str = None) -> List:
        """回忆相似代码"""
        return self.memory_editor.recall_similar(query, language)

    def get_snippet(self, trigger: str) -> Optional[Snippet]:
        """获取代码片段"""
        return self.memory_editor.get_snippet(trigger)

    def open_project(self, project_path: str) -> ProjectMemory:
        """打开项目"""
        return self.memory_editor.open_project(project_path)

    # ========== 协同编辑 ==========

    def create_collab_document(
        self,
        title: str = "",
        content: str = "",
        language: str = "plaintext"
    ) -> CollabDocument:
        """创建协作文档"""
        return self.collab_editor.create_document(title, content, language)

    def join_collab_document(
        self,
        document_id: str,
        user_id: str,
        username: str
    ) -> Optional[CollabDocument]:
        """加入协作文档"""
        return self.collab_editor.join_document(document_id, user_id, username)

    def create_invite_link(
        self,
        document_id: str,
        created_by: str,
        role: str = "editor"
    ) -> Optional[str]:
        """创建邀请链接"""
        return self.collab_editor.create_invite_link(document_id, created_by, role)

    # ========== 游戏客户端 ==========

    async def start_game(
        self,
        game_id: str,
        config: GameConfig,
        resources: List = None
    ):
        """启动游戏"""
        await self.game_client.start(game_id)
        if resources:
            await self.game_client.load_game(config, resources)

    async def pause_game(self):
        """暂停游戏"""
        await self.game_client.pause()

    async def resume_game(self):
        """继续游戏"""
        await self.game_client.resume()

    # ========== 游戏房间 ==========

    def create_game_room(
        self,
        host_id: str,
        host_name: str,
        settings: RoomSettings
    ) -> GameRoom:
        """创建游戏房间"""
        return self.room_manager.create_room(host_id, host_name, settings)

    def join_game_room(
        self,
        room_id: str,
        user_id: str,
        username: str,
        password: str = None
    ) -> Optional[GameRoom]:
        """加入游戏房间"""
        return self.room_manager.join_room(room_id, user_id, username, password)

    def leave_game_room(self, user_id: str) -> bool:
        """离开游戏房间"""
        return self.room_manager.leave_room(user_id)

    def get_room_list(
        self,
        game_mode: str = None,
        public_only: bool = True
    ) -> List[Dict[str, Any]]:
        """获取房间列表"""
        return self.room_manager.get_room_list(game_mode, public_only=public_only)

    # ========== 游戏分享 ==========

    async def share_game(
        self,
        game_id: str,
        created_by: str,
        expires_in_days: int = 7
    ) -> ShareLink:
        """分享游戏"""
        return await self.game_share.create_game_share(game_id, created_by, expires_in_days)

    async def share_room(
        self,
        room_id: str,
        created_by: str,
        expires_in_hours: int = 24
    ) -> ShareLink:
        """分享房间"""
        return await self.game_share.create_room_share(room_id, created_by, expires_in_hours)

    async def generate_qr_code(
        self,
        share_id: str,
        size: int = 300
    ) -> Optional[bytes]:
        """生成二维码"""
        return await self.game_share.generate_qr_code(share_id, size)

    def create_room_invite_code(
        self,
        room_id: str,
        created_by: str,
        max_uses: int = 1
    ) -> str:
        """创建房间邀请码"""
        return self.game_share.create_invite_code(room_id, created_by, max_uses=max_uses)

    # ========== 游戏同步 ==========

    async def start_game_sync(self, room_id: str):
        """启动游戏同步"""
        await self.game_sync.start(room_id)

    async def stop_game_sync(self):
        """停止游戏同步"""
        await self.game_sync.stop()

    def update_local_player_state(
        self,
        player_id: str,
        position: Dict[str, float],
        rotation: Dict[str, float],
        velocity: Dict[str, float],
        health: float,
        state: str
    ):
        """更新本地玩家状态"""
        self.game_sync.update_local_player(
            player_id, position, rotation, velocity, health, state
        )

    # ========== 事件系统 ==========

    def add_event_listener(self, event: str, callback: Callable):
        """添加事件监听"""
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def remove_event_listener(self, event: str, callback: Callable):
        """移除事件监听"""
        if event in self._event_callbacks:
            self._event_callbacks[event].remove(callback)

    def _emit_event(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    callback(event, data)
                except Exception as e:
                    print(f"Event callback error: {e}")

    # ========== 统计信息 ==========

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "ide": {
                "open_documents": len(self.code_editor.documents),
                "active_document": self.code_editor.active_document,
            },
            "ai": self.ai_assistant.get_assistant_stats(),
            "debug": self.debugger.get_debugger_state(),
            "memory": self.memory_editor.get_editor_stats(),
            "collab": self.collab_editor.get_editor_stats(),
            "game": {
                "client": self.game_client.get_client_stats(),
                "rooms": self.room_manager.get_manager_stats(),
                "shares": self.game_share.get_share_stats(),
                "sync": self.game_sync.get_sync_stats(),
            },
            "running": self._running
        }


# ========== 便捷函数 ==========

def create_smart_ide_game_system(storage_path: str = None) -> SmartIDEGameSystem:
    """创建智能IDE与游戏系统"""
    return SmartIDEGameSystem(storage_path)


def create_game_config(
    name: str,
    game_type: GameType = GameType.CUSTOM,
    max_players: int = 1
) -> GameConfig:
    """创建游戏配置"""
    return GameConfig(
        id="",  # 将由系统分配
        name=name,
        game_type=game_type,
        max_players=max_players
    )


def create_room_settings(
    room_name: str,
    max_players: int = 8,
    game_mode: str = "deathmatch"
) -> RoomSettings:
    """创建房间设置"""
    return RoomSettings(
        room_name=room_name,
        max_players=max_players,
        game_mode=game_mode
    )


# ========== 导出 ==========

__all__ = [
    # 核心类
    'SmartIDEGameSystem',
    'create_smart_ide_game_system',
    
    # 模型
    'LanguageType', 'GameType', 'RoomType', 'RoomStatus', 'ShareMode', 'SyncMode',
    'IDESettings', 'GameSettings', 'UserPreferences',
    'GameConfig', 'GamePlayer', 'RoomSettings', 'RoomPlayer',
    'ShareLink', 'CollabDocument', 'Participant', 'Cursor',
    
    # IDE 组件
    'CodeEditorCore', 'AICodingAssistant', 'DebuggerManager', 'DebugSession',
    'MemoryEnhancedEditor', 'CollabEditor',
    'CodePosition', 'CompletionItem', 'Diagnostic', 'Symbol',
    'AIRecommendation', 'Breakpoint', 'Snippet', 'ProjectMemory',
    
    # 游戏组件
    'GameClient', 'RoomManager', 'GameShare', 'GameSync',
    'GameState', 'InputState', 'NetworkQualityMonitor',
    
    # 辅助函数
    'create_game_config', 'create_room_settings',
]
