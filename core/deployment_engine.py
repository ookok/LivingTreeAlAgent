"""
自动化模型部署引擎
负责 L0-L4 模型的自动下载、部署和启动
"""

import os
import re
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
import httpx

from core.model_layer_config import (
    ModelTier, ServiceStatus, DeployMode,
    ModelDefinition, LayerConfig, LayerDeploymentConfig,
    L0_L4_MODELS, get_default_model_for_tier,
    check_ollama_installed, check_system_memory
)

# 导入配置获取函数
try:
    from client.src.business.config import get_config
except ImportError:
    get_config = None

from core.logger import get_logger
logger = get_logger('deployment_engine')


def _get_config(key: str, default=None):
    """获取配置值"""
    if get_config:
        return get_config(key, default=default)
    return default


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class DeploymentTask:
    """部署任务"""
    tier: ModelTier
    model_name: str
    action: str  # download, deploy, start, stop
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    tier: ModelTier
    model_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class DeploymentEngine:
    """
    自动化模型部署引擎
    
    功能：
    1. 自动检测 Ollama 安装状态
    2. 自动下载模型
    3. 自动部署模型到指定层级
    4. 启动/停止模型服务
    5. 状态监控和健康检查
    """

    def __init__(self, config: Optional[LayerDeploymentConfig] = None):
        self.config = config or LayerDeploymentConfig()
        self._ollama_running = False
        self._downloading_models: Dict[str, DeploymentTask] = {}
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        
        # 初始化时检查 Ollama 状态
        self._check_ollama_status()

    # ── 事件回调 ──────────────────────────────────────────────────────────────

    def add_callback(self, callback: Callable[[DeploymentTask], None]):
        """添加状态更新回调"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, task: DeploymentTask):
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(task)
            except Exception:
                pass

    # ── Ollama 管理 ───────────────────────────────────────────────────────────

    def _check_ollama_status(self) -> bool:
        """检查 Ollama 是否运行"""
        try:
            response = httpx.get(
                f"{self.config.ollama_base_url}/api/tags",
                timeout=_get_config("timeouts.quick", 5.0)
            )
            self._ollama_running = response.status_code == 200
            return self._ollama_running
        except Exception:
            self._ollama_running = False
            return False

    def is_ollama_installed(self) -> bool:
        """检查 Ollama 是否已安装"""
        return check_ollama_installed()

    def is_ollama_running(self) -> bool:
        """检查 Ollama 服务是否运行"""
        return self._check_ollama_status()

    def start_ollama(self) -> bool:
        """启动 Ollama 服务"""
        if self._ollama_running:
            return True
        
        try:
            # 在后台启动 ollama serve
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # 等待服务启动
            max_wait_attempts = _get_config("deploy.ollama_startup_attempts", 10)
            for _ in range(max_wait_attempts):
                time.sleep(_get_config("delays.wait_short", 1))
                if self._check_ollama_status():
                    return True
            
            return False
        except Exception:
            return False

    def stop_ollama(self) -> bool:
        """停止 Ollama 服务"""
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(
                    ["taskkill", "/F", "/IM", "ollama.exe"],
                    capture_output=True,
                    timeout=_get_config("timeouts.quick", 5)
                )
            else:
                subprocess.run(
                    ["pkill", "-f", "ollama serve"],
                    capture_output=True,
                    timeout=_get_config("timeouts.quick", 5)
                )
            self._ollama_running = False
            return True
        except Exception:
            return False

    # ── 模型管理 ─────────────────────────────────────────────────────────────

    def list_local_models(self) -> List[str]:
        """列出本地已安装的模型"""
        if not self._check_ollama_status():
            return []
        
        try:
            response = httpx.get(
                f"{self.config.ollama_base_url}/api/tags",
                timeout=_get_config("timeouts.default", 10.0)
            )
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except Exception:
            return []

    def is_model_installed(self, model_name: str) -> bool:
        """检查模型是否已安装"""
        local_models = self.list_local_models()
        return model_name in local_models

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取模型详细信息"""
        if not self._check_ollama_status():
            return None
        
        try:
            response = httpx.post(
                f"{self.config.ollama_base_url}/api/show",
                json={"name": model_name},
                timeout=_get_config("timeouts.default", 10.0)
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    # ── 模型下载 ─────────────────────────────────────────────────────────────

    def download_model(
        self,
        model_name: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> DeploymentResult:
        """
        下载模型
        
        Args:
            model_name: 模型名称
            progress_callback: 进度回调 (progress, status)
        
        Returns:
            DeploymentResult: 下载结果
        """
        tier = self._get_tier_for_model(model_name)
        
        # 检查模型是否已安装
        if self.is_model_installed(model_name):
            return DeploymentResult(
                success=True,
                tier=tier,
                model_name=model_name,
                message="模型已安装"
            )
        
        # 启动 Ollama（如未运行）
        if not self.start_ollama():
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="无法启动 Ollama 服务",
                error="Ollama 服务启动失败"
            )
        
        # 创建下载任务
        task = DeploymentTask(
            tier=tier,
            model_name=model_name,
            action="download",
            status="running",
            progress=0.0,
            message="开始下载...",
            started_at=time.time()
        )
        self._downloading_models[model_name] = task
        self._notify_callbacks(task)
        
        try:
            # 执行下载
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 监控下载进度
            for line in process.stdout:
                line = line.strip()
                
                # 解析下载进度
                if "Downloading" in line or "%" in line:
                    match = re.search(r'\((\d+)%\)', line)
                    if match:
                        progress = int(match.group(1)) / 100.0
                        task.progress = progress
                        task.message = line[:80]
                        self._notify_callbacks(task)
                        
                        if progress_callback:
                            progress_callback(progress, line[:80])
                
                if "verifying" in line.lower() or "creating" in line.lower():
                    task.progress = 0.95
                    task.message = line[:80]
                    self._notify_callbacks(task)
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                task.status = "completed"
                task.progress = 1.0
                task.message = "下载完成"
                task.completed_at = time.time()
                self._notify_callbacks(task)
                
                return DeploymentResult(
                    success=True,
                    tier=tier,
                    model_name=model_name,
                    message="模型下载成功",
                    details={"size_gb": self._estimate_model_size(model_name)}
                )
            else:
                stderr = process.stderr.read()
                task.status = "failed"
                task.error = stderr or "下载失败"
                task.completed_at = time.time()
                self._notify_callbacks(task)
                
                return DeploymentResult(
                    success=False,
                    tier=tier,
                    model_name=model_name,
                    message="模型下载失败",
                    error=stderr or "未知错误"
                )
        
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = time.time()
            self._notify_callbacks(task)
            
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="下载异常",
                error=str(e)
            )
        finally:
            with self._lock:
                if model_name in self._downloading_models:
                    del self._downloading_models[model_name]

    def _estimate_model_size(self, model_name: str) -> float:
        """估算模型大小"""
        for model in L0_L4_MODELS:
            if model.ollama_name == model_name:
                return model.size_gb
        return 0.0

    def _get_tier_for_model(self, model_name: str) -> ModelTier:
        """获取模型对应的层级"""
        for model in L0_L4_MODELS:
            if model.ollama_name == model_name:
                return model.tier
        return ModelTier.L0

    # ── 模型加载/卸载 ────────────────────────────────────────────────────────

    def load_model(
        self,
        model_name: str,
        keep_alive: str = "5m"
    ) -> DeploymentResult:
        """加载模型到内存"""
        tier = self._get_tier_for_model(model_name)
        
        if not self.is_model_installed(model_name):
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="模型未安装",
                error="请先下载模型"
            )
        
        try:
            response = httpx.post(
                f"{self.config.ollama_base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "",
                    "stream": False
                },
                timeout=_get_config("timeouts.long", 30.0)
            )
            
            if response.status_code == 200:
                return DeploymentResult(
                    success=True,
                    tier=tier,
                    model_name=model_name,
                    message=f"模型已加载 (keep_alive: {keep_alive})",
                    details={"keep_alive": keep_alive}
                )
            else:
                return DeploymentResult(
                    success=False,
                    tier=tier,
                    model_name=model_name,
                    message="模型加载失败",
                    error=f"HTTP {response.status_code}"
                )
        
        except Exception as e:
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="模型加载异常",
                error=str(e)
            )

    def unload_model(self, model_name: str) -> DeploymentResult:
        """卸载模型"""
        tier = self._get_tier_for_model(model_name)
        
        try:
            response = httpx.delete(
                f"{self.config.ollama_base_url}/api/delete",
                json={"name": model_name},
                timeout=_get_config("timeouts.long", 30.0)
            )
            
            return DeploymentResult(
                success=response.status_code == 200,
                tier=tier,
                model_name=model_name,
                message="模型已卸载" if response.status_code == 200 else "卸载失败"
            )
        
        except Exception as e:
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="卸载异常",
                error=str(e)
            )

    # ── 一键部署 ─────────────────────────────────────────────────────────────

    def auto_deploy_tier(
        self,
        tier: ModelTier,
        model: Optional[ModelDefinition] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> DeploymentResult:
        """自动部署指定层级的模型"""
        if model is None:
            model = get_default_model_for_tier(tier)
        
        if model is None:
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name="",
                message=f"{tier.value} 层无可用模型",
                error="未找到合适的模型"
            )
        
        model_name = model.ollama_name
        steps = []
        current_step = 0
        total_steps = 3
        
        def step_progress(p: float, status: str):
            if progress_callback:
                overall = (current_step + p) / total_steps
                progress_callback(overall, status)
        
        # 步骤 1: 检查/启动 Ollama
        current_step = 0
        if progress_callback:
            progress_callback(0, "检查 Ollama 服务...")
        
        if not self.is_ollama_installed():
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="Ollama 未安装",
                error="请先安装 Ollama: https://ollama.com/download"
            )
        
        if not self.start_ollama():
            return DeploymentResult(
                success=False,
                tier=tier,
                model_name=model_name,
                message="Ollama 服务启动失败",
                error="无法启动 Ollama"
            )
        
        steps.append("Ollama 就绪")
        
        # 步骤 2: 下载模型
        current_step = 1
        if progress_callback:
            progress_callback(0.33, f"下载 {model_name}...")
        
        if not self.is_model_installed(model_name):
            download_result = self.download_model(model_name, step_progress)
            if not download_result.success:
                return download_result
        else:
            steps.append("模型已安装")
        
        # 步骤 3: 加载模型
        current_step = 2
        if progress_callback:
            progress_callback(0.66, f"加载 {model_name}...")
        
        layer_config = self.config.layers.get(tier.value, LayerConfig(tier=tier))
        load_result = self.load_model(model_name, keep_alive=layer_config.keep_alive)
        if not load_result.success:
            return load_result
        
        steps.append("模型已加载")
        
        if progress_callback:
            progress_callback(1.0, "部署完成!")
        
        return DeploymentResult(
            success=True,
            tier=tier,
            model_name=model_name,
            message=f"{tier.value} 层部署成功",
            details={
                "model": model.model_dump(),
                "steps": steps,
                "size_gb": model.size_gb
            }
        )

    def auto_deploy_all(
        self,
        models: Optional[Dict[ModelTier, ModelDefinition]] = None,
        progress_callback: Optional[Callable[[float, str, ModelTier], None]] = None
    ) -> Dict[ModelTier, DeploymentResult]:
        """自动部署所有层级模型"""
        results = {}
        tiers = list(ModelTier)
        total_tiers = len(tiers)
        
        for i, tier in enumerate(tiers):
            model = models.get(tier) if models else None
            if model is None:
                model = get_default_model_for_tier(tier)
            
            def tier_callback(p: float, status: str):
                if progress_callback:
                    overall = (i + p) / total_tiers
                    progress_callback(overall, status, tier)
            
            result = self.auto_deploy_tier(tier, model, tier_callback)
            results[tier] = result
        
        return results

    # ── 状态查询 ─────────────────────────────────────────────────────────────

    def get_tier_status(self, tier: ModelTier) -> ServiceStatus:
        """获取指定层级的状态"""
        if not self._check_ollama_status():
            return ServiceStatus.STOPPED
        
        layer_config = self.config.layers.get(tier.value)
        if layer_config and layer_config.model:
            model_name = layer_config.model.ollama_name
            if self.is_model_installed(model_name):
                return ServiceStatus.RUNNING
        
        return ServiceStatus.STOPPED

    def get_all_status(self) -> Dict[ModelTier, ServiceStatus]:
        """获取所有层级的状态"""
        return {tier: self.get_tier_status(tier) for tier in ModelTier}

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "ollama_installed": self.is_ollama_installed(),
            "ollama_running": self.is_ollama_running(),
            "local_models": self.list_local_models(),
            "tier_status": {tier.value: status.value for tier, status in self.get_all_status().items()}
        }


# ── 单例 ─────────────────────────────────────────────────────────────────────

_deployment_engine: Optional[DeploymentEngine] = None


def get_deployment_engine() -> DeploymentEngine:
    """获取部署引擎单例"""
    global _deployment_engine
    if _deployment_engine is None:
        _deployment_engine = DeploymentEngine()
    return _deployment_engine


# ── 测试 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = DeploymentEngine()
    
    logger.info("=" * 60)
    logger.info("自动化模型部署引擎测试")
    logger.info("=" * 60)
    
    # 健康检查
    logger.info("\n[健康检查]")
    health = engine.health_check()
    logger.info(f"  Ollama 已安装: {health['ollama_installed']}")
    logger.info(f"  Ollama 运行中: {health['ollama_running']}")
    logger.info(f"  本地模型: {health['local_models']}")
    
    # 部署单个模型测试
    logger.info("\n[单模型部署测试]")
    result = engine.auto_deploy_tier(
        ModelTier.L0,
        progress_callback=lambda p, s: logger.info(f"  [{p:.0%}] {s}")
    )
    logger.info(f"  结果: {result.message}")
    
    logger.info("\n" + "=" * 60)
