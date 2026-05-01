"""
LLM Wiki 与进化环境整合模块

将 LLM Wiki 的知识库能力与进化环境的四层架构深度整合，
实现知识的自动积累和进化。

核心功能：
1. 感知层增强：利用Wiki解析能力处理多模态文档
2. 记忆层增强：将学习到的知识存储到Wiki
3. 行动层增强：根据Wiki内容生成动态UI
4. 目标层增强：利用Wiki中的合规知识进行评估
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from loguru import logger

# 延迟导入避免循环依赖
WIKI_AVAILABLE = False
WIKI_CORE = None

try:
    from client.src.business.llm_wiki.wiki_core import WikiCore, WikiPage, get_wiki_core
    from client.src.business.llm_wiki.integration import LLMWikiIntegration
    WIKI_AVAILABLE = True
    logger.info("LLM Wiki 模块导入成功")
except ImportError as e:
    logger.warning(f"LLM Wiki 模块导入失败: {e}")

@dataclass
class WikiKnowledgeEntry:
    """Wiki 知识条目"""
    title: str
    content: str
    tags: List[str] = None
    source_type: str = "evolution"  # evolution, manual, imported
    confidence: float = 1.0

class WikiIntegrationLayer:
    """
    LLM Wiki 整合层
    
    将进化环境与 LLM Wiki 知识库无缝集成，实现：
    - 知识自动积累
    - 页面自动创建和更新
    - 基于 Wiki 内容的推理增强
    """
    
    def __init__(self):
        self.wiki_core = None
        self.wiki_integration = None
        
        if WIKI_AVAILABLE:
            self.wiki_core = get_wiki_core()
            try:
                self.wiki_integration = LLMWikiIntegration()
            except Exception as e:
                logger.warning(f"LLMWikiIntegration 初始化失败: {e}")
        
        logger.info("[WikiIntegrationLayer] 初始化完成")
    
    def add_knowledge(self, title: str, content: str, tags: Optional[List[str]] = None) -> bool:
        """
        向Wiki添加知识
        
        Args:
            title: 知识标题
            content: 知识内容
            tags: 标签列表
        
        Returns:
            bool 是否成功
        """
        if not self.wiki_core:
            logger.warning("Wiki Core 不可用")
            return False
        
        try:
            # 检查是否已存在
            existing_page = self.wiki_core.get_page_by_title(title)
            
            if existing_page:
                # 更新现有页面
                success = self.wiki_core.update_page(
                    page_id=existing_page.id,
                    content=content,
                    author="evolution_system",
                    comment="自动更新：进化系统学习到的新知识"
                )
                if success:
                    logger.info(f"Wiki 页面更新成功: {title}")
                    return True
                else:
                    return False
            else:
                # 创建新页面
                page = self.wiki_core.create_page(
                    title=title,
                    content=content,
                    author="evolution_system",
                    tags=tags or []
                )
                logger.info(f"Wiki 页面创建成功: {title}")
                return True
                
        except Exception as e:
            logger.error(f"添加知识到Wiki失败: {e}")
            return False
    
    def add_pattern_to_wiki(self, pattern_name: str, conditions: List[Dict[str, Any]], 
                           action: str, confidence: float):
        """
        将学习到的模式保存到Wiki
        
        Args:
            pattern_name: 模式名称
            conditions: 触发条件
            action: 推荐动作
            confidence: 置信度
        """
        content = f"""# {pattern_name}

## 触发条件
{chr(10).join([f"- {k}: {v}" for cond in conditions for k, v in cond.items()])}

## 推荐动作
{action}

## 置信度
{confidence * 100:.1f}%

## 来源
自动学习自进化系统
"""
        
        tags = ["pattern", "auto-learned", "workflow"]
        self.add_knowledge(pattern_name, content, tags)
    
    def add_concept_to_wiki(self, concept_name: str, description: str, 
                           related_concepts: Optional[List[str]] = None):
        """
        将概念保存到Wiki
        
        Args:
            concept_name: 概念名称
            description: 概念描述
            related_concepts: 相关概念列表
        """
        related_links = ""
        if related_concepts:
            related_links = "\n## 相关概念\n" + \
                          "\n".join([f"- [[{concept}]]" for concept in related_concepts])
        
        content = f"""# {concept_name}

## 描述
{description}

{related_links}

## 来源
自动学习自进化系统
"""
        
        tags = ["concept", "auto-learned"]
        self.add_knowledge(concept_name, content, tags)
    
    def search_knowledge(self, query: str, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        在Wiki中搜索知识
        
        Args:
            query: 搜索词
            tags: 标签过滤
        
        Returns:
            List 匹配的知识条目
        """
        if not self.wiki_core:
            return []
        
        try:
            pages = self.wiki_core.search_pages(query, tags)
            results = []
            
            for page in pages:
                results.append({
                    "title": page.title,
                    "content": page.content,
                    "summary": page.summary,
                    "tags": page.tags,
                    "revision": page.revision,
                    "updated_at": page.updated_at
                })
            
            return results
        
        except Exception as e:
            logger.error(f"搜索Wiki失败: {e}")
            return []
    
    def get_compliance_rules_from_wiki(self) -> List[Dict[str, Any]]:
        """
        从Wiki获取合规规则
        
        Returns:
            List 合规规则列表
        """
        if not self.wiki_core:
            return []
        
        # 搜索合规相关页面
        compliance_pages = self.wiki_core.search_pages("合规", ["regulation"])
        
        rules = []
        for page in compliance_pages:
            # 解析页面内容提取规则
            rule = self._parse_compliance_rule(page)
            if rule:
                rules.append(rule)
        
        return rules
    
    def _parse_compliance_rule(self, page: WikiPage) -> Optional[Dict[str, Any]]:
        """解析合规规则页面"""
        content = page.content
        
        # 简单解析：提取关键信息
        rule = {
            "id": page.id,
            "name": page.title,
            "description": page.summary,
            "tags": page.tags,
            "required": "强制" in content or "必须" in content
        }
        
        return rule
    
    def update_wiki_from_feedback(self, original_content: str, corrected_content: str, 
                                  context: Dict[str, Any]):
        """
        根据用户反馈更新Wiki
        
        Args:
            original_content: 原始内容
            corrected_content: 用户修改后的内容
            context: 上下文信息
        """
        if not self.wiki_core:
            return
        
        if corrected_content != original_content:
            # 提取关键概念
            concepts = self._extract_concepts(corrected_content)
            
            for concept in concepts:
                # 创建或更新相关页面
                self.add_concept_to_wiki(
                    concept_name=concept,
                    description=f"从用户反馈中学习到的概念: {context.get('text_content', '')[:100]}",
                    related_concepts=[]
                )
            
            logger.info(f"Wiki 已根据用户反馈更新，提取了 {len(concepts)} 个概念")
    
    def _extract_concepts(self, text: str) -> List[str]:
        """从文本中提取概念"""
        # 简单的关键词提取
        keywords = [
            '三线一单', '环境现状', '监测数据', '影响预测',
            '环境保护', '公众参与', '风险评价', '清洁生产',
            '总量控制', '敏感目标', '水环境', '大气环境',
            '噪声预测', '生态保护', '污染源强'
        ]
        
        found = []
        for keyword in keywords:
            if keyword in text:
                found.append(keyword)
        
        return found
    
    def get_wiki_stats(self) -> Dict[str, Any]:
        """获取Wiki统计信息"""
        if not self.wiki_core:
            return {"available": False}
        
        stats = self.wiki_core.get_stats()
        stats["available"] = True
        return stats
    
    def sync_with_fusion_rag(self):
        """
        同步Wiki内容到FusionRAG
        
        将Wiki中的知识同步到向量数据库，增强检索能力
        """
        if not self.wiki_core:
            return
        
        try:
            from client.src.business.fusion_rag import KnowledgeBaseLayer
            kb_layer = KnowledgeBaseLayer()
            
            for page in self.wiki_core.get_all_pages():
                # 添加到知识库
                metadata = {
                    "source": "wiki",
                    "page_id": page.id,
                    "title": page.title,
                    "tags": page.tags,
                    "revision": page.revision
                }
                
                if hasattr(kb_layer, 'add'):
                    kb_layer.add(page.content, metadata)
            
            logger.info("Wiki 内容已同步到 FusionRAG")
        
        except ImportError as e:
            logger.warning(f"同步到FusionRAG失败: {e}")
    
    def recommend_pages(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据上下文推荐Wiki页面
        
        Args:
            context: 当前上下文
        
        Returns:
            List 推荐的页面列表
        """
        if not self.wiki_core:
            return []
        
        text_content = context.get('text_content', '')
        
        # 提取关键词进行搜索
        keywords = []
        potential_keywords = ['化工', '水源地', '噪声', '大气', '水环境', '敏感', '监测', '评价']
        
        for keyword in potential_keywords:
            if keyword in text_content:
                keywords.append(keyword)
        
        if not keywords:
            return []
        
        # 搜索相关页面
        results = []
        for keyword in keywords[:3]:
            pages = self.wiki_core.search_pages(keyword)
            results.extend([{
                "title": p.title,
                "summary": p.summary,
                "tags": p.tags,
                "score": 1.0  # 匹配分数
            } for p in pages[:2]])
        
        # 去重并按相关性排序
        seen = set()
        unique_results = []
        for r in results:
            if r["title"] not in seen:
                seen.add(r["title"])
                unique_results.append(r)
        
        return unique_results[:5]


# 单例模式
_wiki_integration_instance = None

def get_wiki_integration() -> WikiIntegrationLayer:
    """获取全局 Wiki 整合实例"""
    global _wiki_integration_instance
    if _wiki_integration_instance is None:
        _wiki_integration_instance = WikiIntegrationLayer()
    return _wiki_integration_instance