"""
自动扫描器 - 极速扫描本地文件系统

核心功能：
1. 极速扫描本地所有文档
2. 智能分类文档类型
3. 优先级排序（核心优先）
4. 资源限制管理
"""
import os
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScannedFile:
    """扫描到的文件"""
    path: str
    file_type: str
    size: int
    modified_time: float
    priority: int = 5  # 1-10，1最高
    is_core: bool = False
    processed: bool = False


@dataclass
class ScanResult:
    """扫描结果"""
    files: List[ScannedFile]
    total_count: int
    core_count: int
    execution_time: float
    directories_scanned: int


class AutoScanner:
    """
    自动扫描器
    
    特点：
    - 极速扫描（跳过系统目录和大文件）
    - 智能分类文档类型
    - 核心文档优先识别
    - 资源限制支持
    """
    
    # 文档类型映射
    DOCUMENT_EXTENSIONS = {
        'pdf': 'pdf',
        'docx': 'word',
        'doc': 'word',
        'xlsx': 'excel',
        'xls': 'excel',
        'pptx': 'powerpoint',
        'ppt': 'powerpoint',
        'txt': 'text',
        'md': 'markdown',
        'json': 'json',
        'xml': 'xml',
        'html': 'html',
    }
    
    # 核心文档关键词
    CORE_KEYWORDS = [
        '标准', '规范', '导则', '法规', '条例', '办法',
        '环评', '可研', '报告', '方案', '规划',
        '财务', '分析', '计算', '模型', '数据',
    ]
    
    # 跳过的目录
    SKIP_DIRECTORIES = [
        'node_modules', '__pycache__', '.git', '.svn',
        'System Volume Information', '$RECYCLE.BIN',
        'Windows', 'Program Files', 'Program Files (x86)',
        '.venv', 'venv', 'env',
    ]
    
    def __init__(self):
        self.max_scan_depth = 3
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.max_files_per_scan = 1000
        self.scan_results: List[ScannedFile] = []
    
    def scan(self, root_paths: Optional[List[str]] = None) -> ScanResult:
        """
        执行扫描
        
        Args:
            root_paths: 根路径列表，默认扫描所有本地磁盘
            
        Returns:
            ScanResult
        """
        start_time = time.time()
        files = []
        directories_scanned = 0
        
        # 如果没有指定路径，扫描所有本地磁盘
        if not root_paths:
            root_paths = self._get_local_drives()
        
        for root_path in root_paths:
            try:
                result = self._scan_directory(root_path, depth=0)
                files.extend(result['files'])
                directories_scanned += result['directories']
            except Exception as e:
                logger.warning(f"扫描路径失败 {root_path}: {e}")
        
        # 限制文件数量
        files = files[:self.max_files_per_scan]
        
        # 标记核心文档
        files = self._mark_core_documents(files)
        
        # 按优先级排序
        files.sort(key=lambda f: f.priority)
        
        execution_time = time.time() - start_time
        
        self.scan_results = files
        
        return ScanResult(
            files=files,
            total_count=len(files),
            core_count=sum(1 for f in files if f.is_core),
            execution_time=execution_time,
            directories_scanned=directories_scanned
        )
    
    def _get_local_drives(self) -> List[str]:
        """获取本地磁盘驱动器"""
        drives = []
        
        if os.name == 'nt':
            # Windows
            import win32api
            for drive in win32api.GetLogicalDriveStrings().split('\x00')[:-1]:
                drives.append(drive)
        else:
            # Unix-like
            drives = ['/']
        
        return drives
    
    def _scan_directory(self, path: str, depth: int) -> Dict[str, Any]:
        """扫描目录"""
        files = []
        directories = 0
        
        if depth > self.max_scan_depth:
            return {'files': files, 'directories': directories}
        
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        # 跳过特殊目录
                        if entry.name.lower() in self.SKIP_DIRECTORIES:
                            continue
                        
                        if entry.is_dir(follow_symlinks=False):
                            directories += 1
                            result = self._scan_directory(entry.path, depth + 1)
                            files.extend(result['files'])
                            directories += result['directories']
                        
                        elif entry.is_file(follow_symlinks=False):
                            file_info = self._process_file(entry)
                            if file_info:
                                files.append(file_info)
                    
                    except PermissionError:
                        continue
                    except Exception as e:
                        logger.debug(f"处理文件失败 {entry.path}: {e}")
        
        except Exception as e:
            logger.debug(f"扫描目录失败 {path}: {e}")
        
        return {'files': files, 'directories': directories}
    
    def _process_file(self, entry) -> Optional[ScannedFile]:
        """处理单个文件"""
        try:
            # 获取文件大小
            stat = entry.stat()
            size = stat.st_size
            
            # 跳过太大的文件
            if size > self.max_file_size:
                return None
            
            # 获取文件类型
            ext = entry.name.split('.')[-1].lower()
            file_type = self.DOCUMENT_EXTENSIONS.get(ext)
            
            if not file_type:
                return None
            
            return ScannedFile(
                path=entry.path,
                file_type=file_type,
                size=size,
                modified_time=stat.st_mtime,
                priority=self._calculate_priority(entry.name, file_type)
            )
        
        except Exception as e:
            logger.debug(f"处理文件失败 {entry.path}: {e}")
            return None
    
    def _calculate_priority(self, filename: str, file_type: str) -> int:
        """计算文件优先级"""
        priority = 5
        
        # 文件类型权重
        type_weights = {
            'pdf': 2,
            'word': 2,
            'excel': 3,
            'text': 4,
            'markdown': 4,
        }
        priority += type_weights.get(file_type, 3)
        
        # 关键词权重
        for keyword in self.CORE_KEYWORDS:
            if keyword in filename:
                priority -= 2  # 提高优先级
                break
        
        # 文件名长度（短文件名可能更重要）
        if len(filename) < 20:
            priority -= 1
        
        return max(1, min(10, priority))
    
    def _mark_core_documents(self, files: List[ScannedFile]) -> List[ScannedFile]:
        """标记核心文档"""
        for file in files:
            # 根据文件名判断是否为核心文档
            for keyword in self.CORE_KEYWORDS:
                if keyword in file.path:
                    file.is_core = True
                    file.priority = min(file.priority, 2)  # 提高优先级
                    break
        
        return files
    
    def get_core_documents(self) -> List[ScannedFile]:
        """获取核心文档"""
        return [f for f in self.get_unprocessed_files() if f.is_core]
    
    def get_unprocessed_files(self) -> List[ScannedFile]:
        """获取未处理的文件"""
        return [f for f in self.scan_results if not f.processed]
    
    def mark_processed(self, file_path: str):
        """标记文件已处理"""
        for file in self.scan_results:
            if file.path == file_path:
                file.processed = True
                break
    
    def clear_results(self):
        """清除扫描结果"""
        self.scan_results = []