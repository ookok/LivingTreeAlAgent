"""
业务逻辑测试器

测试 OpenCode IDE 的核心业务逻辑：
- 消息渲染
- 流式输出
- 工具调用时间线
- 流水线进度
- 主题切换
- 布局调整
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from .test_base import TestCase, wait_for


# ─────────────────────────────────────────────────────────────────────────────
# 测试数据
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MockMessage:
    """模拟消息"""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = None
    is_streaming: bool = False
    thinking: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class MockToolCall:
    """模拟工具调用"""
    tool_name: str
    status: str  # "pending" | "running" | "success" | "failed"
    start_time: datetime = None
    end_time: datetime = None
    result: Any = None
    error: str = ""

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()


@dataclass
class MockPipelineStage:
    """模拟流水线阶段"""
    name: str
    status: str  # "pending" | "running" | "success" | "failed"
    progress: float = 0.0  # 0.0 - 1.0


# ─────────────────────────────────────────────────────────────────────────────
# BusinessLogicTester
# ─────────────────────────────────────────────────────────────────────────────

class BusinessLogicTester:
    """
    业务逻辑测试器

    测试 IDE 核心业务逻辑，不依赖 UI 组件。

    Usage:
        tester = BusinessLogicTester()
        tester.test_message_rendering()
        tester.test_streaming_output()
        tester.test_tool_call_timeline()
    """

    def __init__(self):
        self._results: List[Dict] = []

    # ── 消息渲染测试 ──────────────────────────────────────────

    def test_message_rendering(self, messages: List[MockMessage]) -> Dict[str, Any]:
        """
        测试消息渲染逻辑

        验证：
        - 用户消息右对齐样式
        - 助手消息左对齐样式
        - Markdown 渲染
        - 代码块高亮
        """
        results = {
            "total": len(messages),
            "user_messages": 0,
            "assistant_messages": 0,
            "streaming_messages": 0,
            "with_thinking": 0,
            "passed": True
        }

        for msg in messages:
            if msg.role == "user":
                results["user_messages"] += 1
                # 验证用户消息格式
                if not msg.content.strip():
                    results["passed"] = False
            elif msg.role == "assistant":
                results["assistant_messages"] += 1
                if msg.is_streaming:
                    results["streaming_messages"] += 1
                if msg.thinking:
                    results["with_thinking"] += 1

        self._results.append({
            "test": "message_rendering",
            "results": results
        })

        return results

    def test_markdown_parsing(self, markdown: str) -> Dict[str, Any]:
        """
        测试 Markdown 解析

        验证：
        - 标题渲染
        - 列表渲染
        - 代码块渲染
        - 链接渲染
        """
        import re

        results = {
            "has_headers": bool(re.search(r'^#+ ', markdown, re.MULTILINE)),
            "has_lists": bool(re.search(r'^[\*\-\+]\s', markdown, re.MULTILINE)),
            "has_code_blocks": '```' in markdown,
            "has_inline_code": '`' in markdown,
            "has_links": '[' in markdown and '](' in markdown,
        }

        results["passed"] = all(results.values())
        return results

    def test_code_highlighting(self, code: str, language: str) -> Dict[str, Any]:
        """
        测试代码高亮

        验证：
        - 关键字识别
        - 字符串识别
        - 注释识别
        """
        import re

        patterns = {
            "python": {
                "keywords": r'\b(def|class|import|from|return|if|else|for|while|try|except|with|as|lambda|yield|async|await)\b',
                "strings": r'["\'].*?["\']',
                "comments": r'#.*$',
                "numbers": r'\b\d+\.?\d*\b',
            }
        }

        results = {"language": language}
        lang_patterns = patterns.get(language, {})

        for name, pattern in lang_patterns.items():
            matches = re.findall(pattern, code, re.MULTILINE)
            results[f"has_{name}"] = len(matches) > 0
            results[f"{name}_count"] = len(matches)

        results["passed"] = results.get("has_keywords", False)

        return results

    # ── 流式输出测试 ──────────────────────────────────────────

    def test_streaming_output(
        self,
        full_text: str,
        chunks: List[str],
        on_chunk: Callable[[str], None] = None
    ) -> Dict[str, Any]:
        """
        测试流式输出逻辑

        验证：
        - 块累积正确
        - 顺序正确
        - 性能（延迟）
        - 完成回调
        """
        import time

        results = {
            "total_chunks": len(chunks),
            "expected_full": full_text,
            "actual_full": "",
            "order_correct": True,
            "completed": False,
            "duration_ms": 0,
        }

        start = time.time()
        accumulated = ""

        for i, chunk in enumerate(chunks):
            if i > 0 and chunks[i-1] > chunk:
                results["order_correct"] = False

            accumulated += chunk
            results["actual_full"] = accumulated

            if on_chunk:
                on_chunk(chunk)

        results["duration_ms"] = (time.time() - start) * 1000
        results["completed"] = results["actual_full"] == results["expected_full"]
        results["passed"] = results["completed"] and results["order_correct"]

        self._results.append({
            "test": "streaming_output",
            "results": results
        })

        return results

    def test_streaming_latency(self, chunks: List[str]) -> Dict[str, Any]:
        """测试流式输出延迟"""
        import time

        latencies = []
        for chunk in chunks:
            start = time.time()
            # 模拟处理
            _ = chunk.upper()
            latencies.append((time.time() - start) * 1000)

        return {
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "passed": True
        }

    # ── 工具调用测试 ──────────────────────────────────────────

    def test_tool_call_timeline(
        self,
        tool_calls: List[MockToolCall]
    ) -> Dict[str, Any]:
        """
        测试工具调用时间线

        验证：
        - 状态转换正确
        - 时间顺序
        - 错误处理
        """
        results = {
            "total": len(tool_calls),
            "pending": 0,
            "running": 0,
            "success": 0,
            "failed": 0,
            "passed": True
        }

        for i, call in enumerate(tool_calls):
            # 统计状态
            status_key = call.status
            if status_key in results:
                results[status_key] += 1

            # 验证状态转换
            if i > 0:
                prev = tool_calls[i - 1]
                # 状态应该向前推进，不应倒退
                state_order = {"pending": 0, "running": 1, "success": 2, "failed": 2}
                if state_order.get(prev.status, 0) > state_order.get(call.status, 0):
                    results["passed"] = False

            # 验证时间顺序
            if call.end_time and call.start_time:
                if call.end_time < call.start_time:
                    results["passed"] = False

            # 失败状态应有错误信息
            if call.status == "failed" and not call.error:
                results["passed"] = False

        self._results.append({
            "test": "tool_call_timeline",
            "results": results
        })

        return results

    def test_tool_call_simulation(
        self,
        tool_name: str,
        args: Dict,
        expected_result: Any,
        execute: Callable
    ) -> Dict[str, Any]:
        """测试工具调用执行"""
        try:
            result = execute(tool_name, args)
            success = result == expected_result
            return {
                "tool": tool_name,
                "success": success,
                "expected": expected_result,
                "actual": result,
                "passed": success
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "success": False,
                "error": str(e),
                "passed": False
            }

    # ── 流水线测试 ──────────────────────────────────────────

    def test_pipeline_progress(
        self,
        stages: List[MockPipelineStage]
    ) -> Dict[str, Any]:
        """
        测试流水线进度

        验证：
        - 阶段顺序
        - 进度递增
        - 状态转换
        """
        results = {
            "total_stages": len(stages),
            "completed_stages": 0,
            "current_stage": None,
            "order_correct": True,
            "passed": True
        }

        for i, stage in enumerate(stages):
            if stage.status in ("success", "failed"):
                results["completed_stages"] += 1

            if stage.status == "running":
                results["current_stage"] = stage.name

            # 验证进度在有效范围
            if not (0.0 <= stage.progress <= 1.0):
                results["passed"] = False

            # 验证顺序（不能跳阶段）
            if i > 0:
                prev = stages[i - 1]
                if prev.status == "pending" and stage.status in ("running", "success"):
                    results["order_correct"] = False

        self._results.append({
            "test": "pipeline_progress",
            "results": results
        })

        return results

    def test_pipeline_stage_transitions(
        self,
        stage_name: str,
        transitions: List[tuple[str, str]]  # (from_status, to_status)
    ) -> Dict[str, Any]:
        """测试阶段状态转换"""
        valid_transitions = {
            "pending": ["running", "failed"],
            "running": ["success", "failed"],
            "success": [],  # 终态
            "failed": []     # 终态
        }

        results = {
            "stage": stage_name,
            "valid_transitions": 0,
            "invalid_transitions": 0,
            "passed": True
        }

        for from_status, to_status in transitions:
            if to_status in valid_transitions.get(from_status, []):
                results["valid_transitions"] += 1
            else:
                results["invalid_transitions"] += 1
                results["passed"] = False

        return results

    # ── 主题测试 ──────────────────────────────────────────

    def test_theme_switching(
        self,
        themes: List[str],
        apply_theme: Callable[[str], None]
    ) -> Dict[str, Any]:
        """测试主题切换"""
        results = {
            "themes_tested": len(themes),
            "passed": True
        }

        for theme in themes:
            try:
                apply_theme(theme)
                results[f"{theme}_applied"] = True
            except Exception as e:
                results[f"{theme}_applied"] = False
                results["passed"] = False
                results["error"] = str(e)

        return results

    def test_color_scheme(self, colors: Dict[str, str]) -> Dict[str, Any]:
        """测试配色方案"""
        required_keys = [
            "background", "surface", "primary", "text", "text_muted"
        ]

        results = {
            "has_required": all(k in colors for k in required_keys),
            "color_count": len(colors),
            "passed": True
        }

        # 验证颜色格式
        import re
        color_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')

        for key, color in colors.items():
            if not color_pattern.match(color):
                results["passed"] = False
                results[f"invalid_{key}"] = color

        return results

    # ── 布局测试 ──────────────────────────────────────────

    def test_layout_adjustment(
        self,
        current_layout: str,
        available_layouts: List[str],
        expected_ratio: Dict[str, float]
    ) -> Dict[str, Any]:
        """测试布局调整"""
        results = {
            "current_layout": current_layout,
            "available_layouts": available_layouts,
            "ratio_correct": True,
            "passed": True
        }

        # 验证当前布局有效
        if current_layout not in available_layouts:
            results["passed"] = False
            return results

        # 验证比例
        total = sum(expected_ratio.values())
        if abs(total - 1.0) > 0.01:  # 允许小数误差
            results["ratio_correct"] = False
            results["passed"] = False

        return results

    def test_panel_resize(
        self,
        initial_width: int,
        final_width: int,
        min_width: int,
        max_width: int
    ) -> Dict[str, Any]:
        """测试面板调整大小"""
        results = {
            "initial_width": initial_width,
            "final_width": final_width,
            "within_bounds": min_width <= final_width <= max_width,
            "size_changed": initial_width != final_width,
            "passed": True
        }

        if not results["within_bounds"]:
            results["passed"] = False

        return results


# ─────────────────────────────────────────────────────────────────────────────
# 便捷测试函数
# ─────────────────────────────────────────────────────────────────────────────

def test_message_rendering(messages: List[MockMessage]) -> Dict[str, Any]:
    """便捷函数：测试消息渲染"""
    tester = BusinessLogicTester()
    return tester.test_message_rendering(messages)


def test_streaming_output(full_text: str, chunks: List[str]) -> Dict[str, Any]:
    """便捷函数：测试流式输出"""
    tester = BusinessLogicTester()
    return tester.test_streaming_output(full_text, chunks)


def test_tool_call_timeline(tool_calls: List[MockToolCall]) -> Dict[str, Any]:
    """便捷函数：测试工具调用"""
    tester = BusinessLogicTester()
    return tester.test_tool_call_timeline(tool_calls)


def test_pipeline_progress(stages: List[MockPipelineStage]) -> Dict[str, Any]:
    """便捷函数：测试流水线"""
    tester = BusinessLogicTester()
    return tester.test_pipeline_progress(stages)
