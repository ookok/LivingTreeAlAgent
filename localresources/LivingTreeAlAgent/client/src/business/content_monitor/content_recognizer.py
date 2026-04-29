"""
智能创作与内容监控系统 - 内容识别引擎
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .models import ContentType, RecognizedEntity, ContentAnalysis


class ContentRecognizer:
    """内容识别引擎"""
    
    def __init__(self):
        self.financial_patterns = {
            'amount': re.compile(r'[\d,.]+\s*(?:元|美元|¥|\$)'),
            'income_kw': ['收入', '进账', '盈利', '利润', '收益', '工资'],
            'expense_kw': ['支出', '花费', '消费', '成本', '费用']
        }
        self.legal_patterns = {
            'clause': re.compile(r'第[一二三四五六七八九十百\d]+条'),
            'contract_kw': ['合同', '协议', '条款', '甲方', '乙方', '权利', '义务']
        }
        self.project_patterns = {
            'milestone_kw': ['里程碑', '阶段', '节点', '交付', 'deadline'],
            'task_kw': ['任务', '分配', '负责人', '完成', '进度'],
            'resource_kw': ['资源', '预算', '人员', '设备']
        }
        self.meeting_patterns = {
            'keywords': ['会议', '讨论', '决议', '决定', '参会', '议题']
        }
        self.type_scores = {ct: 0 for ct in ContentType}
    
    def recognize(self, text: str) -> ContentAnalysis:
        """识别内容类型并提取实体"""
        self.type_scores = {ct: 0 for ct in ContentType}
        entities = []
        
        fin_entities = self._recognize_financial(text)
        entities.extend(fin_entities)
        if fin_entities:
            self.type_scores[ContentType.FINANCIAL] += len(fin_entities)
        
        legal_entities = self._recognize_legal(text)
        entities.extend(legal_entities)
        if legal_entities:
            self.type_scores[ContentType.LEGAL] += len(legal_entities)
        
        proj_entities = self._recognize_project(text)
        entities.extend(proj_entities)
        if proj_entities:
            self.type_scores[ContentType.PROJECT_PLAN] += len(proj_entities)
        
        meeting_entities = self._recognize_meeting(text)
        entities.extend(meeting_entities)
        if meeting_entities:
            self.type_scores[ContentType.MEETING_NOTES] += len(meeting_entities)
        
        best_type = max(self.type_scores, key=self.type_scores.get)
        confidence = self.type_scores[best_type] / max(len(text) / 100, 1)
        
        return ContentAnalysis(
            content_id="",
            content_type=best_type,
            confidence=min(confidence, 1.0),
            entities=entities,
            keywords=self._extract_keywords(text)
        )
    
    def _recognize_financial(self, text: str) -> List[RecognizedEntity]:
        entities = []
        for match in self.financial_patterns['amount'].finditer(text):
            entities.append(RecognizedEntity(
                entity_type="financial_amount", value=match.group(),
                start_pos=match.start(), end_pos=match.end(), confidence=0.9))
        for kw in self.financial_patterns['income_kw'] + self.financial_patterns['expense_kw']:
            for match in re.finditer(kw, text):
                entities.append(RecognizedEntity(
                    entity_type="financial_keyword", value=kw,
                    start_pos=match.start(), end_pos=match.end(), confidence=0.7))
        return entities
    
    def _recognize_legal(self, text: str) -> List[RecognizedEntity]:
        entities = []
        for match in self.legal_patterns['clause'].finditer(text):
            entities.append(RecognizedEntity(
                entity_type="legal_clause", value=match.group(),
                start_pos=match.start(), end_pos=match.end(), confidence=0.95))
        for kw in self.legal_patterns['contract_kw']:
            if kw in text:
                pos = text.index(kw)
                entities.append(RecognizedEntity(
                    entity_type="legal_keyword", value=kw,
                    start_pos=pos, end_pos=pos + len(kw), confidence=0.7))
        return entities
    
    def _recognize_project(self, text: str) -> List[RecognizedEntity]:
        entities = []
        all_kw = self.project_patterns['milestone_kw'] + self.project_patterns['task_kw'] + self.project_patterns['resource_kw']
        for kw in all_kw:
            for match in re.finditer(kw, text):
                etype = "project_milestone" if kw in self.project_patterns['milestone_kw'] else \
                        "project_task" if kw in self.project_patterns['task_kw'] else "project_resource"
                entities.append(RecognizedEntity(
                    entity_type=etype, value=kw,
                    start_pos=match.start(), end_pos=match.end(), confidence=0.75))
        return entities
    
    def _recognize_meeting(self, text: str) -> List[RecognizedEntity]:
        entities = []
        for kw in self.meeting_patterns['keywords']:
            for match in re.finditer(kw, text):
                entities.append(RecognizedEntity(
                    entity_type="meeting_keyword", value=kw,
                    start_pos=match.start(), end_pos=match.end(), confidence=0.7))
        return entities
    
    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r'[\w]{2,}', text)
        freq = {}
        for w in words:
            if len(w) > 2:
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
