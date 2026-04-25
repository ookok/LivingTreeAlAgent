# -*- coding: utf-8 -*-
"""
模型管理器 - Model Manager
=========================

功能：
1. Ollama模型生命周期管理
2. 模型版本检测与比较
3. 自动升级提案生成
4. 增量下载与回滚
5. 健康检查与状态监控

Author: Hermes Desktop Team
"""

import asyncio
import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import logging
import subprocess

import httpx

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class UpgradeStage(Enum):
    """升级阶段"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    TESTING = "testing"
    SWITCHING = "switching"
    CLEANUP = "cleanup"
    ROLLBACK = "rollback"
    COMPLETED = "completed"
    FAILED = "failed"


class UpgradeDecision(Enum):
    """升级决策"""
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTPONED = "postponed"
    PENDING = "pending"


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class LocalModel:
    """本地模型"""
    name: str
    size_mb: float
    digest: str
    modified_at: str
    parent_model: str = ""  # 基础模型（如 qwen2）
    version: str = ""  # 版本（如 2.5）
    tag: str = ""  # 标签（如 14b）


@dataclass
class RemoteModel:
    """远程可用模型"""
    name: str
    size_mb: float
    updated_at: str
    pulls: int = 0
    description: str = ""


@dataclass
class UpgradeProposal:
    """升级提案"""
    proposal_id: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # 当前模型
    current_model: str = ""
    current_version: str = ""
    
    # 目标模型
    target_model: str = ""
    target_version: str = ""
    
    # 触发原因
    trigger_reasons: List[str] = field(default_factory=list)
    
    # 预期收益
    expected_benefits: Dict[str, float] = field(default_factory=dict)
    
    # 风险评估
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_factors: List[str] = field(default_factory=list)
    
    # 资源需求
    required_disk_gb: float = 0.0
    required_memory_gb: float = 0.0
    estimated_download_time_minutes: float = 0.0
    
    # 决策
    decision: UpgradeDecision = UpgradeDecision.PENDING
    
    # 执行状态
    stage: UpgradeStage = UpgradeStage.IDLE
    progress_percent: float = 0.0
    error_message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 模型管理器
# ─────────────────────────────────────────────────────────────────────────────

class ModelManager:
    """
    模型管理器
    
    功能：
    1. 模型列表与状态管理
    2. 版本检测与比较
    3. 升级提案生成
    4. 模型下载与安装
    5. 热切换与回滚
    """
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model_cache_dir: Optional[Path] = None
    ):
        self.ollama_host = ollama_host.rstrip("/")
        self.cache_dir = model_cache_dir or (Path.home() / ".ollama" / "models")
        
        # 状态
        self._local_models: List[LocalModel] = []
        self._remote_models: List[RemoteModel] = []
        self._current_upgrade: Optional[UpgradeProposal] = None
        self._upgrade_in_progress = False
        
        # 回调
        self.on_stage_change: Optional[Callable[[UpgradeStage, float], None]] = None
        self.on_upgrade_complete: Optional[Callable[[bool, str], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
    
    # ── 模型列表 ─────────────────────────────────────────────────────────────
    
    async def get_local_models(self) -> List[LocalModel]:
        """获取本地模型列表"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                response.raise_for_status()
                
                models = []
                for m in response.json().get("models", []):
                    name = m.get("name", "")
                    parent, version, tag = self._parse_model_name(name)
                    
                    models.append(LocalModel(
                        name=name,
                        size_mb=m.get("size", 0) / (1024 * 1024),
                        digest=m.get("digest", ""),
                        modified_at=m.get("modified_at", ""),
                        parent_model=parent,
                        version=version,
                        tag=tag,
                    ))
                
                self._local_models = models
                return models
        except Exception as e:
            logger.error(f"获取本地模型失败: {e}")
            return []
    
    async def get_remote_models(self) -> List[RemoteModel]:
        """获取远程可用模型（从Ollama Library）"""
        # Ollama Library API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://ollama.com/api/library",
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                
                models = []
                for m in response.json():
                    models.append(RemoteModel(
                        name=m.get("name", ""),
                        size_mb=0,  # Library API不直接提供大小
                        updated_at=m.get("lastModified", ""),
                        pulls=m.get("pulls", 0),
                        description=m.get("description", ""),
                    ))
                
                self._remote_models = models
                return models
        except Exception as e:
            logger.error(f"获取远程模型失败: {e}")
            return []
    
    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """获取模型详细信息"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.ollama_host}/api/show",
                    json={"name": model_name}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取模型信息失败: {e}")
            return {}
    
    # ── 模型解析 ─────────────────────────────────────────────────────────────
    
    def _parse_model_name(self, name: str) -> tuple:
        """解析模型名称"""
        # 例如: qwen2.5:14b-instruct-q4_K_M
        parts = name.split(":")
        if len(parts) < 2:
            return name, "", ""
        
        parent = parts[0]
        tags = parts[1].split("-")
        version = tags[0] if tags else ""
        tag = tags[1] if len(tags) > 1 else ""
        
        return parent, version, tag
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号"""
        try:
            # 提取数字版本
            import re
            nums1 = re.findall(r'\d+', v1)
            nums2 = re.findall(r'\d+', v2)
            
            if not nums1 or not nums2:
                return 0
            
            # 逐个比较
            for n1, n2 in zip(nums1, nums2):
                if int(n1) > int(n2):
                    return 1
                elif int(n1) < int(n2):
                    return -1
            return 0
        except:
            return 0
    
    # ── 升级提案生成 ────────────────────────────────────────────────────────
    
    async def check_for_upgrades(self) -> List[UpgradeProposal]:
        """检查可用的升级"""
        proposals = []
        
        # 获取本地和远程模型
        local_models = await self.get_local_models()
        remote_models = await self.get_remote_models()
        
        # 创建远程模型映射
        remote_map = {r.name: r for r in remote_models}
        
        for local in local_models:
            # 查找更新的版本
            base_name = local.parent_model
            if not base_name:
                continue
            
            # 查找同系列的其他版本
            for remote in remote_models:
                if remote.name.startswith(base_name):
                    parent, version, _ = self._parse_model_name(remote.name)
                    
                    # 比较版本
                    if self._compare_versions(version, local.version) > 0:
                        # 发现新版本，生成提案
                        proposal = await self._create_upgrade_proposal(local, remote)
                        if proposal:
                            proposals.append(proposal)
        
        return proposals
    
    async def _create_upgrade_proposal(
        self, 
        current: LocalModel, 
        target: RemoteModel
    ) -> Optional[UpgradeProposal]:
        """创建升级提案"""
        # 生成提案ID
        proposal_id = f"UP-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(target.name.encode()).hexdigest()[:6].upper()}"
        
        # 计算资源需求
        target_size_mb = target.size_mb or 5000  # 默认5GB
        required_disk = target_size_mb / 1024 + current.size_mb / 1024  # 新+旧
        
        # 估算下载时间（假设5MB/s）
        estimated_time = (target_size_mb / 1024) / 5 * 60  # 分钟
        
        # 评估风险
        risk_level = RiskLevel.MEDIUM
        risk_factors = []
        
        if estimated_time > 60:
            risk_factors.append("下载时间较长，可能中断")
        
        if required_disk > 20:
            risk_factors.append("需要较大磁盘空间")
        
        return UpgradeProposal(
            proposal_id=proposal_id,
            current_model=current.name,
            current_version=current.version,
            target_model=target.name,
            target_version=target.version,
            trigger_reasons=[
                f"检测到新版本 {target.name}",
                f"当前版本 {current.version} 可升级",
            ],
            expected_benefits={
                "accuracy_improvement": 15.0,  # 预估准确率提升15%
                "context_length": 128 * 1024,   # 128K上下文
                "performance": -8.0,             # 速度可能降低8%
            },
            risk_level=risk_level,
            risk_factors=risk_factors,
            required_disk_gb=required_disk,
            required_memory_gb=target_size_mb / 1024 * 2,  # 估算内存需求
            estimated_download_time_minutes=estimated_time,
        )
    
    # ── 执行升级 ────────────────────────────────────────────────────────────
    
    async def execute_upgrade(self, proposal: UpgradeProposal) -> bool:
        """执行升级"""
        if self._upgrade_in_progress:
            logger.warning("升级正在进行中")
            return False
        
        self._upgrade_in_progress = True
        self._current_upgrade = proposal
        
        try:
            # 阶段1: 环境检查
            await self._stage_check()
            
            # 阶段2: 下载模型
            await self._stage_download(proposal.target_model)
            
            # 阶段3: 验证测试
            await self._stage_test(proposal.target_model)
            
            # 阶段4: 热切换
            await self._stage_switch(proposal.target_model)
            
            # 阶段5: 清理
            await self._stage_cleanup(proposal.current_model)
            
            # 完成
            proposal.stage = UpgradeStage.COMPLETED
            proposal.progress_percent = 100.0
            
            if self.on_upgrade_complete:
                self.on_upgrade_complete(True, "升级成功")
            
            return True
            
        except Exception as e:
            logger.error(f"升级失败: {e}")
            proposal.stage = UpgradeStage.FAILED
            proposal.error_message = str(e)
            
            # 尝试回滚
            await self._stage_rollback(proposal.current_model)
            
            if self.on_upgrade_complete:
                self.on_upgrade_complete(False, str(e))
            
            return False
        
        finally:
            self._upgrade_in_progress = False
            self._current_upgrade = None
    
    async def _stage_check(self):
        """阶段1: 环境检查"""
        self._log("开始环境检查...")
        self._set_stage(UpgradeStage.CHECKING, 0)
        
        # 检查磁盘空间
        import psutil
        disk = psutil.disk_usage('/')
        available_gb = disk.free / (1024 ** 3)
        
        if self._current_upgrade:
            if available_gb < self._current_upgrade.required_disk_gb:
                raise RuntimeError(f"磁盘空间不足: 需要{self._current_upgrade.required_disk_gb:.1f}GB，可用{available_gb:.1f}GB")
        
        # 检查内存
        vm = psutil.virtual_memory()
        available_memory_gb = vm.available / (1024 ** 3)
        
        if self._current_upgrade:
            if available_memory_gb < self._current_upgrade.required_memory_gb:
                raise RuntimeError(f"内存不足: 需要{self._current_upgrade.required_memory_gb:.1f}GB，可用{available_memory_gb:.1f}GB")
        
        # 检查网络
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get(f"{self.ollama_host}/")
        except:
            raise RuntimeError("无法连接到Ollama服务")
        
        self._log("环境检查通过")
        self._set_stage(UpgradeStage.CHECKING, 100)
    
    async def _stage_download(self, model_name: str):
        """阶段2: 下载模型"""
        self._log(f"开始下载模型: {model_name}")
        self._set_stage(UpgradeStage.DOWNLOADING, 0)
        
        # 使用ollama pull命令下载
        process = await asyncio.create_subprocess_exec(
            "ollama", "pull", model_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        total_size = 0
        last_update = time.time()
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            decoded = line.decode('utf-8', errors='ignore').strip()
            self._log(decoded)
            
            # 解析下载进度
            if "downloading" in decoded.lower():
                # 尝试提取进度
                import re
                match = re.search(r'(\d+\.?\d*)\s*[KMG]B', decoded)
                if match:
                    current_size = self._parse_size(match.group(0))
                    total_size = max(total_size, current_size)
                    
                    # 估算进度
                    if self._current_upgrade:
                        target_size = self._current_upgrade.required_disk_gb * 1024  # MB
                        progress = min(90, (total_size / target_size) * 100) if target_size > 0 else 0
                        self._set_stage(UpgradeStage.DOWNLOADING, progress)
        
        await process.wait()
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            raise RuntimeError(f"下载失败: {stderr.decode()}")
        
        self._log("下载完成")
        self._set_stage(UpgradeStage.DOWNLOADING, 100)
    
    def _parse_size(self, size_str: str) -> float:
        """解析大小字符串"""
        import re
        match = re.match(r'(\d+\.?\d*)\s*([KMG])B?', size_str)
        if not match:
            return 0
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        multipliers = {'K': 1, 'M': 1024, 'G': 1024 * 1024}
        return value * multipliers.get(unit, 1)
    
    async def _stage_test(self, model_name: str):
        """阶段3: 验证测试"""
        self._log(f"验证模型: {model_name}")
        self._set_stage(UpgradeStage.TESTING, 0)
        
        # 简单测试调用
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "Hello",
                        "stream": False,
                    }
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"测试失败: {response.status_code}")
        
        except Exception as e:
            raise RuntimeError(f"模型验证失败: {e}")
        
        self._log("模型验证通过")
        self._set_stage(UpgradeStage.TESTING, 100)
    
    async def _stage_switch(self, model_name: str):
        """阶段4: 热切换"""
        self._log(f"切换到模型: {model_name}")
        self._set_stage(UpgradeStage.SWITCHING, 0)
        
        # 停止当前模型
        if self._current_upgrade and self._current_upgrade.current_model:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.ollama_host}/api/generate",
                        json={
                            "model": self._current_upgrade.current_model,
                            "keep_alive": 0,  # 卸载模型
                        }
                    )
            except:
                pass
        
        self._set_stage(UpgradeStage.SWITCHING, 50)
        
        # 加载新模型
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": model_name,
                        "keep_alive": "24h",  # 保持加载24小时
                    }
                )
        except Exception as e:
            raise RuntimeError(f"加载新模型失败: {e}")
        
        self._log("模型切换完成")
        self._set_stage(UpgradeStage.SWITCHING, 100)
    
    async def _stage_cleanup(self, old_model: str):
        """阶段5: 清理"""
        self._log("清理旧模型...")
        self._set_stage(UpgradeStage.CLEANUP, 0)
        
        # 询问是否删除旧模型（默认保留）
        # 可以在配置中设置 auto_delete_old = True
        # 这里保留旧模型以便回滚
        
        self._log("清理完成")
        self._set_stage(UpgradeStage.CLEANUP, 100)
    
    async def _stage_rollback(self, fallback_model: str):
        """回滚"""
        self._log("执行回滚...")
        self._set_stage(UpgradeStage.ROLLBACK, 0)
        
        if not fallback_model:
            self._log("没有可回滚的模型")
            self._set_stage(UpgradeStage.ROLLBACK, 100)
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": fallback_model,
                        "keep_alive": "24h",
                    }
                )
            self._log("回滚完成")
        except Exception as e:
            self._log(f"回滚失败: {e}")
        
        self._set_stage(UpgradeStage.ROLLBACK, 100)
    
    def _set_stage(self, stage: UpgradeStage, progress: float):
        """设置当前阶段和进度"""
        if self._current_upgrade:
            self._current_upgrade.stage = stage
            self._current_upgrade.progress_percent = progress
        
        if self.on_stage_change:
            self.on_stage_change(stage, progress)
    
    def _log(self, message: str):
        """记录日志"""
        logger.info(f"[ModelManager] {message}")
        if self.on_log:
            self.on_log(message)
    
    # ── 工具方法 ────────────────────────────────────────────────────────────
    
    async def delete_model(self, model_name: str) -> bool:
        """删除模型"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.ollama_host}/api/delete",
                    json={"name": model_name}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_host}/")
                return response.status_code == 200
        except:
            return False
    
    def get_upgrade_status(self) -> Optional[UpgradeProposal]:
        """获取升级状态"""
        return self._current_upgrade


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """获取模型管理器单例"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
