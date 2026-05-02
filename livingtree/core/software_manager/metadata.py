import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional


software_metadata: Dict[str, Dict[str, Any]] = {
    # 开发工具
    "vscode": {
        "id": "vscode",
        "name": "Visual Studio Code",
        "category": "development",
        "description": "微软开发的轻量级代码编辑器",
        "icon": "vscode",
        "backend": "winget",
        "package_id": "Microsoft.VisualStudioCode",
        "tags": ["code", "editor", "development"]
    },
    "python": {
        "id": "python",
        "name": "Python",
        "category": "development",
        "description": "Python编程语言",
        "icon": "python",
        "backend": "winget",
        "package_id": "Python.Python.3.11",
        "tags": ["python", "programming", "development"]
    },
    "git": {
        "id": "git",
        "name": "Git",
        "category": "development",
        "description": "版本控制系统",
        "icon": "git",
        "backend": "winget",
        "package_id": "Git.Git",
        "tags": ["version", "control", "git"]
    },
    "nodejs": {
        "id": "nodejs",
        "name": "Node.js",
        "category": "development",
        "description": "JavaScript运行时",
        "icon": "nodejs",
        "backend": "winget",
        "package_id": "OpenJS.NodeJS",
        "tags": ["javascript", "node", "development"]
    },
    "docker": {
        "id": "docker",
        "name": "Docker Desktop",
        "category": "development",
        "description": "容器化平台",
        "icon": "docker",
        "backend": "winget",
        "package_id": "Docker.DockerDesktop",
        "tags": ["container", "docker", "devops"]
    },
    
    # 计算工具
    "anaconda": {
        "id": "anaconda",
        "name": "Anaconda",
        "category": "computation",
        "description": "数据科学和机器学习平台",
        "icon": "anaconda",
        "backend": "winget",
        "package_id": "Anaconda.Anaconda3",
        "tags": ["data", "science", "machine", "learning"]
    },
    "julia": {
        "id": "julia",
        "name": "Julia",
        "category": "computation",
        "description": "高性能数值计算语言",
        "icon": "julia",
        "backend": "winget",
        "package_id": "JuliaLang.Julia",
        "tags": ["numerical", "computing", "julia"]
    },
    "r": {
        "id": "r",
        "name": "R",
        "category": "computation",
        "description": "统计分析和绘图语言",
        "icon": "r",
        "backend": "winget",
        "package_id": "RProject.R",
        "tags": ["statistics", "data", "analysis"]
    },
    
    # 工业软件
    "qgis": {
        "id": "qgis",
        "name": "QGIS",
        "category": "industrial",
        "description": "开源GIS地理信息系统",
        "icon": "qgis",
        "backend": "chocolatey",
        "package_id": "qgis",
        "tags": ["gis", "mapping", "geospatial"]
    },
    "grass": {
        "id": "grass",
        "name": "GRASS GIS",
        "category": "industrial",
        "description": "开源GIS分析系统",
        "icon": "grass",
        "backend": "chocolatey",
        "package_id": "grass-gis",
        "tags": ["gis", "analysis", "geospatial"]
    },
    "paraview": {
        "id": "paraview",
        "name": "ParaView",
        "category": "industrial",
        "description": "科学可视化工具",
        "icon": "paraview",
        "backend": "chocolatey",
        "package_id": "paraview",
        "tags": ["visualization", "science", "3d"]
    },
    
    # 应急工具
    "gnuplot": {
        "id": "gnuplot",
        "name": "Gnuplot",
        "category": "emergency",
        "description": "科学绘图工具",
        "icon": "gnuplot",
        "backend": "chocolatey",
        "package_id": "gnuplot",
        "tags": ["plotting", "graph", "visualization"]
    },
    "octave": {
        "id": "octave",
        "name": "GNU Octave",
        "category": "emergency",
        "description": "数值计算和可视化工具",
        "icon": "octave",
        "backend": "winget",
        "package_id": "GNU.Octave",
        "tags": ["matlab", "numerical", "computing"]
    },
    
    # 办公工具
    "notepadplusplus": {
        "id": "notepadplusplus",
        "name": "Notepad++",
        "category": "productivity",
        "description": "高级文本编辑器",
        "icon": "notepad",
        "backend": "winget",
        "package_id": "Notepad++.Notepad++",
        "tags": ["editor", "text", "notepad"]
    },
    "7zip": {
        "id": "7zip",
        "name": "7-Zip",
        "category": "productivity",
        "description": "文件压缩工具",
        "icon": "7zip",
        "backend": "winget",
        "package_id": "7zip.7zip",
        "tags": ["compression", "archive", "zip"]
    },
    "sumatrapdf": {
        "id": "sumatrapdf",
        "name": "Sumatra PDF",
        "category": "productivity",
        "description": "轻量级PDF阅读器",
        "icon": "pdf",
        "backend": "winget",
        "package_id": "SumatraPDF.SumatraPDF",
        "tags": ["pdf", "reader", "document"]
    }
}


categories = {
    "development": {"name": "开发工具", "icon": "code"},
    "computation": {"name": "计算工具", "icon": "calculator"},
    "industrial": {"name": "工业软件", "icon": "factory"},
    "emergency": {"name": "应急工具", "icon": "alert"},
    "productivity": {"name": "办公工具", "icon": "office"}
}


class MetadataManager:
    """软件元数据管理器"""
    
    def __init__(self):
        self.metadata = software_metadata
        self.categories = categories
        self.install_history_file = Path(__file__).parent / 'install_history.json'
        self._load_install_history()
    
    def _load_install_history(self):
        """加载安装历史"""
        if self.install_history_file.exists():
            try:
                with open(self.install_history_file, 'r', encoding='utf-8') as f:
                    self.install_history = json.load(f)
            except:
                self.install_history = {}
        else:
            self.install_history = {}
    
    def _save_install_history(self):
        """保存安装历史"""
        with open(self.install_history_file, 'w', encoding='utf-8') as f:
            json.dump(self.install_history, f, indent=2, ensure_ascii=False)
    
    def get_all_software(self) -> List[Dict[str, Any]]:
        """获取所有软件列表"""
        return list(self.metadata.values())
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按类别获取软件"""
        return [s for s in self.metadata.values() if s.get('category') == category]
    
    def get_by_id(self, software_id: str) -> Optional[Dict[str, Any]]:
        """按ID获取软件"""
        return self.metadata.get(software_id)
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索软件"""
        query_lower = query.lower()
        results = []
        for software in self.metadata.values():
            if (query_lower in software.get('name', '').lower() or
                query_lower in software.get('description', '').lower() or
                any(query_lower in tag.lower() for tag in software.get('tags', []))):
                results.append(software)
        return results
    
    def record_install(self, software_id: str, success: bool, install_time: str):
        """记录安装历史"""
        self.install_history[software_id] = {
            'success': success,
            'install_time': install_time,
            'last_updated': install_time
        }
        self._save_install_history()
    
    def get_install_history(self) -> Dict[str, Any]:
        """获取安装历史"""
        return self.install_history
    
    def get_categories(self) -> Dict[str, Dict[str, str]]:
        """获取所有类别"""
        return self.categories


metadata_manager = MetadataManager()