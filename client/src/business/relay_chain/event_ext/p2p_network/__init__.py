"""
P2P 自组织网络 - Zero-Config Distributed System

零配置、自发现、自组织的分布式 P2P 网络实现。

核心特性：
1. 零配置：启动时无需指定任何 IP/端口/节点列表
2. 自动发现：UDP 多播广播，节点自动找到彼此
3. 自组织：节点间自动建立连接，形成 P2P 网络
4. 自调度：基于负载感知的智能任务分配
5. 自愈：故障自动检测与恢复，支持领导者选举

架构分层：
├── discovery/      自动发现层（UDP多播 + 节点交换）
├── network/        网络层（TCP连接 + 路由协议）
├── scheduler/      调度层（负载均衡 + 任务分发）
└── distributed_node.py  主节点类（整合所有功能）

使用示例：
```python
from client.src.business.relay_chain.event_ext.p2p_network import DistributedNode

# 零配置启动
node = DistributedNode()
node.start()

# 自动发现邻居
# 自动选举协调者
# 自动分配任务
```

协议消息类型：
- DISCOVER: 节点发现广播
- HELLO: 节点握手响应
- PEER_EXCHANGE: 节点列表交换
- ELECTION: 选举投票
- COORDINATOR: 协调者公告
- HEARTBEAT: 心跳保活
- TASK_DISPATCH: 任务分发
- TASK_RESULT: 任务结果
-负载上报
"""

from .distributed_node import DistributedNode
from .discovery.multicast import MulticastDiscover
from .discovery.election import Election, NodeRole
from .network.protocol import Protocol, MessageType
from .network.routing import RoutingTable
from .scheduler.load_balancer import LoadBalancer
from .scheduler.task_distributor import TaskDistributor

__all__ = [
    # 主节点
    "DistributedNode",

    # 发现
    "MulticastDiscover",
    "Election",
    "NodeRole",

    # 网络
    "Protocol",
    "MessageType",
    "RoutingTable",

    # 调度
    "LoadBalancer",
    "TaskDistributor",
]
