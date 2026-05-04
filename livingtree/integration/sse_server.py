"""HTTP/SSE Runtime API — Headless agent workflow server.

Inspired by DeepSeek-TUI's `deepseek serve --http`. Starts an HTTP server
with Server-Sent Events for headless agent operations. Accepts tasks via
POST and streams results via SSE.

Usage:
    deepseek serve --http --port 8100
    
    # Client side:
    curl -N -X POST http://localhost:8100/tasks \
      -H "Content-Type: application/json" \
      -d '{"prompt": "fix the bug in auth.py"}'
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from aiohttp import web
from loguru import logger


class SSEAgentServer:
    """HTTP/SSE server for headless agent task execution."""

    def __init__(self, hub: Any = None, port: int = 8100):
        self._hub = hub
        self._port = port
        self._app = web.Application()
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._task_results: dict[str, dict] = {}
        self._setup_routes()

    def _setup_routes(self) -> None:
        self._app.router.add_post("/tasks", self._handle_create_task)
        self._app.router.add_get("/tasks/{task_id}", self._handle_get_task)
        self._app.router.add_get("/tasks/{task_id}/stream", self._handle_stream_task)
        self._app.router.add_get("/tasks", self._handle_list_tasks)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/", self._handle_health)

    async def start(self) -> None:
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        logger.info(f"SSE Agent Server started on http://0.0.0.0:{self._port}")

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "version": "2.1.0",
            "hub_ready": self._hub is not None,
            "active_tasks": len(self._active_tasks),
        })

    async def _handle_create_task(self, request: web.Request) -> web.Response:
        if not self._hub:
            return web.json_response({"error": "Hub not ready"}, status=503)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        prompt = body.get("prompt", "")
        if not prompt:
            return web.json_response({"error": "prompt is required"}, status=400)

        task_id = uuid.uuid4().hex[:12]

        task = asyncio.create_task(self._run_agent_task(task_id, prompt, body))
        self._active_tasks[task_id] = task

        return web.json_response({
            "task_id": task_id,
            "status": "accepted",
            "stream_url": f"/tasks/{task_id}/stream",
            "created": datetime.now(timezone.utc).isoformat(),
        }, status=202)

    async def _handle_get_task(self, request: web.Request) -> web.Response:
        task_id = request.match_info["task_id"]
        result = self._task_results.get(task_id)
        if not result:
            return web.json_response({"error": "Task not found"}, status=404)
        return web.json_response(result)

    async def _handle_stream_task(self, request: web.Request) -> web.StreamResponse:
        task_id = request.match_info["task_id"]

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        result = self._task_results.get(task_id, {})
        await response.write(f"data: {json.dumps(result)}\n\n".encode())
        await response.write_eof()
        return response

    async def _handle_list_tasks(self, request: web.Request) -> web.Response:
        return web.json_response({
            "tasks": [
                {"task_id": tid, "status": t.get_name() if not t.done() else "completed"}
                for tid, t in self._active_tasks.items()
            ],
            "completed": list(self._task_results.keys()),
        })

    async def _run_agent_task(self, task_id: str, prompt: str, options: dict) -> None:
        try:
            result = await self._hub.chat(prompt, **options.get("context", {}))
            self._task_results[task_id] = {
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self._task_results[task_id] = {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            self._active_tasks.pop(task_id, None)


def create_sse_server(hub=None, port: int = 8100) -> SSEAgentServer:
    return SSEAgentServer(hub=hub, port=port)
