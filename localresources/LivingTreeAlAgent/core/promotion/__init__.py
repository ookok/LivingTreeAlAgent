# Living Tree AI — 对外软广推广系统
# Promotion System for Living Tree AI Assistant

"""
核心架构：

1. 差异化模板库 (template_engine.py)
   - 四大独家卖点：私有智能/根系互联/思维外脑/智能路由
   - 关键词匹配最佳模板
   - 兜底随机策略

2. 归因追踪 (attribution.py)
   - 短链生成：https://dl.living-tree.ai/v1?from=xxx
   - 分身标识/渠道标识/时间窗口
   - 点击归因记录

3. 静态页生成器 (landing_page.py)
   - GitHub Pages / Cloudflare Pages / Vercel 兼容
   - 三大卖点区块 + 多端下载 + 二维码
   - 纯静态，无依赖

4. 统一调度器 (system.py)
   - PromotionSystem 整合所有组件
   - generate_ad(): 根据内容生成软广
   - get_attribution_link(): 生成归因短链
"""

import os
import json
from pathlib import Path

# 项目根目录
_ROOT_DIR = Path(__file__).parent.parent.parent  # core/promotion -> hermes-desktop
_DATA_DIR = Path.home() / ".hermes-desktop" / "promotion"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

from .models import (
    AdTemplate,
    AdCampaign,
    AttributionRecord,
    PromotionResult,
    TemplateMatch,
    ClickAttribution,
)

from .system import PromotionSystem, get_promotion_system

__all__ = [
    # 系统
    "PromotionSystem",
    "get_promotion_system",
    # 模型
    "AdTemplate",
    "AdCampaign",
    "AttributionRecord",
    "PromotionResult",
    "TemplateMatch",
    "ClickAttribution",
]