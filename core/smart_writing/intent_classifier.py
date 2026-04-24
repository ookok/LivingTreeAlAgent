# -*- coding: utf-8 -*-
"""
智能写作意图分类器 - Dynamic Document Intent Classifier
=======================================================

设计原则：
1. 【不固定文档类型】基于上传内容动态识别，而非硬编码枚举
2. 多策略融合：关键词匹配 + LLM语义分析 + 已有文档相似度对比
3. 与知识库、专家系统和SkillEvolution集成
4. 识别结果反哺知识库，实现自进化

集成模块：
- core/knowledge_vector_db.py       → 向量相似度匹配
- core/fusion_rag/knowledge_base.py → 知识库检索
- expert_system/smart_expert.py     → 专家系统分类辅助
- core/skill_evolution/             → 分类经验自进化

Author: Hermes Desktop Team
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 动态文档分类结果
# =============================================================================

@dataclass
class DocumentClassification:
    """
    动态文档分类结果
    
    不使用固定枚举，用字符串+标签灵活表达文档类型
    """
    # 主类型（自然语言描述，如 "可行性研究报告" / "环境影响评价报告"）
    primary_type: str
    # 标签组（多维度标签，如 ["环境类", "政府审批", "新建项目"]）
    tags: List[str] = field(default_factory=list)
    # 推断依据
    evidence: List[str] = field(default_factory=list)
    # 识别置信度 0-1
    confidence: float = 0.0
    # 提取的关键实体
    entities: Dict[str, Any] = field(default_factory=dict)
    # 缺失信息清单（需要向用户补充的）
    missing_fields: List[str] = field(default_factory=list)
    # 推荐的专家角色
    recommended_experts: List[str] = field(default_factory=list)
    # 推荐的计算模型
    recommended_calculations: List[str] = field(default_factory=dict)
    # 匹配到的知识库文档ID
    matched_kb_ids: List[str] = field(default_factory=list)
    # 识别来源
    source: str = "rule"   # rule / llm / kb_match / hybrid

    def to_dict(self) -> Dict:
        return {
            "primary_type": self.primary_type,
            "tags": self.tags,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "entities": self.entities,
            "missing_fields": self.missing_fields,
            "recommended_experts": self.recommended_experts,
            "recommended_calculations": self.recommended_calculations,
            "matched_kb_ids": self.matched_kb_ids,
            "source": self.source,
        }


# =============================================================================
# 实体抽取器
# =============================================================================

class EntityExtractor:
    """从自然语言需求中抽取关键实体"""

    # 地理位置正则
    _LOCATION_PATTERNS = [
        r"(北京|上海|广州|深圳|武汉|成都|杭州|南京|重庆|西安|苏州|郑州|长沙|青岛)",
        r"([\u4e00-\u9fa5]{2,4}[省市区县镇乡])",
        r"([\u4e00-\u9fa5]{2,4}(开发区|产业园|工业园|保税区|自贸区))",
    ]

    # 行业关键词
    _INDUSTRY_KEYWORDS = {
        "化工": ["化工", "化学品", "石化", "医药", "农药", "染料", "涂料", "树脂", "溶剂"],
        "制造": ["制造", "加工", "生产", "装配", "机械", "电子", "汽车", "钢铁", "铸造"],
        "能源": ["电力", "发电", "风电", "光伏", "太阳能", "核电", "天然气", "煤矿", "油气"],
        "建筑": ["建设", "施工", "房地产", "住宅", "商业", "厂房", "仓储", "交通"],
        "农业": ["农业", "种植", "养殖", "渔业", "林业", "食品", "粮食"],
        "服务": ["服务", "商业", "餐饮", "酒店", "旅游", "物流", "仓储"],
        "环保": ["污水处理", "固废处理", "垃圾", "环保", "废气处理", "脱硫", "脱硝"],
        "矿产": ["矿山", "采矿", "矿产", "铁矿", "铜矿", "金矿", "煤矿"],
    }

    # 金额正则
    _MONEY_PATTERN = re.compile(
        r"([\d,]+(?:\.\d+)?)\s*([亿百千万]元|万元|亿元|元|USD|美元|¥|\$)"
    )

    # 时间正则
    _TIME_PATTERN = re.compile(
        r"(\d+)\s*(?:年|个月|月份|年内|年间|年期|年限)"
    )

    def extract(self, text: str) -> Dict[str, Any]:
        """从文本中抽取实体"""
        entities = {}

        # 地点
        locations = []
        for pat in self._LOCATION_PATTERNS:
            found = re.findall(pat, text)
            if isinstance(found[0], tuple) if found else False:
                found = [f[0] for f in found]
            locations.extend(found)
        if locations:
            entities["location"] = locations[0]
            entities["locations_all"] = list(set(locations))

        # 行业
        for industry, keywords in self._INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                entities.setdefault("industry", industry)
                entities.setdefault("industry_keywords", [kw for kw in keywords if kw in text])

        # 金额
        amounts = self._MONEY_PATTERN.findall(text)
        if amounts:
            entities["investment_raw"] = f"{amounts[0][0]}{amounts[0][1]}"
            try:
                val = float(amounts[0][0].replace(",", ""))
                unit = amounts[0][1]
                if "亿" in unit:
                    val *= 10000  # 转万元
                entities["investment_wan"] = val
            except Exception:
                pass

        # 时间/建设周期
        times = self._TIME_PATTERN.findall(text)
        if times:
            entities["duration"] = f"{times[0]}年" if "年" in text[text.find(times[0]):text.find(times[0])+5] else f"{times[0]}月"

        # 规模/产能
        scale_pattern = re.compile(
            r"(\d+(?:\.\d+)?)\s*(?:万吨|吨|MW|万kW|台|套|万平|平方米|公里|km)"
        )
        scales = scale_pattern.findall(text)
        if scales:
            entities["scale"] = scales[0]

        # 项目名称（尝试抽取）
        name_patterns = [
            r"\u300a(.+?)\u300b",
            r"\u300c(.+?)\u300d",
            r"\u201c(.+?)\u201d",
            r"(.{4,20}(?:项目|工程|系统|平台|基地|中心|工厂))",
        ]
        for pat in name_patterns:
            found = re.findall(pat, text)
            if found:
                entities["project_name"] = found[0]
                break

        return entities


# =============================================================================
# 规则分类器（快速、无需LLM）
# =============================================================================

class RuleBasedClassifier:
    """
    基于规则的快速分类器
    
    特点：不固定类型，通过特征权重动态生成分类描述
    """

    # 分类规则：每条规则 = (关键词列表, 分类名称, 标签, 权重, 推荐计算, 推荐专家, 缺失字段)
    _RULES = [
        # 可行性研究类
        {
            "keywords": ["可行性", "feasibility", "可研", "项目建议书", "投资分析"],
            "type": "可行性研究报告",
            "tags": ["投资分析", "政府审批", "财务评价"],
            "calcs": ["npv", "irr", "payback", "cost"],
            "experts": ["financial_analyst", "project_manager"],
            "missing": ["项目名称", "建设地点", "总投资", "建设规模", "建设周期"],
        },
        # 环境影响评价类
        {
            "keywords": ["环评", "环境影响评价", "eia", "环境保护", "排污许可", "环境影响报告"],
            "type": "环境影响评价报告",
            "tags": ["环保合规", "政府审批", "污染物分析"],
            "calcs": ["emission", "carbon", "gaussian", "noise"],
            "experts": ["env_engineer", "eia_expert"],
            "missing": ["项目类型", "污染物种类", "主要生产工艺", "厂址位置", "周边环境敏感点"],
        },
        # 安全评价类
        {
            "keywords": ["安全评价", "安全评估", "安全现状", "危险化学品", "重大危险源", "安全生产"],
            "type": "安全评价报告",
            "tags": ["安全合规", "政府审批", "风险评估"],
            "calcs": ["ls", "lec"],
            "experts": ["safety_engineer"],
            "missing": ["危险物质种类", "工艺流程", "危险源分布"],
        },
        # 节能评估类
        {
            "keywords": ["节能", "能评", "节能报告", "能源消耗", "节能审查"],
            "type": "节能评估报告",
            "tags": ["节能合规", "政府审批", "能耗分析"],
            "calcs": ["carbon"],
            "experts": ["energy_engineer"],
            "missing": ["主要用能设备", "年能耗量", "节能措施"],
        },
        # 社会稳定风险评估
        {
            "keywords": ["社稳", "社会稳定风险", "稳评", "群众意见", "公众参与"],
            "type": "社会稳定风险评估报告",
            "tags": ["社会风险", "政府审批"],
            "calcs": ["ls"],
            "experts": ["social_analyst"],
            "missing": ["项目类型", "影响范围", "受影响人口"],
        },
        # 规划设计类
        {
            "keywords": ["规划", "总体设计", "初步设计", "施工图", "设计方案"],
            "type": "工程设计文件",
            "tags": ["工程设计", "技术文档"],
            "calcs": ["cost"],
            "experts": ["civil_engineer", "process_engineer"],
            "missing": ["工程规模", "技术方案", "设备选型"],
        },
        # 市场研究类
        {
            "keywords": ["市场调研", "市场分析", "行业分析", "竞争分析", "需求分析"],
            "type": "市场研究报告",
            "tags": ["市场分析", "商业决策"],
            "calcs": ["sensitivity"],
            "experts": ["market_analyst"],
            "missing": ["目标市场", "调研范围", "数据来源"],
        },
        # 商业计划书
        {
            "keywords": ["商业计划", "BP", "融资", "创业", "商业模式", "商业计划书"],
            "type": "商业计划书",
            "tags": ["融资材料", "创业", "商业模式"],
            "calcs": ["npv", "irr", "sensitivity"],
            "experts": ["financial_analyst", "market_analyst"],
            "missing": ["公司简介", "产品/服务", "目标市场", "财务预测"],
        },
        # 土地报批类
        {
            "keywords": ["土地", "用地", "地块", "征地", "拆迁", "国土", "土地利用"],
            "type": "土地利用规划说明",
            "tags": ["土地审批", "政府报批"],
            "calcs": [],
            "experts": ["land_planner"],
            "missing": ["用地面积", "用地性质", "规划用途"],
        },
        # 技术方案类
        {
            "keywords": ["技术方案", "解决方案", "技术规格", "技术路线", "工艺路线"],
            "type": "技术方案报告",
            "tags": ["技术文档", "工程方案"],
            "calcs": ["cost"],
            "experts": ["technical_expert"],
            "missing": ["技术要求", "应用场景", "性能指标"],
        },
    ]

    def classify(self, text: str, entities: Dict) -> Optional[DocumentClassification]:
        """基于规则快速分类"""
        text_lower = text.lower()
        scored = []

        for rule in self._RULES:
            score = sum(1 for kw in rule["keywords"] if kw.lower() in text_lower)
            if score > 0:
                scored.append((score, rule))

        if not scored:
            return None

        # 按匹配得分排序
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_rule = scored[0]
        max_possible = len(best_rule["keywords"])
        confidence = min(best_score / max_possible + 0.1, 0.95)

        evidence = [kw for kw in best_rule["keywords"] if kw.lower() in text_lower]

        # 结合实体动态调整缺失字段
        missing = list(best_rule["missing"])
        if entities.get("project_name"):
            missing = [f for f in missing if "项目名称" not in f]
        if entities.get("location"):
            missing = [f for f in missing if "地点" not in f and "位置" not in f]
        if entities.get("investment_wan"):
            missing = [f for f in missing if "投资" not in f]

        return DocumentClassification(
            primary_type=best_rule["type"],
            tags=best_rule["tags"][:],
            evidence=evidence,
            confidence=confidence,
            entities=entities,
            missing_fields=missing,
            recommended_experts=best_rule["experts"][:],
            recommended_calculations=best_rule["calcs"][:],
            source="rule"
        )


# =============================================================================
# LLM辅助分类器（调用本地Ollama）
# =============================================================================

class LLMClassifier:
    """
    基于LLM的语义分类器
    
    当规则分类器置信度低时启用
    调用本地Ollama（qwen2.5:1.5b），保持低延迟
    """

    _PROMPT_TEMPLATE = """你是一个专业文档分类助手。根据以下用户需求，识别文档类型。

用户需求：
{requirement}

请返回JSON格式（不要markdown代码块，直接返回）：
{{
  "primary_type": "文档类型名称（自然语言，如：可行性研究报告）",
  "tags": ["标签1", "标签2"],
  "confidence": 0.85,
  "missing_fields": ["缺少的信息1", "缺少的信息2"],
  "recommended_calculations": ["npv", "irr"],
  "reasoning": "判断依据"
}}"""

    def __init__(self, model: str = "qwen2.5:1.5b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def classify(self, text: str, entities: Dict) -> Optional[DocumentClassification]:
        """调用LLM进行语义分类"""
        try:
            import urllib.request
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": self._PROMPT_TEMPLATE.format(requirement=text[:2000])}
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512}
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/v1/chat/completions",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"].strip()

                # 清理可能的markdown代码块
                if content.startswith("```"):
                    content = re.sub(r"```(?:json)?", "", content).strip("` \n")

                parsed = json.loads(content)
                return DocumentClassification(
                    primary_type=parsed.get("primary_type", "未知文档类型"),
                    tags=parsed.get("tags", []),
                    evidence=[parsed.get("reasoning", "LLM语义判断")],
                    confidence=float(parsed.get("confidence", 0.7)),
                    entities=entities,
                    missing_fields=parsed.get("missing_fields", []),
                    recommended_calculations=parsed.get("recommended_calculations", []),
                    source="llm"
                )
        except Exception as e:
            logger.warning(f"LLM分类失败: {e}")
            return None


# =============================================================================
# 知识库辅助分类器（复用 KnowledgeBaseLayer）
# =============================================================================

class KBClassifier:
    """
    基于知识库的分类器
    
    将历史文档分类经验存入知识库
    新文档通过向量相似度匹配历史案例
    """

    def __init__(self):
        self._kb = None
        self._vector_db = None

    def _get_kb(self):
        if self._kb is None:
            try:
                from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
                self._kb = KnowledgeBaseLayer()
            except ImportError:
                pass
        return self._kb

    def _get_vector_db(self):
        if self._vector_db is None:
            try:
                from core.knowledge_vector_db import KnowledgeBaseVectorStore
                self._vector_db = KnowledgeBaseVectorStore()
            except ImportError:
                pass
        return self._vector_db

    def classify(self, text: str, entities: Dict) -> Optional[DocumentClassification]:
        """通过知识库匹配历史文档类型案例"""
        kb = self._get_kb()
        if not kb:
            return None

        try:
            # 搜索相似案例
            results = kb.search(f"文档类型识别: {text[:200]}", top_k=3)
            if not results:
                return None

            # 取最相似的案例
            best = results[0]
            metadata = best.get("metadata", {})
            if metadata.get("doc_classification"):
                cls_data = metadata["doc_classification"]
                return DocumentClassification(
                    primary_type=cls_data.get("primary_type", ""),
                    tags=cls_data.get("tags", []),
                    evidence=[f"知识库匹配案例: {best.get('title', '')}"],
                    confidence=float(best.get("score", 0.6)) * 0.9,
                    entities=entities,
                    missing_fields=cls_data.get("missing_fields", []),
                    recommended_calculations=cls_data.get("recommended_calculations", []),
                    matched_kb_ids=[best.get("id", "")],
                    source="kb_match"
                )
        except Exception as e:
            logger.warning(f"KB分类失败: {e}")

        return None

    def store_classification(self, text: str, classification: DocumentClassification):
        """将成功的分类结果存入知识库（自进化）"""
        kb = self._get_kb()
        if not kb or not classification.primary_type:
            return
        try:
            doc = {
                "title": f"分类案例: {classification.primary_type}",
                "content": text[:500],
                "metadata": {
                    "doc_classification": classification.to_dict(),
                    "created_at": time.time(),
                    "source": "auto_classified"
                }
            }
            kb.add_document(doc)
            logger.info(f"分类结果已存入知识库: {classification.primary_type}")
        except Exception as e:
            logger.warning(f"存入知识库失败: {e}")


# =============================================================================
# 自进化意图分类器（核心）
# =============================================================================

class DocumentIntentClassifier:
    """
    文档意图分类器 - 自进化版
    
    多策略融合：
    1. 规则分类（毫秒级，无需LLM）
    2. 知识库匹配（历史案例学习）
    3. LLM语义分类（规则无法处理时）
    4. 结果反馈到知识库（自进化）
    
    使用示例：
        classifier = DocumentIntentClassifier()
        
        # 从文本分类
        result = classifier.classify("帮我写一个武汉化工项目的可行性研究报告")
        print(result.primary_type)   # → "可行性研究报告"
        
        # 从上传文档内容分类
        result = classifier.classify_from_document(doc_content, file_name="某某项目EIA.pdf")
    """

    def __init__(self, use_llm: bool = True, use_kb: bool = True):
        self.entity_extractor = EntityExtractor()
        self.rule_classifier = RuleBasedClassifier()
        self.llm_classifier = LLMClassifier() if use_llm else None
        self.kb_classifier = KBClassifier() if use_kb else None
        self._skill_evolution = None

    def _get_skill_evolution(self):
        """获取SkillEvolutionAgent（延迟加载）"""
        if self._skill_evolution is None:
            try:
                from core.skill_evolution.agent_loop import SkillEvolutionAgent
                self._skill_evolution = SkillEvolutionAgent()
            except ImportError:
                pass
        return self._skill_evolution

    def classify(self, requirement: str, feedback: str = "") -> DocumentClassification:
        """
        从文本需求分类文档类型
        
        Args:
            requirement: 用户需求文本
            feedback: 用户的反馈（用于修正，触发自进化）
        """
        # 1. 实体抽取
        entities = self.entity_extractor.extract(requirement)

        # 2. 规则快速分类
        rule_result = self.rule_classifier.classify(requirement, entities)

        # 3. 知识库历史匹配
        kb_result = None
        if self.kb_classifier:
            kb_result = self.kb_classifier.classify(requirement, entities)

        # 4. 融合策略
        if rule_result and rule_result.confidence >= 0.7:
            # 规则高置信度 → 直接使用
            final = rule_result
            if kb_result and kb_result.matched_kb_ids:
                final.matched_kb_ids = kb_result.matched_kb_ids
        elif kb_result and kb_result.confidence >= 0.65:
            # 知识库匹配 → 使用KB结果
            final = kb_result
        elif rule_result:
            # 规则低置信度 → 尝试LLM增强
            if self.llm_classifier:
                llm_result = self.llm_classifier.classify(requirement, entities)
                if llm_result and llm_result.confidence > rule_result.confidence:
                    final = llm_result
                    # 补充规则找到的实体
                    final.entities.update(rule_result.entities)
                else:
                    final = rule_result
            else:
                final = rule_result
        else:
            # 全规则未命中 → LLM兜底
            final = self._llm_fallback(requirement, entities)

        # 5. 处理用户反馈（修正分类）
        if feedback:
            final = self._apply_feedback(final, feedback)

        # 6. 结果存入知识库（自进化）
        if final.confidence >= 0.5 and self.kb_classifier:
            self.kb_classifier.store_classification(requirement, final)

        return final

    def classify_from_document(
        self,
        doc_content: str,
        file_name: str = "",
        requirement: str = ""
    ) -> DocumentClassification:
        """
        从上传的文档内容动态分类（关键功能）
        
        Args:
            doc_content: 文档内容（通常取前2000字）
            file_name: 文件名（提供额外线索）
            requirement: 用户附加的说明
        """
        # 综合文件名 + 文档内容 + 用户说明
        analysis_text = ""
        if file_name:
            analysis_text += f"文件名: {file_name}\n"
        analysis_text += f"文档内容摘要:\n{doc_content[:1500]}"
        if requirement:
            analysis_text += f"\n用户说明: {requirement}"

        result = self.classify(analysis_text)

        # 从文档内容补充实体
        doc_entities = self.entity_extractor.extract(doc_content[:2000])
        result.entities.update(doc_entities)

        # 标记来源为上传文档
        result.source = f"document_upload+{result.source}"

        return result

    def classify_batch(self, documents: List[Dict]) -> List[DocumentClassification]:
        """
        批量分类文档
        
        Args:
            documents: [{"content": ..., "file_name": ..., "requirement": ...}]
        """
        results = []
        for doc in documents:
            result = self.classify_from_document(
                doc_content=doc.get("content", ""),
                file_name=doc.get("file_name", ""),
                requirement=doc.get("requirement", "")
            )
            results.append(result)
        return results

    def _llm_fallback(self, text: str, entities: Dict) -> DocumentClassification:
        """LLM兜底分类"""
        if self.llm_classifier:
            result = self.llm_classifier.classify(text, entities)
            if result:
                return result

        # 最终兜底：返回通用文档类型
        return DocumentClassification(
            primary_type="通用报告文档",
            tags=["通用", "待确认"],
            evidence=["未能识别具体类型"],
            confidence=0.3,
            entities=entities,
            missing_fields=["文档类型", "项目名称", "主要用途"],
            source="fallback"
        )

    def _apply_feedback(
        self,
        classification: DocumentClassification,
        feedback: str
    ) -> DocumentClassification:
        """
        根据用户反馈修正分类（自进化触发点）
        """
        # 简单关键词修正
        if "不对" in feedback or "错了" in feedback or "应该是" in feedback:
            # 尝试从反馈中提取正确类型
            corrected_type = re.search(r"应该是(.{4,20}(?:报告|文件|方案|计划|评价))", feedback)
            if corrected_type:
                classification.primary_type = corrected_type.group(1).strip()
                classification.confidence = 0.95
                classification.evidence.append(f"用户反馈修正: {feedback[:50]}")
                classification.source += "+user_feedback"

                # 触发SkillEvolution记录修正经验
                self._record_correction_to_skill_evolution(classification, feedback)

        return classification

    def _record_correction_to_skill_evolution(
        self,
        classification: DocumentClassification,
        feedback: str
    ):
        """将用户修正记录到SkillEvolution系统"""
        agent = self._get_skill_evolution()
        if agent is None:
            return
        try:
            # 将成功分类经验作为任务执行记录
            task_ctx = agent.execute_task(
                task_description=f"文档分类: {classification.primary_type}",
                task_type="document_classification",
                initial_context={
                    "classification": classification.to_dict(),
                    "user_feedback": feedback,
                    "corrected": True,
                }
            )
            logger.info(f"分类修正经验已记录到SkillEvolution: {task_ctx.status}")
        except Exception as e:
            logger.warning(f"SkillEvolution记录失败: {e}")

    def get_requirements_checklist(self, classification: DocumentClassification) -> List[Dict]:
        """
        生成需求补充清单（引导用户填写缺失信息）
        """
        checklist = []
        for field_name in classification.missing_fields:
            # 生成引导问题
            question = self._field_to_question(field_name, classification.primary_type)
            checklist.append({
                "field": field_name,
                "question": question,
                "required": True,
                "hint": self._get_field_hint(field_name),
            })
        return checklist

    def _field_to_question(self, field_name: str, doc_type: str) -> str:
        """字段名转引导问题"""
        mapping = {
            "项目名称": "项目的正式名称是什么？（如：XX公司XX项目）",
            "建设地点": "项目建设的具体地点是哪里？（省/市/县）",
            "总投资": "项目预计总投资金额是多少？（万元）",
            "建设规模": f"该{doc_type}项目的建设规模/产能是多少？",
            "建设周期": "预计建设周期（从开工到投产）是多少年？",
            "污染物种类": "项目运营过程中会产生哪些主要污染物？",
            "工艺流程": "项目主要生产工艺/技术路线是什么？",
            "厂址位置": "厂址的具体坐标或行政区域是？",
        }
        return mapping.get(field_name, f"请提供{field_name}的相关信息")

    def _get_field_hint(self, field_name: str) -> str:
        """字段填写提示"""
        hints = {
            "总投资": "格式示例：5000万元，包含建设投资+流动资金",
            "建设规模": "格式示例：年产10万吨XX产品",
            "污染物种类": "格式示例：废气（SO₂、NOx）、废水（COD、SS）、固废（炉渣）",
            "工艺流程": "请简要描述主要生产流程或技术方案",
        }
        return hints.get(field_name, "")


# =============================================================================
# 快捷函数
# =============================================================================

_classifier_instance: Optional[DocumentIntentClassifier] = None

def get_classifier() -> DocumentIntentClassifier:
    """获取分类器单例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = DocumentIntentClassifier()
    return _classifier_instance


def quick_classify(text: str) -> DocumentClassification:
    """快速分类（单行调用）"""
    return get_classifier().classify(text)


def classify_document(
    content: str,
    file_name: str = "",
    requirement: str = ""
) -> DocumentClassification:
    """从上传文档分类（单行调用）"""
    return get_classifier().classify_from_document(content, file_name, requirement)
