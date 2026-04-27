"""
工具权限控制模块 (ToolPermissionManager)
===========================================

实现三维权限控制：
1. 角色级权限：基于用户角色（admin/user/guest/api）
2. 智能体级权限：限制智能体可使用的工具范围
3. 操作级权限：控制工具的 read/write/admin 操作

权限决策顺序：
智能体权限 → 角色权限 → 操作权限 → 默认拒绝

存储：SQLite (tool_permissions.db)
"""

import json
import sqlite3
from typing import Optional, List, Dict, Set
from enum import Enum
from pathlib import Path

from client.src.business.tools.tool_result import ToolResult


# ============================================================
# 权限枚举
# ============================================================

class Role(str, Enum):
    """用户角色"""
    ADMIN = "admin"          # 管理员：所有权限
    USER = "user"            # 普通用户：大部分权限
    GUEST = "guest"          # 访客：只读权限
    API = "api"              # API调用：受限权限
    SERVICE = "service"      # 内部服务：跨服务调用


class Operation(str, Enum):
    """工具操作类型"""
    READ = "read"            # 读取操作（搜索、查询）
    WRITE = "write"          # 写入操作（创建、更新、删除）
    EXECUTE = "execute"      # 执行操作（运行、计算）
    ADMIN = "admin"          # 管理操作（配置、权限变更）


# 角色默认操作权限映射
ROLE_OPERATIONS: Dict[Role, Set[Operation]] = {
    Role.ADMIN: {Operation.READ, Operation.WRITE, Operation.EXECUTE, Operation.ADMIN},
    Role.USER: {Operation.READ, Operation.WRITE, Operation.EXECUTE},
    Role.GUEST: {Operation.READ},
    Role.API: {Operation.READ, Operation.EXECUTE},
    Role.SERVICE: {Operation.READ, Operation.WRITE, Operation.EXECUTE},
}


class ToolPermissionManager:
    """
    工具权限管理器（单例模式）
    
    功能：
    - 角色权限管理：基于角色的访问控制（RBAC）
    - 智能体权限管理：限制智能体可使用的工具
    - 操作权限管理：控制读写执行管理操作
    - 权限继承：智能体继承用户角色权限
    - 审计日志：记录权限决策和拒绝原因
    """
    
    _instance: Optional["ToolPermissionManager"] = None
    _db_path: Path = Path.home() / ".livingtree" / "tool_permissions.db"
    
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
        """初始化权限数据库"""
        conn = self._get_conn()
        conn.executescript("""
            -- 角色-工具权限表
            CREATE TABLE IF NOT EXISTS role_tool_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                granted_operations TEXT NOT NULL,  -- JSON array of operations
                granted_by TEXT DEFAULT 'system',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(role, tool_name)
            );
            
            -- 智能体-工具权限表
            CREATE TABLE IF NOT EXISTS agent_tool_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                granted_operations TEXT NOT NULL,
                granted_by TEXT DEFAULT 'system',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agent_id, tool_name)
            );
            
            -- 工具操作策略表（默认策略）
            CREATE TABLE IF NOT EXISTS tool_operation_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL UNIQUE,
                default_operations TEXT NOT NULL,  -- JSON array
                requires_approval BOOLEAN DEFAULT FALSE,
                risk_level TEXT DEFAULT 'low',  -- low/medium/high/critical
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- 权限审计日志
            CREATE TABLE IF NOT EXISTS permission_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role TEXT,
                agent_id TEXT,
                tool_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                allowed BOOLEAN NOT NULL,
                reason TEXT,
                context TEXT  -- JSON context
            );
            
            -- 创建索引
            CREATE INDEX IF NOT EXISTS idx_role_perm ON role_tool_permissions(role, tool_name);
            CREATE INDEX IF NOT EXISTS idx_agent_perm ON agent_tool_permissions(agent_id, tool_name);
            CREATE INDEX IF NOT EXISTS idx_audit_log ON permission_audit_log(timestamp, tool_name, allowed);
        """)
        conn.commit()
        self._init_default_policies()
    
    def _init_default_policies(self):
        """初始化默认工具操作策略"""
        defaults = [
            # (tool_name, default_operations, requires_approval, risk_level)
            ("web_search", ["read"], False, "low"),
            ("web_crawler", ["read"], False, "low"),
            ("deep_search", ["read"], False, "low"),
            ("vector_database", ["read", "write"], False, "low"),
            ("knowledge_graph", ["read", "write"], False, "medium"),
            ("task_decomposer", ["execute"], False, "low"),
            ("task_execution_engine", ["execute"], True, "medium"),
            ("expert_training", ["execute"], False, "medium"),
            ("skill_evolution", ["execute"], True, "high"),
            ("file_accessor", ["read", "write"], False, "medium"),
            ("system_command", ["execute"], True, "critical"),
            ("mike21_tool", ["execute"], False, "high"),
            ("cadnaa_tool", ["execute"], False, "high"),
        ]
        
        conn = self._get_conn()
        for tool_name, ops, requires_approval, risk_level in defaults:
            conn.execute("""
                INSERT OR IGNORE INTO tool_operation_policies
                (tool_name, default_operations, requires_approval, risk_level)
                VALUES (?, ?, ?, ?)
            """, (tool_name, json.dumps(ops), requires_approval, risk_level))
        conn.commit()
    
    # ============================================================
    # 权限检查 API
    # ============================================================
    
    def check_permission(
        self,
        tool_name: str,
        operation: Operation,
        role: Role = Role.USER,
        agent_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> ToolResult:
        """
        检查权限（核心方法）
        
        决策顺序：
        1. 智能体权限（如果指定了 agent_id）
        2. 角色权限
        3. 工具操作策略
        4. 默认拒绝
        
        Args:
            tool_name: 工具名称
            operation: 操作类型
            role: 用户角色
            agent_id: 智能体ID（可选）
            context: 上下文（用于审计）
        
        Returns:
            ToolResult: success=True 表示允许，False 表示拒绝
        """
        conn = self._get_conn()
        
        # 1. 检查智能体权限（最高优先级）
        if agent_id:
            agent_perm = conn.execute("""
                SELECT granted_operations FROM agent_tool_permissions
                WHERE agent_id = ? AND tool_name = ?
            """, (agent_id, tool_name)).fetchone()
            
            if agent_perm:
                ops = json.loads(agent_perm["granted_operations"])
                allowed = operation.value in ops
                self._audit_log(role, agent_id, tool_name, operation, allowed,
                              f"agent permission: {ops}", context)
                if allowed:
                    return ToolResult(success=True, data={"source": "agent", "agent_id": agent_id})
                else:
                    return ToolResult(success=False, error=f"Agent {agent_id} 无权执行 {operation.value} 操作")
        
        # 2. 检查角色-工具权限
        role_perm = conn.execute("""
            SELECT granted_operations FROM role_tool_permissions
            WHERE role = ? AND tool_name = ?
        """, (role.value, tool_name)).fetchone()
        
        if role_perm:
            ops = json.loads(role_perm["granted_operations"])
            allowed = operation.value in ops
            self._audit_log(role, agent_id, tool_name, operation, allowed,
                          f"role permission: {ops}", context)
            if allowed:
                return ToolResult(success=True, data={"source": "role", "role": role.value})
            else:
                return ToolResult(success=False, error=f"角色 {role.value} 无权对工具 {tool_name} 执行 {operation.value} 操作")
        
        # 3. 检查工具操作策略（默认权限）
        policy = conn.execute("""
            SELECT default_operations, requires_approval, risk_level
            FROM tool_operation_policies
            WHERE tool_name = ?
        """, (tool_name,)).fetchone()
        
        if policy:
            ops = json.loads(policy["default_operations"])
            allowed = operation.value in ops
            
            # 高风险操作需要额外检查
            if allowed and policy["requires_approval"]:
                allowed = self._check_approval(tool_name, operation, role, agent_id)
            
            self._audit_log(role, agent_id, tool_name, operation, allowed,
                           f"policy: {ops}, risk: {policy['risk_level']}", context)
            
            if allowed:
                return ToolResult(success=True, data={
                    "source": "policy",
                    "risk_level": policy["risk_level"],
                    "requires_approval": policy["requires_approval"]
                })
            else:
                return ToolResult(success=False, error=f"工具 {tool_name} 不允许 {operation.value} 操作（策略限制）")
        
        # 4. 默认拒绝（安全优先）
        self._audit_log(role, agent_id, tool_name, operation, False, "default deny", context)
        return ToolResult(success=False, error=f"工具 {tool_name} 未配置权限策略，默认拒绝")
    
    def _check_approval(self, tool_name: str, operation: Operation,
                       role: Role, agent_id: Optional[str]) -> bool:
        """检查是否需要审批（可扩展为工作流审批）"""
        # TODO: 集成审批工作流
        # 目前简单处理：admin 自动通过，其他需要审批
        return role == Role.ADMIN
    
    def _audit_log(self, role: Role, agent_id: Optional[str], tool_name: str,
                  operation: Operation, allowed: bool, reason: str,
                  context: Optional[Dict] = None):
        """记录权限审计日志"""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO permission_audit_log
            (role, agent_id, tool_name, operation, allowed, reason, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (role.value, agent_id, tool_name, operation.value,
              allowed, reason, json.dumps(context) if context else None))
        conn.commit()
    
    # ============================================================
    # 权限管理 API
    # ============================================================
    
    def grant_role_permission(self, role: Role, tool_name: str,
                            operations: List[Operation],
                            granted_by: str = "system") -> ToolResult:
        """授予角色工具权限"""
        conn = self._get_conn()
        ops = [op.value for op in operations]
        conn.execute("""
            INSERT OR REPLACE INTO role_tool_permissions
            (role, tool_name, granted_operations, granted_by)
            VALUES (?, ?, ?, ?)
        """, (role.value, tool_name, json.dumps(ops), granted_by))
        conn.commit()
        return ToolResult(success=True, data={"role": role.value, "tool": tool_name, "ops": ops})
    
    def revoke_role_permission(self, role: Role, tool_name: str) -> ToolResult:
        """撤销角色工具权限"""
        conn = self._get_conn()
        cursor = conn.execute("""
            DELETE FROM role_tool_permissions
            WHERE role = ? AND tool_name = ?
        """, (role.value, tool_name))
        conn.commit()
        return ToolResult(success=True, data={"deleted": cursor.rowcount})
    
    def grant_agent_permission(self, agent_id: str, tool_name: str,
                             operations: List[Operation],
                             granted_by: str = "system") -> ToolResult:
        """授予智能体工具权限"""
        conn = self._get_conn()
        ops = [op.value for op in operations]
        conn.execute("""
            INSERT OR REPLACE INTO agent_tool_permissions
            (agent_id, tool_name, granted_operations, granted_by)
            VALUES (?, ?, ?, ?)
        """, (agent_id, tool_name, json.dumps(ops), granted_by))
        conn.commit()
        return ToolResult(success=True, data={"agent": agent_id, "tool": tool_name, "ops": ops})
    
    def revoke_agent_permission(self, agent_id: str, tool_name: str) -> ToolResult:
        """撤销智能体工具权限"""
        conn = self._get_conn()
        cursor = conn.execute("""
            DELETE FROM agent_tool_permissions
            WHERE agent_id = ? AND tool_name = ?
        """, (agent_id, tool_name))
        conn.commit()
        return ToolResult(success=True, data={"deleted": cursor.rowcount})
    
    def set_tool_policy(self, tool_name: str, default_operations: List[Operation],
                       requires_approval: bool = False,
                       risk_level: str = "low") -> ToolResult:
        """设置工具操作策略"""
        conn = self._get_conn()
        ops = [op.value for op in default_operations]
        conn.execute("""
            INSERT OR REPLACE INTO tool_operation_policies
            (tool_name, default_operations, requires_approval, risk_level, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (tool_name, json.dumps(ops), requires_approval, risk_level))
        conn.commit()
        return ToolResult(success=True, data={"tool": tool_name, "ops": ops})
    
    # ============================================================
    # 查询 API
    # ============================================================
    
    def get_role_permissions(self, role: Role) -> Dict[str, List[str]]:
        """获取角色的所有工具权限"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT tool_name, granted_operations FROM role_tool_permissions
            WHERE role = ?
        """, (role.value,)).fetchall()
        return {row["tool_name"]: json.loads(row["granted_operations"]) for row in rows}
    
    def get_agent_permissions(self, agent_id: str) -> Dict[str, List[str]]:
        """获取智能体的所有工具权限"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT tool_name, granted_operations FROM agent_tool_permissions
            WHERE agent_id = ?
        """, (agent_id,)).fetchall()
        return {row["tool_name"]: json.loads(row["granted_operations"]) for row in rows}
    
    def get_tool_policy(self, tool_name: str) -> Optional[Dict]:
        """获取工具操作策略"""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT * FROM tool_operation_policies WHERE tool_name = ?
        """, (tool_name,)).fetchone()
        if row:
            return {
                "tool_name": row["tool_name"],
                "default_operations": json.loads(row["default_operations"]),
                "requires_approval": bool(row["requires_approval"]),
                "risk_level": row["risk_level"]
            }
        return None
    
    def get_audit_log(self, limit: int = 100, tool_name: Optional[str] = None,
                     allowed: Optional[bool] = None) -> List[Dict]:
        """获取权限审计日志"""
        conn = self._get_conn()
        query = "SELECT * FROM permission_audit_log WHERE 1=1"
        params = []
        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)
        if allowed is not None:
            query += " AND allowed = ?"
            params.append(allowed)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    
    # ============================================================
    # 便捷方法
    # ============================================================
    
    def can_read(self, tool_name: str, role: Role = Role.USER,
                agent_id: Optional[str] = None) -> bool:
        """检查读权限"""
        result = self.check_permission(tool_name, Operation.READ, role, agent_id)
        return result.success
    
    def can_write(self, tool_name: str, role: Role = Role.USER,
                 agent_id: Optional[str] = None) -> bool:
        """检查写权限"""
        result = self.check_permission(tool_name, Operation.WRITE, role, agent_id)
        return result.success
    
    def can_execute(self, tool_name: str, role: Role = Role.USER,
                   agent_id: Optional[str] = None) -> bool:
        """检查执行权限"""
        result = self.check_permission(tool_name, Operation.EXECUTE, role, agent_id)
        return result.success
    
    def can_admin(self, tool_name: str, role: Role = Role.USER,
                 agent_id: Optional[str] = None) -> bool:
        """检查管理权限"""
        result = self.check_permission(tool_name, Operation.ADMIN, role, agent_id)
        return result.success
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================
# 便捷函数
# ============================================================

_default_manager: Optional[ToolPermissionManager] = None

def get_permission_manager() -> ToolPermissionManager:
    """获取权限管理器单例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = ToolPermissionManager()
    return _default_manager


def check_tool_permission(tool_name: str, operation: Operation,
                         role: Role = Role.USER,
                         agent_id: Optional[str] = None) -> bool:
    """便捷函数：检查工具权限"""
    manager = get_permission_manager()
    result = manager.check_permission(tool_name, operation, role, agent_id)
    return result.success


def grant_tool_to_role(tool_name: str, role: Role,
                      operations: List[Operation]) -> ToolResult:
    """便捷函数：授予角色工具权限"""
    manager = get_permission_manager()
    return manager.grant_role_permission(role, tool_name, operations)


def grant_tool_to_agent(tool_name: str, agent_id: str,
                       operations: List[Operation]) -> ToolResult:
    """便捷函数：授予智能体工具权限"""
    manager = get_permission_manager()
    return manager.grant_agent_permission(agent_id, tool_name, operations)
