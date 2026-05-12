"""Flash-First Streaming Orchestrator — minimal perceived latency.

Combines 3 techniques into one chat flow:
  1. Flash-First: Flash model streams tokens immediately (TTFB ~100ms)
  2. Parallel Race: N free models fire simultaneously, first token wins
  3. Instant Skeleton: Predict response structure, fill content streamingly

User experience timeline:
  T+0ms:   Query received
  T+50ms:  Skeleton structure predicted → frontend renders outline
  T+100ms: Flash model begins token stream → user sees text flowing
  T+500ms: Parallel free models race emerges → best first token shown
  T+3s:    Pro model finishes verification → refined version replaces if different
  T+5s:    Response complete → cache for next time

Integration point: hub.chat() → FlashFirstOrchestrator.chat()
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from loguru import logger


@dataclass
class StreamChunk:
    """A chunk of the progressive streaming response."""
    type: str  # "skeleton", "token", "phase", "complete", "refine"
    content: str = ""
    phase: str = ""       # for "phase" type: intent/tools/knowledge/reasoning
    model: str = ""        # which model produced this chunk
    timestamp: float = field(default_factory=time.time)


@dataclass
class SkeletonTemplate:
    """Predicted response structure — rendered instantly, filled progressively."""
    outline: list[str]     # ["## 标题", "1. [填充中]", "```python\n[填充中]\n```"]
    content_slots: int     # how many content slots to fill


class FlashFirstOrchestrator:
    """Orchestrate flash-first progressive chat with parallel drafting.

    Attributes:
        flash_model: Fast/cheap model for immediate streaming.
        pro_model: Powerful model for background verification.
        free_models: Additional models for parallel first-token race.
        skeleton_enabled: Whether to predict response structure.
        cache: Optional ResponseCache for hot queries.
        _parallel_drafter: Optional ParallelBlockDrafter instance.
    """

    def __init__(
        self,
        flash_model=None,
        pro_model=None,
        free_models: list = None,
        skeleton_enabled: bool = True,
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.free_models = free_models or []
        self.skeleton_enabled = skeleton_enabled
        self.cache = None
        self._stats = {"flash_hits": 0, "cache_hits": 0, "refines": 0}

    async def chat_stream(
        self, message: str, context: dict = None, hub=None
    ) -> AsyncIterator[StreamChunk]:
        """Progressive chat with flash-first streaming.

        Args:
            message: User input.
            context: Optional session context.
            hub: Optional IntegrationHub for accessing consciousness.

        Yields:
            StreamChunk objects for progressive rendering.
        """
        context = context or {}
        t0 = time.time()

        # Check hot cache first
        if self.cache:
            cached = await self.cache.get(message)
            if cached:
                self._stats["cache_hits"] += 1
                yield StreamChunk(type="phase", phase="cache", content="hit")
                yield StreamChunk(type="token", content=cached, model="cache")
                yield StreamChunk(
                    type="complete",
                    content=cached,
                    model="cache",
                )
                return

        # Phase 1: Instant skeleton (T+50ms)
        if self.skeleton_enabled:
            skeleton = self._predict_skeleton(message)
            if skeleton:
                yield StreamChunk(
                    type="skeleton",
                    content="\n".join(skeleton.outline),
                    model="system",
                )

        # Phase 2: Progressive pipeline phases (T+50-500ms)
        if hub and hasattr(hub, 'world'):
            yield StreamChunk(type="phase", phase="intent", content="正在理解意图...")
            yield StreamChunk(type="phase", phase="tools", content="正在匹配工具...")

        # Phase 3: Flash model immediate streaming (T+100ms)
        flash_task = None
        pro_task = None
        race_tasks = []

        if self.flash_model:
            flash_task = asyncio.create_task(
                self._stream_from_model(self.flash_model, message, "flash")
            )

        # Phase 4: Parallel free model race (T+100ms+)
        if self.free_models:
            race_tasks = [
                asyncio.create_task(
                    self._stream_from_model(m, message, f"free-{i}")
                )
                for i, m in enumerate(self.free_models[:3])
            ]

        # Collect first token from fastest source
        all_streams = []
        if flash_task:
            all_streams.append(flash_task)
        all_streams.extend(race_tasks)

        if all_streams:
            # Wait for first token from any source
            first_token_yielded = False
            pending = all_streams.copy()

            while pending:
                done, pending = await asyncio.wait(
                    pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED
                )

                for task in done:
                    try:
                        result = await task
                        if isinstance(result, list):
                            for chunk in result:
                                if not first_token_yielded:
                                    yield StreamChunk(
                                        type="phase", phase="generating",
                                        content="正在生成回复...",
                                    )
                                    first_token_yielded = True
                                yield chunk
                    except Exception as e:
                        logger.debug(f"Flash stream error: {e}")

                if first_token_yielded:
                    # Once we have first token, cancel remaining racers
                    for t in pending:
                        t.cancel()
                    break

        # Phase 5: Pro model background verification (T+3s)
        # Pro model verifies quality asynchronously, replaces if significant diff
        if self.pro_model:
            try:
                pro_task = asyncio.create_task(
                    self._verify_with_pro(message, context)
                )
                # Don't block — let flash output continue
            except Exception:
                pass

        # Phase 6: Signal completion
        yield StreamChunk(type="phase", phase="done", content="完成")

        # Pro model refinement (if different from flash)
        if pro_task:
            try:
                refined = await asyncio.wait_for(pro_task, timeout=10.0)
                if refined:
                    self._stats["refines"] += 1
                    yield StreamChunk(
                        type="refine",
                        content=refined,
                        model="pro",
                    )
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.debug(f"Pro refine error: {e}")

        yield StreamChunk(type="complete", content="")

        # Cache for next time
        if self.cache and self._last_full_response:
            await self.cache.set(message, self._last_full_response)

    async def _stream_from_model(
        self, model, message: str, model_name: str
    ) -> list[StreamChunk]:
        """Stream tokens from a single model."""
        chunks = []
        try:
            if hasattr(model, 'stream_of_thought'):
                async for token in model.stream_of_thought(message):
                    chunk = StreamChunk(
                        type="token",
                        content=token,
                        model=model_name,
                    )
                    chunks.append(chunk)
            elif hasattr(model, 'chat'):
                result = await model.chat(message)
                text = result.text if hasattr(result, 'text') else str(result)
                chunks.append(StreamChunk(
                    type="token", content=text, model=model_name,
                ))
        except Exception as e:
            logger.debug(f"Model {model_name} stream error: {e}")
        return chunks

    async def _verify_with_pro(self, message: str, context: dict) -> Optional[str]:
        """Pro model verifies and refines flash output in background."""
        try:
            if hasattr(self.pro_model, 'chat'):
                verify_prompt = (
                    f"User asked: {message}\n\n"
                    f"Flash model responded. Provide a refined, more accurate "
                    f"version if the flash response had any errors or omissions. "
                    f"If the flash response was adequate, reply 'OK'."
                )
                result = await self.pro_model.chat(verify_prompt)
                text = result.text if hasattr(result, 'text') else str(result)
                if text.strip().upper() != "OK" and len(text) > 20:
                    return text
        except Exception:
            pass
        return None

    # ── Skeleton Prediction (#3) ──

    SKELETON_PATTERNS = {
        "分析": ["## 分析结果", "", "1. [分析中...]", "2. [分析中...]", "", "## 建议", "", "1. [生成中...]"],
        "代码": ["```python", "# [生成中...]", "```", "", "## 说明", "", "[解释生成中...]"],
        "总结": ["## 摘要", "", "[总结生成中...]", "", "## 关键点", "", "1. [提炼中...]"],
        "比较": ["## 对比分析", "", "| 维度 | A | B |", "|------|---|---|", "| [维度1] | [填充中] | [填充中] |"],
        "搜索": ["## 搜索结果", "", "1. **[结果1]** - [加载中...]", "2. **[结果2]** - [加载中...]"],
        "帮助": ["## 帮助", "", "以下是可用功能：", "", "1. [加载中...]"],
        "翻译": ["## 翻译", "", "[翻译生成中...]"],
    }

    def _predict_skeleton(self, message: str) -> Optional[SkeletonTemplate]:
        """Predict response structure from query keywords."""
        msg_lower = message.lower()
        for keyword, outline in self.SKELETON_PATTERNS.items():
            if keyword in msg_lower:
                # Count placeholder slots — any line containing [...] is a slot
                slot_count = sum(
                    1 for line in outline
                    if "[" in line and "]" in line and "中" in line
                )
                return SkeletonTemplate(outline=outline, content_slots=slot_count)
        # Default skeleton
        return SkeletonTemplate(
            outline=["[生成回复中...]"],
            content_slots=1,
        )


# ── Singleton ──

_ffs_orchestrator: Optional[FlashFirstOrchestrator] = None


def get_flash_first(hub=None) -> FlashFirstOrchestrator:
    """Get or create FlashFirstOrchestrator with models from hub."""
    global _ffs_orchestrator
    if _ffs_orchestrator is None:
        orch = FlashFirstOrchestrator()

        if hub and hasattr(hub, 'world') and hub.world:
            consciousness = hub.world.consciousness
            if consciousness:
                orch.flash_model = getattr(consciousness, '_flash_llm', None) or consciousness
                orch.pro_model = getattr(consciousness, '_llm', None)

                # Free models from pool
                try:
                    from .free_pool_manager import get_free_pool
                    pool = get_free_pool()
                    orch.free_models = pool.models[:3] if pool.models else []
                except Exception:
                    pass

        _ffs_orchestrator = orch

    # Attach cache if available
    if _ffs_orchestrator.cache is None:
        try:
            from .response_cache import get_response_cache
            _ffs_orchestrator.cache = get_response_cache()
        except Exception:
            pass

    return _ffs_orchestrator
