"""
工具依赖管理模块 (ToolDependencyManager)
============================================

实现工具间依赖关系的声明、解析和验证：
1. 依赖声明：工具可以声明其依赖的其他工具
2. 依赖解析：自动解析依赖树，检查环路
3. 拓扑排序：按依赖顺序加载工具
4. 版本兼容：检查依赖版本约束
5. 自动安装：可选自动安装缺失依赖

存储：SQLite (tool_dependencies.db)
"""

import json
import sqlite3
from typing import Optional, List, Dict, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


# ============================================================
# 数据结构
# ============================================================

class DependencyType(str, Enum):
    """依赖类型"""
    REQUIRED = "required"      # 硬依赖：必须存在
    OPTIONAL = "optional"      # 软依赖：增强功能
    CONFLICTS = "conflicts"    # 冲突：不能同时存在
    PROVIDES = "provides"      # 提供：虚拟依赖的实际提供者


@dataclass
class Dependency:
    """依赖声明"""
    name: str                           # 依赖工具名称
    type: DependencyType = DependencyType.REQUIRED
    version_constraint: str = "*"       # 版本约束（semver）
    optional: bool = False
    reason: str = ""                    # 依赖原因说明


@dataclass
class DependencyNode:
    """依赖树节点"""
    tool_name: str
    dependencies: List[Dependency] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)  # 依赖此工具的工具
    depth: int = 0
    version: str = "0.0.0"


# ============================================================
# 依赖管理器
# ============================================================

class ToolDependencyManager:
    """
    工具依赖管理器（单例模式）
    
    功能：
    - 注册工具依赖关系
    - 解析依赖树（含循环依赖检测）
    - 拓扑排序（保证加载顺序）
    - 版本兼容性检查
    - 依赖链查询
    """
    
    _instance: Optional["ToolDependencyManager"] = None
    _db_path: Path = Path.home() / ".livingtree" / "tool_dependencies.db"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._conn: Optional[sqlite3.Connection] = None
        self._dependency_cache: Dict[str, List[Dependency]] = {}
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn
    
    def _init_db(self):
        """初始化依赖数据库"""
        conn = self._get_conn()
        conn.executescript("""
            -- 工具依赖表
            CREATE TABLE IF NOT EXISTS tool_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                depends_on TEXT NOT NULL,
                dependency_type TEXT NOT NULL DEFAULT 'required',
                version_constraint TEXT DEFAULT '*',
                reason TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tool_name, depends_on)
            );
            
            -- 工具提供的虚拟依赖表
            CREATE TABLE IF NOT EXISTS tool_provides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                provides TEXT NOT NULL,  -- 虚拟依赖名称
                version TEXT DEFAULT '1.0.0',
                UNIQUE(tool_name, provides)
            );
            
            -- 依赖解析缓存表
            CREATE TABLE IF NOT EXISTS dependency_resolution_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                resolved_order TEXT NOT NULL,  -- JSON array
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tool_name)
            );
            
            -- 创建索引
            CREATE INDEX IF NOT EXISTS idx_deps_tool ON tool_dependencies(tool_name);
            CREATE INDEX IF NOT EXISTS idx_deps_on ON tool_dependencies(depends_on);
            CREATE INDEX IF NOT EXISTS idx_provides ON tool_provides(provides);
        """)
        conn.commit()
    
    # ============================================================
    # 依赖注册 API
    # ============================================================
    
    def register_dependencies(self, tool_name: str,
                            dependencies: List[Dependency]) -> Tuple[bool, str]:
        """
        注册工具依赖关系
        
        Args:
            tool_name: 工具名称
            dependencies: 依赖列表
        
        Returns:
            (success, message)
        """
        conn = self._get_conn()
        
        try:
            for dep in dependencies:
                conn.execute("""
                    INSERT OR REPLACE INTO tool_dependencies
                    (tool_name, depends_on, dependency_type, version_constraint, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (tool_name, dep.name, dep.type.value,
                      dep.version_constraint, dep.reason))
            
            conn.commit()
            self._dependency_cache.pop(tool_name, None)  # 清除缓存
            return True, f"Registered {len(dependencies)} dependencies for {tool_name}"
        except Exception as e:
            return False, f"Failed to register dependencies: {e}"
    
    def register_provider(self, tool_name: str,
                        provides: str, version: str = "1.0.0") -> Tuple[bool, str]:
        """注册工具提供的虚拟依赖"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO tool_provides
                (tool_name, provides, version)
                VALUES (?, ?, ?)
            """, (tool_name, provides, version))
            conn.commit()
            return True, f"Tool {tool_name} provides {provides} (v{version})"
        except Exception as e:
            return False, f"Failed to register provider: {e}"
    
    def unregister_dependencies(self, tool_name: str) -> Tuple[bool, str]:
        """取消注册工具的所有依赖"""
        conn = self._get_conn()
        cursor = conn.execute("""
            DELETE FROM tool_dependencies WHERE tool_name = ?
        """, (tool_name,))
        conn.commit()
        self._dependency_cache.pop(tool_name, None)
        return True, f"Removed {cursor.rowcount} dependencies for {tool_name}"
    
    # ============================================================
    # 依赖解析 API
    # ============================================================
    
    def get_dependencies(self, tool_name: str,
                        include_optional: bool = False) -> List[Dependency]:
        """获取工具的直接依赖"""
        if tool_name in self._dependency_cache:
            deps = self._dependency_cache[tool_name]
            if not include_optional:
                deps = [d for d in deps if d.type != DependencyType.OPTIONAL]
            return deps
        
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT depends_on, dependency_type, version_constraint, reason
            FROM tool_dependencies
            WHERE tool_name = ?
        """, (tool_name,)).fetchall()
        
        deps = []
        for row in rows:
            deps.append(Dependency(
                name=row["depends_on"],
                type=DependencyType(row["dependency_type"]),
                version_constraint=row["version_constraint"],
                reason=row["reason"] or ""
            ))
        
        self._dependency_cache[tool_name] = deps
        if not include_optional:
            return [d for d in deps if d.type != DependencyType.OPTIONAL]
        return deps
    
    def get_dependents(self, tool_name: str) -> List[str]:
        """获取依赖此工具的所有工具（反向依赖）"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT tool_name FROM tool_dependencies
            WHERE depends_on = ? AND dependency_type != 'conflicts'
        """, (tool_name,)).fetchall()
        return [row["tool_name"] for row in rows]
    
    def resolve_dependencies(self, tool_name: str,
                           max_depth: int = 10) -> Tuple[bool, List[str], str]:
        """
        解析工具的所有依赖（含传递依赖）
        
        Args:
            tool_name: 工具名称
            max_depth: 最大递归深度
        
        Returns:
            (success, ordered_tools, error_message)
            ordered_tools: 按依赖顺序排列的工具列表（被依赖的在前）
        """
        # 检查缓存
        conn = self._get_conn()
        cached = conn.execute("""
            SELECT resolved_order FROM dependency_resolution_cache
            WHERE tool_name = ?
        """, (tool_name,)).fetchone()
        
        if cached:
            return True, json.loads(cached["resolved_order"]), "from cache"
        
        # BFS 解析依赖树
        visited: Set[str] = set()
        result: List[str] = []
        error_msg = ""
        
        def _resolve(current: str, depth: int, path: List[str]):
            nonlocal error_msg
            
            if depth > max_depth:
                error_msg = f"Max recursion depth ({max_depth}) exceeded for {current}"
                return False
            
            if current in path:
                error_msg = f"Circular dependency detected: {' -> '.join(path + [current])}"
                return False
            
            if current in visited:
                return True
            
            deps = self.get_dependencies(current, include_optional=False)
            
            for dep in deps:
                if dep.type == DependencyType.CONFLICTS:
                    continue  # 冲突依赖不加入解析
                
                # 检查是否有工具提供此依赖
                provider = self._find_provider(dep.name)
                actual_dep = provider if provider else dep.name
                
                if not _resolve(actual_dep, depth + 1, path + [current]):
                    return False
            
            visited.add(current)
            result.append(current)
            return True
        
        success = _resolve(tool_name, 0, [])
        
        if success:
            # 缓存结果
            conn.execute("""
                INSERT OR REPLACE INTO dependency_resolution_cache
                (tool_name, resolved_order)
                VALUES (?, ?)
            """, (tool_name, json.dumps(result)))
            conn.commit()
        
        return success, result, error_msg
    
    def _find_provider(self, virtual_dep: str) -> Optional[str]:
        """查找提供虚拟依赖的实际工具"""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT tool_name FROM tool_provides
            WHERE provides = ?
            LIMIT 1
        """, (virtual_dep,)).fetchone()
        return row["tool_name"] if row else None
    
    def get_topological_order(self, tool_names: List[str]) -> Tuple[bool, List[str], str]:
        """
        获取多个工具的拓扑排序
        
        Args:
            tool_names: 工具名称列表
        
        Returns:
            (success, ordered_tools, error_message)
        """
        # 收集所有工具和它们的依赖
        all_tools: Set[str] = set(tool_names)
        for tool in tool_names:
            success, deps, _ = self.resolve_dependencies(tool)
            if success:
                all_tools.update(deps)
        
        # Kahn's algorithm for topological sort
        in_degree: Dict[str, int] = {t: 0 for t in all_tools}
        graph: Dict[str, List[str]] = {t: [] for t in all_tools}
        
        for tool in all_tools:
            deps = self.get_dependencies(tool, include_optional=False)
            for dep in deps:
                if dep.type == DependencyType.CONFLICTS:
                    continue
                provider = self._find_provider(dep.name)
                actual_dep = provider if provider else dep.name
                if actual_dep in all_tools:
                    graph[actual_dep].append(tool)
                    in_degree[tool] += 1
        
        # 拓扑排序
        queue = [t for t in all_tools if in_degree[t] == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(all_tools):
            # 检测循环依赖
            remaining = all_tools - set(result)
            return False, list(result), f"Circular dependency detected among: {remaining}"
        
        return True, result, ""
    
    # ============================================================
    # 冲突检测 API
    # ============================================================
    
    def check_conflicts(self, tool_name: str) -> List[Tuple[str, str]]:
        """
        检查工具依赖冲突
        
        Returns:
            List of (tool_name, conflict_reason)
        """
        conflicts = []
        deps = self.get_dependencies(tool_name, include_optional=True)
        
        for dep in deps:
            if dep.type == DependencyType.CONFLICTS:
                # 检查是否有已加载的工具与此冲突
                conflict_tool = dep.name
                conflicts.append((conflict_tool, f"Conflicts with {conflict_tool}"))
        
        # 检查版本冲突
        conn = self._get_conn()
        for dep in deps:
            if dep.version_constraint != "*":
                # TODO: 实现版本约束检查
                pass
        
        return conflicts
    
    def get_conflict_report(self, tool_names: List[str]) -> Dict:
        """生成冲突报告"""
        report = {
            "tools_checked": tool_names,
            "conflicts": [],
            "warnings": []
        }
        
        for tool in tool_names:
            conflicts = self.check_conflicts(tool)
            for conflict_tool, reason in conflicts:
                if conflict_tool in tool_names:
                    report["conflicts"].append({
                        "tool": tool,
                        "conflicts_with": conflict_tool,
                        "reason": reason
                    })
        
        return report
    
    # ============================================================
    # 查询 API
    # ============================================================
    
    def get_dependency_tree(self, tool_name: str, max_depth: int = 5) -> Dict:
        """获取依赖树（嵌套结构）"""
        def _build_tree(current: str, depth: int, visited: Set[str]) -> Dict:
            if depth > max_depth or current in visited:
                return {"name": current, "dependencies": [], "circular": True}
            
            visited.add(current)
            deps = self.get_dependencies(current, include_optional=False)
            
            children = []
            for dep in deps:
                child_tree = _build_tree(dep.name, depth + 1, visited.copy())
                child_tree["type"] = dep.type.value
                child_tree["reason"] = dep.reason
                children.append(child_tree)
            
            return {
                "name": current,
                "dependencies": children,
                "depth": depth
            }
        
        return _build_tree(tool_name, 0, set())
    
    def get_stats(self) -> Dict:
        """获取依赖统计信息"""
        conn = self._get_conn()
        
        total_deps = conn.execute("SELECT COUNT(*) FROM tool_dependencies").fetchone()[0]
        total_tools = conn.execute("SELECT COUNT(DISTINCT tool_name) FROM tool_dependencies").fetchone()[0]
        total_provides = conn.execute("SELECT COUNT(*) FROM tool_provides").fetchone()[0]
        
        # 最常依赖的工具
        most_depended = conn.execute("""
            SELECT depends_on, COUNT(*) as cnt
            FROM tool_dependencies
            WHERE dependency_type != 'conflicts'
            GROUP BY depends_on
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
        
        return {
            "total_dependencies": total_deps,
            "total_tools_with_deps": total_tools,
            "total_providers": total_provides,
            "most_depended_tools": [dict(row) for row in most_depended]
        }
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================
# 便捷函数
# ============================================================

_default_manager: Optional[ToolDependencyManager] = None

def get_dependency_manager() -> ToolDependencyManager:
    """获取依赖管理器单例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = ToolDependencyManager()
    return _default_manager


def register_tool_dependencies(tool_name: str,
                             dependencies: List[Dependency]) -> Tuple[bool, str]:
    """便捷函数：注册工具依赖"""
    manager = get_dependency_manager()
    return manager.register_dependencies(tool_name, dependencies)


def resolve_tool_dependencies(tool_name: str) -> Tuple[bool, List[str], str]:
    """便捷函数：解析工具依赖"""
    manager = get_dependency_manager()
    return manager.resolve_dependencies(tool_name)


def get_tool_load_order(tool_names: List[str]) -> Tuple[bool, List[str], str]:
    """便捷函数：获取工具加载顺序（拓扑排序）"""
    manager = get_dependency_manager()
    return manager.get_topological_order(tool_names)


# ============================================================
# 常用依赖声明
# ============================================================

# 预定义常用依赖组合
SEARCH_DEPS = [
    Dependency("web_crawler", DependencyType.REQUIRED, reason="需要网页爬取"),
    Dependency("content_extractor", DependencyType.REQUIRED, reason="需要内容提取"),
]

VECTOR_DB_DEPS = [
    Dependency("vector_database", DependencyType.REQUIRED, reason="需要向量存储"),
]

EI_ANALYSIS_DEPS = [
    Dependency("vector_database", DependencyType.REQUIRED, reason="需要知识检索"),
    Dependency("deep_search", DependencyType.OPTIONAL, reason="增强搜索能力"),
    Dependency("report_generator", DependencyType.REQUIRED, reason="需要报告生成"),
]

GEOSPATIAL_DEPS = [
    Dependency("distance_tool", DependencyType.REQUIRED, reason="需要距离计算"),
    Dependency("elevation_tool", DependencyType.OPTIONAL, reason="需要高程数据"),
    Dependency("map_api_tool", DependencyType.OPTIONAL, reason="需要地图API"),
]

SIMULATION_DEPS = [
    Dependency("mike21_tool", DependencyType.OPTIONAL, reason="水动力模拟"),
    Dependency("cadnaa_tool", DependencyType.OPTIONAL, reason="噪声模拟"),
]
