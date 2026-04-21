"""
根系装配园 (Root Assembly Garden)

核心理念：让开源库像外来种一样在苗圃中培育，然后嫁接到生命之树

七阶嫁接管线：
1. 良种搜寻台 (Seed Scouting Table) - 输入解析
2. 良种雷达 (Seed Radar) - 库发现
3. 亲和试验台 (Affinity Test Bench) - 冲突检测
4. 园丁指挥台 (Gardener Command) - 用户决策
5. 育苗温床 (Sapling Bed) - 沙箱安装
6. 萌芽试炼场 (Sprout Trial Ground) - 测试验证
7. 扎根部署 (Rooting Deploy) - 动态上线
"""

from .navigator import StarNavigator
from .radar import OSSRadar
from .conflict import ConflictDetector
from .isolation_bay import IsolationBay
from .adapter_gen import AdapterGenerator
from .proving_grounds import ProvingGrounds
from .deployment_bay import DeploymentBay
from .assembler_core import RootAssemblyGarden

__all__ = [
    'RootAssemblyGarden',
    'StarNavigator',
    'OSSRadar',
    'ConflictDetector',
    'IsolationBay',
    'AdapterGenerator',
    'ProvingGrounds',
    'DeploymentBay',
]


def get_assembler() -> RootAssemblyGarden:
    """获取根系装配园单例"""
    return RootAssemblyGarden.get_instance()