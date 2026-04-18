"""
知识引擎
负责与 Hermes Agent 交互，生成带标签的学习响应
"""

import time
from typing import List, Dict, Any, Optional, Callable, Iterator

from ..models.knowledge_models import (
    LearningResponse, KnowledgeTag, Reference
)
from .tag_generator import TagGenerator


class KnowledgeEngine:
    """知识引擎，负责生成带标签的学习响应"""
    
    def __init__(
        self,
        llm_callback: Callable,
        tag_generator: Optional[TagGenerator] = None,
        model_name: str = "qwen2.5:7b"
    ):
        self.llm_callback = llm_callback
        self.tag_generator = tag_generator or TagGenerator()
        self.model_name = model_name
    
    async def generate_response(
        self,
        query: str,
        user_profile: Dict[str, Any] = None,
        show_reasoning: bool = False,
        reasoning_callback: Optional[Callable[[str], None]] = None,
    ) -> LearningResponse:
        """生成学习响应（异步）"""
        start_time = time.time()
        
        prompt = self._build_prompt(query, user_profile)
        response_text = self.llm_callback(prompt)
        
        response_data = self._parse_response(response_text)
        
        if not response_data.get("tags"):
            user_interests = user_profile.get("interests", []) if user_profile else []
            tags = self.tag_generator.generate_tags(
                query, response_data["answer"], user_interests
            )
        else:
            tags = [KnowledgeTag(**t) for t in response_data["tags"]]
        
        suggested = response_data.get("suggested", [])
        
        result = LearningResponse(
            query=query,
            answer=response_data["answer"],
            tags=tags,
            sources=[Reference(**s) for s in response_data.get("sources", [])],
            suggested_next=suggested,
            model_used=self.model_name,
            duration=time.time() - start_time,
        )
        
        self.tag_generator.enrich_tags_with_keywords(result.tags, result.answer)
        
        return result
    
    def _build_prompt(self, query: str, user_profile: Dict[str, Any] = None) -> str:
        """构建提示词"""
        interest_context = ""
        if user_profile:
            interests = user_profile.get("interests", [])
            if interests:
                interest_context = f"\n\n用户兴趣领域：{', '.join(interests)}"
            
            difficulty = user_profile.get("difficulty_preference", "normal")
            if difficulty == "easy":
                interest_context += "\n\n请用通俗易懂的语言解释。"
            elif difficulty == "advanced":
                interest_context += "\n\n请提供专业深入的分析。"
        
        prompt = f"""你是一位知识渊博的向导，帮助用户探索知识的海洋。
当用户提出问题时，你不仅给出答案，还要生成相关的"知识标签"。

用户问题：{query}
{interest_context}

请按以下格式回答：

## 回答
[你的详细回答]

## 知识标签
[提取 4-6 个相关的知识标签，格式：标签名 - 类型 - 描述]
类型：人物/事件/技术/地点/时期/组织/作品/概念

## 延伸问题
[3 个后续问题]

回答要求：
1. 回答要准确、深入
2. 标签要有探索意义
"""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        result = {"answer": "", "tags": [], "sources": [], "suggested": []}
        
        lines = response_text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('## 回答'):
                if section_content and current_section == "answer":
                    result["answer"] = '\n'.join(section_content).strip()
                current_section = "answer"
                section_content = []
                continue
            elif stripped.startswith('## 知识标签'):
                if section_content:
                    result["answer"] = '\n'.join(section_content).strip()
                current_section = "tags"
                section_content = []
                continue
            elif stripped.startswith('## 延伸问题'):
                if section_content and current_section == "tags":
                    result["tags"] = self._parse_tags_section(section_content)
                current_section = "suggested"
                section_content = []
                continue
            
            if current_section and stripped:
                section_content.append(stripped)
        
        if not result["answer"]:
            result["answer"] = response_text
        
        return result
    
    def _parse_tags_section(self, lines: List[str]) -> List[Dict[str, Any]]:
        """解析标签部分"""
        tags = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(' - ')
            if len(parts) >= 2:
                tags.append({
                    "text": parts[0].strip(),
                    "type": parts[1].strip(),
                    "description": parts[2].strip() if len(parts) > 2 else "",
                    "weight": 0.7,
                })
        return tags
