"""
首次启动引导系统
First Run Wizard System

功能：
1. 检测首次启动
2. 管理引导步骤状态
3. 验证必须配置项
4. 支持跳过和默认选项
"""

import json
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import os


class ConfigStep(Enum):
    """配置步骤枚举"""
    # 必须配置项（阻塞式）
    OLLAMA = "ollama"                    # Ollama 服务配置（必须）
    
    # 可选配置项（可跳过）
    MODEL = "model"                      # 模型选择
    KNOWLEDGE_BASE = "knowledge_base"    # 知识库路径
    SEARCH_API = "search_api"           # 搜索 API
    USER_PROFILE = "user_profile"       # 用户画像
    APPEARANCE = "appearance"           # 外观设置


@dataclass
class WizardStep:
    """向导步骤"""
    step_id: ConfigStep
    title: str                          # 步骤标题
    description: str                    # 步骤描述
    required: bool                      # 是否必须
    skippable: bool = True              # 是否可跳过
    icon: str = "📌"                    # 步骤图标
    default_values: dict = field(default_factory=dict)  # 默认值


@dataclass
class WizardResult:
    """向导结果"""
    completed: bool                    # 是否完成
    skipped: bool                      # 是否跳过
    config_values: dict = field(default_factory=dict)  # 配置值
    error_message: str = ""            # 错误信息


class FirstRunConfig:
    """
    首次启动配置管理器
    
    管理首次启动引导流程的配置状态
    """
    
    # 向导步骤定义
    WIZARD_STEPS = [
        WizardStep(
            step_id=ConfigStep.OLLAMA,
            title="Ollama 服务配置",
            description="配置 Ollama 服务地址和默认模型。这是运行 AI 助手所必需的。",
            required=True,
            skippable=False,
            icon="🔧",
            default_values={
                "base_url": "http://localhost:11434",
                "default_model": "",
                "num_ctx": 8192,
                "keep_alive": "5m"
            }
        ),
        WizardStep(
            step_id=ConfigStep.MODEL,
            title="选择默认模型",
            description="选择要使用的默认 AI 模型。您也可以稍后在设置中更改。",
            required=False,
            skippable=True,
            icon="🤖",
            default_values={}
        ),
        WizardStep(
            step_id=ConfigStep.KNOWLEDGE_BASE,
            title="知识库路径",
            description="设置文档和项目文件的存储路径。留空使用默认路径。",
            required=False,
            skippable=True,
            icon="📁",
            default_values={
                "models_dir": "",
                "projects_dir": ""
            }
        ),
        WizardStep(
            step_id=ConfigStep.SEARCH_API,
            title="搜索 API 配置",
            description="配置网络搜索功能（可选）。留空将使用基础搜索功能。",
            required=False,
            skippable=True,
            icon="🔍",
            default_values={
                "serper_key": "",
                "brave_key": ""
            }
        ),
        WizardStep(
            step_id=ConfigStep.USER_PROFILE,
            title="用户画像",
            description="设置您的使用偏好，帮助 AI 提供更个性化的服务。",
            required=False,
            skippable=True,
            icon="👤",
            default_values={
                "display_name": "",
                "expertise_areas": []
            }
        ),
        WizardStep(
            step_id=ConfigStep.APPEARANCE,
            title="外观设置",
            description="自定义界面外观和布局偏好。",
            required=False,
            skippable=True,
            icon="🎨",
            default_values={
                "theme": "dark",
                "language": "zh-CN"
            }
        ),
    ]
    
    def __init__(self, data_dir: str = None):
        """
        初始化
        
        Args:
            data_dir: 数据目录路径
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = self._get_default_data_dir()
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 状态文件
        self.state_file = self.data_dir / "wizard_state.json"
        self.meta_file = self.data_dir / "wizard_meta.json"
    
    def _get_default_data_dir(self) -> Path:
        """获取默认数据目录"""
        user_dir = Path.home() / ".hermes-desktop"
        if os.access(str(Path.home()), os.W_OK):
            return user_dir
        return Path(__file__).parent.parent
    
    # ── 首次启动检测 ─────────────────────────────────────────────────
    
    def is_first_run(self) -> bool:
        """
        检测是否首次运行
        
        Returns:
            bool: True 表示首次运行
        """
        # 检查主配置文件是否存在
        config_file = self.data_dir / "config.json"
        if config_file.exists():
            # 检查是否已经完成引导
            return not self.is_wizard_completed()
        
        return True
    
    def is_wizard_completed(self) -> bool:
        """检查引导是否已完成"""
        if not self.meta_file.exists():
            return False
        
        try:
            data = json.loads(self.meta_file.read_text(encoding="utf-8"))
            return data.get("completed", False)
        except Exception:
            return False
    
    def mark_wizard_completed(self):
        """标记引导完成"""
        meta = {
            "completed": True,
            "completed_at": self._get_timestamp(),
            "version": "2.0"
        }
        self.meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def reset_wizard(self):
        """重置引导状态（允许重新运行引导）"""
        if self.state_file.exists():
            self.state_file.unlink()
        if self.meta_file.exists():
            self.meta_file.unlink()
    
    # ── 向导状态管理 ─────────────────────────────────────────────────
    
    def save_state(self, current_step: int, config_values: dict):
        """
        保存向导状态
        
        Args:
            current_step: 当前步骤索引
            config_values: 已配置的值
        """
        state = {
            "current_step": current_step,
            "config_values": config_values,
            "saved_at": self._get_timestamp()
        }
        self.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def load_state(self) -> tuple[int, dict]:
        """
        加载向导状态
        
        Returns:
            (current_step, config_values): 当前步骤和已配置的值
        """
        if not self.state_file.exists():
            return 0, {}
        
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data.get("current_step", 0), data.get("config_values", {})
        except Exception:
            return 0, {}
    
    def clear_state(self):
        """清除向导状态"""
        if self.state_file.exists():
            self.state_file.unlink()
    
    # ── 配置验证 ─────────────────────────────────────────────────────
    
    def validate_required_config(self, config_values: dict) -> tuple[bool, str]:
        """
        验证必须配置项
        
        Args:
            config_values: 配置值
            
        Returns:
            (is_valid, error_message)
        """
        # 检查 Ollama 配置
        ollama = config_values.get("ollama", {})
        if not ollama.get("base_url"):
            return False, "请配置 Ollama 服务地址"
        
        if not ollama.get("default_model"):
            return False, "请选择或输入默认模型名称"
        
        return True, ""
    
    def get_missing_required(self, config_values: dict) -> list[str]:
        """
        获取缺失的必须配置项
        
        Args:
            config_values: 配置值
            
        Returns:
            缺失的配置项列表
        """
        missing = []
        
        ollama = config_values.get("ollama", {})
        if not ollama.get("base_url"):
            missing.append("Ollama 服务地址")
        if not ollama.get("default_model"):
            missing.append("默认模型")
        
        return missing
    
    # ── 工具方法 ─────────────────────────────────────────────────────
    
    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_step_by_id(self, step_id: ConfigStep) -> Optional[WizardStep]:
        """根据 ID 获取步骤"""
        for step in self.WIZARD_STEPS:
            if step.step_id == step_id:
                return step
        return None
    
    def get_step_index(self, step_id: ConfigStep) -> int:
        """获取步骤索引"""
        for i, step in enumerate(self.WIZARD_STEPS):
            if step.step_id == step_id:
                return i
        return -1
    
    def get_next_required_step(self, from_index: int) -> Optional[int]:
        """
        获取下一个必须步骤索引
        
        Args:
            from_index: 从哪个索引开始查找
            
        Returns:
            下一个必须步骤索引，如果没有则返回 None
        """
        for i in range(from_index, len(self.WIZARD_STEPS)):
            if self.WIZARD_STEPS[i].required:
                return i
        return None
    
    # ── 配置合并 ─────────────────────────────────────────────────────
    
    def apply_wizard_config(self, wizard_config: dict, target_file: str = None) -> bool:
        """
        将向导配置应用到目标配置文件
        
        Args:
            wizard_config: 向导收集的配置
            target_file: 目标配置文件路径
            
        Returns:
            是否成功
        """
        if target_file is None:
            target_file = str(self.data_dir / "config.json")
        
        target_path = Path(target_file)
        
        # 读取现有配置
        existing = {}
        if target_path.exists():
            try:
                existing = json.loads(target_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        # 合并配置
        merged = self._merge_configs(existing, wizard_config)
        
        # 写入配置
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return True
        except Exception:
            return False
    
    def _merge_configs(self, base: dict, update: dict) -> dict:
        """深度合并配置"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result


# 单例
_first_run_config: Optional[FirstRunConfig] = None


def get_first_run_config() -> FirstRunConfig:
    """获取首次运行配置管理器单例"""
    global _first_run_config
    if _first_run_config is None:
        _first_run_config = FirstRunConfig()
    return _first_run_config
