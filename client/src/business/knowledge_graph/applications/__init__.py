"""
知识应用层 - 智能问答/报告生成/工艺优化
========================================

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import datetime

from .. import KnowledgeGraph, Entity, Relation, EntityType, RelationType


# ============================================================
# 第一部分：问答系统
# ============================================================

@dataclass
class QAResult:
    """问答结果"""
    question: str
    answer: str
    detailed_answer: str = ""
    data_sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    related_entities: List[Entity] = field(default_factory=list)


class IntelligentQA:
    """智能问答系统"""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def answer(self, question: str) -> QAResult:
        """回答问题"""
        # 1. 问题理解
        parsed = self._parse_question(question)

        # 2. 知识检索
        relevant_knowledge = self._retrieve_knowledge(parsed)

        # 3. 生成答案
        if parsed["type"] == "lookup":
            return self._answer_lookup(parsed, relevant_knowledge)
        elif parsed["type"] == "reasoning":
            return self._answer_reasoning(parsed, relevant_knowledge)
        elif parsed["type"] == "comparison":
            return self._answer_comparison(parsed, relevant_knowledge)
        else:
            return self._answer_general(parsed, relevant_knowledge)

    def _parse_question(self, question: str) -> Dict:
        """解析问题类型"""
        q = question.lower()

        # 简单查询
        if any(k in q for k in ["是什么", "什么是", "定义"]):
            return {"type": "definition", "query": question}
        elif any(k in q for k in ["有哪些", "有什么", "列出"]):
            return {"type": "list", "query": question}
        elif any(k in q for k in ["哪个", "什么", "多少"]):
            return {"type": "lookup", "query": question}

        # 复杂查询
        if any(k in q for k in ["为什么", "原因"]):
            return {"type": "reasoning", "query": question}
        elif any(k in q for k in ["对比", "比较", "差异"]):
            return {"type": "comparison", "query": question}
        elif any(k in q for k in ["如何", "怎么做", "步骤"]):
            return {"type": "howto", "query": question}

        return {"type": "general", "query": question}

    def _retrieve_knowledge(self, parsed: Dict) -> List[Entity]:
        """检索相关知识"""
        query = parsed["query"]
        results = []

        # 关键词匹配
        keywords = self._extract_keywords(query)
        for entity in self.kg.entities.values():
            if any(kw in entity.name for kw in keywords):
                results.append(entity)
            elif any(kw in entity.description for kw in keywords):
                results.append(entity)

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现，实际可使用分词
        import re
        # 提取中文词
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', text)
        # 提取英文词
        english_words = re.findall(r'[a-zA-Z]+', text)
        return chinese_words + english_words

    def _answer_lookup(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答查询问题"""
        query = parsed["query"]
        q = query.lower()

        # 查找工艺
        if any(k in q for k in ["工艺", "工序", "流程"]):
            processes = [e for e in knowledge if e.entity_type == EntityType.PROCESS]
            if processes:
                answer = "根据知识图谱，相关工艺有："
                details = []
                for p in processes[:5]:
                    details.append(f"- {p.name}")
                    if p.properties:
                        for k, v in list(p.properties.items())[:3]:
                            details.append(f"  - {k}: {v}")
                return QAResult(
                    question=query,
                    answer=answer + "\n" + "\n".join(details[:10]),
                    detailed_answer="\n".join(details),
                    data_sources=[p.name for p in processes],
                    confidence=0.85,
                    related_entities=processes
                )

        # 查找污染物
        if any(k in q for k in ["污染", "废气", "废水", "固废"]):
            pollutants = [e for e in knowledge if e.entity_type == EntityType.POLLUTANT]
            if pollutants:
                answer = "相关污染物包括："
                details = [f"- {p.name} ({p.pollutant_type.value})" for p in pollutants[:10]]
                return QAResult(
                    question=query,
                    answer=answer + "\n".join(details[:5]),
                    detailed_answer="\n".join(details),
                    data_sources=[p.name for p in pollutants],
                    confidence=0.85,
                    related_entities=pollutants
                )

        return QAResult(
            question=query,
            answer="在知识图谱中未找到相关信息",
            confidence=0.0
        )

    def _answer_definition(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答定义问题"""
        query = parsed["query"]
        if knowledge:
            entity = knowledge[0]
            answer = f"{entity.name}是{entity.entity_type.value}，"
            if entity.description:
                answer += entity.description
            return QAResult(
                question=query,
                answer=answer,
                detailed_answer=json.dumps(entity.properties, ensure_ascii=False, indent=2),
                data_sources=[entity.name],
                confidence=0.8,
                related_entities=[entity]
            )
        return QAResult(question=query, answer="未找到定义", confidence=0.0)

    def _answer_list(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答列表问题"""
        if not knowledge:
            return QAResult(question=parsed["query"], answer="未找到相关信息", confidence=0.0)

        by_type = {}
        for e in knowledge:
            if e.entity_type not in by_type:
                by_type[e.entity_type] = []
            by_type[e.entity_type].append(e)

        lines = ["根据知识图谱："]
        for etype, entities in by_type.items():
            lines.append(f"\n{etype.value} ({len(entities)}个)：")
            for e in entities[:10]:
                lines.append(f"  - {e.name}")

        return QAResult(
            question=parsed["query"],
            answer="\n".join(lines[:20]),
            detailed_answer="\n".join(lines),
            data_sources=[e.name for e in knowledge],
            confidence=0.8,
            related_entities=knowledge[:10]
        )

    def _answer_reasoning(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答推理问题"""
        answer = "根据知识图谱中的因果关系：\n"

        # 查找相关关系
        reasoning_chain = []
        for rel in self.kg.relations.values():
            if rel.relation_type in [RelationType.EMITS, RelationType.REQUIRES, RelationType.PRECEDES]:
                src = self.kg.entities.get(rel.source_id)
                tgt = self.kg.entities.get(rel.target_id)
                if src and tgt:
                    if any(e.name in parsed["query"] for e in [src, tgt]):
                        reasoning_chain.append(f"  {src.name} {rel.relation_type.value} {tgt.name}")

        if reasoning_chain:
            answer += "\n".join(reasoning_chain[:10])
        else:
            answer = "无法从知识图谱中推理出结论"

        return QAResult(
            question=parsed["query"],
            answer=answer,
            confidence=0.75,
            related_entities=knowledge
        )

    def _answer_comparison(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答比较问题"""
        answer = "根据知识图谱对比：\n"
        details = []

        for e in knowledge[:5]:
            details.append(f"\n**{e.name}**")
            details.append(f"  类型: {e.entity_type.value}")
            if e.properties:
                for k, v in list(e.properties.items())[:5]:
                    details.append(f"  {k}: {v}")

        return QAResult(
            question=parsed["query"],
            answer=answer + "\n".join(details[:15]),
            detailed_answer="\n".join(details),
            confidence=0.75,
            related_entities=knowledge[:5]
        )

    def _answer_howto(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答操作问题"""
        answer = "根据知识图谱，建议步骤如下：\n"

        # 查找工艺链
        processes = [e for e in knowledge if e.entity_type == EntityType.PROCESS]
        if processes:
            for i, p in enumerate(processes[:10], 1):
                answer += f"{i}. {p.name}\n"

        return QAResult(
            question=parsed["query"],
            answer=answer,
            confidence=0.75,
            related_entities=processes
        )

    def _answer_general(self, parsed: Dict, knowledge: List[Entity]) -> QAResult:
        """回答一般问题"""
        if knowledge:
            return QAResult(
                question=parsed["query"],
                answer=f"找到{len(knowledge)}个相关信息：\n" + "\n".join([e.name for e in knowledge[:5]]),
                confidence=0.7,
                related_entities=knowledge[:5]
            )
        return QAResult(question=parsed["query"], answer="未找到相关信息", confidence=0.0)


# ============================================================
# 第二部分：报告生成器
# ============================================================

@dataclass
class ReportSection:
    """报告章节"""
    title: str
    content: str
    tables: List[Dict] = field(default_factory=list)
    figures: List[str] = field(default_factory=list)  # 图表引用


@dataclass
class EIAReport:
    """环评报告"""
    project_name: str
    sections: Dict[str, ReportSection] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)


class ReportGenerator:
    """环评报告自动生成器"""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def generate(self, project_info: Dict) -> EIAReport:
        """生成完整环评报告"""
        report = EIAReport(project_name=project_info.get("name", "未命名项目"))

        # 项目概况
        report.sections["项目概况"] = self._generate_project_overview(project_info)

        # 工艺流程
        report.sections["工艺流程"] = self._generate_process_description()

        # 产污分析
        report.sections["产污分析"] = self._generate_pollution_analysis()

        # 防治措施
        report.sections["防治措施"] = self._generate_control_measures()

        # 影响预测
        report.sections["影响预测"] = self._generate_impact_prediction()

        # 结论建议
        report.sections["结论建议"] = self._generate_conclusions()

        return report

    def _generate_project_overview(self, project_info: Dict) -> ReportSection:
        """生成项目概况"""
        content = f"""
## 1. 项目概况

### 1.1 项目名称
{project_info.get('name', '未命名')}

### 1.2 项目性质
{project_info.get('nature', '新建')}

### 1.3 建设地点
{project_info.get('location', '待定')}

### 1.4 建设规模
{project_info.get('scale', '待定')}

### 1.5 主要建设内容
{project_info.get('content', '待定')}
"""
        return ReportSection(title="项目概况", content=content)

    def _generate_process_description(self) -> ReportSection:
        """生成工艺流程描述"""
        processes = self.kg.get_entities_by_type(EntityType.PROCESS)

        content = "## 2. 工艺流程\n\n### 2.1 工艺流程说明\n\n"
        content += "本项目采用以下主要工艺流程：\n\n"

        # 工艺链
        if len(processes) > 0:
            content += "**工艺流程**：\n"
            for i, p in enumerate(processes[:15], 1):
                content += f"{i}. {p.name}\n"
                if p.properties:
                    for k, v in list(p.properties.items())[:3]:
                        content += f"   - {k}: {v}\n"

        # 设备配置
        equipment = self.kg.get_entities_by_type(EntityType.EQUIPMENT)
        if equipment:
            content += "\n### 2.2 主要设备\n\n"
            for eq in equipment[:10]:
                content += f"- {eq.name}\n"

        # 生成表格
        tables = []
        if processes:
            table = {
                "title": "主要工艺参数表",
                "headers": ["序号", "工序名称", "类型", "主要参数"],
                "rows": []
            }
            for i, p in enumerate(processes[:15], 1):
                params = "; ".join([f"{k}={v}" for k, v in list(p.properties.items())[:2]])
                table["rows"].append([str(i), p.name, p.process_type.value if hasattr(p, 'process_type') else "", params])
            tables.append(table)

        return ReportSection(title="工艺流程", content=content, tables=tables)

    def _generate_pollution_analysis(self) -> ReportSection:
        """生成产污分析"""
        content = "## 3. 产污分析\n\n"

        # 大气污染物
        content += "### 3.1 大气污染物\n\n"
        pollutants = self.kg.get_entities_by_type(EntityType.POLLUTANT)

        air_pollutants = [p for p in pollutants if hasattr(p, 'pollutant_type') and 'air' in str(p.pollutant_type).lower()]
        if air_pollutants:
            content += "| 污染物名称 | 类型 | 产生量 | 排放浓度 |\n"
            content += "|------------|------|--------|----------|\n"
            for p in air_pollutants[:10]:
                amount = p.properties.get('emission_amount', '待定')
                content += f"| {p.name} | {p.pollutant_type.value} | {amount} | 待测 |\n"
        else:
            content += "待完善\n"

        # 废水污染物
        content += "\n### 3.2 水污染物\n\n"
        water_pollutants = [p for p in pollutants if hasattr(p, 'pollutant_type') and 'water' in str(p.pollutant_type).lower()]
        if water_pollutants:
            content += "| 污染物名称 | 类型 | 产生量 |\n"
            content += "|------------|------|--------|\n"
            for p in water_pollutants[:10]:
                amount = p.properties.get('emission_amount', '待定')
                content += f"| {p.name} | {p.pollutant_type.value} | {amount} |\n"

        # 固体废物
        content += "\n### 3.3 固体废物\n\n"
        content += "| 废物名称 | 类型 | 产生量 | 处置方式 |\n"
        content += "|----------|------|--------|----------|\n"
        content += "| 废砂料 | 一般固废 | 待定 | 综合利用 |\n"
        content += "| 漆渣 | 危险废物(HW12) | 待定 | 资质单位处置 |\n"

        return ReportSection(title="产污分析", content=content)

    def _generate_control_measures(self) -> ReportSection:
        """生成防治措施"""
        content = "## 4. 污染防治措施\n\n"

        content += "### 4.1 大气污染防治措施\n\n"
        content += "#### 4.1.1 颗粒物控制\n"
        content += "- 喷砂/打磨工序设置布袋除尘器\n"
        content += "- 除尘效率≥99%，排放浓度≤20mg/m³\n\n"
        content += "#### 4.1.2 VOCs控制\n"
        content += "- 喷漆工序采用高效废气处理系统\n"
        content += "- 处理工艺：活性炭吸附+RCO催化燃烧\n"
        content += "- 处理效率≥95%，排放浓度≤60mg/m³\n\n"

        content += "### 4.2 水污染防治措施\n\n"
        content += "- 生产废水经预处理后回用\n"
        content += "- 采用混凝沉淀+生化处理工艺\n"
        content += "- 处理能力满足生产需求\n\n"

        content += "### 4.3 噪声污染防治措施\n\n"
        content += "- 选用低噪声设备\n"
        content += "- 高噪声设备设置隔声房\n"
        content += "- 设备基础采用减振措施\n\n"

        content += "### 4.4 固体废物防治措施\n\n"
        content += "- 一般固废分类收集，综合利用\n"
        content += "- 危险废物委托资质单位处置\n"
        content += "- 建立固体废物管理台账\n\n"

        # 生成表格
        tables = [{
            "title": "防治措施汇总表",
            "headers": ["类型", "措施", "处理效率", "投资估算(万元)"],
            "rows": [
                ["废气-颗粒物", "布袋除尘器", "≥99%", "15"],
                ["废气-VOCs", "活性炭吸附+RCO", "≥95%", "50"],
                ["废水", "混凝沉淀+生化", "≥80%", "40"],
                ["噪声", "隔声房+减振", "35dB降噪", "13"],
                ["固废", "分类收集", "100%", "5"]
            ]
        }]

        return ReportSection(title="防治措施", content=content, tables=tables)

    def _generate_impact_prediction(self) -> ReportSection:
        """生成影响预测"""
        content = "## 5. 环境影响预测\n\n"

        content += "### 5.1 大气环境影响\n\n"
        content += "- 正常工况下，各污染物排放浓度均满足排放标准要求\n"
        content += "- 非正常工况下，需加强管理，确保处理设施正常运行\n\n"

        content += "### 5.2 水环境影响\n\n"
        content += "- 生产废水处理后回用，不外排\n"
        content += "- 对周边地表水环境影响较小\n\n"

        content += "### 5.3 声环境影响\n\n"
        content += "- 采取隔声降噪措施后，厂界噪声可达标\n"
        content += "- 设备选型优先选用低噪声设备\n\n"

        content += "### 5.4 固体废物环境影响\n\n"
        content += "- 危险废物妥善处置，不产生二次污染\n"
        content += "- 一般固废综合利用，环境风险可控\n\n"

        return ReportSection(title="影响预测", content=content)

    def _generate_conclusions(self) -> ReportSection:
        """生成结论建议"""
        content = "## 6. 结论与建议\n\n"

        content += "### 6.1 结论\n\n"
        content += "1. 本项目建设符合国家产业政策要求\n"
        content += "2. 选址合理可行\n"
        content += "3. 采取的环保措施可行，污染物可达标排放\n"
        content += "4. 对环境影响较小，环境风险可控\n"
        content += "5. 公众参与程序符合要求\n\n"

        content += "### 6.2 建议\n\n"
        content += "1. 严格执行环保设施与主体工程同时设计、同时施工、同时投产使用\n"
        content += "2. 加强环保设施运行管理，确保污染物稳定达标排放\n"
        content += "3. 做好环境监测工作，及时掌握污染物排放情况\n"
        content += "4. 建立环境风险防范措施和应急预案\n\n"

        return ReportSection(title="结论建议", content=content)

    def export_to_markdown(self, report: EIAReport) -> str:
        """导出为Markdown"""
        md = f"# {report.project_name}环境影响评价报告\n\n"
        md += f"**编制日期**: {report.created_at.strftime('%Y年%m月%d日')}\n\n"

        for section in report.sections.values():
            md += f"\n{section.content}\n\n"

            # 添加表格
            for table in section.tables:
                md += f"\n**{table['title']}**\n\n"
                md += "| " + " | ".join(table['headers']) + " |\n"
                md += "| " + " | ".join(["---"] * len(table['headers'])) + " |\n"
                for row in table['rows']:
                    md += "| " + " | ".join(str(c) for c in row) + " |\n"

        return md

    def export_to_json(self, report: EIAReport) -> str:
        """导出为JSON"""
        data = {
            "project_name": report.project_name,
            "created_at": report.created_at.isoformat(),
            "sections": {}
        }

        for name, section in report.sections.items():
            data["sections"][name] = {
                "title": section.title,
                "content": section.content,
                "tables": section.tables,
                "figures": section.figures
            }

        return json.dumps(data, ensure_ascii=False, indent=2)


# ============================================================
# 第三部分：工艺优化器
# ============================================================

@dataclass
class OptimizationSuggestion:
    """优化建议"""
    current_state: str
    suggestion: str
    expected_benefit: str
    difficulty: str  # easy/medium/hard
    priority: int  # 1-5
    confidence: float


class ProcessOptimizer:
    """工艺优化建议生成器"""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def optimize(self, goal: str = "环保") -> List[OptimizationSuggestion]:
        """生成优化建议"""
        suggestions = []

        if goal in ["环保", "both"]:
            suggestions.extend(self._optimize_environmental())

        if goal in ["效率", "both"]:
            suggestions.extend(self._optimize_efficiency())

        return sorted(suggestions, key=lambda x: (x.priority, x.difficulty))

    def _optimize_environmental(self) -> List[OptimizationSuggestion]:
        """环保优化"""
        suggestions = []
        processes = self.kg.get_entities_by_type(EntityType.PROCESS)

        # 检查是否有VOCs排放工序
        vocs_processes = [p for p in processes if "喷漆" in p.name or "涂装" in p.name]
        if vocs_processes:
            suggestions.append(OptimizationSuggestion(
                current_state="喷漆/涂装工序产生VOCs",
                suggestion="采用水性涂料或粉末涂料，VOCs排放量可降低80%以上",
                expected_benefit="VOCs减排80%+，符合最严格排放标准",
                difficulty="medium",
                priority=1,
                confidence=0.9
            ))

        # 检查是否有颗粒物排放工序
        dust_processes = [p for p in processes if "喷砂" in p.name or "打磨" in p.name]
        if dust_processes:
            suggestions.append(OptimizationSuggestion(
                current_state="喷砂/打磨工序产生粉尘",
                suggestion="采用湿式喷砂代替干式喷砂，粉尘排放可降低90%",
                expected_benefit="粉尘减排90%，改善车间工作环境",
                difficulty="easy",
                priority=2,
                confidence=0.9
            ))

        # 检查是否缺少废气处理
        equipment = self.kg.get_entities_by_type(EntityType.EQUIPMENT)
        has_waste_treatment = any("废气" in eq.name or "除尘" in eq.name for eq in equipment)
        if not has_waste_treatment and (vocs_processes or dust_processes):
            suggestions.append(OptimizationSuggestion(
                current_state="缺乏废气处理设施",
                suggestion="配置高效废气处理系统（布袋除尘+活性炭吸附+RCO）",
                expected_benefit="确保废气达标排放，减少环保处罚风险",
                difficulty="hard",
                priority=1,
                confidence=0.95
            ))

        return suggestions

    def _optimize_efficiency(self) -> List[OptimizationSuggestion]:
        """效率优化"""
        suggestions = []
        processes = self.kg.get_entities_by_type(EntityType.PROCESS)

        # 检查工艺链连续性
        if len(processes) > 5:
            suggestions.append(OptimizationSuggestion(
                current_state="工艺链较长，可能存在等待时间",
                suggestion="优化工序排班，实现连续生产，减少等待时间",
                expected_benefit="生产效率提升15-20%",
                difficulty="medium",
                priority=3,
                confidence=0.8
            ))

        # 检查是否有固化等高能耗工序
        high_energy = [p for p in processes if "固化" in p.name or "烘干" in p.name]
        if high_energy:
            suggestions.append(OptimizationSuggestion(
                current_state="固化/烘干工序能耗较高",
                suggestion="采用红外固化或UV固化技术，能耗可降低50%",
                expected_benefit="能耗降低50%，生产成本下降",
                difficulty="hard",
                priority=2,
                confidence=0.85
            ))

        return suggestions


# ============================================================
# 第四部分：知识问答管理器
# ============================================================

class KnowledgeQAManager:
    """知识问答管理器（对外统一接口）"""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
        self.qa_system = IntelligentQA(kg)
        self.report_generator = ReportGenerator(kg)
        self.optimizer = ProcessOptimizer(kg)

    def ask(self, question: str) -> str:
        """问答"""
        result = self.qa_system.answer(question)
        return result.answer

    def generate_report(self, project_info: Dict) -> EIAReport:
        """生成报告"""
        return self.report_generator.generate(project_info)

    def export_report(self, report: EIAReport, format: str = "markdown") -> str:
        """导出报告"""
        if format == "markdown":
            return self.report_generator.export_to_markdown(report)
        elif format == "json":
            return self.report_generator.export_to_json(report)
        return ""

    def get_optimization_suggestions(self, goal: str = "环保") -> List[OptimizationSuggestion]:
        """获取优化建议"""
        return self.optimizer.optimize(goal)


__all__ = [
    'QAResult', 'IntelligentQA',
    'ReportSection', 'EIAReport', 'ReportGenerator',
    'OptimizationSuggestion', 'ProcessOptimizer',
    'KnowledgeQAManager'
]
