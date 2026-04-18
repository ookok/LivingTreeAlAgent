"""
Hermes P2P Tools - P2P核心作为Hermes工具集
============================================

将P2P核心功能封装为Hermes Tools，供Agent调用：

1. 节点管理工具
   - start_p2p_node: 启动P2P节点
   - stop_p2p_node: 停止P2P节点
   - get_node_status: 获取节点状态
   - get_network_peers: 获取网络邻居

2. 配置管理工具
   - check_config: 检查配置完整性
   - get_missing_config: 获取缺失配置项
   - update_config: 更新配置
   - validate_config: 验证配置有效性

3. 中继服务器工具
   - connect_relay: 连接中继服务器
   - disconnect_relay: 断开中继服务器
   - get_relay_status: 获取中继状态
   - broadcast_to_relay: 向中继广播消息

4. 模型分发工具
   - search_models: 搜索可用模型
   - download_model: 下载模型
   - get_download_progress: 获取下载进度
   - cancel_download: 取消下载

5. 密钥管理工具
   - get_api_key: 获取API密钥
   - check_key_health: 检查密钥健康状态
   - rotate_key: 轮转密钥

6. 身份与数据管家工具 (新增)
   - create_identity: 创建身份
   - unlock_vault: 解锁保险箱
   - sync_data: 同步数据
   - create_backup: 创建备份
   - get_connection_status: 获取连接状态

Author: Hermes Desktop AI Assistant
"""

from .hermes_p2p_tools import (
    register_p2p_tools,
    get_p2p_tools,
)
from .gateway import (
    HermesGateway,
    GatewayMessage,
    UIAction,
    MessageType,
    get_hermes_gateway,
    reset_gateway,
)
from .hermes_evolution import (
    HermesGuideEvolution,
    EvolutionEvent,
    get_hermes_guide_evolution,
)
from .hermes_data_butler_tools import (
    # 身份管理
    create_identity,
    unlock_vault,
    lock_vault,
    recover_identity,
    get_vault_status,
    # 数据管理
    set_state,
    get_state,
    sync_data,
    sync_with_peer,
    # 备份管理
    create_backup,
    restore_backup,
    list_backups,
    # 连接管理
    get_connection_status,
    force_reconnect,
    # 诊断
    run_diagnose,
)

__all__ = [
    # 工具注册
    'register_p2p_tools',
    'get_p2p_tools',
    # Gateway
    'HermesGateway',
    'GatewayMessage',
    'UIAction',
    'MessageType',
    'get_hermes_gateway',
    'reset_gateway',
    # 进化系统
    'HermesGuideEvolution',
    'EvolutionEvent',
    'get_hermes_guide_evolution',
    # 数据管家工具
    'create_identity',
    'unlock_vault',
    'lock_vault',
    'recover_identity',
    'get_vault_status',
    'set_state',
    'get_state',
    'sync_data',
    'sync_with_peer',
    'create_backup',
    'restore_backup',
    'list_backups',
    'get_connection_status',
    'force_reconnect',
    'run_diagnose',
]

__version__ = '2.0.0'