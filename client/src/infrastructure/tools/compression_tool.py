"""
压缩工具 - 系统工具注册

将压缩工具库注册为系统工具，供聊天面板和其他模块使用
"""

from typing import List, Dict, Optional, Union
from pathlib import Path
from loguru import logger

# 导入压缩工具库
from ..compression_utils import (
    CompressionUtils,
    PeaZipIntegration,
    compress,
    decompress,
    list_archive_contents
)


class CompressionTool:
    """
    压缩工具 - 系统工具封装
    
    提供压缩、解压、查看压缩包内容等功能
    """
    
    # 工具元数据
    NAME = "compression"
    DESCRIPTION = "压缩工具 - 支持多种压缩格式的压缩、解压和查看"
    DESCRIPTION_EN = "Compression Tool - Supports compression, decompression and viewing of various archive formats"
    
    # 支持的格式
    SUPPORTED_FORMATS = CompressionUtils.SUPPORTED_FORMATS
    
    @classmethod
    def get_tool_info(cls) -> Dict:
        """获取工具信息"""
        return {
            "name": cls.NAME,
            "description": cls.DESCRIPTION,
            "description_en": cls.DESCRIPTION_EN,
            "version": "1.0.0",
            "author": "LivingTreeAlAgent",
            "capabilities": [
                "compress",
                "decompress",
                "list_contents",
                "check_format",
                "is_encrypted",
                "get_compression_ratio"
            ],
            "supported_formats": cls.SUPPORTED_FORMATS
        }
    
    @classmethod
    def compress(
        cls,
        source_path: Union[str, Path],
        output_path: Union[str, Path],
        compression_format: str = "zip",
        password: str = None
    ) -> Dict:
        """
        压缩文件或目录
        
        Args:
            source_path: 源文件或目录路径
            output_path: 输出压缩文件路径
            compression_format: 压缩格式（默认 zip）
            password: 密码（仅 ZIP 支持）
        
        Returns:
            结果字典，包含 success、message、output_path 等字段
        """
        try:
            success = CompressionUtils.compress(source_path, output_path, compression_format, password)
            
            if success:
                return {
                    "success": True,
                    "message": f"压缩成功",
                    "message_en": "Compression successful",
                    "output_path": str(output_path),
                    "format": compression_format
                }
            else:
                return {
                    "success": False,
                    "message": f"压缩失败",
                    "message_en": "Compression failed",
                    "output_path": None,
                    "format": compression_format
                }
        except Exception as e:
            logger.error(f"压缩异常: {e}")
            return {
                "success": False,
                "message": f"压缩异常: {str(e)}",
                "message_en": f"Compression error: {str(e)}",
                "output_path": None,
                "format": compression_format
            }
    
    @classmethod
    def decompress(
        cls,
        source_path: Union[str, Path],
        output_dir: Union[str, Path],
        password: str = None
    ) -> Dict:
        """
        解压文件
        
        Args:
            source_path: 压缩文件路径
            output_dir: 输出目录
            password: 密码
        
        Returns:
            结果字典，包含 success、message、output_dir 等字段
        """
        try:
            success = CompressionUtils.decompress(source_path, output_dir, password)
            
            if success:
                return {
                    "success": True,
                    "message": f"解压成功",
                    "message_en": "Decompression successful",
                    "output_dir": str(output_dir),
                    "files": cls.list_contents(source_path, password)
                }
            else:
                return {
                    "success": False,
                    "message": f"解压失败",
                    "message_en": "Decompression failed",
                    "output_dir": None,
                    "files": None
                }
        except Exception as e:
            logger.error(f"解压异常: {e}")
            return {
                "success": False,
                "message": f"解压异常: {str(e)}",
                "message_en": f"Decompression error: {str(e)}",
                "output_dir": None,
                "files": None
            }
    
    @classmethod
    def list_contents(cls, source_path: Union[str, Path], password: str = None) -> List[Dict]:
        """
        查看压缩包内容
        
        Args:
            source_path: 压缩文件路径
            password: 密码
        
        Returns:
            文件列表
        """
        return CompressionUtils.list_contents(source_path, password)
    
    @classmethod
    def check_format(cls, file_path: Union[str, Path]) -> Dict:
        """
        检查文件格式
        
        Args:
            file_path: 文件路径
        
        Returns:
            格式信息字典
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {
                "exists": False,
                "format": None,
                "supported": False,
                "message": "文件不存在"
            }
        
        suffix = file_path.suffix.lower()
        
        for format_name, info in cls.SUPPORTED_FORMATS.items():
            if suffix == info["ext"]:
                return {
                    "exists": True,
                    "format": format_name,
                    "description": info["description"],
                    "supported": True,
                    "can_compress": info.get("can_compress", False),
                    "can_decompress": info.get("can_decompress", False)
                }
        
        return {
            "exists": True,
            "format": None,
            "supported": False,
            "message": "不支持的格式"
        }
    
    @classmethod
    def is_encrypted(cls, source_path: Union[str, Path]) -> bool:
        """
        检查压缩文件是否加密
        
        Args:
            source_path: 压缩文件路径
        
        Returns:
            是否加密
        """
        return CompressionUtils.is_encrypted(source_path)
    
    @classmethod
    def get_compression_ratio(cls, source_path: Union[str, Path], original_size: int = None) -> float:
        """
        计算压缩率
        
        Args:
            source_path: 压缩文件路径
            original_size: 原始大小
        
        Returns:
            压缩率
        """
        return CompressionUtils.get_compression_ratio(source_path, original_size)
    
    @classmethod
    def is_peazip_available(cls) -> bool:
        """检查 PeaZip 是否可用"""
        return PeaZipIntegration.is_peazip_available()


# 工具注册函数
def register_compression_tool():
    """注册压缩工具到系统工具注册表"""
    try:
        from client.src.business.tools.tool_registry import ToolRegistry, ToolDefinition
        
        tool_info = CompressionTool.get_tool_info()
        
        # 创建工具定义
        tool_def = ToolDefinition(
            name=tool_info["name"],
            description=tool_info["description"],
            handler=CompressionTool,
            parameters={
                "compress": "source_path, output_path, compression_format='zip', password=None",
                "decompress": "source_path, output_dir, password=None",
                "list_contents": "source_path, password=None",
                "check_format": "file_path",
                "is_encrypted": "source_path",
                "get_compression_ratio": "source_path, original_size=None"
            },
            returns="Dict[str, Any]",
            category="compression",
            version=tool_info["version"],
            author=tool_info["author"]
        )
        
        # 注册工具
        registry = ToolRegistry.get_instance()
        registry.register(tool_def)
        
        logger.info(f"压缩工具已注册: {tool_info['name']}")
        return True
    except Exception as e:
        logger.warning(f"压缩工具注册失败: {e}")
        return False


# 快捷函数
def get_compression_tool() -> CompressionTool:
    """获取压缩工具实例"""
    return CompressionTool()


# 自动注册
register_compression_tool()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("压缩工具测试")
    print("=" * 60)
    
    tool = CompressionTool()
    
    # 获取工具信息
    info = tool.get_tool_info()
    print(f"工具名称: {info['name']}")
    print(f"工具描述: {info['description']}")
    print(f"支持格式: {list(info['supported_formats'].keys())}")
    print(f"PeaZip 可用: {'是' if tool.is_peazip_available() else '否'}")
    
    # 检查格式
    format_info = tool.check_format("test.zip")
    print(f"\n格式检查 (test.zip): {format_info}")
    
    print("\n" + "=" * 60)