"""
环保模型商店 (Model Store)
===========================

核心理念：从模型发现 → 一键部署 → 统一调用的全流程自动化

模型分级：
1. 轻量级 (Light)    - pip包，直接import
2. 中型 (Medium)     - 预编译二进制，CLI封装
3. 重型 (Heavy)      - Docker容器，REST/gRPC
4. 云端 (Cloud)      - API密钥调用

架构：
├── ModelRegistry     - 模型元数据管理、版本控制
├── DeployExecutor    - 部署执行器（pip/binary/docker/api）
├── RuntimeManager    - 运行时管理（进程池/容器/API网关）
├── P2PDiscovery      - P2P模型发现与分发（复用relay_chain基础设施）
└── ModelStoreManager - 商店统一管理器

复用现有基础设施：
- core/p2p_knowledge/      - P2P知识同步
- core/relay_chain/        - 中继链数据同步
- core/key_management/     - 密钥管理（API Key安全存储）

Author: Hermes Desktop AI Assistant
"""

from .model_registry import ModelRegistry, ModelInfo, ModelCategory, ModelLevel
from .deploy_executor import DeployExecutor, DeployStatus
from .runtime_manager import RuntimeManager, RuntimeStatus
from .p2p_discovery import P2PModelDiscovery, ModelPackage
from .store_manager import ModelStoreManager, get_store_manager

__all__ = [
    'ModelRegistry',
    'ModelInfo',
    'ModelCategory',
    'ModelLevel',
    'DeployExecutor',
    'DeployStatus',
    'RuntimeManager',
    'RuntimeStatus',
    'P2PModelDiscovery',
    'ModelPackage',
    'ModelStoreManager',
    'get_store_manager',
]

__version__ = '1.0.0'