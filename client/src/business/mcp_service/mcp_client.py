"""
MCP客户端 - MCP Client

功能：
1. 连接MCP服务
2. 调用MCP工具
3. 处理响应
4. 错误处理和重试
"""

import logging
import time
import json
import subprocess
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    host: str
    port: int
    status: ServiceStatus
    tools: List[str] = None
    last_heartbeat: float = 0.0
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class MCPClient:
    """
    MCP客户端 - 连接和调用MCP服务
    
    支持的通信方式：
    1. 子进程模式 - 启动本地MCP服务进程
    2. TCP模式 - 连接远程MCP服务
    3. 管道模式 - 通过标准输入输出通信
    """
    
    def __init__(self):
        self._service_info: Optional[ServiceInfo] = None
        self._process: Optional[subprocess.Popen] = None
        self._status = ServiceStatus.DISCONNECTED
        self._retry_count = 0
        self._max_retries = 3
    
    def connect(self, mode: str = "subprocess", host: str = "localhost", port: int = 8000) -> bool:
        """
        连接MCP服务
        
        Args:
            mode: 连接模式 (subprocess/tcp/pipe)
            host: 主机地址
            port: 端口号
        
        Returns:
            是否成功
        """
        self._status = ServiceStatus.CONNECTING
        
        try:
            if mode == "subprocess":
                return self._connect_subprocess()
            elif mode == "tcp":
                return self._connect_tcp(host, port)
            elif mode == "pipe":
                return self._connect_pipe()
            else:
                logger.error(f"未知连接模式: {mode}")
                return False
        except Exception as e:
            logger.error(f"连接MCP服务失败: {e}")
            self._status = ServiceStatus.ERROR
            return False
    
    def _connect_subprocess(self) -> bool:
        """启动子进程模式"""
        # 查找MCP服务入口
        mcp_script = self._find_mcp_script()
        
        if not mcp_script:
            logger.warning("未找到MCP服务脚本")
            return False
        
        logger.info(f"启动MCP服务: {mcp_script}")
        
        # 启动子进程
        self._process = subprocess.Popen(
            [os.path.join(os.getcwd(), mcp_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 等待服务启动
        time.sleep(2)
        
        # 检查进程是否正常运行
        if self._process.poll() is None:
            self._status = ServiceStatus.CONNECTED
            self._service_info = ServiceInfo(
                name="MCP Service",
                host="localhost",
                port=0,
                status=ServiceStatus.CONNECTED,
                last_heartbeat=time.time()
            )
            logger.info("MCP服务启动成功")
            return True
        else:
            # 读取错误信息
            stderr = self._process.stderr.read() if self._process.stderr else ""
            logger.error(f"MCP服务启动失败: {stderr}")
            self._status = ServiceStatus.ERROR
            return False
    
    def _connect_tcp(self, host: str, port: int) -> bool:
        """TCP连接模式"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            try:
                sock.connect((host, port))
                sock.close()
                
                self._status = ServiceStatus.CONNECTED
                self._service_info = ServiceInfo(
                    name="MCP TCP Service",
                    host=host,
                    port=port,
                    status=ServiceStatus.CONNECTED,
                    last_heartbeat=time.time()
                )
                logger.info(f"MCP TCP服务连接成功: {host}:{port}")
                return True
            except ConnectionRefusedError:
                logger.error(f"MCP TCP服务连接失败: {host}:{port}")
                return False
        except ImportError:
            logger.error("socket模块不可用")
            return False
    
    def _connect_pipe(self) -> bool:
        """管道连接模式（简化实现）"""
        logger.warning("管道模式尚未完全实现")
        self._status = ServiceStatus.CONNECTED
        return True
    
    def _find_mcp_script(self) -> Optional[str]:
        """查找MCP服务脚本"""
        candidates = [
            "mcp_server.py",
            "tools/mcp_server.py",
            "client/src/business/mcp_service/mcp_server.py"
        ]
        
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        
        return None
    
    def call_tool(self, tool_name: str, **kwargs) -> Dict:
        """
        调用MCP工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            调用结果
        """
        if self._status != ServiceStatus.CONNECTED:
            return {
                'success': False,
                'error': 'MCP服务未连接',
                'used_fallback': False
            }
        
        try:
            # 构建请求
            request = json.dumps({
                'tool': tool_name,
                'args': kwargs,
                'timestamp': time.time()
            })
            
            # 发送请求（子进程模式）
            if self._process:
                self._process.stdin.write(request + '\n')
                self._process.stdin.flush()
                
                # 读取响应
                response = self._process.stdout.readline()
                if response:
                    return json.loads(response)
                else:
                    return {'success': False, 'error': '无响应'}
            else:
                return {'success': False, 'error': '未连接'}
                
        except Exception as e:
            logger.error(f"调用MCP工具失败 {tool_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> ServiceStatus:
        """获取服务状态"""
        # 检查进程是否仍然运行
        if self._process and self._process.poll() is not None:
            self._status = ServiceStatus.DISCONNECTED
        
        return self._status
    
    def disconnect(self):
        """断开连接"""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"关闭MCP进程失败: {e}")
            
            self._process = None
        
        self._status = ServiceStatus.DISCONNECTED
        self._service_info = None
        logger.info("MCP服务已断开")
    
    def get_service_info(self) -> Optional[ServiceInfo]:
        """获取服务信息"""
        return self._service_info