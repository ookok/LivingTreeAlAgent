# 零配置分布式中继集群架构

## 1. 设计目标

| 目标 | 说明 |
|------|------|
| **零配置** | 节点启动时只需指定 cluster 名称，无需知道其他节点 IP |
| **自动发现** | 通过轻量级注册中心自动发现同集群节点 |
| **去中心化** | 无单点故障，任意节点可独立工作 |
| **消息同步** | Gossip 协议保证最终一致性 |
| **负载均衡** | 客户端随机选择节点，自动分散负载 |

## 2. 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Global Registry                              │
│                    (轻量级，只存节点列表)                              │
│                                                                      │
│   /register ──► NodeList[cluster] ◄── /heartbeat                   │
│         │                        │                                   │
│         ▼                        ▼                                   │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                           │
│   │ Node A  │  │ Node B  │  │ Node C  │                           │
│   │ relay-1 │◄─┤ relay-2 ├─►│ relay-3 │   (Gossip 消息同步)         │
│   └────┬────┘  └────┬────┘  └────┬────┘                           │
│        │            │            │                                  │
│        ▼            ▼            ▼                                  │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                           │
│   │ Clients │  │ Clients │  │ Clients │                           │
│   └─────────┘  └─────────┘  └─────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 组件说明

### 3.1 NodeRegistry（节点注册表）

```
职责：
- 管理所有在线节点
- 心跳保活（120秒 TTL）
- 节点选择（随机/加权）

存储结构：
{
  "hermes": {
    "relay-001": { host, port, load, status },
    "relay-002": { host, port, load, status },
    ...
  }
}
```

### 3.2 GossipProtocol（Gossip 协议）

```
工作原理：
1. 节点 A 收到消息 M
2. 随机选择 FANOUT=3 个节点发送 M
3. 收到 M 的节点重复步骤 1-2
4. 直到 TTL=10 轮或全网传播完成

特点：
- 最终一致性（非强一致）
- 去中心化
- 容错（节点宕机不影响其他节点）
```

### 3.3 LoadBalancer（负载均衡）

```
客户端路由策略：
1. 客户端首次连接，随机选择可用节点
2. 后续请求优先保持同一节点
3. 节点故障时自动切换

负载计算：
- 基于 WebSocket 连接数
- 优先选择连接数少的节点
```

## 4. API 端点

### 4.1 节点注册

```
POST /api/cluster/register
Body: {
  "node_id": "xxx",
  "cluster": "hermes",
  "host": "192.168.1.100",
  "port": 8080,
  "public_host": "x.x.x.x",
  "public_port": 8080
}
Response: { "success": true }
```

### 4.2 心跳

```
POST /api/cluster/heartbeat
Body: { "node_id": "xxx" }
Response: { "success": true }
```

### 4.3 获取节点列表

```
GET /api/cluster/nodes?cluster=hermes&status=online
Response: {
  "nodes": [
    { "node_id": "xxx", "host": "...", "port": 8080, "load": 5 }
  ]
}
```

### 4.4 WebSocket 客户端连接

```
WS /ws/{channel}?client_id=xxx&token=xxx

消息格式（客户端 -> 服务端）：
{
  "type": "message",
  "content": "Hello",
  "channel": "general"
}

消息格式（服务端 -> 客户端）：
{
  "type": "message",
  "msg_id": "xxx",
  "sender": "client-001",
  "content": "Hello",
  "timestamp": 1234567890
}
```

## 5. 零配置流程

```
用户启动中继服务器：

1. 启动命令
   python -m server.relay_server.main_cluster --cluster=hermes --port=8080

2. 节点自动行为
   ├─ 生成 node_id（基于 host:port:uuid 哈希）
   ├─ 向 Registry 注册（指定 cluster）
   ├─ 定时心跳保活
   └─ 启动 Gossip 传播循环

3. 客户端连接流程
   ├─ 调用 /api/cluster/nodes 获取节点列表
   ├─ 随机选择一个节点
   ├─ 建立 WebSocket 连接
   └─ 加入频道开始通信

4. 消息传播流程
   ├─ 客户端 A 向 Node-1 发送消息
   ├─ Node-1 通过 Gossip 广播到 Node-2, Node-3
   ├─ Node-2, Node-3 投递给本地客户端
   └─ 重复直到全网同步
```

## 6. 对比

| 特性 | 单体架构 | 分布式集群 |
|------|----------|------------|
| 部署 | 简单 | 简单 |
| 扩展 | 手动 | 自动 |
| 容错 | 单点故障 | 无单点 |
| 消息同步 | 无需 | Gossip |
| 配置 | 需指定节点 | 只需集群名 |
| 延迟 | 低 | 略高（多跳） |

## 7. 配置文件

```yaml
# relay_cluster.yaml
cluster:
  name: hermes          # 集群名称（唯一标识）
  region: cn-east       # 区域（可选，用于多区域部署）

server:
  host: 0.0.0.0
  port: 8080
  public_host: auto     # 自动检测
  public_port: auto

registry:
  url: https://registry.hermes-p2p.com  # 注册中心地址
  fallback:
    - https://relay-backup.hermes-p2p.com

gossip:
  fanout: 3             # 每轮传播节点数
  interval: 2            # 传播间隔（秒）
  ttl: 10               # 消息生存周期

limits:
  max_clients: 10000    # 最大客户端数
  max_channels: 1000    # 最大频道数
  max_history: 200      # 每频道历史消息数
```

## 8. 启动方式

```bash
# 单节点启动
python -m server.relay_server.main_cluster --cluster=hermes --port=8080

# 多节点启动（自动形成集群）
# 终端 1
python -m server.relay_server.main_cluster --cluster=hermes --port=8080
# 终端 2
python -m server.relay_server.main_cluster --cluster=hermes --port=8081
# 终端 3
python -m server.relay_server.main_cluster --cluster=hermes --port=8082

# 客户端连接时，只需指定集群名，系统自动选择节点
```
