"""
Skill 自进化系统 - 自主执行循环

参考 GenericAgent 的 ~100 行 Agent Loop 核心

设计核心：
- 感知环境状态
- 任务推理
- 调用工具执行
- 经验写入记忆
- 循环

技能进化核心流程：
[遇到新任务] → [搜索相似技能] → [有则复用/无则自主摸索] → [固化为 Skill] → [写入 L3]
"""

from core.logger import get_logger
logger = get_logger('skill_evolution.agent_loop')

import json
import re
import time
import threading
from typing import Any, Optional, List, Dict, Callable, Generator
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    TaskContext,
    TaskStatus,
    ExecutionRecord,
    ExecutionPhase,
    TaskSkill,
    SkillEvolutionStatus,
    InsightIndex,
    MemoryLayer,
    SessionArchive,
    generate_id,
    generate_skill_id,
)
from .database import EvolutionDatabase
from .atom_tools import UnifiedToolHandler, ToolResult, get_tool_schemas
from core.amphiloop import (
    AmphiLoopEngine,
    CheckpointManager,
    BidirectionalScheduler,
    DynamicTerminator,
    IncrementalLearning,
    get_amphiloop_engine,
)


@dataclass
class StepOutcome:
    """步骤结果"""
    data: Any = None
    next_prompt: Optional[str] = None
    should_exit: bool = False
    skill_consumed: bool = False  # 是否消耗了已有技能


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_turns: int = 40
    tool_timeout: int = 30
    skill_threshold: float = 0.3  # 技能匹配阈值
    auto_consolidate: bool = True  # 自动固化
    consolidation_min_successes: int = 2  # 最少成功次数才固化
    verbose: bool = True
    # AmphiLoop 配置
    enable_amphiloop: bool = True  # 启用 AmphiLoop
    checkpoint_interval: int = 5   # 检查点间隔
    rollback_on_failure: bool = True  # 失败时回滚
    dynamic_termination: bool = True  # 动态终止


class SkillEvolutionAgent:
    """
    技能自进化 Agent

    核心循环：
    1. 接收任务描述
    2. 搜索相似技能（从 L3）
    3a. 有相似技能 → 尝试复用
    3b. 无相似技能 → 自主摸索执行
    4. 执行完成后，判断是否需要固化
    5. 固化成功 → 写入 L3 层
    """

    def __init__(
        self,
        database: EvolutionDatabase,
        llm_client: Any,  # LLM 客户端接口
        tool_handler: UnifiedToolHandler = None,
        config: AgentConfig = None,
    ):
        self.db = database
        self.llm = llm_client
        self.config = config or AgentConfig()
        self.tool_handler = tool_handler or UnifiedToolHandler()

        # 回调
        self.on_task_start: Callable[[str], None] = None
        self.on_task_end: Callable[[TaskContext], None] = None
        self.on_skill_created: Callable[[TaskSkill], None] = None
        self.on_phase_change: Callable[[ExecutionPhase], None] = None

        # 内部状态
        self._current_task: Optional[TaskContext] = None
        self._messages: List[Dict[str, Any]] = []
        self._turn = 0
        self._lock = threading.Lock()

        # AmphiLoop 引擎
        self.amphiloop = get_amphiloop_engine()
        self._checkpoint_manager = self.amphiloop.checkpoint_manager
        self._bidirectional_scheduler = self.amphiloop.bidirectional_scheduler
        self._dynamic_terminator = self.amphiloop.dynamic_terminator
        self._incremental_learning = self.amphiloop.incremental_learning

    def execute_task(
        self,
        task_description: str,
        task_type: str = "",
        session_id: str = "",
        initial_context: Dict[str, Any] = None,
    ) -> TaskContext:
        """
        执行任务的主入口

        Args:
            task_description: 任务描述
            task_type: 任务类型（可选，用于分类）
            session_id: 会话 ID（用于关联归档）
            initial_context: 初始上下文

        Returns:
            TaskContext: 任务上下文（包含完整执行记录）
        """
        with self._lock:
            task_id = generate_id("task")

            # 创建任务上下文
            self._current_task = TaskContext(
                task_id=task_id,
                description=task_description,
                task_type=task_type,
                status=TaskStatus.RUNNING,
                session_id=session_id,
            )
            self._current_task.start_time = time.time()
            self.db.create_task_context(self._current_task)

            # 设置 AmphiLoop 任务 ID
            self.amphiloop.current_task_id = task_id

            # 回调
            if self.on_task_start:
                self.on_task_start(task_description)

            # 构建系统提示（包含 L0 元规则和 L2 事实）
            system_prompt = self._build_system_prompt()

            # 构建初始消息
            user_content = task_description
            if initial_context:
                user_content = f"{task_description}\n\n上下文信息：\n{json.dumps(initial_context, ensure_ascii=False)}"

            self._messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            # 首先尝试查找相似技能
            similar_skills = self.db.find_similar_skills(
                task_description,
                threshold=self.config.skill_threshold
            )

            skill_used = None
            if similar_skills:
                # 尝试使用最相似的技能
                best_skill = similar_skills[0]
                if self.config.verbose:
                    logger.info(f"[Agent] 发现相似技能: {best_skill.name} (匹配度: {best_skill.use_count})")

                # 直接执行技能流程
                skill_used = best_skill
                outcome = self._execute_skill(best_skill, task_description)
                if outcome.skill_consumed:
                    self._current_task.skill_id = best_skill.skill_id

            # 如果没有技能或技能执行失败，进入自主摸索循环
            if not skill_used or not self._current_task.execution_records:
                self._run_autonomous_loop()

            # 任务完成
            self._finish_task()

            # 判断是否需要固化
            if self.config.auto_consolidate:
                self._try_consolidate()

            # 回调
            if self.on_task_end:
                self.on_task_end(self._current_task)

            return self._current_task

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        parts = ["# Skill Evolution Agent\n"]

        # L0: 元规则
        meta_rules = self.db.get_meta_rules()
        if meta_rules:
            parts.append("## 元规则 (L0)\n")
            for rule in meta_rules:
                parts.append(f"- {rule.content}")
            parts.append("")

        # L2: 全局事实
        facts = self.db.get_global_facts(verified_only=False)[:10]  # 限制数量
        if facts:
            parts.append("## 全局事实 (L2)\n")
            for fact in facts:
                parts.append(f"- {fact.content} (来源: {fact.source})")
            parts.append("")

        # 工具说明
        parts.append("## 可用工具\n")
        parts.append("你可以通过调用工具来完成任务。以下是可用工具：\n")
        for tool in get_tool_schemas():
            func = tool["function"]
            parts.append(f"- {func['name']}: {func['description']}")

        parts.append("\n## 指令\n")
        parts.append("1. 仔细分析任务，选择合适的工具")
        parts.append("2. 逐步执行，每个工具调用都要记录")
        parts.append("3. 如果遇到问题，尝试其他方法")
        parts.append("4. 完成任务后，输出最终结果")

        return "\n".join(parts)

    def _execute_skill(self, skill: TaskSkill, task_description: str) -> StepOutcome:
        """执行已有技能"""
        skill.record_usage(success=True, duration=0)
        self.db.update_skill(skill.skill_id, {
            "use_count": skill.use_count,
            "last_used": time.time(),
            "success_rate": skill.success_rate,
            "avg_duration": skill.avg_duration,
            "evolution_status": skill.evolution_status,
        })

        # 为每个步骤创建执行记录
        for i, step in enumerate(skill.execution_flow):
            tool_name = step.get("tool", "no_tool")
            phase = step.get("phase", ExecutionPhase.EXECUTE.value)

            record = ExecutionRecord(
                id=generate_id("rec"),
                task_id=self._current_task.task_id,
                phase=ExecutionPhase(phase),
                tool_name=tool_name,
                tool_args=step.get("args", {}),
            )
            self.db.add_execution_record(record)

            # 执行工具
            if tool_name != "no_tool":
                result = self.tool_handler.dispatch(tool_name, record.tool_args)
                record.finish(success=result.success, error_msg=result.error, result=result.data)
                self.db.finish_execution_record(record.id, result.success, result.error, result.data)

            self._current_task.execution_records.append(record)

        return StepOutcome(data={"skill_executed": skill.name}, skill_consumed=True)

    def _run_autonomous_loop(self):
        """自主摸索循环（没有可用技能时）- 集成 AmphiLoop"""
        self._turn = 0
        tool_schemas = get_tool_schemas()
        success_count = 0
        total_count = 0

        while self._turn < self.config.max_turns:
            self._turn += 1
            phase = f"turn_{self._turn}"

            if self.config.verbose:
                logger.info(f"[Agent] Turn {self._turn}...")

            # AmphiLoop: 创建检查点
            if self.config.enable_amphiloop:
                if self._checkpoint_manager.should_create_checkpoint(self._turn):
                    self._checkpoint_manager.create_checkpoint(
                        task_id=self._current_task.task_id,
                        turn=self._turn,
                        phase=phase,
                        state={"turn": self._turn},
                        messages=self._messages.copy(),
                        execution_records=self._current_task.execution_records
                    )

            # 每 10 轮重置工具描述，避免上下文膨胀
            if self._turn % 10 == 0 and hasattr(self.llm, 'last_tools'):
                self.llm.last_tools = ''

            # 调用 LLM
            response = self.llm.chat(messages=self._messages, tools=tool_schemas)
            if self.config.verbose:
                content = response.content
                if content:
                    logger.info(f"[Agent] LLM: {content[:200]}...")

            # 解析工具调用
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # 没有工具调用，任务可能完成
                self._messages.append({"role": "assistant", "content": response.content})
                break

            # 执行工具调用
            for i, tc in enumerate(tool_calls):
                tool_name = tc["tool_name"]
                args = tc["args"]

                if self.config.verbose:
                    logger.info(f"[Agent] Tool: {tool_name}({args})")

                # 记录执行
                record = ExecutionRecord(
                    id=generate_id("rec"),
                    task_id=self._current_task.task_id,
                    phase=ExecutionPhase.EXECUTE,
                    tool_name=tool_name,
                    tool_args=args,
                )
                self.db.add_execution_record(record)
                self._current_task.execution_records.append(record)
                total_count += 1

                # 执行工具
                result = self.tool_handler.dispatch(tool_name, args)
                record.finish(success=result.success, error_msg=result.error, result=result.data)

                # 更新记录
                self.db.finish_execution_record(record.id, result.success, result.error, result.data)

                # 添加到消息
                tool_result_content = json.dumps(result.data, ensure_ascii=False) if result.data else result.error
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": tool_result_content
                })

                # AmphiLoop: 记录反馈和检查终止
                if self.config.enable_amphiloop:
                    score = 1.0 if result.success else 0.0
                    feedback = self._bidirectional_scheduler.record_feedback(
                        turn=self._turn,
                        success=result.success,
                        score=score,
                        message=f"Tool {tool_name}: {'success' if result.success else 'failed'}"
                    )

                    # 检查是否应该终止
                    if self.config.dynamic_termination and total_count > 0:
                        should_terminate, reason = self._dynamic_terminator.should_terminate(
                            turn=self._turn,
                            success_count=success_count,
                            total_count=total_count,
                            current_score=score,
                            feedback_trend=self._bidirectional_scheduler.get_feedback_trend()
                        )
                        if should_terminate:
                            if self.config.verbose:
                                logger.info(f"[Agent] 动态终止: {reason}")
                            break

                # 检查是否成功
                if result.success:
                    success_count += 1
                elif not result.success and result.error:
                    # 工具执行失败，记录但继续
                    if self.config.verbose:
                        logger.info(f"[Agent] Tool error: {result.error}")

                    # AmphiLoop: 失败时尝试回滚
                    if self.config.enable_amphiloop and self.config.rollback_on_failure:
                        checkpoint = self.amphiloop.handle_failure(f"Tool {tool_name} failed: {result.error}")
                        if checkpoint and self.config.verbose:
                            logger.info(f"[Agent] 回滚到检查点: {checkpoint.checkpoint_id}")

    def _parse_tool_calls(self, response) -> List[Dict[str, Any]]:
        """解析 LLM 响应中的工具调用"""
        tool_calls = []

        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                if hasattr(tc, 'function'):
                    try:
                        args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        tool_calls.append({
                            "tool_name": tc.function.name,
                            "args": args,
                            "id": tc.id
                        })
                    except json.JSONDecodeError:
                        continue

        return tool_calls

    def _finish_task(self):
        """完成任务"""
        # 判断成功与否
        records = self._current_task.execution_records
        if records:
            success_count = sum(1 for r in records if r.success)
            total = len(records)
            success_rate = success_count / total if total > 0 else 0
            is_success = success_rate >= 0.5
        else:
            is_success = False

        self._current_task.finish(
            status=TaskStatus.COMPLETED if is_success else TaskStatus.FAILED,
            result={"turns": self._turn, "records": len(records)},
            error="" if is_success else "执行失败"
        )

        # 更新数据库
        self.db.update_task_context(self._current_task.task_id, {
            "status": self._current_task.status,
            "end_time": self._current_task.end_time,
            "duration": self._current_task.duration,
        })

        # AmphiLoop: 增量学习
        if self.config.enable_amphiloop:
            self.amphiloop.distill_and_optimize(
                self._current_task.task_id,
                self._current_task.execution_records
            )

        # 归档到 L4
        self._archive_session()

    def _archive_session(self):
        """将会话归档到 L4"""
        records = self._current_task.execution_records
        tools_used = list(set(r.tool_name for r in records if r.tool_name != "no_tool"))

        archive = SessionArchive(
            id=generate_id("arch"),
            task_description=self._current_task.description,
            task_type=self._current_task.task_type,
            execution_summary=self._summarize_execution(),
            key_insights=self._extract_insights(),
            mistakes_made=self._extract_mistakes(),
            lessons_learned=self._extract_lessons(),
            final_outcome="成功" if self._current_task.status == TaskStatus.COMPLETED else "失败",
            success=self._current_task.status == TaskStatus.COMPLETED,
            duration=self._current_task.duration,
            turns_count=self._turn,
            tools_used=tools_used,
            session_id=self._current_task.session_id,
        )
        self.db.add_session_archive(archive)

        # 同时添加索引到 L1
        idx = InsightIndex(
            id=generate_id("idx"),
            keywords=self._extract_keywords(),
            layer=MemoryLayer.L4_SESSION_ARCHIVE,
            target_id=archive.id,
            summary=archive.execution_summary,
        )
        self.db.add_insight_index(idx)

    def _summarize_execution(self) -> str:
        """总结执行过程"""
        records = self._current_task.execution_records
        if not records:
            return "无执行记录"

        steps = []
        for r in records:
            status = "✓" if r.success else "✗"
            steps.append(f"{status} {r.tool_name}")

        return f"执行了 {len(records)} 个步骤：{' → '.join(steps)}"

    def _extract_keywords(self) -> List[str]:
        """提取关键词"""
        text = self._current_task.description
        # 简单分词
        words = re.findall(r'[\w]+', text.lower())
        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '一个', '这个', '那'}
        keywords = [w for w in words if len(w) > 1 and w not in stopwords]
        return keywords[:10]

    def _extract_insights(self) -> List[str]:
        """提取关键洞察"""
        insights = []
        records = self._current_task.execution_records

        # 分析成功模式
        successful_tools = [r.tool_name for r in records if r.success and r.tool_name != "no_tool"]
        if successful_tools:
            insights.append(f"成功使用的工具: {', '.join(successful_tools)}")

        return insights

    def _extract_mistakes(self) -> List[str]:
        """提取错误"""
        mistakes = []
        records = self._current_task.execution_records

        for r in records:
            if not r.success and r.error_msg:
                mistakes.append(f"{r.tool_name}: {r.error_msg}")

        return mistakes

    def _extract_lessons(self) -> List[str]:
        """提取经验教训"""
        lessons = []
        mistakes = self._extract_mistakes()

        if mistakes:
            lessons.append("需要避免重复同样的错误")
        else:
            lessons.append("执行过程顺利")

        return lessons

    def _try_consolidate(self):
        """
        尝试将成功的执行固化为技能

        条件：
        1. 任务成功完成
        2. 有足够的执行步骤（至少2步）
        3. 成功次数 >= consolidation_min_successes（这里简化为1次成功即可固化）
        """
        if self._current_task.status != TaskStatus.COMPLETED:
            return

        records = self._current_task.execution_records
        if len(records) < 2:
            return

        # 检查是否已经存在非常相似的技能
        existing_skills = self.db.find_similar_skills(
            self._current_task.description,
            threshold=0.6  # 高阈值，避免重复
        )

        if existing_skills:
            # 更新已有技能
            skill = existing_skills[0]
            skill.use_count += 1
            skill.last_used = time.time()
            self.db.update_skill(skill.skill_id, {
                "use_count": skill.use_count,
                "last_used": skill.last_used,
            })
            return

        # 创建新技能
        tool_sequence = [r.tool_name for r in records if r.tool_name != "no_tool"]
        execution_flow = []
        for r in records:
            execution_flow.append({
                "phase": r.phase.value if hasattr(r.phase, 'value') else r.phase,
                "tool": r.tool_name,
                "args": r.tool_args,
                "success": r.success,
            })

        keywords = self._extract_keywords()

        skill = TaskSkill(
            skill_id=generate_skill_id(self._current_task.description[:20]),
            name=self._generate_skill_name(),
            description=self._current_task.description,
            trigger_patterns=keywords,
            execution_flow=execution_flow,
            tool_sequence=tool_sequence,
            success_rate=1.0,
            use_count=1,
            failed_count=0,
            avg_duration=self._current_task.duration,
            total_duration=self._current_task.duration,
            evolution_status=SkillEvolutionStatus.SEED,
            metadata={
                "task_type": self._current_task.task_type,
                "first_created": True,
            }
        )

        self.db.add_skill(skill)

        # 添加索引到 L1
        idx = InsightIndex(
            id=generate_id("idx"),
            keywords=keywords,
            layer=MemoryLayer.L3_TASK_SKILLS,
            target_id=skill.skill_id,
            summary=f"技能: {skill.name}",
        )
        self.db.add_insight_index(idx)

        if self.config.verbose:
            logger.info(f"[Agent] 创建新技能: {skill.name} (ID: {skill.skill_id})")

        if self.on_skill_created:
            self.on_skill_created(skill)

    def _generate_skill_name(self) -> str:
        """生成技能名称"""
        desc = self._current_task.description
        # 取前20个字符作为基础
        base = desc[:20] if len(desc) >= 20 else desc
        # 移除特殊字符
        base = re.sub(r'[^\w\u4e00-\u9fff]', '_', base)
        return f"{base}_v1"


# ============ 简单 LLM 客户端接口 ============

class SimpleLLMClient:
    """
    简单的 LLM 客户端接口

    支持本地模型（Ollama）和远程 API
    """

    def __init__(self, provider: str = "ollama", base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.provider = provider
        self.base_url = base_url
        self.model = model
        self.last_tools = ""
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化客户端"""
        if self.provider == "ollama":
            try:
                import ollama
                self._client = ollama
            except ImportError:
                logger.info("[Warning] ollama 包未安装")

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict] = None) -> Any:
        """
        发送聊天请求

        Returns:
            响应对象（包含 content 和 tool_calls）
        """
        if self.provider == "ollama" and self._client:
            return self._chat_ollama(messages, tools)
        else:
            # 模拟响应
            return self._mock_response(messages)

    def _chat_ollama(self, messages: List[Dict], tools: List[Dict]) -> Any:
        """Ollama 聊天"""
        try:
            # 构建选项
            options = {}
            if tools:
                # 将工具格式转换为 Ollama 格式
                tool_prompt = self._build_tool_prompt(tools)
                self.last_tools = tool_prompt

                # 将工具提示添加到系统消息
                for msg in messages:
                    if msg["role"] == "system":
                        msg["content"] += "\n\n" + tool_prompt

            response = self._client.chat(
                model=self.model,
                messages=messages,
                options=options,
            )

            # 包装响应
            class Response:
                def __init__(self, content):
                    self.content = content
                    self.tool_calls = None

            return Response(response['message']['content'])

        except Exception as e:
            logger.info(f"[Error] Ollama chat failed: {e}")
            return self._mock_response(messages)

    def _build_tool_prompt(self, tools: List[Dict]) -> str:
        """构建工具提示"""
        if not tools:
            return ""

        parts = ["\n\n## 可用工具\n"]
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", tool.get("name", "unknown"))
            desc = func.get("description", "")
            params = func.get("parameters", {})

            parts.append(f"### {name}\n")
            parts.append(f"{desc}\n")
            parts.append(f"参数: {json.dumps(params, ensure_ascii=False)}\n")

        return "".join(parts)

    def _mock_response(self, messages: List[Dict]) -> Any:
        """模拟响应（用于测试）"""

        class MockTC:
            def __init__(self, name, args):
                self.function = type('obj', (object,), {'name': name, 'arguments': json.dumps(args)})()
                self.id = generate_id("tc")

        class Response:
            def __init__(self, content, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls or []

        # 简单模拟：根据用户输入返回响应
        last_msg = messages[-1]["content"] if messages else ""

        # 检查是否包含文件操作
        if "读" in last_msg and "文件" in last_msg:
            return Response("我将读取文件内容", [])

        return Response("收到任务描述，开始执行...", [])


def create_agent(
    db_path: str = None,
    workspace_root: str = None,
    llm_provider: str = "ollama",
    llm_model: str = "llama3.2",
    llm_base_url: str = "http://localhost:11434",
) -> SkillEvolutionAgent:
    """
    创建自进化 Agent 实例

    使用示例：
        agent = create_agent(
            db_path="~/.hermes-desktop/evolution/evolution.db",
            workspace_root="d:/mhzyapp/hermes-desktop",
        )
        result = agent.execute_task("帮我读取 config.py 文件")
    """
    import os
    from pathlib import Path


    # 默认路径
    if db_path is None:
        db_path = Path.home() / ".hermes-desktop" / "evolution" / "evolution.db"
    else:
        db_path = Path(db_path)

    # 初始化数据库
    db = EvolutionDatabase(db_path)

    # 初始化 LLM 客户端
    llm = SimpleLLMClient(
        provider=llm_provider,
        base_url=llm_base_url,
        model=llm_model,
    )

    # 初始化工具处理器
    tool_handler = UnifiedToolHandler(workspace_root=workspace_root)

    # 创建 Agent
    agent = SkillEvolutionAgent(
        database=db,
        llm_client=llm,
        tool_handler=tool_handler,
    )

    return agent
