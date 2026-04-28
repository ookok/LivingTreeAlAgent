"""
Agent 进度反馈系统测试
======================

测试内容：
1. 进度回调机制
2. 流式 thinking 输出
3. 任务分解执行
"""

import sys
sys.path.insert(0, '.')

import time
import threading
from core.agent_progress import (
    AgentProgress,
    AgentProgressCallback,
    ProgressEmitter,
    ProgressPhase,
    get_progress_tracker
)


def demo_progress_callback():
    """演示进度回调"""
    print("=" * 60)
    print("【演示1】进度回调机制")
    print("=" * 60)
    
    # 创建回调
    def on_progress(prog: AgentProgress):
        bar = "=" * (prog.percent // 5) + "-" * (20 - prog.percent // 5)
        print(f"\r[{bar}] {prog.percent:3d}% | {prog.message}", end="", flush=True)
        if prog.thinking:
            # 只显示最后 30 字
            thinking_short = prog.thinking[-30:] if len(prog.thinking) > 30 else prog.thinking
            print(f"\n   [TH] {thinking_short}", end="", flush=True)
    
    # 模拟进度
    emitter = ProgressEmitter(on_progress)
    emitter.start()
    
    time.sleep(0.3)
    emitter.emit_phase(ProgressPhase.INTENT_CLASSIFY, "正在分析意图...")
    time.sleep(0.5)
    
    emitter.emit_phase(ProgressPhase.KNOWLEDGE_SEARCH, "搜索知识库...")
    time.sleep(0.5)
    
    emitter.emit_phase(ProgressPhase.DEEP_SEARCH, "执行深度搜索...")
    time.sleep(0.5)
    
    emitter.emit_phase(ProgressPhase.LLM_GENERATING, "正在生成回复...")
    # 模拟 thinking 输出
    for i in range(10):
        emitter.emit_thinking(f"思考内容{i}... ")
        time.sleep(0.1)
    
    emitter.complete("回答已生成")
    print()  # 换行


def demo_progress_tracker():
    """演示全局进度跟踪器"""
    print("\n" + "=" * 60)
    print("【演示2】全局进度跟踪器")
    print("=" * 60)
    
    tracker = get_progress_tracker()
    
    def on_progress(prog: AgentProgress):
        print(f"[{prog.phase.value}] {prog.percent}%: {prog.message}")
    
    tracker.add_callback(on_progress)
    
    # 模拟处理
    emitter = ProgressEmitter(tracker.emit)
    emitter.start()
    
    for phase in [ProgressPhase.INTENT_CLASSIFY, ProgressPhase.KNOWLEDGE_SEARCH, 
                  ProgressPhase.DEEP_SEARCH, ProgressPhase.LLM_GENERATING]:
        time.sleep(0.2)
        emitter.emit_phase(phase, f"正在{phase.value}...")
    
    emitter.complete()
    tracker.remove_callback(on_progress)


def demo_task_decomposition():
    """演示任务分解执行"""
    print("\n" + "=" * 60)
    print("【演示3】任务分解执行")
    print("=" * 60)
    
    from core.task_queue import TaskQueue, QueuePriority, TaskState
    
    queue = TaskQueue(name="test", max_concurrent=2, persist=False)
    
    # 定义子任务
    def search_task(query: str) -> str:
        print(f"  [S] 执行搜索: {query}")
        time.sleep(0.5)
        return f"搜索结果: {query}"
    
    def analyze_task(data: str) -> str:
        print(f"  [A] 执行分析: {data}")
        time.sleep(0.5)
        return f"分析结果: {data}"
    
    def report_task(results: list) -> str:
        print(f"  [R] 生成报告: {len(results)} 项")
        time.sleep(0.3)
        return f"报告完成，共 {len(results)} 项"
    
    # 分解任务
    print("分解任务: 搜索 → 分析 → 报告")
    print("-" * 40)
    
    # 添加并行任务
    task1_id = queue.add(
        title="搜索任务1",
        handler=search_task,
        query="吉奥环朋",
        priority=QueuePriority.HIGH
    )
    
    task2_id = queue.add(
        title="搜索任务2",
        handler=search_task,
        query="人工智能公司",
        priority=QueuePriority.NORMAL
    )
    
    print(f"添加任务1: {task1_id}")
    print(f"添加任务2: {task2_id}")
    
    # 等待并行任务完成
    time.sleep(1.5)
    
    # 添加后续任务
    task3_id = queue.add(
        title="分析任务",
        handler=analyze_task,
        data="搜索结果汇总",
        priority=QueuePriority.HIGH
    )
    
    print(f"添加任务3: {task3_id}")
    time.sleep(1)
    
    # 统计
    stats = queue.get_stats()
    print()
    print("-" * 40)
    print(f"[OK] 统计: 待处理={stats['pending']}, 运行中={stats['running']}, 已完成={stats['completed']}")


def demo_streaming_output():
    """演示流式输出（模拟 LLM thinking）"""
    print("\n" + "=" * 60)
    print("【演示4】流式 thinking 输出")
    print("=" * 60)
    
    def on_progress(prog: AgentProgress):
        # 清屏效果：打印进度条
        if prog.percent > 0:
            bar_len = int(prog.percent / 5)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            thinking = prog.thinking[-40:] if prog.thinking else ""
            print(f"\r  [{bar}] {prog.percent:3d}% ", end="", flush=True)
            if thinking:
                print(f"| [TH] {thinking}", end="", flush=True)
    
    emitter = ProgressEmitter(on_progress)
    emitter.start()
    
    # 模拟 LLM 流式输出
    emitter.emit_phase(ProgressPhase.LLM_GENERATING, "模型生成中...")
    
    thinking_content = "这是一个复杂的推理过程，我需要先理解用户的问题..."
    for char in thinking_content:
        emitter.emit_thinking(char)
        time.sleep(0.02)
    
    emitter.emit_phase(ProgressPhase.FINALIZING, "整理答案...")
    emitter.complete()
    print()


if __name__ == "__main__":
    print("\n" + "=" * 40)
    print("Agent 进度反馈系统测试")
    print("=" * 40 + "\n")
    
    # 测试进度回调
    demo_progress_callback()
    
    # 测试全局跟踪器
    demo_progress_tracker()
    
    # 测试任务分解
    demo_task_decomposition()
    
    # 测试流式输出
    demo_streaming_output()
    
    print("\n" + "=" * 40)
    print("所有演示完成!")
    print("=" * 40)
