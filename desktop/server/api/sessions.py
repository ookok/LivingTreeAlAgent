"""
API endpoints for session management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from core.store import storage

router = APIRouter()

class SessionCreate(BaseModel):
    name: str

class SessionUpdate(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    starred: Optional[bool] = None

class SessionResponse(BaseModel):
    id: str
    name: str
    timestamp: float
    tags: List[str]
    starred: bool

@router.post("/", response_model=SessionResponse)
async def create_session(data: SessionCreate):
    session = storage.create_session(data.name)
    return SessionResponse(
        id=session.id,
        name=session.name,
        timestamp=session.timestamp,
        tags=session.tags,
        starred=session.starred
    )

@router.get("/", response_model=List[SessionResponse])
async def get_all_sessions():
    sessions = storage.get_all_sessions()
    return [
        SessionResponse(
            id=s.id,
            name=s.name,
            timestamp=s.timestamp,
            tags=s.tags,
            starred=s.starred
        )
        for s in sessions
    ]

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        id=session.id,
        name=session.name,
        timestamp=session.timestamp,
        tags=session.tags,
        starred=session.starred
    )

@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, data: SessionUpdate):
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.tags is not None:
        update_data["tags"] = data.tags
    if data.starred is not None:
        update_data["starred"] = data.starred
    
    success = storage.update_session(session_id, **update_data)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = storage.get_session(session_id)
    return SessionResponse(
        id=session.id,
        name=session.name,
        timestamp=session.timestamp,
        tags=session.tags,
        starred=session.starred
    )

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    success = storage.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}