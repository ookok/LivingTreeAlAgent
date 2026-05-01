"""
Living Tree AI - 聊天服务主应用

支持 WebSocket 和 HTTP 双重协议，自动降级机制
"""

import os
import sys
import json
import time
import logging
import uvicorn
import uuid
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== FastAPI 应用 ==========

app = FastAPI(
    title="Living Tree AI — Chat Service",
    description="智能聊天服务 - 支持 WebSocket 和 HTTP 协议",
    version="2.0.0",
)

# ========== CORS 中间件 ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 数据库初始化 ==========

DB_DIR = Path.home() / ".hermes-desktop" / "relay_server" / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "chat.db"

import sqlite3

def init_tables():
    """初始化数据库表"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    cursor = conn.cursor()
    
    # 会话表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            title TEXT DEFAULT '新会话',
            session_type TEXT DEFAULT 'chat',
            context TEXT DEFAULT '{}',
            meta_data TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            is_pinned INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP
        )
    """)
    
    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            session_id INTEGER NOT NULL,
            user_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            model TEXT,
            tokens_used INTEGER DEFAULT 0,
            meta_data TEXT DEFAULT '{}',
            related_memories TEXT DEFAULT '[]',
            related_skills TEXT DEFAULT '[]',
            related_docs TEXT DEFAULT '[]',
            is_hidden INTEGER DEFAULT 0,
            is_edited INTEGER DEFAULT 0,
            edit_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    
    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
    
    conn.commit()
    conn.close()

init_tables()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ========== WebSocket 管理器 ==========

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_info: Dict[WebSocket, Dict[str, str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        if client_id:
            self.connection_info[websocket] = {"client_id": client_id}
        logger.info(f"WebSocket connected: {len(self.active_connections)} active connections")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.connection_info.pop(websocket, None)
        logger.info(f"WebSocket disconnected: {len(self.active_connections)} active connections")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast failed: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

# 全局连接管理器
connection_manager = ConnectionManager()

# ========== 协议降级支持 ==========

class ProtocolDetector:
    """协议检测和降级管理器"""
    
    @staticmethod
    async def check_websocket_available(websocket: WebSocket) -> bool:
        """检测 WebSocket 是否可用"""
        try:
            await websocket.accept()
            await websocket.send_json({"type": "protocol_check", "supported": True, "protocol": "websocket"})
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_fallback_protocol() -> str:
        """获取降级协议"""
        return "http"

# ========== 简化的聊天API ==========

class SimpleChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    client_id: Optional[str] = None

@app.get("/api/sessions")
async def get_sessions():
    """获取会话列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE is_active = 1 ORDER BY updated_at DESC")
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "id": row["session_id"],
            "name": row["title"],
            "timestamp": row["updated_at"],
            "starred": row["is_pinned"] == 1,
        })
    conn.close()
    return sessions

class CreateSessionRequest(BaseModel):
    name: str = "新会话"

@app.post("/api/sessions")
async def create_session(request: Optional[CreateSessionRequest] = None, name: str = "新会话"):
    """创建新会话"""
    session_name = request.name if request else name
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, session_name, now, now))
    conn.commit()
    conn.close()
    
    return {"id": session_id, "name": session_name, "timestamp": now}

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET is_active = 0 WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, data: Dict[str, Any]):
    """更新会话"""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    
    if "name" in data:
        updates.append("title = ?")
        params.append(data["name"])
    if "starred" in data:
        updates.append("is_pinned = ?")
        params.append(1 if data["starred"] else 0)
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(session_id)
    
    if updates:
        cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", params)
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/messages/{session_id}")
async def get_messages(session_id: str):
    """获取会话消息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
    session_row = cursor.fetchone()
    
    if not session_row:
        conn.close()
        return []
    
    session_id_int = session_row["id"]
    
    cursor.execute("""
        SELECT * FROM messages 
        WHERE session_id = ? AND is_hidden = 0 
        ORDER BY created_at ASC
    """, (session_id_int,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row["message_id"],
            "session_id": session_id,
            "content": row["content"],
            "role": row["role"],
            "timestamp": row["created_at"],
        })
    conn.close()
    return messages

@app.post("/api/ai/chat")
async def ai_chat(request: SimpleChatRequest):
    """AI聊天接口 (HTTP)"""
    session_id = request.session_id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not session_id:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO sessions (session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, "新会话", now, now))
    
    cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="会话不存在")
    session_id_int = row["id"]
    
    user_message_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO messages (message_id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_message_id, session_id_int, "user", request.message, now))
    
    cursor.execute("""
        UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
        WHERE id = ?
    """, (now, now, session_id_int))
    
    ai_response = generate_ai_response(request.message)
    
    ai_message_id = str(uuid.uuid4())
    ai_now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO messages (message_id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ai_message_id, session_id_int, "assistant", ai_response, ai_now))
    
    cursor.execute("""
        UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
        WHERE id = ?
    """, (ai_now, ai_now, session_id_int))
    
    conn.commit()
    conn.close()
    
    return {"content": ai_response, "session_id": session_id}

@app.post("/api/ai/chat/stream")
async def ai_chat_stream(request: SimpleChatRequest):
    """AI聊天流式接口 (SSE)"""
    session_id = request.session_id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not session_id:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO sessions (session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, "新会话", now, now))
    
    cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="会话不存在")
    session_id_int = row["id"]
    
    user_message_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO messages (message_id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_message_id, session_id_int, "user", request.message, now))
    
    cursor.execute("""
        UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
        WHERE id = ?
    """, (now, now, session_id_int))
    
    ai_response = generate_ai_response(request.message)
    
    ai_message_id = str(uuid.uuid4())
    ai_now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO messages (message_id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ai_message_id, session_id_int, "assistant", ai_response, ai_now))
    
    cursor.execute("""
        UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
        WHERE id = ?
    """, (ai_now, ai_now, session_id_int))
    
    conn.commit()
    conn.close()
    
    async def generate():
        for chunk in ai_response:
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/ai/models")
async def get_models():
    """获取模型列表"""
    return [
        {"id": "gpt4", "name": "GPT-4 Turbo", "provider": "OpenAI"},
        {"id": "gpt3.5", "name": "GPT-3.5 Turbo", "provider": "OpenAI"},
        {"id": "claude3", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gemini", "name": "Gemini Pro", "provider": "Google"},
    ]

@app.get("/api/protocol")
async def get_protocol_info():
    """获取协议支持信息"""
    return {
        "supported_protocols": ["websocket", "http", "sse"],
        "websocket_endpoint": "/ws/chat",
        "http_endpoints": {
            "sessions": "/api/sessions",
            "messages": "/api/messages/{session_id}",
            "chat": "/api/ai/chat",
            "stream": "/api/ai/chat/stream"
        },
        "recommended": "websocket"
    }

# ========== WebSocket 聊天接口 ==========

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, client_id: Optional[str] = None):
    """WebSocket 聊天接口"""
    await connection_manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "message")
            
            if message_type == "message":
                await handle_websocket_message(websocket, data)
            elif message_type == "create_session":
                await handle_create_session(websocket, data)
            elif message_type == "get_sessions":
                await handle_get_sessions(websocket)
            elif message_type == "get_messages":
                await handle_get_messages(websocket, data)
            elif message_type == "delete_session":
                await handle_delete_session(websocket, data)
            elif message_type == "update_session":
                await handle_update_session(websocket, data)
            elif message_type == "ping":
                await connection_manager.send_personal_message(
                    {"type": "pong", "timestamp": time.time()}, websocket
                )
            else:
                await connection_manager.send_personal_message(
                    {"type": "error", "message": f"Unknown message type: {message_type}"}, websocket
                )
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)

async def handle_websocket_message(websocket: WebSocket, data: dict):
    """处理 WebSocket 消息"""
    message = data.get("message", "")
    session_id = data.get("session_id")
    
    if not message:
        await connection_manager.send_personal_message(
            {"type": "error", "message": "Message content is required"}, websocket
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if not session_id:
            session_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO sessions (session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, "新会话", now, now))
        
        cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            await connection_manager.send_personal_message(
                {"type": "error", "message": "会话不存在"}, websocket
            )
            return
        session_id_int = row["id"]
        
        user_message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO messages (message_id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_message_id, session_id_int, "user", message, now))
        
        cursor.execute("""
            UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
            WHERE id = ?
        """, (now, now, session_id_int))
        
        conn.commit()
        
        await connection_manager.send_personal_message({
            "type": "message",
            "id": user_message_id,
            "session_id": session_id,
            "content": message,
            "role": "user",
            "timestamp": now
        }, websocket)
        
        ai_response = generate_ai_response(message)
        
        ai_message_id = str(uuid.uuid4())
        ai_now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO messages (message_id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (ai_message_id, session_id_int, "assistant", ai_response, ai_now))
        
        cursor.execute("""
            UPDATE sessions SET message_count = message_count + 1, last_message_at = ?, updated_at = ? 
            WHERE id = ?
        """, (ai_now, ai_now, session_id_int))
        
        conn.commit()
        
        await connection_manager.send_personal_message({
            "type": "message",
            "id": ai_message_id,
            "session_id": session_id,
            "content": ai_response,
            "role": "assistant",
            "timestamp": ai_now
        }, websocket)
        
    finally:
        conn.close()

async def handle_create_session(websocket: WebSocket, data: dict):
    """处理创建会话请求"""
    name = data.get("name", "新会话")
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, name, now, now))
    conn.commit()
    conn.close()
    
    await connection_manager.send_personal_message({
        "type": "session_created",
        "id": session_id,
        "name": name,
        "timestamp": now
    }, websocket)

async def handle_get_sessions(websocket: WebSocket):
    """处理获取会话列表请求"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE is_active = 1 ORDER BY updated_at DESC")
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "id": row["session_id"],
            "name": row["title"],
            "timestamp": row["updated_at"],
            "starred": row["is_pinned"] == 1,
        })
    conn.close()
    
    await connection_manager.send_personal_message({
        "type": "sessions",
        "data": sessions
    }, websocket)

async def handle_get_messages(websocket: WebSocket, data: dict):
    """处理获取消息请求"""
    session_id = data.get("session_id")
    if not session_id:
        await connection_manager.send_personal_message(
            {"type": "error", "message": "session_id is required"}, websocket
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
    session_row = cursor.fetchone()
    
    if not session_row:
        conn.close()
        await connection_manager.send_personal_message({
            "type": "messages",
            "session_id": session_id,
            "data": []
        }, websocket)
        return
    
    session_id_int = session_row["id"]
    
    cursor.execute("""
        SELECT * FROM messages 
        WHERE session_id = ? AND is_hidden = 0 
        ORDER BY created_at ASC
    """, (session_id_int,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row["message_id"],
            "session_id": session_id,
            "content": row["content"],
            "role": row["role"],
            "timestamp": row["created_at"],
        })
    conn.close()
    
    await connection_manager.send_personal_message({
        "type": "messages",
        "session_id": session_id,
        "data": messages
    }, websocket)

async def handle_delete_session(websocket: WebSocket, data: dict):
    """处理删除会话请求"""
    session_id = data.get("session_id")
    if not session_id:
        await connection_manager.send_personal_message(
            {"type": "error", "message": "session_id is required"}, websocket
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET is_active = 0 WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    
    await connection_manager.send_personal_message({
        "type": "session_deleted",
        "session_id": session_id,
        "success": True
    }, websocket)

async def handle_update_session(websocket: WebSocket, data: dict):
    """处理更新会话请求"""
    session_id = data.get("session_id")
    updates = data.get("updates", {})
    
    if not session_id:
        await connection_manager.send_personal_message(
            {"type": "error", "message": "session_id is required"}, websocket
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    db_updates = []
    params = []
    
    if "name" in updates:
        db_updates.append("title = ?")
        params.append(updates["name"])
    if "starred" in updates:
        db_updates.append("is_pinned = ?")
        params.append(1 if updates["starred"] else 0)
    
    db_updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(session_id)
    
    if db_updates:
        cursor.execute(f"UPDATE sessions SET {', '.join(db_updates)} WHERE session_id = ?", params)
    conn.commit()
    conn.close()
    
    await connection_manager.send_personal_message({
        "type": "session_updated",
        "session_id": session_id,
        "success": True
    }, websocket)

def generate_ai_response(prompt: str) -> str:
    """生成AI响应"""
    responses = [
        f"这是一个很好的问题！关于「{prompt[:20]}...」，我的分析如下：\n\n**核心要点：**\n\n1. 首先需要明确核心需求和目标\n2. 评估现有资源和约束条件\n3. 制定详细的实施计划\n4. 执行并持续优化\n\n如果需要更详细的信息，请告诉我！",
        
        f"好的，我来帮你分析这个问题。\n\n根据你的描述，主要涉及以下几个方面：\n\n**问题分析：**\n- 核心问题识别\n- 潜在影响评估\n- 可行解决方案探索\n\n**实施建议：**\n- 分阶段实施\n- 优先级排序\n- 风险控制\n\n需要我深入解释哪个部分？",
        
        f"理解你的需求了。以下是针对「{prompt[:20]}...」的详细建议：\n\n```python\ndef solve_problem(input_data):\n    \"\"\"解决问题的核心函数\"\"\"\n    # 步骤1: 分析输入\n    analysis = analyze_input(input_data)\n    \n    # 步骤2: 制定方案\n    solution = design_solution(analysis)\n    \n    # 步骤3: 执行实施\n    result = execute_solution(solution)\n    \n    return result\n```\n\n**关键要点：**\n- 模块化设计\n- 错误处理\n- 性能优化\n\n这个方案应该能满足你的需求。",
        
        f"我来详细解答你的问题。\n\n**核心思路：**\n\n1. **明确目标** - 确定最终想要达成的结果\n2. **现状分析** - 评估当前状态和可用资源\n3. **路径规划** - 制定实现路线图\n4. **执行验证** - 逐步实施并验证效果\n\n**注意事项：**\n- 保持灵活性\n- 定期回顾调整\n- 关注关键指标\n\n如果有任何疑问，请随时问我！",
        
        f"关于「{prompt[:20]}...」这个话题，我有以下见解：\n\n**背景知识：**\n- 这是一个常见的问题场景\n- 业界有成熟的解决方案\n- 需要结合具体情况调整\n\n**推荐方案：**\n1. 采用主流技术栈\n2. 参考最佳实践\n3. 持续迭代优化\n\n需要更详细的技术方案吗？",
    ]
    
    index = len(prompt) % len(responses)
    return responses[index]

# ========== 健康检查 ==========
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy", 
        "timestamp": int(time.time()),
        "active_connections": len(connection_manager.active_connections),
        "protocol_support": ["websocket", "http", "sse"]
    }

# ========== 启动 ==========

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8766, log_level="info")