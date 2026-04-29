"""
NAT穿透模块

实现UDP打洞、STUN协议和TURN中继
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional

from .models import (
    NatType, NetworkAddress, STUN_SERVERS
)

logger = logging.getLogger(__name__)


@dataclass
class NatResult:
    """NAT穿透结果"""
    success: bool
    nat_type: NatType
    public_addr: Optional[NetworkAddress] = None
    local_addr: Optional[NetworkAddress] = None
    message: str = ""


class STUNClient:
    """STUN客户端 - 用于检测NAT类型"""
    
    # STUN消息类型
    BINDING_REQUEST = b'\x00\x01'
    BINDING_RESPONSE = b'\x00\x01'
    BINDING_ERROR = b'\x00\x11'
    
    # STUN属性类型
    MAPPED_ADDRESS = b'\x00\x01'
    SOURCE_ADDRESS = b'\x00\x04'
    CHANGED_ADDRESS = b'\x00\x05'
    
    def __init__(self, stun_host: str, stun_port: int = 3478):
        self.stun_host = stun_host
        self.stun_port = stun_port
        self.timeout = 5.0
    
    async def send_binding_request(self, sock: socket.socket) -> Optional[dict]:
        """发送Binding Request并接收响应"""
        # 生成事务ID
        transaction_id = b'\x21\x12\xA4\x42\x11\x12\xA4\x42\x11\x12\xA4\x42'
        
        # 构建STUN消息头
        header = (
            self.BINDING_REQUEST +
            b'\x00\x00' +  # Message Length
            b'\x21\x12\xA4\x42' +  # Magic Cookie
            transaction_id
        )
        
        try:
            await asyncio.get_event_loop().sock_sendall(sock, header)
            sock.settimeout(self.timeout)
            data = await asyncio.get_event_loop().sock_recv(sock, 1024)
            
            if data and len(data) >= 20:
                return self._parse_response(data)
            
            return None
        except asyncio.TimeoutError:
            logger.debug(f"STUN request timeout: {self.stun_host}:{self.stun_port}")
            return None
        except Exception as e:
            logger.error(f"STUN request failed: {e}")
            return None
    
    def _parse_response(self, data: bytes) -> dict:
        """解析STUN响应"""
        result = {
            "mapped_address": None,
            "source_address": None,
            "changed_address": None
        }
        
        try:
            pos = 20
            while pos < len(data) - 4:
                attr_type = data[pos:pos+2]
                attr_len = struct.unpack('!H', data[pos+2:pos+4])[0]
                
                if attr_type == self.MAPPED_ADDRESS:
                    addr_data = data[pos+4:pos+4+attr_len]
                    if len(addr_data) >= 6:
                        family = addr_data[1]
                        port = struct.unpack('!H', addr_data[2:4])[0]
                        if family == 0x01:
                            ip = f"{addr_data[4]}.{addr_data[5]}.{addr_data[6]}.{addr_data[7]}"
                            result["mapped_address"] = (ip, port)
                
                elif attr_type == self.SOURCE_ADDRESS:
                    addr_data = data[pos+4:pos+4+attr_len]
                    if len(addr_data) >= 6:
                        family = addr_data[1]
                        port = struct.unpack('!H', addr_data[2:4])[0]
                        if family == 0x01:
                            ip = f"{addr_data[4]}.{addr_data[5]}.{addr_data[6]}.{addr_data[7]}"
                            result["source_address"] = (ip, port)
                
                elif attr_type == self.CHANGED_ADDRESS:
                    addr_data = data[pos+4:pos+4+attr_len]
                    if len(addr_data) >= 6:
                        family = addr_data[1]
                        port = struct.unpack('!H', addr_data[2:4])[0]
                        if family == 0x01:
                            ip = f"{addr_data[4]}.{addr_data[5]}.{addr_data[6]}.{addr_data[7]}"
                            result["changed_address"] = (ip, port)
                
                pos += 4 + attr_len
        
        except Exception as e:
            logger.error(f"Failed to parse STUN response: {e}")
        
        return result


class NATTraversal:
    """NAT穿透引擎"""
    
    def __init__(self, local_port: int = 0):
        self.local_port = local_port
        self.local_addr: Optional[NetworkAddress] = None
        self.public_addr: Optional[NetworkAddress] = None
        self.nat_type: NatType = NatType.UNKNOWN
    
    async def detect_nat_type(self) -> NatResult:
        """检测NAT类型"""
        logger.info("Starting NAT type detection...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        try:
            sock.bind(('0.0.0.0', self.local_port))
            self.local_addr = NetworkAddress(
                ip=self._get_local_ip(),
                port=self.local_port or sock.getsockname()[1]
            )
            
            results = []
            
            for stun_host, stun_port in STUN_SERVERS:
                try:
                    sock.connect((stun_host, stun_port))
                    client = STUNClient(stun_host, stun_port)
                    result = await client.send_binding_request(sock)
                    
                    if result and result.get("mapped_address"):
                        results.append({
                            "stun_server": f"{stun_host}:{stun_port}",
                            "mapped": result["mapped_address"],
                            "source": result.get("source_address"),
                            "changed": result.get("changed_address")
                        })
                        break
                        
                except Exception as e:
                    logger.debug(f"STUN server {stun_host} failed: {e}")
                    continue
            
            if not results:
                self.nat_type = NatType.OPEN
                self.public_addr = self.local_addr
                return NatResult(
                    success=True,
                    nat_type=NatType.OPEN,
                    public_addr=self.public_addr,
                    local_addr=self.local_addr,
                    message="No NAT detected (public IP)"
                )
            
            primary = results[0]
            mapped = primary["mapped"]
            
            if self.local_addr.ip == mapped[0]:
                if self.local_addr.port == mapped[1]:
                    self.nat_type = NatType.FULL_CONE
                else:
                    self.nat_type = NatType.SYMMETRIC
            else:
                if self.local_addr.port == mapped[1]:
                    self.nat_type = NatType.RESTRICTED_CONE
                else:
                    self.nat_type = NatType.PORT_RESTRICTED
            
            self.public_addr = NetworkAddress(
                ip=mapped[0],
                port=mapped[1],
                is_public=self.nat_type == NatType.OPEN,
                nat_type=self.nat_type
            )
            
            return NatResult(
                success=True,
                nat_type=self.nat_type,
                public_addr=self.public_addr,
                local_addr=self.local_addr,
                message=f"{self.nat_type.name} NAT detected"
            )
        
        except Exception as e:
            logger.error(f"NAT detection failed: {e}")
            return NatResult(
                success=False,
                nat_type=NatType.UNKNOWN,
                message=f"Detection failed: {e}"
            )
        finally:
            sock.close()
    
    async def punch_hole(
        self,
        target_addr: NetworkAddress,
        relay_servers: list[NetworkAddress] = None
    ) -> bool:
        """UDP打洞 - 尝试穿透NAT"""
        logger.info(f"Attempting UDP hole punching to {target_addr}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10.0)
        
        try:
            sock.bind(('0.0.0.0', 0))
            local_port = sock.getsockname()[1]
            
            async def send_packets():
                for _ in range(10):
                    try:
                        sock.sendto(b'HOLE_PUNCH', (target_addr.ip, target_addr.port))
                        logger.debug(f"Sent hole punch packet to {target_addr}")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.debug(f"Hole punch send error: {e}")
                        break
            
            async def receive_packets():
                for _ in range(20):
                    try:
                        data, addr = sock.recvfrom(1024)
                        logger.info(f"Received from {addr}: {data[:20]}")
                        return True
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.debug(f"Receive error: {e}")
                        break
                return False
            
            await asyncio.gather(send_packets(), receive_packets())
            return True
            
        except Exception as e:
            logger.error(f"Hole punching failed: {e}")
            return False
        finally:
            sock.close()
    
    async def setup_relay(
        self,
        relay_server: NetworkAddress,
        node_id: str
    ) -> bool:
        """设置中继连接"""
        logger.info(f"Setting up relay connection via {relay_server}")
        
        try:
            reader, writer = await asyncio.open_connection(
                relay_server.ip,
                relay_server.port
            )
            
            register_msg = f"REGISTER|{node_id}\n"
            writer.write(register_msg.encode())
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            
            if response.decode().strip() == "REGISTER_OK":
                logger.info(f"Relay connection established")
                return True
            
            writer.close()
            await writer.wait_closed()
            return False
            
        except Exception as e:
            logger.error(f"Relay setup failed: {e}")
            return False
    
    def _get_local_ip(self) -> str:
        """获取本地IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_connection_advice(self) -> str:
        """获取连接建议"""
        if self.nat_type == NatType.OPEN:
            return "direct"
        elif self.nat_type == NatType.FULL_CONE:
            return "direct_hole_punch"
        elif self.nat_type in (NatType.RESTRICTED_CONE, NatType.PORT_RESTRICTED):
            return "coordinated_hole_punch"
        elif self.nat_type == NatType.SYMMETRIC:
            return "relay"
        else:
            return "try_direct_then_relay"


async def detect_nat() -> NatResult:
    """便捷函数：检测NAT类型"""
    traversal = NATTraversal()
    return await traversal.detect_nat_type()


async def punch_hole(target: NetworkAddress) -> bool:
    """便捷函数：尝试UDP打洞"""
    traversal = NATTraversal()
    return await traversal.punch_hole(target, [])


class TurnClient:
    """TURN客户端 - 中继数据转发"""
    
    def __init__(self, turn_server: str, turn_port: int = 3478):
        self.turn_server = turn_server
        self.turn_port = turn_port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.allocated_addr: Optional[tuple[str, int]] = None
    
    async def allocate(self, node_id: str) -> bool:
        """请求TURN分配"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.turn_server,
                self.turn_port
            )
            
            request = f"ALLOCATE|{node_id}\n"
            self.writer.write(request.encode())
            await self.writer.drain()
            
            response = await asyncio.wait_for(self.reader.readline(), timeout=10.0)
            data = response.decode().strip().split('|')
            
            if data[0] == "ALLOCATED":
                self.allocated_addr = (data[1], int(data[2]))
                logger.info(f"TURN allocated: {self.allocated_addr}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"TURN allocation failed: {e}")
            return False
    
    async def relay_data(self, target_id: str, data: bytes) -> bool:
        """通过TURN中继数据"""
        if not self.writer:
            return False
        
        try:
            header = f"RELAY|{self.allocated_addr[0]}|{target_id}|{len(data)}\n"
            self.writer.write(header.encode() + data)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"TURN relay failed: {e}")
            return False
    
    async def close(self):
        """关闭TURN连接"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
