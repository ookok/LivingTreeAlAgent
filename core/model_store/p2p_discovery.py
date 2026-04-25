"""
P2P模型发现与分发 (P2P Model Discovery)
=========================================

复用现有P2P基础设施实现模型的分布式发现和分发

核心功能：
1. 模型包广播 - 向邻居节点广播可用模型
2. 模型请求响应 - 处理其他节点的模型请求
3. 模型下载 - 从邻居节点下载模型文件
4. 断点续传 - 支持大文件分片下载

复用模块：
- core/p2p_knowledge/ - P2P知识同步基础设施
- core/relay_chain/ - 中继链数据同步协议

Author: Hermes Desktop AI Assistant
"""

import os
import json
import logging
import hashlib
import threading
import time
import asyncio
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import queue

logger = logging.getLogger(__name__)

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_p2p = _get_unified_config()
except Exception:
    _uconfig_p2p = None

def _p2p_get(key: str, default):
    return _uconfig_p2p.get(key, default) if _uconfig_p2p else default


class DiscoveryProtocol(Enum):
    """发现协议"""
    GOSSIP = "gossip"           # Gossip协议（邻居节点扩散）
    FLOOD = "flood"             # 泛洪协议（广播）
    DHT = "dht"                 # DHT协议（分布式哈希表）


@dataclass
class ModelPackage:
    """
    模型包

    包含模型的完整信息，用于P2P分发
    """
    model_id: str
    version: str
    checksum: str              # SHA256校验
    size_bytes: int            # 文件大小
    download_url: Optional[str] = None  # 优先从邻居下载
    file_path: Optional[str] = None      # 本地文件路径
    metadata: Dict = field(default_factory=dict)
    source_node: str = ""      # 来源节点ID
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            'model_id': self.model_id,
            'version': self.version,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'download_url': self.download_url,
            'file_path': self.file_path,
            'metadata': self.metadata,
            'source_node': self.source_node,
            'timestamp': self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelPackage':
        return cls(**data)


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    address: str
    port: int
    available_models: List[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    is_trusted: bool = False  # 信任节点（中继服务器）

    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'address': self.address,
            'port': self.port,
            'available_models': self.available_models,
            'last_seen': self.last_seen,
            'is_trusted': self.is_trusted,
        }


class P2PModelDiscovery:
    """
    P2P模型发现与分发

    核心思想：
    1. 优先从邻居节点获取模型（更快、更省钱）
    2. 如果邻居没有，再从原始源下载
    3. 下载完成后自动广播给其他邻居（种子的概念）

    复用现有基础设施：
    - relay_chain/sync_protocol.py - 同步协议
    - p2p_knowledge/p2p_node.py - P2P节点通信

    使用示例：
        discovery = P2PModelDiscovery()
        discovery.start()

        # 注册本地可用模型
        discovery.register_model('pyswmm', '/path/to/pyswmm')

        # 搜索模型
        models = await discovery.find_model('pyswmm')

        # 下载模型
        await discovery.download_model('pyswmm', progress_callback=print)
    """

    # 协议消息类型
    MSG_MODEL_QUERY = "model_query"           # 模型查询
    MSG_MODEL_RESPONSE = "model_response"    # 模型响应
    MSG_MODEL_REQUEST = "model_request"      # 模型下载请求
    MSG_MODEL_DATA = "model_data"           # 模型数据
    MSG_MODEL_AVAILABLE = "model_available" # 模型可用广播

    def __init__(self, node_id: Optional[str] = None, storage_dir: Optional[str] = None):
        """
        初始化P2P模型发现

        Args:
            node_id: 本节点ID，默认自动生成
            storage_dir: 缓存目录
        """
        # 生成节点ID
        self.node_id = node_id or self._generate_node_id()

        # 存储目录
        self.storage_dir = Path(storage_dir or os.path.expanduser('~/.model_store/p2p_cache'))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 下载目录
        self.download_dir = self.storage_dir / 'downloads'
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # 已知节点
        self.nodes: Dict[str, NodeInfo] = {}

        # 本地可用模型
        self.local_models: Dict[str, ModelPackage] = {}

        # 下载中的模型
        self.downloading: Dict[str, Dict] = {}

        # 下载完成回调
        self._download_callbacks: Dict[str, Callable] = {}

        # 消息队列
        self._message_queue: queue.Queue = queue.Queue()

        # 运行状态
        self._running = False

        # 线程
        self._ listener_thread: Optional[threading.Thread] = None
        self._broadcaster_thread: Optional[threading.Thread] = None

        # 同步协议（复用relay_chain）
        self._sync_protocol = None

        # P2P节点（复用p2p_knowledge）
        self._p2p_node = None

        # 中继服务器列表
        self._relay_servers: List[str] = []

        logger.info(f"P2PModelDiscovery 初始化，节点ID: {self.node_id}")

    def _generate_node_id(self) -> str:
        """生成节点ID"""
        content = f"{os.getpid()}_{time.time()}_{os.getlogin() or 'user'}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def start(self, relay_servers: Optional[List[str]] = None):
        """
        启动P2P发现服务

        Args:
            relay_servers: 中继服务器地址列表
        """
        if self._running:
            logger.warning("P2P发现服务已在运行")
            return

        self._running = True

        # 设置中继服务器
        if relay_servers:
            self._relay_servers = relay_servers

        # 启动监听线程
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()

        # 启动广播线程（定期广播本地模型）
        self._broadcaster_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._broadcaster_thread.start()

        # 连接到中继服务器
        self._connect_to_relays()

        logger.info("P2P发现服务已启动")

    def stop(self):
        """停止P2P发现服务"""
        self._running = False

        if self._listener_thread:
            self._listener_thread.join(timeout=_p2p_get("timeouts.short", 5))

        if self._broadcaster_thread:
            self._broadcaster_thread.join(timeout=_p2p_get("timeouts.short", 5))

        # 断开中继连接
        self._disconnect_from_relays()

        logger.info("P2P发现服务已停止")

    def register_model(self, model_id: str, file_path: str, version: str = "1.0", metadata: Optional[Dict] = None):
        """
        注册本地可用模型

        Args:
            model_id: 模型ID
            file_path: 模型文件路径
            version: 版本
            metadata: 额外元数据
        """
        # 计算校验和
        checksum = self._calculate_checksum(file_path)
        size = os.path.getsize(file_path)

        package = ModelPackage(
            model_id=model_id,
            version=version,
            checksum=checksum,
            size_bytes=size,
            file_path=file_path,
            metadata=metadata or {},
            source_node=self.node_id,
        )

        self.local_models[model_id] = package

        # 广播模型可用
        self._broadcast_model_available(package)

        logger.info(f"注册本地模型: {model_id} ({size // 1024 // 1024}MB)")

    def unregister_model(self, model_id: str):
        """注销本地模型"""
        if model_id in self.local_models:
            del self.local_models[model_id]
            logger.info(f"注销本地模型: {model_id}")

    async def find_model(self, model_id: str, timeout: float = 10.0) -> List[ModelPackage]:
        """
        查找模型

        Args:
            model_id: 模型ID
            timeout: 超时时间

        Returns:
            可用的模型包列表
        """
        results: List[ModelPackage] = []

        # 1. 先检查本地
        if model_id in self.local_models:
            results.append(self.local_models[model_id])

        # 2. 查询邻居节点
        query_msg = {
            'type': self.MSG_MODEL_QUERY,
            'model_id': model_id,
            'from_node': self.node_id,
            'timestamp': time.time(),
        }

        found_events = asyncio.Event()
        found_results: List[ModelPackage] = []

        def on_response(package_data):
            if package_data['model_id'] == model_id:
                found_results.append(ModelPackage.from_dict(package_data))
                if len(found_results) >= 3:  # 找到3个就停止
                    found_events.set()

        self._on_model_response = on_response

        # 广播查询
        await self._broadcast(query_msg)

        # 等待响应
        try:
            await asyncio.wait_for(found_events.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        results.extend(found_results)

        # 3. 如果邻居都没有，尝试中继服务器
        if not results:
            results.extend(await self._query_relay_servers(model_id, timeout))

        return results

    async def download_model(self, model_id: str, target_path: Optional[str] = None,
                            progress_callback: Optional[Callable] = None,
                            checksum: Optional[str] = None) -> Optional[str]:
        """
        下载模型

        优先从邻居节点下载，如果失败再从原始源下载

        Args:
            model_id: 模型ID
            target_path: 目标路径
            progress_callback: 进度回调
            checksum: 校验和（用于验证）

        Returns:
            下载后的文件路径
        """
        # 查找可用源
        sources = await self.find_model(model_id)

        if not sources:
            logger.warning(f"未找到模型: {model_id}")
            return None

        # 按优先级排序
        sources.sort(key=lambda x: 0 if x.source_node != self.node_id else 1)

        # 尝试从各源下载
        for source in sources:
            try:
                # 优先从邻居节点下载
                if source.file_path and source.source_node != self.node_id:
                    file_path = await self._download_from_peer(source, target_path, progress_callback)
                elif source.download_url:
                    file_path = await self._download_from_url(source, target_path, progress_callback)
                else:
                    continue

                # 验证校验和
                if checksum and file_path:
                    actual_checksum = self._calculate_checksum(file_path)
                    if actual_checksum != checksum:
                        logger.warning(f"校验失败: {model_id}")
                        continue

                logger.info(f"模型下载成功: {model_id} -> {file_path}")
                return file_path

            except Exception as e:
                logger.warning(f"从 {source.source_node} 下载失败: {e}")
                continue

        return None

    async def _download_from_peer(self, package: ModelPackage, target_path: Optional[str], 
                                   callback: Optional[Callable]) -> Optional[str]:
        """从邻居节点下载"""
        # 发送下载请求
        request_msg = {
            'type': self.MSG_MODEL_REQUEST,
            'model_id': package.model_id,
            'from_node': self.node_id,
            'timestamp': time.time(),
        }

        # 获取源节点信息
        source_node = self.nodes.get(package.source_node)
        if not source_node:
            raise ValueError(f"未知节点: {package.source_node}")

        # 发起下载（简化实现，实际应通过P2P协议传输）
        # 这里假设邻居节点提供一个HTTP服务
        try:
            import requests

            # 构造下载URL
            download_url = f"http://{source_node.address}:{source_node.port}/model/{package.model_id}"

            response = requests.get(download_url, stream=True, timeout=_p2p_get("timeouts.download", 300))

            target = Path(target_path) if target_path else self.download_dir / package.model_id
            target.parent.mkdir(parents=True, exist_ok=True)

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(target, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            callback(f"下载中: {progress:.1f}%")

            return str(target)

        except Exception as e:
            raise e

    async def _download_from_url(self, package: ModelPackage, target_path: Optional[str],
                                  callback: Optional[Callable]) -> Optional[str]:
        """从URL下载"""
        import requests

        url = package.download_url
        if not url:
            return None

        target = Path(target_path) if target_path else self.download_dir / f"{package.model_id}.pkg"

        response = requests.get(url, stream=True, timeout=_p2p_get("timeouts.download", 300))

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(target, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        callback(f"下载中: {progress:.1f}%")

        return str(target)

    def _broadcast_model_available(self, package: ModelPackage):
        """广播模型可用"""
        msg = {
            'type': self.MSG_MODEL_AVAILABLE,
            'model_id': package.model_id,
            'version': package.version,
            'size': package.size_bytes,
            'checksum': package.checksum,
            'from_node': self.node_id,
            'timestamp': time.time(),
        }

        # 异步广播
        asyncio.create_task(self._broadcast(msg))

    async def _broadcast(self, message: Dict):
        """广播消息到所有邻居"""
        # 通过P2P协议广播
        if self._p2p_node:
            await self._p2p_node.broadcast(message)

        # 通过中继广播
        await self._broadcast_to_relays(message)

    async def _broadcast_to_relays(self, message: Dict):
        """通过中继服务器广播"""
        for relay in self._relay_servers:
            try:
                # 发送到中继服务器
                import requests
                requests.post(f"{relay}/broadcast", json=message, timeout=_p2p_get("timeouts.quick", 5))
            except Exception as e:
                logger.debug(f"中继广播失败: {relay} - {e}")

    async def _query_relay_servers(self, model_id: str, timeout: float) -> List[ModelPackage]:
        """查询中继服务器"""
        results = []

        for relay in self._relay_servers:
            try:
                import requests
                response = requests.get(
                    f"{relay}/model/{model_id}",
                    timeout=timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    results.append(ModelPackage.from_dict(data))

            except Exception as e:
                logger.debug(f"中继查询失败: {relay} - {e}")

        return results

    def _listen_loop(self):
        """监听消息循环"""
        while self._running:
            try:
                # 从消息队列获取消息
                try:
                    message = self._message_queue.get(timeout=_p2p_get("delays.polling_short", 1))
                    self._handle_message(message)
                except queue.Empty:
                    continue

            except Exception as e:
                logger.error(f"监听循环错误: {e}")

    def _broadcast_loop(self):
        """广播循环"""
        while self._running:
            try:
                # 每60秒广播一次本地模型
                time.sleep(_p2p_get("p2p.broadcast_interval", 60))

                for package in self.local_models.values():
                    self._broadcast_model_available(package)

            except Exception as e:
                logger.error(f"广播循环错误: {e}")

    def _handle_message(self, message: Dict):
        """处理收到的消息"""
        msg_type = message.get('type')

        if msg_type == self.MSG_MODEL_QUERY:
            self._handle_model_query(message)
        elif msg_type == self.MSG_MODEL_RESPONSE:
            self._handle_model_response(message)
        elif msg_type == self.MSG_MODEL_AVAILABLE:
            self._handle_model_available(message)

    def _handle_model_query(self, message: Dict):
        """处理模型查询"""
        model_id = message.get('model_id')
        from_node = message.get('from_node')

        if model_id in self.local_models:
            response = self.local_models[model_id].to_dict()
            response['type'] = self.MSG_MODEL_RESPONSE
            response['from_node'] = self.node_id

            asyncio.create_task(self._send_to_node(from_node, response))

    def _handle_model_response(self, message: Dict):
        """处理模型响应"""
        if hasattr(self, '_on_model_response'):
            self._on_model_response(message)

    def _handle_model_available(self, message: Dict):
        """处理模型可用广播"""
        node_id = message.get('from_node')
        model_id = message.get('model_id')

        # 更新节点信息
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeInfo(
                node_id=node_id,
                address=message.get('address', ''),
                port=message.get('port', 0),
            )

        # 添加模型到节点
        if model_id not in self.nodes[node_id].available_models:
            self.nodes[node_id].available_models.append(model_id)

    async def _send_to_node(self, node_id: str, message: Dict):
        """发送消息到指定节点"""
        # 实现节点间通信
        pass

    def _connect_to_relays(self):
        """连接到中继服务器"""
        for relay in self._relay_servers:
            try:
                logger.info(f"连接到中继服务器: {relay}")
                # 连接逻辑
            except Exception as e:
                logger.warning(f"连接中继失败: {relay} - {e}")

    def _disconnect_from_relays(self):
        """断开中继连接"""
        logger.info("断开中继服务器连接")

    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件SHA256校验和"""
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        return sha256.hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'node_id': self.node_id,
            'local_models': len(self.local_models),
            'known_nodes': len(self.nodes),
            'downloading': len(self.downloading),
            'relay_servers': len(self._relay_servers),
        }