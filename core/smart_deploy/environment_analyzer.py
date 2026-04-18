"""
环境分析器 - EnvironmentAnalyzer
核心理念：分析目标服务器能力

功能：
1. 服务器类型检测
2. 系统能力分析
3. 资源监控
4. 网络探测
"""

import subprocess
import platform
import re
import os
import json
import shlex
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ServerType(Enum):
    """服务器类型"""
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"
    UNKNOWN = "unknown"


class ServerCapability(Enum):
    """服务器能力级别"""
    LOW = "low"          # 轻量级设备
    MEDIUM = "medium"    # 普通VPS
    HIGH = "high"        # 高性能服务器
    CONTAINER = "container"  # 容器环境


@dataclass
class ServerInfo:
    """服务器信息"""
    server_type: ServerType
    hostname: str
    os_version: str
    kernel_version: str
    cpu_model: str
    cpu_cores: int
    memory_total_mb: int
    memory_available_mb: int
    disk_total_gb: float
    disk_available_gb: float
    capability: ServerCapability
    is_container: bool
    container_type: Optional[str]
    python_version: Optional[str]
    docker_available: bool
    docker_version: Optional[str]
    ssh_available: bool
    network_interfaces: List[Dict[str, Any]]


class EnvironmentAnalyzer:
    """
    环境分析器

    本地或远程服务器环境分析
    """

    def __init__(self):
        self._cache: Dict[str, ServerInfo] = {}
        self._cache_ttl = 300  # 5分钟缓存
        self._cache_time: Dict[str, float] = {}

    def analyze(self, target: str = "local", use_cache: bool = True) -> ServerInfo:
        """
        分析服务器环境

        Args:
            target: 目标地址 ("local" 或 "user@host")
            use_cache: 是否使用缓存

        Returns:
            ServerInfo: 服务器信息
        """
        # 检查缓存
        if use_cache and target in self._cache:
            if self._is_cache_valid(target):
                return self._cache[target]

        # 执行分析
        if target == "local":
            info = self._analyze_local()
        else:
            info = self._analyze_remote(target)

        # 更新缓存
        self._cache[target] = info
        self._cache_time[target] = __import__('time').time()

        return info

    def _is_cache_valid(self, target: str) -> bool:
        """检查缓存是否有效"""
        import time
        if target not in self._cache_time:
            return False
        return (time.time() - self._cache_time[target]) < self._cache_ttl

    def _analyze_local(self) -> ServerInfo:
        """分析本地环境"""
        system = platform.system().lower()

        if system == "linux":
            return self._analyze_linux()
        elif system == "windows":
            return self._analyze_windows()
        elif system == "darwin":
            return self._analyze_macos()
        else:
            return self._create_unknown_info()

    def _analyze_linux(self) -> ServerInfo:
        """分析Linux环境"""
        hostname = self._run_cmd("hostname", fallback="unknown")
        os_version = self._run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2", fallback="Linux")
        kernel_version = self._run_cmd("uname -r", fallback="unknown")

        # CPU信息
        cpu_model = self._run_cmd("cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2", fallback="unknown").strip()
        cpu_cores = os.cpu_count() or 1

        # 内存信息
        mem_info = self._parse_meminfo()
        memory_total = mem_info.get('total', 2048)
        memory_available = mem_info.get('available', 1024)

        # 磁盘信息
        disk_info = self._get_disk_info_linux()

        # 容器检测
        is_container, container_type = self._detect_container()

        # Python版本
        python_version = self._get_python_version()

        # Docker
        docker_available, docker_version = self._check_docker()

        # 网络接口
        network_ifaces = self._get_network_interfaces_linux()

        # 能力评估
        capability = self._evaluate_capability(
            cpu_cores=cpu_cores,
            memory_mb=memory_total,
            is_container=is_container
        )

        return ServerInfo(
            server_type=ServerType.LINUX,
            hostname=hostname,
            os_version=os_version,
            kernel_version=kernel_version,
            cpu_model=cpu_model,
            cpu_cores=cpu_cores,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            disk_total_gb=disk_info['total'],
            disk_available_gb=disk_info['available'],
            capability=capability,
            is_container=is_container,
            container_type=container_type,
            python_version=python_version,
            docker_available=docker_available,
            docker_version=docker_version,
            ssh_available=self._check_command("ssh"),
            network_interfaces=network_ifaces
        )

    def _analyze_windows(self) -> ServerInfo:
        """分析Windows环境"""
        hostname = os.environ.get('COMPUTERNAME', 'unknown')
        os_version = self._run_cmd("powershell (Get-WmiObject Win32_OperatingSystem).Caption", fallback="Windows")
        kernel_version = platform.release()

        # CPU
        cpu_model = platform.processor() or "unknown"
        cpu_cores = os.cpu_count() or 1

        # 内存
        mem_info = self._get_windows_memory()
        memory_total = mem_info['total']
        memory_available = mem_info['available']

        # 磁盘
        disk_info = self._get_disk_info_windows()

        # 能力评估
        capability = self._evaluate_capability(cpu_cores, memory_total)

        return ServerInfo(
            server_type=ServerType.WINDOWS,
            hostname=hostname,
            os_version=os_version,
            kernel_version=kernel_version,
            cpu_model=cpu_model,
            cpu_cores=cpu_cores,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            disk_total_gb=disk_info['total'],
            disk_available_gb=disk_info['available'],
            capability=capability,
            is_container=False,
            container_type=None,
            python_version=self._get_python_version(),
            docker_available=self._check_command("docker"),
            docker_version=None,
            ssh_available=self._check_command("ssh"),
            network_interfaces=[]
        )

    def _analyze_macos(self) -> ServerInfo:
        """分析macOS环境"""
        hostname = subprocess.run("hostname", shell=True, capture_output=True, text=True).stdout.strip()
        os_version = subprocess.run("sw_vers -productVersion", shell=True, capture_output=True, text=True).stdout.strip()

        cpu_model = "Apple Silicon" if platform.machine() == "arm64" else platform.processor()
        cpu_cores = os.cpu_count() or 1

        memory_total = int(subprocess.run(
            "sysctl -n hw.memsize",
            shell=True, capture_output=True, text=True
        ).stdout.strip()) // (1024 * 1024)

        disk_info = self._get_disk_info_macos()

        return ServerInfo(
            server_type=ServerType.MACOS,
            hostname=hostname,
            os_version=f"macOS {os_version}",
            kernel_version="Darwin",
            cpu_model=cpu_model,
            cpu_cores=cpu_cores,
            memory_total_mb=memory_total,
            memory_available_mb=memory_total // 2,
            disk_total_gb=disk_info['total'],
            disk_available_gb=disk_info['available'],
            capability=ServerCapability.HIGH,
            is_container=False,
            container_type=None,
            python_version=self._get_python_version(),
            docker_available=self._check_command("docker"),
            docker_version=None,
            ssh_available=True,
            network_interfaces=[]
        )

    def _analyze_remote(self, target: str) -> ServerInfo:
        """分析远程服务器（通过SSH）"""
        commands = {
            'hostname': 'hostname',
            'os_version': 'cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d\\" -f2 || uname -s',
            'cpu_model': "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2",
            'cpu_cores': 'nproc',
            'memory': 'free -m | grep Mem',
            'disk': 'df -BG / | tail -1',
            'docker': 'docker --version 2>/dev/null || echo "not_found"',
            'python': 'python3 --version 2>/dev/null || python --version 2>/dev/null || echo "not_found"'
        }

        results = {}
        for key, cmd in commands.items():
            results[key] = self._run_ssh_cmd(target, cmd)

        # 解析结果并构建 ServerInfo
        hostname = results.get('hostname', 'unknown')
        os_version = results.get('os_version', 'unknown')

        # 解析CPU核心数
        cpu_cores = 1
        try:
            if results.get('cpu_cores'):
                cpu_cores = int(results['cpu_cores'].strip())
        except ValueError:
            pass

        # 解析内存信息
        memory_total = 2048
        memory_available = 1024
        mem_line = results.get('memory', '')
        if mem_line:
            mem_parts = mem_line.split()
            if len(mem_parts) >= 2:
                try:
                    memory_total = int(mem_parts[1])
                    if len(mem_parts) >= 7:
                        memory_available = int(mem_parts[6])
                except ValueError:
                    pass

        # 解析磁盘信息
        disk_total = 50
        disk_available = 20
        disk_line = results.get('disk', '')
        if disk_line:
            disk_parts = disk_line.split()
            if len(disk_parts) >= 2:
                try:
                    disk_total = float(disk_parts[0].replace('G', ''))
                    disk_available = float(disk_parts[1].replace('G', ''))
                except ValueError:
                    pass

        # 检查 Docker
        docker_available = 'not_found' not in results.get('docker', 'not_found')
        docker_version = results.get('docker', None) if docker_available else None
        if docker_version and docker_version != 'not_found':
            docker_version = docker_version.split()[2].replace(',', '') if len(docker_version.split()) > 2 else None

        # 检查 Python
        python_version = results.get('python', None)
        if python_version and 'not_found' in python_version:
            python_version = None

        # 评估服务器能力
        capability = self._evaluate_capability(cpu_cores, memory_total)

        return ServerInfo(
            server_type=ServerType.LINUX,  # 假设Linux，除非检测到其他
            hostname=hostname,
            os_version=os_version,
            kernel_version="unknown",
            cpu_model=results.get('cpu_model', 'unknown').strip(),
            cpu_cores=cpu_cores,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            disk_total_gb=disk_total,
            disk_available_gb=disk_available,
            capability=capability,
            is_container=False,
            container_type=None,
            python_version=python_version,
            docker_available=docker_available,
            docker_version=docker_version,
            ssh_available=True,
            network_interfaces=[]
        )

    def _create_unknown_info(self) -> ServerInfo:
        """创建未知服务器信息"""
        return ServerInfo(
            server_type=ServerType.UNKNOWN,
            hostname="unknown",
            os_version="unknown",
            kernel_version="unknown",
            cpu_model="unknown",
            cpu_cores=1,
            memory_total_mb=1024,
            memory_available_mb=512,
            disk_total_gb=20,
            disk_available_gb=10,
            capability=ServerCapability.LOW,
            is_container=False,
            container_type=None,
            python_version=None,
            docker_available=False,
            docker_version=None,
            ssh_available=False,
            network_interfaces=[]
        )

    def _run_cmd(self, cmd: str, fallback: str = "") -> str:
        """运行本地命令"""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else fallback
        except Exception:
            return fallback

    def _run_ssh_cmd(self, target: str, cmd: str) -> str:
        """通过SSH运行命令"""
        try:
            # 使用 shlex 正确转义命令，避免引号和特殊字符问题
            import shlex
            safe_cmd = shlex.quote(cmd)
            result = subprocess.run(
                f"ssh {target} {safe_cmd}",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _check_command(self, cmd: str) -> bool:
        """检查命令是否可用"""
        result = subprocess.run(
            f"which {cmd}",
            shell=True, capture_output=True, text=True
        )
        return result.returncode == 0

    def _parse_meminfo(self) -> Dict[str, int]:
        """解析Linux内存信息"""
        mem_info = {'total': 2048, 'available': 1024}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_info['total'] = int(line.split()[1]) // 1024
                    elif line.startswith('MemAvailable:'):
                        mem_info['available'] = int(line.split()[1]) // 1024
                        break
        except:
            pass
        return mem_info

    def _get_disk_info_linux(self) -> Dict[str, float]:
        """获取Linux磁盘信息"""
        try:
            result = subprocess.run(
                "df -BG --output=size,avail / | tail -1",
                shell=True, capture_output=True, text=True
            )
            parts = result.stdout.strip().split()
            return {
                'total': float(parts[0].replace('G', '')),
                'available': float(parts[1].replace('G', ''))
            }
        except:
            return {'total': 50, 'available': 20}

    def _get_disk_info_windows(self) -> Dict[str, float]:
        """获取Windows磁盘信息"""
        try:
            result = subprocess.run(
                'powershell "(Get-PSDrive C).Free / 1GB"',
                shell=True, capture_output=True, text=True
            )
            available = float(result.stdout.strip())
            return {'total': 100, 'available': available}
        except:
            return {'total': 100, 'available': 30}

    def _get_disk_info_macos(self) -> Dict[str, float]:
        """获取macOS磁盘信息"""
        try:
            result = subprocess.run(
                'df -kg / | tail -1 | awk \'{print $2, $4}\'',
                shell=True, capture_output=True, text=True
            )
            parts = result.stdout.strip().split()
            return {
                'total': float(parts[0]),
                'available': float(parts[1])
            }
        except:
            return {'total': 250, 'available': 100}

    def _detect_container(self) -> tuple:
        """检测容器环境"""
        # 检查cgroup
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content.lower():
                    return True, 'docker'
                if 'kubernetes' in content.lower():
                    return True, 'kubernetes'
        except:
            pass

        # 检查.dockerenv
        if os.path.exists('/.dockerenv'):
            return True, 'docker'

        return False, None

    def _get_python_version(self) -> Optional[str]:
        """获取Python版本"""
        try:
            result = subprocess.run(
                'python3 --version || python --version',
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split()[1]
        except:
            pass
        return None

    def _check_docker(self) -> tuple:
        """检查Docker"""
        if not self._check_command('docker'):
            return False, None
        try:
            result = subprocess.run(
                'docker --version',
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split()[2].replace(',', '')
                return True, version
        except:
            pass
        return False, None

    def _get_network_interfaces_linux(self) -> List[Dict[str, Any]]:
        """获取网络接口"""
        interfaces = []
        try:
            result = subprocess.run(
                'ip -j addr show | jq -r ".[] | {name: .ifname, ip: .addr_info[0].local}" 2>/dev/null || ip addr show',
                shell=True, capture_output=True, text=True, timeout=5
            )
            # 简单解析
            for line in result.stdout.split('\n'):
                if ':' in line and 'inet' in line:
                    parts = line.split(':')
                    name = parts[1].strip()
                    inet_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if inet_match:
                        interfaces.append({
                            'name': name,
                            'ip': inet_match.group(1),
                            'type': 'ethernet'
                        })
        except:
            pass
        return interfaces

    def _get_windows_memory(self) -> Dict[str, int]:
        """获取Windows内存信息"""
        try:
            result = subprocess.run(
                'powershell "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize, (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"',
                shell=True, capture_output=True, text=True, timeout=10
            )
            parts = result.stdout.strip().split()
            return {
                'total': int(parts[0]) // 1024,
                'available': int(parts[1]) // 1024
            }
        except:
            return {'total': 4096, 'available': 2048}

    def _evaluate_capability(self, cpu_cores: int, memory_mb: int, is_container: bool = False) -> ServerCapability:
        """评估服务器能力"""
        if is_container:
            return ServerCapability.CONTAINER

        score = cpu_cores * 0.3 + (memory_mb / 1024) * 0.7

        if score >= 8:
            return ServerCapability.HIGH
        elif score >= 3:
            return ServerCapability.MEDIUM
        else:
            return ServerCapability.LOW

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_time.clear()


# 全局实例
analyzer = EnvironmentAnalyzer()
