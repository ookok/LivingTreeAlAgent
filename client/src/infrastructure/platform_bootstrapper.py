"""
平台启动器 - Platform Bootstrapper

提供跨平台的自动配置和服务部署能力：
- 自动检测操作系统 (Linux/Windows)
- 扫描硬件配置 (GPU/CPU/RAM)
- 生成平台指纹
- 部署后台服务 (Systemd/NSSM)
- 生命周期管理
"""

import platform
import psutil
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger


class PlatformBootstrapper:
    """跨平台启动器"""
    
    def __init__(self):
        self.os_type = platform.system().lower()  # 'linux' or 'windows'
        self.app_dir = Path.home() / ".livingtree_agent"
        self.config = {}
        self._logger = logger.bind(component="PlatformBootstrapper")
    
    def auto_start(self) -> Dict[str, Any]:
        """自动启动流程"""
        self._logger.info("=== 启动阶段1: 环境自检 ===")
        self.detect_and_configure()
        
        self._logger.info("=== 启动阶段2: 服务部署 ===")
        self._deploy_services()
        
        self._logger.info("=== 启动阶段3: 应用启动 ===")
        return self.config
    
    def detect_and_configure(self) -> Dict[str, Any]:
        """生成跨平台配置"""
        # 硬件扫描 (跨平台)
        hardware = {
            "os": self.os_type,
            "gpu_vram": self._get_gpu_memory(),
            "cpu_cores": psutil.cpu_count(logical=False) or 4,
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "arch": platform.machine(),
            "hostname": platform.node()
        }
        
        self._logger.info(f"硬件检测完成: {hardware}")
        
        # 根据OS和硬件选择配置
        if self.os_type == "linux":
            self.config.update(self._linux_config(hardware))
        else:  # windows
            self.config.update(self._windows_config(hardware))
        
        # 添加通用配置
        self.config.update({
            "hardware": hardware,
            "app_dir": str(self.app_dir),
            "version": "1.0.0",
            "first_run": not (self.app_dir / "config.json").exists()
        })
        
        # 确保目录存在
        self.app_dir.mkdir(parents=True, exist_ok=True)
        (self.app_dir / "logs").mkdir(exist_ok=True)
        (self.app_dir / "services").mkdir(exist_ok=True)
        
        # 保存配置
        (self.app_dir / "config.json").write_text(json.dumps(self.config, indent=2, ensure_ascii=False))
        self._logger.info(f"配置已保存到: {self.app_dir / 'config.json'}")
        
        return self.config
    
    def _get_gpu_memory(self) -> float:
        """获取GPU显存（跨平台）"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            pynvml.nvmlShutdown()
            return info.total / 1e9
        except ImportError:
            self._logger.warning("pynvml未安装，无法检测GPU")
        except Exception as e:
            self._logger.warning(f"GPU检测失败: {e}")
        return 0.0
    
    def _linux_config(self, hardware) -> Dict[str, Any]:
        """Linux 特定配置"""
        return {
            "service_manager": "systemd",
            "inference_engine": "vllm" if hardware["gpu_vram"] >= 8 else "llama.cpp",
            "vector_engine": "qdrant",
            "model": self._select_model(hardware),
            "venv_path": str(self.app_dir / "venv"),
            "service_path": "/etc/systemd/system/livingtree-agent.service",
            "log_path": str(self.app_dir / "logs"),
            "pip_path": str(self.app_dir / "venv" / "bin" / "pip"),
            "python_path": str(self.app_dir / "venv" / "bin" / "python")
        }
    
    def _windows_config(self, hardware) -> Dict[str, Any]:
        """Windows 特定配置"""
        return {
            "service_manager": "nssm",
            "inference_engine": "vllm" if hardware["gpu_vram"] >= 8 else "llama.cpp",
            "vector_engine": "qdrant",
            "model": self._select_model(hardware),
            "venv_path": str(self.app_dir / "venv"),
            "service_path": str(self.app_dir / "services"),
            "log_path": str(self.app_dir / "logs"),
            "pip_path": str(self.app_dir / "venv" / "Scripts" / "pip.exe"),
            "python_path": str(self.app_dir / "venv" / "Scripts" / "python.exe")
        }
    
    def _select_model(self, hardware) -> str:
        """根据硬件选择模型"""
        if hardware["gpu_vram"] >= 24:
            return "Qwen2-72B"
        elif hardware["gpu_vram"] >= 16:
            return "Qwen2-32B"
        elif hardware["gpu_vram"] >= 8:
            return "Qwen2-7B"
        elif hardware["ram_gb"] >= 32:
            return "Qwen2-1.5B"
        else:
            return "Qwen2-0.5B"
    
    def _deploy_services(self):
        """部署服务"""
        from .service_deployer import ServiceDeployer
        
        if self.config.get("first_run", False):
            deployer = ServiceDeployer(self.config)
            deployer.deploy_all()
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self.config
    
    def is_first_run(self) -> bool:
        """是否首次运行"""
        return self.config.get("first_run", False)


class ServiceDeployer:
    """跨平台服务部署器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.os_type = config["hardware"]["os"]
        self._logger = logger.bind(component="ServiceDeployer")
    
    def deploy_all(self):
        """部署所有服务"""
        self._logger.info(f"开始部署服务到 {self.os_type}")
        
        if self.os_type == "linux":
            self._deploy_linux_services()
        else:
            self._deploy_windows_services()
    
    def _deploy_linux_services(self):
        """Linux: 创建 Systemd 服务"""
        import subprocess
        
        # 创建主服务
        service_content = f"""[Unit]
Description=LivingTree AI Agent Service
After=network.target

[Service]
Type=simple
User={os.getlogin()}
WorkingDirectory={self.config['app_dir']}
Environment="PATH={self.config['venv_path']}/bin"
ExecStart={self.config['python_path']} {self.config['app_dir']}/main.py relay
Restart=always
RestartSec=10
StandardOutput=append:{self.config['log_path']}/output.log
StandardError=append:{self.config['log_path']}/error.log

[Install]
WantedBy=multi-user.target
"""
        
        # 写入 systemd 服务文件
        service_file = Path(self.config["service_path"])
        service_file.parent.mkdir(parents=True, exist_ok=True)
        service_file.write_text(service_content)
        
        self._logger.info(f"Systemd服务文件已创建: {service_file}")
        
        # 启用并启动服务
        try:
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", "livingtree-agent"], check=True)
            subprocess.run(["sudo", "systemctl", "start", "livingtree-agent"], check=True)
            self._logger.info("Systemd服务已启动")
        except subprocess.CalledProcessError as e:
            self._logger.error(f"Systemd服务部署失败: {e}")
    
    def _deploy_windows_services(self):
        """Windows: 创建 NSSM 服务"""
        import subprocess
        
        # 1. 确保 NSSM 存在
        nssm_path = self._ensure_nssm()
        
        # 2. 创建启动脚本
        start_script = self._create_start_script()
        
        # 3. 注册 NSSM 服务
        try:
            # 删除已存在的服务
            subprocess.run([nssm_path, "remove", "LivingTreeAgent", "confirm"], 
                         capture_output=True)
        except:
            pass
        
        # 安装服务
        subprocess.run([
            nssm_path, "install", "LivingTreeAgent",
            str(start_script)
        ], check=True)
        
        # 设置自动启动
        subprocess.run([nssm_path, "set", "LivingTreeAgent", "Start", "SERVICE_AUTO_START"], check=True)
        
        # 设置工作目录
        subprocess.run([nssm_path, "set", "LivingTreeAgent", "WorkingDirectory", self.config["app_dir"]], check=True)
        
        # 启动服务
        subprocess.run(["net", "start", "LivingTreeAgent"], check=True)
        
        self._logger.info("Windows服务已部署并启动")
    
    def _ensure_nssm(self) -> str:
        """确保 NSSM 工具存在"""
        nssm_dir = self.app_dir / "nssm"
        nssm_path = nssm_dir / "nssm.exe"
        
        if not nssm_path.exists():
            self._logger.info("正在下载NSSM...")
            nssm_dir.mkdir(parents=True, exist_ok=True)
            
            import urllib.request
            url = "https://github.com/nssm/nssm/releases/download/v2.24/nssm-2.24.zip"
            zip_path = nssm_dir / "nssm.zip"
            
            urllib.request.urlretrieve(url, str(zip_path))
            
            # 解压
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(nssm_dir)
            
            # 找到实际的nssm.exe路径
            for path in nssm_dir.rglob("nssm.exe"):
                return str(path)
        
        return str(nssm_path)
    
    def _create_start_script(self) -> Path:
        """创建启动脚本"""
        if self.os_type == "windows":
            batch_content = f"""@echo off
cd /d "{self.config['app_dir']}"
call "{self.config['venv_path']}\\Scripts\\activate.bat"
python main.py relay
"""
            script_path = self.app_dir / "start_relay.bat"
            script_path.write_text(batch_content, encoding="gbk")
        else:
            script_content = f"""#!/bin/bash
cd {self.config['app_dir']}
source {self.config['venv_path']}/bin/activate
python main.py relay
"""
            script_path = self.app_dir / "start_relay.sh"
            script_path.write_text(script_content)
            # 添加执行权限
            import subprocess
            subprocess.run(["chmod", "+x", str(script_path)])
        
        return script_path
    
    def uninstall(self):
        """卸载服务"""
        import subprocess
        
        if self.os_type == "linux":
            try:
                subprocess.run(["sudo", "systemctl", "stop", "livingtree-agent"])
                subprocess.run(["sudo", "systemctl", "disable", "livingtree-agent"])
                Path(self.config["service_path"]).unlink(missing_ok=True)
                subprocess.run(["sudo", "systemctl", "daemon-reload"])
                self._logger.info("Linux服务已卸载")
            except Exception as e:
                self._logger.error(f"卸载失败: {e}")
        else:
            try:
                nssm_path = self._ensure_nssm()
                subprocess.run(["net", "stop", "LivingTreeAgent"], capture_output=True)
                subprocess.run([nssm_path, "remove", "LivingTreeAgent", "confirm"])
                self._logger.info("Windows服务已卸载")
            except Exception as e:
                self._logger.error(f"卸载失败: {e}")


class EnvironmentManager:
    """管理虚拟环境和依赖"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._logger = logger.bind(component="EnvironmentManager")
    
    def setup_environment(self) -> bool:
        """设置环境"""
        self._logger.info("设置虚拟环境...")
        
        # 1. 创建虚拟环境
        venv_path = Path(self.config["venv_path"])
        if not venv_path.exists():
            self._create_venv(venv_path)
        
        # 2. 安装依赖
        self._install_dependencies()
        
        # 3. 设置应用目录
        self._setup_app_directory()
        
        return True
    
    def _create_venv(self, venv_path: Path):
        """创建虚拟环境"""
        import subprocess
        
        self._logger.info(f"创建虚拟环境: {venv_path}")
        
        try:
            subprocess.run([
                sys.executable, "-m", "venv", str(venv_path)
            ], check=True, capture_output=True)
            self._logger.info("虚拟环境创建成功")
        except subprocess.CalledProcessError as e:
            self._logger.error(f"虚拟环境创建失败: {e}")
            raise
    
    def _install_dependencies(self):
        """安装依赖"""
        import subprocess
        
        pip_cmd = self.config["pip_path"]
        requirements = self._get_requirements()
        
        self._logger.info(f"安装依赖 ({len(requirements)}个)")
        
        try:
            result = subprocess.run(
                [pip_cmd, "install"] + requirements,
                check=True,
                capture_output=True,
                text=True
            )
            self._logger.info("依赖安装成功")
        except subprocess.CalledProcessError as e:
            self._logger.error(f"依赖安装失败: {e.stderr}")
            raise
    
    def _get_requirements(self) -> list:
        """获取依赖列表"""
        base_requirements = [
            "PyQt6",
            "loguru",
            "psutil",
            "pynvml",
            "fastapi",
            "uvicorn",
            "requests",
            "numpy",
            "pandas",
            "scikit-learn"
        ]
        
        # 根据配置添加额外依赖
        if self.config.get("inference_engine") == "vllm":
            base_requirements.append("vllm")
        else:
            base_requirements.append("llama-cpp-python")
        
        if self.config.get("vector_engine") == "qdrant":
            base_requirements.append("qdrant-client")
        else:
            base_requirements.append("chromadb")
        
        return base_requirements
    
    def _setup_app_directory(self):
        """设置应用目录结构"""
        app_dir = Path(self.config["app_dir"])
        
        # 创建必要目录
        directories = [
            "logs",
            "services",
            "models",
            "data",
            "plugins"
        ]
        
        for dir_name in directories:
            (app_dir / dir_name).mkdir(exist_ok=True)
        
        self._logger.info("应用目录结构已创建")


def bootstrap() -> Dict[str, Any]:
    """启动引导函数"""
    logger.info("=== LivingTree AI Agent 启动引导 ===")
    
    bootstrapper = PlatformBootstrapper()
    
    try:
        config = bootstrapper.auto_start()
        logger.info(f"启动引导完成，配置: {config}")
        return config
    except Exception as e:
        logger.error(f"启动引导失败: {e}")
        raise


if __name__ == "__main__":
    bootstrap()