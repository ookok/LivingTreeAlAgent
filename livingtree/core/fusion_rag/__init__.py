"""
FusionRAG - 多源融合智能加速系统
兼容层: 优先使用 livingtree.core.knowledge.rag，缺失时回退到 client.src.business.fusion_rag。
"""
import sys
import os
import importlib

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_biz = os.path.join(_root, 'client', 'src')
if _biz not in sys.path:
    sys.path.insert(0, _biz)

from livingtree.core.knowledge.rag import *
from livingtree.core.knowledge.rag import __all__ as __all__

_legacy_pkg = "client.src.business.fusion_rag"
_legacy_mod = None

def _load_legacy_module():
    global _legacy_mod
    if _legacy_mod is None:
        _legacy_mod = importlib.import_module(_legacy_pkg)
    return _legacy_mod


def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    if name in globals():
        return globals()[name]
    legacy = _load_legacy_module()
    try:
        return getattr(legacy, name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
