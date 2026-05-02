"""
FusionRAG - 多源融合智能加速系统
桥接层: 委托到 client.src.business.fusion_rag
TODO: 逐步将子模块迁移到 livingtree/core/fusion_rag/
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_biz = os.path.join(_root, 'client', 'src')
if _biz not in sys.path:
    sys.path.insert(0, _biz)

from client.src.business.fusion_rag import *
