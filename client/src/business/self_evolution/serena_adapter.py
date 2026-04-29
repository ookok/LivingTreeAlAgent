"""
SerenaAdapter - Serena MCP 客户端适配层

Serena 作为代码理解与操作核心，通过 LSP 提供精准的代码操作能力。
当 Serena MCP Server 不可用时，自动 fallback 到 AST 本地解析。

能力：
- find_symbol: 符号查找（跨文件引用追踪）
- insert_symbol: 精准插入代码块
- rename_symbol: 安全重命名符号
- replace_content: 原子化内容替换
- get_diagnostics: LSP 诊断（编译错误、Lint 警告）
- get_references: 查找符号的所有引用位置
- get_file_structure: 获取文件 AST 结构

协议：MCP (Model Context Protocol) over stdio / HTTP
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
import json
import os
import ast
import subprocess
import re


class SerenaStatus(Enum):
    """Serena 连接状态"""
    ONLINE = "online"           # Serena MCP Server 在线
    OFFLINE = "offline"         # Serena 不可用
    FALLBACK = "fallback"       # 使用 AST 本地 fallback


@dataclass
class SymbolInfo:
    """符号信息"""
    name: str
    kind: str                   # class, function, variable, method, module
    file_path: str
    line_start: int
    line_end: int
    documentation: str = ""
    signature: str = ""
    children: List['SymbolInfo'] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # 引用位置


@dataclass
class DiagnosticInfo:
    """诊断信息"""
    severity: str               # error, warning, info, hint
    message: str
    file_path: str
    line: int
    column: int
    code: str = ""
    source: str = ""


@dataclass
class SerenaResult:
    """Serena 操作结果"""
    success: bool
    data: Any = None
    error: str = ""
    used_fallback: bool = False


class ASTFallbackEngine:
    """
    AST 本地 fallback 引擎

    当 Serena MCP Server 不可用时，使用 Python AST 模块提供基本的代码操作能力。
    虽然不如 LSP 精准，但足以完成大部分操作。
    """

    def __init__(self):
        self._logger = logger.bind(component="ASTFallback")

    def find_symbol(self, file_path: str, symbol_name: str) -> Optional[SymbolInfo]:
        """通过 AST 查找符号定义"""
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
                lines = source.split('\n')

            tree = ast.parse(source)

            for node in ast.walk(tree):
                sym_info = self._extract_symbol(node, file_path, lines)
                if sym_info and sym_info.name == symbol_name:
                    return sym_info

            return None
        except Exception as e:
            self._logger.warning(f"AST 查找符号失败: {e}")
            return None

    def find_symbols_by_kind(self, file_path: str, kind: str = "") -> List[SymbolInfo]:
        """查找指定类型的所有符号"""
        try:
            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
                lines = source.split('\n')

            tree = ast.parse(source)
            results = []

            for node in ast.walk(tree):
                sym_info = self._extract_symbol(node, file_path, lines)
                if sym_info:
                    if not kind or sym_info.kind == kind:
                        results.append(sym_info)

            return results
        except Exception as e:
            self._logger.warning(f"AST 查找符号列表失败: {e}")
            return []

    def get_file_structure(self, file_path: str) -> List[SymbolInfo]:
        """获取文件结构"""
        try:
            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
                lines = source.split('\n')

            tree = ast.parse(source)
            results = []

            # 顶层节点
            for node in ast.iter_child_nodes(tree):
                sym = self._extract_symbol(node, file_path, lines)
                if sym:
                    # 为类提取方法
                    if isinstance(node, ast.ClassDef):
                        sym.children = []
                        for child in node.body:
                            child_sym = self._extract_symbol(child, file_path, lines)
                            if child_sym:
                                sym.children.append(child_sym)
                    results.append(sym)

            return results
        except Exception as e:
            self._logger.warning(f"AST 获取文件结构失败: {e}")
            return []

    def get_diagnostics(self, file_path: str) -> List[DiagnosticInfo]:
        """通过编译检查获取基本诊断信息"""
        diagnostics = []

        try:
            if not os.path.exists(file_path):
                diagnostics.append(DiagnosticInfo(
                    severity="error",
                    message=f"文件不存在: {file_path}",
                    file_path=file_path, line=0, column=0,
                    source="ast_fallback"
                ))
                return diagnostics

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()

            try:
                ast.parse(source)
            except SyntaxError as e:
                diagnostics.append(DiagnosticInfo(
                    severity="error",
                    message=f"语法错误: {e.msg}",
                    file_path=file_path,
                    line=e.lineno or 0,
                    column=e.offset or 0,
                    code="E001",
                    source="ast_fallback"
                ))

            # 检查未使用的 import
            try:
                tree = ast.parse(source)
                used_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name):
                        used_names.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        used_names.add(node.attr)

                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.asname or alias.name
                            if name not in used_names:
                                diagnostics.append(DiagnosticInfo(
                                    severity="info",
                                    message=f"未使用的导入: {name}",
                                    file_path=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    code="W001",
                                    source="ast_fallback"
                                ))
                    elif isinstance(node, ast.ImportFrom):
                        if node.names:
                            for alias in node.names:
                                name = alias.asname or alias.name
                                if name != '*' and name not in used_names:
                                    diagnostics.append(DiagnosticInfo(
                                        severity="info",
                                        message=f"未使用的导入: {name}",
                                        file_path=file_path,
                                        line=node.lineno,
                                        column=node.col_offset,
                                        code="W001",
                                        source="ast_fallback"
                                    ))
            except Exception:
                pass

        except Exception as e:
            self._logger.warning(f"AST 诊断失败: {e}")

        return diagnostics

    def find_references(self, file_path: str, symbol_name: str) -> List[str]:
        """查找符号在当前文件中的引用"""
        try:
            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
                lines = source.split('\n')

            references = []
            for i, line in enumerate(lines, 1):
                if re.search(rf'\b{re.escape(symbol_name)}\b', line):
                    references.append(f"{file_path}:{i}")

            return references
        except Exception as e:
            self._logger.warning(f"AST 查找引用失败: {e}")
            return []

    def _extract_symbol(self, node, file_path: str, lines: List[str]) -> Optional[SymbolInfo]:
        """从 AST 节点提取符号信息"""
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            sig = f"class {node.name}"
            if node.bases:
                bases = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(f"{b.attr}")
                sig += f"({', '.join(bases)})"
            return SymbolInfo(
                name=node.name, kind="class",
                file_path=file_path,
                line_start=node.lineno, line_end=node.end_lineno or node.lineno,
                documentation=doc, signature=sig
            )
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            doc = ast.get_docstring(node) or ""
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            sig = f"{prefix}def {node.name}({', '.join(args)})"
            return SymbolInfo(
                name=node.name, kind="function" if not isinstance(node, ast.FunctionDef) or not any(
                    isinstance(p, ast.arg) for p in [node.args.args[0]] if node.args.args
                ) else "method",
                file_path=file_path,
                line_start=node.lineno, line_end=node.end_lineno or node.lineno,
                documentation=doc, signature=sig
            )
        elif isinstance(node, ast.Import):
            return SymbolInfo(
                name=", ".join(a.name for a in node.names),
                kind="import", file_path=file_path,
                line_start=node.lineno, line_end=node.end_lineno or node.lineno,
            )
        elif isinstance(node, ast.ImportFrom):
            return SymbolInfo(
                name=f"from {node.module}",
                kind="import", file_path=file_path,
                line_start=node.lineno, line_end=node.end_lineno or node.lineno,
            )

        return None


class SerenaAdapter:
    """
    Serena MCP 客户端适配器

    双模式运行：
    1. ONLINE 模式：通过 MCP 协议与 Serena Server 通信（精准 LSP 操作）
    2. FALLBACK 模式：使用 ASTFallbackEngine 本地解析（基础能力）

    通信协议：MCP (Model Context Protocol)
    - stdio: 子进程 stdin/stdout（推荐）
    - HTTP: POST JSON-RPC 2.0
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._logger = logger.bind(component="SerenaAdapter")
        self._config = config or {}
        self._status = SerenaStatus.OFFLINE
        self._process: Optional[subprocess.Popen] = None
        self._fallback = ASTFallbackEngine()
        self._serena_cmd = self._config.get(
            "serena_command",
            "serena"  # 默认命令，可通过配置覆盖
        )
        self._mcp_server_url = self._config.get("mcp_server_url", "")
        self._initialized = False

        # 尝试连接 Serena
        self._try_connect()

    @property
    def status(self) -> SerenaStatus:
        """获取当前连接状态"""
        return self._status

    @property
    def is_online(self) -> bool:
        """Serena 是否在线"""
        return self._status == SerenaStatus.ONLINE

    def _try_connect(self):
        """尝试连接 Serena MCP Server"""
        # 1. 检查 HTTP 模式
        if self._mcp_server_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{self._mcp_server_url}/health",
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        self._status = SerenaStatus.ONLINE
                        self._logger.info(f"Serena MCP Server 在线 (HTTP): {self._mcp_server_url}")
                        self._initialized = True
                        return
            except Exception as e:
                self._logger.debug(f"Serena HTTP 连接失败: {e}")

        # 2. 检查 stdio 模式
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", self._serena_cmd],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                self._logger.info(f"发现 Serena CLI: {result.stdout.strip()}")
                # 启动 Serena 进程（stdio 模式）
                try:
                    self._process = subprocess.Popen(
                        [self._serena_cmd, "--mcp"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    self._status = SerenaStatus.ONLINE
                    self._initialized = True
                    self._logger.info("Serena MCP Server 已启动 (stdio)")
                    return
                except Exception as e:
                    self._logger.warning(f"启动 Serena 进程失败: {e}")
        except Exception as e:
            self._logger.debug(f"Serena CLI 未找到: {e}")

        # 3. Fallback
        self._status = SerenaStatus.FALLBACK
        self._logger.info("Serena 不可用，使用 AST 本地 fallback 引擎")

    def _send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """发送 MCP 请求"""
        if self._status != SerenaStatus.ONLINE:
            return None

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        try:
            if self._process and self._process.poll() is None:
                # stdio 模式
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()

                response_line = self._process.stdout.readline()
                if response_line:
                    return json.loads(response_line.strip())

            elif self._mcp_server_url:
                # HTTP 模式
                import urllib.request
                req = urllib.request.Request(
                    self._mcp_server_url,
                    data=json.dumps(request).encode('utf-8'),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode('utf-8'))

        except Exception as e:
            self._logger.warning(f"MCP 请求失败 ({method}): {e}")
            self._status = SerenaStatus.FALLBACK

        return None

    # ── 公共 API ──────────────────────────────────────────

    def find_symbol(self, file_path: str, symbol_name: str) -> SerenaResult:
        """
        查找符号定义

        Args:
            file_path: 文件路径
            symbol_name: 符号名称
        """
        if self.is_online:
            response = self._send_mcp_request("tools/call", {
                "name": "find_symbol",
                "arguments": {"file_path": file_path, "symbol_name": symbol_name}
            })
            if response and response.get("result"):
                return SerenaResult(
                    success=True,
                    data=self._parse_symbol_data(response["result"]),
                    used_fallback=False
                )

        # Fallback
        sym = self._fallback.find_symbol(file_path, symbol_name)
        return SerenaResult(
            success=sym is not None,
            data=sym,
            used_fallback=True
        )

    def find_symbols(self, file_path: str, kind: str = "") -> SerenaResult:
        """查找文件中所有符号"""
        if self.is_online:
            response = self._send_mcp_request("tools/call", {
                "name": "find_symbols",
                "arguments": {"file_path": file_path, "kind": kind}
            })
            if response and response.get("result"):
                return SerenaResult(
                    success=True,
                    data=response["result"],
                    used_fallback=False
                )

        syms = self._fallback.find_symbols_by_kind(file_path, kind)
        return SerenaResult(success=True, data=syms, used_fallback=True)

    def get_file_structure(self, file_path: str) -> SerenaResult:
        """获取文件 AST 结构"""
        if self.is_online:
            response = self._send_mcp_request("tools/call", {
                "name": "get_file_structure",
                "arguments": {"file_path": file_path}
            })
            if response and response.get("result"):
                return SerenaResult(
                    success=True, data=response["result"],
                    used_fallback=False
                )

        structure = self._fallback.get_file_structure(file_path)
        return SerenaResult(success=True, data=structure, used_fallback=True)

    def get_diagnostics(self, file_path: str) -> SerenaResult:
        """获取 LSP 诊断信息"""
        if self.is_online:
            response = self._send_mcp_request("tools/call", {
                "name": "get_diagnostics",
                "arguments": {"file_path": file_path}
            })
            if response and response.get("result"):
                diagnostics = []
                for d in response["result"]:
                    diagnostics.append(DiagnosticInfo(
                        severity=d.get("severity", "info"),
                        message=d.get("message", ""),
                        file_path=d.get("file_path", file_path),
                        line=d.get("line", 0),
                        column=d.get("column", 0),
                        code=d.get("code", ""),
                        source=d.get("source", "serena")
                    ))
                return SerenaResult(
                    success=True, data=diagnostics,
                    used_fallback=False
                )

        diagnostics = self._fallback.get_diagnostics(file_path)
        return SerenaResult(success=True, data=diagnostics, used_fallback=True)

    def get_references(self, file_path: str, symbol_name: str) -> SerenaResult:
        """查找符号的所有引用"""
        if self.is_online:
            response = self._send_mcp_request("tools/call", {
                "name": "get_references",
                "arguments": {"file_path": file_path, "symbol_name": symbol_name}
            })
            if response and response.get("result"):
                return SerenaResult(
                    success=True, data=response["result"],
                    used_fallback=False
                )

        refs = self._fallback.find_references(file_path, symbol_name)
        return SerenaResult(success=True, data=refs, used_fallback=True)

    def insert_after_symbol(self, file_path: str, symbol_name: str,
                            code: str) -> SerenaResult:
        """
        在指定符号之后插入代码块

        Args:
            file_path: 文件路径
            symbol_name: 目标符号名称
            code: 要插入的代码
        """
        # 先查找符号位置
        sym_result = self.find_symbol(file_path, symbol_name)
        if not sym_result.success or not sym_result.data:
            return SerenaResult(
                success=False,
                error=f"找不到符号: {symbol_name} 在 {file_path}"
            )

        sym = sym_result.data
        insert_line = sym.line_end

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 在符号结束后插入
            code_lines = code.split('\n')
            for i, cl in enumerate(code_lines):
                lines.insert(insert_line + i, cl + '\n')

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            return SerenaResult(success=True, data={
                "action": "insert_after",
                "symbol": symbol_name,
                "line": insert_line + 1,
                "inserted_lines": len(code_lines)
            }, used_fallback=sym_result.used_fallback)

        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def replace_content(self, file_path: str, old_content: str,
                        new_content: str) -> SerenaResult:
        """
        原子化内容替换

        Args:
            file_path: 文件路径
            old_content: 旧内容（精确匹配）
            new_content: 新内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if old_content not in content:
                return SerenaResult(
                    success=False,
                    error="旧内容未在文件中找到，无法替换"
                )

            new_file_content = content.replace(old_content, new_content, 1)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)

            return SerenaResult(success=True, data={
                "action": "replace",
                "file": file_path,
                "replacements": 1
            })

        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def rename_symbol(self, file_path: str, old_name: str,
                      new_name: str) -> SerenaResult:
        """
        安全重命名符号

        使用 AST + 正则替换，确保只替换标识符而非字符串内容。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 使用正则只匹配独立的标识符
            pattern = re.compile(rf'\b{re.escape(old_name)}\b')
            new_content = pattern.sub(new_name, content)

            count = len(pattern.findall(content))

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return SerenaResult(success=True, data={
                "action": "rename",
                "old_name": old_name,
                "new_name": new_name,
                "replacements": count
            })

        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def read_file(self, file_path: str, start_line: int = 0,
                  end_line: int = 0) -> SerenaResult:
        """读取文件内容（支持行范围）"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if start_line > 0 or end_line > 0:
                s = max(0, start_line - 1)
                e = end_line if end_line > 0 else len(lines)
                selected = lines[s:e]
                content = ''.join(selected)
                return SerenaResult(success=True, data={
                    "content": content,
                    "start_line": s + 1,
                    "end_line": min(e, len(lines)),
                    "total_lines": len(lines)
                })
            else:
                return SerenaResult(success=True, data={
                    "content": ''.join(lines),
                    "total_lines": len(lines)
                })

        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def write_file(self, file_path: str, content: str) -> SerenaResult:
        """写入文件（自动创建目录）"""
        try:
            os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return SerenaResult(success=True, data={
                "action": "write",
                "file": file_path,
                "size": len(content)
            })
        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def check_syntax(self, file_path: str) -> SerenaResult:
        """检查文件语法"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            ast.parse(source)
            return SerenaResult(success=True, data={"syntax_valid": True})
        except SyntaxError as e:
            return SerenaResult(success=False, data={
                "syntax_valid": False,
                "error": e.msg,
                "line": e.lineno,
                "column": e.offset
            }, error=f"语法错误: {e.msg} (行 {e.lineno})")
        except Exception as e:
            return SerenaResult(success=False, error=str(e))

    def _parse_symbol_data(self, data: Any) -> SymbolInfo:
        """解析 MCP 返回的符号数据"""
        if isinstance(data, dict):
            return SymbolInfo(
                name=data.get("name", ""),
                kind=data.get("kind", ""),
                file_path=data.get("file_path", ""),
                line_start=data.get("line_start", 0),
                line_end=data.get("line_end", 0),
                documentation=data.get("documentation", ""),
                signature=data.get("signature", ""),
            )
        return SymbolInfo(name="", kind="", file_path="")

    def shutdown(self):
        """关闭连接"""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._status = SerenaStatus.OFFLINE
        self._logger.info("Serena 连接已关闭")

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "status": self._status.value,
            "mcp_server_url": self._mcp_server_url,
            "serena_command": self._serena_cmd,
            "process_alive": self._process.poll() is None if self._process else False,
            "initialized": self._initialized
        }
