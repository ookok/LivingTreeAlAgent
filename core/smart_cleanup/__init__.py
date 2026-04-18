"""
智能临时文件清理系统 - SmartCleanup

核心理念："不是简单的删除，而是智能的资产管理"

三级清理策略:
- Level 1: 即时清理 (内存缓存/临时预览/敏感数据)
- Level 2: 定期清理 (工作文件/下载缓存/日志文件)
- Level 3: 智能归档 (重要结果/中间文件/历史版本)

Author: Hermes Desktop Team
"""

import os
import time
import hashlib
import shutil
import psutil
import json
import gzip
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import logging

# 配置日志
logger = logging.getLogger(__name__)


class CleanupLevel(Enum):
    """清理级别"""
    INSTANT = 1       # 即时清理
    REGULAR = 2       # 定期清理
    ARCHIVE = 3       # 智能归档


class FileCategory(Enum):
    """文件类别"""
    TEMP_CACHE = "temp_cache"           # 临时缓存
    MEMORY_BUFFER = "memory_buffer"       # 内存缓冲
    SENSITIVE_DATA = "sensitive_data"     # 敏感数据
    WORK_FILE = "work_file"              # 工作文件
    DOWNLOAD_CACHE = "download_cache"    # 下载缓存
    LOG_FILE = "log_file"                # 日志文件
    BUILD_ARTIFACT = "build_artifact"    # 构建产物
    ANALYSIS_RESULT = "analysis_result"  # 分析结果
    DRAFT_VERSION = "draft_version"      # 草稿版本
    FINAL_WORK = "final_work"           # 最终作品
    PROJECT_BACKUP = "project_backup"    # 项目备份
    OTHER = "other"                      # 其他


class CleanupDecision(Enum):
    """清理决策"""
    KEEP_FOREVER = "keep_forever"        # 永久保留
    KEEP_LONG = "keep_long"              # 长期保留 (30天)
    KEEP_MEDIUM = "keep_medium"         # 中期保留 (7天)
    KEEP_SHORT = "keep_short"            # 短期保留 (1天)
    CLEAN_NOW = "clean_now"             # 即时清理
    ARCHIVE = "archive"                  # 归档
    UNKNOWN = "unknown"                  # 未知


@dataclass
class FileMetadata:
    """文件元数据"""
    path: str
    name: str
    size: int
    category: FileCategory
    created_time: float
    modified_time: float
    accessed_time: float
    content_hash: str = ""
    ai_context: str = ""           # AI生成上下文
    user_tags: List[str] = field(default_factory=list)
    access_count: int = 0
    last_access_time: float = 0
    value_score: float = 0.0       # 价值评分
    protection_level: int = 0      # 保护级别 0-10
    is_important: bool = False     # 用户标记重要


@dataclass
class CleanupCandidate:
    """待清理文件候选"""
    metadata: FileMetadata
    decision: CleanupDecision
    reason: str
    confidence: float = 0.0          # 决策置信度
    cleanup_level: CleanupLevel = CleanupLevel.REGULAR
    stages_passed: List[str] = field(default_factory=list)  # 已通过的清理阶段


@dataclass
class CleanupResult:
    """清理结果"""
    cleaned_files: List[str]
    archived_files: List[str]
    failed_files: List[Tuple[str, str]]  # (path, reason)
    space_reclaimed: int
    cleanup_time: float
    cleanup_level: CleanupLevel


@dataclass
class CleanupHistory:
    """清理历史记录"""
    timestamp: float
    files: List[str]
    space_reclaimed: int
    reason: str
    categories: List[str]


class CleanupConfig:
    """清理配置"""

    # 磁盘空间阈值
    SPACE_WARNING_THRESHOLD = 0.80      # 80% 警告
    SPACE_CRITICAL_THRESHOLD = 0.90     # 90% 危险

    # 保留时间 (秒)
    INSTANT_CLEANUP_MAX_AGE = 60        # 即时清理: 60秒
    SHORT_KEEP_TIME = 86400             # 短期: 1天
    MEDIUM_KEEP_TIME = 604800           # 中期: 7天
    LONG_KEEP_TIME = 2592000            # 长期: 30天

    # 价值评分权重
    WEIGHT_ACCESS_FREQ = 0.25
    WEIGHT_FRESHNESS = 0.20
    WEIGHT_SIZE = 0.15
    WEIGHT_IMPORTANCE = 0.20
    WEIGHT_PROJECT_RELATED = 0.10
    WEIGHT_AI_VALUE = 0.10

    # 价值评分阈值
    SCORE_KEEP_FOREVER = 0.8
    SCORE_KEEP_LONG = 0.6
    SCORE_KEEP_MEDIUM = 0.4
    SCORE_KEEP_SHORT = 0.2

    # 渐进式清理阶段
    STAGE_MARK = "mark"                # 标记阶段
    STAGE_COMPRESS = "compress"        # 压缩阶段
    STAGE_MOVE = "move"               # 移动阶段
    STAGE_DELETE = "delete"            # 删除阶段

    # 恢复保留时间
    RECYCLE_BIN_RETENTION = 30         # 回收站保留天数
    ARCHIVE_RETENTION = 90            # 归档保留天数

    def __init__(self):
        # 默认临时文件路径
        self.temp_paths = [
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            str(Path.home() / "Downloads"),
            str(Path.home() / "AppData" / "Local" / "Temp"),
        ]

        # 忽略的目录/文件模式
        self.ignore_patterns = [
            "*.system",
            "*.protected",
            ".git",
            ".svn",
            "node_modules",
            "__pycache__",
            ".DS_Store",
            "Thumbs.db",
        ]

        # 保护的文件模式
        self.protected_patterns = [
            "*.important",
            "*.keep",
            "*.protected",
            ".backup",
        ]


class FileValueCalculator:
    """
    文件价值评估器

    文件价值评分算法:
    文件价值 = 访问频率×0.25 + 新鲜度×0.20 + 大小权重×0.15
             + 用户标记重要性×0.20 + 项目关联度×0.10 + AI生成价值分×0.10
    """

    def __init__(self, config: CleanupConfig):
        self.config = config

    def calculate_value_score(self, metadata: FileMetadata) -> float:
        """
        计算文件价值评分

        Returns:
            0.0 - 1.0 的评分
        """
        score = 0.0

        # 1. 访问频率 (0-1)
        access_score = self._calculate_access_score(metadata)

        # 2. 新鲜度 (0-1)
        freshness_score = self._calculate_freshness_score(metadata)

        # 3. 大小权重 (0-1)
        size_score = self._calculate_size_score(metadata)

        # 4. 用户标记重要性 (0或1)
        importance_score = 1.0 if metadata.is_important else 0.0

        # 5. 项目关联度 (0-1) - 简化计算
        project_score = self._calculate_project_score(metadata)

        # 6. AI生成价值分 (0-1)
        ai_score = self._calculate_ai_value_score(metadata)

        # 加权求和
        score = (
            access_score * self.config.WEIGHT_ACCESS_FREQ +
            freshness_score * self.config.WEIGHT_FRESHNESS +
            size_score * self.config.WEIGHT_SIZE +
            importance_score * self.config.WEIGHT_IMPORTANCE +
            project_score * self.config.WEIGHT_PROJECT_RELATED +
            ai_score * self.config.WEIGHT_AI_VALUE
        )

        return min(1.0, max(0.0, score))

    def _calculate_access_score(self, metadata: FileMetadata) -> float:
        """计算访问频率评分"""
        if metadata.access_count == 0:
            return 0.0
        # 使用对数函数，访问次数越多分数越高，但边际效益递减
        import math
        return min(1.0, math.log1p(metadata.access_count) / 10)

    def _calculate_freshness_score(self, metadata: FileMetadata) -> float:
        """计算新鲜度评分"""
        now = time.time()
        age = now - metadata.modified_time

        if age < 3600:  # 1小时内
            return 1.0
        elif age < 86400:  # 1天内
            return 0.8
        elif age < 604800:  # 7天内
            return 0.6
        elif age < 2592000:  # 30天内
            return 0.4
        else:
            return 0.2

    def _calculate_size_score(self, metadata: FileMetadata) -> float:
        """计算大小权重评分"""
        # 越大或越小的文件可能更重要
        # 这里简化为: 极大文件(>100MB)和极小文件(<1KB)分数较低
        size_mb = metadata.size / (1024 * 1024)

        if size_mb > 100:
            return 0.6  # 太大可能不重要
        elif size_mb < 0.001:
            return 0.3  # 太小可能不重要
        else:
            return 0.8

    def _calculate_project_score(self, metadata: FileMetadata) -> float:
        """计算项目关联度"""
        # 检查文件路径是否在项目目录中
        project_indicators = ['project', 'workspace', 'code', 'src', 'work']
        path_lower = metadata.path.lower()

        for indicator in project_indicators:
            if indicator in path_lower:
                return 0.8
        return 0.3

    def _calculate_ai_value_score(self, metadata: FileMetadata) -> float:
        """计算AI生成价值分"""
        if metadata.ai_context:
            return 0.9  # 有AI上下文说明是生成的
        return 0.3


class SmartCleanupEngine:
    """
    智能清理引擎主类

    核心功能:
    - 文件扫描和元数据提取
    - 价值评估和清理决策
    - 多级清理策略执行
    - 渐进式清理机制
    - 清理历史和恢复
    """

    def __init__(self, config: CleanupConfig = None):
        self.config = config or CleanupConfig()
        self.calculator = FileValueCalculator(self.config)
        self.lock = Lock()

        # 内存缓存
        self.file_cache: Dict[str, FileMetadata] = {}
        self.protected_files: set = set()

        # 清理历史
        self.cleanup_history: List[CleanupHistory] = []

        # 统计信息
        self.stats = {
            "total_scanned": 0,
            "total_size": 0,
            "cleaned_count": 0,
            "cleaned_size": 0,
            "archived_count": 0,
            "archived_size": 0,
        }

        # 工作模式
        self.work_mode = "default"  # default/programming/data_analysis/creative/work

    def set_work_mode(self, mode: str):
        """设置工作模式"""
        self.work_mode = mode

    def scan_directory(self, path: str, recursive: bool = True) -> List[FileMetadata]:
        """
        扫描目录并提取文件元数据

        Args:
            path: 扫描路径
            recursive: 是否递归扫描

        Returns:
            文件元数据列表
        """
        results = []

        try:
            scan_path = Path(path)
            if not scan_path.exists():
                return results

            # 选择扫描方式
            if recursive:
                files = scan_path.rglob("*")
            else:
                files = scan_path.glob("*")

            for file_path in files:
                if file_path.is_file():
                    try:
                        metadata = self._extract_metadata(file_path)
                        if metadata:
                            results.append(metadata)
                            self.stats["total_scanned"] += 1
                            self.stats["total_size"] += metadata.size
                    except Exception as e:
                        logger.warning(f"Failed to extract metadata for {file_path}: {e}")

        except Exception as e:
            logger.error(f"Failed to scan directory {path}: {e}")

        return results

    def _extract_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """提取文件元数据"""
        try:
            stat = file_path.stat()

            metadata = FileMetadata(
                path=str(file_path),
                name=file_path.name,
                size=stat.st_size,
                category=self._categorize_file(file_path),
                created_time=stat.st_ctime,
                modified_time=stat.st_mtime,
                accessed_time=stat.st_atime,
                last_access_time=stat.st_atime,
            )

            # 计算内容哈希
            metadata.content_hash = self._calculate_hash(file_path)

            # 计算价值评分
            metadata.value_score = self.calculator.calculate_value_score(metadata)

            return metadata

        except Exception:
            return None

    def _categorize_file(self, file_path: Path) -> FileCategory:
        """根据文件路径和扩展名分类"""
        path_str = str(file_path).lower()
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()

        # 临时缓存
        if any(tmp in path_str for tmp in ['temp', 'tmp', 'cache']):
            return FileCategory.TEMP_CACHE

        # 内存缓冲
        if suffix in ['.tmp', '.bak', '.swp']:
            return FileCategory.MEMORY_BUFFER

        # 敏感数据
        if any(p in name for p in ['password', 'secret', 'key', '.env']):
            return FileCategory.SENSITIVE_DATA

        # 日志文件
        if suffix in ['.log', '.out']:
            return FileCategory.LOG_FILE

        # 构建产物
        if any(p in path_str for p in ['build', 'dist', 'target', '__pycache__']):
            return FileCategory.BUILD_ARTIFACT

        # 下载缓存
        downloads = str(Path.home() / "Downloads")
        if downloads in path_str:
            return FileCategory.DOWNLOAD_CACHE

        # 工作文件
        if any(p in path_str for p in ['workspace', 'project', 'code']):
            return FileCategory.WORK_FILE

        return FileCategory.OTHER

    def _calculate_hash(self, file_path: Path, chunk_size: 8192) -> str:
        """计算文件内容哈希"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def evaluate_cleanup_candidates(
        self,
        files: List[FileMetadata]
    ) -> List[CleanupCandidate]:
        """
        评估文件清理候选

        Args:
            files: 文件元数据列表

        Returns:
            清理候选列表
        """
        candidates = []

        for metadata in files:
            # 检查是否被保护
            if self._is_protected(metadata):
                continue

            # 决策
            decision, reason = self._make_cleanup_decision(metadata)

            candidate = CleanupCandidate(
                metadata=metadata,
                decision=decision,
                reason=reason,
                confidence=self._calculate_confidence(metadata, decision),
                cleanup_level=self._get_cleanup_level(decision),
            )
            candidates.append(candidate)

        # 按价值评分排序
        candidates.sort(key=lambda x: x.metadata.value_score)

        return candidates

    def _is_protected(self, metadata: FileMetadata) -> bool:
        """检查文件是否被保护"""
        # 检查用户标记
        if metadata.is_important or metadata.protection_level >= 5:
            return True

        # 检查保护模式
        for pattern in self.config.protected_patterns:
            if pattern.replace("*", "") in metadata.name:
                return True

        return False

    def _make_cleanup_decision(
        self,
        metadata: FileMetadata
    ) -> Tuple[CleanupDecision, str]:
        """做出清理决策"""
        score = metadata.value_score

        # 根据价值评分决策
        if score >= self.config.SCORE_KEEP_FOREVER:
            return CleanupDecision.KEEP_FOREVER, "价值评分很高，永久保留"

        if score >= self.config.SCORE_KEEP_LONG:
            return CleanupDecision.KEEP_LONG, "价值评分较高，长期保留"

        if score >= self.config.SCORE_KEEP_MEDIUM:
            return CleanupDecision.KEEP_MEDIUM, "价值评分中等，中期保留"

        if score >= self.config.SCORE_KEEP_SHORT:
            return CleanupDecision.KEEP_SHORT, "价值评分较低，短期保留"

        # 根据文件类别决策
        if metadata.category == FileCategory.TEMP_CACHE:
            return CleanupDecision.CLEAN_NOW, "临时缓存文件，即时清理"

        if metadata.category == FileCategory.MEMORY_BUFFER:
            return CleanupDecision.CLEAN_NOW, "内存缓冲文件，即时清理"

        if metadata.category == FileCategory.LOG_FILE:
            # 日志文件根据时间决策
            age = time.time() - metadata.modified_time
            if age > self.config.LONG_KEEP_TIME:
                return CleanupDecision.ARCHIVE, "旧日志文件，归档处理"
            else:
                return CleanupDecision.KEEP_SHORT, "新日志文件，短期保留"

        if metadata.category == FileCategory.BUILD_ARTIFACT:
            return CleanupDecision.CLEAN_NOW, "构建产物，清理"

        return CleanupDecision.ARCHIVE, "低价值文件，归档处理"

    def _calculate_confidence(
        self,
        metadata: FileMetadata,
        decision: CleanupDecision
    ) -> float:
        """计算决策置信度"""
        base_confidence = metadata.value_score

        # 根据文件类别调整置信度
        if metadata.category in [FileCategory.TEMP_CACHE, FileCategory.MEMORY_BUFFER]:
            base_confidence = max(base_confidence, 0.9)

        return min(1.0, base_confidence + 0.1)

    def _get_cleanup_level(self, decision: CleanupDecision) -> CleanupLevel:
        """获取清理级别"""
        if decision == CleanupDecision.CLEAN_NOW:
            return CleanupLevel.INSTANT
        elif decision == CleanupDecision.ARCHIVE:
            return CleanupLevel.ARCHIVE
        else:
            return CleanupLevel.REGULAR

    def execute_cleanup(
        self,
        candidates: List[CleanupCandidate],
        level: CleanupLevel = CleanupLevel.REGULAR,
        dry_run: bool = False
    ) -> CleanupResult:
        """
        执行清理

        Args:
            candidates: 清理候选列表
            level: 清理级别
            dry_run: 是否只预览不执行

        Returns:
            清理结果
        """
        with self.lock:
            start_time = time.time()

            cleaned_files = []
            archived_files = []
            failed_files = []
            space_reclaimed = 0

            # 过滤指定级别的候选
            filtered = [c for c in candidates if c.cleanup_level == level]

            for candidate in filtered:
                try:
                    if dry_run:
                        # 预览模式
                        if candidate.decision == CleanupDecision.CLEAN_NOW:
                            space_reclaimed += candidate.metadata.size
                            cleaned_files.append(candidate.metadata.path)
                        elif candidate.decision == CleanupDecision.ARCHIVE:
                            archived_files.append(candidate.metadata.path)
                    else:
                        # 执行清理
                        success = self._execute_single_cleanup(candidate)
                        if success:
                            space_reclaimed += candidate.metadata.size
                            cleaned_files.append(candidate.metadata.path)
                        else:
                            failed_files.append((
                                candidate.metadata.path,
                                "清理失败"
                            ))

                except Exception as e:
                    failed_files.append((candidate.metadata.path, str(e)))

            cleanup_time = time.time() - start_time

            # 更新统计
            self.stats["cleaned_count"] += len(cleaned_files)
            self.stats["cleaned_size"] += space_reclaimed
            self.stats["archived_count"] += len(archived_files)

            # 记录历史
            history = CleanupHistory(
                timestamp=time.time(),
                files=cleaned_files + archived_files,
                space_reclaimed=space_reclaimed,
                reason=f"{level.name} cleanup",
                categories=[c.metadata.category.value for c in candidates]
            )
            self.cleanup_history.append(history)

            return CleanupResult(
                cleaned_files=cleaned_files,
                archived_files=archived_files,
                failed_files=failed_files,
                space_reclaimed=space_reclaimed,
                cleanup_time=cleanup_time,
                cleanup_level=level
            )

    def _execute_single_cleanup(self, candidate: CleanupCandidate) -> bool:
        """执行单个文件清理"""
        metadata = candidate.metadata
        path = Path(metadata.path)

        if not path.exists():
            return False

        try:
            if candidate.decision == CleanupDecision.CLEAN_NOW:
                # 即时清理 - 移到回收站
                return self._move_to_recycle_bin(path)

            elif candidate.decision == CleanupDecision.ARCHIVE:
                # 归档处理
                return self._archive_file(candidate)

            return False

        except Exception as e:
            logger.error(f"Failed to cleanup {path}: {e}")
            return False

    def _move_to_recycle_bin(self, path: Path) -> bool:
        """移动文件到回收站"""
        try:
            # 使用 shutil.move 移到回收站
            # 在 Windows 上可以使用 send2trash 库
            recycle_path = Path.home() / ".smart_cleanup" / "recycle_bin"
            recycle_path.mkdir(parents=True, exist_ok=True)

            # 以时间戳命名避免冲突
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{timestamp}_{path.name}"
            target = recycle_path / new_name

            shutil.copy2(path, target)

            # 保存元数据
            self._save_metadata_for_recovery(target, path)

            # 删除原文件
            path.unlink()

            return True

        except Exception as e:
            logger.error(f"Failed to move {path} to recycle bin: {e}")
            return False

    def _archive_file(self, candidate: CleanupCandidate) -> bool:
        """归档文件"""
        try:
            archive_path = Path.home() / ".smart_cleanup" / "archives"
            archive_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{timestamp}_{candidate.metadata.name}.gz"
            archive_file = archive_path / archive_name

            # 压缩文件
            with open(candidate.metadata.path, 'rb') as f_in:
                with gzip.open(archive_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # 保存元数据
            self._save_metadata_for_recovery(archive_file, Path(candidate.metadata.path))

            # 删除原文件
            Path(candidate.metadata.path).unlink()

            return True

        except Exception as e:
            logger.error(f"Failed to archive {candidate.metadata.path}: {e}")
            return False

    def _save_metadata_for_recovery(self, archived_path: Path, original_path: Path):
        """保存元数据用于恢复"""
        metadata_path = archived_path.with_suffix(archived_path.suffix + ".meta")

        metadata = {
            "original_path": str(original_path),
            "archived_time": time.time(),
            "original_size": original_path.stat().st_size if original_path.exists() else 0,
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

    def progressive_cleanup(
        self,
        candidates: List[CleanupCandidate],
        target_stage: str = CleanupConfig.STAGE_DELETE,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        渐进式清理

        阶段: mark -> compress -> move -> delete

        Args:
            candidates: 清理候选列表
            target_stage: 目标阶段
            dry_run: 是否只预览

        Returns:
            各阶段的文件统计
        """
        stages = [
            CleanupConfig.STAGE_MARK,
            CleanupConfig.STAGE_COMPRESS,
            CleanupConfig.STAGE_MOVE,
            CleanupConfig.STAGE_DELETE
        ]

        target_index = stages.index(target_stage) if target_stage in stages else 3

        results = {
            "marked": [],
            "compressed": [],
            "moved": [],
            "deleted": []
        }

        for candidate in candidates:
            for i, stage in enumerate(stages):
                if i > target_index:
                    break

                if stage == CleanupConfig.STAGE_MARK:
                    candidate.stages_passed.append(CleanupConfig.STAGE_MARK)
                    results["marked"].append(candidate.metadata.path)

                    if not dry_run:
                        self._mark_file(candidate.metadata.path)

                elif stage == CleanupConfig.STAGE_COMPRESS:
                    candidate.stages_passed.append(CleanupConfig.STAGE_COMPRESS)
                    results["compressed"].append(candidate.metadata.path)

                    if not dry_run:
                        self._compress_file(candidate.metadata.path)

                elif stage == CleanupConfig.STAGE_MOVE:
                    candidate.stages_passed.append(CleanupConfig.STAGE_MOVE)
                    results["moved"].append(candidate.metadata.path)

                    if not dry_run:
                        self._move_to_recycle_bin(Path(candidate.metadata.path))

                elif stage == CleanupConfig.STAGE_DELETE:
                    candidate.stages_passed.append(CleanupConfig.STAGE_DELETE)
                    results["deleted"].append(candidate.metadata.path)

                    if not dry_run:
                        Path(candidate.metadata.path).unlink()

        return results

    def _mark_file(self, path: str):
        """标记文件 (添加标记或变灰)"""
        # 在文件名添加标记前缀
        marked_path = str(Path(path).parent / f"_marked_{Path(path).name}")
        Path(path).rename(marked_path)

    def _compress_file(self, path: str):
        """压缩文件"""
        path = Path(path)
        compressed_path = path.with_suffix(path.suffix + ".gz")

        with open(path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        path.unlink()

    def get_cleanup_suggestions(self) -> Dict[str, Any]:
        """
        获取清理建议

        Returns:
            清理建议字典
        """
        # 获取磁盘使用情况
        disk_usage = psutil.disk_usage('/')

        # 估算可清理空间
        temp_files = self.scan_directory(self.config.temp_paths[0])
        candidates = self.evaluate_cleanup_candidates(temp_files)

        cleanable_size = sum(
            c.metadata.size for c in candidates
            if c.decision == CleanupDecision.CLEAN_NOW
        )

        # 分类统计
        category_stats = {}
        for candidate in candidates:
            cat = candidate.metadata.category.value
            if cat not in category_stats:
                category_stats[cat] = {"count": 0, "size": 0}
            category_stats[cat]["count"] += 1
            category_stats[cat]["size"] += candidate.metadata.size

        # 生成建议
        suggestions = {
            "disk_usage": {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": disk_usage.percent,
            },
            "cleanable": {
                "count": len(candidates),
                "size": cleanable_size,
            },
            "category_stats": category_stats,
            "actions": []
        }

        # 根据磁盘空间添加建议
        if disk_usage.percent >= self.config.SPACE_CRITICAL_THRESHOLD:
            suggestions["actions"].append({
                "type": "critical",
                "message": "磁盘空间已临界，建议立即清理",
                "priority": "high"
            })
        elif disk_usage.percent >= self.config.SPACE_WARNING_THRESHOLD:
            suggestions["actions"].append({
                "type": "warning",
                "message": "磁盘空间使用率较高，建议清理",
                "priority": "medium"
            })

        return suggestions

    def generate_cleanup_report(self) -> str:
        """生成清理报告"""
        suggestions = self.get_cleanup_suggestions()

        report = ["🧹 智能清理报告", "=" * 40]
        report.append(f"\n💾 磁盘空间: {suggestions['disk_usage']['percent']:.1f}% 已使用")
        report.append(f"   总空间: {suggestions['disk_usage']['total'] / (1024**3):.2f} GB")
        report.append(f"   已用空间: {suggestions['disk_usage']['used'] / (1024**3):.2f} GB")
        report.append(f"   空闲空间: {suggestions['disk_usage']['free'] / (1024**3):.2f} GB")

        report.append(f"\n📁 可清理文件: {suggestions['cleanable']['count']} 个")
        report.append(f"   可释放空间: {suggestions['cleanable']['size'] / (1024**2):.2f} MB")

        report.append(f"\n📊 分类统计:")
        for cat, stats in suggestions['category_stats'].items():
            report.append(f"   {cat}: {stats['count']} 个 ({stats['size'] / (1024**2):.2f} MB)")

        if suggestions['actions']:
            report.append(f"\n⚡ 建议:")
            for action in suggestions['actions']:
                report.append(f"   [{action['priority'].upper()}] {action['message']}")

        return "\n".join(report)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

    def cleanup_expired_from_recycle_bin(self) -> int:
        """
        清理回收站中过期的文件

        Returns:
            清理的文件数量
        """
        recycle_path = Path.home() / ".smart_cleanup" / "recycle_bin"
        if not recycle_path.exists():
            return 0

        expired_time = time.time() - (self.config.RECYCLE_BIN_RETENTION * 86400)
        cleaned_count = 0

        for file_path in recycle_path.iterdir():
            if file_path.is_file():
                if file_path.stat().st_mtime < expired_time:
                    # 删除文件和元数据
                    file_path.unlink()
                    meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                    if meta_path.exists():
                        meta_path.unlink()
                    cleaned_count += 1

        return cleaned_count


# ============ 便捷函数 ============

def quick_cleanup(path: str = None, dry_run: bool = True) -> Dict[str, Any]:
    """
    快速清理函数

    Args:
        path: 要清理的路径，默认系统临时目录
        dry_run: 是否只预览

    Returns:
        清理结果摘要
    """
    engine = SmartCleanupEngine()

    if path is None:
        path = os.environ.get('TEMP', '')

    files = engine.scan_directory(path)
    candidates = engine.evaluate_cleanup_candidates(files)
    result = engine.execute_cleanup(candidates, level=CleanupLevel.INSTANT, dry_run=dry_run)

    return {
        "scanned": len(files),
        "cleaned": len(result.cleaned_files),
        "archived": len(result.archived_files),
        "space_reclaimed": result.space_reclaimed,
        "dry_run": dry_run
    }


def get_temp_directory_size() -> int:
    """
    获取临时目录大小

    Returns:
        临时目录总大小 (字节)
    """
    temp_path = os.environ.get('TEMP', '')
    total_size = 0

    try:
        for dirpath, dirnames, filenames in os.walk(temp_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except Exception:
                    pass
    except Exception:
        pass

    return total_size