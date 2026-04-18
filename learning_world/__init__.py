"""
学习世界 - Knowledge Navigation System
知识导航系统模块

从"问答机"到"导航仪"的转变
"""

__version__ = "1.0.0"
__author__ = "Hermes Team"

# 导入主要组件
from .models import (
    TagType,
    KnowledgeTag,
    Reference,
    LearningResponse,
    ExplorationPath,
    KnowledgeNode,
    LearningSession,
    LearningProfile,
    KnowledgeGraph,
    UserProfileManager,
)

from .core import (
    TagGenerator,
    KnowledgeEngine,
    NavigationEngine,
)

from .ui import (
    LearningBrowser,
    TagClickBridge,
)

# 导入工具函数
from .utils import config

__all__ = [
    # 版本
    "__version__",
    
    # 模型
    "TagType",
    "KnowledgeTag",
    "Reference",
    "LearningResponse",
    "ExplorationPath",
    "KnowledgeNode",
    "LearningSession",
    "LearningProfile",
    "KnowledgeGraph",
    "UserProfileManager",
    
    # 核心
    "TagGenerator",
    "KnowledgeEngine",
    "NavigationEngine",
    
    # UI
    "LearningBrowser",
    "TagClickBridge",
    
    # 工具
    "config",
]


def create_learning_browser(
    llm_callback=None,
    model_name="qwen2.5:7b",
    user_profile_db=None,
) -> LearningBrowser:
    """
    创建学习浏览器实例
    
    Args:
        llm_callback: LLM 调用回调，签名: (prompt: str) -> str
        model_name: 使用的模型名
        user_profile_db: 用户画像数据库路径
        
    Returns:
        LearningBrowser 实例
    """
    # 初始化用户画像管理器
    profile_manager = None
    if user_profile_db:
        profile_manager = UserProfileManager(user_profile_db)
        profile_manager.load()
    
    # 初始化引擎
    tag_generator = TagGenerator()
    knowledge_engine = KnowledgeEngine(
        llm_callback=llm_callback,
        tag_generator=tag_generator,
        model_name=model_name,
    )
    navigation_engine = NavigationEngine(
        knowledge_engine=knowledge_engine,
        user_profile_manager=profile_manager,
    )
    
    # 创建浏览器
    browser = LearningBrowser(navigation_engine=navigation_engine)
    
    return browser


class LearningWorld:
    """
    学习世界主类
    
    提供统一的接口管理学习世界的各个组件
    """
    
    def __init__(
        self,
        llm_callback=None,
        model_name="qwen2.5:7b",
        profile_db_path=None,
    ):
        self.llm_callback = llm_callback
        self.model_name = model_name
        
        # 初始化用户画像
        self.profile_manager = UserProfileManager(profile_db_path)
        self.profile_manager.load()
        
        # 初始化引擎
        self.tag_generator = TagGenerator()
        self.knowledge_engine = KnowledgeEngine(
            llm_callback=self._wrap_llm_callback(),
            tag_generator=self.tag_generator,
            model_name=model_name,
        )
        self.navigation_engine = NavigationEngine(
            knowledge_engine=self.knowledge_engine,
            user_profile_manager=self.profile_manager,
        )
        
        # 浏览器（延迟初始化）
        self._browser = None
    
    def _wrap_llm_callback(self):
        """包装 LLM 回调，添加用户画像"""
        if not self.llm_callback:
            return lambda p: "请先配置 LLM 回调"
        
        def wrapped(prompt: str) -> str:
            # 在提示词中添加用户画像信息
            profile = self.profile_manager.get_profile()
            if profile.interests:
                # 这个简化的实现直接使用回调
                return self.llm_callback(prompt)
            return self.llm_callback(prompt)
        
        return wrapped
    
    def get_browser(self) -> LearningBrowser:
        """获取浏览器实例"""
        if self._browser is None:
            self._browser = LearningBrowser(
                navigation_engine=self.navigation_engine
            )
        return self._browser
    
    async def explore(self, query: str) -> LearningResponse:
        """
        开始探索
        
        Args:
            query: 探索主题
            
        Returns:
            LearningResponse
        """
        # 开始新会话
        self.navigation_engine.start_new_session(query)
        
        # 生成响应
        response = await self.knowledge_engine.generate_response(
            query=query,
            user_profile=self.profile_manager.get_profile().to_dict(),
        )
        
        return response
    
    async def explore_by_tag(self, tag: KnowledgeTag) -> LearningResponse:
        """
        通过标签继续探索
        
        Args:
            tag: 点击的标签
            
        Returns:
            LearningResponse
        """
        response = await self.navigation_engine.navigate_by_tag(
            current_query=self.navigation_engine.get_current_topic(),
            clicked_tag=tag,
            user_profile=self.profile_manager.get_profile().to_dict(),
        )
        
        return response
    
    def get_current_path(self) -> str:
        """获取当前探索路径"""
        return self.navigation_engine.get_full_path()
    
    def get_breadcrumbs(self) -> list:
        """获取面包屑"""
        return self.navigation_engine.get_breadcrumbs()
    
    def get_user_profile(self) -> LearningProfile:
        """获取用户画像"""
        return self.profile_manager.get_profile()
    
    def save_profile(self):
        """保存用户画像"""
        self.profile_manager.save()
