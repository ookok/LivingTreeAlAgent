import os
import sys
import subprocess
import tempfile
import shutil
import zipfile
import tarfile
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolPackage:
    """工具包定义"""
    tool_id: str
    name: str
    description: str
    source_type: Literal["github", "gitlab", "url", "pip", "apt", "conda"]
    source_url: str
    version: str = "latest"
    target_dir: Optional[str] = None
    executable: Optional[str] = None
    install_commands: List[str] = field(default_factory=list)
    check_command: str = ""
    dependencies: List[str] = field(default_factory=list)
    supported_platforms: List[str] = field(default_factory=lambda: ["windows", "linux", "macos"])


class ToolDownloader:
    """CLI工具自动下载管理器"""
    
    def __init__(self):
        self.download_dir = Path(__file__).parent / "tools_bin"
        self.download_dir.mkdir(exist_ok=True)
        self.installed_tools: Dict[str, ToolPackage] = {}
        self._load_installed_tools()
    
    def _load_installed_tools(self):
        """加载已安装工具列表"""
        for tool_dir in self.download_dir.iterdir():
            if tool_dir.is_dir():
                manifest_file = tool_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        import json
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            pkg = ToolPackage(**data)
                            self.installed_tools[pkg.tool_id] = pkg
                    except:
                        pass
    
    def download_tool(self, tool_package: ToolPackage) -> bool:
        """下载并安装工具"""
        platform = self._get_platform()
        
        if platform not in tool_package.supported_platforms:
            logger.warning(f"Platform {platform} not supported for {tool_package.tool_id}")
            return False
        
        try:
            target_dir = Path(tool_package.target_dir) if tool_package.target_dir else \
                        self.download_dir / tool_package.tool_id
            target_dir.mkdir(parents=True, exist_ok=True)
            
            if tool_package.source_type == "github":
                success = self._download_from_github(tool_package, target_dir)
            elif tool_package.source_type == "url":
                success = self._download_from_url(tool_package, target_dir)
            elif tool_package.source_type == "pip":
                success = self._install_via_pip(tool_package)
            elif tool_package.source_type == "apt":
                success = self._install_via_apt(tool_package)
            elif tool_package.source_type == "conda":
                success = self._install_via_conda(tool_package)
            else:
                success = False
            
            if success and tool_package.install_commands:
                for cmd in tool_package.install_commands:
                    subprocess.run(cmd, shell=True, cwd=target_dir, check=True)
            
            self._save_tool_manifest(tool_package, target_dir)
            self.installed_tools[tool_package.tool_id] = tool_package
            
            return True
        except Exception as e:
            logger.error(f"Failed to install {tool_package.tool_id}: {e}")
            return False
    
    def _get_platform(self) -> str:
        """获取当前平台"""
        if sys.platform.startswith('win'):
            return "windows"
        elif sys.platform.startswith('linux'):
            return "linux"
        elif sys.platform.startswith('darwin'):
            return "macos"
        return "unknown"
    
    def _download_from_github(self, pkg: ToolPackage, target_dir: Path) -> bool:
        """从GitHub下载工具"""
        # 解析GitHub URL
        # https://github.com/user/repo -> https://github.com/user/repo/archive/refs/tags/{version}.zip
        url = pkg.source_url.rstrip('/')
        
        if pkg.version == "latest":
            # 获取最新release
            api_url = url.replace("github.com", "api.github.com/repos") + "/releases/latest"
            try:
                response = requests.get(api_url)
                response.raise_for_status()
                data = response.json()
                download_url = data.get("assets", [{}])[0].get("browser_download_url")
                if not download_url:
                    download_url = f"{url}/archive/refs/heads/main.zip"
            except:
                download_url = f"{url}/archive/refs/heads/main.zip"
        else:
            download_url = f"{url}/archive/refs/tags/{pkg.version}.zip"
        
        return self._download_and_extract(download_url, target_dir)
    
    def _download_from_url(self, pkg: ToolPackage, target_dir: Path) -> bool:
        """从URL下载工具"""
        return self._download_and_extract(pkg.source_url, target_dir)
    
    def _download_and_extract(self, url: str, target_dir: Path) -> bool:
        """下载并解压文件"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
                temp_file = Path(f.name)
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if url.endswith('.zip'):
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
            elif url.endswith('.tar.gz') or url.endswith('.tgz'):
                with tarfile.open(temp_file, 'r:gz') as tar_ref:
                    tar_ref.extractall(target_dir)
            else:
                shutil.move(str(temp_file), str(target_dir / os.path.basename(url)))
            
            temp_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def _install_via_pip(self, pkg: ToolPackage) -> bool:
        """通过pip安装"""
        try:
            cmd = f"pip install {pkg.source_url}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            return True
        except:
            return False
    
    def _install_via_apt(self, pkg: ToolPackage) -> bool:
        """通过apt安装（Linux）"""
        if sys.platform.startswith('linux'):
            try:
                cmd = f"sudo apt-get install -y {pkg.source_url}"
                subprocess.run(cmd, shell=True, check=True, capture_output=True)
                return True
            except:
                return False
        return False
    
    def _install_via_conda(self, pkg: ToolPackage) -> bool:
        """通过conda安装"""
        try:
            cmd = f"conda install -y {pkg.source_url}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            return True
        except:
            return False
    
    def _save_tool_manifest(self, pkg: ToolPackage, target_dir: Path):
        """保存工具清单"""
        manifest = {
            "tool_id": pkg.tool_id,
            "name": pkg.name,
            "description": pkg.description,
            "source_type": pkg.source_type,
            "source_url": pkg.source_url,
            "version": pkg.version,
            "target_dir": str(target_dir),
            "executable": pkg.executable,
            "check_command": pkg.check_command
        }
        
        import json
        with open(target_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    def is_tool_installed(self, tool_id: str) -> bool:
        """检查工具是否已安装"""
        return tool_id in self.installed_tools
    
    def get_tool_path(self, tool_id: str) -> Optional[Path]:
        """获取工具路径"""
        pkg = self.installed_tools.get(tool_id)
        if pkg:
            return Path(pkg.target_dir) if pkg.target_dir else self.download_dir / tool_id
        return None
    
    def get_executable_path(self, tool_id: str) -> Optional[str]:
        """获取可执行文件路径"""
        pkg = self.installed_tools.get(tool_id)
        if pkg and pkg.executable:
            tool_path = self.get_tool_path(tool_id)
            if tool_path:
                return str(tool_path / pkg.executable)
        return None
    
    def uninstall_tool(self, tool_id: str) -> bool:
        """卸载工具"""
        if tool_id in self.installed_tools:
            tool_path = self.get_tool_path(tool_id)
            if tool_path and tool_path.exists():
                shutil.rmtree(tool_path, ignore_errors=True)
            del self.installed_tools[tool_id]
            return True
        return False
    
    def list_installed_tools(self) -> List[ToolPackage]:
        """列出已安装工具"""
        return list(self.installed_tools.values())


class EnvironmentalToolRegistry:
    """环境领域工具注册表 - 预定义常用环评/安全/应急工具"""
    
    def __init__(self):
        self.tools: Dict[str, ToolPackage] = self._load_predefined_tools()
    
    def _load_predefined_tools(self) -> Dict[str, ToolPackage]:
        """加载预定义工具"""
        tools = {}
        
        # 环评工具
        tools["cmaq"] = ToolPackage(
            tool_id="cmaq",
            name="CMAQ",
            description="开源多尺度空气质量模拟系统",
            source_type="github",
            source_url="https://github.com/USEPA/CMAQ",
            version="latest",
            check_command="cmaq --version",
            dependencies=["netcdf", "mpi"],
            supported_platforms=["linux"]
        )
        
        tools["noisemodelling"] = ToolPackage(
            tool_id="noisemodelling",
            name="NoiseModelling",
            description="符合ISO 1996标准的噪声预测工具",
            source_type="github",
            source_url="https://github.com/INRA/NoiseModelling",
            version="latest",
            check_command="java -jar NoiseModelling.jar --help",
            dependencies=["java"],
            supported_platforms=["windows", "linux", "macos"]
        )
        
        tools["openlca"] = ToolPackage(
            tool_id="openlca",
            name="openLCA",
            description="生命周期评估工具",
            source_type="url",
            source_url="https://github.com/GreenDelta/olca-app/releases/download/v2.0.0/openLCA-2.0.0-win64.zip",
            version="2.0.0",
            executable="openLCA.exe",
            check_command="openLCA --help",
            dependencies=["java"],
            supported_platforms=["windows", "linux", "macos"]
        )
        
        # 安全风险工具
        tools["raven"] = ToolPackage(
            tool_id="raven",
            name="RAVEN",
            description="风险分析虚拟环境",
            source_type="github",
            source_url="https://github.com/idaholab/RAVEN",
            version="latest",
            check_command="raven --version",
            dependencies=["python", "numpy"],
            supported_platforms=["linux", "windows"]
        )
        
        # 应急工具
        tools["slab"] = ToolPackage(
            tool_id="slab",
            name="SLAB",
            description="重质气体扩散模型",
            source_type="url",
            source_url="https://www.epa.gov/sites/default/files/2020-06/slab_v2.2.2.zip",
            version="2.2.2",
            executable="SLAB.exe",
            check_command="SLAB",
            supported_platforms=["windows"]
        )
        
        tools["epanet"] = ToolPackage(
            tool_id="epanet",
            name="EPANET",
            description="开源水网模拟引擎",
            source_type="github",
            source_url="https://github.com/OpenWaterAnalytics/EPANET",
            version="latest",
            check_command="epanet --version",
            supported_platforms=["windows", "linux", "macos"]
        )
        
        # 监测工具
        tools["grass"] = ToolPackage(
            tool_id="grass",
            name="GRASS GIS",
            description="开源GIS系统",
            source_type="apt",
            source_url="grass",
            check_command="grass --version",
            supported_platforms=["linux"]
        )
        
        # 可研工具
        tools["coolprop"] = ToolPackage(
            tool_id="coolprop",
            name="CoolProp",
            description="热物理性质计算库",
            source_type="pip",
            source_url="coolprop",
            check_command="python -c \"import CoolProp; print(CoolProp.__version__)\"",
            supported_platforms=["windows", "linux", "macos"]
        )
        
        tools["openmodelica"] = ToolPackage(
            tool_id="openmodelica",
            name="OpenModelica",
            description="多领域物理系统建模",
            source_type="url",
            source_url="https://github.com/OpenModelica/OMCompiler/releases/download/v1.22.0/OpenModelica-v1.22.0-win64.exe",
            version="1.22.0",
            executable="omc.exe",
            check_command="omc --version",
            supported_platforms=["windows", "linux"]
        )
        
        return tools
    
    def get_tool(self, tool_id: str) -> Optional[ToolPackage]:
        """获取工具定义"""
        return self.tools.get(tool_id)
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolPackage]:
        """列出工具，可选按类别筛选"""
        if category:
            # 简单的类别映射
            category_map = {
                "环评": ["cmaq", "noisemodelling", "openlca"],
                "安全": ["raven"],
                "应急": ["slab", "epanet"],
                "监测": ["grass"],
                "可研": ["coolprop", "openmodelica"]
            }
            tool_ids = category_map.get(category, [])
            return [self.tools[t] for t in tool_ids if t in self.tools]
        return list(self.tools.values())
    
    def search_tools(self, keyword: str) -> List[ToolPackage]:
        """搜索工具"""
        keyword_lower = keyword.lower()
        results = []
        for tool in self.tools.values():
            if (keyword_lower in tool.name.lower() or 
                keyword_lower in tool.description.lower()):
                results.append(tool)
        return results


downloader = ToolDownloader()
env_tool_registry = EnvironmentalToolRegistry()
