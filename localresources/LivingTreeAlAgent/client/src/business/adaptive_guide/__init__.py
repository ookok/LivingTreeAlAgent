"""
自适应引导式零配置系统
Adaptive Guide System

核心理念："能使用就不配置" - 三层可用性保障
1. 开箱即用 - 无任何配置 → 基础功能可用
2. 智能降级 - 缺少配置 → 自动寻找免费/公开替代方案
3. 引导增强 - 需要高级功能 → 一键引导配置（最短路径）

架构：
┌─────────────────────────────────────────────────────────────┐
│                    AdaptiveGuideManager                      │
│  自适应引导管理器 - 统一协调层                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                          │                                   │
▼                          ▼                                   ▼
┌─────────────┐    ┌───────────────┐    ┌─────────────────┐
│ AdaptiveRouter│    │DowngradeMatrix│    │ShortestPathGuide│
│ (自适应路由) │    │ (功能降级)    │    │ (最短路径引导)  │
└──────┬──────┘    └───────┬───────┘    └────────┬────────┘
       │                    │                      │
       └────────────────────┼──────────────────────┘
                            ▼
                 ┌─────────────────────┐
                 │  UserProfileDetector │
                 │   (用户画像识别)    │
                 └──────────┬──────────┘
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
          ┌──────────┐ ┌─────────┐ ┌────────────┐
          │BrowserAuto│ │ContextHelp│ │GuideProgress│
          │ (浏览器) │ │(上下文帮助)│ │ (进度保存) │
          └──────────┘ └─────────┘ └────────────┘
"""

__version__ = "1.0.0"
__author__ = "Hermes Desktop Team"

from .adaptive_router import AdaptiveRouter, RouteResult
from .downgrade_matrix import DowngradeMatrix, Implementation, AvailabilityLevel
from .shortest_path_guide import ShortestPathGuide, GuideFlow, GuideStep, GuideProgress
from .user_profile_detector import UserProfileDetector, UserProfile, TechLevel
from .context_help import ContextHelp, HelpCard
from .adaptive_guide_manager import AdaptiveGuideManager, get_guide_manager

__all__ = [
    # 版本
    "__version__",
    # 核心路由
    "AdaptiveRouter",
    "RouteResult",
    # 降级矩阵
    "DowngradeMatrix",
    "Implementation",
    "AvailabilityLevel",
    # 最短路径引导
    "ShortestPathGuide",
    "GuideFlow",
    "GuideStep",
    "GuideProgress",
    # 用户画像
    "UserProfileDetector",
    "UserProfile",
    "TechLevel",
    # 上下文帮助
    "ContextHelp",
    "HelpCard",
    # 统一管理器
    "AdaptiveGuideManager",
    "get_guide_manager",
]