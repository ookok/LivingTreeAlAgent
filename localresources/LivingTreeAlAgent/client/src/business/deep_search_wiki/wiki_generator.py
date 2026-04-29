"""
深度Wiki生成器
"""

import re
from typing import List, Optional, Dict
from datetime import datetime

from .models import WikiPage, WikiSection, SourceInfo, SearchResult, SourceType
from .search_engine import SmartSearchEngine
from .credibility import CredibilityEvaluator


class WikiGenerator:
    """Wiki页面生成器"""
    
    # 章节模板
    SECTION_TEMPLATES = {
        "overview": {
            "title": "📖 概述",
            "level": 2,
            "subs": [
                ("背景", "背景与发展"),
                ("定义", "什么是{topic}"),
            ],
        },
        "principles": {
            "title": "⚙️ 技术原理",
            "level": 2,
            "subs": [
                ("核心概念", "核心概念解释"),
                ("工作流程", "工作原理"),
                ("关键技术", "关键技术点"),
            ],
        },
        "applications": {
            "title": "💼 应用场景",
            "level": 2,
            "subs": [
                ("典型应用", "典型应用案例"),
                ("使用场景", "适用场景"),
                ("实践案例", "实践示例"),
            ],
        },
        "comparison": {
            "title": "⚖️ 优缺点分析",
            "level": 2,
            "subs": [
                ("优势", "主要优势"),
                ("局限性", "局限性/挑战"),
            ],
        },
        "future": {
            "title": "🔮 未来趋势",
            "level": 2,
            "subs": [
                ("发展方向", "发展趋势"),
                ("技术演进", "技术演进方向"),
            ],
        },
    }
    
    def __init__(self):
        self.search_engine = SmartSearchEngine()
        self.credibility_evaluator = CredibilityEvaluator()
    
    async def close(self):
        await self.search_engine.close()
    
    def generate(
        self,
        topic: str,
        search_results: Optional[List[SearchResult]] = None,
        use_search: bool = True,
    ) -> WikiPage:
        """生成Wiki页面"""
        wiki = WikiPage(topic=topic)
        
        # 如果没有搜索结果，使用空数据
        if not search_results:
            if use_search:
                search_results = self._generate_empty_results(topic)
            else:
                search_results = []
        
        # 处理搜索结果
        sources = self._process_results(search_results)
        wiki.sources = sources
        wiki.sources_count = len(sources)
        
        # 计算平均可信度
        if sources:
            wiki.credibility_avg = sum(s.credibility for s in sources) / len(sources)
        
        # 生成概述
        wiki.summary = self._generate_summary(topic, sources)
        
        # 生成核心信息
        self._generate_key_info(topic, sources, wiki)
        
        # 生成章节内容
        wiki.sections = self._generate_sections(topic, sources)
        
        # 生成学习资源
        wiki.resources = self._generate_resources(sources)
        
        # 设置置信度
        wiki.confidence = min(0.95, wiki.credibility_avg / 100 * 0.8 + 0.2)
        
        return wiki
    
    def _generate_empty_results(self, topic: str) -> List[SearchResult]:
        """生成空结果占位符"""
        return []
    
    def _process_results(self, results: List[SearchResult]) -> List[SourceInfo]:
        """处理搜索结果，转换为来源信息"""
        sources = []
        
        for result in results:
            # 提取域名
            domain = re.sub(r"https?://(www\.)?", "", result.url.split("/")[0] if "/" in result.url else result.url)
            
            # 创建来源信息
            source = SourceInfo(
                url=result.url,
                title=result.title,
                source_type=result.source_type,
                domain=domain,
            )
            
            # 评估可信度
            self.credibility_evaluator.evaluate(source)
            
            sources.append(source)
        
        # 按可信度排序
        sources.sort(key=lambda x: x.credibility, reverse=True)
        
        return sources
    
    def _generate_summary(self, topic: str, sources: List[SourceInfo]) -> str:
        """生成概述"""
        if not sources:
            return f"{topic}是一个重要的技术领域，在当今的科技发展中扮演着关键角色。"
        
        # 基于高可信度来源生成概述
        high_cred_sources = [s for s in sources if s.credibility >= 70]
        
        summary_parts = [
            f"{topic}是一个涉及多个方面的综合性技术领域。"
        ]
        
        if high_cred_sources:
            # 添加基于来源的信息
            summary_parts.append(
                f"根据权威资料，{topic}主要包含以下核心要素。"
            )
        
        return "".join(summary_parts)
    
    def _generate_key_info(
        self,
        topic: str,
        sources: List[SourceInfo],
        wiki: WikiPage
    ):
        """生成关键信息"""
        # 定义
        wiki.definition = f"{topic}是当代技术发展的重要组成部分"
        
        # 类别（基于搜索结果推断）
        categories = set()
        for source in sources:
            if "arxiv" in source.domain or "paper" in source.domain:
                categories.add("学术研究")
            if "github" in source.domain:
                categories.add("开源项目")
            if "stackoverflow" in source.domain:
                categories.add("技术问答")
            if "docs" in source.domain:
                categories.add("官方文档")
        
        if categories:
            wiki.category = "、".join(categories)
        else:
            wiki.category = "综合技术"
        
        # 标签
        wiki.tags = self._extract_tags(topic, sources)
        
        # 应用场景
        wiki.applications = [
            "技术开发",
            "学术研究",
            "产品应用",
        ]
        
        # 关键要点
        wiki.key_points = self._generate_key_points(topic, sources)
    
    def _extract_tags(self, topic: str, sources: List[SourceInfo]) -> List[str]:
        """提取标签"""
        tags = [topic]
        
        # 基于域名添加标签
        for source in sources[:5]:
            if "github" in source.domain:
                tags.append("开源")
            if "arxiv" in source.domain:
                tags.append("学术")
            if "stackoverflow" in source.domain:
                tags.append("社区")
            if "docs" in source.domain:
                tags.append("文档")
        
        return list(set(tags))[:5]
    
    def _generate_key_points(self, topic: str, sources: List[SourceInfo]) -> List[str]:
        """生成关键要点"""
        points = []
        
        # 基于高可信度来源生成要点
        high_cred = [s for s in sources if s.credibility >= 70]
        
        if high_cred:
            points.append(f"权威资料表明{topic}具有重要的技术价值")
            points.append(f"相关开源项目和学术研究为其发展提供了支持")
        
        if len(sources) > 3:
            points.append(f"本领域有丰富的学习资源和社区支持")
        
        if not points:
            points = [
                f"{topic}是该领域的重要概念",
                "建议查阅官方文档获取详细信息",
                "参与社区讨论可以获得更多实践经验",
            ]
        
        return points
    
    def _generate_sections(
        self,
        topic: str,
        sources: List[SourceInfo]
    ) -> List[WikiSection]:
        """生成章节"""
        sections = []
        
        # 选择要生成的章节
        section_order = ["overview", "principles", "applications", "comparison", "future"]
        
        for section_key in section_order:
            if section_key not in self.SECTION_TEMPLATES:
                continue
            
            template = self.SECTION_TEMPLATES[section_key]
            section = WikiSection(
                title=template["title"].replace("{topic}", topic),
                level=template["level"],
            )
            
            # 根据来源生成内容
            section.content = self._generate_section_content(
                section_key, topic, sources
            )
            
            # 添加子章节
            for sub_title, _ in template.get("subs", []):
                sub = WikiSection(
                    title=sub_title,
                    level=template["level"] + 1,
                    content=self._generate_sub_content(sub_title, topic, sources),
                )
                section.subs.append(sub)
            
            sections.append(section)
        
        return sections
    
    def _generate_section_content(
        self,
        section_key: str,
        topic: str,
        sources: List[SourceInfo]
    ) -> str:
        """生成章节内容"""
        content_map = {
            "overview": f"本节介绍{topic}的基本概念、背景和发展历程。",
            "principles": f"本节详细解释{topic}的工作原理和核心技术。",
            "applications": f"本节展示{topic}的主要应用场景和实践案例。",
            "comparison": f"本节分析{topic}的优势和局限性。",
            "future": f"本节探讨{topic}的发展趋势和未来方向。",
        }
        
        base_content = content_map.get(section_key, "")
        
        # 添加来自来源的信息
        relevant_sources = self._find_relevant_sources(sources, section_key)
        
        if relevant_sources:
            content_map[section_key] += f"\n\n"
            for source in relevant_sources[:2]:
                content_map[section_key] += f"来源：{source.title}（可信度：{source.credibility:.0f}%）\n"
        
        return content_map.get(section_key, base_content)
    
    def _generate_sub_content(
        self,
        sub_title: str,
        topic: str,
        sources: List[SourceInfo]
    ) -> str:
        """生成子章节内容"""
        contents = {
            "背景": f"{topic}的发展历程可以追溯到早期研究阶段。",
            "定义": f"{topic}是指与{topic}相关的理论、方法和实践的总称。",
            "核心概念": f"理解{topic}需要掌握其核心概念和基本原理。",
            "工作流程": f"{topic}的工作流程通常包括多个关键步骤。",
            "关键技术": f"实现{topic}涉及多项关键技术的综合应用。",
            "典型应用": f"{topic}已在多个领域得到成功应用。",
            "使用场景": f"{topic}适用于多种实际应用场景。",
            "实践案例": f"以下是{topic}的典型实践案例。",
            "优势": f"{topic}的主要优势包括技术先进性和实用性。",
            "局限性": f"{topic}目前仍面临一些技术挑战和局限性。",
            "发展方向": f"{topic}的未来发展方向包括技术创新和应用拓展。",
            "技术演进": f"随着技术发展，{topic}将持续演进和优化。",
        }
        
        return contents.get(sub_title, f"关于{sub_title}的详细内容请参考相关资料。")
    
    def _find_relevant_sources(
        self,
        sources: List[SourceInfo],
        section_key: str
    ) -> List[SourceInfo]:
        """查找相关来源"""
        keyword_map = {
            "overview": ["official", "introduction", "guide"],
            "principles": ["tutorial", "technical", "implementation"],
            "applications": ["example", "use-case", "application"],
            "comparison": ["review", "analysis", "comparison"],
            "future": ["future", "trend", "research"],
        }
        
        keywords = keyword_map.get(section_key, [])
        
        relevant = []
        for source in sources:
            if any(kw in source.title.lower() for kw in keywords):
                relevant.append(source)
        
        return relevant if relevant else sources[:2]
    
    def _generate_resources(self, sources: List[SourceInfo]) -> Dict[str, List[str]]:
        """生成学习资源"""
        resources: Dict[str, List[str]] = {
            "官方文档": [],
            "教程指南": [],
            "视频课程": [],
            "实践项目": [],
        }
        
        for source in sources:
            if source.credibility < 50:
                continue
            
            if source.source_type == SourceType.OFFICIAL_DOCS:
                resources["官方文档"].append(f"[{source.title}]({source.url})")
            elif source.source_type == SourceType.BLOG:
                resources["教程指南"].append(f"[{source.title}]({source.url})")
            elif source.source_type == SourceType.VIDEO:
                resources["视频课程"].append(f"[{source.title}]({source.url})")
            elif "github" in source.domain:
                resources["实践项目"].append(f"[{source.title}]({source.url})")
        
        # 限制每个类别最多5个
        for key in resources:
            resources[key] = resources[key][:5]
        
        # 移除空类别
        return {k: v for k, v in resources.items() if v}
    
    def generate_quick(self, topic: str) -> WikiPage:
        """快速生成（不执行搜索）"""
        wiki = WikiPage(topic=topic)
        
        wiki.summary = f"{topic}是一个重要的技术主题。"
        wiki.definition = f"{topic}"
        wiki.category = "技术领域"
        wiki.tags = [topic]
        wiki.key_points = [
            f"{topic}具有广泛的应用价值",
            "相关技术持续发展",
            "建议深入学习相关知识",
        ]
        wiki.sources_count = 0
        wiki.credibility_avg = 50
        wiki.confidence = 0.5
        
        # 创建基础章节
        sections = []
        for section_key in ["overview", "principles", "applications"]:
            if section_key not in self.SECTION_TEMPLATES:
                continue
            
            template = self.SECTION_TEMPLATES[section_key]
            section = WikiSection(
                title=template["title"].replace("{topic}", topic),
                level=template["level"],
            )
            sections.append(section)
        
        wiki.sections = sections
        
        return wiki


# 全局单例
_wiki_system: Optional['DeepSearchWikiSystem'] = None


def get_wiki_system() -> 'DeepSearchWikiSystem':
    """获取Wiki系统单例"""
    global _wiki_system
    if _wiki_system is None:
        _wiki_system = DeepSearchWikiSystem()
    return _wiki_system


class DeepSearchWikiSystem:
    """深度搜索Wiki系统"""
    
    def __init__(self):
        self.generator = WikiGenerator()
        self.search_engine = self.generator.search_engine
    
    async def generate_async(self, topic: str, use_search: bool = True) -> WikiPage:
        """异步生成Wiki"""
        search_results = None
        
        if use_search:
            search_results = await self.search_engine.search(topic, max_results=10)
        
        return self.generator.generate(topic, search_results)
    
    def generate(self, topic: str, use_search: bool = True) -> WikiPage:
        """同步生成Wiki"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.generate_async(topic, use_search))
    
    def generate_quick(self, topic: str) -> WikiPage:
        """快速生成"""
        return self.generator.generate_quick(topic)
    
    async def close(self):
        """关闭系统"""
        await self.generator.close()
    
    def get_statistics(self) -> Dict:
        """获取统计"""
        return {
            "search_stats": self.search_engine.get_statistics(),
        }


async def generate_wiki_async(topic: str) -> WikiPage:
    """异步生成Wiki"""
    system = get_wiki_system()
    return await system.generate_async(topic)


def generate_wiki(topic: str) -> WikiPage:
    """同步生成Wiki"""
    system = get_wiki_system()
    return system.generate(topic)
