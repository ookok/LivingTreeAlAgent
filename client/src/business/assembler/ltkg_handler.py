"""
📦 LTKG处理器 (LTKG Handler)
=============================

LTKG = Life Tree Knowledge Grove

.ltkg 包格式：ZIP压缩档
├── manifest.json     # 包清单
├── entries/          # 知识条目JSON
└── files/            # 附件文件

导入策略：
- skip_existing: 跳过已存在的条目
- merge: 合并更新
- replace: 全部覆盖（需确认）

导出格式：
- 全量导出: 所有知识
- 行业导出: 指定行业
- 选择导出: 指定条目ID列表
"""

import json
import zipfile
import io
import hashlib
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable
from datetime import datetime
from enum import Enum


class ImportStrategy(Enum):
    """导入策略"""
    SKIP_EXISTING = "skip_existing"  # 跳过已有
    MERGE = "merge"                  # 合并更新
    REPLACE = "replace"             # 全部覆盖


@dataclass
class LTKGManifest:
    """LTKG包清单"""
    format_version: str = "1.0"
    exported_at: str = ""
    exported_by: str = "Hermes Knowledge Grove"
    description: str = ""
    entry_count: int = 0
    industries: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    checksum: str = ""  # SHA256校验

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'LTKGManifest':
        return cls(**data)


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    merged: int = 0

    def summary(self) -> str:
        parts = []
        if self.imported > 0:
            parts.append(f"导入 {self.imported} 条")
        if self.skipped > 0:
            parts.append(f"跳过 {self.skipped} 条")
        if self.merged > 0:
            parts.append(f"合并 {self.merged} 条")
        if self.failed > 0:
            parts.append(f"失败 {self.failed} 条")
        return ", ".join(parts) if parts else "无变动"


@dataclass
class ExportResult:
    """导出结果"""
    success: bool
    file_path: str = ""
    entry_count: int = 0
    message: str = ""


def asdict(obj):
    """简化版asdict"""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: asdict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [asdict(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: asdict(v) for k, v in obj.items()}
    return obj


class LTKGHandler:
    """
    LTKG包处理器

    负责：
    1. 导出知识包 (.ltkg)
    2. 导入知识包
    3. 包验证
    """

    MANIFEST_NAME = "manifest.json"
    ENTRIES_DIR = "entries"
    FILES_DIR = "files"

    def __init__(self, grove):
        self.grove = grove

    # ==================== 导出 ====================

    def export_package(
        self,
        output_path: str | Path,
        entry_ids: List[str] = None,
        industry: str = None,
        include_attachments: bool = True,
        description: str = ""
    ) -> ExportResult:
        """
        导出知识包

        Args:
            output_path: 输出文件路径
            entry_ids: 要导出的条目ID列表（None表示全部）
            industry: 导出指定行业的知识
            include_attachments: 是否包含附件
            description: 包描述

        Returns:
            ExportResult
        """
        output_path = Path(output_path)

        try:
            # 确定要导出的条目
            if entry_ids:
                entries = [self.grove.get_entry(eid) for eid in entry_ids]
                entries = [e for e in entries if e is not None]
            elif industry:
                entries = self.grove.list_entries(industry=industry)
            else:
                entries = self.grove.list_entries()

            if not entries:
                return ExportResult(False, message="没有可导出的知识条目")

            # 收集行业和标签
            industries = list(set(e.industries[0] for e in entries if e.industries))
            all_tags = set()
            for e in entries:
                all_tags.update(e.tags)
            tags = list(all_tags)[:50]  # 限制数量

            # 创建清单
            manifest = LTKGManifest(
                exported_at=datetime.now().isoformat(),
                description=description or f"导出 {len(entries)} 条知识",
                entry_count=len(entries),
                industries=industries,
                tags=tags
            )

            # 创建ZIP包
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 添加清单
                zf.writestr(
                    self.MANIFEST_NAME,
                    json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
                )

                # 添加条目
                for entry in entries:
                    entry_data = entry.to_dict() if hasattr(entry, 'to_dict') else entry
                    entry_json = json.dumps(entry_data, ensure_ascii=False, indent=2)
                    entry_filename = f"{entry.id}.json"
                    zf.writestr(f"{self.ENTRIES_DIR}/{entry_filename}", entry_json)

                    # 添加附件
                    if include_attachments and hasattr(entry, 'attachments'):
                        for att in entry.attachments:
                            att_path = Path(att)
                            if att_path.exists():
                                zf.write(att_path, f"{self.FILES_DIR}/{att_path.name}")

                # 计算校验和
                manifest.checksum = self._calculate_checksum(output_path)
                zf.writestr(
                    self.MANIFEST_NAME,
                    json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
                )

            return ExportResult(
                success=True,
                file_path=str(output_path),
                entry_count=len(entries),
                message=f"已导出 {len(entries)} 条知识到 {output_path.name}"
            )

        except Exception as e:
            return ExportResult(success=False, message=f"导出失败: {e}")

    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件SHA256校验和"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ==================== 导入 ====================

    def import_package(
        self,
        package_path: str | Path,
        strategy: ImportStrategy = ImportStrategy.SKIP_EXISTING,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> ImportResult:
        """
        导入知识包

        Args:
            package_path: LTKG包路径
            strategy: 导入策略
            progress_callback: 进度回调 (current, total, message)

        Returns:
            ImportResult
        """
        package_path = Path(package_path)

        if not package_path.exists():
            return ImportResult(success=False, errors=["文件不存在"])

        result = ImportResult(success=False)

        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # 验证清单
                if self.MANIFEST_NAME not in zf.namelist():
                    return ImportResult(success=False, errors=["无效的LTKG包：缺少清单文件"])

                manifest_data = json.loads(zf.read(self.MANIFEST_NAME))
                manifest = LTKGManifest.from_dict(manifest_data)

                # 获取条目列表
                entry_files = [n for n in zf.namelist()
                              if n.startswith(f"{self.ENTRIES_DIR}/") and n.endswith('.json')]

                total = len(entry_files)

                for i, entry_file in enumerate(entry_files):
                    try:
                        entry_data = json.loads(zf.read(entry_file))

                        # 检查是否已存在
                        existing = self.grove.get_entry(entry_data.get('id', ''))

                        if existing:
                            if strategy == ImportStrategy.SKIP_EXISTING:
                                result.skipped += 1
                                if progress_callback:
                                    progress_callback(i + 1, total, f"跳过: {entry_data.get('title', '未知')}")
                                continue

                            elif strategy == ImportStrategy.MERGE:
                                # 合并：保留新的内容字段
                                merged_data = self._merge_entries(existing, entry_data)
                                entry_data = merged_data
                                result.merged += 1

                            elif strategy == ImportStrategy.REPLACE:
                                # 删除旧条目
                                self.grove.delete_entry(existing.id)
                                result.skipped += 1  # 计入替换

                        # 提取附件
                        if self.FILES_DIR in zf.namelist():
                            files_in_pkg = [n for n in zf.namelist()
                                          if n.startswith(f"{self.FILES_DIR}/")]
                            for f in files_in_pkg:
                                fname = Path(f).name
                                dest = self.grove.base_path / "attachments" / fname
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                with open(dest, 'wb') as out:
                                    out.write(zf.read(f))
                                # 更新attachment路径
                                if fname in str(entry_data.get('attachments', [])):
                                    entry_data['attachments'] = [
                                        str(dest) if Path(a).name == fname else a
                                        for a in entry_data.get('attachments', [])
                                    ]

                        # 保存条目
                        from .knowledge_grove import GroveKnowledgeEntry
                        entry = GroveKnowledgeEntry.from_dict(entry_data)
                        success, msg = self.grove.save_entry(entry)

                        if success:
                            result.imported += 1
                        else:
                            result.failed += 1
                            result.errors.append(msg)

                        if progress_callback:
                            progress_callback(i + 1, total, msg or f"导入: {entry.title}")

                    except Exception as e:
                        result.failed += 1
                        result.errors.append(f"处理 {entry_file} 时出错: {e}")

            result.success = True
            return result

        except zipfile.BadZipFile:
            return ImportResult(success=False, errors=["无效的ZIP文件"])
        except Exception as e:
            return ImportResult(success=False, errors=[f"导入失败: {e}"])

    def _merge_entries(self, existing, new_data: dict) -> dict:
        """合并两个条目，保留最新内容"""
        # 简单策略：新数据覆盖旧数据，但保留旧条目的usage_count和created_at
        existing_data = existing.to_dict() if hasattr(existing, 'to_dict') else existing

        merged = existing_data.copy()
        for key, value in new_data.items():
            if key in ('content_md', 'summary', 'title'):
                # 核心内容用新的
                merged[key] = value
            elif key in ('updated_at',):
                # 更新时间用新的
                merged[key] = value
            elif key == 'attachments':
                # 附件合并去重
                existing_attachments = set(existing_data.get('attachments', []))
                existing_attachments.update(value)
                merged['attachments'] = list(existing_attachments)
            elif key == 'tags':
                # 标签合并去重
                existing_tags = set(existing_data.get('tags', []))
                existing_tags.update(value)
                merged['tags'] = list(existing_tags)

        return merged

    # ==================== 验证 ====================

    def validate_package(self, package_path: str | Path) -> Tuple[bool, str, Optional[LTKGManifest]]:
        """
        验证LTKG包

        Returns:
            (is_valid, message, manifest)
        """
        package_path = Path(package_path)

        if not package_path.exists():
            return False, "文件不存在", None

        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # 检查清单
                if self.MANIFEST_NAME not in zf.namelist():
                    return False, "缺少清单文件", None

                # 读取清单
                manifest_data = json.loads(zf.read(self.MANIFEST_NAME))
                manifest = LTKGManifest.from_dict(manifest_data)

                # 检查条目
                entry_files = [n for n in zf.namelist()
                              if n.startswith(f"{self.ENTRIES_DIR}/") and n.endswith('.json')]

                if len(entry_files) != manifest.entry_count:
                    return False, f"条目数量不匹配：清单{manifest.entry_count}，实际{len(entry_files)}", None

                return True, f"有效的LTKG包，包含 {manifest.entry_count} 条知识", manifest

        except zipfile.BadZipFile:
            return False, "无效的ZIP文件", None
        except Exception as e:
            return False, f"验证失败: {e}", None

    # ==================== 工具 ====================

    def create_shareable_link(
        self,
        entry_ids: List[str],
        output_dir: str | Path = None
    ) -> str:
        """
        创建可分享的LTKG包

        Returns:
            包文件路径
        """
        if output_dir is None:
            output_dir = self.grove.archives_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"knowledge_share_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ltkg"
        output_path = output_dir / filename

        result = self.export_package(output_path, entry_ids=entry_ids)

        if result.success:
            return str(output_path)
        raise RuntimeError(result.message)


# ==================== 辅助函数 ====================

def get_ltkg_handler(grove=None) -> LTKGHandler:
    """获取LTKG处理器"""
    if grove is None:
        from .knowledge_grove import KnowledgeGrove
        grove = KnowledgeGrove()
    return LTKGHandler(grove)
