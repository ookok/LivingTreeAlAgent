"""
自动化部署系统 - AutoDeploy

核心功能：
1. 依赖自动安装
2. 服务自动启动
3. 配置自动同步
4. 健康检查
5. 一键部署脚本生成
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import asyncio
import subprocess
import os
from loguru import logger


class DeploymentStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


class ServiceType(Enum):
    """服务类型"""
    OLLAMA = "ollama"
    GITNEXUS = "gitnexus"
    RELAY_SERVER = "relay_server"
    TRACKER_SERVER = "tracker_server"
    CLIENT = "client"


@dataclass
class ServiceConfig:
    """服务配置"""
    name: str
    type: ServiceType
    command: str
    cwd: str
    port: int = 0
    enabled: bool = True
    auto_start: bool = True
    health_check_url: str = ""
    dependencies: List[str] = field(default_factory=list)


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    status: DeploymentStatus
    message: str
    services_started: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class AutoDeploy:
    """
    自动化部署系统
    
    核心特性：
    1. 依赖自动安装
    2. 服务自动启动
    3. 配置自动同步
    4. 健康检查
    5. 一键部署
    """

    def __init__(self):
        self._logger = logger.bind(component="AutoDeploy")
        self._services: Dict[str, ServiceConfig] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._init_services()

    def _init_services(self):
        """初始化服务配置"""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Ollama服务
        self._services["ollama"] = ServiceConfig(
            name="Ollama",
            type=ServiceType.OLLAMA,
            command="ollama serve",
            cwd=str(project_root),
            port=11434,
            enabled=True,
            auto_start=True,
            health_check_url="http://localhost:11434/api/tags"
        )
        
        # GitNexus服务
        self._services["gitnexus"] = ServiceConfig(
            name="GitNexus",
            type=ServiceType.GITNEXUS,
            command="gitnexus serve --port 8080",
            cwd=str(project_root),
            port=8080,
            enabled=True,
            auto_start=True,
            health_check_url="http://localhost:8080/health",
            dependencies=["ollama"]
        )
        
        # Relay Server
        self._services["relay_server"] = ServiceConfig(
            name="Relay Server",
            type=ServiceType.RELAY_SERVER,
            command="python -m uvicorn server.relay_server.api.main:app --host 0.0.0.0 --port 8000",
            cwd=str(project_root),
            port=8000,
            enabled=True,
            auto_start=True,
            health_check_url="http://localhost:8000/health"
        )
        
        # Tracker Server
        self._services["tracker_server"] = ServiceConfig(
            name="Tracker Server",
            type=ServiceType.TRACKER_SERVER,
            command="python server/tracker_server.py",
            cwd=str(project_root),
            port=8888,
            enabled=True,
            auto_start=True
        )
        
        # Desktop Client
        self._services["client"] = ServiceConfig(
            name="Desktop Client",
            type=ServiceType.CLIENT,
            command="python main.py client",
            cwd=str(project_root),
            enabled=True,
            auto_start=True,
            dependencies=["relay_server"]
        )

    async def install_dependencies(self) -> Dict[str, Any]:
        """自动安装依赖"""
        self._logger.info("开始安装依赖...")
        
        results = {
            "success": True,
            "steps": []
        }
        
        steps = [
            ("pip install -e ./client", "安装客户端依赖"),
            ("pip install -e ./server/relay_server", "安装Relay Server依赖"),
            ("pip install -e ./app", "安装App依赖"),
            ("pip install ollama httpx uvicorn", "安装额外依赖")
        ]
        
        for cmd, desc in steps:
            self._logger.info(f"执行: {desc}")
            try:
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate(timeout=300)
                
                if process.returncode == 0:
                    results["steps"].append({"step": desc, "success": True, "output": stdout.decode()[:200]})
                else:
                    results["success"] = False
                    results["steps"].append({"step": desc, "success": False, "error": stderr.decode()})
                    break
            except asyncio.TimeoutError:
                results["success"] = False
                results["steps"].append({"step": desc, "success": False, "error": "超时"})
                break
            except Exception as e:
                results["success"] = False
                results["steps"].append({"step": desc, "success": False, "error": str(e)})
                break
        
        return results

    async def start_service(self, service_name: str) -> bool:
        """启动单个服务"""
        service = self._services.get(service_name)
        if not service or not service.enabled:
            return False
        
        # 检查依赖
        for dep_name in service.dependencies:
            if dep_name not in self._processes:
                self._logger.warning(f"服务 {service_name} 依赖 {dep_name} 未启动，先启动依赖")
                if not await self.start_service(dep_name):
                    self._logger.error(f"依赖服务 {dep_name} 启动失败")
                    return False
        
        # 检查端口是否被占用
        if service.port > 0:
            if await self._is_port_occupied(service.port):
                self._logger.warning(f"端口 {service.port} 已被占用，跳过启动 {service_name}")
                return True
        
        try:
            self._logger.info(f"启动服务: {service.name}")
            
            if os.name == 'nt':
                # Windows 使用 start 命令
                cmd = f"start /B {service.command}"
            else:
                cmd = f"{service.command} &"
            
            process = subprocess.Popen(
                cmd,
                cwd=service.cwd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self._processes[service_name] = process
            
            # 等待服务启动
            if service.health_check_url:
                await self._wait_for_service(service.health_check_url, service_name)
            
            self._logger.info(f"服务 {service.name} 启动成功")
            return True
        except Exception as e:
            self._logger.error(f"启动服务 {service.name} 失败: {e}")
            return False

    async def _is_port_occupied(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _wait_for_service(self, url: str, service_name: str, timeout: int = 30):
        """等待服务启动"""
        import httpx
        
        for i in range(timeout):
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        self._logger.info(f"服务 {service_name} 健康检查通过")
                        return
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
        self._logger.warning(f"服务 {service_name} 健康检查超时")

    async def stop_service(self, service_name: str) -> bool:
        """停止单个服务"""
        process = self._processes.get(service_name)
        if not process:
            return False
        
        try:
            process.terminate()
            await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, process.wait), timeout=5)
            del self._processes[service_name]
            self._logger.info(f"服务 {service_name} 已停止")
            return True
        except Exception as e:
            self._logger.error(f"停止服务 {service_name} 失败: {e}")
            return False

    async def stop_all_services(self):
        """停止所有服务"""
        for service_name in list(self._processes.keys()):
            await self.stop_service(service_name)

    async def start_all_services(self) -> List[str]:
        """启动所有服务"""
        started = []
        
        for service_name, service in self._services.items():
            if service.auto_start:
                if await self.start_service(service_name):
                    started.append(service_name)
        
        return started

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        results = {
            "services": {},
            "overall": "healthy"
        }
        
        for service_name, service in self._services.items():
            status = "unknown"
            
            if service_name in self._processes:
                process = self._processes[service_name]
                if process.poll() is None:
                    # 进程正在运行
                    if service.health_check_url:
                        try:
                            import httpx
                            async with httpx.AsyncClient(timeout=2) as client:
                                response = await client.get(service.health_check_url)
                                status = "healthy" if response.status_code == 200 else "unhealthy"
                        except Exception:
                            status = "unhealthy"
                    else:
                        status = "running"
                else:
                    status = "stopped"
            
            results["services"][service_name] = {
                "status": status,
                "port": service.port,
                "enabled": service.enabled
            }
            
            if status in ["unhealthy", "stopped"]:
                results["overall"] = "unhealthy"
        
        return results

    async def deploy(self, install_deps: bool = True) -> DeploymentResult:
        """一键部署"""
        self._logger.info("开始一键部署...")
        
        result = DeploymentResult(
            success=True,
            status=DeploymentStatus.PENDING,
            message="部署开始"
        )
        
        try:
            # 1. 安装依赖
            if install_deps:
                result.status = DeploymentStatus.INSTALLING
                deps_result = await self.install_dependencies()
                if not deps_result["success"]:
                    result.success = False
                    result.status = DeploymentStatus.FAILED
                    result.message = "依赖安装失败"
                    result.errors.append("依赖安装失败")
                    return result
            
            # 2. 启动服务
            result.status = DeploymentStatus.STARTING
            started = await self.start_all_services()
            result.services_started = started
            
            # 3. 健康检查
            health = await self.health_check()
            if health["overall"] == "healthy":
                result.status = DeploymentStatus.RUNNING
                result.message = "部署成功"
            else:
                result.status = DeploymentStatus.FAILED
                result.message = "健康检查失败"
                result.errors.append(f"服务状态: {health}")
        
        except Exception as e:
            result.success = False
            result.status = DeploymentStatus.FAILED
            result.message = str(e)
            result.errors.append(str(e))
        
        return result

    async def generate_startup_script(self, path: Optional[str] = None) -> str:
        """生成启动脚本"""
        if not path:
            path = "start_all.bat" if os.name == 'nt' else "start_all.sh"
        
        content = ""
        
        if os.name == 'nt':
            content = f"""@echo off
REM LivingTree AI Agent 一键启动脚本
echo 正在启动所有服务...

REM 启动 Ollama
echo 启动 Ollama...
start /B ollama serve

REM 等待 Ollama 启动
timeout /t 5 /nobreak >nul

REM 启动 GitNexus
echo 启动 GitNexus...
start /B gitnexus serve --port 8080

REM 启动 Relay Server
echo 启动 Relay Server...
start /B python -m uvicorn server.relay_server.api.main:app --host 0.0.0.0 --port 8000

REM 启动 Tracker Server
echo 启动 Tracker Server...
start /B python server/tracker_server.py

REM 等待服务启动
timeout /t 10 /nobreak >nul

REM 启动客户端
echo 启动 Desktop Client...
python main.py client

echo 所有服务已启动！
"""
        else:
            content = f"""#!/bin/bash
# LivingTree AI Agent 一键启动脚本
echo "正在启动所有服务..."

# 启动 Ollama
echo "启动 Ollama..."
ollama serve &

# 等待 Ollama 启动
sleep 5

# 启动 GitNexus
echo "启动 GitNexus..."
gitnexus serve --port 8080 &

# 启动 Relay Server
echo "启动 Relay Server..."
python -m uvicorn server.relay_server.api.main:app --host 0.0.0.0 --port 8000 &

# 启动 Tracker Server
echo "启动 Tracker Server..."
python server/tracker_server.py &

# 等待服务启动
sleep 10

# 启动客户端
echo "启动 Desktop Client..."
python main.py client

echo "所有服务已启动！"
"""
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        if os.name != 'nt':
            os.chmod(path, 0o755)
        
        self._logger.info(f"启动脚本已生成: {path}")
        return path


def get_auto_deploy() -> AutoDeploy:
    """获取自动部署单例"""
    global _auto_deploy_instance
    if _auto_deploy_instance is None:
        _auto_deploy_instance = AutoDeploy()
    return _auto_deploy_instance


_auto_deploy_instance = None