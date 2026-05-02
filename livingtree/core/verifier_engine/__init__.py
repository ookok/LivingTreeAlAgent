"""
Verifier Engine - 验证引擎
桥接层: 委托到 client.src.business.verifier_engine
TODO: 逐步迁移到 livingtree/core/verifier_engine/
"""
import sys, os, importlib
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_biz = os.path.join(_root, 'client', 'src')
if _biz not in sys.path:
    sys.path.insert(0, _biz)

from client.src.business.verifier_engine import *

_legacy_pkg = "client.src.business.verifier_engine"

def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    try:
        return importlib.import_module(f"{_legacy_pkg}.{name}")
    except ImportError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
