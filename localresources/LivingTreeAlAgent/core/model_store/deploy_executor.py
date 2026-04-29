"""
部署执行器 (Deploy Executor)
============================

负责执行具体的安装/卸载操作

支持类型：
1. pip安装 - Python包
2. 二进制解压 - 预编译程序
3. Docker部署 - 容器化模型
4. API配置 - 云端服务

Author: Hermes Desktop AI Assistant
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
import logging
import tempfile
import zipfile
import tarfile
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import threading
import requests

logger = logging.getLogger(__name__)


class DeployStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    UNINSTALLING = "uninstalling"


class DeployType(Enum):
    """部署类型"""
    INSTALL = "install"
    UPDATE = "update"
    UNINSTALL = "uninstall"
    START = "start"
    STOP = "stop"


@dataclass
class DeployProgress:
    """部署进度"""
    status: DeployStatus
    progress: float = 0.0  # 0-100
    message: str = ""
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        return self.status in [DeployStatus.RUNNING, DeployStatus.STOPPED, DeployStatus.FAILED]


@dataclass
class DeployResult:
    """部署结果"""
    success: bool
    model_id: str
    message: str
    install_path: Optional[str] = None
    runtime_info: Optional[Dict] = None
    error: Optional[str] = None


class ProgressCallback:
    """进度回调函数类型"""
    def __call__(self, progress: DeployProgress):
        pass


class DeployExecutor:
    """
    部署执行器

    功能：
    1. pip包安装/卸载
    2. 二进制下载、解压、配置
    3. Docker镜像拉取、容器启动
    4. API配置（API Key注册）

    使用示例：
        executor = DeployExecutor()
        result = executor.deploy('pyswmm', progress_callback=print)
    """

    def __init__(self, install_dir: Optional[str] = None):
        """
        初始化部署执行器

        Args:
            install_dir: 安装根目录，默认为 ~/.model_store/installs/
        """
        self.install_dir = Path(install_dir or os.path.expanduser('~/.model_store/installs'))
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # 进度回调
        self._progress_callbacks: Dict[str, ProgressCallback] = {}

        # Docker客户端（延迟初始化）
        self._docker_client = None

        logger.info(f"DeployExecutor 初始化完成，安装目录: {self.install_dir}")

    def deploy(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """
        部署模型（主入口）

        Args:
            model_id: 模型ID
            model_info: 模型信息
            progress_callback: 进度回调

        Returns:
            DeployResult: 部署结果
        """
        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.PENDING,
            message=f"准备部署 {model_id}"
        ), progress_callback)

        try:
            install_type = model_info.install.type

            if install_type == InstallType.PIP:
                return self._deploy_pip(model_id, model_info, progress_callback)
            elif install_type == InstallType.BINARY:
                return self._deploy_binary(model_id, model_info, progress_callback)
            elif install_type == InstallType.DOCKER:
                return self._deploy_docker(model_id, model_info, progress_callback)
            elif install_type == InstallType.API:
                return self._deploy_api(model_id, model_info, progress_callback)
            else:
                return DeployResult(
                    success=False,
                    model_id=model_id,
                    message=f"不支持的安装类型: {install_type}"
                )

        except Exception as e:
            logger.error(f"部署 {model_id} 失败: {e}")
            import traceback
            traceback.print_exc()

            self._set_progress(model_id, DeployProgress(
                status=DeployStatus.FAILED,
                error=str(e)
            ), progress_callback)

            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"部署失败: {str(e)}",
                error=str(e)
            )

    def uninstall(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """
        卸载模型

        Args:
            model_id: 模型ID
            model_info: 模型信息
            progress_callback: 进度回调

        Returns:
            DeployResult: 卸载结果
        """
        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.UNINSTALLING,
            message=f"准备卸载 {model_id}"
        ), progress_callback)

        try:
            install_type = model_info.install.type

            if install_type == InstallType.PIP:
                return self._uninstall_pip(model_id, model_info, progress_callback)
            elif install_type == InstallType.BINARY:
                return self._uninstall_binary(model_id, model_info, progress_callback)
            elif install_type == InstallType.DOCKER:
                return self._uninstall_docker(model_id, model_info, progress_callback)
            elif install_type == InstallType.API:
                return self._uninstall_api(model_id, model_info, progress_callback)
            else:
                return DeployResult(
                    success=False,
                    model_id=model_id,
                    message=f"不支持的卸载类型: {install_type}"
                )

        except Exception as e:
            logger.error(f"卸载 {model_id} 失败: {e}")
            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"卸载失败: {str(e)}",
                error=str(e)
            )

    # ========== PIP 安装 ==========

    def _deploy_pip(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """PIP安装"""
        package = model_info.install.package or model_id

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.INSTALLING,
            progress=0,
            message=f"安装pip包: {package}"
        ), progress_callback)

        # 检查pip是否可用
        if not self._check_pip():
            return DeployResult(
                success=False,
                model_id=model_id,
                message="pip不可用"
            )

        # 执行安装
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package, '--quiet'],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return DeployResult(
                    success=False,
                    model_id=model_id,
                    message=f"pip安装失败: {result.stderr}",
                    error=result.stderr
                )

        except subprocess.TimeoutExpired:
            return DeployResult(
                success=False,
                model_id=model_id,
                message="pip安装超时"
            )

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.RUNNING,
            progress=100,
            message="安装完成"
        ), progress_callback)

        return DeployResult(
            success=True,
            model_id=model_id,
            message="安装成功",
            install_path=f"pip:{package}"
        )

    def _uninstall_pip(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """PIP卸载"""
        package = model_info.install.package or model_id

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'uninstall', package, '-y', '--quiet'],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return DeployResult(
                    success=False,
                    model_id=model_id,
                    message=f"pip卸载失败: {result.stderr}",
                    error=result.stderr
                )

        except subprocess.TimeoutExpired:
            return DeployResult(
                success=False,
                model_id=model_id,
                message="pip卸载超时"
            )

        return DeployResult(
            success=True,
            model_id=model_id,
            message="卸载成功"
        )

    def _check_pip(self) -> bool:
        """检查pip是否可用"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', '--version'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    # ========== 二进制安装 ==========

    def _deploy_binary(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """二进制部署"""
        url = model_info.install.url
        if not url:
            return DeployResult(
                success=False,
                model_id=model_id,
                message="未提供下载URL"
            )

        # 创建模型目录
        model_dir = self.install_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.DOWNLOADING,
            progress=0,
            message=f"下载二进制包..."
        ), progress_callback)

        # 下载文件
        try:
            download_path = model_dir / f"{model_id}_download"

            # 流式下载，带进度
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 50  # 下载占50%
                            self._set_progress(model_id, DeployProgress(
                                status=DeployStatus.DOWNLOADING,
                                progress=progress,
                                message=f"下载中... {downloaded//1024//1024}MB / {total_size//1024//1024}MB"
                            ), progress_callback)

        except Exception as e:
            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"下载失败: {str(e)}",
                error=str(e)
            )

        # 校验
        if model_info.install.checksum:
            self._set_progress(model_id, DeployProgress(
                status=DeployStatus.INSTALLING,
                progress=50,
                message="校验文件..."
            ), progress_callback)

            if not self._verify_checksum(download_path, model_info.install.checksum):
                download_path.unlink()
                return DeployResult(
                    success=False,
                    model_id=model_id,
                    message="文件校验失败"
                )

        # 解压
        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.INSTALLING,
            progress=75,
            message="解压文件..."
        ), progress_callback)

        try:
            self._extract_archive(download_path, model_dir)
            download_path.unlink()  # 删除压缩包
        except Exception as e:
            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"解压失败: {str(e)}",
                error=str(e)
            )

        # 设置环境变量（如果需要）
        if model_info.install.env:
            self._set_environment_vars(model_id, model_info.install.env)

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.RUNNING,
            progress=100,
            message="安装完成"
        ), progress_callback)

        return DeployResult(
            success=True,
            model_id=model_id,
            message="安装成功",
            install_path=str(model_dir)
        )

    def _uninstall_binary(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """二进制卸载"""
        model_dir = self.install_dir / model_id

        if model_dir.exists():
            shutil.rmtree(model_dir)

        # 清理环境变量
        env_file = self.install_dir / f"{model_id}_env.json"
        if env_file.exists():
            env_file.unlink()

        return DeployResult(
            success=True,
            model_id=model_id,
            message="卸载成功"
        )

    def _verify_checksum(self, file_path: Path, checksum: str) -> bool:
        """验证校验和"""
        try:
            algo, expected = checksum.split(':')

            with open(file_path, 'rb') as f:
                if algo == 'md5':
                    actual = hashlib.md5(f.read()).hexdigest()
                elif algo == 'sha256':
                    actual = hashlib.sha256(f.read()).hexdigest()
                else:
                    logger.warning(f"不支持的校验算法: {algo}")
                    return True  # 跳过校验

            return actual == expected
        except Exception as e:
            logger.error(f"校验失败: {e}")
            return False

    def _extract_archive(self, archive_path: Path, dest_dir: Path):
        """解压压缩包"""
        if archive_path.suffix in ['.zip', '.exe']:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(dest_dir)
        elif archive_path.suffix in ['.tar', '.gz', '.tgz', '.tar.gz']:
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(dest_dir)
        else:
            raise ValueError(f"不支持的压缩格式: {archive_path.suffix}")

    def _set_environment_vars(self, model_id: str, env_vars: Dict[str, str]):
        """设置环境变量"""
        # 保存到文件
        env_file = self.install_dir / f"{model_id}_env.json"
        with open(env_file, 'w') as f:
            json.dump(env_vars, f)

    # ========== Docker 部署 ==========

    def _deploy_docker(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """Docker部署"""
        image = model_info.install.image

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.DOWNLOADING,
            progress=0,
            message=f"拉取Docker镜像: {image}"
        ), progress_callback)

        # 检查Docker是否可用
        if not self._check_docker():
            return DeployResult(
                success=False,
                model_id=model_id,
                message="Docker不可用，请安装Docker Desktop"
            )

        # 拉取镜像
        try:
            client = self._get_docker_client()

            # 使用低级别API获取拉取进度
            import docker
            for line in client.api.pull(image, stream=True, decode=True):
                status = line.get('status', '')
                progress = line.get('progress', '')

                if 'Downloading' in status or 'Extracting' in status:
                    self._set_progress(model_id, DeployProgress(
                        status=DeployStatus.DOWNLOADING,
                        progress=50,
                        message=f"{status} {progress}"
                    ), progress_callback)

        except Exception as e:
            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"Docker镜像拉取失败: {str(e)}",
                error=str(e)
            )

        # 启动容器
        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.INSTALLING,
            progress=75,
            message="启动容器..."
        ), progress_callback)

        try:
            ports = {}
            if model_info.install.port_mapping:
                for container_port, host_port in model_info.install.port_mapping.items():
                    ports[f'{container_port}/tcp'] = int(host_port)

            volumes = {
                str(self.install_dir / model_id / 'data'): {'bind': '/app/data', 'mode': 'rw'}
            }

            environment = model_info.install.env or {}

            container = client.containers.run(
                image,
                detach=True,
                ports=ports,
                volumes=volumes,
                environment=environment,
                name=f"model_{model_id}"
            )

            runtime_info = {
                'container_id': container.id,
                'status': container.status,
            }

        except Exception as e:
            return DeployResult(
                success=False,
                model_id=model_id,
                message=f"容器启动失败: {str(e)}",
                error=str(e)
            )

        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.RUNNING,
            progress=100,
            message="部署完成"
        ), progress_callback)

        return DeployResult(
            success=True,
            model_id=model_id,
            message="Docker部署成功",
            install_path=f"docker:{container.id[:12]}",
            runtime_info=runtime_info
        )

    def _uninstall_docker(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """Docker卸载"""
        try:
            client = self._get_docker_client()
            container_name = f"model_{model_id}"

            # 停止并删除容器
            try:
                container = client.containers.get(container_name)
                container.stop(timeout=10)
                container.remove()
            except docker.errors.NotFound:
                pass  # 容器不存在

            # 删除镜像（可选）
            # client.images.remove(image)

        except Exception as e:
            logger.warning(f"Docker卸载警告: {e}")

        return DeployResult(
            success=True,
            model_id=model_id,
            message="卸载成功"
        )

    def _check_docker(self) -> bool:
        """检查Docker是否可用"""
        try:
            client = self._get_docker_client()
            client.ping()
            return True
        except Exception:
            return False

    def _get_docker_client(self):
        """获取Docker客户端"""
        if self._docker_client is None:
            import docker
            self._docker_client = docker.from_env()
        return self._docker_client

    # ========== API 配置 ==========

    def _deploy_api(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """API配置"""
        self._set_progress(model_id, DeployProgress(
            status=DeployStatus.INSTALLING,
            progress=50,
            message="配置API..."
        ), progress_callback)

        # API类型模型不需要实际安装，只需记录配置
        # API Key由密钥管理系统管理

        return DeployResult(
            success=True,
            model_id=model_id,
            message="API配置成功（请在密钥管理中设置API Key）",
            install_path=f"api:{model_info.runtime.endpoint}"
        )

    def _uninstall_api(self, model_id: str, model_info, progress_callback: Optional[Callable] = None) -> DeployResult:
        """API卸载"""
        # 只需要清理本地配置
        return DeployResult(
            success=True,
            model_id=model_id,
            message="配置已清理"
        )

    # ========== 辅助方法 ==========

    def _set_progress(self, model_id: str, progress: DeployProgress, callback: Optional[Callable]):
        """设置进度"""
        if callback:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")

    def get_install_path(self, model_id: str) -> Optional[Path]:
        """获取模型的安装路径"""
        path = self.install_dir / model_id
        return path if path.exists() else None

    def is_installed(self, model_id: str) -> bool:
        """检查模型是否已安装"""
        # 检查目录
        if (self.install_dir / model_id).exists():
            return True

        # 检查pip包
        if self._check_pip():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'show', model_id],
                    capture_output=True,
                    timeout=10
                )
                return result.returncode == 0
            except Exception:
                pass

        # 检查Docker容器
        if self._check_docker():
            try:
                client = self._get_docker_client()
                container_name = f"model_{model_id}"
                client.containers.get(container_name)
                return True
            except Exception:
                pass

        return False

    def get_container_info(self, model_id: str) -> Optional[Dict]:
        """获取Docker容器信息"""
        if not self._check_docker():
            return None

        try:
            client = self._get_docker_client()
            container = client.containers.get(f"model_{model_id}")
            return {
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'ports': container.ports,
            }
        except Exception:
            return None


# 解决循环引用
from .model_registry import ModelInfo, InstallType