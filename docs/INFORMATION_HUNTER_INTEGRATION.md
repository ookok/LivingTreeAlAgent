# 信息需求智能体 - LivingTreeAI 整合分析

## 一、核心理念

```
从 "被动响应查询" → "主动发现知识缺口"

信息需求智能体 = 知识缺口探测器 + 来源策略师 + 信息验证器
```

### 与之前设计的协同关系

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LivingTreeAI 智能系统矩阵                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Architect Agent (架构智能体)                                   │    │
│  │  功能: 探索外部架构知识，生成演进路线图                           │    │
│  │  依赖: 信息需求智能体提供"去哪找"的能力                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Industry Expert Factory (行业专家工厂)                          │    │
│  │  功能: 训练多领域专家智能体                                     │    │
│  │  依赖: 信息需求智能体提供"最新知识获取"能力                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Information Hunter (信息需求智能体) 🆕                         │    │
│  │  功能: 识别知识缺口 → 选择最优来源 → 验证信息质量                 │    │
│  │  基础: IntentEngine + Search + FusionRAG                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、LivingTreeAI 现有搜索与分析模块

### 2.1 模块清单

```
核心搜索模块
├── core/intent_engine/          意图引擎 ⭐核心入口
│   ├── intent_engine.py          意图解析主控制器
│   ├── intent_parser.py          意图解析器
│   ├── tech_stack_detector.py    技术栈检测
│   └── constraint_extractor.py  约束提取
│
├── core/search/                 分层搜索系统
│   ├── tiered_adapter.py        分层搜索适配器
│   ├── models.py                 数据模型
│   ├── search_scheduler.py       搜索调度器
│   └── tier_router.py            层级路由
│
├── core/intelligence_center/    情报中心
│   └── multi_search.py           多源搜索聚合引擎 ⭐
│
├── core/fusion_rag/             融合RAG
│   ├── fusion_engine.py          多源融合引擎
│   ├── knowledge_base.py         知识库
│   └── intelligent_router.py     智能路由
│
├── core/knowledge_graph/        知识图谱
│   ├── knowledge_graph_manager.py 知识图谱管理器
│   └── external_data/            外部数据源集成
│
└── core/smart_proxy_gateway/    智能代理网关
    └── unified_proxy_config.py   统一代理配置
```

### 2.2 现有能力分析

| 模块 | 现有能力 | 可扩展方向 |
|------|---------|-----------|
| **IntentEngine** | 意图类型解析、技术栈检测、约束提取 | 知识缺口识别 |
| **MultiSearch** | 多源搜索、意图分类、结果聚合 | 来源策略选择 |
| **TieredSearch** | 分层API调度、查询优化 | 智能来源发现 |
| **FusionRAG** | 多源融合、结果去重、质量排序 | 信息质量评估 |
| **KnowledgeGraph** | 外部数据集成、实体抽取 | 信息源图谱 |

---

## 三、整合架构设计

### 3.1 三层信息需求智能体

```
┌─────────────────────────────────────────────────────────────────────┐
│                  InformationHunterAgent (信息需求智能体)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 1: KnowledgeGapDetector (知识缺口探测器)                │    │
│  │  ════════════════════════════════════════════════════════     │    │
│  │                                                              │    │
│  │  复用: IntentEngine                                          │    │
│  │  ├── intent_parser.py  → 信息依赖提取                        │    │
│  │  ├── tech_stack_detector.py → 技术知识检测                   │    │
│  │  └── constraint_extractor.py → 约束分析                      │    │
│  │                                                              │    │
│  │  新增: GapAnalysisEngine                                      │    │
│  │  ├── 任务分解 → 信息依赖图                                    │    │
│  │  ├── 知识自省 → 缺口识别                                     │    │
│  │  └── 追问生成 → 用户澄清                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 2: SourceStrategist (来源策略师)                         │    │
│  │  ════════════════════════════════════════════════════════     │    │
│  │                                                              │    │
│  │  复用: MultiSearch + TieredSearch                             │    │
│  │  ├── SearchIntent → 信息类型分类                              │    │
│  │  ├── SearchSource → 来源选择                                  │    │
│  │  └── QueryOptimizer → 查询优化                                │    │
│  │                                                              │    │
│  │  新增: SourceGraphEngine                                       │    │
│  │  ├── 信息源图谱 → 权威性/时效性/覆盖度                        │    │
│  │  ├── 来源推荐 → 基于需求类型                                  │    │
│  │  └── 策略生成 → 采集计划                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 3: InformationValidator (信息验证器)                      │    │
│  │  ════════════════════════════════════════════════════════     │    │
│  │                                                              │    │
│  │  复用: FusionRAG                                              │    │
│  │  ├── fusion_engine.py → 多源融合评分                          │    │
│  │  └── intelligent_router.py → 质量路由                         │    │
│  │                                                              │    │
│  │  新增: QualityAssessmentEngine                                 │    │
│  │  ├── 权威性评估 → 作者/机构/引用                             │    │
│  │  ├── 准确性评估 → 技术细节/可复现性                         │    │
│  │  ├── 时效性评估 → 发布/更新/趋势                             │    │
│  │  └── 综合评分 → 采纳/拒绝决策                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心类设计

```python
# ============================================================
# 信息需求智能体核心实现
# ============================================================

# ── 1. 知识缺口探测器 (扩展现有 IntentEngine) ─────────────────────────────

class KnowledgeGapDetector:
    """
    知识缺口探测器
    
    复用现有:
    - IntentEngine.intent_parser
    - IntentEngine.tech_stack_detector
    - IntentEngine.constraint_extractor
    """
    
    def __init__(self, llm_caller=None):
        # 复用现有 IntentEngine
        from core.intent_engine import IntentEngine
        self.intent_engine = IntentEngine(use_llm_enhancement=True)
        
        # 新增: 知识库对比
        from core.knowledge_graph import KnowledgeGraphManager
        self.knowledge_base = KnowledgeGraphManager()
        
        self.llm_caller = llm_caller
    
    def analyze_gaps(
        self, 
        task: str, 
        context: Dict = None
    ) -> GapAnalysisResult:
        """分析任务的知识缺口"""
        
        # 1. 解析任务意图 (复用 IntentEngine)
        intent = self.intent_engine.parse(task)
        
        # 2. 提取信息依赖 (新增)
        info_dependencies = self.extract_dependencies(intent, context)
        
        # 3. 对比知识库，找出缺口
        gaps = []
        for dep in info_dependencies:
            # 检查知识库覆盖度
            coverage = self.check_knowledge_coverage(dep)
            
            if coverage < 0.8:  # 低于80%覆盖度视为缺口
                gaps.append(KnowledgeGap(
                    dependency=dep,
                    coverage=coverage,
                    gap_type=self.classify_gap_type(dep),
                    priority=self.calculate_priority(dep, intent)
                ))
        
        # 4. 生成澄清问题 (如果需要)
        clarifications = self.generate_clarifications(gaps)
        
        return GapAnalysisResult(
            task=task,
            intent=intent,
            gaps=gaps,
            needs_clarification=len(clarifications) > 0,
            clarification_questions=clarifications
        )
    
    def extract_dependencies(
        self, 
        intent, 
        context: Dict
    ) -> List[InfoDependency]:
        """提取信息依赖"""
        
        # 基于意图类型定义依赖模板
        dependency_templates = {
            "code_generation": [
                "技术栈文档",
                "API接口规范",
                "最佳实践案例",
                "性能指标要求"
            ],
            "architecture_design": [
                "架构模式选择",
                "技术选型对比",
                " scalability 方案",
                "运维监控要求"
            ],
            "bug_fixing": [
                "错误日志分析",
                "类似问题案例",
                "官方解决方案",
                "版本兼容性"
            ]
        }
        
        # 从模板获取基础依赖
        base_deps = dependency_templates.get(intent.intent_type.value, [])
        
        # 使用 LLM 补充 (如果有)
        if self.llm_caller:
            llm_deps = self.llm_extract_dependencies(intent, context)
            base_deps.extend(llm_deps)
        
        return [InfoDependency(d) for d in base_deps]
    
    def check_knowledge_coverage(self, dep: InfoDependency) -> float:
        """检查知识库对某个依赖的覆盖度"""
        
        # 查询知识图谱
        concepts = self.knowledge_base.query_concepts(dep.description)
        
        if not concepts:
            return 0.0
        
        # 计算覆盖度: 有多少相关实体和关系
        coverage = min(1.0, len(concepts) / dep.expected_depth * 0.5)
        
        # 检查时效性
        latest_update = max(c.updated_at for c in concepts)
        days_since_update = (datetime.now() - latest_update).days
        
        if days_since_update > 180:  # 超过半年
            coverage *= 0.7
        
        return coverage


# ── 2. 来源策略师 (扩展现有 MultiSearch) ─────────────────────────────────

class SourceStrategist:
    """
    智能来源选择器
    
    复用现有:
    - MultiSearch.SearchIntent
    - MultiSearch.SearchSource
    - TieredSearch.TierRouter
    """
    
    # 信息源图谱
    SOURCE_GRAPH = {
        "conceptual_knowledge": {
            "primary": ["Wikipedia", "专业百科", "教科书"],
            "secondary": ["技术博客深度解析", "学术论文前言"],
            "tertiary": ["社区讨论", "问答网站"],
            "authority_weight": 0.8,
            "freshness_weight": 0.2
        },
        "technical_implementation": {
            "primary": ["官方文档", "GitHub源码", "API文档"],
            "secondary": ["技术教程", "StackOverflow高票"],
            "tertiary": ["博客实践", "视频教程"],
            "authority_weight": 0.6,
            "freshness_weight": 0.4
        },
        "latest_trends": {
            "primary": ["GitHub Trending", "Hacker News", "技术新闻"],
            "secondary": ["技术大会演讲", "公司工程博客"],
            "tertiary": ["社交媒体讨论"],
            "authority_weight": 0.4,
            "freshness_weight": 0.6
        },
        "best_practices": {
            "primary": ["Netflix/Uber工程博客", "行业白皮书"],
            "secondary": ["架构决策记录(ADRs)", "案例研究"],
            "tertiary": ["社区总结"],
            "authority_weight": 0.7,
            "freshness_weight": 0.3
        }
    }
    
    def __init__(self):
        # 复用现有搜索能力
        from core.intelligence_center.multi_search import MultiSearchEngine
        self.multi_search = MultiSearchEngine()
        
        from core.search.tiered_adapter import TieredSearchAdapter
        self.tiered_search = TieredSearchAdapter()
    
    def select_sources(
        self, 
        gaps: List[KnowledgeGap],
        user_context: Dict
    ) -> List[SourcePlan]:
        """为每个知识缺口选择最优来源"""
        
        plans = []
        
        for gap in gaps:
            # 1. 分类信息类型
            info_type = self.classify_info_type(gap)
            
            # 2. 获取来源推荐
            candidates = self.SOURCE_GRAPH.get(info_type, {})
            
            # 3. 基于用户上下文筛选
            filtered = self.filter_by_context(candidates, user_context)
            
            # 4. 智能排序
            ranked = self.rank_sources(filtered, gap)
            
            # 5. 生成采集策略
            plan = SourcePlan(
                gap=gap,
                info_type=info_type,
                primary_sources=ranked[:3],
                fallback_sources=ranked[3:6],
                strategy=self.generate_strategy(ranked[:3], gap)
            )
            plans.append(plan)
        
        return plans
    
    def classify_info_type(self, gap: KnowledgeGap) -> str:
        """分类信息类型"""
        
        gap_keywords = {
            "conceptual_knowledge": ["什么是", "原理", "概念", "定义"],
            "technical_implementation": ["怎么用", "实现", "代码", "示例"],
            "latest_trends": ["最新", "趋势", "2024", "2025", "新特性"],
            "best_practices": ["最佳实践", "经验", "建议", "避坑"]
        }
        
        for info_type, keywords in gap_keywords.items():
            if any(kw in gap.description for kw in keywords):
                return info_type
        
        return "technical_implementation"  # 默认
    
    def rank_sources(
        self, 
        sources: Dict, 
        gap: KnowledgeGap
    ) -> List[ScoredSource]:
        """对来源进行智能排序"""
        
        scored = []
        
        for priority in ["primary", "secondary", "tertiary"]:
            for source_name in sources.get(priority, []):
                # 查询知识图谱中的来源记录
                source_info = self.query_source_reputation(source_name)
                
                score = ScoredSource(
                    name=source_name,
                    priority=priority,
                    authority=source_info.authority_score,
                    freshness=source_info.freshness_score,
                    coverage=source_info.topic_coverage.get(gap.info_type, 0.5)
                )
                
                # 综合评分
                score.total_score = (
                    score.authority * 0.4 +
                    score.freshness * 0.3 +
                    score.coverage * 0.3
                )
                
                scored.append(score)
        
        return sorted(scored, key=lambda x: x.total_score, reverse=True)


# ── 3. 信息验证器 (扩展现有 FusionEngine) ─────────────────────────────────

class InformationValidator:
    """
    信息质量验证器
    
    复用现有:
    - FusionEngine (多源融合)
    - IntelligentRouter (质量路由)
    """
    
    QUALITY_WEIGHTS = {
        "authority": 0.3,    # 权威性
        "accuracy": 0.4,     # 准确性
        "freshness": 0.2,    # 时效性
        "coverage": 0.1      # 完整性
    }
    
    def __init__(self, llm_caller=None):
        # 复用现有融合引擎
        from core.fusion_rag.fusion_engine import FusionEngine
        self.fusion_engine = FusionEngine()
        
        self.llm_caller = llm_caller
    
    def evaluate_and_validate(
        self, 
        webpages: List[WebPage],
        gap: KnowledgeGap
    ) -> ValidationResult:
        """评估并验证网页质量"""
        
        validated = []
        
        for page in webpages:
            # 1. 提取质量指标
            metrics = self.extract_quality_metrics(page)
            
            # 2. 计算各维度评分
            scores = {
                "authority": self.score_authority(page),
                "accuracy": self.score_accuracy(page, gap),
                "freshness": self.score_freshness(page),
                "coverage": self.score_coverage(page, gap)
            }
            
            # 3. 加权总分
            total_score = sum(
                scores[k] * self.QUALITY_WEIGHTS[k] 
                for k in scores
            )
            
            # 4. 生成验证说明
            notes = self.generate_verification_notes(scores)
            
            # 5. 验证决策
            decision = "accept" if total_score >= 0.7 else "reject"
            
            validated.append(PageValidation(
                url=page.url,
                title=page.title,
                total_score=total_score,
                decision=decision,
                metrics=scores,
                notes=notes
            ))
        
        # 按评分排序
        validated.sort(key=lambda x: x.total_score, reverse=True)
        
        return ValidationResult(
            gap=gap,
            pages_validated=validated,
            accepted=[v for v in validated if v.decision == "accept"],
            rejected=[v for v in validated if v.decision == "reject"]
        )
    
    def score_authority(self, page: WebPage) -> float:
        """评估权威性"""
        
        # 权威来源列表
        HIGH_AUTHORITY_DOMAINS = {
            # 官方文档
            "docs.python.org", "docs.microsoft.com", "developer.github.com",
            # 工程博客
            "engineering.linkedin.com", "netflixtechblog.com", "eng.uber.com",
            "cloud.google.com", "aws.amazon.com",
            # 学术
            "arxiv.org", "scholar.google.com"
        }
        
        # 检查域名
        if any(domain in page.url for domain in HIGH_AUTHORITY_DOMAINS):
            return 0.95
        
        # 检查作者信息
        if page.author and page.author.get("verified"):
            return 0.85
        
        # 检查引用数
        if page.citation_count and page.citation_count > 100:
            return 0.8
        
        return 0.5  # 默认中等权威
    
    def score_accuracy(self, page: WebPage, gap: KnowledgeGap) -> float:
        """评估准确性"""
        
        # 复用 LLM 判断准确性
        if self.llm_caller:
            prompt = f"""
评估以下内容关于"{gap.description}"的准确性。

标题: {page.title}
摘要: {page.snippet[:500]}

请给出 0-1 的准确度评分，并说明理由。
            """
            response = self.llm_caller(prompt)
            return self.parse_accuracy_score(response)
        
        # 默认评分
        return 0.6
    
    def score_freshness(self, page: WebPage) -> float:
        """评估时效性"""
        
        if not page.published_date:
            return 0.5
        
        days_old = (datetime.now() - page.published_date).days
        
        if days_old <= 30:
            return 1.0
        elif days_old <= 90:
            return 0.9
        elif days_old <= 180:
            return 0.7
        elif days_old <= 365:
            return 0.5
        else:
            return 0.3


# ── 4. 信息猎手主控制器 ─────────────────────────────────────────────────────

class InformationHunterAgent:
    """
    信息需求智能体主控制器
    
    整合三个层级，提供统一入口
    """
    
    def __init__(
        self, 
        llm_caller=None,
        enable_active_learning: bool = True
    ):
        self.gap_detector = KnowledgeGapDetector(llm_caller)
        self.source_strategist = SourceStrategist()
        self.validator = InformationValidator(llm_caller)
        
        self.enable_active_learning = enable_active_learning
        self.feedback_history = []
    
    async def hunt(
        self, 
        task: str,
        context: Dict = None,
        max_sources_per_gap: int = 5
    ) -> HuntResult:
        """执行信息猎取"""
        
        start_time = datetime.now()
        
        # Phase 1: 缺口探测
        gap_result = self.gap_detector.analyze_gaps(task, context)
        
        if gap_result.needs_clarification:
            return HuntResult(
                status="needs_clarification",
                clarification_questions=gap_result.clarification_questions,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        
        # Phase 2: 来源决策
        source_plans = self.source_strategist.select_sources(
            gap_result.gaps, 
            context or {}
        )
        
        # Phase 3: 信息采集
        collected_info = []
        for plan in source_plans:
            webpages = await self.collect_from_sources(plan, max_sources_per_gap)
            collected_info.append(CollectedInfo(gap=plan.gap, webpages=webpages))
        
        # Phase 4: 质量验证
        validated_results = []
        for info in collected_info:
            validation = self.validator.evaluate_and_validate(
                info.webpages, 
                info.gap
            )
            validated_results.append(validation)
        
        # 生成最终报告
        report = self.generate_report(validated_results)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return HuntResult(
            status="completed",
            gaps_analyzed=len(gap_result.gaps),
            sources_selected=sum(len(p.primary_sources) for p in source_plans),
            pages_collected=sum(len(c.webpages) for c in collected_info),
            pages_accepted=sum(len(v.accepted) for v in validated_results),
            report=report,
            execution_time=execution_time
        )
    
    async def collect_from_sources(
        self, 
        plan: SourcePlan, 
        max_results: int
    ) -> List[WebPage]:
        """从选定来源采集信息"""
        
        # 使用分层搜索采集
        from core.search.tiered_adapter import TieredSearchAdapter
        
        adapter = TieredSearchAdapter()
        results = await adapter.search(
            query=plan.gap.description,
            num_results=max_results,
            max_tier=3
        )
        
        # 转换为 WebPage 对象
        webpages = [
            WebPage(
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                published_date=r.published_date,
                domain=r.domain,
                authority_score=r.authority_score
            )
            for r in results.get("results", [])
        ]
        
        return webpages
    
    def learn_from_feedback(
        self, 
        gap: KnowledgeGap,
        selected_sources: List[str],
        user_rating: float
    ):
        """从用户反馈中学习 (主动学习)"""
        
        if not self.enable_active_learning:
            return
        
        # 记录反馈
        self.feedback_history.append({
            "gap": gap,
            "sources": selected_sources,
            "rating": user_rating,
            "timestamp": datetime.now()
        })
        
        # 如果反馈足够多，更新来源策略
        if len(self.feedback_history) >= 10:
            self.update_source_strategy()
    
    def update_source_strategy(self):
        """基于反馈更新来源策略"""
        
        # 分析成功案例
        successful = [f for f in self.feedback_history if f["rating"] > 0.8]
        
        # 更新 SOURCE_GRAPH 中的权重
        for feedback in successful:
            gap_type = feedback["gap"].info_type
            for source in feedback["sources"]:
                self.source_strategist.increase_source_weight(gap_type, source)
        
        # 清空历史
        self.feedback_history = []
```

---

## 四、与现有模块的深度整合

### 4.1 模块复用映射

| 新增组件 | 复用现有模块 | 复用内容 | 扩展内容 |
|---------|------------|---------|---------|
| **KnowledgeGapDetector** | `IntentEngine` | 意图解析、依赖提取 | 知识缺口分析、覆盖率计算 |
| **SourceStrategist** | `MultiSearch` | 搜索意图分类、来源枚举 | 信息源图谱、策略生成 |
| **SourceStrategist** | `TieredSearch` | API调度、分层路由 | 权威性排序 |
| **InformationValidator** | `FusionEngine` | 多源融合评分 | 质量维度评估 |
| **InformationHunterAgent** | `FusionRAG` | 结果聚合、去重 | 完整猎取流程 |

### 4.2 整合架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      信息需求智能体整合架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  InformationHunterAgent (主控制器)                                    │
│  ════════════════════════════════════════════                        │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    复用: IntentEngine                           │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │  IntentParser → KnowledgeGapDetector                  │   │    │
│  │  │  TechStackDetector → GapTypeClassifier              │   │    │
│  │  │  ConstraintExtractor → PriorityCalculator            │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    复用: MultiSearch + TieredSearch            │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │  SearchIntent → InfoTypeClassifier                  │   │    │
│  │  │  SearchSource → SourceSelector                       │   │    │
│  │  │  TierRouter → PriorityRouter                        │   │    │
│  │  │  QueryOptimizer → StrategyGenerator                  │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    复用: FusionRAG                            │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │  FusionEngine → QualityFusion                        │   │    │
│  │  │  IntelligentRouter → ValidationRouter               │   │    │
│  │  │  KnowledgeBase → SourceReputationDB                  │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、工作流程示例

### 5.1 完整猎取流程

```
用户任务: "设计一个高性能的消息队列系统"
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: 缺口探测 (KnowledgeGapDetector)                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ IntentEngine 解析:                                           │
│ ├── intent_type: architecture_design                         │
│ ├── tech_stack: ["消息队列", "高并发"]                       │
│ └── constraints: ["高性能", "低延迟"]                        │
│                                                              │
│ 缺口识别:                                                    │
│ ├── Gap 1: 消息队列性能基准数据 (覆盖率 30%)                │
│ ├── Gap 2: Kafka vs RocketMQ 对比 (覆盖率 50%)              │
│ ├── Gap 3: 常见性能瓶颈解决方案 (覆盖率 60%)                │
│ └── Gap 4: 2024年最新趋势 (覆盖率 20%)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: 来源策略 (SourceStrategist)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Gap 1 → 性能基准                                             │
│ ├── 首选: JMH官方基准, Confluent博客                        │
│ ├── 备选: 技术大会演讲PDF                                    │
│ └── 策略: 搜索"kafka performance benchmark 2024"            │
│                                                              │
│ Gap 2 → 技术对比                                             │
│ ├── 首选: 官方文档对比页, GitHub对比Repo                    │
│ ├── 备选: StackOverflow高票答案                             │
│ └── 策略: 搜索"kafka vs rocketmq comparison"                │
│                                                              │
│ Gap 3 → 瓶颈方案                                             │
│ ├── 首选: Confluent/LinkedIn工程博客                        │
│ ├── 备选: 官方文档+常见问题                                 │
│ └── 策略: 搜索"kafka performance tuning best practices"     │
│                                                              │
│ Gap 4 → 最新趋势                                             │
│ ├── 首选: Kafka Summit 2024, Hacker News                    │
│ ├── 备选: 技术新闻网站                                       │
│ └── 策略: 搜索"kafka 2024 new features"                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: 信息采集                                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 使用 TieredSearch 执行搜索:                                   │
│ ├── Tier 1: 国内高稳定性API (百度/必应)                     │
│ ├── Tier 2: 专业技术API (CSDN/博客园)                       │
│ └── Tier 3: 国外API (DuckDuckGo)                            │
│                                                              │
│ 采集结果:                                                    │
│ ├── LinkedIn工程博客: kafka性能深度分析                      │
│ ├── Confluent博客: Kafka vs其他MQ对比                       │
│ ├── StackOverflow: 性能调优高票答案                         │
│ └── Kafka Summit 2024: 主题演讲视频                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: 质量验证 (InformationValidator)                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 评估结果:                                                    │
│ ├── LinkedIn博客: ⭐0.92 (采纳)                              │
│ │   ├── 权威性: 0.95 (Netflix官方)                          │
│ │   ├── 准确性: 0.90 (详细测试数据)                        │
│ │   └── 时效性: 0.85 (2023年)                              │
│ │                                                          │
│ ├── Confluent博客: ⭐0.88 (采纳)                            │
│ │   ├── 权威性: 0.98 (Kafka官方)                           │
│ │   ├── 准确性: 0.85 (官方数据)                            │
│ │   └── 时效性: 0.80 (2023年中)                            │
│ │                                                          │
│ └── StackOverflow: ⭐0.72 (采纳，需交叉验证)                 │
│     ├── 权威性: 0.60 (社区内容)                            │
│     ├── 准确性: 0.75 (高票验证)                            │
│     └── 时效性: 0.80 (持续更新)                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 最终报告                                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ # 高性能消息队列系统设计 - 信息猎取报告                       │
│                                                              │
│ ## 知识缺口: 4个                                             │
│ ## 信息来源: 8个                                            │
│ ## 采纳来源: 6个                                            │
│                                                              │
│ ## 关键发现:                                                 │
│ 1. Kafka在吞吐量方面领先，但延迟略高于Pulsar                │
│ 2. 性能瓶颈主要集中在磁盘IO和网络                            │
│ 3. 2024年趋势: 事务性消息、渐进式分区再均衡                 │
│                                                              │
│ ## 推荐来源:                                                 │
│ - LinkedIn工程博客 (权威+深度)                              │
│ - Confluent官方文档 (准确+全面)                              │
│ - Kafka Summit 2024视频 (趋势+前瞻)                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、与 Architect Agent 的协同

### 6.1 协同工作流

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Architect Agent + Information Hunter 协同           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Architect Agent                                                    │
│  ═══════════════                                                    │
│  "分析架构演进机会"                                                   │
│           ↓                                                          │
│           │ 调用 InformationHunter                                    │
│           ↓                                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ InformationHunter: "发现外部架构知识"                          │    │
│  │                                                              │    │
│  │ 1. 缺口探测:                                                  │    │
│  │    - 当前架构 → 微服务                                       │    │
│  │    - 缺失知识 → 事件驱动、CQRS、服务网格                      │    │
│  │                                                              │    │
│  │ 2. 来源策略:                                                  │    │
│  │    - Netflix → 事件驱动实践                                  │    │
│  │    - Uber → CQRS案例                                          │    │
│  │    - Solo.io → 服务网格对比                                  │    │
│  │                                                              │    │
│  │ 3. 信息验证:                                                  │    │
│  │    - LinkedIn博客: 权威性0.95 ✓                              │    │
│  │    - Uber工程: 权威性0.92 ✓                                  │    │
│  │                                                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│           ↓                                                          │
│           │ 返回高质量外部知识                                       │
│           ↓                                                          │
│  Architect Agent                                                    │
│  ═══════════════                                                    │
│  "生成架构演进路线图"                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 七、实施路径

### 7.1 三阶段实施计划

```
Phase 1: 基础整合 (2-3 周)
═══════════════════════════════
目标: 扩展现有模块支持信息猎取

任务:
├── [ ] 1.1 扩展 IntentEngine → KnowledgeGapDetector
├── [ ] 1.2 扩展 MultiSearch → SourceStrategist
├── [ ] 1.3 扩展 FusionEngine → InformationValidator
├── [ ] 1.4 实现 InformationHunterAgent 主控制器
└── [ ] 1.5 基础测试

产出:
• 可用的信息猎取能力
• 与 Architect Agent 集成


Phase 2: 智能增强 (4-6 周)
═══════════════════════════════
目标: 提升来源选择和信息验证能力

任务:
├── [ ] 2.1 构建信息源图谱
├── [ ] 2.2 实现来源权威性评估
├── [ ] 2.3 实现内容准确性验证
├── [ ] 2.4 添加主动学习反馈机制
└── [ ] 2.5 性能优化

产出:
• 智能来源推荐
• 高质量信息验证


Phase 3: 生态整合 (6-8 周)
═══════════════════════════════
目标: 与其他智能体深度集成

任务:
├── [ ] 3.1 与 Architect Agent 深度集成
├── [ ] 3.2 与 Industry Expert Factory 集成
├── [ ] 3.3 与 LivingTreeAI IDE 升级引擎集成
├── [ ] 3.4 实现跨语言信息获取
└── [ ] 3.5 完整生态系统测试

产出:
• 完整的 LivingTreeAI 智能系统矩阵
```

---

## 八、总结

### 8.1 整合评估

**整合匹配度: ⭐⭐⭐⭐⭐ (95%)**

| 组件 | 复用现有 | 匹配度 | 扩展价值 |
|------|---------|--------|---------|
| KnowledgeGapDetector | IntentEngine | ⭐⭐⭐⭐⭐ | 缺口识别 |
| SourceStrategist | MultiSearch + TieredSearch | ⭐⭐⭐⭐⭐ | 智能来源 |
| InformationValidator | FusionRAG | ⭐⭐⭐⭐⭐ | 质量评估 |
| InformationHunterAgent | 全部 | ⭐⭐⭐⭐ | 统一入口 |

### 8.2 核心价值

1. **元认知能力**: AI知道自己不知道什么
2. **主动获取**: 知道去哪找、怎么找
3. **质量保障**: 找到的信息经过验证
4. **持续进化**: 从反馈中学习改进

### 8.3 智能系统矩阵

```
LivingTreeAI 智能系统
├── InformationHunter (信息猎手) 🆕
│   └── 能力: 知识缺口 → 来源 → 验证
├── Architect Agent (架构智能体)
│   └── 能力: 探索 → 理解 → 映射 → 规划
├── Industry Expert Factory (行业专家工厂)
│   └── 能力: 训练 → 适配 → 协作
└── IDE Upgrader Engine (IDE升级引擎)
    └── 能力: 分析 → 建议 → 改造

协同价值:
InformationHunter → 为所有智能体提供"去哪知道"的能力
```
