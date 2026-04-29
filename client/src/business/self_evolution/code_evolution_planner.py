"""
CodeEvolutionPlanner - 代码进化规划器

基于项目结构扫描结果 + 知识摄入，通过 LLM 分析差距，
生成具体的代码改进/新增/重构计划，按优先级排序。

进化类型：
1. NEW_FEATURE - 新增功能模块
2. REFACTOR - 重构优化现有代码
3. BUG_FIX - 修复已知 Bug
4. PERFORMANCE - 性能优化
5. SECURITY - 安全加固
6. TEST_ADD - 添加测试
7. DOC_ADD - 添加文档
8. DEPENDENCY - 依赖更新/添加

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from loguru import logger


class EvolutionType(Enum):
    """进化类型"""
    NEW_FEATURE = "new_feature"
    REFACTOR = "refactor"
    BUG_FIX = "bug_fix"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TEST_ADD = "test_add"
    DOC_ADD = "doc_add"
    DEPENDENCY = "dependency"
    TOOL_REGISTER = "tool_register"


class EvolutionPriority(Enum):
    """进化优先级"""
    CRITICAL = 0    # 紧急：影响核心功能
    HIGH = 1        # 高：重要改进
    MEDIUM = 2      # 中：有价值的优化
    LOW = 3         # 低：锦上添花
    FUTURE = 4      # 未来：储备想法


class EvolutionStatus(Enum):
    """进化状态"""
    PLANNED = "planned"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


@dataclass
class EvolutionAction:
    """单个进化动作"""
    action_id: str
    evolution_type: EvolutionType
    priority: EvolutionPriority
    title: str
    description: str
    target_files: List[str]           # 需要创建/修改的文件
    code_changes: List[Dict[str, str]] = field(default_factory=list)
    # code_changes 格式: [{"file": "path", "action": "create|modify|delete", "content": "...", "description": "..."}]
    dependencies: List[str] = field(default_factory=list)  # 依赖的 package
    required_knowledge: List[str] = field(default_factory=list)  # 依赖的知识 ID
    estimated_impact: str = "medium"  # low / medium / high / critical
    rollback_plan: str = ""
    verification_steps: List[str] = field(default_factory=list)
    status: EvolutionStatus = EvolutionStatus.PLANNED
    result: str = ""
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "evolution_type": self.evolution_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "target_files": self.target_files,
            "code_changes": self.code_changes,
            "dependencies": self.dependencies,
            "required_knowledge": self.required_knowledge,
            "estimated_impact": self.estimated_impact,
            "status": self.status.value,
            "result": self.result,
            "created_at": self.created_at,
        }


@dataclass
class EvolutionPlan:
    """进化计划"""
    plan_id: str
    title: str
    description: str
    created_at: str
    actions: List[EvolutionAction] = field(default_factory=list)
    project_context: str = ""  # 项目结构摘要
    knowledge_context: str = ""  # 相关知识摘要
    status: EvolutionStatus = EvolutionStatus.PLANNED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "actions": [a.to_dict() for a in self.actions],
            "status": self.status.value,
        }

    def get_pending_actions(self) -> List[EvolutionAction]:
        return [a for a in self.actions if a.status in (
            EvolutionStatus.PLANNED, EvolutionStatus.APPROVED
        )]


class CodeEvolutionPlanner:
    """
    代码进化规划器

    工作流程：
    1. 接收项目结构扫描结果（ProjectStructureScanner）
    2. 接收未应用的知识条目（KnowledgeIngestionPipeline）
    3. 接收用户指令/目标
    4. 构建 LLM 提示（上下文：项目结构 + 知识 + 用户目标）
    5. LLM 生成进化计划（结构化 JSON）
    6. 验证和排序进化动作
    7. 返回可执行的 EvolutionPlan

    用法：
        planner = CodeEvolutionPlanner(project_root)
        plan = await planner.create_evolution_plan(
            scan_result=scanner.scan(),
            knowledge=pipeline.get_unapplied_entries(),
            user_goal="增强代码生成能力，集成 OpenCode 风格的代码补全"
        )
    """

    def __init__(self, project_root: str):
        self._root = project_root
        self._logger = logger.bind(component="CodeEvolutionPlanner")
        self._plan_counter = 0

    async def create_evolution_plan(
        self,
        scan_result: Any,  # ScanResult from ProjectStructureScanner
        knowledge_entries: Optional[list] = None,
        user_goal: str = "",
        user_constraints: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        max_actions: int = 10,
    ) -> EvolutionPlan:
        """
        创建进化计划

        Args:
            scan_result: 项目结构扫描结果
            knowledge_entries: 知识条目列表
            user_goal: 用户进化目标
            user_constraints: 用户约束条件
            focus_areas: 关注领域
            max_actions: 最大动作数
        """
        self._plan_counter += 1
        plan_id = f"evo_plan_{self._plan_counter:04d}"
        self._logger.info(f"创建进化计划 #{self._plan_counter}: {user_goal or '自动分析'}")

        # 1. 构建上下文
        project_context = scan_result.to_dict() if hasattr(scan_result, 'to_dict') else str(scan_result)

        knowledge_context = ""
        if knowledge_entries:
            k_lines = []
            for entry in knowledge_entries[:20]:
                k_lines.append(
                    f"- [{entry.knowledge_type.value}] {entry.title}: {entry.summary}"
                )
            knowledge_context = "\n".join(k_lines)

        # 2. 构建提示
        prompt = self._build_planning_prompt(
            project_context=project_context,
            knowledge_context=knowledge_context,
            user_goal=user_goal,
            user_constraints=user_constraints or [],
            focus_areas=focus_areas or [],
            max_actions=max_actions,
        )

        # 3. 调用 LLM
        response = await self._call_llm(prompt)

        # 4. 解析计划
        plan = self._parse_plan_response(
            response, plan_id, user_goal,
            project_context, knowledge_context,
        )

        self._logger.info(f"进化计划已创建: {len(plan.actions)} 个动作")
        return plan

    async def analyze_gap(
        self,
        scan_result: Any,
        target_description: str,
    ) -> List[Dict[str, Any]]:
        """
        分析项目与目标之间的差距

        Args:
            scan_result: 扫描结果
            target_description: 目标描述（如 "支持 OpenCode 风格的代码补全"）

        Returns:
            差距列表
        """
        prompt = f"""你是项目架构分析专家。请分析当前项目与目标之间的差距。

目标: {target_description}

当前项目概况:
- 文件: {scan_result.total_files}
- 代码行: {scan_result.total_lines}
- 类: {scan_result.total_classes}
- 函数: {scan_result.total_functions}
- 已注册工具: {scan_result.registered_tools}
- TODO: {scan_result.todo_count}
- FIXME: {scan_result.fixme_count}

请分析：
1. 缺少哪些关键模块/功能？
2. 现有模块有哪些不足？
3. 需要新增哪些依赖？
4. 代码质量有哪些改进空间？

以 JSON 格式输出:
[
  {{
    "gap": "差距描述",
    "severity": "critical|high|medium|low",
    "suggested_action": "建议动作",
    "affected_modules": ["模块1", "模块2"]
  }}
]"""

        try:
            response = await self._call_llm(prompt)
            gaps = json.loads(response)
            if not isinstance(gaps, list):
                gaps = [gaps]
            return gaps
        except Exception as e:
            self._logger.error(f"差距分析失败: {e}")
            return []

    def _build_planning_prompt(
        self,
        project_context: dict | str,
        knowledge_context: str,
        user_goal: str,
        user_constraints: List[str],
        focus_areas: List[str],
        max_actions: int,
    ) -> str:
        """构建进化规划提示"""
        if isinstance(project_context, dict):
            pc = json.dumps(project_context, ensure_ascii=False, indent=2)[:8000]
        else:
            pc = str(project_context)[:8000]

        constraints_text = "\n".join(f"  - {c}" for c in user_constraints) if user_constraints else "  无特殊约束"
        focus_text = "\n".join(f"  - {f}" for f in focus_areas) if focus_areas else "  全面分析"

        return f"""你是一个高级软件架构师，擅长项目自我进化规划。

## 当前项目概况
{pc}

## 已学习知识
{knowledge_context if knowledge_context else "暂无"}

## 用户目标
{user_goal if user_goal else "自动分析并优化项目"}

## 约束条件
{constraints_text}

## 关注领域
{focus_text}

## 任务
请基于以上信息，生成一个具体的代码进化计划（最多 {max_actions} 个动作）。

每个动作必须包含：
- type: new_feature|refactor|bug_fix|performance|security|test_add|doc_add|dependency|tool_register
- priority: 0(critical)|1(high)|2(medium)|3(low)|4(future)
- title: 动作标题
- description: 详细描述（包含具体实现思路）
- target_files: 需要创建或修改的文件路径列表
- dependencies: 需要安装的 Python 包
- verification_steps: 验证步骤列表

请以 JSON 格式输出：
{{
  "title": "进化计划标题",
  "description": "计划描述",
  "actions": [
    {{
      "action_id": "action_001",
      "type": "new_feature",
      "priority": 1,
      "title": "动作标题",
      "description": "详细描述",
      "target_files": ["path/to/file.py"],
      "dependencies": ["package_name"],
      "required_knowledge": [],
      "estimated_impact": "high",
      "verification_steps": ["步骤1", "步骤2"]
    }}
  ]
}}

只输出 JSON，不要其他文字。重要：动作要具体、可执行，包含足够的细节让执行器能够理解并生成代码。"""

    def _parse_plan_response(
        self,
        response: str,
        plan_id: str,
        user_goal: str,
        project_context: str,
        knowledge_context: str,
    ) -> EvolutionPlan:
        """解析 LLM 返回的进化计划"""
        try:
            # 提取 JSON
            json_match = self._extract_json(response)
            if not json_match:
                return self._create_empty_plan(plan_id, user_goal)

            plan_data = json.loads(json_match)
            actions = []

            for ad in plan_data.get("actions", []):
                type_map = {
                    "new_feature": EvolutionType.NEW_FEATURE,
                    "refactor": EvolutionType.REFACTOR,
                    "bug_fix": EvolutionType.BUG_FIX,
                    "performance": EvolutionType.PERFORMANCE,
                    "security": EvolutionType.SECURITY,
                    "test_add": EvolutionType.TEST_ADD,
                    "doc_add": EvolutionType.DOC_ADD,
                    "dependency": EvolutionType.DEPENDENCY,
                    "tool_register": EvolutionType.TOOL_REGISTER,
                }
                etype = type_map.get(ad.get("type", "refactor"), EvolutionType.REFACTOR)
                priority = EvolutionPriority(ad.get("priority", 2))

                action = EvolutionAction(
                    action_id=ad.get("action_id", f"action_{len(actions)+1:03d}"),
                    evolution_type=etype,
                    priority=priority,
                    title=ad.get("title", "未命名动作"),
                    description=ad.get("description", ""),
                    target_files=ad.get("target_files", []),
                    dependencies=ad.get("dependencies", []),
                    required_knowledge=ad.get("required_knowledge", []),
                    estimated_impact=ad.get("estimated_impact", "medium"),
                    verification_steps=ad.get("verification_steps", []),
                    status=EvolutionStatus.PLANNED,
                    created_at=datetime.now().isoformat(),
                )
                actions.append(action)

            # 按优先级排序
            actions.sort(key=lambda a: a.priority.value)

            return EvolutionPlan(
                plan_id=plan_id,
                title=plan_data.get("title", f"进化计划 #{self._plan_counter}"),
                description=plan_data.get("description", user_goal),
                created_at=datetime.now().isoformat(),
                actions=actions,
                project_context=str(project_context)[:2000],
                knowledge_context=knowledge_context[:2000],
            )

        except json.JSONDecodeError as e:
            self._logger.error(f"计划 JSON 解析失败: {e}")
            return self._create_empty_plan(plan_id, user_goal)
        except Exception as e:
            self._logger.error(f"计划解析失败: {e}")
            return self._create_empty_plan(plan_id, user_goal)

    def _create_empty_plan(self, plan_id: str, user_goal: str) -> EvolutionPlan:
        """创建空计划"""
        return EvolutionPlan(
            plan_id=plan_id,
            title="进化计划（解析失败）",
            description=user_goal,
            created_at=datetime.now().isoformat(),
            status=EvolutionStatus.FAILED,
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("{") or text.startswith("["):
            return text

        # 查找 JSON 块
        import re
        match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if match:
            return match.group(1).strip()

        # 查找大括号块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)

        return None

    async def _call_llm(self, prompt: str) -> str:
        """通过 GlobalModelRouter 调用 LLM"""
        try:
            from client.src.business.global_model_router import GlobalModelRouter
            router = GlobalModelRouter.get_instance()

            response = await router.call_model(
                capability="reasoning",
                prompt=prompt,
                temperature=0.3,
            )

            if hasattr(response, 'thinking') and response.thinking:
                return response.thinking
            elif hasattr(response, 'content') and response.content:
                return response.content
            return str(response)

        except Exception as e:
            self._logger.error(f"LLM 调用失败: {e}")
            return "{}"
