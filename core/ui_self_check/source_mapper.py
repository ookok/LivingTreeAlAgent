"""
源码映射器 - SourceMapper
核心理念：利用Source Map将运行时组件映射回源码文件

功能：
1. 组件到源码文件的映射
2. 构建时Source Map解析
3. 轻量级源码加载（只加载当前活跃组件）
"""

import os
import json
import logging
import threading
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class SourceLocation:
    """源码位置"""
    file_path: str
    line_number: int
    column_number: int = 0
    component_name: str = ""
    method_name: str = ""


@dataclass
class SourceMapEntry:
    """Source Map条目"""
    generated_line: int
    generated_column: int
    original_line: int
    original_column: int
    source_file: str
    name: str = ""


class SourceMapper:
    """
    源码映射器

    设计原则：
    1. 懒加载：只在需要时才加载源码
    2. 缓存：已加载的源码缓存在内存中
    3. 限制：限制单次加载的源码大小
    """

    def __init__(self, project_root: str):
        self._project_root = project_root
        self._source_cache: Dict[str, str] = {}
        self._source_map_cache: Dict[str, List[SourceMapEntry]] = {}
        self._component_to_file: Dict[str, str] = {}
        self._max_cache_size = 50
        self._max_file_size = 100 * 1024  # 100KB

        self._lock = threading.RLock()

    def register_component(self, component_name: str, file_path: str):
        """注册组件到文件的映射"""
        with self._lock:
            self._component_to_file[component_name] = file_path

    def register_components_bulk(self, mappings: Dict[str, str]):
        """批量注册组件映射"""
        with self._lock:
            self._component_to_file.update(mappings)

    def get_source_location(self, component_name: str) -> Optional[SourceLocation]:
        """获取组件源码位置"""
        file_path = self._resolve_file_path(component_name)
        if not file_path:
            return None

        return SourceLocation(
            file_path=file_path,
            line_number=1,
            component_name=component_name
        )

    def load_source(self, file_path: str) -> Optional[str]:
        """
        加载源码（带缓存和大小限制）

        Returns:
            源码内容或None（如果文件过大或不存在）
        """
        with self._lock:
            # 检查缓存
            if file_path in self._source_cache:
                return self._source_cache[file_path]

            # 检查文件大小
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > self._max_file_size:
                    logger.warning(f"File too large to load: {file_path}")
                    return None

            # 加载文件
            try:
                full_path = file_path if os.path.isabs(file_path) else os.path.join(self._project_root, file_path)
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 缓存管理
                self._maybe_evict_cache()
                self._source_cache[file_path] = content

                return content
            except Exception as e:
                logger.error(f"Failed to load source {file_path}: {e}")
                return None

    def get_source_snippet(
        self,
        file_path: str,
        line_number: int,
        context_lines: int = 5
    ) -> Optional[str]:
        """
        获取源码片段

        Args:
            file_path: 文件路径
            line_number: 行号
            context_lines: 上下文行数

        Returns:
            源码片段
        """
        content = self.load_source(file_path)
        if not content:
            return None

        lines = content.split('\n')
        total_lines = len(lines)

        start_line = max(0, line_number - context_lines - 1)
        end_line = min(total_lines, line_number + context_lines)

        snippet_lines = []
        for i in range(start_line, end_line):
            prefix = ">>> " if i == line_number - 1 else "    "
            snippet_lines.append(f"{prefix}{i+1}: {lines[i]}")

        return '\n'.join(snippet_lines)

    def _resolve_file_path(self, component_name: str) -> Optional[str]:
        """解析组件对应的文件路径"""
        # 1. 查找注册的映射
        if component_name in self._component_to_file:
            return self._component_to_file[component_name]

        # 2. 尝试推断路径
        inferred = self._infer_file_path(component_name)
        if inferred and os.path.exists(inferred):
            return inferred

        return None

    def _infer_file_path(self, component_name: str) -> Optional[str]:
        """推断文件路径"""
        # 常见命名模式
        patterns = [
            f"{component_name}.py",
            f"{component_name.lower()}.py",
            f"{component_name}_panel.py",
            f"panel_{component_name.lower()}.py",
            f"{component_name}/__init__.py",
        ]

        for pattern in patterns:
            full_path = os.path.join(self._project_root, pattern)
            if os.path.exists(full_path):
                return full_path

        return None

    def _maybe_evict_cache(self):
        """缓存淘汰"""
        if len(self._source_cache) >= self._max_cache_size:
            # 淘汰最早的
            oldest_key = next(iter(self._source_cache))
            del self._source_cache[oldest_key]

    def load_source_map(self, source_map_path: str) -> bool:
        """
        加载Source Map文件

        Args:
            source_map_path: source map 文件路径

        Returns:
            是否加载成功
        """
        try:
            with open(source_map_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entries: List[SourceMapEntry] = []
            sources = data.get('sources', [])
            mappings = data.get('mappings', '')
            sources_content = data.get('sourcesContent', [])

            # 解析mappings（完整VLQ解码实现）
            generated_line = 0
            line_entries: List[SourceMapEntry] = []

            for line_idx, line_mappings in enumerate(mappings.split(';')):
                if not line_mappings:
                    continue

                generated_column = 0
                source_index = 0
                original_line = 0
                original_column = 0
                name_index = 0

                segments = line_mappings.split(',')
                for segment in segments:
                    if not segment:
                        continue

                    # VLQ 解码
                    vlq_values = self._decode_vlq(segment)

                    # 解析每个 segment
                    idx = 0

                    # generated_column（必填）
                    if idx < len(vlq_values):
                        generated_column += vlq_values[idx]
                        idx += 1

                    # source_index（可选）
                    if idx < len(vlq_values):
                        source_index += vlq_values[idx]
                        idx += 1
                    else:
                        source_index = -1  # 无源码映射

                    # original_line（可选）
                    if idx < len(vlq_values) and source_index >= 0:
                        original_line += vlq_values[idx]
                        idx += 1

                    # original_column（可选）
                    if idx < len(vlq_values) and source_index >= 0:
                        original_column += vlq_values[idx]
                        idx += 1

                    # name_index（可选）
                    if idx < len(vlq_values) and source_index >= 0:
                        name_index += vlq_values[idx]

                    # 创建 entry
                    source_file = sources[source_index] if 0 <= source_index < len(sources) else ''
                    entry = SourceMapEntry(
                        generated_line=line_idx,
                        generated_column=generated_column,
                        original_line=original_line + 1,  # 转为1-based
                        original_column=original_column,
                        source_file=source_file,
                        name=sources_content[name_index] if 0 <= name_index < len(sources_content) else ''
                    )
                    line_entries.append(entry)

                entries.extend(line_entries)
                line_entries.clear()

            self._source_map_cache[source_map_path] = entries
            return True

        except Exception as e:
            logger.error(f"Failed to load source map {source_map_path}: {e}")
            return False

    def _decode_vlq(self, segment: str) -> List[int]:
        """
        解码单个 VLQ segment

        Source Map 使用 VLQ (Variable Length Quantity) 编码：
        - 每个值用多个字节表示
        - 最高位是延续位（1=还有字节，0=最后字节）
        - 剩下7位是实际数据
        - 使用补码表示负数

        Args:
            segment: 如 "AAAA,BBBB" 这样的字符串

        Returns:
            解码后的整数列表
        """
        values = []
        current = 0
        shift = 0

        for char in segment:
            char_code = ord(char)

            # 判断是哪个VLQ字符集
            if 'A' <= char <= 'Z':
                vlq_value = char_code - ord('A')
            elif 'a' <= char <= 'z':
                vlq_value = char_code - ord('a') + 26
            elif '0' <= char <= '9':
                vlq_value = char_code - ord('0') + 52
            elif char == '+':
                vlq_value = 62
            elif char == '/':
                vlq_value = 63
            else:
                continue

            # 提取延续位和数据
            continuation = (vlq_value >> 5) & 1
            data = vlq_value & 0x1f

            # 累加数据
            current += data << shift

            if continuation:
                shift += 5
            else:
                # 判断正负（最后一位是符号位）
                if current & 1:
                    current = -(current >> 1)
                else:
                    current = current >> 1
                values.append(current)
                current = 0
                shift = 0

        return values

    def resolve_source_location(
        self,
        generated_file: str,
        line: int,
        column: int = 0
    ) -> Optional[SourceLocation]:
        """解析源码位置（通过Source Map）"""
        if generated_file not in self._source_map_cache:
            return None

        entries = self._source_map_cache[generated_file]

        for entry in entries:
            if entry.generated_line == line:
                return SourceLocation(
                    file_path=entry.source_file,
                    line_number=entry.original_line,
                    column_number=entry.original_column,
                    name=entry.name
                )

        return None

    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._source_cache.clear()
            self._source_map_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        with self._lock:
            return {
                "cached_files": len(self._source_cache),
                "source_maps": len(self._source_map_cache),
                "component_mappings": len(self._component_to_file),
                "cache_limit": self._max_cache_size
            }


class SourceMapBuilder:
    """
    Source Map 构建器

    用于构建时生成 source map，便于运行时定位
    """

    @staticmethod
    def build_source_map(
        source_files: List[str],
        output_path: str
    ) -> bool:
        """
        构建Source Map

        Args:
            source_files: 源文件列表
            output_path: 输出路径

        Returns:
            是否成功
        """
        try:
            mappings = []
            sources = []

            for i, file_path in enumerate(source_files):
                if not os.path.exists(file_path):
                    continue

                sources.append(file_path)

                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 每行一个空mapping（简化）
                line_mappings = ['' for _ in lines]
                mappings.append(';'.join(line_mappings))

            source_map = {
                "version": 3,
                "sources": sources,
                "mappings": ';'.join(mappings),
                "file": "bundle.js"
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(source_map, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to build source map: {e}")
            return False
