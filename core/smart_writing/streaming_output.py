# -*- coding: utf-8 -*-
"""
流式输出系统 - Streaming Output System
======================================

功能：
1. 打字机效果（逐字/逐词/逐句输出）
2. 智能断句（标点、空格、Markdown边界）
3. 速率控制（可配置速度）
4. 暂停/恢复控制
5. 多格式支持（文本、Markdown、代码块）
6. 回调集成（进度、状态、格式化）

设计原则：
- 异步优先，支持同步调用
- 可中断、可恢复
- 支持富文本渲染
- 与 PyQt6/Qt 完美集成

Author: Hermes Desktop Team
"""

import asyncio
import time
import re
import threading
from typing import Optional, Callable, Dict, Any, List, Generator, AsyncGenerator, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from core.logger import get_logger
logger = get_logger('smart_writing.streaming_output')


logger = logging.getLogger(__name__)


# =============================================================================
# 输出模式与配置
# =============================================================================

class OutputMode(Enum):
    """输出模式"""
    INSTANT = "instant"              # 即时输出（无延迟）
    TYPEWRITER = "typewriter"        # 逐字输出（打字机效果）
    WORD = "word"                    # 逐词输出
    SENTENCE = "sentence"            # 逐句输出
    PARAGRAPH = "paragraph"          # 逐段输出


class OutputSpeed(Enum):
    """输出速度"""
    FAST = ("fast", 0.001)           # 极快（1ms/字）
    NORMAL = ("normal", 0.01)        # 正常（10ms/字）
    SLOW = ("slow", 0.03)           # 慢速（30ms/字）
    TYPING = ("typing", 0.05)        # 打字速度（50ms/字）
    
    def __init__(self, name: str, delay: float):
        self._name = name
        self.delay = delay


@dataclass
class StreamingConfig:
    """流式输出配置"""
    # 模式
    mode: OutputMode = OutputMode.TYPEWRITER
    speed: OutputSpeed = OutputSpeed.NORMAL
    
    # 断句规则
    sentence_delimiters: str = "。！？；\n"
    word_delimiters: str = " \t\n.,!?;:'\"()[]{}"
    
    # Markdown 处理
    enable_markdown_aware: bool = True
    code_block_delay: float = 0.5      # 代码块开始/结束延迟
    
    # 智能等待
    sentence_pause: float = 0.1        # 句末额外暂停
    comma_pause: float = 0.05          # 逗号暂停
    paragraph_pause: float = 0.2       # 段末额外暂停
    
    # 控制
    enable_sound: bool = False         # 打字音效
    sound_volume: float = 0.3          # 音量
    
    # 缓冲区
    buffer_size: int = 100             # 输出缓冲区大小


@dataclass
class OutputChunk:
    """输出块"""
    content: str
    chunk_type: str = "text"           # text/markdown/code/section
    start_pos: int = 0
    end_pos: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return self.content


# =============================================================================
# 断句器
# =============================================================================

class SentenceTokenizer:
    """
    智能断句器
    
    功能：
    1. Markdown 感知（代码块、标题、列表等）
    2. 标点断句（中文、英文）
    3. 结构断句（段落、空行）
    """
    
    # Markdown 模式正则
    MARKDOWN_PATTERNS = {
        "code_block": re.compile(r'```[\s\S]*?```'),
        "inline_code": re.compile(r'`[^`]+`'),
        "heading": re.compile(r'^#{1,6}\s+.+$', re.MULTILINE),
        "list_item": re.compile(r'^[\s]*[-*+]\s+.+$', re.MULTILINE),
        "numbered_list": re.compile(r'^[\s]*\d+\.\s+.+$', re.MULTILINE),
        "blank_line": re.compile(r'\n\s*\n'),
    }
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
    
    def split(self, text: str, mode: OutputMode = OutputMode.SENTENCE) -> List[str]:
        """
        断句
        
        Args:
            text: 原始文本
            mode: 输出模式
        
        Returns:
            分块列表
        """
        if mode == OutputMode.INSTANT:
            return [text]
        
        if mode == OutputMode.PARAGRAPH:
            return self._split_paragraphs(text)
        
        if mode == OutputMode.SENTENCE:
            return self._split_sentences(text)
        
        if mode == OutputMode.WORD:
            return self._split_words(text)
        
        # TYPEWRITER: 返回每个字符
        return list(text)
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """按段落分割"""
        if self.config.enable_markdown_aware:
            # 先处理 Markdown 结构
            text = self._normalize_markdown(text)
        
        paragraphs = []
        current = ""
        
        for line in text.split('\n'):
            if line.strip():
                current += line + '\n'
            else:
                if current.strip():
                    paragraphs.append(current.rstrip())
                current = ""
        
        if current.strip():
            paragraphs.append(current.rstrip())
        
        return paragraphs if paragraphs else [text]
    
    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割"""
        if self.config.enable_markdown_aware:
            # 保护 Markdown 结构
            protected, markers = self._protect_markdown(text)
        else:
            protected = text
            markers = {}
        
        sentences = []
        current = ""
        i = 0
        
        while i < len(protected):
            char = protected[i]
            current += char
            
            # 检查是否到达句子边界
            if char in self.config.sentence_delimiters:
                # 确认是句子结束（后面是空白或句子开始）
                next_char = protected[i + 1] if i + 1 < len(protected) else ''
                if next_char in ' \t\n' or not next_char or next_char.isupper():
                    sentences.append(current)
                    current = ""
            
            i += 1
        
        if current.strip():
            sentences.append(current)
        
        return sentences if sentences else [text]
    
    def _split_words(self, text: str) -> List[str]:
        """按单词分割"""
        # 中文按字符，英文按空格分词
        words = []
        current_word = ""
        
        for char in text:
            if char in ' \t\n':
                if current_word:
                    words.append(current_word)
                    current_word = ""
            else:
                current_word += char
        
        if current_word:
            words.append(current_word)
        
        return words if words else [text]
    
    def _protect_markdown(self, text: str) -> tuple:
        """
        保护 Markdown 结构，替换为临时标记
        
        Returns:
            (处理后文本, 标记映射)
        """
        markers = {}
        marker_id = 0
        
        # 保护代码块
        for match in self.MARKDOWN_PATTERNS["code_block"].finditer(text):
            marker = f"\x00MD_MARKER_{marker_id}\x00"
            markers[marker] = match.group()
            text = text.replace(match.group(), marker)
            marker_id += 1
        
        # 保护行内代码
        for match in self.MARKDOWN_PATTERNS["inline_code"].finditer(text):
            marker = f"\x00MD_MARKER_{marker_id}\x00"
            markers[marker] = match.group()
            text = text.replace(match.group(), marker)
            marker_id += 1
        
        return text, markers
    
    def _normalize_markdown(self, text: str) -> str:
        """Markdown 结构规范化"""
        # 确保代码块之间有空行
        text = re.sub(r'```\n[^`]+', r'\g<0>\n', text)
        return text
    
    def calculate_pause(self, chunk: str) -> float:
        """
        计算输出后暂停时间
        
        Args:
            chunk: 输出块
        
        Returns:
            暂停时间（秒）
        """
        if not chunk:
            return 0
        
        # 基础暂停
        pause = self.config.speed.delay * len(chunk)
        
        # 句末暂停
        if chunk[-1] in '。！？':
            pause += self.config.sentence_pause
        
        # 逗号暂停
        elif chunk[-1] in '，；:':
            pause += self.config.comma_pause
        
        # 段末暂停
        elif chunk[-1] == '\n' and chunk.rstrip('\n').endswith('\n'):
            pause += self.config.paragraph_pause
        
        # 代码块暂停
        if '```' in chunk:
            pause += self.config.code_block_delay
        
        return pause


# =============================================================================
# 回调与状态
# =============================================================================

@dataclass
class StreamingState:
    """流式输出状态"""
    is_running: bool = False
    is_paused: bool = False
    is_cancelled: bool = False
    total_chars: int = 0
    output_chars: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def progress(self) -> float:
        """进度百分比"""
        if self.total_chars == 0:
            return 0
        return self.output_chars / self.total_chars
    
    @property
    def elapsed(self) -> float:
        """已用时间"""
        if self.start_time == 0:
            return 0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time
    
    @property
    def eta(self) -> float:
        """预估剩余时间"""
        if self.output_chars == 0 or self.elapsed == 0:
            return 0
        rate = self.output_chars / self.elapsed
        remaining = self.total_chars - self.output_chars
        return remaining / rate if rate > 0 else 0


# =============================================================================
# 抽象输出器
# =============================================================================

class OutputSink(ABC):
    """输出接收器抽象基类"""
    
    @abstractmethod
    def write(self, chunk: OutputChunk) -> None:
        """写入单个块"""
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """刷新缓冲区"""
        pass
    
    def on_start(self, state: StreamingState) -> None:
        """开始回调"""
        pass
    
    def on_complete(self, state: StreamingState) -> None:
        """完成回调"""
        pass
    
    def on_cancel(self, state: StreamingState) -> None:
        """取消回调"""
        pass
    
    def on_error(self, error: Exception, state: StreamingState) -> None:
        """错误回调"""
        pass


class StringBuilderSink(OutputSink):
    """字符串构建器输出"""
    
    def __init__(self):
        self.builder = ""
    
    def write(self, chunk: OutputChunk) -> None:
        self.builder += chunk.content
    
    def flush(self) -> None:
        pass
    
    def get_result(self) -> str:
        return self.builder


class ListSink(OutputSink):
    """列表输出"""
    
    def __init__(self):
        self.chunks: List[OutputChunk] = []
    
    def write(self, chunk: OutputChunk) -> None:
        self.chunks.append(chunk)
    
    def flush(self) -> None:
        pass
    
    def get_result(self) -> str:
        return "".join(c.content for c in self.chunks)


# =============================================================================
# 核心流式输出器
# =============================================================================

class StreamingOutput:
    """
    流式输出器
    
    支持打字机效果、智能断句、暂停恢复
    """
    
    def __init__(
        self,
        config: Optional[StreamingConfig] = None,
        sink: Optional[OutputSink] = None,
    ):
        self.config = config or StreamingConfig()
        self.sink = sink or StringBuilderSink()
        self.tokenizer = SentenceTokenizer(self.config)
        self.state = StreamingState()
        
        # 事件回调
        self.on_progress: Optional[Callable[[StreamingState], None]] = None
        self.on_chunk: Optional[Callable[[OutputChunk], None]] = None
        self.on_markdown_detected: Optional[Callable[[str, Dict], None]] = None
        
        # 锁
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    # ── 配置方法 ──────────────────────────────────────────────────────────────
    
    def set_mode(self, mode: OutputMode) -> "StreamingOutput":
        """设置输出模式"""
        self.config.mode = mode
        return self
    
    def set_speed(self, speed: OutputSpeed) -> "StreamingOutput":
        """设置输出速度"""
        self.config.speed = speed
        return self
    
    def set_callbacks(
        self,
        on_progress: Optional[Callable[[StreamingState], None]] = None,
        on_chunk: Optional[Callable[[OutputChunk], None]] = None,
    ) -> "StreamingOutput":
        """设置回调"""
        self.on_progress = on_progress
        self.on_chunk = on_chunk
        return self
    
    # ── 同步流式输出 ─────────────────────────────────────────────────────────
    
    def stream_sync(
        self,
        text: str,
        delay_func: Optional[Callable[[str], float]] = None,
    ) -> str:
        """
        同步流式输出
        
        Args:
            text: 要输出的文本
            delay_func: 自定义延迟函数
        
        Returns:
            完整输出文本
        """
        self.state = StreamingState(
            is_running=True,
            total_chars=len(text),
            start_time=time.time(),
        )
        self.sink.on_start(self.state)
        
        try:
            # 分块
            chunks = self.tokenizer.split(text, self.config.mode)
            
            for i, chunk_text in enumerate(chunks):
                if self.state.is_cancelled:
                    break
                
                # 等待（如暂停）
                while self.state.is_paused and not self.state.is_cancelled:
                    time.sleep(0.05)
                
                if self.state.is_cancelled:
                    break
                
                # 创建输出块
                chunk = OutputChunk(
                    content=chunk_text,
                    chunk_type=self._detect_chunk_type(chunk_text),
                    start_pos=sum(len(c) for c in chunks[:i]),
                    end_pos=sum(len(c) for c in chunks[:i+1]),
                )
                
                # 输出
                self.sink.write(chunk)
                self.sink.flush()
                self.state.output_chars += len(chunk_text)
                
                # 回调
                if self.on_chunk:
                    self.on_chunk(chunk)
                if self.on_progress:
                    self.on_progress(self.state)
                
                # 延迟
                if self.config.mode != OutputMode.INSTANT:
                    delay = delay_func(chunk_text) if delay_func else self.tokenizer.calculate_pause(chunk_text)
                    time.sleep(delay)
            
            self.state.end_time = time.time()
            self.sink.on_complete(self.state)
            
        except Exception as e:
            self.sink.on_error(e, self.state)
            raise
        
        finally:
            self.state.is_running = False
        
        return self.sink.get_result()
    
    # ── 异步流式输出 ─────────────────────────────────────────────────────────
    
    async def stream_async(self, text: str) -> str:
        """
        异步流式输出
        
        Args:
            text: 要输出的文本
        
        Returns:
            完整输出文本
        """
        self.state = StreamingState(
            is_running=True,
            total_chars=len(text),
            start_time=time.time(),
        )
        self._loop = asyncio.get_event_loop()
        self.sink.on_start(self.state)
        
        try:
            chunks = self.tokenizer.split(text, self.config.mode)
            
            for i, chunk_text in enumerate(chunks):
                if self.state.is_cancelled:
                    break
                
                while self.state.is_paused and not self.state.is_cancelled:
                    await asyncio.sleep(0.05)
                
                if self.state.is_cancelled:
                    break
                
                chunk = OutputChunk(
                    content=chunk_text,
                    chunk_type=self._detect_chunk_type(chunk_text),
                    start_pos=sum(len(c) for c in chunks[:i]),
                    end_pos=sum(len(c) for c in chunks[:i+1]),
                )
                
                self.sink.write(chunk)
                self.sink.flush()
                self.state.output_chars += len(chunk_text)
                
                if self.on_chunk:
                    if asyncio.iscoroutinefunction(self.on_chunk):
                        await self.on_chunk(chunk)
                    else:
                        self.on_chunk(chunk)
                
                if self.on_progress:
                    if asyncio.iscoroutinefunction(self.on_progress):
                        await self.on_progress(self.state)
                    else:
                        self.on_progress(self.state)
                
                if self.config.mode != OutputMode.INSTANT:
                    delay = self.tokenizer.calculate_pause(chunk_text)
                    await asyncio.sleep(delay)
            
            self.state.end_time = time.time()
            self.sink.on_complete(self.state)
            
        except Exception as e:
            self.sink.on_error(e, self.state)
            raise
        
        finally:
            self.state.is_running = False
        
        return self.sink.get_result()
    
    # ── 生成器接口 ───────────────────────────────────────────────────────────
    
    def stream_generator(self, text: str) -> Generator[OutputChunk, None, None]:
        """
        生成器接口（用于同步迭代）
        
        Yields:
            OutputChunk: 输出块
        """
        chunks = self.tokenizer.split(text, self.config.mode)
        
        for chunk_text in chunks:
            if self.state.is_cancelled:
                return
            
            while self.state.is_paused and not self.state.is_cancelled:
                time.sleep(0.05)
            
            yield OutputChunk(
                content=chunk_text,
                chunk_type=self._detect_chunk_type(chunk_text),
            )
            
            if self.config.mode != OutputMode.INSTANT:
                delay = self.tokenizer.calculate_pause(chunk_text)
                time.sleep(delay)
    
    async def stream_async_generator(self, text: str) -> AsyncGenerator[OutputChunk, None]:
        """
        异步生成器接口
        
        Yields:
            OutputChunk: 输出块
        """
        chunks = self.tokenizer.split(text, self.config.mode)
        
        for chunk_text in chunks:
            if self.state.is_cancelled:
                return
            
            while self.state.is_paused and not self.state.is_cancelled:
                await asyncio.sleep(0.05)
            
            yield OutputChunk(
                content=chunk_text,
                chunk_type=self._detect_chunk_type(chunk_text),
            )
            
            if self.config.mode != OutputMode.INSTANT:
                delay = self.tokenizer.calculate_pause(chunk_text)
                await asyncio.sleep(delay)
    
    # ── 控制方法 ─────────────────────────────────────────────────────────────
    
    def pause(self) -> None:
        """暂停输出"""
        with self._lock:
            if self.state.is_running:
                self.state.is_paused = True
    
    def resume(self) -> None:
        """恢复输出"""
        with self._lock:
            self.state.is_paused = False
    
    def cancel(self) -> None:
        """取消输出"""
        with self._lock:
            self.state.is_cancelled = True
            self.state.is_paused = False
            self.sink.on_cancel(self.state)
    
    def reset(self) -> None:
        """重置状态"""
        self.state = StreamingState()
        if hasattr(self.sink, 'builder'):
            self.sink.builder = ""
        elif hasattr(self.sink, 'chunks'):
            self.sink.chunks = []
    
    # ── 辅助方法 ─────────────────────────────────────────────────────────────
    
    def _detect_chunk_type(self, chunk: str) -> str:
        """检测块类型"""
        chunk = chunk.strip()
        
        if chunk.startswith('```'):
            return "code_block_start" if chunk.count('```') == 1 else "code_block"
        if chunk.startswith('`') and chunk.endswith('`'):
            return "inline_code"
        if chunk.startswith('#'):
            return "heading"
        if chunk.startswith('- ') or chunk.startswith('* '):
            return "list_item"
        if re.match(r'^\d+\.\s', chunk):
            return "numbered_list"
        if chunk.startswith('|'):
            return "table"
        
        return "text"


# =============================================================================
# 增强版流式输出器（支持 Markdown 渲染）
# =============================================================================

class EnhancedStreamingOutput(StreamingOutput):
    """
    增强版流式输出器
    
    特性：
    1. Markdown 结构感知
    2. 语法高亮支持
    3. 表格流式输出
    4. 代码块特殊处理
    """
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        super().__init__(config)
        
        # Markdown 解析状态
        self._in_code_block = False
        self._in_table = False
        self._current_lang = ""
    
    def _detect_chunk_type(self, chunk: str) -> str:
        """增强的块类型检测"""
        chunk = chunk.strip()
        
        # 代码块
        if '```' in chunk:
            if chunk.startswith('```'):
                self._in_code_block = True
                self._current_lang = chunk[3:].strip()
                return "code_block_start"
            if chunk.endswith('```'):
                self._in_code_block = False
                self._current_lang = ""
                return "code_block_end"
            return "code_block"
        
        if self._in_code_block:
            return "code_content"
        
        # 行内代码
        if chunk.startswith('`') and chunk.endswith('`'):
            return "inline_code"
        
        # 标题
        if chunk.startswith('#'):
            level = len(chunk) - len(chunk.lstrip('#'))
            return f"heading_{level}"
        
        # 列表
        if chunk.startswith('- ') or chunk.startswith('* '):
            return "bullet_list"
        if re.match(r'^\d+\.\s', chunk):
            return "numbered_list"
        
        # 表格
        if chunk.startswith('|'):
            if '| --- |' in chunk or '|---|---|' in chunk:
                return "table_header"
            return "table_row"
        
        # 引用
        if chunk.startswith('>'):
            return "blockquote"
        
        # 链接/图片
        if '](' in chunk:
            return "link"
        
        # 强调
        if chunk.startswith('**') or chunk.startswith('*'):
            return "emphasis"
        
        return "text"
    
    def stream_markdown_sync(self, markdown_text: str) -> str:
        """
        流式输出 Markdown（保持结构）
        
        Args:
            markdown_text: Markdown 文本
        
        Returns:
            完整输出文本
        """
        # 按行分割，保持 Markdown 结构
        lines = markdown_text.split('\n')
        
        self.state = StreamingState(
            is_running=True,
            total_chars=len(markdown_text),
            start_time=time.time(),
        )
        self.sink.on_start(self.state)
        
        try:
            buffer = ""
            
            for line in lines:
                # 检测行类型
                line_type = self._detect_line_type(line)
                
                if line_type == "code_block_start":
                    self._flush_buffer(buffer)
                    buffer = ""
                    self._output_chunk(line, "code_block_start")
                    continue
                
                if line_type == "code_block_end":
                    buffer += line + "\n"
                    self._flush_buffer(buffer)
                    buffer = ""
                    self._output_chunk("", "code_block_end")
                    continue
                
                if self._in_code_block:
                    # 代码块内直接输出
                    self._output_chunk(line + "\n", "code_content")
                    continue
                
                # 普通行：累积到缓冲区
                buffer += line + "\n"
                
                # 空行触发缓冲区输出
                if not line.strip():
                    self._flush_buffer(buffer)
                    buffer = ""
            
            # 输出剩余内容
            if buffer:
                self._flush_buffer(buffer)
            
            self.state.end_time = time.time()
            self.sink.on_complete(self.state)
            
        except Exception as e:
            self.sink.on_error(e, self.state)
            raise
        
        finally:
            self.state.is_running = False
            self._in_code_block = False
        
        return self.sink.get_result()
    
    def _detect_line_type(self, line: str) -> str:
        """检测行类型"""
        line = line.strip()
        
        if line.startswith('```'):
            return "code_block_start" if not self._in_code_block else "code_block_end"
        if self._in_code_block:
            return "code_content"
        if line.startswith('#'):
            return "heading"
        if line.startswith('- ') or line.startswith('* '):
            return "bullet"
        if re.match(r'^\d+\.\s', line):
            return "numbered"
        if line.startswith('|'):
            return "table"
        
        return "paragraph"
    
    def _flush_buffer(self, buffer: str) -> None:
        """刷新缓冲区（分句输出）"""
        sentences = self.tokenizer.split(buffer.strip(), OutputMode.SENTENCE)
        
        for sentence in sentences:
            if self.state.is_cancelled:
                break
            
            while self.state.is_paused:
                time.sleep(0.05)
            
            self._output_chunk(sentence, "text")
            
            # 句子间暂停
            if self.config.mode != OutputMode.INSTANT:
                delay = self.tokenizer.calculate_pause(sentence)
                time.sleep(delay)
    
    def _output_chunk(self, content: str, chunk_type: str) -> None:
        """输出块"""
        if not content:
            return
        
        chunk = OutputChunk(
            content=content,
            chunk_type=chunk_type,
            metadata={"lang": self._current_lang} if chunk_type == "code_content" else {},
        )
        
        self.sink.write(chunk)
        self.sink.flush()
        self.state.output_chars += len(content)
        
        if self.on_chunk:
            self.on_chunk(chunk)
        if self.on_progress:
            self.on_progress(self.state)


# =============================================================================
# LLM 流式输出适配器
# =============================================================================

class LLMStreamAdapter:
    """
    LLM 流式输出适配器
    
    将 LLM 的 token 流适配为统一的流式输出格式
    """
    
    def __init__(
        self,
        streaming_output: Optional[StreamingOutput] = None,
        config: Optional[StreamingConfig] = None,
    ):
        self.streaming = streaming_output or StreamingOutput(config)
        self._buffer = ""
        self._pending_text = ""
    
    def process_token(self, token: str) -> Optional[str]:
        """
        处理单个 token
        
        Args:
            token: LLM 输出的 token
        
        Returns:
            可显示的文本（如果累积到一个可显示单位）
        """
        self._pending_text += token
        
        # 智能累积：根据 token 类型决定输出时机
        displayable = None
        
        # 标点触发输出
        if token in '。！？；\n':
            displayable = self._pending_text
            self._pending_text = ""
        
        # 一定长度后输出（防止长 token 卡顿）
        elif len(self._pending_text) >= 10:
            # 找最后一个空格或标点
            for i in range(len(self._pending_text) - 1, -1, -1):
                if self._pending_text[i] in ' \t\n.,!?;':
                    displayable = self._pending_text[:i + 1]
                    self._pending_text = self._pending_text[i + 1:]
                    break
        
        if displayable:
            self.streaming.sink.write(OutputChunk(content=displayable))
            return displayable
        
        return None
    
    def flush(self) -> str:
        """强制刷新缓冲区"""
        result = self._pending_text
        if result:
            self.streaming.sink.write(OutputChunk(content=result))
        self._pending_text = ""
        return result


# =============================================================================
# 便捷函数
# =============================================================================

def typewriter_effect(
    text: str,
    speed: OutputSpeed = OutputSpeed.NORMAL,
    on_char: Optional[Callable[[str], None]] = None,
) -> str:
    """
    快捷打字机效果函数
    
    Args:
        text: 要输出的文本
        speed: 输出速度
        on_char: 字符回调
    
    Returns:
        完整文本
    """
    config = StreamingConfig(mode=OutputMode.TYPEWRITER, speed=speed)
    output = EnhancedStreamingOutput(config)
    
    if on_char:
        output.on_chunk = lambda c: on_char(c.content)
    
    return output.stream_sync(text)


def stream_markdown(
    markdown_text: str,
    speed: OutputSpeed = OutputSpeed.NORMAL,
    on_chunk: Optional[Callable[[OutputChunk], None]] = None,
) -> str:
    """
    快捷 Markdown 流式输出函数
    
    Args:
        markdown_text: Markdown 文本
        speed: 输出速度
        on_chunk: 块回调
    
    Returns:
        完整文本
    """
    config = StreamingConfig(mode=OutputMode.SENTENCE, speed=speed)
    output = EnhancedStreamingOutput(config)
    
    if on_chunk:
        output.on_chunk = on_chunk
    
    return output.stream_markdown_sync(markdown_text)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    logger.info("=== 测试流式输出系统 ===\n")
    
    # 测试 1：基础打字机效果
    logger.info("1. 基础打字机效果:")
    output = StreamingOutput()
    output.set_speed(OutputSpeed.FAST)
    result = output.stream_sync("你好，这是一段测试文本。")
    logger.info(f"\n结果: {result}\n")
    
    # 测试 2：Markdown 流式输出
    logger.info("2. Markdown 流式输出:")
    markdown = """# 标题
这是一个**加粗**文本。

```python
def hello():
    logger.info("Hello!")
```

- 列表项 1
- 列表项 2

> 引用文本
"""
    output2 = EnhancedStreamingOutput()
    output2.set_speed(OutputSpeed.FAST)
    result2 = output2.stream_markdown_sync(markdown)
    logger.info(f"\n结果:\n{result2}")
