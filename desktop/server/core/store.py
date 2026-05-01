"""
In-memory storage with persistence for sessions and messages.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

class Message:
    def __init__(self, id: str, session_id: str, content: str, role: str, timestamp: Optional[float] = None):
        self.id = id
        self.session_id = session_id
        self.content = content
        self.role = role
        self.timestamp = timestamp or datetime.now().timestamp()

class Session:
    def __init__(self, id: str, name: str, timestamp: Optional[float] = None, tags: Optional[List[str]] = None):
        self.id = id
        self.name = name
        self.timestamp = timestamp or datetime.now().timestamp()
        self.tags = tags or []
        self.starred = False

class Storage:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_storage()
        return cls._instance
    
    def _init_storage(self):
        self.sessions: Dict[str, Session] = {}
        self.messages: Dict[str, List[Message]] = {}
        self._load_from_disk()
    
    def _load_from_disk(self):
        if os.path.exists("sessions.json"):
            with open("sessions.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for session_data in data.get("sessions", []):
                    self.sessions[session_data["id"]] = Session(**session_data)
        
        if os.path.exists("messages.json"):
            with open("messages.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for session_id, msg_list in data.items():
                    self.messages[session_id] = [Message(**m) for m in msg_list]
    
    def _save_to_disk(self):
        sessions_data = [
            {"id": s.id, "name": s.name, "timestamp": s.timestamp, "tags": s.tags, "starred": s.starred}
            for s in self.sessions.values()
        ]
        with open("sessions.json", "w", encoding="utf-8") as f:
            json.dump({"sessions": sessions_data}, f)
        
        messages_data = {
            session_id: [
                {"id": m.id, "session_id": m.session_id, "content": m.content, "role": m.role, "timestamp": m.timestamp}
                for m in msgs
            ]
            for session_id, msgs in self.messages.items()
        }
        with open("messages.json", "w", encoding="utf-8") as f:
            json.dump(messages_data, f)
    
    def create_session(self, name: str) -> Session:
        session_id = f"session_{datetime.now().timestamp()}"
        session = Session(id=session_id, name=name)
        self.sessions[session_id] = session
        self.messages[session_id] = []
        self._save_to_disk()
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> List[Session]:
        return sorted(self.sessions.values(), key=lambda x: x.timestamp, reverse=True)
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        if session_id not in self.sessions:
            return False
        session = self.sessions[session_id]
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.timestamp = datetime.now().timestamp()
        self._save_to_disk()
        return True
    
    def delete_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        del self.sessions[session_id]
        if session_id in self.messages:
            del self.messages[session_id]
        self._save_to_disk()
        return True
    
    def add_message(self, session_id: str, content: str, role: str) -> Message:
        if session_id not in self.sessions:
            raise ValueError("Session not found")
        
        message_id = f"msg_{datetime.now().timestamp()}"
        message = Message(id=message_id, session_id=session_id, content=content, role=role)
        self.messages[session_id].append(message)
        self._save_to_disk()
        
        if len(self.messages[session_id]) == 1:
            self.sessions[session_id].name = content[:50] + "..." if len(content) > 50 else content
            self._save_to_disk()
        
        return message
    
    def get_messages(self, session_id: str) -> List[Message]:
        return self.messages.get(session_id, [])
    
    def delete_message(self, session_id: str, message_id: str) -> bool:
        if session_id not in self.messages:
            return False
        messages = self.messages[session_id]
        for i, msg in enumerate(messages):
            if msg.id == message_id:
                del messages[i]
                self._save_to_disk()
                return True
        return False

storage = Storage()