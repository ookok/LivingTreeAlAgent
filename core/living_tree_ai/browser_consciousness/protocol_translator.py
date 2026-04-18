"""
协议翻译器 (Protocol Translator)
================================

将多种协议路由到不同的处理引擎：

- http:// → 直接 HTTP 请求 或 P2P 代理
- hyperos:// → 本地 P2P 网络路由
- node://<id>/path → WebRTC 直连
- mailto:// → 内置邮件新建
- forum:// → 内部论坛跳转
- cid:// → CID 内容寻址
"""

import re
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """支持的协议类型"""
    HTTP = "http"
    HTTPS = "https"
    HYPEROS = "hyperos"
    NODE = "node"
    MAILTO = "mailto"
    FORUM = "forum"
    CID = "cid"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass
class ProtocolRoute:
    """协议路由信息"""
    protocol: ProtocolType
    handler: str                          # 处理器名称
    action: str                           # 操作类型
    params: Dict[str, Any] = field(default_factory=dict)
    raw_uri: str = ""


@dataclass
class TranslationResult:
    """翻译结果"""
    success: bool
    route: Optional[ProtocolRoute] = None
    error: Optional[str] = None
    fallback_url: Optional[str] = None    # 降级后的 URL


class ProtocolTranslator:
    """
    协议翻译器

    将统一资源标识符翻译为内部路由动作
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认处理器映射"""
        self._handlers = {
            "http": self._handle_http,
            "https": self._handle_https,
            "hyperos": self._handle_hyperos,
            "node": self._handle_node,
            "mailto": self._handle_mailto,
            "forum": self._handle_forum,
            "cid": self._handle_cid,
            "file": self._handle_file,
        }

    def register_handler(self, protocol: str, handler: Callable) -> None:
        """注册自定义协议处理器"""
        self._handlers[protocol.lower()] = handler

    def translate(self, uri: str) -> TranslationResult:
        """
        翻译 URI 为内部路由

        Args:
            uri: 统一资源标识符

        Returns:
            TranslationResult: 翻译结果
        """
        if not uri:
            return TranslationResult(
                success=False,
                error="Empty URI"
            )

        uri = uri.strip()

        # 解析协议
        protocol_match = re.match(r'^([a-zA-Z][a-zA-Z0-9+]*)://', uri)
        if not protocol_match:
            # 尝试补全 http://
            if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', uri):
                return self.translate(f"http://{uri}")
            return TranslationResult(
                success=False,
                error=f"Invalid URI format: {uri}"
            )

        protocol_str = protocol_match.group(1).lower()
        protocol = self._parse_protocol(protocol_str)

        if protocol == ProtocolType.UNKNOWN:
            return TranslationResult(
                success=False,
                error=f"Unknown protocol: {protocol_str}"
            )

        # 调用对应处理器
        handler = self._handlers.get(protocol_str)
        if not handler:
            return TranslationResult(
                success=False,
                error=f"No handler for protocol: {protocol_str}"
            )

        try:
            route = handler(uri, protocol_str, protocol)
            return TranslationResult(success=True, route=route)
        except Exception as e:
            logger.error(f"Protocol handler error: {e}")
            return TranslationResult(
                success=False,
                error=str(e)
            )

    def _parse_protocol(self, protocol_str: str) -> ProtocolType:
        """解析协议类型"""
        protocol_map = {
            "http": ProtocolType.HTTP,
            "https": ProtocolType.HTTPS,
            "hyperos": ProtocolType.HYPEROS,
            "node": ProtocolType.NODE,
            "mailto": ProtocolType.MAILTO,
            "forum": ProtocolType.FORUM,
            "cid": ProtocolType.CID,
            "file": ProtocolType.FILE,
        }
        return protocol_map.get(protocol_str, ProtocolType.UNKNOWN)

    # ========== 协议处理器 ==========

    def _handle_http(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """处理 HTTP 协议"""
        # 提取主机和路径
        match = re.match(r'http://([^/]+)(/.*)?$', uri, re.IGNORECASE)
        if match:
            host = match.group(1)
            path = match.group(2) or "/"
        else:
            host = ""
            path = "/"

        return ProtocolRoute(
            protocol=protocol,
            handler="http_client",
            action="fetch",
            params={"host": host, "path": path, "use_p2p_proxy": False},
            raw_uri=uri
        )

    def _handle_https(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """处理 HTTPS 协议"""
        return self._handle_http(uri.replace("https://", "http://"), "http", protocol)

    def _handle_hyperos(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 hyperos:// 协议

        格式：
        - hyperos://node/<node-id>/<action>
        - hyperos://mail/<action>?to=xxx&subject=xxx
        - hyperos://content/<content-id>
        - hyperos://cid/<cid>
        - hyperos://forum/<post-id>
        - hyperos://search?q=xxx
        """
        # 移除协议前缀
        path = re.sub(r'^hyperos://', '', uri)

        # 解析路径
        parts = path.split('/')
        if not parts:
            raise ValueError("Invalid hyperos URI: empty path")

        namespace = parts[0].lower()

        if namespace == "node":
            # hyperos://node/<node-id>/<action>
            if len(parts) < 3:
                raise ValueError("Invalid node URI: expected node/<node-id>/<action>")
            node_id = parts[1]
            action = parts[2]
            extra_params = self._parse_query_params(path)
            return ProtocolRoute(
                protocol=protocol,
                handler="p2p_router",
                action=action,
                params={"node_id": node_id, **extra_params},
                raw_uri=uri
            )

        elif namespace == "mail":
            # hyperos://mail/<action>
            action = parts[1] if len(parts) > 1 else "compose"
            extra_params = self._parse_query_params(path)
            return ProtocolRoute(
                protocol=protocol,
                handler="internal_mail",
                action=action,
                params=extra_params,
                raw_uri=uri
            )

        elif namespace == "content":
            # hyperos://content/<content-id>
            content_id = parts[1] if len(parts) > 1 else ""
            return ProtocolRoute(
                protocol=protocol,
                handler="content_store",
                action="get",
                params={"content_id": content_id},
                raw_uri=uri
            )

        elif namespace == "cid":
            # hyperos://cid/<cid>
            cid = parts[1] if len(parts) > 1 else ""
            return ProtocolRoute(
                protocol=protocol,
                handler="cid_resolver",
                action="resolve",
                params={"cid": cid},
                raw_uri=uri
            )

        elif namespace == "forum":
            # hyperos://forum/<post-id>
            post_id = parts[1] if len(parts) > 1 else ""
            action = parts[2] if len(parts) > 2 else "view"
            return ProtocolRoute(
                protocol=protocol,
                handler="internal_forum",
                action=action,
                params={"post_id": post_id},
                raw_uri=uri
            )

        elif namespace == "search":
            # hyperos://search?q=xxx
            params = self._parse_query_params(path)
            return ProtocolRoute(
                protocol=protocol,
                handler="unified_search",
                action="search",
                params=params,
                raw_uri=uri
            )

        else:
            raise ValueError(f"Unknown hyperos namespace: {namespace}")

    def _handle_node(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 node:// 协议

        格式：node://<node-id>/<path>
        """
        path = re.sub(r'^node://', '', uri)
        parts = path.split('/')

        if not parts or not parts[0]:
            raise ValueError("Invalid node URI: missing node ID")

        node_id = parts[0]
        resource_path = '/'.join(parts[1:]) if len(parts) > 1 else "/"

        return ProtocolRoute(
            protocol=protocol,
            handler="webrtc_direct",
            action="connect",
            params={"node_id": node_id, "path": resource_path},
            raw_uri=uri
        )

    def _handle_mailto(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 mailto:// 协议

        格式：mailto:<to>[?subject=xxx][&body=xxx]
        """
        path = re.sub(r'^mailto:', '', uri)

        # 分离收件人和查询参数
        if '?' in path:
            to, query = path.split('?', 1)
            params = self._parse_query_params("?" + query)
        else:
            to = path
            params = {}

        return ProtocolRoute(
            protocol=protocol,
            handler="internal_mail",
            action="compose",
            params={"to": to, **params},
            raw_uri=uri
        )

    def _handle_forum(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 forum:// 协议

        格式：forum://<post-id>[/<action>]
        """
        path = re.sub(r'^forum://', '', uri)
        parts = path.split('/')

        post_id = parts[0] if parts else ""
        action = parts[1] if len(parts) > 1 else "view"

        return ProtocolRoute(
            protocol=protocol,
            handler="internal_forum",
            action=action,
            params={"post_id": post_id},
            raw_uri=uri
        )

    def _handle_cid(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 cid:// 协议

        格式：cid:<cid>
        """
        cid = re.sub(r'^cid://', '', uri)

        return ProtocolRoute(
            protocol=protocol,
            handler="cid_resolver",
            action="resolve",
            params={"cid": cid},
            raw_uri=uri
        )

    def _handle_file(self, uri: str, protocol_str: str, protocol: ProtocolType) -> ProtocolRoute:
        """
        处理 file:// 协议

        格式：file://<path>
        """
        path = re.sub(r'^file://', '', uri)

        return ProtocolRoute(
            protocol=protocol,
            handler="local_file",
            action="read",
            params={"path": path},
            raw_uri=uri
        )

    def _parse_query_params(self, query_string: str) -> Dict[str, Any]:
        """解析查询参数"""
        if not query_string or '?' not in query_string:
            return {}

        query = query_string.split('?', 1)[1]
        params = {}

        for pair in query.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                # URL 解码
                import urllib.parse
                key = urllib.parse.unquote(key)
                value = urllib.parse.unquote(value)
                params[key] = value
            else:
                params[urllib.parse.unquote(pair)] = True

        return params

    def get_supported_protocols(self) -> List[str]:
        """获取支持的协议列表"""
        return list(self._handlers.keys())


def create_protocol_translator() -> ProtocolTranslator:
    """创建协议翻译器工厂函数"""
    return ProtocolTranslator()