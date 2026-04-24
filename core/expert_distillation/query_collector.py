"""
高频查询收集器 - QueryCollector

阶段1: 收集真实用户查询，用于分析高频场景和生成蒸馏数据。

核心功能:
1. 记录用户查询，自动标注领域
2. 统计高频查询和领域分布
3. 导出高质量查询用于蒸馏
4. 与 L4 交互获取专家回答

使用方法:
    collector = QueryCollector()

    # 记录用户查询
    collector.record("分析一下茅台的估值", user_id="user1")

    # 获取高频领域
    stats = collector.get_domain_stats()

    # 生成蒸馏数据
    qa_list = collector.generate_distillation_pairs()

    # 导出查询
    collector.export_queries("high_freq_queries.jsonl")
"""

import json
import re
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from pathlib import Path


@dataclass
class QueryRecord:
    """查询记录"""
    query_id: str
    query: str
    domain: str
    timestamp: str
    user_id: str = ""
    response: str = ""
    response_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_llama_factory_format(self) -> Dict:
        return {
            "instruction": self.query,
            "input": "",
            "output": self.response
        }


@dataclass
class DomainStats:
    """领域统计"""
    domain: str
    query_count: int
    percentage: float
    top_queries: List[str]
    avg_response_time: float


class QueryCollector:
    """
    高频查询收集器

    记录和分析用户查询，为蒸馏数据生成提供真实样本。

    Example:
        collector = QueryCollector()

        # 记录查询
        collector.record("分析茅台股票", user_id="user1")

        # 统计
        stats = collector.get_domain_stats()

        # 生成蒸馏数据
        qa_list = collector.generate_distillation_pairs(min_freq=10)
    """

    DOMAIN_PATTERNS = {
        "金融": [
            r"股票|股价|涨跌|市值|估值|市盈率|财报|营收|利润|投资|基金|债券|收益|风险|资产",
            r"ipo|证券|期货|期权|etf|净值|分红|回购"
        ],
        "技术": [
            r"代码|编程|函数|算法|api|架构|部署|服务器|数据库|cache|队列",
            r"python|java|javascript|sql|git|docker|kubernetes"
        ],
        "法律": [
            r"合同|协议|条款|法律|法规|合规|侵权|违约|诉讼|权利|义务|律师"
        ],
        "医疗": [
            r"症状|诊断|治疗|药物|检查|血压|血糖|ct|mri|医生|医院|手术"
        ],
        "代码": [
            r"bug|error|exception|debug|fix|import|def|class|function|method"
        ],
    }

    def __init__(
        self,
        storage_dir: str = "data/distillation/queries",
        llm_caller: Optional[Callable] = None,
        min_freq_threshold: int = 3
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.llm_caller = llm_caller

        # 查询存储
        self.queries_file = self.storage_dir / "queries.jsonl"
        self.stats_file = self.storage_dir / "stats.json"

        # 内存缓存
        self._queries: List[QueryRecord] = []
        self._domain_counts: Dict[str, int] = defaultdict(int)
        self._query_counts: Dict[str, int] = defaultdict(int)

        # 配置
        self.min_freq_threshold = min_freq_threshold

        # 加载已有数据
        self._load()

    def _normalize_query(self, query: str) -> str:
        """规范化查询（去噪声）"""
        # 移除多余空格
        query = re.sub(r"\s+", " ", query).strip()
        # 移除末尾标点
        query = query.rstrip("？?.,，、")
        return query

    def _detect_domain(self, query: str) -> str:
        """检测查询领域"""
        query_lower = query.lower()
        scores = {}

        for domain, patterns in self.DOMAIN_PATTERNS.items():
            score = sum(len(re.findall(p, query_lower)) for p in patterns)
            if score > 0:
                scores[domain] = score

        if not scores:
            return "通用"

        return max(scores, key=scores.get)

    def record(
        self,
        query: str,
        user_id: str = "",
        response: str = "",
        response_time: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> QueryRecord:
        """
        记录用户查询

        Args:
            query: 用户查询
            user_id: 用户ID
            response: L4回答
            response_time: 响应时间
            metadata: 附加数据

        Returns:
            QueryRecord
        """
        # 规范化
        normalized = self._normalize_query(query)
        domain = self._detect_domain(normalized)

        # 生成ID
        query_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._queries)}"

        # 创建记录
        record = QueryRecord(
            query_id=query_id,
            query=normalized,
            domain=domain,
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            response=response,
            response_time=response_time,
            metadata=metadata or {}
        )

        # 更新内存
        self._queries.append(record)
        self._domain_counts[domain] += 1
        self._query_counts[normalized] += 1

        # 持久化
        self._save_record(record)

        return record

    def batch_record(self, queries: List[str], user_id: str = "") -> List[QueryRecord]:
        """批量记录查询"""
        return [self.record(q, user_id) for q in queries]

    def _save_record(self, record: QueryRecord):
        """保存单条记录"""
        with open(self.queries_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def _load(self):
        """加载已有数据"""
        if not self.queries_file.exists():
            return

        with open(self.queries_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    record = QueryRecord(**data)
                    self._queries.append(record)
                    self._domain_counts[record.domain] += 1
                    self._query_counts[record.query] += 1
                except (json.JSONDecodeError, TypeError):
                    continue

    def get_domain_stats(self) -> List[DomainStats]:
        """
        获取领域统计

        Returns:
            领域统计列表，按查询量降序
        """
        total = len(self._queries) or 1

        stats = []
        for domain, count in self._domain_counts.items():
            # 获取该领域的高频查询
            domain_queries = [q.query for q in self._queries if q.domain == domain]
            query_freq = defaultdict(int)
            for q in domain_queries:
                query_freq[q] += 1

            top_queries = sorted(query_freq.items(), key=lambda x: -x[1])[:5]
            top_queries = [q for q, _ in top_queries]

            # 计算平均响应时间
            domain_responses = [q.response_time for q in self._queries if q.domain == domain]
            avg_time = sum(domain_responses) / len(domain_responses) if domain_responses else 0.0

            stats.append(DomainStats(
                domain=domain,
                query_count=count,
                percentage=count / total * 100,
                top_queries=top_queries,
                avg_response_time=avg_time
            ))

        return sorted(stats, key=lambda x: -x.query_count)

    def get_high_freq_queries(self, min_freq: int = 3) -> List[QueryRecord]:
        """
        获取高频查询

        Args:
            min_freq: 最小频率

        Returns:
            高频查询列表（去重）
        """
        seen = set()
        results = []

        for record in self._queries:
            normalized = record.query
            if self._query_counts[normalized] >= min_freq and normalized not in seen:
                seen.add(normalized)
                results.append(record)

        return sorted(results, key=lambda x: -self._query_counts[x.query])

    def get_recent_queries(self, hours: int = 24) -> List[QueryRecord]:
        """获取最近N小时的查询"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [q for q in self._queries if datetime.fromisoformat(q.timestamp) > cutoff]

    def generate_distillation_pairs(
        self,
        min_freq: int = 5,
        use_existing_responses: bool = True,
        llm_regenerate: bool = False
    ) -> List[QueryRecord]:
        """
        生成蒸馏问答对

        策略:
        1. 如果已有 response 且 use_existing_responses=True，直接使用
        2. 如果需要重新生成，用 LLM 生成专家回答
        3. 如果没有 LLMCaller，返回仅有 query 的记录

        Args:
            min_freq: 最小频率
            use_existing_responses: 使用已有回答
            llm_regenerate: 强制用 LLM 重新生成

        Returns:
            可用于蒸馏的 QueryRecord 列表
        """
        high_freq = self.get_high_freq_queries(min_freq)
        results = []

        for record in high_freq:
            # 跳过没有回答的记录
            if not record.response and not use_existing_responses:
                if self.llm_caller and llm_regenerate:
                    # 用 LLM 重新生成
                    record.response = self._call_llm(record)
                else:
                    continue

            results.append(record)

        return results

    def _call_llm(self, record: QueryRecord) -> str:
        """调用 LLM 生成回答"""
        if not self.llm_caller:
            return ""

        system_prompts = {
            "金融": "你是一位资深金融分析师，请给出专业分析。",
            "技术": "你是一位资深技术专家，请给出专业技术解答。",
            "法律": "你是一位资深律师，请给出专业法律建议。",
            "医疗": "你是一位主任医师，请给出专业医疗建议。",
            "通用": "你是一位知识渊博的助手。"
        }

        system = system_prompts.get(record.domain, system_prompts["通用"])
        return self.llm_caller(record.query, system)

    def enrich_with_responses(
        self,
        queries: List[QueryRecord],
        llm_caller: Optional[Callable] = None
    ) -> List[QueryRecord]:
        """
        为查询列表补充 LLM 回答

        Args:
            queries: 查询列表
            llm_caller: LLM 调用函数

        Returns:
            补充了回答的记录
        """
        caller = llm_caller or self.llm_caller
        if not caller:
            return queries

        for record in queries:
            if not record.response:
                record.response = self._call_llm(record)

        return queries

    def export_queries(
        self,
        filepath: str,
        format: str = "jsonl",
        min_freq: int = 1,
        include_responses: bool = True
    ) -> Path:
        """
        导出查询

        Args:
            filepath: 输出路径
            format: 格式 (jsonl/llama_factory/json)
            min_freq: 最小频率
            include_responses: 是否包含回答

        Returns:
            输出文件路径
        """
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        queries = self.get_high_freq_queries(min_freq)
        if not include_responses:
            queries = [q for q in queries if q.response]

        with open(output_path, "w", encoding="utf-8") as f:
            for record in queries:
                if format == "llama_factory":
                    f.write(json.dumps(record.to_llama_factory_format(), ensure_ascii=False) + "\n")
                else:
                    f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        return output_path

    def get_stats_summary(self) -> Dict:
        """获取统计摘要"""
        return {
            "total_queries": len(self._queries),
            "unique_queries": len(self._query_counts),
            "domain_distribution": dict(self._domain_counts),
            "top_domains": [s.domain for s in self.get_domain_stats()[:5]],
            "storage_file": str(self.queries_file)
        }


# 便捷函数
def create_collector(
    storage_dir: str = "data/distillation/queries",
    llm_caller: Optional[Callable] = None
) -> QueryCollector:
    """创建查询收集器"""
    return QueryCollector(storage_dir=storage_dir, llm_caller=llm_caller)
