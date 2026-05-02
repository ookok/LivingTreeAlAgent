"""
跨框架互操作适配器
==================
支持与外部 Agent 框架通信，实现互操作性。

支持的框架：
1. A2A Protocol - 现有 LivingTree A2A
2. ModelScope-Agent - 魔搭 Agent 协议
3. LangChain Agent Protocol - LangChain 标准协议
4. MCP (Model Context Protocol) - Claude MCP
5. 自定义协议 - 支持扩展

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type
from collections import defaultdict
import threading

# ==================== 协议定义 ====================

class ProtocolType(Enum):
    """支持的协议类型"""
    A2A = "a2a"                          # LivingTree A2A
    MODELSCOPE_AGENT = "modelscope"       # 魔搭 Agent
    LANGCHAIN = "langchain"              # LangChain Agent Protocol
    MCP = "mcp"                          # Model Context Protocol
    CUSTOM = "custom"                    # 自定义协议


@dataclass
class InteropMessage:
    """跨框架通用消息格式"""
    message_id: str
    protocol: ProtocolType
    message_type: str                    # request, response, notification, stream
    action: str                          # 具体动作
    sender: str                          # 发送方 ID
    receiver: Optional[str] = None       # 接收方 ID（可选，支持广播）
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    @classmethod
    def create(cls, protocol: ProtocolType, action: str,
               sender: str, payload: Dict = None, receiver: str = None):
        """创建消息"""
        return cls(
            message_id=str(uuid.uuid4()),
            protocol=protocol,
            message_type="request",
            action=action,
            sender=sender,
            receiver=receiver,
            payload=payload or {},
        )
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "protocol": self.protocol.value,
            "type": self.message_type,
            "action": self.action,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# ==================== 协议适配器基类 ====================

class ProtocolAdapter(ABC):
    """
    协议适配器抽象基类
    ==================
    所有框架适配器需要实现此接口
    """
    
    protocol_type: ProtocolType = ProtocolType.CUSTOM
    
    @abstractmethod
    def encode(self, message: InteropMessage) -> Any:
        """将通用消息编码为目标框架格式"""
        pass
    
    @abstractmethod
    def decode(self, raw_message: Any) -> Optional[InteropMessage]:
        """将目标框架消息解码为通用格式"""
        pass
    
    @abstractmethod
    def encode_response(self, request: InteropMessage, 
                        result: Any) -> Any:
        """编码响应消息"""
        pass
    
    @abstractmethod
    def get_action_mapping(self) -> Dict[str, str]:
        """获取动作名称映射"""
        pass


# ==================== A2A 适配器 ====================

class A2AAdapter(ProtocolAdapter):
    """
    LivingTree A2A 协议适配器
    ==================
    与现有 A2A 协议无缝集成
    """
    
    protocol_type = ProtocolType.A2A
    
    ACTION_MAP = {
        # 外部动作 -> A2A 动作
        "execute_task": "task/execute",
        "query_capability": "capability/query",
        "register": "agent/register",
        "heartbeat": "agent/heartbeat",
        "discover": "agent/discover",
    }
    
    REVERSE_ACTION_MAP = {v: k for k, v in ACTION_MAP.items()}
    
    def encode(self, message: InteropMessage) -> Dict:
        """编码为 A2A 格式"""
        return {
            "jsonrpc": "2.0",
            "method": self.REVERSE_ACTION_MAP.get(message.action, message.action),
            "params": {
                "sender": message.sender,
                "receiver": message.receiver,
                "data": message.payload,
            },
            "id": message.message_id,
        }
    
    def decode(self, raw_message: Any) -> Optional[InteropMessage]:
        """解码 A2A 消息"""
        try:
            if isinstance(raw_message, dict):
                if raw_message.get("jsonrpc") != "2.0":
                    return None
                
                method = raw_message.get("method", "")
                params = raw_message.get("params", {})
                
                return InteropMessage(
                    message_id=str(raw_message.get("id", "")),
                    protocol=self.protocol_type,
                    message_type="request" if "params" in raw_message else "response",
                    action=self.ACTION_MAP.get(method, method),
                    sender=params.get("sender", ""),
                    receiver=params.get("receiver"),
                    payload=params.get("data", {}),
                    timestamp=time.time(),
                )
        except Exception as e:
            print(f"[A2AAdapter] Decode error: {e}")
        return None
    
    def encode_response(self, request: InteropMessage, result: Any) -> Dict:
        """编码 A2A 响应"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "data": result,
                "original_action": request.action,
            },
            "id": request.message_id,
        }
    
    def get_action_mapping(self) -> Dict[str, str]:
        return self.ACTION_MAP.copy()


# ==================== ModelScope Agent 适配器 ====================

class ModelScopeAgentAdapter(ProtocolAdapter):
    """
    魔搭 ModelScope-Agent 协议适配器
    ==================
    支持阿里魔搭平台的 Agent 通信协议
    """
    
    protocol_type = ProtocolType.MODELSCOPE_AGENT
    
    ACTION_MAP = {
        "execute_task": "invoke",
        "query_capability": "capabilities",
        "register": "register_agent",
        "heartbeat": "ping",
        "discover": "list_agents",
    }
    
    def encode(self, message: InteropMessage) -> Dict:
        """编码为 ModelScope 格式"""
        action = self.ACTION_MAP.get(message.action, message.action)
        
        return {
            "action": action,
            "agent_id": message.sender,
            "target_id": message.receiver,
            "parameters": message.payload,
            "request_id": message.message_id,
            "timestamp": message.timestamp,
        }
    
    def decode(self, raw_message: Any) -> Optional[InteropMessage]:
        """解码 ModelScope 消息"""
        try:
            if isinstance(raw_message, dict):
                action = raw_message.get("action", "")
                reverse_map = {v: k for k, v in self.ACTION_MAP.items()}
                
                return InteropMessage(
                    message_id=str(raw_message.get("request_id", "")),
                    protocol=self.protocol_type,
                    message_type="response" if "result" in raw_message else "request",
                    action=reverse_map.get(action, action),
                    sender=raw_message.get("agent_id", ""),
                    receiver=raw_message.get("target_id"),
                    payload=raw_message.get("parameters") or raw_message.get("result", {}),
                    timestamp=raw_message.get("timestamp", time.time()),
                )
        except Exception as e:
            print(f"[ModelScopeAdapter] Decode error: {e}")
        return None
    
    def encode_response(self, request: InteropMessage, result: Any) -> Dict:
        """编码 ModelScope 响应"""
        return {
            "action": "result",
            "request_id": request.message_id,
            "result": result,
            "success": True,
            "timestamp": time.time(),
        }
    
    def get_action_mapping(self) -> Dict[str, str]:
        return self.ACTION_MAP.copy()


# ==================== LangChain 适配器 ====================

class LangChainAdapter(ProtocolAdapter):
    """
    LangChain Agent Protocol 适配器
    ==================
    支持 LangChain 的标准化 Agent 通信协议
    """
    
    protocol_type = ProtocolType.LANGCHAIN
    
    # LangChain 使用 OpenAI 风格的 tool_calls 格式
    ACTION_MAP = {
        "execute_task": "tool_use",
        "query_capability": "tool_choice",
        "register": "session/start",
        "heartbeat": "session/heartbeat",
        "discover": "session/list",
    }
    
    def encode(self, message: InteropMessage) -> Dict:
        """编码为 LangChain 格式"""
        action = self.ACTION_MAP.get(message.action, message.action)
        
        # LangChain 使用特定的 tool_calls 格式
        tool_calls = [{
            "name": message.action,
            "arguments": json.dumps(message.payload),
        }]
        
        return {
            "type": action,
            "session_id": message.sender,
            "tool_calls": tool_calls,
            "metadata": message.metadata,
            "id": message.message_id,
        }
    
    def decode(self, raw_message: Any) -> Optional[InteropMessage]:
        """解码 LangChain 消息"""
        try:
            if isinstance(raw_message, dict):
                msg_type = raw_message.get("type", "")
                reverse_map = {v: k for k, v in self.ACTION_MAP.items()}
                
                tool_calls = raw_message.get("tool_calls", [])
                payload = {}
                
                if tool_calls and len(tool_calls) > 0:
                    tool = tool_calls[0]
                    payload = json.loads(tool.get("arguments", "{}"))
                    action = tool.get("name", "")
                else:
                    payload = raw_message.get("content", {})
                    action = reverse_map.get(msg_type, msg_type)
                
                return InteropMessage(
                    message_id=str(raw_message.get("id", "")),
                    protocol=self.protocol_type,
                    message_type="response" if raw_message.get("content") else "request",
                    action=action,
                    sender=raw_message.get("session_id", ""),
                    receiver=raw_message.get("target_session"),
                    payload=payload,
                    metadata=raw_message.get("metadata", {}),
                    timestamp=time.time(),
                )
        except Exception as e:
            print(f"[LangChainAdapter] Decode error: {e}")
        return None
    
    def encode_response(self, request: InteropMessage, result: Any) -> Dict:
        """编码 LangChain 响应"""
        return {
            "type": "tool_result",
            "id": request.message_id,
            "content": json.dumps(result),
            "status": "success",
        }
    
    def get_action_mapping(self) -> Dict[str, str]:
        return self.ACTION_MAP.copy()


# ==================== MCP 适配器 ====================

class MCPAdapter(ProtocolAdapter):
    """
    Model Context Protocol (MCP) 适配器
    ==================
    支持 Anthropic Claude 的 MCP 协议
    """
    
    protocol_type = ProtocolType.MCP
    
    ACTION_MAP = {
        "execute_task": "tools/call",
        "query_capability": "tools/list",
        "register": "resources/subscribe",
        "heartbeat": "ping",
        "discover": "resources/list",
    }
    
    def encode(self, message: InteropMessage) -> Dict:
        """编码为 MCP 格式"""
        action = self.ACTION_MAP.get(message.action, message.action)
        
        # MCP JSON-RPC 风格
        return {
            "jsonrpc": "2.0",
            "method": action,
            "params": {
                "name": message.action,
                "arguments": message.payload,
            },
            "id": message.message_id,
        }
    
    def decode(self, raw_message: Any) -> Optional[InteropMessage]:
        """解码 MCP 消息"""
        try:
            if isinstance(raw_message, dict):
                if raw_message.get("jsonrpc") != "2.0":
                    return None
                
                method = raw_message.get("method", "")
                params = raw_message.get("params", {})
                reverse_map = {v: k for k, v in self.ACTION_MAP.items()}
                
                return InteropMessage(
                    message_id=str(raw_message.get("id", "")),
                    protocol=self.protocol_type,
                    message_type="response" if "result" in raw_message else "request",
                    action=reverse_map.get(method, method),
                    sender=params.get("session_id", "unknown"),
                    receiver=params.get("target"),
                    payload=params.get("arguments", {}),
                    metadata=raw_message.get("metadata", {}),
                    timestamp=time.time(),
                )
        except Exception as e:
            print(f"[MCPAdapter] Decode error: {e}")
        return None
    
    def encode_response(self, request: InteropMessage, result: Any) -> Dict:
        """编码 MCP 响应"""
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request.message_id,
        }
    
    def get_action_mapping(self) -> Dict[str, str]:
        return self.ACTION_MAP.copy()


# ==================== 协议转换器 ====================

class ProtocolConverter:
    """
    协议转换器
    ==================
    在不同协议之间转换消息
    """
    
    def __init__(self):
        self._adapters: Dict[ProtocolType, ProtocolAdapter] = {}
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """注册默认适配器"""
        self.register(A2AAdapter())
        self.register(ModelScopeAgentAdapter())
        self.register(LangChainAdapter())
        self.register(MCPAdapter())
    
    def register(self, adapter: ProtocolAdapter):
        """注册适配器"""
        self._adapters[adapter.protocol_type] = adapter
    
    def get_adapter(self, protocol: ProtocolType) -> Optional[ProtocolAdapter]:
        """获取指定协议的适配器"""
        return self._adapters.get(protocol)
    
    def convert(self, message: InteropMessage, 
                target_protocol: ProtocolType) -> Optional[Any]:
        """
        转换消息到目标协议
        
        参数：
            message: 源消息
            target_protocol: 目标协议类型
        
        返回：编码后的目标协议消息
        """
        adapter = self._adapters.get(target_protocol)
        if not adapter:
            print(f"[ProtocolConverter] No adapter for {target_protocol}")
            return None
        
        return adapter.encode(message)
    
    def parse(self, raw_message: Any, 
              source_protocol: ProtocolType) -> Optional[InteropMessage]:
        """
        解析源协议消息
        
        参数：
            raw_message: 原始消息
            source_protocol: 源协议类型
        
        返回：通用 InteropMessage
        """
        adapter = self._adapters.get(source_protocol)
        if not adapter:
            print(f"[ProtocolConverter] No adapter for {source_protocol}")
            return None
        
        return adapter.decode(raw_message)
    
    def translate(self, raw_message: Any, source_protocol: ProtocolType,
                  target_protocol: ProtocolType) -> Optional[Any]:
        """
        直接在两个协议之间转换
        
        参数：
            raw_message: 原始消息
            source_protocol: 源协议
            target_protocol: 目标协议
        
        返回：目标协议消息
        """
        # 先解析为通用格式
        message = self.parse(raw_message, source_protocol)
        if not message:
            return None
        
        # 转换为目标协议
        return self.convert(message, target_protocol)


# ==================== 跨框架网关 ====================

class InteropGateway:
    """
    跨框架互操作网关
    ==================
    统一的跨框架通信接口
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._converter = ProtocolConverter()
        self._handlers: Dict[str, Callable] = {}
        self._enabled_protocols: Set[ProtocolType] = {
            ProtocolType.A2A,
        }
        self._lock = threading.Lock()
        self._stats = {
            "messages_sent": defaultdict(int),
            "messages_received": defaultdict(int),
            "conversions": defaultdict(int),
        }
    
    def enable_protocol(self, protocol: ProtocolType):
        """启用协议"""
        with self._lock:
            self._enabled_protocols.add(protocol)
    
    def disable_protocol(self, protocol: ProtocolType):
        """禁用协议"""
        with self._lock:
            self._enabled_protocols.discard(protocol)
    
    def register_handler(self, action: str, 
                         handler: Callable[[InteropMessage], Any]):
        """注册消息处理器"""
        self._handlers[action] = handler
    
    def send_message(self, action: str, payload: Dict,
                     target_protocol: ProtocolType,
                     receiver: str = None) -> bool:
        """
        发送跨框架消息
        
        参数：
            action: 动作名称
            payload: 消息载荷
            target_protocol: 目标协议
            receiver: 目标 Agent ID
        
        返回：是否成功
        """
        if target_protocol not in self._enabled_protocols:
            print(f"[InteropGateway] Protocol {target_protocol} not enabled")
            return False
        
        message = InteropMessage.create(
            protocol=ProtocolType.A2A,  # 源协议
            action=action,
            sender=self.agent_id,
            payload=payload,
            receiver=receiver,
        )
        
        # 转换为目标协议
        encoded = self._converter.convert(message, target_protocol)
        if not encoded:
            return False
        
        self._stats["messages_sent"][target_protocol.value] += 1
        self._stats["conversions"][target_protocol.value] += 1
        
        # TODO: 通过实际的传输层发送
        print(f"[InteropGateway] Sending to {target_protocol.value}: {encoded}")
        return True
    
    def receive_message(self, raw_message: Any, 
                        source_protocol: ProtocolType) -> Optional[Any]:
        """
        接收跨框架消息
        
        参数：
            raw_message: 原始消息
            source_protocol: 源协议
        
        返回：处理结果
        """
        if source_protocol not in self._enabled_protocols:
            print(f"[InteropGateway] Protocol {source_protocol} not enabled")
            return None
        
        # 解析消息
        message = self._converter.parse(raw_message, source_protocol)
        if not message:
            return None
        
        self._stats["messages_received"][source_protocol.value] += 1
        
        # 查找处理器
        handler = self._handlers.get(message.action)
        if handler:
            try:
                result = handler(message)
                
                # 如果需要响应，编码响应
                if message.receiver or not message.receiver:
                    response_adapter = self._converter.get_adapter(source_protocol)
                    if response_adapter:
                        return response_adapter.encode_response(message, result)
                
                return result
            except Exception as e:
                print(f"[InteropGateway] Handler error: {e}")
                return {"error": str(e)}
        
        return {"status": "no_handler"}
    
    def bridge_protocols(self, source: ProtocolType, target: ProtocolType,
                         raw_message: Any) -> Optional[Any]:
        """
        桥接两个协议（协议转换）
        """
        self._stats["conversions"][f"{source.value}_to_{target.value}"] += 1
        return self._converter.translate(raw_message, source, target)
    
    def discover_agents(self, protocol: ProtocolType) -> List[Dict]:
        """
        发现支持指定协议的 Agent
        """
        if protocol == ProtocolType.MODELSCOPE_AGENT:
            # 模拟发现
            return [
                {"agent_id": "modelscope_agent_1", "capabilities": ["nlp", "vision"]},
                {"agent_id": "modelscope_agent_2", "capabilities": ["code", "reasoning"]},
            ]
        elif protocol == ProtocolType.LANGCHAIN:
            return [
                {"agent_id": "langchain_agent_1", "tools": ["search", "calculator"]},
            ]
        
        return []
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **dict(self._stats),
            "enabled_protocols": [p.value for p in self._enabled_protocols],
            "handlers_count": len(self._handlers),
        }


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""
    # 创建网关
    gateway = InteropGateway("livingtree_agent_001")
    
    # 启用其他协议
    gateway.enable_protocol(ProtocolType.MODELSCOPE_AGENT)
    gateway.enable_protocol(ProtocolType.LANGCHAIN)
    gateway.enable_protocol(ProtocolType.MCP)
    
    # 注册处理器
    def handle_execute(message: InteropMessage):
        print(f"Executing task: {message.payload}")
        return {"status": "success", "result": "task_completed"}
    
    gateway.register_handler("execute_task", handle_execute)
    
    # 发送消息到其他框架
    gateway.send_message(
        action="execute_task",
        payload={"task": "analyze_data"},
        target_protocol=ProtocolType.MODELSCOPE_AGENT,
        receiver="modelscope_agent_1"
    )
    
    # 接收来自其他框架的消息
    modelscope_message = {
        "action": "invoke",
        "agent_id": "external_agent",
        "parameters": {"task": "translate", "text": "Hello"},
        "request_id": "req_123",
    }
    result = gateway.receive_message(
        modelscope_message,
        ProtocolType.MODELSCOPE_AGENT
    )
    print(f"Result: {result}")
    
    # 协议桥接
    langchain_message = {
        "type": "tool_use",
        "session_id": "user_session",
        "tool_calls": [{"name": "search", "arguments": '{"query":"AI"}'}],
        "id": "msg_456",
    }
    converted = gateway.bridge_protocols(
        ProtocolType.LANGCHAIN,
        ProtocolType.MODELSCOPE_AGENT,
        langchain_message
    )
    print(f"Converted: {converted}")
