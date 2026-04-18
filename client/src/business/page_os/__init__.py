# =================================================================
# PageOS - 人机协同操作系统
# =================================================================
# "浏览器已死，页面永生"
#
# 愿景：让网页不再是信息孤岛，而是可以编程、对话、重组甚至共生的智能体
#
# 架构原则：
# 1. 每个页面是一个进程（PageContainer）- 隔离且可通信
# 2. AI 是内核调度器 - 决定何时注入何种能力
# 3. 用户通过自然语言与页面交互
# 4. 页面可被保存为"可执行快照"
#
# 核心模块：
# - PageContainer: 页面容器（进程抽象）
# - PageAgent: 页面智能体
# - DOMReWriter: 网页实时重写
# - StateSyncHub: 双向状态同步
# - WorkflowEngine: 跨页工作流
# - SkillMarket: 网页技能市场
# - OverlayRenderer: 增强现实叠加
# - ScriptGenerator: 实时代码生成
# =================================================================

from .page_container import PageContainer, PageInfo, PageState
from .page_agent import PageAgent, AgentCapability
from .dom_rewriter import DOMReWriter, RewriteStyle, RewriteResult
from .state_sync import StateSyncHub, SyncChannel, SyncMessage
from .workflow_engine import WorkflowEngine, WorkflowStep, WorkflowContext
from .skill_market import WebSkill, SkillMatcher, SkillExecutor
from .overlay_renderer import OverlayRenderer, OverlayWidget, OverlayData
from .script_generator import ScriptGenerator, GeneratedScript, DOMSnapshot

__all__ = [
    # PageContainer
    'PageContainer',
    'PageInfo',
    'PageState',

    # PageAgent
    'PageAgent',
    'AgentCapability',

    # DOMReWriter
    'DOMReWriter',
    'RewriteStyle',
    'RewriteResult',

    # StateSync
    'StateSyncHub',
    'SyncChannel',
    'SyncMessage',

    # Workflow
    'WorkflowEngine',
    'WorkflowStep',
    'WorkflowContext',

    # SkillMarket
    'WebSkill',
    'SkillMatcher',
    'SkillExecutor',

    # Overlay
    'OverlayRenderer',
    'OverlayWidget',
    'OverlayData',

    # ScriptGenerator
    'ScriptGenerator',
    'GeneratedScript',
    'DOMSnapshot',
]
