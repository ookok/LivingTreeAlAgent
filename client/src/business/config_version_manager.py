"""
配置版本管理器 - 管理配置的版本历史、对比和恢复
"""

import uuid
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class ConfigVersion:
    """配置版本"""
    id: str
    name: str
    timestamp: float
    config: Dict[str, Any]
    diff: Optional[Dict[str, Dict[str, Any]]] = None


class ConfigVersionManager:
    """配置版本管理器"""
    
    def __init__(self):
        self._versions: List[ConfigVersion] = []
        self._current_config: Dict[str, Any] = {}
        self._max_versions = 50
    
    def set_current_config(self, config: Dict[str, Any]):
        """设置当前配置"""
        self._current_config = config.copy()
    
    def save_version(self, name: str = "auto") -> ConfigVersion:
        """保存配置版本"""
        # 计算与上一个版本的差异
        diff = None
        if self._versions:
            prev_version = self._versions[-1]
            diff = self._calculate_diff(prev_version.config, self._current_config)
        
        version = ConfigVersion(
            id=str(uuid.uuid4()),
            name=name,
            timestamp=time.time(),
            config=self._current_config.copy(),
            diff=diff
        )
        
        self._versions.append(version)
        
        # 保持版本数量限制
        while len(self._versions) > self._max_versions:
            self._versions.pop(0)
        
        return version
    
    def _calculate_diff(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """计算配置差异"""
        diff = {}
        
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if old_val != new_val:
                diff[key] = {
                    "old": old_val,
                    "new": new_val
                }
        
        return diff
    
    def compare_versions(self, v1_id: str, v2_id: str) -> Dict[str, Dict[str, Any]]:
        """对比两个版本"""
        v1 = self._get_version(v1_id)
        v2 = self._get_version(v2_id)
        
        if not v1 or not v2:
            return {}
        
        return self._calculate_diff(v1.config, v2.config)
    
    def restore_version(self, version_id: str) -> bool:
        """恢复配置版本"""
        version = self._get_version(version_id)
        if not version:
            return False
        
        self._current_config = version.config.copy()
        return True
    
    def _get_version(self, version_id: str) -> Optional[ConfigVersion]:
        """获取版本"""
        for version in self._versions:
            if version.id == version_id:
                return version
        return None
    
    def get_versions(self) -> List[ConfigVersion]:
        """获取所有版本"""
        return list(self._versions)
    
    def get_version_by_name(self, name: str) -> Optional[ConfigVersion]:
        """按名称获取版本"""
        for version in self._versions:
            if version.name == name:
                return version
        return None
    
    def delete_version(self, version_id: str) -> bool:
        """删除版本"""
        for i, version in enumerate(self._versions):
            if version.id == version_id:
                del self._versions[i]
                return True
        return False
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._current_config.copy()
    
    def export_version(self, version_id: str) -> str:
        """导出版本配置为JSON"""
        import json
        version = self._get_version(version_id)
        if not version:
            return ""
        
        return json.dumps({
            "id": version.id,
            "name": version.name,
            "timestamp": version.timestamp,
            "config": version.config
        }, indent=2, ensure_ascii=False)
    
    def import_version(self, json_str: str) -> bool:
        """导入版本配置"""
        import json
        try:
            data = json.loads(json_str)
            version = ConfigVersion(
                id=data.get("id", str(uuid.uuid4())),
                name=data.get("name", "imported"),
                timestamp=data.get("timestamp", time.time()),
                config=data.get("config", {})
            )
            self._versions.append(version)
            return True
        except Exception:
            return False


def get_version_manager() -> ConfigVersionManager:
    """获取版本管理器单例"""
    if not hasattr(get_version_manager, '_instance'):
        get_version_manager._instance = ConfigVersionManager()
    return get_version_manager._instance