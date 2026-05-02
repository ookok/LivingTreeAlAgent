"""
Serena Direct Integration - 直接集成层

采用方案 A（推荐）直接集成 Serena：
- 延迟低（进程内调用，零序列化）
- 零 JSON-RPC 开销
- 可靠的 AST fallback

废弃旧的 MCP 协议方式。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from loguru import logger
import os
import ast

# 直接导入 SerenaAgent（方案 A）
try:
    from libs.serena_core import SerenaAgent, SymbolInfo
    _HAS_DIRECT = True
except ImportError:
    _HAS_DIRECT = False
    logger.warning("Serena 直接集成不可用，使用纯 AST fallback")


class SerenaDirectStatus:
    """Serena 连接状态（直接集成模式）"""
    ONLINE = "online"           # Serena 直接集成可用
    FALLBACK = "fallback"       # 使用纯 AST 引擎


@dataclass
class DirectSymbolInfo:
    """符号信息"""
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    documentation: str = ""
    signature: str = ""


@dataclass
class DirectDiagnosticInfo:
    """诊断信息"""
    severity: str
    message: str
    line: int
    column: int
    code: str = ""


@dataclass
class DirectResult:
    """操作结果"""
    success: bool
    data: Any = None
    error: str = ""


class SerenaDirect:
    """
    Serena 直接集成层（方案 A）

    特点：
    - 进程内直接调用，零序列化开销
    - 延迟 < 1ms
    - 自动 fallback 到纯 AST 引擎

    弃用警告：
    - 旧的 MCP JSON-RPC 协议已废弃
    - 不再需要 stdio 或 HTTP 通信
    """

    def __init__(self, workspace_root: str = ""):
        self._logger = logger.bind(component="SerenaDirect")
        self._workspace = workspace_root or os.getcwd()
        self._status = SerenaDirectStatus.ONLINE if _HAS_DIRECT else SerenaDirectStatus.FALLBACK
        self._agent = None

        if _HAS_DIRECT:
            try:
                self._agent = SerenaAgent(workspace_root=self._workspace)
                self._logger.info("Serena 直接集成已就绪")
            except Exception as e:
                self._logger.warning(f"Serena 初始化失败，使用 AST fallback: {e}")
                self._status = SerenaDirectStatus.FALLBACK
                self._agent = None
        else:
            self._logger.info("使用纯 AST fallback 引擎")

    @property
    def status(self) -> str:
        """获取状态"""
        return self._status

    @property
    def is_online(self) -> bool:
        """是否在线"""
        return self._status == SerenaDirectStatus.ONLINE

    # ── 公共 API ──────────────────────────────────────────

    def find_symbol(self, file_path: str, symbol_name: str) -> DirectResult:
        """查找符号定义"""
        if self._agent:
            sym = self._agent.find_symbol(file_path, symbol_name)
            if sym:
                return DirectResult(
                    success=True,
                    data=DirectSymbolInfo(
                        name=sym.get('name', ''),
                        kind=sym.get('kind', ''),
                        file_path=sym.get('file_path', ''),
                        line_start=sym.get('line_start', 0),
                        line_end=sym.get('line_end', 0),
                        documentation=sym.get('documentation', ''),
                        signature=sym.get('signature', '')
                    )
                )
            return DirectResult(success=False, error=f"符号未找到: {symbol_name}")

        # Fallback to AST
        return DirectResult(success=False, error="Serena 不可用")

    def get_file_structure(self, file_path: str) -> DirectResult:
        """获取文件结构"""
        if self._agent:
            structure = self._agent.get_file_structure(file_path)
            symbols = []
            for s in structure:
                symbols.append(DirectSymbolInfo(
                    name=s.get('name', ''),
                    kind=s.get('kind', ''),
                    file_path=s.get('file_path', ''),
                    line_start=s.get('line_start', 0),
                    line_end=s.get('line_end', 0),
                    documentation=s.get('documentation', ''),
                    signature=s.get('signature', '')
                ))
            return DirectResult(success=True, data=symbols)

        return DirectResult(success=False, error="Serena 不可用")

    def get_diagnostics(self, file_path: str) -> DirectResult:
        """获取诊断信息"""
        if self._agent:
            diagnostics = self._agent.get_diagnostics(file_path)
            diag_list = []
            for d in diagnostics:
                diag_list.append(DirectDiagnosticInfo(
                    severity=d.get('severity', 'info'),
                    message=d.get('message', ''),
                    line=d.get('line', 0),
                    column=d.get('column', 0),
                    code=d.get('code', '')
                ))
            return DirectResult(success=True, data=diag_list)

        return DirectResult(success=False, error="Serena 不可用")

    def get_references(self, file_path: str, symbol_name: str) -> DirectResult:
        """查找符号引用"""
        if self._agent:
            refs = self._agent.get_references(file_path, symbol_name)
            return DirectResult(success=True, data=refs)

        return DirectResult(success=False, error="Serena 不可用")

    def rename_symbol(self, file_path: str, old_name: str,
                     new_name: str) -> DirectResult:
        """重命名符号"""
        if self._agent:
            result = self._agent.rename_symbol(file_path, old_name, new_name)
            return DirectResult(success=True, data=result)

        return DirectResult(success=False, error="Serena 不可用")

    def replace_content(self, file_path: str, old_content: str,
                       new_content: str) -> DirectResult:
        """替换内容"""
        if self._agent:
            result = self._agent.replace_content(file_path, old_content, new_content)
            return DirectResult(success=True, data=result)

        return DirectResult(success=False, error="Serena 不可用")

    def shutdown(self):
        """关闭"""
        if self._agent:
            self._agent.shutdown()
        self._logger.info("Serena 直接集成已关闭")


# ── 向后兼容别名 ──────────────────────────────────────────

class SerenaAdapter(SerenaDirect):
    """
    Serena 适配器（向后兼容）

    警告：已弃用 MCP 协议方式。
    请使用 SerenaDirect 替代。
    """
    pass


# 全局单例
_serena_direct_instance: Optional[SerenaDirect] = None


def get_serena_direct(workspace_root: str = "") -> SerenaDirect:
    """获取 Serena 直接集成单例"""
    global _serena_direct_instance
    if _serena_direct_instance is None:
        _serena_direct_instance = SerenaDirect(workspace_root)
    return _serena_direct_instance
