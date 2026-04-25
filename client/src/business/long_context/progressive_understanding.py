"""
Phase 4: 渐进式理解 (Progressive Understanding)
================================================

渐进式理解是长上下文处理的最高层次，它整合了前面三个阶段的能力：

Phase 1: 差异化压缩 + 语义分块
Phase 2: 分层混合分析
Phase 3: 多智能体协同

核心特性：
1. 迭代式深度理解 - 多轮渐进深入
2. 跨轮次上下文保持 - 记忆之前理解
3. 知识积累 - 边分析边积累知识
4. 进度可视化 - 显示理解进度
5. 智能路由 - 根据任务选择最优分析路径

使用示例：
```python
from client.src.business.long_context import ProgressiveUnderstanding

# 创建渐进式理解器
understander = ProgressiveUnderstanding()

# 首次理解
result = understander.understand(
    text="长文档内容...",
    task="分析主要观点"
)

# 追加轮次 - 深入理解
follow_up = understander.understand(
    text="补充内容...",
    task="深入分析某个点",
    session_id=result.session_id  # 复用会话
)

# 获取会话状态
status = understander.get_session_status(result.session_id)
print(f"理解进度: {status.progress:.0%}")
print(f"已积累知识: {len(status.knowledge_base)} 条")
```
"""

from .progressive_understanding import (
    ComprehensionPhase,
    ComprehensionState,
    ComprehensionProgress,
    UnderstandingSession,
    UnderstandingContext,
    KnowledgeAccumulator,
    ProgressTracker,
    ProgressiveUnderstanding,
    ProgressiveResult,
    UnderstandingConfig,
    UnderstandingDepth,
    SessionManager,
    create_progressive_understander,
    quick_understand,
)
