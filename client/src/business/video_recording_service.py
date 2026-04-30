"""
视频录制服务 (Video Recording Service)

可选的视频录制功能：
1. 支持全屏录制和窗口录制
2. 可配置录制质量（分辨率、帧率、编码）
3. 录制完成后自动生成摘要
4. 与操作记忆系统集成
5. 资源友好：可配置录制时长和质量

核心特点：
- 可选功能，默认关闭
- 可配置录制参数
- 录制后自动处理（压缩、摘要）
- 与记忆图和知识库关联
"""

import os
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from enum import Enum

# 导入共享基础设施
from client.src.business.shared import (
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


class RecordingQuality(Enum):
    """录制质量"""
    LOW = "low"       # 低质量：640x480, 10fps
    MEDIUM = "medium" # 中等：1280x720, 15fps
    HIGH = "high"     # 高质量：1920x1080, 30fps


class RecordingMode(Enum):
    """录制模式"""
    FULL_SCREEN = "full_screen"  # 全屏录制
    ACTIVE_WINDOW = "active_window"  # 当前窗口
    SELECTED_REGION = "selected_region"  # 选择区域


@dataclass
class RecordingConfig:
    """录制配置"""
    quality: RecordingQuality = RecordingQuality.MEDIUM
    mode: RecordingMode = RecordingMode.FULL_SCREEN
    max_duration: int = 3600  # 最大录制时长（秒）
    frame_rate: int = 15
    output_format: str = "mp4"
    save_path: str = "recordings"
    auto_compress: bool = True
    auto_summarize: bool = True


@dataclass
class RecordingSession:
    """录制会话"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    config: RecordingConfig = field(default_factory=RecordingConfig)
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    summary: Optional[str] = None
    duration: float = 0.0


class VideoRecordingService:
    """
    视频录制服务
    
    核心功能：
    1. 开始/停止视频录制
    2. 配置录制参数
    3. 录制后自动处理
    4. 与记忆图和知识库集成
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
        
        # 默认配置
        self.config = RecordingConfig()
        
        # 状态
        self.active_session: Optional[RecordingSession] = None
        self.is_recording = False
        
        # 初始化保存目录
        self._init_save_path()
        
        print("[VideoRecordingService] 初始化完成")
        self._initialized = True
    
    def _init_save_path(self):
        """初始化保存目录"""
        os.makedirs(self.config.save_path, exist_ok=True)
    
    # ============ 配置管理 ============
    
    def set_config(self, **kwargs):
        """
        设置录制配置
        
        Args:
            **kwargs: 配置参数
                - quality: RecordingQuality 或字符串 ("low", "medium", "high")
                - mode: RecordingMode 或字符串 ("full_screen", "active_window", "selected_region")
                - max_duration: 最大录制时长（秒）
                - frame_rate: 帧率
                - output_format: 输出格式
                - save_path: 保存路径
                - auto_compress: 是否自动压缩
                - auto_summarize: 是否自动生成摘要
        """
        if "quality" in kwargs:
            quality = kwargs["quality"]
            if isinstance(quality, str):
                quality = RecordingQuality(quality.lower())
            self.config.quality = quality
        
        if "mode" in kwargs:
            mode = kwargs["mode"]
            if isinstance(mode, str):
                mode = RecordingMode(mode.lower())
            self.config.mode = mode
        
        if "max_duration" in kwargs:
            self.config.max_duration = int(kwargs["max_duration"])
        
        if "frame_rate" in kwargs:
            self.config.frame_rate = int(kwargs["frame_rate"])
        
        if "output_format" in kwargs:
            self.config.output_format = kwargs["output_format"]
        
        if "save_path" in kwargs:
            self.config.save_path = kwargs["save_path"]
            self._init_save_path()
        
        if "auto_compress" in kwargs:
            self.config.auto_compress = bool(kwargs["auto_compress"])
        
        if "auto_summarize" in kwargs:
            self.config.auto_summarize = bool(kwargs["auto_summarize"])
        
        print(f"[VideoRecordingService] 配置已更新: {self.config}")
    
    def get_config(self) -> RecordingConfig:
        """获取当前配置"""
        return self.config
    
    # ============ 录制控制 ============
    
    def start_recording(self, **kwargs) -> str:
        """
        开始视频录制
        
        Args:
            **kwargs: 覆盖默认配置
            
        Returns:
            会话ID
        """
        if self.is_recording:
            raise RuntimeError("已有录制会话正在进行")
        
        # 临时覆盖配置
        temp_config = RecordingConfig(**self.config.__dict__)
        if kwargs:
            self._apply_temp_config(temp_config, kwargs)
        
        session_id = str(uuid4())[:8]
        
        # 创建录制会话
        self.active_session = RecordingSession(
            session_id=session_id,
            start_time=datetime.now(),
            config=temp_config
        )
        
        # 实际录制（占位实现）
        self._start_recording_internal(temp_config)
        
        self.is_recording = True
        print(f"[VideoRecordingService] 开始录制: {session_id}")
        
        return session_id
    
    def _apply_temp_config(self, config: RecordingConfig, kwargs: Dict):
        """应用临时配置"""
        if "quality" in kwargs:
            quality = kwargs["quality"]
            if isinstance(quality, str):
                quality = RecordingQuality(quality.lower())
            config.quality = quality
        
        if "mode" in kwargs:
            mode = kwargs["mode"]
            if isinstance(mode, str):
                mode = RecordingMode(mode.lower())
            config.mode = mode
    
    def _start_recording_internal(self, config: RecordingConfig):
        """
        内部录制逻辑（占位实现）
        
        实际实现需要使用屏幕录制库，如：
        - Windows: pywin32 + opencv
        - macOS: pyobjc + opencv
        - Linux: pyqt5 + opencv
        
        这里提供占位实现，记录录制状态
        """
        # 模拟录制开始
        self._simulate_recording = True
    
    def stop_recording(self) -> Optional[str]:
        """
        停止视频录制
        
        Returns:
            视频文件路径
        """
        if not self.is_recording or not self.active_session:
            return None
        
        # 停止录制（占位实现）
        self._stop_recording_internal()
        
        # 生成文件名
        timestamp = self.active_session.start_time.strftime("%Y%m%d_%H%M%S")
        video_filename = f"recording_{self.active_session.session_id}_{timestamp}.{self.active_session.config.output_format}"
        video_path = os.path.join(self.active_session.config.save_path, video_filename)
        
        # 模拟保存视频文件
        self._save_video_file(video_path)
        
        # 更新会话
        self.active_session.end_time = datetime.now()
        self.active_session.duration = (self.active_session.end_time - self.active_session.start_time).total_seconds()
        self.active_session.video_path = video_path
        
        # 自动处理
        if self.active_session.config.auto_compress:
            self._compress_video()
        
        if self.active_session.config.auto_summarize:
            self._generate_summary()
        
        # 保存到记忆图
        self._save_to_memory_graph()
        
        # 发布事件
        self.event_bus.publish(EVENTS["KNOWLEDGE_INGESTED"], {
            "type": "video_recording",
            "session_id": self.active_session.session_id,
            "duration": self.active_session.duration,
            "video_path": video_path,
            "summary": self.active_session.summary
        })
        
        self.is_recording = False
        print(f"[VideoRecordingService] 停止录制: {self.active_session.session_id}")
        
        return video_path
    
    def _stop_recording_internal(self):
        """内部停止录制逻辑"""
        self._simulate_recording = False
    
    def _save_video_file(self, path: str):
        """保存视频文件（占位实现）"""
        # 创建一个空文件作为占位
        with open(path, 'w') as f:
            f.write(f"Video recording placeholder\nSession: {self.active_session.session_id}")
        
        # 生成缩略图路径
        thumbnail_path = path.replace('.mp4', '_thumb.jpg')
        with open(thumbnail_path, 'w') as f:
            f.write(f"Thumbnail placeholder")
        self.active_session.thumbnail_path = thumbnail_path
    
    def _compress_video(self):
        """压缩视频（占位实现）"""
        print(f"[VideoRecordingService] 压缩视频: {self.active_session.video_path}")
    
    def _generate_summary(self):
        """生成视频摘要（占位实现）"""
        if not self.active_session:
            return
        
        summary = f"""视频录制摘要
会话ID: {self.active_session.session_id}
开始时间: {self.active_session.start_time.strftime('%Y-%m-%d %H:%M:%S')}
结束时间: {self.active_session.end_time.strftime('%Y-%m-%d %H:%M:%S')}
时长: {self.active_session.duration:.1f} 秒
质量: {self.active_session.config.quality.value}
模式: {self.active_session.config.mode.value}
路径: {self.active_session.video_path}

（视频内容分析摘要将在此处生成）
"""
        self.active_session.summary = summary
        print(f"[VideoRecordingService] 生成摘要完成")
    
    # ============ 记忆图集成 ============
    
    def _save_to_memory_graph(self):
        """保存录制会话到记忆图"""
        if not self.active_session or not self.memory_graph_engine:
            return
        
        try:
            # 创建记忆图
            graph_id = self.memory_graph_engine.create_graph()
            
            # 添加视频节点
            video_node = self.memory_graph_engine.add_evidence(
                graph_id=graph_id,
                content=f"视频录制: {self.active_session.summary[:200]}",
                confidence=0.9,
                modalities=["video"]
            )
            
            # 添加摘要节点
            if self.active_session.summary:
                summary_node = self.memory_graph_engine.add_reasoning(
                    graph_id=graph_id,
                    content=self.active_session.summary,
                    confidence=0.8
                )
                self.memory_graph_engine.connect_nodes(
                    graph_id=graph_id,
                    from_node=video_node,
                    to_node=summary_node,
                    relation_type=RelationType.DERIVES_FROM,
                    weight=0.9
                )
            
            print(f"[VideoRecordingService] 视频已保存到记忆图: {graph_id}")
            
        except Exception as e:
            print(f"[VideoRecordingService] 保存到记忆图失败: {e}")
    
    # ============ 与知识库关联 ============
    
    async def link_to_knowledge(self):
        """将视频与知识库关联"""
        if not self.active_session or not self.kb_manager:
            return
        
        if self.active_session.summary:
            await self.kb_manager.save_to_wiki(
                title=f"视频录制_{self.active_session.session_id}",
                content=self.active_session.summary,
                references=[self.active_session.video_path]
            )
            print(f"[VideoRecordingService] 视频摘要已保存到知识库")
    
    # ============ 快捷方法 ============
    
    def get_recording_status(self) -> Dict[str, Any]:
        """获取录制状态"""
        if not self.is_recording:
            return {
                "is_recording": False,
                "message": "未在录制"
            }
        
        if not self.active_session:
            return {
                "is_recording": False,
                "message": "状态异常"
            }
        
        elapsed = (datetime.now() - self.active_session.start_time).total_seconds()
        
        return {
            "is_recording": True,
            "session_id": self.active_session.session_id,
            "start_time": self.active_session.start_time.isoformat(),
            "elapsed_seconds": int(elapsed),
            "quality": self.active_session.config.quality.value,
            "mode": self.active_session.config.mode.value
        }
    
    def list_recordings(self) -> List[Dict[str, Any]]:
        """列出所有录制文件"""
        recordings = []
        
        if not os.path.exists(self.config.save_path):
            return recordings
        
        for filename in os.listdir(self.config.save_path):
            if filename.endswith(f".{self.config.output_format}"):
                filepath = os.path.join(self.config.save_path, filename)
                stats = os.stat(filepath)
                
                recordings.append({
                    "filename": filename,
                    "path": filepath,
                    "size": stats.st_size,
                    "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
                })
        
        return recordings


# 创建全局实例
_video_recording_service = None


def get_video_recording_service() -> VideoRecordingService:
    """获取视频录制服务实例"""
    global _video_recording_service
    if _video_recording_service is None:
        _video_recording_service = VideoRecordingService()
    return _video_recording_service


__all__ = [
    "RecordingQuality",
    "RecordingMode",
    "RecordingConfig",
    "RecordingSession",
    "VideoRecordingService",
    "get_video_recording_service"
]