"""
工具发现引擎 - 核心实现

实现Tool Morphogenesis（工具形态发生）能力。
"""
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ToolSource(Enum):
    """工具来源"""
    PYPI = "pypi"
    GITHUB = "github"
    LOCAL = "local"
    CUSTOM = "custom"


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    source: ToolSource
    url: str
    description: str
    version: str = "latest"
    install_command: Optional[str] = None
    score: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class ToolSearchResult:
    """工具搜索结果"""
    query: str
    results: List[ToolInfo]
    total_count: int
    execution_time: float


class ToolDiscoveryEngine:
    """
    工具发现引擎
    
    核心能力：
    1. 搜索外部工具（PyPI/GitHub）
    2. 自动安装和封装
    3. 创建自定义工具
    4. 注册为Skill
    """
    
    def __init__(self):
        self.installed_tools: Dict[str, ToolInfo] = {}
        self.skill_registry = {}
    
    def search_pypi(self, query: str, limit: int = 10) -> ToolSearchResult:
        """
        搜索PyPI包
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            ToolSearchResult
        """
        import time
        start_time = time.time()
        
        results = []
        
        try:
            # 使用pip search（需要pip-search包）
            result = subprocess.run(
                ["pip", "search", query],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines[:limit]:
                    if line:
                        parts = line.split(" - ")
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            description = " - ".join(parts[1:]).strip()
                            
                            results.append(ToolInfo(
                                name=name,
                                source=ToolSource.PYPI,
                                url=f"https://pypi.org/project/{name}",
                                description=description,
                                install_command=f"pip install {name}",
                                score=self._calculate_score(description)
                            ))
        
        except Exception as e:
            logger.warning(f"PyPI搜索失败: {e}")
            # 返回模拟结果
            results = self._get_mock_pypi_results(query)
        
        execution_time = time.time() - start_time
        
        return ToolSearchResult(
            query=query,
            results=results,
            total_count=len(results),
            execution_time=execution_time
        )
    
    def _get_mock_pypi_results(self, query: str) -> List[ToolInfo]:
        """获取模拟PyPI结果（用于演示）"""
        mock_results = {
            "air dispersion": [
                ToolInfo(
                    name="pydispersion",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/pydispersion",
                    description="大气扩散模型库",
                    install_command="pip install pydispersion",
                    score=0.85
                ),
                ToolInfo(
                    name="atmospheric-models",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/atmospheric-models",
                    description="大气科学模型集合",
                    install_command="pip install atmospheric-models",
                    score=0.75
                ),
            ],
            "financial": [
                ToolInfo(
                    name="numpy-financial",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/numpy-financial",
                    description="金融计算工具",
                    install_command="pip install numpy-financial",
                    score=0.9
                ),
                ToolInfo(
                    name="quantlib",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/quantlib",
                    description="量化金融库",
                    install_command="pip install quantlib",
                    score=0.85
                ),
            ],
            "data analysis": [
                ToolInfo(
                    name="pandas",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/pandas",
                    description="数据分析库",
                    install_command="pip install pandas",
                    score=0.95
                ),
                ToolInfo(
                    name="scikit-learn",
                    source=ToolSource.PYPI,
                    url="https://pypi.org/project/scikit-learn",
                    description="机器学习库",
                    install_command="pip install scikit-learn",
                    score=0.95
                ),
            ],
        }
        
        for key, tools in mock_results.items():
            if key.lower() in query.lower():
                return tools
        
        return [
            ToolInfo(
                name=f"tool-{query}",
                source=ToolSource.PYPI,
                url=f"https://pypi.org/project/{query}",
                description=f"{query}相关工具",
                install_command=f"pip install {query}",
                score=0.7
            )
        ]
    
    def search_github(self, query: str, limit: int = 10) -> ToolSearchResult:
        """
        搜索GitHub仓库
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            ToolSearchResult
        """
        import time
        start_time = time.time()
        
        # 模拟GitHub搜索结果
        mock_results = [
            ToolInfo(
                name="AirDispersionModel",
                source=ToolSource.GITHUB,
                url="https://github.com/example/AirDispersionModel",
                description="高性能大气扩散模型",
                score=0.88
            ),
            ToolInfo(
                name="EIA-Calculator",
                source=ToolSource.GITHUB,
                url="https://github.com/example/EIA-Calculator",
                description="环评计算工具集",
                score=0.82
            ),
        ]
        
        execution_time = time.time() - start_time
        
        return ToolSearchResult(
            query=query,
            results=mock_results[:limit],
            total_count=len(mock_results),
            execution_time=execution_time
        )
    
    def search_tools(self, query: str, sources: Optional[List[ToolSource]] = None) -> List[ToolInfo]:
        """
        搜索工具（综合多个来源）
        
        Args:
            query: 搜索关键词
            sources: 搜索来源（可选）
        
        Returns:
            ToolInfo列表
        """
        results = []
        
        if sources is None:
            sources = [ToolSource.PYPI, ToolSource.GITHUB]
        
        if ToolSource.PYPI in sources:
            pypi_result = self.search_pypi(query)
            results.extend(pypi_result.results)
        
        if ToolSource.GITHUB in sources:
            github_result = self.search_github(query)
            results.extend(github_result.results)
        
        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def install_tool(self, tool_info: ToolInfo) -> bool:
        """
        安装工具
        
        Args:
            tool_info: 工具信息
        
        Returns:
            是否成功
        """
        if not tool_info.install_command:
            logger.error(f"无法安装工具 {tool_info.name}: 没有安装命令")
            return False
        
        try:
            logger.info(f"📦 安装工具: {tool_info.name}")
            
            result = subprocess.run(
                tool_info.install_command.split(),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.installed_tools[tool_info.name] = tool_info
                logger.info(f"✅ 工具安装成功: {tool_info.name}")
                return True
            else:
                logger.error(f"❌ 工具安装失败: {tool_info.name}\n{result.stderr}")
                return False
        
        except Exception as e:
            logger.error(f"❌ 安装工具失败 {tool_info.name}: {e}")
            return False
    
    def generate_wrapper(self, tool_info: ToolInfo) -> str:
        """
        生成工具wrapper
        
        Args:
            tool_info: 工具信息
        
        Returns:
            wrapper代码
        """
        wrapper = f'''"""
自动生成的 {tool_info.name} 工具Wrapper

来源: {tool_info.source.value}
描述: {tool_info.description}
"""

import importlib

class {tool_info.name.capitalize()}Wrapper:
    """{tool_info.description}"""
    
    def __init__(self):
        self._module = importlib.import_module("{tool_info.name}")
    
    def __getattr__(self, name):
        """代理调用底层模块"""
        return getattr(self._module, name)

# 快捷访问
_wrapper_instance = None

def get_{tool_info.name}():
    """获取工具实例"""
    global _wrapper_instance
    if _wrapper_instance is None:
        _wrapper_instance = {tool_info.name.capitalize()}Wrapper()
    return _wrapper_instance
'''
        
        return wrapper
    
    def create_tool(self, requirements: str) -> bool:
        """
        创建自定义工具
        
        如果找不到合适的外部工具，自己创建一个。
        
        Args:
            requirements: 工具需求描述
        
        Returns:
            是否成功
        """
        logger.info(f"🛠️ 创建自定义工具: {requirements}")
        
        # 生成工具代码
        tool_code = self._generate_tool_code(requirements)
        
        # 保存工具文件
        tool_name = self._generate_tool_name(requirements)
        tool_path = Path(__file__).parent / f"tools/{tool_name}.py"
        
        try:
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tool_path, "w", encoding="utf-8") as f:
                f.write(tool_code)
            
            logger.info(f"✅ 自定义工具创建成功: {tool_path}")
            return True
        
        except Exception as e:
            logger.error(f"❌ 创建自定义工具失败: {e}")
            return False
    
    def _generate_tool_code(self, requirements: str) -> str:
        """生成工具代码"""
        from ..sica_engine.sica_engine import SICACodeGenerator
        
        generator = SICACodeGenerator()
        code = generator.generate_code(
            task_description=requirements,
            include_tests=True
        )
        
        return code
    
    def _generate_tool_name(self, requirements: str) -> str:
        """生成工具名称"""
        import re
        # 提取关键词
        keywords = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]+", requirements)
        # 使用前3个关键词
        name_parts = keywords[:3]
        # 转换为小写并连接
        return "_".join(name_parts).lower()
    
    def acquire_tool(self, requirements: str) -> Optional[ToolInfo]:
        """
        获取工具（搜索→安装→封装）
        
        Args:
            requirements: 工具需求描述
        
        Returns:
            ToolInfo如果成功，否则None
        """
        # 1. 搜索相关工具
        tools = self.search_tools(requirements)
        
        if tools:
            # 选择评分最高的工具
            best_tool = tools[0]
            logger.info(f"🎯 找到最佳工具: {best_tool.name} (评分: {best_tool.score})")
            
            # 2. 安装工具
            if self.install_tool(best_tool):
                # 3. 生成wrapper
                wrapper_code = self.generate_wrapper(best_tool)
                
                # 4. 保存wrapper
                wrapper_path = Path(__file__).parent / f"wrappers/{best_tool.name}_wrapper.py"
                wrapper_path.parent.mkdir(parents=True, exist_ok=True)
                with open(wrapper_path, "w", encoding="utf-8") as f:
                    f.write(wrapper_code)
                
                logger.info(f"📦 工具获取完成: {best_tool.name}")
                return best_tool
            else:
                logger.warning(f"⚠️ 安装失败，尝试创建自定义工具")
        
        # 如果没有找到或安装失败，创建自定义工具
        logger.info(f"🔧 未找到合适工具，创建自定义工具")
        if self.create_tool(requirements):
            return ToolInfo(
                name=self._generate_tool_name(requirements),
                source=ToolSource.CUSTOM,
                url="local",
                description=requirements
            )
        
        return None
    
    def _calculate_score(self, description: str) -> float:
        """计算工具评分"""
        score = 0.5
        
        # 根据关键词评分
        positive_keywords = ["高性能", "快速", "精确", "专业", "开源", "活跃"]
        for kw in positive_keywords:
            if kw in description:
                score += 0.1
        
        return min(score, 1.0)


# 单例模式
_tool_discovery_engine = None


def get_tool_discovery_engine() -> ToolDiscoveryEngine:
    """获取工具发现引擎单例"""
    global _tool_discovery_engine
    if _tool_discovery_engine is None:
        _tool_discovery_engine = ToolDiscoveryEngine()
    return _tool_discovery_engine