"""
智能IDE与游戏分享系统 - 数据模型
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
import uuid


class LanguageType(Enum):
    """编程语言类型"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    OTHER = "other"


class GameType(Enum):
    """游戏类型"""
    STRATEGY = "strategy"
    ACTION = "action"
    ADVENTURE = "adventure"
    RPG = "rpg"
    SIMULATION = "simulation"
    PUZZLE = "puzzle"
    RACING = "racing"
    SPORTS = "sports"
    CARD = "card"
    BOARD = "board"
    CUSTOM = "custom"


class RoomType(Enum):
    """游戏房间类型"""
    PRIVATE = "private"
    PUBLIC = "public"
    MATCHMAKING = "matchmaking"
    RANKED = "ranked"
    CREATIVE = "creative"
    SPECTATOR = "spectator"


class RoomStatus(Enum):
    """房间状态"""
    WAITING = "waiting"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    CLOSED = "closed"


class PlayerStatus(Enum):
    """玩家状态"""
    ONLINE = "online"
    IN_GAME = "in_game"
    AWAY = "away"
    OFFLINE = "offline"


class ShareMode(Enum):
    """分享模式"""
    FULL_GAME = "full_game"
    CLOUD_GAME = "cloud_game"
    ROOM_LINK = "room_link"
    QR_CODE = "qr_code"
    INVITE_CODE = "invite_code"
    GAME_STATE = "game_state"


class SyncMode(Enum):
    """同步模式"""
    FULL_STATE = "full_state"
    DELTA_STATE = "delta_state"
    INPUT_SYNC = "input_sync"
    AUTHORITATIVE = "authoritative"
    P2P_SYNC = "p2p_sync"


@dataclass
class CodeSnippet:
    """代码片段"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    code: str = ""
    language: LanguageType = LanguageType.PYTHON
    description: str = ""
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_favorite: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectTemplate:
    """项目模板"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    language: LanguageType = LanguageType.PYTHON
    structure: Dict[str, str] = field(default_factory=dict)  # path -> content
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CodeMemory:
    """代码记忆"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    context: str = ""
    usage_history: List[str] = field(default_factory=list)  # file paths
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[datetime] = None
    embedding: Optional[List[float]] = None


@dataclass
class Breakpoint:
    """断点"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    line: int = 0
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0
    log_message: Optional[str] = None


@dataclass
class WatchVariable:
    """监视变量"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    expression: str = ""
    value: Any = None
    value_type: str = ""
    updated_at: Optional[datetime] = None


@dataclass
class CallStackFrame:
    """调用栈帧"""
    function_name: str
    file_path: str
    line: int
    locals: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DebugSession:
    """调试会话"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    process_id: Optional[int] = None
    file_path: Optional[str] = None
    status: str = "stopped"  # stopped, running, paused, terminated
    breakpoints: List[Breakpoint] = field(default_factory=list)
    watch_variables: List[WatchVariable] = field(default_factory=list)
    call_stack: List[CallStackFrame] = field(default_factory=list)
    current_line: Optional[int] = None
    current_file: Optional[str] = None
    started_at: Optional[datetime] = None


@dataclass
class GamePlayer:
    """游戏玩家"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    username: str = ""
    avatar: Optional[str] = None
    status: PlayerStatus = PlayerStatus.ONLINE
    is_host: bool = False
    is_ready: bool = False
    score: int = 0
    team: Optional[str] = None
    latency: int = 0
    joined_at: datetime = field(default_factory=datetime.now)


@dataclass
class GameRoom:
    """游戏房间"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    game_type: GameType = GameType.STRATEGY
    room_type: RoomType = RoomType.PRIVATE
    status: RoomStatus = RoomStatus.WAITING
    max_players: int = 4
    min_players: int = 2
    players: List[GamePlayer] = field(default_factory=list)
    host_id: str = ""
    password: Optional[str] = None
    game_state: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    allow_spectators: bool = False
    spectators: List[str] = field(default_factory=list)


@dataclass
class ShareLink:
    """分享链接"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    share_mode: ShareMode = ShareMode.FULL_GAME
    target_id: str = ""
    short_code: str = ""
    qr_code_data: Optional[bytes] = None
    url: str = ""
    expires_at: Optional[datetime] = None
    max_access_count: Optional[int] = None
    access_count: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class GameState:
    """游戏状态"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str = ""
    players_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    shared_state: Dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    tick: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 0


@dataclass
class GameResource:
    """游戏资源"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: str = ""  # image, audio, video, model, data
    path: str = ""
    size: int = 0
    hash: Optional[str] = None
    compressed: bool = False
    compression_ratio: float = 1.0
    url: Optional[str] = None


@dataclass
class CollabSession:
    """协作会话"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    document_path: str = ""
    participants: List[str] = field(default_factory=list)
    cursors: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # user_id -> cursor info
    operations: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class ResourceUsage:
    """资源使用情况"""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    gpu_percent: float = 0.0
    disk_mb: float = 0.0
    network_mbps: float = 0.0


@dataclass
class PerformanceMetrics:
    """性能指标"""
    startup_time_ms: float = 0.0
    editor_response_ms: float = 0.0
    build_time_ms: float = 0.0
    debug_overhead_ms: float = 0.0
    memory_efficiency: float = 0.0
    cpu_efficiency: float = 0.0


@dataclass
class QualitySettings:
    """质量设置"""
    graphics_level: str = "medium"  # low, medium, high, ultra
    audio_quality: str = "medium"
    network_quality: str = "auto"
    physics_quality: str = "medium"
    ai_quality: str = "medium"
    auto_adjust: bool = True


@dataclass
class IDESettings:
    """IDE设置"""
    theme: str = "dark"
    font_size: int = 14
    font_family: str = "JetBrains Mono, Consolas, monospace"
    tab_size: int = 4
    auto_save: bool = True
    auto_save_interval: int = 30
    format_on_save: bool = True
    lint_on_save: bool = True
    line_numbers: bool = True
    minimap: bool = True
    word_wrap: bool = False
    bracket_pair_colorization: bool = True


@dataclass
class GameSettings:
    """游戏设置"""
    graphics_quality: str = "medium"
    audio_volume: float = 0.8
    music_volume: float = 0.6
    voice_volume: float = 1.0
    show_fps: bool = False
    show_ping: bool = True
    v_sync: bool = True
    fullscreen: bool = False
    resolution: str = "1920x1080"
    sensitivity: float = 1.0
    inverted_y: bool = False


@dataclass
class UserPreferences:
    """用户偏好"""
    ide_settings: IDESettings = field(default_factory=IDESettings)
    game_settings: GameSettings = field(default_factory=GameSettings)
    quality_settings: QualitySettings = field(default_factory=QualitySettings)
    shortcuts: Dict[str, str] = field(default_factory=dict)
    recent_projects: List[str] = field(default_factory=list)
    favorite_snippets: List[str] = field(default_factory=list)
    favorite_games: List[str] = field(default_factory=list)
