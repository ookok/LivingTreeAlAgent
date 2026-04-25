"""
文件分类器
基于扩展名和内容特征的文件类型识别
"""

import os
import re
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass


class FileCategory(Enum):
    """文件大类"""
    DOCUMENT = "文档"
    CODE = "代码"
    MEDIA = "媒体"
    ARCHIVE = "压缩包"
    CONFIG = "配置"
    DATA = "数据"
    OTHER = "其他"


@dataclass
class FileCategoryInfo:
    """文件分类信息"""
    category: FileCategory
    subcategory: str
    extensions: List[str]
    description: str
    icon: str = ""


class FileClassifier:
    """
    文件分类器
    
    支持:
    - 基于扩展名的快速分类
    - 多级分类体系
    - 自定义分类规则
    """
    
    # 扩展名到分类的映射
    EXTENSION_MAP: Dict[str, FileCategory] = {
        # 文档
        '.pdf': FileCategory.DOCUMENT,
        '.doc': FileCategory.DOCUMENT, '.docx': FileCategory.DOCUMENT,
        '.txt': FileCategory.DOCUMENT, '.md': FileCategory.DOCUMENT,
        '.rtf': FileCategory.DOCUMENT, '.odt': FileCategory.DOCUMENT,
        '.xls': FileCategory.DOCUMENT, '.xlsx': FileCategory.DOCUMENT,
        '.ppt': FileCategory.DOCUMENT, '.pptx': FileCategory.DOCUMENT,
        '.csv': FileCategory.DOCUMENT,
        
        # 代码
        '.py': FileCategory.CODE, '.js': FileCategory.CODE, '.ts': FileCategory.CODE,
        '.java': FileCategory.CODE, '.cpp': FileCategory.CODE, '.c': FileCategory.CODE,
        '.h': FileCategory.CODE, '.hpp': FileCategory.CODE, '.cs': FileCategory.CODE,
        '.go': FileCategory.CODE, '.rs': FileCategory.CODE, '.rb': FileCategory.CODE,
        '.php': FileCategory.CODE, '.swift': FileCategory.CODE, '.kt': FileCategory.CODE,
        '.html': FileCategory.CODE, '.css': FileCategory.CODE, '.scss': FileCategory.CODE,
        '.vue': FileCategory.CODE, '.jsx': FileCategory.CODE, '.tsx': FileCategory.CODE,
        '.sql': FileCategory.CODE, '.sh': FileCategory.CODE, '.bat': FileCategory.CODE,
        '.ps1': FileCategory.CODE, '.r': FileCategory.CODE, '.m': FileCategory.CODE,
        '.lua': FileCategory.CODE, '.pl': FileCategory.CODE, '.ex': FileCategory.CODE,
        '.exs': FileCategory.CODE, '.erl': FileCategory.CODE, '.hs': FileCategory.CODE,
        '.clj': FileCategory.CODE, '.scala': FileCategory.CODE, '.fs': FileCategory.CODE,
        '.fsx': FileCategory.CODE, '.dart': FileCategory.CODE, '.groovy': FileCategory.CODE,
        '.gradle': FileCategory.CODE, '.makefile': FileCategory.CODE,
        '.dockerfile': FileCategory.CODE, '.v': FileCategory.CODE, '.vhd': FileCategory.CODE,
        '.asm': FileCategory.CODE, '.s': FileCategory.CODE, '.S': FileCategory.CODE,
        
        # 配置
        '.json': FileCategory.CONFIG, '.yaml': FileCategory.CONFIG, '.yml': FileCategory.CONFIG,
        '.xml': FileCategory.CONFIG, '.toml': FileCategory.CONFIG, '.ini': FileCategory.CONFIG,
        '.cfg': FileCategory.CONFIG, '.conf': FileCategory.CONFIG, '.properties': FileCategory.CONFIG,
        '.env': FileCategory.CONFIG, '.gitignore': FileCategory.CONFIG,
        
        # 媒体 - 图片
        '.jpg': FileCategory.MEDIA, '.jpeg': FileCategory.MEDIA, '.png': FileCategory.MEDIA,
        '.gif': FileCategory.MEDIA, '.bmp': FileCategory.MEDIA, '.svg': FileCategory.MEDIA,
        '.ico': FileCategory.MEDIA, '.webp': FileCategory.MEDIA, '.tiff': FileCategory.MEDIA,
        '.tif': FileCategory.MEDIA, '.psd': FileCategory.MEDIA, '.ai': FileCategory.MEDIA,
        '.eps': FileCategory.MEDIA, '.raw': FileCategory.MEDIA, '.heic': FileCategory.MEDIA,
        
        # 媒体 - 视频
        '.mp4': FileCategory.MEDIA, '.avi': FileCategory.MEDIA, '.mkv': FileCategory.MEDIA,
        '.mov': FileCategory.MEDIA, '.wmv': FileCategory.MEDIA, '.flv': FileCategory.MEDIA,
        '.webm': FileCategory.MEDIA, '.m4v': FileCategory.MEDIA, '.mpeg': FileCategory.MEDIA,
        '.mpg': FileCategory.MEDIA, '.3gp': FileCategory.MEDIA, '.ogv': FileCategory.MEDIA,
        
        # 媒体 - 音频
        '.mp3': FileCategory.MEDIA, '.wav': FileCategory.MEDIA, '.flac': FileCategory.MEDIA,
        '.aac': FileCategory.MEDIA, '.ogg': FileCategory.MEDIA, '.wma': FileCategory.MEDIA,
        '.m4a': FileCategory.MEDIA, '.opus': FileCategory.MEDIA, '.ape': FileCategory.MEDIA,
        '.alac': FileCategory.MEDIA,
        
        # 压缩包
        '.zip': FileCategory.ARCHIVE, '.rar': FileCategory.ARCHIVE, '.7z': FileCategory.ARCHIVE,
        '.tar': FileCategory.ARCHIVE, '.gz': FileCategory.ARCHIVE, '.bz2': FileCategory.ARCHIVE,
        '.xz': FileCategory.ARCHIVE, '.tgz': FileCategory.ARCHIVE, '.tbz2': FileCategory.ARCHIVE,
        '.tar.gz': FileCategory.ARCHIVE, '.tar.bz2': FileCategory.ARCHIVE, '.tar.xz': FileCategory.ARCHIVE,
        
        # 数据
        '.db': FileCategory.DATA, '.sqlite': FileCategory.DATA, '.mdb': FileCategory.DATA,
        '.dbf': FileCategory.DATA, '.parquet': FileCategory.DATA, '.arrow': FileCategory.DATA,
        '.pickle': FileCategory.DATA, '.pkl': FileCategory.DATA, '.h5': FileCategory.DATA,
        '.hdf5': FileCategory.DATA, '.npy': FileCategory.DATA, '.npz': FileCategory.DATA,
    }
    
    # 文件名模式到分类
    PATTERN_MAP = [
        # 代码
        (r'^Makefile$', FileCategory.CODE, 'Makefile'),
        (r'^Dockerfile$', FileCategory.CODE, 'Dockerfile'),
        (r'^\.gitignore$', FileCategory.CONFIG, 'Git配置'),
        (r'^\.env$', FileCategory.CONFIG, '环境变量'),
        
        # 文档
        (r'^README', FileCategory.DOCUMENT, 'README'),
        (r'^CHANGELOG', FileCategory.DOCUMENT, '变更日志'),
        (r'^LICENSE', FileCategory.DOCUMENT, '许可证'),
        (r'^TODO', FileCategory.DOCUMENT, '待办事项'),
    ]
    
    # 分类描述
    CATEGORY_INFO = {
        FileCategory.DOCUMENT: FileCategoryInfo(
            category=FileCategory.DOCUMENT,
            subcategory="文档",
            extensions=['.pdf', '.doc', '.docx', '.txt', '.md'],
            description="文档、报告、手册",
            icon="📄"
        ),
        FileCategory.CODE: FileCategoryInfo(
            category=FileCategory.CODE,
            subcategory="代码",
            extensions=['.py', '.js', '.java', '.cpp'],
            description="源代码和脚本",
            icon="💻"
        ),
        FileCategory.MEDIA: FileCategoryInfo(
            category=FileCategory.MEDIA,
            subcategory="媒体",
            extensions=['.jpg', '.mp4', '.mp3'],
            description="图片、音频、视频",
            icon="🎨"
        ),
        FileCategory.ARCHIVE: FileCategoryInfo(
            category=FileCategory.ARCHIVE,
            subcategory="压缩包",
            extensions=['.zip', '.rar', '.7z'],
            description="压缩和归档文件",
            icon="📦"
        ),
        FileCategory.CONFIG: FileCategoryInfo(
            category=FileCategory.CONFIG,
            subcategory="配置",
            extensions=['.json', '.yaml', '.xml'],
            description="配置和设置文件",
            icon="⚙️"
        ),
        FileCategory.DATA: FileCategoryInfo(
            category=FileCategory.DATA,
            subcategory="数据",
            extensions=['.db', '.sqlite', '.csv'],
            description="数据库和数据文件",
            icon="🗃️"
        ),
        FileCategory.OTHER: FileCategoryInfo(
            category=FileCategory.OTHER,
            subcategory="其他",
            extensions=[],
            description="其他文件",
            icon="📁"
        ),
    }
    
    def __init__(self):
        """初始化分类器"""
        # 构建快速查询表
        self._ext_lower_map: Dict[str, FileCategory] = {}
        for ext, cat in self.EXTENSION_MAP.items():
            self._ext_lower_map[ext.lower()] = cat
        
        # 编译模式
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), cat, name)
            for pattern, cat, name in self.PATTERN_MAP
        ]
    
    def classify(self, path: str) -> FileCategory:
        """
        分类文件
        
        Args:
            path: 文件路径
            
        Returns:
            文件分类
        """
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1]
        
        # 优先按扩展名
        if ext.lower() in self._ext_lower_map:
            return self._ext_lower_map[ext.lower()]
        
        # 按文件名模式
        for pattern, cat, name in self._compiled_patterns:
            if pattern.match(filename):
                return cat
        
        return FileCategory.OTHER
    
    def classify_with_info(self, path: str) -> FileCategoryInfo:
        """
        获取分类详细信息
        
        Args:
            path: 文件路径
            
        Returns:
            分类信息
        """
        category = self.classify(path)
        return self.CATEGORY_INFO[category]
    
    def get_extensions(self, category: FileCategory) -> List[str]:
        """获取指定分类的所有扩展名"""
        return [
            ext for ext, cat in self.EXTENSION_MAP.items()
            if cat == category
        ]
    
    def filter_by_category(
        self,
        paths: List[str],
        categories: List[FileCategory]
    ) -> List[str]:
        """
        按分类过滤文件列表
        
        Args:
            paths: 文件路径列表
            categories: 要保留的分类列表
            
        Returns:
            过滤后的文件列表
        """
        category_set = set(categories)
        return [p for p in paths if self.classify(p) in category_set]
    
    def group_by_category(self, paths: List[str]) -> Dict[FileCategory, List[str]]:
        """
        按分类分组文件
        
        Args:
            paths: 文件路径列表
            
        Returns:
            {分类: [文件列表]}
        """
        groups: Dict[FileCategory, List[str]] = {cat: [] for cat in FileCategory}
        
        for path in paths:
            category = self.classify(path)
            groups[category].append(path)
        
        # 移除空分组
        return {k: v for k, v in groups.items() if v}
    
    def suggest_category_keywords(self, category: FileCategory) -> List[str]:
        """获取分类建议关键词"""
        keywords = {
            FileCategory.DOCUMENT: ['文档', '报告', '手册', '论文', '合同'],
            FileCategory.CODE: ['代码', '源码', '脚本', '程序'],
            FileCategory.MEDIA: ['图片', '照片', '视频', '音频', '音乐'],
            FileCategory.ARCHIVE: ['压缩', '归档', '备份'],
            FileCategory.CONFIG: ['配置', '设置', '环境'],
            FileCategory.DATA: ['数据', '数据库', '日志'],
            FileCategory.OTHER: [],
        }
        return keywords.get(category, [])


# ==================== 单例 ====================

_classifier: Optional[FileClassifier] = None


def get_classifier() -> FileClassifier:
    """获取分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = FileClassifier()
    return _classifier


if __name__ == "__main__":
    classifier = FileClassifier()
    
    test_files = [
        "/path/to/readme.md",
        "/path/to/main.py",
        "/path/to/image.png",
        "/path/to/data.zip",
        "/path/to/config.yaml",
        "/path/to/database.sqlite",
        "/path/to/document.pdf",
        "/path/to/video.mp4",
        "/path/to/script.sh",
        "/path/to/notes.txt",
    ]
    
    print("文件分类测试:")
    print("-" * 50)
    
    for path in test_files:
        info = classifier.classify_with_info(path)
        print(f"{info.icon} {os.path.basename(path):20} -> {info.category.value} ({info.subcategory})")
    
    print("\n按分类分组:")
    print("-" * 50)
    
    groups = classifier.group_by_category(test_files)
    for category, files in groups.items():
        info = classifier.CATEGORY_INFO[category]
        print(f"\n{info.icon} {info.subcategory}:")
        for f in files:
            print(f"  - {os.path.basename(f)}")
