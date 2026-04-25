"""
Skill 市场管理器
支持 Skill 发现、安装、卸载
"""

import json
import time
import asyncio
import sqlite3
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx
import yaml


class SkillStatus(Enum):
    INSTALLED = "installed"
    AVAILABLE = "available"
    OUTDATED = "outdated"
    INSTALLING = "installing"
    ERROR = "error"


class SkillCategory(Enum):
    GENERAL = "general"
    WRITING = "writing"
    CODE = "code"
    RESEARCH = "research"
    BUSINESS = "business"
    CREATIVE = "creative"
    DOCUMENT = "document"
    DATA = "data"
    CUSTOM = "custom"


@dataclass
class Skill:
    """Skill 定义"""
    id: str
    name: str
    description: str = ""
    category: str = "general"
    version: str = "1.0.0"
    source: str = "local"
    manifest_url: str = ""
    local_path: str = ""
    status: str = "available"
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    triggers: List[str] = field(default_factory=list)
    installed_at: float = 0.0
    updated_at: float = 0.0
    rating: float = 0.0
    downloads: int = 0
    author: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class SkillManifest:
    """Skill Manifest (SKILL.md)"""
    name: str
    description: str
    category: str = "general"
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    author: str = ""
    tags: List[str] = field(default_factory=list)
    license: str = "MIT"


class SkillDatabase:
    """Skill 数据库管理"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                version TEXT DEFAULT '1.0.0',
                source TEXT DEFAULT 'local',
                manifest_url TEXT DEFAULT '',
                local_path TEXT DEFAULT '',
                status TEXT DEFAULT 'available',
                dependencies TEXT DEFAULT '[]',
                config_schema TEXT DEFAULT '{}',
                triggers TEXT DEFAULT '[]',
                installed_at REAL DEFAULT 0,
                updated_at REAL DEFAULT 0,
                rating REAL DEFAULT 0.0,
                downloads INTEGER DEFAULT 0,
                author TEXT DEFAULT '',
                tags TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
            CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
            CREATE TABLE IF NOT EXISTS skill_ratings (
                skill_id TEXT PRIMARY KEY,
                user_id TEXT,
                rating REAL,
                rated_at REAL,
                FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
            );
        """)
        conn.close()

    def add_skill(self, skill: Skill) -> bool:
        """添加 Skill"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT OR REPLACE INTO skills 
                (id, name, description, category, version, source, manifest_url,
                 local_path, status, dependencies, config_schema, triggers,
                 installed_at, updated_at, rating, downloads, author, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill.id, skill.name, skill.description, skill.category,
                skill.version, skill.source, skill.manifest_url,
                skill.local_path, skill.status,
                json.dumps(skill.dependencies),
                json.dumps(skill.config_schema),
                json.dumps(skill.triggers),
                skill.installed_at, skill.updated_at, skill.rating,
                skill.downloads, skill.author, json.dumps(skill.tags)
            ))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT * FROM skills WHERE id=?", (skill_id,)
            ).fetchone()
            if row:
                return self._row_to_skill(row)
            return None
        finally:
            conn.close()

    def list_skills(self, status: str = None, category: str = None) -> List[Skill]:
        """列出 Skills"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM skills WHERE 1=1"
            params = []
            if status:
                query += " AND status=?"
                params.append(status)
            if category:
                query += " AND category=?"
                params.append(category)
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_skill(row) for row in rows]
        finally:
            conn.close()

    def update_status(self, skill_id: str, status: str):
        """更新状态"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE skills SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), skill_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_local_path(self, skill_id: str, local_path: str):
        """更新本地路径"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE skills SET local_path=?, status=?, installed_at=? WHERE id=?",
                (local_path, SkillStatus.INSTALLED.value, time.time(), skill_id)
            )
            conn.commit()
        finally:
            conn.close()

    def delete_skill(self, skill_id: str):
        """删除 Skill"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
            conn.commit()
        finally:
            conn.close()

    def search_skills(self, query: str, category: str = None) -> List[Skill]:
        """搜索 Skills"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            sql = """
                SELECT * FROM skills 
                WHERE (name LIKE ? OR description LIKE ? OR tags LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%", f"%{query}%"]
            if category:
                sql += " AND category=?"
                params.append(category)
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_skill(row) for row in rows]
        finally:
            conn.close()

    def _row_to_skill(self, row: sqlite3.Row) -> Skill:
        """行转 Skill"""
        return Skill(
            id=row[0], name=row[1], description=row[2], category=row[3],
            version=row[4], source=row[5], manifest_url=row[6],
            local_path=row[7], status=row[8],
            dependencies=json.loads(row[9] or "[]"),
            config_schema=json.loads(row[10] or "{}"),
            triggers=json.loads(row[11] or "[]"),
            installed_at=row[12], updated_at=row[13], rating=row[14],
            downloads=row[15], author=row[16],
            tags=json.loads(row[17] or "[]")
        )


class SkillMarketBrowser:
    """Skill 市场浏览器"""

    # 内置市场 URL (可配置)
    DEFAULT_MARKETS = [
        "https://market.hermes-ai.cn/skills",
    ]

    def __init__(self):
        self.markets = self.DEFAULT_MARKETS.copy()

    def add_market(self, url: str):
        """添加市场"""
        if url not in self.markets:
            self.markets.append(url)

    async def browse_market(
        self, market_url: str = None, query: str = "",
        category: str = None, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """浏览市场"""
        url = market_url or self.markets[0] if self.markets else None
        if not url:
            return {"skills": [], "total": 0, "page": page}

        try:
            params = {"q": query, "page": page, "size": page_size}
            if category:
                params["category"] = category

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{url}/api/skills", params=params
                )
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return {"skills": [], "total": 0, "page": page}

    async def get_skill_details(self, skill_id: str, market_url: str = None) -> Optional[Skill]:
        """获取 Skill 详情"""
        url = market_url or self.markets[0] if self.markets else None
        if not url:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{url}/api/skills/{skill_id}")
                if response.status_code == 200:
                    data = response.json()
                    return Skill(**data)
        except Exception:
            pass

        return None


class SkillInstaller:
    """Skill 安装器"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    async def install_from_url(
        self, manifest_url: str, progress_callback: Callable[[float, str], None] = None
    ) -> Skill:
        """从 URL 安装"""
        manifest = await self._fetch_manifest(manifest_url)
        if not manifest:
            raise ValueError("无法获取 Skill Manifest")

        skill_id = manifest.name.lower().replace(" ", "_")
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # 下载 ZIP
            if progress_callback:
                progress_callback(0.1, "下载 Skill 包...")

            zip_url = manifest_url.rsplit("/", 1)[0] + "/skill.zip"
            zip_path = temp_dir / "skill.zip"

            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.get(zip_url)
                if response.status_code == 200:
                    zip_path.write_bytes(response.content)

            if progress_callback:
                progress_callback(0.3, "解压中...")

            # 解压
            skill_dir = self.skills_dir / skill_id
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(skill_dir)

            if progress_callback:
                progress_callback(0.7, "安装依赖...")

            # 安装依赖
            if manifest.dependencies:
                await self._install_dependencies(manifest.dependencies)

            if progress_callback:
                progress_callback(0.9, "完成安装...")

            # 保存到数据库
            skill = Skill(
                id=skill_id,
                name=manifest.name,
                description=manifest.description,
                category=manifest.category,
                version=manifest.version,
                source="market",
                manifest_url=manifest_url,
                local_path=str(skill_dir),
                status=SkillStatus.INSTALLED.value,
                dependencies=manifest.dependencies,
                config_schema=manifest.config,
                triggers=manifest.triggers,
                installed_at=time.time(),
                author=manifest.author,
                tags=manifest.tags
            )

            if progress_callback:
                progress_callback(1.0, "安装完成!")

            return skill

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def install_from_local(self, local_path: str | Path) -> Skill:
        """从本地安装"""
        path = Path(local_path)
        manifest_path = path / "SKILL.md"

        if not manifest_path.exists():
            raise ValueError(f"SKILL.md 不存在: {manifest_path}")

        manifest = self._parse_manifest(manifest_path)
        skill_id = manifest.name.lower().replace(" ", "_")

        # 复制到 skills 目录
        skill_dir = self.skills_dir / skill_id
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(path, skill_dir)

        return Skill(
            id=skill_id,
            name=manifest.name,
            description=manifest.description,
            category=manifest.category,
            version=manifest.version,
            source="local",
            manifest_url="",
            local_path=str(skill_dir),
            status=SkillStatus.INSTALLED.value,
            dependencies=manifest.dependencies,
            config_schema=manifest.config,
            triggers=manifest.triggers,
            installed_at=time.time(),
            author=manifest.author,
            tags=manifest.tags
        )

    def uninstall(self, skill_id: str, skill_path: str):
        """卸载 Skill"""
        path = Path(skill_path)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    async def update(self, skill: Skill) -> bool:
        """更新 Skill"""
        if not skill.manifest_url:
            return False

        try:
            manifest = await self._fetch_manifest(skill.manifest_url)
            if manifest and manifest.version != skill.version:
                # 删除旧版本
                self.uninstall(skill.id, skill.local_path)
                # 安装新版本
                new_skill = await self.install_from_url(skill.manifest_url)
                return True
        except Exception:
            pass

        return False

    async def _fetch_manifest(self, url: str) -> Optional[SkillManifest]:
        """获取 Manifest"""
        try:
            manifest_url = url.rsplit("/", 1)[0] + "/SKILL.md"
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(manifest_url)
                if response.status_code == 200:
                    return self._parse_manifest_content(response.text)
        except Exception:
            pass
        return None

    def _parse_manifest(self, path: Path) -> SkillManifest:
        """解析本地 Manifest"""
        content = path.read_text(encoding="utf-8")
        return self._parse_manifest_content(content)

    def _parse_manifest_content(self, content: str) -> SkillManifest:
        """解析 Manifest 内容"""
        try:
            data = yaml.safe_load(content)
            return SkillManifest(
                name=data.get("name", "Unknown"),
                description=data.get("description", ""),
                category=data.get("category", "general"),
                version=data.get("version", "1.0.0"),
                capabilities=data.get("capabilities", []),
                dependencies=data.get("dependencies", []),
                triggers=data.get("triggers", []),
                config=data.get("config", {}),
                author=data.get("author", ""),
                tags=data.get("tags", []),
                license=data.get("license", "MIT")
            )
        except Exception:
            # 简单解析
            lines = content.split("\n")
            name = ""
            desc = ""
            for line in lines:
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()

            return SkillManifest(name=name, description=desc)

    async def _install_dependencies(self, dependencies: List[str]):
        """安装依赖"""
        import subprocess
        for dep in dependencies:
            try:
                subprocess.run(
                    ["pip", "install", dep],
                    check=True,
                    capture_output=True
                )
            except Exception:
                pass


class SkillManager:
    """
    Skill 市场管理器
    
    功能：
    - 浏览市场
    - 安装/卸载/更新
    - 本地 Skill 管理
    """

    def __init__(self, db_path: str | Path = None, skills_dir: Path = None):
        from client.src.business.config import get_config_dir
        
        if db_path is None:
            db_path = get_config_dir() / "skills.db"
        
        if skills_dir is None:
            skills_dir = get_config_dir() / "skills"
        
        self.db = SkillDatabase(db_path)
        self.browser = SkillMarketBrowser()
        self.installer = SkillInstaller(skills_dir)
        self._skills_dir = skills_dir

    def add_skill(self, skill: Skill) -> bool:
        """添加 Skill 到数据库"""
        return self.db.add_skill(skill)

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        return self.db.get_skill(skill_id)

    def list_skills(self, status: str = None, category: str = None) -> List[Skill]:
        """列出 Skills"""
        return self.db.list_skills(status, category)

    def list_installed(self) -> List[Skill]:
        """列出已安装的 Skills"""
        return self.db.list_skills(status=SkillStatus.INSTALLED.value)

    def search_local(self, query: str, category: str = None) -> List[Skill]:
        """搜索本地 Skills"""
        return self.db.search_skills(query, category)

    async def install_from_market(
        self, manifest_url: str, progress_callback: Callable[[float, str], None] = None
    ) -> Skill:
        """从市场安装"""
        skill = await self.installer.install_from_url(manifest_url, progress_callback)
        self.db.add_skill(skill)
        return skill

    async def install_from_local(self, local_path: str) -> Skill:
        """从本地安装"""
        skill = await self.installer.install_from_local(local_path)
        self.db.add_skill(skill)
        return skill

    def uninstall(self, skill_id: str):
        """卸载 Skill"""
        skill = self.db.get_skill(skill_id)
        if skill:
            self.installer.uninstall(skill_id, skill.local_path)
            self.db.delete_skill(skill_id)

    async def update(self, skill_id: str) -> bool:
        """更新 Skill"""
        skill = self.db.get_skill(skill_id)
        if not skill:
            return False

        success = await self.installer.update(skill)
        if success:
            self.db.update_status(skill_id, SkillStatus.INSTALLED.value)
        return success

    async def browse_market(
        self, query: str = "", category: str = None, page: int = 1
    ) -> Dict[str, Any]:
        """浏览市场"""
        return await self.browser.browse_market(query=query, category=category, page=page)

    def register_to_agent(self, skill: Skill):
        """注册 Skill 到 Agent"""
        # TODO: 实现与 Agent 工具系统的集成
        pass


# 单例
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取 Skill 管理器单例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
