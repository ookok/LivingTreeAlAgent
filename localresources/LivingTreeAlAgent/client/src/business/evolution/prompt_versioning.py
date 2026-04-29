"""
提示词版本管理和审计功能

实现提示词的版本控制、审计追踪、回滚和比较
借鉴 hermes-desktop 的版本管理理念
"""

import os
import json
import time
import uuid
import difflib
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import shutil


class VersionStatus(Enum):
    """版本状态"""
    DRAFT = "draft"        # 草稿
    PUBLISHED = "published"  # 已发布
    DEPRECATED = "deprecated"  # 已废弃
    ARCHIVED = "archived"    # 已归档


class ChangeType(Enum):
    """变更类型"""
    CREATED = "created"      # 创建
    UPDATED = "updated"      # 更新
    DELETED = "deleted"      # 删除
    ROLLBACK = "rollback"    # 回滚
    TAGGED = "tagged"        # 标记


@dataclass
class PromptVersion:
    """提示词版本"""
    version_id: str
    prompt_id: str
    content: str
    author: str
    timestamp: float
    status: VersionStatus
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parent_version_id: Optional[str] = None
    change_type: Optional[ChangeType] = None


@dataclass
class AuditLog:
    """审计日志"""
    log_id: str
    prompt_id: str
    version_id: str
    action: str
    actor: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptTag:
    """提示词标签"""
    tag_id: str
    name: str
    description: str
    color: str = "#3498db"
    created_by: str = "system"
    created_at: float = field(default_factory=time.time)


class PromptVersionManager:
    """提示词版本管理器"""

    def __init__(self, storage_dir: str = "~/.living_tree_ai/prompt_versions"):
        """初始化"""
        self.storage_dir = os.path.expanduser(storage_dir)
        self.prompts_dir = os.path.join(self.storage_dir, "prompts")
        self.versions_dir = os.path.join(self.storage_dir, "versions")
        self.audit_dir = os.path.join(self.storage_dir, "audit")
        self.tags_dir = os.path.join(self.storage_dir, "tags")

        # 创建目录
        for directory in [self.prompts_dir, self.versions_dir, self.audit_dir, self.tags_dir]:
            os.makedirs(directory, exist_ok=True)

        self._cache: Dict[str, List[PromptVersion]] = {}

    def create_prompt(
        self,
        name: str,
        content: str,
        author: str,
        description: str = ""
    ) -> Tuple[str, str]:
        """
        创建新提示词

        Args:
            name: 提示词名称
            content: 内容
            author: 创建者
            description: 描述

        Returns:
            Tuple[str, str]: (prompt_id, version_id)
        """
        prompt_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        version = PromptVersion(
            version_id=version_id,
            prompt_id=prompt_id,
            content=content,
            author=author,
            timestamp=time.time(),
            status=VersionStatus.DRAFT,
            description=description,
            change_type=ChangeType.CREATED
        )

        # 保存版本
        self._save_version(version)

        # 保存提示词元数据
        prompt_data = {
            "prompt_id": prompt_id,
            "name": name,
            "created_at": time.time(),
            "created_by": author,
            "current_version_id": version_id
        }

        prompt_file = os.path.join(self.prompts_dir, f"{prompt_id}.json")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, indent=2, ensure_ascii=False)

        # 记录审计日志
        self._log_audit(
            prompt_id=prompt_id,
            version_id=version_id,
            action="create_prompt",
            actor=author,
            details={"name": name, "description": description}
        )

        return prompt_id, version_id

    def update_prompt(
        self,
        prompt_id: str,
        content: str,
        author: str,
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> str:
        """
        更新提示词

        Args:
            prompt_id: 提示词ID
            content: 新内容
            author: 更新者
            description: 描述
            tags: 标签

        Returns:
            str: 新版本ID
        """
        # 获取当前版本
        current_version = self.get_current_version(prompt_id)
        if not current_version:
            raise ValueError(f"Prompt not found: {prompt_id}")

        # 创建新版本
        version_id = str(uuid.uuid4())
        version = PromptVersion(
            version_id=version_id,
            prompt_id=prompt_id,
            content=content,
            author=author,
            timestamp=time.time(),
            status=VersionStatus.DRAFT,
            description=description,
            tags=tags or [],
            parent_version_id=current_version.version_id,
            change_type=ChangeType.UPDATED
        )

        # 保存版本
        self._save_version(version)

        # 更新提示词元数据
        prompt_data = self._load_prompt_metadata(prompt_id)
        prompt_data["current_version_id"] = version_id
        prompt_file = os.path.join(self.prompts_dir, f"{prompt_id}.json")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, indent=2, ensure_ascii=False)

        # 记录审计日志
        self._log_audit(
            prompt_id=prompt_id,
            version_id=version_id,
            action="update_prompt",
            actor=author,
            details={"description": description, "tags": tags}
        )

        # 清除缓存
        if prompt_id in self._cache:
            del self._cache[prompt_id]

        return version_id

    def publish_version(self, version_id: str, author: str) -> bool:
        """发布版本"""
        version = self.get_version(version_id)
        if not version:
            return False

        version.status = VersionStatus.PUBLISHED
        version.timestamp = time.time()

        self._save_version(version)

        # 记录审计日志
        self._log_audit(
            prompt_id=version.prompt_id,
            version_id=version_id,
            action="publish_version",
            actor=author
        )

        return True

    def rollback_to_version(self, version_id: str, author: str) -> str:
        """
        回滚到指定版本

        Args:
            version_id: 要回滚到的版本ID
            author: 操作人

        Returns:
            str: 新回滚版本ID
        """
        target_version = self.get_version(version_id)
        if not target_version:
            raise ValueError(f"Version not found: {version_id}")

        # 创建回滚版本
        new_version_id = str(uuid.uuid4())
        rollback_version = PromptVersion(
            version_id=new_version_id,
            prompt_id=target_version.prompt_id,
            content=target_version.content,
            author=author,
            timestamp=time.time(),
            status=VersionStatus.PUBLISHED,
            description=f"Rollback to version {version_id}",
            tags=target_version.tags,
            parent_version_id=target_version.version_id,
            change_type=ChangeType.ROLLBACK
        )

        # 保存版本
        self._save_version(rollback_version)

        # 更新提示词元数据
        prompt_data = self._load_prompt_metadata(target_version.prompt_id)
        prompt_data["current_version_id"] = new_version_id
        prompt_file = os.path.join(self.prompts_dir, f"{target_version.prompt_id}.json")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, indent=2, ensure_ascii=False)

        # 记录审计日志
        self._log_audit(
            prompt_id=target_version.prompt_id,
            version_id=new_version_id,
            action="rollback_version",
            actor=author,
            details={"target_version_id": version_id}
        )

        # 清除缓存
        if target_version.prompt_id in self._cache:
            del self._cache[target_version.prompt_id]

        return new_version_id

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """获取版本"""
        version_file = os.path.join(self.versions_dir, f"{version_id}.json")
        if not os.path.exists(version_file):
            return None

        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return PromptVersion(
                version_id=data["version_id"],
                prompt_id=data["prompt_id"],
                content=data["content"],
                author=data["author"],
                timestamp=data["timestamp"],
                status=VersionStatus(data["status"]),
                description=data.get("description", ""),
                tags=data.get("tags", []),
                parent_version_id=data.get("parent_version_id"),
                change_type=ChangeType(data["change_type"]) if data.get("change_type") else None
            )
        except Exception:
            return None

    def get_current_version(self, prompt_id: str) -> Optional[PromptVersion]:
        """获取当前版本"""
        prompt_data = self._load_prompt_metadata(prompt_id)
        if not prompt_data:
            return None

        version_id = prompt_data.get("current_version_id")
        if not version_id:
            return None

        return self.get_version(version_id)

    def get_version_history(self, prompt_id: str) -> List[PromptVersion]:
        """获取版本历史"""
        if prompt_id in self._cache:
            return self._cache[prompt_id]

        versions = []
        version_files = []

        # 遍历所有版本文件
        for filename in os.listdir(self.versions_dir):
            if not filename.endswith('.json'):
                continue

            try:
                with open(os.path.join(self.versions_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("prompt_id") == prompt_id:
                    version = PromptVersion(
                        version_id=data["version_id"],
                        prompt_id=data["prompt_id"],
                        content=data["content"],
                        author=data["author"],
                        timestamp=data["timestamp"],
                        status=VersionStatus(data["status"]),
                        description=data.get("description", ""),
                        tags=data.get("tags", []),
                        parent_version_id=data.get("parent_version_id"),
                        change_type=ChangeType(data["change_type"]) if data.get("change_type") else None
                    )
                    versions.append(version)
            except Exception:
                continue

        # 按时间排序
        versions.sort(key=lambda v: v.timestamp, reverse=True)
        self._cache[prompt_id] = versions
        return versions

    def compare_versions(self, version_id1: str, version_id2: str) -> str:
        """比较两个版本"""
        version1 = self.get_version(version_id1)
        version2 = self.get_version(version_id2)

        if not version1 or not version2:
            return "版本不存在"

        diff = difflib.unified_diff(
            version1.content.splitlines(),
            version2.content.splitlines(),
            lineterm='',
            fromfile=f'version_{version_id1}',
            tofile=f'version_{version_id2}'
        )

        return '\n'.join(diff)

    def add_tag(self, version_id: str, tag_name: str, author: str) -> bool:
        """添加标签"""
        version = self.get_version(version_id)
        if not version:
            return False

        if tag_name not in version.tags:
            version.tags.append(tag_name)
            version.timestamp = time.time()
            self._save_version(version)

            # 记录审计日志
            self._log_audit(
                prompt_id=version.prompt_id,
                version_id=version_id,
                action="add_tag",
                actor=author,
                details={"tag": tag_name}
            )

        return True

    def remove_tag(self, version_id: str, tag_name: str, author: str) -> bool:
        """移除标签"""
        version = self.get_version(version_id)
        if not version:
            return False

        if tag_name in version.tags:
            version.tags.remove(tag_name)
            version.timestamp = time.time()
            self._save_version(version)

            # 记录审计日志
            self._log_audit(
                prompt_id=version.prompt_id,
                version_id=version_id,
                action="remove_tag",
                actor=author,
                details={"tag": tag_name}
            )

        return True

    def get_audit_logs(self, prompt_id: str, limit: int = 100) -> List[AuditLog]:
        """获取审计日志"""
        logs = []

        for filename in os.listdir(self.audit_dir):
            if not filename.endswith('.json'):
                continue

            try:
                with open(os.path.join(self.audit_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("prompt_id") == prompt_id:
                    log = AuditLog(
                        log_id=data["log_id"],
                        prompt_id=data["prompt_id"],
                        version_id=data["version_id"],
                        action=data["action"],
                        actor=data["actor"],
                        timestamp=data["timestamp"],
                        details=data.get("details", {})
                    )
                    logs.append(log)
            except Exception:
                continue

        # 按时间排序
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        return logs[:limit]

    def export_versions(self, prompt_id: str, output_dir: str) -> bool:
        """导出版本历史"""
        try:
            os.makedirs(output_dir, exist_ok=True)

            # 导出提示词元数据
            prompt_data = self._load_prompt_metadata(prompt_id)
            with open(os.path.join(output_dir, "prompt_metadata.json"), 'w', encoding='utf-8') as f:
                json.dump(prompt_data, f, indent=2, ensure_ascii=False)

            # 导出版本历史
            versions = self.get_version_history(prompt_id)
            versions_data = []
            for version in versions:
                versions_data.append({
                    "version_id": version.version_id,
                    "content": version.content,
                    "author": version.author,
                    "timestamp": version.timestamp,
                    "status": version.status.value,
                    "description": version.description,
                    "tags": version.tags,
                    "parent_version_id": version.parent_version_id,
                    "change_type": version.change_type.value if version.change_type else None
                })

            with open(os.path.join(output_dir, "versions.json"), 'w', encoding='utf-8') as f:
                json.dump(versions_data, f, indent=2, ensure_ascii=False)

            # 导出审计日志
            logs = self.get_audit_logs(prompt_id)
            logs_data = []
            for log in logs:
                logs_data.append({
                    "log_id": log.log_id,
                    "action": log.action,
                    "actor": log.actor,
                    "timestamp": log.timestamp,
                    "details": log.details
                })

            with open(os.path.join(output_dir, "audit_logs.json"), 'w', encoding='utf-8') as f:
                json.dump(logs_data, f, indent=2, ensure_ascii=False)

            return True
        except Exception:
            return False

    def import_versions(self, input_dir: str) -> str:
        """导入版本历史"""
        try:
            # 读取提示词元数据
            with open(os.path.join(input_dir, "prompt_metadata.json"), 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)

            prompt_id = prompt_data["prompt_id"]

            # 读取版本历史
            with open(os.path.join(input_dir, "versions.json"), 'r', encoding='utf-8') as f:
                versions_data = json.load(f)

            # 导入版本
            for version_data in versions_data:
                version = PromptVersion(
                    version_id=version_data["version_id"],
                    prompt_id=prompt_id,
                    content=version_data["content"],
                    author=version_data["author"],
                    timestamp=version_data["timestamp"],
                    status=VersionStatus(version_data["status"]),
                    description=version_data.get("description", ""),
                    tags=version_data.get("tags", []),
                    parent_version_id=version_data.get("parent_version_id"),
                    change_type=ChangeType(version_data["change_type"]) if version_data.get("change_type") else None
                )
                self._save_version(version)

            # 保存提示词元数据
            prompt_file = os.path.join(self.prompts_dir, f"{prompt_id}.json")
            with open(prompt_file, 'w', encoding='utf-8') as f:
                json.dump(prompt_data, f, indent=2, ensure_ascii=False)

            # 读取审计日志
            if os.path.exists(os.path.join(input_dir, "audit_logs.json")):
                with open(os.path.join(input_dir, "audit_logs.json"), 'r', encoding='utf-8') as f:
                    logs_data = json.load(f)

                # 导入审计日志
                for log_data in logs_data:
                    log = AuditLog(
                        log_id=log_data["log_id"],
                        prompt_id=prompt_id,
                        version_id=log_data.get("version_id", ""),
                        action=log_data["action"],
                        actor=log_data["actor"],
                        timestamp=log_data["timestamp"],
                        details=log_data.get("details", {})
                    )
                    self._save_audit_log(log)

            # 清除缓存
            if prompt_id in self._cache:
                del self._cache[prompt_id]

            return prompt_id
        except Exception as e:
            raise ValueError(f"导入失败: {str(e)}")

    def _save_version(self, version: PromptVersion):
        """保存版本"""
        version_file = os.path.join(self.versions_dir, f"{version.version_id}.json")
        data = {
            "version_id": version.version_id,
            "prompt_id": version.prompt_id,
            "content": version.content,
            "author": version.author,
            "timestamp": version.timestamp,
            "status": version.status.value,
            "description": version.description,
            "tags": version.tags,
            "parent_version_id": version.parent_version_id,
            "change_type": version.change_type.value if version.change_type else None
        }
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_audit_log(self, log: AuditLog):
        """保存审计日志"""
        log_file = os.path.join(self.audit_dir, f"{log.log_id}.json")
        data = {
            "log_id": log.log_id,
            "prompt_id": log.prompt_id,
            "version_id": log.version_id,
            "action": log.action,
            "actor": log.actor,
            "timestamp": log.timestamp,
            "details": log.details
        }
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _log_audit(self, prompt_id: str, version_id: str, action: str, actor: str, details: Optional[Dict] = None):
        """记录审计日志"""
        log = AuditLog(
            log_id=str(uuid.uuid4()),
            prompt_id=prompt_id,
            version_id=version_id,
            action=action,
            actor=actor,
            timestamp=time.time(),
            details=details or {}
        )
        self._save_audit_log(log)

    def _load_prompt_metadata(self, prompt_id: str) -> Optional[Dict]:
        """加载提示词元数据"""
        prompt_file = os.path.join(self.prompts_dir, f"{prompt_id}.json")
        if not os.path.exists(prompt_file):
            return None

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None


class PromptRegistry:
    """提示词注册表"""

    def __init__(self, version_manager: PromptVersionManager):
        self.version_manager = version_manager
        self._prompts: Dict[str, Dict] = {}
        self._load_prompts()

    def _load_prompts(self):
        """加载提示词"""
        for filename in os.listdir(self.version_manager.prompts_dir):
            if not filename.endswith('.json'):
                continue

            try:
                prompt_id = filename[:-5]  # 移除 .json 后缀
                data = self.version_manager._load_prompt_metadata(prompt_id)
                if data:
                    self._prompts[prompt_id] = data
            except Exception:
                continue

    def get_prompt(self, prompt_id: str) -> Optional[Dict]:
        """获取提示词"""
        return self._prompts.get(prompt_id)

    def get_all_prompts(self) -> List[Dict]:
        """获取所有提示词"""
        return list(self._prompts.values())

    def search_prompts(self, query: str) -> List[Dict]:
        """搜索提示词"""
        results = []
        query_lower = query.lower()

        for prompt_id, data in self._prompts.items():
            if query_lower in data.get("name", "").lower():
                results.append(data)

        return results


# 全局实例
_global_version_manager: Optional[PromptVersionManager] = None


def get_version_manager() -> PromptVersionManager:
    """获取版本管理器"""
    global _global_version_manager
    if _global_version_manager is None:
        _global_version_manager = PromptVersionManager()
    return _global_version_manager


def get_prompt_registry() -> PromptRegistry:
    """获取提示词注册表"""
    return PromptRegistry(get_version_manager())


# 示例使用
def demo_version_management():
    """演示版本管理"""
    manager = get_version_manager()

    # 创建提示词
    prompt_id, version_id1 = manager.create_prompt(
        name="数据分析专家",
        content="你是一个专业的数据分析专家，请分析以下数据...",
        author="user",
        description="基础数据分析提示词"
    )

    print(f"创建提示词: {prompt_id}, 版本: {version_id1}")

    # 更新提示词
    version_id2 = manager.update_prompt(
        prompt_id=prompt_id,
        content="你是一个专业的数据分析专家，精通统计学和机器学习，请详细分析以下数据...",
        author="user",
        description="增强版数据分析提示词"
    )

    print(f"更新提示词，新版本: {version_id2}")

    # 发布版本
    manager.publish_version(version_id2, "admin")
    print("发布版本")

    # 查看版本历史
    versions = manager.get_version_history(prompt_id)
    print(f"版本历史: {len(versions)} 个版本")

    # 比较版本
    if len(versions) >= 2:
        diff = manager.compare_versions(versions[0].version_id, versions[1].version_id)
        print("版本差异:")
        print(diff)

    # 回滚版本
    rollback_version = manager.rollback_to_version(version_id1, "admin")
    print(f"回滚到版本 {version_id1}，新回滚版本: {rollback_version}")

    # 查看审计日志
    logs = manager.get_audit_logs(prompt_id)
    print(f"审计日志: {len(logs)} 条记录")


if __name__ == "__main__":
    demo_version_management()
