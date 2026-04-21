"""
运行时管理器 (Runtime Manager)
==============================

统一管理已部署模型的运行状态

功能：
1. Python模型 - 直接import调用
2. CLI模型 - 进程池管理
3. Docker模型 - 容器状态监控
4. API模型 - HTTP客户端管理

Author: Hermes Desktop AI Assistant
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import queue
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class RuntimeType(Enum):
    """运行时类型"""
    PYTHON = "python"   # Python直接调用
    CLI = "cli"         # 命令行执行
    REST = "rest"       # REST API
    GRPC = "grpc"       # gRPC


class RuntimeStatus(Enum):
    """运行时状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 忙碌
    ERROR = "error"         # 错误
    STOPPED = "stopped"     # 已停止


@dataclass
class RuntimeInfo:
    """运行时信息"""
    model_id: str
    runtime_type: RuntimeType
    status: RuntimeStatus
    process_id: Optional[int] = None       # 进程ID
    container_id: Optional[str] = None     # Docker容器ID
    endpoint: Optional[str] = None          # API端点
    port: Optional[int] = None             # 端口
    start_time: Optional[datetime] = None
    last_use: Optional[datetime] = None
    use_count: int = 0
    error_message: Optional[str] = None

    # 资源使用
    cpu_percent: float = 0.0
    memory_mb: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'model_id': self.model_id,
            'runtime_type': self.runtime_type.value,
            'status': self.status.value,
            'process_id': self.process_id,
            'container_id': self.container_id,
            'endpoint': self.endpoint,
            'port': self.port,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_use': self.last_use.isoformat() if self.last_use else None,
            'use_count': self.use_count,
            'cpu_percent': self.cpu_percent,
            'memory_mb': self.memory_mb,
        }


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class ProcessPool:
    """
    CLI进程池

    对于频繁调用的CLI模型，复用进程避免频繁启动开销
    """

    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self._pools: Dict[str, List[subprocess.Popen]] = {}
        self._lock = threading.Lock()

    def get_process(self, model_id: str, command: str, env: Optional[Dict] = None) -> Optional[subprocess.Popen]:
        """获取可用进程"""
        with self._lock:
            if model_id not in self._pools:
                self._pools[model_id] = []

            pool = self._pools[model_id]

            # 查找空闲进程
            for proc in pool:
                if proc.poll() is None:  # 进程仍在运行
                    return proc

            # 创建新进程（如果未达上限）
            if len(pool) < self.max_size:
                try:
                    full_env = os.environ.copy()
                    if env:
                        full_env.update(env)

                    proc = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=full_env
                    )
                    pool.append(proc)
                    return proc
                except Exception as e:
                    logger.error(f"创建进程失败: {e}")

            return None

    def release(self, model_id: str, proc: subprocess.Popen):
        """释放进程回池"""
        # 进程继续保留在池中供下次使用
        pass

    def cleanup(self, model_id: str):
        """清理指定模型的进程池"""
        with self._lock:
            if model_id in self._pools:
                for proc in self._pools[model_id]:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()
                self._pools[model_id].clear()

    def cleanup_all(self):
        """清理所有进程池"""
        with self._lock:
            for model_id, pool in self._pools.items():
                for proc in pool:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()
            self._pools.clear()


class RESTClient:
    """
    REST API客户端

    管理API模型的HTTP请求
    """

    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self._session = None
        self._lock = threading.Lock()

    def get_session(self):
        """获取或创建会话"""
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def post(self, endpoint: str, data: Dict, headers: Optional[Dict] = None) -> ExecutionResult:
        """POST请求"""
        import requests

        start_time = time.time()

        try:
            response = self.get_session().post(
                endpoint,
                json=data,
                headers=headers,
                timeout=self.timeout
            )

            execution_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return ExecutionResult(
                    success=True,
                    output=response.json(),
                    execution_time_ms=execution_time,
                    stdout=str(response.status_code)
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                    execution_time_ms=execution_time,
                    stderr=response.text
                )

        except requests.Timeout:
            return ExecutionResult(
                success=False,
                error=f"请求超时 ({self.timeout}s)",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )

    def get(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> ExecutionResult:
        """GET请求"""
        import requests

        start_time = time.time()

        try:
            response = self.get_session().get(
                endpoint,
                params=params,
                headers=headers,
                timeout=self.timeout
            )

            execution_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return ExecutionResult(
                    success=True,
                    output=response.json(),
                    execution_time_ms=execution_time
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                    execution_time_ms=execution_time
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )


class RuntimeManager:
    """
    运行时管理器

    统一管理所有模型的运行时状态

    使用示例：
        manager = RuntimeManager()
        result = manager.execute('pyswmm', input_data={'file': 'test.inp'})
    """

    def __init__(self, install_dir: Optional[str] = None):
        """
        初始化运行时管理器

        Args:
            install_dir: 模型安装目录
        """
        self.install_dir = Path(install_dir or os.path.expanduser('~/.model_store/installs'))

        # 运行时信息缓存
        self._runtimes: Dict[str, RuntimeInfo] = {}

        # 进程池
        self._process_pool = ProcessPool(max_size=3)

        # REST客户端
        self._rest_clients: Dict[str, RESTClient] = {}

        # Docker客户端
        self._docker_client = None

        # 密钥管理（延迟导入）
        self._key_manager = None

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()

        logger.info("RuntimeManager 初始化完成")

    def execute(self, model_id: str, model_info, input_data: Any, timeout: Optional[int] = None) -> ExecutionResult:
        """
        执行模型（主入口）

        Args:
            model_id: 模型ID
            model_info: 模型信息
            input_data: 输入数据
            timeout: 超时时间（秒）

        Returns:
            ExecutionResult: 执行结果
        """
        runtime_type = model_info.runtime.type

        # 更新运行时信息
        self._update_runtime_info(model_id, model_info, RuntimeStatus.BUSY)

        try:
            if runtime_type == RuntimeType.PYTHON:
                return self._execute_python(model_id, model_info, input_data, timeout)
            elif runtime_type == RuntimeType.CLI:
                return self._execute_cli(model_id, model_info, input_data, timeout)
            elif runtime_type == RuntimeType.REST:
                return self._execute_rest(model_id, model_info, input_data, timeout)
            elif runtime_type == RuntimeType.GRPC:
                return self._execute_grpc(model_id, model_info, input_data, timeout)
            else:
                return ExecutionResult(
                    success=False,
                    error=f"不支持的运行时类型: {runtime_type}"
                )

        except Exception as e:
            logger.error(f"执行模型 {model_id} 失败: {e}")
            self._update_runtime_info(model_id, model_info, RuntimeStatus.ERROR, error=str(e))
            return ExecutionResult(success=False, error=str(e))

    def _execute_python(self, model_id: str, model_info, input_data: Any, timeout: Optional[int]) -> ExecutionResult:
        """执行Python模型"""
        import importlib

        start_time = time.time()

        try:
            # 动态导入模块
            module_name = model_info.runtime.entry_module or model_id
            module = importlib.import_module(module_name)

            # 调用主函数（假设模块有run或predict函数）
            if hasattr(module, 'run'):
                output = module.run(input_data)
            elif hasattr(module, 'predict'):
                output = module.predict(input_data)
            elif hasattr(module, 'execute'):
                output = module.execute(input_data)
            else:
                # 返回模块信息
                output = {'module': module_name, 'functions': dir(module)}

            execution_time = (time.time() - start_time) * 1000

            self._update_runtime_info(model_id, model_info, RuntimeStatus.IDLE)

            return ExecutionResult(
                success=True,
                output=output,
                execution_time_ms=execution_time
            )

        except ImportError as e:
            return ExecutionResult(
                success=False,
                error=f"模块导入失败: {module_name}，请先安装",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )

    def _execute_cli(self, model_id: str, model_info, input_data: Any, timeout: Optional[int]) -> ExecutionResult:
        """执行CLI模型"""
        command = model_info.runtime.command
        env_vars = model_info.runtime.env or {}
        timeout = timeout or model_info.runtime.timeout

        # 准备输入文件
        input_path = self._prepare_input_file(model_id, input_data)

        # 构建命令
        cmd = command.replace('{input}', str(input_path))

        # 获取环境变量
        full_env = os.environ.copy()
        full_env.update(env_vars)

        # 添加模型目录到PATH
        model_dir = self.install_dir / model_id
        if model_dir.exists():
            bin_dir = model_dir / 'bin'
            if bin_dir.exists():
                full_env['PATH'] = str(bin_dir) + os.pathsep + full_env.get('PATH', '')

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=full_env
            )

            execution_time = (time.time() - start_time) * 1000

            # 解析输出
            output = self._parse_output(result.stdout, model_info)

            self._update_runtime_info(model_id, model_info, RuntimeStatus.IDLE)

            return ExecutionResult(
                success=result.returncode == 0,
                output=output,
                execution_time_ms=execution_time,
                stdout=result.stdout,
                stderr=result.stderr
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时 ({timeout}s)",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )

    def _execute_rest(self, model_id: str, model_info, input_data: Any, timeout: Optional[int]) -> ExecutionResult:
        """执行REST API模型"""
        endpoint = model_info.runtime.endpoint
        timeout = timeout or model_info.runtime.timeout

        # 获取REST客户端
        if model_id not in self._rest_clients:
            self._rest_clients[model_id] = RESTClient(timeout=timeout)

        client = self._rest_clients[model_id]

        # 获取认证头
        headers = self._get_auth_headers(model_info)

        # 发送请求
        result = client.post(endpoint, input_data, headers)

        self._update_runtime_info(
            model_id, model_info,
            RuntimeStatus.IDLE if result.success else RuntimeStatus.ERROR
        )

        return result

    def _execute_grpc(self, model_id: str, model_info, input_data: Any, timeout: Optional[int]) -> ExecutionResult:
        """执行gRPC模型"""
        # gRPC支持（简化实现）
        return ExecutionResult(
            success=False,
            error="gRPC支持待实现"
        )

    def _prepare_input_file(self, model_id: str, input_data: Any) -> Path:
        """准备输入文件"""
        model_dir = self.install_dir / model_id / 'data'
        model_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hash_suffix = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        input_file = model_dir / f"input_{timestamp}_{hash_suffix}.json"

        # 写入输入数据
        if isinstance(input_data, dict):
            with open(input_file, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, ensure_ascii=False, indent=2)
        else:
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(str(input_data))

        return input_file

    def _parse_output(self, stdout: str, model_info) -> Any:
        """解析CLI输出"""
        # 尝试解析JSON
        try:
            return json.loads(stdout)
        except Exception:
            pass

        # 返回原始文本
        return {'output': stdout, 'format': 'text'}

    def _get_auth_headers(self, model_info) -> Dict[str, str]:
        """获取认证头"""
        headers = {}

        # 从密钥管理获取API Key
        if self._key_manager:
            try:
                provider = model_info.install.provider if hasattr(model_info.install, 'provider') else None
                if provider:
                    api_key = self._key_manager.get_key(provider.lower())
                    if api_key:
                        auth_type = model_info.install.auth_type if hasattr(model_info.install, 'auth_type') else 'api_key'
                        if auth_type == 'bearer':
                            headers['Authorization'] = f"Bearer {api_key}"
                        else:
                            headers['X-API-Key'] = api_key
            except Exception as e:
                logger.warning(f"获取API Key失败: {e}")

        return headers

    def _update_runtime_info(self, model_id: str, model_info, status: RuntimeStatus, error: Optional[str] = None):
        """更新运行时信息"""
        if model_id in self._runtimes:
            runtime = self._runtimes[model_id]
            runtime.status = status
            runtime.last_use = datetime.now()
            runtime.use_count += 1
            if error:
                runtime.error_message = error
        else:
            runtime = RuntimeInfo(
                model_id=model_id,
                runtime_type=model_info.runtime.type,
                status=status,
                start_time=datetime.now(),
                error_message=error
            )
            self._runtimes[model_id] = runtime

    def get_runtime_info(self, model_id: str) -> Optional[RuntimeInfo]:
        """获取运行时信息"""
        return self._runtimes.get(model_id)

    def list_runtimes(self) -> List[RuntimeInfo]:
        """列出所有运行时"""
        return list(self._runtimes.values())

    def start_monitoring(self, interval: int = 30):
        """启动资源监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()

        logger.info(f"运行时监控已启动（间隔 {interval}s）")

    def stop_monitoring(self):
        """停止资源监控"""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

    def _monitor_loop(self, interval: int):
        """监控循环"""
        while not self._stop_monitor.is_set():
            try:
                self._update_resource_usage()
            except Exception as e:
                logger.error(f"资源监控错误: {e}")

            self._stop_monitor.wait(interval)

    def _update_resource_usage(self):
        """更新资源使用情况"""
        import psutil

        for runtime in self._runtimes.values():
            if runtime.process_id:
                try:
                    process = psutil.Process(runtime.process_id)
                    runtime.cpu_percent = process.cpu_percent()
                    runtime.memory_mb = process.memory_info().rss / 1024 / 1024
                except Exception:
                    pass

    def stop_runtime(self, model_id: str) -> bool:
        """停止运行时"""
        if model_id not in self._runtimes:
            return False

        runtime = self._runtimes[model_id]

        try:
            if runtime.process_id:
                import psutil
                process = psutil.Process(runtime.process_id)
                process.terminate()
                process.wait(timeout=10)

            elif runtime.container_id:
                if self._docker_client:
                    container = self._docker_client.containers.get(runtime.container_id)
                    container.stop()

            runtime.status = RuntimeStatus.STOPPED
            return True

        except Exception as e:
            logger.error(f"停止运行时 {model_id} 失败: {e}")
            return False

    def cleanup(self):
        """清理所有运行时"""
        # 清理进程池
        self._process_pool.cleanup_all()

        # 停止监控
        self.stop_monitoring()

        logger.info("运行时管理器已清理")


# 延迟导入避免循环
from .model_registry import RuntimeType