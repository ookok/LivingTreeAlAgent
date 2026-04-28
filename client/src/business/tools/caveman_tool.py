"""
CavemanTool - LLM 输出 token 压缩工具

参考 caveman 项目（https://github.com/JuliusBrussee/caveman）：
- LLM 输出 token 压缩，节省约 75% token 消耗
- 四级压缩模式：Lite / Full / Ultra / 文言文（趣味模式）

集成方案：
1. 通过 subprocess 调用 caveman CLI
2. 支持配置压缩级别
3. 提供智能体原生调用接口

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import subprocess
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum

from client.src.business.tools.base_tool import BaseTool


class CompressionLevel(Enum):
    """压缩级别"""
    LITE = "lite"           # 轻度压缩
    FULL = "full"           # 完全压缩（默认）
    ULTRA = "ultra"         # 极致压缩
    WENYAN = "wenyan"       # 文言文模式（趣味模式）


@dataclass
class CavemanResult:
    """caveman 压缩结果"""
    success: bool
    compressed_text: str = ""
    original_length: int = 0
    compressed_length: int = 0
    compression_ratio: float = 0.0
    level: str = "full"
    error_message: str = ""


class CavemanTool(BaseTool):
    """
    LLM 输出 token 压缩工具
    
    功能：
    1. 对 LLM 输出进行 token 压缩，节省约 75% token 消耗
    2. 支持四种压缩级别：Lite / Full / Ultra / 文言文
    3. 通过 subprocess 调用 caveman CLI
    4. 提供智能体原生调用接口
    
    使用方式：
        tool = CavemanTool()
        result = await tool.execute(text="需要压缩的文本", level="full")
    """
    
    def __init__(self):
        super().__init__()
        self._logger = logger.bind(component="CavemanTool")
        self._caveman_available = self._check_caveman_availability()
        self._default_level = CompressionLevel.FULL
    
    @property
    def name(self) -> str:
        return "caveman_compress"
    
    @property
    def description(self) -> str:
        return "LLM 输出 token 压缩工具，支持四级压缩模式（Lite/Full/Ultra/文言文），可节省约 75% token 消耗"
    
    @property
    def category(self) -> str:
        return "utility"
    
    @property
    def node_type(self) -> str:
        return "deterministic"  # 确定性工具
    
    def _check_caveman_availability(self) -> bool:
        """检查 caveman 是否可用"""
        try:
            result = subprocess.run(
                ["caveman", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self._logger.info(f"caveman 可用，版本: {result.stdout.strip()}")
                return True
            else:
                self._logger.warning(f"caveman 返回错误: {result.stderr}")
                return False
        except FileNotFoundError:
            self._logger.warning("caveman 未安装，请运行: pip install caveman")
            return False
        except Exception as e:
            self._logger.error(f"检查 caveman 可用性失败: {e}")
            return False
    
    def is_available(self) -> bool:
        """检查工具是否可用"""
        return self._caveman_available
    
    async def execute(self, text: str, level: str = "full", **kwargs) -> Dict[str, Any]:
        """
        执行压缩
        
        Args:
            text: 需要压缩的文本
            level: 压缩级别（lite/full/ultra/wenyan）
            
        Returns:
            压缩结果
        """
        if not self._caveman_available:
            return {
                "success": False,
                "message": "caveman 不可用，请先安装",
                "compressed_text": text,
                "original_length": len(text),
                "compressed_length": len(text),
                "compression_ratio": 0.0
            }
        
        if not text:
            return {
                "success": True,
                "message": "空文本无需压缩",
                "compressed_text": "",
                "original_length": 0,
                "compressed_length": 0,
                "compression_ratio": 0.0
            }
        
        try:
            # 验证压缩级别
            try:
                compression_level = CompressionLevel(level.lower())
            except ValueError:
                self._logger.warning(f"无效的压缩级别: {level}，使用默认级别")
                compression_level = self._default_level
            
            # 调用 caveman CLI
            result = subprocess.run(
                ["caveman", f"--{compression_level.value}"],
                input=text,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                compressed_text = result.stdout.strip()
                original_length = len(text)
                compressed_length = len(compressed_text)
                compression_ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0
                
                self._logger.debug(
                    f"压缩成功: {original_length} -> {compressed_length} "
                    f"({compression_ratio:.1%} 压缩率)"
                )
                
                return {
                    "success": True,
                    "message": "压缩成功",
                    "compressed_text": compressed_text,
                    "original_length": original_length,
                    "compressed_length": compressed_length,
                    "compression_ratio": compression_ratio,
                    "level": compression_level.value
                }
            else:
                self._logger.error(f"caveman 压缩失败: {result.stderr}")
                return {
                    "success": False,
                    "message": f"压缩失败: {result.stderr}",
                    "compressed_text": text,
                    "original_length": len(text),
                    "compressed_length": len(text),
                    "compression_ratio": 0.0,
                    "level": compression_level.value
                }
        
        except subprocess.TimeoutExpired:
            self._logger.error("caveman 压缩超时")
            return {
                "success": False,
                "message": "压缩超时",
                "compressed_text": text,
                "original_length": len(text),
                "compressed_length": len(text),
                "compression_ratio": 0.0,
                "level": level
            }
        except Exception as e:
            self._logger.error(f"压缩过程中发生错误: {e}")
            return {
                "success": False,
                "message": str(e),
                "compressed_text": text,
                "original_length": len(text),
                "compressed_length": len(text),
                "compression_ratio": 0.0,
                "level": level
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体调用信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": {
                "text": {
                    "type": "string",
                    "description": "需要压缩的文本内容",
                    "required": True
                },
                "level": {
                    "type": "string",
                    "description": "压缩级别：lite（轻度）/ full（完全，默认）/ ultra（极致）/ wenyan（文言文）",
                    "required": False,
                    "default": "full",
                    "enum": ["lite", "full", "ultra", "wenyan"]
                }
            },
            "examples": [
                {
                    "input": {"text": "这是一段需要压缩的文本内容，用于测试 caveman 的压缩效果。", "level": "full"},
                    "description": "压缩一段普通文本"
                },
                {
                    "input": {"text": "def hello_world():\n    print('Hello, World!')", "level": "ultra"},
                    "description": "极致压缩代码文本"
                }
            ]
        }


# 创建工具实例
caveman_tool = CavemanTool()


def get_caveman_tool() -> CavemanTool:
    """获取 caveman 工具实例"""
    return caveman_tool


# 测试函数
async def test_caveman_tool():
    """测试 caveman 工具"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 CavemanTool")
    print("=" * 60)
    
    tool = CavemanTool()
    print(f"\ncaveman 可用: {'✓' if tool.is_available() else '✗'}")
    
    if tool.is_available():
        # 测试文本
        test_text = """
这是一段用于测试的文本内容，包含多个段落和不同类型的内容。

第一段落：介绍 caveman 工具的功能和用途。
caveman 是一个强大的 LLM 输出压缩工具，可以将输出 token 减少约 75%。

第二段落：测试不同压缩级别的效果。
支持四种压缩级别：Lite、Full、Ultra 和文言文模式。

第三段落：代码示例。
def hello_world():
    print("Hello, World!")
    return True

这是最后一段，用于测试压缩效果。
        """.strip()
        
        print(f"\n原始文本长度: {len(test_text)} 字符")
        
        # 测试不同压缩级别
        for level in ["lite", "full", "ultra", "wenyan"]:
            print(f"\n--- 测试 {level} 级别 ---")
            result = await tool.execute(text=test_text, level=level)
            
            if result["success"]:
                ratio = result["compression_ratio"]
                print(f"压缩率: {ratio:.1%}")
                print(f"压缩后长度: {result['compressed_length']} 字符")
                print(f"压缩后内容:\n{result['compressed_text'][:200]}...")
            else:
                print(f"压缩失败: {result['message']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_caveman_tool())