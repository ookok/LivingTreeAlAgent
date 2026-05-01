"""
API endpoints for message management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from core.store import storage

router = APIRouter()

class MessageCreate(BaseModel):
    content: str
    role: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    content: str
    role: str
    timestamp: float

@router.post("/{session_id}", response_model=MessageResponse)
async def create_message(session_id: str, data: MessageCreate):
    try:
        message = storage.add_message(session_id, data.content, data.role)
        return MessageResponse(
            id=message.id,
            session_id=message.session_id,
            content=message.content,
            role=message.role,
            timestamp=message.timestamp
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

@router.get("/{session_id}", response_model=List[MessageResponse])
async def get_messages(session_id: str):
    messages = storage.get_messages(session_id)
    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            content=m.content,
            role=m.role,
            timestamp=m.timestamp
        )
        for m in messages
    ]

@router.delete("/{session_id}/{message_id}")
async def delete_message(session_id: str, message_id: str):
    success = storage.delete_message(session_id, message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"status": "success"}