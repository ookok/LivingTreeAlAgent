"""
知识图谱系统主控制器
=====================

统一入口，管理整个知识图谱生命周期

新增功能：
- 外部数据源集成 (External Data Hub)
- 排放系数融合
- 背景环境数据融合
- 实时监测数据融合
- 实体链接与映射
- 工艺数字孪生体 (Digital Twin) 🆕
- 环境合规自动驾驶仪 (Compliance Autopilot) 🆕
- 环境AI科学家 (AI Scientist) 🆕
- 产业级知识网络 (Industry Network) 🆕

Author: Hermes Desktop Team
"""

from typing import Dict, List, Optional, Any, Tuple, Set
import json

from .graph import KnowledgeGraph, KnowledgeNode, KnowledgeRelation, KnowledgeBase
try:
    from .storage import HybridStorageManager, StorageConfig, CacheManager
except ImportError:
    HybridStorageManager = StorageConfig = CacheManager = None
try:
    from .agents import ExtractionPipeline, ExtractionConfig, DocumentParserFactory, UnifiedDocumentParser
except ImportError:
    ExtractionPipeline = ExtractionConfig = DocumentParserFactory = UnifiedDocumentParser = None
try:
    from .reasoning import ReasoningEngine
except ImportError:
    ReasoningEngine = None
try:
    from .applications import KnowledgeQAManager, ReportGenerator, ProcessOptimizer
except ImportError:
    KnowledgeQAManager = ReportGenerator = ProcessOptimizer = None
try:
    from .evolution import KnowledgeGraphSystem, FeedbackType, FeedbackSource
except ImportError:
    KnowledgeGraphSystem = FeedbackType = FeedbackSource = None
try:
    from .external_data import (
        ExternalDataHub, get_external_data_hub,
        EmissionFactorRegistry, get_emission_registry, EmissionGraphIntegrator, get_integrator,
        EnvBackgroundData, get_env_background_data, EnvDataGraphIntegrator, get_env_integrator,
        RealtimeMonitoringCenter, get_monitoring_center, MonitoringGraphIntegrator,
        EntityLinker, get_entity_linker, GraphFusionEngine, get_fusion_engine
    )
except ImportError:
    ExternalDataHub = get_external_data_hub = None
    EmissionFactorRegistry = get_emission_registry = EmissionGraphIntegrator = get_integrator = None
    EnvBackgroundData = get_env_background_data = EnvDataGraphIntegrator = get_env_integrator = None
    RealtimeMonitoringCenter = get_monitoring_center = MonitoringGraphIntegrator = None
    EntityLinker = get_entity_linker = GraphFusionEngine = get_fusion_engine = None
try:
    from ..digital_twin import (
        ProcessDigitalTwin, DigitalTwinFactory, get_twin_factory,
        create_digital_twin, SimulationStatus, ScenarioType
    )
except ImportError:
    ProcessDigitalTwin = DigitalTwinFactory = get_twin_factory = None
    create_digital_twin = SimulationStatus = ScenarioType = None
try:
    from ..compliance_auto import (
        ComplianceAutopilot, PermitManager, get_compliance_autopilot,
        AlertLevel, ComplianceStatus, MonitoringPoint, ComplianceRule
    )
except ImportError:
    ComplianceAutopilot = PermitManager = get_compliance_autopilot = None
    AlertLevel = ComplianceStatus = MonitoringPoint = ComplianceRule = None
try:
    from ..ai_scientist import (
        EnvironmentalAIScientist, get_ai_scientist,
        TechnologyRoute, TechRecommendation
    )
except ImportError:
    EnvironmentalAIScientist = get_ai_scientist = TechnologyRoute = TechRecommendation = None
try:
    from ..industry_network import (
        IndustryEnvironmentalNetwork, get_industry_network,
        SupplyChainAudit, RegionalCapacity, TradeMatch
    )
except ImportError:
    IndustryEnvironmentalNetwork = get_industry_network = SupplyChainAudit = RegionalCapacity = TradeMatch = None


class KnowledgeGraphManager:
    """知识图谱管理器"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 存储层
        storage_config = StorageConfig()
        self.storage = HybridStorageManager(storage_config)

        # 缓存
        self.cache = CacheManager(max_size=1000)

        # 抽取流水线
        extraction_config = ExtractionConfig()
        self.extraction_pipeline = ExtractionPipeline(extraction_config)

        # 推理引擎
        self.reasoning_engine = ReasoningEngine()

        # 进化引擎
        self.evolution_system = KnowledgeGraphSystem()

        # 当前知识图谱
        self.current_kg: Optional[KnowledgeGraph] = None

        # QA系统（延迟初始化）
        self._qa_system: Optional[KnowledgeQAManager] = None

        # ============================================================
        # 外部数据源集成 (External Data Hub)
        # ============================================================
        # 外部数据接入中心
        self.external_hub = get_external_data_hub()

        # 排放系数注册表
        self.emission_registry = get_emission_registry(self.external_hub)

        # 背景环境数据
        self.env_background = get_env_background_data(self.external_hub)

        # 实时监测中心
        self.monitoring_center = get_monitoring_center(
            self.external_hub, self.emission_registry
        )

        # 实体链接器
        self.entity_linker = get_entity_linker(self._kg_wrapper())

        # 图谱融合引擎
        self.fusion_engine = get_fusion_engine(self._kg_wrapper())

        # 融合器快捷访问
        self.emission_integrator = get_integrator(self._kg_wrapper())
        self.env_integrator = get_env_integrator(self._kg_wrapper())
        self.monitoring_integrator = self.monitoring_center  # MonitoringGraphIntegrator

        # ============================================================
        # 高级功能模块 🆕
        # ============================================================

        # 数字孪生体工厂
        self._twin_factory = get_twin_factory()

        # 合规自动驾驶仪（延迟初始化，需要公司ID）
        self._compliance_autopilot: Optional[ComplianceAutopilot] = None
        self._company_id: str = config.get("company_id", "default_company")

        # 环境AI科学家
        self.ai_scientist = get_ai_scientist(self._kg_wrapper())

        # 产业级知识网络
        self.industry_network = get_industry_network(self._kg_wrapper())

    def _kg_wrapper(self):
        """获取图谱访问包装器（用于融合器）"""
        return self.current_kg

    # ============================================================
    # 核心操作
    # ============================================================

    def create_empty_graph(self, name: str = "new_graph") -> KnowledgeGraph:
        """创建空知识图谱"""
        self.current_kg = KnowledgeGraph(name=name)
        return self.current_kg

    def load_graph(self, graph_id: str) -> bool:
        """加载知识图谱"""
        # 尝试从存储加载
        results = self.storage.execute_graph_query(f"MATCH (n {{id: '{graph_id}'}}) RETURN n")
        if results:
            # 重建知识图谱
            # TODO: 实现完整的图谱重建
            return True
        return False

    def save_graph(self) -> bool:
        """保存当前知识图谱"""
        if not self.current_kg:
            return False
        return self.storage.store_knowledge_graph(self.current_kg)

    # ============================================================
    # 知识抽取
    # ============================================================

    def extract_from_text(self, text: str) -> KnowledgeGraph:
        """从文本抽取知识"""
        self.current_kg = self.extraction_pipeline.run(text)
        return self.current_kg

    def extract_from_document(self, file_path: str) -> KnowledgeGraph:
        """从文档抽取知识"""
        parser = UnifiedDocumentParser()
        parsed_doc = parser.parse(file_path)
        self.current_kg = self.extraction_pipeline.run(parsed_doc.text_content)
        return self.current_kg

    def extract_from_documents(self, file_paths: List[str]) -> KnowledgeGraph:
        """批量从文档抽取"""
        all_text = []
        parser = UnifiedDocumentParser()

        for path in file_paths:
            parsed_doc = parser.parse(path)
            if parsed_doc.text_content:
                all_text.append(parsed_doc.text_content)

        combined_text = "\n\n".join(all_text)
        self.current_kg = self.extraction_pipeline.run(combined_text)
        return self.current_kg

    # ============================================================
    # 知识推理
    # ============================================================

    def reason(self, strategy: str = "hybrid", query: Optional[str] = None) -> KnowledgeGraph:
        """执行推理"""
        if not self.current_kg:
            return self.create_empty_graph()

        # 执行推理
        result = self.reasoning_engine.reason(self.current_kg, strategy, query)

        # 添加推断的知识
        for entity in result.inferred_entities:
            if not self.current_kg.get_entity_by_name(entity.name):
                self.current_kg.add_entity(entity)

        for relation in result.inferred_relations:
            existing = any(
                r.source_id == relation.source_id and
                r.target_id == relation.target_id and
                r.relation_type == relation.relation_type
                for r in self.current_kg.relations.values()
            )
            if not existing:
                self.current_kg.add_relation(relation)

        return self.current_kg

    def complete_graph(self) -> KnowledgeGraph:
        """补全知识图谱"""
        if not self.current_kg:
            return self.create_empty_graph()

        self.current_kg = self.reasoning_engine.complete_knowledge_graph(self.current_kg)
        return self.current_kg

    # ============================================================
    # 知识应用
    # ============================================================

    def get_qa_system(self) -> KnowledgeQAManager:
        """获取问答系统"""
        if not self._qa_system and self.current_kg:
            self._qa_system = KnowledgeQAManager(self.current_kg)
        return self._qa_system

    def ask(self, question: str) -> str:
        """问答"""
        if not self.current_kg:
            return "请先加载或创建知识图谱"

        qa = self.get_qa_system()
        return qa.ask(question)

    def generate_report(self, project_info: Dict) -> Any:
        """生成报告"""
        if not self.current_kg:
            return None

        qa = self.get_qa_system()
        return qa.generate_report(project_info)

    def export_report(self, report: Any, format: str = "markdown") -> str:
        """导出报告"""
        qa = self.get_qa_system()
        return qa.export_report(report, format)

    def get_optimization_suggestions(self, goal: str = "环保") -> List:
        """获取优化建议"""
        if not self.current_kg:
            return []

        qa = self.get_qa_system()
        return qa.get_optimization_suggestions(goal)

    # ============================================================
    # 知识管理
    # ============================================================

    def add_entity(self, entity: Entity) -> None:
        """添加实体"""
        if not self.current_kg:
            self.create_empty_graph()
        self.current_kg.add_entity(entity)

    def add_relation(self, relation: Relation) -> None:
        """添加关系"""
        if not self.current_kg:
            return
        self.current_kg.add_relation(relation)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        if not self.current_kg:
            return None
        return self.current_kg.entities.get(entity_id)

    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """按类型获取实体"""
        if not self.current_kg:
            return []
        return self.current_kg.get_entities_by_type(entity_type)

    def delete_entity(self, entity_id: str) -> bool:
        """删除实体"""
        if not self.current_kg:
            return False
        if entity_id in self.current_kg.entities:
            del self.current_kg.entities[entity_id]
            # 删除相关关系
            to_delete = [
                rid for rid, rel in self.current_kg.relations.items()
                if rel.source_id == entity_id or rel.target_id == entity_id
            ]
            for rid in to_delete:
                del self.current_kg.relations[rid]
            return True
        return False

    # ============================================================
    # 反馈和学习
    # ============================================================

    def collect_feedback(self, feedback_type: FeedbackType, target_id: str,
                        content: Any, source: FeedbackSource = FeedbackSource.USER) -> str:
        """收集反馈"""
        return self.evolution_system.evolution.feedback_collector.add_feedback(
            feedback_type, source, target_id, content
        )

    # ============================================================
    # 外部数据源集成
    # ============================================================

    def query_emission_factor(self, process_name: str, industry: str = None,
                            pollutant: str = None) -> Optional[Dict]:
        """
        查询排放系数

        Args:
            process_name: 工艺名称
            industry: 行业
            pollutant: 污染物

        Returns:
            排放系数数据
        """
        return self.external_hub.query_emission_factor(
            process_name=process_name,
            industry=industry,
            pollutant=pollutant
        )

    def query_regional_environment(self, province: str, year: int = None,
                                  data_type: str = "air") -> Optional[Dict]:
        """
        查询区域环境数据

        Args:
            province: 省份
            year: 年份
            data_type: 数据类型（air/water/soil/all）

        Returns:
            区域环境数据
        """
        return self.external_hub.query_regional_environment(
            province=province,
            year=year,
            data_type=data_type
        )

    def query_realtime_monitoring(self, company_name: str = None,
                                 region: str = None) -> List[Dict]:
        """
        查询实时监测数据

        Args:
            company_name: 企业名称
            region: 区域

        Returns:
            实时监测数据列表
        """
        return self.external_hub.query_realtime_monitoring(
            company_name=company_name,
            region=region
        )

    def integrate_emission_factor(self, process_node_id: str,
                                 process_name: str = None,
                                 pollutant: str = None) -> bool:
        """
        将排放系数集成到知识图谱

        Args:
            process_node_id: 工艺节点ID
            process_name: 工艺名称（从节点获取或指定）
            pollutant: 污染物

        Returns:
            是否成功
        """
        if not self.current_kg:
            return False

        # 获取工艺名称
        if not process_name:
            entity = self.current_kg.get_entity(process_node_id)
            process_name = entity.name if entity else ""

        return self.emission_integrator.integrate_factor_to_graph(
            process_node_id=process_node_id,
            factor=self._find_emission_factor(process_name, pollutant)
        )

    def _find_emission_factor(self, process_name: str, pollutant: str = None):
        """查找排放系数"""
        factors = self.emission_registry.find_factors(
            process_name=process_name,
            pollutant=pollutant
        )
        if factors:
            return factors[0]
        # 尝试从外部获取
        ext_factors = self.emission_registry.query_from_external(process_name, pollutant)
        if ext_factors:
            return ext_factors[0]
        return None

    def auto_complete_process_emissions(self, process_node_id: str) -> List[str]:
        """
        自动补全工艺的排放信息

        Args:
            process_node_id: 工艺节点ID

        Returns:
            融合的系数节点ID列表
        """
        return self.emission_integrator.auto_complete_process_emissions(process_node_id)

    def calculate_emission(self, process_node_id: str,
                          activity_level: float,
                          activity_unit: str) -> List[Dict]:
        """
        计算工艺排放量

        Args:
            process_node_id: 工艺节点ID
            activity_level: 活动水平（产量、用料量）
            activity_unit: 活动水平单位

        Returns:
            排放计算结果列表
        """
        return self.emission_integrator.calculate_process_emissions(
            process_node_id, activity_level, activity_unit
        )

    def generate_region_env_chapter(self, project_location: Dict[str, str],
                                   year: int = None) -> Dict[str, str]:
        """
        生成"区域环境现状"章节

        Args:
            project_location: 项目位置 {"province": "江苏", "city": "南京"}
            year: 数据年份

        Returns:
            章节内容 {"title", "content", "tables", "data_year", "data_source"}
        """
        return self.env_background.generate_chapter_region_env(
            project_location=project_location,
            year=year
        )

    def integrate_regional_data(self, region_node_id: str,
                              province: str, year: int = None) -> int:
        """
        将区域环境数据集成到图谱

        Args:
            region_node_id: 区域节点ID
            province: 省份
            year: 年份

        Returns:
            融合的数据条数
        """
        return self.env_integrator.auto_integrate_region(province, year)

    def check_monitoring_alerts(self) -> List[Dict]:
        """
        检查监测预警

        Returns:
            预警记录列表
        """
        return self.monitoring_center.check_alerts()

    def detect_anomaly(self, point_id: str, pollutant: str,
                      time_range: Tuple = None) -> Optional[Dict]:
        """
        异常检测：对比实测与理论

        Args:
            point_id: 监测点位ID
            pollutant: 污染物
            time_range: 时间范围

        Returns:
            异常检测结果
        """
        return self.monitoring_center.detect_anomaly(point_id, pollutant, time_range)

    def generate_verification_report(self, project_info: Dict) -> Dict:
        """
        生成数据验证报告（"三本账"核算参照）

        Args:
            project_info: 项目信息

        Returns:
            验证报告
        """
        return self.monitoring_center.generate_verification_report(project_info)

    def fuse_external_data(self, node_id: str, node_type: str) -> Dict:
        """
        全面融合外部数据到指定节点

        Args:
            node_id: 节点ID
            node_type: 节点类型（Process/Location/Company）

        Returns:
            融合报告
        """
        return self.fusion_engine.full_fusion(node_id, node_type)

    def link_external_entity(self, internal_id: str, external_id: str,
                            external_source: str, entity_type: str) -> bool:
        """
        链接外部实体

        Args:
            internal_id: 内部实体ID
            external_id: 外部实体ID
            external_source: 外部数据源
            entity_type: 实体类型

        Returns:
            是否成功
        """
        from .external_data.entity_linker import EntityMapping, MappingQuality
        mapping = EntityMapping(
            mapping_id=f"map_{internal_id}_{external_id}",
            internal_id=internal_id,
            external_id=external_id,
            external_source=external_source,
            entity_type=entity_type,
            quality=MappingQuality.MEDIUM
        )
        return self.entity_linker.register_mapping(mapping)

    def get_external_links(self, internal_id: str) -> Set[str]:
        """
        获取内部节点的外部链接

        Args:
            internal_id: 内部节点ID

        Returns:
            外部节点ID集合
        """
        return self.entity_linker.get_external_links(internal_id)

    def get_mapping_quality_report(self) -> Dict:
        """
        获取映射质量报告

        Returns:
            质量报告
        """
        return self.entity_linker.get_mapping_quality_report()

    def sync_external_data(self, source_id: str = None) -> Dict:
        """
        手动触发外部数据同步

        Args:
            source_id: 数据源ID（None表示全部）

        Returns:
            同步结果
        """
        return self.external_hub.sync_data(source_id)

    def get_external_data_stats(self) -> Dict:
        """
        获取外部数据源统计

        Returns:
            统计信息
        """
        return self.external_hub.get_stats()

    # ============================================================
    # 工艺数字孪生体 (Digital Twin) 🆕
    # ============================================================

    def create_digital_twin(self, project_id: str, project_name: str = "") -> ProcessDigitalTwin:
        """
        创建工艺数字孪生体

        Args:
            project_id: 项目ID
            project_name: 项目名称

        Returns:
            数字孪生体实例
        """
        twin = self._twin_factory.create_twin(project_id, project_name)

        # 链接到知识图谱
        if self.current_kg:
            process_ids = [e.entity_id for e in self.current_kg.entities.values()
                         if e.entity_type == EntityType.PROCESS]
            twin.link_to_knowledge_graph(process_ids)

        return twin

    def get_digital_twin(self, project_id: str) -> Optional[ProcessDigitalTwin]:
        """获取数字孪生体"""
        return self._twin_factory.get_twin(project_id)

    def simulate_environmental_impact(self, project_id: str,
                                     duration_hours: float = 24,
                                     scenario_type: str = "normal") -> Dict:
        """
        运行环境影响仿真

        Args:
            project_id: 项目ID
            duration_hours: 仿真时长
            scenario_type: 情景类型

        Returns:
            仿真结果
        """
        twin = self._twin_factory.get_twin(project_id)
        if not twin:
            return {"error": "数字孪生体不存在"}

        scenario = ScenarioType(scenario_type) if scenario_type else ScenarioType.NORMAL
        result = twin.simulate(duration_hours, scenario_type=scenario)

        return {
            "simulation_id": result.simulation_id,
            "max_ground_level": result.max_ground_level,
            "exceedance_areas_count": len(result.exceedance_areas),
            "receptor_impacts": result.receptor_impacts,
            "status": result.status.value
        }

    def whatif_analysis(self, project_id: str, name: str,
                      modifications: List[Dict]) -> Dict:
        """
        What-If情景分析

        Args:
            project_id: 项目ID
            name: 情景名称
            modifications: 修改列表

        Returns:
            分析结果
        """
        twin = self._twin_factory.get_twin(project_id)
        if not twin:
            return {"error": "数字孪生体不存在"}

        scenario = twin.create_whatif_scenario(name, modifications)
        return twin.evaluate_scenario(scenario)

    # ============================================================
    # 环境合规自动驾驶仪 (Compliance Autopilot) 🆕
    # ============================================================

    def get_compliance_autopilot(self, company_id: str = None) -> ComplianceAutopilot:
        """
        获取合规自动驾驶仪

        Args:
            company_id: 公司ID

        Returns:
            合规自动驾驶仪实例
        """
        company_id = company_id or self._company_id
        return get_compliance_autopilot(company_id)

    def start_compliance_monitoring(self, company_id: str = None) -> bool:
        """
        启动合规监控

        Args:
            company_id: 公司ID

        Returns:
            是否成功
        """
        autopilot = self.get_compliance_autopilot(company_id)
        autopilot.start_monitoring()
        return True

    def stop_compliance_monitoring(self) -> bool:
        """停止合规监控"""
        if self._compliance_autopilot:
            self._compliance_autopilot.stop_monitoring()
        return True

    def get_compliance_status(self) -> Dict:
        """获取当前合规状态"""
        autopilot = self.get_compliance_autopilot()
        return {
            "status": autopilot.get_compliance_status().value,
            "active_alerts": len(autopilot.get_active_alerts()),
            "monitoring_points": len(autopilot.monitoring_points)
        }

    def get_compliance_alerts(self, level: str = None) -> List[Dict]:
        """
        获取合规预警

        Args:
            level: 预警级别

        Returns:
            预警列表
        """
        autopilot = self.get_compliance_autopilot()
        alert_level = AlertLevel(level) if level else None
        alerts = autopilot.get_active_alerts(alert_level)

        return [
            {
                "alert_id": a.alert_id,
                "level": a.level.value,
                "message": a.message,
                "recommendations": a.recommendations,
                "timestamp": a.timestamp.isoformat()
            }
            for a in alerts
        ]

    def generate_compliance_report(self, period_start: datetime,
                                 period_end: datetime) -> Dict:
        """
        生成合规报告

        Args:
            period_start: 报告期起始
            period_end: 报告期结束

        Returns:
            合规报告
        """
        autopilot = self.get_compliance_autopilot()
        report = autopilot.generate_compliance_report(period_start, period_end)
        return autopilot.export_report(report)

    # ============================================================
    # 环境AI科学家 (AI Scientist) 🆕
    # ============================================================

    def detect_unknown_pollutant(self, source_id: str,
                                peaks: List[Tuple[float, float]]) -> Dict:
        """
        检测未知污染物

        Args:
            source_id: 来源ID
            peaks: 质谱峰列表

        Returns:
            检测结果
        """
        result = self.ai_scientist.detect_unknown_pollutant(source_id, peaks)

        return {
            "pollutant_id": result.pollutant_id,
            "possible_compounds": result.possible_compounds,
            "risk_assessment": result.risk_assessment,
            "recommendations": result.recommendations
        }

    def plan_pollution_control(self, target_pollutant: str,
                              current_emission: float,
                              reduction_target: float) -> Dict:
        """
        规划污染控制技术路线

        Args:
            target_pollutant: 目标污染物
            current_emission: 当前排放量
            reduction_target: 减排目标

        Returns:
            技术推荐
        """
        rec = self.ai_scientist.plan_pollution_control(
            target_pollutant, current_emission, reduction_target
        )

        return {
            "target_pollutant": rec.target_pollutant,
            "target_reduction": f"{rec.target_reduction*100:.0f}%",
            "best_route": {
                "name": rec.best_route.name if rec.best_route else None,
                "investment": rec.best_route.total_investment if rec.best_route else 0,
                "payback_period": rec.best_route.payback_period if rec.best_route else 0,
                "expected_efficiency": rec.best_route.expected_efficiency if rec.best_route else 0
            } if rec.best_route else None,
            "alternatives": [
                {"name": r.name, "efficiency": r.expected_efficiency}
                for r in rec.alternatives[:3]
            ],
            "considerations": rec.considerations
        }

    def mine_literature(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        挖掘文献

        Args:
            query: 查询关键词
            max_results: 最大结果数

        Returns:
            文献列表
        """
        results = self.ai_scientist.mine_literature(query, max_results)
        return [
            {
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "findings": r.findings
            }
            for r in results
        ]

    def discover_knowledge(self, project_data: Dict) -> List[Dict]:
        """
        知识发现

        Args:
            project_data: 项目数据

        Returns:
            发现列表
        """
        discoveries = self.ai_scientist.discover_knowledge(project_data)
        return [
            {
                "title": d.title,
                "confidence": d.confidence,
                "implications": d.implications
            }
            for d in discoveries
        ]

    # ============================================================
    # 产业级知识网络 (Industry Network) 🆕
    # ============================================================

    def build_supply_chain_network(self, company_id: str) -> Dict:
        """
        构建供应链网络

        Args:
            company_id: 公司ID

        Returns:
            网络信息
        """
        network = self.industry_network
        chain = network.build_supply_chain_network(company_id)

        return {
            "company_id": company_id,
            "supplier_count": len(chain),
            "tier_distribution": {
                "tier1": len([n for n in chain if n.tier == 1]),
                "tier2": len([n for n in chain if n.tier == 2])
            },
            "high_risk_count": len([n for n in chain if n.risk_score >= 0.6])
        }

    def audit_supply_chain(self, company_id: str) -> Dict:
        """
        供应链环境审计

        Args:
            company_id: 公司ID

        Returns:
            审计报告
        """
        audit = self.industry_network.audit_supply_chain(company_id)

        return {
            "audit_id": audit.audit_id,
            "target_company": audit.target_company,
            "supplier_count": audit.supplier_count,
            "total_risk_score": audit.total_risk_score,
            "high_risk_suppliers": audit.high_risk_suppliers,
            "emission_transfer_risks": audit.emission_transfer_risks,
            "recommendations": audit.recommendations
        }

    def predict_region_capacity(self, region_name: str,
                              capacity_type: str = "air") -> Dict:
        """
        预测区域环境容量

        Args:
            region_name: 区域名称
            capacity_type: 容量类型

        Returns:
            容量预测
        """
        capacity = self.industry_network.predict_region_capacity(region_name, capacity_type)

        return {
            "region": capacity.region_name,
            "type": capacity.capacity_type,
            "utilization_rate": f"{capacity.utilization_rate*100:.1f}%",
            "remaining": f"{capacity.remaining_capacity:.0f}",
            "prediction_3month": f"{capacity.prediction_3month:.0f}",
            "prediction_6month": f"{capacity.prediction_6month:.0f}",
            "confidence": capacity.confidence
        }

    def match_emission_trades(self, pollutant: str) -> List[Dict]:
        """
        排放权交易撮合

        Args:
            pollutant: 污染物类型

        Returns:
            匹配列表
        """
        matches = self.industry_network.match_emission_trades(pollutant)

        return [
            {
                "match_id": m.match_id,
                "seller": m.seller_company,
                "quantity": m.quantity,
                "suggested_price": m.suggested_price,
                "savings": m.savings,
                "confidence": m.confidence
            }
            for m in matches
        ]

    def assess_regional_risk(self, region_name: str) -> Dict:
        """
        区域风险评估

        Args:
            region_name: 区域名称

        Returns:
            风险评估报告
        """
        assessment = self.industry_network.assess_regional_risk(region_name)

        return {
            "assessment_id": assessment.assessment_id,
            "region": region_name,
            "overall_risk": assessment.overall_risk_level.value,
            "risk_hotspots": assessment.risk_hotspots,
            "传导路径": assessment.传导路径,
            "recommendations": assessment.recommendations
        }

    def get_all_sources(self) -> List[Dict]:
        """
        获取所有外部数据源

        Returns:
            数据源列表
        """
        sources = self.external_hub.list_sources()
        return [
            {
                "source_id": s.source_id,
                "name": s.name,
                "type": s.source_type.value,
                "freshness": s.freshness.value,
                "enabled": s.enabled
            }
            for s in sources
        ]

    def evolve_knowledge(self, new_data: Optional[KnowledgeGraph] = None) -> None:
        """触发知识进化"""
        if self.current_kg:
            self.evolution_system.load_knowledge_graph(self.current_kg)
        self.evolution_system.evolve_knowledge(new_data)
        if new_data:
            self.current_kg = self.evolution_system.get_current_kg()

    def get_quality_report(self) -> Dict:
        """获取质量报告"""
        if self.current_kg:
            self.evolution_system.load_knowledge_graph(self.current_kg)
        return self.evolution_system.get_quality_report()

    # ============================================================
    # 导入导出
    # ============================================================

    def export_to_json(self) -> str:
        """导出为JSON"""
        if not self.current_kg:
            return "{}"
        return json.dumps(self.current_kg.to_dict(), ensure_ascii=False, indent=2)

    def export_to_cypher(self) -> str:
        """导出为Cypher"""
        if not self.current_kg:
            return ""
        from . import export_to_cypher
        return export_to_cypher(self.current_kg)

    def export_to_graphviz(self) -> str:
        """导出为Graphviz"""
        if not self.current_kg:
            return ""
        from . import export_to_graphviz
        return export_to_graphviz(self.current_kg)

    def import_from_json(self, json_str: str) -> bool:
        """从JSON导入"""
        try:
            data = json.loads(json_str)
            self.current_kg = KnowledgeGraph.from_dict(data)
            return True
        except Exception as e:
            print(f"导入失败: {e}")
            return False

    # ============================================================
    # 统计信息
    # ============================================================

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self.current_kg:
            return {
                "entity_count": 0,
                "relation_count": 0,
                "entity_types": {},
                "relation_types": {},
                "external_data": self.get_external_data_stats()
            }

        entity_types = {}
        for entity in self.current_kg.entities.values():
            etype = entity.entity_type.value
            entity_types[etype] = entity_types.get(etype, 0) + 1

        relation_types = {}
        for relation in self.current_kg.relations.values():
            rtype = relation.relation_type.value
            relation_types[rtype] = relation_types.get(rtype, 0) + 1

        return {
            "entity_count": len(self.current_kg.entities),
            "relation_count": len(self.current_kg.relations),
            "entity_types": entity_types,
            "relation_types": relation_types,
            "external_data": self.get_external_data_stats()
        }


# ============================================================
# 便捷函数
# ============================================================

def create_knowledge_graph(name: str = "default") -> KnowledgeGraphManager:
    """创建知识图谱管理器"""
    return KnowledgeGraphManager({"name": name})


# 导出
__all__ = [
    'KnowledgeGraphManager', 'create_knowledge_graph',
    # 外部数据源
    'get_external_data_hub', 'get_emission_registry', 'get_integrator',
    'get_env_background_data', 'get_env_integrator',
    'get_monitoring_center', 'get_entity_linker', 'get_fusion_engine'
]
