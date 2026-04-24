# -*- coding: utf-8 -*-
"""
超大文档性能优化 - Streaming Document Processor
================================================

功能：
1. 文档分块流式处理
2. 增量分析
3. 内存优化
4. 进度跟踪
5. 中断恢复

Author: Hermes Desktop Team
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable, Iterator, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """处理模式"""
    STREAMING = "streaming"     # 流式处理
    BATCH = "batch"             # 批量处理
    INCREMENTAL = "incremental"  # 增量处理


@dataclass
class ChunkInfo:
    """分块信息"""
    chunk_id: str
    index: int
    content: str
    start_pos: int
    end_pos: int
    length: int
    checksum: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "index": self.index,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "length": self.length,
        }


@dataclass
class ProcessingProgress:
    """处理进度"""
    total_chunks: int = 0
    processed_chunks: int = 0
    current_chunk: int = 0
    processed_bytes: int = 0
    total_bytes: int = 0
    start_time: float = 0
    status: str = "pending"  # pending/processing/completed/error
    current_operation: str = ""
    
    def get_percentage(self) -> float:
        if self.total_chunks == 0:
            return 0
        return self.processed_chunks / self.total_chunks * 100
    
    def get_eta(self) -> float:
        """预估剩余时间（秒）"""
        if self.processed_chunks == 0:
            return 0
        elapsed = datetime.now().timestamp() - self.start_time
        rate = self.processed_chunks / elapsed
        remaining = self.total_chunks - self.processed_chunks
        return remaining / rate if rate > 0 else 0


@dataclass
class ProcessingConfig:
    """处理配置"""
    # 分块大小
    chunk_size: int = 5000  # 字符数
    chunk_overlap: int = 200  # 重叠字符数
    
    # 内存限制
    max_memory_mb: int = 512
    
    # 并发控制
    max_concurrent_chunks: int = 3
    
    # 处理选项
    preserve_structure: bool = True  # 保持章节结构
    extract_metadata: bool = True
    
    # 缓存
    enable_cache: bool = True
    cache_dir: Optional[str] = None


class StreamingProcessor:
    """
    流式文档处理器
    
    用于超大文档的性能优化处理
    
    使用示例：
    ```python
    processor = StreamingProcessor()
    
    # 配置
    config = ProcessingConfig(chunk_size=3000, max_concurrent_chunks=2)
    
    # 同步处理
    result = processor.process_sync(large_document, config)
    
    # 异步流式处理
    async for chunk_result in processor.process_stream(large_document):
        logger.info(f"处理中: {chunk_result['progress']}%")
        
    # 增量处理（中断恢复）
    checkpoint = processor.create_checkpoint()
    result = processor.process_incremental(document, checkpoint)
    ```
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self._cache: Dict[str, Any] = {}
        self._checkpoints: Dict[str, Dict] = {}
        
    def chunk_document(
        self,
        content: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None
    ) -> List[ChunkInfo]:
        """
        文档分块
        
        Args:
            content: 文档内容
            chunk_size: 块大小
            overlap: 重叠大小
        
        Returns:
            List[ChunkInfo]: 分块列表
        """
        chunk_size = chunk_size or self.config.chunk_size
        overlap = overlap or self.config.chunk_overlap
        
        if len(content) <= chunk_size:
            return [ChunkInfo(
                chunk_id=self._generate_chunk_id(content[:50]),
                index=0,
                content=content,
                start_pos=0,
                end_pos=len(content),
                length=len(content),
                checksum=self._checksum(content),
            )]
            
        chunks = []
        start = 0
        index = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            
            # 尝试在句子边界分割
            if end < len(content):
                # 向前查找句子边界
                boundary = self._find_boundary(content, start, end)
                if boundary > start:
                    end = boundary
                    
            chunk_content = content[start:end]
            
            chunk_info = ChunkInfo(
                chunk_id=self._generate_chunk_id(chunk_content[:50]),
                index=index,
                content=chunk_content,
                start_pos=start,
                end_pos=end,
                length=len(chunk_content),
                checksum=self._checksum(chunk_content),
            )
            chunks.append(chunk_info)
            
            # 下一个块的起点（考虑重叠）
            start = end - overlap if end < len(content) else end
            index += 1
            
            if start >= len(content):
                break
                
        return chunks
    
    def _find_boundary(self, content: str, start: int, end: int) -> int:
        """查找句子边界"""
        # 优先在换行符处分隔
        for i in range(end - 1, start + 100, -1):
            if content[i] == '\n':
                # 检查是否确实是段落结束
                next_char = content[i + 1] if i + 1 < len(content) else ''
                if next_char in '\n　 ' or next_char.isupper():
                    return i + 1
                    
        # 其次在句号处分隔
        for i in range(end - 1, start + 50, -1):
            if content[i] in '。！？；':
                return i + 1
                
        return end
    
    def _generate_chunk_id(self, prefix: str) -> str:
        """生成块ID"""
        return hashlib.md5(f"{prefix}{datetime.now().timestamp()}".encode()).hexdigest()[:12]
    
    def _checksum(self, content: str) -> str:
        """计算校验和"""
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def process_sync(
        self,
        content: str,
        config: Optional[ProcessingConfig] = None,
        process_func: Optional[Callable[[str], Dict]] = None
    ) -> Dict[str, Any]:
        """
        同步处理文档
        
        Args:
            content: 文档内容
            config: 处理配置
            process_func: 处理函数
        
        Returns:
            Dict: 处理结果
        """
        config = config or self.config
        
        # 分块
        chunks = self.chunk_document(content, config.chunk_size, config.chunk_overlap)
        
        results = []
        progress = ProcessingProgress(
            total_chunks=len(chunks),
            total_bytes=len(content),
            status="processing",
            start_time=datetime.now().timestamp(),
        )
        
        for i, chunk in enumerate(chunks):
            progress.current_chunk = i
            
            # 检查缓存
            if config.enable_cache and chunk.checksum in self._cache:
                results.append(self._cache[chunk.checksum])
            else:
                # 处理
                if process_func:
                    result = process_func(chunk.content)
                else:
                    result = self._default_process(chunk.content)
                    
                results.append(result)
                
                # 更新缓存
                if config.enable_cache:
                    self._cache[chunk.checksum] = result
                    
            progress.processed_chunks += 1
            progress.processed_bytes += chunk.length
            
        progress.status = "completed"
        
        return {
            "chunks": len(results),
            "results": results,
            "progress": progress,
            "merged": self._merge_results(results),
        }
    
    async def process_stream(
        self,
        content: str,
        config: Optional[ProcessingConfig] = None,
        process_func: Optional[Callable[[str], Dict]] = None,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        异步流式处理
        
        Args:
            content: 文档内容
            config: 处理配置
            process_func: 处理函数
            progress_callback: 进度回调
        
        Yields:
            Dict: 处理结果（每个块的结果）
        """
        config = config or self.config
        
        # 分块
        chunks = self.chunk_document(content, config.chunk_size, config.chunk_overlap)
        
        progress = ProcessingProgress(
            total_chunks=len(chunks),
            total_bytes=len(content),
            status="processing",
            start_time=datetime.now().timestamp(),
        )
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(config.max_concurrent_chunks)
        
        async def process_chunk(chunk: ChunkInfo) -> Dict[str, Any]:
            async with semaphore:
                progress.current_operation = f"处理第 {chunk.index + 1} 块"
                
                # 检查缓存
                if config.enable_cache and chunk.checksum in self._cache:
                    result = self._cache[chunk.checksum]
                else:
                    # 处理
                    if process_func:
                        result = await self._async_wrapper(process_func, chunk.content)
                    else:
                        result = await self._default_process_async(chunk.content)
                        
                    if config.enable_cache:
                        self._cache[chunk.checksum] = result
                        
                progress.processed_chunks += 1
                progress.processed_bytes += chunk.length
                
                if progress_callback:
                    progress_callback(progress)
                    
                return {
                    "chunk": chunk.to_dict(),
                    "result": result,
                    "progress": progress,
                }
                
        # 并发处理所有块
        tasks = [process_chunk(chunk) for chunk in chunks]
        
        for coro in asyncio.as_completed(tasks):
            yield await coro
            
        progress.status = "completed"
        if progress_callback:
            progress_callback(progress)
    
    async def _async_wrapper(self, func: Callable, content: str) -> Dict:
        """异步包装同步函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, content)
    
    async def _default_process_async(self, content: str) -> Dict:
        """默认异步处理"""
        # 简单处理：提取关键信息
        return self._default_process(content)
    
    def _default_process(self, content: str) -> Dict:
        """默认处理"""
        # 提取关键信息
        entities = self._extract_entities(content)
        keywords = self._extract_keywords(content)
        sections = self._extract_sections(content)
        
        return {
            "entities": entities,
            "keywords": keywords,
            "sections": sections,
            "stats": {
                "length": len(content),
                "lines": content.count('\n'),
                "sentences": content.count('。') + content.count('!') + content.count('?'),
            }
        }
    
    def _extract_entities(self, content: str) -> Dict[str, List[str]]:
        """提取实体"""
        import re
        entities = {
            "numbers": re.findall(r'\d+(?:\.\d+)?(?:\s*(?:万|亿|元|吨|%))?', content)[:20],
            "standards": re.findall(r'(?:GB|HJ|AQ|YD)\s*\d+(?:\.\d+)*', content, re.IGNORECASE)[:10],
            "dates": re.findall(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?', content)[:10],
        }
        return entities
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        import re
        # 简单提取：出现频率高的短语
        words = re.findall(r'[\u4e00-\u9fa5]{3,6}', content)
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:20] if len(w[0]) >= 3]
    
    def _extract_sections(self, content: str) -> List[Dict]:
        """提取章节"""
        import re
        sections = []
        
        # 标题模式
        patterns = [
            r'^#{1,6}\s+(.+)$',
            r'^第[一二三四五六七八九十]+[章节](?:之)?(.+)$',
            r'^(\d+\.)+\s+(.+)$',
            r'^【(.+?)】$',
        ]
        
        for line_num, line in enumerate(content.split('\n')[:100]):
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    title = match.group(1) if match.lastindex else match.group(0)
                    sections.append({
                        "title": title.strip(),
                        "line": line_num,
                    })
                    break
                    
        return sections
    
    def _merge_results(self, results: List[Dict]) -> Dict:
        """合并处理结果"""
        merged = {
            "entities": {},
            "keywords": [],
            "sections": [],
            "stats": {"total_length": 0, "total_lines": 0, "total_sentences": 0},
        }
        
        keyword_freq = {}
        
        for result in results:
            # 合并实体
            for key, values in result.get("entities", {}).items():
                if key not in merged["entities"]:
                    merged["entities"][key] = []
                merged["entities"][key].extend(values)
                
            # 合并关键词频率
            for kw in result.get("keywords", []):
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
                
            # 合并统计
            stats = result.get("stats", {})
            merged["stats"]["total_length"] += stats.get("length", 0)
            merged["stats"]["total_lines"] += stats.get("lines", 0)
            merged["stats"]["total_sentences"] += stats.get("sentences", 0)
            
            # 合并章节
            merged["sections"].extend(result.get("sections", []))
            
        # 去重关键词
        sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        merged["keywords"] = [kw for kw, _ in sorted_keywords[:50]]
        
        # 去重实体
        for key in merged["entities"]:
            merged["entities"][key] = list(set(merged["entities"][key]))[:20]
            
        return merged
    
    def create_checkpoint(self, doc_id: str, progress: ProcessingProgress) -> str:
        """
        创建检查点（用于中断恢复）
        
        Args:
            doc_id: 文档ID
            progress: 处理进度
        
        Returns:
            str: 检查点ID
        """
        checkpoint_id = f"cp_{doc_id}_{datetime.now().timestamp()}"
        self._checkpoints[checkpoint_id] = {
            "progress": progress.__dict__,
            "timestamp": datetime.now().isoformat(),
        }
        return checkpoint_id
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[ProcessingProgress]:
        """获取检查点"""
        if checkpoint_id in self._checkpoints:
            cp = self._checkpoints[checkpoint_id]
            progress = ProcessingProgress()
            progress.__dict__.update(cp["progress"])
            return progress
        return None
    
    def process_incremental(
        self,
        content: str,
        checkpoint_id: Optional[str] = None,
        config: Optional[ProcessingConfig] = None
    ) -> Dict[str, Any]:
        """
        增量处理（支持中断恢复）
        
        Args:
            content: 文档内容
            checkpoint_id: 检查点ID
            config: 处理配置
        
        Returns:
            Dict: 处理结果
        """
        config = config or self.config
        
        chunks = self.chunk_document(content)
        
        start_index = 0
        
        # 如果有检查点，从断点继续
        if checkpoint_id and checkpoint_id in self._checkpoints:
            checkpoint = self._checkpoints[checkpoint_id]
            start_index = checkpoint["progress"].get("processed_chunks", 0)
            logger.info(f"从检查点恢复: {start_index}/{len(chunks)}")
            
        results = []
        
        for i in range(start_index, len(chunks)):
            chunk = chunks[i]
            
            if config.enable_cache and chunk.checksum in self._cache:
                results.append(self._cache[chunk.checksum])
            else:
                result = self._default_process(chunk.content)
                results.append(result)
                
                if config.enable_cache:
                    self._cache[chunk.checksum] = result
                    
        return {
            "chunks": len(results),
            "results": results,
            "merged": self._merge_results(results),
            "processed_from": start_index,
        }
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
    
    def get_memory_usage(self) -> Dict[str, int]:
        """获取内存使用情况"""
        import sys
from core.logger import get_logger
logger = get_logger('smart_writing.streaming_processor')

        
        # 估算缓存大小
        cache_size = sum(
            sys.getsizeof(str(v)) for v in self._cache.values()
        )
        
        return {
            "cache_entries": len(self._cache),
            "cache_size_bytes": cache_size,
            "cache_size_mb": cache_size / (1024 * 1024),
        }


# 全局实例
_processor: Optional[StreamingProcessor] = None


def get_streaming_processor() -> StreamingProcessor:
    """获取全局流式处理器"""
    global _processor
    if _processor is None:
        _processor = StreamingProcessor()
    return _processor


async def quick_process(content: str, chunk_size: int = 3000) -> Dict:
    """快速处理文档"""
    processor = get_streaming_processor()
    results = []
    
    async for result in processor.process_stream(content):
        results.append(result["result"])
        
    return processor._merge_results(results)
