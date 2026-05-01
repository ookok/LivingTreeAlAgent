"""
Smart Wiki Editor

智能页面编辑器，支持 AI 辅助编辑、链接建议、摘要生成等功能，集成DeepOnto本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class EditSuggestion:
    """编辑建议"""
    type: str  # link, summary, rewrite, tag, entity
    text: str
    position: Optional[int] = None
    confidence: float = 0.0
    replacement: Optional[str] = None


@dataclass
class EditorState:
    """编辑器状态"""
    page_id: str
    content: str
    cursor_position: int = 0
    suggestions: List[EditSuggestion] = field(default_factory=list)
    is_dirty: bool = False


class SmartWikiEditor:
    """
    智能 Wiki 编辑器
    
    核心功能：
    - AI 辅助编辑
    - 智能链接建议（自动发现可链接的实体）
    - 自动摘要生成
    - 内容重写建议
    - 实体高亮
    """
    
    def __init__(self):
        """初始化智能编辑器"""
        self._wiki_core = None
        self._entity_recognizer = None
        self._fusion_rag = None
        
        self._init_dependencies()
        logger.info("SmartWikiEditor 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .wiki_core import WikiCore
            from ..entity_management import get_entity_recognizer
            from ..fusion_rag import get_fusion_rag_engine
            
            self._wiki_core = WikiCore()
            self._entity_recognizer = get_entity_recognizer()
            self._fusion_rag = get_fusion_rag_engine()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    def suggest_links(self, content: str, page_id: Optional[str] = None) -> List[EditSuggestion]:
        """
        建议可链接的实体
        
        Args:
            content: 页面内容
            page_id: 当前页面ID（可选）
            
        Returns:
            List 链接建议列表
        """
        suggestions = []
        
        if not self._entity_recognizer:
            return suggestions
        
        # 识别实体
        result = self._entity_recognizer.recognize(content)
        
        for entity in result.entities:
            # 跳过简单类型
            if entity.entity_type.value in ["date", "number", "email", "phone", "url"]:
                continue
            
            # 检查是否已有链接
            if f"[[{entity.text}]]" in content:
                continue
            
            suggestions.append(EditSuggestion(
                type="link",
                text=f"将「{entity.text}」链接到 Wiki 页面",
                position=entity.start,
                confidence=entity.confidence,
                replacement=f"[[{entity.text}]]",
            ))
        
        return suggestions
    
    def generate_summary(self, content: str) -> str:
        """
        生成页面摘要
        
        Args:
            content: 页面内容
            
        Returns:
            str 摘要文本
        """
        # 简单实现：取前200个字符
        import re
        
        # 去除 Markdown 格式
        text = re.sub(r'[#*`>\[\]]', '', content)
        
        # 取前200个字符
        summary = text.strip()[:200]
        
        if len(text) > 200:
            summary += "..."
        
        return summary
    
    def suggest_tags(self, content: str) -> List[str]:
        """
        建议标签
        
        Args:
            content: 页面内容
            
        Returns:
            List 标签建议列表
        """
        tags = set()
        
        if not self._entity_recognizer:
            return list(tags)
        
        # 基于实体类型生成标签
        result = self._entity_recognizer.recognize(content)
        
        type_tags = {
            "person": "人物",
            "organization": "组织",
            "location": "地点",
            "tech_term": "技术",
            "concept": "概念",
            "product": "产品",
            "algorithm": "算法",
            "framework": "框架",
            "language": "编程语言",
        }
        
        for entity in result.entities:
            tag = type_tags.get(entity.entity_type.value)
            if tag:
                tags.add(tag)
        
        # 添加通用标签
        content_lower = content.lower()
        if "学习" in content_lower or "教程" in content_lower:
            tags.add("学习")
        if "代码" in content_lower or "编程" in content_lower:
            tags.add("代码")
        if "AI" in content_lower or "人工智能" in content_lower:
            tags.add("AI")
        
        return list(tags)
    
    def rewrite_content(self, content: str, style: str = "clear") -> str:
        """
        重写内容
        
        Args:
            content: 原始内容
            style: 重写风格 (clear, concise, detailed, formal)
            
        Returns:
            str 重写后的内容
        """
        # 简化实现：返回原始内容
        # 实际实现中可以调用 LLM 进行内容重写
        return content
    
    def extract_entities(self, content: str) -> List[Dict[str, Any]]:
        """
        提取内容中的实体
        
        Args:
            content: 页面内容
            
        Returns:
            List 实体列表
        """
        if not self._entity_recognizer:
            return []
        
        result = self._entity_recognizer.recognize(content)
        entities = []
        
        for entity in result.entities:
            entities.append({
                "text": entity.text,
                "type": entity.entity_type.value,
                "start": entity.start,
                "end": entity.end,
                "confidence": entity.confidence,
            })
        
        return entities
    
    def validate_content(self, content: str) -> List[str]:
        """
        验证内容
        
        Args:
            content: 页面内容
            
        Returns:
            List 问题列表
        """
        issues = []
        
        # 检查空内容
        if not content.strip():
            issues.append("页面内容为空")
        
        # 检查链接格式
        import re
        links = re.findall(r'\[\[([^\]]+)\]\]', content)
        for link in links:
            if len(link.strip()) < 2:
                issues.append(f"无效链接: [[{link}]]")
        
        # 检查标题
        if not content.startswith("# "):
            issues.append("建议添加页面标题（以 # 开头）")
        
        return issues
    
    def format_content(self, content: str) -> str:
        """
        格式化内容
        
        Args:
            content: 原始内容
            
        Returns:
            str 格式化后的内容
        """
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            # 确保标题后面有空白行
            if line.startswith('#') and len(formatted_lines) > 0:
                if not formatted_lines[-1].strip() == '':
                    formatted_lines.append('')
            
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def get_edit_state(self, page_id: str) -> EditorState:
        """
        获取编辑器状态
        
        Args:
            page_id: 页面ID
            
        Returns:
            EditorState 编辑器状态
        """
        content = ""
        
        if self._wiki_core:
            page = self._wiki_core.get_page(page_id)
            if page:
                content = page.content
        
        suggestions = self.suggest_links(content, page_id)
        
        return EditorState(
            page_id=page_id,
            content=content,
            suggestions=suggestions,
            is_dirty=False,
        )
    
    async def enrich_page(self, page_id: str) -> Dict[str, Any]:
        """
        丰富页面内容（使用 FusionRAG）
        
        Args:
            page_id: 页面ID
            
        Returns:
            Dict 丰富后的页面数据
        """
        if not self._wiki_core or not self._fusion_rag:
            return {"success": False, "message": "依赖模块不可用"}
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return {"success": False, "message": "页面不存在"}
        
        # 使用 FusionRAG 查询相关知识
        result = await self._fusion_rag.query(page.title)
        
        return {
            "success": True,
            "page_id": page_id,
            "related_knowledge": result.content,
            "sources": result.sources,
            "entities": result.entities,
        }


# 全局编辑器实例
_editor_instance = None

def get_smart_wiki_editor() -> SmartWikiEditor:
    """获取全局智能编辑器实例"""
    global _editor_instance
    if _editor_instance is None:
        _editor_instance = SmartWikiEditor()
    return _editor_instance