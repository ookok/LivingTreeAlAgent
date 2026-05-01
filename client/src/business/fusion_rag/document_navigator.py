"""
文档导航器 (Document Navigator)
基于 Doc-V* 的主动导航设计

功能:
- 缩略图概览扫描
- 语义检索导航
- 精准区域获取
- 选择性注意力机制
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class NavigationMode(Enum):
    """导航模式"""
    OVERVIEW = "overview"      # 概览模式
    SEMANTIC = "semantic"      # 语义导航
    TARGETED = "targeted"      # 精准获取
    SEQUENTIAL = "sequential"  # 顺序浏览


class NavigationState(Enum):
    """导航状态"""
    IDLE = "idle"
    SCANNING = "scanning"
    NAVIGATING = "navigating"
    FETCHING = "fetching"
    COMPLETED = "completed"


@dataclass
class PageInfo:
    """页面信息"""
    page_number: int
    thumbnail: Optional[str] = None
    content_summary: str = ""
    key_elements: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    has_images: bool = False
    has_tables: bool = False
    has_charts: bool = False


@dataclass
class NavigationAction:
    """导航动作"""
    action_type: str  # scan, navigate, fetch, summarize
    target_page: Optional[int] = None
    target_region: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class NavigationResult:
    """导航结果"""
    success: bool
    content: str = ""
    page_number: Optional[int] = None
    region: Optional[Tuple[int, int, int, int]] = None
    confidence: float = 0.0
    references: List[str] = field(default_factory=list)


class DocumentNavigator:
    """
    文档导航器
    
    实现 Doc-V* 的核心导航策略：
    1. 缩略图概览 - 快速获取文档整体结构
    2. 语义检索 - 基于查询语义定位相关页面
    3. 精准获取 - 获取目标区域内容
    4. 选择性注意力 - 聚焦关键信息
    
    导航流程:
    Overview → Semantic Navigation → Targeted Fetching → Aggregation
    """
    
    def __init__(self):
        """初始化文档导航器"""
        self._document = None
        self._document_type = ""
        self._total_pages = 0
        self._current_page = 0
        self._page_info_cache: Dict[int, PageInfo] = {}
        self._attention_map: Dict[int, float] = {}  # 页面注意力权重
        self._navigation_history: List[NavigationAction] = []
        self._state = NavigationState.IDLE
        
        print("[DocumentNavigator] 初始化完成")
    
    @property
    def current_page(self) -> int:
        """当前页码"""
        return self._current_page
    
    @property
    def total_pages(self) -> int:
        """总页数"""
        return self._total_pages
    
    @property
    def state(self) -> NavigationState:
        """导航状态"""
        return self._state
    
    def load_document(self, document_path: str, document_type: str = "pdf") -> bool:
        """
        加载文档
        
        Args:
            document_path: 文档路径
            document_type: 文档类型 (pdf, docx, image等)
            
        Returns:
            是否成功加载
        """
        self._document = document_path
        self._document_type = document_type
        self._total_pages = self._estimate_pages()
        self._current_page = 0
        self._page_info_cache.clear()
        self._attention_map.clear()
        self._navigation_history.clear()
        
        print(f"[DocumentNavigator] 文档加载完成: {document_path}, 页数: {self._total_pages}")
        return True
    
    def _estimate_pages(self) -> int:
        """估算文档页数（模拟）"""
        # 实际实现中会解析文档获取真实页数
        import random
        return random.randint(1, 50)
    
    async def overview_scan(self, max_pages: int = 10) -> List[PageInfo]:
        """
        快速扫描获取文档概览
        
        模拟 Doc-V* 的缩略图概览阶段
        
        Args:
            max_pages: 最大扫描页数
            
        Returns:
            页面信息列表
        """
        self._state = NavigationState.SCANNING
        
        print(f"[DocumentNavigator] 开始概览扫描，目标页数: {min(max_pages, self._total_pages)}")
        
        results = []
        scan_count = min(max_pages, self._total_pages)
        
        for page_num in range(1, scan_count + 1):
            page_info = await self._scan_page(page_num)
            results.append(page_info)
            
            # 更新注意力映射
            self._attention_map[page_num] = page_info.relevance_score
            
            # 添加导航历史
            self._navigation_history.append(NavigationAction(
                action_type="scan",
                target_page=page_num,
                confidence=page_info.relevance_score,
                reasoning=f"扫描页面 {page_num}"
            ))
            
            # 模拟处理延迟
            await asyncio.sleep(0.1)
        
        self._state = NavigationState.IDLE
        
        print(f"[DocumentNavigator] 概览扫描完成，获取 {len(results)} 页信息")
        return results
    
    async def _scan_page(self, page_number: int) -> PageInfo:
        """
        扫描单页内容
        
        Args:
            page_number: 页码
            
        Returns:
            页面信息
        """
        # 模拟页面扫描结果
        import random
        
        summaries = [
            "文档介绍和目录",
            "研究背景和动机",
            "相关工作综述",
            "提出的方法和模型架构",
            "实验设置和数据集描述",
            "实验结果和分析",
            "讨论和未来工作",
            "结论和参考文献",
            "附录和补充材料",
            "图表和表格说明"
        ]
        
        key_elements = []
        if random.random() > 0.5:
            key_elements.append("图表")
        if random.random() > 0.3:
            key_elements.append("表格")
        if random.random() > 0.6:
            key_elements.append("公式")
        
        return PageInfo(
            page_number=page_number,
            content_summary=random.choice(summaries),
            key_elements=key_elements,
            relevance_score=round(random.uniform(0.1, 1.0), 2),
            has_images=random.random() > 0.4,
            has_tables=random.random() > 0.3,
            has_charts=random.random() > 0.2
        )
    
    async def semantic_navigate(self, query: str) -> NavigationResult:
        """
        基于语义检索导航到相关页面
        
        模拟 Doc-V* 的语义检索阶段
        
        Args:
            query: 查询问题
            
        Returns:
            导航结果
        """
        self._state = NavigationState.NAVIGATING
        
        print(f"[DocumentNavigator] 语义导航: {query}")
        
        # 分析查询意图
        intent = self._analyze_query_intent(query)
        
        # 基于意图和注意力映射选择目标页面
        target_page = self._select_target_page(intent)
        
        if target_page is None:
            # 如果没有找到相关页面，返回第一页
            target_page = 1
        
        # 更新当前页面
        self._current_page = target_page
        
        # 获取页面内容
        result = await self.fetch_targeted(target_page)
        
        # 添加导航历史
        self._navigation_history.append(NavigationAction(
            action_type="navigate",
            target_page=target_page,
            confidence=result.confidence,
            reasoning=f"语义检索: {query}"
        ))
        
        self._state = NavigationState.IDLE
        
        return result
    
    def _analyze_query_intent(self, query: str) -> str:
        """
        分析查询意图
        
        Args:
            query: 查询问题
            
        Returns:
            意图类型
        """
        intent_keywords = {
            "介绍": "introduction",
            "背景": "background",
            "方法": "method",
            "实验": "experiment",
            "结果": "result",
            "结论": "conclusion",
            "图表": "figure",
            "表格": "table",
            "参考文献": "reference",
            "摘要": "abstract"
        }
        
        for keyword, intent in intent_keywords.items():
            if keyword in query:
                return intent
        
        return "general"
    
    def _select_target_page(self, intent: str) -> Optional[int]:
        """
        根据意图选择目标页面
        
        Args:
            intent: 意图类型
            
        Returns:
            目标页码
        """
        # 根据意图映射到大致页码范围
        intent_page_map = {
            "introduction": (1, 5),
            "background": (5, 15),
            "method": (15, 30),
            "experiment": (30, 45),
            "result": (45, 60),
            "conclusion": (60, 70),
            "figure": (1, self._total_pages),
            "table": (1, self._total_pages),
            "reference": (max(1, self._total_pages - 10), self._total_pages),
            "abstract": (1, 3),
            "general": (1, self._total_pages)
        }
        
        if intent in intent_page_map:
            start, end = intent_page_map[intent]
            # 确保范围有效
            actual_start = max(1, start)
            actual_end = min(self._total_pages, end)
            
            # 如果范围无效，返回第一页
            if actual_start > actual_end:
                actual_start, actual_end = 1, self._total_pages
            
            # 在范围内随机选择一个页面
            import random
            return random.randint(actual_start, actual_end)
        
        # 如果有注意力映射，选择权重最高的页面
        if self._attention_map:
            return max(self._attention_map, key=self._attention_map.get)
        
        return None
    
    async def fetch_targeted(
        self,
        page_number: int,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> NavigationResult:
        """
        精准获取指定页面或区域内容
        
        模拟 Doc-V* 的精准获取阶段
        
        Args:
            page_number: 目标页码
            region: 目标区域（可选）
            
        Returns:
            获取结果
        """
        self._state = NavigationState.FETCHING
        
        print(f"[DocumentNavigator] 精准获取: 页面 {page_number}, 区域 {region}")
        
        # 更新当前页面
        self._current_page = page_number
        
        # 检查缓存
        if page_number in self._page_info_cache:
            page_info = self._page_info_cache[page_number]
        else:
            page_info = await self._scan_page(page_number)
            self._page_info_cache[page_number] = page_info
        
        # 生成模拟内容
        content = self._generate_page_content(page_number, page_info)
        
        # 添加导航历史
        self._navigation_history.append(NavigationAction(
            action_type="fetch",
            target_page=page_number,
            target_region=region,
            confidence=page_info.relevance_score,
            reasoning=f"获取页面 {page_number} 内容"
        ))
        
        self._state = NavigationState.IDLE
        
        return NavigationResult(
            success=True,
            content=content,
            page_number=page_number,
            region=region,
            confidence=page_info.relevance_score,
            references=[f"page_{page_number}"]
        )
    
    def _generate_page_content(self, page_number: int, page_info: PageInfo) -> str:
        """
        生成模拟页面内容
        
        Args:
            page_number: 页码
            page_info: 页面信息
            
        Returns:
            页面内容
        """
        content_templates = {
            "introduction": f"""第 {page_number} 页 - 引言

本研究旨在解决多页面文档视觉问答中的挑战。现有的OCR-free方法在文档长度上面临容量与精度的权衡。

我们提出了一种新的agentic框架，将多页面DocVQA转化为顺序证据聚合问题。通过主动导航和结构化工作记忆，实现更高效的推理。

关键词：文档理解、视觉问答、多模态AI""",
            
            "method": f"""第 {page_number} 页 - 方法

我们的方法包含三个主要阶段：
1. 缩略图概览：快速扫描文档结构
2. 语义导航：基于查询定位相关页面
3. 精准获取：提取目标区域信息

证据记忆系统负责管理和聚合来自不同页面的证据片段，支持选择性注意力机制。

实验表明，该方法在多个基准测试上取得了优异成绩。""",
            
            "experiment": f"""第 {page_number} 页 - 实验结果

实验数据集包括五个基准测试：
- DocVQA
- InfographicsVQA
- ChartQA
- TabFact
- WikiTableQuestions

{page_info.content_summary}

关键结果显示，我们的方法在域外性能上提升了47.9%。""",
            
            "conclusion": f"""第 {page_number} 页 - 结论

本文提出了Doc-V*，一个OCR-free的agentic框架。主要贡献包括：
1. 粗到细的交互式视觉推理
2. 主动导航策略
3. 结构化工作记忆系统

未来工作包括扩展到更多模态和优化推理效率。

参考文献：
[1] Zheng et al., Doc-V*, arXiv 2026
[2] 相关工作引用..."""
        }
        
        # 根据页面摘要选择模板
        summary = page_info.content_summary
        if "介绍" in summary or "目录" in summary:
            return content_templates["introduction"]
        elif "方法" in summary or "架构" in summary:
            return content_templates["method"]
        elif "实验" in summary or "结果" in summary:
            return content_templates["experiment"]
        elif "结论" in summary or "参考" in summary:
            return content_templates["conclusion"]
        else:
            return f"""第 {page_number} 页内容

{page_info.content_summary}

本页面包含以下元素：{', '.join(page_info.key_elements) if page_info.key_elements else '文本内容'}

相关性评分: {page_info.relevance_score}"""
    
    async def sequential_navigate(self, direction: str = "next") -> NavigationResult:
        """
        顺序导航（上一页/下一页）
        
        Args:
            direction: 导航方向 (next/previous)
            
        Returns:
            导航结果
        """
        if direction == "next":
            next_page = min(self._current_page + 1, self._total_pages)
        else:
            next_page = max(self._current_page - 1, 1)
        
        if next_page == self._current_page:
            # 已经在边界
            return NavigationResult(
                success=False,
                content=f"已经在{'第一' if direction == 'previous' else '最后'}一页",
                page_number=self._current_page
            )
        
        return await self.fetch_targeted(next_page)
    
    def get_navigation_history(self) -> List[NavigationAction]:
        """获取导航历史"""
        return self._navigation_history.copy()
    
    def get_attention_summary(self) -> Dict[int, float]:
        """获取注意力摘要"""
        return dict(sorted(self._attention_map.items(), key=lambda x: x[1], reverse=True))
    
    def reset(self):
        """重置导航状态"""
        self._current_page = 0
        self._attention_map.clear()
        self._navigation_history.clear()
        self._state = NavigationState.IDLE


# 单例模式
_document_navigator_instance = None

def get_document_navigator() -> DocumentNavigator:
    """获取全局文档导航器实例"""
    global _document_navigator_instance
    if _document_navigator_instance is None:
        _document_navigator_instance = DocumentNavigator()
    return _document_navigator_instance
