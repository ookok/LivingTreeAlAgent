"""
用户画像识别 - User Profile Detector

自动识别用户类型，提供最适合的引导方式：

1. 检测技术能力
2. 检测使用模式
3. 检测偏好设置
4. 生成用户画像
5. 推荐最优引导方式

使用示例：
    detector = UserProfileDetector()
    profile = detector.detect_profile()
    logger.info(f"技术等级: {profile.tech_level.value}")
    
    guide = detector.get_optimal_guide("weather_api", profile)
    logger.info(f"推荐引导: {guide.guide_type}")
"""

from core.logger import get_logger
logger = get_logger('adaptive_guide.user_profile_detector')

import os
import json
import platform
import subprocess
import logging
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TechLevel(Enum):
    """技术能力等级"""
    BEGINNER = "beginner"      # 初学者 - 需要一键式引导
    INTERMEDIATE = "intermediate"  # 中级 - 分步引导
    ADVANCED = "advanced"      # 高级 - 配置文件即可


class UsagePattern(Enum):
    """使用模式"""
    INTERACTIVE = "interactive"  # 交互式使用
    SCRIPTED = "scripted"        # 脚本化使用
    API = "api"                  # API集成使用
    EXPERIMENTAL = "experimental" # 探索式使用


class GuideType(Enum):
    """引导类型"""
    ONE_CLICK = "one_click"           # 一键式引导
    STEP_BY_STEP = "step_by_step"     # 分步引导
    CONFIG_FILE = "config_file"       # 配置文件引导
    VIDEO_TUTORIAL = "video_tutorial"  # 视频教程
    TEXT_DOCUMENT = "text_document"   # 文字文档


@dataclass
class UserProfile:
    """
    用户画像
    
    Attributes:
        user_id: 用户标识符
        tech_level: 技术能力等级
        usage_pattern: 使用模式
        prefers_visual: 是否偏好视觉引导
        prefers_video: 是否偏好视频教程
        environment: 运行环境信息
        detected_at: 检测时间
        config_history: 配置历史
        success_history: 成功历史
        preferred_guide_types: 偏好的引导类型
    """
    user_id: str = "default"
    tech_level: TechLevel = TechLevel.INTERMEDIATE
    usage_pattern: UsagePattern = UsagePattern.INTERACTIVE
    prefers_visual: bool = True
    prefers_video: bool = False
    environment: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = ""
    config_history: List[Dict[str, Any]] = field(default_factory=list)
    success_history: List[Dict[str, Any]] = field(default_factory=list)
    preferred_guide_types: List[GuideType] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "tech_level": self.tech_level.value,
            "usage_pattern": self.usage_pattern.value,
            "prefers_visual": self.prefers_visual,
            "prefers_video": self.prefers_video,
            "environment": self.environment,
            "detected_at": self.detected_at,
            "config_history_count": len(self.config_history),
            "success_history_count": len(self.success_history),
            "preferred_guide_types": [g.value for g in self.preferred_guide_types],
        }


@dataclass
class OptimalGuide:
    """最优引导推荐"""
    guide_type: GuideType
    guide_config: Dict[str, Any]
    reasoning: str
    estimated_time_minutes: int
    success_probability: float


class UserProfileDetector:
    """
    用户画像检测器
    
    通过多种方式检测用户画像：
    1. 环境检测
    2. 历史行为分析
    3. 配置模式识别
    4. 交互式探测
    """
    
    _instance: Optional["UserProfileDetector"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._profile: Optional[UserProfile] = None
        self._profile_cache_path = Path.home() / ".hermes" / "user_profile.json"
        self._init_environment()
    
    def _init_environment(self):
        """初始化环境信息"""
        self._env = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "has_docker": self._check_docker(),
            "has_gpu": self._check_gpu(),
            "is_wsl": self._is_wsl(),
            "is_docker": self._is_docker(),
            "network_type": self._detect_network_type(),
            "terminal_emulator": os.getenv("TERM", "unknown"),
            "shell": os.getenv("SHELL", "unknown"),
            "has_config_files": False,
            "terminal_history_size": 0,
        }
        
        # 检查配置文件
        self._env["has_config_files"] = self._check_config_files()
        self._env["terminal_history_size"] = self._get_terminal_history_size()
    
    def _check_docker(self) -> bool:
        """检查Docker是否安装"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _check_gpu(self) -> bool:
        """检查GPU是否可用"""
        # Windows: 检查NVIDIA
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["nvidia-smi", "-L"],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            except:
                pass
        
        # Linux/macOS: 检查CUDA
        try:
            result = subprocess.run(
                ["which", "nvidia-smi"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            pass
        
        return False
    
    def _is_wsl(self) -> bool:
        """检查是否在WSL中"""
        if platform.system() == "Linux":
            if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
                return True
            try:
                with open("/proc/version", "r") as f:
                    return "WSL" in f.read().upper()
            except:
                pass
        return False
    
    def _is_docker(self) -> bool:
        """检查是否在Docker容器中"""
        return os.path.exists("/.dockerenv")
    
    def _detect_network_type(self) -> str:
        """检测网络类型"""
        if self._is_docker():
            return "container"
        if self._is_wsl():
            return "wsl"
        
        # 检查网络连接
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return "online"
        except:
            return "offline"
    
    def _check_config_files(self) -> bool:
        """检查是否存在配置文件"""
        config_patterns = [
            Path.home() / ".hermes" / "config.yaml",
            Path.home() / ".hermes" / "settings.json",
            Path.home() / ".env",
            Path.cwd() / "config.yaml",
            Path.cwd() / ".env",
        ]
        
        for pattern in config_patterns:
            if pattern.exists():
                return True
        
        return False
    
    def _get_terminal_history_size(self) -> int:
        """获取终端历史大小"""
        history_files = [
            Path.home() / ".bash_history",
            Path.home() / ".zsh_history",
            Path.home() / ".history",
        ]
        
        total_lines = 0
        for hist_file in history_files:
            if hist_file.exists():
                try:
                    with open(hist_file, "r", encoding="utf-8", errors="ignore") as f:
                        total_lines += sum(1 for _ in f)
                except:
                    pass
        
        return total_lines
    
    def _detect_tech_level(self) -> TechLevel:
        """检测技术能力等级"""
        score = 0
        
        # 终端历史越多，技术能力可能越高
        if self._env["terminal_history_size"] > 1000:
            score += 2
        elif self._env["terminal_history_size"] > 100:
            score += 1
        
        # 有配置文件表示有经验
        if self._env["has_config_files"]:
            score += 1
        
        # Docker可用表示有开发经验
        if self._env["has_docker"]:
            score += 2
        
        # GPU可用表示有AI/ML经验
        if self._env["has_gpu"]:
            score += 1
        
        # WSL用户通常更有经验
        if self._env["is_wsl"]:
            score += 1
        
        # 根据得分判断等级
        if score >= 5:
            return TechLevel.ADVANCED
        elif score >= 2:
            return TechLevel.INTERMEDIATE
        else:
            return TechLevel.BEGINNER
    
    def _detect_usage_pattern(self) -> UsagePattern:
        """检测使用模式"""
        # 检查是否是脚本化使用
        script_indicators = [
            Path.cwd() / "run.sh",
            Path.cwd() / "start.sh",
            Path.cwd() / "script.py",
            Path.cwd() / "batch.sh",
        ]
        
        for indicator in script_indicators:
            if indicator.exists():
                return UsagePattern.SCRIPTED
        
        # 检查是否有API调用模式
        # 通过检查环境变量
        if os.getenv("API_MODE") or os.getenv("SCRIPT_MODE"):
            return UsagePattern.SCRIPTED
        
        # 检查是否是API集成
        if os.getenv("INTEGRATION_MODE"):
            return UsagePattern.API
        
        return UsagePattern.INTERACTIVE
    
    def detect_profile(self, user_id: str = "default") -> UserProfile:
        """
        检测用户画像（主入口）
        
        Args:
            user_id: 用户标识符
        
        Returns:
            UserProfile: 用户画像
        """
        # 如果已有缓存，直接返回
        if self._profile is not None:
            return self._profile
        
        profile = UserProfile(
            user_id=user_id,
            tech_level=self._detect_tech_level(),
            usage_pattern=self._detect_usage_pattern(),
            prefers_visual=self._env.get("prefers_visual", True),
            prefers_video=self._env.get("prefers_video", False),
            environment=self._env.copy(),
            detected_at=self._get_timestamp(),
        )
        
        # 根据检测结果调整偏好
        self._adjust_preferences(profile)
        
        self._profile = profile
        
        # 异步保存
        self._save_profile_async(profile)
        
        return profile
    
    def _adjust_preferences(self, profile: UserProfile):
        """根据环境调整偏好"""
        # 技术等级影响引导类型偏好
        if profile.tech_level == TechLevel.BEGINNER:
            profile.preferred_guide_types = [
                GuideType.ONE_CLICK,
                GuideType.VIDEO_TUTORIAL,
                GuideType.STEP_BY_STEP,
            ]
            profile.prefers_visual = True
            profile.prefers_video = True
        elif profile.tech_level == TechLevel.INTERMEDIATE:
            profile.preferred_guide_types = [
                GuideType.STEP_BY_STEP,
                GuideType.ONE_CLICK,
                GuideType.CONFIG_FILE,
            ]
            profile.prefers_visual = True
        else:
            profile.preferred_guide_types = [
                GuideType.CONFIG_FILE,
                GuideType.STEP_BY_STEP,
            ]
            profile.prefers_visual = False
            profile.prefers_video = False
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _save_profile_async(self, profile: UserProfile):
        """异步保存画像到磁盘"""
        import threading
        thread = threading.Thread(target=self._save_profile, args=(profile,))
        thread.daemon = True
        thread.start()
    
    def _save_profile(self, profile: UserProfile):
        """保存画像到磁盘"""
        try:
            self._profile_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._profile_cache_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save user profile: %s", e)
    
    def load_profile(self, user_id: str = "default") -> Optional[UserProfile]:
        """从磁盘加载画像"""
        try:
            if self._profile_cache_path.exists():
                with open(self._profile_cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                profile = UserProfile(
                    user_id=data.get("user_id", user_id),
                    tech_level=TechLevel(data.get("tech_level", "intermediate")),
                    usage_pattern=UsagePattern(data.get("usage_pattern", "interactive")),
                    prefers_visual=data.get("prefers_visual", True),
                    prefers_video=data.get("prefers_video", False),
                    environment=data.get("environment", {}),
                    detected_at=data.get("detected_at", ""),
                )
                
                self._profile = profile
                return profile
        except Exception as e:
            logger.warning("Failed to load user profile: %s", e)
        
        return None
    
    def update_profile(self, profile: UserProfile):
        """更新画像"""
        self._profile = profile
        self._save_profile(profile)
    
    def record_success(self, feature_id: str, guide_type: GuideType, time_taken: float):
        """
        记录引导成功
        
        Args:
            feature_id: 功能标识符
            guide_type: 引导类型
            time_taken: 花费时间（分钟）
        """
        if self._profile is None:
            return
        
        self._profile.success_history.append({
            "feature_id": feature_id,
            "guide_type": guide_type.value,
            "time_taken": time_taken,
            "timestamp": self._get_timestamp(),
        })
        
        # 如果同一功能多次成功，减少该引导类型的权重
        self._adjust_guide_preferences(feature_id, guide_type)
        
        self._save_profile(self._profile)
    
    def _adjust_guide_preferences(self, feature_id: str, guide_type: GuideType):
        """调整引导偏好"""
        if self._profile is None:
            return
        
        # 如果使用了某个引导类型并成功，增加其优先级
        if guide_type in self._profile.preferred_guide_types:
            # 移到最前面
            self._profile.preferred_guide_types.remove(guide_type)
            self._profile.preferred_guide_types.insert(0, guide_type)
    
    def record_failure(self, feature_id: str, guide_type: GuideType):
        """
        记录引导失败
        
        Args:
            feature_id: 功能标识符
            guide_type: 引导类型
        """
        if self._profile is None:
            return
        
        # 降低该引导类型的优先级
        if guide_type in self._profile.preferred_guide_types:
            self._profile.preferred_guide_types.remove(guide_type)
            self._profile.preferred_guide_types.append(guide_type)
        
        self._save_profile(self._profile)
    
    def get_optimal_guide(
        self, 
        feature_id: str, 
        profile: Optional[UserProfile] = None
    ) -> OptimalGuide:
        """
        获取最优引导方式
        
        Args:
            feature_id: 功能标识符
            profile: 用户画像（如果为None，使用检测的画像）
        
        Returns:
            OptimalGuide: 最优引导推荐
        """
        if profile is None:
            profile = self.detect_profile()
        
        guide_type = profile.preferred_guide_types[0] if profile.preferred_guide_types else GuideType.STEP_BY_STEP
        
        # 根据引导类型生成配置
        guide_config = self._generate_guide_config(feature_id, guide_type, profile)
        
        # 估算时间和成功率
        estimated_time = self._estimate_guide_time(guide_type, feature_id)
        success_prob = self._estimate_success_probability(guide_type, profile)
        
        reasoning = self._generate_reasoning(guide_type, profile)
        
        return OptimalGuide(
            guide_type=guide_type,
            guide_config=guide_config,
            reasoning=reasoning,
            estimated_time_minutes=estimated_time,
            success_probability=success_prob,
        )
    
    def _generate_guide_config(
        self, 
        feature_id: str, 
        guide_type: GuideType,
        profile: UserProfile
    ) -> Dict[str, Any]:
        """生成引导配置"""
        config = {
            "guide_type": guide_type.value,
            "feature_id": feature_id,
        }
        
        if guide_type == GuideType.ONE_CLICK:
            config["auto_detect_key"] = True
            config["prefill_support"] = True
            config["clipboard_monitoring"] = True
        elif guide_type == GuideType.STEP_BY_STEP:
            config["steps"] = self._generate_steps(feature_id)
            config["show_progress"] = True
        elif guide_type == GuideType.CONFIG_FILE:
            config["template_path"] = self._get_config_template_path(feature_id)
            config["validation_enabled"] = True
        
        return config
    
    def _generate_steps(self, feature_id: str) -> List[Dict[str, Any]]:
        """生成引导步骤"""
        # 通用步骤模板
        step_templates = {
            "weather_api": [
                {"title": "注册账号", "description": "访问官网注册免费账号", "link": "https://openweathermap.org/signup"},
                {"title": "获取API Key", "description": "在个人面板复制API Key", "link": "https://home.openweathermap.org/api_keys"},
                {"title": "配置Key", "description": "将API Key填入系统配置", "action": "open_config"},
            ],
            "map_service": [
                {"title": "获取API Key", "description": "在控制台创建应用获取Key", "link": None},
                {"title": "配置服务", "description": "将Key填入配置", "action": "open_config"},
            ],
        }
        
        return step_templates.get(feature_id, [
            {"title": "打开配置", "description": "导航到配置页面", "action": "open_config"},
        ])
    
    def _get_config_template_path(self, feature_id: str) -> str:
        """获取配置模板路径"""
        template_dir = Path(__file__).parent.parent / "templates"
        return str(template_dir / f"{feature_id}.yaml")
    
    def _estimate_guide_time(self, guide_type: GuideType, feature_id: str) -> int:
        """估算引导所需时间（分钟）"""
        base_times = {
            GuideType.ONE_CLICK: 1,
            GuideType.STEP_BY_STEP: 3,
            GuideType.CONFIG_FILE: 5,
            GuideType.VIDEO_TUTORIAL: 10,
            GuideType.TEXT_DOCUMENT: 5,
        }
        
        return base_times.get(guide_type, 3)
    
    def _estimate_success_probability(
        self, 
        guide_type: GuideType, 
        profile: UserProfile
    ) -> float:
        """估算成功率"""
        # 根据用户等级和引导类型估算
        if profile.tech_level == TechLevel.BEGINNER:
            if guide_type == GuideType.ONE_CLICK:
                return 0.9
            elif guide_type == GuideType.STEP_BY_STEP:
                return 0.7
            else:
                return 0.4
        elif profile.tech_level == TechLevel.INTERMEDIATE:
            if guide_type in (GuideType.STEP_BY_STEP, GuideType.ONE_CLICK):
                return 0.9
            elif guide_type == GuideType.CONFIG_FILE:
                return 0.8
            else:
                return 0.6
        else:  # ADVANCED
            if guide_type == GuideType.CONFIG_FILE:
                return 0.95
            else:
                return 0.8
    
    def _generate_reasoning(self, guide_type: GuideType, profile: UserProfile) -> str:
        """生成推荐理由"""
        if guide_type == GuideType.ONE_CLICK:
            return f"检测到您为{profile.tech_level.value}用户，推荐最简单的一键式引导，无需手动操作"
        elif guide_type == GuideType.STEP_BY_STEP:
            return f"根据您的技术等级，提供清晰的分步指导，确保每一步都能成功"
        elif guide_type == GuideType.CONFIG_FILE:
            return f"您有丰富的配置经验，直接编辑配置文件最高效"
        else:
            return "根据您的使用习惯推荐此引导方式"
    
    def get_context(self) -> Dict[str, Any]:
        """获取环境上下文"""
        return {
            "environment": self._env.copy(),
            "browser_available": self._check_browser(),
            "clipboard_access": True,  # PyQt6支持
            "auto_fill_support": True,
            "network_speed": self._measure_network_speed(),
        }
    
    def _check_browser(self) -> bool:
        """检查浏览器是否可用"""
        import webbrowser
        try:
            webbrowser.get()
            return True
        except:
            return False
    
    def _measure_network_speed(self) -> str:
        """测量网络速度"""
        try:
            import socket

            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return "fast"
        except:
            return "slow"


# 全局实例
_detector: Optional[UserProfileDetector] = None


def get_user_profile_detector() -> UserProfileDetector:
    """获取用户画像检测器全局实例"""
    global _detector
    if _detector is None:
        _detector = UserProfileDetector()
    return _detector