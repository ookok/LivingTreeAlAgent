"""
企业微信工具适配器 (WeCom Tool Adapter)
=======================================

让智能体可以调用企业微信工具

实现工具调用接口：
1. send_message - 发送消息
2. send_file - 发送文件
3. send_image - 发送图片
4. get_contacts - 获取联系人
5. search_contacts - 搜索联系人
6. get_groups - 获取群组
7. smart_reply - 智能回复

核心特性：
- 符合Agent工具调用规范
- 支持参数验证
- 自动格式化输出
- 异步操作支持

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = __import__('logging').getLogger(__name__)


@dataclass
class ToolResult:
    """工具调用结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    description: str
    parameters: List[Dict[str, Any]]
    return_type: str


class WeComToolAdapter:
    """
    企业微信工具适配器
    
    提供符合Agent工具调用规范的接口
    """
    
    def __init__(self):
        self._wecom_tool = None
        self._lazy_load_wecom_tool()
    
    def _lazy_load_wecom_tool(self):
        """延迟加载企业微信工具"""
        if self._wecom_tool is None:
            try:
                from business.wecom_tool import get_wecom_tool
                self._wecom_tool = get_wecom_tool()
                logger.info("[WeComToolAdapter] 企业微信工具加载成功")
            except Exception as e:
                logger.error(f"[WeComToolAdapter] 加载企业微信工具失败: {e}")
    
    def get_tools(self) -> List[ToolInfo]:
        """获取可用工具列表"""
        return [
            ToolInfo(
                name="send_wecom_message",
                description="发送企业微信消息",
                parameters=[
                    {"name": "receiver_id", "type": "string", "required": True, "description": "接收者ID"},
                    {"name": "content", "type": "string", "required": True, "description": "消息内容"},
                    {"name": "message_type", "type": "string", "required": False, "description": "消息类型: text/image/file", "default": "text"},
                    {"name": "chat_type", "type": "string", "required": False, "description": "聊天类型: private/group", "default": "private"},
                ],
                return_type="object",
            ),
            ToolInfo(
                name="send_wecom_file",
                description="发送企业微信文件",
                parameters=[
                    {"name": "receiver_id", "type": "string", "required": True, "description": "接收者ID"},
                    {"name": "file_path", "type": "string", "required": True, "description": "文件路径"},
                    {"name": "chat_type", "type": "string", "required": False, "description": "聊天类型: private/group", "default": "private"},
                ],
                return_type="object",
            ),
            ToolInfo(
                name="get_wecom_contacts",
                description="获取企业微信联系人列表",
                parameters=[],
                return_type="array",
            ),
            ToolInfo(
                name="search_wecom_contacts",
                description="搜索企业微信联系人",
                parameters=[
                    {"name": "keyword", "type": "string", "required": True, "description": "搜索关键词"},
                ],
                return_type="array",
            ),
            ToolInfo(
                name="get_wecom_groups",
                description="获取企业微信群组列表",
                parameters=[],
                return_type="array",
            ),
            ToolInfo(
                name="get_wecom_group_members",
                description="获取群组成员",
                parameters=[
                    {"name": "group_id", "type": "string", "required": True, "description": "群组ID"},
                ],
                return_type="array",
            ),
            ToolInfo(
                name="send_wecom_template",
                description="发送模板消息",
                parameters=[
                    {"name": "receiver_id", "type": "string", "required": True, "description": "接收者ID"},
                    {"name": "template_name", "type": "string", "required": True, "description": "模板名称"},
                    {"name": "params", "type": "object", "required": False, "description": "模板参数"},
                ],
                return_type="object",
            ),
        ]
    
    async def call_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            kwargs: 工具参数
            
        Returns:
            工具调用结果
        """
        if not self._wecom_tool:
            return ToolResult(
                success=False,
                error="企业微信工具未加载",
            )
        
        try:
            if tool_name == "send_wecom_message":
                return await self._send_message(**kwargs)
            elif tool_name == "send_wecom_file":
                return await self._send_file(**kwargs)
            elif tool_name == "get_wecom_contacts":
                return self._get_contacts()
            elif tool_name == "search_wecom_contacts":
                return self._search_contacts(**kwargs)
            elif tool_name == "get_wecom_groups":
                return self._get_groups()
            elif tool_name == "get_wecom_group_members":
                return self._get_group_members(**kwargs)
            elif tool_name == "send_wecom_template":
                return await self._send_template(**kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"未知工具: {tool_name}",
                )
        
        except Exception as e:
            logger.error(f"[WeComToolAdapter] 调用工具失败: {e}")
            return ToolResult(
                success=False,
                error=str(e),
            )
    
    async def _send_message(self, receiver_id: str, content: str, 
                           message_type: str = "text", chat_type: str = "private") -> ToolResult:
        """发送消息"""
        from business.wecom_tool import MessageType, ChatType
        
        msg_type = MessageType(message_type)
        chat_type_enum = ChatType(chat_type)
        
        result = await self._wecom_tool.send_message(
            receiver_id, content, msg_type, chat_type_enum
        )
        
        return ToolResult(
            success=result.success,
            data={"message_id": result.message_id},
            message="消息发送成功" if result.success else result.error_message,
        )
    
    async def _send_file(self, receiver_id: str, file_path: str, 
                        chat_type: str = "private") -> ToolResult:
        """发送文件"""
        from business.wecom_tool import ChatType
        
        chat_type_enum = ChatType(chat_type)
        
        result = await self._wecom_tool.send_file(receiver_id, file_path, chat_type_enum)
        
        return ToolResult(
            success=result.success,
            data={"message_id": result.message_id},
            message="文件发送成功" if result.success else result.error_message,
        )
    
    def _get_contacts(self) -> ToolResult:
        """获取联系人"""
        contacts = self._wecom_tool.get_contacts()
        
        data = [
            {
                "id": c.id,
                "name": c.name,
                "department": c.department,
                "position": c.position,
            }
            for c in contacts
        ]
        
        return ToolResult(
            success=True,
            data=data,
            message=f"找到 {len(data)} 个联系人",
        )
    
    def _search_contacts(self, keyword: str) -> ToolResult:
        """搜索联系人"""
        contacts = self._wecom_tool.search_contacts(keyword)
        
        data = [
            {
                "id": c.id,
                "name": c.name,
                "department": c.department,
                "position": c.position,
            }
            for c in contacts
        ]
        
        return ToolResult(
            success=True,
            data=data,
            message=f"找到 {len(data)} 个匹配的联系人",
        )
    
    def _get_groups(self) -> ToolResult:
        """获取群组"""
        groups = self._wecom_tool.get_groups()
        
        data = [
            {
                "id": g.id,
                "name": g.name,
                "member_count": g.member_count,
                "is_top": g.is_top,
            }
            for g in groups
        ]
        
        return ToolResult(
            success=True,
            data=data,
            message=f"找到 {len(data)} 个群组",
        )
    
    def _get_group_members(self, group_id: str) -> ToolResult:
        """获取群组成员"""
        members = self._wecom_tool.get_group_members(group_id)
        
        if members is None:
            return ToolResult(
                success=False,
                error=f"群组不存在: {group_id}",
            )
        
        data = [
            {
                "id": m.id,
                "name": m.name,
                "department": m.department,
            }
            for m in members
        ]
        
        return ToolResult(
            success=True,
            data=data,
            message=f"群组成员: {len(data)} 人",
        )
    
    async def _send_template(self, receiver_id: str, template_name: str, 
                            params: Optional[Dict[str, str]] = None) -> ToolResult:
        """发送模板消息"""
        from business.wecom_tool import ChatType
        
        result = await self._wecom_tool.send_template_message(
            receiver_id, template_name, params or {}, ChatType.PRIVATE
        )
        
        return ToolResult(
            success=result.success,
            data={"message_id": result.message_id},
            message="模板消息发送成功" if result.success else result.error_message,
        )


# 便捷函数
def get_wecom_tool_adapter() -> WeComToolAdapter:
    """获取企业微信工具适配器"""
    return WeComToolAdapter()


__all__ = [
    "ToolResult",
    "ToolInfo",
    "WeComToolAdapter",
    "get_wecom_tool_adapter",
]
