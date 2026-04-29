# delta_update.py — 基因式增量更新

"""
基因式增量更新
==============

核心理念：版本之间不是独立补丁，而是构建"基因图谱"，
自动计算最小差异集，支持跨版本直接升级和回滚。

创新点：
1. 版本基因图谱 - 构建版本之间的关系图
2. 最小差异集计算 - 自动计算最优升级路径
3. 跨版本直接升级 - 支持跳过中间版本
4. 任意历史回滚 - 可回滚到任意历史版本
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict

from .models import (
    VersionInfo, UpdateManifest, calculate_version_code, format_size
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DeltaConfig:
    """增量更新配置"""
    chunk_size: int = 1024 * 1024      # 分块大小 (1MB)
    max_delta_size: int = 50 * 1024 * 1024  # 最大增量包大小 (50MB)
    compression_level: int = 6         # 压缩级别 (0-9)
    verify_integrity: bool = True       # 验证完整性
    keep_history: int = 5              # 保留历史版本数


# ═══════════════════════════════════════════════════════════════════════════════
# 版本基因图谱
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class VersionGene:
    """版本基因"""
    version: str                              # 版本号
    version_code: int                         # 版本数值
    parent: Optional[str] = None              # 父版本
    children: List[str] = field(default_factory=list)  # 子版本列表
    delta_from: Optional[str] = None         # 增量基础版本
    delta_to: Optional[str] = None           # 增量目标版本
    delta_size: int = 0                       # 增量大小
    full_size: int = 0                       # 完整包大小
    delta_checksum: str = ""                  # 增量包校验和
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def compression_ratio(self) -> float:
        """压缩率"""
        if self.full_size == 0:
            return 0
        return self.delta_size / self.full_size


class VersionGeneGraph:
    """
    版本基因图谱

    构建和管理版本之间的关系网络
    """

    def __init__(self):
        self.genes: Dict[str, VersionGene] = {}  # version -> VersionGene
        self.latest_version: Optional[str] = None
        self._adjacency: Dict[str, List[str]] = defaultdict(list)  # 版本 -> 相邻版本

    def add_version(self, gene: VersionGene):
        """添加版本基因"""
        self.genes[gene.version] = gene

        # 更新父子公司关系
        if gene.parent:
            parent_gene = self.genes.get(gene.parent)
            if parent_gene and gene.version not in parent_gene.children:
                parent_gene.children.append(gene.version)

        # 更新图结构
        if gene.delta_from:
            self._adjacency[gene.delta_from].append(gene.version)

        # 更新最新版本
        if self.latest_version is None or gene.version_code > self.genes[self.latest_version].version_code:
            self.latest_version = gene.version

    def get_gene(self, version: str) -> Optional[VersionGene]:
        """获取版本基因"""
        return self.genes.get(version)

    def get_path(self, from_version: str, to_version: str) -> List[str]:
        """
        获取从 from_version 到 to_version 的升级路径

        使用 BFS 查找最短路径
        """
        if from_version == to_version:
            return [from_version]

        if from_version not in self.genes or to_version not in self.genes:
            return []

        visited = {from_version}
        queue = [(from_version, [from_version])]

        while queue:
            current, path = queue.pop(0)

            # 检查是否是目标版本
            if current == to_version:
                return path

            # 探索相邻版本
            gene = self.genes.get(current)
            if not gene:
                continue

            # 添加子版本
            for child in gene.children:
                if child not in visited:
                    visited.add(child)
                    queue.append((child, path + [child]))

            # 添加增量相邻版本
            for adjacent in self._adjacency.get(current, []):
                if adjacent not in visited:
                    visited.add(adjacent)
                    queue.append((adjacent, path + [adjacent]))

        return []

    def get_delta_chain(self, from_version: str, to_version: str) -> List[Tuple[str, str]]:
        """
        获取增量链

        Returns:
            [(version1, version2), ...] 表示从 version1 -> version2 的增量
        """
        path = self.get_path(from_version, to_version)
        if not path or len(path) < 2:
            return []

        chain = []
        for i in range(len(path) - 1):
            chain.append((path[i], path[i + 1]))

        return chain

    def calculate_total_delta_size(self, from_version: str, to_version: str) -> int:
        """计算从 from_version 到 to_version 的总增量大小"""
        chain = self.get_delta_chain(from_version, to_version)
        total = 0

        for src, dst in chain:
            gene = self.genes.get(dst)
            if gene:
                total += gene.delta_size

        return total


# ═══════════════════════════════════════════════════════════════════════════════
# 增量计算器
# ═══════════════════════════════════════════════════════════════════════════════


class DeltaCalculator:
    """
    增量计算器

    计算两个版本之间的差异
    """

    def __init__(self, config: DeltaConfig = None):
        self.config = config or DeltaConfig()

    def calculate_delta(
        self,
        old_path: Path,
        new_path: Path,
        old_version: str,
        new_version: str
    ) -> Tuple[Path, str, int]:
        """
        计算增量包

        Args:
            old_path: 旧版本文件/目录路径
            new_path: 新版本文件/目录路径
            old_version: 旧版本号
            new_version: 新版本号

        Returns:
            (delta_path, checksum, delta_size)
        """
        logger.info(f"Calculating delta: {old_version} -> {new_version}")

        # 创建临时文件存储增量
        delta_file = tempfile.NamedTemporaryFile(delete=False, suffix='.delta')
        delta_path = Path(delta_file.name)
        delta_file.close()

        try:
            # 使用 bsdiff 算法计算差异（简化实现：使用二进制 diff）
            delta_size = self._binary_diff(old_path, new_path, delta_path)

            # 计算校验和
            checksum = self._calculate_checksum(delta_path)

            logger.info(f"Delta created: {format_size(delta_size)}, checksum={checksum[:16]}")

            return delta_path, checksum, delta_size

        except Exception as e:
            # 清理临时文件
            if delta_path.exists():
                delta_path.unlink()
            raise e

    def _binary_diff(self, old_path: Path, new_path: Path, delta_path: Path) -> int:
        """
        二进制差异计算（简化实现）

        实际生产环境应使用 bsdiff 或 Courgette 等专业增量算法
        """
        # 读取文件内容
        if old_path.is_file():
            with open(old_path, 'rb') as f:
                old_data = f.read()
        else:
            old_data = self._directory_to_bytes(old_path)

        if new_path.is_file():
            with open(new_path, 'rb') as f:
                new_data = f.read()
        else:
            new_data = self._directory_to_bytes(new_path)

        # 使用 zlib 压缩差异
        compressed = zlib.compress(new_data, level=self.config.compression_level)

        # 写入增量文件
        with open(delta_path, 'wb') as f:
            # 写入元数据
            metadata = {
                'old_size': len(old_data),
                'new_size': len(new_data),
            }
            f.write(json.dumps(metadata).encode())
            f.write(b'\n---DELTA---\n')
            # 写入增量数据
            f.write(compressed)

        return os.path.getsize(delta_path)

    def _directory_to_bytes(self, dir_path: Path) -> bytes:
        """将目录转换为字节（简化实现）"""
        data = {}
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(dir_path)
                with open(file_path, 'rb') as f:
                    data[str(rel_path)] = f.read()

        return json.dumps(data).encode()

    def _calculate_checksum(self, delta_path: Path) -> str:
        """计算文件的 SHA256 校验和"""
        sha256 = hashlib.sha256()
        with open(delta_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def apply_delta(
        self,
        old_path: Path,
        delta_path: Path,
        output_path: Path
    ) -> bool:
        """
        应用增量包

        Args:
            old_path: 旧版本路径
            delta_path: 增量包路径
            output_path: 输出路径

        Returns:
            True 如果成功
        """
        logger.info(f"Applying delta to {output_path}")

        try:
            # 读取增量文件
            with open(delta_path, 'rb') as f:
                content = f.read()

            # 分离元数据和增量数据
            parts = content.split(b'\n---DELTA---\n')
            metadata = json.loads(parts[0].decode())
            compressed_delta = parts[1]

            # 解压缩
            new_data = zlib.decompress(compressed_delta)

            # 写入输出文件
            if output_path.is_dir():
                # 如果是目录，写入到单个文件（简化处理）
                output_file = output_path / 'restored.bin'
                with open(output_file, 'wb') as f:
                    f.write(new_data)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(new_data)

            logger.info(f"Delta applied successfully, output size: {len(new_data)}")

            return True

        except Exception as e:
            logger.error(f"Failed to apply delta: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# 版本路径规划器
# ═══════════════════════════════════════════════════════════════════════════════


class VersionPathPlanner:
    """
    版本路径规划器

    为用户提供最优的升级/降级路径规划
    """

    def __init__(self, gene_graph: VersionGeneGraph):
        self.gene_graph = gene_graph

    def plan_upgrade(
        self,
        from_version: str,
        to_version: str = None
    ) -> Dict[str, Any]:
        """
        规划升级路径

        Args:
            from_version: 当前版本
            to_version: 目标版本（None 表示最新版本）

        Returns:
            升级规划信息
        """
        if to_version is None:
            to_version = self.gene_graph.latest_version

        if not to_version:
            return {'error': 'No latest version available'}

        # 获取增量链
        delta_chain = self.gene_graph.get_delta_chain(from_version, to_version)
        total_size = self.gene_graph.calculate_total_delta_size(from_version, to_version)

        # 获取完整包大小
        to_gene = self.gene_graph.get_gene(to_version)
        full_size = to_gene.full_size if to_gene else 0

        # 计算节省比例
        savings = (1 - total_size / full_size) * 100 if full_size > 0 else 0

        return {
            'from_version': from_version,
            'to_version': to_version,
            'delta_chain': delta_chain,
            'total_delta_size': total_size,
            'full_size': full_size,
            'savings_percent': round(savings, 2),
            'steps': len(delta_chain),
            'path': self.gene_graph.get_path(from_version, to_version)
        }

    def plan_downgrade(
        self,
        from_version: str,
        to_version: str
    ) -> Dict[str, Any]:
        """
        规划降级路径

        降级通常需要完整包，因为增量通常是单向的
        """
        from_gene = self.gene_graph.get_gene(from_version)
        to_gene = self.gene_graph.get_gene(to_version)

        if not from_gene or not to_gene:
            return {'error': 'Version not found'}

        # 降级需要完整包
        return {
            'from_version': from_version,
            'to_version': to_version,
            'requires_full_package': True,
            'download_size': to_gene.full_size,
            'method': 'Download full package for target version'
        }

    def find_optimal_path(
        self,
        from_version: str,
        to_version: str
    ) -> List[Tuple[str, str]]:
        """
        找到最优升级路径（最小下载量）

        可能存在多条路径：直接增量 vs 多步增量
        """
        # 获取所有可能的路径
        direct_chain = self.gene_graph.get_delta_chain(from_version, to_version)

        # 如果直接路径存在且增量较小，使用直接路径
        if direct_chain:
            direct_size = sum(
                self.gene_graph.get_gene(dst).delta_size
                for dst, _ in direct_chain
                if self.gene_graph.get_gene(dst)
            )

            # 获取完整包大小
            to_gene = self.gene_graph.get_gene(to_version)
            full_size = to_gene.full_size if to_gene else float('inf')

            # 如果直接增量小于完整包，使用直接路径
            if direct_size < full_size * 0.8:
                return direct_chain

        # 否则返回空列表（需要下载完整包）
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# 增量管理器
# ═══════════════════════════════════════════════════════════════════════════════


class DeltaManager:
    """
    增量管理器

    整合基因图谱、增量计算和路径规划
    """

    def __init__(self, config: DeltaConfig = None):
        self.config = config or DeltaConfig()
        self.gene_graph = VersionGeneGraph()
        self.calculator = DeltaCalculator(config)
        self.planner = VersionPathPlanner(self.gene_graph)
        self._local_versions: Dict[str, Path] = {}  # version -> local path
        self._delta_cache: Dict[Tuple[str, str], Path] = {}  # (from, to) -> delta path

    def register_version(self, version_info: VersionInfo, local_path: Path):
        """注册本地版本"""
        gene = VersionGene(
            version=version_info.version,
            version_code=version_info.version_code,
            delta_from=version_info.delta_from,
            delta_size=version_info.delta_size,
            full_size=version_info.full_size,
            delta_checksum=version_info.delta_checksum or ""
        )
        self.gene_graph.add_version(gene)
        self._local_versions[version_info.version] = local_path

        logger.info(f"Registered version {version_info.version}")

    def calculate_delta_for_new_version(
        self,
        new_version: str,
        new_path: Path
    ) -> Optional[Tuple[Path, str, int]]:
        """
        为新版本计算增量

        自动查找最近的父版本进行增量计算
        """
        if new_version not in self._local_versions:
            logger.error(f"New version {new_version} not registered")
            return None

        old_path = None
        best_parent = None
        best_size = float('inf')

        # 查找可用的父版本
        new_gene = self.gene_graph.get_gene(new_version)
        if not new_gene:
            return None

        # 尝试所有可能的父版本
        for version, path in self._local_versions.items():
            if version == new_version:
                continue

            gene = self.gene_graph.get_gene(version)
            if not gene:
                continue

            # 跳过更新的版本
            if gene.version_code >= new_gene.version_code:
                continue

            # 计算增量
            try:
                delta_path, checksum, delta_size = self.calculator.calculate_delta(
                    path, new_path, version, new_version
                )

                # 选择最小的增量
                if delta_size < best_size:
                    best_size = delta_size
                    best_parent = version
                    best_result = (delta_path, checksum, delta_size)

            except Exception as e:
                logger.warning(f"Failed to calculate delta {version} -> {new_version}: {e}")
                continue

        if best_parent:
            logger.info(f"Best delta: {best_parent} -> {new_version}, size={format_size(best_size)}")
            return best_result

        return None

    def get_upgrade_plan(
        self,
        from_version: str,
        to_version: str = None
    ) -> Dict[str, Any]:
        """获取升级规划"""
        return self.planner.plan_upgrade(from_version, to_version)

    def get_downgrade_plan(
        self,
        from_version: str,
        to_version: str
    ) -> Dict[str, Any]:
        """获取降级规划"""
        return self.planner.plan_downgrade(from_version, to_version)

    def apply_upgrade(
        self,
        from_version: str,
        to_version: str,
        delta_path: Path,
        output_dir: Path
    ) -> bool:
        """
        应用升级

        Args:
            from_version: 起始版本
            to_version: 目标版本
            delta_path: 增量包路径
            output_dir: 输出目录

        Returns:
            True 如果成功
        """
        old_path = self._local_versions.get(from_version)
        if not old_path:
            logger.error(f"Source version {from_version} not available locally")
            return False

        output_path = output_dir / f"hermes-desktop-{to_version}"

        # 应用增量
        success = self.calculator.apply_delta(old_path, delta_path, output_path)

        if success:
            # 注册新版本
            self._local_versions[to_version] = output_path

        return success

    def prune_old_versions(self, keep_count: int = None):
        """
        清理旧版本

        保留最近 N 个版本，删除其他版本的本地文件
        """
        keep_count = keep_count or self.config.keep_history

        # 按版本号排序
        sorted_versions = sorted(
            self._local_versions.items(),
            key=lambda x: x[0]  # version_code would be better
        )

        # 删除旧版本
        for version, path in sorted_versions[:-keep_count]:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.is_file():
                    path.unlink()
                del self._local_versions[version]
                logger.info(f"Pruned version {version}")
            except Exception as e:
                logger.error(f"Failed to prune {version}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_delta_manager: Optional[DeltaManager] = None


def get_delta_manager() -> DeltaManager:
    """获取全局增量管理器"""
    global _delta_manager
    if _delta_manager is None:
        _delta_manager = DeltaManager()
    return _delta_manager
