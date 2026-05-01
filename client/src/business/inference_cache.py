"""
推理缓存模块 - 用于缓存LLM推理结果

核心功能：
1. 基于prompt的结果缓存
2. 支持TTL过期策略
3. 内存缓存 + 文件持久化
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import hashlib


class InferenceCache:
    """推理缓存"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self._cache_dir = Path(cache_dir or os.path.expanduser("~/.livingtree/cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(hours=24)
        
        self._load_cache()
    
    def _get_key(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成缓存键"""
        content = f"{system_prompt or ''}|||{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """获取缓存"""
        key = self._get_key(prompt, system_prompt)
        
        # 先检查内存缓存
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if datetime.fromisoformat(entry["timestamp"]) + self._ttl > datetime.now():
                return entry["response"]
            else:
                del self._memory_cache[key]
        
        # 再检查文件缓存
        file_path = self._cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    if datetime.fromisoformat(entry["timestamp"]) + self._ttl > datetime.now():
                        # 加载到内存
                        self._memory_cache[key] = entry
                        return entry["response"]
            except:
                pass
        
        return None
    
    def set(self, prompt: str, system_prompt: Optional[str], response: str):
        """设置缓存"""
        key = self._get_key(prompt, system_prompt)
        
        entry = {
            "prompt": prompt[:500],
            "system_prompt": system_prompt[:200] if system_prompt else None,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # 更新内存缓存
        self._memory_cache[key] = entry
        
        # 保存到文件
        file_path = self._cache_dir / f"{key}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False)
    
    def clear(self):
        """清空缓存"""
        self._memory_cache.clear()
        for file in self._cache_dir.glob("*.json"):
            file.unlink()
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "memory_entries": len(self._memory_cache),
            "disk_entries": len(list(self._cache_dir.glob("*.json")))
        }
    
    def _load_cache(self):
        """加载缓存"""
        # 只加载最近使用的缓存（最近1小时）
        recent_files = sorted(
            self._cache_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:50]
        
        for file in recent_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    key = file.stem
                    self._memory_cache[key] = entry
            except:
                pass


def get_inference_cache() -> InferenceCache:
    """获取推理缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = InferenceCache()
    return _cache_instance


_cache_instance = None