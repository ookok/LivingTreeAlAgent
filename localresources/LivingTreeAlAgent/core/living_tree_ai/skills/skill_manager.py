"""
技能管理器 - 支持 Hermes Agent 技能系统

实现技能的下载、管理、制作和上传
支持多平台技能格式
"""

import os
import json
import shutil
import zipfile
import tempfile
import subprocess
import requests
import asyncio
import uuid
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading


class SkillPlatform(Enum):
    """技能平台"""
    HERMES = "hermes"
    AGENT_SKILLS = "agent_skills"
    OPENAI = "openai"
    CUSTOM = "custom"


class SkillStatus(Enum):
    """技能状态"""
    INSTALLED = "installed"
    PENDING = "pending"
    UPDATING = "updating"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class SkillManifest:
    """技能清单"""
    skill_id: str
    name: str
    version: str
    description: str
    author: str
    platform: SkillPlatform
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class SkillInstance:
    """技能实例"""
    instance_id: str
    manifest: SkillManifest
    status: SkillStatus
    path: str
    enabled: bool = True
    last_used: Optional[float] = None
    usage_count: int = 0


class SkillManager:
    """技能管理器"""

    def __init__(self, skills_dir: str = "~/.living_tree_ai/skills"):
        """初始化技能管理器"""
        self.skills_dir = os.path.expanduser(skills_dir)
        self.manifests_dir = os.path.join(self.skills_dir, "manifests")
        self.instances_dir = os.path.join(self.skills_dir, "instances")
        self.temp_dir = os.path.join(self.skills_dir, "temp")

        # 创建目录
        for directory in [self.skills_dir, self.manifests_dir, self.instances_dir, self.temp_dir]:
            os.makedirs(directory, exist_ok=True)

        self.skills: Dict[str, SkillInstance] = {}
        self._load_skills()

    def _load_skills(self):
        """加载已安装的技能"""
        for filename in os.listdir(self.manifests_dir):
            if not filename.endswith('.json'):
                continue

            try:
                manifest_path = os.path.join(self.manifests_dir, filename)
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                manifest = SkillManifest(
                    skill_id=data["skill_id"],
                    name=data["name"],
                    version=data["version"],
                    description=data["description"],
                    author=data["author"],
                    platform=SkillPlatform(data["platform"]),
                    dependencies=data.get("dependencies", []),
                    tags=data.get("tags", []),
                    created_at=data.get("created_at", time.time()),
                    updated_at=data.get("updated_at", time.time())
                )

                instance_id = filename[:-5]  # 移除 .json 后缀
                instance_path = os.path.join(self.instances_dir, instance_id)
                status = SkillStatus.INSTALLED if os.path.exists(instance_path) else SkillStatus.ERROR

                instance = SkillInstance(
                    instance_id=instance_id,
                    manifest=manifest,
                    status=status,
                    path=instance_path,
                    enabled=data.get("enabled", True),
                    last_used=data.get("last_used"),
                    usage_count=data.get("usage_count", 0)
                )

                self.skills[instance_id] = instance
            except Exception as e:
                print(f"[SkillManager] 加载技能失败 {filename}: {e}")

    def _save_skill(self, instance: SkillInstance):
        """保存技能"""
        manifest_path = os.path.join(self.manifests_dir, f"{instance.instance_id}.json")
        data = {
            "skill_id": instance.manifest.skill_id,
            "name": instance.manifest.name,
            "version": instance.manifest.version,
            "description": instance.manifest.description,
            "author": instance.manifest.author,
            "platform": instance.manifest.platform.value,
            "dependencies": instance.manifest.dependencies,
            "tags": instance.manifest.tags,
            "created_at": instance.manifest.created_at,
            "updated_at": instance.manifest.updated_at,
            "enabled": instance.enabled,
            "last_used": instance.last_used,
            "usage_count": instance.usage_count
        }
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def download_skill(self, skill_url: str, platform: SkillPlatform = SkillPlatform.HERMES) -> Optional[SkillInstance]:
        """
        下载技能

        Args:
            skill_url: 技能 URL
            platform: 技能平台

        Returns:
            Optional[SkillInstance]: 技能实例
        """
        try:
            # 下载技能包
            temp_file = os.path.join(self.temp_dir, f"skill_{uuid.uuid4()}.zip")
            response = requests.get(skill_url, stream=True)
            response.raise_for_status()

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 解压
            instance_id = str(uuid.uuid4())
            instance_path = os.path.join(self.instances_dir, instance_id)
            os.makedirs(instance_path, exist_ok=True)

            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(instance_path)

            # 读取 manifest
            manifest_path = os.path.join(instance_path, "manifest.json")
            if not os.path.exists(manifest_path):
                raise ValueError("Manifest not found")

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

            manifest = SkillManifest(
                skill_id=manifest_data.get("skill_id", instance_id),
                name=manifest_data.get("name", "Unknown Skill"),
                version=manifest_data.get("version", "1.0.0"),
                description=manifest_data.get("description", ""),
                author=manifest_data.get("author", "Unknown"),
                platform=platform,
                dependencies=manifest_data.get("dependencies", []),
                tags=manifest_data.get("tags", [])
            )

            # 创建技能实例
            instance = SkillInstance(
                instance_id=instance_id,
                manifest=manifest,
                status=SkillStatus.INSTALLED,
                path=instance_path
            )

            # 保存
            self.skills[instance_id] = instance
            self._save_skill(instance)

            # 清理临时文件
            os.remove(temp_file)

            print(f"[SkillManager] 下载技能成功: {manifest.name}")
            return instance
        except Exception as e:
            print(f"[SkillManager] 下载技能失败: {e}")
            return None

    async def download_hermes_skill(self, skill_name: str) -> Optional[SkillInstance]:
        """
        下载 Hermes 官方技能

        Args:
            skill_name: 技能名称

        Returns:
            Optional[SkillInstance]: 技能实例
        """
        # 这里需要根据 Hermes 技能库的实际 API 来实现
        # 暂时使用模拟 URL
        skill_url = f"https://hermes-agent.nousresearch.com/skills/{skill_name}/download"
        return await self.download_skill(skill_url, SkillPlatform.HERMES)

    async def download_agent_skills_skill(self, skill_id: str) -> Optional[SkillInstance]:
        """
        下载 agent-skills.io 技能

        Args:
            skill_id: 技能 ID

        Returns:
            Optional[SkillInstance]: 技能实例
        """
        skill_url = f"https://agent-skills.io/api/skills/{skill_id}/download"
        return await self.download_skill(skill_url, SkillPlatform.AGENT_SKILLS)

    def create_skill(
        self,
        name: str,
        description: str,
        author: str,
        platform: SkillPlatform = SkillPlatform.CUSTOM,
        dependencies: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[SkillInstance]:
        """
        创建新技能

        Args:
            name: 技能名称
            description: 描述
            author: 作者
            platform: 平台
            dependencies: 依赖
            tags: 标签

        Returns:
            Optional[SkillInstance]: 技能实例
        """
        try:
            instance_id = str(uuid.uuid4())
            instance_path = os.path.join(self.instances_dir, instance_id)
            os.makedirs(instance_path, exist_ok=True)

            # 创建 manifest
            manifest = SkillManifest(
                skill_id=instance_id,
                name=name,
                version="1.0.0",
                description=description,
                author=author,
                platform=platform,
                dependencies=dependencies or [],
                tags=tags or []
            )

            # 保存 manifest
            manifest_path = os.path.join(instance_path, "manifest.json")
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "skill_id": manifest.skill_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "description": manifest.description,
                    "author": manifest.author,
                    "platform": manifest.platform.value,
                    "dependencies": manifest.dependencies,
                    "tags": manifest.tags
                }, f, indent=2, ensure_ascii=False)

            # 创建默认文件结构
            os.makedirs(os.path.join(instance_path, "src"), exist_ok=True)
            os.makedirs(os.path.join(instance_path, "tests"), exist_ok=True)

            # 创建示例代码
            with open(os.path.join(instance_path, "src", "main.py"), 'w', encoding='utf-8') as f:
                f.write('''"""
Skill main module
"""

def execute(input_data):
    """Execute the skill"""
    return {
        "result": "Skill executed successfully",
        "input": input_data
    }
''')

            # 创建技能实例
            instance = SkillInstance(
                instance_id=instance_id,
                manifest=manifest,
                status=SkillStatus.INSTALLED,
                path=instance_path
            )

            # 保存
            self.skills[instance_id] = instance
            self._save_skill(instance)

            print(f"[SkillManager] 创建技能成功: {name}")
            return instance
        except Exception as e:
            print(f"[SkillManager] 创建技能失败: {e}")
            return None

    async def upload_skill(self, instance_id: str, platform: SkillPlatform) -> bool:
        """
        上传技能

        Args:
            instance_id: 技能实例 ID
            platform: 目标平台

        Returns:
            bool: 是否成功
        """
        instance = self.skills.get(instance_id)
        if not instance:
            return False

        try:
            # 创建技能包
            temp_file = os.path.join(self.temp_dir, f"skill_{instance_id}.zip")

            with zipfile.ZipFile(temp_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 添加所有文件
                for root, dirs, files in os.walk(instance.path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, instance.path)
                        zipf.write(file_path, arcname)

            # 根据平台上传
            if platform == SkillPlatform.HERMES:
                # 这里需要实现 Hermes 技能上传 API
                print(f"[SkillManager] 上传技能到 Hermes: {instance.manifest.name}")
                # 模拟上传
                await asyncio.sleep(2)
            elif platform == SkillPlatform.AGENT_SKILLS:
                # 这里需要实现 agent-skills.io 上传 API
                print(f"[SkillManager] 上传技能到 agent-skills.io: {instance.manifest.name}")
                # 模拟上传
                await asyncio.sleep(2)

            # 清理临时文件
            os.remove(temp_file)

            print(f"[SkillManager] 上传技能成功: {instance.manifest.name}")
            return True
        except Exception as e:
            print(f"[SkillManager] 上传技能失败: {e}")
            return False

    def get_skill(self, instance_id: str) -> Optional[SkillInstance]:
        """获取技能"""
        return self.skills.get(instance_id)

    def get_all_skills(self) -> List[SkillInstance]:
        """获取所有技能"""
        return list(self.skills.values())

    def get_skills_by_platform(self, platform: SkillPlatform) -> List[SkillInstance]:
        """按平台获取技能"""
        return [s for s in self.skills.values() if s.manifest.platform == platform]

    def get_skills_by_tag(self, tag: str) -> List[SkillInstance]:
        """按标签获取技能"""
        return [s for s in self.skills.values() if tag in s.manifest.tags]

    def update_skill(self, instance_id: str, **kwargs) -> bool:
        """
        更新技能

        Args:
            instance_id: 技能实例 ID
            **kwargs: 更新的字段

        Returns:
            bool: 是否成功
        """
        instance = self.skills.get(instance_id)
        if not instance:
            return False

        try:
            # 更新 manifest
            if "name" in kwargs:
                instance.manifest.name = kwargs["name"]
            if "description" in kwargs:
                instance.manifest.description = kwargs["description"]
            if "version" in kwargs:
                instance.manifest.version = kwargs["version"]
            if "tags" in kwargs:
                instance.manifest.tags = kwargs["tags"]
            if "dependencies" in kwargs:
                instance.manifest.dependencies = kwargs["dependencies"]

            instance.manifest.updated_at = time.time()

            # 更新 instance
            if "enabled" in kwargs:
                instance.enabled = kwargs["enabled"]

            # 保存
            self._save_skill(instance)

            # 更新 manifest.json
            manifest_path = os.path.join(instance.path, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                data.update({
                    "name": instance.manifest.name,
                    "description": instance.manifest.description,
                    "version": instance.manifest.version,
                    "tags": instance.manifest.tags,
                    "dependencies": instance.manifest.dependencies
                })

                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"[SkillManager] 更新技能成功: {instance.manifest.name}")
            return True
        except Exception as e:
            print(f"[SkillManager] 更新技能失败: {e}")
            return False

    def delete_skill(self, instance_id: str) -> bool:
        """
        删除技能

        Args:
            instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        instance = self.skills.get(instance_id)
        if not instance:
            return False

        try:
            # 删除文件
            if os.path.exists(instance.path):
                shutil.rmtree(instance.path)

            manifest_path = os.path.join(self.manifests_dir, f"{instance_id}.json")
            if os.path.exists(manifest_path):
                os.remove(manifest_path)

            # 从内存中删除
            del self.skills[instance_id]

            print(f"[SkillManager] 删除技能成功: {instance.manifest.name}")
            return True
        except Exception as e:
            print(f"[SkillManager] 删除技能失败: {e}")
            return False

    def enable_skill(self, instance_id: str) -> bool:
        """启用技能"""
        instance = self.skills.get(instance_id)
        if not instance:
            return False

        instance.enabled = True
        self._save_skill(instance)
        print(f"[SkillManager] 启用技能: {instance.manifest.name}")
        return True

    def disable_skill(self, instance_id: str) -> bool:
        """禁用技能"""
        instance = self.skills.get(instance_id)
        if not instance:
            return False

        instance.enabled = False
        self._save_skill(instance)
        print(f"[SkillManager] 禁用技能: {instance.manifest.name}")
        return True

    def get_skill_stats(self) -> Dict[str, Any]:
        """获取技能统计"""
        total = len(self.skills)
        enabled = sum(1 for s in self.skills.values() if s.enabled)
        by_platform = {}
        for platform in SkillPlatform:
            count = sum(1 for s in self.skills.values() if s.manifest.platform == platform)
            if count > 0:
                by_platform[platform.value] = count

        return {
            "total_skills": total,
            "enabled_skills": enabled,
            "disabled_skills": total - enabled,
            "skills_by_platform": by_platform
        }

    def search_skills(self, query: str) -> List[SkillInstance]:
        """
        搜索技能

        Args:
            query: 搜索关键词

        Returns:
            List[SkillInstance]: 匹配的技能
        """
        query_lower = query.lower()
        results = []

        for instance in self.skills.values():
            if (
                query_lower in instance.manifest.name.lower() or
                query_lower in instance.manifest.description.lower() or
                any(query_lower in tag.lower() for tag in instance.manifest.tags)
            ):
                results.append(instance)

        return results


class SkillRegistry:
    """技能注册表"""

    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager
        self._registry: Dict[str, Dict] = {}
        self._load_registry()

    def _load_registry(self):
        """加载注册表"""
        # 这里可以从远程注册表加载技能信息
        # 暂时使用本地存储
        registry_file = os.path.join(self.skill_manager.skills_dir, "registry.json")
        if os.path.exists(registry_file):
            try:
                with open(registry_file, 'r', encoding='utf-8') as f:
                    self._registry = json.load(f)
            except Exception as e:
                print(f"[SkillRegistry] 加载注册表失败: {e}")

    def _save_registry(self):
        """保存注册表"""
        registry_file = os.path.join(self.skill_manager.skills_dir, "registry.json")
        try:
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(self._registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[SkillRegistry] 保存注册表失败: {e}")

    async def search_remote_skills(self, query: str, platform: SkillPlatform = SkillPlatform.HERMES) -> List[Dict]:
        """
        搜索远程技能

        Args:
            query: 搜索关键词
            platform: 平台

        Returns:
            List[Dict]: 技能信息
        """
        # 这里需要实现远程 API 调用
        # 暂时返回模拟数据
        if platform == SkillPlatform.HERMES:
            return [
                {
                    "skill_id": "hermes-skill-1",
                    "name": "Web Search",
                    "description": "Search the web for information",
                    "version": "1.0.0",
                    "author": "Nous Research",
                    "platform": "hermes",
                    "tags": ["web", "search"]
                },
                {
                    "skill_id": "hermes-skill-2",
                    "name": "Code Generator",
                    "description": "Generate code based on requirements",
                    "version": "1.0.0",
                    "author": "Nous Research",
                    "platform": "hermes",
                    "tags": ["code", "programming"]
                }
            ]
        elif platform == SkillPlatform.AGENT_SKILLS:
            return [
                {
                    "skill_id": "agent-skill-1",
                    "name": "Email Assistant",
                    "description": "Manage emails and schedule",
                    "version": "1.0.0",
                    "author": "Community",
                    "platform": "agent_skills",
                    "tags": ["email", "productivity"]
                }
            ]
        return []

    async def get_skill_details(self, skill_id: str, platform: SkillPlatform) -> Optional[Dict]:
        """
        获取技能详情

        Args:
            skill_id: 技能 ID
            platform: 平台

        Returns:
            Optional[Dict]: 技能详情
        """
        # 这里需要实现远程 API 调用
        # 暂时返回模拟数据
        return {
            "skill_id": skill_id,
            "name": "Sample Skill",
            "description": "A sample skill",
            "version": "1.0.0",
            "author": "Unknown",
            "platform": platform.value,
            "tags": ["sample"],
            "dependencies": [],
            "downloads": 100,
            "rating": 4.5
        }


class SkillExecutor:
    """技能执行器"""

    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager
        self._executors: Dict[str, Callable] = {}

    def execute_skill(self, instance_id: str, input_data: Dict) -> Dict:
        """
        执行技能

        Args:
            instance_id: 技能实例 ID
            input_data: 输入数据

        Returns:
            Dict: 执行结果
        """
        instance = self.skill_manager.get_skill(instance_id)
        if not instance or not instance.enabled:
            return {"error": "Skill not found or disabled"}

        try:
            # 更新使用统计
            instance.last_used = time.time()
            instance.usage_count += 1
            self.skill_manager._save_skill(instance)

            # 执行技能
            main_file = os.path.join(instance.path, "src", "main.py")
            if not os.path.exists(main_file):
                return {"error": "Main file not found"}

            # 动态导入并执行
            import sys
            sys.path.insert(0, instance.path)

            try:
                from src.main import execute
                result = execute(input_data)
                return result
            finally:
                if instance.path in sys.path:
                    sys.path.remove(instance.path)

        except Exception as e:
            return {"error": str(e)}

    def register_executor(self, skill_id: str, executor: Callable):
        """注册执行器"""
        self._executors[skill_id] = executor

    def unregister_executor(self, skill_id: str):
        """注销执行器"""
        if skill_id in self._executors:
            del self._executors[skill_id]


# 全局实例
_global_skill_manager: Optional[SkillManager] = None
_global_skill_registry: Optional[SkillRegistry] = None
_global_skill_executor: Optional[SkillExecutor] = None


def get_skill_manager() -> SkillManager:
    """获取技能管理器"""
    global _global_skill_manager
    if _global_skill_manager is None:
        _global_skill_manager = SkillManager()
    return _global_skill_manager


def get_skill_registry() -> SkillRegistry:
    """获取技能注册表"""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry(get_skill_manager())
    return _global_skill_registry


def get_skill_executor() -> SkillExecutor:
    """获取技能执行器"""
    global _global_skill_executor
    if _global_skill_executor is None:
        _global_skill_executor = SkillExecutor(get_skill_manager())
    return _global_skill_executor


# 示例使用
async def demo_skill_management():
    """演示技能管理"""
    manager = get_skill_manager()
    registry = get_skill_registry()
    executor = get_skill_executor()

    # 创建技能
    skill = manager.create_skill(
        name="Test Skill",
        description="A test skill",
        author="User"
    )

    if skill:
        print(f"创建技能: {skill.manifest.name}")

        # 执行技能
        result = executor.execute_skill(skill.instance_id, {"test": "data"})
        print(f"执行结果: {result}")

        # 搜索远程技能
        remote_skills = await registry.search_remote_skills("search")
        print(f"远程技能: {len(remote_skills)}")

        # 获取技能统计
        stats = manager.get_skill_stats()
        print(f"技能统计: {stats}")

        # 删除技能
        manager.delete_skill(skill.instance_id)


if __name__ == "__main__":
    asyncio.run(demo_skill_management())
