"""
标签生成器
根据回答内容智能提取和排序标签
"""

import re
import json
from typing import List, Dict, Any, Optional, Callable

from ..models.knowledge_models import KnowledgeTag, TagType


class TagGenerator:
    """
    标签生成器
    
    从回答内容中提取知识标签，并进行智能排序
    """
    
    # 标签类型关键词映射
    TYPE_KEYWORDS = {
        TagType.PERSON: [
            "皇帝", "帝王", "王", "后", "妃", "臣", "相", "将", "军",
            "人物", "领袖", "总统", "总理", "首相", "CEO", "创始人",
            "科学家", "思想家", "哲学家", "文学家", "艺术家",
        ],
        TagType.EVENT: [
            "战争", "战役", "起义", "改革", "革命", "运动", "事件",
            "发生", "爆发", "始于", "结束于", "期间",
        ],
        TagType.TECH: [
            "技术", "发明", "创造", "工程", "科学", "方法", "理论",
            "系统", "机制", "原理", "工艺", "制造", "设计", "架构",
        ],
        TagType.PLACE: [
            "城市", "国家", "地区", "王朝", "帝国", "建筑", "地点",
            "位于", "坐落在", "建在", "都城", "京城", "首都",
        ],
        TagType.PERIOD: [
            "朝代", "时期", "时代", "世纪", "年代", "年间",
            "公元前", "公元", "早期", "中期", "晚期", "后期",
        ],
        TagType.ORGANIZATION: [
            "组织", "机构", "政党", "军队", "学派", "流派",
            "政府", "部门", "公司", "企业", "社团", "联盟",
        ],
        TagType.WORK: [
            "作品", "书籍", "著作", "典籍", "文章", "诗歌",
            "小说", "画作", "雕塑", "建筑", "发明",
        ],
        TagType.CONCEPT: [
            "思想", "理念", "哲学", "宗教", "信仰", "文化",
            "制度", "礼制", "法律", "道德", "思想体系",
        ],
    }
    
    # 实体识别模式
    ENTITY_PATTERNS = [
        # 朝代/时期
        (r'([\u4e00-\u9fa5]{2,6}?(?:朝|代|时期|时代|世纪))', TagType.PERIOD),
        # 特定朝代
        (r'(隋|唐|宋|元|明|清|秦|汉|晋|魏|吴|蜀|周)朝', TagType.PERIOD),
        (r'(隋炀帝|唐太宗|秦始皇|汉武帝|宋太祖|康熙|乾隆)', TagType.PERSON),
        # 著名建筑
        (r'(大运河|长城|故宫|金字塔|埃菲尔铁塔|赵州桥)', TagType.PLACE),
        # 著名人物
        (r'([\u4e00-\u9fa5]{2,4}(?:帝|王|皇|后|相|将))', TagType.PERSON),
        # 概念
        (r'(儒家|道家|佛家|法家|墨家|理学|心学|程朱理学)', TagType.CONCEPT),
        # 组织
        (r'([\u4e00-\u9fa5]{2,6}(?:党|会|社|派|门|教|军))', TagType.ORGANIZATION),
    ]
    
    def __init__(self, llm_callback: Optional[Callable] = None):
        self.llm_callback = llm_callback
    
    def generate_tags(
        self,
        query: str,
        answer: str,
        user_interests: List[str] = None,
        max_tags: int = 8
    ) -> List[KnowledgeTag]:
        tags = []
        
        # 1. 使用 LLM 智能提取
        if self.llm_callback:
            llm_tags = self._extract_with_llm(query, answer, user_interests)
            tags.extend(llm_tags)
        
        # 2. 使用正则模式提取
        pattern_tags = self._extract_with_patterns(answer)
        tags.extend(pattern_tags)
        
        # 3. 基于查询关键词提取
        query_tags = self._extract_from_query(query)
        tags.extend(query_tags)
        
        # 4. 去重和合并
        tags = self._deduplicate_tags(tags)
        
        # 5. 排序
        tags = self._rank_tags(tags, query, user_interests)
        
        # 6. 限制数量
        return tags[:max_tags]
    
    def _extract_with_llm(
        self,
        query: str,
        answer: str,
        user_interests: List[str] = None
    ) -> List[KnowledgeTag]:
        if not self.llm_callback:
            return []
        
        prompt = f"""从以下内容中提取 5-8 个关键知识标签，以 JSON 数组格式返回。

查询：{query}

回答内容：
{answer[:2000]}

用户兴趣：{', '.join(user_interests) if user_interests else '无'}

要求：
1. 每个标签包含：text(名称), type(person/event/tech/place/period/org/work/concept), description(一句话描述), weight(0-1相关度)
2. 优先选择与回答内容密切相关且有探索价值的标签
3. 返回纯 JSON 数组

示例：
[
  {{"text": "大运河", "type": "place", "description": "隋朝修建的伟大水利工程", "weight": 0.9}},
  {{"text": "隋炀帝", "type": "person", "description": "隋朝第二位皇帝，开凿大运河", "weight": 0.85}}
]
"""
        
        try:
            response = self.llm_callback(prompt)
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                tags_data = json.loads(json_match.group())
                return [
                    KnowledgeTag(
                        text=t["text"],
                        type=TagType(t.get("type", "unknown")),
                        weight=t.get("weight", 0.5),
                        description=t.get("description", ""),
                    )
                    for t in tags_data
                ]
        except Exception:
            pass
        
        return []
    
    def _extract_with_patterns(self, text: str) -> List[KnowledgeTag]:
        tags = []
        seen = set()
        
        for pattern, tag_type in self.ENTITY_PATTERNS:
            for match in re.finditer(pattern, text):
                tag_text = match.group(1) if match.lastindex else match.group()
                if tag_text and tag_text not in seen and len(tag_text) >= 2:
                    seen.add(tag_text)
                    tags.append(KnowledgeTag(
                        text=tag_text,
                        type=tag_type,
                        weight=0.6,
                        description=f"相关概念：{tag_text}",
                    ))
        
        return tags
    
    def _extract_from_query(self, query: str) -> List[KnowledgeTag]:
        tags = []
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,10}', query)
        stop_words = {"的", "是", "在", "和", "了", "有", "什么", "如何", "怎么", "为什么", "哪个", "哪些", "这个", "那个"}
        important_words = [w for w in words if w not in stop_words and len(w) >= 2]
        
        for word in important_words[:3]:
            tags.append(KnowledgeTag(
                text=word,
                type=TagType.CONCEPT,
                weight=0.4,
                description=f"探索更多关于 {word} 的知识",
            ))
        
        return tags
    
    def _deduplicate_tags(self, tags: List[KnowledgeTag]) -> List[KnowledgeTag]:
        seen = {}
        result = []
        
        for tag in tags:
            key = tag.text.strip().lower()
            if key not in seen:
                seen[key] = tag
                result.append(tag)
            else:
                if tag.weight > seen[key].weight:
                    seen[key] = tag
                    result[result.index(seen[key])] = tag
        
        return result
    
    def _rank_tags(
        self,
        tags: List[KnowledgeTag],
        query: str,
        user_interests: List[str] = None
    ) -> List[KnowledgeTag]:
        for tag in tags:
            score = tag.weight
            
            if tag.text in query:
                score += 0.2
            
            if user_interests:
                for interest in user_interests:
                    if interest.lower() in tag.text.lower():
                        score += 0.15
            
            type_weights = {
                TagType.PERSON: 0.1,
                TagType.EVENT: 0.1,
                TagType.TECH: 0.1,
                TagType.PLACE: 0.05,
                TagType.PERIOD: 0.05,
            }
            score += type_weights.get(tag.type, 0)
            
            tag.weight = min(score, 1.0)
        
        return sorted(tags, key=lambda t: t.weight, reverse=True)
    
    def enrich_tags_with_keywords(self, tags: List[KnowledgeTag], answer: str) -> List[KnowledgeTag]:
        for tag in tags:
            if not tag.search_keywords:
                tag.search_keywords = self._extract_related_keywords(tag.text, answer)
        return tags
    
    def _extract_related_keywords(self, main_term: str, text: str) -> List[str]:
        keywords = [main_term]
        sentences = text.split('。')
        for sentence in sentences:
            if main_term in sentence:
                words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,8}', sentence)
                for word in words:
                    if word != main_term and word not in keywords:
                        keywords.append(word)
                        if len(keywords) >= 5:
                            break
        
        return keywords[:5]
