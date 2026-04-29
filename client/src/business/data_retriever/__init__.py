"""
统一数据检索系统 - Universal Data Retrieval

功能：
1. 自然语言数据查询
2. 多数据源支持
3. 对话式数据探索
4. 智能排序与过滤
5. 结果可视化
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import threading
import asyncio


class QueryIntent(Enum):
    """查询意图"""
    FIND = "find"           # 查找
    SHOW = "show"           # 显示
    STAT = "stat"           # 统计
    COMPARE = "compare"     # 比较
    TREND = "trend"         # 趋势
    FILTER = "filter"       # 过滤
    AGGREGATE = "aggregate" # 聚合
    RANK = "rank"           # 排名
    EXPORT = "export"       # 导出


class DataSource(Enum):
    """数据源"""
    LOCAL_SQLITE = "local_sqlite"
    USER_FORMS = "user_forms"
    WORKFLOW_HISTORY = "workflow_history"
    EXTERNAL_API = "external_api"
    MEMORY = "memory"


@dataclass
class ParsedQuery:
    """解析后的查询"""
    intent: str = QueryIntent.FIND.value
    target_entity: str = ""       # 查询目标实体
    target_field: str = ""        # 查询字段
    conditions: List[Dict] = field(default_factory=list)
    time_range: Optional[Dict] = None
    aggregation: Optional[str] = None
    group_by: Optional[str] = None
    order_by: Optional[str] = None
    limit: int = 100

    # 原始输入
    raw_query: str = ""


@dataclass
class SearchResult:
    """搜索结果"""
    query: str = ""
    intent: str = ""
    results: List[Dict] = field(default_factory=list)
    total_count: int = 0
    summary: str = ""
    suggestions: List[str] = field(default_factory=list)
    visualization: Optional[Dict] = None
    export_options: List[Dict] = field(default_factory=list)


@dataclass
class DataSchema:
    """数据模式"""
    table_name: str = ""
    columns: List[Dict] = field(default_factory=list)  # {name, type, description}
    description: str = ""
    source: str = ""


class NaturalLanguageQueryParser:
    """自然语言查询解析器"""

    # 查询模式
    PATTERNS = {
        # 查找类
        r"查找(.+?)的(.+?)$": {"intent": "find", "entity_group": 1, "field_group": 2},
        r"找一下(.+?)的(.+?)$": {"intent": "find", "entity_group": 1, "field_group": 2},
        r"查询(.+?)的(.+?)$": {"intent": "find", "entity_group": 1, "field_group": 2},
        r"搜索(.+?)的(.+?)$": {"intent": "find", "entity_group": 1, "field_group": 2},

        # 显示类
        r"显示(.+?)的(.+?)$": {"intent": "show", "entity_group": 1, "field_group": 2},
        r"展示(.+?)的(.+?)$": {"intent": "show", "entity_group": 1, "field_group": 2},
        r"看看(.+?)的(.+?)$": {"intent": "show", "entity_group": 1, "field_group": 2},

        # 统计类
        r"统计(.+?)的(.+?)$": {"intent": "stat", "entity_group": 1, "field_group": 2},
        r"有多少(.+?)$": {"intent": "count", "entity_group": 1},
        r"总(.+?)$": {"intent": "total", "entity_group": 1},

        # 时间类
        r"最近(.+?)的(.+?)$": {"intent": "recent", "time_group": 1, "entity_group": 2},
        r"上周的(.+?)$": {"intent": "last_week", "entity_group": 1},
        r"本月的(.+?)$": {"intent": "this_month", "entity_group": 1},
        r"今天的(.+?)$": {"intent": "today", "entity_group": 1},

        # 比较类
        r"比较(.+?)和(.+?)$": {"intent": "compare", "entity_group": 1, "compare_group": 2},
        r"哪个(.+?)更(.+?)$": {"intent": "compare", "entity_group": 1, "criteria_group": 2},

        # 排名类
        r"排名前?(.+?)的(.+?)$": {"intent": "rank", "limit_group": 1, "entity_group": 2},
        r"最(.+?)的(.+?)$": {"intent": "extremum", "criteria_group": 1, "entity_group": 2},
    }

    # 时间词映射
    TIME_MAPPING = {
        "今天": (0, 0),
        "昨天": (-1, 0),
        "前天": (-2, 0),
        "明天": (1, 0),
        "本周": (0, 7),
        "上周": (-7, 7),
        "本月": (0, 30),
        "上月": (-30, 30),
        "近一周": (-7, 0),
        "近一月": (-30, 0),
    }

    # 单位时间
    TIME_UNITS = {
        "天": 1,
        "周": 7,
        "月": 30,
        "年": 365,
    }

    def parse(self, query: str) -> ParsedQuery:
        """解析自然语言查询"""
        query = query.strip()

        # 尝试匹配模式
        for pattern, config in self.PATTERNS.items():
            match = re.match(pattern, query)
            if match:
                return self._build_parsed_query(query, config, match)

        # 默认解析
        return ParsedQuery(
            intent=QueryIntent.FIND.value,
            target_entity=query,
            raw_query=query
        )

    def _build_parsed_query(self, query: str, config: dict, match) -> ParsedQuery:
        """构建解析后的查询"""
        result = ParsedQuery(raw_query=query)

        result.intent = config.get("intent", QueryIntent.FIND.value)

        # 提取实体
        if "entity_group" in config:
            result.target_entity = match.group(config["entity_group"]) if config["entity_group"] else ""

        # 提取字段
        if "field_group" in config:
            result.target_field = match.group(config["field_group"]) if config["field_group"] else ""

        # 提取时间范围
        if "time_group" in config:
            time_str = match.group(config["time_group"])
            result.time_range = self._parse_time_range(time_str)
        elif config.get("intent") in ["last_week", "this_month", "today", "recent"]:
            time_str = match.group(1) if "time_group" not in config else match.group(config["time_group"])
            if not time_str:
                time_str = config["intent"]
            result.time_range = self._parse_time_keywords(time_str)

        # 提取数量限制
        if "limit_group" in config:
            limit_str = match.group(config["limit_group"])
            result.limit = self._parse_limit(limit_str)

        return result

    def _parse_time_range(self, time_str: str) -> Dict[str, str]:
        """解析时间范围字符串"""
        # 移除量词
        time_str = re.sub(r"\d+个?", "", time_str)

        if time_str in self.TIME_MAPPING:
            days_offset, range_days = self.TIME_MAPPING[time_str]
            end = datetime.now()
            start = end - timedelta(days=range_days)
            return {
                "start": start.isoformat(),
                "end": end.isoformat()
            }

        return {}

    def _parse_time_keywords(self, keyword: str) -> Dict[str, str]:
        """解析时间关键字"""
        end = datetime.now()
        start = end

        if keyword == "today":
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        elif keyword == "last_week":
            start = end - timedelta(days=7)
        elif keyword == "this_month":
            start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        return {
            "start": start.isoformat(),
            "end": end.isoformat()
        }

    def _parse_limit(self, limit_str: str) -> int:
        """解析数量限制"""
        match = re.search(r"\d+", limit_str)
        return int(match.group()) if match else 10


class UniversalDataRetriever:
    """统一数据检索系统"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/data_retriever").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        # 初始化数据源
        self.data_sources: Dict[str, Any] = {}

        # 查询解析器
        self.query_parser = NaturalLanguageQueryParser()

        # 模式注册表
        self._schemas: Dict[str, DataSchema] = {}
        self._register_default_schemas()

    def _register_default_schemas(self):
        """注册默认数据模式"""
        # 表单提交模式
        self._schemas["form_submissions"] = DataSchema(
            table_name="form_submissions",
            columns=[
                {"name": "id", "type": "text", "description": "提交ID"},
                {"name": "template_id", "type": "text", "description": "模板ID"},
                {"name": "template_name", "type": "text", "description": "模板名称"},
                {"name": "submitter_id", "type": "text", "description": "提交人ID"},
                {"name": "submitter_name", "type": "text", "description": "提交人名称"},
                {"name": "submitted_at", "type": "datetime", "description": "提交时间"},
                {"name": "status", "type": "text", "description": "状态"},
                {"name": "workflow_status", "type": "text", "description": "工作流状态"},
            ],
            description="表单提交记录",
            source="smart_form"
        )

        # 工作流执行模式
        self._schemas["workflow_executions"] = DataSchema(
            table_name="workflow_executions",
            columns=[
                {"name": "id", "type": "text", "description": "执行ID"},
                {"name": "workflow_id", "type": "text", "description": "工作流ID"},
                {"name": "workflow_name", "type": "text", "description": "工作流名称"},
                {"name": "status", "type": "text", "description": "状态"},
                {"name": "initiator_id", "type": "text", "description": "发起人ID"},
                {"name": "initiator_name", "type": "text", "description": "发起人名称"},
                {"name": "started_at", "type": "datetime", "description": "开始时间"},
                {"name": "completed_at", "type": "datetime", "description": "完成时间"},
            ],
            description="工作流执行记录",
            source="workflow"
        )

        # 模板模式
        self._schemas["templates"] = DataSchema(
            table_name="templates",
            columns=[
                {"name": "id", "type": "text", "description": "模板ID"},
                {"name": "name", "type": "text", "description": "模板名称"},
                {"name": "category", "type": "text", "description": "分类"},
                {"name": "author_id", "type": "text", "description": "作者ID"},
                {"name": "author_name", "type": "text", "description": "作者名称"},
                {"name": "created_at", "type": "datetime", "description": "创建时间"},
                {"name": "use_count", "type": "int", "description": "使用次数"},
                {"name": "download_count", "type": "int", "description": "下载次数"},
            ],
            description="模板记录",
            source="template_market"
        )

    def register_data_source(self, name: str, source: Any):
        """注册数据源"""
        self.data_sources[name] = source

    def register_schema(self, schema: DataSchema):
        """注册数据模式"""
        self._schemas[schema.table_name] = schema

    def get_schema(self, table_name: str) -> Optional[DataSchema]:
        """获取数据模式"""
        return self._schemas.get(table_name)

    def list_schemas(self) -> List[DataSchema]:
        """列出所有数据模式"""
        return list(self._schemas.values())

    async def search(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> SearchResult:
        """智能搜索"""
        # 1. 理解查询意图
        parsed = self.query_parser.parse(query)

        # 2. 路由到合适的数据源
        data_source = self._route_to_data_source(parsed)

        # 3. 执行搜索
        if data_source:
            results = await data_source.search(parsed)
        else:
            results = await self._fallback_search(parsed)

        # 4. 智能排序
        ranked_results = self._rank_results(results, parsed)

        # 5. 生成摘要
        summary = self._generate_summary(ranked_results, parsed)

        # 6. 生成建议
        suggestions = self._generate_suggestions(query, ranked_results)

        # 7. 生成可视化配置
        visualization = self._generate_visualization(ranked_results, parsed)

        return SearchResult(
            query=query,
            intent=parsed.intent,
            results=ranked_results,
            total_count=len(ranked_results),
            summary=summary,
            suggestions=suggestions,
            visualization=visualization,
            export_options=self._generate_export_options(ranked_results)
        )

    def _route_to_data_source(self, parsed: ParsedQuery) -> Optional[Any]:
        """路由到数据源"""
        entity = parsed.target_entity.lower()

        # 根据实体类型路由
        entity_mapping = {
            "表单": "form_submissions",
            "提交": "form_submissions",
            "申请": "form_submissions",
            "工作流": "workflow_executions",
            "执行": "workflow_executions",
            "模板": "templates",
        }

        for keyword, source_name in entity_mapping.items():
            if keyword in entity:
                return self.data_sources.get(source_name)

        return None

    async def _fallback_search(self, parsed: ParsedQuery) -> List[Dict]:
        """回退搜索（搜索所有数据源）"""
        all_results = []

        for name, source in self.data_sources.items():
            try:
                results = await source.search(parsed)
                all_results.extend(results)
            except Exception as e:
                print(f"Data source {name} search error: {e}")

        return all_results

    def _rank_results(
        self,
        results: List[Dict],
        parsed: ParsedQuery
    ) -> List[Dict]:
        """排序结果"""
        # 按时间排序（最新的在前）
        if parsed.time_range:
            results.sort(
                key=lambda x: x.get("submitted_at") or x.get("created_at") or "",
                reverse=True
            )

        # 限制数量
        return results[:parsed.limit]

    def _generate_summary(self, results: List[Dict], parsed: ParsedQuery) -> str:
        """生成结果摘要"""
        if not results:
            return f"没有找到与「{parsed.target_entity}」相关的数据"

        entity = parsed.target_entity or "数据"
        count = len(results)

        # 根据意图生成不同摘要
        if parsed.intent == QueryIntent.COUNT.value:
            return f"共有 {count} 条{entity}"
        elif parsed.intent == QueryIntent.STAT.value:
            return f"统计结果：共 {count} 条符合条件的{entity}"
        else:
            return f"找到 {count} 条与「{entity}」相关的{parsed.target_field or '记录'}"

    def _generate_suggestions(self, query: str, results: List[Dict]) -> List[str]:
        """生成搜索建议"""
        suggestions = []

        # 导出建议
        if results:
            suggestions.append("导出为 Excel")
            suggestions.append("导出为 JSON")

        # 分析建议
        if len(results) > 10:
            suggestions.append("查看更多结果")
            suggestions.append("添加筛选条件缩小范围")

        # 相关查询建议
        entity = query.replace("的", "").replace("查找", "").replace("显示", "").strip()
        if entity:
            suggestions.append(f"查看{entity}统计")
            suggestions.append(f"查看{entity}趋势")

        return suggestions

    def _generate_visualization(
        self,
        results: List[Dict],
        parsed: ParsedQuery
    ) -> Optional[Dict]:
        """生成可视化配置"""
        if not results:
            return None

        # 根据数据特征选择可视化类型
        has_time_field = any(
            "time" in str(k).lower() or "date" in str(k).lower()
            for r in results for k in r.keys()
        )

        has_numeric_field = any(
            any(isinstance(v, (int, float)) for v in r.values())
            for r in results
        )

        viz_config = {
            "type": "table",  # 默认表格
            "data": results[:100],  # 限制数据量
        }

        if has_time_field and has_numeric_field:
            viz_config["type"] = "line"  # 时间趋势图
            viz_config["x_field"] = "time"
            viz_config["y_field"] = "value"
        elif has_numeric_field:
            # 检查是否是排名数据
            if any("count" in str(k).lower() or "amount" in str(k).lower() for r in results for k in r.keys()):
                viz_config["type"] = "bar"  # 条形图

        return viz_config

    def _generate_export_options(self, results: List[Dict]) -> List[Dict]:
        """生成导出选项"""
        return [
            {"format": "json", "label": "JSON", "description": "适合程序处理"},
            {"format": "csv", "label": "CSV", "description": "适合Excel打开"},
            {"format": "html", "label": "HTML", "description": "适合浏览器查看"},
        ]


class ConversationalDataExplorer:
    """对话式数据探索助手"""

    def __init__(self, retriever: UniversalDataRetriever):
        self.retriever = retriever
        self.conversation_context: Dict[str, Any] = {}
        self.history: List[Dict] = []

    async def process_query(self, query: str) -> SearchResult:
        """处理查询"""
        # 结合对话历史理解意图
        full_context = self._build_full_context(query)

        # 执行搜索
        result = await self.retriever.search(query, full_context)

        # 更新历史
        self.history.append({
            "query": query,
            "response": result
        })

        # 更新上下文
        self._update_context(query, result)

        return result

    def _build_full_context(self, query: str) -> Dict[str, Any]:
        """构建完整上下文"""
        context = self.conversation_context.copy()

        # 添加历史中的实体引用
        if self.history and "上次" in query:
            last_result = self.history[-1]["response"]
            context["referenced_entity"] = last_result.results[0] if last_result.results else None

        return context

    def _update_context(self, query: str, result: SearchResult):
        """更新对话上下文"""
        if result.results:
            # 保存最后一个实体的主要信息
            self.conversation_context["last_entity"] = {
                "type": result.intent,
                "sample": result.results[0]
            }

    def clear_history(self):
        """清除历史"""
        self.history = []
        self.conversation_context = {}


class LocalSQLiteSource:
    """本地SQLite数据源"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path("~/.hermes/data.db").expanduser()

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建默认表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS form_submissions (
                id TEXT PRIMARY KEY,
                template_id TEXT,
                template_name TEXT,
                submitter_id TEXT,
                submitter_name TEXT,
                submitted_at TEXT,
                status TEXT,
                workflow_status TEXT,
                data TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_executions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT,
                workflow_name TEXT,
                status TEXT,
                initiator_id TEXT,
                initiator_name TEXT,
                started_at TEXT,
                completed_at TEXT,
                context TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                author_id TEXT,
                author_name TEXT,
                created_at TEXT,
                use_count INTEGER,
                download_count INTEGER
            )
        """)

        conn.commit()
        conn.close()

    async def search(self, parsed: ParsedQuery) -> List[Dict]:
        """搜索数据"""
        results = []

        # 确定表名
        entity = parsed.target_entity.lower()
        if any(keyword in entity for keyword in ["表单", "提交", "申请"]):
            table = "form_submissions"
        elif any(keyword in entity for keyword in ["工作流", "执行"]):
            table = "workflow_executions"
        elif any(keyword in entity for keyword in ["模板"]):
            table = "templates"
        else:
            # 搜索所有表
            tables = ["form_submissions", "workflow_executions", "templates"]
        
        if table:
            tables = [table]

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for table in tables:
            try:
                # 构建查询
                sql = f"SELECT * FROM {table}"
                params = []

                # 添加时间过滤
                if parsed.time_range:
                    time_field = self._get_time_field(table)
                    if time_field:
                        sql += f" WHERE {time_field} >= ? AND {time_field} <= ?"
                        params.extend([
                            parsed.time_range.get("start", ""),
                            parsed.time_range.get("end", "")
                        ])

                # 添加限制
                sql += f" LIMIT {parsed.limit}"

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                for row in rows:
                    results.append(dict(row))

            except Exception as e:
                print(f"Query error for {table}: {e}")

        conn.close()
        return results

    def _get_time_field(self, table: str) -> Optional[str]:
        """获取时间字段"""
        mapping = {
            "form_submissions": "submitted_at",
            "workflow_executions": "started_at",
            "templates": "created_at"
        }
        return mapping.get(table)


# 全局实例
_retriever: Optional[UniversalDataRetriever] = None
_explorer: Optional[ConversationalDataExplorer] = None


def get_data_retriever() -> UniversalDataRetriever:
    """获取数据检索器"""
    global _retriever
    if _retriever is None:
        _retriever = UniversalDataRetriever()

        # 注册内置数据源
        sqlite_source = LocalSQLiteSource()
        _retriever.register_data_source("local_sqlite", sqlite_source)

    return _retriever


def get_conversational_explorer() -> ConversationalDataExplorer:
    """获取对话式探索器"""
    global _explorer
    if _explorer is None:
        _explorer = ConversationalDataExplorer(get_data_retriever())
    return _explorer