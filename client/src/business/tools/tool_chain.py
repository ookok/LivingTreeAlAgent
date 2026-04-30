"""
通用工具链模块 (ToolChain)
=============================

实现工具间的管道式执行：
1. 工具链定义：按序执行多个工具，前一个输出作为后一个输入
2. 数据流管理：工具间数据传递和格式转换
3. 错误处理：链中某工具失败时的处理策略
4. 条件执行：根据条件跳过某些工具
5. 并行执行：无依赖的工具可并行执行

存储：工具链定义（JSON） + 执行历史（SQLite）
"""

import json
import sqlite3
import asyncio
from typing import Optional, List, Dict, Any, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


# ============================================================
# 数据结构
# ============================================================

class ChainExecutionStrategy(str, Enum):
    """链执行策略"""
    SEQUENTIAL = "sequential"    # 顺序执行
    PARALLEL = "parallel"        # 并行执行（无依赖）
    CONDITIONAL = "conditional"   # 条件执行


class StepExecutionResult(str, Enum):
    """步骤执行结果"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


@dataclass
class ChainStep:
    """工具链步骤"""
    step_id: str                    # 步骤ID
    tool_name: str                  # 工具名称
    inputs: Dict[str, Any] = field(default_factory=dict)  # 输入参数
    input_mapping: Dict[str, str] = field(default_factory=dict)  # 从前序步骤映射输入
    condition: Optional[str] = None  # 条件表达式（可选）
    on_failure: str = "stop"        # 失败策略：stop/continue/retry
    max_retries: int = 0
    timeout: float = 300.0          # 超时（秒）
    depends_on: List[str] = field(default_factory=list)  # 依赖的步骤ID


@dataclass
class ChainDefinition:
    """工具链定义"""
    chain_id: str
    name: str
    description: str = ""
    steps: List[ChainStep] = field(default_factory=list)
    strategy: ChainExecutionStrategy = ChainExecutionStrategy.SEQUENTIAL
    context: Dict[str, Any] = field(default_factory=dict)  # 共享上下文


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: str
    status: StepExecutionResult
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0


# ============================================================
# 工具链执行引擎
# ============================================================

class ToolChain:
    """
    通用工具链执行引擎
    
    功能：
    - 定义工具链（步骤、依赖、条件）
    - 执行工具链（顺序/并行/条件）
    - 数据流管理（步骤间数据传递）
    - 错误处理（重试、跳过、停止）
    - 执行历史记录和回放
    """
    
    def __init__(self, definition: ChainDefinition):
        self.definition = definition
        self._registry = None  # 延迟加载 ToolRegistry
        self._step_results: Dict[str, StepResult] = {}
    
    def _get_registry(self):
        if self._registry is None:
            from business.unified_tool_registry import get_registry
            self._registry = get_registry()
        return self._registry
    
    def _resolve_inputs(self, step: ChainStep,
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析步骤输入：合并直接输入和映射输入
        
        映射语法：
        - "step_id.output_field" : 从指定步骤的输出中获取字段
        - "$chain.input_field"    : 从链输入中获取字段
        - "$context.key"          : 从共享上下文获取
        """
        inputs = dict(step.inputs)  # 复制直接输入
        
        for target_key, source_expr in step.input_mapping.items():
            if source_expr.startswith("$chain."):
                field_name = source_expr[len("$chain."):]
                inputs[target_key] = context.get("chain_input", {}).get(field_name)
            elif source_expr.startswith("$context."):
                key = source_expr[len("$context."):]
                inputs[target_key] = context.get(key)
            elif "." in source_expr:
                step_id, field = source_expr.split(".", 1)
                if step_id in self._step_results:
                    step_result = self._step_results[step_id]
                    if step_result.status == StepExecutionResult.SUCCESS:
                        if isinstance(step_result.result, dict):
                            inputs[target_key] = step_result.result.get(field)
                        else:
                            inputs[target_key] = step_result.result
        
        return inputs
    
    def _check_condition(self, condition: str,
                        context: Dict[str, Any]) -> bool:
        """检查条件表达式（简化版，支持基本比较）"""
        if not condition:
            return True
        
        # 简单条件解析：支持 $step_id.status == 'success' 等
        # TODO: 实现完整的条件表达式解析器
        try:
            # 安全的表达式求值（限制可用变量）
            safe_globals = {"__builtins__": {}}
            safe_locals = dict(context)
            safe_locals.update({
                "status": {k: v.status.value for k, v in self._step_results.items()}
            })
            result = eval(condition, safe_globals, safe_locals)  # noqa: S307
            return bool(result)
        except Exception:
            return True  # 条件解析失败，默认执行
    
    def execute(self, chain_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行工具链
        
        Args:
            chain_input: 链的输入数据
        
        Returns:
            执行结果字典，包含所有步骤的结果
        """
        context = {
            "chain_input": chain_input or {},
            "chain_id": self.definition.chain_id,
            "steps_completed": [],
            "steps_failed": []
        }
        
        if self.definition.strategy == ChainExecutionStrategy.SEQUENTIAL:
            return self._execute_sequential(context)
        elif self.definition.strategy == ChainExecutionStrategy.PARALLEL:
            return self._execute_parallel(context)
        else:
            return self._execute_conditional(context)
    
    def _execute_sequential(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """顺序执行"""
        registry = self._get_registry()
        
        for step in self.definition.steps:
            # 检查依赖步骤是否完成
            deps_met = all(
                dep in context["steps_completed"]
                for dep in step.depends_on
            )
            if not deps_met:
                self._step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=StepExecutionResult.SKIPPED,
                    error="Dependencies not met"
                )
                continue
            
            # 检查条件
            if not self._check_condition(step.condition, context):
                self._step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=StepExecutionResult.SKIPPED,
                    error="Condition not met"
                )
                context["steps_completed"].append(step.step_id)
                continue
            
            # 解析输入
            inputs = self._resolve_inputs(step, context)
            
            # 执行工具
            import time
            start_time = time.time()
            
            retry_count = 0
            while retry_count <= step.max_retries:
                tool = registry.get_tool(step.tool_name)
                if not tool:
                    result = {
                        "success": False,
                        "error": f"Tool {step.tool_name} not found"
                    }
                    break
                
                result = tool.execute(inputs)
                if result.get("success", False):
                    break
                
                retry_count += 1
                if retry_count > step.max_retries:
                    break
            
            execution_time = time.time() - start_time
            
            # 处理结果
            if result.get("success", False):
                self._step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=StepExecutionResult.SUCCESS,
                    result=result.get("data"),
                    execution_time=execution_time,
                    retry_count=retry_count
                )
                context["steps_completed"].append(step.step_id)
            else:
                error = result.get("error", "Unknown error")
                self._step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=StepExecutionResult.FAILED,
                    error=error,
                    execution_time=execution_time,
                    retry_count=retry_count
                )
                context["steps_failed"].append(step.step_id)
                
                if step.on_failure == "stop":
                    break
                elif step.on_failure == "continue":
                    continue
        
        return self._build_chain_result(context)
    
    def _execute_parallel(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """并行执行（无依赖的步骤）"""
        import concurrent.futures
        
        registry = self._get_registry()
        futures = {}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for step in self.definition.steps:
                if step.depends_on:
                    continue  # 有依赖的步骤不支持并行
                
                inputs = self._resolve_inputs(step, context)
                future = executor.submit(self._execute_step, step, inputs)
                futures[future] = step
            
            for future in concurrent.futures.as_completed(futures):
                step = futures[future]
                try:
                    step_result = future.result()
                    self._step_results[step.step_id] = step_result
                except Exception as e:
                    self._step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status=StepExecutionResult.FAILED,
                        error=str(e)
                    )
        
        return self._build_chain_result(context)
    
    def _execute_conditional(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """条件执行"""
        # 条件执行是顺序执行的变种，每一步都有条件检查
        return self._execute_sequential(context)
    
    def _execute_step(self, step: ChainStep, inputs: Dict[str, Any]) -> StepResult:
        """执行单个步骤"""
        import time
        start_time = time.time()
        
        registry = self._get_registry()
        tool = registry.get_tool(step.tool_name)
        
        if not tool:
            return StepResult(
                step_id=step.step_id,
                status=StepExecutionResult.FAILED,
                error=f"Tool {step.tool_name} not found"
            )
        
        result = tool.execute(inputs)
        execution_time = time.time() - start_time
        
        if result.get("success", False):
            return StepResult(
                step_id=step.step_id,
                status=StepExecutionResult.SUCCESS,
                result=result.get("data"),
                execution_time=execution_time
            )
        else:
            return StepResult(
                step_id=step.step_id,
                status=StepExecutionResult.FAILED,
                error=result.get("error"),
                execution_time=execution_time
            )
    
    def _build_chain_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建链执行结果"""
        step_results = {
            step_id: {
                "status": result.status.value,
                "result": result.result,
                "error": result.error,
                "execution_time": result.execution_time,
                "retry_count": result.retry_count
            }
            for step_id, result in self._step_results.items()
        }
        
        overall_success = all(
            r.status == StepExecutionResult.SUCCESS
            for r in self._step_results.values()
        )
        
        return {
            "chain_id": self.definition.chain_id,
            "success": overall_success,
            "step_results": step_results,
            "steps_completed": context["steps_completed"],
            "steps_failed": context["steps_failed"],
            "total_steps": len(self.definition.steps)
        }
    
    def visualize(self) -> str:
        """生成工具链可视化文本"""
        lines = [f"ToolChain: {self.definition.name}"]
        lines.append("=" * 50)
        
        for i, step in enumerate(self.definition.steps):
            deps = f" [depends: {', '.join(step.depends_on)}]" if step.depends_on else ""
            condition = f" [if: {step.condition}]" if step.condition else ""
            lines.append(f"  {i+1}. {step.tool_name}{deps}{condition}")
            
            if step.input_mapping:
                for target, source in step.input_mapping.items():
                    lines.append(f"       {target} <- {source}")
        
        return "\n".join(lines)


# ============================================================
# 工具链管理器（持久化 + 预定义链）
# ============================================================

class ToolChainManager:
    """
    工具链管理器（单例模式）
    
    功能：
    - 注册和存储工具链定义
    - 执行工具链
    - 预定义常用工具链（EI分析、文档处理等）
    - 工具链模板
    """
    
    _instance: Optional["ToolChainManager"] = None
    _db_path: Path = Path.home() / ".livingtree" / "tool_chains.db"
    _chain_store_path: Path = Path.home() / ".livingtree" / "chains"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._register_predefined_chains()
    
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn
    
    def _init_db(self):
        """初始化工具链数据库"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chain_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                success BOOLEAN,
                total_steps INTEGER,
                steps_completed INTEGER,
                steps_failed INTEGER,
                total_execution_time REAL,
                result_json TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_chain_exec ON chain_executions(chain_id, started_at);
        """)
        conn.commit()
        self._chain_store_path.mkdir(parents=True, exist_ok=True)
    
    def _register_predefined_chains(self):
        """注册预定义工具链"""
        predefined = [
            self._create_ei_analysis_chain(),
            self._create_document_processing_chain(),
            self._create_web_research_chain(),
        ]
        
        for chain_def in predefined:
            self.save_chain_definition(chain_def)
    
    def _create_ei_analysis_chain(self) -> ChainDefinition:
        """创建环评分析工具链"""
        return ChainDefinition(
            chain_id="ei_analysis",
            name="环评分析报告生成链",
            description="自动执行环评分析全流程：资料收集 → 现状调查 → 影响预测 → 措施建议 → 报告生成",
            strategy=ChainExecutionStrategy.SEQUENTIAL,
            steps=[
                ChainStep(
                    step_id="collect_data",
                    tool_name="web_crawler",
                    inputs={"url": "$chain.url"},
                    input_mapping={"query": "$chain.keywords"}
                ),
                ChainStep(
                    step_id="search_knowledge",
                    tool_name="deep_search",
                    depends_on=["collect_data"],
                    input_mapping={"query": "collect_data.summary"}
                ),
                ChainStep(
                    step_id="generate_report",
                    tool_name="report_generator",
                    depends_on=["search_knowledge"],
                    input_mapping={
                        "title": "$chain.report_title",
                        "data": "search_knowledge.results"
                    }
                )
            ]
        )
    
    def _create_document_processing_chain(self) -> ChainDefinition:
        """创建文档处理工具链"""
        return ChainDefinition(
            chain_id="document_processing",
            name="文档处理链",
            description="文档解析 → 内容提取 → OCR → Markdown 转换",
            strategy=ChainExecutionStrategy.SEQUENTIAL,
            steps=[
                ChainStep(
                    step_id="parse_doc",
                    tool_name="document_parser",
                    inputs={"file_path": "$chain.file_path"}
                ),
                ChainStep(
                    step_id="ocr_process",
                    tool_name="intelligent_ocr",
                    depends_on=["parse_doc"],
                    input_mapping={"file_path": "$chain.file_path"}
                ),
                ChainStep(
                    step_id="convert_markdown",
                    tool_name="markitdown_converter",
                    depends_on=["ocr_process"],
                    input_mapping={"content": "ocr_process.text"}
                )
            ]
        )
    
    def _create_web_research_chain(self) -> ChainDefinition:
        """创建网络研究工具链"""
        return ChainDefinition(
            chain_id="web_research",
            name="网络研究链",
            description="网页爬取 → 内容提取 → 向量存储 → 知识图谱更新",
            strategy=ChainExecutionStrategy.SEQUENTIAL,
            steps=[
                ChainStep(
                    step_id="crawl",
                    tool_name="web_crawler",
                    inputs={"url": "$chain.url"}
                ),
                ChainStep(
                    step_id="extract",
                    tool_name="content_extractor",
                    depends_on=["crawl"],
                    input_mapping={"html": "crawl.html"}
                ),
                ChainStep(
                    step_id="store_vector",
                    tool_name="vector_database",
                    depends_on=["extract"],
                    input_mapping={"text": "extract.content"}
                ),
                ChainStep(
                    step_id="update_kg",
                    tool_name="knowledge_graph",
                    depends_on=["store_vector"],
                    input_mapping={"text": "extract.content"}
                )
            ]
        )
    
    # ============================================================
    # 工具链管理 API
    # ============================================================
    
    def save_chain_definition(self, definition: ChainDefinition) -> bool:
        """保存工具链定义到 JSON 文件"""
        file_path = self._chain_store_path / f"{definition.chain_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "chain_id": definition.chain_id,
                "name": definition.name,
                "description": definition.description,
                "strategy": definition.strategy.value,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "tool_name": s.tool_name,
                        "inputs": s.inputs,
                        "input_mapping": s.input_mapping,
                        "condition": s.condition,
                        "on_failure": s.on_failure,
                        "max_retries": s.max_retries,
                        "timeout": s.timeout,
                        "depends_on": s.depends_on
                    }
                    for s in definition.steps
                ]
            }, f, ensure_ascii=False, indent=2)
        return True
    
    def load_chain_definition(self, chain_id: str) -> Optional[ChainDefinition]:
        """加载工具链定义"""
        file_path = self._chain_store_path / f"{chain_id}.json"
        if not file_path.exists():
            return None
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        steps = [
            ChainStep(
                step_id=s["step_id"],
                tool_name=s["tool_name"],
                inputs=s.get("inputs", {}),
                input_mapping=s.get("input_mapping", {}),
                condition=s.get("condition"),
                on_failure=s.get("on_failure", "stop"),
                max_retries=s.get("max_retries", 0),
                timeout=s.get("timeout", 300.0),
                depends_on=s.get("depends_on", [])
            )
            for s in data["steps"]
        ]
        
        return ChainDefinition(
            chain_id=data["chain_id"],
            name=data["name"],
            description=data.get("description", ""),
            strategy=ChainExecutionStrategy(data.get("strategy", "sequential")),
            steps=steps
        )
    
    def execute_chain(self, chain_id: str,
                     chain_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行工具链"""
        definition = self.load_chain_definition(chain_id)
        if not definition:
            return {"success": False, "error": f"Chain {chain_id} not found"}
        
        chain = ToolChain(definition)
        result = chain.execute(chain_input)
        
        # 记录执行历史
        self._record_execution(chain_id, result)
        
        return result
    
    def _record_execution(self, chain_id: str, result: Dict[str, Any]):
        """记录执行历史"""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO chain_executions
            (chain_id, completed_at, success, total_steps,
             steps_completed, steps_failed, total_execution_time, result_json)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
        """, (
            chain_id,
            result.get("success"),
            result.get("total_steps"),
            len(result.get("steps_completed", [])),
            len(result.get("steps_failed", [])),
            0.0,  # TODO: 计算总执行时间
            json.dumps(result)
        ))
        conn.commit()
    
    def list_chains(self) -> List[Dict[str, str]]:
        """列出所有工具链"""
        chains = []
        for file_path in self._chain_store_path.glob("*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                chains.append({
                    "chain_id": data["chain_id"],
                    "name": data["name"],
                    "description": data.get("description", "")
                })
        return chains
    
    def delete_chain(self, chain_id: str) -> bool:
        """删除工具链定义"""
        file_path = self._chain_store_path / f"{chain_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================
# 便捷函数
# ============================================================

_default_manager: Optional[ToolChainManager] = None

def get_chain_manager() -> ToolChainManager:
    """获取工具链管理器单例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = ToolChainManager()
    return _default_manager


def execute_chain(chain_id: str,
                 chain_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """便捷函数：执行工具链"""
    manager = get_chain_manager()
    return manager.execute_chain(chain_id, chain_input)


def create_chain(definition: ChainDefinition) -> bool:
    """便捷函数：创建工具链"""
    manager = get_chain_manager()
    return manager.save_chain_definition(definition)


# ============================================================
# EI 工具链模板（环评专用）
# ============================================================

def create_ei_tool_chain(task_type: str) -> ChainDefinition:
    """
    创建环评工具链模板
    
    Args:
        task_type: 任务类型（大气/噪声/水文/土壤）
    """
    templates = {
        "atmospheric": ChainDefinition(
            chain_id="ei_atmospheric",
            name="大气环境影响分析链",
            steps=[
                ChainStep(step_id="s1", tool_name="aermod_tool",
                         inputs={"task_type": "atmospheric"}),
                ChainStep(step_id="s2", tool_name="report_generator",
                         depends_on=["s1"],
                         input_mapping={"data": "s1.results"}),
            ]
        ),
        "noise": ChainDefinition(
            chain_id="ei_noise",
            name="噪声环境影响分析链",
            steps=[
                ChainStep(step_id="s1", tool_name="cadnaa_tool",
                         inputs={"task_type": "noise"}),
                ChainStep(step_id="s2", tool_name="report_generator",
                         depends_on=["s1"],
                         input_mapping={"data": "s1.results"}),
            ]
        ),
        "hydrology": ChainDefinition(
            chain_id="ei_hydrology",
            name="水环境影响分析链",
            steps=[
                ChainStep(step_id="s1", tool_name="mike21_tool",
                         inputs={"task_type": "hydrology"}),
                ChainStep(step_id="s2", tool_name="report_generator",
                         depends_on=["s1"],
                         input_mapping={"data": "s1.results"}),
            ]
        ),
    }
    
    return templates.get(task_type, templates["atmospheric"])
