"""
系统智能大脑
System Brain - Small Model Manager

自动下载和管理一个轻量级模型，作为系统的最小智能核心。
该模型始终存在，界面不可见，不可卸载。

增强功能：
1. UI 自动化理解 - 理解并操作软件界面
2. 推理模型支持 - 使用 DeepSeek-R1 等支持思考过程的模型
3. 连接超时优化 - 自动检测最优连接时间
"""

import os
import json
import subprocess
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import requests

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_sb = _get_unified_config()
except Exception:
    _uconfig_sb = None

def _sb_get(key: str, default):
    return _uconfig_sb.get(key, default) if _uconfig_sb else default


class ModelStatus(Enum):
    """模型状态"""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    READY = "ready"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class SystemBrainConfig:
    """系统大脑配置"""
    model_name: str = "qwen2.5:0.5b"
    model_repo: str = "qwen"  # ollama library
    download_url: str = ""  # 可选的备用下载URL
    max_tokens: int = 512
    temperature: float = 0.7
    num_ctx: int = 2048
    fallback_to_api: bool = True  #  Ollama 不可用时使用API
    api_base: str = "http://localhost:11434"  # Ollama API地址


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size: str
    digest: str
    modified: str
    status: ModelStatus = ModelStatus.NOT_DOWNLOADED
    download_progress: float = 0.0


class SystemBrain:
    """
    系统智能大脑
    
    功能：
    1. 自动检测并下载轻量级模型
    2. 管理模型的加载和卸载
    3. 提供简单的推理接口
    4. 作为系统的基础智能组件
    5. UI 自动化理解（集成 UIAutomation）
    6. 推理模型支持（DeepSeek-R1 等）
    7. 连接超时优化（自动调整）
    """
    
    # 默认模型配置
    DEFAULT_MODELS = [
        {
            "name": "qwen2.5:0.5b",
            "display_name": "Qwen 2.5 0.5B",
            "description": "通义千问轻量版，适合中文任务分解",
            "size": "~390MB",
            "recommended": True
        },
        {
            "name": "qwen2.5:1.5b", 
            "display_name": "Qwen 2.5 1.5B",
            "description": "通义千问中等版，平衡性能与速度",
            "size": "~1.1GB",
            "recommended": False
        },
        {
            "name": "deepseek-r1:1.5b",
            "display_name": "DeepSeek-R1 1.5B",
            "description": "深度推理模型，支持思考过程展示",
            "size": "~1.1GB",
            "recommended": False,
            "reasoning": True
        },
        {
            "name": "phi3:mini",
            "display_name": "Phi-3 Mini",
            "description": "微软Phi-3迷你版，英文能力强",
            "size": "~2.3GB",
            "recommended": False
        },
        {
            "name": "llama3.2:1b",
            "display_name": "Llama 3.2 1B",
            "description": "Meta Llama轻量版，多语言支持",
            "size": "~1.3GB",
            "recommended": False
        }
    ]
    
    # 支持推理的模型
    REASONING_MODELS = [
        "deepseek-r1",
        "deepseek-coder-r1",
        "qwq",
        "qwen2.5-reasoning",
        "llama3.2-reasoning"
    ]
    
    def __init__(
        self,
        config: SystemBrainConfig = None,
        models_dir: str = None,
        status_callback: Callable[[str, float], None] = None
    ):
        """
        初始化系统大脑
        
        Args:
            config: 配置（使用默认配置如果为None）
            models_dir: 模型存储目录
            status_callback: 状态回调 (status_msg, progress)
        """
        self.config = config or SystemBrainConfig()
        self.status_callback = status_callback
        
        # 模型目录
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            self.models_dir = self._get_default_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # 状态
        self._status = ModelStatus.NOT_DOWNLOADED
        self._model_info: Optional[ModelInfo] = None
        self._is_available = False
        self._lock = threading.Lock()
        
        # HTTP Session for API calls
        self._session = requests.Session()
        
        # 连接时间记录（用于超时优化）
        self._connection_times: List[float] = []
        self._optimal_timeout: Optional[float] = None
        
        # UI 自动化（延迟加载）
        self._ui_automation = None
        
        # 推理客户端（延迟加载）
        self._reasoning_client = None
        
        # 检查Ollama状态
        self._check_ollama()
    
    def _get_default_models_dir(self) -> Path:
        """获取默认模型目录"""
        # 优先用户目录
        user_dir = Path.home() / ".hermes-desktop" / "models" / "system_brain"
        if os.access(str(Path.home()), os.W_OK):
            return user_dir
        
        # 兜底到软件目录
        sw_dir = Path(__file__).parent.parent
        return sw_dir / "models" / "system_brain"
    
    def _check_ollama(self) -> bool:
        """检查Ollama是否可用"""
        try:
            resp = self._session.get(
                f"{self.config.api_base}/api/tags",
                timeout=_sb_get("timeouts.quick", 5)
            )
            if resp.status_code == 200:
                self._is_available = True
                return True
        except Exception:
            pass
        
        self._is_available = False
        return False
    
    @property
    def is_available(self) -> bool:
        """系统大脑是否可用"""
        return self._is_available and self._status in [ModelStatus.READY, ModelStatus.LOADED]
    
    @property
    def status(self) -> ModelStatus:
        """当前状态"""
        return self._status
    
    @property
    def current_model(self) -> Optional[str]:
        """当前模型名"""
        if self._model_info:
            return self._model_info.name
        return None
    
    def get_model_list(self) -> list:
        """获取可用模型列表"""
        return self.DEFAULT_MODELS.copy()
    
    def _report_status(self, msg: str, progress: float = -1):
        """报告状态"""
        if self.status_callback:
            self.status_callback(msg, progress)
    
    def check_and_prepare(self) -> bool:
        """
        检查并准备模型
        
        Returns:
            是否准备就绪
        """
        with self._lock:
            # 检查Ollama
            if not self._check_ollama():
                self._report_status("Ollama未运行，正在尝试启动...", 0)
                self._try_start_ollama()
            
            # 检查模型是否已下载
            self._check_local_models()
            
            # 如果模型未下载，自动下载
            if self._status == ModelStatus.NOT_DOWNLOADED:
                return self.download_model(self.config.model_name)
            
            return self._status in [ModelStatus.READY, ModelStatus.LOADED]
    
    def _check_local_models(self):
        """检查本地已下载的模型"""
        try:
            resp = self._session.get(
                f"{self.config.api_base}/api/tags",
                timeout=_sb_get("timeouts.quick", 5)
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for model in models:
                    if self.config.model_name in model.get("name", ""):
                        self._model_info = ModelInfo(
                            name=model["name"],
                            size=self._format_size(model.get("size", 0)),
                            digest=model.get("digest", "")[:12],
                            modified=model.get("modified_at", "")[:10],
                            status=ModelStatus.READY
                        )
                        self._status = ModelStatus.READY
                        self._report_status(f"模型已就绪: {self._model_info.name}", 1.0)
                        return
                
                # 模型未找到
                self._status = ModelStatus.NOT_DOWNLOADED
        except Exception:
            self._status = ModelStatus.NOT_DOWNLOADED
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    def _try_start_ollama(self):
        """尝试启动Ollama"""
        import platform
        
        system = platform.system().lower()
        
        try:
            if system == "windows":
                # Windows上尝试启动Ollama
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, 'DETACHED_PROCESS') else 0
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            # 等待Ollama启动
            import time
            _wait_short = _sb_get("delays.wait_short", 1)
            for _ in range(10):
                time.sleep(_wait_short)
                if self._check_ollama():
                    self._report_status("Ollama已启动", 0.1)
                    return
                    
        except Exception as e:
            self._report_status(f"启动Ollama失败: {e}", 0)
    
    def download_model(self, model_name: str = None, progress_callback: Callable[[float, str], None] = None) -> bool:
        """
        下载模型
        
        Args:
            model_name: 模型名
            progress_callback: 进度回调 (progress, status_msg)
            
        Returns:
            是否下载成功
        """
        model_name = model_name or self.config.model_name
        self._report_status(f"正在下载模型: {model_name}", 0)
        
        def run_download():
            try:
                # 使用ollama pull下载
                self._status = ModelStatus.DOWNLOADING
                
                process = subprocess.Popen(
                    ["ollama", "pull", model_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                for line in process.stdout:
                    line = line.strip()
                    
                    # 解析进度
                    if "downloading" in line.lower():
                        # 提取百分比
                        import re
                        match = re.search(r'(\d+)%', line)
                        if match:
                            progress = int(match.group(1)) / 100
                            self._report_status(f"下载中: {line}", progress)
                            if progress_callback:
                                progress_callback(progress, line)
                    
                    # 下载完成
                    if "pulling manifest" in line.lower() or "verifying" in line.lower():
                        self._report_status("验证模型...", 0.95)
                
                process.wait()
                
                if process.returncode == 0:
                    self._status = ModelStatus.READY
                    self._model_info = ModelInfo(
                        name=model_name,
                        size="~390MB",
                        digest="",
                        modified="",
                        status=ModelStatus.READY
                    )
                    self._report_status("模型下载完成", 1.0)
                    return True
                else:
                    self._status = ModelStatus.ERROR
                    self._report_status("模型下载失败", 0)
                    return False
                    
            except Exception as e:
                self._status = ModelStatus.ERROR
                self._report_status(f"下载出错: {e}", 0)
                return False
        
        # 在后台线程下载
        thread = threading.Thread(target=run_download, daemon=True)
        thread.start()
        
        # 如果同步等待
        thread.join()
        return self._status == ModelStatus.READY
    
    def load_model(self) -> bool:
        """
        加载模型到内存
        
        Returns:
            是否加载成功
        """
        if not self._is_available:
            if not self._check_ollama():
                return False
        
        self._status = ModelStatus.LOADING
        self._report_status("加载模型中...", 0)
        
        try:
            # 调用ollama API生成一个token来预热/加载模型
            resp = self._session.post(
                f"{self.config.api_base}/api/generate",
                json={
                    "model": self.config.model_name,
                    "prompt": "hello",
                    "stream": False,
                    "options": {
                        "num_predict": 1
                    }
                },
                timeout=_sb_get("timeouts.long", 60)
            )
            
            if resp.status_code == 200:
                self._status = ModelStatus.LOADED
                self._report_status("模型已就绪", 1.0)
                return True
            else:
                self._status = ModelStatus.ERROR
                return False
                
        except Exception as e:
            self._status = ModelStatus.ERROR
            self._report_status(f"加载失败: {e}", 0)
            return False
    
    def unload_model(self):
        """卸载模型释放内存"""
        try:
            # 使用ollama PS查看当前模型，然后删除
            self._session.delete(
                f"{self.config.api_base}/api/generate",
                json={"model": self.config.model_name}
            )
        except Exception:
            pass
        
        self._status = ModelStatus.READY
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = None,
        temperature: float = None,
        stream: bool = False,
        callback: Callable[[str], None] = None
    ) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            max_tokens: 最大token数
            temperature: 温度参数
            stream: 是否流式输出
            callback: 流式回调
            
        Returns:
            生成的文本
        """
        if not self._is_available:
            return "[错误] 系统大脑不可用，请确保Ollama正在运行"
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature or self.config.temperature
        
        try:
            if stream:
                return self._generate_stream(prompt, max_tokens, temperature, callback)
            else:
                return self._generate_sync(prompt, max_tokens, temperature)
        except Exception as e:
            return f"[错误] 生成失败: {e}"
    
    def _generate_sync(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """同步生成"""
        resp = self._session.post(
            f"{self.config.api_base}/api/generate",
            json={
                "model": self.config.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "num_ctx": self.config.num_ctx
                }
            },
            timeout=_sb_get("timeouts.llm_generate", 120)
        )
        
        if resp.status_code == 200:
            return resp.json().get("response", "")
        else:
            return f"[错误] API返回: {resp.status_code}"
    
    def _generate_stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        callback: Callable[[str], None]
    ) -> str:
        """流式生成"""
        resp = self._session.post(
            f"{self.config.api_base}/api/generate",
            json={
                "model": self.config.model_name,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "num_ctx": self.config.num_ctx
                }
            },
            stream=True,
            timeout=_sb_get("timeouts.llm_generate", 120)
        )
        
        full_response = ""
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
                    full_response += token
                    if callback:
                        callback(token)
                except json.JSONDecodeError:
                    continue
        
        return full_response
    
    def think(
        self,
        question: str,
        context: str = None,
        use_chain_of_thought: bool = True
    ) -> Dict[str, Any]:
        """
        系统思考（整合链式思考）
        
        Args:
            question: 问题
            context: 上下文
            use_chain_of_thought: 是否使用链式思考
            
        Returns:
            {
                "answer": str,           # 最终答案
                "thinking_process": str, # 思考过程
                "confidence": float,     # 置信度
                "steps": list           # 分解的步骤
            }
        """
        from core.task_decomposer import get_chain_of_thought_prompt
        
        if use_chain_of_thought:
            prompt = get_chain_of_thought_prompt(question)
        else:
            prompt = question
        
        if context:
            prompt = f"上下文: {context}\n\n{prompt}"
        
        # 生成
        response = self.generate(prompt, max_tokens=1024)
        
        # 简单解析置信度
        confidence = 0.8
        if "置信度：低" in response or "confidence: low" in response.lower():
            confidence = 0.4
        elif "置信度：中" in response or "confidence: medium" in response.lower():
            confidence = 0.6
        
        return {
            "answer": response,
            "thinking_process": "",  # 可以进一步解析
            "confidence": confidence,
            "steps": []
        }
    
    def is_model_downloaded(self, model_name: str = None) -> bool:
        """检查模型是否已下载"""
        model_name = model_name or self.config.model_name
        
        try:
            resp = self._session.get(
                f"{self.config.api_base}/api/tags",
                timeout=_sb_get("timeouts.quick", 5)
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(model_name in m.get("name", "") for m in models)
        except Exception:
            pass
        
        return False
    
    def delete_model(self, model_name: str = None) -> bool:
        """
        删除模型（谨慎使用）
        
        注意：系统大脑模型默认不可删除
        
        Args:
            model_name: 模型名
            
        Returns:
            是否删除成功
        """
        model_name = model_name or self.config.model_name
        
        # 保护系统大脑
        if model_name == self.config.model_name:
            return False
        
        try:
            resp = self._session.delete(
                f"{self.config.api_base}/api/delete",
                json={"name": model_name}
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "is_available": self.is_available,
            "status": self._status.value,
            "model_name": self.current_model,
            "model_info": self._model_info.__dict__ if self._model_info else None,
            "ollama_available": self._is_available
        }

    # ── UI 自动化功能 ────────────────────────────────────────────────

    def get_ui_automation(self):
        """
        获取 UI 自动化实例

        Returns:
            UIAutomation 实例
        """
        if self._ui_automation is None:
            try:
                from core.ui_automation import UIAutomation
                self._ui_automation = UIAutomation(system_brain=self)
            except ImportError as e:
                raise ImportError(
                    f"UI 自动化模块未安装: {e}\n"
                    "请运行: pip install mss pyautogui Pillow opencv-python"
                )
        return self._ui_automation

    def execute_ui_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        执行 UI 操作指令

        Args:
            instruction: 自然语言指令，如"点击确定按钮"

        Returns:
            执行结果
        """
        automation = self.get_ui_automation()
        result = automation.execute_instruction(instruction)

        return {
            "success": result.success,
            "message": result.message,
            "action_type": result.action.action_type.value,
            "screenshot_after": result.screenshot_after
        }

    def analyze_screen(self) -> Dict[str, Any]:
        """
        分析当前屏幕

        Returns:
            UI 分析结果
        """
        automation = self.get_ui_automation()
        return automation.analyze_screen()

    # ── 推理模型功能 ────────────────────────────────────────────────

    def is_reasoning_model(self, model_name: str = None) -> bool:
        """
        检查是否为推理模型

        Args:
            model_name: 模型名（None=当前模型）

        Returns:
            是否为推理模型
        """
        model_name = (model_name or self.current_model or "").lower()
        return any(r_model in model_name for r_model in self.REASONING_MODELS)

    def get_reasoning_client(self):
        """
        获取推理客户端

        Returns:
            ReasoningModelClient 实例
        """
        if self._reasoning_client is None:
            from core.reasoning_client import ReasoningModelClient, ReasoningConfig

            model_name = self.current_model or "deepseek-r1:1.5b"

            config = ReasoningConfig(
                model_name=model_name,
                base_url=self.config.api_base,
                timeout=self.config.max_tokens * 0.1,  # 粗略估计
                connect_timeout=_sb_get("timeouts.default", 30.0),
                track_connection_times=True
            )

            self._reasoning_client = ReasoningModelClient(config)
            self._reasoning_client.connect()

        return self._reasoning_client

    def generate_with_reasoning(
        self,
        prompt: str,
        system_prompt: str = None,
        reasoning_callback: Callable[[str], None] = None,
        stream_callback: Callable[[str], None] = None
    ) -> Dict[str, Any]:
        """
        使用推理模型生成（带思考过程）

        Args:
            prompt: 提示词
            system_prompt: 系统提示
            reasoning_callback: 思考过程回调
            stream_callback: 流式输出回调

        Returns:
            {
                "final_answer": str,
                "reasoning": str,
                "raw_output": str,
                "input_params": dict,
                "duration": float
            }
        """
        client = self.get_reasoning_client()
        result = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            reasoning_callback=reasoning_callback,
            stream_callback=stream_callback
        )

        return {
            "final_answer": result.final_answer,
            "reasoning": result.reasoning,
            "raw_output": result.raw_output,
            "input_params": result.input_params,
            "duration": result.duration,
            "model_type": result.model_type.value
        }

    # ── 连接超时优化 ────────────────────────────────────────────────

    def _record_connection_time(self, connect_time: float):
        """记录连接时间"""
        self._connection_times.append(connect_time)

        # 保持最近 50 条记录
        if len(self._connection_times) > 50:
            self._connection_times = self._connection_times[-50:]

        # 计算最优超时（使用 P95）
        if len(self._connection_times) >= 10:
            sorted_times = sorted(self._connection_times)
            p95_index = int(len(sorted_times) * 0.95)
            self._optimal_timeout = sorted_times[p95_index] * 1.5  # 留 50% 余量

    def get_optimal_timeout(self) -> float:
        """
        获取最优超时时间

        Returns:
            最优超时秒数
        """
        if self._optimal_timeout:
            return self._optimal_timeout

        # 默认超时
        return 30.0

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        stats = {
            "total_records": len(self._connection_times),
            "optimal_timeout": self._optimal_timeout,
        }

        if self._connection_times:
            stats.update({
                "avg_connect_time": sum(self._connection_times) / len(self._connection_times),
                "min_connect_time": min(self._connection_times),
                "max_connect_time": max(self._connection_times)
            })

        # 推理客户端统计
        if self._reasoning_client:
            client_stats = self._reasoning_client.get_connection_stats()
            stats["reasoning_client"] = client_stats

        return stats

    # ── 增强的 generate 方法 ───────────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_tokens: int = None,
        temperature: float = None,
        stream: bool = False,
        callback: Callable[[str], None] = None,
        reasoning_callback: Callable[[str], None] = None,
        use_reasoning_model: bool = None
    ) -> str:
        """
        生成文本（增强版）

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数
            temperature: 温度参数
            stream: 是否流式输出
            callback: 流式回调
            reasoning_callback: 思考过程回调（仅推理模型）
            use_reasoning_model: 是否使用推理模型（None=自动检测）

        Returns:
            生成的文本
        """
        # 自动检测是否使用推理模型
        if use_reasoning_model is None:
            use_reasoning_model = self.is_reasoning_model()

        if use_reasoning_model and reasoning_callback:
            # 使用推理模型
            result = self.generate_with_reasoning(
                prompt=prompt,
                reasoning_callback=reasoning_callback,
                stream_callback=callback
            )
            return result["final_answer"]
        else:
            # 使用普通生成
            return self._generate_sync(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

    def _generate_sync(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """同步生成（带超时优化）"""
        # 使用优化的超时时间
        optimal_timeout = self.get_optimal_timeout()

        start_time = time.time()

        try:
            resp = self._session.post(
                f"{self.config.api_base}/api/generate",
                json={
                    "model": self.config.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                        "num_ctx": self.config.num_ctx
                    }
                },
                timeout=optimal_timeout
            )

            connect_time = time.time() - start_time
            self._record_connection_time(connect_time)

            if resp.status_code == 200:
                return resp.json().get("response", "")
            else:
                return f"[错误] API返回: {resp.status_code}"

        except requests.exceptions.Timeout:
            # 超时，尝试重连
            self._report_status(f"连接超时 ({optimal_timeout:.1f}s)，正在重试...", -1)
            return "[错误] 连接超时，请稍后重试"

        except Exception as e:
            return f"[错误] 生成失败: {e}"

    # ── 便捷方法 ───────────────────────────────────────────────────

    def think(self, question: str) -> Dict[str, Any]:
        """
        思考问题（使用推理模型）

        Args:
            question: 问题

        Returns:
            {
                "answer": str,
                "reasoning": str,
                "confidence": float
            }
        """
        result = self.generate_with_reasoning(
            prompt=question,
            reasoning_callback=None
        )

        # 估算置信度
        confidence = 0.8
        if "可能" in result["reasoning"] or "也许" in result["reasoning"]:
            confidence = 0.6

        return {
            "answer": result["final_answer"],
            "reasoning": result["reasoning"],
            "confidence": confidence,
            "input_params": result["input_params"]
        }

    def analyze_ui_and_act(self, instruction: str) -> Dict[str, Any]:
        """
        分析屏幕并执行操作（组合操作）

        Args:
            instruction: 操作指令

        Returns:
            执行结果
        """
        # 1. 先分析屏幕
        screen_analysis = self.analyze_screen()

        # 2. 解析操作
        automation = self.get_ui_automation()
        action = automation.parse_operation(instruction)

        # 3. 执行操作
        result = automation.execute_action(action)

        return {
            "screen_analysis": screen_analysis,
            "action": action.action_type.value,
            "target": action.target,
            "success": result.success,
            "message": result.message,
            "screenshot": result.screenshot_after
        }


# 单例
_system_brain: Optional[SystemBrain] = None


def get_system_brain(
    config: SystemBrainConfig = None,
    status_callback: Callable[[str, float], None] = None
) -> SystemBrain:
    """获取系统大脑单例"""
    global _system_brain
    if _system_brain is None:
        _system_brain = SystemBrain(config, status_callback=status_callback)
    return _system_brain


def init_system_brain_async(
    config: SystemBrainConfig = None,
    callback: Callable[[bool], None] = None
) -> SystemBrain:
    """异步初始化系统大脑"""
    brain = get_system_brain(config)
    
    def init():
        result = brain.check_and_prepare()
        if callback:
            callback(result)
    
    thread = threading.Thread(target=init, daemon=True)
    thread.start()
    
    return brain
