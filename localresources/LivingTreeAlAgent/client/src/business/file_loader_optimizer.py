"""
文件加载极速优化模块
实现三层智能加载策略，提升IDE文件加载性能
"""

import os
import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class FileType(Enum):
    """文件类型"""
    CODE = "code"          # 代码文件
    CONFIG = "config"      # 配置文件
    TEST = "test"          # 测试文件
    ASSET = "asset"        # 资源文件
    DOCUMENT = "document"  # 文档文件
    OTHER = "other"        # 其他文件


class FilePriority(Enum):
    """文件优先级"""
    HIGH = 3     # 高优先级（配置文件、核心代码）
    MEDIUM = 2   # 中等优先级（普通代码文件）
    LOW = 1      # 低优先级（测试文件、资源文件）


@dataclass
class FileMetadata:
    """文件元数据"""
    path: str
    name: str
    size: int
    mtime: float
    file_type: FileType
    priority: FilePriority
    loaded: bool = False
    loading: bool = False
    last_access: float = 0.0
    content: Optional[str] = None


@dataclass
class DirectoryNode:
    """目录节点"""
    path: str
    name: str
    is_dir: bool
    children: List['DirectoryNode'] = field(default_factory=list)
    metadata: Optional[FileMetadata] = None


class FileCacheLevel(Enum):
    """缓存级别"""
    L1 = "memory"   # 内存缓存（活跃文件）
    L2 = "disk"     # 磁盘缓存（最近使用）
    L3 = "index"    # 索引缓存（符号表）
    L4 = "prefetch" # 预取缓存（预测文件）


class FileLoader:
    """
    文件加载器
    实现三层智能加载策略
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.file_metadata: Dict[str, FileMetadata] = {}
        self.directory_tree: Optional[DirectoryNode] = None
        self.cache: Dict[FileCacheLevel, Dict[str, Any]] = {
            FileCacheLevel.L1: {},  # 内存缓存
            FileCacheLevel.L2: {},  # 磁盘缓存
            FileCacheLevel.L3: {},  # 索引缓存
            FileCacheLevel.L4: {}   # 预取缓存
        }
        self.ignore_patterns = {
            "node_modules", "dist", "build", ".git", ".venv", 
            "__pycache__", "*.pyc", "*.pyo", "*.class"
        }
        self.semantic_connections: Dict[str, List[str]] = {}  # 文件间语义连接
        self.heatmap: Dict[str, int] = {}  # 文件访问热力图
        self.workflow_context = "coding"  # 当前工作流上下文
        
        # 工作流预测规则
        self.workflow_rules = {
            ".tsx": [".css", ".test.tsx"],
            ".jsx": [".css", ".test.jsx"],
            ".py": ["test_*.py", "*_test.py"],
            ".ts": [".d.ts", "*.test.ts"],
            ".js": ["*.test.js"]
        }
        
        # 关键文件类型
        self.key_file_patterns = {
            "package.json", "tsconfig.json", "webpack.config.js",
            "requirements.txt", "setup.py", "Dockerfile",
            "README.md", "README.rst"
        }
    
    def build_directory_tree(self) -> DirectoryNode:
        """
        构建秒级目录树（<100ms）
        只读取元数据，不读取文件内容
        """
        start_time = time.time()
        
        def build_node(path: str, name: str, is_dir: bool) -> DirectoryNode:
            node = DirectoryNode(path=path, name=name, is_dir=is_dir)
            
            if is_dir:
                try:
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        
                        # 跳过忽略的目录和文件
                        if self._should_ignore(item):
                            continue
                        
                        is_item_dir = os.path.isdir(item_path)
                        child_node = build_node(item_path, item, is_item_dir)
                        node.children.append(child_node)
                except PermissionError:
                    pass
            else:
                # 读取文件元数据
                try:
                    stat = os.stat(path)
                    file_type = self._detect_file_type(name)
                    priority = self._calculate_priority(name, file_type)
                    
                    metadata = FileMetadata(
                        path=path,
                        name=name,
                        size=stat.st_size,
                        mtime=stat.st_mtime,
                        file_type=file_type,
                        priority=priority
                    )
                    node.metadata = metadata
                    self.file_metadata[path] = metadata
                except Exception:
                    pass
            
            return node
        
        self.directory_tree = build_node(self.project_root, os.path.basename(self.project_root), True)
        
        # 关键文件优先处理
        self._prioritize_key_files()
        
        build_time = (time.time() - start_time) * 1000
        print(f"目录树构建完成，耗时: {build_time:.2f}ms")
        
        return self.directory_tree
    
    def _should_ignore(self, name: str) -> bool:
        """判断是否应该忽略文件"""
        for pattern in self.ignore_patterns:
            if pattern == name or (pattern.startswith('*') and name.endswith(pattern[1:])):
                return True
        return False
    
    def _detect_file_type(self, filename: str) -> FileType:
        """检测文件类型"""
        if filename.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cs')):
            return FileType.CODE
        elif filename.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg', '.env')):
            return FileType.CONFIG
        elif filename.endswith(('.test.js', '.test.ts', '.test.jsx', '.test.tsx', 'test_*.py', '*_test.py')):
            return FileType.TEST
        elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico')):
            return FileType.ASSET
        elif filename.endswith(('.md', '.rst', '.txt', '.doc', '.docx')):
            return FileType.DOCUMENT
        else:
            return FileType.OTHER
    
    def _calculate_priority(self, filename: str, file_type: FileType) -> FilePriority:
        """计算文件优先级"""
        if filename in self.key_file_patterns:
            return FilePriority.HIGH
        elif file_type == FileType.CONFIG:
            return FilePriority.HIGH
        elif file_type == FileType.CODE:
            return FilePriority.MEDIUM
        else:
            return FilePriority.LOW
    
    def _prioritize_key_files(self):
        """优先处理关键文件"""
        for path, metadata in self.file_metadata.items():
            if metadata.name in self.key_file_patterns:
                metadata.priority = FilePriority.HIGH
    
    async def smart_preload(self, focused_file: str):
        """
        智能预加载
        基于视觉焦点和工作流预测
        """
        # 标记当前文件为活跃
        self._update_heatmap(focused_file)
        
        # 预测相关文件
        related_files = self._predict_related_files(focused_file)
        
        # 异步预加载
        preload_tasks = []
        for file_path in related_files:
            if file_path in self.file_metadata and not self.file_metadata[file_path].loaded:
                preload_tasks.append(self._preload_file(file_path))
        
        if preload_tasks:
            await asyncio.gather(*preload_tasks)
    
    def _predict_related_files(self, file_path: str) -> List[str]:
        """预测相关文件"""
        related_files = []
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1]
        
        # 基于文件扩展名的预测
        if ext in self.workflow_rules:
            for pattern in self.workflow_rules[ext]:
                # 生成可能的相关文件路径
                base_name = os.path.splitext(filename)[0]
                if pattern.startswith('*'):
                    # 如 *.test.ts
                    test_filename = f"{base_name}{pattern[1:]}"
                elif pattern.endswith('*'):
                    # 如 test_*.py
                    test_filename = f"{pattern[:-1]}{base_name}.py"
                else:
                    # 如 .css
                    test_filename = f"{base_name}{pattern}"
                
                test_path = os.path.join(os.path.dirname(file_path), test_filename)
                if os.path.exists(test_path):
                    related_files.append(test_path)
        
        # 基于语义连接的预测
        if file_path in self.semantic_connections:
            related_files.extend(self.semantic_connections[file_path])
        
        return related_files
    
    async def _preload_file(self, file_path: str):
        """预加载文件"""
        if file_path in self.file_metadata:
            metadata = self.file_metadata[file_path]
            if not metadata.loaded and not metadata.loading:
                metadata.loading = True
                try:
                    # 预加载前100行
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= 100:
                                break
                            lines.append(line)
                        metadata.content = ''.join(lines)
                        metadata.loaded = True
                except Exception:
                    pass
                finally:
                    metadata.loading = False
    
    async def load_file_content(self, file_path: str, load_full: bool = False) -> Optional[str]:
        """
        渐进式内容加载
        1. 先加载前100行（函数声明/接口）
        2. 按需加载具体函数
        3. 最后加载完整文件（极少需要）
        """
        if file_path not in self.file_metadata:
            return None
        
        metadata = self.file_metadata[file_path]
        
        # 更新访问时间和热力图
        metadata.last_access = time.time()
        self._update_heatmap(file_path)
        
        # 如果已经加载，直接返回
        if metadata.loaded and (not load_full or metadata.content):
            return metadata.content
        
        # 标记为加载中
        metadata.loading = True
        
        try:
            if load_full:
                # 加载完整文件
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    metadata.content = f.read()
            else:
                # 加载前100行
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 100:
                            break
                        lines.append(line)
                    metadata.content = ''.join(lines)
            
            metadata.loaded = True
            
            # 缓存到L1
            self.cache[FileCacheLevel.L1][file_path] = metadata.content
            
            # 预加载相关文件
            await self.smart_preload(file_path)
            
            return metadata.content
        except Exception as e:
            print(f"加载文件失败: {file_path}, 错误: {e}")
            return None
        finally:
            metadata.loading = False
    
    def _update_heatmap(self, file_path: str):
        """更新文件访问热力图"""
        self.heatmap[file_path] = self.heatmap.get(file_path, 0) + 1
    
    def build_semantic_connections(self):
        """
        构建语义连接图
        文件间不止是import关系，还有功能关联、数据流依赖、文档对应
        """
        # 这里可以实现更复杂的语义分析
        # 暂时基于文件路径和扩展名构建简单的语义连接
        for file_path, metadata in self.file_metadata.items():
            if metadata.file_type == FileType.CODE:
                # 查找同目录下的相关文件
                dir_path = os.path.dirname(file_path)
                for other_path, other_metadata in self.file_metadata.items():
                    if other_path != file_path and os.path.dirname(other_path) == dir_path:
                        if other_metadata.file_type in [FileType.CODE, FileType.TEST, FileType.CONFIG]:
                            if file_path not in self.semantic_connections:
                                self.semantic_connections[file_path] = []
                            if other_path not in self.semantic_connections[file_path]:
                                self.semantic_connections[file_path].append(other_path)
    
    def set_workflow_context(self, context: str):
        """
        设置工作流上下文
        - coding: 编码模式（侧重源代码）
        - debugging: 调试模式（侧重测试文件）
        - refactoring: 重构模式（侧重类型定义）
        """
        self.workflow_context = context
    
    def get_file_metadata(self, file_path: str) -> Optional[FileMetadata]:
        """获取文件元数据"""
        return self.file_metadata.get(file_path)
    
    def get_directory_tree(self) -> Optional[DirectoryNode]:
        """获取目录树"""
        return self.directory_tree
    
    def get_heatmap(self) -> Dict[str, int]:
        """获取文件访问热力图"""
        return self.heatmap
    
    def get_semantic_connections(self) -> Dict[str, List[str]]:
        """获取语义连接图"""
        return self.semantic_connections
    
    def clear_cache(self, level: Optional[FileCacheLevel] = None):
        """清理缓存"""
        if level:
            self.cache[level].clear()
        else:
            for cache_level in self.cache:
                self.cache[cache_level].clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "L1_memory": len(self.cache[FileCacheLevel.L1]),
            "L2_disk": len(self.cache[FileCacheLevel.L2]),
            "L3_index": len(self.cache[FileCacheLevel.L3]),
            "L4_prefetch": len(self.cache[FileCacheLevel.L4])
        }


class FileLoaderManager:
    """
    文件加载管理器
    管理多个文件加载器实例
    """
    
    def __init__(self):
        self.loaders: Dict[str, FileLoader] = {}
        self.lock = threading.Lock()
    
    def get_loader(self, project_root: str) -> FileLoader:
        """获取或创建文件加载器"""
        with self.lock:
            if project_root not in self.loaders:
                self.loaders[project_root] = FileLoader(project_root)
                # 异步构建目录树
                threading.Thread(target=self.loaders[project_root].build_directory_tree).start()
            return self.loaders[project_root]
    
    def remove_loader(self, project_root: str):
        """移除文件加载器"""
        with self.lock:
            if project_root in self.loaders:
                del self.loaders[project_root]
    
    def get_all_loaders(self) -> Dict[str, FileLoader]:
        """获取所有文件加载器"""
        return self.loaders


# 全局文件加载管理器实例
file_loader_manager = FileLoaderManager()


def get_file_loader(project_root: str) -> FileLoader:
    """
    获取文件加载器
    
    Args:
        project_root: 项目根目录
        
    Returns:
        FileLoader: 文件加载器实例
    """
    return file_loader_manager.get_loader(project_root)


def remove_file_loader(project_root: str):
    """
    移除文件加载器
    
    Args:
        project_root: 项目根目录
    """
    file_loader_manager.remove_loader(project_root)


def get_file_loader_manager() -> FileLoaderManager:
    """
    获取文件加载管理器
    
    Returns:
        FileLoaderManager: 文件加载管理器实例
    """
    return file_loader_manager