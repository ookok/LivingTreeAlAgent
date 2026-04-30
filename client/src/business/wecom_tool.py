"""
企业微信操作工具 (WeCom Tool)
=============================

参考: wecom-cli - 让AI Agent能在终端中操作企业微信

实现企业微信的核心操作功能：
1. 发送消息 - 发送文本、图片、文件消息
2. 获取联系人 - 获取企业微信联系人列表
3. 获取群组 - 获取企业微信群组列表
4. 发送文件 - 发送文件到聊天
5. 智能回复 - 基于AI的智能消息回复
6. 消息监控 - 实时监控消息

核心特性：
- 命令行接口支持
- AI智能回复
- 消息分类处理
- 批量操作支持
- 消息模板管理

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    CARD = "card"
    LINK = "link"


class ChatType(Enum):
    """聊天类型"""
    PRIVATE = "private"      # 私聊
    GROUP = "group"          # 群组
    ROOM = "room"            # 群聊


@dataclass
class Contact:
    """联系人信息"""
    id: str
    name: str
    department: Optional[str] = None
    position: Optional[str] = None
    avatar: Optional[str] = None
    status: str = "active"


@dataclass
class Group:
    """群组信息"""
    id: str
    name: str
    members: List[str] = field(default_factory=list)
    member_count: int = 0
    is_top: bool = False


@dataclass
class Message:
    """消息信息"""
    id: str
    type: MessageType
    content: str
    sender: str
    receiver: str
    chat_type: ChatType
    timestamp: float
    read: bool = False


@dataclass
class SendResult:
    """发送结果"""
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: float = 0.0


class WeComTool:
    """
    企业微信操作工具
    
    核心功能：
    1. 消息发送 - 支持文本、图片、文件
    2. 联系人管理 - 获取和搜索联系人
    3. 群组管理 - 获取群组信息
    4. 智能回复 - AI驱动的消息回复
    5. 消息监控 - 实时消息监听
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 模拟企业微信数据
        self._contacts = self._load_mock_contacts()
        self._groups = self._load_mock_groups()
        self._messages = []
        
        # 消息模板
        self._message_templates = {
            "welcome": "您好！我是智能助手，请问有什么可以帮您的？",
            "reminder": "温馨提醒：{content}",
            "report": "【日报】{date}\n{content}",
            "meeting": "会议通知：{title}\n时间：{time}\n地点：{location}",
        }
        
        # 消息分类器
        self._message_classifier = MessageClassifier()
        
        # 智能回复引擎
        self._smart_replier = SmartReplier()
        
        # 监控状态
        self._monitoring = False
        self._monitor_task = None
        
        self._initialized = True
        logger.info("[WeComTool] 企业微信工具初始化完成")
    
    def _load_mock_contacts(self) -> Dict[str, Contact]:
        """加载模拟联系人数据"""
        return {
            "user1": Contact(
                id="user1",
                name="张三",
                department="技术部",
                position="高级工程师",
            ),
            "user2": Contact(
                id="user2",
                name="李四",
                department="产品部",
                position="产品经理",
            ),
            "user3": Contact(
                id="user3",
                name="王五",
                department="运营部",
                position="运营主管",
            ),
            "user4": Contact(
                id="user4",
                name="赵六",
                department="财务部",
                position="财务专员",
            ),
        }
    
    def _load_mock_groups(self) -> Dict[str, Group]:
        """加载模拟群组数据"""
        return {
            "group1": Group(
                id="group1",
                name="技术交流群",
                members=["user1", "user2", "user3"],
                member_count=3,
                is_top=True,
            ),
            "group2": Group(
                id="group2",
                name="产品需求群",
                members=["user2", "user3"],
                member_count=2,
            ),
            "group3": Group(
                id="group3",
                name="管理层群",
                members=["user1", "user2", "user4"],
                member_count=3,
                is_top=True,
            ),
        }
    
    async def send_message(self, receiver_id: str, content: str, 
                          message_type: MessageType = MessageType.TEXT,
                          chat_type: ChatType = ChatType.PRIVATE) -> SendResult:
        """
        发送消息
        
        Args:
            receiver_id: 接收者ID
            content: 消息内容
            message_type: 消息类型
            chat_type: 聊天类型
            
        Returns:
            发送结果
        """
        import time
        
        try:
            # 验证接收者
            if chat_type == ChatType.PRIVATE:
                if receiver_id not in self._contacts:
                    return SendResult(
                        success=False,
                        error_message=f"联系人不存在: {receiver_id}"
                    )
            else:
                if receiver_id not in self._groups:
                    return SendResult(
                        success=False,
                        error_message=f"群组不存在: {receiver_id}"
                    )
            
            # 创建消息
            message_id = f"msg_{int(time.time() * 1000)}"
            message = Message(
                id=message_id,
                type=message_type,
                content=content,
                sender="agent",
                receiver=receiver_id,
                chat_type=chat_type,
                timestamp=time.time(),
            )
            
            self._messages.append(message)
            
            logger.info(f"[WeComTool] 消息发送成功: {message_id}")
            return SendResult(
                success=True,
                message_id=message_id,
                timestamp=time.time(),
            )
        
        except Exception as e:
            logger.error(f"[WeComTool] 消息发送失败: {e}")
            return SendResult(
                success=False,
                error_message=str(e),
            )
    
    async def send_file(self, receiver_id: str, file_path: str, 
                       chat_type: ChatType = ChatType.PRIVATE) -> SendResult:
        """
        发送文件
        
        Args:
            receiver_id: 接收者ID
            file_path: 文件路径
            chat_type: 聊天类型
            
        Returns:
            发送结果
        """
        # 模拟文件发送
        content = f"[文件] {file_path}"
        return await self.send_message(receiver_id, content, MessageType.FILE, chat_type)
    
    async def send_image(self, receiver_id: str, image_path: str, 
                        chat_type: ChatType = ChatType.PRIVATE) -> SendResult:
        """
        发送图片
        
        Args:
            receiver_id: 接收者ID
            image_path: 图片路径
            chat_type: 聊天类型
            
        Returns:
            发送结果
        """
        content = f"[图片] {image_path}"
        return await self.send_message(receiver_id, content, MessageType.IMAGE, chat_type)
    
    async def send_template_message(self, receiver_id: str, template_name: str, 
                                   params: Dict[str, str],
                                   chat_type: ChatType = ChatType.PRIVATE) -> SendResult:
        """
        发送模板消息
        
        Args:
            receiver_id: 接收者ID
            template_name: 模板名称
            params: 模板参数
            chat_type: 聊天类型
            
        Returns:
            发送结果
        """
        if template_name not in self._message_templates:
            return SendResult(
                success=False,
                error_message=f"模板不存在: {template_name}"
            )
        
        template = self._message_templates[template_name]
        content = template.format(**params)
        
        return await self.send_message(receiver_id, content, MessageType.TEXT, chat_type)
    
    def get_contacts(self) -> List[Contact]:
        """获取所有联系人"""
        return list(self._contacts.values())
    
    def search_contacts(self, keyword: str) -> List[Contact]:
        """
        搜索联系人
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的联系人列表
        """
        keyword_lower = keyword.lower()
        return [
            contact for contact in self._contacts.values()
            if keyword_lower in contact.name.lower() or
               (contact.department and keyword_lower in contact.department.lower()) or
               (contact.position and keyword_lower in contact.position.lower())
        ]
    
    def get_groups(self) -> List[Group]:
        """获取所有群组"""
        return list(self._groups.values())
    
    def get_group_members(self, group_id: str) -> Optional[List[Contact]]:
        """
        获取群组成员
        
        Args:
            group_id: 群组ID
            
        Returns:
            成员列表
        """
        if group_id not in self._groups:
            return None
        
        group = self._groups[group_id]
        return [
            self._contacts[member_id]
            for member_id in group.members
            if member_id in self._contacts
        ]
    
    async def smart_reply(self, message: Message) -> Optional[str]:
        """
        智能回复消息
        
        Args:
            message: 收到的消息
            
        Returns:
            回复内容
        """
        return await self._smart_replier.generate_reply(message)
    
    def classify_message(self, content: str) -> str:
        """
        分类消息
        
        Args:
            content: 消息内容
            
        Returns:
            消息类别
        """
        return self._message_classifier.classify(content)
    
    def start_monitoring(self):
        """开始监控消息"""
        if not self._monitoring:
            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("[WeComTool] 消息监控已启动")
    
    def stop_monitoring(self):
        """停止监控消息"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("[WeComTool] 消息监控已停止")
    
    async def _monitor_loop(self):
        """消息监控循环"""
        while self._monitoring:
            # 模拟收到消息
            await asyncio.sleep(5)
            self._simulate_incoming_message()
    
    def _simulate_incoming_message(self):
        """模拟收到消息"""
        import time
        contacts = list(self._contacts.keys())
        if contacts:
            sender_id = contacts[0]
            message = Message(
                id=f"msg_{int(time.time() * 1000)}",
                type=MessageType.TEXT,
                content="您好，请问今天的工作安排是什么？",
                sender=sender_id,
                receiver="agent",
                chat_type=ChatType.PRIVATE,
                timestamp=time.time(),
            )
            self._messages.append(message)
            logger.info(f"[WeComTool] 收到消息: {message.id}")
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """获取最近消息"""
        return sorted(self._messages, key=lambda m: m.timestamp, reverse=True)[:limit]
    
    def add_message_template(self, name: str, template: str):
        """添加消息模板"""
        self._message_templates[name] = template
    
    def get_message_templates(self) -> Dict[str, str]:
        """获取所有消息模板"""
        return self._message_templates.copy()


class MessageClassifier:
    """消息分类器"""
    
    def __init__(self):
        self._categories = {
            "greeting": ["你好", "您好", "嗨", "Hello", "Hi"],
            "question": ["什么", "怎么", "如何", "为什么", "请问", "吗"],
            "request": ["帮我", "请帮我", "需要", "想要", "请求"],
            "report": ["报告", "日报", "周报", "月报", "总结"],
            "meeting": ["会议", "开会", "讨论", "沟通"],
            "reminder": ["提醒", "通知", "注意"],
            "chat": ["哈哈", "哦", "好的", "嗯", "知道了"],
        }
    
    def classify(self, content: str) -> str:
        """分类消息"""
        content_lower = content.lower()
        
        for category, keywords in self._categories.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return "other"


class SmartReplier:
    """智能回复引擎"""
    
    def __init__(self):
        self._reply_templates = {
            "greeting": "您好！我是智能助手，很高兴为您服务！",
            "question": "好的，我来帮您解答。",
            "request": "收到，我来处理这件事。",
            "report": "好的，我会生成报告并发送给您。",
            "meeting": "收到会议通知，我会安排时间参加。",
            "reminder": "好的，我会记住这个提醒。",
            "chat": "😄",
            "other": "明白了，我会认真处理。",
        }
    
    async def generate_reply(self, message: Message) -> Optional[str]:
        """生成智能回复"""
        classifier = MessageClassifier()
        category = classifier.classify(message.content)
        
        template = self._reply_templates.get(category)
        
        # 简单的上下文理解
        if "工作安排" in message.content:
            return "今天的工作安排是：上午10点参加技术会议，下午完成项目报告。"
        
        return template


# 便捷函数
def get_wecom_tool() -> WeComTool:
    """获取企业微信工具单例"""
    return WeComTool()


__all__ = [
    "MessageType",
    "ChatType",
    "Contact",
    "Group",
    "Message",
    "SendResult",
    "WeComTool",
    "get_wecom_tool",
]
