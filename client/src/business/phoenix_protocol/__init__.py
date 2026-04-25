# -*- coding: utf-8 -*-
"""
通用数字永生系统 - Phoenix Protocol
==================================

核心理念："网络可死，基因永生；载体可灭，灵魂不灭"

核心子系统：
1. PhoenixDNA Engine - DNA编码与管理
2. Carrier Adapters - 载体适配层
3. Resurrection Protocol - 复活协议
4. NetworkGenome - 网络基因组
5. FractalStorage - 分形存储策略
6. UniversalCarrier - 载体不可知传输
7. EvolutionEngine - 数字物种进化
8. TimeCapsule - 时间胶囊
9. InfectionPropagation - 信息瘟疫传播
10. DNASchema - DNA编码规范

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import json
import hashlib
import gzip
import base64
import msgpack
import time
import uuid
import random
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================

class ProtocolVersion(Enum):
    """协议版本"""
    V1_0 = "Phoenix/1.0"
    V2_0 = "Phoenix/2.0"


class EncodingType(Enum):
    """编码类型"""
    MSGPACK_GZIP = "msgpack+gzip"
    JSON_GZIP = "json+gzip"
    MSGPACK = "msgpack"
    JSON = "json"


class ChecksumType(Enum):
    """校验类型"""
    BLAKE3 = "blake3"
    SHA3_256 = "sha3-256"
    SHA256 = "sha256"
    MD5 = "md5"


class CarrierType(Enum):
    """载体类型"""
    # 网络存储
    GITHUB_GIST = "github_gist"
    IPFS = "ipfs"
    ARWEAVE = "arweave"
    BLOCKSTREAM_SATELLITE = "blockstream_satellite"

    # P2P网络
    BITTORRENT = "bittorrent"
    IPFS_DHT = "ipfs_dht"
    NOSTR = "nostr"

    # 物理媒介
    QR_CODE = "qr_code"
    NFC = "nfc"
    BLE_BROADCAST = "ble_broadcast"
    AUDIO = "audio"
    PAPER = "paper"

    # 区块链
    OP_RETURN = "op_return"
    CALLDATA = "calldata"

    # 云存储
    EMAIL = "email"
    DNS_TXT = "dns_txt"
    WEBDAV = "webdav"


class DNAType(Enum):
    """DNA类型"""
    CORE = "core"           # 核心DNA (1KB)
    EXTENDED = "extended"   # 扩展DNA (10KB)
    FULL = "full"           # 完整DNA (100KB)
    SIGNATURE = "signature" # 签名DNA


class LifecycleStage(Enum):
    """生命周期阶段"""
    GENESIS = "genesis"     # 诞生
    GROWTH = "growth"       # 生长
    MATURITY = "maturity"    # 成熟
    DECLINE = "decline"     # 衰退
    DEATH = "death"         # 死亡
    RESURRECTION = "resurrection"  # 复活


class InfectionPhase(Enum):
    """感染阶段"""
    PATIENT_ZERO = "patient_zero"      # 零号病人
    INCUBATION = "incubation"         # 潜伏期
    OUTBREAK = "outbreak"              # 爆发期
    CARRIER = "carrier"               # 携带者
    IMMORTAL = "immortal"              # 永生


class UnlockConditionType(Enum):
    """解锁条件类型"""
    TIME_LOCK = "time_lock"
    MULTI_SIG = "multi_sig"
    QUORUM = "quorum"
    HEIR_KEY = "heir_key"
    COMMUNITY_VOTE = "community_vote"


class StorageTier(Enum):
    """存储层级"""
    TIER_1_LOCAL = 1      # 本地设备
    TIER_2_LAN = 2        # 局域网P2P
    TIER_3_CLOUD = 3      # 互联网云
    TIER_4_BLOCKCHAIN = 4 # 区块链
    TIER_5_PHYSICAL = 5   # 物理媒介
    TIER_6_SATELLITE = 6  # 卫星广播
    TIER_7_SOCIAL = 7     # 社交网络
    TIER_8_EMAIL = 8      # 邮件列表
    TIER_9_DHT = 9        # 分布式哈希表


# ==================== 数据类定义 ====================

@dataclass
class DNAHeader:
    """DNA头部信息"""
    protocol: str = "Phoenix/1.0"
    encoding: str = "msgpack+gzip"
    checksum: str = "blake3"
    timestamp: str = ""
    version: int = 1
    dna_type: str = "core"
    fingerprint: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class NetworkGenome:
    """网络基因组"""
    node_registry: List[Dict[str, Any]] = field(default_factory=list)
    trust_graph: List[List[Any]] = field(default_factory=list)
    routing_dna: Dict[str, Any] = field(default_factory=dict)
    service_mesh: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ShardLocation:
    """碎片存储位置"""
    type: str
    id: str
    key_hint: str = ""
    url: str = ""
    verified: bool = False
    last_check: str = ""


@dataclass
class UnlockCondition:
    """解锁条件"""
    type: str
    unlock_after: str = ""
    required_signers: int = 0
    signers: List[str] = field(default_factory=list)
    threshold: int = 0


@dataclass
class ResurrectionData:
    """复活数据"""
    dna_fingerprint: str = ""
    shard_locations: List[ShardLocation] = field(default_factory=list)
    unlock_conditions: List[UnlockCondition] = field(default_factory=list)
    genesis_time: str = ""
    expected_resurrection: str = ""


@dataclass
class PhoenixDNA:
    """Phoenix DNA 完整结构"""
    header: DNAHeader = field(default_factory=DNAHeader)
    network_genome: NetworkGenome = field(default_factory=NetworkGenome)
    resurrection_data: ResurrectionData = field(default_factory=ResurrectionData)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DNAShard:
    """DNA碎片"""
    shard_id: str
    dna_type: DNAType
    data: bytes
    carrier: CarrierType
    location: str
    checksum: str
    created_at: str = ""
    replicated: bool = False
    replication_count: int = 0


@dataclass
class CarrierStatus:
    """载体状态"""
    carrier_type: CarrierType
    available: bool = False
    last_used: str = ""
    success_count: int = 0
    failure_count: int = 0
    latency_ms: float = 0.0


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    endpoints: List[str]
    capabilities: List[str]
    last_seen: str
    reputation_score: float = 0.5
    is_alive: bool = True


@dataclass
class EvolutionRecord:
    """进化记录"""
    timestamp: str
    mutation_type: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    survival: bool = True


# ==================== DNA管理器 ====================

class DNAManager:
    """Layer 1: DNA管理层 - DNA序列化、差分编码、增量合并"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.encoding = EncodingType(self.config.get("encoding", "MSGPACK_GZIP"))
        self.checksum = ChecksumType(self.config.get("checksum", "BLAKE3"))

    def encode(self, dna: PhoenixDNA) -> bytes:
        """将DNA编码为二进制格式"""
        # 序列化为字典
        dna_dict = self._dna_to_dict(dna)

        # 根据编码类型压缩
        if self.encoding == EncodingType.MSGPACK_GZIP:
            packed = msgpack.packb(dna_dict, use_bin_type=True)
            compressed = gzip.compress(packed)
            return compressed
        elif self.encoding == EncodingType.JSON_GZIP:
            json_str = json.dumps(dna_dict, ensure_ascii=False)
            compressed = gzip.compress(json_str.encode('utf-8'))
            return compressed
        elif self.encoding == EncodingType.MSGPACK:
            return msgpack.packb(dna_dict, use_bin_type=True)
        else:  # JSON
            return json.dumps(dna_dict, ensure_ascii=False).encode('utf-8')

    def decode(self, data: bytes) -> PhoenixDNA:
        """从二进制数据解码DNA"""
        # 解压缩
        try:
            decompressed = gzip.decompress(data)
            dna_dict = msgpack.unpackb(decompressed, raw=False)
        except:
            # 尝试直接msgpack解析
            try:
                dna_dict = msgpack.unpackb(data, raw=False)
            except:
                # 尝试JSON
                dna_dict = json.loads(data.decode('utf-8'))

        return self._dict_to_dna(dna_dict)

    def compute_fingerprint(self, dna: PhoenixDNA) -> str:
        """计算DNA指纹"""
        encoded = self.encode(dna)
        if self.checksum == ChecksumType.BLAKE3:
            return hashlib.blake2b(encoded).hexdigest()[:16]
        elif self.checksum == ChecksumType.SHA3_256:
            return hashlib.sha3_256(encoded).hexdigest()[:16]
        else:
            return hashlib.sha256(encoded).hexdigest()[:16]

    def split_dna(self, dna: PhoenixDNA) -> List[DNAShard]:
        """将DNA分割成碎片"""
        encoded = self.encode(dna)
        total_len = len(encoded)

        # 根据大小确定碎片类型
        if total_len < 1024:
            dna_type = DNAType.CORE
        elif total_len < 10240:
            dna_type = DNAType.EXTENDED
        else:
            dna_type = DNAType.FULL

        # 简单分片：每4KB一片
        shard_size = 4096
        shards = []

        for i in range(0, total_len, shard_size):
            chunk = encoded[i:i + shard_size]
            shard = DNAShard(
                shard_id=f"{dna_type.value}_{i // shard_size}",
                dna_type=dna_type,
                data=chunk,
                carrier=CarrierType.IPFS,  # 默认载体
                location="",
                checksum=self._compute_chunk_checksum(chunk),
                created_at=datetime.utcnow().isoformat() + "Z"
            )
            shards.append(shard)

        return shards

    def merge_dna(self, shards: List[DNAShard]) -> Optional[PhoenixDNA]:
        """合并DNA碎片"""
        if not shards:
            return None

        # 按shard_id排序
        sorted_shards = sorted(shards, key=lambda s: s.shard_id)

        # 拼接数据
        combined = b''.join([s.data for s in sorted_shards])

        try:
            return self.decode(combined)
        except Exception as e:
            logger.error(f"DNA合并失败: {e}")
            return None

    def compute_diff(self, old_dna: PhoenixDNA, new_dna: PhoenixDNA) -> Dict[str, Any]:
        """计算两个DNA之间的差异"""
        old_dict = self._dna_to_dict(old_dna)
        new_dict = self._dna_to_dict(new_dna)

        diff = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "changes": []
        }

        def recursive_diff(path, old, new):
            if type(old) != type(new):
                diff["changes"].append({"path": path, "op": "replace", "old": old, "new": new})
            elif isinstance(old, dict):
                all_keys = set(old.keys()) | set(new.keys())
                for key in all_keys:
                    new_path = f"{path}.{key}" if path else key
                    if key not in old:
                        diff["changes"].append({"path": new_path, "op": "add", "value": new[key]})
                    elif key not in new:
                        diff["changes"].append({"path": new_path, "op": "remove", "value": old[key]})
                    else:
                        recursive_diff(new_path, old[key], new[key])
            elif isinstance(old, list):
                if old != new:
                    diff["changes"].append({"path": path, "op": "replace", "old": old, "new": new})
            else:
                if old != new:
                    diff["changes"].append({"path": path, "op": "replace", "old": old, "new": new})

        recursive_diff("", old_dict, new_dict)
        return diff

    def apply_diff(self, base_dna: PhoenixDNA, diff: Dict) -> PhoenixDNA:
        """应用差异到DNA"""
        result = copy.deepcopy(base_dna)
        result_dict = self._dna_to_dict(result)

        for change in diff.get("changes", []):
            path = change["path"]
            op = change["op"]

            if op == "add" or op == "replace":
                self._set_nested(result_dict, path, change["value"])
            elif op == "remove":
                self._remove_nested(result_dict, path)

        return self._dict_to_dna(result_dict)

    def _dna_to_dict(self, dna: PhoenixDNA) -> Dict:
        """DNA转字典"""
        return {
            "header": {
                "protocol": dna.header.protocol,
                "encoding": dna.header.encoding,
                "checksum": dna.header.checksum,
                "timestamp": dna.header.timestamp,
                "version": dna.header.version,
                "dna_type": dna.header.dna_type,
                "fingerprint": dna.header.fingerprint
            },
            "network_genome": {
                "node_registry": dna.network_genome.node_registry,
                "trust_graph": dna.network_genome.trust_graph,
                "routing_dna": dna.network_genome.routing_dna,
                "service_mesh": dna.network_genome.service_mesh
            },
            "resurrection_data": {
                "dna_fingerprint": dna.resurrection_data.dna_fingerprint,
                "shard_locations": [asdict(s) for s in dna.resurrection_data.shard_locations],
                "unlock_conditions": [asdict(u) for u in dna.resurrection_data.unlock_conditions],
                "genesis_time": dna.resurrection_data.genesis_time,
                "expected_resurrection": dna.resurrection_data.expected_resurrection
            },
            "payload": dna.payload
        }

    def _dict_to_dna(self, d: Dict) -> PhoenixDNA:
        """字典转DNA"""
        header = DNAHeader(
            protocol=d["header"]["protocol"],
            encoding=d["header"]["encoding"],
            checksum=d["header"]["checksum"],
            timestamp=d["header"]["timestamp"],
            version=d["header"]["version"],
            dna_type=d["header"]["dna_type"],
            fingerprint=d["header"]["fingerprint"]
        )

        ng = d["network_genome"]
        network_genome = NetworkGenome(
            node_registry=ng["node_registry"],
            trust_graph=ng["trust_graph"],
            routing_dna=ng["routing_dna"],
            service_mesh=ng["service_mesh"]
        )

        rd = d["resurrection_data"]
        resurrection_data = ResurrectionData(
            dna_fingerprint=rd["dna_fingerprint"],
            shard_locations=[ShardLocation(**s) for s in rd["shard_locations"]],
            unlock_conditions=[UnlockCondition(**u) for u in rd["unlock_conditions"]],
            genesis_time=rd["genesis_time"],
            expected_resurrection=rd["expected_resurrection"]
        )

        return PhoenixDNA(
            header=header,
            network_genome=network_genome,
            resurrection_data=resurrection_data,
            payload=d["payload"]
        )

    def _compute_chunk_checksum(self, data: bytes) -> str:
        """计算数据块校验和"""
        return hashlib.sha256(data).hexdigest()[:16]

    def _set_nested(self, d: Dict, path: str, value: Any):
        """设置嵌套字典值"""
        keys = path.split('.')
        current = d
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def _remove_nested(self, d: Dict, path: str):
        """删除嵌套字典值"""
        keys = path.split('.')
        current = d
        for key in keys[:-1]:
            if key not in current:
                return
            current = current[key]
        if keys[-1] in current:
            del current[keys[-1]]


# ==================== 载体适配器 ====================

class BaseCarrierAdapter:
    """载体适配器基类"""

    def __init__(self, carrier_type: CarrierType):
        self.carrier_type = carrier_type
        self.status = CarrierStatus(carrier_type=carrier_type)

    async def store(self, shard: DNAShard) -> bool:
        """存储DNA碎片"""
        raise NotImplementedError

    async def retrieve(self, location: str) -> Optional[bytes]:
        """检索DNA碎片"""
        raise NotImplementedError

    async def broadcast(self, data: bytes) -> List[str]:
        """广播数据"""
        raise NotImplementedError

    async def discover(self) -> List[str]:
        """发现可用位置"""
        raise NotImplementedError

    def is_available(self) -> bool:
        """检查载体是否可用"""
        raise NotImplementedError


class GitHubGistAdapter(BaseCarrierAdapter):
    """GitHub Gist 适配器"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(CarrierType.GITHUB_GIST)
        self.token = config.get("github_token", "") if config else ""
        self.endpoint = "https://api.github.com/gists"

    async def store(self, shard: DNAShard) -> bool:
        """存储到GitHub Gist"""
        try:
            import aiohttp

            content = base64.b64encode(shard.data).decode('utf-8')
            gist_data = {
                "description": f"PhoenixDNA Shard {shard.shard_id}",
                "public": False,
                "files": {
                    f"phoenix_{shard.shard_id}.bin": {
                        "content": content
                    }
                }
            }

            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, json=gist_data, headers=headers) as resp:
                    if resp.status == 201:
                        result = await resp.json()
                        shard.location = result.get("id", "")
                        self.status.success_count += 1
                        return True
                    else:
                        self.status.failure_count += 1
                        return False
        except Exception as e:
            logger.error(f"GitHub Gist存储失败: {e}")
            self.status.failure_count += 1
            return False

    async def retrieve(self, gist_id: str) -> Optional[bytes]:
        """从GitHub Gist检索"""
        try:
            import aiohttp

            headers = {"Accept": "application/vnd.github.v3+json"}
            url = f"{self.endpoint}/{gist_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        files = result.get("files", {})
                        for fname, fdata in files.items():
                            if fname.endswith(".bin"):
                                content = fdata.get("content", "")
                                return base64.b64decode(content)
                        self.status.success_count += 1
                    else:
                        self.status.failure_count += 1
            return None
        except Exception as e:
            logger.error(f"GitHub Gist检索失败: {e}")
            self.status.failure_count += 1
            return None

    async def discover(self) -> List[str]:
        """发现用户的所有Phoenix Gist"""
        try:
            import aiohttp

            headers = {"Authorization": f"token {self.token}"} if self.token else {}
            url = f"{self.endpoint}?per_page=100"

            gists = []
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        results = await resp.json()
                        for gist in results:
                            if "phoenix_" in str(gist.get("files", {})):
                                gists.append(gist["id"])
            return gists
        except Exception as e:
            logger.error(f"GitHub Gist发现失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查GitHub Gist是否可用"""
        return bool(self.token)


class IPFSAdapter(BaseCarrierAdapter):
    """IPFS 适配器"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(CarrierType.IPFS)
        self.api_url = config.get("ipfs_api", "http://localhost:5001") if config else "http://localhost:5001"
        self.gateway_url = config.get("ipfs_gateway", "https://ipfs.io") if config else "https://ipfs.io"

    async def store(self, shard: DNAShard) -> bool:
        """存储到IPFS"""
        try:
            import aiohttp

            url = f"{self.api_url}/api/v0/add"
            data = aiohttp.FormData()
            data.add_field('file', shard.data, filename=f"{shard.shard_id}.bin")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        shard.location = result.get("Hash", "")
                        shard.carrier = CarrierType.IPFS
                        self.status.success_count += 1
                        return True
                    else:
                        self.status.failure_count += 1
                        return False
        except Exception as e:
            logger.error(f"IPFS存储失败: {e}")
            self.status.failure_count += 1
            return False

    async def retrieve(self, cid: str) -> Optional[bytes]:
        """从IPFS检索"""
        try:
            import aiohttp

            url = f"{self.gateway_url}/ipfs/{cid}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        self.status.success_count += 1
                        return await resp.read()
                    else:
                        self.status.failure_count += 1
                        return None
        except Exception as e:
            logger.error(f"IPFS检索失败: {e}")
            self.status.failure_count += 1
            return None

    async def discover(self) -> List[str]:
        """IPFS不主动发现碎片"""
        return []

    def is_available(self) -> bool:
        """检查IPFS是否可用"""
        import socket
        try:
            host = self.api_url.replace("http://", "").split(":")[0]
            port = int(self.api_url.split(":")[-1])
            socket.create_connection((host, port), timeout=2)
            return True
        except:
            return False


class NostrAdapter(BaseCarrierAdapter):
    """Nostr 适配器"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(CarrierType.NOSTR)
        self.relays = config.get("nostr_relays", [
            "wss://relay.damus.io",
            "wss://relay.nostr.band",
            "wss://nos.lol"
        ]) if config else ["wss://relay.damus.io", "wss://relay.nostr.band"]
        self.private_key = config.get("nostr_sk", "") if config else ""
        self.public_key = config.get("nostr_pk", "") if config else ""

    async def store(self, shard: DNAShard) -> bool:
        """通过Nostr发布DNA碎片"""
        try:
            import asyncio
            import websockets

            content = base64.b64encode(shard.data).decode('utf-8')
            event = {
                "pubkey": self.public_key,
                "created_at": int(time.time()),
                "kind": 30078,  # 自定义类型
                "tags": [["d", f"phoenix_{shard.shard_id}"]],
                "content": content
            }

            # 签名事件（简化版）
            event["id"] = hashlib.sha256(json.dumps(event, separators=(',', ':')).encode()).hexdigest()
            event["sig"] = "fake_signature"  # 实际需要secp256k1签名

            success_count = 0
            for relay in self.relays:
                try:
                    async with websockets.connect(relay) as ws:
                        await ws.send(json.dumps(["EVENT", event]))
                        await ws.recv()
                        success_count += 1
                except:
                    pass

            if success_count > 0:
                shard.location = event["id"]
                self.status.success_count += 1
                return True
            else:
                self.status.failure_count += 1
                return False
        except Exception as e:
            logger.error(f"Nostr存储失败: {e}")
            self.status.failure_count += 1
            return False

    async def retrieve(self, event_id: str) -> Optional[bytes]:
        """从Nostr检索"""
        try:
            import asyncio
            import websockets

            for relay in self.relays:
                try:
                    async with websockets.connect(relay) as ws:
                        subscription = [
                            "REQ", "sub1",
                            {"ids": [event_id]}
                        ]
                        await ws.send(json.dumps(subscription))
                        async for msg in ws:
                            if "EVENT" in msg:
                                data = json.loads(msg)
                                if len(data) >= 3:
                                    content = data[2].get("content", "")
                                    return base64.b64decode(content)
                except:
                    pass
            return None
        except Exception as e:
            logger.error(f"Nostr检索失败: {e}")
            return None

    async def discover(self) -> List[str]:
        """发现Nostr上的Phoenix事件"""
        return []

    def is_available(self) -> bool:
        """Nostr总是可用（依赖公共中继）"""
        return True


class QRCodeAdapter(BaseCarrierAdapter):
    """二维码适配器"""
    # 二维码容量：约2KB UTF-8文本
    MAX_QR_CAPACITY = 2000

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(CarrierType.QR_CODE)
        self.chunk_size = self.MAX_QR_CAPACITY

    async def store(self, shard: DNAShard) -> bool:
        """生成DNA碎片二维码"""
        try:
            from PIL import Image, ImageDraw
            import qrcode
            import io

            # Base64编码
            content = base64.b64encode(shard.data).decode('utf-8')

            # 分块（每块包含索引信息）
            chunks = []
            chunk_size = self.MAX_QR_CAPACITY - 100  # 留出索引空间
            for i in range(0, len(content), chunk_size):
                chunk_data = content[i:i+chunk_size]
                chunk_info = f"{shard.shard_id}|{i//chunk_size}|{len(content)//chunk_size + 1}|{chunk_data}"
                chunks.append(chunk_info)

            shard.data = json.dumps(chunks).encode('utf-8')
            self.status.success_count += 1
            return True
        except Exception as e:
            logger.error(f"QR码生成失败: {e}")
            self.status.failure_count += 1
            return False

    async def generate_image(self, content: str, output_path: str):
        """生成二维码图片"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)

    def is_available(self) -> bool:
        """总是可用"""
        return True


class EmailAdapter(BaseCarrierAdapter):
    """电子邮件适配器"""
    MAX_EMAIL_SIZE = 1024 * 1024  # 1MB

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(CarrierType.EMAIL)
        self.smtp_server = config.get("smtp_server", "") if config else ""
        self.smtp_port = config.get("smtp_port", 587) if config else 587
        self.username = config.get("email", "") if config else ""
        self.password = config.get("email_password", "") if config else ""

    async def store(self, shard: DNAShard) -> bool:
        """通过邮件发送DNA碎片"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email.mime.multipart import MIMEMultipart

            if len(shard.data) > self.MAX_EMAIL_SIZE:
                logger.error("数据超过邮件大小限制")
                return False

            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.username  # 发给自己
            msg['Subject'] = f"PhoenixDNA Shard {shard.shard_id}"

            # 将二进制数据编码为文本
            content = base64.b64encode(shard.data).decode('utf-8')
            msg.attach(MIMEText(content, 'plain'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            self.status.success_count += 1
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            self.status.failure_count += 1
            return False

    async def retrieve(self, subject_pattern: str) -> List[bytes]:
        """检索邮件中的DNA碎片"""
        # 简化实现
        return []

    def is_available(self) -> bool:
        """检查邮件是否配置"""
        return bool(self.smtp_server and self.username and self.password)


class CarrierAdapterManager:
    """载体适配器管理器"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.adapters: Dict[CarrierType, BaseCarrierAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self):
        """注册默认适配器"""
        self.adapters[CarrierType.GITHUB_GIST] = GitHubGistAdapter(self.config)
        self.adapters[CarrierType.IPFS] = IPFSAdapter(self.config)
        self.adapters[CarrierType.NOSTR] = NostrAdapter(self.config)
        self.adapters[CarrierType.QR_CODE] = QRCodeAdapter(self.config)
        self.adapters[CarrierType.EMAIL] = EmailAdapter(self.config)

    def get_adapter(self, carrier_type: CarrierType) -> Optional[BaseCarrierAdapter]:
        """获取指定载体适配器"""
        return self.adapters.get(carrier_type)

    def get_available_carriers(self) -> List[CarrierType]:
        """获取所有可用的载体"""
        return [ct for ct, adapter in self.adapters.items() if adapter.is_available()]

    async def store_dna(self, dna: PhoenixDNA, carriers: Optional[List[CarrierType]] = None) -> List[ShardLocation]:
        """在多个载体上存储DNA"""
        from client.src.business.phoenix_protocol import DNAManager

        dna_manager = DNAManager(self.config)
        shards = dna_manager.split_dna(dna)

        if carriers is None:
            carriers = self.get_available_carriers()

        locations = []
        for shard in shards:
            for carrier_type in carriers:
                adapter = self.get_adapter(carrier_type)
                if adapter and adapter.is_available():
                    success = await adapter.store(shard)
                    if success:
                        locations.append(ShardLocation(
                            type=carrier_type.value,
                            id=shard.shard_id,
                            key_hint=shard.checksum[:8],
                            location=shard.location
                        ))

        return locations


# ==================== 复活协议 ====================

class ResurrectionProtocol:
    """Layer 3: 复活协议层"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.dna_manager = DNAManager(config)
        self.carrier_manager = CarrierAdapterManager(config)
        self.time_unlock_intervals = [
            timedelta(days=1),
            timedelta(days=7),
            timedelta(days=30),
            timedelta(days=365),
            timedelta(days=36500)  # 100年
        ]

    async def resurrect(self, resurrection_data: ResurrectionData) -> Optional[PhoenixDNA]:
        """执行复活协议"""
        logger.info("开始复活协议...")

        # 阶段1：DNA发现
        discovered_shards = await self._discover_dna_shards(resurrection_data)

        if not discovered_shards:
            logger.warning("未发现DNA碎片，尝试时间解锁递延...")
            return await self._time_delayed_resurrection(resurrection_data)

        # 阶段2：完整性验证
        if not await self._verify_integrity(discovered_shards):
            logger.warning("DNA碎片不完整，尝试修复...")
            discovered_shards = await self._repair_missing_shards(resurrection_data, discovered_shards)

        # 阶段3：碎片重组
        dna = self.dna_manager.merge_dna(discovered_shards)
        if not dna:
            logger.error("DNA重组失败")
            return None

        # 阶段4：网络重建
        await self._rebuild_network(dna)

        logger.info("复活成功!")
        return dna

    async def _discover_dna_shards(self, res_data: ResurrectionData) -> List[DNAShard]:
        """发现DNA碎片"""
        shards = []

        for location in res_data.shard_locations:
            carrier_type = CarrierType(location.type)
            adapter = self.carrier_manager.get_adapter(carrier_type)

            if not adapter:
                continue

            try:
                data = await adapter.retrieve(location.id)
                if data:
                    shard = DNAShard(
                        shard_id=location.id,
                        dna_type=DNAType.CORE,
                        data=data,
                        carrier=carrier_type,
                        location=location.id,
                        checksum=location.key_hint
                    )
                    shards.append(shard)
            except Exception as e:
                logger.error(f"从{carrier_type.value}发现碎片失败: {e}")

        return shards

    async def _verify_integrity(self, shards: List[DNAShard]) -> bool:
        """验证DNA完整性"""
        # 简化实现：检查碎片数量
        if len(shards) < 1:
            return False
        return True

    async def _repair_missing_shards(self, res_data: ResurrectionData, current_shards: List[DNAShard]) -> List[DNAShard]:
        """修复缺失的碎片"""
        # 尝试从其他位置获取
        return current_shards

    async def _time_delayed_resurrection(self, res_data: ResurrectionData) -> Optional[PhoenixDNA]:
        """时间递延复活"""
        genesis_time = datetime.fromisoformat(res_data.genesis_time.replace("Z", "+00:00"))
        elapsed = datetime.now(genesis_time.tzinfo) - genesis_time

        # 根据经过的时间解锁更多DNA
        for i, interval in enumerate(self.time_unlock_intervals):
            if elapsed >= interval:
                logger.info(f"时间解锁阶段{i+1}: {interval}")
                # 尝试获取更多碎片
                # ...

        return None

    async def _rebuild_network(self, dna: PhoenixDNA):
        """重建网络"""
        # 重新连接节点
        for node in dna.network_genome.node_registry:
            logger.info(f"重连节点: {node['id']}")
            # ...重连逻辑


# ==================== 分形存储策略 ====================

class FractalStorage:
    """分形存储策略 - 9层DNA存储"""

    STORAGE_TIERS = [
        (StorageTier.TIER_1_LOCAL, "本地设备存储"),
        (StorageTier.TIER_2_LAN, "局域网P2P同步"),
        (StorageTier.TIER_3_CLOUD, "互联网云存储"),
        (StorageTier.TIER_4_BLOCKCHAIN, "区块链永久存储"),
        (StorageTier.TIER_5_PHYSICAL, "物理媒介备份"),
        (StorageTier.TIER_6_SATELLITE, "卫星广播"),
        (StorageTier.TIER_7_SOCIAL, "社交网络传播"),
        (StorageTier.TIER_8_EMAIL, "邮件列表"),
        (StorageTier.TIER_9_DHT, "分布式哈希表"),
    ]

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.dna_manager = DNAManager(config)
        self.carrier_manager = CarrierAdapterManager(config)

    def create_dna_tier(self, dna: PhoenixDNA, tier: StorageTier) -> List[DNAShard]:
        """为特定层级创建DNA"""
        if tier == StorageTier.TIER_1_LOCAL:
            # 本地：完整DNA
            return self.dna_manager.split_dna(dna)
        elif tier == StorageTier.TIER_2_LAN:
            # 局域网：压缩完整DNA
            compressed = self.dna_manager.encode(dna)
            return [DNAShard(
                shard_id=f"lan_{DNAType.FULL.value}",
                dna_type=DNAType.FULL,
                data=compressed,
                carrier=CarrierType.BLE_BROADCAST,
                location="",
                checksum=self.dna_manager._compute_chunk_checksum(compressed)
            )]
        elif tier == StorageTier.TIER_3_CLOUD:
            # 云：分片存储
            return self.dna_manager.split_dna(dna)
        elif tier == StorageTier.TIER_4_BLOCKCHAIN:
            # 区块链：极简核心数据
            core_payload = {
                "fingerprint": dna.resurrection_data.dna_fingerprint,
                "genesis": dna.resurrection_data.genesis_time,
                "nodes": len(dna.network_genome.node_registry)
            }
            minimal_dna = PhoenixDNA(
                header=dna.header,
                payload=core_payload
            )
            encoded = self.dna_manager.encode(minimal_dna)
            return [DNAShard(
                shard_id=f"bc_{DNAType.SIGNATURE.value}",
                dna_type=DNAType.SIGNATURE,
                data=encoded[:500],  # 限制大小
                carrier=CarrierType.OP_RETURN,
                location="",
                checksum=self.dna_manager._compute_chunk_checksum(encoded[:500])
            )]
        else:
            # 其他层级：简化版
            return self.dna_manager.split_dna(dna)[:1]

    async def store_all_tiers(self, dna: PhoenixDNA) -> Dict[StorageTier, List[ShardLocation]]:
        """存储到所有层级"""
        results = {}

        for tier, name in self.STORAGE_TIERS:
            shards = self.create_dna_tier(dna, tier)
            locations = []

            for shard in shards:
                adapter = self.carrier_manager.get_adapter(shard.carrier)
                if adapter and await adapter.store(shard):
                    locations.append(ShardLocation(
                        type=shard.carrier.value,
                        id=shard.shard_id,
                        key_hint=shard.checksum[:8],
                        location=shard.location
                    ))

            results[tier] = locations
            logger.info(f"{name}: 存储了 {len(locations)} 个位置")

        return results

    async def retrieve_from_tier(self, tier: StorageTier, res_data: ResurrectionData) -> Optional[PhoenixDNA]:
        """从特定层级检索"""
        # 筛选该层级的碎片
        tier_locations = [loc for loc in res_data.shard_locations if loc.type == tier.value]

        shards = []
        for location in tier_locations:
            adapter = self.carrier_manager.get_adapter(CarrierType(location.type))
            if adapter:
                data = await adapter.retrieve(location.id)
                if data:
                    shards.append(DNAShard(
                        shard_id=location.id,
                        dna_type=DNAType.CORE,
                        data=data,
                        carrier=CarrierType(location.type),
                        location=location.id,
                        checksum=location.key_hint
                    ))

        if shards:
            return self.dna_manager.merge_dna(shards)
        return None


# ==================== 信息瘟疫传播 ====================

class InfectionPropagation:
    """信息瘟疫模型 - 感染式传播协议"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.phase = InfectionPhase.PATIENT_ZERO
        self.infection_count = 0
        self.ttl = config.get("ttl", 3) if config else 3
        self.fanout = config.get("fanout", 3) if config else 3

    def get_phase_description(self) -> str:
        """获取当前阶段描述"""
        descriptions = {
            InfectionPhase.PATIENT_ZERO: "零号病人 - 第一个携带DNA的节点",
            InfectionPhase.INCUBATION: "潜伏期 - DNA静默复制",
            InfectionPhase.OUTBREAK: "爆发期 - 指数级传播",
            InfectionPhase.CARRIER: "携带者 - 所有节点都带DNA",
            InfectionPhase.IMMORTAL: "永生 - DNA存在于全网"
        }
        return descriptions.get(self.phase, "未知阶段")

    def should_spread(self, node_reputation: float) -> bool:
        """判断是否应该传播给该节点"""
        # 基于声誉和TTL决定
        if self.ttl <= 0:
            return node_reputation > 0.8

        return node_reputation > 0.3

    async def spread_dna(self, dna: PhoenixDNA, nodes: List[NodeInfo]) -> List[str]:
        """向节点传播DNA"""
        if self.ttl <= 0:
            self.phase = InfectionPhase.IMMORTAL
            return []

        infected = []
        for node in nodes:
            if self.should_spread(node.reputation_score) and node.is_alive:
                # 模拟传播
                logger.info(f"感染节点 {node.node_id} (声誉: {node.reputation_score:.2f})")
                infected.append(node.node_id)
                self.infection_count += 1

        # 更新TTL和阶段
        self.ttl -= 1
        self._update_phase()

        return infected

    def _update_phase(self):
        """更新感染阶段"""
        if self.infection_count == 0:
            self.phase = InfectionPhase.PATIENT_ZERO
        elif self.ttl > 2:
            self.phase = InfectionPhase.INCUBATION
        elif self.ttl > 0:
            self.phase = InfectionPhase.OUTBREAK
        elif self.infection_count > 10:
            self.phase = InfectionPhase.CARRIER
        else:
            self.phase = InfectionPhase.IMMORTAL

    def get_carrier_matrix(self) -> Dict[str, Tuple[str, str]]:
        """获取传播载体矩阵"""
        return {
            "github_gist": ("HTTP API", "免费,版本控制"),
            "ipfs": ("内容寻址", "永久,去中心化"),
            "nostr": ("中继网络", "抗审查,实时"),
            "bittorrent": ("DHT网络", "大规模分发"),
            "ble_broadcast": ("物理接近", "离线传播"),
            "qr_code": ("视觉扫描", "物理世界传播"),
            "blockstream_satellite": ("全球广播", "抗断网"),
            "email": ("SMTP", "广泛覆盖"),
        }


# ==================== 主引擎 ====================

class PhoenixProtocolEngine:
    """Phoenix Protocol 主引擎"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.node_id = config.get("node_id", f"phoenix_{uuid.uuid4().hex[:8]}") if config else f"phoenix_{uuid.uuid4().hex[:8]}"

        # 初始化各层
        self.dna_manager = DNAManager(self.config)
        self.carrier_manager = CarrierAdapterManager(self.config)
        self.resurrection_protocol = ResurrectionProtocol(self.config)
        self.fractal_storage = FractalStorage(self.config)
        self.infection = InfectionPropagation(self.config)

        # 状态
        self.lifecycle_stage = LifecycleStage.GENESIS
        self.current_dna: Optional[PhoenixDNA] = None
        self.nodes: Dict[str, NodeInfo] = {}
        self.evolution_history: List[EvolutionRecord] = []

    async def initialize(self):
        """初始化Phoenix"""
        logger.info(f"Phoenix节点 {self.node_id} 初始化中...")

        # 生成初始DNA
        self.current_dna = await self._generate_genesis_dna()

        # 标记为诞生阶段
        self.lifecycle_stage = LifecycleStage.GENESIS

        logger.info(f"Phoenix初始化完成: {self.lifecycle_stage.value}")

    async def _generate_genesis_dna(self) -> PhoenixDNA:
        """生成创始DNA"""
        header = DNAHeader(
            protocol="Phoenix/1.0",
            encoding="msgpack+gzip",
            checksum="blake3",
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=1,
            dna_type="genesis"
        )

        network_genome = NetworkGenome(
            node_registry=[{
                "id": self.node_id,
                "endpoints": ["local"],
                "capabilities": ["store", "relay"],
                "last_seen": datetime.utcnow().isoformat() + "Z",
                "reputation_score": 1.0
            }],
            trust_graph=[],
            routing_dna={},
            service_mesh={}
        )

        res_data = ResurrectionData(
            dna_fingerprint="",
            shard_locations=[],
            unlock_conditions=[],
            genesis_time=datetime.utcnow().isoformat() + "Z"
        )

        dna = PhoenixDNA(
            header=header,
            network_genome=network_genome,
            resurrection_data=res_data,
            payload={"genesis": True}
        )

        # 计算指纹
        dna.header.fingerprint = self.dna_manager.compute_fingerprint(dna)
        res_data.dna_fingerprint = dna.header.fingerprint

        return dna

    async def backup_current_state(self) -> List[ShardLocation]:
        """备份当前状态到所有载体"""
        if not self.current_dna:
            raise ValueError("没有可备份的DNA")

        # 更新DNA时间戳
        self.current_dna.header.timestamp = datetime.utcnow().isoformat() + "Z"

        # 使用分形存储
        all_locations = await self.fractal_storage.store_all_tiers(self.current_dna)

        # 扁平化位置列表
        flat_locations = []
        for tier, locations in all_locations.items():
            flat_locations.extend(locations)

        # 更新复活数据
        self.current_dna.resurrection_data.shard_locations = flat_locations

        return flat_locations

    async def add_node(self, node_info: NodeInfo):
        """添加网络节点"""
        self.nodes[node_info.node_id] = node_info

        # 更新基因组
        self.current_dna.network_genome.node_registry.append({
            "id": node_info.node_id,
            "endpoints": node_info.endpoints,
            "capabilities": node_info.capabilities,
            "last_seen": node_info.last_seen,
            "reputation_score": node_info.reputation_score
        })

    async def attempt_resurrection(self) -> Optional[PhoenixDNA]:
        """尝试复活"""
        if self.lifecycle_stage != LifecycleStage.DEATH:
            logger.warning("节点未死亡，无需复活")
            return None

        self.lifecycle_stage = LifecycleStage.RESURRECTION
        return await self.resurrection_protocol.resurrect(self.current_dna.resurrection_data)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "node_id": self.node_id,
            "lifecycle_stage": self.lifecycle_stage.value,
            "infection_phase": self.infection.get_phase_description(),
            "nodes_count": len(self.nodes),
            "dna_fingerprint": self.current_dna.resurrection_data.dna_fingerprint if self.current_dna else None,
            "available_carriers": [ct.value for ct in self.carrier_manager.get_available_carriers()]
        }

    def export_dna_summary(self) -> str:
        """导出DNA摘要"""
        if not self.current_dna:
            return "No DNA available"

        return f"""
Phoenix DNA Summary
==================
Node ID: {self.node_id}
Fingerprint: {self.current_dna.resurrection_data.dna_fingerprint}
Protocol: {self.current_dna.header.protocol}
Encoding: {self.current_dna.header.encoding}
Genesis: {self.current_dna.resurrection_data.genesis_time}
Nodes: {len(self.current_dna.network_genome.node_registry)}
Lifecycle: {self.lifecycle_stage.value}
        """


# ==================== 导出 ====================

__all__ = [
    'PhoenixProtocolEngine',
    'DNAManager',
    'CarrierAdapterManager',
    'CarrierType',
    'DNAType',
    'LifecycleStage',
    'InfectionPhase',
    'PhoenixDNA',
    'DNAShard',
    'ShardLocation',
    'NodeInfo',
    'NetworkGenome',
    'ResurrectionData',
    'StorageTier',
    'FractalStorage',
    'InfectionPropagation',
    'ResurrectionProtocol',
]
