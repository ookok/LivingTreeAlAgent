"""WeChat Work Bot webhook routes — callback URL handler.

GET  → URL verification (echostr)
POST → message handling + auto-reply

Env vars required:
    WEWORK_BOT_TOKEN    - Bot callback token
    WEWORK_BOT_AES_KEY  - Encoding AES key (43 chars base64)
    WEWORK_CORP_ID      - Corp ID
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request, Response
from loguru import logger


def setup_bot_routes(app: FastAPI) -> None:
    """Register WeChat Work bot webhook routes."""

    @app.get("/api/wework/bot")
    async def bot_verify(
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: str = Query(...),
    ):
        """URL verification callback from WeChat Work."""
        from ..integration.wechat_notifier import get_bot

        bot = get_bot()
        if not bot.enabled:
            raise HTTPException(status_code=503, detail="Bot not configured")

        ok, result = bot.verify_url(msg_signature, timestamp, nonce, echostr)
        if not ok:
            logger.warning(f"Bot URL verification failed: {result}")
            raise HTTPException(status_code=403, detail=result)

        logger.info("Bot URL verification succeeded")
        return Response(content=result, media_type="text/plain")

    @app.post("/api/wework/bot")
    async def bot_callback(
        request: Request,
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
    ):
        """Message callback from WeChat Work."""
        from ..integration.wechat_notifier import get_bot

        bot = get_bot()
        if not bot.enabled:
            raise HTTPException(status_code=503, detail="Bot not configured")

        body = await request.body()
        logger.debug(f"Bot callback: {len(body)} bytes")

        reply = await bot.handle_message(msg_signature, timestamp, nonce, body)

        if reply:
            return Response(content=reply, media_type="application/xml")
        else:
            # Return empty success for messages that don't need reply
            return Response(content="success", media_type="text/plain")

    logger.info("WeWork Bot webhook routes registered")
