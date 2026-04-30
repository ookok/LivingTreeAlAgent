"""
Registrar - 统一注册入口

负责注册所有已实现的工具模块。

遵循自我进化原则：
- 支持延迟加载
- 支持动态注册
- 支持自动发现新工具
"""

from loguru import logger


def register_all_tools():
    """注册所有已实现的工具模块"""
    logger.info("开始注册所有工具...")
    
    registry = _get_registry()
    
    # 1. 注册网络与搜索工具
    _register_network_tools(registry)
    
    # 2. 注册文档处理工具
    _register_document_tools(registry)
    
    # 3. 注册数据存储与检索工具
    _register_database_tools(registry)
    
    # 4. 注册任务与流程工具
    _register_task_tools(registry)
    
    # 5. 注册学习与进化工具
    _register_learning_tools(registry)
    
    # 6. 注册地理空间工具
    _register_geo_tools(registry)
    
    # 7. 注册计算模拟工具
    _register_simulation_tools(registry)
    
    # 8. 注册文本处理工具
    _register_text_tools(registry)
    
    stats = registry.get_stats()
    logger.info(f"工具注册完成，共 {stats['total_tools']} 个工具")
    logger.info(f"工具类别分布: {stats['categories']}")


def _get_registry():
    """获取 ToolRegistry 实例"""
    from .tool_registry import ToolRegistry
    return ToolRegistry.get_instance()


def _register_network_tools(registry):
    """注册网络与搜索工具"""
    try:
        from business.web_crawler.engine import ScraplingEngine
        from .tool_registry import ToolDefinition
        
        # 注册网页爬虫工具
        crawler = ScraplingEngine()
        registry.register(ToolDefinition(
            name="web_crawler",
            description="网页内容提取（支持自适应解析、反爬绕过、并发爬取）",
            handler=crawler.extract,
            parameters={"url": "str", "selector": "str", "output_format": "str"},
            returns="CrawResult",
            category="network"
        ))
    except Exception as e:
        logger.warning(f"注册网络工具失败: {e}")


def _register_document_tools(registry):
    """注册文档处理工具"""
    try:
        from business.bilingual_doc.document_parser import DocumentParser
        from .tool_registry import ToolDefinition
        
        # 注册文档解析工具
        parser = DocumentParser()
        registry.register(ToolDefinition(
            name="document_parser",
            description="文档解析（支持 TXT/DOCX/PDF）",
            handler=parser.parse,
            parameters={"file_path": "str", "output_format": "str"},
            returns="ParsedDocument",
            category="document"
        ))
        
        # 注册 Markdown 转换工具
        try:
            from business.tools.markdown_tool.markdown_converter import MarkdownConverter
            converter = MarkdownConverter()
            registry.register(ToolDefinition(
                name="markdown_converter",
                description="将 HTML/PDF/DOCX 转换为 Markdown 格式",
                handler=converter.convert,
                parameters={"input_path": "str", "output_format": "str"},
                returns="ToolResult",
                category="document"
            ))
        except ImportError:
            logger.info("Markdown 转换工具未安装，跳过注册")
    except Exception as e:
        logger.warning(f"注册文档工具失败: {e}")


def _register_database_tools(registry):
    """注册数据存储与检索工具"""
    try:
        from business.knowledge_vector_db import VectorDatabase
        from business.knowledge_graph import KnowledgeGraph
        from .tool_registry import ToolDefinition
        
        # 注册向量数据库工具
        vdb = VectorDatabase()
        registry.register(ToolDefinition(
            name="vector_database",
            description="向量数据库（支持 Chroma/FAISS/memory）",
            handler=vdb.query,
            parameters={"query": "str", "top_k": "int"},
            returns="List[Document]",
            category="database"
        ))
        
        # 注册知识图谱工具
        kg = KnowledgeGraph()
        registry.register(ToolDefinition(
            name="knowledge_graph",
            description="知识图谱（实体-关系建模与查询）",
            handler=kg.query,
            parameters={"query": "str"},
            returns="List[Entity]",
            category="database"
        ))
    except Exception as e:
        logger.warning(f"注册数据库工具失败: {e}")


def _register_task_tools(registry):
    """注册任务与流程工具"""
    try:
        from business.task_decomposer import TaskDecomposer
        from business.task_queue import TaskQueue
        from .tool_registry import ToolDefinition
        
        # 注册任务分解工具
        decomposer = TaskDecomposer()
        registry.register(ToolDefinition(
            name="task_decomposer",
            description="任务分解（分析/设计/写作类任务模板）",
            handler=decomposer.decompose,
            parameters={"task": "str", "task_type": "str"},
            returns="DecomposedTask",
            category="task"
        ))
        
        # 注册任务队列工具
        queue = TaskQueue()
        registry.register(ToolDefinition(
            name="task_queue",
            description="任务队列（FIFO + 优先级队列）",
            handler=queue.submit_task,
            parameters={"task": "dict", "priority": "str"},
            returns="TaskResult",
            category="task"
        ))
    except Exception as e:
        logger.warning(f"注册任务工具失败: {e}")


def _register_learning_tools(registry):
    """注册学习与进化工具"""
    try:
        from business.expert_learning import ExpertGuidedLearningSystem
        from business.skill_evolution import SkillEvolutionAgent
        from .tool_registry import ToolDefinition
        
        # 注册专家学习工具
        expert_learning = ExpertGuidedLearningSystem()
        registry.register(ToolDefinition(
            name="expert_learning",
            description="专家学习系统（三层学习架构）",
            handler=expert_learning.learn,
            parameters={"topic": "str", "data": "list"},
            returns="LearningResult",
            category="learning"
        ))
        
        # 注册技能进化工具
        skill_evolution = SkillEvolutionAgent()
        registry.register(ToolDefinition(
            name="skill_evolution",
            description="技能进化（L0-L4 分层记忆系统）",
            handler=skill_evolution.evolve,
            parameters={"skill": "str", "experience": "dict"},
            returns="EvolutionResult",
            category="learning"
        ))
    except Exception as e:
        logger.warning(f"注册学习工具失败: {e}")


def _register_geo_tools(registry):
    """注册地理空间工具"""
    try:
        from .tool_registry import ToolDefinition
        
        # 注册距离计算工具
        try:
            from business.tools.distance_calculator import DistanceCalculator
            calculator = DistanceCalculator()
            registry.register(ToolDefinition(
                name="distance_calculator",
                description="距离计算（Haversine 公式）",
                handler=calculator.calculate,
                parameters={"lat1": "float", "lon1": "float", "lat2": "float", "lon2": "float"},
                returns="float",
                category="geo"
            ))
        except ImportError:
            logger.info("距离计算工具未安装，跳过注册")
        
        # 注册高程数据工具
        try:
            from business.tools.elevation_tool import ElevationTool
            elevation = ElevationTool()
            registry.register(ToolDefinition(
                name="elevation_tool",
                description="高程数据获取（SRTM/GTOPO30）",
                handler=elevation.get_elevation,
                parameters={"lat": "float", "lon": "float"},
                returns="float",
                category="geo"
            ))
        except ImportError:
            logger.info("高程数据工具未安装，跳过注册")
        
        # 注册地图 API 工具
        try:
            from business.tools.map_api_tool import MapAPITool
            map_api = MapAPITool()
            registry.register(ToolDefinition(
                name="map_api_tool",
                description="地图 API（高德/天地图）",
                handler=map_api.geocode,
                parameters={"address": "str"},
                returns="GeoResult",
                category="geo"
            ))
        except ImportError:
            logger.info("地图 API 工具未安装，跳过注册")
    except Exception as e:
        logger.warning(f"注册地理工具失败: {e}")


def _register_simulation_tools(registry):
    """注册计算模拟工具"""
    try:
        from .tool_registry import ToolDefinition
        
        # 注册大气扩散模型工具
        try:
            from business.tools.aermod_tool import AERMODTool
            aermod = AERMODTool()
            registry.register(ToolDefinition(
                name="aermod_tool",
                description="AERMOD 大气扩散模型",
                handler=aermod.run,
                parameters={"input_file": "str", "output_file": "str"},
                returns="SimulationResult",
                category="simulation"
            ))
        except ImportError:
            logger.info("AERMOD 工具未安装，跳过注册")
    except Exception as e:
        logger.warning(f"注册模拟工具失败: {e}")


def _register_text_tools(registry):
    """注册文本处理工具"""
    try:
        from business.tools.text_correction_tool import TextCorrectionTool
        from .tool_registry import ToolDefinition
        
        # 注册错别字纠正工具
        corrector = TextCorrectionTool()
        registry.register(ToolDefinition(
            name="text_correction",
            description="错别字纠正（上下文感知）",
            handler=corrector.correct,
            parameters={"text": "str", "context": "str"},
            returns="CorrectionResult",
            category="text"
        ))
    except Exception as e:
        logger.warning(f"注册文本工具失败: {e}")


def register_tool(tool_class):
    """
    装饰器：注册单个工具
    
    Usage:
        @register_tool
        class MyTool(BaseTool):
            ...
    """
    def wrapper(cls):
        instance = cls()
        instance.register()
        return cls
    return wrapper