# Living Tree AI — 智能进化系统（终极版）
# Intelligent Evolution System for Living Tree AI Client

"""
三层自治 + 一层管控架构：

┌─────────────────────────────────────────────────────────────────┐
│                    客户端（进化个体）                              │
│              沙箱自愈 × 群体共生 × 隐身外联 × 中心可控              │
├─────────────────────────────────────────────────────────────────┤
│  自我修补 (patch_manager.py)                                      │
│    - 配置覆盖 / 逻辑补丁 / 白名单验证 / P2P广播                     │
│                                                                 │
│  体验优化 (experience_optimizer.py)                               │
│    - UI埋点 / 痛点捕获 / 行业感知蒸馏                             │
│                                                                 │
│  数据收集 (data_collector.py)                                     │
│    - 脱敏处理 / 周聚合 / 内容回流解析                             │
│                                                                 │
│  社区共享 (forum_client.py)                                       │
│    - .tree论坛 / 补丁分享 / 求助回复                             │
│                                                                 │
│  外部求解 (relay_client.py + BotPostingService)                   │
│    - 拟人化发帖 / Safety检查 / 频率限制                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 上报/发帖
┌─────────────────────────────────────────────────────────────────┐
│                   中继服务器（种群观察 + 管控）                     │
│           FastAPI + 文件存储 + Bot管理 + 静态页 + 熔断              │
├─────────────────────────────────────────────────────────────────┤
│  /api/collect      - 数据接收（验证/去重/存储）                    │
│  /api/forum/*      - 论坛发帖/拉取/点赞                          │
│  /api/bot/*        - Bot配置/发帖/熔断                           │
│  /api/weekly/<w>   - 原始数据下载                                │
│  /api/trends       - 进化趋势分析                                │
│  /api/safety       - 安全规则下发                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 聚合结果
┌─────────────────────────────────────────────────────────────────┐
│                  Web管理端（全局洞察）                             │
│              趋势分析 × Bot管理 × 远程熔断 × 下载导出                │
├─────────────────────────────────────────────────────────────────┤
│  /web/index.html   - 周数据表 / 热力图 / 趋势图                   │
│  /web/bots.html    - Bot配置管理 / 熔断控制                       │
│  /api/trends       - 进化趋势分析                                 │
│  /api/safety       - 安全规则下发                                 │
└─────────────────────────────────────────────────────────────────┘
"""

from pathlib import Path

# 数据目录
_DATA_DIR = Path.home() / ".hermes-desktop" / "evolution"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

from .models import (
    PatchDoc,
    PatchAction,
    PatchStatus,
    UIPainPoint,
    PainType,
    PainCause,
    WeeklyReport,
    ReportStatus,
    ClientConfig,
    EvolutionStats,
    # 终极版新增
    ForumPost,
    ForumPostType,
    PostStatus,
    ExternalPlatform,
    DistillationRule,
    DistillationCategory,
    IndustryInsight,
    BotConfig,
    ExternalPost,
    Reply回流,
)

from .system import EvolutionSystem, get_evolution_system

__all__ = [
    # 系统
    "EvolutionSystem",
    "get_evolution_system",
    # 模型
    "PatchDoc",
    "PatchAction",
    "PatchStatus",
    "UIPainPoint",
    "PainType",
    "PainCause",
    "WeeklyReport",
    "ReportStatus",
    "ClientConfig",
    "EvolutionStats",
    # 终极版新增
    "ForumPost",
    "ForumPostType",
    "PostStatus",
    "ExternalPlatform",
    "DistillationRule",
    "DistillationCategory",
    "IndustryInsight",
    "BotConfig",
    "ExternalPost",
    "Reply回流",
]