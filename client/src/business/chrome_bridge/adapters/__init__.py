"""
Website Adapters Package
=========================

内置 80+ 网站适配器，支持会话复用和反检测。

适配器按网站分类：
- 开发平台：github, gitlab, bitbucket, gitee, coding...
- 技术社区：stackoverflow, reddit, hackernews, v2ex, juejin...
- 云服务商：aws, azure, gcp, aliyun, tencent_cloud...
- AI 平台：openai, claude, huggingface, modelscope...
- 社交媒体：twitter, linkedin, weibo, zhihu, bilibili...
- 其他：wikipedia, arxiv, pubmed, cnki...
"""

from loguru import logger

# 导入所有适配器模块（延迟导入，按需加载）
_loaded = False
_registry_data = None


def _get_registry_data():
    """获取注册表数据（从 website_adapter_registry 导入）"""
    global _registry_data
    if _registry_data is None:
        from business.chrome_bridge.website_adapter_registry import WEBSITE_REGISTRY_DATA
        _registry_data = WEBSITE_REGISTRY_DATA
    return _registry_data


def register_all(force_reload: bool = False):
    """
    注册所有内置适配器

    Args:
        force_reload: 强制重新加载
    """
    global _loaded
    if _loaded and not force_reload:
        return

    from business.chrome_bridge.website_adapter_registry import get_adapter_registry

    registry = get_adapter_registry()
    data = _get_registry_data()

    imported = 0
    failed = 0

    for entry in data:
        name = entry["name"]
        module_name = entry["module"]
        class_name = entry["class"]

        try:
            import importlib
            mod = importlib.import_module(
                f"client.src.business.chrome_bridge.adapters.{module_name}"
            )
            adapter_class = getattr(mod, class_name)
            adapter = adapter_class()
            registry.register(adapter)
            imported += 1
        except Exception as e:
            logger.debug(f"适配器 {name} 导入失败（将使用通用适配器）: {e}")
            failed += 1

    _loaded = True
    logger.bind(module="adapters").info(
        f"适配器注册完成：成功 {imported}，失败 {failed}"
    )


__all__ = ["register_all"]
