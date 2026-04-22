"""
上下文预处理器 (Context Preprocessor)
=====================================

参考 RTK (Rust Token Killer) 项目理念：
在内容到达 LLM 之前进行过滤、压缩和优化，节省 60-90% 的 token。

核心功能：
1. 智能上下文压缩（基于重要度评分）
2. 冗余内容检测和去重
3. 关键信息提取（代码、错误、关键数据）
4. 上下文窗口优化
5. 内容摘要生成

Author: Hermes Desktop Team
Date: 2026-04-22
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """内容类型"""
    CODE = "code"
    ERROR = "error"
    WARNING = "warning"
    OUTPUT = "output"
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ContextSegment:
    """上下文片段"""
    content: str
    content_type: ContentType
    importance_score: float = 0.0  # 0-10 的重要度评分
    source: str = ""  # 来源标识
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_compressed: bool = False  # 是否已压缩


@dataclass
class ProcessingStats:
    """处理统计"""
    original_tokens: int = 0
    compressed_tokens: int = 0
    segments_removed: int = 0
    segments_compressed: int = 0
    segments_kept: int = 0
    processing_time_ms: float = 0.0
    compression_ratio: float = 0.0


class ContextPreprocessor:
    """
    上下文预处理器

    参考 RTK 项目理念，在内容到达 LLM 之前进行优化：
    - 过滤无关内容
    - 压缩冗余信息
    - 提取关键信息
    - 优化上下文窗口
    """

    def __init__(
        self,
        max_context_tokens: int = 8192,
        compression_ratio: float = 0.3,
        enable_compression: bool = True,
        enable_dedup: bool = True,
        enable_extraction: bool = True,
        importance_threshold: float = 3.0,
    ):
        """
        初始化上下文预处理器

        Args:
            max_context_tokens: 最大上下文 token 数
            compression_ratio: 目标压缩比例（0.3 = 压缩到原来的 30%）
            enable_compression: 是否启用压缩
            enable_dedup: 是否启用去重
            enable_extraction: 是否启用关键信息提取
            importance_threshold: 重要度阈值，低于此值的内容会被过滤
        """
        self.max_context_tokens = max_context_tokens
        self.compression_ratio = compression_ratio
        self.enable_compression = enable_compression
        self.enable_dedup = enable_dedup
        self.enable_extraction = enable_extraction
        self.importance_threshold = importance_threshold

        # 处理统计
        self.stats = ProcessingStats()

        # 预编译正则表达式
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        # 代码块匹配
        self.code_pattern = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)

        # 错误信息匹配
        self.error_pattern = re.compile(
            r'(?:Error|Exception|Traceback|Failed|FAILURE|CRITICAL)[^\n]{0,200}',
            re.IGNORECASE
        )

        # 警告信息匹配
        self.warning_pattern = re.compile(
            r'(?:Warning|WARN|deprecated)[^\n]{0,200}',
            re.IGNORECASE
        )

        # 空白行压缩
        self.whitespace_pattern = re.compile(r'\n{3,}')

        # URL 匹配
        self.url_pattern = re.compile(r'https?://[^\s<>\"\')\]]+')

        # 重复行检测
        self.repeat_pattern = re.compile(r'^(.+)$\n^\1$', re.MULTILINE)

    # ─── 核心处理流程 ──────────────────────────────────

    def process_context(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """
        处理上下文（主入口）

        处理流程：
        1. 重要度评分
        2. 去重
        3. 关键信息提取
        4. 内容压缩
        5. 窗口优化

        Args:
            segments: 原始上下文片段列表

        Returns:
            优化后的上下文片段列表
        """
        start_time = time.time()

        # 记录原始 token 数
        self.stats.original_tokens = self._estimate_tokens(
            "\n".join(s.content for s in segments)
        )

        processed = segments.copy()

        # 步骤 1: 重要度评分
        processed = self._score_importance(processed)

        # 步骤 2: 去重
        if self.enable_dedup:
            processed = self._deduplicate(processed)

        # 步骤 3: 关键信息提取
        if self.enable_extraction:
            processed = self._extract_key_info(processed)

        # 步骤 4: 内容压缩
        if self.enable_compression:
            processed = self._compress_content(processed)

        # 步骤 5: 过滤低重要度内容
        processed = self._filter_by_importance(processed)

        # 步骤 6: 窗口优化
        processed = self._optimize_window(processed)

        # 更新统计
        self.stats.compressed_tokens = self._estimate_tokens(
            "\n".join(s.content for s in processed)
        )
        self.stats.processing_time_ms = (time.time() - start_time) * 1000
        self.stats.compression_ratio = (
            (1 - self.stats.compressed_tokens / max(self.stats.original_tokens, 1)) * 100
        )

        return processed

    def process_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理消息列表（LLM API 格式）

        Args:
            messages: 原始消息列表 [{"role": "user", "content": "..."}, ...]

        Returns:
            优化后的消息列表
        """
        # 转换为 ContextSegment
        segments = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 根据角色确定内容类型
            if role == "system":
                content_type = ContentType.SYSTEM
            elif role == "user":
                content_type = ContentType.USER
            elif role == "assistant":
                content_type = ContentType.ASSISTANT
            else:
                content_type = ContentType.OUTPUT

            segments.append(ContextSegment(
                content=content,
                content_type=content_type,
                source=role,
                timestamp=msg.get("timestamp", time.time()),
            ))

        # 处理
        processed_segments = self.process_context(segments)

        # 转换回消息格式
        processed_messages = []
        for segment in processed_segments:
            role_map = {
                ContentType.SYSTEM: "system",
                ContentType.USER: "user",
                ContentType.ASSISTANT: "assistant",
                ContentType.ASSISTANT: "assistant",
            }
            role = role_map.get(segment.content_type, "user")
            processed_messages.append({
                "role": role,
                "content": segment.content,
            })

        return processed_messages

    # ─── 重要度评分 ──────────────────────────────────

    def _score_importance(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """对内容进行重要度评分"""
        for segment in segments:
            score = 0.0

            # 代码内容：高分（8-10）
            if segment.content_type == ContentType.CODE:
                score += 8.0
                # 短代码更重要（通常是关键代码）
                if len(segment.content) < 100:
                    score += 2.0

            # 错误信息：最高分（10）
            if segment.content_type == ContentType.ERROR:
                score += 10.0

            # 警告信息：中高分（7）
            if segment.content_type == ContentType.WARNING:
                score += 7.0

            # 用户输入：高分（9）
            if segment.content_type == ContentType.USER:
                score += 9.0

            # 系统提示：中分（6）
            if segment.content_type == ContentType.SYSTEM:
                score += 6.0

            # 检测错误关键词
            if self.error_pattern.search(segment.content):
                score += 5.0

            # 检测代码块
            if self.code_pattern.search(segment.content):
                score += 4.0

            # 长输出降权
            if len(segment.content) > 1000:
                score -= 2.0

            # 空白内容降权
            if not segment.content.strip():
                score -= 10.0

            segment.importance_score = max(0.0, min(10.0, score))

        return segments

    # ─── 去重 ──────────────────────────────────

    def _deduplicate(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """检测并去除重复内容"""
        seen_contents = {}
        deduped = []

        for segment in segments:
            # 生成内容哈希（忽略空白）
            content_hash = self._normalize_content(segment.content)

            if content_hash in seen_contents:
                # 重复内容，保留重要度更高的
                existing = seen_contents[content_hash]
                if segment.importance_score > existing.importance_score:
                    # 替换为更重要的
                    deduped.remove(existing)
                    seen_contents[content_hash] = segment
                    deduped.append(segment)
                self.stats.segments_removed += 1
            else:
                seen_contents[content_hash] = segment
                deduped.append(segment)

        return deduped

    def _normalize_content(self, content: str) -> str:
        """标准化内容用于去重比较"""
        # 移除多余空白
        normalized = re.sub(r'\s+', ' ', content.strip())
        # 转为小写
        return normalized.lower()

    # ─── 关键信息提取 ──────────────────────────────────

    def _extract_key_info(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """从内容中提取关键信息"""
        extracted = []

        for segment in segments:
            content = segment.content

            # 提取错误信息
            errors = self.error_pattern.findall(content)
            if errors:
                error_segment = ContextSegment(
                    content="\n".join(errors[:5]),  # 最多保留 5 个错误
                    content_type=ContentType.ERROR,
                    importance_score=10.0,
                    source=f"extracted_error_{segment.source}",
                )
                extracted.append(error_segment)

            # 提取代码块
            code_blocks = self.code_pattern.findall(content)
            if code_blocks:
                for lang, code in code_blocks:
                    code_segment = ContextSegment(
                        content=f"```{lang or ''}\n{code}\n```",
                        content_type=ContentType.CODE,
                        importance_score=8.5,
                        source=f"extracted_code_{segment.source}",
                        metadata={"language": lang or "unknown"},
                    )
                    extracted.append(code_segment)

            # 如果原段没有特殊内容，保留原样
            if not errors and not code_blocks:
                extracted.append(segment)

        return extracted

    # ─── 内容压缩 ──────────────────────────────────

    def _compress_content(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """压缩内容（减少冗余）"""
        compressed = []

        for segment in segments:
            content = segment.content

            # 压缩连续空白行
            content = self.whitespace_pattern.sub('\n\n', content)

            # 压缩长输出（保留首尾）
            if len(content) > 2000 and segment.content_type in (ContentType.OUTPUT, ContentType.ASSISTANT):
                lines = content.split('\n')
                if len(lines) > 50:
                    # 保留前 20 行和后 10 行
                    compressed_content = '\n'.join(lines[:20])
                    compressed_content += f"\n\n... [{len(lines) - 30} lines omitted] ...\n\n"
                    compressed_content += '\n'.join(lines[-10:])
                    content = compressed_content
                    segment.is_compressed = True
                    self.stats.segments_compressed += 1

            # 压缩重复行
            content = self._compress_repeated_lines(content)

            segment.content = content
            compressed.append(segment)

        return compressed

    def _compress_repeated_lines(self, content: str) -> str:
        """压缩重复行"""
        lines = content.split('\n')
        compressed = []
        repeat_count = 0
        last_line = None

        for line in lines:
            if line == last_line and repeat_count < 3:
                repeat_count += 1
                if repeat_count == 3:
                    compressed.append(f"... (repeated {repeat_count + 1} times)")
            else:
                compressed.append(line)
                repeat_count = 0
            last_line = line

        return '\n'.join(compressed)

    # ─── 过滤 ──────────────────────────────────

    def _filter_by_importance(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """过滤低重要度内容"""
        filtered = []

        for segment in segments:
            if segment.importance_score >= self.importance_threshold:
                filtered.append(segment)
            else:
                self.stats.segments_removed += 1

        return filtered

    # ─── 窗口优化 ──────────────────────────────────

    def _optimize_window(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """优化上下文窗口，确保不超过最大 token 数"""
        total_tokens = self._estimate_tokens(
            "\n".join(s.content for s in segments)
        )

        # 如果未超过限制，直接返回
        if total_tokens <= self.max_context_tokens:
            return segments

        # 按重要度排序
        sorted_segments = sorted(segments, key=lambda s: s.importance_score, reverse=True)

        # 保留系统消息（最高优先级）
        system_segments = [s for s in sorted_segments if s.content_type == ContentType.SYSTEM]
        other_segments = [s for s in sorted_segments if s.content_type != ContentType.SYSTEM]

        optimized = system_segments.copy()
        current_tokens = self._estimate_tokens(
            "\n".join(s.content for s in optimized)
        )

        # 按重要度添加其他段
        for segment in other_segments:
            segment_tokens = self._estimate_tokens(segment.content)
            if current_tokens + segment_tokens <= self.max_context_tokens:
                optimized.append(segment)
                current_tokens += segment_tokens
            else:
                self.stats.segments_removed += 1

        return optimized

    # ─── Token 估算 ──────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量

        基于经验规则：
        - 英文：1 token ≈ 4 字符
        - 中文：1 token ≈ 1-2 字符
        - 代码：1 token ≈ 3 字符
        """
        if not text:
            return 0

        # 简单估算
        char_count = len(text)

        # 检测是否包含中文
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))

        if has_chinese:
            # 中文占比较高，使用更保守的估算
            return int(char_count * 0.7)
        else:
            # 英文/代码
            return int(char_count / 3.5)

    # ─── 辅助方法 ──────────────────────────────────

    def get_stats(self) -> ProcessingStats:
        """获取处理统计"""
        return self.stats

    def reset_stats(self):
        """重置统计"""
        self.stats = ProcessingStats()

    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> 'ContextPreprocessor':
        """从配置字典创建预处理器"""
        return ContextPreprocessor(
            max_context_tokens=config.get("max_context_tokens", 8192),
            compression_ratio=config.get("compression_ratio", 0.3),
            enable_compression=config.get("enable_compression", True),
            enable_dedup=config.get("enable_dedup", True),
            enable_extraction=config.get("enable_extraction", True),
            importance_threshold=config.get("importance_threshold", 3.0),
        )
