"""
HyperOS 协议 (hyperos://)
=========================

自定义协议实现，用于连接 Web 与内部分布式系统。

协议格式：
- hyperos://node/<node-id>/<action>
- hyperos://mail/<action>?to=xxx&subject=xxx
- hyperos://content/<content-id>
- hyperos://cid/<cid>
- hyperos://forum/<post-id>
- hyperos://search?q=xxx
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HyperOSURI:
    """HyperOS URI 解析结果"""
    protocol: str = "hyperos"
    authority: str = ""               # 节点 ID (如 node-id@device)
    path: str = ""                   # 路径
    action: str = ""                 # 操作
    params: dict[str, str] = field(default_factory=dict)  # 查询参数
    fragment: str = ""               # 片段
    raw: str = ""                    # 原始 URI


def parse_hyperos_uri(uri: str) -> Optional[HyperOSURI]:
    """
    解析 hyperos:// URI

    Examples:
        hyperos://node/alice@laptop-001/status
        hyperos://mail/send?to=bob@desktop&subject=Hello
        hyperos://content/abc123def456
        hyperos://cid/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco
        hyperos://forum/post/123
        hyperos://search?q=distributed+AI
    """
    if not uri or not uri.startswith("hyperos://"):
        return None

    result = HyperOSURI(raw=uri)

    # 移除协议前缀
    remainder = uri[10:]  # len("hyperos://") = 10

    # 解析 authority (节点 ID)
    if "/" in remainder:
        authority_part, remainder = remainder.split("/", 1)
        if "@" in authority_part:
            result.authority = authority_part
    else:
        authority_part = remainder
        remainder = ""

    # 分割路径和查询参数
    if "?" in remainder:
        path_part, query_part = remainder.split("?", 1)
        result.path = "/" + path_part
        result.params = parse_query_string(query_part)
    else:
        result.path = "/" + remainder

    # 解析 fragment
    if "#" in result.path:
        result.path, result.fragment = result.path.split("#", 1)

    # 提取 action (路径最后一段)
    if result.path:
        segments = result.path.strip("/").split("/")
        if segments:
            result.action = segments[-1]

    return result


def parse_query_string(query: str) -> dict[str, str]:
    """解析查询字符串"""
    params = {}
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[key] = value
    return params


def build_hyperos_uri(
    path: str,
    params: Optional[dict[str, str]] = None,
    authority: Optional[str] = None,
    fragment: Optional[str] = None
) -> str:
    """
    构建 hyperos:// URI

    Args:
        path: 路径 (如 "/mail/send")
        params: 查询参数
        authority: 权限 (如 "alice@laptop-001")
        fragment: 片段

    Returns:
        完整的 URI 字符串
    """
    uri = "hyperos://"

    if authority:
        uri += authority + "/"

    uri += path.lstrip("/")

    # 添加查询参数
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        uri += "?" + query

    # 添加片段
    if fragment:
        uri += "#" + fragment

    return uri


class HyperOSProtocol:
    """
    HyperOS 协议处理器

    负责路由和执行 hyperos:// URI
    """

    # 预定义路径模板
    PATH_TEMPLATES = {
        # 节点操作
        "node_status": "/node/{node_id}/status",
        "node_info": "/node/{node_id}/info",
        "node_mail": "/node/{node_id}/mail",

        # 邮件操作
        "mail_send": "/mail/send",
        "mail_inbox": "/mail/inbox",
        "mail_sent": "/mail/sent",
        "mail_draft": "/mail/draft",
        "mail_read": "/mail/read/{message_id}",

        # 内容操作
        "content_get": "/content/{content_id}",
        "content_list": "/content/list",
        "content_search": "/content/search",

        # 论坛操作
        "forum_post": "/forum/post/{post_id}",
        "forum_create": "/forum/create",
        "forum_list": "/forum/list",

        # 搜索
        "search": "/search",
    }

    def __init__(self, gateway: "BrowserGateway"):
        self.gateway = gateway

    def build_uri(self, template_name: str, **kwargs) -> str:
        """构建 URI"""
        template = self.PATH_TEMPLATES.get(template_name, "/{template_name}")
        path = template.format(**kwargs)

        # 提取查询参数
        params = {k: v for k, v in kwargs.items() if k not in path}

        return build_hyperos_uri(path, params if params else None)

    def route(self, uri: str) -> dict[str, Any]:
        """
        路由 URI 到对应处理器

        Returns:
            路由结果，包含 action, handler, params
        """
        parsed = parse_hyperos_uri(uri)
        if not parsed:
            return {"error": "Invalid URI"}

        path = parsed.path.strip("/")
        segments = path.split("/")

        # 根据路径前缀路由
        if segments[0] == "node":
            return {
                "action": "node",
                "sub_action": segments[-1] if len(segments) > 1 else "info",
                "node_id": segments[1] if len(segments) > 1 else parsed.authority,
                "params": parsed.params
            }
        elif segments[0] == "mail":
            return {
                "action": "mail",
                "sub_action": segments[1] if len(segments) > 1 else "inbox",
                "params": parsed.params
            }
        elif segments[0] == "content":
            return {
                "action": "content",
                "content_id": segments[1] if len(segments) > 1 else None,
                "params": parsed.params
            }
        elif segments[0] == "cid":
            return {
                "action": "cid",
                "cid": segments[1] if len(segments) > 1 else None,
                "params": parsed.params
            }
        elif segments[0] == "forum":
            return {
                "action": "forum",
                "sub_action": segments[1] if len(segments) > 1 else "list",
                "post_id": segments[2] if len(segments) > 2 else None,
                "params": parsed.params
            }
        elif segments[0] == "search":
            return {
                "action": "search",
                "query": parsed.params.get("q", ""),
                "params": parsed.params
            }

        return {"action": "unknown", "path": path}

    def generate_clickable_link(
        self,
        action: str,
        text: str,
        **kwargs
    ) -> str:
        """
        生成可点击的链接 HTML

        用于在网页中插入 hyperos:// 链接
        """
        uri = self.build_uri(action, **kwargs)
        return f'<a href="{uri}" class="hyperos-link">{text}</a>'

    def generate_bookmarklet(self, action: str, **kwargs) -> str:
        """
        生成 Bookmarklet

        用于浏览器书签
        """
        uri = self.build_uri(action, **kwargs)
        return f'javascript:window.location.href="{uri}";'


# 常用 URI 构建辅助函数

def node_status_uri(node_id: str) -> str:
    """节点状态 URI"""
    return build_hyperos_uri(f"/node/{node_id}/status")


def send_mail_uri(to: str, subject: str = "", content: str = "") -> str:
    """发送邮件 URI"""
    params = {"to": to}
    if subject:
        params["subject"] = subject
    if content:
        params["content"] = content
    return build_hyperos_uri("/mail/send", params)


def content_uri(content_id: str) -> str:
    """内容 URI"""
    return build_hyperos_uri(f"/content/{content_id}")


def cid_uri(cid: str) -> str:
    """CID URI"""
    return build_hyperos_uri(f"/cid/{cid}")


def search_uri(query: str) -> str:
    """搜索 URI"""
    return build_hyperos_uri("/search", {"q": query})


def forum_post_uri(post_id: str) -> str:
    """论坛帖子 URI"""
    return build_hyperos_uri(f"/forum/post/{post_id}")