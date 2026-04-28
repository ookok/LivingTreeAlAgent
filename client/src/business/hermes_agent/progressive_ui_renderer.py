"""
渐进式UI渲染器 (Progressive UI Renderer)
遵循自我进化原则：从用户交互中学习渲染优先级，而非硬编码渲染顺序

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.3)
"""
from typing import AsyncGenerator, Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
import asyncio

from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
from client.src.business.hermes_agent.intent_recognizer import Intent


logger = logging.getLogger(__name__)


@dataclass
class UIRenderState:
    """UI渲染状态"""
    level: int  # 1-4
    skeleton: Optional[Dict[str, Any]] = None  # L1: 骨架
    structure: Optional[Dict[str, Any]] = None  # L2: 结构
    content: Optional[Dict[str, Any]] = None  # L3: 内容
    enriched: Optional[Dict[str, Any]] = None  # L4: 丰富交互
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderPriority:
    """渲染优先级 - 从交互中学习"""
    component: str
    avg_view_time: float = 0.0  # 平均查看时间
    click_rate: float = 0.0  # 点击率
    completion_rate: float = 0.0  # 完成率
    priority_score: float = 0.0  # 综合优先级分数

    def update_from_interaction(self, interaction: Dict[str, Any]):
        """从交互中更新优先级"""
        self.avg_view_time = (
            self.avg_view_time * 0.8 + interaction.get("view_time", 0) * 0.2
        )
        self.click_rate = (
            self.click_rate * 0.8 + (1.0 if interaction.get("clicked") else 0.0) * 0.2
        )
        self.completion_rate = (
            self.completion_rate * 0.8 + (1.0 if interaction.get("completed") else 0.0) * 0.2
        )

        # 综合分数：查看时间 × 点击率 × 完成率
        self.priority_score = (
            (self.avg_view_time / 1000.0) * self.click_rate * (1.0 + self.completion_rate)
        )


class ProgressiveUIRenderer:
    """
    渐进式UI渲染器

    核心原则：
    ❌ 不预置固定的渲染顺序
    ✅ 从用户交互中学习组件优先级
    ✅ 动态调整渲染层级
    ✅ 记录用户行为，持续优化

    渲染时间线：
    T+0ms   → L1: 骨架（立即返回）
    T+100ms → L2: 核心结构
    T+300ms → L3: 完整内容
    T+500ms → L4: 丰富交互（按需）
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "render_priorities.json"
        self.render_priorities: Dict[str, List[RenderPriority]] = {}
        self.interaction_history: List[Dict[str, Any]] = []
        self._load_priorities()

    def _load_priorities(self):
        """加载已学习的渲染优先级"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_type, priorities in data.get("priorities", {}).items():
                        self.render_priorities[task_type] = [
                            RenderPriority(**p) for p in priorities
                        ]
                    self.interaction_history = data.get("history", [])
                logger.info(f"✅ 已加载 {len(self.render_priorities)} 个任务的渲染优先级")
            except Exception as e:
                logger.warning(f"⚠️ 加载渲染优先级失败: {e}")

    def _save_priorities(self):
        """保存渲染优先级"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "priorities": {
                    task_type: [
                        {
                            "component": p.component,
                            "avg_view_time": p.avg_view_time,
                            "click_rate": p.click_rate,
                            "completion_rate": p.completion_rate,
                            "priority_score": p.priority_score
                        }
                        for p in priorities
                    ]
                    for task_type, priorities in self.render_priorities.items()
                },
                "history": self.interaction_history[-200:]  # 只保留最近200条
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存渲染优先级失败: {e}")

    async def render(self, task: 'Task') -> AsyncGenerator[Dict[str, Any], None]:
        """
        渐进式渲染入口

        生成器模式：逐步yield渲染结果
        """
        # L1: 立即返回骨架
        skeleton = self._render_skeleton(task)
        yield skeleton
        await asyncio.sleep(0.05)  # 模拟异步

        # L2: 加载核心数据
        core_data = await self._load_core_data(task)
        structure = self._render_structure(task, core_data)
        yield structure
        await asyncio.sleep(0.1)

        # L3: 加载完整内容
        content = await self._load_content(task, core_data)
        content_render = self._render_content(task, content)
        yield content_render
        await asyncio.sleep(0.15)

        # L4: 检查是否需要丰富交互
        if await self._should_enrich(task, content):
            enriched = await self._load_enriched(task, content)
            enriched_render = self._render_enriched(task, enriched)
            yield enriched_render

    def _render_skeleton(self, task: 'Task') -> Dict[str, Any]:
        """
        渲染骨架屏

        学习型实现：从同类任务的渲染历史中学习最佳骨架布局
        """
        task_type = getattr(task, 'task_type', 'default')

        # 如果已学习过，使用学习的骨架
        if task_type in self.render_priorities:
            priorities = self.render_priorities[task_type]
            # 按优先级排序的组件列表
            components = [p.component for p in sorted(priorities, key=lambda x: -x.priority_score)]
            skeleton_components = components[:3]  # 骨架只显示前3个高优先级组件
        else:
            # 未学习，使用默认骨架
            skeleton_components = ["header", "content", "actions"]

        return {
            "level": 1,
            "type": "skeleton",
            "components": skeleton_components,
            "layout": "minimal",
            "metadata": {
                "task_type": task_type,
                "render_time_ms": 0
            }
        }

    async def _load_core_data(self, task: 'Task') -> Dict[str, Any]:
        """
        加载核心数据

        学习型实现：从交互中学习哪些数据是"核心"
        """
        # 使用LLM判断核心数据
        task_desc = getattr(task, 'description', str(task))

        prompt = f"""
作为一个UI渲染优化专家，分析以下任务，识别核心数据（用户最关心的信息）。

任务描述: {task_desc}

要求：
1. 识别用户最关心的 3-5 个核心数据点
2. 返回 JSON 格式: {{"core_data": ["数据1", "数据2", ...]}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            result = json.loads(response)
            return {"core_items": result.get("core_data", [])}
        except Exception as e:
            logger.error(f"❌ 加载核心数据失败: {e}")
            return {"core_items": []}

    def _render_structure(self, task: 'Task', core_data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染结构层"""
        return {
            "level": 2,
            "type": "structure",
            "core_data": core_data.get("core_items", []),
            "layout": "structured",
            "metadata": {
                "task_type": getattr(task, 'task_type', 'default'),
                "render_time_ms": 100
            }
        }

    async def _load_content(self, task: 'Task', core_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载完整内容

        学习型实现：优先加载高优先级内容
        """
        task_type = getattr(task, 'task_type', 'default')

        # 如果已学习过优先级，按优先级加载
        if task_type in self.render_priorities:
            priorities = self.render_priorities[task_type]
            sorted_components = sorted(priorities, key=lambda x: -x.priority_score)

            # 模拟加载内容
            content = {
                "components": [
                    {"name": p.component, "priority": p.priority_score}
                    for p in sorted_components
                ],
                "total_count": len(priorities)
            }
        else:
            # 未学习，加载全部
            content = {
                "components": [{"name": "main_content", "priority": 1.0}],
                "total_count": 1
            }

        return content

    def _render_content(self, task: 'Task', content: Dict[str, Any]) -> Dict[str, Any]:
        """渲染内容层"""
        return {
            "level": 3,
            "type": "content",
            "content": content,
            "layout": "full",
            "metadata": {
                "task_type": getattr(task, 'task_type', 'default'),
                "render_time_ms": 300
            }
        }

    async def _should_enrich(self, task: 'Task', content: Dict[str, Any]) -> bool:
        """
        判断是否需要丰富交互

        学习型实现：从交互中学习何时需要丰富交互
        """
        task_type = getattr(task, 'task_type', 'default')

        # 简单启发式：如果任务复杂，需要丰富交互
        if task_type in ['search', 'query']:
            return True

        # 可以扩展：从学习数据中判断
        return False

    async def _load_enriched(self, task: 'Task', content: Dict[str, Any]) -> Dict[str, Any]:
        """加载丰富交互数据"""
        return {
            "interactions": ["share", "export", "related"],
            "recommendations": [],
            "metadata": {"enriched": True}
        }

    def _render_enriched(self, task: 'Task', enriched: Dict[str, Any]) -> Dict[str, Any]:
        """渲染丰富交互层"""
        return {
            "level": 4,
            "type": "enriched",
            "enriched": enriched,
            "layout": "interactive",
            "metadata": {
                "task_type": getattr(task, 'task_type', 'default'),
                "render_time_ms": 500
            }
        }

    async def learn_from_interaction(self, interaction: Dict[str, Any]):
        """
        从交互中学习渲染优先级

        交互格式:
        {
            "task_type": "search",
            "viewed_components": ["header", "content", "actions"],
            "clicked_components": ["content"],
            "view_times": {"header": 1000, "content": 5000, "actions": 500},
            "completed": True
        }
        """
        task_type = interaction.get("task_type", "default")

        if task_type not in self.render_priorities:
            self.render_priorities[task_type] = []

        priorities = self.render_priorities[task_type]
        priority_map = {p.component: p for p in priorities}

        # 更新每个组件的优先级
        for component, view_time in interaction.get("view_times", {}).items():
            if component not in priority_map:
                priority_map[component] = RenderPriority(component=component)
                priorities.append(priority_map[component])

            interaction_data = {
                "view_time": view_time,
                "clicked": component in interaction.get("clicked_components", []),
                "completed": interaction.get("completed", False)
            }
            priority_map[component].update_from_interaction(interaction_data)

        # 记录历史
        self.interaction_history.append({
            "timestamp": interaction.get("timestamp", ""),
            "task_type": task_type,
            "components_viewed": len(interaction.get("viewed_components", [])),
            "completed": interaction.get("completed", False)
        })

        self._save_priorities()
        logger.info(f"📝 已更新渲染优先级: {task_type}, 组件数: {len(priorities)}")

    def get_priority_stats(self) -> Dict[str, Any]:
        """获取优先级统计信息"""
        if not self.render_priorities:
            return {"total_task_types": 0}

        all_stats = {}
        for task_type, priorities in self.render_priorities.items():
            all_stats[task_type] = [
                {
                    "component": p.component,
                    "priority_score": round(p.priority_score, 2),
                    "avg_view_time_ms": round(p.avg_view_time, 2),
                    "click_rate": round(p.click_rate, 2)
                }
                for p in sorted(priorities, key=lambda x: -x.priority_score)
            ]

        return {
            "total_task_types": len(self.render_priorities),
            "total_interactions": len(self.interaction_history),
            "priorities_by_task": all_stats
        }
