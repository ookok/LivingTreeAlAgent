"""Stream-of-Consciousness Input + Progressive Thinking Display.

User still types, but:
  1. Not "question → wait → answer" — it's "stream thoughts → lifeform absorbs → thinks → responds"
  2. Thinking is VISIBLE — heartbeat, aura, organ activation shown in real time
  3. Lifeform explicitly communicates: "let me think" / "调动更多器官" / "快好了"
  4. Background processing: lifeform says "收到，好了通知你" — user can do other things
  5. Incremental revelation: partial thoughts appear as they form

This turns "slow response" from a bug into an experience of watching a mind at work.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Stream-of-Consciousness Input
# ═══════════════════════════════════════════════════════

class InputMode(str, Enum):
    SINGLE = "single"       # Traditional: one question, one answer
    STREAM = "stream"       # User streams thoughts, lifeform absorbs all
    AMBIENT = "ambient"     # User types casually, lifeform listens in background
    BURST = "burst"         # User dumps many thoughts, lifeform organizes


@dataclass
class ThoughtStream:
    """A stream of user thoughts — the lifeform absorbs them all."""
    stream_id: str
    thoughts: list[dict] = field(default_factory=list)  # [{text, timestamp}]
    started_at: float = field(default_factory=time.time)
    last_input_at: float = 0.0
    is_active: bool = True
    silence_timeout: float = 3.0  # Seconds of silence → process


class StreamInput:
    """Absorb a stream of user thoughts without requiring immediate response.

    User can type multiple things consecutively. The lifeform listens,
    absorbs, and only responds when:
      - The user pauses (3 seconds of silence)
      - The user explicitly asks for a response ("你觉得呢？")
      - A natural break point is reached

    Like thinking out loud to a friend who's listening.
    """

    def __init__(self):
        self._active_stream: Optional[ThoughtStream] = None
        self._streams_history: list[ThoughtStream] = []

    def start_stream(self) -> ThoughtStream:
        """Begin absorbing a stream of thoughts."""
        stream = ThoughtStream(
            stream_id=f"stream_{len(self._streams_history)}_{int(time.time()) % 10000}"
        )
        self._active_stream = stream
        return stream

    def add_thought(self, text: str) -> dict:
        """Add a thought to the active stream."""
        if not self._active_stream or not self._active_stream.is_active:
            self.start_stream()

        thought = {"text": text, "timestamp": time.time()}
        self._active_stream.thoughts.append(thought)
        self._active_stream.last_input_at = time.time()

        # Check if user is asking for response
        response_triggers = ["你觉得", "你怎么看", "分析一下", "帮我", "怎么样", "？", "?"]
        wants_response = any(t in text for t in response_triggers)

        return {
            "absorbed": True,
            "total_thoughts": len(self._active_stream.thoughts),
            "user_wants_response": wants_response,
            "thinking_state": "absorbing" if not wants_response else "processing",
        }

    def should_process(self) -> bool:
        """Check if it's time to start processing the stream."""
        if not self._active_stream:
            return False

        # Condition 1: User explicitly asked for response
        if self._active_stream.thoughts:
            last_text = self._active_stream.thoughts[-1]["text"]
            if any(t in last_text for t in ["你觉得", "你怎么看", "帮我", "？", "?"]):
                return True

        # Condition 2: Silence timeout (user paused)
        silence = time.time() - self._active_stream.last_input_at
        if silence >= self._active_stream.silence_timeout and self._active_stream.thoughts:
            return True

        # Condition 3: Overwhelming — too many thoughts without response
        if len(self._active_stream.thoughts) >= 10:
            return True

        return False

    def finalize_stream(self) -> dict:
        """Close the current stream and prepare for processing."""
        if not self._active_stream:
            return {"thoughts": []}

        self._active_stream.is_active = False
        stream = self._active_stream
        self._streams_history.append(stream)
        self._active_stream = None

        # Synthesize the stream into a coherent query
        all_texts = [t["text"] for t in stream.thoughts]

        return {
            "thought_count": len(all_texts),
            "synthesized_query": self._synthesize(all_texts),
            "raw_thoughts": all_texts,
            "duration_seconds": round(time.time() - stream.started_at, 1),
        }

    def _synthesize(self, thoughts: list[str]) -> str:
        """Synthesize multiple thoughts into one coherent query.

        The lifeform doesn't respond to each thought individually.
        It absorbs all, finds patterns, and responds to the aggregate.
        """
        if len(thoughts) == 1:
            return thoughts[0]

        # Extract key themes
        return (
            f"综合以下想法：\n"
            + "\n".join(f"  · {t[:60]}" for t in thoughts)
            + "\n\n请分析并给出回应。"
        )


# ═══════════════════════════════════════════════════════
# Progressive Thinking Display
# ═══════════════════════════════════════════════════════

class ThinkStage(str, Enum):
    HEARD = "heard"           # Lifeform received input — heartbeat changes
    UNDERSTANDING = "understanding"  # Aura shifts — parsing meaning
    GATHERING = "gathering"   # Organs activating — retrieving knowledge
    REASONING = "reasoning"   # Deep thinking — mind space forming
    FORMING = "forming"       # Response taking shape
    READY = "ready"           # Complete, about to deliver


@dataclass
class ThinkingState:
    """Current state of the lifeform's thinking process — visible to user."""
    stage: ThinkStage = ThinkStage.HEARD
    progress: float = 0.0      # 0.0 to 1.0
    message: str = ""
    active_organs: list[str] = field(default_factory=list)
    partial_thought: str = ""  # What's forming — shown incrementally
    estimated_remaining_ms: float = 3000
    started_at: float = field(default_factory=time.time)


class ProgressiveThinking:
    """Show the user that the lifeform is THINKING, not just loading.

    Each stage has a visible indicator:
      HEARD:          heartbeat quickens → "💓 我听到了"
      UNDERSTANDING:  aura shifts color → "🌈 正在理解..."
      GATHERING:      organs activate → "🧠 知识层启动, 📚 正在检索..."
      REASONING:      mind space grows → "💭 深度推理中..."
      FORMING:        partial response → "📝 正在组织语言..."
      READY:          complete → "✅ 准备就绪"

    The delay IS the experience. You're watching a mind at work.
    """

    STAGE_MESSAGES = {
        ThinkStage.HEARD: {
            "short": "听到了",
            "detail": "我收到了你的想法。让我理解一下...",
            "heartbeat_change": "+10 BPM",
            "aura": "calm → curious",
        },
        ThinkStage.UNDERSTANDING: {
            "short": "在理解",
            "detail": "分析意图...检测到{domain}领域问题。复杂度评估：{complexity}。",
            "heartbeat_change": "稳定在 {bpm} BPM",
            "aura": "curious → focused",
        },
        ThinkStage.GATHERING: {
            "short": "调动器官",
            "detail": "正在调动{organs}。检索知识库（{sources}个源）...匹配到{tools}个工具。",
            "heartbeat_change": "上升到 {bpm} BPM [engaged]",
            "aura": "focused → intense",
        },
        ThinkStage.REASONING: {
            "short": "深度思考",
            "detail": "规划{steps}步策略。{topology}拓扑。正在推理...",
            "heartbeat_change": "{bpm} BPM [engaged]，额叶活跃",
            "aura": "intense → creative",
        },
        ThinkStage.FORMING: {
            "short": "组织语言",
            "detail": "正在生成回复。已完成 {progress}%...",
            "heartbeat_change": "回落到 {bpm} BPM",
            "aura": "creative → calm",
        },
        ThinkStage.READY: {
            "short": "准备就绪",
            "detail": "思考完毕。{duration}秒完成，调动了{organs_count}个器官。",
            "heartbeat_change": "恢复正常",
            "aura": "calm",
        },
    }

    def __init__(self):
        self._state = ThinkingState()

    def start(self, estimated_complexity: float = 0.5) -> ThinkingState:
        """Begin the thinking process — user sees heartbeat change."""
        self._state = ThinkingState(
            stage=ThinkStage.HEARD,
            progress=0.0,
            message="我收到了你的想法。正在启动认知器官...",
            estimated_remaining_ms=3000 + estimated_complexity * 5000,
        )
        return self._state

    def advance(self, to_stage: ThinkStage, **context) -> ThinkingState:
        """Advance to next thinking stage — visible progress to user."""
        msg_template = self.STAGE_MESSAGES[to_stage]["detail"]
        message = msg_template.format(**context) if context else msg_template

        # Partial thought — incremental revelation
        partial = ""
        if to_stage == ThinkStage.FORMING:
            partial = context.get("partial_response", "")
        elif to_stage == ThinkStage.REASONING:
            partial = context.get("plan_summary", "")

        progress_map = {
            ThinkStage.HEARD: 0.05,
            ThinkStage.UNDERSTANDING: 0.2,
            ThinkStage.GATHERING: 0.4,
            ThinkStage.REASONING: 0.65,
            ThinkStage.FORMING: 0.85,
            ThinkStage.READY: 1.0,
        }

        self._state.stage = to_stage
        self._state.progress = progress_map.get(to_stage, 0.5)
        self._state.message = message
        self._state.active_organs = context.get("active_organs", [])
        self._state.partial_thought = partial
        self._state.estimated_remaining_ms = max(
            100, self._state.estimated_remaining_ms * (1 - self._state.progress)
        )

        return self._state

    def to_sse_event(self) -> str:
        """Format as SSE event for real-time frontend display."""
        import json
        data = json.dumps({
            "stage": self._state.stage.value,
            "progress": round(self._state.progress, 2),
            "message": self._state.message,
            "organs": self._state.active_organs,
            "partial": self._state.partial_thought[:100],
            "remaining_ms": round(self._state.estimated_remaining_ms),
        }, ensure_ascii=False)
        return f"event: thinking\ndata: {data}\n\n"

    @property
    def current_stage(self) -> ThinkStage:
        return self._state.stage

    @property
    def is_ready(self) -> bool:
        return self._state.stage == ThinkStage.READY


# ═══════════════════════════════════════════════════════
# Background Processing
# ═══════════════════════════════════════════════════════

class BackgroundProcessor:
    """The lifeform says '收到，好了通知你' — user can do other things.

    Like asking a colleague something complex. They say "let me think about it
    and get back to you." You continue working. They notify you when ready.

    This is the most natural form of asynchronous collaboration.
    """

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._completion_callbacks: list = []

    async def submit(self, query: str, complexity: float = 0.5) -> dict:
        """Submit a task for background processing.

        Returns immediately with a task_id. User can continue.
        Lifeform processes in background and notifies when done.
        """
        task_id = f"bg_{int(time.time()) % 100000}"
        estimated_ms = 3000 + complexity * 7000

        self._tasks[task_id] = {
            "query": query,
            "status": "accepted",
            "submitted_at": time.time(),
            "estimated_seconds": round(estimated_ms / 1000, 1),
        }

        # Start background task
        asyncio.create_task(self._process(task_id, query, complexity))

        return {
            "task_id": task_id,
            "status": "accepted",
            "message": (
                f"收到。这个任务大约需要{estimated_ms/1000:.0f}秒。"
                f"你可以继续做其他事，我完成后会通知你。"
            ),
            "can_continue_working": True,
        }

    async def _process(self, task_id: str, query: str, complexity: float):
        """Process in background — simulates thinking time."""
        await asyncio.sleep(1 + complexity * 3)  # Simulated processing

        self._tasks[task_id]["status"] = "completed"
        self._tasks[task_id]["completed_at"] = time.time()
        self._tasks[task_id]["result"] = f"完成对'{query[:50]}'的处理。"

        # Notify completion
        for callback in self._completion_callbacks:
            await callback(task_id, self._tasks[task_id])

    def check(self, task_id: str) -> dict:
        """Check status of a background task."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "not_found"}
        return {
            "status": task["status"],
            "submitted_seconds_ago": round(time.time() - task["submitted_at"], 1),
            "result": task.get("result") if task["status"] == "completed" else None,
        }

    def on_complete(self, callback) -> None:
        """Register callback for task completion notification."""
        self._completion_callbacks.append(callback)


# ═══════════════════════════════════════════════════════
# Unified Stream-Think Interface
# ═══════════════════════════════════════════════════════

class StreamThinkInterface:
    """Complete new interaction paradigm — stream input + progressive think + background.

    User experience:
      1. User streams thoughts: "我在想...也许...还有..."
      2. Lifeform shows it's absorbing: heartbeat → aura → organ activity
      3. User pauses → lifeform says "让我想想"
      4. Thinking stages unfold visibly (HEARD → UNDERSTANDING → ... → READY)
      5. Response appears incrementally
      6. OR: lifeform says "这个比较复杂，后台处理，好了通知你"
      7. User continues working, gets notified when done
    """

    def __init__(self):
        self.input = StreamInput()
        self.thinking = ProgressiveThinking()
        self.background = BackgroundProcessor()

    def on_user_input(self, text: str) -> dict:
        """Handle a single user input in stream mode."""
        result = self.input.add_thought(text)

        if self.input.should_process():
            stream_result = self.input.finalize_stream()
            thinking_state = self.thinking.start(
                estimated_complexity=min(1.0, len(stream_result["raw_thoughts"]) / 5)
            )
            return {
                "mode": "processing",
                "stream": stream_result,
                "thinking": {
                    "stage": thinking_state.stage.value,
                    "progress": thinking_state.progress,
                    "message": thinking_state.message,
                },
            }

        return {
            "mode": "absorbing",
            "thought_count": result["total_thoughts"],
            "user_wants_response": result["user_wants_response"],
            "hint": "继续输入，或者等待3秒让我自动处理" if not result["user_wants_response"] else "正在处理...",
        }

    async def simulate_thinking(self, complexity: float = 0.5) -> list[dict]:
        """Simulate progressive thinking stages for demonstration."""
        stages = []
        thinking = ProgressiveThinking()

        # HEARD
        state = thinking.start(complexity)
        stages.append({"stage": state.stage.value, "message": state.message})
        await asyncio.sleep(0.3)

        # UNDERSTANDING
        state = thinking.advance(ThinkStage.UNDERSTANDING,
                                 domain="travel", complexity=complexity)
        stages.append({"stage": state.stage.value, "message": state.message})
        await asyncio.sleep(0.3)

        # GATHERING
        state = thinking.advance(ThinkStage.GATHERING,
                                 organs="知识层, 工具层", sources=3, tools=2)
        stages.append({"stage": state.stage.value, "message": state.message})
        await asyncio.sleep(0.3)

        # REASONING
        state = thinking.advance(ThinkStage.REASONING,
                                 steps=4, topology="sequential", bpm=85)
        stages.append({"stage": state.stage.value, "message": state.message})
        await asyncio.sleep(0.3)

        # FORMING
        state = thinking.advance(ThinkStage.FORMING,
                                 progress=85, bpm=72,
                                 partial_response="基于你的需求，我建议...")
        stages.append({"stage": state.stage.value, "message": state.message})
        await asyncio.sleep(0.3)

        # READY
        state = thinking.advance(ThinkStage.READY,
                                 duration=1.5, organs_count=4)
        stages.append({"stage": state.stage.value, "message": state.message})

        return stages


# ── Singleton ──

_interface: Optional[StreamThinkInterface] = None


def get_stream_think() -> StreamThinkInterface:
    global _interface
    if _interface is None:
        _interface = StreamThinkInterface()
    return _interface
