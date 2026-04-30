"""
Token压缩器 (Token Compressor)
=============================

集成 Caveman 功能，实现：
1. 输出压缩 - 将LLM输出压缩75%同时保留技术准确性
2. 多语言支持 - 支持中文、英文、文言文等多种模式
3. 多级压缩 - 支持Lite/Full/Ultra/文言文四种压缩级别
4. 技术文档优化 - 特别优化技术文档的压缩

核心特性：
- 支持多种压缩级别
- 保留技术准确性
- 支持多种语言模式
- 可通过CLI或API调用

参考项目：https://github.com/JuliusBrussee/caveman

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import subprocess
import json
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class CompressionLevel(Enum):
    """压缩级别"""
    LITE = "lite"           # 轻量级压缩（保留大部分格式）
    FULL = "full"           # 完全压缩（标准）
    ULTRA = "ultra"         # 超压缩（激进）
    CLASSICAL = "classical" # 文言文模式（实验性）


class CompressionMode(Enum):
    """压缩模式"""
    CLI = "cli"             # 通过Caveman CLI调用
    API = "api"             # 通过API调用
    INTERNAL = "internal"   # 内部算法（默认，无需外部依赖）


@dataclass
class CompressionResult:
    """压缩结果"""
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    level: CompressionLevel
    mode: CompressionMode
    execution_time: float


class TokenCompressor:
    """
    Token压缩器
    
    核心功能：
    1. 输出压缩 - 将LLM输出压缩75%同时保留技术准确性
    2. 多语言支持 - 支持中文、英文、文言文等多种模式
    3. 多级压缩 - 支持Lite/Full/Ultra/文言文四种压缩级别
    4. 技术文档优化 - 特别优化技术文档的压缩
    
    参考项目：https://github.com/JuliusBrussee/caveman
    
    Caveman CLI安装：npx skills add JuliusBrussee/caveman
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 配置参数
        self._config = {
            "default_level": "full",
            "default_mode": "internal",
            "caveman_path": "caveman",  # Caveman CLI路径
            "enabled": True,
        }
        
        # LLM调用函数（用于内部压缩）
        self._llm_callable = None
        
        # Caveman可用性缓存
        self._caveman_available = None
        
        self._initialized = True
        logger.info("[TokenCompressor] Token压缩器初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置LLM调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置压缩器"""
        self._config.update(kwargs)
        logger.info(f"[TokenCompressor] 配置更新: {kwargs}")
    
    def compress(self, text: str, level: CompressionLevel = None, 
                 mode: CompressionMode = None) -> CompressionResult:
        """
        压缩文本
        
        Args:
            text: 原始文本
            level: 压缩级别（可选）
            mode: 压缩模式（可选）
            
        Returns:
            CompressionResult: 压缩结果
        """
        start_time = time.time()
        
        level = level or CompressionLevel(self._config["default_level"])
        mode = mode or CompressionMode(self._config["default_mode"])
        
        # 计算原始Token数
        original_tokens = self._count_tokens(text)
        
        # 如果文本太短，直接返回
        if original_tokens < 50:
            return CompressionResult(
                compressed_text=text,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                level=level,
                mode=mode,
                execution_time=time.time() - start_time
            )
        
        # 根据模式执行压缩
        compressed_text = text
        if mode == CompressionMode.CLI:
            compressed_text = self._compress_with_caveman_cli(text, level)
        elif mode == CompressionMode.API:
            compressed_text = self._compress_with_api(text, level)
        else:
            compressed_text = self._compress_internal(text, level)
        
        # 计算压缩后的Token数
        compressed_tokens = self._count_tokens(compressed_text)
        
        return CompressionResult(
            compressed_text=compressed_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            level=level,
            mode=mode,
            execution_time=time.time() - start_time
        )
    
    def _count_tokens(self, text: str) -> int:
        """估算Token数"""
        if not text:
            return 0
        
        english_words = len([w for w in text.split() if w.isalpha()])
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        
        return english_words + int(chinese_chars * 0.5)
    
    def _compress_with_caveman_cli(self, text: str, level: CompressionLevel) -> str:
        """通过Caveman CLI进行压缩"""
        if not self._is_caveman_available():
            logger.warning("[TokenCompressor] Caveman CLI不可用，回退到内部压缩")
            return self._compress_internal(text, level)
        
        try:
            level_arg = {
                CompressionLevel.LITE: "--lite",
                CompressionLevel.FULL: "--full",
                CompressionLevel.ULTRA: "--ultra",
                CompressionLevel.CLASSICAL: "--classical",
            }.get(level, "--full")
            
            result = subprocess.run(
                [self._config["caveman_path"], level_arg],
                input=text,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"[TokenCompressor] Caveman CLI调用失败: {result.stderr}")
                return text
                
        except Exception as e:
            logger.error(f"[TokenCompressor] Caveman CLI调用异常: {e}")
            return text
    
    def _compress_with_api(self, text: str, level: CompressionLevel) -> str:
        """通过API进行压缩（预留接口）"""
        logger.warning("[TokenCompressor] API模式尚未实现，回退到内部压缩")
        return self._compress_internal(text, level)
    
    def _compress_internal(self, text: str, level: CompressionLevel) -> str:
        """内部压缩算法"""
        if not self._llm_callable:
            # 使用简单规则压缩
            return self._simple_compress(text, level)
        
        try:
            # 使用LLM进行智能压缩
            prompt = self._build_compression_prompt(text, level)
            response = self._llm_callable(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"[TokenCompressor] LLM压缩失败: {e}")
            return self._simple_compress(text, level)
    
    def _simple_compress(self, text: str, level: CompressionLevel) -> str:
        """简单规则压缩"""
        result = text
        
        # 基础压缩：去除多余空格和换行
        result = ' '.join(result.split())
        
        # 根据级别应用不同的压缩强度
        if level in [CompressionLevel.FULL, CompressionLevel.ULTRA]:
            # 移除多余的标点
            result = self._remove_extra_punctuation(result)
            
        if level in [CompressionLevel.ULTRA, CompressionLevel.CLASSICAL]:
            # 移除冗余词
            result = self._remove_redundant_words(result)
            
        if level == CompressionLevel.CLASSICAL:
            # 文言文风格压缩（简化）
            result = self._classical_style(result)
        
        return result
    
    def _remove_extra_punctuation(self, text: str) -> str:
        """移除多余标点"""
        import re
        # 移除连续的标点
        text = re.sub(r'([，。！？、；：])\1+', r'\1', text)
        # 移除括号周围的空格
        text = re.sub(r'\s*([（）\(\)])\s*', r'\1', text)
        return text
    
    def _remove_redundant_words(self, text: str) -> str:
        """移除冗余词"""
        redundant_patterns = [
            (r'非常|十分|特别|极其|相当', ''),
            (r'基本上(来说)?|本质上(来说)?', ''),
            (r'也就是说|换句话说|即', ''),
            (r'的话', ''),
            (r'其实', ''),
            (r'实际上', ''),
        ]
        
        import re
        result = text
        for pattern, replacement in redundant_patterns:
            result = re.sub(pattern, replacement, result)
        
        return result
    
    def _classical_style(self, text: str) -> str:
        """文言文风格压缩（简化版本）"""
        replacements = [
            ('你', '汝'),
            ('我', '吾'),
            ('他', '其'),
            ('他们', '彼等'),
            ('的', '之'),
            ('是', '乃'),
            ('有', '有'),
            ('在', '于'),
            ('和', '与'),
            ('但是', '然'),
            ('因为', '因'),
            ('所以', '故'),
            ('可以', '可'),
            ('不能', '不可'),
            ('知道', '知'),
            ('说', '曰'),
            ('看', '视'),
            ('做', '为'),
        ]
        
        result = text
        for old, new in replacements:
            result = result.replace(old, new)
        
        return result
    
    def _build_compression_prompt(self, text: str, level: CompressionLevel) -> str:
        """构建压缩提示词"""
        level_descriptions = {
            CompressionLevel.LITE: "轻微压缩，保留格式和大部分细节",
            CompressionLevel.FULL: "中等压缩，保留关键信息",
            CompressionLevel.ULTRA: "深度压缩，只保留核心内容",
            CompressionLevel.CLASSICAL: "文言文风格压缩，简洁优雅",
        }
        
        return f"""请将以下文本进行{level_descriptions[level]}：

{text}

压缩要求：
1. 保留技术准确性
2. 保持语义完整
3. 去除冗余内容
4. 保持可读性

压缩后的文本："""
    
    def _is_caveman_available(self) -> bool:
        """检查Caveman CLI是否可用"""
        if self._caveman_available is not None:
            return self._caveman_available
        
        try:
            result = subprocess.run(
                [self._config["caveman_path"], "--version"],
                capture_output=True,
                text=True
            )
            self._caveman_available = result.returncode == 0
            return self._caveman_available
        except Exception:
            self._caveman_available = False
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "config": self._config,
            "caveman_available": self._is_caveman_available(),
        }


# 便捷函数
def get_token_compressor() -> TokenCompressor:
    """获取Token压缩器单例"""
    return TokenCompressor()


__all__ = [
    "CompressionLevel",
    "CompressionMode",
    "CompressionResult",
    "TokenCompressor",
    "get_token_compressor",
]