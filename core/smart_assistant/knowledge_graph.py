"""
知识图谱管理器

管理应用内部结构知识库：
1. UI页面注册与管理
2. 操作路径注册
3. 路由注册
4. 指引注册
5. 知识查询与检索
"""

import json
import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict
from .models import (
from core.logger import get_logger
logger = get_logger('smart_assistant.knowledge_graph')

    UIPage, UIComponent, ComponentType, 
    OperationPath, OperationStep, Route,
    Guide, GuideStep, GuideLevel
)


class KnowledgeGraph:
    """
    应用知识图谱管理器
    
    维护UI页面、组件、操作路径、路由、指引等知识库
    """
    
    def __init__(self):
        # 页面注册表
        self.pages: Dict[str, UIPage] = {}
        
        # 组件索引: page_id -> {component_id -> component}
        self.components: Dict[str, Dict[str, UIComponent]] = defaultdict(dict)
        
        # 操作路径库
        self.operation_paths: Dict[str, OperationPath] = {}
        
        # 路由注册表
        self.routes: Dict[str, Route] = {}
        self.route_patterns: List[Tuple[str, str]] = []  # (pattern, route_id)
        
        # 指引库
        self.guides: Dict[str, Guide] = {}
        
        # 反向索引
        self._build_indices()
        
        # 统计信息
        self.stats = {
            "total_pages": 0,
            "total_components": 0,
            "total_paths": 0,
            "total_routes": 0,
            "total_guides": 0
        }
    
    def _build_indices(self):
        """构建反向索引以加速查询"""
        # 标签到页面的映射
        self.tag_to_pages: Dict[str, Set[str]] = defaultdict(set)
        
        # 组件ID到页面的映射
        self.component_to_page: Dict[str, str] = {}
        
        # 关键词到页面的映射
        self.keyword_to_pages: Dict[str, Set[str]] = defaultdict(set)
        
        # 关键词到路径的映射
        self.keyword_to_paths: Dict[str, Set[str]] = defaultdict(set)
    
    # ==================== 页面管理 ====================
    
    def register_page(self, page: UIPage) -> bool:
        """
        注册UI页面
        
        Args:
            page: UIPage对象
            
        Returns:
            是否注册成功
        """
        try:
            self.pages[page.id] = page
            self.components[page.id] = {}
            
            # 更新索引
            for tag in page.tags:
                self.tag_to_pages[tag].add(page.id)
            
            # 索引关键词
            self._index_keywords(page)
            
            self.stats["total_pages"] = len(self.pages)
            return True
        except Exception as e:
            logger.info(f"注册页面失败: {e}")
            return False
    
    def register_component(self, page_id: str, component: UIComponent) -> bool:
        """
        注册UI组件
        
        Args:
            page_id: 所属页面ID
            component: UIComponent对象
            
        Returns:
            是否注册成功
        """
        if page_id not in self.pages:
            logger.info(f"页面不存在: {page_id}")
            return False
        
        try:
            self.pages[page_id].add_component(component)
            self.components[page_id][component.id] = component
            self.component_to_page[component.id] = page_id
            
            # 更新索引
            self._index_keywords(component)
            
            self.stats["total_components"] = sum(
                len(c) for c in self.components.values()
            )
            return True
        except Exception as e:
            logger.info(f"注册组件失败: {e}")
            return False
    
    def _index_keywords(self, obj: Any):
        """为页面或组件索引关键词"""
        # 从标签索引
        if hasattr(obj, 'tags'):
            for tag in obj.tags:
                if isinstance(obj, UIPage):
                    self.tag_to_pages[tag].add(obj.id)
                elif isinstance(obj, UIComponent):
                    self.tag_to_pages[tag].add(self.component_to_page.get(obj.id, ""))
        
        # 从标题/描述索引
        text = ""
        if hasattr(obj, 'title'):
            text += obj.title.lower() + " "
        if hasattr(obj, 'label'):
            text += obj.label.lower() + " "
        if hasattr(obj, 'description'):
            text += obj.description.lower() + " "
        
        words = set(re.findall(r'\w+', text))
        for word in words:
            if len(word) >= 2:
                if isinstance(obj, UIPage):
                    self.keyword_to_pages[word].add(obj.id)
                elif isinstance(obj, UIComponent):
                    self.keyword_to_pages[word].add(self.component_to_page.get(obj.id, ""))
    
    # ==================== 操作路径管理 ====================
    
    def register_operation_path(self, path: OperationPath) -> bool:
        """
        注册操作路径
        
        Args:
            path: OperationPath对象
            
        Returns:
            是否注册成功
        """
        try:
            self.operation_paths[path.path_id] = path
            
            # 索引相关查询
            for query in path.related_queries:
                keywords = re.findall(r'\w+', query.lower())
                for keyword in keywords:
                    if len(keyword) >= 2:
                        self.keyword_to_paths[keyword].add(path.path_id)
            
            # 索引标签
            for tag in path.tags:
                self.keyword_to_paths[tag].add(path.path_id)
            
            self.stats["total_paths"] = len(self.operation_paths)
            return True
        except Exception as e:
            logger.info(f"注册操作路径失败: {e}")
            return False
    
    # ==================== 路由管理 ====================
    
    def register_route(self, route: Route) -> bool:
        """
        注册路由
        
        Args:
            route: Route对象
            
        Returns:
            是否注册成功
        """
        try:
            self.routes[route.route_id] = route
            self.route_patterns.append((route.pattern, route.route_id))
            
            # 按模式长度降序排序，匹配时优先匹配更具体的模式
            self.route_patterns.sort(key=lambda x: len(x[0]), reverse=True)
            
            self.stats["total_routes"] = len(self.routes)
            return True
        except Exception as e:
            logger.info(f"注册路由失败: {e}")
            return False
    
    def resolve_route(self, uri: str) -> Optional[Tuple[Route, Dict[str, Any]]]:
        """
        解析URI到路由
        
        Args:
            uri: 统一资源标识符，格式: app://path/to/page?param=value
            
        Returns:
            (Route对象, 解析后的参数字典) 或 None
        """
        if not uri.startswith("app://"):
            uri = "app://" + uri
        
        # 解析路径和查询参数
        if "?" in uri:
            path_part, query_part = uri.split("?", 1)
            query_params = dict(
                param.split("=") for param in query_part.split("&") if "=" in param
            )
        else:
            path_part = uri
            query_params = {}
        
        # 匹配路由模式
        for pattern, route_id in self.route_patterns:
            params = self._match_pattern(path_part, pattern)
            if params is not None:
                route = self.routes[route_id]
                params.update(query_params)
                return route, params
        
        return None
    
    def _match_pattern(self, path: str, pattern: str) -> Optional[Dict[str, str]]:
        """匹配URL模式"""
        # 转换为正则表达式
        regex_pattern = pattern.replace("/", "\\/").replace(".", "\\.")
        regex_pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', regex_pattern)
        
        match = re.match(f"^{regex_pattern}$", path)
        if match:
            return match.groupdict()
        return None
    
    def generate_route_url(self, page_id: str, **params) -> str:
        """生成路由URL"""
        if page_id not in self.pages:
            return ""
        
        page = self.pages[page_id]
        if not page.route_pattern:
            return f"app://{page.path}"
        
        url = page.route_pattern
        for key, value in params.items():
            if "?" in url:
                url += f"&{key}={value}"
            else:
                url += f"?{key}={value}"
        
        return url
    
    # ==================== 指引管理 ====================
    
    def register_guide(self, guide: Guide) -> bool:
        """注册指引"""
        try:
            self.guides[guide.guide_id] = guide
            self.stats["total_guides"] = len(self.guides)
            return True
        except Exception as e:
            logger.info(f"注册指引失败: {e}")
            return False
    
    def find_guide(self, target_page: str = "", target_component: str = "", 
                   tags: List[str] = None) -> List[Guide]:
        """查找指引"""
        results = []
        
        for guide in self.guides.values():
            # 匹配目标页面
            if target_page and guide.target_page != target_page:
                continue
            
            # 匹配目标组件
            if target_component and guide.target_component != target_component:
                continue
            
            # 匹配标签
            if tags:
                if not any(tag in guide.tags for tag in tags):
                    continue
            
            results.append(guide)
        
        # 按指引级别排序
        results.sort(key=lambda g: g.level.value)
        return results
    
    # ==================== 查询接口 ====================
    
    def find_pages(self, query: str, limit: int = 10) -> List[UIPage]:
        """查找页面"""
        keywords = re.findall(r'\w+', query.lower())
        scores = defaultdict(float)
        
        for keyword in keywords:
            # 直接匹配
            for page in self.pages.values():
                if keyword in page.title.lower():
                    scores[page.id] += 3.0
                if keyword in page.description.lower():
                    scores[page.id] += 1.5
                if keyword in page.tags:
                    scores[page.id] += 2.0
            
            # 关键词匹配
            for page_id in self.keyword_to_pages.get(keyword, []):
                scores[page_id] += 1.0
            
            # 标签匹配
            for page_id in self.tag_to_pages.get(keyword, []):
                scores[page_id] += 1.5
        
        # 排序
        sorted_pages = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self.pages[page_id] for page_id, _ in sorted_pages[:limit] if page_id in self.pages]
    
    def find_operation_paths(self, query: str, from_page: str = "", 
                              to_page: str = "") -> List[OperationPath]:
        """查找操作路径"""
        keywords = re.findall(r'\w+', query.lower())
        scores = defaultdict(float)
        
        for keyword in keywords:
            for path in self.operation_paths.values():
                # 起始/目标页面匹配
                if from_page and path.from_page == from_page:
                    scores[path.path_id] += 2.0
                if to_page and path.to_page == to_page:
                    scores[path.path_id] += 2.0
                
                # 名称/描述匹配
                if keyword in path.name.lower():
                    scores[path.path_id] += 2.5
                if keyword in path.description.lower():
                    scores[path.path_id] += 1.5
                
                # 相关查询匹配
                for related_query in path.related_queries:
                    if keyword in related_query.lower():
                        scores[path.path_id] += 1.0
                
                # 标签匹配
                if keyword in path.tags:
                    scores[path.path_id] += 1.0
        
        sorted_paths = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self.operation_paths[path_id] for path_id, _ in sorted_paths[:10] 
                if path_id in self.operation_paths]
    
    def get_page_by_id(self, page_id: str) -> Optional[UIPage]:
        """获取页面"""
        return self.pages.get(page_id)
    
    def get_component(self, page_id: str, component_id: str) -> Optional[UIComponent]:
        """获取组件"""
        return self.components.get(page_id, {}).get(component_id)
    
    def get_all_pages(self) -> List[UIPage]:
        """获取所有页面"""
        return list(self.pages.values())
    
    def get_all_guides(self) -> List[Guide]:
        """获取所有指引"""
        return list(self.guides.values())
    
    # ==================== 统计与导出 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self.stats.update({
            "total_pages": len(self.pages),
            "total_components": sum(len(c) for c in self.components.values()),
            "total_paths": len(self.operation_paths),
            "total_routes": len(self.routes),
            "total_guides": len(self.guides)
        })
        return self.stats.copy()
    
    def export_knowledge_base(self) -> Dict[str, Any]:
        """导出知识库"""
        return {
            "pages": {
                pid: {
                    "title": p.title,
                    "path": p.path,
                    "description": p.description,
                    "tags": p.tags,
                    "components_count": len(self.components.get(pid, {}))
                }
                for pid, p in self.pages.items()
            },
            "operation_paths": {
                pid: {
                    "name": p.name,
                    "from_page": p.from_page,
                    "to_page": p.to_page,
                    "steps_count": len(p.steps),
                    "difficulty": p.difficulty
                }
                for pid, p in self.operation_paths.items()
            },
            "guides": {
                gid: {
                    "name": g.name,
                    "level": g.level.name,
                    "target_page": g.target_page,
                    "steps_count": len(g.steps)
                }
                for gid, g in self.guides.items()
            },
            "stats": self.get_stats()
        }
    
    # ==================== 预置知识 ====================
    
    def load_preset_knowledge(self):
        """加载预设知识库（Hermes Desktop相关）"""
        # 注册页面
        preset_pages = [
            UIPage(
                id="home",
                title="首页",
                path="/home",
                description="应用程序主页面",
                tags=["首页", "主页", "home", "开始"]
            ),
            UIPage(
                id="settings",
                title="设置",
                path="/settings",
                description="应用程序设置页面",
                tags=["设置", "settings", "配置", "偏好"]
            ),
            UIPage(
                id="settings_model",
                title="模型配置",
                path="/settings/model",
                description="AI模型配置页面",
                tags=["模型", "model", "AI", "配置"]
            ),
            UIPage(
                id="settings_api",
                title="API配置",
                path="/settings/api",
                description="API密钥和端点配置",
                tags=["API", "密钥", "endpoint", "配置"]
            ),
            UIPage(
                id="mcp_market",
                title="MCP市场",
                path="/mcp/market",
                description="MCP服务器市场",
                tags=["MCP", "market", "服务器", "插件"]
            ),
            UIPage(
                id="skill_market",
                title="Skill市场",
                path="/skill/market",
                description="Skill插件市场",
                tags=["Skill", "插件", "扩展", "功能"]
            ),
            UIPage(
                id="chat",
                title="对话",
                path="/chat",
                description="AI对话界面",
                tags=["对话", "chat", "聊天", "AI"]
            ),
            UIPage(
                id="knowledge_base",
                title="知识库",
                path="/knowledge",
                description="个人知识库管理",
                tags=["知识", "knowledge", "文档", "资料"]
            ),
        ]
        
        for page in preset_pages:
            self.register_page(page)
        
        # 注册组件
        preset_components = [
            # 首页组件
            UIComponent(
                id="home_search",
                type=ComponentType.INPUT,
                label="搜索框",
                description="全局搜索框",
                tooltip="输入关键词搜索功能"
            ),
            UIComponent(
                id="home_new_chat",
                type=ComponentType.BUTTON,
                label="新建对话",
                description="创建新的对话",
                shortcut="Ctrl+N"
            ),
            
            # 设置页面组件
            UIComponent(
                id="settings_general",
                type=ComponentType.TABS,
                label="通用设置",
                parent_id="settings"
            ),
            UIComponent(
                id="settings_model_tab",
                type=ComponentType.TABS,
                label="模型设置",
                parent_id="settings"
            ),
            UIComponent(
                id="settings_network_tab",
                type=ComponentType.TABS,
                label="网络设置",
                parent_id="settings"
            ),
            
            # 模型配置组件
            UIComponent(
                id="model_provider_dropdown",
                type=ComponentType.DROPDOWN,
                label="模型提供商",
                description="选择AI模型提供商",
                tooltip="支持Ollama、OpenAI、Claude等"
            ),
            UIComponent(
                id="model_name_input",
                type=ComponentType.DROPDOWN,
                label="模型名称",
                description="选择或输入模型名称",
                tooltip="例如: qwen2.5:7b, gpt-4, claude-3"
            ),
            UIComponent(
                id="api_key_input",
                type=ComponentType.INPUT,
                label="API密钥",
                description="输入API密钥",
                tooltip="从服务商获取的API密钥"
            ),
            UIComponent(
                id="api_endpoint_input",
                type=ComponentType.INPUT,
                label="API端点",
                description="API服务器地址",
                tooltip="例如: http://localhost:11434/v1"
            ),
            UIComponent(
                id="model_test_btn",
                type=ComponentType.BUTTON,
                label="测试连接",
                description="测试模型连接",
                shortcut="Ctrl+T"
            ),
            UIComponent(
                id="model_save_btn",
                type=ComponentType.BUTTON,
                label="保存配置",
                description="保存当前配置",
                shortcut="Ctrl+S"
            ),
            
            # MCP市场组件
            UIComponent(
                id="mcp_search",
                type=ComponentType.INPUT,
                label="搜索MCP",
                description="搜索MCP服务器"
            ),
            UIComponent(
                id="mcp_install_btn",
                type=ComponentType.BUTTON,
                label="安装",
                description="安装选中的MCP服务器"
            ),
            UIComponent(
                id="mcp_config_btn",
                type=ComponentType.BUTTON,
                label="配置",
                description="配置已安装的MCP服务器"
            ),
            
            # Skill市场组件
            UIComponent(
                id="skill_search",
                type=ComponentType.INPUT,
                label="搜索Skill",
                description="搜索Skill插件"
            ),
            UIComponent(
                id="skill_install_btn",
                type=ComponentType.BUTTON,
                label="安装",
                description="安装选中的Skill"
            ),
        ]
        
        for component in preset_components:
            # 推断父页面
            if "model" in component.id:
                page_id = "settings_model"
            elif "api" in component.id:
                page_id = "settings_api"
            elif "mcp" in component.id:
                page_id = "mcp_market"
            elif "skill" in component.id:
                page_id = "skill_market"
            elif "home" in component.id:
                page_id = "home"
            elif component.parent_id:
                page_id = component.parent_id
            else:
                page_id = "settings"
            
            self.register_component(page_id, component)
        
        # 注册操作路径
        preset_paths = [
            OperationPath(
                path_id="path_configure_model",
                name="配置AI模型",
                description="配置一个新的AI模型",
                from_page="settings",
                to_page="settings_model",
                steps=[
                    OperationStep(
                        step_id="step1",
                        page_id="settings",
                        component_id="settings_model_tab",
                        action="click",
                        description="点击模型设置标签"
                    ),
                    OperationStep(
                        step_id="step2",
                        page_id="settings_model",
                        component_id="model_provider_dropdown",
                        action="select",
                        description="选择模型提供商"
                    ),
                    OperationStep(
                        step_id="step3",
                        page_id="settings_model",
                        component_id="model_name_input",
                        action="select",
                        description="选择模型名称"
                    ),
                    OperationStep(
                        step_id="step4",
                        page_id="settings_model",
                        component_id="api_key_input",
                        action="input",
                        description="输入API密钥（如果需要）"
                    ),
                    OperationStep(
                        step_id="step5",
                        page_id="settings_model",
                        component_id="model_save_btn",
                        action="click",
                        description="保存配置"
                    )
                ],
                estimated_time=30,
                difficulty="easy",
                related_queries=[
                    "如何配置模型", "怎么添加新模型", "模型设置",
                    "配置AI", "设置模型", "添加AI模型"
                ],
                tags=["配置", "模型", "AI", "设置"]
            ),
            OperationPath(
                path_id="path_install_mcp",
                name="安装MCP服务器",
                description="从市场安装一个MCP服务器",
                from_page="home",
                to_page="mcp_market",
                steps=[
                    OperationStep(
                        step_id="step1",
                        page_id="home",
                        component_id="home_new_chat",
                        action="click",
                        description="点击新建对话"
                    ),
                    OperationStep(
                        step_id="step2",
                        page_id="mcp_market",
                        component_id="mcp_search",
                        action="input",
                        description="搜索MCP服务器"
                    ),
                    OperationStep(
                        step_id="step3",
                        page_id="mcp_market",
                        component_id="mcp_install_btn",
                        action="click",
                        description="点击安装"
                    )
                ],
                estimated_time=60,
                difficulty="medium",
                related_queries=[
                    "如何安装MCP", "MCP服务器安装", "添加MCP",
                    "MCP插件", "安装插件"
                ],
                tags=["MCP", "安装", "插件", "服务器"]
            ),
        ]
        
        for path in preset_paths:
            self.register_operation_path(path)
        
        # 注册路由
        preset_routes = [
            Route(
                route_id="route_home",
                pattern="app://home",
                page_id="home"
            ),
            Route(
                route_id="route_settings",
                pattern="app://settings",
                page_id="settings"
            ),
            Route(
                route_id="route_settings_model",
                pattern="app://settings/model",
                page_id="settings_model"
            ),
            Route(
                route_id="route_settings_api",
                pattern="app://settings/api",
                page_id="settings_api"
            ),
            Route(
                route_id="route_mcp_market",
                pattern="app://mcp/market",
                page_id="mcp_market"
            ),
            Route(
                route_id="route_skill_market",
                pattern="app://skill/market",
                page_id="skill_market"
            ),
        ]
        
        for route in preset_routes:
            self.register_route(route)
        
        # 注册指引
        preset_guides = [
            Guide(
                guide_id="guide_first_setup",
                name="首次设置向导",
                description="帮助新用户完成首次设置",
                level=GuideLevel.INTERACTIVE,
                target_page="settings_model",
                steps=[
                    GuideStep(
                        step_number=1,
                        page_id="settings",
                        component_id="settings_model_tab",
                        instruction="点击左侧的「模型设置」标签开始配置您的AI模型",
                        highlight=True,
                        animation="pulse"
                    ),
                    GuideStep(
                        step_number=2,
                        page_id="settings_model",
                        component_id="model_provider_dropdown",
                        instruction="从下拉菜单中选择您想使用的AI服务提供商",
                        highlight=True,
                        animation="arrow"
                    ),
                    GuideStep(
                        step_number=3,
                        page_id="settings_model",
                        component_id="model_name_input",
                        instruction="选择您想要使用的具体模型",
                        highlight=True,
                        animation="pulse",
                        tips="如果列表中没有您想要的模型，可以直接输入模型名称"
                    ),
                    GuideStep(
                        step_number=4,
                        page_id="settings_model",
                        component_id="api_key_input",
                        instruction="如果需要API密钥，请在此输入",
                        highlight=True,
                        tips="API密钥会安全存储，不会被分享"
                    ),
                    GuideStep(
                        step_number=5,
                        page_id="settings_model",
                        component_id="model_test_btn",
                        instruction="点击「测试连接」验证配置是否正确",
                        highlight=True,
                        animation="circle"
                    )
                ],
                tags=["新手", "首次", "设置", "配置"]
            ),
        ]
        
        for guide in preset_guides:
            self.register_guide(guide)


# 单例
_knowledge_graph_instance = None

def get_knowledge_graph() -> KnowledgeGraph:
    """获取知识图谱单例"""
    global _knowledge_graph_instance
    if _knowledge_graph_instance is None:
        _knowledge_graph_instance = KnowledgeGraph()
        _knowledge_graph_instance.load_preset_knowledge()
    return _knowledge_graph_instance
