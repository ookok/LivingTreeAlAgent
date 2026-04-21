"""
P2P广播发现与通信系统 - 统一调度器
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .models import (
    DeviceInfo, ChatMessage, Conversation, BroadcastMessage,
    DeviceStatus, MessageType, BroadcastCategory, ResponseType,
    SystemConfig, CAPABILITY_TEXT, CAPABILITY_FILE
)

from .discovery import BroadcastDiscovery, MessageProtocol
from .protocol import ChatConnection, NATTraversalHelper, ProtocolHandler
from .chat import ChatSessionManager
from .friends import FriendManager
from .security import CryptoManager, IdentityManager, SecureChannel, AccessControl

logger = logging.getLogger(__name__)


class P2PBroadcastSystem(QObject):
    """P2P广播发现与通信系统"""
    
    device_discovered = pyqtSignal(object)
    device_left = pyqtSignal(str)
    broadcast_received = pyqtSignal(object)
    message_received = pyqtSignal(str, object)
    conversation_updated = pyqtSignal(str)
    friend_request_received = pyqtSignal(object)
    connection_status_changed = pyqtSignal(bool)
    system_status_changed = pyqtSignal(dict)
    
    def __init__(self, config: SystemConfig = None, parent=None):
        super().__init__(parent)
        
        self.config = config or SystemConfig()
        self._device_id = f"{self.config.user_id}_{uuid.uuid4().hex[:8]}"
        
        self._discovery: Optional[BroadcastDiscovery] = None
        self._chat_manager: Optional[ChatSessionManager] = None
        self._friend_manager: Optional[FriendManager] = None
        self._nat_helper: Optional[NATTraversalHelper] = None
        
        self._crypto = CryptoManager()
        self._identity: Optional[IdentityManager] = None
        self._secure_channel: Optional[SecureChannel] = None
        self._access_control = AccessControl()
        
        self._is_running = False
        self._devices: Dict[str, DeviceInfo] = {}
        self._conversations: Dict[str, Conversation] = {}
        self._ai_engine: Optional[Callable] = None
        
        self._config_dir = Path.home() / ".hermes-desktop" / "p2p_config"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_config()
    
    def start(self):
        if self._is_running:
            return
        
        logger.info("Starting P2P Broadcast System...")
        
        self._init_identity()
        
        self._discovery = BroadcastDiscovery(
            user_id=self.config.user_id,
            user_name=self.config.user_name,
            device_name=self.config.device_name,
            capabilities=[CAPABILITY_TEXT, CAPABILITY_FILE],
        )
        self._discovery.device_found.connect(self._on_device_found)
        self._discovery.device_left.connect(self._on_device_left)
        self._discovery.broadcast_received.connect(self._on_broadcast_received)
        self._discovery.start()
        
        db_path = str(self._config_dir / "chat.db")
        self._chat_manager = ChatSessionManager(
            user_id=self.config.user_id,
            user_name=self.config.user_name,
            db_path=db_path,
        )
        self._chat_manager.new_message.connect(self._on_new_message)
        self._chat_manager.conversation_updated.connect(self._on_conversation_updated)
        self._chat_manager.start()
        
        friend_db_path = str(self._config_dir / "friends.db")
        self._friend_manager = FriendManager(
            user_id=self.config.user_id,
            user_name=self.config.user_name,
            db_path=friend_db_path,
        )
        
        self._nat_helper = NATTraversalHelper()
        self._secure_channel = SecureChannel(self._crypto)
        
        if self._ai_engine:
            self._chat_manager.set_ai_engine(self._ai_engine)
        
        self._is_running = True
        self.connection_status_changed.emit(True)
        logger.info(f"P2P Broadcast System started. Device ID: {self._device_id}")
    
    def stop(self):
        if not self._is_running:
            return
        
        logger.info("Stopping P2P Broadcast System...")
        
        if self._discovery:
            self._discovery.stop()
        
        if self._chat_manager:
            self._chat_manager.stop()
        
        self._is_running = False
        self.connection_status_changed.emit(False)
        logger.info("P2P Broadcast System stopped")
    
    def _init_identity(self):
        self._identity = IdentityManager(self._crypto)
        self._identity.create_identity(
            user_id=self.config.user_id,
            user_name=self.config.user_name,
            device_id=self._device_id,
        )
    
    def _on_device_found(self, device: DeviceInfo):
        self._devices[device.device_id] = device
        if self._friend_manager and self._friend_manager.is_friend(device.device_id):
            device.is_friend = True
        self.device_discovered.emit(device)
        if device.is_friend:
            self._friend_manager.update_online_status(device.device_id, DeviceStatus.ONLINE)
    
    def _on_device_left(self, device_id: str):
        if device_id in self._devices:
            device = self._devices[device_id]
            if device.is_friend and self._friend_manager:
                self._friend_manager.update_online_status(device_id, DeviceStatus.OFFLINE)
            del self._devices[device_id]
        self.device_left.emit(device_id)
    
    def _on_broadcast_received(self, broadcast: BroadcastMessage):
        self.broadcast_received.emit(broadcast)
    
    def _on_new_message(self, conv_id: str, message: ChatMessage):
        self.message_received.emit(conv_id, message)
    
    def _on_conversation_updated(self, conv_id: str):
        self.conversation_updated.emit(conv_id)
    
    def get_devices(self) -> List[DeviceInfo]:
        if self._discovery:
            return self._discovery.get_devices()
        return []
    
    def get_online_devices(self) -> List[DeviceInfo]:
        return [d for d in self.get_devices() if d.is_online()]
    
    def get_friends(self) -> List[DeviceInfo]:
        if self._friend_manager:
            return self._friend_manager.get_friends()
        return []
    
    def send_broadcast(self, content: str, category: BroadcastCategory = BroadcastCategory.GENERAL, keywords: List[str] = None, expires_seconds: int = 60) -> str:
        if not self._discovery:
            return ""
        return self._discovery.send_broadcast_message(content=content, category=category, keywords=keywords, expires_seconds=expires_seconds)
    
    def send_message(self, peer_id: str, content: str) -> str:
        if not self._chat_manager:
            return ""
        return self._chat_manager.send_message(peer_id, content)
    
    def get_conversations(self) -> List[Conversation]:
        if self._chat_manager:
            return self._chat_manager.get_conversations()
        return []
    
    def get_messages(self, conv_id: str, limit: int = 100) -> List[ChatMessage]:
        if self._chat_manager:
            return self._chat_manager.get_messages(conv_id, limit)
        return []
    
    def add_friend(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device or not self._friend_manager:
            return False
        device.is_friend = True
        return self._friend_manager.add_friend(device)
    
    def remove_friend(self, device_id: str):
        if self._friend_manager:
            self._friend_manager.remove_friend(device_id)
        if device_id in self._devices:
            self._devices[device_id].is_friend = False
    
    def set_ai_engine(self, engine: Callable):
        self._ai_engine = engine
        if self._chat_manager:
            self._chat_manager.set_ai_engine(engine)
    
    def _load_config(self):
        config_file = self._config_dir / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
    
    def save_config(self):
        config_file = self._config_dir / "config.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._is_running,
            "device_id": self._device_id,
            "online_devices": len(self.get_online_devices()),
            "online_friends": len(self.get_friends()),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "is_running": self._is_running,
            "devices": len(self._devices),
            "online": len([d for d in self._devices.values() if d.is_online()]),
        }
        if self._friend_manager:
            stats["friends"] = self._friend_manager.get_stats()
        if self._chat_manager:
            stats["chat"] = self._chat_manager.get_stats()
        return stats


_system_instance: Optional[P2PBroadcastSystem] = None


def create_p2p_system(config: SystemConfig = None) -> P2PBroadcastSystem:
    global _system_instance
    _system_instance = P2PBroadcastSystem(config)
    return _system_instance


def get_p2p_system() -> Optional[P2PBroadcastSystem]:
    return _system_instance


__all__ = [
    "P2PBroadcastSystem",
    "BroadcastDiscovery",
    "ChatConnection",
    "ChatSessionManager",
    "FriendManager",
    "NATTraversalHelper",
    "ProtocolHandler",
    "CryptoManager",
    "IdentityManager",
    "SecureChannel",
    "AccessControl",
    "DeviceInfo",
    "ChatMessage",
    "Conversation",
    "BroadcastMessage",
    "DeviceStatus",
    "MessageType",
    "BroadcastCategory",
    "ResponseType",
    "SystemConfig",
    "create_p2p_system",
    "get_p2p_system",
]
