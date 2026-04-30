"""
知识库管理器 (Knowledge Base Manager)

实现三层架构：
- raw/: 原始素材（只读）
- wiki/: AI编译知识库（AI写）
- outputs/: AI生成结果（可选）

三大核心操作：
1. Ingest（摄入）：读取raw/，更新wiki/
2. Query（查询）：检索wiki/，综合作答
3. Lint（健康检查）：巡检wiki/，保持健康

设计模式：单例模式 + 策略模式
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 导入共享基础设施
from client.src.business.shared import (
    EventBus,
    CacheLayer,
    get_event_bus,
    get_cache,
    EVENTS
)

# 导入现有模块
from client.src.business.fusion_rag import (
    create_industry_governance,
    create_fusion_rag,
    create_triple_chain_engine,
    get_term_extractor
)
from client.src.business.llm_wiki import create_llm_wiki_integration


@dataclass
class WikiPage:
    """Wiki页面"""
    title: str
    slug: str  # 文件名（小写、连字符）
    summary: str  # 200字内核心摘要
    content: str  # 核心知识点
    references: List[str] = field(default_factory=list)  # 来源引用
    related_topics: List[str] = field(default_factory=list)  # 关联主题
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LintIssue:
    """健康检查问题"""
    issue_type: str  # contradictions, gaps, orphans, outdated
    page_title: str
    description: str
    severity: str = "medium"  # low, medium, high
    suggestion: str = ""


@dataclass
class IngestResult:
    """摄入结果"""
    files_processed: int
    terms_extracted: int
    pages_updated: int
    new_pages_created: int
    errors: List[str] = field(default_factory=list)


@dataclass
class QueryResult:
    """查询结果"""
    answer: str
    sources: List[Dict[str, Any]]
    related_topics: List[str]
    confidence: float


class KnowledgeBaseManager:
    """
    知识库管理器
    
    核心功能：
    1. Ingest（摄入）：读取raw/新资料，更新wiki/相关页面
    2. Query（查询）：检索wiki/，综合作答，附上引用
    3. Lint（健康检查）：巡检wiki/，找矛盾、补缺口、清理孤儿页面
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        # 获取共享基础设施
        self.event_bus = get_event_bus()
        self.cache = get_cache()
        
        # 导入现有模块
        self.governance = create_industry_governance()
        self.fusion_rag = create_fusion_rag()
        self.triple_chain_engine = create_triple_chain_engine()
        self.wiki_integration = create_llm_wiki_integration()
        self.term_extractor = get_term_extractor()
        
        # 知识库路径配置
        self.base_path = Path("knowledge_base")
        self.raw_path = self.base_path / "raw"
        self.wiki_path = self.base_path / "wiki"
        self.outputs_path = self.base_path / "outputs"
        
        # 规则文件
        self.rules_file = self.base_path / "KNOWLEDGE_RULES.md"
        
        # 初始化目录结构
        self._init_directories()
        
        # 加载规则
        self.rules = self._load_rules()
        
        self._initialized = True
        print("[KnowledgeBaseManager] 初始化完成")
    
    def _init_directories(self):
        """初始化三层目录结构"""
        for path in [self.raw_path, self.wiki_path, self.outputs_path]:
            path.mkdir(parents=True, exist_ok=True)
        print(f"[KnowledgeBaseManager] 目录结构已创建: {self.base_path}")
    
    def _load_rules(self) -> Dict[str, Any]:
        """加载知识库规则"""
        if self.rules_file.exists():
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                content = f.read()
                return self._parse_rules(content)
        else:
            # 默认规则
            return self._get_default_rules()
    
    def _parse_rules(self, content: str) -> Dict[str, Any]:
        """解析规则文件"""
        rules = {
            "purpose": "",
            "folder_rules": [],
            "page_rules": [],
            "workflow": []
        }
        
        # 简单解析 Markdown
        sections = re.split(r'^## ', content, flags=re.MULTILINE)
        
        for section in sections:
            if section.startswith('知识库定位'):
                rules["purpose"] = section.replace('知识库定位', '').strip()
            elif section.startswith('文件夹规则'):
                lines = section.split('\n')[1:]
                rules["folder_rules"] = [l.strip('- ') for l in lines if l.strip()]
            elif section.startswith('页面规则'):
                lines = section.split('\n')[1:]
                rules["page_rules"] = [l.strip('- ') for l in lines if l.strip()]
            elif section.startswith('工作流'):
                lines = section.split('\n')[1:]
                rules["workflow"] = [l.strip('123. ') for l in lines if l.strip()]
        
        return rules
    
    def _get_default_rules(self) -> Dict[str, Any]:
        """获取默认规则"""
        return {
            "purpose": "专注于工业AI领域的专业知识库",
            "folder_rules": [
                "raw/: 原始素材，只读不写",
                "wiki/: AI维护的结构化知识库",
                "wiki/INDEX.md: 总目录",
                "outputs/: AI生成结果"
            ],
            "page_rules": [
                "每个主题1个wiki页面",
                "页面开头：1段200字内核心摘要",
                "中间：分点核心知识点",
                "结尾：关联主题和来源引用"
            ],
            "workflow": [
                "摄入：raw/新增资料→AI读取→更新wiki/",
                "查询：提问→AI检索wiki/→综合作答",
                "维护：定期巡检→找矛盾→补缺口"
            ]
        }
    
    def create_default_rules(self):
        """创建默认规则文件"""
        content = """# 知识库规则

## 知识库定位
专注于【工业AI】领域的专业知识库，用于积累、整理、关联工业场景知识，形成可检索、可复用、可增长的知识体系。

## 文件夹规则
- raw/: 原始素材，只读不写，按日期/来源分类；
- wiki/: AI维护的结构化知识库，Markdown格式；
- wiki/INDEX.md: 总目录，列出所有主题+1行描述；
- outputs/: AI生成的报告、分析结果；
- 所有wiki页面用[[主题名]]关联相关知识。

## 页面规则
- 每个主题1个wiki页面，文件名：主题名.md（小写、连字符）；
- 页面开头：1段200字内核心摘要；
- 中间：分点核心知识点、关键数据、重要结论；
- 结尾：关联主题（[[链接]]）、来源引用。

## 工作流
1. 摄入：raw/新增资料→AI读取→更新wiki/相关页面；
2. 查询：提问→AI检索wiki/→综合作答→引用来源；
3. 维护：定期巡检→找矛盾→补缺口→更新索引。
"""
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[KnowledgeBaseManager] 规则文件已创建: {self.rules_file}")
    
    # ============ Ingest（摄入） ============
    
    async def ingest_from_raw(self) -> IngestResult:
        """
        从 raw/ 读取新资料并更新 wiki/
        
        复用现有模块：
        - LLM Wiki 的文档解析能力
        - FusionRAG 的知识入库能力
        - DeepKE-LLM 的术语抽取能力
        
        Returns:
            摄入结果
        """
        result = IngestResult(
            files_processed=0,
            terms_extracted=0,
            pages_updated=0,
            new_pages_created=0
        )
        
        try:
            # 扫描 raw/ 文件夹
            raw_files = list(self.raw_path.glob("*.md")) + list(self.raw_path.glob("*.txt"))
            raw_files += list(self.raw_path.rglob("**/*.md")) + list(self.raw_path.rglob("**/*.txt"))
            
            for file_path in raw_files:
                try:
                    # 检查是否已处理过
                    if self._is_file_processed(file_path):
                        continue
                    
                    # 读取文件内容
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 1. 使用 LLM Wiki 解析文档（复用现有能力）
                    if self.wiki_integration:
                        terms = self.wiki_integration.extract_terms_from_text(content, self._get_current_industry())
                        relations = self.wiki_integration.extract_relations_from_text(content, self._get_current_industry())
                    else:
                        # 降级方案：使用 DeepKE-LLM 术语抽取器
                        terms = self.term_extractor.extract_terms(content)
                        relations = self.term_extractor.extract_relations(content)
                    
                    result.terms_extracted += len(terms)
                    
                    # 2. 使用行业治理添加术语（复用现有能力）
                    for term in terms:
                        term_name = term.get("term", "")
                        if term_name:
                            self.governance.add_term(term_name, term_name, self._get_current_industry())
                    
                    # 3. 更新 wiki 页面（内部实现，因为这是文件级操作）
                    updated, created = await self._update_wiki_pages(terms, relations, file_path)
                    result.pages_updated += updated
                    result.new_pages_created += created
                    result.files_processed += 1
                    
                    # 4. 将知识入库到 FusionRAG（复用现有能力）
                    if self.fusion_rag:
                        self.fusion_rag.add_document({
                            "title": file_path.stem,
                            "content": content[:5000],
                            "source": str(file_path),
                            "industry": self._get_current_industry()
                        })
                    
                    # 标记文件已处理
                    self._mark_file_processed(file_path)
                    
                except Exception as e:
                    result.errors.append(f"处理 {file_path} 失败: {e}")
            
            # 更新索引
            self._update_index()
            
            # 发布事件
            self.event_bus.publish(EVENTS["KNOWLEDGE_INGESTED"], {
                "result": result.__dict__,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            result.errors.append(f"摄入过程失败: {e}")
        
        return result
    
    def _get_current_industry(self) -> str:
        """获取当前行业（从配置或治理模块）"""
        if hasattr(self.governance, 'target_industry'):
            return self.governance.target_industry
        return "通用"
    
    def _is_file_processed(self, file_path: Path) -> bool:
        """检查文件是否已处理"""
        cache_key = f"ingested_{file_path.name}"
        return self.cache.get(cache_key) is not None
    
    def _mark_file_processed(self, file_path: Path):
        """标记文件已处理"""
        cache_key = f"ingested_{file_path.name}"
        self.cache.set(cache_key, True, ttl=86400 * 30)  # 30天
    
    async def _update_wiki_pages(self, terms: List[Dict], relations: List[Dict], 
                                  source_file: Path) -> tuple:
        """更新 wiki 页面"""
        updated = 0
        created = 0
        
        for term in terms:
            term_name = term.get("term", "")
            if not term_name:
                continue
            
            # 创建或更新页面
            slug = self._create_slug(term_name)
            page_path = self.wiki_path / f"{slug}.md"
            
            if page_path.exists():
                # 更新现有页面
                await self._update_page(page_path, term, source_file)
                updated += 1
            else:
                # 创建新页面
                await self._create_page(page_path, term, source_file)
                created += 1
        
        return updated, created
    
    def _create_slug(self, title: str) -> str:
        """创建页面slug"""
        return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    
    async def _create_page(self, page_path: Path, term: Dict, source_file: Path):
        """创建新页面"""
        content = f"""# {term.get('term', '')}

## 核心摘要
{term.get('definition', '暂无摘要')}

## 核心知识点
- 术语类别: {term.get('category', '未分类')}
- 置信度: {term.get('confidence', 0):.2f}

## 来源引用
- [{source_file.name}]({source_file})

## 关联主题
"""
        
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    async def _update_page(self, page_path: Path, term: Dict, source_file: Path):
        """更新现有页面"""
        with open(page_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 添加来源引用（如果不存在）
        source_name = source_file.name
        if source_name not in content:
            content += f"\n- [{source_name}]({source_file})"
        
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _update_index(self):
        """更新 INDEX.md"""
        pages = list(self.wiki_path.glob("*.md"))
        pages = [p for p in pages if p.name != "INDEX.md"]
        
        index_content = "# 知识库总目录\n\n"
        index_content += f"> 共 {len(pages)} 个主题\n\n"
        index_content += "## 主题列表\n\n"
        
        for page in sorted(pages):
            title = page.stem.replace('-', ' ').title()
            index_content += f"- [[{title}]]\n"
        
        with open(self.wiki_path / "INDEX.md", 'w', encoding='utf-8') as f:
            f.write(index_content)
    
    # ============ Query（查询） ============
    
    async def query(self, question: str) -> QueryResult:
        """
        查询知识库
        
        复用现有模块：
        - LLM Wiki 的搜索能力（search_with_governance, search_with_triple_chain）
        - FusionRAG 的三重链验证和检索能力
        
        Args:
            question: 用户问题
            
        Returns:
            查询结果（含答案、来源、关联主题）
        """
        # 1. 优先使用 LLM Wiki 进行检索（已集成 FusionRAG 能力）
        if self.wiki_integration:
            results = self.wiki_integration.search_with_governance(question, top_k=10)
            
            # 2. 使用三重链验证（LLM Wiki 已集成）
            triple_chain_result = self.wiki_integration.search_with_triple_chain(question)
            answer = triple_chain_result.get("answer", "")
            
            # 3. 提取来源和关联主题
            sources = []
            for item in results:
                sources.append({
                    "title": item.get("title", ""),
                    "source": item.get("source_attribution", ""),
                    "score": item.get("score", 0)
                })
            
            related_topics = triple_chain_result.get("reasoning", [])[:5]
            
            return QueryResult(
                answer=answer,
                sources=sources,
                related_topics=related_topics,
                confidence=triple_chain_result.get("overall_confidence", 0.85)
            )
        else:
            # 降级方案：直接使用 FusionRAG
            results = self.fusion_rag.search_with_governance(question)
            verified = self.triple_chain_engine.verify(results)
            answer = self._synthesize_answer(verified)
            sources = self._extract_sources(verified)
            related_topics = self._extract_related_topics(verified)
            
            return QueryResult(
                answer=answer,
                sources=sources,
                related_topics=related_topics,
                confidence=0.85
            )
    
    def _synthesize_answer(self, results: List[Dict]) -> str:
        """综合答案"""
        if not results:
            return "未找到相关知识。"
        
        # 简单综合：取前3条结果
        answer = ""
        for i, result in enumerate(results[:3], 1):
            content = result.get("content", "")[:300]
            answer += f"{i}. {content}\n\n"
        
        return answer.strip()
    
    def _extract_sources(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """提取来源"""
        sources = []
        for result in results:
            sources.append({
                "title": result.get("title", ""),
                "source": result.get("source", ""),
                "score": result.get("score", 0)
            })
        return sources
    
    def _extract_related_topics(self, results: List[Dict]) -> List[str]:
        """提取关联主题"""
        topics = set()
        for result in results:
            topics.add(result.get("title", ""))
        return list(topics)
    
    def save_to_wiki(self, title: str, content: str, references: List[str] = None):
        """
        将答案保存回 wiki
        
        Args:
            title: 页面标题
            content: 内容
            references: 引用来源
        """
        slug = self._create_slug(title)
        page_path = self.wiki_path / f"{slug}.md"
        
        page_content = f"""# {title}

## 核心摘要
{content[:200]}...

## 详细内容
{content}

## 来源引用
"""
        for ref in references or []:
            page_content += f"- {ref}\n"
        
        page_content += "\n## 关联主题\n"
        
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(page_content)
        
        # 更新索引
        self._update_index()
        
        print(f"[KnowledgeBaseManager] 页面已保存: {page_path}")
    
    # ============ Lint（健康检查） ============
    
    async def lint(self) -> List[LintIssue]:
        """
        巡检 wiki/ 所有页面
        
        复用现有模块：
        - FusionRAG 的行业治理和反馈学习能力
        - LLM Wiki 的验证能力
        
        Returns:
            问题列表
        """
        issues = []
        
        # 1. 使用 FusionRAG 行业治理检查术语冲突（复用现有能力）
        if hasattr(self.governance, 'check_term_conflicts'):
            conflicts = self.governance.check_term_conflicts()
            for conflict in conflicts:
                issues.append(LintIssue(
                    issue_type="contradictions",
                    page_title=conflict.get("term", ""),
                    description=f"术语冲突: {conflict.get('message', '')}",
                    severity="high"
                ))
        
        # 2. 使用 FusionRAG 反馈学习检查低质量内容（复用现有能力）
        if hasattr(self.fusion_rag, 'get_low_quality_docs'):
            low_quality_docs = self.fusion_rag.get_low_quality_docs()
            for doc in low_quality_docs:
                issues.append(LintIssue(
                    issue_type="gaps",
                    page_title=doc.get("title", ""),
                    description=f"低质量内容: 相关性评分低",
                    severity="medium"
                ))
        
        # 3. 检查孤儿页面（文件级操作）
        issues.extend(await self._find_orphans())
        
        # 4. 检查内容缺口（文件级操作）
        issues.extend(await self._find_gaps())
        
        # 5. 检查过期信息（文件级操作）
        issues.extend(await self._find_outdated())
        
        # 6. 检查知识矛盾（文件级操作）
        issues.extend(await self._find_contradictions())
        
        # 发布事件
        self.event_bus.publish(EVENTS["KNOWLEDGE_LINTED"], {
            "issues_count": len(issues),
            "timestamp": datetime.now().isoformat()
        })
        
        return issues
    
    async def _find_orphans(self) -> List[LintIssue]:
        """查找孤儿页面（无关联）"""
        issues = []
        pages = list(self.wiki_path.glob("*.md"))
        
        for page in pages:
            if page.name == "INDEX.md":
                continue
            
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否有 [[链接]]
            if "[[" not in content:
                issues.append(LintIssue(
                    issue_type="orphans",
                    page_title=page.stem.replace('-', ' ').title(),
                    description="页面没有任何关联链接",
                    severity="medium",
                    suggestion="添加 [[关联主题]] 链接"
                ))
        
        return issues
    
    async def _find_gaps(self) -> List[LintIssue]:
        """查找内容缺口"""
        issues = []
        pages = list(self.wiki_path.glob("*.md"))
        
        for page in pages:
            if page.name == "INDEX.md":
                continue
            
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查摘要是否存在
            if "## 核心摘要" not in content:
                issues.append(LintIssue(
                    issue_type="gaps",
                    page_title=page.stem.replace('-', ' ').title(),
                    description="缺少核心摘要",
                    severity="high",
                    suggestion="添加 ## 核心摘要 章节"
                ))
        
        return issues
    
    async def _find_outdated(self) -> List[LintIssue]:
        """查找过期信息"""
        issues = []
        pages = list(self.wiki_path.glob("*.md"))
        
        for page in pages:
            if page.name == "INDEX.md":
                continue
            
            mtime = datetime.fromtimestamp(page.stat().st_mtime)
            days_old = (datetime.now() - mtime).days
            
            if days_old > 90:
                issues.append(LintIssue(
                    issue_type="outdated",
                    page_title=page.stem.replace('-', ' ').title(),
                    description=f"页面已 {days_old} 天未更新",
                    severity="low",
                    suggestion="检查内容是否需要更新"
                ))
        
        return issues
    
    async def _find_contradictions(self) -> List[LintIssue]:
        """查找知识矛盾（简化版）"""
        issues = []
        
        # 简化实现：检查重复页面
        pages = list(self.wiki_path.glob("*.md"))
        page_names = {}
        
        for page in pages:
            if page.name == "INDEX.md":
                continue
            
            title = page.stem.replace('-', ' ').title()
            if title in page_names:
                issues.append(LintIssue(
                    issue_type="contradictions",
                    page_title=title,
                    description=f"存在重复页面: {page_names[title]} 和 {page.name}",
                    severity="high",
                    suggestion="合并重复页面"
                ))
            else:
                page_names[title] = page.name
        
        return issues
    
    async def auto_fix(self, issues: List[LintIssue]) -> int:
        """
        自动修复问题
        
        Args:
            issues: 问题列表
            
        Returns:
            修复数量
        """
        fixed = 0
        
        for issue in issues:
            try:
                if issue.issue_type == "orphans":
                    await self._fix_orphan(issue)
                    fixed += 1
                elif issue.issue_type == "gaps":
                    await self._fix_gap(issue)
                    fixed += 1
            except Exception as e:
                print(f"修复 {issue.page_title} 失败: {e}")
        
        return fixed
    
    async def _fix_orphan(self, issue: LintIssue):
        """修复孤儿页面"""
        slug = self._create_slug(issue.page_title)
        page_path = self.wiki_path / f"{slug}.md"
        
        if page_path.exists():
            with open(page_path, 'a', encoding='utf-8') as f:
                f.write("\n## 关联主题\n")
                f.write("[[工业AI]]\n")
    
    async def _fix_gap(self, issue: LintIssue):
        """修复内容缺口"""
        slug = self._create_slug(issue.page_title)
        page_path = self.wiki_path / f"{slug}.md"
        
        if page_path.exists():
            with open(page_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "## 核心摘要" not in content:
                content = f"# {issue.page_title}\n\n## 核心摘要\n暂无摘要\n\n" + content
                with open(page_path, 'w', encoding='utf-8') as f:
                    f.write(content)


# 创建全局实例
_knowledge_manager = None


def get_knowledge_manager() -> KnowledgeBaseManager:
    """获取知识库管理器实例"""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeBaseManager()
    return _knowledge_manager


__all__ = [
    "WikiPage",
    "LintIssue",
    "IngestResult",
    "QueryResult",
    "KnowledgeBaseManager",
    "get_knowledge_manager"
]