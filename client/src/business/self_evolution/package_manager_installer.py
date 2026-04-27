"""
PackageManagerInstaller - 包管理器自动安装器

核心功能：
1. 通过 pip/npm/cargo/brew/winget/choco 自动安装 CLI 工具
2. 安装后自动验证（shutil.which / version check / import test）
3. 触发 StructuredHelpParser 解析帮助文档
4. 自动生成 BaseTool 封装并注册到 ToolRegistry
5. 支持 PRESET_CLI_TOOLS 扩展字段：install_command, verify_command, post_install

流程：
  检测缺失 → 安装 → 验证 → 解析帮助 → LLM生成封装 → 注册
"""

import os
import sys
import json
import shutil
import asyncio
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger


@dataclass
class InstallResult:
    """安装结果"""
    tool_name: str
    package_manager: str          # pip / npm / cargo / brew / winget / choco
    success: bool
    version: str = ""
    message: str = ""
    verification_passed: bool = False
    help_text: str = ""
    error: str = ""


@dataclass
class PackageSpec:
    """包安装规格"""
    tool_name: str                # 工具名（如 "flopy"）
    package_manager: str          # 包管理器
    install_command: List[str]    # 安装命令（如 ["pip", "install", "flopy"]）
    verify_command: Optional[List[str]] = None  # 验证命令（如 ["python", "-c", "import flopy"]）
    verify_type: str = "cli"      # cli | import | version
    category: str = "general"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    post_install: Optional[List[str]] = None  # 安装后命令
    priority: str = "P2"


# ── EIA 专用包预设 ─────────────────────────────────────────

EIA_PACKAGE_PRESETS: Dict[str, PackageSpec] = {
    # ── 地下水模拟 ──
    "flopy": PackageSpec(
        tool_name="flopy",
        package_manager="pip",
        install_command=["pip", "install", "flopy"],
        verify_command=["python", "-c", "import flopy; print(flopy.__version__)"],
        verify_type="import",
        category="eia_groundwater",
        description="MODFLOW 地下水模型 Python 接口，支持 MODFLOW-6/MODFLOW-2005/MT3DMS/SEAWAT",
        tags=["eia", "groundwater", "modflow", "simulation"],
        priority="P1",
    ),
    "pyemu": PackageSpec(
        tool_name="pyemu",
        package_manager="pip",
        install_command=["pip", "install", "pyemu"],
        verify_command=["python", "-c", "import pyemu; print('ok')"],
        verify_type="import",
        category="eia_groundwater",
        description="地下水模型不确定性分析和参数估计工具（PEST 接口）",
        tags=["eia", "groundwater", "pest", "uncertainty"],
        priority="P2",
    ),

    # ── 水网络模拟 ──
    "pyswmm": PackageSpec(
        tool_name="pyswmm",
        package_manager="pip",
        install_command=["pip", "install", "pyswmm"],
        verify_command=["python", "-c", "import pyswmm; print(pyswmm.__version__)"],
        verify_type="import",
        category="eia_water",
        description="SWMM 雨水/污水管网模型 Python 接口",
        tags=["eia", "water", "swmm", "stormwater"],
        priority="P1",
    ),
    "swmmio": PackageSpec(
        tool_name="swmmio",
        package_manager="pip",
        install_command=["pip", "install", "swmmio"],
        verify_command=["python", "-c", "import swmmio; print('ok')"],
        verify_type="import",
        category="eia_water",
        description="SWMM 输入/输出文件解析和操作工具",
        tags=["eia", "water", "swmm", "parsing"],
        priority="P1",
    ),
    "wntr": PackageSpec(
        tool_name="wntr",
        package_manager="pip",
        install_command=["pip", "install", "wntr"],
        verify_command=["python", "-c", "import wntr; print(wntr.__version__)"],
        verify_type="import",
        category="eia_water",
        description="供水管网水力/水质模拟工具（EPANET 接口）",
        tags=["eia", "water", "epanet", "hydraulic"],
        priority="P1",
    ),

    # ── 水动力/水环境 ──
    "mikeio": PackageSpec(
        tool_name="mikeio",
        package_manager="pip",
        install_command=["pip", "install", "mikeio"],
        verify_command=["python", "-c", "import mikeio; print(mikeio.__version__)"],
        verify_type="import",
        category="eia_water",
        description="MIKE 系列模型文件 I/O（DFS 格式读写）",
        tags=["eia", "water", "mike", "dfs"],
        priority="P2",
    ),
    "xarray": PackageSpec(
        tool_name="xarray",
        package_manager="pip",
        install_command=["pip", "install", "xarray", "netCDF4"],
        verify_command=["python", "-c", "import xarray; print(xarray.__version__)"],
        verify_type="import",
        category="eia_water",
        description="多维数组数据处理，水环境模型输出分析",
        tags=["eia", "water", "data", "analysis"],
        priority="P1",
    ),

    # ── 大气扩散 ──
    "pyaerocom": PackageSpec(
        tool_name="pyaerocom",
        package_manager="pip",
        install_command=["pip", "install", "pyaerocom"],
        verify_command=["python", "-c", "import pyaerocom; print('ok')"],
        verify_type="import",
        category="eia_air",
        description="大气成分分析和模型评估工具",
        tags=["eia", "air", "aerosol", "model"],
        priority="P2",
    ),

    # ── GIS / 空间分析 ──
    "geopandas": PackageSpec(
        tool_name="geopandas",
        package_manager="pip",
        install_command=["pip", "install", "geopandas"],
        verify_command=["python", "-c", "import geopandas; print(geopandas.__version__)"],
        verify_type="import",
        category="gis",
        description="地理空间数据处理，支持 Shapefile/GeoJSON/GeoPackage",
        tags=["gis", "spatial", "geodata"],
        priority="P1",
    ),
    "rasterio": PackageSpec(
        tool_name="rasterio",
        package_manager="pip",
        install_command=["pip", "install", "rasterio"],
        verify_command=["python", "-c", "import rasterio; print(rasterio.__version__)"],
        verify_type="import",
        category="gis",
        description="栅格数据 I/O（GeoTIFF/NetCDF/DEM 等）",
        tags=["gis", "raster", "dem"],
        priority="P1",
    ),
    "shapely": PackageSpec(
        tool_name="shapely",
        package_manager="pip",
        install_command=["pip", "install", "shapely"],
        verify_command=["python", "-c", "import shapely; print(shapely.__version__)"],
        verify_type="import",
        category="gis",
        description="几何对象操作（缓冲区/交集/距离计算）",
        tags=["gis", "geometry", "buffer"],
        priority="P1",
    ),
    "pyproj": PackageSpec(
        tool_name="pyproj",
        package_manager="pip",
        install_command=["pip", "install", "pyproj"],
        verify_command=["python", "-c", "import pyproj; print(pyproj.__version__)"],
        verify_type="import",
        category="gis",
        description="坐标系转换（WGS84/GCJ02/CGCS2000 等）",
        tags=["gis", "crs", "projection"],
        priority="P1",
    ),
    "folium": PackageSpec(
        tool_name="folium",
        package_manager="pip",
        install_command=["pip", "install", "folium"],
        verify_command=["python", "-c", "import folium; print(folium.__version__)"],
        verify_type="import",
        category="gis",
        description="交互式地图可视化（HTML 地图生成）",
        tags=["gis", "visualization", "map"],
        priority="P2",
    ),

    # ── 数据分析 / 可视化 ──
    "pandas": PackageSpec(
        tool_name="pandas",
        package_manager="pip",
        install_command=["pip", "install", "pandas"],
        verify_command=["python", "-c", "import pandas; print(pandas.__version__)"],
        verify_type="import",
        category="analysis",
        description="数据分析和处理（表格/时序/统计）",
        tags=["analysis", "data", "statistics"],
        priority="P0",
    ),
    "numpy": PackageSpec(
        tool_name="numpy",
        package_manager="pip",
        install_command=["pip", "install", "numpy"],
        verify_command=["python", "-c", "import numpy; print(numpy.__version__)"],
        verify_type="import",
        category="analysis",
        description="数值计算（矩阵/线性代数/FFT）",
        tags=["analysis", "numeric", "math"],
        priority="P0",
    ),
    "matplotlib": PackageSpec(
        tool_name="matplotlib",
        package_manager="pip",
        install_command=["pip", "install", "matplotlib"],
        verify_command=["python", "-c", "import matplotlib; print(matplotlib.__version__)"],
        verify_type="import",
        category="visualization",
        description="绑图库（折线/柱状/等值线/玫瑰图等）",
        tags=["visualization", "plot", "chart"],
        priority="P1",
    ),
    "scipy": PackageSpec(
        tool_name="scipy",
        package_manager="pip",
        install_command=["pip", "install", "scipy"],
        verify_command=["python", "-c", "import scipy; print(scipy.__version__)"],
        verify_type="import",
        category="analysis",
        description="科学计算（插值/优化/统计/积分）",
        tags=["analysis", "scientific", "statistics"],
        priority="P1",
    ),
    "openpyxl": PackageSpec(
        tool_name="openpyxl",
        package_manager="pip",
        install_command=["pip", "install", "openpyxl"],
        verify_command=["python", "-c", "import openpyxl; print(openpyxl.__version__)"],
        verify_type="import",
        category="document",
        description="Excel (.xlsx) 文件读写",
        tags=["document", "excel", "spreadsheet"],
        priority="P1",
    ),

    # ── 文档处理 ──
    "python-docx": PackageSpec(
        tool_name="python-docx",
        package_manager="pip",
        install_command=["pip", "install", "python-docx"],
        verify_command=["python", "-c", "import docx; print('ok')"],
        verify_type="import",
        category="document",
        description="Word (.docx) 文件读写",
        tags=["document", "word", "docx"],
        priority="P1",
    ),
    "markitdown": PackageSpec(
        tool_name="markitdown",
        package_manager="pip",
        install_command=["pip", "install", "markitdown"],
        verify_command=["python", "-c", "from markitdown import MarkItDown; print('ok')"],
        verify_type="import",
        category="document",
        description="多格式转 Markdown（PDF/DOCX/PPTX/XLSX/HTML 等）",
        tags=["document", "markdown", "conversion"],
        priority="P1",
    ),

    # ── CLI 工具（需要 pip install --user 或全局安装） ──
    "ffmpeg-python": PackageSpec(
        tool_name="ffmpeg-python",
        package_manager="pip",
        install_command=["pip", "install", "ffmpeg-python"],
        verify_command=["python", "-c", "import ffmpeg; print('ok')"],
        verify_type="import",
        category="media",
        description="FFmpeg Python 绑定（音视频处理）",
        tags=["media", "video", "audio"],
        priority="P2",
    ),

    # ── npm 全局工具 ──
    "typescript": PackageSpec(
        tool_name="typescript",
        package_manager="npm",
        install_command=["npm", "install", "-g", "typescript"],
        verify_command=["tsc", "--version"],
        verify_type="version",
        category="development",
        description="TypeScript 编译器",
        tags=["development", "typescript", "compiler"],
        priority="P2",
    ),

    # ── cargo 工具 ──
    "ripgrep-cargo": PackageSpec(
        tool_name="rg",
        package_manager="cargo",
        install_command=["cargo", "install", "ripgrep"],
        verify_command=["rg", "--version"],
        verify_type="version",
        category="search",
        description="超快速文本搜索（Rust 实现，通过 cargo install 安装）",
        tags=["search", "ripgrep", "rust"],
        priority="P2",
    ),
}

# 合并 EIA 预设到通用预设
ALL_PACKAGE_PRESETS = {**EIA_PACKAGE_PRESETS}


class PackageManagerInstaller:
    """
    包管理器自动安装器

    支持 pip / npm / cargo / brew / winget / choco 六种包管理器。
    安装后自动验证、解析帮助文档、生成 BaseTool 封装。

    用法：
        installer = PackageManagerInstaller()

        # 安装单个包
        result = await installer.install("flopy")

        # 批量安装（按优先级）
        results = await installer.install_all(priority="P1")

        # 自动发现缺失并安装
        results = await installer.auto_install_missing()

        # 查看状态
        status = installer.get_status_report()
    """

    # 包管理器配置
    PACKAGE_MANAGERS = {
        "pip": {
            "name": "pip",
            "description": "Python 包管理器",
            "check_cmd": ["pip", "--version"],
            "install_prefix": ["pip", "install"],
            "user_flag": "--user",
            "global_flag": "",
            "timeout": 300,
        },
        "npm": {
            "name": "npm",
            "description": "Node.js 包管理器",
            "check_cmd": ["npm", "--version"],
            "install_prefix": ["npm", "install", "-g"],
            "timeout": 300,
        },
        "cargo": {
            "name": "cargo",
            "description": "Rust 包管理器",
            "check_cmd": ["cargo", "--version"],
            "install_prefix": ["cargo", "install"],
            "timeout": 600,
        },
        "brew": {
            "name": "brew",
            "description": "Homebrew (macOS/Linux)",
            "check_cmd": ["brew", "--version"],
            "install_prefix": ["brew", "install"],
            "timeout": 600,
        },
        "winget": {
            "name": "winget",
            "description": "Windows 包管理器",
            "check_cmd": ["winget", "--version"],
            "install_prefix": ["winget", "install", "--accept-package-agreements", "--accept-source-agreements"],
            "timeout": 600,
        },
        "choco": {
            "name": "choco",
            "description": "Chocolatey (Windows)",
            "check_cmd": ["choco", "--version"],
            "install_prefix": ["choco", "install", "-y"],
            "timeout": 600,
        },
    }

    def __init__(
        self,
        dry_run: bool = False,
        auto_approve_p0: bool = True,
        auto_approve_p1: bool = False,
        install_timeout: int = 300,
        verify_timeout: int = 30,
    ):
        """
        初始化

        Args:
            dry_run: 仅分析不安装
            auto_approve_p0: 自动批准 P0 安装（无需用户确认）
            auto_approve_p1: 自动批准 P1 安装
            install_timeout: 安装超时秒数
            verify_timeout: 验证超时秒数
        """
        self._dry_run = dry_run
        self._auto_approve = {"P0": auto_approve_p0, "P1": auto_approve_p1, "P2": False}
        self._install_timeout = install_timeout
        self._verify_timeout = verify_timeout
        self._installed: Dict[str, InstallResult] = {}
        self._available_managers: Dict[str, bool] = {}
        self._logger = logger.bind(component="PackageManagerInstaller")

    # ── Phase 0: 检测可用包管理器 ─────────────────────────

    def detect_available_managers(self) -> Dict[str, bool]:
        """检测系统中可用的包管理器"""
        self._logger.info("检测可用包管理器...")
        for mgr_name, mgr_config in self.PACKAGE_MANAGERS.items():
            check_cmd = mgr_config["check_cmd"]
            try:
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self._available_managers[mgr_name] = result.returncode == 0
            except Exception:
                self._available_managers[mgr_name] = False

        available = {k: v for k, v in self._available_managers.items() if v}
        self._logger.info(f"可用包管理器: {list(available.keys())}")
        return self._available_managers

    # ── Phase 1: 检测已安装包 ─────────────────────────────

    def check_installed(self, spec: PackageSpec) -> bool:
        """
        检查包是否已安装

        通过 verify_command 或 import 检测
        """
        if spec.verify_command:
            try:
                result = subprocess.run(
                    spec.verify_command,
                    capture_output=True,
                    text=True,
                    timeout=self._verify_timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return result.returncode == 0
            except Exception:
                return False

        # fallback: shutil.which
        return shutil.which(spec.tool_name) is not None

    def get_missing_packages(self, priority: Optional[str] = None) -> List[PackageSpec]:
        """获取未安装的包列表"""
        if not self._available_managers:
            self.detect_available_managers()

        missing = []
        for name, spec in ALL_PACKAGE_PRESETS.items():
            if priority and spec.priority != priority:
                continue
            if not self.check_installed(spec):
                # 检查对应的包管理器是否可用
                if self._available_managers.get(spec.package_manager, False):
                    missing.append(spec)
        return missing

    # ── Phase 2: 安装 ────────────────────────────────────

    async def install(
        self,
        package_name: str,
        user_confirm: Optional[bool] = None,
    ) -> InstallResult:
        """
        安装指定包

        Args:
            package_name: 包名（对应 ALL_PACKAGE_PRESETS 的 key）
            user_confirm: 用户确认（None=根据 auto_approve 设置）

        Returns:
            InstallResult
        """
        spec = ALL_PACKAGE_PRESETS.get(package_name)
        if not spec:
            return InstallResult(
                tool_name=package_name,
                package_manager="unknown",
                success=False,
                error=f"未知包: {package_name}，不在预设列表中",
            )

        return await self._install_spec(spec, user_confirm)

    async def _install_spec(
        self,
        spec: PackageSpec,
        user_confirm: Optional[bool] = None,
    ) -> InstallResult:
        """安装单个 PackageSpec"""
        result = InstallResult(
            tool_name=spec.tool_name,
            package_manager=spec.package_manager,
            success=False,
        )

        # 检查是否已安装
        if self.check_installed(spec):
            result.success = True
            result.verification_passed = True
            result.message = f"{spec.tool_name} 已安装"
            self._logger.info(f"{spec.tool_name} 已安装，跳过")
            return result

        # 权限检查
        should_auto = user_confirm if user_confirm is not None else self._auto_approve.get(spec.priority, False)
        if not should_auto and not self._dry_run:
            self._logger.warning(f"[{spec.priority}] {spec.tool_name} 需要用户确认安装")

        if self._dry_run:
            result.message = f"[DRY RUN] 将安装: {' '.join(spec.install_command)}"
            result.success = True
            return result

        # 检查包管理器可用
        if not self._available_managers.get(spec.package_manager, False):
            result.error = f"包管理器 {spec.package_manager} 不可用"
            return result

        # 执行安装
        self._logger.info(f"正在安装 {spec.tool_name} ({spec.package_manager})...")
        try:
            cmd = spec.install_command
            timeout = self.PACKAGE_MANAGERS[spec.package_manager].get("timeout", self._install_timeout)

            loop = asyncio.get_event_loop()
            proc_result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )

            if proc_result.returncode != 0:
                result.error = f"安装失败 (exit={proc_result.returncode}): {proc_result.stderr[:500]}"
                return result

            result.success = True
            result.message = f"安装成功: {spec.tool_name}"

        except subprocess.TimeoutExpired:
            result.error = f"安装超时 ({timeout}s)"
            return result
        except Exception as e:
            result.error = str(e)
            return result

        # 执行安装后命令
        if spec.post_install:
            for post_cmd in spec.post_install:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda cmd=post_cmd: subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
                    )
                except Exception as e:
                    self._logger.warning(f"post_install 命令失败: {e}")

        # 验证
        result.verification_passed = self._verify_install(spec)
        if result.verification_passed:
            # 尝试获取版本
            result.version = self._get_installed_version(spec)
            result.message += f" (v{result.version})" if result.version else " (已验证)"

        self._installed[spec.tool_name] = result
        return result

    def _verify_install(self, spec: PackageSpec) -> bool:
        """验证安装"""
        if spec.verify_command:
            try:
                result = subprocess.run(
                    spec.verify_command,
                    capture_output=True,
                    text=True,
                    timeout=self._verify_timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return result.returncode == 0
            except Exception:
                return False
        return shutil.which(spec.tool_name) is not None

    def _get_installed_version(self, spec: PackageSpec) -> str:
        """获取安装版本"""
        try:
            if spec.verify_type == "import" and spec.verify_command:
                result = subprocess.run(
                    spec.verify_command,
                    capture_output=True,
                    text=True,
                    timeout=self._verify_timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                output = (result.stdout or "").strip()
                return output.split("\n")[-1].strip() if output else ""
            elif spec.verify_type == "version" and spec.verify_command:
                result = subprocess.run(
                    spec.verify_command,
                    capture_output=True,
                    text=True,
                    timeout=self._verify_timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                output = (result.stdout or "").strip()
                # 提取版本号
                import re
                match = re.search(r"[\d]+\.[\d]+[\.\d]*", output)
                return match.group(0) if match else output[:50]
        except Exception:
            pass
        return ""

    # ── Phase 3: 批量安装 ────────────────────────────────

    async def install_all(
        self,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[InstallResult]:
        """
        批量安装

        Args:
            priority: 优先级过滤（P0/P1/P2）
            category: 类别过滤（如 eia_groundwater, gis, analysis）
        """
        missing = self.get_missing_packages(priority)
        if category:
            missing = [s for s in missing if s.category == category]

        results = []
        for spec in missing:
            result = await self._install_spec(spec)
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        self._logger.info(
            f"批量安装完成: {success_count}/{len(results)} 成功 "
            f"(P0→P1→P2)"
        )
        return results

    async def auto_install_missing(self) -> List[InstallResult]:
        """自动安装缺失的 P0 + P1 包"""
        results = []
        for p in ["P0", "P1"]:
            batch = await self.install_all(priority=p)
            results.extend(batch)
        return results

    # ── Phase 4: 自动学习 ────────────────────────────────

    async def install_and_learn(
        self,
        package_name: str,
        learn_depth: str = "full",
    ) -> Tuple[InstallResult, Optional[Dict[str, Any]]]:
        """
        安装包并自动学习其用法

        Args:
            package_name: 包名
            learn_depth: 学习深度
                - "quick": 仅解析 --help
                - "full": 解析帮助 + 生成 BaseTool 封装
                - "deep": full + 查找官方文档 + 示例代码

        Returns:
            (InstallResult, learned_info or None)
        """
        # 安装
        install_result = await self.install(package_name)
        if not install_result.success:
            return install_result, None

        learned_info = None

        if learn_depth in ("quick", "full", "deep"):
            # 解析帮助文档
            from client.src.business.self_evolution.structured_help_parser import StructuredHelpParser
            parser = StructuredHelpParser()

            spec = ALL_PACKAGE_PRESETS.get(package_name)
            if spec:
                if spec.verify_type == "import":
                    # Python 包：生成学习命令
                    learned_info = await parser.learn_python_package(
                        package_name=spec.tool_name,
                        help_commands=self._get_python_help_commands(spec),
                        depth=learn_depth,
                    )
                else:
                    # CLI 工具：解析 --help
                    if spec.verify_command:
                        exe = spec.verify_command[0]
                        help_text = await self._get_cli_help(exe)
                        if help_text:
                            learned_info = parser.parse_help_text(help_text, spec.tool_name)

        if learn_depth == "deep" and learned_info:
            # 尝试查找官方文档
            doc_info = await self._find_documentation(package_name)
            if doc_info:
                learned_info["documentation"] = doc_info

        return install_result, learned_info

    def _get_python_help_commands(self, spec: PackageSpec) -> List[str]:
        """获取 Python 包的帮助命令列表"""
        pkg = spec.tool_name
        return [
            f"python -c \"import {pkg}; help({pkg})\"",
            f"python -c \"import {pkg}; print({pkg}.__doc__)\"",
            f"python -c \"import {pkg}; print(dir({pkg}))\"",
        ]

    async def _get_cli_help(self, exe: str) -> str:
        """获取 CLI 工具的帮助文档"""
        for flag in ["--help", "-h", "help"]:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        [exe, flag],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                )
                output = (result.stdout or "") + (result.stderr or "")
                if output and len(output) > 20:
                    return output[:4000]
            except Exception:
                continue
        return ""

    async def _find_documentation(self, package_name: str) -> Optional[Dict[str, str]]:
        """查找包的官方文档"""
        # TODO: 通过 web_crawler 或 deep_search 查找
        return None

    # ── Phase 5: 生成 BaseTool 封装 ─────────────────────

    async def install_wrap_and_register(
        self,
        package_name: str,
    ) -> Tuple[InstallResult, bool]:
        """
        完整流程：安装 → 学习 → 生成封装 → 注册到 ToolRegistry

        Returns:
            (InstallResult, registered: bool)
        """
        install_result, learned = await self.install_and_learn(package_name, learn_depth="full")
        if not install_result.success:
            return install_result, False

        if not learned:
            self._logger.warning(f"无法学习 {package_name}，跳过封装")
            return install_result, False

        # 生成封装代码
        from client.src.business.self_evolution.cli_tool_discoverer import CLIToolDiscoverer
        discoverer = CLIToolDiscoverer()

        spec = ALL_PACKAGE_PRESETS.get(package_name)
        if not spec:
            return install_result, False

        # 构建 CLIToolInfo
        from client.src.business.self_evolution.cli_tool_discoverer import CLIToolInfo
        info = CLIToolInfo(
            name=spec.tool_name,
            path=shutil.which(spec.tool_name) or spec.tool_name,
            help_text=learned.get("raw_help", learned.get("description", "")),
            category=spec.category,
            description=spec.description,
        )

        # 生成封装
        try:
            code = await discoverer.generate_wrapper(info, category=spec.category)
            if code:
                success = await discoverer.wrap_and_register(info, code)
                return install_result, success
        except Exception as e:
            self._logger.error(f"封装失败: {e}")

        return install_result, False

    # ── 状态报告 ─────────────────────────────────────────

    def get_status_report(self) -> Dict[str, Any]:
        """获取包安装状态报告"""
        if not self._available_managers:
            self.detect_available_managers()

        report = {
            "available_managers": {k: v for k, v in self._available_managers.items() if v},
            "total_packages": len(ALL_PACKAGE_PRESETS),
            "by_category": {},
            "by_priority": {"P0": {"total": 0, "installed": 0}, "P1": {"total": 0, "installed": 0}, "P2": {"total": 0, "installed": 0}},
            "installed": [],
            "missing": [],
        }

        for name, spec in ALL_PACKAGE_PRESETS.items():
            is_installed = self.check_installed(spec)
            entry = {
                "name": name,
                "tool_name": spec.tool_name,
                "package_manager": spec.package_manager,
                "priority": spec.priority,
                "category": spec.category,
                "installed": is_installed,
                "description": spec.description,
            }

            if is_installed:
                report["installed"].append(entry)
            else:
                report["missing"].append(entry)

            # 按优先级
            p = spec.priority
            if p in report["by_priority"]:
                report["by_priority"][p]["total"] += 1
                if is_installed:
                    report["by_priority"][p]["installed"] += 1

            # 按类别
            c = spec.category
            report["by_category"].setdefault(c, {"total": 0, "installed": 0})
            report["by_category"][c]["total"] += 1
            if is_installed:
                report["by_category"][c]["installed"] += 1

        return report


# ── 便捷函数 ─────────────────────────────────────────────

async def quick_install(package_name: str) -> InstallResult:
    """快速安装单个包"""
    installer = PackageManagerInstaller()
    return await installer.install(package_name)


async def auto_install_eia_packages() -> List[InstallResult]:
    """自动安装所有 EIA 相关包"""
    installer = PackageManagerInstaller()
    eia_categories = {"eia_groundwater", "eia_water", "eia_air", "gis"}
    results = []
    for category in eia_categories:
        batch = await installer.install_all(category=category)
        results.extend(batch)
    return results


async def install_and_learn(package_name: str) -> Tuple[InstallResult, Optional[Dict]]:
    """安装并自动学习"""
    installer = PackageManagerInstaller()
    return await installer.install_and_learn(package_name)
