"""
压缩工具深度集成模块

提供多层级的信息压缩与优化方案：
1. 传输层压缩 - P2P网络传输优化
2. 模型响应压缩 - LLM输出自动压缩
3. 上下文压缩 - 对话历史智能压缩
4. 智能压缩策略 - 基于内容类型自适应
5. 高级压缩 - 领域自适应、知识蒸馏、增量压缩

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import json
import zlib
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False
    logger.warning("lz4 模块不可用，将使用 zlib 作为后备")

from business.tools.caveman_tool import get_caveman_tool, CompressionLevel
from business.advanced_compression import (
    get_advanced_compressor,
    CompressionAlgorithm,
    DomainType
)


class CompressionStrategy(Enum):
    """压缩策略"""
    NONE = "none"
    LITE = "lite"
    FULL = "full"
    ULTRA = "ultra"
    WENYAN = "wenyan"
    ADAPTIVE = "adaptive"  # 自适应策略
    DOMAIN = "domain"      # 领域自适应
    KNOWLEDGE = "knowledge"  # 知识蒸馏
    INCREMENTAL = "incremental"  # 增量压缩
    HYBRID = "hybrid"      # 混合策略


class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    CODE = "code"
    JSON = "json"
    MARKDOWN = "markdown"
    LOG = "log"
    BINARY = "binary"


@dataclass
class CompressionResult:
    """压缩结果"""
    success: bool
    data: bytes
    original_size: int
    compressed_size: int
    strategy: str
    content_type: str
    encoding: str = "lz4"


@dataclass
class CompressionStats:
    """压缩统计"""
    total_compressed: int = 0
    total_original_size: int = 0
    total_compressed_size: int = 0
    compression_ratio: float = 0.0

    def update(self, original_size: int, compressed_size: int):
        self.total_compressed += 1
        self.total_original_size += original_size
        self.total_compressed_size += compressed_size
        if self.total_original_size > 0:
            self.compression_ratio = 1 - (self.total_compressed_size / self.total_original_size)


class CompressionIntegration:
    """
    压缩工具深度集成管理器
    
    提供多层级信息传递优化：
    - 传输层：网络传输前压缩
    - 应用层：LLM响应自动压缩
    - 缓存层：压缩后缓存存储
    - 上下文层：对话历史智能压缩
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._logger = logger.bind(component="CompressionIntegration")
        self._caveman = get_caveman_tool()
        self._advanced = get_advanced_compressor()
        self._stats = CompressionStats()
        self._content_type_rules = {
            ContentType.CODE: CompressionStrategy.LITE,
            ContentType.JSON: CompressionStrategy.FULL,
            ContentType.TEXT: CompressionStrategy.ADAPTIVE,
            ContentType.MARKDOWN: CompressionStrategy.FULL,
            ContentType.LOG: CompressionStrategy.ULTRA,
            ContentType.BINARY: CompressionStrategy.NONE,
        }
        self._previous_text = ""
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> "CompressionIntegration":
        return cls()
    
    def _detect_content_type(self, data: str) -> ContentType:
        """检测内容类型"""
        data = data.strip()
        
        if data.startswith("{") and data.endswith("}"):
            try:
                json.loads(data)
                return ContentType.JSON
            except:
                pass
        
        if any(line.startswith("```") for line in data.split('\n')):
            return ContentType.CODE
        
        if any(line.startswith("# ") for line in data.split('\n')):
            return ContentType.MARKDOWN
        
        if any(keyword in data.lower() for keyword in ["error", "warning", "info", "debug"]):
            return ContentType.LOG
        
        return ContentType.TEXT
    
    def _select_strategy(self, data: str) -> CompressionStrategy:
        """根据内容类型选择压缩策略"""
        content_type = self._detect_content_type(data)
        strategy = self._content_type_rules.get(content_type, CompressionStrategy.FULL)
        
        if strategy == CompressionStrategy.ADAPTIVE:
            return self._adaptive_strategy(data)
        
        return strategy
    
    def _adaptive_strategy(self, data: str) -> CompressionStrategy:
        """自适应策略：根据内容特征选择最佳压缩级别"""
        length = len(data)
        
        if length < 100:
            return CompressionStrategy.LITE
        
        if any(keyword in data.lower() for keyword in ["代码", "code", "function", "def", "class"]):
            return CompressionStrategy.LITE
        
        if any(keyword in data.lower() for keyword in ["解释", "说明", "分析", "建议", "总结"]):
            return CompressionStrategy.FULL
        
        if length > 1000:
            return CompressionStrategy.ULTRA
        
        return CompressionStrategy.FULL
    
    async def compress_text(self, text: str, strategy: Optional[CompressionStrategy] = None) -> Dict[str, Any]:
        """
        文本压缩（支持多种策略）
        
        Args:
            text: 原始文本
            strategy: 压缩策略（None表示自动选择）
        
        Returns:
            压缩结果
        """
        if not text:
            return {"success": True, "compressed_text": "", "original_length": 0, "compressed_length": 0, "ratio": 0.0}
        
        if strategy is None:
            strategy = self._select_strategy(text)
        
        if strategy == CompressionStrategy.NONE:
            return {
                "success": True,
                "compressed_text": text,
                "original_length": len(text),
                "compressed_length": len(text),
                "ratio": 0.0,
                "strategy": strategy.value
            }
        
        if strategy in [CompressionStrategy.DOMAIN, CompressionStrategy.KNOWLEDGE, 
                        CompressionStrategy.INCREMENTAL, CompressionStrategy.HYBRID]:
            return await self._compress_advanced(text, strategy)
        
        level = strategy.value
        result = await self._caveman.execute(text, level=level)
        
        if result.get("success"):
            self._stats.update(result["original_length"], result["compressed_length"])
        
        return result
    
    async def _compress_advanced(self, text: str, strategy: CompressionStrategy) -> Dict[str, Any]:
        """
        使用高级压缩器进行压缩
        
        Args:
            text: 原始文本
            strategy: 压缩策略
        
        Returns:
            压缩结果
        """
        algorithm_map = {
            CompressionStrategy.DOMAIN: CompressionAlgorithm.DOMAIN_ADAPTIVE,
            CompressionStrategy.KNOWLEDGE: CompressionAlgorithm.KNOWLEDGE_DISTILLATION,
            CompressionStrategy.INCREMENTAL: CompressionAlgorithm.INCREMENTAL,
            CompressionStrategy.HYBRID: CompressionAlgorithm.HYBRID,
        }
        
        algorithm = algorithm_map.get(strategy, CompressionAlgorithm.HYBRID)
        
        result = await self._advanced.compress(
            text, 
            mode=algorithm,
            previous_text=self._previous_text
        )
        
        if result.get("success"):
            self._stats.update(result["original_length"], result["compressed_length"])
            self._previous_text = text
        
        return {
            "success": result["success"],
            "compressed_text": result["compressed_text"],
            "original_length": result["original_length"],
            "compressed_length": result["compressed_length"],
            "ratio": result["ratio"],
            "strategy": strategy.value,
            "mode": result["mode"],
            "domain": result.get("domain"),
            "compression_info": result.get("compression_info")
        }
    
    def compress_binary(self, data: bytes, method: str = "lz4") -> CompressionResult:
        """
        二进制数据压缩（使用 LZ4 或 zlib）
        
        Args:
            data: 原始数据
            method: 压缩方法（lz4/zlib）
        
        Returns:
            CompressionResult
        """
        if not data:
            return CompressionResult(
                success=True,
                data=b"",
                original_size=0,
                compressed_size=0,
                strategy="none",
                content_type="binary"
            )
        
        try:
            if method == "lz4" and LZ4_AVAILABLE:
                compressed = lz4.frame.compress(data)
            else:
                compressed = zlib.compress(data)
                method = "zlib"
            
            self._stats.update(len(data), len(compressed))
            
            return CompressionResult(
                success=True,
                data=compressed,
                original_size=len(data),
                compressed_size=len(compressed),
                strategy=method,
                content_type="binary",
                encoding=method
            )
        except Exception as e:
            self._logger.error(f"二进制压缩失败: {e}")
            return CompressionResult(
                success=False,
                data=data,
                original_size=len(data),
                compressed_size=len(data),
                strategy="none",
                content_type="binary"
            )
    
    def decompress_binary(self, data: bytes, encoding: str = "lz4") -> bytes:
        """
        解压二进制数据
        
        Args:
            data: 压缩数据
            encoding: 编码方式
        
        Returns:
            解压后的数据
        """
        if not data:
            return b""
        
        try:
            if encoding == "lz4" and LZ4_AVAILABLE:
                return lz4.frame.decompress(data)
            else:
                return zlib.decompress(data)
        except Exception as e:
            self._logger.error(f"二进制解压失败: {e}")
            return data
    
    async def compress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        压缩消息（完整消息结构）
        
        Args:
            message: 原始消息字典
        
        Returns:
            压缩后的消息
        """
        compressed_msg = {**message}
        
        if "content" in message and isinstance(message["content"], str):
            text_result = await self.compress_text(message["content"])
            compressed_msg["content"] = text_result["compressed_text"]
            compressed_msg["compression"] = {
                "type": "caveman",
                "level": text_result.get("level", "full"),
                "original_length": text_result["original_length"],
                "compressed_length": text_result["compressed_length"],
                "ratio": text_result["compression_ratio"]
            }
        
        return compressed_msg
    
    async def decompress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        解压消息
        
        Args:
            message: 压缩消息
        
        Returns:
            原始消息
        """
        decompressed_msg = {**message}
        
        if "compression" in message and message["compression"].get("type") == "caveman":
            decompressed_msg["content"] = message.get("content", "")
        
        return decompressed_msg
    
    async def compress_context(self, messages: List[Dict], max_tokens: int = 4096) -> List[Dict]:
        """
        智能压缩对话上下文
        
        策略：
        1. 对非关键消息进行压缩
        2. 保持最新消息完整
        3. 根据token限制进行裁剪
        
        Args:
            messages: 消息列表
            max_tokens: 最大token数
        
        Returns:
            压缩后的消息列表
        """
        if not messages:
            return []
        
        compressed = []
        total_tokens = 0
        
        for i, msg in enumerate(reversed(messages)):
            content = msg.get("content", "")
            tokens = len(content) // 4
            
            if i < 3:
                compressed.insert(0, msg)
                total_tokens += tokens
            else:
                if total_tokens < max_tokens:
                    text_result = await self.compress_text(content, strategy=CompressionStrategy.FULL)
                    compressed.insert(0, {
                        **msg,
                        "content": text_result["compressed_text"],
                        "compressed": True
                    })
                    total_tokens += len(text_result["compressed_text"]) // 4
                else:
                    break
        
        return compressed
    
    async def wrap_p2p_message(self, data: Any, message_type: str) -> bytes:
        """
        封装P2P消息（自动选择最佳压缩方式）
        
        Args:
            data: 消息数据
            message_type: 消息类型
        
        Returns:
            封装后的二进制消息
        """
        try:
            serialized = json.dumps(data).encode('utf-8')
            
            content_type = self._detect_content_type(json.dumps(data))
            strategy = self._content_type_rules.get(content_type, CompressionStrategy.FULL)
            
            if strategy != CompressionStrategy.NONE:
                text_result = await self.compress_text(json.dumps(data))
                compressed_data = json.dumps({
                    "original": data,
                    "compression_info": {
                        "level": text_result.get("level"),
                        "ratio": text_result.get("compression_ratio")
                    }
                }).encode('utf-8')
                
                result = self.compress_binary(compressed_data)
            else:
                result = self.compress_binary(serialized)
            
            wrapper = {
                "type": message_type,
                "encoding": result.encoding,
                "strategy": result.strategy,
                "content_type": content_type.value,
                "data": result.data.hex(),
                "original_size": result.original_size,
                "compressed_size": result.compressed_size
            }
            
            return json.dumps(wrapper).encode('utf-8')
        
        except Exception as e:
            self._logger.error(f"P2P消息封装失败: {e}")
            return json.dumps({
                "type": message_type,
                "data": json.dumps(data)
            }).encode('utf-8')
    
    async def unwrap_p2p_message(self, wrapped_data: bytes) -> Tuple[Any, Dict]:
        """
        解包P2P消息
        
        Args:
            wrapped_data: 封装后的二进制消息
        
        Returns:
            (原始数据, 元数据)
        """
        try:
            wrapper = json.loads(wrapped_data.decode('utf-8'))
            
            if "data" in wrapper:
                if wrapper.get("encoding"):
                    compressed_data = bytes.fromhex(wrapper["data"])
                    decompressed = self.decompress_binary(compressed_data, wrapper["encoding"])
                    content = json.loads(decompressed.decode('utf-8'))
                    
                    if "original" in content:
                        return content["original"], {
                            "strategy": wrapper.get("strategy"),
                            "compression_ratio": 1 - (wrapper["compressed_size"] / wrapper["original_size"]),
                            "content_type": wrapper.get("content_type")
                        }
                    return content, {}
                else:
                    return json.loads(wrapper["data"]), {}
            
            return wrapper, {}
        
        except Exception as e:
            self._logger.error(f"P2P消息解包失败: {e}")
            return wrapped_data, {}
    
    def get_stats(self) -> CompressionStats:
        """获取压缩统计"""
        return self._stats
    
    def reset_stats(self):
        """重置统计"""
        self._stats = CompressionStats()


# 全局实例
_compression_integration = CompressionIntegration()


def get_compression_integration() -> CompressionIntegration:
    """获取压缩集成管理器实例"""
    return _compression_integration


# ========== 便捷装饰器 ==========

def compress_response(func: Callable) -> Callable:
    """
    装饰器：自动压缩函数返回的文本响应
    
    使用示例：
        @compress_response
        async def generate_response(prompt: str) -> str:
            return await llm.generate(prompt)
    """
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        
        if isinstance(result, str):
            compression = get_compression_integration()
            compressed = await compression.compress_text(result)
            return compressed.get("compressed_text", result)
        
        if isinstance(result, dict) and "content" in result:
            compression = get_compression_integration()
            compressed = await compression.compress_text(result["content"])
            result["content"] = compressed.get("compressed_text", result["content"])
            result["compression_info"] = {
                "ratio": compressed.get("compression_ratio", 0),
                "level": compressed.get("level", "full")
            }
        
        return result
    
    return wrapper


def compress_p2p(func: Callable) -> Callable:
    """
    装饰器：自动压缩P2P消息
    
    使用示例：
        @compress_p2p
        async def send_message(node_id: str, message: Dict):
            return await p2p.send(node_id, message)
    """
    async def wrapper(*args, **kwargs):
        message = args[-1] if args else kwargs.get('message')
        
        if message and isinstance(message, dict):
            compression = get_compression_integration()
            compressed_message = await compression.compress_message(message)
            args = list(args)
            args[-1] = compressed_message
            args = tuple(args)
        
        return await func(*args, **kwargs)
    
    return wrapper
