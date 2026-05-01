import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import OrderedDict

@dataclass
class Message:
    id: str
    role: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    token_count: int = 0

@dataclass
class Dialogue:
    id: str
    messages: List[Message]
    title: str = ""
    created_at: datetime = None
    updated_at: datetime = None
    metadata: Dict[str, Any] = None

class ContextWindowManager:
    """上下文窗口管理器"""
    
    def __init__(self, max_tokens: int = 8192, max_messages: int = 100):
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.dialogues: Dict[str, Dialogue] = {}
        self.active_dialogue_id: Optional[str] = None
    
    def create_dialogue(self, title: str = "") -> Dialogue:
        """创建新对话"""
        dialogue_id = hashlib.md5(f"{datetime.now().timestamp()}".encode()).hexdigest()
        dialogue = Dialogue(
            id=dialogue_id,
            messages=[],
            title=title or "新对话",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={}
        )
        self.dialogues[dialogue_id] = dialogue
        self.active_dialogue_id = dialogue_id
        return dialogue
    
    def get_dialogue(self, dialogue_id: str) -> Optional[Dialogue]:
        """获取对话"""
        return self.dialogues.get(dialogue_id)
    
    def add_message(self, dialogue_id: str, role: str, content: str, metadata: Dict = None) -> Message:
        """添加消息到对话"""
        dialogue = self.get_dialogue(dialogue_id)
        if not dialogue:
            raise ValueError("对话不存在")
        
        token_count = self._estimate_tokens(content)
        message = Message(
            id=hashlib.md5(f"{datetime.now().timestamp()}{content[:100]}".encode()).hexdigest(),
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {},
            token_count=token_count
        )
        
        dialogue.messages.append(message)
        dialogue.updated_at = datetime.now()
        
        self._compress_history(dialogue)
        
        return message
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数量"""
        return len(text) // 4
    
    def _compress_history(self, dialogue: Dialogue):
        """压缩对话历史"""
        total_tokens = sum(m.token_count for m in dialogue.messages)
        
        while total_tokens > self.max_tokens and len(dialogue.messages) > 2:
            removed = dialogue.messages.pop(1)
            total_tokens -= removed.token_count
        
        while len(dialogue.messages) > self.max_messages:
            dialogue.messages.pop(1)
    
    def get_context_window(self, dialogue_id: str, max_tokens: Optional[int] = None) -> List[Message]:
        """获取上下文窗口"""
        dialogue = self.get_dialogue(dialogue_id)
        if not dialogue:
            return []
        
        limit = max_tokens or self.max_tokens
        messages = []
        total_tokens = 0
        
        for message in reversed(dialogue.messages):
            if total_tokens + message.token_count <= limit:
                messages.insert(0, message)
                total_tokens += message.token_count
            else:
                break
        
        return messages
    
    def summarize_dialogue(self, dialogue_id: str) -> str:
        """生成对话摘要"""
        dialogue = self.get_dialogue(dialogue_id)
        if not dialogue or not dialogue.messages:
            return ""
        
        messages = dialogue.messages[-5:]
        summary = "对话摘要：\n"
        
        for msg in messages:
            role = "用户" if msg.role == "user" else "助手"
            summary += f"{role}: {msg.content[:50]}...\n"
        
        return summary.strip()
    
    def compress_dialogue(self, dialogue_id: str):
        """压缩对话 - 将早期消息替换为摘要"""
        dialogue = self.get_dialogue(dialogue_id)
        if not dialogue or len(dialogue.messages) <= 10:
            return
        
        if len(dialogue.messages) > 20:
            summary = self._generate_summary(dialogue.messages[:-10])
            new_messages = [
                dialogue.messages[0],
                Message(
                    id=hashlib.md5(f"summary_{datetime.now().timestamp()}".encode()).hexdigest(),
                    role="system",
                    content=f"【对话摘要】{summary}",
                    timestamp=datetime.now(),
                    metadata={"is_summary": True}
                )
            ] + dialogue.messages[-10:]
            
            dialogue.messages = new_messages
            dialogue.updated_at = datetime.now()
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """生成消息摘要"""
        user_messages = [m for m in messages if m.role == "user"]
        if len(user_messages) == 0:
            return "无用户消息"
        
        topics = []
        for msg in user_messages[-3:]:
            topics.append(msg.content[:30])
        
        return "; ".join(topics)
    
    def get_dialogue_list(self) -> List[Dict[str, Any]]:
        """获取对话列表"""
        result = []
        for dialogue in self.dialogues.values():
            result.append({
                "id": dialogue.id,
                "title": dialogue.title,
                "message_count": len(dialogue.messages),
                "created_at": dialogue.created_at.isoformat(),
                "updated_at": dialogue.updated_at.isoformat()
            })
        
        return sorted(result, key=lambda x: x["updated_at"], reverse=True)
    
    def delete_dialogue(self, dialogue_id: str):
        """删除对话"""
        if dialogue_id in self.dialogues:
            del self.dialogues[dialogue_id]
            if self.active_dialogue_id == dialogue_id:
                self.active_dialogue_id = None

class DialogueCompressor:
    """对话历史压缩器"""
    
    def __init__(self):
        self.compression_rules = [
            self._compress_repetitive_patterns,
            self._summarize_long_conversations,
            self._remove_duplicate_messages,
            self._truncate_long_messages
        ]
    
    def compress(self, messages: List[Message]) -> List[Message]:
        """应用所有压缩规则"""
        for rule in self.compression_rules:
            messages = rule(messages)
        return messages
    
    def _compress_repetitive_patterns(self, messages: List[Message]) -> List[Message]:
        """压缩重复模式"""
        result = []
        prev_content = None
        repeat_count = 0
        
        for msg in messages:
            if msg.content == prev_content:
                repeat_count += 1
            else:
                if repeat_count > 1:
                    result[-1].content += f" (重复{repeat_count}次)"
                repeat_count = 0
                result.append(msg)
            prev_content = msg.content
        
        return result
    
    def _summarize_long_conversations(self, messages: List[Message]) -> List[Message]:
        """对长对话生成摘要"""
        if len(messages) <= 5:
            return messages
        
        user_msgs = [m for m in messages if m.role == "user"]
        if len(user_msgs) <= 2:
            return messages
        
        summary_content = f"【对话摘要】用户询问了关于{len(user_msgs)}个话题"
        summary_msg = Message(
            id=hashlib.md5(f"summary_{datetime.now().timestamp()}".encode()).hexdigest(),
            role="system",
            content=summary_content,
            timestamp=datetime.now(),
            metadata={"is_summary": True}
        )
        
        return [messages[0], summary_msg] + messages[-3:]
    
    def _remove_duplicate_messages(self, messages: List[Message]) -> List[Message]:
        """移除重复消息"""
        seen = set()
        result = []
        
        for msg in messages:
            msg_hash = hashlib.md5(msg.content.encode()).hexdigest()
            if msg_hash not in seen:
                seen.add(msg_hash)
                result.append(msg)
        
        return result
    
    def _truncate_long_messages(self, messages: List[Message]) -> List[Message]:
        """截断超长消息"""
        max_length = 2000
        
        for msg in messages:
            if len(msg.content) > max_length:
                msg.content = msg.content[:max_length] + "...【内容已截断】"
        
        return messages