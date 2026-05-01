"""
API endpoints for AI interactions.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: Optional[str] = "default"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2000

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    max_tokens: int

@router.post("/chat")
async def chat(request: ChatRequest):
    async def generate_response():
        responses = [
            "我理解您的问题。",
            "让我思考一下...",
            "根据我的分析，",
            "这是一个很好的问题！",
            "\n\n以下是详细解答：",
            "\n\n1. 首先，需要理解问题的核心",
            "\n2. 然后，分析可能的解决方案",
            "\n3. 最后，选择最佳方案",
            "\n\n如果您有其他问题，请随时提问！",
        ]
        
        for part in responses:
            yield f"data: {part}\n\n"
            await asyncio.sleep(0.3)
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate_response(), media_type="text/event-stream")

@router.get("/models", response_model=list[ModelInfo])
async def get_models():
    models = [
        ModelInfo(id="default", name="默认模型", description="通用AI模型", max_tokens=4096),
        ModelInfo(id="chat", name="聊天模型", description="专门优化的对话模型", max_tokens=8192),
        ModelInfo(id="code", name="代码模型", description="擅长编程相关任务", max_tokens=16384),
        ModelInfo(id="creative", name="创意模型", description="擅长创意写作", max_tokens=4096),
    ]
    return models

@router.get("/config")
async def get_config():
    return {
        "temperature": {"min": 0.0, "max": 2.0, "default": 0.7},
        "max_tokens": {"min": 100, "max": 32000, "default": 2000},
        "top_p": {"min": 0.0, "max": 1.0, "default": 0.9},
        "frequency_penalty": {"min": 0.0, "max": 2.0, "default": 0.0},
        "presence_penalty": {"min": 0.0, "max": 2.0, "default": 0.0},
    }