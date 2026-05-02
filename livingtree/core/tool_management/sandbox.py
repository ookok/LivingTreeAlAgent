import subprocess
import tempfile
import os
import shutil
import signal
import threading
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxConfig:
    enabled: bool = True
    max_execution_time: int = 300
    max_memory_mb: int = 512
    max_filesize_mb: int = 100
    allow_network: bool = True
    allow_write: bool = True
    working_dir: Optional[str] = None


@dataclass
class ExecutionContext:
    sandbox_id: str
    working_dir: str
    env_vars: Dict[str, str]
    start_time: float
    process: Optional[subprocess.Popen] = None
    stdout: str = ""
    stderr: str = ""
    return_code: Optional[int] = None
    timed_out: bool = False


class ToolSandbox:
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.active_contexts: Dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()

    def execute(self, command: str, 
                inputs: Dict[str, Any] = None,
                env_vars: Dict[str, str] = None) -> Tuple[bool, str, str, int]:
        """
        在沙盒中执行命令
        
        Returns:
            (success, stdout, stderr, return_code)
        """
        if not self.config.enabled:
            return self._execute_direct(command, inputs, env_vars)
        
        sandbox_id = self._generate_id()
        working_dir = self._create_working_dir(sandbox_id)
        
        try:
            context = ExecutionContext(
                sandbox_id=sandbox_id,
                working_dir=working_dir,
                env_vars=env_vars or {},
                start_time=time.time()
            )
            
            with self._lock:
                self.active_contexts[sandbox_id] = context
            
            # 写入输入文件
            if inputs:
                self._write_inputs(context, inputs)
            
            # 执行命令
            full_env = os.environ.copy()
            full_env.update(context.env_vars)
            
            context.process = subprocess.Popen(
                command,
                shell=True,
                cwd=context.working_dir,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=self._set_limits if os.name != 'nt' else None
            )
            
            # 设置超时监控
            timeout_thread = threading.Thread(
                target=self._watch_timeout,
                args=(sandbox_id,)
            )
            timeout_thread.daemon = True
            timeout_thread.start()
            
            # 等待完成
            context.stdout, context.stderr = context.process.communicate(
                timeout=self.config.max_execution_time + 5
            )
            context.return_code = context.process.returncode
            
            # 读取输出文件
            outputs = self._read_outputs(context)
            
            success = context.return_code == 0 and not context.timed_out
            
            return success, context.stdout, context.stderr, context.return_code
            
        finally:
            self._cleanup(sandbox_id)

    def _execute_direct(self, command: str, inputs: Dict[str, Any], env_vars: Dict[str, str]) -> Tuple[bool, str, str, int]:
        """直接执行命令（不使用沙盒）"""
        full_env = os.environ.copy()
        if env_vars:
            full_env.update(env_vars)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config.max_execution_time
            )
            return result.returncode == 0, result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out", -1
        except Exception as e:
            return False, "", str(e), -1

    def _generate_id(self) -> str:
        """生成唯一沙盒ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    def _create_working_dir(self, sandbox_id: str) -> str:
        """创建临时工作目录"""
        base_dir = self.config.working_dir or tempfile.gettempdir()
        working_dir = os.path.join(base_dir, f"tool_sandbox_{sandbox_id}")
        os.makedirs(working_dir, exist_ok=True)
        return working_dir

    def _write_inputs(self, context: ExecutionContext, inputs: Dict[str, Any]):
        """将输入写入文件"""
        for key, value in inputs.items():
            if isinstance(value, dict) or isinstance(value, list):
                with open(os.path.join(context.working_dir, f"{key}.json"), 'w', encoding='utf-8') as f:
                    import json
                    json.dump(value, f, ensure_ascii=False, indent=2)
            elif isinstance(value, str) and (value.startswith('file://') or '\n' in value):
                if value.startswith('file://'):
                    src_path = value[7:]
                    dst_path = os.path.join(context.working_dir, os.path.basename(src_path))
                    shutil.copy(src_path, dst_path)
                else:
                    with open(os.path.join(context.working_dir, f"{key}.txt"), 'w', encoding='utf-8') as f:
                        f.write(value)
            else:
                with open(os.path.join(context.working_dir, f"{key}.txt"), 'w', encoding='utf-8') as f:
                    f.write(str(value))

    def _read_outputs(self, context: ExecutionContext) -> Dict[str, Any]:
        """读取输出文件"""
        outputs = {}
        for filename in os.listdir(context.working_dir):
            filepath = os.path.join(context.working_dir, filename)
            if os.path.isfile(filepath):
                name = os.path.splitext(filename)[0]
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        try:
                            import json
                            outputs[name] = json.loads(content)
                        except:
                            outputs[name] = content
                except:
                    pass
        return outputs

    def _watch_timeout(self, sandbox_id: str):
        """监控超时"""
        time.sleep(self.config.max_execution_time)
        
        with self._lock:
            context = self.active_contexts.get(sandbox_id)
            if context and context.process and context.return_code is None:
                context.timed_out = True
                self._kill_process(context.process)

    def _kill_process(self, process: subprocess.Popen):
        """终止进程"""
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)])
            else:
                os.kill(process.pid, signal.SIGTERM)
                time.sleep(1)
                if process.poll() is None:
                    os.kill(process.pid, signal.SIGKILL)
        except:
            pass

    def _set_limits(self):
        """设置资源限制（仅Unix）"""
        try:
            import resource
            # 设置CPU时间限制
            resource.setrlimit(resource.RLIMIT_CPU, (self.config.max_execution_time, self.config.max_execution_time))
            # 设置内存限制
            mem_limit = self.config.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        except:
            pass

    def _cleanup(self, sandbox_id: str):
        """清理沙盒环境"""
        with self._lock:
            context = self.active_contexts.pop(sandbox_id, None)
        
        if context and context.working_dir and os.path.exists(context.working_dir):
            try:
                shutil.rmtree(context.working_dir, ignore_errors=True)
            except:
                pass

    def get_active_contexts(self) -> Dict[str, ExecutionContext]:
        """获取所有活跃的执行上下文"""
        with self._lock:
            return dict(self.active_contexts)

    def cancel_execution(self, sandbox_id: str) -> bool:
        """取消正在执行的任务"""
        with self._lock:
            context = self.active_contexts.get(sandbox_id)
            if context and context.process and context.return_code is None:
                self._kill_process(context.process)
                context.return_code = -9
                return True
        return False

    def enable(self):
        """启用沙盒"""
        self.config.enabled = True

    def disable(self):
        """禁用沙盒"""
        self.config.enabled = False


sandbox = ToolSandbox()
