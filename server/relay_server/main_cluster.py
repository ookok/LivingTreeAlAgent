"""
Hermes Relay Cluster - 分布式中继服务器主入口
==============================================

零配置分布式集群，支持：
- 自动节点发现
- Gossip 消息同步
- WebSocket 客户端接入
- 负载均衡

启动方式：
    # 单节点
    python -m server.relay_server.main_cluster

    # 指定集群和端口
    python -m server.relay_server.main_cluster --cluster=hermes --port=8080

    # 多节点集群
    python -m server.relay_server.main_cluster --cluster=hermes --port=8080
    python -m server.relay_server.main_cluster --cluster=hermes --port=8081
    python -m server.relay_server.main_cluster --cluster=hermes --port=8082
"""

import asyncio
import argparse
import logging
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from server.relay_server.cluster import NodeInfo, create_node, get_node, NodeRegistry, GossipProtocol

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RelayCluster.Main")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(title="Hermes Relay Cluster", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局注册表实例（模拟，实际应为独立服务）
_registry = NodeRegistry()
_cluster_nodes: dict = {}


# ============================================================
# Pydantic 模型
# ============================================================

class RegisterRequest(BaseModel):
    node_id: str
    cluster: str
    host: str
    port: int
    public_host: str = ""
    public_port: int = 0


class HeartbeatRequest(BaseModel):
    node_id: str


class ChatMessage(BaseModel):
    channel: str
    content: str
    sender: str = ""


# ============================================================
# API 端点
# ============================================================

@app.get("/")
async def root():
    return {
        "service": "Hermes Relay Cluster",
        "version": "2.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---- 节点注册 API ----

@app.post("/api/cluster/register")
async def register_node(req: RegisterRequest):
    """注册中继节点到集群"""
    node_info = NodeInfo(
        node_id=req.node_id,
        cluster=req.cluster,
        host=req.host,
        port=req.port,
        public_host=req.public_host or req.host,
        public_port=req.public_port or req.port
    )
    success = await _registry.register(node_info)
    return {"success": success, "node_id": req.node_id}


@app.post("/api/cluster/heartbeat")
async def heartbeat(req: HeartbeatRequest):
    """节点心跳"""
    success = await _registry.heartbeat(req.node_id)
    return {"success": success}


@app.get("/api/cluster/nodes")
async def get_nodes(cluster: str = "default", status: str = "online"):
    """获取集群节点列表"""
    nodes = await _registry.get_nodes(cluster, status)
    return {
        "cluster": cluster,
        "count": len(nodes),
        "nodes": [
            {
                "node_id": n.node_id,
                "host": n.host,
                "port": n.port,
                "public_host": n.public_host,
                "public_port": n.public_port,
                "status": n.status,
                "load": n.load
            }
            for n in nodes
        ]
    }


# ---- 中继消息 API ----

@app.post("/api/relay/message")
async def relay_message(msg: ChatMessage):
    """转发消息到指定频道（客户端 -> 服务端 -> 广播）"""
    node = get_node()
    if not node:
        raise HTTPException(status_code=503, detail="Relay node not initialized")

    await node.relay_message(msg.channel, msg.sender or "anonymous", msg.content)
    return {"success": True, "channel": msg.channel}


@app.get("/api/relay/history/{channel}")
async def get_history(channel: str, limit: int = 100):
    """获取频道历史消息"""
    node = get_node()
    if not node:
        raise HTTPException(status_code=503, detail="Relay node not initialized")

    history = await node.gossip.get_history(channel, limit)
    return {
        "channel": channel,
        "count": len(history),
        "messages": [
            {
                "msg_id": m.msg_id,
                "sender": m.sender,
                "content": m.content,
                "timestamp": m.timestamp
            }
            for m in history
        ]
    }


# ============================================================
# WebSocket 端点
# ============================================================

@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    """WebSocket 客户端连接"""
    # 获取参数
    client_id = websocket.query_params.get("client_id", "anonymous")
    token = websocket.query_params.get("token", "")

    # 验证 token
    if token:
        try:
            from server.relay_server.api.v1.user_auth import verify_token
            user_info = verify_token(token)
            if not user_info:
                await websocket.close(code=4001, reason="Token 无效或已过期")
                return
            # 将用户信息附加到连接中
            websocket.client_id = user_info.get("user_id", client_id)
            websocket.user_info = user_info
        except Exception as e:
            logger.warning(f"Token 验证失败: {e}")
            await websocket.close(code=4001, reason="Token 验证失败")
            return
    else:
        # 无 token 时作为匿名连接
        websocket.client_id = client_id
        websocket.user_info = {"anonymous": True}

    await websocket.accept()

    node = get_node()
    if not node:
        await websocket.send_json({"type": "error", "message": "Relay not initialized"})
        await websocket.close()
        return

    # 连接客户端
    await node.connect_client(websocket.client_id, channel, websocket)
    logger.info(f"WebSocket: {websocket.client_id} joined {channel}")

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                # 广播消息
                await node.relay_message(channel, websocket.client_id, data.get("content", ""))
                logger.debug(f"WebSocket: {websocket.client_id} sent to {channel}")

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        await node.disconnect_client(websocket.client_id, channel)
        logger.info(f"WebSocket: {websocket.client_id} left {channel}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await node.disconnect_client(websocket.client_id, channel)


# ============================================================
# 主入口
# ============================================================

async def startup_cluster(cluster: str, host: str, port: int):
    """启动集群节点"""
    logger.info(f"正在启动 Relay Cluster Node...")
    logger.info(f"  集群: {cluster}")
    logger.info(f"  地址: {host}:{port}")

    node = await create_node(
        cluster=cluster,
        host=host,
        port=port
    )

    # 注册到本地（模拟多节点场景）
    await _registry.register(NodeInfo(
        node_id=node.node_id,
        cluster=cluster,
        host=host,
        port=port,
        public_host=host,
        public_port=port
    ))

    logger.info(f"节点启动成功: {node.node_id}")
    return node


def main():
    parser = argparse.ArgumentParser(description="Hermes Relay Cluster Node")
    parser.add_argument("--cluster", "-c", default="hermes", help="集群名称")
    parser.add_argument("--host", "-h", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", "-p", type=int, default=8080, help="监听端口")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           Hermes Relay Cluster Node V2.0                   ║
╠══════════════════════════════════════════════════════════╣
║  集群: {args.cluster}
║  地址: {args.host}:{args.port}
╚══════════════════════════════════════════════════════════╝
    """)

    # 启动节点
    asyncio.run(startup_cluster(args.cluster, args.host, args.port))

    # 启动 FastAPI
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
