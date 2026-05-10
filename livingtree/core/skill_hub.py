"""Skill Hub — open marketplace + QGIS-style plugin management.

Merged: CowAgent Skill Hub + QGIS Plugin Manager (enhanced_skill_hub.py).

Features:
  - One-click install from GitHub/Git
  - Version compatibility (semver, LT version range)
  - Dependency resolution (recursive, conflict detection)
  - Security sandbox hints (5 levels)
  - Rating + install count + enable/disable toggle
  - Remote hub index fetch
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import re as _re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from loguru import logger

SKILLS_DIR = Path(".livingtree/skills")
SKILL_HUB_URL = "https://raw.githubusercontent.com/ookok/livingtree-skills/main/index.json"
GIT_CLONE_TIMEOUT = 60
LIVINGTREE_VERSION = "2.3.0"
SANDBOX_LEVELS = ["full", "network", "filesystem", "shell", "none"]


@dataclass
class SkillMeta:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    source: str = ""          # "github", "git", "local", "hub"
    repo_url: str = ""
    category: str = "general"
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    lt_version_min: str = "2.0.0"
    lt_version_max: str = "3.0.0"
    sandbox_level: str = "filesystem"
    ratings_count: int = 0
    ratings_avg: float = 0.0
    installs: int = 0
    updated_at: str = ""
    installed: bool = False
    install_path: str = ""
    installed_at: float = 0.0
    enabled: bool = True
    compatible: bool = True
    compatibility_note: str = ""


class SkillHub:
    """Unified skill marketplace + plugin manager."""

    def __init__(self):
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        self._installed: dict[str, SkillMeta] = {}
        self._remote_index: list[SkillMeta] = []
        self._load_installed()

    # ═══ Persistence ═══

    def _load_installed(self):
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            meta_file = skill_dir / "skill.json"
            if meta_file.is_file():
                try:
                    data = _json.loads(meta_file.read_text())
                    meta = SkillMeta()
                    for k in SkillMeta.__dataclass_fields__:
                        if k in data:
                            setattr(meta, k, data[k])
                    meta.installed = True
                    meta.install_path = str(skill_dir)
                    meta.compatible = self._check_compat(meta.lt_version_min, meta.lt_version_max)
                    self._installed[meta.name] = meta
                except Exception as e:
                    logger.debug(f"Skill load {skill_dir.name}: {e}")

    def _save_installed(self, meta: SkillMeta):
        path = Path(meta.install_path) if meta.install_path else SKILLS_DIR / meta.name
        path.mkdir(parents=True, exist_ok=True)
        data = {k: getattr(meta, k) for k in SkillMeta.__dataclass_fields__
                if k not in ("installed", "compatible", "compatibility_note")}
        (path / "skill.json").write_text(_json.dumps(data, ensure_ascii=False, indent=2))

    # ═══ Version Compatibility ═══

    def _check_compat(self, min_v: str, max_v: str) -> bool:
        if not min_v or not max_v:
            return True
        try:
            lt = self._parse_semver(LIVINGTREE_VERSION)
            lo = self._parse_semver(min_v)
            hi = self._parse_semver(max_v)
            return lo <= lt <= hi
        except Exception:
            return True

    @staticmethod
    def _parse_semver(v: str) -> tuple:
        parts = v.replace("v", "").split(".")
        return tuple(int(p) for p in parts[:3] if p.isdigit())

    def check_skill_compat(self, name: str) -> dict:
        meta = self._installed.get(name)
        if not meta:
            return {"compatible": False, "error": "not found"}
        ok = self._check_compat(meta.lt_version_min, meta.lt_version_max)
        return {"compatible": ok, "required": f"{meta.lt_version_min}..{meta.lt_version_max}"}

    # ═══ Dependency Resolution ═══

    def resolve_dependencies(self, name: str, resolved: set = None) -> dict:
        if resolved is None:
            resolved = set()
        if name in resolved:
            return {"ok": True, "dependencies": [], "conflicts": []}

        meta = self._installed.get(name)
        if not meta:
            return {"ok": False, "error": f"Skill not found: {name}"}

        resolved.add(name)
        deps, conflicts = [], []

        for dep_name, dep_version in meta.dependencies.items():
            dep = self._installed.get(dep_name)
            if not dep:
                conflicts.append({"skill": dep_name, "reason": "not installed"})
            elif not self._version_matches(dep.version, dep_version):
                conflicts.append({"skill": dep_name, "required": dep_version,
                                 "installed": dep.version, "reason": "version mismatch"})
            else:
                sub = self.resolve_dependencies(dep_name, resolved)
                deps.append(dep_name)
                deps.extend(sub.get("dependencies", []))
                conflicts.extend(sub.get("conflicts", []))

        return {"ok": len(conflicts) == 0, "dependencies": deps, "conflicts": conflicts}

    @staticmethod
    def _version_matches(installed: str, constraint: str) -> bool:
        if not constraint:
            return True
        for op in (">=", "<=", "==", ">", "<", "~="):
            if constraint.startswith(op):
                ver = constraint[len(op):]
                a = SkillHub._parse_semver(installed)
                b = SkillHub._parse_semver(ver)
                if op == ">=": return a >= b
                if op == "<=": return a <= b
                if op == "==": return a == b
                if op == ">": return a > b
                if op == "<": return a < b
                if op == "~=": return a[:2] == b[:2]
                return a >= b
        return True

    # ═══ Sandbox Assessment ═══

    def assess_sandbox(self, name: str) -> dict:
        meta = self._installed.get(name)
        if not meta:
            return {"level": "unknown", "risks": []}

        risks = []
        if meta.sandbox_level == "shell":
            risks.extend(["可执行系统命令", "可修改系统文件"])
        elif meta.sandbox_level == "filesystem":
            risks.append("可读写工作目录文件")
        elif meta.sandbox_level == "network":
            risks.append("可发起网络请求")

        risk_level = "safe" if meta.sandbox_level in ("none", "network") else (
            "caution" if meta.sandbox_level == "filesystem" else "review")
        return {"level": meta.sandbox_level, "risks": risks, "recommendation": risk_level}

    # ═══ Enable/Disable ═══

    def toggle(self, name: str, enabled: bool = True) -> bool:
        meta = self._installed.get(name)
        if not meta:
            return False
        meta.enabled = enabled
        self._save_installed(meta)
        logger.info(f"Skill '{name}': {'enabled' if enabled else 'disabled'}")
        return True

    # ═══ Remote Index ═══

    async def fetch_hub_index(self, hub_url: str = "") -> list[SkillMeta]:
        import httpx
        url = hub_url or SKILL_HUB_URL
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    items = resp.json()
                    if isinstance(items, dict):
                        items = items.get("skills", items.get("data", []))
                    if isinstance(items, list):
                        self._remote_index = []
                        for it in items:
                            if isinstance(it, dict):
                                m = SkillMeta()
                                for k in SkillMeta.__dataclass_fields__:
                                    if k in it:
                                        setattr(m, k, it[k])
                                self._remote_index.append(m)
                        logger.info(f"Skill hub: {len(self._remote_index)} skills available")
                        return self._remote_index
        except Exception as e:
            logger.debug(f"Skill hub fetch: {e}")
        return []

    # ═══ Install / Uninstall ═══

    async def install(self, name_or_url: str) -> Optional[SkillMeta]:
        if name_or_url.startswith(("http://", "https://", "git@")):
            return await self._install_from_url(name_or_url)
        return await self._install_from_hub(name_or_url)

    async def _install_from_hub(self, name: str) -> Optional[SkillMeta]:
        if name in self._installed:
            return self._installed[name]
        if not self._remote_index:
            await self.fetch_hub_index()
        for s in self._remote_index:
            if s.name == name:
                return await self._install_from_url(s.repo_url, name)
        return None

    async def _install_from_url(self, url: str, name: str = "") -> Optional[SkillMeta]:
        parsed = urlparse(url)
        install_path = SKILLS_DIR / (name or Path(parsed.path).stem.replace(".git", ""))
        if install_path.exists():
            shutil.rmtree(install_path, ignore_errors=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", url, str(install_path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=GIT_CLONE_TIMEOUT)
            if proc.returncode != 0:
                raise RuntimeError("git clone failed")
        except FileNotFoundError:
            raise RuntimeError("git not found")

        meta_file = install_path / "skill.json"
        if meta_file.is_file():
            data = _json.loads(meta_file.read_text())
            meta = SkillMeta(
                name=data.get("name", install_path.name),
                installed=True, install_path=str(install_path),
                installed_at=time.time(), source="github" if "github" in url else "git",
                repo_url=url,
            )
            for k in SkillMeta.__dataclass_fields__:
                if k in data and k not in ("installed", "install_path", "installed_at", "source", "repo_url"):
                    setattr(meta, k, data[k])
        else:
            meta = SkillMeta(name=install_path.name, installed=True,
                           install_path=str(install_path), installed_at=time.time(),
                           source="git", repo_url=url)

        self._installed[meta.name] = meta
        self._save_installed(meta)

        if meta.dependencies:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "pip", "install", *meta.dependencies.values(),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
            except Exception:
                pass

        logger.info(f"Skill installed: {meta.name} v{meta.version}")
        return meta

    def uninstall(self, name: str) -> bool:
        if name not in self._installed:
            return False
        meta = self._installed.pop(name)
        path = Path(meta.install_path) if meta.install_path else SKILLS_DIR / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        return True

    # ═══ List / Search ═══

    def list_installed(self) -> list[SkillMeta]:
        return list(self._installed.values())

    def list_all(self, category: str = "") -> list[SkillMeta]:
        specs = list(self._installed.values())
        for s in self._remote_index:
            if s.name not in self._installed:
                specs.append(s)
        if category:
            specs = [s for s in specs if s.category == category]
        specs.sort(key=lambda s: (-s.installed, -s.ratings_avg, -s.installs))
        return specs

    def search(self, keyword: str) -> list[SkillMeta]:
        kw = keyword.lower()
        results = []
        for s in self._remote_index:
            if kw in s.name.lower() or kw in s.description.lower() or kw in s.category.lower():
                results.append(s)
        for s in self._installed.values():
            if kw in s.name.lower() or kw in s.description.lower():
                if s not in results:
                    results.append(s)
        return results

    # ═══ Stats ═══

    def stats(self) -> dict:
        installed = list(self._installed.values())
        return {
            "total": len(installed),
            "installed": sum(1 for s in installed if s.installed),
            "enabled": sum(1 for s in installed if s.enabled),
            "compatible": sum(1 for s in installed if s.compatible),
            "categories": list(set(s.category for s in installed)),
            "remote_available": len(self._remote_index),
            "sandbox_summary": {
                level: sum(1 for s in installed if s.sandbox_level == level)
                for level in SANDBOX_LEVELS
            },
            "skills": [
                {"name": s.name, "version": s.version, "category": s.category,
                 "enabled": s.enabled, "compatible": s.compatible,
                 "sandbox": s.sandbox_level, "rating": s.ratings_avg,
                 "deps": list(s.dependencies.keys())}
                for s in installed
            ],
        }

    # ═══ Render HTML (QGIS-style plugin table) ═══

    def render_html(self) -> str:
        all_specs = self.list_all()
        if not all_specs:
            return '<div class="card"><h2>🧩 插件生态</h2><p style="color:var(--dim)">暂无插件 — livingtree skill install X</p></div>'

        rows = ""
        for s in all_specs:
            enabled_icon = "✅" if s.enabled else "⏸"
            compat_icon = "🟢" if s.compatible else "🔴"
            sandbox_color = {"full": "var(--err)", "shell": "var(--err)", "filesystem": "var(--warn)",
                           "network": "var(--accent)", "none": "var(--accent)"}.get(s.sandbox_level, "var(--dim)")
            stars = "⭐" * min(5, int(s.ratings_avg)) if s.ratings_avg > 0 else "—"
            deps = ", ".join(s.dependencies.keys()) if s.dependencies else "无"
            rows += (
                f'<tr style="border-bottom:1px solid var(--border)">'
                f'<td style="padding:6px 8px;font-size:11px">{enabled_icon} <b>{s.name}</b>'
                f' <span style="font-size:9px;color:var(--dim)">v{s.version}</span>'
                f'<div style="font-size:9px;color:var(--dim)">{s.description[:60]}</div></td>'
                f'<td style="padding:6px 4px;text-align:center;font-size:10px">{s.category}</td>'
                f'<td style="padding:6px 4px;text-align:center;font-size:10px">{compat_icon}</td>'
                f'<td style="padding:6px 4px;text-align:center;font-size:10px;color:{sandbox_color}">{s.sandbox_level}</td>'
                f'<td style="padding:6px 4px;text-align:center;font-size:10px">{stars}</td>'
                f'<td style="padding:6px 4px;text-align:center;font-size:9px;color:var(--dim)">{deps}</td></tr>'
            )

        return f'''<div class="card">
<h2>🧩 插件生态系统 <span style="font-size:10px;color:var(--dim)">— QGIS Plugin Manager 风格</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0;display:flex;gap:12px">
  <span>总计 <b>{len(all_specs)}</b></span>
  <span>已启用 <b>{sum(1 for s in all_specs if s.enabled)}</b></span>
  <span>兼容 <b>{sum(1 for s in all_specs if s.compatible)}</b></span>
</div>
<table style="width:100%;border-collapse:collapse;font-size:11px">
<thead><tr style="border-bottom:2px solid var(--border);font-size:10px;color:var(--dim)">
  <th style="padding:6px 8px">插件</th><th style="padding:6px 4px;text-align:center">分类</th>
  <th style="padding:6px 4px;text-align:center">兼容</th><th style="padding:6px 4px;text-align:center">沙箱</th>
  <th style="padding:6px 4px;text-align:center">评分</th><th style="padding:6px 4px;text-align:center">依赖</th>
</tr></thead><tbody>{rows}</tbody></table></div>'''


# ═══ Singleton ═══

_hub: Optional[SkillHub] = None


def get_skill_hub() -> SkillHub:
    global _hub
    if _hub is None:
        _hub = SkillHub()
    return _hub


def get_enhanced_hub() -> SkillHub:
    """Backward-compatible alias for get_skill_hub."""
    return get_skill_hub()
