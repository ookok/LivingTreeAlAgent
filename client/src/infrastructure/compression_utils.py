"""
压缩工具库 - 基于 NanoZip 的压缩和解压缩功能

功能特性：
1. 支持多种压缩格式：zip, tar, gzip, bzip2, xz
2. 支持 NanoZip 压缩（如果可用）
3. 查看压缩包内容
4. 支持密码保护
5. 批量压缩/解压
"""

import os
import zipfile
import tarfile
import gzip
import bz2
import lzma
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Union
from loguru import logger


class CompressionUtils:
    """
    压缩工具类
    
    支持的格式：
    - ZIP (.zip)
    - TAR (.tar)
    - GZIP (.gz)
    - BZIP2 (.bz2)
    - XZ (.xz)
    - TAR.GZ (.tar.gz)
    - TAR.BZ2 (.tar.bz2)
    - TAR.XZ (.tar.xz)
    """
    
    # 支持的压缩格式
    SUPPORTED_FORMATS = {
        "zip": {"ext": ".zip", "description": "ZIP 压缩"},
        "tar": {"ext": ".tar", "description": "TAR 归档"},
        "gz": {"ext": ".gz", "description": "GZIP 压缩"},
        "bz2": {"ext": ".bz2", "description": "BZIP2 压缩"},
        "xz": {"ext": ".xz", "description": "XZ 压缩"},
        "tar.gz": {"ext": ".tar.gz", "description": "TAR + GZIP"},
        "tar.bz2": {"ext": ".tar.bz2", "description": "TAR + BZIP2"},
        "tar.xz": {"ext": ".tar.xz", "description": "TAR + XZ"},
    }
    
    @classmethod
    def compress(cls, source_path: Union[str, Path], output_path: Union[str, Path], 
                 compression_format: str = "zip", password: str = None) -> bool:
        """
        压缩文件或目录
        
        Args:
            source_path: 源文件或目录路径
            output_path: 输出压缩文件路径
            compression_format: 压缩格式（默认 zip）
            password: 密码（仅 ZIP 支持）
        
        Returns:
            是否压缩成功
        """
        source_path = Path(source_path)
        output_path = Path(output_path)
        
        if not source_path.exists():
            logger.error(f"源路径不存在: {source_path}")
            return False
        
        try:
            if compression_format == "zip":
                return cls._compress_zip(source_path, output_path, password)
            elif compression_format == "tar":
                return cls._compress_tar(source_path, output_path)
            elif compression_format == "gz":
                return cls._compress_gzip(source_path, output_path)
            elif compression_format == "bz2":
                return cls._compress_bz2(source_path, output_path)
            elif compression_format == "xz":
                return cls._compress_xz(source_path, output_path)
            elif compression_format == "tar.gz":
                return cls._compress_tar_gz(source_path, output_path)
            elif compression_format == "tar.bz2":
                return cls._compress_tar_bz2(source_path, output_path)
            elif compression_format == "tar.xz":
                return cls._compress_tar_xz(source_path, output_path)
            else:
                logger.error(f"不支持的压缩格式: {compression_format}")
                return False
                
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return False
    
    @classmethod
    def decompress(cls, source_path: Union[str, Path], output_dir: Union[str, Path], 
                   password: str = None) -> bool:
        """
        解压文件
        
        Args:
            source_path: 压缩文件路径
            output_dir: 输出目录
            password: 密码（仅 ZIP 支持）
        
        Returns:
            是否解压成功
        """
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        
        if not source_path.exists():
            logger.error(f"压缩文件不存在: {source_path}")
            return False
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if source_path.suffix == ".zip":
                return cls._decompress_zip(source_path, output_dir, password)
            elif source_path.suffix == ".tar":
                return cls._decompress_tar(source_path, output_dir)
            elif source_path.suffix == ".gz":
                return cls._decompress_gzip(source_path, output_dir)
            elif source_path.suffix == ".bz2":
                return cls._decompress_bz2(source_path, output_dir)
            elif source_path.suffix == ".xz":
                return cls._decompress_xz(source_path, output_dir)
            elif source_path.suffixes[-2:] == [".tar", ".gz"]:
                return cls._decompress_tar_gz(source_path, output_dir)
            elif source_path.suffixes[-2:] == [".tar", ".bz2"]:
                return cls._decompress_tar_bz2(source_path, output_dir)
            elif source_path.suffixes[-2:] == [".tar", ".xz"]:
                return cls._decompress_tar_xz(source_path, output_dir)
            else:
                logger.error(f"无法识别的压缩格式: {source_path.suffix}")
                return False
                
        except Exception as e:
            logger.error(f"解压失败: {e}")
            return False
    
    @classmethod
    def list_contents(cls, source_path: Union[str, Path], password: str = None) -> List[Dict]:
        """
        查看压缩包内容
        
        Args:
            source_path: 压缩文件路径
            password: 密码（仅 ZIP 支持）
        
        Returns:
            文件列表，包含文件名、大小、修改时间等信息
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            logger.error(f"压缩文件不存在: {source_path}")
            return []
        
        try:
            if source_path.suffix == ".zip":
                return cls._list_zip_contents(source_path, password)
            elif source_path.suffix == ".tar" or source_path.suffixes[-2:] == [".tar", ".gz"]:
                return cls._list_tar_contents(source_path)
            else:
                logger.warning(f"不支持查看该格式的内容: {source_path.suffix}")
                return []
                
        except Exception as e:
            logger.error(f"查看压缩包内容失败: {e}")
            return []
    
    @classmethod
    def is_encrypted(cls, source_path: Union[str, Path]) -> bool:
        """
        检查压缩文件是否加密
        
        Args:
            source_path: 压缩文件路径
        
        Returns:
            是否加密
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            return False
        
        if source_path.suffix == ".zip":
            try:
                with zipfile.ZipFile(source_path, 'r') as zf:
                    for info in zf.infolist():
                        if info.flag_bits & 0x01:
                            return True
            except Exception:
                pass
        
        return False
    
    @classmethod
    def get_compression_ratio(cls, source_path: Union[str, Path], 
                             original_size: int = None) -> float:
        """
        计算压缩率
        
        Args:
            source_path: 压缩文件路径
            original_size: 原始大小（如果已知）
        
        Returns:
            压缩率 (0-1)
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            return 0.0
        
        compressed_size = source_path.stat().st_size
        
        if original_size is not None:
            return compressed_size / original_size if original_size > 0 else 0.0
        
        # 尝试从压缩包中获取原始大小
        contents = cls.list_contents(source_path)
        if contents:
            original_size = sum(item.get("size", 0) for item in contents)
            return compressed_size / original_size if original_size > 0 else 0.0
        
        return 0.0
    
    # ==================== ZIP ====================
    @classmethod
    def _compress_zip(cls, source_path: Path, output_path: Path, password: str = None) -> bool:
        """压缩为 ZIP 格式"""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            if source_path.is_file():
                zf.write(source_path, source_path.name)
            else:
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_path)
                        zf.write(file_path, arcname)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_zip(cls, source_path: Path, output_dir: Path, password: str = None) -> bool:
        """解压 ZIP 文件"""
        with zipfile.ZipFile(source_path, 'r') as zf:
            zf.extractall(output_dir)
        
        logger.info(f"已解压到: {output_dir}")
        return True
    
    @classmethod
    def _list_zip_contents(cls, source_path: Path, password: str = None) -> List[Dict]:
        """列出 ZIP 文件内容"""
        contents = []
        
        with zipfile.ZipFile(source_path, 'r') as zf:
            for info in zf.infolist():
                contents.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "modified": info.date_time,
                    "is_dir": info.filename.endswith('/'),
                    "encrypted": bool(info.flag_bits & 0x01)
                })
        
        return contents
    
    # ==================== TAR ====================
    @classmethod
    def _compress_tar(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 TAR 格式"""
        with tarfile.open(output_path, 'w') as tf:
            tf.add(source_path, arcname=source_path.name)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_tar(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 TAR 文件"""
        with tarfile.open(source_path, 'r') as tf:
            tf.extractall(output_dir)
        
        logger.info(f"已解压到: {output_dir}")
        return True
    
    @classmethod
    def _list_tar_contents(cls, source_path: Path) -> List[Dict]:
        """列出 TAR 文件内容"""
        contents = []
        
        mode = 'r:gz' if source_path.suffix == '.gz' else 'r'
        with tarfile.open(source_path, mode) as tf:
            for member in tf.getmembers():
                contents.append({
                    "name": member.name,
                    "size": member.size,
                    "modified": member.mtime,
                    "is_dir": member.isdir(),
                    "type": member.type
                })
        
        return contents
    
    # ==================== GZIP ====================
    @classmethod
    def _compress_gzip(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 GZIP 格式（仅支持单个文件）"""
        if not source_path.is_file():
            logger.error("GZIP 只支持压缩单个文件")
            return False
        
        with open(source_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_gzip(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 GZIP 文件"""
        output_path = output_dir / source_path.stem
        
        with gzip.open(source_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已解压到: {output_path}")
        return True
    
    # ==================== BZIP2 ====================
    @classmethod
    def _compress_bz2(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 BZIP2 格式（仅支持单个文件）"""
        if not source_path.is_file():
            logger.error("BZIP2 只支持压缩单个文件")
            return False
        
        with open(source_path, 'rb') as f_in:
            with bz2.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_bz2(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 BZIP2 文件"""
        output_path = output_dir / source_path.stem
        
        with bz2.open(source_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已解压到: {output_path}")
        return True
    
    # ==================== XZ ====================
    @classmethod
    def _compress_xz(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 XZ 格式（仅支持单个文件）"""
        if not source_path.is_file():
            logger.error("XZ 只支持压缩单个文件")
            return False
        
        with open(source_path, 'rb') as f_in:
            with lzma.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_xz(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 XZ 文件"""
        output_path = output_dir / source_path.stem
        
        with lzma.open(source_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"已解压到: {output_path}")
        return True
    
    # ==================== TAR.GZ ====================
    @classmethod
    def _compress_tar_gz(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 TAR.GZ 格式"""
        with tarfile.open(output_path, 'w:gz') as tf:
            tf.add(source_path, arcname=source_path.name)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_tar_gz(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 TAR.GZ 文件"""
        with tarfile.open(source_path, 'r:gz') as tf:
            tf.extractall(output_dir)
        
        logger.info(f"已解压到: {output_dir}")
        return True
    
    # ==================== TAR.BZ2 ====================
    @classmethod
    def _compress_tar_bz2(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 TAR.BZ2 格式"""
        with tarfile.open(output_path, 'w:bz2') as tf:
            tf.add(source_path, arcname=source_path.name)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_tar_bz2(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 TAR.BZ2 文件"""
        with tarfile.open(source_path, 'r:bz2') as tf:
            tf.extractall(output_dir)
        
        logger.info(f"已解压到: {output_dir}")
        return True
    
    # ==================== TAR.XZ ====================
    @classmethod
    def _compress_tar_xz(cls, source_path: Path, output_path: Path) -> bool:
        """压缩为 TAR.XZ 格式"""
        with tarfile.open(output_path, 'w:xz') as tf:
            tf.add(source_path, arcname=source_path.name)
        
        logger.info(f"已压缩到: {output_path}")
        return True
    
    @classmethod
    def _decompress_tar_xz(cls, source_path: Path, output_dir: Path) -> bool:
        """解压 TAR.XZ 文件"""
        with tarfile.open(source_path, 'r:xz') as tf:
            tf.extractall(output_dir)
        
        logger.info(f"已解压到: {output_dir}")
        return True


class NanoZipIntegration:
    """
    NanoZip 集成类
    
    如果系统安装了 NanoZip，则使用 NanoZip 进行压缩
    否则回退到标准库实现
    """
    
    _nanozip_available = None
    
    @classmethod
    def is_nanozip_available(cls) -> bool:
        """检查 NanoZip 是否可用"""
        if cls._nanozip_available is not None:
            return cls._nanozip_available
        
        try:
            import nanozip
            cls._nanozip_available = True
        except ImportError:
            # 尝试检查命令行工具
            try:
                import subprocess
                result = subprocess.run(["nanozip", "--version"], capture_output=True)
                cls._nanozip_available = result.returncode == 0
            except Exception:
                cls._nanozip_available = False
        
        return cls._nanozip_available
    
    @classmethod
    def compress(cls, source_path: Union[str, Path], output_path: Union[str, Path], 
                 level: int = 5, password: str = None) -> bool:
        """
        使用 NanoZip 压缩
        
        Args:
            source_path: 源文件或目录路径
            output_path: 输出压缩文件路径
            level: 压缩级别 (1-9)
            password: 密码
        
        Returns:
            是否压缩成功
        """
        if not cls.is_nanozip_available():
            logger.warning("NanoZip 不可用，使用标准压缩")
            return CompressionUtils.compress(source_path, output_path, "zip", password)
        
        try:
            # 尝试使用 nanozip 库
            import nanozip
            
            source_path = Path(source_path)
            output_path = Path(output_path)
            
            if source_path.is_file():
                nanozip.compress_file(
                    str(source_path), 
                    str(output_path), 
                    level=level,
                    password=password
                )
            else:
                nanozip.compress_directory(
                    str(source_path), 
                    str(output_path), 
                    level=level,
                    password=password
                )
            
            logger.info(f"NanoZip 压缩完成: {output_path}")
            return True
            
        except Exception as e:
            logger.warning(f"NanoZip 压缩失败，回退到标准压缩: {e}")
            return CompressionUtils.compress(source_path, output_path, "zip", password)
    
    @classmethod
    def decompress(cls, source_path: Union[str, Path], output_dir: Union[str, Path], 
                   password: str = None) -> bool:
        """
        使用 NanoZip 解压
        
        Args:
            source_path: 压缩文件路径
            output_dir: 输出目录
            password: 密码
        
        Returns:
            是否解压成功
        """
        if not cls.is_nanozip_available():
            logger.warning("NanoZip 不可用，使用标准解压")
            return CompressionUtils.decompress(source_path, output_dir, password)
        
        try:
            import nanozip
            
            source_path = Path(source_path)
            output_dir = Path(output_dir)
            
            nanozip.decompress(
                str(source_path), 
                str(output_dir),
                password=password
            )
            
            logger.info(f"NanoZip 解压完成: {output_dir}")
            return True
            
        except Exception as e:
            logger.warning(f"NanoZip 解压失败，回退到标准解压: {e}")
            return CompressionUtils.decompress(source_path, output_dir, password)
    
    @classmethod
    def list_contents(cls, source_path: Union[str, Path]) -> List[Dict]:
        """
        使用 NanoZip 查看压缩包内容
        
        Args:
            source_path: 压缩文件路径
        
        Returns:
            文件列表
        """
        if not cls.is_nanozip_available():
            return CompressionUtils.list_contents(source_path)
        
        try:
            import nanozip
            
            source_path = Path(source_path)
            return nanozip.list_contents(str(source_path))
            
        except Exception as e:
            logger.warning(f"NanoZip 查看失败，回退到标准方法: {e}")
            return CompressionUtils.list_contents(source_path)


# 快捷函数
def compress(source_path: Union[str, Path], output_path: Union[str, Path], 
             compression_format: str = "zip", password: str = None) -> bool:
    """快捷压缩函数"""
    return CompressionUtils.compress(source_path, output_path, compression_format, password)


def decompress(source_path: Union[str, Path], output_dir: Union[str, Path], 
               password: str = None) -> bool:
    """快捷解压函数"""
    return CompressionUtils.decompress(source_path, output_dir, password)


def list_archive_contents(source_path: Union[str, Path], password: str = None) -> List[Dict]:
    """快捷查看压缩包内容函数"""
    return CompressionUtils.list_contents(source_path, password)


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("压缩工具库测试")
    print("=" * 60)
    
    # 测试文件路径
    test_dir = Path(__file__).parent / "test_compression"
    test_dir.mkdir(exist_ok=True)
    
    # 创建测试文件
    test_file = test_dir / "test.txt"
    test_file.write_text("Hello, Compression!", encoding="utf-8")
    
    # 测试压缩
    zip_file = test_dir / "test.zip"
    success = CompressionUtils.compress(test_file, zip_file)
    print(f"ZIP 压缩: {'成功' if success else '失败'}")
    
    # 测试查看内容
    contents = CompressionUtils.list_contents(zip_file)
    print(f"压缩包内容: {len(contents)} 个文件")
    for item in contents:
        print(f"  - {item['name']}: {item['size']} bytes")
    
    # 测试解压
    extract_dir = test_dir / "extracted"
    success = CompressionUtils.decompress(zip_file, extract_dir)
    print(f"ZIP 解压: {'成功' if success else '失败'}")
    
    # 测试 NanoZip
    print(f"\nNanoZip 可用: {'是' if NanoZipIntegration.is_nanozip_available() else '否'}")
    
    # 清理测试文件
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    
    print("\n" + "=" * 60)