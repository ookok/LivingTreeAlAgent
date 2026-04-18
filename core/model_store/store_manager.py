"""
商店管理器 (Model Store Manager)
================================

协调所有模型商店组件的统一接口

组件：
- ModelRegistry     - 模型注册表
- DeployExecutor    - 部署执行器
- RuntimeManager    - 运行时管理器
- P2PModelDiscovery - P2P模型发现

Author: Hermes Desktop AI Assistant
"""

import os
import logging
import threading
import json
from typing import Dict, Optional, Any, List, Callable
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# 全局单例
_store_manager_instance: Optional['ModelStoreManager'] = None
_store_manager_lock = threading.Lock()


class ModelStoreManager:
    """
    模型商店管理器 - 统一协调所有组件

    功能：
    1. 模型发现与浏览
    2. 一键安装/卸载
    3. 统一执行接口
    4. P2P模型共享
    5. 资源监控

    使用示例：
        store = get_store_manager()
        store.install('aermod')
        result = store.run_model('aermod', {'source': {...}})
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化模型商店管理器

        Args:
            config: 配置字典
        """
        self.config = config or {}

        # 存储目录
        self.storage_dir = Path(
            self.config.get('storage_dir') or os.path.expanduser('~/.model_store')
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self._init_components()

        # 启动P2P发现
        if self.config.get('enable_p2p', True):
            relay_servers = self.config.get('relay_servers', [])
            self.p2p_discovery.start(relay_servers=relay_servers)

        # 启动运行时监控
        if self.config.get('enable_monitoring', True):
            self.runtime_manager.start_monitoring()

        logger.info("ModelStoreManager 初始化完成")

    def _init_components(self):
        """初始化所有组件"""
        # 模型注册表
        from .model_registry import ModelRegistry
        self.registry = ModelRegistry(storage_dir=str(self.storage_dir))

        # 部署执行器
        from .deploy_executor import DeployExecutor
        self.deploy_executor = DeployExecutor(install_dir=str(self.storage_dir / 'installs'))

        # 运行时管理器
        from .runtime_manager import RuntimeManager
        self.runtime_manager = RuntimeManager(install_dir=str(self.storage_dir / 'installs'))

        # P2P模型发现
        from .p2p_discovery import P2PModelDiscovery
        self.p2p_discovery = P2PModelDiscovery(storage_dir=str(self.storage_dir / 'p2p'))

        # 注册本地已安装模型到P2P
        self._register_installed_models()

    def _register_installed_models(self):
        """注册已安装的模型到P2P发现"""
        for model in self.registry.list_installed():
            model_dir = self.storage_dir / 'installs' / model.id

            # 查找可执行文件
            if model.level.value == 'light':
                # Python包不需要注册到P2P
                continue

            # 查找二进制文件
            for ext in ['.exe', '']:
                bin_path = model_dir / f"{model.id}{ext}"
                if bin_path.exists():
                    self.p2p_discovery.register_model(
                        model.id,
                        str(bin_path),
                        version=model.installed_version or model.version
                    )
                    break

    # ========== 模型发现 ==========

    def list_models(self, category: Optional[str] = None, level: Optional[str] = None,
                    installed_only: bool = False) -> List[Dict]:
        """
        列出模型

        Args:
            category: 按类别筛选
            level: 按级别筛选
            installed_only: 只显示已安装

        Returns:
            模型列表
        """
        models = self.registry.list_all()

        if category:
            from .model_registry import ModelCategory
            models = [m for m in models if m.category.value == category]

        if level:
            from .model_registry import ModelLevel
            models = [m for m in models if m.level.value == level]

        if installed_only:
            models = [m for m in models if m.installed]

        return [m.to_dict() for m in models]

    def search_models(self, query: str) -> List[Dict]:
        """
        搜索模型

        Args:
            query: 搜索关键词

        Returns:
            匹配的模型列表
        """
        results = self.registry.search(query)
        return [m.to_dict() for m in results]

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """
        获取模型详情

        Args:
            model_id: 模型ID

        Returns:
            模型信息
        """
        model = self.registry.get_model(model_id)
        if not model:
            return None

        info = model.to_dict()

        # 添加运行时信息
        runtime_info = self.runtime_manager.get_runtime_info(model_id)
        if runtime_info:
            info['runtime'] = runtime_info.to_dict()

        return info

    def get_categories(self) -> List[str]:
        """获取所有类别"""
        return [c.value for c in self.registry.get_categories()]

    # ========== 模型安装 ==========

    def install(self, model_id: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        安装模型（主入口）

        Args:
            model_id: 模型ID
            progress_callback: 进度回调

        Returns:
            安装结果
        """
        model = self.registry.get_model(model_id)
        if not model:
            return {'success': False, 'error': f'未知模型: {model_id}'}

        if model.installed:
            return {'success': True, 'message': '模型已安装'}

        # 执行部署
        result = self.deploy_executor.deploy(model_id, model, progress_callback)

        # 更新注册表状态
        if result.success:
            self.registry.update_install_status(model_id, True, model.version)

            # 注册到P2P发现
            if result.install_path:
                self.p2p_discovery.register_model(model_id, result.install_path, model.version)

        return {
            'success': result.success,
            'message': result.message,
            'install_path': result.install_path,
            'error': result.error,
        }

    def uninstall(self, model_id: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        卸载模型

        Args:
            model_id: 模型ID
            progress_callback: 进度回调

        Returns:
            卸载结果
        """
        model = self.registry.get_model(model_id)
        if not model:
            return {'success': False, 'error': f'未知模型: {model_id}'}

        if not model.installed:
            return {'success': True, 'message': '模型未安装'}

        # 执行卸载
        result = self.deploy_executor.uninstall(model_id, model, progress_callback)

        # 更新注册表状态
        if result.success:
            self.registry.update_install_status(model_id, False)

            # 从P2P注销
            self.p2p_discovery.unregister_model(model_id)

        return {
            'success': result.success,
            'message': result.message,
            'error': result.error,
        }

    def update(self, model_id: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        更新模型

        Args:
            model_id: 模型ID
            progress_callback: 进度回调

        Returns:
            更新结果
        """
        # 先卸载
        uninstall_result = self.uninstall(model_id, progress_callback)
        if not uninstall_result['success']:
            return uninstall_result

        # 再安装（会安装最新版本）
        return self.install(model_id, progress_callback)

    # ========== 模型执行 ==========

    def run_model(self, model_id: str, input_data: Any, timeout: Optional[int] = None) -> Dict:
        """
        运行模型（主入口）

        Args:
            model_id: 模型ID
            input_data: 输入数据
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        model = self.registry.get_model(model_id)
        if not model:
            return {'success': False, 'error': f'未知模型: {model_id}'}

        if not model.installed:
            return {'success': False, 'error': '模型未安装，请先安装'}

        # 执行模型
        result = self.runtime_manager.execute(model_id, model, input_data, timeout)

        return {
            'success': result.success,
            'output': result.output,
            'error': result.error,
            'execution_time_ms': result.execution_time_ms,
            'stdout': result.stdout,
            'stderr': result.stderr,
        }

    def get_runtime_status(self, model_id: str) -> Optional[Dict]:
        """
        获取运行时状态

        Args:
            model_id: 模型ID

        Returns:
            运行时状态
        """
        runtime_info = self.runtime_manager.get_runtime_info(model_id)
        if runtime_info:
            return runtime_info.to_dict()
        return None

    # ========== P2P模型发现 ==========

    async def find_model_on_network(self, model_id: str) -> List[Dict]:
        """
        在网络上搜索模型

        Args:
            model_id: 模型ID

        Returns:
            可用的模型源列表
        """
        packages = await self.p2p_discovery.find_model(model_id)
        return [p.to_dict() for p in packages]

    async def download_model_from_network(self, model_id: str,
                                          progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        从网络下载模型

        Args:
            model_id: 模型ID
            progress_callback: 进度回调

        Returns:
            下载后的文件路径
        """
        return await self.p2p_discovery.download_model(
            model_id,
            progress_callback=progress_callback
        )

    # ========== 监控与统计 ==========

    def get_dashboard_data(self) -> Dict:
        """
        获取仪表盘数据

        Returns:
            仪表盘数据
        """
        # 运行时状态
        runtimes = self.runtime_manager.list_runtimes()

        # 模型统计
        stats = self.registry.get_stats()

        return {
            'timestamp': datetime.now().isoformat(),
            'total_models': stats['total_models'],
            'installed_models': stats['installed_models'],
            'by_category': stats['by_category'],
            'by_level': stats['by_level'],
            'runtimes': [r.to_dict() for r in runtimes],
            'p2p_stats': self.p2p_discovery.get_stats(),
        }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_models': len(self.registry.list_all()),
            'installed_models': len(self.registry.list_installed()),
            'running_models': sum(1 for r in self.runtime_manager.list_runtimes() 
                                  if r.status.value == 'busy'),
            'p2p_nodes': len(self.p2p_discovery.nodes),
            'local_models': len(self.p2p_discovery.local_models),
        }

    def export_model_list(self, format: str = 'json') -> str:
        """
        导出模型列表

        Args:
            format: 格式（json/markdown）

        Returns:
            导出的内容
        """
        models = self.list_models()

        if format == 'json':
            return json.dumps(models, ensure_ascii=False, indent=2)

        elif format == 'markdown':
            lines = ["# 环保模型商店 - 模型清单", ""]
            lines.append(f"总计: {len(models)} 个模型", "")
            lines.append("| ID | 名称 | 类别 | 级别 | 已安装 | 版本 |")
            lines.append("|----|------|------|------|--------|------|")

            for m in models:
                lines.append(
                    f"| {m['id']} | {m['name']} | {m['category']} | "
                    f"{m['level']} | {'是' if m['installed'] else '否'} | "
                    f"{m['version']} |"
                )

            return "\n".join(lines)

        return "[]"

    # ========== 生命周期 ==========

    def shutdown(self):
        """关闭模型商店"""
        logger.info("正在关闭模型商店...")

        # 停止P2P发现
        self.p2p_discovery.stop()

        # 停止运行时监控
        self.runtime_manager.cleanup()

        logger.info("模型商店已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False


def get_store_manager(config: Optional[Dict] = None) -> ModelStoreManager:
    """
    获取模型商店单例

    Args:
        config: 可选配置

    Returns:
        ModelStoreManager实例
    """
    global _store_manager_instance

    with _store_manager_lock:
        if _store_manager_instance is None:
            _store_manager_instance = ModelStoreManager(config=config)
        return _store_manager_instance


def reset_store_manager():
    """重置模型商店单例"""
    global _store_manager_instance

    with _store_manager_lock:
        if _store_manager_instance:
            _store_manager_instance.shutdown()
        _store_manager_instance = None

    logger.info("ModelStoreManager 单例已重置")