"""
Wiki 编译器核心 - Wiki Compiler

整合三层架构，实现 Ingest → Query → Check 持续迭代循环

三层架构：
┌─────────────────────────────────────────────────┐
│           Layer 3: Schema                       │
│    配置文档，定义wiki结构规范、工作流约定         │
├─────────────────────────────────────────────────┤
│              Layer 2: Wiki (LLM操作)             │
│   实体页面│概念页面│主题摘要│对比表格│综合概述   │
├─────────────────────────────────────────────────┤
│            Layer 1: Raw Material (不可变)        │
│        文章│论文│PDF│网页│代码│图片 → raw/       │
└─────────────────────────────────────────────────┘
"""

import os
import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from .models import (
    RawMaterial,
    WikiPage,
    CompiledAnswer,
    Schema,
    MaterialType,
    WikiPageType,
    IngestResult,
    CheckResult,
    CompiledTruth,
    EvidenceEntry
)
from .compiled_cache import CompiledCache
from .compounding_engine import CompoundingEngine


class WikiCompiler:
    """
    Wiki 编译器 - LLM Wiki 的核心引擎

    核心功能：
    1. Ingest: 摄入原材料 → 编译为 Wiki 页面
    2. Query: 查询 → 先查 Wiki → 组合答案
    3. Check: 检查矛盾/过时/孤立页面
    """

    _instance = None
    _lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "WikiCompiler":
        """获取单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        wiki_root: str = "~/.hermes-desktop/wiki",
        cache_path: str = "~/.hermes-desktop/wiki_cache",
        compounder_path: str = "~/.hermes-desktop/wiki_compounder"
    ):
        self.wiki_root = Path(os.path.expanduser(wiki_root))
        self.wiki_root.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.cache = CompiledCache(persist_path=cache_path)
        self.compounder = CompoundingEngine(persist_path=compounder_path)

        # Schema
        self.schema = Schema()

        # 存储
        self._raw_materials: Dict[str, RawMaterial] = {}
        self._wiki_pages: Dict[str, WikiPage] = {}
        self._page_index: Dict[str, List[str]] = {}  # topic -> page_ids

        # 统计
        self._stats = {
            "total_ingests": 0,
            "total_queries": 0,
            "total_checks": 0,
            "avg_query_time": 0.0
        }

        # 回调
        self._ingest_callbacks: List[Callable] = []
        self._query_callbacks: List[Callable] = []

        # 加载数据
        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 加载原材料
        raw_path = self.wiki_root / "raw_materials.json"
        if raw_path.exists():
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._raw_materials = {
                        k: RawMaterial.from_dict(v) for k, v in data.items()
                    }
            except Exception as e:
                logger.info(f"[WikiCompiler] 加载原材料失败: {e}")

        # 加载 Wiki 页面
        pages_path = self.wiki_root / "wiki_pages.json"
        if pages_path.exists():
            try:
                with open(pages_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._wiki_pages = {
                        k: WikiPage.from_dict(v) for k, v in data.items()
                    }
            except Exception as e:
                logger.info(f"[WikiCompiler] 加载 Wiki 页面失败: {e}")

        # 加载 Schema
        schema_path = self.wiki_root / "schema.json"
        if schema_path.exists():
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    self.schema = Schema.from_dict(json.load(f))
            except Exception as e:
                logger.info(f"[WikiCompiler] 加载 Schema 失败: {e}")

        # 构建索引
        self._rebuild_index()

    def _save_data(self):
        """保存数据"""
        try:
            # 保存原材料
            raw_path = self.wiki_root / "raw_materials.json"
            with open(raw_path, 'w', encoding='utf-8') as f:
                json.dump({
                    k: v.to_dict() for k, v in self._raw_materials.items()
                }, f, ensure_ascii=False, indent=2)

            # 保存 Wiki 页面
            pages_path = self.wiki_root / "wiki_pages.json"
            with open(pages_path, 'w', encoding='utf-8') as f:
                json.dump({
                    k: v.to_dict() for k, v in self._wiki_pages.items()
                }, f, ensure_ascii=False, indent=2)

            # 保存 Schema
            schema_path = self.wiki_root / "schema.json"
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(self.schema.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[WikiCompiler] 保存数据失败: {e}")

    def _rebuild_index(self):
        """重建索引"""
        self._page_index.clear()
        for page_id, page in self._wiki_pages.items():
            # 按标签索引
            for tag in page.tags:
                if tag not in self._page_index:
                    self._page_index[tag] = []
                self._page_index[tag].append(page_id)
            # 按类型索引
            page_type = page.page_type.value
            if page_type not in self._page_index:
                self._page_index[page_type] = []
            self._page_index[page_type].append(page_id)

    # ==================== Ingest ====================

    def ingest(
        self,
        content: str,
        title: str,
        material_type: MaterialType = MaterialType.UNKNOWN,
        source_url: str = "",
        tags: List[str] = None,
        llm_compile_fn: Callable[[str, str], Dict] = None
    ) -> IngestResult:
        """
        摄入原材料并编译为 Wiki 页面

        Args:
            content: 原材料内容
            title: 标题
            material_type: 原材料类型
            source_url: 来源 URL
            tags: 标签
            llm_compile_fn: LLM 编译函数，签名为 (content, hint) -> {summary, key_points, entities, concepts}

        Returns:
            IngestResult
        """
        self._stats["total_ingests"] += 1
        start_time = time.time()

        result = IngestResult(success=False)

        try:
            # 1. 创建原材料
            material = RawMaterial(
                title=title,
                content=content,
                material_type=material_type,
                source_url=source_url
            )
            self._raw_materials[material.id] = material
            result.material_id = material.id

            # 2. 调用 LLM 编译（如果提供了函数）
            compiled_info = {
                "summary": content[:200],
                "key_points": [],
                "entities": [],
                "concepts": []
            }

            if llm_compile_fn:
                try:
                    compiled_info = llm_compile_fn(content, title)
                except Exception as e:
                    logger.info(f"[WikiCompiler] LLM编译失败: {e}")

            # 3. 创建源摘要页
            source_page = WikiPage(
                title=title,
                page_type=WikiPageType.SOURCE,
                compiled_truth=CompiledTruth(
                    summary=compiled_info.get("summary", content[:200]),
                    key_points=compiled_info.get("key_points", [])
                ),
                source_material_ids=[material.id],
                tags=tags or []
            )
            source_page.add_evidence(
                source_id=material.id,
                source_title=title,
                content=content[:500],
                context="原材料完整引用"
            )
            self._wiki_pages[source_page.id] = source_page
            result.created_pages.append(source_page.id)

            # 4. 创建/更新实体页
            for entity_name in compiled_info.get("entities", []):
                entity_page = self._get_or_create_entity_page(entity_name)
                entity_page.add_evidence(
                    source_id=material.id,
                    source_title=title,
                    content=f"在\"{title}\"中被提及",
                    context=f"相关引用: {content[:200]}"
                )
                entity_page.source_material_ids.append(material.id)
                if entity_page.id not in result.created_pages:
                    result.created_pages.append(entity_page.id)

            # 5. 创建/更新概念页
            for concept_name in compiled_info.get("concepts", []):
                concept_page = self._get_or_create_concept_page(concept_name)
                concept_page.add_evidence(
                    source_id=material.id,
                    source_title=title,
                    content=content[:300],
                    context=f"来自\"{title}\""
                )
                if concept_page.id not in result.created_pages:
                    result.created_pages.append(concept_page.id)

            # 6. 丰富复利上下文
            self.compounder.enrich_with_new_knowledge(
                content=content,
                topic=title,
                insights=compiled_info.get("key_points", []),
                source_id=material.id
            )

            # 7. 触发回调
            for callback in self._ingest_callbacks:
                try:
                    callback(material, result)
                except Exception as e:
                    logger.info(f"[WikiCompiler] Ingest回调失败: {e}")

            result.success = True
            self._save_data()
            self._rebuild_index()

        except Exception as e:
            result.error = str(e)
            logger.info(f"[WikiCompiler] Ingest失败: {e}")

        return result

    def _get_or_create_entity_page(self, entity_name: str) -> WikiPage:
        """获取或创建实体页"""
        # 查找是否已存在
        for page in self._wiki_pages.values():
            if page.title == entity_name and page.page_type == WikiPageType.ENTITY:
                return page

        # 创建新页面
        page = WikiPage(
            title=entity_name,
            page_type=WikiPageType.ENTITY,
            tags=["人物", "公司", "项目"]  # 默认标签
        )
        self._wiki_pages[page.id] = page
        return page

    def _get_or_create_concept_page(self, concept_name: str) -> WikiPage:
        """获取或创建概念页"""
        # 查找是否已存在
        for page in self._wiki_pages.values():
            if page.title == concept_name and page.page_type == WikiPageType.CONCEPT:
                return page

        # 创建新页面
        page = WikiPage(
            title=concept_name,
            page_type=WikiPageType.CONCEPT,
            tags=["概念"]
        )
        self._wiki_pages[page.id] = page
        return page

    def register_ingest_callback(self, callback: Callable):
        """注册摄入回调"""
        self._ingest_callbacks.append(callback)

    # ==================== Query ====================

    def query(
        self,
        query_text: str,
        use_cache: bool = True,
        use_compounding: bool = True,
        llm_answer_fn: Callable[[str, List[WikiPage]], Dict] = None
    ) -> CompiledAnswer:
        """
        查询 Wiki

        Args:
            query_text: 查询文本
            use_cache: 是否使用缓存
            use_compounding: 是否使用复利上下文
            llm_answer_fn: LLM 回答函数，签名为 (query, context_pages) -> {answer, reasoning_chain, worth_saving}

        Returns:
            CompiledAnswer
        """
        self._stats["total_queries"] += 1
        start_time = time.time()

        answer = CompiledAnswer(query=query_text)

        try:
            # 1. 检查缓存
            if use_cache:
                cached = self.cache.get(
                    query=query_text,
                    wiki_pages=list(self._wiki_pages.values()),
                    sources=list(self._raw_materials.keys())
                )
                if cached:
                    answer.answer = cached["response"]
                    answer.confidence = cached["confidence"]
                    answer.referenced_pages = cached.get("wiki_pages", [])
                    return answer

            # 2. 获取复利上下文
            enriched_query = query_text
            compounding_bonus = 0.0
            if use_compounding:
                enriched_query, compounding_bonus = self.compounder.get_context_for_query(query_text)

            # 3. 搜索相关页面
            relevant_pages = self._search_relevant_pages(enriched_query)

            if relevant_pages:
                # 4. 调用 LLM 生成答案
                if llm_answer_fn:
                    try:
                        llm_result = llm_answer_fn(enriched_query, relevant_pages)
                        answer.answer = llm_result.get("answer", "")
                        answer.reasoning_chain = llm_result.get("reasoning_chain", [])

                        # 检查是否值得保存
                        if llm_result.get("worth_saving"):
                            answer.worth_saving = True
                            answer.suggested_title = llm_result.get("suggested_title", query_text[:50])

                        # 编译好答案
                        self.cache.compile_good_answer(
                            query=query_text,
                            answer=answer.answer,
                            referenced_pages=[p.id for p in relevant_pages],
                            referenced_sources=answer.referenced_sources,
                            reasoning_chain=answer.reasoning_chain
                        )
                    except Exception as e:
                        logger.info(f"[WikiCompiler] LLM回答失败: {e}")
                        # 使用默认答案
                        answer.answer = self._compose_default_answer(relevant_pages)
                else:
                    # 无 LLM，使用默认组合
                    answer.answer = self._compose_default_answer(relevant_pages)
            else:
                # 无相关页面
                answer.answer = "暂无相关知识，请先摄入相关原材料。"
                answer.confidence = 0.1

            # 设置引用
            answer.referenced_pages = [p.id for p in relevant_pages]
            answer.confidence = min(0.95, answer.confidence + compounding_bonus)

            # 5. 保存到缓存
            if use_cache:
                self.cache.set(
                    query=query_text,
                    response=answer.answer,
                    wiki_pages=answer.referenced_pages,
                    sources=answer.referenced_sources,
                    confidence=answer.confidence,
                    worth_compiling=answer.worth_saving
                )

        except Exception as e:
            logger.info(f"[WikiCompiler] Query失败: {e}")
            answer.answer = f"查询失败: {e}"
            answer.confidence = 0.0

        # 更新统计
        elapsed = time.time() - start_time
        self._stats["avg_query_time"] = (
            (self._stats["avg_query_time"] * (self._stats["total_queries"] - 1) + elapsed)
            / self._stats["total_queries"]
        )

        return answer

    def _search_relevant_pages(self, query: str) -> List[WikiPage]:
        """搜索相关页面"""
        import re
from core.logger import get_logger
logger = get_logger('wiki_compiler.compiler')

        query_lower = query.lower()
        query_keywords = set(re.findall(r'[\w]+', query_lower))

        scored_pages = []
        for page in self._wiki_pages.values():
            score = 0.0

            # 标题匹配
            if any(kw in page.title.lower() for kw in query_keywords):
                score += 0.5

            # 标签匹配
            if any(kw in tag.lower() for kw in query_keywords for tag in page.tags):
                score += 0.3

            # 内容匹配
            summary = page.compiled_truth.summary.lower()
            if any(kw in summary for kw in query_keywords):
                score += 0.2

            # 证据匹配
            for entry in page.evidence_timeline:
                if any(kw in entry.content.lower() for kw in query_keywords):
                    score += 0.1
                    break

            # 复利加成
            if page.compiled_truth.key_points:
                score += 0.1

            if score > 0.2:
                scored_pages.append((page, score))

        # 按分数排序
        scored_pages.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in scored_pages[:10]]

    def _compose_default_answer(self, pages: List[WikiPage]) -> str:
        """组合默认答案"""
        if not pages:
            return "暂无相关知识。"

        lines = []
        lines.append("根据已有知识：\n")

        for page in pages[:3]:
            lines.append(f"## {page.title}")
            if page.compiled_truth.summary:
                lines.append(page.compiled_truth.summary)
            if page.compiled_truth.key_points:
                lines.append("关键点：")
                for point in page.compiled_truth.key_points[:3]:
                    lines.append(f"- {point}")
            lines.append("")

        return "\n".join(lines)

    def register_query_callback(self, callback: Callable):
        """注册查询回调"""
        self._query_callbacks.append(callback)

    # ==================== Check ====================

    def check(self) -> CheckResult:
        """
        检查 Wiki 的一致性

        Returns:
            CheckResult
        """
        self._stats["total_checks"] += 1
        result = CheckResult()

        try:
            # 1. 检测矛盾页面
            result.contradictions = self._find_contradictions()

            # 2. 检测过时页面
            result.outdated_pages = self._find_outdated_pages()

            # 3. 检测孤立页面（无入站链接）
            result.orphan_pages = self._find_orphan_pages()

            # 4. 检测缺失的交叉引用
            result.missing_links = self._find_missing_links()

            # 5. 生成建议
            if result.contradictions:
                result.suggestions.append(f"发现 {len(result.contradictions)} 个矛盾页面，请检查。")
            if result.orphan_pages:
                result.suggestions.append(f"发现 {len(result.orphan_pages)} 个孤立页面，考虑添加链接。")
            if result.outdated_pages:
                result.suggestions.append(f"发现 {len(result.outdated_pages)} 个过时页面，考虑更新。")

        except Exception as e:
            logger.info(f"[WikiCompiler] Check失败: {e}")

        return result

    def _find_contradictions(self) -> List[Dict]:
        """找出矛盾页面"""
        contradictions = []
        # 简化实现：检查是否有页面更新后与之前矛盾
        for page in self._wiki_pages.values():
            if len(page.evidence_timeline) >= 2:
                # 检查是否有相反的证据
                first_evidence = page.evidence_timeline[0].content.lower()
                latest_evidence = page.evidence_timeline[-1].content.lower()

                # 简化的矛盾检测
                negations = ["不是", "没有", "不能", "不会", "不会", "不等于"]
                if any(neg in first_evidence and neg in latest_evidence and first_evidence != latest_evidence
                       for neg in negations):
                    contradictions.append({
                        "page_id": page.id,
                        "title": page.title,
                        "first": page.evidence_timeline[0].content[:100],
                        "latest": page.evidence_timeline[-1].content[:100]
                    })

        return contradictions

    def _find_outdated_pages(self) -> List[Dict]:
        """找出过时页面"""
        outdated = []
        threshold = 86400 * 30  # 30天未更新

        for page in self._wiki_pages.values():
            if time.time() - page.last_modified > threshold:
                outdated.append({
                    "page_id": page.id,
                    "title": page.title,
                    "last_modified": page.last_modified,
                    "days_ago": int((time.time() - page.last_modified) / 86400)
                })

        return outdated

    def _find_orphan_pages(self) -> List[Dict]:
        """找出孤立页面"""
        orphans = []

        # 统计每个页面的入站链接数
        inbound_count = {page_id: 0 for page_id in self._wiki_pages}
        for page in self._wiki_pages.values():
            for ref in page.cross_references:
                if ref.target_page_id in inbound_count:
                    inbound_count[ref.target_page_id] += 1

        # 没有入站链接的页面是孤立的（除了首页）
        for page_id, count in inbound_count.items():
            if count == 0 and page_id not in [p.id for p in self._wiki_pages.values() if p.page_type == WikiPageType.INDEX]:
                page = self._wiki_pages[page_id]
                orphans.append({
                    "page_id": page_id,
                    "title": page.title,
                    "type": page.page_type.value
                })

        return orphans

    def _find_missing_links(self) -> List[Dict]:
        """找出缺失的交叉引用"""
        missing = []

        # 简化实现：检查是否有概念被多次提及但未建立链接
        concept_pages = [p for p in self._wiki_pages.values() if p.page_type == WikiPageType.CONCEPT]

        for page in self._wiki_pages.values():
            if page.page_type == WikiPageType.SOURCE:
                for concept_page in concept_pages:
                    if concept_page.id != page.id:
                        # 检查是否在内容中提到但未链接
                        if (concept_page.title in page.compiled_truth.summary or
                                any(concept_page.title in e.content for e in page.evidence_timeline)):
                            # 检查是否已有链接
                            has_link = any(r.target_page_id == concept_page.id for r in page.cross_references)
                            if not has_link:
                                missing.append({
                                    "from_page": page.id,
                                    "from_title": page.title,
                                    "to_page": concept_page.id,
                                    "to_title": concept_page.title,
                                    "suggestion": f"考虑添加与 [[{concept_page.id}|{concept_page.title}]] 的链接"
                                })

        return missing[:20]  # 限制数量

    # ==================== 公共接口 ====================

    def get_page(self, page_id: str) -> Optional[WikiPage]:
        """获取页面"""
        return self._wiki_pages.get(page_id)

    def search_pages(self, query: str) -> List[WikiPage]:
        """搜索页面"""
        return self._search_relevant_pages(query)

    def get_all_pages(self, page_type: WikiPageType = None) -> List[WikiPage]:
        """获取所有页面"""
        if page_type:
            return [p for p in self._wiki_pages.values() if p.page_type == page_type]
        return list(self._wiki_pages.values())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "raw_materials": len(self._raw_materials),
            "wiki_pages": len(self._wiki_pages),
            "cache_stats": self.cache.get_stats(),
            "compounding_stats": self.compounder.get_compounding_insights()
        }

    def export_markdown(self, output_dir: str = None) -> str:
        """导出为 Markdown 文件"""
        if output_dir is None:
            output_dir = self.wiki_root / "export"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 导出 Schema
        with open(output_dir / "CLAUDE.md", 'w', encoding='utf-8') as f:
            f.write(self.schema.to_markdown())

        # 导出页面
        for page in self._wiki_pages.values():
            filename = f"{page.id}.md"
            with open(output_dir / filename, 'w', encoding='utf-8') as f:
                f.write(page.to_markdown())

        return str(output_dir)


# 全局单例
def get_wiki_compiler() -> WikiCompiler:
    """获取 Wiki 编译器单例"""
    return WikiCompiler.get_instance()
