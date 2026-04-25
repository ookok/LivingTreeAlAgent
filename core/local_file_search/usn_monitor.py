"""
USN Journal 监听器 - Windows 文件系统变更监控
用于增量更新索引，无需全量扫描
"""

import os
import sys
import struct
import ctypes
from ctypes import wintypes
import logging
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_um = _get_unified_config()
except Exception:
    _uconfig_um = None

def _um_get(key: str, default):
    return _uconfig_um.get(key, default) if _uconfig_um else default


# Windows API 常量
FSCTL_QUERY_USN_JOURNAL = 0x900a4
FSCTL_CREATE_USN_JOURNAL = 0x900e4
FSCTL_READ_USN_JOURNAL = 0x900b3


@dataclass
class USNChange:
    """USN 变更记录"""
    path: str
    reason: int
    is_file: bool
    is_directory: bool
    size: int
    timestamp: datetime


def is_usn_available() -> bool:
    """检查 USN Journal 是否可用"""
    if sys.platform != 'win32':
        return False
    
    try:
        import ctypes
        handle = ctypes.windll.kernel32.CreateFileW(
            r"\\.\C:",
            0,
            0,
            None,
            3,
            0,
            None
        )
        
        if handle == -1:
            return False
        
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except:
        return False


class USNJournalReader:
    """USN Journal 读取器"""
    
    def __init__(self, drive_letter: str):
        self.drive = drive_letter.rstrip('\\').rstrip('/')
        self.volume_path = rf"\\.\{self.drive}"
        self._handle: Optional[int] = None
        self._journal_id: int = 0
        self._usn: int = 0
        self._open()
    
    def _open(self):
        """打开卷"""
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        FILE_ATTRIBUTE_NORMAL = 0x00000080
        
        try:
            self._handle = ctypes.windll.kernel32.CreateFileW(
                self.volume_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS | FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            if self._handle == -1:
                raise OSError(f"无法打开卷 {self.volume_path}")
            
            self._query_journal()
            logger.info(f"[USNJournal] 已连接到 {self.drive}")
            
        except Exception as e:
            logger.error(f"[USNJournal] 连接失败: {e}")
            self._handle = None
    
    def _query_journal(self):
        """查询 Journal 信息"""
        class USN_JOURNAL_DATA(ctypes.Structure):
            _fields_ = [
                ("UsnJournalID", wintypes.ULONGLONG),
                ("FirstUsn", wintypes.ULONGLONG),
                ("NextUsn", wintypes.ULONGLONG),
                ("MinSupportedMajorVersion", wintypes.USHORT),
                ("MaxSupportedMajorVersion", wintypes.USHORT),
                ("MaxSupportedMinorVersion", wintypes.USHORT),
                ("Flags", wintypes.ULONG),
                ("Retention", wintypes.ULONGLONG),
            ]
        
        buffer = USN_JOURNAL_DATA()
        bytes_returned = wintypes.DWORD()
        
        success = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            FSCTL_QUERY_USN_JOURNAL,
            None,
            0,
            ctypes.byref(buffer),
            ctypes.sizeof(buffer),
            ctypes.byref(bytes_returned),
            None
        )
        
        if success:
            self._journal_id = buffer.UsnJournalID
            self._usn = buffer.NextUsn
    
    def _create_journal(self):
        """创建 Journal"""
        class CREATE_USN_JOURNAL_DATA(ctypes.Structure):
            _fields_ = [
                ("MaximumSize", wintypes.ULONGLONG),
                ("AllocationDelta", wintypes.ULONGLONG),
            ]
        
        buffer = CREATE_USN_JOURNAL_DATA(1024 * 1024 * 100, 1024 * 1024 * 10)
        bytes_returned = wintypes.DWORD()
        
        success = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            FSCTL_CREATE_USN_JOURNAL,
            ctypes.byref(buffer),
            ctypes.sizeof(buffer),
            None,
            0,
            ctypes.byref(bytes_returned),
            None
        )
        
        if success:
            logger.info(f"[USNJournal] Journal 创建成功")
            self._query_journal()
    
    def read_changes(self, start_usn: int = None, max_count: int = 1000) -> List[USNChange]:
        """读取 USN 变更记录"""
        if self._handle is None or self._handle == -1:
            return []
        
        changes = []
        
        if start_usn is None:
            start_usn = self._usn
        
        class READ_USN_JOURNAL_DATA(ctypes.Structure):
            _fields_ = [
                ("StartUsn", wintypes.ULONGLONG),
                ("ReasonMask", wintypes.ULONG),
                ("ReturnOnlyOnClose", wintypes.BOOLEAN),
                ("Timeout", wintypes.ULONGLONG),
                ("BytesToWaitFor", wintypes.ULONGLONG),
                ("MinMajorVersion", wintypes.USHORT),
                ("MaxMajorVersion", wintypes.USHORT),
            ]
        
        buffer_size = 64 * 1024
        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_returned = wintypes.DWORD()
        
        read_data = READ_USN_JOURNAL_DATA(
            start_usn, 0xFFFFFFFF, False, 0, 0, 2, 3
        )
        
        success = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            FSCTL_READ_USN_JOURNAL,
            ctypes.byref(read_data),
            ctypes.sizeof(read_data),
            buffer,
            buffer_size,
            ctypes.byref(bytes_returned),
            None
        )
        
        if success and bytes_returned.value > 8:
            data = buffer.raw[:bytes_returned.value]
            usn = struct.unpack('<Q', data[:8])[0]
            
            pos = 8
            while pos < len(data) and len(changes) < max_count:
                try:
                    record_length = struct.unpack('<I', data[pos:pos+4])[0]
                    major_version = struct.unpack('<H', data[pos+4:pos+6])[0]
                    
                    if major_version != 2:
                        pos += record_length
                        continue
                    
                    file_ref = struct.unpack('<Q', data[pos+8:pos+16])[0]
                    parent_ref = struct.unpack('<Q', data[pos+16:pos+24])[0]
                    usn_reason = struct.unpack('<I', data[pos+24:pos+28])[0]
                    
                    file_name_offset = struct.unpack('<H', data[pos+40:pos+42])[0]
                    file_name_length = struct.unpack('<H', data[pos+42:pos+44])[0]
                    
                    if file_name_length > 0:
                        name_data = data[pos+file_name_offset:pos+file_name_offset+file_name_length]
                        filename = name_data.decode('utf-16-le', errors='ignore').rstrip('\x00')
                        
                        path = f"{self.drive}\\{filename}" if parent_ref == 5 else f"{self.drive}\\...\\{filename}"
                        
                        changes.append(USNChange(
                            path=path,
                            reason=usn_reason,
                            is_file=(usn_reason & 0x10000000) == 0,
                            is_directory=(usn_reason & 0x10000000) != 0,
                            size=0,
                            timestamp=datetime.now()
                        ))
                    
                    pos += record_length
                    
                except Exception:
                    break
        
        return changes
    
    def get_latest_usn(self) -> int:
        """获取最新的 USN"""
        return self._usn
    
    def close(self):
        """关闭句柄"""
        if self._handle and self._handle != -1:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


class USNJournalMonitor:
    """USN Journal 监控器"""
    
    def __init__(self, drive: str, on_change: Callable[[List[USNChange]], None] = None):
        self.drive = drive
        self.on_change = on_change
        self._reader: Optional[USNJournalReader] = None
        self._running = False
        self._last_usn = 0
        self._poll_interval = _um_get("delays.polling_medium", 1.0)
        
        self._stats = {
            "total_changes": 0,
            "creates": 0,
            "deletes": 0,
            "modifies": 0,
            "renames": 0,
        }
    
    def start(self):
        """启动监控"""
        if self._running:
            return
        
        try:
            self._reader = USNJournalReader(self.drive)
            self._last_usn = self._reader.get_latest_usn()
            self._running = True
            logger.info(f"[USNJournalMonitor] 启动监控 {self.drive}")
        except Exception as e:
            logger.error(f"[USNJournalMonitor] 启动失败: {e}")
            self._running = False
    
    def poll(self) -> List[USNChange]:
        """轮询获取变更"""
        if not self._running or self._reader is None:
            return []
        
        changes = self._reader.read_changes(self._last_usn, max_count=100)
        
        if changes:
            self._last_usn = self._reader.get_latest_usn()
            
            for change in changes:
                self._stats["total_changes"] += 1
                if change.reason & 0x00010000:
                    self._stats["creates"] += 1
                if change.reason & 0x00020000:
                    self._stats["deletes"] += 1
                if change.reason & 0x00000001:
                    self._stats["modifies"] += 1
                if change.reason & 0x00040000:
                    self._stats["renames"] += 1
            
            if self.on_change:
                self.on_change(changes)
        
        return changes
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._reader:
            self._reader.close()
            self._reader = None
        logger.info(f"[USNJournalMonitor] 停止监控 {self.drive}")
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return self._stats.copy()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if is_usn_available():
        print("USN Journal 可用")
        
        def on_change(changes):
            for c in changes[:5]:
                print(f"  {c.path}")
        
        with USNJournalMonitor("C:", on_change=on_change) as monitor:
            print("监控中，按 Ctrl+C 退出...")
            import time
            while True:
                monitor.poll()
                time.sleep(1)
    else:
        print("USN Journal 不可用（需要 Windows NTFS 或管理员权限）")
