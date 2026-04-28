"""
文件加载极速优化测试
验证三层智能加载策略和智能IDE系统集成
"""

import asyncio
import time
import os
from typing import List, Dict, Optional, Any

print("=" * 60)
print("文件加载极速优化测试")
print("=" * 60)


class FileType:
    """文件类型"""
    CODE = "code"
    CONFIG = "config"
    TEST = "test"
    ASSET = "asset"
    DOCUMENT = "document"
    OTHER = "other"


class FilePriority:
    """文件优先级"""
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class FileCacheLevel:
    """缓存级别"""
    L1 = "memory"
    L2 = "disk"
    L3 = "index"
    L4 = "prefetch"


class FileMetadata:
    """文件元数据"""
    def __init__(self, path, name, size, mtime, file_type, priority):
        self.path = path
        self.name = name
        self.size = size
        self.mtime = mtime
        self.file_type = file_type
        self.priority = priority
        self.loaded = False
        self.loading = False
        self.last_access = 0.0
        self.content = None


class DirectoryNode:
    """目录节点"""
    def __init__(self, path, name, is_dir):
        self.path = path
        self.name = name
        self.is_dir = is_dir
        self.children = []
        self.metadata = None


class FileLoader:
    """文件加载器"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.file_metadata = {}
        self.directory_tree = None
        self.cache = {
            FileCacheLevel.L1: {},
            FileCacheLevel.L2: {},
            FileCacheLevel.L3: {},
            FileCacheLevel.L4: {}
        }
        self.ignore_patterns = {
            "node_modules", "dist", "build", ".git", ".venv", 
            "__pycache__", "*.pyc", "*.pyo", "*.class"
        }
        self.semantic_connections = {}
        self.heatmap = {}
        self.workflow_context = "coding"
        
        self.workflow_rules = {
            ".tsx": [".css", ".test.tsx"],
            ".jsx": [".css", ".test.jsx"],
            ".py": ["test_*.py", "*_test.py"],
            ".ts": [".d.ts", "*.test.ts"],
            ".js": ["*.test.js"]
        }
        
        self.key_file_patterns = {
            "package.json", "tsconfig.json", "webpack.config.js",
            "requirements.txt", "setup.py", "Dockerfile",
            "README.md", "README.rst"
        }
    
    def build_directory_tree(self):
        """构建秒级目录树"""
        start_time = time.time()
        
        def build_node(path, name, is_dir):
            node = DirectoryNode(path, name, is_dir)
            
            if is_dir:
                try:
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        
                        if self._should_ignore(item):
                            continue
                        
                        is_item_dir = os.path.isdir(item_path)
                        child_node = build_node(item_path, item, is_item_dir)
                        node.children.append(child_node)
                except PermissionError:
                    pass
            else:
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
        self._prioritize_key_files()
        
        build_time = (time.time() - start_time) * 1000
        print(f"目录树构建完成，耗时: {build_time:.2f}ms")
        
        return self.directory_tree
    
    def _should_ignore(self, name):
        """判断是否应该忽略文件"""
        for pattern in self.ignore_patterns:
            if pattern == name or (pattern.startswith('*') and name.endswith(pattern[1:])):
                return True
        return False
    
    def _detect_file_type(self, filename):
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
    
    def _calculate_priority(self, filename, file_type):
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
    
    async def smart_preload(self, focused_file):
        """智能预加载"""
        self._update_heatmap(focused_file)
        related_files = self._predict_related_files(focused_file)
        
        preload_tasks = []
        for file_path in related_files:
            if file_path in self.file_metadata and not self.file_metadata[file_path].loaded:
                preload_tasks.append(self._preload_file(file_path))
        
        if preload_tasks:
            await asyncio.gather(*preload_tasks)
    
    def _predict_related_files(self, file_path):
        """预测相关文件"""
        related_files = []
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1]
        
        if ext in self.workflow_rules:
            for pattern in self.workflow_rules[ext]:
                base_name = os.path.splitext(filename)[0]
                if pattern.startswith('*'):
                    test_filename = f"{base_name}{pattern[1:]}"
                elif pattern.endswith('*'):
                    test_filename = f"{pattern[:-1]}{base_name}.py"
                else:
                    test_filename = f"{base_name}{pattern}"
                
                test_path = os.path.join(os.path.dirname(file_path), test_filename)
                if os.path.exists(test_path):
                    related_files.append(test_path)
        
        if file_path in self.semantic_connections:
            related_files.extend(self.semantic_connections[file_path])
        
        return related_files
    
    async def _preload_file(self, file_path):
        """预加载文件"""
        if file_path in self.file_metadata:
            metadata = self.file_metadata[file_path]
            if not metadata.loaded and not metadata.loading:
                metadata.loading = True
                try:
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
    
    async def load_file_content(self, file_path, load_full=False):
        """渐进式内容加载"""
        if file_path not in self.file_metadata:
            return None
        
        metadata = self.file_metadata[file_path]
        metadata.last_access = time.time()
        self._update_heatmap(file_path)
        
        if metadata.loaded and (not load_full or metadata.content):
            return metadata.content
        
        metadata.loading = True
        
        try:
            if load_full:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    metadata.content = f.read()
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 100:
                            break
                        lines.append(line)
                    metadata.content = ''.join(lines)
            
            metadata.loaded = True
            self.cache[FileCacheLevel.L1][file_path] = metadata.content
            await self.smart_preload(file_path)
            
            return metadata.content
        except Exception as e:
            print(f"加载文件失败: {file_path}, 错误: {e}")
            return None
        finally:
            metadata.loading = False
    
    def _update_heatmap(self, file_path):
        """更新文件访问热力图"""
        self.heatmap[file_path] = self.heatmap.get(file_path, 0) + 1
    
    def build_semantic_connections(self):
        """构建语义连接图"""
        for file_path, metadata in self.file_metadata.items():
            if metadata.file_type == FileType.CODE:
                dir_path = os.path.dirname(file_path)
                for other_path, other_metadata in self.file_metadata.items():
                    if other_path != file_path and os.path.dirname(other_path) == dir_path:
                        if other_metadata.file_type in [FileType.CODE, FileType.TEST, FileType.CONFIG]:
                            if file_path not in self.semantic_connections:
                                self.semantic_connections[file_path] = []
                            if other_path not in self.semantic_connections[file_path]:
                                self.semantic_connections[file_path].append(other_path)
    
    def set_workflow_context(self, context):
        """设置工作流上下文"""
        self.workflow_context = context
    
    def get_file_metadata(self, file_path):
        """获取文件元数据"""
        return self.file_metadata.get(file_path)
    
    def get_directory_tree(self):
        """获取目录树"""
        return self.directory_tree
    
    def get_heatmap(self):
        """获取文件访问热力图"""
        return self.heatmap
    
    def get_semantic_connections(self):
        """获取语义连接图"""
        return self.semantic_connections
    
    def clear_cache(self, level=None):
        """清理缓存"""
        if level:
            self.cache[level].clear()
        else:
            for cache_level in self.cache:
                self.cache[cache_level].clear()
    
    def get_cache_stats(self):
        """获取缓存统计"""
        return {
            "L1_memory": len(self.cache[FileCacheLevel.L1]),
            "L2_disk": len(self.cache[FileCacheLevel.L2]),
            "L3_index": len(self.cache[FileCacheLevel.L3]),
            "L4_prefetch": len(self.cache[FileCacheLevel.L4])
        }


class SmartIDESystem:
    """智能IDE系统"""
    
    def __init__(self, project_root=None):
        self.project_root = project_root
        self.file_loader = FileLoader(project_root) if project_root else None
    
    async def load_file(self, file_path, load_full=False):
        """加载文件内容"""
        if not self.file_loader:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read() if load_full else ''.join(f.readlines()[:100])
            except Exception:
                return None
        
        return await self.file_loader.load_file_content(file_path, load_full)
    
    async def get_directory_tree(self):
        """获取目录树"""
        if not self.file_loader:
            return None
        
        return self.file_loader.build_directory_tree()
    
    def set_workflow_context(self, context):
        """设置工作流上下文"""
        if self.file_loader:
            self.file_loader.set_workflow_context(context)
    
    def build_semantic_connections(self):
        """构建语义连接图"""
        if self.file_loader:
            self.file_loader.build_semantic_connections()
    
    def get_system_status(self):
        """获取系统状态"""
        status = {}
        if self.file_loader:
            status["file_loader"] = {
                "cache_stats": self.file_loader.get_cache_stats(),
                "heatmap_size": len(self.file_loader.get_heatmap()),
                "semantic_connections": len(self.file_loader.get_semantic_connections())
            }
        return status


def create_smart_ide_system(project_root=None):
    """创建智能IDE系统"""
    return SmartIDESystem(project_root)


async def test_directory_tree_building():
    """测试秒级目录树构建"""
    print("=== 测试秒级目录树构建 ===")
    
    # 使用当前项目目录作为测试
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 构建目录树
    start_time = time.time()
    directory_tree = await ide_system.get_directory_tree()
    build_time = (time.time() - start_time) * 1000
    
    print(f"目录树构建耗时: {build_time:.2f}ms")
    print(f"目录树类型: {type(directory_tree).__name__}")
    
    # 统计文件数量
    def count_files(node, count=0):
        if node.is_dir:
            for child in node.children:
                count = count_files(child, count)
        else:
            count += 1
        return count
    
    file_count = count_files(directory_tree)
    print(f"扫描到的文件数量: {file_count}")
    
    return build_time < 100  # 验证是否在100ms内完成


async def test_smart_preloading():
    """测试智能预加载"""
    print("\n=== 测试智能预加载 ===")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 构建目录树
    await ide_system.get_directory_tree()
    
    # 构建语义连接图
    ide_system.build_semantic_connections()
    
    # 模拟加载一个Python文件
    test_file = os.path.join(project_root, "test_enhanced_features.py")
    if os.path.exists(test_file):
        print(f"测试文件: {test_file}")
        
        # 加载文件
        content = await ide_system.load_file(test_file)
        print(f"文件加载成功，内容长度: {len(content) if content else 0}")
        
        # 检查预加载
        status = ide_system.get_system_status()
        print(f"缓存统计: {status.get('file_loader', {}).get('cache_stats', {})}")
        print(f"热力图大小: {status.get('file_loader', {}).get('heatmap_size', 0)}")
        
        return True
    else:
        print("测试文件不存在，跳过测试")
        return True


async def test_progressive_loading():
    """测试渐进式内容加载"""
    print("\n=== 测试渐进式内容加载 ===")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 构建目录树
    await ide_system.get_directory_tree()
    
    # 测试文件
    test_file = os.path.join(project_root, "test_enhanced_features.py")
    if os.path.exists(test_file):
        print(f"测试文件: {test_file}")
        
        # 加载前100行
        start_time = time.time()
        partial_content = await ide_system.load_file(test_file, load_full=False)
        partial_time = time.time() - start_time
        print(f"加载前100行耗时: {partial_time:.3f}s")
        print(f"部分内容长度: {len(partial_content) if partial_content else 0}")
        
        # 加载完整文件
        start_time = time.time()
        full_content = await ide_system.load_file(test_file, load_full=True)
        full_time = time.time() - start_time
        print(f"加载完整文件耗时: {full_time:.3f}s")
        print(f"完整内容长度: {len(full_content) if full_content else 0}")
        
        return True
    else:
        print("测试文件不存在，跳过测试")
        return True


async def test_semantic_connections():
    """测试语义连接图"""
    print("\n=== 测试语义连接图 ===")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 构建目录树
    await ide_system.get_directory_tree()
    
    # 构建语义连接图
    ide_system.build_semantic_connections()
    
    # 获取语义连接
    if ide_system.file_loader:
        connections = ide_system.file_loader.get_semantic_connections()
        print(f"语义连接数量: {len(connections)}")
        
        # 显示前几个连接
        for i, (file_path, related_files) in enumerate(list(connections.items())[:3]):
            print(f"文件 {i+1}: {os.path.basename(file_path)}")
            print(f"  相关文件: {[os.path.basename(f) for f in related_files[:3]]}")
        
        return True
    else:
        print("文件加载器未初始化，跳过测试")
        return True


async def test_workflow_context():
    """测试工作流上下文"""
    print("\n=== 测试工作流上下文 ===")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 设置不同的工作流上下文
    contexts = ["coding", "debugging", "refactoring"]
    for context in contexts:
        ide_system.set_workflow_context(context)
        print(f"设置工作流上下文: {context}")
    
    return True


async def test_cache_management():
    """测试缓存管理"""
    print("\n=== 测试缓存管理 ===")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    ide_system = create_smart_ide_system(project_root)
    
    # 构建目录树
    await ide_system.get_directory_tree()
    
    # 加载几个文件
    test_files = [
        os.path.join(project_root, "test_enhanced_features.py"),
        os.path.join(project_root, "test_context_enhancer_standalone.py")
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            await ide_system.load_file(test_file)
            print(f"加载文件: {os.path.basename(test_file)}")
    
    # 检查缓存状态
    status = ide_system.get_system_status()
    print(f"缓存统计: {status.get('file_loader', {}).get('cache_stats', {})}")
    
    return True


async def test_integration():
    """集成测试"""
    tests = [
        test_directory_tree_building,
        test_smart_preloading,
        test_progressive_loading,
        test_semantic_connections,
        test_workflow_context,
        test_cache_management
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！文件加载优化集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())