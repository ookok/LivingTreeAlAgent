"""
Database Models - SQLAlchemy 模型定义
====================================

提供用户、会话、消息等核心数据模型
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(128), unique=True, nullable=False)
    email = Column(String(256), unique=True, nullable=True)
    
    # 认证信息
    password_hash = Column(String(256), nullable=True)  # 第三方用户可为空
    token = Column(String(256), nullable=True, index=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # 用户设置
    display_name = Column(String(256), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    auth_provider = Column(String(32), default="local")  # local, github, google
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # 关系
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    configs = relationship("UserConfig", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self, include_sensitive: bool = False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_sensitive:
            data["token"] = self.token
            data["token_expires_at"] = self.token_expires_at.isoformat() if self.token_expires_at else None
        return data


class Session(Base):
    """会话模型"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # 外键
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    # 会话信息
    title = Column(String(256), default="新会话")
    session_type = Column(String(32), default="chat")  # chat, skill, rag
    
    # 上下文
    context = Column(JSON, default=dict)  # 存储额外上下文
    metadata = Column(JSON, default=dict)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    
    # 统计
    message_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_updated", "updated_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "title": self.title,
            "session_type": self.session_type,
            "is_active": self.is_active,
            "is_pinned": self.is_pinned,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }


class Message(Base):
    """消息模型"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # 外键
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 消息内容
    role = Column(String(16), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    content_type = Column(String(32), default="text")  # text, markdown, code, image
    
    # 元数据
    model = Column(String(64), nullable=True)  # 使用的模型
    tokens_used = Column(Integer, default=0)
    metadata = Column(JSON, default=dict)
    
    # 关联
    related_memories = Column(JSON, default=list)  # 关联的记忆 ID
    related_skills = Column(JSON, default=list)   # 调用的技能
    related_docs = Column(JSON, default=list)      # RAG 检索的文档
    
    # 状态
    is_hidden = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    edit_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)

    # 关系
    session = relationship("Session", back_populates="messages")
    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("idx_message_session_time", "session_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "content_type": self.content_type,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
            "related_memories": self.related_memories,
            "related_skills": self.related_skills,
            "related_docs": self.related_docs,
            "is_hidden": self.is_hidden,
            "is_edited": self.is_edited,
            "edit_count": self.edit_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
        }


class UserConfig(Base):
    """用户配置模型"""
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 外键
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 配置键值
    config_key = Column(String(64), nullable=False)  # app, ollama, model_market, search, agent
    config_data = Column(JSON, default=dict)
    
    # 来源信息
    client_id = Column(String(64), nullable=True)
    platform = Column(String(32), default="unknown")
    version = Column(String(32), default="2.0.0")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="configs")

    __table_args__ = (
        UniqueConstraint("user_id", "config_key", name="uq_user_config_key"),
        Index("idx_config_user", "user_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "config_key": self.config_key,
            "config_data": self.config_data,
            "client_id": self.client_id,
            "platform": self.platform,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RelayStats(Base):
    """中继统计模型"""
    __tablename__ = "relay_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 统计维度
    week_id = Column(String(16), nullable=False, index=True)  # 2026-W16
    client_id = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 统计数据
    patches = Column(JSON, default=list)
    pain_points = Column(JSON, default=list)
    
    # 聚合数据
    total_patches = Column(Integer, default=0)
    total_pain_points = Column(Integer, default=0)
    aggregated = Column(Boolean, default=False)
    
    # 客户端信息
    client_version = Column(String(32), default="2.0.0")
    platform = Column(String(32), default="unknown")
    
    # 时间戳
    generated_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_stats_week_client", "week_id", "client_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "week_id": self.week_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "patches": self.patches,
            "pain_points": self.pain_points,
            "total_patches": self.total_patches,
            "total_pain_points": self.total_pain_points,
            "aggregated": self.aggregated,
            "client_version": self.client_version,
            "platform": self.platform,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
        }


class APIKey(Base):
    """API Key 模型"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 外键
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Key 信息
    key_id = Column(String(32), unique=True, nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    key_name = Column(String(128), nullable=True)
    
    # 权限
    scopes = Column(JSON, default=list)  # chat, memory, skills, rag, admin
    
    # 限制
    rate_limit = Column(Integer, default=60)  # 每分钟请求数
    daily_limit = Column(Integer, default=10000)
    expires_at = Column(DateTime, nullable=True)
    
    # 使用统计
    total_calls = Column(Integer, default=0)
    today_calls = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_revoked = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User")

    __table_args__ = (
        Index("idx_apikey_user_active", "user_id", "is_active"),
    )

    def to_dict(self, include_key: bool = False):
        data = {
            "id": self.id,
            "key_id": self.key_id,
            "key_name": self.key_name,
            "scopes": self.scopes,
            "rate_limit": self.rate_limit,
            "daily_limit": self.daily_limit,
            "total_calls": self.total_calls,
            "today_calls": self.today_calls,
            "is_active": self.is_active,
            "is_revoked": self.is_revoked,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        if include_key:
            data["key"] = f"hbd_{self.key_id}_{'****'}"  # 不返回完整 key
        return data


class WebSocketConnection(Base):
    """WebSocket 连接记录"""
    __tablename__ = "ws_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 连接信息
    connection_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # 外键
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 连接详情
    channel = Column(String(64), default="default")
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    
    # 统计
    messages_sent = Column(Integer, default=0)
    messages_received = Column(Integer, default=0)
    bytes_transferred = Column(Integer, default=0)
    
    # 时间戳
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    last_ping_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_ws_user_active", "user_id", "is_active"),
        Index("idx_ws_channel", "channel", "is_active"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "client_ip": self.client_ip,
            "is_active": self.is_active,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_transferred": self.bytes_transferred,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
        }
