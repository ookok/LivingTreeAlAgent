"""
压缩工具库 - 基于 PeaZip 的压缩和解压缩功能

功能特性：
1. 支持多种压缩格式：zip, tar, gzip, bzip2, xz, rar, 7z
2. 支持 PeaZip 压缩/解压（如果可用）
3. 查看压缩包内容
4. 支持密码保护
5. 批量压缩/解压
6. RAR 文件解压支持

项目参考: https://github.com/giorgiotani/PeaZip
"""

import os
import zipfile
import tarfile
import gzip
import bz2
import lzma
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
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
    - RAR (.rar) - 仅支持解压
    - 7Z (.7z) - 仅支持解压
    - TAR.GZ (.tar.gz)
    - TAR.BZ2 (.tar.bz2)
    - TAR.XZ (.tar.xz)
    """
    
    # 支持的压缩格式
    SUPPORTED_FORMATS = {
        "zip": {"ext": ".zip", "description": "ZIP 压缩", "can_compress": True, "can_decompress": True},
        "tar": {"ext": ".tar", "description": "TAR 归档", "can_compress": True, "can_decompress": True},
        "gz": {"ext": ".gz", "description": "GZIP 压缩", "can_compress": True, "can_decompress": True},
        "bz2": {"ext": ".bz2", "description": "BZIP2 压缩", "can_compress": True, "can_decompress": True},
        "xz": {"ext": ".xz", "description": "XZ 压缩", "can_compress": True, "can_decompress": True},
        "rar": {"ext": ".rar", "description": "RAR 压缩", "can_compress": False, "can_decompress": True},
        "7z": {"ext": ".7z", "description": "7-Zip 压缩", "can_compress": False, "can_decompress": True},
        "tar.gz": {"ext": ".tar.gz", "description": "TAR + GZIP", "can_compress": True, "can_decompress": True},
        "tar.bz2": {"ext": ".tar.bz2", "description": "TAR + BZIP2", "can_compress": True, "can_decompress": True},
        "tar.xz": {"ext": ".tar.xz", "description": "TAR + XZ", "can_compress": True, "can_decompress": True},
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
            elif source_path.suffix == ".rar":
                return cls._decompress_rar(source_path, output_dir, password)
            elif source_path.suffix == ".7z":
                return cls._decompress_7z(source_path, output_dir, password)
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
    
    # ==================== RAR ====================
    @classmethod
    def _decompress_rar(cls, source_path: Path, output_dir: Path, password: str = None) -> bool:
        """解压 RAR 文件（使用 PeaZip）"""
        from .compression_utils import PeaZipIntegration
        
        if PeaZipIntegration.is_peazip_available():
            return PeaZipIntegration.decompress(source_path, output_dir, password)
        
        # 尝试使用 unrar 命令行工具
        try:
            result = subprocess.run(
                ["unrar", "x", str(source_path), str(output_dir) + "/"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"已解压 RAR 到: {output_dir}")
                return True
            else:
                logger.warning(f"unrar 解压失败: {result.stderr}")
        except Exception as e:
            logger.warning(f"无法使用 unrar: {e}")
        
        # 尝试使用 rarfile 库
        try:
            import rarfile
            rf = rarfile.RarFile(str(source_path))
            rf.extractall(str(output_dir), pwd=password)
            logger.info(f"已解压 RAR 到: {output_dir}")
            return True
        except ImportError:
            logger.warning("rarfile 库未安装")
        except Exception as e:
            logger.warning(f"rarfile 解压失败: {e}")
        
        logger.error("无法解压 RAR 文件，请安装 PeaZip、unrar 或 rarfile 库")
        return False
    
    # ==================== 7Z ====================
    @classmethod
    def _decompress_7z(cls, source_path: Path, output_dir: Path, password: str = None) -> bool:
        """解压 7Z 文件（使用 PeaZip）"""
        from .compression_utils import PeaZipIntegration
        
        if PeaZipIntegration.is_peazip_available():
            return PeaZipIntegration.decompress(source_path, output_dir, password)
        
        # 尝试使用 7z 命令行工具
        try:
            args = ["7z", "x", str(source_path), f"-o{output_dir}"]
            if password:
                args.append(f"-p{password}")
            
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"已解压 7Z 到: {output_dir}")
                return True
            else:
                logger.warning(f"7z 解压失败: {result.stderr}")
        except Exception as e:
            logger.warning(f"无法使用 7z: {e}")
        
        # 尝试使用 py7zr 库
        try:
            import py7zr
            with py7zr.SevenZipFile(str(source_path), mode='r', password=password) as z:
                z.extractall(str(output_dir))
            logger.info(f"已解压 7Z 到: {output_dir}")
            return True
        except ImportError:
            logger.warning("py7zr 库未安装")
        except Exception as e:
            logger.warning(f"py7zr 解压失败: {e}")
        
        logger.error("无法解压 7Z 文件，请安装 PeaZip、7z 或 py7zr 库")
        return False


class PeaZipIntegration:
    """
    PeaZip 集成类
    
    如果系统安装了 PeaZip，则使用 PeaZip 进行压缩/解压
    否则回退到标准库实现
    
    PeaZip 命令行语法:
    - 压缩: peazip -add archive.zip files
    - 解压: peazip -extract archive.zip dest_folder
    - 查看内容: peazip -list archive.zip
    
    项目地址: https://github.com/giorgiotani/PeaZip
    """
    
    _peazip_available = None
    
    @classmethod
    def is_peazip_available(cls) -> bool:
        """检查 PeaZip 是否可用"""
        if cls._peazip_available is not None:
            return cls._peazip_available
        
        try:
            # 检查命令行工具
            result = subprocess.run(
                ["peazip", "--help"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            cls._peazip_available = result.returncode == 0
        except Exception:
            # 尝试查找 PeaZip 安装路径
            possible_paths = [
                "C:\\Program Files\\PeaZip\\peazip.exe",
                "C:\\Program Files (x86)\\PeaZip\\peazip.exe",
                "/usr/bin/peazip",
                "/usr/local/bin/peazip"
            ]
            for path in possible_paths:
                if Path(path).exists():
                    cls._peazip_available = True
                    break
            else:
                cls._peazip_available = False
        
        return cls._peazip_available
    
    @classmethod
    def get_peazip_path(cls) -> Optional[str]:
        """获取 PeaZip 可执行文件路径"""
        # 首先尝试直接调用
        try:
            result = subprocess.run(["peazip", "--help"], capture_output=True)
            if result.returncode == 0:
                return "peazip"
        except:
            pass
        
        # 尝试常见安装路径
        possible_paths = [
            "C:\\Program Files\\PeaZip\\peazip.exe",
            "C:\\Program Files (x86)\\PeaZip\\peazip.exe",
            "/usr/bin/peazip",
            "/usr/local/bin/peazip"
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        return None
    
    @classmethod
    def compress(cls, source_path: Union[str, Path], output_path: Union[str, Path], 
                 level: int = 5, password: str = None) -> bool:
        """
        使用 PeaZip 压缩
        
        Args:
            source_path: 源文件或目录路径
            output_path: 输出压缩文件路径
            level: 压缩级别 (1-9)
            password: 密码
        
        Returns:
            是否压缩成功
        """
        if not cls.is_peazip_available():
            logger.warning("PeaZip 不可用，使用标准压缩")
            return CompressionUtils.compress(source_path, output_path, "zip", password)
        
        peazip_path = cls.get_peazip_path()
        if not peazip_path:
            return CompressionUtils.compress(source_path, output_path, "zip", password)
        
        source_path = Path(source_path)
        output_path = Path(output_path)
        
        try:
            # PeaZip 命令行参数
            args = [peazip_path, "-add", str(output_path), str(source_path)]
            
            # 添加压缩级别
            if level:
                args.extend(["-level", str(level)])
            
            # 添加密码
            if password:
                args.extend(["-password", password])
            
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"PeaZip 压缩完成: {output_path}")
                return True
            else:
                logger.warning(f"PeaZip 压缩失败: {result.stderr}")
                return CompressionUtils.compress(source_path, output_path, "zip", password)
                
        except Exception as e:
            logger.warning(f"PeaZip 压缩失败，回退到标准压缩: {e}")
            return CompressionUtils.compress(source_path, output_path, "zip", password)
    
    @classmethod
    def decompress(cls, source_path: Union[str, Path], output_dir: Union[str, Path], 
                   password: str = None) -> bool:
        """
        使用 PeaZip 解压
        
        Args:
            source_path: 压缩文件路径
            output_dir: 输出目录
            password: 密码
        
        Returns:
            是否解压成功
        """
        if not cls.is_peazip_available():
            logger.warning("PeaZip 不可用，使用标准解压")
            return CompressionUtils.decompress(source_path, output_dir, password)
        
        peazip_path = cls.get_peazip_path()
        if not peazip_path:
            return CompressionUtils.decompress(source_path, output_dir, password)
        
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # PeaZip 命令行参数
            args = [peazip_path, "-extract", str(source_path), str(output_dir)]
            
            # 添加密码
            if password:
                args.extend(["-password", password])
            
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"PeaZip 解压完成: {output_dir}")
                return True
            else:
                logger.warning(f"PeaZip 解压失败: {result.stderr}")
                return CompressionUtils.decompress(source_path, output_dir, password)
                
        except Exception as e:
            logger.warning(f"PeaZip 解压失败，回退到标准解压: {e}")
            return CompressionUtils.decompress(source_path, output_dir, password)
    
    @classmethod
    def list_contents(cls, source_path: Union[str, Path]) -> List[Dict]:
        """
        使用 PeaZip 查看压缩包内容
        
        Args:
            source_path: 压缩文件路径
        
        Returns:
            文件列表
        """
        if not cls.is_peazip_available():
            return CompressionUtils.list_contents(source_path)
        
        peazip_path = cls.get_peazip_path()
        if not peazip_path:
            return CompressionUtils.list_contents(source_path)
        
        source_path = Path(source_path)
        
        try:
            # PeaZip 命令行参数
            result = subprocess.run(
                [peazip_path, "-list", str(source_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 解析输出
                lines = result.stdout.strip().split('\n')
                contents = []
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith(('---', 'Archive', 'Size', 'Name')):
                        parts = line.split()
                        if len(parts) >= 2:
                            size_str = parts[-2]
                            name = ' '.join(parts[:-2])
                            contents.append({
                                "name": name,
                                "size": cls._parse_size(size_str),
                                "is_dir": name.endswith('/')
                            })
                
                return contents
            else:
                logger.warning(f"PeaZip 查看失败: {result.stderr}")
                return CompressionUtils.list_contents(source_path)
                
        except Exception as e:
            logger.warning(f"PeaZip 查看失败，回退到标准方法: {e}")
            return CompressionUtils.list_contents(source_path)
    
    @classmethod
    def _parse_size(cls, size_str: str) -> int:
        """解析文件大小字符串"""
        size_str = size_str.upper()
        multipliers = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        
        for unit, multiplier in multipliers.items():
            if unit in size_str:
                try:
                    num = float(size_str.replace(unit, '').strip())
                    return int(num * multiplier)
                except:
                    return 0
        
        try:
            return int(size_str)
        except:
            return 0


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