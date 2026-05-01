"""
LivingTree AI Agent - Desktop Backend Server

FastAPI backend for AI chat application.
"""

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.sessions import router as sessions_router
from api.messages import router as messages_router
from api.ai import router as ai_router
from core.config import settings

app = FastAPI(title="LivingTree AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(messages_router, prefix="/api/messages", tags=["messages"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )