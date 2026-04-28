"""
ProjectMemoryManager - 项目记忆管理器

借鉴 Trellis 的核心哲学：Write Conventions Once，自动注入上下文。

核心功能：
1. 创建项目规范（.trellis/spec/）
2. 创建项目记忆（.trellis/memory/）
3. 会话开始自动注入上下文
4. 支持多项目隔离

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import os
import json
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time


class MemoryType(Enum):
    """记忆类型"""
    SPEC = "spec"           # 规范
    CONTEXT = "context"     # 上下文
    HISTORY = "history"     # 历史记录
    KNOWLEDGE = "knowledge" # 知识
    TEMPLATE = "template"   # 模板


@dataclass
class ProjectSpec:
    """项目规范"""
    project_id: str
    name: str
    description: str = ""
    conventions: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())


@dataclass
class ProjectMemory:
    """项目记忆"""
    project_id: str
    memory_id: str
    type: MemoryType
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())


class ProjectMemoryManager:
    """
    项目记忆管理器
    
    核心特性：
    1. 创建项目规范（.trellis/spec/）
    2. 创建项目记忆（.trellis/memory/）
    3. 会话开始自动注入上下文
    4. 支持多项目隔离
    5. Write Conventions Once，自动复用
    """
    
    def __init__(self, base_path: str = ".trellis"):
        self._logger = logger.bind(component="ProjectMemoryManager")
        
        # 基础路径
        self._base_path = base_path
        self._spec_path = os.path.join(base_path, "spec")
        self._memory_path = os.path.join(base_path, "memory")
        
        # 内存缓存
        self._spec_cache: Dict[str, ProjectSpec] = {}
        self._memory_cache: Dict[str, Dict[str, ProjectMemory]] = {}
        
        # 初始化目录结构
        self._init_directories()
        
        self._logger.info(f"✅ ProjectMemoryManager 初始化完成 (base_path={base_path})")
    
    def _init_directories(self):
        """初始化目录结构"""
        os.makedirs(self._spec_path, exist_ok=True)
        os.makedirs(self._memory_path, exist_ok=True)
        self._logger.debug(f"📁 初始化目录: {self._base_path}")
    
    def create_project(self, project_id: str, name: str, description: str = "") -> ProjectSpec:
        """
        创建项目
        
        Args:
            project_id: 项目ID
            name: 项目名称
            description: 项目描述
        
        Returns:
            项目规范对象
        """
        spec = ProjectSpec(
            project_id=project_id,
            name=name,
            description=description,
            conventions={},
            settings={}
        )
        
        # 保存到文件
        self._save_spec(spec)
        
        # 添加到缓存
        self._spec_cache[project_id] = spec
        
        # 创建项目记忆目录
        project_memory_path = os.path.join(self._memory_path, project_id)
        os.makedirs(project_memory_path, exist_ok=True)
        
        self._logger.info(f"📋 创建项目: {project_id} ({name})")
        return spec
    
    def get_project(self, project_id: str) -> Optional[ProjectSpec]:
        """获取项目规范"""
        # 先从缓存获取
        if project_id in self._spec_cache:
            return self._spec_cache[project_id]
        
        # 从文件加载
        spec = self._load_spec(project_id)
        if spec:
            self._spec_cache[project_id] = spec
        
        return spec
    
    def delete_project(self, project_id: str):
        """删除项目"""
        # 删除缓存
        if project_id in self._spec_cache:
            del self._spec_cache[project_id]
        if project_id in self._memory_cache:
            del self._memory_cache[project_id]
        
        # 删除文件
        spec_file = os.path.join(self._spec_path, f"{project_id}.json")
        if os.path.exists(spec_file):
            os.remove(spec_file)
        
        # 删除记忆目录
        project_memory_path = os.path.join(self._memory_path, project_id)
        if os.path.exists(project_memory_path):
            import shutil
            shutil.rmtree(project_memory_path)
        
        self._logger.info(f"🗑️ 删除项目: {project_id}")
    
    def update_project(self, project_id: str, **kwargs):
        """更新项目"""
        spec = self.get_project(project_id)
        if not spec:
            return
        
        if 'name' in kwargs:
            spec.name = kwargs['name']
        if 'description' in kwargs:
            spec.description = kwargs['description']
        if 'conventions' in kwargs:
            spec.conventions.update(kwargs['conventions'])
        if 'settings' in kwargs:
            spec.settings.update(kwargs['settings'])
        
        spec.updated_at = time.time()
        self._save_spec(spec)
        
        self._logger.debug(f"🔄 更新项目: {project_id}")
    
    def add_convention(self, project_id: str, key: str, value: Any):
        """添加规范"""
        spec = self.get_project(project_id)
        if spec:
            spec.conventions[key] = value
            spec.updated_at = time.time()
            self._save_spec(spec)
            self._logger.debug(f"➕ 添加规范: {project_id}.{key}")
    
    def get_convention(self, project_id: str, key: str, default: Any = None) -> Any:
        """获取规范"""
        spec = self.get_project(project_id)
        return spec.conventions.get(key, default) if spec else default
    
    def add_memory(self, project_id: str, memory_id: str, type: MemoryType, content: Dict[str, Any], metadata: Dict[str, Any] = None):
        """
        添加项目记忆
        
        Args:
            project_id: 项目ID
            memory_id: 记忆ID
            type: 记忆类型
            content: 记忆内容
            metadata: 元数据
        """
        memory = ProjectMemory(
            project_id=project_id,
            memory_id=memory_id,
            type=type,
            content=content,
            metadata=metadata or {}
        )
        
        # 确保项目缓存存在
        if project_id not in self._memory_cache:
            self._memory_cache[project_id] = {}
        
        # 添加到缓存
        self._memory_cache[project_id][memory_id] = memory
        
        # 保存到文件
        self._save_memory(memory)
        
        self._logger.debug(f"💾 添加记忆: {project_id}/{memory_id} ({type.value})")
    
    def get_memory(self, project_id: str, memory_id: str) -> Optional[ProjectMemory]:
        """获取项目记忆"""
        # 先从缓存获取
        if project_id in self._memory_cache and memory_id in self._memory_cache[project_id]:
            return self._memory_cache[project_id][memory_id]
        
        # 从文件加载
        memory = self._load_memory(project_id, memory_id)
        if memory:
            if project_id not in self._memory_cache:
                self._memory_cache[project_id] = {}
            self._memory_cache[project_id][memory_id] = memory
        
        return memory
    
    def delete_memory(self, project_id: str, memory_id: str):
        """删除项目记忆"""
        # 删除缓存
        if project_id in self._memory_cache and memory_id in self._memory_cache[project_id]:
            del self._memory_cache[project_id][memory_id]
        
        # 删除文件
        memory_file = self._get_memory_file_path(project_id, memory_id)
        if os.path.exists(memory_file):
            os.remove(memory_file)
        
        self._logger.debug(f"🗑️ 删除记忆: {project_id}/{memory_id}")
    
    def list_memories(self, project_id: str, type: Optional[MemoryType] = None) -> List[ProjectMemory]:
        """列出项目记忆"""
        memories = []
        
        # 先检查缓存
        if project_id in self._memory_cache:
            for memory in self._memory_cache[project_id].values():
                if type is None or memory.type == type:
                    memories.append(memory)
        
        # 如果缓存为空，从文件加载
        if not memories:
            project_memory_path = os.path.join(self._memory_path, project_id)
            if os.path.exists(project_memory_path):
                for filename in os.listdir(project_memory_path):
                    if filename.endswith('.json'):
                        memory_id = filename[:-5]
                        memory = self._load_memory(project_id, memory_id)
                        if memory and (type is None or memory.type == type):
                            memories.append(memory)
        
        return memories
    
    def inject_context(self, project_id: str) -> Dict[str, Any]:
        """
        注入项目上下文
        
        在会话开始时自动调用，将项目规范和记忆注入到上下文中。
        
        Returns:
            上下文字典
        """
        context = {}
        
        # 获取项目规范
        spec = self.get_project(project_id)
        if spec:
            context['project'] = {
                'id': spec.project_id,
                'name': spec.name,
                'description': spec.description,
                'conventions': spec.conventions,
                'settings': spec.settings
            }
        
        # 获取所有记忆
        memories = self.list_memories(project_id)
        if memories:
            context['memories'] = {}
            for memory in memories:
                context['memories'][memory.memory_id] = {
                    'type': memory.type.value,
                    'content': memory.content,
                    'metadata': memory.metadata
                }
        
        self._logger.debug(f"📥 注入上下文: {project_id} (记忆数: {len(memories)})")
        return context
    
    def _save_spec(self, spec: ProjectSpec):
        """保存项目规范到文件"""
        spec_file = os.path.join(self._spec_path, f"{spec.project_id}.json")
        with open(spec_file, 'w', encoding='utf-8') as f:
            json.dump({
                'project_id': spec.project_id,
                'name': spec.name,
                'description': spec.description,
                'conventions': spec.conventions,
                'settings': spec.settings,
                'created_at': spec.created_at,
                'updated_at': spec.updated_at
            }, f, ensure_ascii=False, indent=2)
    
    def _load_spec(self, project_id: str) -> Optional[ProjectSpec]:
        """从文件加载项目规范"""
        spec_file = os.path.join(self._spec_path, f"{project_id}.json")
        if not os.path.exists(spec_file):
            return None
        
        with open(spec_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ProjectSpec(
            project_id=data['project_id'],
            name=data['name'],
            description=data.get('description', ''),
            conventions=data.get('conventions', {}),
            settings=data.get('settings', {}),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time())
        )
    
    def _save_memory(self, memory: ProjectMemory):
        """保存记忆到文件"""
        memory_file = self._get_memory_file_path(memory.project_id, memory.memory_id)
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump({
                'project_id': memory.project_id,
                'memory_id': memory.memory_id,
                'type': memory.type.value,
                'content': memory.content,
                'metadata': memory.metadata,
                'created_at': memory.created_at,
                'updated_at': memory.updated_at
            }, f, ensure_ascii=False, indent=2)
    
    def _load_memory(self, project_id: str, memory_id: str) -> Optional[ProjectMemory]:
        """从文件加载记忆"""
        memory_file = self._get_memory_file_path(project_id, memory_id)
        if not os.path.exists(memory_file):
            return None
        
        with open(memory_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ProjectMemory(
            project_id=data['project_id'],
            memory_id=data['memory_id'],
            type=MemoryType(data['type']),
            content=data.get('content', {}),
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time())
        )
    
    def _get_memory_file_path(self, project_id: str, memory_id: str) -> str:
        """获取记忆文件路径"""
        project_memory_path = os.path.join(self._memory_path, project_id)
        os.makedirs(project_memory_path, exist_ok=True)
        return os.path.join(project_memory_path, f"{memory_id}.json")
    
    def list_projects(self) -> List[str]:
        """列出所有项目ID"""
        project_ids = []
        
        # 从缓存获取
        project_ids.extend(self._spec_cache.keys())
        
        # 从文件获取
        if os.path.exists(self._spec_path):
            for filename in os.listdir(self._spec_path):
                if filename.endswith('.json'):
                    project_id = filename[:-5]
                    if project_id not in project_ids:
                        project_ids.append(project_id)
        
        return project_ids
    
    def export_project(self, project_id: str, export_path: str):
        """导出项目"""
        spec = self.get_project(project_id)
        if not spec:
            return
        
        export_data = {
            'spec': {
                'project_id': spec.project_id,
                'name': spec.name,
                'description': spec.description,
                'conventions': spec.conventions,
                'settings': spec.settings
            },
            'memories': []
        }
        
        # 添加所有记忆
        memories = self.list_memories(project_id)
        for memory in memories:
            export_data['memories'].append({
                'memory_id': memory.memory_id,
                'type': memory.type.value,
                'content': memory.content,
                'metadata': memory.metadata
            })
        
        # 保存导出文件
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, 'w', encoding='utf-8') as f:
            yaml.dump(export_data, f, allow_unicode=True, default_flow_style=False)
        
        self._logger.info(f"📤 导出项目: {project_id} -> {export_path}")
    
    def import_project(self, import_path: str) -> str:
        """导入项目"""
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = yaml.safe_load(f)
        
        spec_data = import_data.get('spec', {})
        project_id = spec_data.get('project_id', f"imported_{int(time.time())}")
        
        # 创建项目
        self.create_project(
            project_id=project_id,
            name=spec_data.get('name', 'Unnamed Project'),
            description=spec_data.get('description', '')
        )
        
        # 更新规范和设置
        if 'conventions' in spec_data:
            self.update_project(project_id, conventions=spec_data['conventions'])
        if 'settings' in spec_data:
            self.update_project(project_id, settings=spec_data['settings'])
        
        # 导入记忆
        for memory_data in import_data.get('memories', []):
            self.add_memory(
                project_id=project_id,
                memory_id=memory_data['memory_id'],
                type=MemoryType(memory_data['type']),
                content=memory_data.get('content', {}),
                metadata=memory_data.get('metadata', {})
            )
        
        self._logger.info(f"📥 导入项目: {import_path} -> {project_id}")
        return project_id


# 创建全局实例
project_memory_manager = ProjectMemoryManager()


def get_project_memory_manager() -> ProjectMemoryManager:
    """获取项目记忆管理器实例"""
    return project_memory_manager


# 测试函数
async def test_project_memory_manager():
    """测试项目记忆管理器"""
    import sys
    import tempfile
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ProjectMemoryManager")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = ProjectMemoryManager(base_path=os.path.join(tmp_dir, ".trellis"))
        
        # 1. 创建项目
        print("\n[1] 测试创建项目...")
        spec = manager.create_project(
            project_id="test_project",
            name="测试项目",
            description="这是一个测试项目"
        )
        print(f"    ✓ 创建项目: {spec.project_id}")
        print(f"    ✓ 项目名称: {spec.name}")
        
        # 2. 添加规范
        print("\n[2] 测试添加规范...")
        manager.add_convention("test_project", "code_style", "PEP8")
        manager.add_convention("test_project", "language", "Python")
        convention = manager.get_convention("test_project", "code_style")
        print(f"    ✓ 添加规范: code_style = {convention}")
        
        # 3. 添加记忆
        print("\n[3] 测试添加记忆...")
        manager.add_memory(
            project_id="test_project",
            memory_id="requirements",
            type=MemoryType.KNOWLEDGE,
            content={"python": "3.11+", "pyqt6": "*"},
            metadata={"source": "requirements.txt"}
        )
        memory = manager.get_memory("test_project", "requirements")
        print(f"    ✓ 添加记忆: {memory.memory_id} ({memory.type.value})")
        
        # 4. 列出记忆
        print("\n[4] 测试列出记忆...")
        memories = manager.list_memories("test_project")
        print(f"    ✓ 记忆数量: {len(memories)}")
        
        # 5. 注入上下文
        print("\n[5] 测试注入上下文...")
        context = manager.inject_context("test_project")
        print(f"    ✓ 上下文包含项目信息: {'project' in context}")
        print(f"    ✓ 上下文包含记忆: {'memories' in context}")
        
        # 6. 测试导出导入
        print("\n[6] 测试导出导入...")
        export_path = os.path.join(tmp_dir, "export.yaml")
        manager.export_project("test_project", export_path)
        print(f"    ✓ 导出项目成功")
        
        imported_id = manager.import_project(export_path)
        print(f"    ✓ 导入项目成功: {imported_id}")
        
        # 7. 列出项目
        print("\n[7] 测试列出项目...")
        projects = manager.list_projects()
        print(f"    ✓ 项目数量: {len(projects)}")
        print(f"    ✓ 项目列表: {projects}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_project_memory_manager())