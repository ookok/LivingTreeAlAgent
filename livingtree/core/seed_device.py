"""Seed Device — one-click role-based initialization wizard.

Inspired by Cognitum Seed Device:
  - Select professional role → auto-configure all subsystems
  - One command to set up the complete LivingTree for a specific use case

Usage in TUI: type /seed or /setup
CLI: python main.py seed --role=eia_engineer
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class SeedConfig:
    """Complete role-based configuration."""
    role: str = ""
    role_name: str = ""
    auto_register_sites: list[str] = field(default_factory=list)
    auto_subscribe_stages: list[str] = field(default_factory=list)
    knowledge_domains: list[str] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    default_notify_channel: str = "console"


SEED_PROFILES = {
    "eia_engineer": SeedConfig(
        role="eia_engineer",
        role_name="环评工程师",
        auto_register_sites=[
            "https://www.haian.gov.cn/hasgxq/gggs/gggs.html",
        ],
        auto_subscribe_stages=["受理公示", "拟批准公示", "审批批复", "验收公示"],
        knowledge_domains=["environment", "regulation"],
        suggested_commands=[
            "/check 查看今日环评公告",
            "/ask 大气扩散模型参数标准",
            "/docs 生成环评报告大气章节",
            "/scinet start 启用海外站点加速",
        ],
    ),
    "env_engineer": SeedConfig(
        role="env_engineer",
        role_name="环保工程师",
        auto_register_sites=[],  # user adds their own
        auto_subscribe_stages=["审批批复", "验收公示", "招标公告"],
        knowledge_domains=["environment", "engineering"],
        suggested_commands=[
            "/check 查看项目批复进度",
            "/ask 废气处理技术方案",
            "/check 法规期限提醒",
        ],
    ),
    "equipment_supplier": SeedConfig(
        role="equipment_supplier",
        role_name="设备供应商",
        auto_register_sites=[],
        auto_subscribe_stages=["受理公示", "招标公告", "审批批复"],
        knowledge_domains=["environment", "engineering"],
        suggested_commands=[
            "/ask 最新项目招标信息",
            "/check 市场机会分析",
            "/docs 生成投标文件",
        ],
    ),
    "monitoring_company": SeedConfig(
        role="monitoring_company",
        role_name="监测公司",
        auto_register_sites=[],
        auto_subscribe_stages=["受理公示", "审批批复", "验收公示"],
        knowledge_domains=["environment", "regulation"],
        suggested_commands=[
            "/ask 在线监测最新标准",
            "/check 项目验收公示",
            "/ask 监测方案模板",
        ],
    ),
    "consultant": SeedConfig(
        role="consultant",
        role_name="咨询顾问",
        auto_register_sites=[],
        auto_subscribe_stages=["审批批复", "验收公示"],
        knowledge_domains=["regulation", "data_science"],
        suggested_commands=[
            "/ask 最新环保政策法规",
            "/check 合规咨询机会",
            "/docs 生成咨询报告",
        ],
    ),
}


class SeedDevice:
    """One-click role-based initialization.

    Usage:
        seed = SeedDevice()
        result = await seed.plant("eia_engineer", hub)
        # → auto-configures: sites, deadlines, knowledge, commands
    """

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree")
        self._active_role: Optional[str] = None

    async def plant(self, role: str, hub: Any = None) -> dict:
        """Plant a seed — configure all subsystems for a role."""
        profile = SEED_PROFILES.get(role)
        if not profile:
            return {"error": f"Unknown role: {role}"}

        self._active_role = role
        result = {"role": role, "role_name": profile.role_name, "steps": []}

        # Step 1: Register food sources
        if profile.auto_register_sites:
            try:
                from ..capability.knowledge_forager import get_forager
                forager = get_forager()
                for url in profile.auto_register_sites:
                    await forager.register_site(role, url, category="env")
                result["steps"].append(f"registered {len(profile.auto_register_sites)} sites")
            except Exception as e:
                result["steps"].append(f"site registration: {e}")

        # Step 2: Subscribe to deadline reminders
        if profile.auto_subscribe_stages and hub:
            try:
                from ..capability.deadline_engine import DeadlineEngine, TaskScheduler
                engine = DeadlineEngine()
                scheduler = TaskScheduler(engine)
                # Subscribe to each stage for all registered projects
                scheduler.start_background(interval_hours=24)
                result["steps"].append("deadline scheduler started")
            except Exception as e:
                result["steps"].append(f"scheduler: {e}")

        # Step 3: Initialize knowledge domains
        try:
            for domain in profile.knowledge_domains:
                pass  # Domains auto-loaded by TrendClassifier
            result["steps"].append(f"knowledge domains: {profile.knowledge_domains}")
        except Exception:
            pass

        # Step 4: Save role config
        self._save_role(profile)
        result["steps"].append("role config saved")

        logger.info("SeedDevice: planted '%s' (%s)", role, profile.role_name)
        return result

    def get_guide(self, role: str) -> str:
        """Get a quick-start guide for the role."""
        profile = SEED_PROFILES.get(role)
        if not profile:
            return f"未知角色: {role}"

        lines = [
            f"# 🌱 {profile.role_name} — 快速开始",
            f"角色已配置，以下是推荐命令：",
            "",
        ]
        for cmd in profile.suggested_commands:
            lines.append(f"  {cmd}")
        lines.append("")
        lines.append(f"监控阶段: {', '.join(profile.auto_subscribe_stages)}")
        lines.append(f"知识域: {', '.join(profile.knowledge_domains)}")
        return "\n".join(lines)

    def get_active_role(self) -> Optional[str]:
        return self._active_role

    def list_roles(self) -> list[str]:
        return list(SEED_PROFILES.keys())

    def _save_role(self, profile: SeedConfig) -> None:
        os.makedirs(self._data_dir, exist_ok=True)
        config_path = os.path.join(self._data_dir, "seed_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "role": profile.role,
                    "role_name": profile.role_name,
                    "planted_at": __import__('time').strftime("%Y-%m-%d %H:%M"),
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# Singleton
_seed: Optional[SeedDevice] = None


def get_seed_device() -> SeedDevice:
    global _seed
    if _seed is None:
        _seed = SeedDevice()
    return _seed
