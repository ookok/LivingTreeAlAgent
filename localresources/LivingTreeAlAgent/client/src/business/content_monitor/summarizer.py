"""
智能创作与内容监控系统 - 自动归纳汇总系统
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from .models import ContentType, SummarizationResult


class ContentSummarizer:
    """内容归纳汇总引擎"""
    
    def __init__(self):
        self.supported_types = [ContentType.FINANCIAL, ContentType.LEGAL, 
                               ContentType.PROJECT_PLAN, ContentType.MEETING_NOTES]
    
    def summarize(self, content: str, content_type: ContentType,
                  options: Optional[Dict] = None) -> SummarizationResult:
        """根据内容类型进行归纳"""
        options = options or {}
        depth = options.get("depth", "normal")
        
        if content_type == ContentType.FINANCIAL:
            return self._summarize_financial(content, depth)
        elif content_type == ContentType.LEGAL:
            return self._summarize_legal(content, depth)
        elif content_type == ContentType.PROJECT_PLAN:
            return self._summarize_project(content, depth)
        elif content_type == ContentType.MEETING_NOTES:
            return self._summarize_meeting(content, depth)
        else:
            return self._summarize_general(content, depth)
    
    def _summarize_financial(self, content: str, depth: str) -> SummarizationResult:
        result = SummarizationResult(original_content=content, content_type=ContentType.FINANCIAL)
        amounts = re.findall(r'[\d,.]+\s*(?:元|美元|¥|\$)', content)
        total = sum(float(a.replace(',', '').split()[0]) for a in amounts if a[0].isdigit())
        
        categories = defaultdict(list)
        income_kw = ['收入', '进账', '盈利', '工资']
        expense_kw = ['支出', '花费', '消费', '成本']
        
        for kw in income_kw:
            if kw in content:
                categories['收入'].append(kw)
        for kw in expense_kw:
            if kw in content:
                categories['支出'].append(kw)
        
        timeline = []
        date_pattern = re.compile(r'(\d{4}[-/年]\d{1,2}[-/月]\d{0,2})[日]?\s*(.+)')
        for match in date_pattern.finditer(content):
            timeline.append({"date": match.group(1), "event": match.group(2)})
        
        result.summary = f"总计 {len(amounts)} 笔交易，金额 {total:.2f} 元"
        result.categories = dict(categories)
        result.statistics = {
            "total_transactions": len(amounts), "total_amount": total,
            "income_count": len(categories.get('收入', [])), "expense_count": len(categories.get('支出', []))}
        result.timeline = timeline
        result.key_points = [f"共 {len(amounts)} 笔财务记录"]
        result.confidence = 0.85
        return result
    
    def _summarize_legal(self, content: str, depth: str) -> SummarizationResult:
        result = SummarizationResult(original_content=content, content_type=ContentType.LEGAL)
        clauses = re.findall(r'第[一二三四五六七八九十百\d]+条[：:]?\s*([^第\n]+)', content)
        dates = re.findall(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', content)
        
        result.summary = f"共识别 {len(clauses)} 个条款，{len(dates)} 个关键日期"
        result.key_points = clauses[:5] if depth != "simple" else clauses[:3]
        result.statistics = {"total_clauses": len(clauses), "key_dates": len(dates)}
        result.timeline = [{"date": d, "type": "deadline"} for d in dates]
        result.confidence = 0.9
        return result
    
    def _summarize_project(self, content: str, depth: str) -> SummarizationResult:
        result = SummarizationResult(original_content=content, content_type=ContentType.PROJECT_PLAN)
        tasks = re.findall(r'(?:任务|TODO)[：:]\s*([^\n]+)', content)
        milestones = re.findall(r'(?:里程碑|节点|阶段)[：:]\s*([^\n]+)', content)
        resources = re.findall(r'(?:资源|人员|预算)[：:]\s*([^\n]+)', content)
        dates = re.findall(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', content)
        
        result.summary = f"项目包含 {len(tasks)} 个任务，{len(milestones)} 个里程碑"
        result.key_points = milestones[:5]
        result.categories = {"任务": tasks, "里程碑": milestones, "资源": resources}
        result.statistics = {"total_tasks": len(tasks), "milestones": len(milestones), "resources": len(resources)}
        result.timeline = [{"date": d, "type": "milestone"} for d in dates]
        result.confidence = 0.85
        return result
    
    def _summarize_meeting(self, content: str, depth: str) -> SummarizationResult:
        result = SummarizationResult(original_content=content, content_type=ContentType.MEETING_NOTES)
        resolutions = re.findall(r'(?:决议|决定|议定)[：:]\s*([^\n]+)', content)
        discussions = re.findall(r'(?:讨论|议题)[：:]\s*([^\n]+)', content)
        attendees = re.findall(r'(?:参会|参加|出席)[：:]?\s*([^\n,，]+)', content)
        
        result.summary = f"会议产生 {len(resolutions)} 项决议，{len(discussions)} 个讨论议题"
        result.key_points = resolutions
        result.categories = {"决议": resolutions, "讨论": discussions, "参会人": attendees}
        result.statistics = {"resolutions": len(resolutions), "discussions": len(discussions), "attendees": len(attendees)}
        result.confidence = 0.8
        return result
    
    def _summarize_general(self, content: str, depth: str) -> SummarizationResult:
        result = SummarizationResult(original_content=content, content_type=ContentType.GENERAL)
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        words = re.findall(r'[\w]{3,}', content)
        freq = defaultdict(int)
        for w in words:
            freq[w] += 1
        top_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        result.summary = f"文档共 {len(paragraphs)} 个段落"
        result.key_points = [p[:100] for p in paragraphs[:5] if len(p) > 20]
        result.statistics = {"paragraphs": len(paragraphs), "characters": len(content), "keywords": dict(top_keywords)}
        result.confidence = 0.7
        return result
    
    def suggest_summarization(self, content: str) -> Dict[str, Any]:
        suggestions = []
        if self._looks_financial(content):
            suggestions.append({"type": ContentType.FINANCIAL.value, "label": "财务流水账归纳", "preview": "自动分类收支、统计总额"})
        if self._looks_legal(content):
            suggestions.append({"type": ContentType.LEGAL.value, "label": "法律文档归纳", "preview": "提取条款、权利义务"})
        if self._looks_project(content):
            suggestions.append({"type": ContentType.PROJECT_PLAN.value, "label": "项目计划归纳", "preview": "整理任务、里程碑"})
        if not suggestions:
            suggestions.append({"type": ContentType.GENERAL.value, "label": "通用归纳", "preview": "提取要点、分类整理"})
        return {"suggestions": suggestions}
    
    def _looks_financial(self, content: str) -> bool:
        return sum(1 for kw in ['金额', '收入', '支出', '元', '成本'] if kw in content) >= 2
    
    def _looks_legal(self, content: str) -> bool:
        return sum(1 for kw in ['合同', '条款', '甲方', '乙方', '权利'] if kw in content) >= 2
    
    def _looks_project(self, content: str) -> bool:
        return sum(1 for kw in ['任务', '里程碑', '阶段', '负责人'] if kw in content) >= 2
