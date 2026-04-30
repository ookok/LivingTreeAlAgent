"""
配置中心 (Configuration Center)

统一管理系统配置，支持动态调整和热加载。
"""

import json
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ConfigEntry:
    """配置条目"""
    key: str
    value: Any
    description: str = ""
    default: Any = None
    required: bool = False


class ConfigCenter:
    """
    配置中心
    
    功能：
    1. 从文件加载配置（JSON/YAML）
    2. 支持点路径访问（如 "industry.target_industry"）
    3. 配置热更新
    4. 默认值支持
    5. 配置验证
    
    使用方式：
    config = ConfigCenter("config.yaml")
    target_industry = config.get("industry.target_industry", "通用")
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._descriptions: Dict[str, str] = {}
        self._lock = Lock()
        
        # 加载默认配置
        self._load_defaults()
        
        # 如果提供了配置路径，加载配置文件
        if config_path:
            self.load_config(config_path)
        
        print("[ConfigCenter] 初始化完成")
    
    def _load_defaults(self):
        """加载默认配置"""
        defaults = {
            # 行业配置
            "industry.target_industry": "通用",
            "industry.supported_industries": [
                "机械制造", "电子电气", "化工", "环评", 
                "汽车", "制药", "建筑", "能源"
            ],
            
            # 检索配置
            "retrieval.top_k": 10,
            "retrieval.min_confidence": 0.6,
            "retrieval.enable_industry_filter": True,
            
            # 训练配置
            "training.model_name": "Qwen/Qwen2.5-7B-Instruct",
            "training.gpu_memory_gb": 64,
            "training.enable_reasoning_chain": True,
            "training.max_samples": 10000,
            
            # 知识库配置
            "knowledge.tier_weights": {
                "L1": 0.55,
                "L2": 0.35,
                "L3": 0.10
            },
            
            # 评估配置
            "evaluation.task_completion_threshold": 0.90,
            "evaluation.tool_call_threshold": 0.85,
            "evaluation.hallucination_threshold": 0.03,
            "evaluation.expert_score_threshold": 4.0,
            
            # 缓存配置
            "cache.enabled": True,
            "cache.ttl_seconds": 3600,
            
            # 日志配置
            "logging.level": "INFO",
            "logging.enabled": True
        }
        
        descriptions = {
            "industry.target_industry": "目标行业",
            "retrieval.top_k": "检索返回数量",
            "retrieval.min_confidence": "最小置信度阈值",
            "training.model_name": "训练模型名称",
            "training.gpu_memory_gb": "GPU显存大小(GB)"
        }
        
        self._defaults.update(defaults)
        self._descriptions.update(descriptions)
    
    def load_config(self, config_path: str):
        """
        从文件加载配置
        
        Args:
            config_path: 配置文件路径（支持JSON/YAML）
        """
        path = Path(config_path)
        
        if not path.exists():
            print(f"[ConfigCenter] 配置文件不存在: {config_path}，使用默认配置")
            return
        
        content = path.read_text(encoding='utf-8')
        
        try:
            if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                config_data = yaml.safe_load(content)
            else:
                config_data = json.loads(content)
            
            self._merge_config(config_data)
            print(f"[ConfigCenter] 已加载配置: {config_path}")
        
        except Exception as e:
            print(f"[ConfigCenter] 加载配置失败: {e}")
    
    def _merge_config(self, new_config: Dict[str, Any], parent_key: str = ""):
        """递归合并配置"""
        for key, value in new_config.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                self._merge_config(value, full_key)
            else:
                self._config[full_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点路径，如 "industry.target_industry"）
            default: 默认值
            
        Returns:
            配置值
        """
        with self._lock:
            # 优先返回用户配置
            if key in self._config:
                return self._config[key]
            
            # 其次返回默认配置
            if key in self._defaults:
                return self._defaults[key]
            
            # 最后返回用户提供的默认值
            return default
    
    def set(self, key: str, value: Any):
        """
        设置配置值（热更新）
        
        Args:
            key: 配置键
            value: 配置值
        """
        with self._lock:
            self._config[key] = value
        print(f"[ConfigCenter] 配置已更新: {key} = {value}")
    
    def get_description(self, key: str) -> str:
        """获取配置项描述"""
        return self._descriptions.get(key, "")
    
    def get_all_configs(self) -> Dict[str, Any]:
        """获取所有配置（合并用户配置和默认配置）"""
        result = {}
        all_keys = set(self._config.keys()) | set(self._defaults.keys())
        
        for key in all_keys:
            result[key] = self.get(key)
        
        return result
    
    def export_config(self, file_path: str):
        """导出配置到文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            config = self.get_all_configs()
            if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                yaml.dump(config, f, allow_unicode=True, indent=2)
            else:
                json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[ConfigCenter] 配置已导出到: {file_path}")
    
    def validate_config(self) -> List[str]:
        """验证配置是否完整"""
        errors = []
        
        required_keys = [
            "industry.target_industry",
            "training.model_name"
        ]
        
        for key in required_keys:
            if self.get(key) is None:
                errors.append(f"缺少必需配置: {key}")
        
        return errors


# 全局配置中心实例
_global_config = ConfigCenter()


def get_config() -> ConfigCenter:
    """获取全局配置中心实例"""
    return _global_config


def load_config_file(config_path: str):
    """加载配置文件到全局配置中心"""
    _global_config.load_config(config_path)


def get_config_value(key: str, default: Any = None) -> Any:
    """从全局配置中心获取配置值"""
    return _global_config.get(key, default)


def set_config_value(key: str, value: Any):
    """设置全局配置中心的配置值"""
    _global_config.set(key, value)


__all__ = [
    "ConfigCenter",
    "ConfigEntry",
    "get_config",
    "load_config_file",
    "get_config_value",
    "set_config_value"
]