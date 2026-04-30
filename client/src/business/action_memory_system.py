"""
操作记忆系统 (Action Memory System)

轻量级屏幕操作记录方案：
1. 监听系统事件（鼠标点击、键盘输入、窗口切换）
2. 提取操作意图和上下文
3. 定时捕获屏幕快照（非连续录制）
4. 构建操作时间线和知识关联

与现有系统集成：
- 多模态记忆图引擎
- 知识库管理器
- 事件总线

核心特点：
- 低资源消耗（不录制视频）
- 结构化操作日志
- 智能意图识别
- 与知识图谱关联
"""

import time
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from enum import Enum

# 导入共享基础设施
from client.src.business.shared import (
    EventBus,
    get_event_bus,
    EVENTS
)

# 导入现有模块
from client.src.business.memory_graph_engine import (
    get_memory_graph_engine,
    NodeType,
    RelationType
)
from client.src.business.knowledge_base_manager import (
    get_knowledge_manager
)


class ActionType(Enum):
    """操作类型"""
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"
    MOUSE_RIGHT_CLICK = "mouse_right_click"
    KEYBOARD_INPUT = "keyboard_input"
    WINDOW_SWITCH = "window_switch"
    APP_LAUNCH = "app_launch"
    APP_CLOSE = "app_close"
    SCROLL = "scroll"
    COPY = "copy"
    PASTE = "paste"
    DRAG_DROP = "drag_drop"


class ActivityType(Enum):
    """活动类型"""
    BROWSING = "browsing"
    CODING = "coding"
    DOCUMENT_EDITING = "document_editing"
    CHATTING = "chatting"
    PRESENTATION = "presentation"
    SEARCHING = "searching"
    UNKNOWN = "unknown"


@dataclass
class ActionEvent:
    """操作事件"""
    action_id: str
    action_type: ActionType
    timestamp: datetime
    window_title: str
    window_class: str
    position: Optional[Dict[str, int]] = None
    text_content: Optional[str] = None
    selection_text: Optional[str] = None
    intent: Optional[str] = None
    confidence: float = 0.0


@dataclass
class Snapshot:
    """屏幕快照"""
    snapshot_id: str
    timestamp: datetime
    thumbnail: Optional[bytes] = None
    window_titles: List[str] = field(default_factory=list)
    active_window: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ActionSession:
    """操作会话"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    actions: List[ActionEvent] = field(default_factory=list)
    snapshots: List[Snapshot] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None


class ActionMemorySystem:
    """
    操作记忆系统
    
    核心功能：
    1. 监听系统操作事件
    2. 定时捕获屏幕快照
    3. 识别操作意图
    4. 构建操作时间线
    5. 与知识库关联
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        # 获取共享基础设施
        self.event_bus = get_event_bus()
        self.memory_graph_engine = get_memory_graph_engine()
        self.kb_manager = get_knowledge_manager()
        
        # 配置
        self.snapshot_interval = 30  # 每30秒捕获一次快照
        self.max_actions_per_session = 1000
        self.max_snapshots_per_session = 100
        
        # 状态
        self.active_session: Optional[ActionSession] = None
        self.is_recording = False
        self.last_snapshot_time = 0
        
        # 意图识别模型
        self.intent_patterns = self._load_intent_patterns()
        
        # 注册事件监听
        self._register_event_listeners()
        
        print("[ActionMemorySystem] 初始化完成")
        self._initialized = True
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """加载意图识别模式"""
        return {
            "searching": ["搜索", "查找", "query", "search", "google", "baidu"],
            "coding": ["code", "编程", "开发", "IDE", "vscode", "pycharm"],
            "writing": ["文档", "word", "write", "编辑", "笔记"],
            "chatting": ["聊天", "message", "微信", "钉钉", "slack"],
            "browsing": ["浏览", "网页", "chrome", "edge", "firefox"],
            "configuring": ["设置", "配置", "选项", "preferences"],
            "installing": ["安装", "setup", "install", "下载"],
            "debugging": ["调试", "debug", "错误", "error", "bug"]
        }
    
    def _register_event_listeners(self):
        """注册事件监听器"""
        # 监听聊天命令事件
        self.event_bus.subscribe(EVENTS["CHAT_CLEAR"], self._on_chat_clear)
    
    def _on_chat_clear(self, event_data):
        """聊天清空事件处理"""
        self.end_session()
    
    # ============ 会话管理 ============
    
    def start_session(self, session_name: str = "") -> str:
        """开始新的操作会话"""
        if self.is_recording:
            self.end_session()
        
        session_id = str(uuid4())[:8]
        self.active_session = ActionSession(
            session_id=session_id,
            start_time=datetime.now()
        )
        self.is_recording = True
        self.last_snapshot_time = time.time()
        
        print(f"[ActionMemorySystem] 开始操作记录会话: {session_id}")
        return session_id
    
    def end_session(self):
        """结束当前会话"""
        if not self.is_recording or not self.active_session:
            return
        
        self.active_session.end_time = datetime.now()
        
        # 生成会话总结
        self.active_session.summary = self._generate_session_summary()
        
        # 保存到记忆图
        self._save_to_memory_graph()
        
        # 发布事件
        self.event_bus.publish(EVENTS["KNOWLEDGE_INGESTED"], {
            "session_id": self.active_session.session_id,
            "action_count": len(self.active_session.actions),
            "snapshot_count": len(self.active_session.snapshots),
            "duration": (self.active_session.end_time - self.active_session.start_time).total_seconds()
        })
        
        print(f"[ActionMemorySystem] 结束操作记录会话: {self.active_session.session_id}")
        self.is_recording = False
        self.active_session = None
    
    # ============ 操作记录 ============
    
    def record_action(self, action_type: ActionType, window_title: str, 
                      window_class: str, **kwargs):
        """
        记录操作事件
        
        Args:
            action_type: 操作类型
            window_title: 窗口标题
            window_class: 窗口类名
            **kwargs: 额外参数（position, text_content, selection_text等）
        """
        if not self.is_recording or not self.active_session:
            return
        
        # 识别操作意图
        intent = self._recognize_intent(window_title, kwargs.get("text_content", ""))
        
        action = ActionEvent(
            action_id=str(uuid4())[:8],
            action_type=action_type,
            timestamp=datetime.now(),
            window_title=window_title,
            window_class=window_class,
            position=kwargs.get("position"),
            text_content=kwargs.get("text_content"),
            selection_text=kwargs.get("selection_text"),
            intent=intent,
            confidence=kwargs.get("confidence", 0.7)
        )
        
        self.active_session.actions.append(action)
        
        # 检查是否需要捕获快照
        self._check_snapshot()
        
        # 限制数量
        if len(self.active_session.actions) > self.max_actions_per_session:
            self.end_session()
            self.start_session()
    
    def _recognize_intent(self, window_title: str, text_content: str = "") -> Optional[str]:
        """识别操作意图"""
        combined = (window_title + " " + text_content).lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern.lower() in combined:
                    return intent
        
        return None
    
    # ============ 快照管理 ============
    
    def _check_snapshot(self):
        """检查是否需要捕获快照"""
        now = time.time()
        if now - self.last_snapshot_time >= self.snapshot_interval:
            self.capture_snapshot()
    
    def capture_snapshot(self, force: bool = False):
        """
        捕获屏幕快照
        
        Args:
            force: 是否强制捕获
        """
        if not self.is_recording or not self.active_session:
            return
        
        if not force:
            now = time.time()
            if now - self.last_snapshot_time < self.snapshot_interval:
                return
        
        # 限制快照数量
        if len(self.active_session.snapshots) >= self.max_snapshots_per_session:
            return
        
        try:
            snapshot = Snapshot(
                snapshot_id=str(uuid4())[:8],
                timestamp=datetime.now(),
                window_titles=self._get_open_windows(),
                active_window=self._get_active_window(),
                description=self._describe_current_state()
            )
            
            self.active_session.snapshots.append(snapshot)
            self.last_snapshot_time = time.time()
            
            print(f"[ActionMemorySystem] 捕获快照: {snapshot.snapshot_id}")
            
        except Exception as e:
            print(f"[ActionMemorySystem] 捕获快照失败: {e}")
    
    def _get_open_windows(self) -> List[str]:
        """获取打开的窗口列表（占位实现）"""
        # 实际实现需要调用系统API
        return ["当前窗口1", "当前窗口2", "当前窗口3"]
    
    def _get_active_window(self) -> Optional[str]:
        """获取活动窗口（占位实现）"""
        return "活动窗口标题"
    
    def _describe_current_state(self) -> str:
        """描述当前状态"""
        if not self.active_session:
            return ""
        
        recent_actions = self.active_session.actions[-3:] if self.active_session.actions else []
        actions_desc = ", ".join([a.action_type.value for a in recent_actions])
        
        return f"最近操作: {actions_desc}"
    
    # ============ 会话总结 ============
    
    def _generate_session_summary(self) -> str:
        """生成会话总结"""
        if not self.active_session:
            return ""
        
        duration = (self.active_session.end_time - self.active_session.start_time).total_seconds()
        
        # 统计操作类型
        action_counts = {}
        for action in self.active_session.actions:
            key = action.action_type.value
            action_counts[key] = action_counts.get(key, 0) + 1
        
        # 统计意图
        intents = set()
        for action in self.active_session.actions:
            if action.intent:
                intents.add(action.intent)
        
        # 统计窗口
        windows = set()
        for action in self.active_session.actions:
            windows.add(action.window_title)
        
        summary = f"""操作会话总结
持续时间: {duration:.1f} 秒
操作次数: {len(self.active_session.actions)}
快照数量: {len(self.active_session.snapshots)}

主要操作: {', '.join([f'{k}({v})' for k, v in action_counts.items()])}
识别意图: {', '.join(intents) if intents else '未识别'}
涉及窗口: {len(windows)} 个

活跃窗口: {self.active_session.snapshots[-1].active_window if self.active_session.snapshots else '未知'}
"""
        return summary
    
    # ============ 记忆图集成 ============
    
    def _save_to_memory_graph(self):
        """保存会话到记忆图"""
        if not self.active_session or not self.memory_graph_engine:
            return
        
        try:
            # 创建记忆图
            graph_id = self.memory_graph_engine.create_graph()
            
            # 添加会话节点
            session_node = self.memory_graph_engine.add_reasoning(
                graph_id=graph_id,
                content=self.active_session.summary,
                confidence=0.8
            )
            
            # 添加关键操作节点
            for action in self.active_session.actions[:10]:  # 最多10个关键操作
                action_node = self.memory_graph_engine.add_evidence(
                    graph_id=graph_id,
                    content=f"{action.action_type.value}: {action.window_title}",
                    confidence=action.confidence,
                    modalities=["text"]
                )
                self.memory_graph_engine.connect_nodes(
                    graph_id=graph_id,
                    from_node=action_node,
                    to_node=session_node,
                    relation_type=RelationType.SUPPORTS,
                    weight=0.5
                )
            
            # 添加快照节点
            for snapshot in self.active_session.snapshots[:5]:  # 最多5个快照
                snap_node = self.memory_graph_engine.add_evidence(
                    graph_id=graph_id,
                    content=f"快照: {snapshot.description}",
                    modalities=["image"] if snapshot.thumbnail else ["text"]
                )
                self.memory_graph_engine.connect_nodes(
                    graph_id=graph_id,
                    from_node=snap_node,
                    to_node=session_node,
                    relation_type=RelationType.DERIVES_FROM,
                    weight=0.3
                )
            
            print(f"[ActionMemorySystem] 会话已保存到记忆图: {graph_id}")
            
        except Exception as e:
            print(f"[ActionMemorySystem] 保存到记忆图失败: {e}")
    
    # ============ 与知识库关联 ============
    
    async def link_to_knowledge(self, intent: str, content: str):
        """将操作与知识库关联"""
        if not self.kb_manager:
            return
        
        # 搜索相关知识
        result = await self.kb_manager.query(content)
        
        if result and result.sources:
            print(f"[ActionMemorySystem] 找到 {len(result.sources)} 条相关知识")
            
            # 将相关知识添加到当前会话的记忆图
            if self.active_session:
                # 简化实现：直接保存到 wiki
                self.kb_manager.save_to_wiki(
                    title=f"操作关联_{intent}",
                    content=result.answer,
                    references=[s.get("title", "") for s in result.sources]
                )
    
    # ============ 快捷方法 ============
    
    def record_mouse_click(self, window_title: str, window_class: str, x: int, y: int):
        """记录鼠标点击"""
        self.record_action(
            ActionType.MOUSE_CLICK,
            window_title,
            window_class,
            position={"x": x, "y": y}
        )
    
    def record_keyboard_input(self, window_title: str, window_class: str, text: str):
        """记录键盘输入"""
        self.record_action(
            ActionType.KEYBOARD_INPUT,
            window_title,
            window_class,
            text_content=text
        )
    
    def record_window_switch(self, window_title: str, window_class: str):
        """记录窗口切换"""
        self.record_action(
            ActionType.WINDOW_SWITCH,
            window_title,
            window_class
        )
    
    def get_session_summary(self) -> Optional[str]:
        """获取当前会话总结"""
        if self.active_session:
            return self._generate_session_summary()
        return None


# 创建全局实例
_action_memory_system = None


def get_action_memory_system() -> ActionMemorySystem:
    """获取操作记忆系统实例"""
    global _action_memory_system
    if _action_memory_system is None:
        _action_memory_system = ActionMemorySystem()
    return _action_memory_system


__all__ = [
    "ActionType",
    "ActivityType",
    "ActionEvent",
    "Snapshot",
    "ActionSession",
    "ActionMemorySystem",
    "get_action_memory_system"
]