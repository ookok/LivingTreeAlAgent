"""
咨询模式模块
Consulting Mode Module

专注于咨询行业的写作需求：
- 结构化框架生成
- 数据可视化
- 方法论集成
- 团队协作
"""

import re
import json
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ConsultingFramework(Enum):
    """咨询框架"""
    Mckinsey7S = "mckinsey_7s"           # 麦肯锡7S
    SWOT = "swot"                        # SWOT分析
    Porter5Forces = "porter_5_forces"    # 波特五力
    PEST = "pest"                        # PEST分析
    BCG_Matrix = "bcg_matrix"           # 波士顿矩阵
    ValueChain = "value_chain"          # 价值链分析
    BusinessCanvas = "business_canvas"  # 商业画布
    Ansoff = "ansoff"                   # 安索夫矩阵


class DocumentType(Enum):
    """咨询文档类型"""
    MarketResearch = "market_research"      # 市场研究报告
    StrategicPlan = "strategic_plan"        # 战略规划
    DueDiligence = "due_diligence"          # 尽职调查
    CompetitiveAnalysis = "competitive_analysis"  # 竞争分析
    FeasibilityStudy = "feasibility_study" # 可行性研究
    BusinessProposal = "business_proposal"  # 商业提案
    IndustryReport = "industry_report"      # 行业报告
    InvestmentMemo = "investment_memo"      # 投资备忘录


@dataclass
class SectionTemplate:
    """章节模板"""
    id: str
    name: str
    description: str
    content_template: str
    keywords: list = field(default_factory=list)
    required_data: list = field(default_factory=list)
    framework: Optional[ConsultingFramework] = None


@dataclass
class ConsultingProject:
    """咨询项目"""
    project_id: str
    project_name: str
    client_name: str = ""
    industry: str = ""
    doc_type: DocumentType = DocumentType.MarketResearch
    
    # 进度
    status: str = "planning"  # planning/in_progress/review/completed
    progress_percent: float = 0.0
    deadline: Optional[datetime] = None
    
    # 内容
    sections: list = field(default_factory=list)
    current_section: int = 0
    
    # 团队
    team_members: list = field(default_factory=list)
    current_assignee: str = ""
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ConsultingMode:
    """
    咨询模式引擎
    
    提供咨询行业专用的写作功能
    """
    
    # 预设章节模板
    TEMPLATES: dict[DocumentType, list[SectionTemplate]] = {
        DocumentType.MarketResearch: [
            SectionTemplate(
                id="exec_summary",
                name="执行摘要",
                description="报告核心发现和建议的简要概述",
                content_template="""## 执行摘要

### 核心发现
- 发现1: {finding1}
- 发现2: {finding2}
- 发现3: {finding3}

### 关键建议
1. 建议1: {recommendation1}
2. 建议2: {recommendation2}

### 预期影响
{impact_summary}
""",
                keywords=["摘要", "核心", "发现", "建议"],
                framework=None,
            ),
            SectionTemplate(
                id="market_overview",
                name="市场概览",
                description="市场规模、增长率和关键趋势",
                content_template="""## 市场概览

### 市场规模
- 当前市场规模: {market_size}
- 历史增长率: {historical_cagr}%
- 预测期: {forecast_period}

### 市场驱动因素
| 驱动因素 | 影响程度 | 趋势 |
|---------|---------|------|
| {driver1} | {impact1} | {trend1} |
| {driver2} | {impact2} | {trend2} |

### 市场挑战
- 挑战1: {challenge1}
- 挑战2: {challenge2}
""",
                keywords=["市场", "规模", "增长", "趋势"],
                framework=None,
            ),
            SectionTemplate(
                id="competitive_landscape",
                name="竞争格局",
                description="主要竞争对手分析和市场份额",
                content_template="""## 竞争格局

### 主要竞争者
{competitor_analysis}

### SWOT分析
| 因素 | 内容 |
|------|------|
| 优势(Strengths) | {strengths} |
| 劣势(Weaknesses) | {weaknesses} |
| 机会(Opportunities) | {opportunities} |
| 威胁(Threats) | {threats} |

### 市场定位
{market_positioning}
""",
                keywords=["竞争", "SWOT", "市场份额", "定位"],
                framework=ConsultingFramework.SWOT,
            ),
            SectionTemplate(
                id="strategic_recommendations",
                name="战略建议",
                description="基于分析的战略建议和实施路径",
                content_template="""## 战略建议

### 短期建议 (0-12个月)
1. 建议: {short_term_rec1}
   - 预期效果: {short_term_effect1}
   - 资源需求: {short_term_resources1}

### 中期建议 (1-3年)
1. 建议: {mid_term_rec1}
   - 预期效果: {mid_term_effect1}
   - 资源需求: {mid_term_resources1}

### 长期建议 (3-5年)
1. 建议: {long_term_rec1}
   - 预期效果: {long_term_effect1}
   - 资源需求: {long_term_resources1}

### 实施路线图
{implementation_roadmap}
""",
                keywords=["建议", "战略", "实施", "路线图"],
                framework=ConsultingFramework.Ansoff,
            ),
        ],
        DocumentType.StrategicPlan: [
            SectionTemplate(
                id="vision_mission",
                name="愿景与使命",
                description="企业愿景、使命和核心价值观",
                content_template="""## 愿景与使命

### 愿景
{vision}

### 使命
{mission}

### 核心价值观
- 价值1: {value1}
- 价值2: {value2}
- 价值3: {value3}
""",
                keywords=["愿景", "使命", "价值观"],
            ),
            SectionTemplate(
                id="strategic_objectives",
                name="战略目标",
                description="长期和短期战略目标",
                content_template="""## 战略目标

### 长期目标 (3-5年)
| 目标 | 指标 | 基准 | 目标值 |
|------|------|------|--------|
| {obj1} | {kpi1} | {baseline1} | {target1} |
| {obj2} | {kpi2} | {baseline2} | {target2} |

### 年度目标
{annual_objectives}
""",
                keywords=["目标", "指标", "KPI"],
            ),
            SectionTemplate(
                id="7s_analysis",
                name="7S分析",
                description="麦肯锡7S组织分析框架",
                content_template="""## 麦肯锡7S分析

| 要素 | 硬要素 | 软要素 |
|------|--------|--------|
| 战略(Strategy) | {strategy} | - |
| 结构(Structure) | {structure} | - |
| 系统(Systems) | {systems} | - |
| 共享价值观(Shared Values) | - | {shared_values} |
| 风格(Style) | - | {management_style} |
| 员工(Staff) | - | {staff} |
| 技能(Skills) | - | {skills} |

### 战略一致性评估
{consistency_assessment}
""",
                keywords=["7S", "组织", "战略"],
                framework=ConsultingFramework.Mckinsey7S,
            ),
        ],
        DocumentType.CompetitiveAnalysis: [
            SectionTemplate(
                id="industry_structure",
                name="行业结构分析",
                description="波特五力行业结构分析",
                content_template="""## 行业结构分析 (波特五力)

### 1. 现有竞争者
{competitor_intensity}
- 主要玩家: {key_players}
- 竞争强度: {intensity_level}

### 2. 新进入者威胁
{new_entrant_threat}
- 进入壁垒: {barriers}
- 进入速度: {entry_speed}

### 3. 替代品威胁
{substitute_threat}
- 替代品类型: {substitute_types}
- 替代程度: {substitution_level}

### 4. 供应商议价能力
{supplier_power}
- 主要供应商: {major_suppliers}
- 集中度: {concentration}

### 5. 买家议价能力
{buyer_power}
- 主要买家: {major_buyers}
- 价格敏感度: {price_sensitivity}
""",
                keywords=["波特", "五力", "行业结构"],
                framework=ConsultingFramework.Porter5Forces,
            ),
        ],
        DocumentType.BusinessProposal: [
            SectionTemplate(
                id="problem_statement",
                name="问题陈述",
                description="客户面临的核心问题和痛点",
                content_template="""## 问题陈述

### 核心痛点
{core_problems}

### 问题影响
- 财务影响: {financial_impact}
- 运营影响: {operational_impact}
- 战略影响: {strategic_impact}

### 问题根源分析
{root_cause}
""",
                keywords=["问题", "痛点", "影响"],
            ),
            SectionTemplate(
                id="solution_approach",
                name="解决方案",
                description="推荐的解决方案和方法",
                content_template="""## 解决方案

### 方法论
{approach_methodology}

### 解决方案框架
{solution_framework}

### 预期成果
| 成果类型 | 具体内容 | 衡量指标 |
|---------|---------|---------|
| {outcome1} | {outcome1_desc} | {outcome1_kpi} |
| {outcome2} | {outcome2_desc} | {outcome2_kpi} |

### 实施方法
{implementation_approach}
""",
                keywords=["方案", "方法", "成果"],
            ),
        ],
    }
    
    def __init__(self, agent=None):
        self.agent = agent
        self.current_project: Optional[ConsultingProject] = None
        
        # 预设的框架生成器
        self.framework_generators: dict = {
            ConsultingFramework.SWOT: self._generate_swot,
            ConsultingFramework.Porter5Forces: self._generate_porter5,
            ConsultingFramework.Mckinsey7S: self._generate_7s,
            ConsultingFramework.BCG_Matrix: self._generate_bcg,
            ConsultingFramework.PEST: self._generate_pest,
            ConsultingFramework.BusinessCanvas: self._generate_canvas,
        }
    
    # ==================== 项目管理 ====================
    
    def create_project(
        self,
        project_name: str,
        doc_type: DocumentType,
        client_name: str = "",
        industry: str = "",
    ) -> ConsultingProject:
        """创建咨询项目"""
        project = ConsultingProject(
            project_id=self._generate_id(),
            project_name=project_name,
            client_name=client_name,
            industry=industry,
            doc_type=doc_type,
        )
        
        # 初始化章节
        project.sections = self._get_template_sections(doc_type)
        
        self.current_project = project
        return project
    
    def _generate_id(self) -> str:
        """生成项目ID"""
        import time
        return f"CP-{int(time.time())}"
    
    def _get_template_sections(self, doc_type: DocumentType) -> list:
        """获取文档类型的章节模板"""
        templates = self.TEMPLATES.get(doc_type, [])
        return [t.id for t in templates]
    
    def get_project_status(self) -> dict:
        """获取项目状态"""
        if not self.current_project:
            return {"status": "no_project"}
        
        p = self.current_project
        return {
            "project_name": p.project_name,
            "status": p.status,
            "progress": f"{p.progress_percent:.0%}",
            "current_section": p.current_section,
            "total_sections": len(p.sections),
            "sections_remaining": len(p.sections) - p.current_section,
        }
    
    # ==================== 框架生成 ====================
    
    def generate_framework(
        self,
        framework: ConsultingFramework,
        context: dict,
    ) -> str:
        """
        生成咨询框架
        
        Args:
            framework: 框架类型
            context: 上下文数据
            
        Returns:
            框架内容
        """
        generator = self.framework_generators.get(framework)
        if not generator:
            return "[不支持的框架]"
        
        return generator(context)
    
    def _generate_swot(self, context: dict) -> str:
        """生成SWOT分析"""
        template = """
## SWOT分析

### 优势 (Strengths)
{strengths}

### 劣势 (Weaknesses)
{weaknesses}

### 机会 (Opportunities)
{opportunities}

### 威胁 (Threats)
{threats}

### SWOT矩阵

| | 正面 | 负面 |
|---|------|------|
| **内部** | S-O策略: {so_strategy} | W-T策略: {wt_strategy} |
| **外部** | S-T策略: {st_strategy} | W-O策略: {wo_strategy} |
"""
        return self._fill_template(template, context)
    
    def _generate_porter5(self, context: dict) -> str:
        """生成波特五力分析"""
        template = """
## 波特五力分析

### 1. 现有竞争者竞争强度
{intensity}

### 2. 新进入者威胁
{new_entrant_threat}

### 3. 替代品威胁
{substitute_threat}

### 4. 供应商议价能力
{supplier_power}

### 5. 买家议价能力
{buyer_power}

### 行业吸引力评估
{attractiveness}
"""
        return self._fill_template(template, context)
    
    def _generate_7s(self, context: dict) -> str:
        """生成7S分析"""
        template = """
## 麦肯锡7S分析

| 要素 | 内容 |
|------|------|
| 战略 (Strategy) | {strategy} |
| 结构 (Structure) | {structure} |
| 系统 (Systems) | {systems} |
| 共享价值观 (Shared Values) | {shared_values} |
| 风格 (Style) | {style} |
| 员工 (Staff) | {staff} |
| 技能 (Skills) | {skills} |
"""
        return self._fill_template(template, context)
    
    def _generate_bcg(self, context: dict) -> str:
        """生成BCG矩阵"""
        template = """
## BCG矩阵

| 业务 | 市场增长率 | 相对市场份额 | 象限 |
|------|-----------|-------------|------|
{bcg_matrix_rows}

### 战略建议
{strategy_recommendations}
"""
        # 处理BCG矩阵行
        rows = context.get("bcg_items", [])
        if rows:
            row_text = "\n".join([
                f"| {item.get('name', '')} | {item.get('growth', '')} | {item.get('share', '')} | {item.get('quadrant', '')} |"
                for item in rows
            ])
            context["bcg_matrix_rows"] = row_text
        
        return self._fill_template(template, context)
    
    def _generate_pest(self, context: dict) -> str:
        """生成PEST分析"""
        template = """
## PEST分析

### 政治因素 (Political)
{political}

### 经济因素 (Economic)
{economic}

### 社会因素 (Social)
{social}

### 技术因素 (Technological)
{technological}

### 综合评估
{overall_assessment}
"""
        return self._fill_template(template, context)
    
    def _generate_canvas(self, context: dict) -> str:
        """生成商业画布"""
        template = """
## 商业画布

| 合作伙伴 | 关键活动 | 价值主张 | 客户关系 | 客户细分 |
|---------|---------|---------|---------|---------|
| {partners} | {activities} | {value} | {relationships} | {segments} |

| 资源 | 渠道 | 成本结构 | 收入流 |
|------|------|---------|--------|
| {resources} | {channels} | {costs} | {revenue} |
"""
        return self._fill_template(template, context)
    
    def _fill_template(self, template: str, context: dict) -> str:
        """填充模板"""
        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        
        # 清理未填充的占位符
        result = re.sub(r"\{[^}]+\}", "", result)
        return result
    
    # ==================== 章节生成 ====================
    
    def get_section_template(self, section_id: str, doc_type: DocumentType) -> Optional[SectionTemplate]:
        """获取章节模板"""
        templates = self.TEMPLATES.get(doc_type, [])
        for t in templates:
            if t.id == section_id:
                return t
        return None
    
    def generate_section(
        self,
        section_id: str,
        doc_type: DocumentType,
        data: dict,
    ) -> str:
        """生成章节内容"""
        template = self.get_section_template(section_id, doc_type)
        if not template:
            return f"[未找到章节模板: {section_id}]"
        
        return self._fill_template(template.content_template, data)
    
    def get_outline(self, doc_type: DocumentType) -> list[dict]:
        """获取文档大纲"""
        templates = self.TEMPLATES.get(doc_type, [])
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "framework": t.framework.value if t.framework else None,
            }
            for t in templates
        ]
    
    # ==================== 数据处理 ====================
    
    def process_data_table(self, data: str, chart_type: str = "auto") -> dict:
        """
        处理数据表格
        
        Args:
            data: CSV或制表符分隔的数据
            chart_type: 推荐的图表类型
            
        Returns:
            处理结果
        """
        # 解析数据
        lines = data.strip().split("\n")
        if len(lines) < 2:
            return {"error": "数据格式错误"}
        
        headers = lines[0].split("\t") if "\t" in lines[0] else lines[0].split(",")
        headers = [h.strip() for h in headers]
        
        rows = []
        for line in lines[1:]:
            values = line.split("\t") if "\t" in line else line.split(",")
            rows.append([v.strip() for v in values])
        
        # 分析数据特征
        numeric_cols = []
        for i, col in enumerate(headers):
            try:
                [float(row[i]) for row in rows]
                numeric_cols.append(col)
            except (ValueError, IndexError):
                pass
        
        # 推荐图表
        recommendations = self._recommend_chart(
            len(headers),
            len(numeric_cols),
            chart_type,
        )
        
        return {
            "headers": headers,
            "rows": rows,
            "numeric_columns": numeric_cols,
            "recommendations": recommendations,
        }
    
    def _recommend_chart(
        self,
        num_columns: int,
        num_numeric: int,
        preferred_type: str,
    ) -> dict:
        """推荐图表类型"""
        if preferred_type != "auto":
            return {"type": preferred_type, "confidence": 0.9}
        
        # 基于数据特征推荐
        if num_numeric == 1:
            return {"type": "bar", "confidence": 0.8}
        elif num_numeric == 2:
            return {"type": "line", "confidence": 0.85}
        elif num_numeric >= 3:
            return {"type": "combo", "confidence": 0.7}
        else:
            return {"type": "table", "confidence": 0.6}
    
    # ==================== 格式导出 ====================
    
    def format_for_ppt(self, content: str) -> list[dict]:
        """
        格式化为PPT内容
        
        Returns:
            每页幻灯片内容
        """
        slides = []
        sections = content.split("\n## ")
        
        for i, section in enumerate(sections[1:], 1):  # 跳过空的第一部分
            lines = section.strip().split("\n")
            title = lines[0].strip()
            bullet_points = [l.strip() for l in lines[1:] if l.strip().startswith("-")]
            
            slides.append({
                "slide_number": i,
                "title": title,
                "bullets": bullet_points[:5],  # 限制每页点数
            })
        
        return slides
    
    def format_for_email(self, content: str, recipient: str = "") -> str:
        """格式化为邮件内容"""
        return f"""Dear {recipient},

{content}

Best regards,
[Your Name]
"""
    
    # ==================== 一致性检查 ====================
    
    def check_logical_consistency(
        self,
        content: str,
    ) -> list[dict]:
        """
        检查逻辑一致性
        
        Returns:
            发现的问题列表
        """
        issues = []
        
        # 检查数据一致性
        data_refs = re.findall(r"(\d+(?:\.\d+)?)\s*(%|百万|亿|倍)", content)
        # 简化：只检查是否存在数据
        
        # 检查论点-论据匹配
        claims = re.findall(r"(认为|相信|应该|必须|需要)\s*([^,。]+)", content)
        for claim, reason in claims:
            if len(reason) < 10:  # 论据过短
                issues.append({
                    "type": "weak_argument",
                    "severity": "warning",
                    "content": f"论点可能缺乏充分论据: {claim}...",
                    "suggestion": "请补充更详细的论证",
                })
        
        return issues
