"""
CDN 存储

负责数据的持久化存储
"""

from __future__ import annotations


import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from .models import CDNData

logger = logging.getLogger(__name__)


class CDNStorage:
    """
    CDN 存储
    负责数据的持久化存储
    """
    
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.data_dir = self.storage_dir / "data"
        self.meta_dir = self.storage_dir / "meta"
    
    async def init(self):
        """
        初始化存储
        """
        # 创建存储目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized CDN storage at {self.storage_dir}")
    
    async def store_data(self, data: CDNData) -> bool:
        """
        存储数据
        
        Args:
            data: CDN 数据
            
        Returns:
            是否存储成功
        """
        try:
            # 存储数据
            data_path = self.data_dir / f"{data.data_id}.json"
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Stored data {data.data_id} at {data_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to store data {data.data_id}: {e}")
            return False
    
    async def get_data(self, data_id: str) -> Optional[CDNData]:
        """
        获取数据
        
        Args:
            data_id: 数据 ID
            
        Returns:
            CDN 数据，如果不存在则返回 None
        """
        try:
            data_path = self.data_dir / f"{data_id}.json"
            if not data_path.exists():
                return None
            
            with open(data_path, 'r', encoding='utf-8') as f:
                data_dict = json.load(f)
            
            data = CDNData.from_dict(data_dict)
            logger.debug(f"Retrieved data {data_id} from {data_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to get data {data_id}: {e}")
            return None
    
    async def delete_data(self, data_id: str) -> bool:
        """
        删除数据
        
        Args:
            data_id: 数据 ID
            
        Returns:
            是否删除成功
        """
        try:
            data_path = self.data_dir / f"{data_id}.json"
            if data_path.exists():
                data_path.unlink()
                logger.debug(f"Deleted data {data_id} from {data_path}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete data {data_id}: {e}")
            return False
    
    async def list_data(self) -> List[str]:
        """
        列出所有数据 ID
        
        Returns:
            数据 ID 列表
        """
        try:
            data_ids = []
            for file_path in self.data_dir.glob("*.json"):
                data_id = file_path.stem
                data_ids.append(data_id)
            
            logger.debug(f"Listed {len(data_ids)} data items")
            return data_ids
        except Exception as e:
            logger.error(f"Failed to list data: {e}")
            return []
    
    def get_available_space(self) -> int:
        """
        获取可用存储空间
        
        Returns:
            可用存储空间（字节）
        """
        try:
            # 跨平台获取可用空间
            if os.name == 'nt':  # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(str(self.storage_dir)),
                    None, None, ctypes.pointer(free_bytes)
                )
                return free_bytes.value
            else:  # Unix-like
                stat = os.statvfs(self.storage_dir)
                available_space = stat.f_bavail * stat.f_frsize
                return available_space
        except Exception as e:
            logger.error(f"Failed to get available space: {e}")
            return 0
    
    def get_used_space(self) -> int:
        """
        获取已使用存储空间
        
        Returns:
            已使用存储空间（字节）
        """
        try:
            used_space = 0
            for file_path in self.data_dir.glob("*.json"):
                used_space += file_path.stat().st_size
            
            return used_space
        except Exception as e:
            logger.error(f"Failed to get used space: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "storage_dir": str(self.storage_dir),
            "available_space": self.get_available_space(),
            "used_space": self.get_used_space(),
            "data_count": len(list(self.data_dir.glob("*.json")))
        }
    
    async def close(self):
        """
        关闭存储
        """
        # 这里可以添加清理逻辑
        logger.info("Closed CDN storage")
