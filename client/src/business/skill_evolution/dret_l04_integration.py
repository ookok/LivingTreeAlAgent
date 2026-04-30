"""
DRET 系统与 L0-L4 架构集成 (增强版)
=====================================

新增功能:
- 可配置递归深度 (最高 20 层)
- 集成专家角色查找系统 (PersonaDispatcher, ExpertRepository)

复用组件:
- L0: L0RouteCache (路由缓存)
- L1: ExactCacheLayer (精确缓存)
- L2: SessionCacheLayer (会话缓存)
- L3: KnowledgeBaseLayer (知识库)
- L4: L4RelayExecutor (LLM 执行器)

集成模块:
- IntelligentRouter (智能路由)
- FusionEngine (结果融合)
- QueryIntentClassifier (意图分类)
- PersonaDispatcher (专家人格调度)
- ExpertRepository (专家仓库)
"""

import asyncio
import time
import hashlib
import re
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# ════════════════════════════════════════════════════════════════════════════
# 尝试导入 L0-L4 组件
# ════════════════════════════════════════════════════════════════════════════

def _import_l04_components():
    """延迟导入 L0-L4 组件"""
    components = {}

    try:
        from business.fusion_rag.intent_classifier import QueryIntentClassifier
        components["intent_classifier"] = QueryIntentClassifier
    except ImportError:
        pass

    try:
        from business.fusion_rag.knowledge_base import KnowledgeBaseLayer
        components["knowledge_base"] = KnowledgeBaseLayer
    except ImportError:
        pass

    try:
        from business.fusion_rag.session_cache import SessionCacheLayer
        components["session_cache"] = SessionCacheLayer
    except ImportError:
        pass

    try:
        from business.fusion_rag.exact_cache import ExactCacheLayer
        components["exact_cache"] = ExactCacheLayer
    except ImportError:
        pass

    try:
        from business.fusion_rag.l4_executor import get_l4_executor, L4RelayExecutor
        components["l4_executor"] = get_l4_executor
        components["l4_class"] = L4RelayExecutor
    except ImportError:
        pass

    try:
        from business.fusion_rag.intelligent_router import IntelligentRouter
        components["router"] = IntelligentRouter
    except ImportError:
        pass

    try:
        from business.fusion_rag.fusion_engine import FusionEngine
        components["fusion_engine"] = FusionEngine
    except ImportError:
        pass

    try:
        from unified_cache import UnifiedCache, get_unified_cache
        components["unified_cache"] = UnifiedCache
        components["get_cache"] = get_unified_cache
    except ImportError:
        pass

    # ════════════════════════════════════════════════════════════════════════════
    # 导入专家角色系统组件
    # ════════════════════════════════════════════════════════════════════════════
    try:
        from expert_system import (
            PersonaDispatcher, Persona, PersonaLibrary,
            UserProfileParser, UserProfile,
            ExpertRepository
        )
        components["persona_dispatcher"] = PersonaDispatcher
        components["persona_library"] = PersonaLibrary
        components["user_profile_parser"] = UserProfileParser
        components["expert_repository"] = ExpertRepository
        print("[DRET-EXPERT] 专家角色系统组件加载成功")
    except ImportError as e:
        print(f"[DRET-EXPERT] 专家角色系统组件导入失败: {e}")
        pass

    return components

# 全局组件注册
L04_COMPONENTS = _import_l04_components()


# ════════════════════════════════════════════════════════════════════════════
# 递归深度配置
# ════════════════════════════════════════════════════════════════════════════

class RecursionDepthConfig:
    """递归深度配置"""
    
    # 预定义配置档位
    PRESETS = {
        "shallow": 3,        # 浅层学习（快速）
        "medium": 10,       # 中层学习（平衡）
        "deep": 20,         # 深层学习（彻底）
        "training": 20,      # 训练模式（最高）
        "production": 5,     # 生产环境（安全）
    }
    
    # 各阶段深度建议
    STAGE_DEPTHS = {
        "gap_detection": 3,      # 空白检测深度
        "conflict_resolution": 5,  # 矛盾解决深度
        "knowledge_graph": 10,    # 知识图谱深度
        "recursive_fill": 20,     # 递归补全深度（最高）
    }
    
    @classmethod
    def get_depth(cls, config: str = "medium") -> int:
        """获取递归深度"""
        if isinstance(config, int):
            return min(max(1, config), 20)  # 限制在 1-20
        return cls.PRESETS.get(config, 10)
    
    @classmethod
    def get_stage_depth(cls, stage: str, override: int = None) -> int:
        """获取特定阶段深度"""
        if override:
            return min(max(1, override), 20)
        base = cls.STAGE_DEPTHS.get(stage, 5)
        return base


# ════════════════════════════════════════════════════════════════════════════
# 专家角色系统集成层
# ════════════════════════════════════════════════════════════════════════════

class ExpertRoleFinder:
    """
    专家角色查找系统
    
    功能:
    - 根据话题自动匹配最佳专家人格
    - 查询专家仓库中的角色定义
    - 支持岗位和角色筛选
    - 动态加载用户画像
    """
    
    def __init__(self, enable_expert: bool = True):
        self.enable_expert = enable_expert
        self._init_expert_components()
    
    def _init_expert_components(self):
        """初始化专家系统组件"""
        self.persona_dispatcher = None
        self.persona_library = None
        self.user_profile_parser = None
        self.expert_repository = None
        self._user_profiles: Dict[str, UserProfile] = {}
        
        if not self.enable_expert:
            return
        
        # 优先从 L04_COMPONENTS 获取
        if "persona_dispatcher" in L04_COMPONENTS:
            try:
                self.persona_library = L04_COMPONENTS["persona_library"]()
                self.persona_dispatcher = L04_COMPONENTS["persona_dispatcher"](
                    library=self.persona_library
                )
                print("[DRET-EXPERT] PersonaDispatcher 已加载")
            except Exception as e:
                print(f"[DRET-EXPERT] PersonaDispatcher 加载失败: {e}")
        
        if "user_profile_parser" in L04_COMPONENTS:
            try:
                self.user_profile_parser = L04_COMPONENTS["user_profile_parser"]()
                print("[DRET-EXPERT] UserProfileParser 已加载")
            except Exception as e:
                print(f"[DRET-EXPERT] UserProfileParser 加载失败: {e}")
        
        if "expert_repository" in L04_COMPONENTS:
            try:
                self.expert_repository = L04_COMPONENTS["expert_repository"]()
                print("[DRET-EXPERT] ExpertRepository 已加载")
            except Exception as e:
                print(f"[DRET-EXPERT] ExpertRepository 加载失败: {e}")
    
    def find_best_persona(
        self, 
        topic: str, 
        context: str = "",
        user_profile: Dict = None
    ) -> Optional[Dict]:
        """
        查找最佳匹配的人格
        
        Args:
            topic: 话题/问题
            context: 上下文
            user_profile: 用户画像
            
        Returns:
            {"persona_id", "persona_name", "match_score", "reasoning", "domain"}
        """
        if not self.persona_dispatcher:
            return self._get_default_persona()
        
        try:
            # 解析用户画像（如果提供文本）
            if user_profile is None:
                user_profile = self._parse_topic_to_profile(topic, context)
            
            # 分派人格
            persona = self.persona_dispatcher.dispatch(user_profile, topic)
            
            if persona:
                # 计算匹配度
                match_score = persona.matches_profile(user_profile)
                
                # 生成选择理由
                reasoning = self.persona_dispatcher.explain_selection(
                    user_profile, topic
                )
                
                return {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "persona_description": persona.description,
                    "match_score": round(match_score, 2),
                    "reasoning": reasoning,
                    "domain": persona.domain,
                    "traits": persona.traits,
                    "system_prompt": persona.system_prompt[:200] if persona.system_prompt else ""
                }
        except Exception as e:
            print(f"[DRET-EXPERT] 人格分派失败: {e}")
        
        return self._get_default_persona()
    
    def get_persona_for_roles(self, roles: List[str]) -> Optional[Dict]:
        """根据角色列表获取人格"""
        if not self.persona_dispatcher:
            return None
        
        try:
            persona = self.persona_dispatcher.get_persona_for_roles(roles)
            if persona:
                return {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "domain": persona.domain,
                    "description": persona.description
                }
        except Exception as e:
            print(f"[DRET-EXPERT] 角色人格查找失败: {e}")
        
        return None
    
    def get_top_personas(
        self, 
        topic: str, 
        context: str = "",
        n: int = 3
    ) -> List[Dict]:
        """获取 top N 匹配的人格"""
        if not self.persona_dispatcher:
            return [self._get_default_persona()]
        
        try:
            user_profile = self._parse_topic_to_profile(topic, context)
            top_matches = self.persona_dispatcher.dispatch_top_n(
                user_profile, topic, n
            )
            
            return [
                {
                    "persona_id": p.id,
                    "persona_name": p.name,
                    "match_score": round(score, 2),
                    "domain": p.domain,
                    "description": p.description
                }
                for p, score in top_matches
            ]
        except Exception as e:
            print(f"[DRET-EXPERT] Top-N 查找失败: {e}")
            return [self._get_default_persona()]
    
    def search_expert_by_role(
        self, 
        role_keyword: str,
        domain: str = None
    ) -> List[Dict]:
        """搜索特定角色的专家"""
        results = []
        
        if not self.persona_library:
            return results
        
        # 搜索所有激活的人格
        personas = self.persona_library.get_active()
        
        for persona in personas:
            # 匹配角色关键词
            if role_keyword.lower() in persona.id.lower():
                if domain and persona.domain != domain:
                    continue
                results.append({
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "domain": persona.domain,
                    "description": persona.description,
                    "match_type": "id"
                })
            elif role_keyword.lower() in persona.name.lower():
                if domain and persona.domain != domain:
                    continue
                results.append({
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "domain": persona.domain,
                    "description": persona.description,
                    "match_type": "name"
                })
        
        return results
    
    def get_expert_by_domain(self, domain: str) -> List[Dict]:
        """获取特定领域的专家人格"""
        if not self.persona_library:
            return []
        
        personas = self.persona_library.get_active()
        domain_personas = [
            p for p in personas 
            if p.domain == domain
        ]
        
        return [
            {
                "persona_id": p.id,
                "persona_name": p.name,
                "description": p.description,
                "traits": p.traits
            }
            for p in domain_personas
        ]
    
    def _parse_topic_to_profile(self, topic: str, context: str) -> Dict:
        """将话题解析为用户画像"""
        # 使用规则解析
        if self.user_profile_parser:
            try:
                result = self.user_profile_parser.parse_from_message(
                    topic + " " + context
                )
                return {
                    "social_roles": result.get("role_confidences", {}),
                    "core_concerns": result.get("concern_weights", {}),
                    "expertise_level": result.get("expertise_level", "medium"),
                    "decision_style": result.get("decision_style", "data_driven"),
                    "communication_preference": result.get(
                        "communication_preference", "detailed"
                    ),
                    "last_message": topic
                }
            except Exception:
                pass
        
        # 回退：基于关键词的简单画像
        topic_lower = topic.lower()
        profile = {
            "social_roles": {},
            "core_concerns": {},
            "expertise_level": "medium",
            "decision_style": "data_driven",
            "communication_preference": "detailed",
            "last_message": topic
        }
        
        # 关键词匹配
        role_keywords = {
            "enterprise_manager": ["成本", "投资", "预算", "利润", "ROI"],
            "government_official": ["法规", "合规", "审批", "政策", "监管"],
            "engineer": ["技术", "参数", "性能", "配置", "架构"],
            "researcher": ["研究", "论文", "学术", "实验"],
            "student": ["学习", "考试", "作业", "课程"],
        }
        
        for role, keywords in role_keywords.items():
            matches = sum(1 for kw in keywords if kw in topic_lower)
            if matches > 0:
                profile["social_roles"][role] = 0.3 + matches * 0.2
        
        return profile
    
    def _get_default_persona(self) -> Dict:
        """获取默认人格"""
        return {
            "persona_id": "general_expert",
            "persona_name": "通用专家",
            "match_score": 0.5,
            "reasoning": "使用默认通用人格",
            "domain": "general",
            "description": "默认的通用专家人格"
        }
    
    def list_all_personas(self) -> List[Dict]:
        """列出所有人格"""
        if not self.persona_library:
            return []
        
        personas = self.persona_library.get_all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "domain": p.domain,
                "description": p.description,
                "is_active": p.is_active,
                "is_builtin": p.is_builtin
            }
            for p in personas
        ]


# ════════════════════════════════════════════════════════════════════════════
# 专家角色系统常量
# ════════════════════════════════════════════════════════════════════════════

# 内置专家角色（与 PersonaDispatcher 保持一致）
EXPERT_ROLES = {
    "cost_focused_expert": {
        "name": "成本导向专家",
        "domain": "business",
        "roles": ["enterprise_manager", "investor"],
        "concerns": ["成本", "市场"],
        "description": "专注于成本控制和投资回报分析"
    },
    "compliance_focused_expert": {
        "name": "合规导向专家",
        "domain": "legal",
        "roles": ["government_official", "legal_professional"],
        "concerns": ["合规", "风险"],
        "description": "严谨的法规专家，强调程序正义和合规要求"
    },
    "technical_expert": {
        "name": "技术专家",
        "domain": "engineering",
        "roles": ["engineer"],
        "concerns": ["技术"],
        "description": "深入技术细节，适合工程师和技术人员"
    },
    "academic_expert": {
        "name": "学术专家",
        "domain": "academic",
        "roles": ["researcher", "student"],
        "concerns": ["质量"],
        "description": "学术论文和研究报告写作专家"
    },
    "beginner_friendly_expert": {
        "name": "入门友好专家",
        "domain": "education",
        "roles": ["resident", "student"],
        "concerns": ["风险"],
        "description": "耐心解释基础概念，适合初学者"
    },
    "environmental_expert": {
        "name": "环保专家",
        "domain": "environment",
        "roles": ["resident", "government_official"],
        "concerns": ["环保", "排放"],
        "description": "专注于环境影响评价和环境问题分析"
    },
    "data_driven_expert": {
        "name": "数据驱动专家",
        "domain": "analytics",
        "roles": ["investor", "enterprise_manager"],
        "concerns": ["市场", "数据"],
        "description": "注重数据分析和统计，适合数据驱动的决策者"
    },
    "general_expert": {
        "name": "通用专家",
        "domain": "general",
        "roles": [],
        "concerns": [],
        "description": "默认的通用专家人格"
    }
}


# ════════════════════════════════════════════════════════════════════════════
# DRET 与 L0-L4 集成层
# ════════════════════════════════════════════════════════════════════════════

class L04IntegratedGapDetector:
    """
    L0-L4 集成的知识空白检测器

    复用：
    - L0: 空白查询缓存
    - L1: 精确缓存（快速判断）
    - L3: KnowledgeBase（补全搜索）
    - L4: LLM（深度分析）
    """

    def __init__(
        self, 
        llm_client=None, 
        enable_l04: bool = True,
        max_depth: int = 20
    ):
        self.llm = llm_client
        self.enable_l04 = enable_l04
        self.max_depth = min(max(1, max_depth), 20)  # 限制在 1-20

        # 尝试获取 L0-L4 组件
        self._init_l04_components()

        # 本地空白模式（备用）
        self._gap_patterns = [
            (r"使用\s*(\w+)\s*进行", "definition", "未说明 '{0}' 是什么"),
            (r"通过\s*(\w+)\s*实现", "definition", "未解释 '{0}' 的原理"),
            (r"调用\s*(\w+)\s*函数", "definition", "未说明 '{0}' 函数的作用"),
            (r"基于\s*(\w+)\s*技术", "definition", "未介绍 '{0}' 技术背景"),
            (r"首先|第一步", "procedure", "可能存在步骤缺失"),
            (r"首先.*然后", "procedure", "步骤链不完整"),
            (r"比\s*(\w+)\s*[更]*好", "comparison", "未说明与 '{0}' 的对比基准"),
            (r"因此|所以|导致|由于", "causation", "因果关系需要更明确的解释"),
            (r"例如|比如|像.*这样", "example", "缺乏具体示例"),
            (r"参见|参考|详见", "reference", "引用来源未明确标注"),
        ]
        
        # 已访问节点（防止循环）
        self._visited_gaps: Set[str] = set()

    def _init_l04_components(self):
        """初始化 L0-L4 组件"""
        self.intent_classifier = None
        self.knowledge_base = None
        self.l4_executor = None
        self.unified_cache = None

        if not self.enable_l04:
            return

        # L3: 知识库
        if "knowledge_base" in L04_COMPONENTS:
            try:
                self.knowledge_base = L04_COMPONENTS["knowledge_base"]()
                print("[DRET-L0L4] KnowledgeBaseLayer 已加载")
            except Exception as e:
                print(f"[DRET-L0L4] KB 加载失败: {e}")

        # L4: LLM 执行器
        if "get_cache" in L04_COMPONENTS:
            try:
                self.unified_cache = L04_COMPONENTS["get_cache"]()
                print("[DRET-L0L4] UnifiedCache 已加载")
            except Exception as e:
                print(f"[DRET-L0L4] Cache 加载失败: {e}")

        # 意图分类器
        if "intent_classifier" in L04_COMPONENTS:
            try:
                self.intent_classifier = L04_COMPONENTS["intent_classifier"]()
                print("[DRET-L0L4] IntentClassifier 已加载")
            except Exception as e:
                print(f"[DRET-L0L4] IntentClassifier 加载失败: {e}")

    def detect_gaps(
        self,
        content: str,
        doc_id: str = "",
        max_gaps: int = 20,
        session_id: str = "dret_gap_detection",
        recursion_level: int = 0
    ) -> List[Dict]:
        """
        检测知识空白（集成 L0-L4，支持递归深度配置）

        Args:
            content: 待检测内容
            doc_id: 文档ID
            max_gaps: 最大空白数
            session_id: 会话ID
            recursion_level: 当前递归深度（用于限制最大深度）
            
        Returns:
            [{"gap_id", "type", "description", "filled", "fill_content", "source", "recursion_level"}]
        """
        gaps = []
        gap_id = 0
        seen = set()
        
        # ════════════════════════════════════════════════════════════════════════════
        # 递归深度控制（最高 20 层）
        # ════════════════════════════════════════════════════════════════════════════
        effective_depth = min(recursion_level, self.max_depth)
        if recursion_level >= self.max_depth:
            print(f"[DRET-L0L4] 达到最大递归深度 {self.max_depth}，停止深层检测")
            return gaps

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 1: L0 缓存检查（快速路径）
        # ─────────────────────────────────────────────────────────────────────────────
        content_hash = hashlib.md5(content.encode()).hexdigest()

        if self.unified_cache:
            cached = self.unified_cache.get_l0_route(content_hash)
            if cached:
                print(f"[DRET-L0L4] L0 缓存命中，跳过空白检测")
                return cached.data

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 2: 模式匹配检测（本地）
        # ─────────────────────────────────────────────────────────────────────────────
        for pattern, gap_type, template in self._gap_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(gaps) >= max_gaps:
                    break

                entities = [g for g in match.groups() if g] if match.groups() else []
                desc = template.format(*entities) if entities else template

                if desc in seen:
                    continue
                seen.add(desc)

                gap = {
                    "gap_id": f"gap_{gap_id:04d}_L{recursion_level}",
                    "type": gap_type,
                    "description": desc,
                    "related_entities": entities,
                    "recursion_level": recursion_level,
                    "max_recursion_level": self.max_depth,
                    "filled": False,
                    "fill_content": "",
                    "source": "pattern_match"
                }
                gaps.append(gap)
                gap_id += 1

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 3: L3 意图辅助分类
        # ─────────────────────────────────────────────────────────────────────────────
        if self.intent_classifier:
            intent_result = self.intent_classifier.classify(content)
            print(f"[DRET-L0L4] 意图分类: {intent_result['primary']} (置信度: {intent_result['confidence']:.2f})")

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 4: L3 知识库补全搜索
        # ─────────────────────────────────────────────────────────────────────────────
        filled_gaps = []
        for gap in gaps:
            fill_result = self._fill_gap_via_l3(gap, session_id)
            filled_gaps.append(fill_result)

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 5: L4 LLM 深度分析（如果还有未填充的）
        # ─────────────────────────────────────────────────────────────────────────────
        unfilled = [g for g in filled_gaps if not g["filled"]]
        if unfilled and self.llm:
            print(f"[DRET-L0L4] {len(unfilled)} 个空白需要 LLM 深度分析")
            for gap in unfilled:
                llm_result = self._fill_gap_via_l4(gap)
                if llm_result:
                    idx = next(i for i, g in enumerate(filled_gaps) if g["gap_id"] == gap["gap_id"])
                    filled_gaps[idx] = llm_result

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 6: 缓存结果（L0）
        # ─────────────────────────────────────────────────────────────────────────────
        if self.unified_cache and gaps:
            self.unified_cache.set_l0_route(content_hash, filled_gaps)

        return filled_gaps

    def _fill_gap_via_l3(self, gap: Dict, session_id: str) -> Dict:
        """通过 L3 知识库填充空白"""
        if not self.knowledge_base:
            return gap

        try:
            results = self.knowledge_base.search(
                gap["description"],
                top_k=3,
                doc_type=gap["type"]
            )

            if results:
                best = results[0]
                gap["filled"] = True
                gap["fill_content"] = best.get("content", "")[:500]
                gap["fill_source"] = f"KB:{best.get('doc_id', 'unknown')}"
                gap["fill_score"] = best.get("score", 0)
                return gap
        except Exception as e:
            print(f"[DRET-L0L4] KB 搜索失败: {e}")

        return gap

    def _fill_gap_via_l4(self, gap: Dict) -> Optional[Dict]:
        """通过 L4 LLM 填充空白"""
        if not self.llm:
            return None

        try:
            # 使用 LLM 生成补全内容
            prompt = f"""分析以下知识空白并提供补全：

空白类型: {gap['type']}
空白描述: {gap['description']}
相关实体: {', '.join(gap.get('related_entities', []))}
递归深度: {gap.get('recursion_level', 0)}/{self.max_depth}

请提供：
1. 详细的解释或定义
2. 相关背景知识
3. 实际应用示例

答案（简洁清晰）："""

            # 如果有 L4 执行器
            if "get_cache" in L04_COMPONENTS:
                async def _call_llm():
                    executor = L04_COMPONENTS["get_l4_executor"]()
                    result = await executor.execute([{"role": "user", "content": prompt}])
                    return result

                result = asyncio.run(_call_llm())
                if result and "choices" in result:
                    content = result["choices"][0]["message"]["content"]
                    gap["filled"] = True
                    gap["fill_content"] = content[:500]
                    gap["fill_source"] = "L4:LLM"
                    return gap
        except Exception as e:
            print(f"[DRET-L0L4] L4 LLM 调用失败: {e}")

        return None


class L04IntegratedConflictFinder:
    """
    L0-L4 集成的矛盾发现器

    复用：
    - L3: KnowledgeBase（外部矛盾检测）
    - L2: SessionCache（会话内矛盾）
    - L4: LLM（深度矛盾分析）
    """

    def __init__(
        self, 
        llm_client=None, 
        enable_l04: bool = True,
        max_depth: int = 20
    ):

        self.llm = llm_client
        self.enable_l04 = enable_l04
        self.max_depth = min(max(1, max_depth), 20)  # 限制在 1-20

        self._init_l04_components()

        # 量化词矛盾对
        self._contradiction_pairs = [
            ("必须", "可以"),
            ("总是", "有时"),
            ("所有", "某些"),
            ("从不", "经常"),
            ("完全", "部分"),
            ("唯一", "多种"),
            ("绝对", "相对"),
            ("无条件", "有条件"),
        ]

    def _init_l04_components(self):
        """初始化 L0-L4 组件"""
        self.knowledge_base = None
        self.session_cache = None

        if "knowledge_base" in L04_COMPONENTS:
            try:
                self.knowledge_base = L04_COMPONENTS["knowledge_base"]()
                print("[DRET-L0L4] ConflictFinder: KnowledgeBase 已加载")
            except:
                pass

        if "session_cache" in L04_COMPONENTS:
            try:
                self.session_cache = L04_COMPONENTS["session_cache"]()
                print("[DRET-L0L4] ConflictFinder: SessionCache 已加载")
            except:
                pass

    def find_conflicts(
        self,
        content: str,
        doc_id: str = "",
        session_id: str = "dret_conflict"
    ) -> List[Dict]:
        """
        发现矛盾（集成 L0-L4）

        Returns:
            [{"conflict_id", "level", "statement_a", "statement_b",
              "evidence_a", "evidence_b", "resolved", "resolution"}]
        """
        conflicts = []

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 1: 内部矛盾检测（量化词对立）
        # ─────────────────────────────────────────────────────────────────────────────
        internal_conflicts = self._find_internal_conflicts(content)
        conflicts.extend(internal_conflicts)

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 2: L3 外部矛盾检测（与知识库对比）
        # ─────────────────────────────────────────────────────────────────────────────
        if self.knowledge_base:
            external_conflicts = self._find_external_conflicts(content, doc_id)
            conflicts.extend(external_conflicts)

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 3: L2 会话矛盾检测（避免自我矛盾）
        # ─────────────────────────────────────────────────────────────────────────────
        if self.session_cache:
            session_conflicts = self._find_session_conflicts(session_id, content)
            conflicts.extend(session_conflicts)

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 4: L4 深度矛盾分析
        # ─────────────────────────────────────────────────────────────────────────────
        if conflicts and self.llm:
            conflicts = self._analyze_conflicts_deeply(conflicts)

        return conflicts

    def _find_internal_conflicts(self, content: str) -> List[Dict]:
        """内部矛盾检测（量化词对立）"""
        conflicts = []

        # 只检查前 500 字符
        check_content = content[:500]

        for word_a, word_b in self._contradiction_pairs:
            matches_a = re.findall(rf".{{0,30}}{word_a}.{{0,30}}", check_content)
            matches_b = re.findall(rf".{{0,30}}{word_b}.{{0,30}}", check_content)

            if matches_a and matches_b:
                conflicts.append({
                    "conflict_id": f"conflict_{len(conflicts):04d}",
                    "level": "warning",
                    "type": "quantifier_contradiction",
                    "statement_a": f"声明包含: {word_a}",
                    "statement_b": f"声明包含: {word_b}",
                    "evidence_a": matches_a[:2],
                    "evidence_b": matches_b[:2],
                    "resolved": False,
                    "resolution": "",
                    "source": "internal_quantifier"
                })

        return conflicts

    def _find_external_conflicts(self, content: str, doc_id: str) -> List[Dict]:
        """外部矛盾检测（与知识库对比）"""
        conflicts = []

        if not self.knowledge_base:
            return conflicts

        # 提取关键断言
        assertions = re.findall(r"([^。！？]+[是否一定必须所有从不]+[^。！？]+[。！？])", content)

        for assertion in assertions[:5]:  # 只检查前5个
            try:
                results = self.knowledge_base.search(assertion, top_k=3)

                # 检查是否有矛盾结果
                for result in results:
                    kb_content = result.get("content", "")
                    # 简单检测：关键词对立
                    for word_a, word_b in self._contradiction_pairs[:3]:
                        if word_a in assertion and word_b in kb_content:
                            conflicts.append({
                                "conflict_id": f"conflict_{len(conflicts):04d}",
                                "level": "fatal",
                                "type": "external_kb_contradiction",
                                "statement_a": assertion[:100],
                                "statement_b": kb_content[:100],
                                "evidence_a": [assertion[:200]],
                                "evidence_b": [kb_content[:200]],
                                "resolved": False,
                                "resolution": "",
                                "source": f"KB:{result.get('doc_id', 'unknown')}"
                            })
                            break
            except Exception as e:
                print(f"[DRET-L0L4] KB 对比失败: {e}")

        return conflicts

    def _find_session_conflicts(self, session_id: str, content: str) -> List[Dict]:
        """会话矛盾检测"""
        conflicts = []

        if not self.session_cache:
            return conflicts

        try:
            # 获取会话历史
            history = self.session_cache.get(content, session_id, top_k=3)

            for item in history:
                prev_content = item["item"]["response"]
                # 检测与历史内容的矛盾
                # （简化实现）
        except Exception as e:
            print(f"[DRET-L0L4] 会话矛盾检测失败: {e}")

        return conflicts

    def _analyze_conflicts_deeply(self, conflicts: List[Dict]) -> List[Dict]:
        """L4 深度矛盾分析"""
        # 如果有 L4 执行器，使用 LLM 分析
        if "get_l4_executor" in L04_COMPONENTS:
            try:
                async def _analyze():
                    executor = L04_COMPONENTS["get_l4_executor"]()
                    prompt = f"""分析以下矛盾并提供解决方案：

矛盾1: {conflicts[0]['statement_a']} vs {conflicts[0]['statement_b']}
证据A: {conflicts[0]['evidence_a']}
证据B: {conflicts[0]['evidence_b']}

请分析：
1. 矛盾的真实原因
2. 可能的解释
3. 建议的解决方案

分析："""

                    result = await executor.execute([{"role": "user", "content": prompt}])
                    return result

                analysis = asyncio.run(_analyze())
                if analysis and "choices" in analysis:
                    resolution = analysis["choices"][0]["message"]["content"]
                    if conflicts:
                        conflicts[0]["resolution"] = resolution
                        conflicts[0]["resolved"] = True
            except Exception as e:
                print(f"[DRET-L0L4] L4 矛盾分析失败: {e}")

        return conflicts


class L04IntegratedDebater:
    """
    L0-L4 集成的多专家辩论引擎
    
    新增：集成专家角色查找系统
    """

    # 辩论角色定义
    ROLES = {
        "optimist": {
            "name": "乐观派",
            "prompt": "你是一个乐观的技术倡导者，总是看到新技术的优势和潜力。分析问题时强调积极面和机会。"
        },
        "skeptic": {
            "name": "质疑派",
            "prompt": "你是一个严谨的技术质疑者，善于发现风险、局限和潜在问题。分析问题时强调风险和挑战。"
        },
        "synthesizer": {
            "name": "综合派",
            "prompt": "你是一个中立的技术分析师，擅长权衡利弊、形成客观结论。分析问题时全面考虑正反两面。"
        },
        "historian": {
            "name": "历史派",
            "prompt": "你是一个技术历史学家，擅长引用历史案例进行对比分析。分析问题时结合历史经验。"
        }
    }

    def __init__(
        self, 
        llm_client=None, 
        enable_l04: bool = True,
        expert_role_finder: ExpertRoleFinder = None
    ):
        self.llm = llm_client
        self.enable_l04 = enable_l04
        self.expert_role_finder = expert_role_finder
        self.max_rounds = 3

        self._init_l04_components()

    def _init_l04_components(self):
        """初始化 L0-L4 组件"""
        self.knowledge_base = None
        self.session_cache = None
        self.l4_executor = None

        if "get_l4_executor" in L04_COMPONENTS:
            try:
                self.l4_executor = L04_COMPONENTS["get_l4_executor"]()
                print("[DRET-L0L4] Debater: L4Executor 已加载")
            except:
                pass

        if "knowledge_base" in L04_COMPONENTS:
            try:
                self.knowledge_base = L04_COMPONENTS["knowledge_base"]()
            except:
                pass

        if "session_cache" in L04_COMPONENTS:
            try:
                self.session_cache = L04_COMPONENTS["session_cache"]()
            except:
                pass

    async def debate_async(
        self,
        topic: str,
        context: str = "",
        roles: List[str] = None,
        use_expert_personas: bool = True
    ) -> Dict:
        """
        异步执行多专家辩论
        
        Args:
            topic: 辩题
            context: 上下文
            roles: 角色列表
            use_expert_personas: 是否使用专家人格系统
        """

        # ════════════════════════════════════════════════════════════════════════════
        # 新增：使用专家角色系统
        # ════════════════════════════════════════════════════════════════════════════
        expert_persona = None
        if use_expert_personas and self.expert_role_finder:
            expert_persona = self.expert_role_finder.find_best_persona(
                topic, context
            )
            if expert_persona:
                print(f"[DRET-DEBATE] 使用专家人格: {expert_persona['persona_name']}")

        if roles is None:
            roles = list(self.ROLES.keys())

        perspectives = {}

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 1: L3 论据检索
        # ─────────────────────────────────────────────────────────────────────────────
        evidence = []
        if self.knowledge_base:
            try:
                results = self.knowledge_base.search(topic, top_k=5)
                evidence = [r.get("content", "")[:200] for r in results]
            except:
                pass

        evidence_context = "\n".join([f"- {e}" for e in evidence[:3]])
        
        # 添加专家人格上下文
        expert_context = ""
        if expert_persona:
            expert_context = f"\n专家角色: {expert_persona['persona_name']}\n"
            expert_context += f"角色描述: {expert_persona.get('persona_description', '')}\n"
        
        full_context = f"{context}{expert_context}\n\n相关证据：\n{evidence_context}" if evidence_context else context + expert_context

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 2: L4 多角色辩论
        # ─────────────────────────────────────────────────────────────────────────────
        if self.l4_executor:
            for role_key in roles:
                role_info = self.ROLES.get(role_key, {})
                role_name = role_info.get("name", role_key)
                role_prompt = role_info.get("prompt", "")

                # 如果有专家人格，结合人格系统提示
                if expert_persona and "system_prompt" in expert_persona:
                    role_prompt = f"{role_prompt}\n\n参考专家观点：{expert_persona['system_prompt']}"

                prompt = f"""{role_prompt}

主题：{topic}

背景信息：
{full_context}

请从{role_name}的角度，分析这个主题，给出你的观点和论据。

回答格式：
[{role_name}]
观点：...
论据：...
"""

                try:
                    result = await self.l4_executor.execute(
                        [{"role": "user", "content": prompt}],
                        intent="debate"
                    )
                    if result and "choices" in result:
                        perspectives[role_key] = result["choices"][0]["message"]["content"]
                except Exception as e:
                    print(f"[DRET-L0L4] 角色 {role_key} 辩论失败: {e}")
                    perspectives[role_key] = f"[{role_name}] 辩论生成失败"

        else:
            # 降级：模板生成
            for role_key in roles:
                role_name = self.ROLES.get(role_key, {}).get("name", role_key)
                perspectives[role_key] = self._template_perspective(topic, role_key, context)

        # ─────────────────────────────────────────────────────────────────────────────
        # Step 3: 综合形成共识
        # ─────────────────────────────────────────────────────────────────────────────
        consensus = await self._synthesize_async(topic, perspectives, full_context)

        return {
            "topic": topic,
            "perspectives": perspectives,
            "consensus": consensus,
            "confidence": 0.8,
            "key_points": self._extract_key_points(consensus),
            "roles_used": roles,
            "expert_persona": expert_persona
        }

    def debate(
        self,
        topic: str,
        context: str = "",
        roles: List[str] = None,
        use_expert_personas: bool = True
    ) -> Dict:
        """同步辩论入口"""
        return asyncio.run(self.debate_async(topic, context, roles, use_expert_personas))

    def _template_perspective(self, topic: str, role: str, context: str) -> str:
        """模板化观点（无 LLM 时降级使用）"""
        templates = {
            "optimist": f"[乐观派] {topic} 具有显著优势：自动化程度高、效率提升明显、多 Agent 协同增强了能力边界。",
            "skeptic": f"[质疑派] {topic} 存在风险：依赖特定环境、错误传播可能、调试困难、学习曲线陡峭。",
            "synthesizer": f"[综合派] {topic} 需要权衡：优势在于效率，劣势在于复杂度和可控性。建议选择性使用。",
            "historian": f"[历史派] 对比历史 AI 工具演进：自动化工具从单步执行到多步协作是必然趋势，但需要保持人类监督。"
        }
        return templates.get(role, f"[{role}] 关于 {topic} 的观点")

    async def _synthesize_async(self, topic: str, perspectives: Dict, context: str) -> str:
        """异步综合观点"""
        if self.l4_executor:
            prompt = f"""综合以下多方观点，形成一个客观平衡的结论：

话题：{topic}

乐观派观点：
{perspectives.get('optimist', '')}

质疑派观点：
{perspectives.get('skeptic', '')}

综合派观点：
{perspectives.get('synthesizer', '')}

历史派观点：
{perspectives.get('historian', '')}

请综合各方观点，给出一个平衡客观的结论，突出关键要点。结论："""

            try:
                result = await self.l4_executor.execute([{"role": "user", "content": prompt}])
                if result and "choices" in result:
                    return result["choices"][0]["message"]["content"]
            except:
                pass

        return f"综合分析：{topic} 需要权衡多方因素后做出判断。"

    def _extract_key_points(self, consensus: str) -> List[str]:
        """提取关键论点"""
        # 简单实现：按句号分割
        sentences = consensus.replace("\n", "。").split("。")
        key_points = [s.strip() for s in sentences if len(s.strip()) > 10][:5]
        return key_points if key_points else [consensus[:200]]


class L04IntegratedRecursiveLearner:
    """
    L0-L4 集成的递归学习控制器
    
    新增功能:
    - 可配置递归深度 (最高 20 层)
    - 集成专家角色查找系统
    """

    def __init__(
        self,
        max_depth: int = 20,  # 默认最高 20 层
        llm_client=None,
        enable_l04: bool = True,
        enable_expert: bool = True
    ):
        # ════════════════════════════════════════════════════════════════════════════
        # 递归深度验证（最高 20 层）
        # ════════════════════════════════════════════════════════════════════════════
        self.max_depth = min(max(1, max_depth), 20)
        print(f"[DRET-L0L4] 递归深度配置: {self.max_depth} 层")

        self.llm = llm_client
        self.enable_l04 = enable_l04

        # ════════════════════════════════════════════════════════════════════════════
        # 初始化专家角色查找系统
        # ════════════════════════════════════════════════════════════════════════════
        self.expert_role_finder = ExpertRoleFinder(enable_expert) if enable_expert else None

        # 集成组件
        self.gap_detector = L04IntegratedGapDetector(
            llm_client, 
            enable_l04,
            max_depth=self.max_depth
        )
        self.conflict_finder = L04IntegratedConflictFinder(
            llm_client, 
            enable_l04,
            max_depth=self.max_depth
        )
        self.debater = L04IntegratedDebater(
            llm_client, 
            enable_l04,
            expert_role_finder=self.expert_role_finder
        )

        # 初始化 L0-L4 组件
        self._init_l04_components()

        # 统计
        self.stats = {
            "total_gaps": 0,
            "filled_gaps": 0,
            "total_conflicts": 0,
            "resolved_conflicts": 0,
            "debate_rounds": 0,
            "l0_cache_hits": 0,
            "l3_kb_hits": 0,
            "l4_llm_calls": 0,
            "max_recursion_depth": self.max_depth,
            "expert_persona_used": None
        }
        
        # 递归跟踪
        self._current_recursion_level = 0
        self._visited_content_hashes: Set[str] = set()

    def _init_l04_components(self):
        """初始化 L0-L4 组件"""
        if "get_cache" in L04_COMPONENTS:
            try:
                self.unified_cache = L04_COMPONENTS["get_cache"]()
                print("[DRET-L0L4] UnifiedCache 已加载")
            except:
                self.unified_cache = None

        if "fusion_engine" in L04_COMPONENTS:
            try:
                from business.fusion_rag.l4_executor import get_l4_executor
                self.fusion_engine = L04_COMPONENTS["fusion_engine"](
                    l4_executor=get_l4_executor()
                )
                print("[DRET-L0L4] FusionEngine 已加载")
            except:
                self.fusion_engine = None

        if "router" in L04_COMPONENTS:
            try:
                self.router = L04_COMPONENTS["router"]()
                print("[DRET-L0L4] IntelligentRouter 已加载")
            except:
                self.router = None

    def set_recursion_depth(self, depth: int):
        """动态设置递归深度（1-20）"""
        old_depth = self.max_depth
        self.max_depth = min(max(1, depth), 20)
        
        # 更新子组件
        self.gap_detector.max_depth = self.max_depth
        self.conflict_finder.max_depth = self.max_depth
        
        print(f"[DRET-L0L4] 递归深度变更: {old_depth} -> {self.max_depth}")
        self.stats["max_recursion_depth"] = self.max_depth

    def learn_from_document(
        self,
        doc_content: str,
        doc_id: str = "doc_001",
        session_id: str = "dret_learning",
        recursion_depth: int = None
    ) -> Dict:
        """
        从文档递归学习（集成 L0-L4）
        
        Args:
            doc_content: 文档内容
            doc_id: 文档ID
            session_id: 会话ID
            recursion_depth: 覆盖递归深度（可选）

        Returns:
            LearningReport
        """
        start_time = time.time()
        
        # 覆盖递归深度
        if recursion_depth is not None:
            self.set_recursion_depth(recursion_depth)
        
        # 重置递归跟踪
        self._current_recursion_level = 0
        self._visited_content_hashes.clear()

        # ════════════════════════════════════════════════════════════════════════════
        # Phase 1: 空白检测（复用 L0-L3）
        # ════════════════════════════════════════════════════════════════════════════
        print(f"[DRET-L0L4] Phase 1: 知识空白检测 (深度={self.max_depth})")
        gaps = self.gap_detector.detect_gaps(
            doc_content, 
            doc_id,
            recursion_level=0
        )
        self.stats["total_gaps"] = len(gaps)

        # ════════════════════════════════════════════════════════════════════════════
        # Phase 2: 矛盾发现（复用 L3）
        # ════════════════════════════════════════════════════════════════════════════
        print("[DRET-L0L4] Phase 2: 矛盾发现")
        conflicts = self.conflict_finder.find_conflicts(doc_content, doc_id, session_id)
        self.stats["total_conflicts"] = len(conflicts)

        # ════════════════════════════════════════════════════════════════════════════
        # Phase 3: 递归补课（复用 L3 KB + L4 LLM，可配置深度）
        # ════════════════════════════════════════════════════════════════════════════
        print(f"[DRET-L0L4] Phase 3: 递归补课 (深度={self.max_depth})")
        filled_count = self._recursive_fill(gaps, depth=0)
        self.stats["filled_gaps"] = filled_count

        # ════════════════════════════════════════════════════════════════════════════
        # Phase 4: 矛盾辩论解决（复用 L4 LLM + 专家角色系统）
        # ════════════════════════════════════════════════════════════════════════════
        print("[DRET-L0L4] Phase 4: 矛盾辩论解决")
        resolved_count = self._resolve_conflicts(conflicts)

        # ════════════════════════════════════════════════════════════════════════════
        # Phase 5: 知识图谱构建（复用 L3 + L4）
        # ════════════════════════════════════════════════════════════════════════════
        print("[DRET-L0L4] Phase 5: 知识图谱构建")
        kg_stats = self._build_knowledge_graph(doc_content, gaps)

        total_time = time.time() - start_time

        return {
            "doc_id": doc_id,
            "gaps_found": len(gaps),
            "gaps_filled": filled_count,
            "conflicts_found": len(conflicts),
            "conflicts_resolved": resolved_count,
            "debate_rounds": self.stats["debate_rounds"],
            "knowledge_graph": kg_stats,
            "total_time": total_time,
            "max_depth_used": self.max_depth,
            "expert_persona": self.stats["expert_persona_used"],
            "stats": self.stats.copy()
        }

    def _recursive_fill(self, gaps: List[Dict], depth: int = 0) -> int:
        """
        递归补课（可配置深度，最高 20 层）
        
        Args:
            gaps: 空白列表
            depth: 当前递归深度
            
        Returns:
            填充的空白数量
        """
        # ════════════════════════════════════════════════════════════════════════════
        # 深度控制（最高 20 层）
        # ════════════════════════════════════════════════════════════════════════════
        if depth >= self.max_depth:
            print(f"[DRET-L0L4] 达到最大递归深度 {self.max_depth}，停止递归")
            return 0
        
        self._current_recursion_level = depth

        filled = 0
        for gap in gaps:
            if gap.get("filled"):
                filled += 1
                
                # ════════════════════════════════════════════════════════════════════
                # 递归检查补全内容（深度限制 20 层）
                # ════════════════════════════════════════════════════════════════════
                if depth < self.max_depth and gap.get("fill_content"):
                    # 检查是否已访问（防止循环）
                    content_hash = hashlib.md5(
                        gap["fill_content"].encode()
                    ).hexdigest()
                    
                    if content_hash not in self._visited_content_hashes:
                        self._visited_content_hashes.add(content_hash)
                        
                        sub_gaps = self.gap_detector.detect_gaps(
                            gap["fill_content"],
                            max_gaps=3,
                            recursion_level=depth + 1
                        )
                        filled += self._recursive_fill(sub_gaps, depth + 1)
                    else:
                        print(f"[DRET-L0L4] 跳过已访问内容（深度 {depth}）")

        return filled

    def _resolve_conflicts(self, conflicts: List[Dict]) -> int:
        """通过辩论解决矛盾"""
        resolved = 0

        for conflict in conflicts:
            # 调用辩论引擎（使用专家角色系统）
            debate_result = self.debater.debate(
                topic=f"{conflict['statement_a']} vs {conflict['statement_b']}",
                context=f"证据A: {conflict['evidence_a']}\n证据B: {conflict['evidence_b']}",
                use_expert_personas=True
            )

            if debate_result.get("consensus"):
                conflict["resolved"] = True
                conflict["resolution"] = debate_result["consensus"]
                resolved += 1
                self.stats["debate_rounds"] += 1
                
                # 记录使用的专家人格
                if debate_result.get("expert_persona"):
                    self.stats["expert_persona_used"] = debate_result["expert_persona"]["persona_name"]

        return resolved

    def _build_knowledge_graph(self, content: str, gaps: List[Dict]) -> Dict:
        """构建知识图谱"""
        # 统计节点和边
        nodes = len(gaps) + 1  # 文档根节点 + 各空白
        edges = len(gaps)

        # 如果有知识库，存储图谱
        if self.gap_detector.knowledge_base:
            doc = {
                "id": "kg_root",
                "title": "DRET Knowledge Graph",
                "content": content,
                "type": "knowledge_graph"
            }
            self.gap_detector.knowledge_base.add_document(doc)

        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def get_expert_info(self) -> Dict:
        """获取专家角色系统信息"""
        if not self.expert_role_finder:
            return {"available": False}
        
        return {
            "available": True,
            "all_personas": self.expert_role_finder.list_all_personas(),
            "roles": EXPERT_ROLES
        }


# ════════════════════════════════════════════════════════════════════════════
# 工厂函数
# ════════════════════════════════════════════════════════════════════════════

def create_l04_dret_system(
    max_recursion_depth: int = 20,  # 默认最高 20 层
    llm_client=None,
    enable_l04: bool = True,
    enable_expert: bool = True
) -> L04IntegratedRecursiveLearner:
    """
    创建 L0-L4 集成的 DRET 系统
    
    Args:
        max_recursion_depth: 递归深度（最高 20 层）
        llm_client: LLM 客户端
        enable_l04: 启用 L0-L4 集成
        enable_expert: 启用专家角色系统
        
    Returns:
        L04IntegratedRecursiveLearner 实例
    """
    return L04IntegratedRecursiveLearner(
        max_depth=min(max(1, max_recursion_depth), 20),
        llm_client=llm_client,
        enable_l04=enable_l04,
        enable_expert=enable_expert
    )


# ════════════════════════════════════════════════════════════════════════════
# 使用示例
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 示例文档
    sample_doc = """
    OpenCode 是一个 AI 代码助手，支持以下功能：

    1. 安装: npm install -g opencode-ai
    2. 配置 oh-my-opencode: bunx oh-my-opencode install
    3. 使用 ultrawork 模式可以全自动完成任务

    特点：
    - 支持多 Agent 协同
    - 支持 Tab 切换 (plan/build)
    - 支持 /init 生成 AGENTS.md

    注意：需要先安装 Node.js 环境
    """

    print("=" * 60)
    print("DRET 系统（L0-L4 + 专家角色集成版）演示")
    print("=" * 60)

    # ════════════════════════════════════════════════════════════════════════════
    # 配置演示：使用最高 20 层递归深度
    # ════════════════════════════════════════════════════════════════════════════
    print("\n[配置] 递归深度: 20 层 (训练模式)")
    print("[配置] 专家角色系统: 启用")
    
    # 创建系统（支持最高 20 层递归）
    dret = create_l04_dret_system(
        max_recursion_depth=20,  # 训练模式最高 20 层
        enable_expert=True
    )

    # 执行学习
    report = dret.learn_from_document(sample_doc, doc_id="opencode_guide")

    # 输出报告
    print("\n" + "=" * 60)
    print("学习报告")
    print("=" * 60)
    print(f"文档ID: {report['doc_id']}")
    print(f"最大递归深度: {report['max_depth_used']} 层")
    print(f"空白发现: {report['gaps_found']}")
    print(f"空白填充: {report['gaps_filled']}")
    print(f"矛盾发现: {report['conflicts_found']}")
    print(f"矛盾解决: {report['conflicts_resolved']}")
    print(f"辩论轮次: {report['debate_rounds']}")
    print(f"知识图谱: {report['knowledge_graph']['nodes']} 节点, {report['knowledge_graph']['edges']} 边")
    print(f"总耗时: {report['total_time']:.2f}s")
    
    # 专家人格信息
    if report.get("expert_persona"):
        print(f"使用专家人格: {report['expert_persona']}")
    
    print("=" * 60)

    # 显示统计
    print("\n组件使用统计:")
    for k, v in report["stats"].items():
        print(f"  {k}: {v}")
    
    # ════════════════════════════════════════════════════════════════════════════
    # 专家角色查找演示
    # ════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("专家角色查找演示")
    print("=" * 60)
    
    expert_info = dret.get_expert_info()
    if expert_info.get("available"):
        print(f"\n可用人格数量: {len(expert_info['all_personas'])}")
        
        # 查找最佳人格
        best = dret.expert_role_finder.find_best_persona(
            "成本控制和投资回报分析",
            context="企业管理者关注 ROI"
        )
        print(f"\n最佳匹配人格: {best['persona_name']}")
        print(f"匹配度: {best['match_score']}")
        print(f"领域: {best['domain']}")
        print(f"描述: {best['persona_description']}")
        
        # 搜索特定角色
        print("\n搜索 '技术' 相关人格:")
        tech_experts = dret.expert_role_finder.search_expert_by_role("技术")
        for exp in tech_experts:
            print(f"  - {exp['persona_name']} ({exp['domain']})")
        
        # 获取领域专家
        print("\n环境领域专家:")
        env_experts = dret.expert_role_finder.get_expert_by_domain("environment")
        for exp in env_experts:
            print(f"  - {exp['persona_name']}: {exp['description']}")
    
    print("=" * 60)
