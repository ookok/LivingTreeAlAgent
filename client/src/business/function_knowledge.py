"""
功能模块知识库 - 存储各功能模块信息

功能模块包括：
1. 深度搜索
2. 专家训练
3. 智能写作
4. 项目生成
5. 游戏
6. 电商
7. 内置平台
8. 企业驾驶舱
9. IM

设计目标：
- 为AI提供功能模块的详细信息
- 支持根据用户意图自动匹配模块
- 提供简洁的调用接口
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from .vector_db_integration import get_tool_registry, VectorItem, ItemType


class ModuleCategory(Enum):
    """功能模块分类"""
    SEARCH = "search"
    TRAINING = "training"
    WRITING = "writing"
    PROJECT = "project"
    GAME = "game"
    ECOMMERCE = "ecommerce"
    PLATFORM = "platform"
    ENTERPRISE = "enterprise"
    COMMUNICATION = "communication"
    CODE = "code"
    SCHEDULE = "schedule"
    VIP = "vip"


@dataclass
class CommandHelp:
    """命令帮助信息"""
    command: str
    description: str
    usage: str
    description_en: str = ""
    usage_en: str = ""
    examples: List[str] = field(default_factory=list)
    examples_en: List[str] = field(default_factory=list)
    parameters: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class FunctionModule:
    """功能模块数据结构"""
    id: str
    name: str
    category: ModuleCategory
    description: str
    features: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    usage_scenarios: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    requires_input: bool = False
    command_help: Dict[str, CommandHelp] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "features": self.features,
            "keywords": self.keywords,
            "usage_scenarios": self.usage_scenarios,
            "commands": self.commands,
            "requires_input": self.requires_input
        }
    
    def to_vector_item(self) -> VectorItem:
        """转换为向量数据库项"""
        return VectorItem(
            id=self.id,
            type=ItemType.TOOL,
            name=self.name,
            description=self.description,
            keywords=self.keywords,
            metadata=self.to_dict()
        )


# 功能模块定义
FUNCTION_MODULES = [
    FunctionModule(
        id="deep_search",
        name="深度搜索",
        category=ModuleCategory.SEARCH,
        description="基于向量数据库的智能搜索，支持语义检索、多模态搜索、知识图谱查询",
        features=[
            "语义搜索 - 理解用户意图进行智能匹配",
            "多模态搜索 - 支持文本、图片、音频搜索",
            "知识图谱查询 - 基于图结构的关联搜索",
            "文档检索 - 快速定位相关文档",
            "实时搜索 - 整合外部搜索引擎"
        ],
        keywords=["搜索", "查找", "查询", "检索", "搜索信息", "查找资料"],
        usage_scenarios=[
            "用户说：'帮我查找关于人工智能的资料'",
            "用户说：'搜索项目中的相关代码'",
            "用户说：'查找上周的会议记录'"
        ],
        commands=["/search", "/find", "/lookup"],
        requires_input=True,
        command_help={
            "/search": CommandHelp(
                command="/search",
                description="执行深度搜索，支持语义匹配和多模态检索",
                description_en="Perform deep search with semantic matching and multimodal retrieval",
                usage="/search <关键词>",
                usage_en="/search <keywords>",
                examples=["/search 人工智能", "/search 项目代码", "/search 会议记录"],
                examples_en=["/search artificial intelligence", "/search project code", "/search meeting notes"],
                parameters=[
                    {"name": "关键词", "description": "要搜索的内容"}
                ]
            ),
            "/find": CommandHelp(
                command="/find",
                description="查找文件或信息",
                description_en="Find files or information",
                usage="/find <关键词>",
                usage_en="/find <keywords>",
                examples=["/find report.pdf", "/find 客户资料"],
                examples_en=["/find report.pdf", "/find customer data"],
                parameters=[
                    {"name": "关键词", "description": "要查找的内容"}
                ]
            ),
            "/lookup": CommandHelp(
                command="/lookup",
                description="查询知识库中的信息",
                description_en="Lookup information in knowledge base",
                usage="/lookup <主题>",
                usage_en="/lookup <topic>",
                examples=["/lookup Python教程", "/lookup API文档"],
                examples_en=["/lookup Python tutorial", "/lookup API documentation"],
                parameters=[
                    {"name": "主题", "description": "要查询的主题"}
                ]
            )
        }
    ),
    FunctionModule(
        id="expert_training",
        name="专家训练",
        category=ModuleCategory.TRAINING,
        description="训练AI专家角色，支持自定义知识库、技能训练、角色定制",
        features=[
            "知识库导入 - 上传文档训练专家",
            "技能训练 - 自定义专家能力",
            "角色定制 - 创建专属专家形象",
            "微调优化 - 持续优化专家表现",
            "多模态训练 - 支持文本、图像训练"
        ],
        keywords=["训练", "学习", "教育", "培训", "专家", "导师"],
        usage_scenarios=[
            "用户说：'我想训练一个Python专家'",
            "用户说：'导入这份文档让AI学习'",
            "用户说：'创建一个数据分析专家'"
        ],
        commands=["/train", "/expert", "/teach"],
        requires_input=True,
        command_help={
            "/train": CommandHelp(
                command="/train",
                description="训练AI专家角色",
                description_en="Train AI expert role",
                usage="/train <主题>",
                usage_en="/train <topic>",
                examples=["/train Python编程", "/train 数据分析", "/train 医学知识"],
                examples_en=["/train Python programming", "/train data analysis", "/train medical knowledge"],
                parameters=[
                    {"name": "主题", "description": "要训练的领域或主题"}
                ]
            ),
            "/expert": CommandHelp(
                command="/expert",
                description="切换到专家模式或创建专家角色",
                description_en="Switch to expert mode or create expert role",
                usage="/expert [专家名称]",
                usage_en="/expert [expert_name]",
                examples=["/expert", "/expert Python专家", "/expert 写作专家"],
                examples_en=["/expert", "/expert Python Expert", "/expert Writing Expert"],
                parameters=[
                    {"name": "专家名称", "description": "专家角色名称（可选）"}
                ]
            ),
            "/teach": CommandHelp(
                command="/teach",
                description="向AI传授新知识",
                description_en="Teach AI new knowledge",
                usage="/teach <知识内容>",
                usage_en="/teach <knowledge>",
                examples=["/teach 量子计算基础", "/teach 公司制度"],
                examples_en=["/teach quantum computing basics", "/teach company policies"],
                parameters=[
                    {"name": "知识内容", "description": "要传授的知识"}
                ]
            )
        }
    ),
    FunctionModule(
        id="intelligent_writing",
        name="智能写作",
        category=ModuleCategory.WRITING,
        description="AI辅助写作工具，支持小说创作、文档撰写、文案生成",
        features=[
            "小说创作 - 支持多种题材小说生成",
            "文档撰写 - 自动生成报告、论文",
            "文案生成 - 营销文案、广告语创作",
            "润色优化 - 提升文本质量",
            "多语言支持 - 支持多种语言写作"
        ],
        keywords=["写作", "写文章", "创作", "小说", "文案", "报告", "文档"],
        usage_scenarios=[
            "用户说：'帮我写一本小说'",
            "用户说：'写一份产品报告'",
            "用户说：'帮我润色这篇文章'"
        ],
        commands=["/write", "/novel", "/document", "/essay"],
        requires_input=True,
        command_help={
            "/write": CommandHelp(
                command="/write",
                description="使用AI辅助写作",
                description_en="Use AI assisted writing",
                usage="/write <主题或内容描述>",
                usage_en="/write <topic or content description>",
                examples=["/write 科技文章", "/write 产品介绍", "/write 故事开头"],
                examples_en=["/write tech article", "/write product introduction", "/write story beginning"],
                parameters=[
                    {"name": "主题", "description": "写作主题或内容描述"}
                ]
            ),
            "/novel": CommandHelp(
                command="/novel",
                description="创作小说",
                description_en="Write a novel",
                usage="/novel <题材> [情节]",
                usage_en="/novel <genre> [plot]",
                examples=["/novel 科幻", "/novel 悬疑 神秘失踪案", "/novel 爱情"],
                examples_en=["/novel sci-fi", "/novel mystery disappearance", "/novel romance"],
                parameters=[
                    {"name": "题材", "description": "小说题材"},
                    {"name": "情节", "description": "情节描述（可选）"}
                ]
            ),
            "/document": CommandHelp(
                command="/document",
                description="生成正式文档",
                description_en="Generate formal document",
                usage="/document <类型> <主题>",
                usage_en="/document <type> <topic>",
                examples=["/document 报告 销售分析", "/document 论文 AI发展", "/document 方案 项目规划"],
                examples_en=["/document report sales analysis", "/document paper AI development", "/document proposal project plan"],
                parameters=[
                    {"name": "类型", "description": "文档类型（报告/论文/方案等）"},
                    {"name": "主题", "description": "文档主题"}
                ]
            ),
            "/essay": CommandHelp(
                command="/essay",
                description="写短文或随笔",
                description_en="Write an essay",
                usage="/essay <主题>",
                usage_en="/essay <topic>",
                examples=["/essay 人生感悟", "/essay 读书心得", "/essay 旅行日记"],
                examples_en=["/essay life reflections", "/essay reading notes", "/essay travel diary"],
                parameters=[
                    {"name": "主题", "description": "文章主题"}
                ]
            )
        }
    ),
    FunctionModule(
        id="project_generator",
        name="项目生成",
        category=ModuleCategory.PROJECT,
        description="自动化项目生成工具，支持代码生成、架构设计、项目初始化",
        features=[
            "代码生成 - 根据需求生成代码",
            "架构设计 - 自动设计系统架构",
            "项目初始化 - 创建完整项目结构",
            "技术选型 - 推荐技术栈",
            "文档生成 - 自动生成项目文档"
        ],
        keywords=["项目", "代码", "开发", "编程", "生成", "创建"],
        usage_scenarios=[
            "用户说：'帮我创建一个Web项目'",
            "用户说：'生成一个Python脚本'",
            "用户说：'设计一个系统架构'"
        ],
        commands=["/project", "/generate", "/code", "/create"],
        requires_input=True,
        command_help={
            "/project": CommandHelp(
                command="/project",
                description="创建新项目",
                description_en="Create new project",
                usage="/project <类型> [名称]",
                usage_en="/project <type> [name]",
                examples=["/project web", "/project python 数据分析工具", "/project mobile"],
                examples_en=["/project web", "/project python data analysis tool", "/project mobile"],
                parameters=[
                    {"name": "类型", "description": "项目类型（web/python/mobile等）"}
                ]
            ),
            "/generate": CommandHelp(
                command="/generate",
                description="生成代码",
                description_en="Generate code",
                usage="/generate <语言> <功能>",
                usage_en="/generate <language> <function>",
                examples=["/generate python 爬虫", "/generate javascript 表单验证", "/generate sql 查询"],
                examples_en=["/generate python crawler", "/generate javascript form validation", "/generate sql query"],
                parameters=[
                    {"name": "语言", "description": "编程语言"}
                ]
            ),
            "/code": CommandHelp(
                command="/code",
                description="编写代码",
                description_en="Write code",
                usage="/code <语言> <描述>",
                usage_en="/code <language> <description>",
                examples=["/code python 排序算法", "/code java 单例模式", "/code go API服务"],
                examples_en=["/code python sorting algorithm", "/code java singleton pattern", "/code go API service"],
                parameters=[
                    {"name": "语言", "description": "编程语言"}
                ]
            ),
            "/create": CommandHelp(
                command="/create",
                description="创建文件或项目",
                description_en="Create file or project",
                usage="/create <类型> <名称>",
                usage_en="/create <type> <name>",
                examples=["/create file README.md", "/create folder src", "/create project myapp"],
                examples_en=["/create file README.md", "/create folder src", "/create project myapp"],
                parameters=[
                    {"name": "类型", "description": "类型（file/folder/project）"}
                ]
            )
        }
    ),
    FunctionModule(
        id="game_engine",
        name="游戏",
        category=ModuleCategory.GAME,
        description="内置游戏引擎，支持文字冒险、策略游戏、益智游戏",
        features=[
            "文字冒险 - 交互式故事游戏",
            "策略游戏 - 回合制策略对战",
            "益智游戏 - 解谜、数独等",
            "角色扮演 - 创建角色冒险",
            "游戏编辑器 - 自定义游戏内容"
        ],
        keywords=["游戏", "娱乐", "玩游戏", "冒险", "策略", "益智"],
        usage_scenarios=[
            "用户说：'我想玩游戏'",
            "用户说：'开始一个文字冒险'",
            "用户说：'推荐一个游戏'"
        ],
        commands=["/game", "/play", "/adventure"],
        requires_input=False,
        command_help={
            "/game": CommandHelp(
                command="/game",
                description="打开游戏中心",
                description_en="Open game center",
                usage="/game [游戏名称]",
                usage_en="/game [game_name]",
                examples=["/game", "/game 数独", "/game 文字冒险"],
                examples_en=["/game", "/game sudoku", "/game text adventure"],
                parameters=[
                    {"name": "游戏名称", "description": "游戏名称（可选）"}
                ]
            ),
            "/play": CommandHelp(
                command="/play",
                description="开始游戏",
                description_en="Start game",
                usage="/play <游戏类型>",
                usage_en="/play <game_type>",
                examples=["/play adventure", "/play puzzle", "/play strategy"],
                examples_en=["/play adventure", "/play puzzle", "/play strategy"],
                parameters=[
                    {"name": "游戏类型", "description": "adventure/puzzle/strategy"}
                ]
            ),
            "/adventure": CommandHelp(
                command="/adventure",
                description="开始文字冒险游戏",
                description_en="Start text adventure game",
                usage="/adventure [主题]",
                usage_en="/adventure [theme]",
                examples=["/adventure", "/adventure 神秘森林", "/adventure 太空探索"],
                examples_en=["/adventure", "/adventure mysterious forest", "/adventure space exploration"],
                parameters=[
                    {"name": "主题", "description": "冒险主题（可选）"}
                ]
            )
        }
    ),
    FunctionModule(
        id="ecommerce",
        name="电商",
        category=ModuleCategory.ECOMMERCE,
        description="电商平台集成，支持商品搜索、购物、订单管理",
        features=[
            "商品搜索 - 智能商品推荐",
            "购物车 - 管理选购商品",
            "订单管理 - 查看订单状态",
            "价格对比 - 多平台比价",
            "优惠券 - 领取和使用优惠"
        ],
        keywords=["购物", "商品", "订单", "电商", "买东西", "购物车"],
        usage_scenarios=[
            "用户说：'帮我搜索手机'",
            "用户说：'查看我的订单'",
            "用户说：'对比价格'"
        ],
        commands=["/shop", "/buy", "/order"],
        requires_input=True,
        command_help={
            "/shop": CommandHelp(
                command="/shop",
                description="打开电商购物",
                description_en="Open e-commerce shopping",
                usage="/shop [关键词]",
                usage_en="/shop [keywords]",
                examples=["/shop", "/shop 手机", "/shop 书籍"],
                examples_en=["/shop", "/shop phone", "/shop books"],
                parameters=[
                    {"name": "关键词", "description": "搜索关键词（可选）"}
                ]
            ),
            "/buy": CommandHelp(
                command="/buy",
                description="购买商品",
                description_en="Buy product",
                usage="/buy <商品名称>",
                usage_en="/buy <product_name>",
                examples=["/buy iPhone", "/buy 笔记本电脑"],
                examples_en=["/buy iPhone", "/buy laptop"],
                parameters=[
                    {"name": "商品名称", "description": "要购买的商品"}
                ]
            ),
            "/order": CommandHelp(
                command="/order",
                description="查看订单",
                description_en="View orders",
                usage="/order [状态]",
                usage_en="/order [status]",
                examples=["/order", "/order pending", "/order completed"],
                examples_en=["/order", "/order pending", "/order completed"],
                parameters=[
                    {"name": "状态", "description": "订单状态（可选）"}
                ]
            )
        }
    ),
    FunctionModule(
        id="built_in_platform",
        name="内置平台",
        category=ModuleCategory.PLATFORM,
        description="内置应用平台，包含日历、笔记、待办、文件管理等工具",
        features=[
            "日历 - 日程管理和提醒",
            "笔记 - 记录和整理笔记",
            "待办 - 任务管理",
            "文件管理 - 管理本地文件",
            "书签 - 收藏和管理链接"
        ],
        keywords=["日历", "笔记", "待办", "任务", "文件", "书签"],
        usage_scenarios=[
            "用户说：'创建一个待办事项'",
            "用户说：'记录一条笔记'",
            "用户说：'查看我的日程'"
        ],
        commands=["/calendar", "/note", "/todo", "/file"],
        requires_input=False,
        command_help={
            "/calendar": CommandHelp(
                command="/calendar",
                description="打开日历",
                description_en="Open calendar",
                usage="/calendar [日期]",
                usage_en="/calendar [date]",
                examples=["/calendar", "/calendar 2024-01-15"],
                examples_en=["/calendar", "/calendar 2024-01-15"],
                parameters=[
                    {"name": "日期", "description": "日期（可选，格式YYYY-MM-DD）"}
                ]
            ),
            "/note": CommandHelp(
                command="/note",
                description="创建或查看笔记",
                description_en="Create or view notes",
                usage="/note [内容]",
                usage_en="/note [content]",
                examples=["/note", "/note 会议记录", "/note 待办事项"],
                examples_en=["/note", "/note meeting notes", "/note to-do list"],
                parameters=[
                    {"name": "内容", "description": "笔记内容（可选）"}
                ]
            ),
            "/todo": CommandHelp(
                command="/todo",
                description="管理待办事项",
                description_en="Manage to-do items",
                usage="/todo [add|list|done] [内容]",
                usage_en="/todo [add|list|done] [content]",
                examples=["/todo", "/todo add 完成报告", "/todo done 1"],
                examples_en=["/todo", "/todo add complete report", "/todo done 1"],
                parameters=[
                    {"name": "操作", "description": "add/list/done（可选）"}
                ]
            ),
            "/file": CommandHelp(
                command="/file",
                description="文件管理",
                description_en="File management",
                usage="/file [操作] [路径]",
                usage_en="/file [action] [path]",
                examples=["/file", "/file open report.pdf", "/file list"],
                examples_en=["/file", "/file open report.pdf", "/file list"],
                parameters=[
                    {"name": "操作", "description": "open/list（可选）"}
                ]
            )
        }
    ),
    FunctionModule(
        id="enterprise_cockpit",
        name="企业驾驶舱",
        category=ModuleCategory.ENTERPRISE,
        description="企业级数据可视化和管理控制台",
        features=[
            "数据看板 - 实时数据展示",
            "报表分析 - 生成业务报表",
            "流程管理 - 审批流程处理",
            "团队协作 - 团队任务管理",
            "权限管理 - 用户权限配置"
        ],
        keywords=["企业", "管理", "数据", "报表", "分析", "看板"],
        usage_scenarios=[
            "用户说：'查看销售报表'",
            "用户说：'审批这个流程'",
            "用户说：'查看团队进度'"
        ],
        commands=["/dashboard", "/report", "/enterprise"],
        requires_input=False,
        command_help={
            "/dashboard": CommandHelp(
                command="/dashboard",
                description="打开数据看板",
                description_en="Open dashboard",
                usage="/dashboard [视图]",
                usage_en="/dashboard [view]",
                examples=["/dashboard", "/dashboard sales", "/dashboard finance"],
                examples_en=["/dashboard", "/dashboard sales", "/dashboard finance"],
                parameters=[
                    {"name": "视图", "description": "视图类型（可选）"}
                ]
            ),
            "/report": CommandHelp(
                command="/report",
                description="生成报表",
                description_en="Generate report",
                usage="/report <类型> [时间]",
                usage_en="/report <type> [time]",
                examples=["/report sales monthly", "/report inventory weekly"],
                examples_en=["/report sales monthly", "/report inventory weekly"],
                parameters=[
                    {"name": "类型", "description": "报表类型"}
                ]
            ),
            "/enterprise": CommandHelp(
                command="/enterprise",
                description="企业管理中心",
                description_en="Enterprise management center",
                usage="/enterprise [功能]",
                usage_en="/enterprise [function]",
                examples=["/enterprise", "/enterprise workflow", "/enterprise team"],
                examples_en=["/enterprise", "/enterprise workflow", "/enterprise team"],
                parameters=[
                    {"name": "功能", "description": "功能模块（可选）"}
                ]
            )
        }
    ),
    FunctionModule(
        id="im",
        name="即时通讯",
        category=ModuleCategory.COMMUNICATION,
        description="内置即时通讯工具，支持消息发送、文件分享、群组聊天",
        features=[
            "消息发送 - 文本和多媒体消息",
            "文件分享 - 发送和接收文件",
            "群组聊天 - 创建和管理群组",
            "语音通话 - 语音和视频通话",
            "联系人管理 - 添加和管理联系人"
        ],
        keywords=["聊天", "消息", "通讯", "通话", "联系", "群组"],
        usage_scenarios=[
            "用户说：'发送消息给张三'",
            "用户说：'创建一个群组'",
            "用户说：'发起语音通话'"
        ],
        commands=["/message", "/chat", "/call"],
        requires_input=True,
        command_help={
            "/message": CommandHelp(
                command="/message",
                description="发送消息",
                description_en="Send message",
                usage="/message <联系人> <内容>",
                usage_en="/message <contact> <content>",
                examples=["/message 张三 你好", "/message 团队群 会议通知"],
                examples_en=["/message Zhang San hello", "/message team meeting notice"],
                parameters=[
                    {"name": "联系人", "description": "联系人或群组名称"}
                ]
            ),
            "/chat": CommandHelp(
                command="/chat",
                description="打开聊天窗口",
                description_en="Open chat window",
                usage="/chat [联系人]",
                usage_en="/chat [contact]",
                examples=["/chat", "/chat 李四"],
                examples_en=["/chat", "/chat Li Si"],
                parameters=[
                    {"name": "联系人", "description": "联系人名称（可选）"}
                ]
            ),
            "/call": CommandHelp(
                command="/call",
                description="发起通话",
                description_en="Make call",
                usage="/call <联系人> [类型]",
                usage_en="/call <contact> [type]",
                examples=["/call 张三", "/call 王五 video"],
                examples_en=["/call Zhang San", "/call Wang Wu video"],
                parameters=[
                    {"name": "联系人", "description": "联系人名称"}
                ]
            )
        }
    ),
    FunctionModule(
        id="code_generator",
        name="代码生成",
        category=ModuleCategory.CODE,
        description="根据用户输入生成代码，支持多种编程语言",
        features=[
            "代码生成 - 根据需求描述生成代码",
            "代码优化 - 优化现有代码",
            "代码解释 - 解释代码功能",
            "代码审查 - 检查代码问题",
            "单元测试 - 生成单元测试代码"
        ],
        keywords=["代码", "编程", "生成", "Python", "JavaScript", "Java"],
        usage_scenarios=[
            "用户说：'帮我写一个Python函数'",
            "用户说：'生成一个排序算法'",
            "用户说：'优化这段代码'"
        ],
        commands=["/codegen", "/generate", "/optimize", "/explain", "/review"],
        requires_input=True,
        command_help={
            "/codegen": CommandHelp(
                command="/codegen",
                description="根据需求生成代码",
                description_en="Generate code from requirements",
                usage="/codegen <语言> <需求描述>",
                usage_en="/codegen <language> <requirements>",
                examples=["/codegen python 排序算法", "/codegen javascript 表单验证"],
                examples_en=["/codegen python sorting algorithm", "/codegen javascript form validation"],
                parameters=[
                    {"name": "语言", "description": "编程语言"},
                    {"name": "需求描述", "description": "要实现的功能"}
                ]
            ),
            "/generate": CommandHelp(
                command="/generate",
                description="生成代码",
                description_en="Generate code",
                usage="/generate <语言> <功能>",
                usage_en="/generate <language> <function>",
                examples=["/generate python 爬虫", "/generate sql 查询"],
                examples_en=["/generate python crawler", "/generate sql query"],
                parameters=[
                    {"name": "语言", "description": "编程语言"},
                    {"name": "功能", "description": "要实现的功能"}
                ]
            ),
            "/optimize": CommandHelp(
                command="/optimize",
                description="优化代码",
                description_en="Optimize code",
                usage="/optimize <代码内容>",
                usage_en="/optimize <code>",
                examples=["/optimize def func(): pass"],
                examples_en=["/optimize def func(): pass"],
                parameters=[
                    {"name": "代码内容", "description": "要优化的代码"}
                ]
            ),
            "/explain": CommandHelp(
                command="/explain",
                description="解释代码",
                description_en="Explain code",
                usage="/explain <代码内容>",
                usage_en="/explain <code>",
                examples=["/explain print('Hello')"],
                examples_en=["/explain print('Hello')"],
                parameters=[
                    {"name": "代码内容", "description": "要解释的代码"}
                ]
            ),
            "/review": CommandHelp(
                command="/review",
                description="代码审查",
                description_en="Code review",
                usage="/review <代码内容>",
                usage_en="/review <code>",
                examples=["/review def test(): pass"],
                examples_en=["/review def test(): pass"],
                parameters=[
                    {"name": "代码内容", "description": "要审查的代码"}
                ]
            )
        }
    ),
    FunctionModule(
        id="schedule_task",
        name="定时任务",
        category=ModuleCategory.SCHEDULE,
        description="创建和管理定时任务，支持定时执行脚本、发送提醒等",
        features=[
            "定时任务 - 创建定时执行的任务",
            "重复任务 - 设置重复执行规则",
            "提醒服务 - 设置时间提醒",
            "任务管理 - 查看和管理任务",
            "脚本执行 - 定时执行脚本"
        ],
        keywords=["定时", "任务", "计划", "提醒", "闹钟", "定时执行"],
        usage_scenarios=[
            "用户说：'明天早上8点提醒我'",
            "用户说：'每天定时备份'",
            "用户说：'设置一个定时任务'"
        ],
        commands=["/schedule", "/cron", "/remind", "/task", "/job"],
        requires_input=True,
        command_help={
            "/schedule": CommandHelp(
                command="/schedule",
                description="创建定时任务",
                description_en="Create scheduled task",
                usage="/schedule <时间> <任务>",
                usage_en="/schedule <time> <task>",
                examples=["/schedule 08:00 提醒会议", "/schedule 每天 23:00 备份数据"],
                examples_en=["/schedule 08:00 meeting reminder", "/schedule daily 23:00 backup"],
                parameters=[
                    {"name": "时间", "description": "执行时间"},
                    {"name": "任务", "description": "要执行的任务"}
                ]
            ),
            "/cron": CommandHelp(
                command="/cron",
                description="创建Cron定时任务",
                description_en="Create cron job",
                usage="/cron <表达式> <命令>",
                usage_en="/cron <expression> <command>",
                examples=["/cron 0 8 * * * echo hello", "/cron */5 * * * * refresh"],
                examples_en=["/cron 0 8 * * * echo hello", "/cron */5 * * * * refresh"],
                parameters=[
                    {"name": "表达式", "description": "Cron表达式"},
                    {"name": "命令", "description": "要执行的命令"}
                ]
            ),
            "/remind": CommandHelp(
                command="/remind",
                description="设置提醒",
                description_en="Set reminder",
                usage="/remind <时间> <内容>",
                usage_en="/remind <time> <content>",
                examples=["/remind 明天 开会", "/remind 10分钟后 休息"],
                examples_en=["/remind tomorrow meeting", "/remind 10min break"],
                parameters=[
                    {"name": "时间", "description": "提醒时间"},
                    {"name": "内容", "description": "提醒内容"}
                ]
            ),
            "/task": CommandHelp(
                command="/task",
                description="管理任务",
                description_en="Manage tasks",
                usage="/task [list|add|delete] [参数]",
                usage_en="/task [list|add|delete] [params]",
                examples=["/task list", "/task add 任务内容"],
                examples_en=["/task list", "/task add task content"],
                parameters=[
                    {"name": "操作", "description": "list/add/delete"},
                    {"name": "参数", "description": "任务参数"}
                ]
            ),
            "/job": CommandHelp(
                command="/job",
                description="管理定时任务",
                description_en="Manage cron jobs",
                usage="/job [list|create|delete] [参数]",
                usage_en="/job [list|create|delete] [params]",
                examples=["/job list", "/job create 0 0 * * * backup"],
                examples_en=["/job list", "/job create 0 0 * * * backup"],
                parameters=[
                    {"name": "操作", "description": "list/create/delete"},
                    {"name": "参数", "description": "任务参数"}
                ]
            )
        }
    ),
    FunctionModule(
        id="vip_service",
        name="VIP服务",
        category=ModuleCategory.VIP,
        description="VIP专属服务，支持云存储同步、远程大模型、专家角色下载等",
        features=[
            "云存储 - 知识库和用户资料云端存储",
            "同步服务 - 多设备数据同步",
            "远程大模型 - 使用云端大模型",
            "专家下载 - 下载专家角色和技能",
            "插件市场 - 下载和安装插件",
            "模型下载 - 下载训练好的大模型",
            "VIP充值 - 充值VIP会员"
        ],
        keywords=["VIP", "会员", "充值", "云存储", "同步", "大模型"],
        usage_scenarios=[
            "用户说：'开通VIP会员'",
            "用户说：'同步我的数据'",
            "用户说：'下载专家角色'"
        ],
        commands=["/vip", "/sync", "/upgrade", "/download", "/subscribe"],
        requires_input=False,
        command_help={
            "/vip": CommandHelp(
                command="/vip",
                description="VIP服务管理",
                description_en="VIP service management",
                usage="/vip [status|recharge|benefits]",
                usage_en="/vip [status|recharge|benefits]",
                examples=["/vip", "/vip status", "/vip recharge"],
                examples_en=["/vip", "/vip status", "/vip recharge"],
                parameters=[
                    {"name": "操作", "description": "status/recharge/benefits（可选）"}
                ]
            ),
            "/sync": CommandHelp(
                command="/sync",
                description="同步数据到云端",
                description_en="Sync data to cloud",
                usage="/sync [type]",
                usage_en="/sync [type]",
                examples=["/sync", "/sync knowledge", "/sync profile"],
                examples_en=["/sync", "/sync knowledge", "/sync profile"],
                parameters=[
                    {"name": "类型", "description": "knowledge/profile/skills（可选）"}
                ]
            ),
            "/upgrade": CommandHelp(
                command="/upgrade",
                description="升级VIP会员",
                description_en="Upgrade VIP membership",
                usage="/upgrade [plan]",
                usage_en="/upgrade [plan]",
                examples=["/upgrade", "/upgrade premium", "/upgrade enterprise"],
                examples_en=["/upgrade", "/upgrade premium", "/upgrade enterprise"],
                parameters=[
                    {"name": "套餐", "description": "premium/enterprise（可选）"}
                ]
            ),
            "/download": CommandHelp(
                command="/download",
                description="下载资源",
                description_en="Download resources",
                usage="/download <type> <name>",
                usage_en="/download <type> <name>",
                examples=["/download expert Python专家", "/download model qwen"],
                examples_en=["/download expert Python Expert", "/download model qwen"],
                parameters=[
                    {"name": "类型", "description": "expert/skill/tool/plugin/model"},
                    {"name": "名称", "description": "资源名称"}
                ]
            ),
            "/subscribe": CommandHelp(
                command="/subscribe",
                description="订阅VIP服务",
                description_en="Subscribe VIP service",
                usage="/subscribe [plan]",
                usage_en="/subscribe [plan]",
                examples=["/subscribe", "/subscribe monthly"],
                examples_en=["/subscribe", "/subscribe monthly"],
                parameters=[
                    {"name": "套餐", "description": "monthly/yearly（可选）"}
                ]
            )
        }
    )
]


class FunctionKnowledgeBase:
    """
    功能模块知识库
    
    提供功能模块的查询、匹配和推荐服务。
    """
    
    def __init__(self):
        self._modules = {m.id: m for m in FUNCTION_MODULES}
        self._registry = get_tool_registry()
        self._sync_with_vector_db()
        self._build_command_index()
    
    def _build_command_index(self):
        """构建命令索引"""
        self._command_index = {}
        for module in FUNCTION_MODULES:
            for cmd in module.commands:
                self._command_index[cmd] = module.id
    
    def _sync_with_vector_db(self):
        """同步到向量数据库"""
        try:
            # 检查是否已存在
            existing_ids = [item.id for item in self._registry.get_all_tools()]
            
            # 添加不存在的模块
            for module in FUNCTION_MODULES:
                if module.id not in existing_ids:
                    self._registry.register_tool(
                        name=module.name,
                        description=module.description,
                        keywords=module.keywords,
                        category=module.category.value,
                        features=module.features,
                        commands=module.commands,
                        requires_input=module.requires_input
                    )
        except Exception as e:
            logger.warning(f"同步向量数据库失败: {e}")
    
    def get_module(self, module_id: str) -> Optional[FunctionModule]:
        """获取模块信息"""
        return self._modules.get(module_id)
    
    def get_modules_by_category(self, category: ModuleCategory) -> List[FunctionModule]:
        """按分类获取模块"""
        return [m for m in FUNCTION_MODULES if m.category == category]
    
    def search_modules(self, query: str) -> List[FunctionModule]:
        """搜索相关模块"""
        results = self._registry.recommend_tools(query, top_k=5)
        
        matched_modules = []
        for result in results:
            module = self._modules.get(result.id)
            if module:
                matched_modules.append(module)
        
        return matched_modules
    
    def recommend_module(self, user_input: str) -> Optional[FunctionModule]:
        """根据用户输入推荐模块"""
        # 首先检查命令匹配
        for module in FUNCTION_MODULES:
            for cmd in module.commands:
                if user_input.startswith(cmd):
                    return module
        
        # 然后检查关键词匹配
        for module in FUNCTION_MODULES:
            for keyword in module.keywords:
                if keyword in user_input:
                    return module
        
        # 最后使用向量搜索
        results = self.search_modules(user_input)
        if results:
            return results[0]
        
        return None
    
    def suggest_command(self, user_input: str) -> Optional[str]:
        """根据用户输入建议命令"""
        module = self.recommend_module(user_input)
        if module and module.commands:
            return module.commands[0]
        
        return None
    
    def get_all_modules(self) -> List[FunctionModule]:
        """获取所有模块"""
        return FUNCTION_MODULES
    
    def to_llm_context(self) -> str:
        """转换为LLM可理解的上下文"""
        parts = []
        
        for module in FUNCTION_MODULES:
            parts.append(f"""
## {module.name} ({', '.join(module.commands)})
**描述**: {module.description}
**关键词**: {', '.join(module.keywords)}
**场景**: {'; '.join(module.usage_scenarios[:2])}
            """.strip())
        
        return "\n\n".join(parts)
    
    def get_module_info_for_llm(self, module_id: str) -> str:
        """获取单个模块的详细信息（供LLM使用）"""
        module = self.get_module(module_id)
        if not module:
            return ""
        
        return f"""
模块名称: {module.name}
模块ID: {module.id}
分类: {module.category.value}
描述: {module.description}

功能特性:
{chr(10).join([f"- {f}" for f in module.features])}

使用场景:
{chr(10).join([f"- {s}" for s in module.usage_scenarios])}

调用命令: {', '.join(module.commands)}

是否需要输入: {'是' if module.requires_input else '否'}
        """.strip()
    
    def get_command_help(self, command: str) -> Optional[str]:
        """获取命令帮助信息"""
        # 提取命令部分（去掉参数）
        cmd_part = command.split()[0] if ' ' in command else command
        
        # 查找命令所属模块
        module_id = self._command_index.get(cmd_part)
        if not module_id:
            return None
        
        module = self._modules.get(module_id)
        if not module:
            return None
        
        # 获取命令帮助
        help_info = module.command_help.get(cmd_part)
        if not help_info:
            return None
        
        return self._format_command_help(help_info)
    
    def _format_command_help(self, help_info: CommandHelp) -> str:
        """格式化命令帮助信息（中英文）"""
        parts = [f"## {help_info.command}"]
        
        # 描述（中英文）
        parts.append(f"**描述 / Description**: {help_info.description}")
        if help_info.description_en:
            parts.append(f"                          {help_info.description_en}")
        
        # 用法（中英文）
        parts.append(f"**用法 / Usage**: `{help_info.usage}`")
        if help_info.usage_en:
            parts.append(f"                  `{help_info.usage_en}`")
        
        # 参数
        if help_info.parameters:
            parts.append("\n**参数 / Parameters**:")
            for param in help_info.parameters:
                parts.append(f"- `{param['name']}`: {param['description']}")
        
        # 示例（中英文）
        if help_info.examples:
            parts.append("\n**示例 / Examples**:")
            for i, example in enumerate(help_info.examples):
                en_example = help_info.examples_en[i] if i < len(help_info.examples_en) else ""
                parts.append(f"- `{example}`")
                if en_example:
                    parts.append(f"  `{en_example}`")
        
        return "\n".join(parts)
    
    def get_all_commands(self) -> List[str]:
        """获取所有命令列表"""
        commands = []
        for module in FUNCTION_MODULES:
            commands.extend(module.commands)
        return commands
    
    def suggest_commands(self, query: str) -> List[str]:
        """根据输入建议命令"""
        suggestions = []
        query_lower = query.lower()
        
        for cmd in self.get_all_commands():
            if cmd.lower().startswith(query_lower):
                suggestions.append(cmd)
        
        return suggestions[:10]
    
    def format_all_command_help(self) -> str:
        """格式化所有命令帮助信息（中英文）"""
        parts = ["## 可用命令列表 / Available Commands"]
        
        for module in FUNCTION_MODULES:
            parts.append(f"\n### {module.name}")
            for cmd in module.commands:
                help_info = module.command_help.get(cmd)
                if help_info:
                    en_desc = f" ({help_info.description_en})" if help_info.description_en else ""
                    parts.append(f"- `{cmd}`: {help_info.description}{en_desc}")
        
        return "\n".join(parts)


# 全局实例
_knowledge_base = None

def get_knowledge_base() -> FunctionKnowledgeBase:
    """获取全局知识库实例"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = FunctionKnowledgeBase()
    return _knowledge_base


# 示例使用
if __name__ == "__main__":
    # 创建知识库
    kb = get_knowledge_base()
    
    # 测试推荐
    test_queries = [
        "帮我写一本小说",
        "我想搜索一些信息",
        "创建一个项目",
        "玩游戏"
    ]
    
    for query in test_queries:
        module = kb.recommend_module(query)
        if module:
            print(f"查询: '{query}'")
            print(f"推荐模块: {module.name}")
            print(f"推荐命令: {module.commands[0]}")
            print()
    
    # 测试获取所有模块
    print("所有功能模块:")
    for module in kb.get_all_modules():
        print(f"- {module.name} ({module.category.value})")