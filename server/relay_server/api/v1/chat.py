"""
Chat API - 聊天模块 API

提供会话管理和消息处理功能
"""

import json
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ...database.connection import get_db
from ...database.models import Session, Message, User
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc, asc

router = APIRouter(prefix="/chat", tags=["chat"])

# ========== 模型定义 ==========

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = "新会话"
    session_type: Optional[str] = "chat"
    user_id: Optional[int] = None

class CreateMessageRequest(BaseModel):
    """创建消息请求"""
    session_id: str
    content: str
    role: str = "user"
    content_type: Optional[str] = "text"
    user_id: Optional[int] = None

class UpdateSessionRequest(BaseModel):
    """更新会话请求"""
    title: Optional[str] = None
    is_pinned: Optional[bool] = None

class SessionResponse(BaseModel):
    """会话响应"""
    id: int
    session_id: str
    title: str
    session_type: str
    message_count: int
    is_active: bool
    is_pinned: bool
    created_at: str
    updated_at: str
    last_message_at: Optional[str]

class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    message_id: str
    session_id: int
    role: str
    content: str
    content_type: str
    model: Optional[str]
    created_at: str

# ========== 会话管理 ==========

@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    user_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(True),
    db: DBSession = Depends(get_db)
):
    """获取会话列表"""
    query = db.query(Session)
    
    if user_id is not None:
        query = query.filter(Session.user_id == user_id)
    if is_active is not None:
        query = query.filter(Session.is_active == is_active)
    
    sessions = query.order_by(desc(Session.updated_at)).all()
    
    return [session_to_response(s) for s in sessions]

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: DBSession = Depends(get_db)):
    """获取单个会话"""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return session_to_response(session)

@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest, db: DBSession = Depends(get_db)):
    """创建新会话"""
    new_session = Session(
        session_id=str(uuid.uuid4()),
        title=request.title or "新会话",
        session_type=request.session_type or "chat",
        user_id=request.user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return session_to_response(new_session)

@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    db: DBSession = Depends(get_db)
):
    """更新会话"""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if request.title is not None:
        session.title = request.title
    if request.is_pinned is not None:
        session.is_pinned = request.is_pinned
    
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    return session_to_response(session)

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    """删除会话"""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session.is_active = False
    session.updated_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "session_id": session_id}

# ========== 消息管理 ==========

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    limit: int = Query(default=100, le=500),
    db: DBSession = Depends(get_db)
):
    """获取会话消息"""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages = db.query(Message)\n        .filter(Message.session_id == session.id)\n        .order_by(asc(Message.created_at))\n        .limit(limit)\n        .all()
    
    return [message_to_response(m) for m in messages]

@router.post("/messages", response_model=MessageResponse)
async def create_message(request: CreateMessageRequest, db: DBSession = Depends(get_db)):
    """创建消息"""
    session = db.query(Session).filter(Session.session_id == request.session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    new_message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session.id,
        user_id=request.user_id,
        role=request.role,
        content=request.content,
        content_type=request.content_type or "text",
        created_at=datetime.utcnow(),
    )
    
    db.add(new_message)
    session.message_count = session.message_count + 1
    session.last_message_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_message)
    
    return message_to_response(new_message)

@router.delete("/messages/{message_id}")
async def delete_message(message_id: str, db: DBSession = Depends(get_db)):
    """删除消息"""
    message = db.query(Message).filter(Message.message_id == message_id).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    session_id = message.session_id
    message.is_hidden = True
    db.commit()
    
    session = db.query(Session).filter(Session.id == session_id).first()
    if session:
        session.message_count = session.message_count - 1
        db.commit()
    
    return {"success": True, "message_id": message_id}

# ========== AI 聊天接口 ==========

class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str
    message: str
    model: Optional[str] = "gpt4"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4000
    user_id: Optional[int] = None

class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message_id: str
    content: str
    model: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: DBSession = Depends(get_db)):
    """发送聊天消息并获取AI响应"""
    session = db.query(Session).filter(Session.session_id == request.session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 创建用户消息
    user_message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session.id,
        user_id=request.user_id,
        role="user",
        content=request.message,
        content_type="text",
        model=request.model,
        created_at=datetime.utcnow(),
    )
    db.add(user_message)
    
    # 模拟AI响应
    ai_response = generate_ai_response(request.message)
    
    # 创建AI消息
    ai_message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session.id,
        user_id=request.user_id,
        role="assistant",
        content=ai_response,
        content_type="text",
        model=request.model,
        created_at=datetime.utcnow(),
    )
    db.add(ai_message)
    
    # 更新会话
    session.message_count = session.message_count + 2
    session.last_message_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ai_message)
    
    return {
        "success": True,
        "message_id": ai_message.message_id,
        "content": ai_message.content,
        "model": request.model,
    }

def generate_ai_response(prompt: str) -> str:
    """生成模拟AI响应"""
    responses = [
        f"这是一个很好的问题！关于「{prompt[:20]}...」，我的分析如下：\n\n1. 首先需要明确核心需求\n2. 然后评估可用资源\n3. 最后制定实施计划\n\n如果需要更详细的信息，请告诉我！",
        
        f"好的，我来帮你分析这个问题。\n\n根据你的描述，主要涉及以下几个方面：\n\n- 问题分析\n- 解决方案探索\n- 实施建议\n\n需要我深入解释哪个部分？",
        
        f"理解你的需求了。以下是针对「{prompt[:20]}...」的建议：\n\n```python\ndef solve_problem(input_data):\n    # 处理逻辑\n    result = process(input_data)\n    return result\n```\n\n这个方案应该能满足你的需求。",
        
        f"我来详细解答你的问题。\n\n**核心要点：**\n- 关键点一：明确目标\n- 关键点二：制定策略\n- 关键点三：执行验证\n\n如果有任何疑问，请随时问我！",
    ]
    
    # 根据prompt长度选择响应
    index = len(prompt) % len(responses)
    return responses[index]

# ========== 辅助函数 ==========

def session_to_response(session: Session) -> SessionResponse:
    """会话模型转响应"""
    return SessionResponse(
        id=session.id,
        session_id=session.session_id,
        title=session.title,
        session_type=session.session_type,
        message_count=session.message_count,
        is_active=session.is_active,
        is_pinned=session.is_pinned,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        last_message_at=session.last_message_at.isoformat() if session.last_message_at else None,
    )

def message_to_response(message: Message) -> MessageResponse:
    """消息模型转响应"""
    return MessageResponse(
        id=message.id,
        message_id=message.message_id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        content_type=message.content_type,
        model=message.model,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )