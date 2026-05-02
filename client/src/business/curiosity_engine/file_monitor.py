"""
文件监控器 - 监控文件夹变化

支持监控：
1. 本地文件夹
2. 远程文件变更（通过轮询）
3. 特定文件类型过滤
"""
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FileChangeType(Enum):
    """文件变化类型"""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileChange:
    """文件变化记录"""
    file_path: str
    change_type: FileChangeType
    timestamp: float
    file_size: Optional[int] = None
    file_hash: Optional[str] = None


class FileMonitor:
    """
    文件监控器
    
    监控指定文件夹的变化，支持：
    - 递归监控子目录
    - 文件类型过滤
    - 自定义轮询间隔
    """
    
    def __init__(self):
        self.monitored_paths: Dict[str, Dict[str, float]] = {}  # path -> {file: last_modified}
        self.callbacks: List[Callable[[FileChange], None]] = []
        self.is_running = False
        self.polling_interval = 5  # 秒
        self._thread = None
    
    def add_monitor_path(self, path: str, file_patterns: Optional[List[str]] = None):
        """
        添加监控路径
        
        Args:
            path: 文件夹路径
            file_patterns: 文件类型过滤（如 ["*.pdf", "*.docx"]）
        """
        path = str(Path(path).resolve())
        if path not in self.monitored_paths:
            self.monitored_paths[path] = {
                "files": {},
                "patterns": file_patterns or []
            }
            # 初始化文件列表
            self._scan_directory(path, file_patterns)
            logger.info(f"📁 开始监控: {path}")
    
    def remove_monitor_path(self, path: str):
        """移除监控路径"""
        path = str(Path(path).resolve())
        if path in self.monitored_paths:
            del self.monitored_paths[path]
            logger.info(f"📁 停止监控: {path}")
    
    def register_callback(self, callback: Callable[[FileChange], None]):
        """注册变化回调"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
    
    def start(self):
        """启动监控"""
        if self.is_running:
            return
        
        self.is_running = True
        import threading
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("🚀 文件监控器启动")
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🛑 文件监控器停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            for path, config in list(self.monitored_paths.items()):
                self._check_directory(path, config["patterns"])
            time.sleep(self.polling_interval)
    
    def _scan_directory(self, path: str, patterns: List[str]):
        """扫描目录并记录文件状态"""
        try:
            files = {}
            for item in Path(path).rglob("*"):
                if item.is_file() and self._matches_pattern(item.name, patterns):
                    files[str(item)] = item.stat().st_mtime
            self.monitored_paths[path]["files"] = files
        except Exception as e:
            logger.error(f"扫描目录失败 {path}: {e}")
    
    def _check_directory(self, path: str, patterns: List[str]):
        """检查目录变化"""
        try:
            current_files = {}
            
            for item in Path(path).rglob("*"):
                if item.is_file() and self._matches_pattern(item.name, patterns):
                    current_files[str(item)] = item.stat().st_mtime
            
            # 获取之前记录的文件
            previous_files = self.monitored_paths[path].get("files", {})
            
            # 检测新增文件
            for file_path, mtime in current_files.items():
                if file_path not in previous_files:
                    self._notify_change(file_path, FileChangeType.CREATED, mtime)
            
            # 检测修改文件
            for file_path, prev_mtime in previous_files.items():
                if file_path in current_files and current_files[file_path] > prev_mtime:
                    self._notify_change(file_path, FileChangeType.MODIFIED, current_files[file_path])
            
            # 检测删除文件
            for file_path in previous_files:
                if file_path not in current_files:
                    self._notify_change(file_path, FileChangeType.DELETED, time.time())
            
            # 更新记录
            self.monitored_paths[path]["files"] = current_files
            
        except Exception as e:
            logger.error(f"检查目录失败 {path}: {e}")
    
    def _matches_pattern(self, filename: str, patterns: List[str]) -> bool:
        """检查文件名是否匹配模式"""
        if not patterns:
            return True
        
        import fnmatch
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _notify_change(self, file_path: str, change_type: FileChangeType, timestamp: float):
        """通知所有回调"""
        change = FileChange(
            file_path=file_path,
            change_type=change_type,
            timestamp=timestamp,
            file_size=self._get_file_size(file_path) if change_type != FileChangeType.DELETED else None
        )
        
        for callback in self.callbacks:
            try:
                callback(change)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
    
    def _get_file_size(self, file_path: str) -> Optional[int]:
        """获取文件大小"""
        try:
            return os.path.getsize(file_path)
        except:
            return None
    
    def get_monitored_files(self) -> List[str]:
        """获取所有监控的文件"""
        files = []
        for config in self.monitored_paths.values():
            files.extend(config["files"].keys())
        return files