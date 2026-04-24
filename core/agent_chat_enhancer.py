"""
Agent Chat 增强模块 (通用版)
===========================

将 AI OS 的意图识别、Query 压缩、上下文处理等功能集成到 AgentChat

功能：
1. 通用意图识别 - 覆盖对话、推理、操作、创作等 12+ 种场景
2. Query 压缩 - 使用 QueryCompressor 压缩长查询
3. 上下文管理 - 使用 UnifiedContext 智能管理对话上下文
4. 流式增强 - 集成 StreamingOutputWidget 展示思考过程

设计原则：
- 通用优先：不仅支持代码，也支持日常对话、推理、操作等
- 轻量快速：意图识别使用关键词+模式匹配，无额外 LLM 调用
- 可扩展：易于添加新的意图类型和处理逻辑
"""

from typing import Optional, Callable, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import re
import hashlib

# Intent Engine
try:
    from core.intent_engine import IntentEngine, Intent, IntentType
    INTENT_ENGINE_AVAILABLE = True
except ImportError:
    INTENT_ENGINE_AVAILABLE = False
    IntentEngine = None
    Intent = None
    IntentType = None

# 代码签名化（延迟导入，避免循环依赖）
CODE_SIGNER_AVAILABLE = False
CodeSigner = None
signaturize_code = None
LayeredContextBuilder = None
SymbolIndex = None
IncrementalContextManager = None
ContextLevel = None

# 尝试直接导入（不通过 core 包）
try:
    import importlib.util
    spec = importlib.util.find_spec("core.long_context.code_signer")
    if spec:
        from core.long_context import code_signer as _cs_mod
        CodeSigner = getattr(_cs_mod, 'CodeSigner', None)
        signaturize_code = getattr(_cs_mod, 'signaturize_code', None)
    
    spec2 = importlib.util.find_spec("core.long_context.layered_context_pyramid")
    if spec2:
        from core.long_context import layered_context_pyramid as _lcp_mod
        LayeredContextBuilder = getattr(_lcp_mod, 'LayeredContextBuilder', None)
        SymbolIndex = getattr(_lcp_mod, 'SymbolIndex', None)
        IncrementalContextManager = getattr(_lcp_mod, 'IncrementalContextManager', None)
        ContextLevel = getattr(_lcp_mod, 'ContextLevel', None)
    
    if CodeSigner and LayeredContextBuilder:
        CODE_SIGNER_AVAILABLE = True
except Exception:
    pass

# 代码澄清器
CODE_CLARIFIER_AVAILABLE = False
CodeClarifier = None

try:
    import importlib.util
    spec3 = importlib.util.find_spec("core.smart_writing.code_clarifier")
    if spec3:
        from core.smart_writing import code_clarifier as _cc_mod
        CodeClarifier = getattr(_cc_mod, 'CodeClarifier', None)
        CODE_CLARIFIER_AVAILABLE = True
except Exception:
    pass

# IDE 上下文注入器
IDE_CONTEXT_INJECTOR_AVAILABLE = False
IDEContextInjector = None

try:
    import importlib.util
    spec4 = importlib.util.find_spec("core.smart_writing.ide_context_injector")
    if spec4:
        from core.smart_writing import ide_context_injector as _ici_mod
        IDEContextInjector = getattr(_ici_mod, 'IDEContextInjector', None)
        IDE_CONTEXT_INJECTOR_AVAILABLE = True
except Exception:
    pass

# 尝试导入 PyQt6 组件（可选）
try:
    from PyQt6.QtWidgets import QWidget
    from PyQt6.QtCore import QObject, pyqtSignal, QThread
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QObject = object


# ============== 通用意图类型 ==============

class ChatIntent(Enum):
    """Chat 意图类型（通用设计）"""
    
    # === 对话类 ===
    CHITCHAT = "chitchat"                # 闲聊、寒暄
    GREETING = "greeting"                # 问候
    QUESTION = "question"                # 问答
    
    # === 推理类 ===
    REASONING = "reasoning"              # 逻辑推理
    MATHEMATICS = "mathematics"          # 数学计算
    ANALYSIS = "analysis"                # 分析
    
    # === 任务类 ===
    CODE_GENERATION = "code_generation"   # 代码生成
    CODE_REVIEW = "code_review"          # 代码审查
    DEBUGGING = "debugging"             # 调试
    FILE_OPERATION = "file_operation"   # 文件操作
    TASK_EXECUTION = "task_execution"   # 任务执行
    
    # === 创作类 ===
    WRITING = "writing"                  # 写作
    TRANSLATION = "translation"         # 翻译
    SUMMARIZATION = "summarization"     # 摘要
    CREATIVE = "creative"               # 创意
    
    # === 知识类 ===
    KNOWLEDGE_QUERY = "knowledge_query"  # 知识查询
    SEARCH = "search"                   # 搜索
    
    # === 其他 ===
    CALCULATION = "calculation"         # 计算
    UNKNOWN = "unknown"                  # 未知


# ============== 场景分类 ==============

class IntentCategory(Enum):
    """意图分类"""
    CONVERSATION = "conversation"    # 对话类
    REASONING = "reasoning"          # 推理类
    TASK = "task"                   # 任务类
    CREATION = "creation"           # 创作类
    KNOWLEDGE = "knowledge"         # 知识类
    OTHER = "other"                # 其他


# ============== 数据结构 ==============

@dataclass
class IntentAnalysis:
    """意图分析结果"""
    intent: ChatIntent
    confidence: float              # 置信度 0-1
    category: IntentCategory       # 场景分类
    entities: Dict[str, Any] = field(default_factory=dict)  # 提取的实体
    suggested_model: str = "auto"  # 建议模型 L0/L1/L3/L4/auto
    need_tools: List[str] = field(default_factory=list)       # 需要的工具
    need_knowledge: bool = False   # 是否需要知识库
    need_deep_search: bool = False # 是否需要深度搜索
    language: str = ""            # 检测到的语言
    priority: int = 0             # 优先级 (数字越大优先级越高)
    
    # === 新增：回答稳定性分析 ===
    answer_stability: float = 0.5  # 回答稳定性 0-1
    is_cacheable: bool = False     # 是否可缓存
    cache_value: float = 0.0      # 缓存价值 0-1
    needs_realtime: bool = False   # 是否需要实时数据


@dataclass
class ChatContext:
    """对话上下文"""
    session_id: str
    user_id: str = ""
    topic: str = ""                # 当前话题
    intents: List[ChatIntent] = field(default_factory=list)   # 历史意图
    variables: Dict[str, Any] = field(default_factory=dict)  # 变量存储
    last_intent: Optional[ChatIntent] = None
    message_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    
    # 对话质量跟踪
    followup_count: int = 0        # 连续追问次数
    topic_switch_count: int = 0    # 话题切换次数


# ============== 通用意图识别器 ==============

class ChatIntentClassifier:
    """
    Chat 意图分类器（通用版）
    
    基于规则 + 关键词匹配的轻量级意图识别
    覆盖：对话、推理、任务、创作、知识等场景
    
    设计原则：
    - 优先级匹配：多个意图时选择最高优先级
    - 上下文感知：结合上下文提高准确度
    - 轻量快速：无额外 LLM 调用
    """
    
    # 意图定义：模式、权重、优先级
    INTENT_DEFINITIONS = {
        # === 对话类 ===
        ChatIntent.GREETING: {
            "patterns": [
                r'^你好', r'^您好', r'^hi\b', r'^hello\b', r'^hey\b', r'^嗨',
                r'^早上好', r'^下午好', r'^晚上好', r'^hi,', r'hello,',
                r'在吗', r'在不在', r'有人吗', r'你好啊', r'好久不见',
            ],
            "priority": 1,
            "category": IntentCategory.CONVERSATION,
            "model": "l1",
            "followup_templates": [
                "有什么我可以帮您的吗？",
                "今天想聊聊什么？",
            ],
        },
        ChatIntent.CHITCHAT: {
            "patterns": [
                r'今天天气', r'周末', r'心情', r'无聊', r'没事', r'随便',
                r'聊聊', r'吹牛', r'扯淡', r'唠嗑',
                r'吃什么', r'怎么样', r'好不好',
            ],
            "priority": 2,
            "category": IntentCategory.CONVERSATION,
            "model": "l1",
            "followup_templates": [
                "最近有什么感兴趣的话题吗？",
                "想深入聊聊哪个方面？",
            ],
        },
        ChatIntent.QUESTION: {
            "patterns": [
                r'^what\b', r'^how\b', r'^why\b', r'^when\b', r'^where\b', r'^who\b',
                r'^是什么', r'^为什么', r'^怎么办', r'^如何',
                r'是什么[？?。]?$', r'为什么[？?。]?$', r'怎么做[？?。]?$', r'怎样[？?。]?$', r'如何[？?。]?$',
                r'[？?]$', r'[？?] ', r'请问', r'问一下', r'想问一下',
                r'有哪些', r'有什么',
            ],
            "priority": 3,
            "category": IntentCategory.CONVERSATION,
            "model": "l1",
            "followup_templates": [
                "需要我详细解释一下吗？",
                "还有其他方面想了解吗？",
                "这个回答对您有帮助吗？",
            ],
        },
        
        # === 推理类 ===
        ChatIntent.REASONING: {
            "patterns": [
                r'推理', r'逻辑', r'思考', r'推断',
                r'如果.*就', r'因为.*所以', r'所以.*因此',
                r'reason', r'logic', r'infer', r'assume',
                r'假设', r'假如', r'假如', r'证明',
            ],
            "priority": 6,  # 提高优先级
            "category": IntentCategory.REASONING,
            "model": "l3",
            "followup_templates": [
                "需要我进一步推导这个结论吗？",
                "还有其他假设条件吗？",
                "想听听更深入的分析吗？",
            ],
        },
        ChatIntent.MATHEMATICS: {
            "patterns": [
                r'\d+\s*[\+\-\*/\^]\s*\d+', r'\d+\s*\^\s*\d+',  # 数字运算优先
                r'等于', r'加减乘除', r'平方', r'开方',
                r'求解', r'方程', r'微积分',
                r'calculate', r'compute', r'solve', r'equation',
                r'概率', r'统计', r'排列组合', r'矩阵',
                r'计算.*\d+', r'\d+.*计算',  # 包含数字的计算
            ],
            "priority": 5,
            "category": IntentCategory.REASONING,
            "model": "l0",
            "followup_templates": [
                "需要看详细计算过程吗？",
                "还有其他计算需要我帮忙吗？",
            ],
        },
        ChatIntent.ANALYSIS: {
            "patterns": [
                r'分析', r'对比', r'比较', r'评估', r'判断',
                r'analyze', r'compare', r'evaluate', r'assess',
                r'优缺点', r'利弊', r'优势劣势', r'可行性'
            ],
            "priority": 4,
            "category": IntentCategory.REASONING,
            "model": "l3",
            "followup_templates": [
                "您更关注哪个方面？",
                "需要我深入分析某个点吗？",
                "这个分析对您的决策有帮助吗？",
            ],
        },
        
        # === 任务类 ===
        ChatIntent.CODE_GENERATION: {
            "patterns": [
                r'写.*代码', r'生成.*代码', r'创建.*函数', r'实现.*代码',
                r'编写.*代码', r'帮我.*写.*函数', r'帮我.*写.*代码',
                r'code', r'generate', r'implement',
                r'def\s+\w+', r'function\s+\w+', r'class\s+\w+',
                r'脚本', r'程序',
            ],
            "priority": 7,  # 提高优先级
            "category": IntentCategory.TASK,
            "model": "l4",
            "tools": ["code_generator"],
            "followup_templates": [
                "需要我解释这段代码的工作原理吗？",
                "需要添加单元测试吗？",
                "需要我优化这段代码的性能吗？",
                "还有其他功能需要实现吗？",
            ],
        },
        ChatIntent.CODE_REVIEW: {
            "patterns": [
                r'审查代码', r'检查代码', r'review', r'优化代码',
                r'代码审查', r'代码检查', r'看看.*代码',
                r'代码.*问题', r'代码.*建议'
            ],
            "priority": 7,
            "category": IntentCategory.TASK,
            "model": "l3",
            "tools": ["code_analyzer"],
            "need_knowledge": True,
            "followup_templates": [
                "需要我提供具体的修改建议吗？",
                "想让我优化这部分代码吗？",
                "还有其他代码需要审查吗？",
            ],
        },
        ChatIntent.DEBUGGING: {
            "patterns": [
                r'调试', r'debug', r'修复.*错误', r'报错', r'异常',
                r'fix bug', r'error', r'exception', r'崩溃',
                r'闪退', r'卡住', r'不工作', r'出问题了'
            ],
            "priority": 8,  # 最高优先级
            "category": IntentCategory.TASK,
            "model": "l3",
            "tools": ["debugger", "search_knowledge"],
            "need_knowledge": True,
            "need_deep_search": True,
            "followup_templates": [
                "这个解决方案对您有帮助吗？",
                "需要我提供更详细的调试步骤吗？",
                "问题解决了吗？还需要其他帮助吗？",
            ],
        },
        ChatIntent.FILE_OPERATION: {
            "patterns": [
                r'读取.*文件', r'写入.*文件', r'打开', r'保存',
                r'read file', r'write file', r'open', r'save',
                r'文件.*读取', r'文件.*写入', r'创建.*文件',
                r'删除.*文件', r'移动.*文件', r'复制.*文件'
            ],
            "priority": 8,
            "category": IntentCategory.TASK,
            "model": "l0",
            "tools": ["file_read", "file_write", "file_delete"],
            "followup_templates": [
                "还需要对文件进行其他操作吗？",
                "需要我查看文件内容吗？",
            ],
        },
        ChatIntent.TASK_EXECUTION: {
            "patterns": [
                r'执行', r'运行', r'launch',
                r'打开.*应用', r'启动.*程序',
                r'测试用例',
            ],
            "priority": 4,
            "category": IntentCategory.TASK,
            "model": "l0",
            "followup_templates": [
                "执行成功了吗？",
                "还需要执行其他任务吗？",
                "需要我帮您监控执行结果吗？",
            ],
        },
        
        # === 创作类 ===
        ChatIntent.WRITING: {
            "patterns": [
                r'写', r'撰写', r'编辑', r'修改',
                r'write', r'compose', r'draft', r'edit',
                r'作文', r'文章', r'报告', r'文档',
                r'写.*邮件', r'写.*信', r'写.*方案'
            ],
            "priority": 4,
            "category": IntentCategory.CREATION,
            "model": "l3",
            "followup_templates": [
                "需要我调整写作风格吗？",
                "还需要润色或修改吗？",
                "需要添加更多细节吗？",
                "还有其他文档需要撰写吗？",
            ],
        },
        ChatIntent.TRANSLATION: {
            "patterns": [
                r'翻译', r'translate', r'中译英', r'英译中',
                r'翻译成', r'convert to', r'译成',
                r'把.*翻译', r'翻成'
            ],
            "priority": 5,
            "category": IntentCategory.CREATION,
            "model": "l1",
            "followup_templates": [
                "翻译的准确度可以吗？",
                "需要我解释某些词句吗？",
                "还有其他内容需要翻译吗？",
            ],
        },
        ChatIntent.SUMMARIZATION: {
            "patterns": [
                r'摘要', r'总结', r'summarize', r'summary',
                r'概括', r'提炼', r'简短',
                r'总结一下', r'概括一下', r'主要.*是'
            ],
            "priority": 4,
            "category": IntentCategory.CREATION,
            "model": "l3",
            "followup_templates": [
                "这个摘要涵盖了您关心的要点吗？",
                "需要我更详细地展开某个点吗？",
                "还需要总结其他内容吗？",
            ],
        },
        ChatIntent.CREATIVE: {
            "patterns": [
                r'创意', r'想象', r'设计', r'头脑风暴',
                r'creative', r'imagine', r'design', r'brainstorm',
                r'给我.*建议', r'有什么.*想法',
                r'灵感', r'点子'
            ],
            "priority": 4,
            "category": IntentCategory.CREATION,
            "model": "l3",
            "followup_templates": [
                "这些创意对您有启发吗？",
                "想深入发展哪个想法？",
                "需要我提供更多方案吗？",
                "还有哪些场景需要创意支持？",
            ],
        },
        
        # === 知识类 ===
        ChatIntent.KNOWLEDGE_QUERY: {
            "patterns": [
                r'查找', r'搜索知识', r'知识库', r'相关文档',
                r'search knowledge', r'find in docs',
                r'告诉我.*关于', r'关于.*介绍',
                r'是什么', r'有哪些', r'有什么'
            ],
            "priority": 3,
            "category": IntentCategory.KNOWLEDGE,
            "model": "l1",
            "tools": ["search_knowledge"],
            "need_knowledge": True,
            "followup_templates": [
                "这些信息对您有帮助吗？",
                "需要我深入解释某个概念吗？",
                "还想了解相关的其他知识吗？",
            ],
        },
        ChatIntent.SEARCH: {
            "patterns": [
                r'搜索', r'查找', r'search', r'find',
                r'google', r'bing', r'百度',
                r'帮我.*一下', r'帮我.*一下',
                r'查一下', r'找一下'
            ],
            "priority": 3,
            "category": IntentCategory.KNOWLEDGE,
            "model": "l1",
            "tools": ["web_search"],
            "followup_templates": [
                "找到您需要的信息了吗？",
                "需要我搜索其他相关内容吗？",
                "这些搜索结果有用吗？",
            ],
        },
    }
    
    # 工具需求映射
    INTENT_TOOLS = {
        ChatIntent.CODE_GENERATION: ['code_generator'],
        ChatIntent.CODE_REVIEW: ['code_analyzer'],
        ChatIntent.DEBUGGING: ['debugger', 'search_knowledge'],
        ChatIntent.KNOWLEDGE_QUERY: ['search_knowledge'],
        ChatIntent.FILE_OPERATION: ['file_read', 'file_write'],
        ChatIntent.SEARCH: ['web_search'],
    }
    
    # 模型选择映射
    INTENT_MODELS = {
        ChatIntent.CODE_GENERATION: "l4",       # L4 深度生成
        ChatIntent.CODE_REVIEW: "l3",           # L3 推理
        ChatIntent.DEBUGGING: "l3",             # L3 分析
        ChatIntent.REASONING: "l3",             # L3 推理
        ChatIntent.MATHEMATICS: "l0",           # L0 计算
        ChatIntent.ANALYSIS: "l3",              # L3 分析
        ChatIntent.WRITING: "l3",               # L3 创作
        ChatIntent.TRANSLATION: "l1",           # L1 翻译
        ChatIntent.SUMMARIZATION: "l3",         # L3 摘要
        ChatIntent.CREATIVE: "l3",              # L3 创意
        ChatIntent.KNOWLEDGE_QUERY: "l1",      # L1 检索
        ChatIntent.SEARCH: "l1",               # L1 搜索
        ChatIntent.FILE_OPERATION: "l0",       # L0 指令
        ChatIntent.TASK_EXECUTION: "l0",       # L0 指令
        ChatIntent.CHITCHAT: "l1",             # L1 对话
        ChatIntent.GREETING: "l0",             # L0 问候
        ChatIntent.QUESTION: "l1",            # L1 问答
        ChatIntent.UNKNOWN: "auto",            # 自动
    }
    
    # 语言检测关键词
    LANGUAGE_PATTERNS = {
        "python": [r'\bdef\b', r'\bimport\b', r'\bprint\b', r'python'],
        "javascript": [r'\bfunction\b', r'\bconst\b', r'\blet\b', r'javascript', r'js'],
        "java": [r'\bpublic\b', r'\bclass\b', r'\bvoid\b', r'java'],
        "cpp": [r'\b#include\b', r'\bstd::', r'\bc\+\+', r'cpp'],
        "go": [r'\bfunc\b', r'\bpackage\b', r'\bgo\b'],
        "rust": [r'\bfn\b', r'\blet mut\b', r'\brust\b'],
        "sql": [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'sql'],
        "shell": [r'\bchmod\b', r'\bls\b', r'\bcd\b', r'shell', r'bash'],
    }
    
    def __init__(self):
        # 预编译正则表达式
        self._compiled_patterns: Dict[ChatIntent, List[re.Pattern]] = {}
        for intent, defn in self.INTENT_DEFINITIONS.items():
            self._compiled_patterns[intent] = [
                re.compile(p, re.IGNORECASE) for p in defn.get("patterns", [])
            ]
        
        # 语言检测正则
        self._lang_patterns = {
            lang: [re.compile(p, re.IGNORECASE) for p in patterns]
            for lang, patterns in self.LANGUAGE_PATTERNS.items()
        }
    
    def classify(self, message: str, context: Optional[ChatContext] = None) -> IntentAnalysis:
        """
        分类用户消息的意图
        
        Args:
            message: 用户消息
            context: 可选的对话上下文（用于上下文感知）
            
        Returns:
            IntentAnalysis: 意图分析结果
        """
        message_lower = message.lower()
        scores: Dict[ChatIntent, Tuple[float, int]] = {}  # (score, priority)
        
        # 1. 计算每个意图的匹配分数
        for intent, compiled_patterns in self._compiled_patterns.items():
            score = 0
            for pattern in compiled_patterns:
                if pattern.search(message):
                    score += 1
            
            if score > 0:
                priority = self.INTENT_DEFINITIONS[intent].get("priority", 1)
                # 归一化分数并考虑优先级
                normalized = (score / len(compiled_patterns)) * (1 + priority * 0.1)
                scores[intent] = (normalized, priority)
        
        # 2. 上下文感知：检查是否延续上一个意图
        if context and context.last_intent and context.last_intent in self.INTENT_DEFINITIONS:
            last_priority = self.INTENT_DEFINITIONS[context.last_intent].get("priority", 1)
            # 如果是连续追问，略微提高上一个意图的分数
            if context.followup_count > 0 and context.last_intent not in scores:
                scores[context.last_intent] = (0.3, last_priority)
        
        if not scores:
            # 无匹配，返回未知意图
            return IntentAnalysis(
                intent=ChatIntent.UNKNOWN,
                confidence=0.5,
                category=IntentCategory.OTHER,
                suggested_model=self.INTENT_MODELS.get(ChatIntent.UNKNOWN, "auto"),
                language=self._detect_language(message)
            )
        
        # 3. 选择最高分意图
        best_intent = max(scores.keys(), key=lambda i: scores[i][0] * 100 + scores[i][1])
        base_score = scores[best_intent][0]
        confidence = min(0.95, 0.3 + base_score * 0.4)
        
        # 4. 获取意图定义
        defn = self.INTENT_DEFINITIONS.get(best_intent, {})
        category = defn.get("category", IntentCategory.OTHER)
        priority = defn.get("priority", 1)
        
        # 5. 获取建议的工具和模型
        need_tools = defn.get("tools", self.INTENT_TOOLS.get(best_intent, []))
        need_knowledge = defn.get("need_knowledge", False)
        need_deep_search = defn.get("need_deep_search", False)
        suggested_model = defn.get("model", self.INTENT_MODELS.get(best_intent, "auto"))
        
        # 6. 检测语言
        language = self._detect_language(message)
        
        # 7. 提取实体
        entities = self._extract_entities(message)
        
        return IntentAnalysis(
            intent=best_intent,
            confidence=confidence,
            category=category,
            entities=entities,
            suggested_model=suggested_model,
            need_tools=need_tools,
            need_knowledge=need_knowledge,
            need_deep_search=need_deep_search,
            language=language,
            priority=priority,
            # 新增：回答稳定性分析
            answer_stability=self._analyze_stability(best_intent, message),
            is_cacheable=self._is_cacheable_intent(best_intent),
            cache_value=self._calculate_cache_value(best_intent, confidence),
            needs_realtime=self._needs_realtime_data(message)
        )
    
    # === 回答稳定性分析 ===
    
    # 高稳定性意图：回答相对固定，适合缓存
    HIGH_STABILITY_INTENTS = {
        ChatIntent.KNOWLEDGE_QUERY,  # 知识查询
        ChatIntent.TRANSLATION,      # 翻译
        ChatIntent.SUMMARIZATION,    # 摘要
        ChatIntent.CODE_GENERATION,  # 代码生成（相对固定）
        ChatIntent.WRITING,          # 写作（模板化）
    }
    
    # 低稳定性意图：回答变化大，不适合缓存
    LOW_STABILITY_INTENTS = {
        ChatIntent.CHITCHAT,        # 闲聊
        ChatIntent.QUESTION,         # 问答
        ChatIntent.REASONING,        # 推理
    }
    
    # 实时数据关键词
    REALTIME_KEYWORDS = {
        # 新闻/资讯
        "今天", "昨天", "明天", "刚刚", "最新", "新闻", "资讯", "头条",
        # 股票/金融
        "股价", "涨跌", "大盘", "指数", "股票", "基金净值", "市值",
        # 天气
        "天气", "气温", "下雨", "温度", "天气预报", "PM2.5",
        # 位置/实时
        "现在", "当前", "此刻", "实时", "位置", "附近",
        # 社交
        "朋友圈", "微博", "热搜", "趋势",
    }
    
    # 缓存价值评估（基于意图）
    CACHE_VALUE_BASE = {
        ChatIntent.TRANSLATION: 0.9,       # 翻译缓存价值高
        ChatIntent.SUMMARIZATION: 0.8,     # 摘要缓存价值高
        ChatIntent.KNOWLEDGE_QUERY: 0.7,  # 知识查询中等
        ChatIntent.CODE_GENERATION: 0.7,  # 代码生成中等
        ChatIntent.WRITING: 0.6,          # 写作中等
        ChatIntent.CODE_REVIEW: 0.6,      # 代码审查中等
        ChatIntent.MATHEMATICS: 0.6,     # 数学计算中等
        ChatIntent.QUESTION: 0.4,         # 问答缓存价值低
        ChatIntent.CHITCHAT: 0.3,        # 闲聊缓存价值低
        ChatIntent.DEBUGGING: 0.3,        # 调试缓存价值低
    }
    
    def _analyze_stability(self, intent: ChatIntent, message: str) -> float:
        """
        分析回答稳定性
        
        Args:
            intent: 意图类型
            message: 原始消息
            
        Returns:
            float: 稳定性评分 0-1
        """
        # 1. 基于意图的基线稳定性
        if intent in self.HIGH_STABILITY_INTENTS:
            stability = 0.8
        elif intent in self.LOW_STABILITY_INTENTS:
            stability = 0.4
        else:
            stability = 0.6
        
        # 2. 基于消息特征调整
        message_lower = message.lower()
        
        # 有明确实体 → 更稳定
        entities = self._extract_entities(message)
        if entities:
            stability += 0.1
        
        # 包含具体数字 → 更稳定
        if re.search(r'\d+', message):
            stability += 0.05
        
        # 包含实时关键词 → 不稳定
        for keyword in self.REALTIME_KEYWORDS:
            if keyword in message_lower:
                stability -= 0.2
                break
        
        # 连续追问 → 不稳定
        # (context.followup_count 可以进一步降低稳定性)
        
        return max(0.1, min(0.95, stability))
    
    def _is_cacheable_intent(self, intent: ChatIntent) -> bool:
        """
        判断意图是否可缓存
        
        Returns:
            bool: 是否可缓存
        """
        # 明确不可缓存的意图
        NON_CACHEABLE = {
            ChatIntent.CHITCHAT,     # 闲聊
            ChatIntent.GREETING,     # 问候
            ChatIntent.DEBUGGING,    # 调试
            ChatIntent.FILE_OPERATION,  # 文件操作
            ChatIntent.TASK_EXECUTION,  # 任务执行
        }
        
        return intent not in NON_CACHEABLE
    
    def _calculate_cache_value(self, intent: ChatIntent, confidence: float) -> float:
        """
        计算缓存价值
        
        Args:
            intent: 意图类型
            confidence: 意图识别置信度
            
        Returns:
            float: 缓存价值 0-1
        """
        # 获取基线价值
        base_value = self.CACHE_VALUE_BASE.get(intent, 0.5)
        
        # 置信度高 → 缓存价值高
        # 置信度低 → 需要更多 LLM 推理，缓存价值降低
        confidence_factor = 0.5 + confidence * 0.5
        
        return base_value * confidence_factor
    
    def _needs_realtime_data(self, message: str) -> bool:
        """
        判断是否需要实时数据
        
        Args:
            message: 原始消息
            
        Returns:
            bool: 是否需要实时数据
        """
        message_lower = message.lower()
        
        for keyword in self.REALTIME_KEYWORDS:
            if keyword in message_lower:
                return True
        
        return False
        """检测代码语言"""
        for lang, patterns in self._lang_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return lang
        return ""
    
    def _detect_language(self, text: str) -> str:
        """检测代码语言"""
        for lang, patterns in self._lang_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return lang
        return ""
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {}
        
        # 文件路径
        file_paths = re.findall(r'[\w/\\.]+\.[\w]+', text)
        if file_paths:
            entities['files'] = file_paths
        
        # 代码块
        code_blocks = re.findall(r'```[\s\S]*?```', text)
        if code_blocks:
            entities['code_blocks'] = len(code_blocks)
        
        # URL
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            entities['urls'] = urls
        
        # 邮箱
        emails = re.findall(r'\S+@\S+\.\S+', text)
        if emails:
            entities['emails'] = emails
        
        return entities


# ============== Query 压缩器 ==============

class QueryCompressor:
    """
    Query 压缩器
    
    使用 LLM 压缩长查询，减少 token 消耗
    """
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._max_cache_size = 100
        
        # 压缩阈值（字符数）
        self._short_threshold = 100      # <100 字不压缩
        self._medium_threshold = 500     # 100-500 字轻压缩
        self._long_threshold = 1000     # >1000 字强压缩
        
        # LLM 压缩模型
        self._llm_model = "qwen2.5:1.5b"
    
    def compress(self, query: str, force: bool = False) -> str:
        """
        压缩查询
        
        Args:
            query: 原始查询
            force: 强制压缩（忽略短查询不压缩）
            
        Returns:
            str: 压缩后的查询
        """
        # 短查询不压缩（除非强制）
        if len(query) < self._short_threshold and not force:
            return query
        
        # 检查缓存
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 根据长度选择压缩策略
        if len(query) < self._medium_threshold:
            # 轻压缩：去除冗余
            compressed = self._light_compress(query)
        elif len(query) < self._long_threshold:
            # 中压缩：提取关键信息
            compressed = self._medium_compress(query)
        else:
            # 强压缩：使用 LLM
            compressed = self._heavy_compress(query)
        
        # 缓存
        if len(self._cache) >= self._max_cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[cache_key] = compressed
        
        return compressed
    
    def _light_compress(self, text: str) -> str:
        """轻压缩：去除多余空格和换行"""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 去除首尾空白
        text = text.strip()
        return text
    
    def _medium_compress(self, text: str) -> str:
        """中压缩：提取关键实体"""
        # 提取关键信息
        entities = []
        
        # 文件路径
        paths = re.findall(r'[\w/\\.]+\.[\w]+', text)
        entities.extend(paths)
        
        # 代码片段（保留前几个的摘要）
        code_blocks = re.findall(r'```[\s\S]*?```', text)
        for block in code_blocks[:3]:  # 最多保留 3 个
            entities.append(block[:100])
        
        # 关键概念（提取包含技术术语的句子）
        tech_terms = [
            '函数', '类', '方法', 'API', '模块', '接口',
            'function', 'class', 'method', 'api', 'module',
            '什么', '怎么', '如何', '为什么'
        ]
        sentences = re.split(r'[。！？\n]', text)
        for sent in sentences:
            if any(term in sent for term in tech_terms):
                entities.append(sent.strip()[:100])
        
        if entities:
            return ' | '.join(entities[:5])
        
        return self._light_compress(text)
    
    def _heavy_compress(self, text: str) -> str:
        """强压缩：使用 LLM（需要 Ollama）"""
        try:
            from core.ollama_client import OllamaClient
            
            client = OllamaClient()
            prompt = f"""压缩以下查询，保留核心意图和关键实体：

{text[:2000]}

压缩要求：
1. 保留用户的主要目标
2. 保留关键的技术术语和名称
3. 删除解释性和重复性内容
4. 压缩后不超过 200 字

压缩结果："""
            
            response = client.chat([{"role": "user", "content": prompt}])
            
            if response and response.strip():
                return response.strip()
            
        except Exception:
            pass
        
        # 降级：使用关键词提取
        return self._extract_keywords(text)
    
    def _extract_keywords(self, text: str) -> str:
        """提取关键词"""
        # 技术关键词
        tech_keywords = [
            'python', 'javascript', 'java', 'c++', 'go', 'rust',
            'api', '函数', '类', '方法', '模块', '接口',
            'bug', 'error', 'debug', 'test', 'optimize',
            '什么', '怎么', '如何', '为什么'
        ]
        
        found = []
        text_lower = text.lower()
        
        for keyword in tech_keywords:
            if keyword in text_lower:
                found.append(keyword)
        
        if found:
            return ' '.join(found[:10])
        
        return text[:200]
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# ============== Chat 上下文管理器 ==============

class ChatContextManager:
    """
    Chat 上下文管理器
    
    智能管理对话历史，控制 token 消耗
    """
    
    def __init__(
        self,
        max_messages: int = 20,
        max_tokens: int = 4000,
        session_timeout: float = 3600  # 1小时会话超时
    ):
        """
        Args:
            max_messages: 最大保留消息数
            max_tokens: 最大 token 预算
            session_timeout: 会话超时时间（秒）
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.session_timeout = session_timeout
        self._contexts: Dict[str, ChatContext] = {}
        self._histories: Dict[str, List[Dict]] = {}
    
    def get_context(self, session_id: str) -> ChatContext:
        """获取或创建上下文"""
        if session_id not in self._contexts:
            self._contexts[session_id] = ChatContext(session_id=session_id)
        return self._contexts[session_id]
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: Optional[ChatIntent] = None,
        metadata: Optional[Dict] = None
    ):
        """添加消息到历史"""
        if session_id not in self._histories:
            self._histories[session_id] = []
        
        # 检查是否连续追问
        ctx = self.get_context(session_id)
        now = time.time()
        
        # 检测话题切换
        if intent and ctx.last_intent and intent != ctx.last_intent:
            ctx.topic_switch_count += 1
        
        # 检测连续追问
        if intent == ctx.last_intent and intent not in [ChatIntent.GREETING, ChatIntent.CHITCHAT]:
            ctx.followup_count += 1
        else:
            ctx.followup_count = 0
        
        # 添加消息
        message = {
            'role': role,
            'content': content,
            'timestamp': now,
            'intent': intent.value if intent else None
        }
        if metadata:
            message['metadata'] = metadata
        
        self._histories[session_id].append(message)
        
        # 更新上下文
        ctx.message_count += 1
        ctx.last_active = now
        if intent:
            ctx.last_intent = intent
            if intent not in ctx.intents:
                ctx.intents.append(intent)
        
        # 截断历史
        self._prune_history(session_id)
    
    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        intent_filter: Optional[ChatIntent] = None
    ) -> List[Dict]:
        """获取对话历史"""
        history = self._histories.get(session_id, [])
        
        if intent_filter:
            history = [m for m in history if m.get('intent') == intent_filter.value]
        
        if limit:
            return history[-limit:]
        
        return history
    
    def get_context_prompt(self, session_id: str) -> str:
        """生成上下文提示"""
        ctx = self.get_context(session_id)
        
        parts = []
        
        # 话题
        if ctx.topic:
            parts.append(f"当前话题：{ctx.topic}")
        
        # 最近意图
        if ctx.last_intent:
            parts.append(f"用户意图：{ctx.last_intent.value}")
        
        # 连续追问标记
        if ctx.followup_count > 0:
            parts.append(f"[连续追问 x{ctx.followup_count + 1}]")
        
        # 消息数量
        parts.append(f"对话轮次：{ctx.message_count}")
        
        # 上下文总结
        if len(ctx.intents) > 1:
            parts.append(f"涉及领域：{', '.join(i.value for i in ctx.intents[-3:])}")
        
        if parts:
            return "[上下文] " + " | ".join(parts) + "\n"
        
        return ""
    
    def get_conversation_summary(self, session_id: str) -> str:
        """获取对话总结"""
        ctx = self.get_context(session_id)
        history = self.get_history(session_id)
        
        lines = [
            f"会话 ID: {session_id}",
            f"消息数: {ctx.message_count}",
            f"话题切换: {ctx.topic_switch_count} 次",
            f"涉及意图: {[i.value for i in ctx.intents]}",
        ]
        
        if ctx.last_intent:
            lines.append(f"当前意图: {ctx.last_intent.value}")
        
        if history:
            lines.append(f"最后消息: {history[-1]['content'][:50]}...")
        
        return "\n".join(lines)
    
    def _prune_history(self, session_id: str):
        """裁剪历史"""
        history = self._histories.get(session_id, [])
        ctx = self.get_context(session_id)
        now = time.time()
        
        # 1. 清理超时消息（保留最近的）
        if ctx.message_count > 4:  # 至少有2轮对话
            recent = [h for h in history if now - h['timestamp'] < self.session_timeout]
            if len(recent) < len(history):
                history = recent if recent else history[-2:]
        
        # 2. 按消息数裁剪（保留最近的消息对）
        if len(history) > self.max_messages:
            history = history[-self.max_messages:]
        
        # 3. 按 token 预算裁剪
        total_chars = sum(len(m['content']) for m in history)
        max_chars = self.max_tokens * 4  # 粗略估计：1 token ≈ 4 字符
        
        if total_chars > max_chars:
            # 从头开始删除，直到满足预算
            while total_chars > max_chars and len(history) > 4:
                removed = history.pop(0)
                total_chars -= len(removed['content'])
        
        self._histories[session_id] = history
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._histories:
            del self._histories[session_id]
        if session_id in self._contexts:
            del self._contexts[session_id]


# ============== 追问生成器 ==============

@dataclass
class GuidanceResult:
    """追问生成结果"""
    questions: List[str]                    # 生成的追问列表
    strategy: str                          # 使用的策略
    intent: Optional[ChatIntent]            # 对应的意图
    confidence: float = 1.0               # 置信度
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


class GuidanceGenerator:
    """
    追问生成器
    
    基于意图模板 + 内容分析 + 上下文感知生成智能追问
    
    支持策略：
    1. 模板策略 - 从意图模板中选择
    2. 内容分析策略 - 分析回答内容生成追问
    3. 上下文策略 - 基于对话历史生成追问
    4. 选项策略 - 生成选择题式追问
    """
    
    # 策略权重配置
    STRATEGY_WEIGHTS = {
        "template": 0.4,      # 模板策略
        "content": 0.3,       # 内容分析策略
        "context": 0.2,       # 上下文策略
        "option": 0.1,        # 选项策略
    }
    
    # 内容分析关键词
    CONTENT_SIGNALS = {
        # 多方案信号
        "multiple_solution": {
            "patterns": [r'两种', r'三种', r'有.*方法', r'可以.*也可以', r'方案一', r'方案二'],
            "template": "您更倾向于哪个方案？",
        },
        # 深入解释信号
        "need_explain": {
            "patterns": [r'原理', r'机制', r'为什么', r'如何实现', r'怎么工作'],
            "template": "需要我详细解释一下吗？",
        },
        # 示例请求信号
        "need_example": {
            "patterns": [r'例子', r'示例', r'案例', r'举例', r'例如'],
            "template": "需要我举一个具体的例子吗？",
        },
        # 步骤信号
        "need_steps": {
            "patterns": [r'步骤', r'流程', r'过程', r'先后'],
            "template": "需要我列出具体的实施步骤吗？",
        },
        # 代码信号
        "need_code": {
            "patterns": [r'代码', r'函数', r'实现', r'编程'],
            "template": "需要我提供代码实现吗？",
        },
        # 优缺点信号
        "pros_cons": {
            "patterns": [r'优缺点', r'利弊', r'优势', r'劣势', r'比较'],
            "template": "需要我详细对比一下两者的优缺点吗？",
        },
    }
    
    # 选项式追问配置
    OPTION_TEMPLATES = {
        ChatIntent.CODE_GENERATION: [
            ("解释代码原理", "help_explain"),
            ("添加单元测试", "help_test"),
            ("优化性能", "help_optimize"),
            ("添加注释", "help_comment"),
        ],
        ChatIntent.DEBUGGING: [
            ("提供详细步骤", "help_steps"),
            ("解释错误原因", "help_reason"),
            ("给出完整解决方案", "help_solution"),
        ],
        ChatIntent.WRITING: [
            ("调整风格", "help_style"),
            ("润色文字", "help_polish"),
            ("扩展内容", "help_expand"),
        ],
    }
    
    def __init__(self, enable_template: bool = True, enable_content: bool = True,
                 enable_context: bool = True, enable_option: bool = True,
                 max_questions: int = 3):
        """
        Args:
            enable_template: 启用模板策略
            enable_content: 启用内容分析策略
            enable_context: 启用上下文策略
            enable_option: 启用选项策略
            max_questions: 最大追问数量
        """
        self.enable_template = enable_template
        self.enable_content = enable_content
        self.enable_context = enable_context
        self.enable_option = enable_option
        self.max_questions = max_questions
        
        # 预编译模式
        self._compiled_signals = {
            key: [
                (re.compile(p, re.IGNORECASE), info["template"])
                for p in info["patterns"]
            ]
            for key, info in self.CONTENT_SIGNALS.items()
        }
    
    def generate(
        self,
        intent: ChatIntent,
        response: str = "",
        context: Optional[ChatContext] = None,
        user_message: str = "",
    ) -> GuidanceResult:
        """
        生成追问
        
        Args:
            intent: 当前意图
            response: AI 回答内容（用于内容分析）
            context: 对话上下文
            user_message: 用户原始消息
            
        Returns:
            GuidanceResult: 追问生成结果
        """
        questions = []
        strategies_used = []
        
        # 1. 模板策略
        if self.enable_template:
            template_questions = self._generate_from_template(intent)
            if template_questions:
                questions.extend(template_questions)
                strategies_used.append("template")
        
        # 2. 内容分析策略
        if self.enable_content and response:
            content_questions = self._generate_from_content(response)
            if content_questions:
                questions.extend(content_questions)
                strategies_used.append("content")
        
        # 3. 上下文策略
        if self.enable_context and context:
            context_questions = self._generate_from_context(context, intent)
            if context_questions:
                questions.extend(context_questions)
                strategies_used.append("context")
        
        # 4. 选项策略
        if self.enable_option:
            option_questions = self._generate_option(intent, user_message)
            if option_questions:
                # 选项策略不直接添加问题，而是标记为可用
                strategies_used.append("option")
        
        # 去重并限制数量
        questions = self._deduplicate_and_limit(questions)
        
        return GuidanceResult(
            questions=questions,
            strategy=", ".join(strategies_used) if strategies_used else "none",
            intent=intent,
            confidence=self._calculate_confidence(len(questions), strategies_used),
            metadata={
                "template_questions": len([s for s in strategies_used if s == "template"]),
                "content_questions": len([s for s in strategies_used if s == "content"]),
                "context_questions": len([s for s in strategies_used if s == "context"]),
            }
        )
    
    def _generate_from_template(self, intent: ChatIntent) -> List[str]:
        """从意图模板生成追问"""
        templates = ChatIntentClassifier.INTENT_DEFINITIONS.get(intent, {}).get("followup_templates", [])
        if templates:
            # 随机选择 1-2 个模板
            import random
            count = min(len(templates), random.randint(1, 2))
            return random.sample(templates, count)
        return []
    
    def _generate_from_content(self, response: str) -> List[str]:
        """从回答内容分析生成追问"""
        questions = []
        response_lower = response.lower()
        
        for signal_name, compiled_patterns in self._compiled_signals.items():
            for pattern, template in compiled_patterns:
                if pattern.search(response):
                    if template not in questions:
                        questions.append(template)
                    break
        
        return questions
    
    def _generate_from_context(self, context: ChatContext, current_intent: ChatIntent) -> List[str]:
        """从对话上下文生成追问"""
        questions = []
        
        # 基于连续追问次数调整
        if context.followup_count >= 2:
            # 连续追问多了，引导深入
            questions.append("需要我更详细地解释吗？")
        elif context.followup_count == 0 and context.message_count > 0:
            # 刚开始对话，通用引导
            questions.append("还有其他问题吗？")
        
        # 基于话题切换
        if context.topic_switch_count > 0:
            questions.append("这个话题还有需要补充的吗？")
        
        return questions
    
    def _generate_option(self, intent: ChatIntent, user_message: str) -> List[Tuple[str, str]]:
        """生成选项式追问（返回选项列表）"""
        options = self.OPTION_TEMPLATES.get(intent, [])
        if options:
            return options[:self.max_questions]
        return []
    
    def _deduplicate_and_limit(self, questions: List[str]) -> List[str]:
        """去重并限制数量"""
        seen = set()
        result = []
        for q in questions:
            # 简单去重：忽略完全相同的问题
            normalized = q.strip().lower()
            if normalized not in seen and len(result) < self.max_questions:
                seen.add(normalized)
                result.append(q)
        return result
    
    def _calculate_confidence(self, num_questions: int, strategies: List[str]) -> float:
        """计算追问生成置信度"""
        # 基于策略数量和追问数量计算置信度
        base = 0.5
        if len(strategies) >= 3:
            base += 0.3
        elif len(strategies) >= 2:
            base += 0.2
        elif len(strategies) >= 1:
            base += 0.1
        
        # 追问数量加分
        if num_questions >= 3:
            base += 0.1
        elif num_questions >= 2:
            base += 0.05
        
        return min(1.0, base)
    
    def should_show_guidance(
        self,
        intent: ChatIntent,
        context: Optional[ChatContext] = None,
        response_length: int = 0
    ) -> bool:
        """
        判断是否应该显示追问引导
        
        Args:
            intent: 当前意图
            context: 对话上下文
            response_length: 回答长度
            
        Returns:
            bool: 是否应该显示追问
        """
        # 不显示追问的意图
        NO_GUIDANCE_INTENTS = {
            ChatIntent.GREETING,       # 问候不需要追问
            ChatIntent.CHITCHAT,       # 闲聊不需要追问
        }
        
        if intent in NO_GUIDANCE_INTENTS:
            return False
        
        # 连续追问太多时不显示
        if context and context.followup_count >= 5:
            return False
        
        # 回答太短时不显示
        if response_length > 0 and response_length < 20:
            return False
        
        return True


# ============== 增强版 AgentChat ==============

class EnhancedAgentChat:
    """
    增强版 AgentChat
    
    集成通用意图识别、Query 压缩、上下文管理、追问生成
    支持：对话、推理、操作、创作等通用场景
    """
    
    def __init__(
        self,
        base_chat,  # 原始 AgentChat 实例
        enable_intent: bool = True,
        enable_compress: bool = True,
        enable_context: bool = True,
        enable_guidance: bool = True,
        max_guidance_questions: int = 3,
    ):
        self.base_chat = base_chat
        self.session_id = getattr(base_chat.agent, 'session_id', 'default')
        
        # 启用功能
        self.enable_intent = enable_intent
        self.enable_compress = enable_compress
        self.enable_context = enable_context
        self.enable_guidance = enable_guidance
        
        # 初始化组件
        self._intent_classifier = ChatIntentClassifier() if enable_intent else None
        self._query_compressor = QueryCompressor() if enable_compress else None
        self._context_manager = ChatContextManager() if enable_context else None
        self._guidance_generator = GuidanceGenerator(max_questions=max_guidance_questions) if enable_guidance else None
        
        # IntentEngine - 代码专用意图解析（可选）
        self._intent_engine = IntentEngine() if INTENT_ENGINE_AVAILABLE else None
        if self._intent_engine:
            logger.info("[EnhancedAgentChat] IntentEngine enabled - code intent parsing")

        # 代码签名化 - 上下文压缩（可选）
        self._code_signer = CodeSigner() if CODE_SIGNER_AVAILABLE else None
        self._symbol_index = None  # 延迟初始化
        self._incremental_context = IncrementalContextManager() if CODE_SIGNER_AVAILABLE else None
        if self._code_signer:
            logger.info("[EnhancedAgentChat] CodeSigner enabled - context compression")
        
        # 代码澄清器 - 交互式需求澄清（可选）
        self._code_clarifier = CodeClarifier() if CODE_CLARIFIER_AVAILABLE else None
        self._clarify_sessions: Dict[str, Any] = {}  # 澄清会话存储
        if self._code_clarifier:
            logger.info("[EnhancedAgentChat] CodeClarifier enabled - interactive code clarification")
        
        # IDE 上下文注入器 - 项目结构感知（可选）
        self._ide_context_injector = None
        self._ide_context: Any = None
        self._active_file: Optional[str] = None
        if IDE_CONTEXT_INJECTOR_AVAILABLE:
            # 延迟初始化，允许后续设置项目根目录
            logger.info("[EnhancedAgentChat] IDE Context Injector available - project structure awareness")
        
        # 回调
        self._on_intent_detected: Optional[Callable[[IntentAnalysis], None]] = None
        self._on_compress: Optional[Callable[[str, str], None]] = None
        self._on_context_update: Optional[Callable[[ChatContext], None]] = None
        self._on_guidance_generated: Optional[Callable[[GuidanceResult], None]] = None
        
        # 当前对话的追问结果（用于后续显示）
        self._last_guidance: Optional[GuidanceResult] = None
        
        # === 多模态输出支持 (Phase 4) ===
        self._multimodal_manager = None
        self._progress_tracker = None
        self._enable_multimodal = False
        
        # 尝试导入多模态模块
        self._MULTIMODAL_AVAILABLE = False
        try:
            from core.smart_writing import (
                MultimodalOutputManager,
                OutputMode,
                PyQt6OutputManager,
                ProgressTracker,
                RecoveryExecutor,
                RetryPolicy,
            )
            self._MULTIMODAL_AVAILABLE = True
            self._MultimodalOutputManager = MultimodalOutputManager
            self._OutputMode = OutputMode
            self._PyQt6OutputManager = PyQt6OutputManager
            self._ProgressTracker = ProgressTracker
            self._RecoveryExecutor = RecoveryExecutor
            self._RetryPolicy = RetryPolicy
        except ImportError as e:
            logger.info(f"[EnhancedAgentChat] 多模态模块不可用: {e}")
    
    @property
    def agent(self):
        """获取底层 Agent"""
        return self.base_chat.agent
    
    def set_intent_callback(self, callback: Callable[[IntentAnalysis], None]):
        """设置意图检测回调"""
        self._on_intent_detected = callback
    
    def set_compress_callback(self, callback: Callable[[str, str], None]):
        """设置压缩回调"""
        self._on_compress = callback
    
    def set_context_callback(self, callback: Callable[[ChatContext], None]):
        """设置上下文更新回调"""
        self._on_context_update = callback
    
    def set_guidance_callback(self, callback: Callable[[GuidanceResult], None]):
        """设置追问生成回调"""
        self._on_guidance_generated = callback
    
    def get_guidance(self) -> Optional[GuidanceResult]:
        """获取上一次生成的追问"""
        return self._last_guidance
    
    def append_guidance_to_response(self, response: str) -> str:
        """
        将追问追加到响应末尾
        
        Args:
            response: 原始响应
            
        Returns:
            str: 带追问的响应
        """
        if not self._last_guidance or not self._last_guidance.questions:
            return response
        
        questions = self._last_guidance.questions
        if not questions:
            return response
        
        # 构建追问文本
        guidance_text = "\n\n---\n**您可能还想问：**\n"
        for i, q in enumerate(questions, 1):
            guidance_text += f"{i}. {q}\n"
        
        return response + guidance_text
    
    # ============== 多模态输出配置 (Phase 4) ==============
    
    def enable_multimodal(
        self,
        mode: str = "normal",
        text_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        启用多模态输出功能
        
        Args:
            mode: 输出模式 ("quiet"/"normal"/"verbose"/"stream")
            text_callback: 文本更新回调
            progress_callback: 进度更新回调
            error_callback: 错误回调
            
        Returns:
            bool: 是否启用成功
        """
        if not self._MULTIMODAL_AVAILABLE:
            logger.info("[EnhancedAgentChat] 多模态输出不可用")
            return False
        
        try:
            # 创建多模态管理器
            mode_enum = getattr(self._OutputMode, mode.upper(), self._OutputMode.NORMAL)
            self._multimodal_manager = self._MultimodalOutputManager(mode=mode_enum)
            
            # 设置回调
            if text_callback:
                self._multimodal_manager.set_text_callback(text_callback)
            if progress_callback:
                self._multimodal_manager.set_progress_callback(progress_callback)
            if error_callback:
                self._multimodal_manager.set_error_callback(error_callback)
            
            self._enable_multimodal = True
            logger.info(f"[EnhancedAgentChat] 多模态输出已启用，模式: {mode}")
            return True
            
        except Exception as e:
            logger.info(f"[EnhancedAgentChat] 启用多模态输出失败: {e}")
            return False
    
    def disable_multimodal(self) -> None:
        """禁用多模态输出"""
        if self._multimodal_manager:
            self._multimodal_manager.close()
            self._multimodal_manager = None
        self._enable_multimodal = False
    
    def set_progress(self, stage: str, progress: float, message: str = "") -> None:
        """
        设置进度显示
        
        Args:
            stage: 阶段名称
            progress: 进度 0.0-1.0
            message: 消息
        """
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_progress_update(stage, progress, message)
    
    def show_error(self, error: str, recoverable: bool = True) -> None:
        """
        显示错误
        
        Args:
            error: 错误消息
            recoverable: 是否可恢复
        """
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_error(error, recoverable)
    
    def start_progress(self, stage: str, total_steps: int = 5) -> None:
        """
        开始进度追踪
        
        Args:
            stage: 阶段名称
            total_steps: 总步数
        """
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_progress_start(stage, total_steps)
    
    def complete_progress(self, message: str = "完成") -> None:
        """完成进度"""
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_progress_complete("任务", message)
    
    def output_stream(self, text: str, delay: float = 0.02) -> None:
        """
        流式输出文本
        
        Args:
            text: 文本内容
            delay: 字符延迟
        """
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_text(text, stream=True)
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        task_id: str = "default",
        operation_name: str = "操作",
        max_retries: int = 3,
        **kwargs,
    ) -> Any:
        """
        执行带重试的操作
        
        Args:
            func: 要执行的函数
            task_id: 任务 ID
            operation_name: 操作名称
            max_retries: 最大重试次数
            **kwargs: 额外参数
            
        Returns:
            函数执行结果
        """
        # 创建重试策略
        retry_policy = self._RetryPolicy(
            max_retries=max_retries,
            initial_delay=1.0,
            exponential_base=2.0,
        )
        executor = self._RecoveryExecutor(retry_policy=retry_policy)
        
        # 定义重试回调
        def on_retry(error, attempt):
            msg = f"重试 {attempt}/{max_retries}: {error}"
            if self._enable_multimodal and self._multimodal_manager:
                self._multimodal_manager.output_warning(msg)
            else:
                logger.info(f"[EnhancedAgentChat] {msg}")
        
        try:
            return executor.execute(
                func, *args,
                task_id=task_id,
                operation_name=operation_name,
                on_retry=on_retry,
                **kwargs,
            )
        except Exception as e:
            self.show_error(str(e))
            raise
    
    def analyze_intent(
        self,
        message: str,
        use_context: bool = True
    ) -> IntentAnalysis:
        """
        分析用户消息意图
        
        Args:
            message: 用户消息
            use_context: 是否使用上下文
            
        Returns:
            IntentAnalysis: 意图分析结果
        """
        if not self._intent_classifier:
            return IntentAnalysis(
                intent=ChatIntent.UNKNOWN,
                confidence=0.5,
                category=IntentCategory.OTHER
            )
        
        context = None
        if use_context and self._context_manager:
            context = self._context_manager.get_context(self.session_id)
        
        return self._intent_classifier.classify(message, context)
    
    def chat(
        self,
        message: str,
        max_wait: float = 30.0,
        stream_callback: Optional[Callable[[str], None]] = None,
        force_compress: bool = False,
    ) -> str:
        """
        增强版 Chat 入口
        
        Args:
            message: 用户消息
            max_wait: 最大等待时间
            stream_callback: 流式输出回调
            force_compress: 强制压缩（忽略短查询）
            
        Returns:
            str: Agent 响应
        """
        original_message = message
        intent_analysis: Optional[IntentAnalysis] = None
        
        # === Phase 4: 多模态输出 - 开始阶段 ===
        if self._enable_multimodal and self._multimodal_manager:
            self._multimodal_manager.output_progress_start("AI 处理", 5)
        
        try:
            # 1. 意图识别
            if self.enable_intent:
                if self._enable_multimodal:
                    self._multimodal_manager.output_progress_update("AI 处理", 0.1, "分析意图...")
                intent_analysis = self.analyze_intent(message)
                
                if self._on_intent_detected:
                    self._on_intent_detected(intent_analysis)
            
            # 2. Query 压缩
            if self.enable_compress and self._query_compressor:
                compressed = self._query_compressor.compress(
                    message,
                    force=force_compress
                )
                
                if compressed != message and self._on_compress:
                    self._on_compress(original_message, compressed)
                
                message = compressed
            
            # 3. 添加到上下文历史（用户消息）
            if self.enable_context and self._context_manager:
                self._context_manager.add_message(
                    self.session_id,
                    'user',
                    message,
                    intent_analysis.intent if intent_analysis else None,
                    metadata={
                        'original': original_message,
                        'compressed': message != original_message
                    }
                )
            
            # 4. 调用原始 chat
            if self._enable_multimodal:
                self._multimodal_manager.output_progress_update("AI 处理", 0.3, "生成响应...")
            
            def wrapper_callback(delta: str):
                if stream_callback:
                    stream_callback(delta)
                if self.base_chat.on_message:
                    self.base_chat.on_message(delta)
            
            # 临时替换回调
            original_on_message = self.base_chat.on_message
            self.base_chat.on_message = wrapper_callback
            
            try:
                response = self.base_chat.chat(message, max_wait)
            except Exception as e:
                # 错误处理
                if self._enable_multimodal and self._multimodal_manager:
                    self._multimodal_manager.output_error(str(e))
                raise
            finally:
                # 恢复回调
                self.base_chat.on_message = original_on_message
            
            # 5. 添加响应到历史
            if self.enable_context and self._context_manager:
                self._context_manager.add_message(
                    self.session_id,
                    'assistant',
                    response
                )
                
                # 触发上下文更新回调
                if self._on_context_update:
                    ctx = self._context_manager.get_context(self.session_id)
                    self._on_context_update(ctx)
            
            # 6. 生成追问（如果启用）
            if self.enable_guidance and self._guidance_generator and intent_analysis:
                ctx = None
                if self._context_manager:
                    ctx = self._context_manager.get_context(self.session_id)
                
                # 检查是否应该显示追问
                if self._guidance_generator.should_show_guidance(
                    intent_analysis.intent,
                    ctx,
                    len(response)
                ):
                    guidance = self._guidance_generator.generate(
                        intent=intent_analysis.intent,
                        response=response,
                        context=ctx,
                        user_message=original_message
                    )
                    self._last_guidance = guidance
                    
                    # 触发追问回调
                    if self._on_guidance_generated:
                        self._on_guidance_generated(guidance)
            
            # === Phase 4: 多模态输出 - 完成 ===
            if self._enable_multimodal and self._multimodal_manager:
                self._multimodal_manager.output_progress_complete("AI 处理", "完成")
            
            return response
            
        except Exception as e:
            # === Phase 4: 错误处理 ===
            if self._enable_multimodal and self._multimodal_manager:
                self._multimodal_manager.output_error(str(e), recoverable=True)
            raise
    
    def analyze_code_intent(self, query: str) -> Optional[Any]:
        """
        ⭐ 分析代码专用意图（使用 IntentEngine）
        
        比通用 analyze_intent 更细粒度，适合代码开发场景。
        
        Returns:
            Intent: 结构化代码意图，包含：
            - intent_type: 意图类型（CODE_GENERATION, DEBUGGING 等）
            - action: 动作（编写/修改/调试等）
            - target: 目标（登录接口/缓存模块等）
            - tech_stack: 技术栈（FastAPI, Redis 等）
            - constraints: 约束条件
            - confidence: 置信度
            - suggested_model: 建议使用的模型
        """
        if not self._intent_engine:
            return None
        
        return self._intent_engine.parse(query)
    
    def get_code_intent_explanation(self, query: str) -> str:
        """获取代码意图的详细解释（用于调试）"""
        if not self._intent_engine:
            return "IntentEngine 未启用"
        
        intent = self._intent_engine.parse(query)
        return self._intent_engine.explain(intent)

    # ============== 代码签名化 API ==============

    def signaturize_code(self, code: str) -> Optional[Any]:
        """
        签名化代码（大幅压缩上下文）

        用 1% 的 Token 传递 99% 的意图。

        Returns:
            SignatureResult: 签名化结果，包含：
            - signature_code: 签名化后的代码
            - compression_ratio: 压缩比例
            - saved_ratio: 节省比例
            - elements: 提取的代码元素
        """
        if not self._code_signer:
            return None

        return self._code_signer.signaturize(code)

    def build_layered_context(
        self,
        query: str,
        intent_type: str = "general",
        target_file: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        构建分层上下文（按需加载）

        根据任务复杂度动态选择上下文层级：
        - L1: 文件概览（~64 tokens）
        - L2: 符号索引（~256 tokens）
        - L3: 相关代码（~1K tokens）
        - L4: 完整实现（~4K tokens）
        - L5: 全部代码（~16K tokens）

        Args:
            query: 用户查询
            intent_type: 意图类型
            target_file: 目标文件路径

        Returns:
            (context, level_name): 上下文内容和层级名称
        """
        if not self._code_signer:
            return "", "unavailable"

        # 延迟初始化符号索引
        if self._symbol_index is None and hasattr(self.base_chat.agent, 'project_root'):
            self._symbol_index = SymbolIndex()
            self._symbol_index.build_from_project(self.base_chat.agent.project_root)

        # 构建分层上下文
        builder = LayeredContextBuilder(self._symbol_index)
        context, level = builder.build_context(query, intent_type, target_file)

        return context, level.name

    def add_incremental_context(
        self,
        level: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """
        添加增量上下文（累加而非重置）

        持续追踪对话历史中的上下文。
        """
        if not self._incremental_context:
            return

        ctx_level = ContextLevel[f"L{level[-1]}_FILE_OVERVIEW"] if "L1" in level else ContextLevel.L2_SYMBOL_INDEX
        self._incremental_context.add_context(ctx_level, content, metadata)

    def get_incremental_summary(self) -> str:
        """获取增量上下文摘要"""
        if not self._incremental_context:
            return ""
        return self._incremental_context.get_context_summary()

    # ============== 代码澄清 API ==============

    def start_code_clarify(
        self,
        requirement: str,
        context_files: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        开始代码澄清会话

        Args:
            requirement: 代码需求描述
            context_files: 上下文文件列表（用于自动检测技术栈）

        Returns:
            澄清会话状态，包含问题列表
        """
        if not self._code_clarifier:
            return None

        session = self._code_clarifier.start_session(
            requirement=requirement,
            context_files=context_files
        )
        self._clarify_sessions[session["session_id"]] = session
        return session

    def get_clarify_questions(
        self,
        session_id: str,
        answered_field: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取澄清问题

        Args:
            session_id: 会话 ID
            answered_field: 已回答的字段（触发后续问题）

        Returns:
            问题列表
        """
        if not self._code_clarifier:
            return []

        session = self._clarify_sessions.get(session_id)
        if not session:
            return []

        return self._code_clarifier.get_next_questions(session, answered_field)

    def answer_clarify(
        self,
        session_id: str,
        field: str,
        value: Any
    ) -> Dict[str, Any]:
        """
        回答澄清问题

        Args:
            session_id: 会话 ID
            field: 字段名
            value: 回答值

        Returns:
            更新后的会话状态
        """
        if not self._code_clarifier:
            return {}

        session = self._clarify_sessions.get(session_id)
        if not session:
            return {}

        updated = self._code_clarifier.answer(session, field, value)
        self._clarify_sessions[session_id] = updated
        return updated

    def get_code_suggestions(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取代码建议

        Args:
            session_id: 会话 ID

        Returns:
            建议列表
        """
        if not self._code_clarifier:
            return []

        session = self._clarify_sessions.get(session_id)
        if not session:
            return []

        return self._code_clarifier.get_code_suggestions(session)

    def complete_code_clarify(self, session_id: str) -> Dict[str, Any]:
        """
        完成代码澄清会话

        Args:
            session_id: 会话 ID

        Returns:
            完整的代码需求信息
        """
        if not self._code_clarifier:
            return {}

        final = self._code_clarifier.complete_session(
            {"session_id": session_id}
        )
        if session_id in self._clarify_sessions:
            del self._clarify_sessions[session_id]
        return final

    def quick_code_clarify(self, requirement: str) -> Dict[str, Any]:
        """
        快速代码澄清（无需手动管理会话）

        Args:
            requirement: 代码需求描述

        Returns:
            完整的代码需求信息
        """
        if not self._code_clarifier:
            return {}

        return self._code_clarifier.start_session(requirement) or \
               self._code_clarifier.complete_session({})

    # ============== IDE 上下文注入 API ==============

    def set_project_root(self, project_root: str):
        """
        设置项目根目录

        Args:
            project_root: 项目根目录路径
        """
        if not IDE_CONTEXT_INJECTOR_AVAILABLE:
            return

        self._ide_context_injector = IDEContextInjector(project_root=project_root)
        logger.info(f"[EnhancedAgentChat] Project root set: {project_root}")

    def set_active_file(self, file_path: str):
        """
        设置当前活跃文件

        Args:
            file_path: 活跃文件的绝对路径
        """
        self._active_file = file_path
        if self._ide_context_injector:
            self._ide_context_injector.set_active_file(file_path)

    def get_ide_context(
        self,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
        include_content: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        获取 IDE 上下文

        Args:
            active_file: 当前活跃文件
            query: 用户查询（用于相关性排序）
            include_content: 是否包含文件内容

        Returns:
            IDE 上下文字典
        """
        if not self._ide_context_injector:
            return None

        # 使用指定的文件或当前的活跃文件
        file_path = active_file or self._active_file

        ctx = self._ide_context_injector.get_context(
            active_file=file_path,
            query=query,
            include_content=include_content,
        )
        self._ide_context = ctx
        return ctx.to_dict()

    def get_ide_context_text(self, query: Optional[str] = None) -> str:
        """
        获取适合 LLM 的 IDE 上下文文本

        Args:
            query: 用户查询

        Returns:
            格式化的上下文文本
        """
        if not self._ide_context_injector:
            return ""

        return self._ide_context_injector.get_context_for_llm(
            active_file=self._active_file,
            query=query,
        )

    def inject_ide_context(
        self,
        active_file: Optional[str] = None,
        query: Optional[str] = None,
    ) -> str:
        """
        获取并注入 IDE 上下文到系统提示

        Args:
            active_file: 当前活跃文件
            query: 用户查询

        Returns:
            上下文文本
        """
        context_text = self.get_ide_context_text(query)

        # 更新活跃文件
        if active_file:
            self.set_active_file(active_file)

        return context_text

    def get_project_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取项目统计信息

        Returns:
            项目统计字典
        """
        if not self._ide_context_injector:
            return None

        stats = self._ide_context_injector.scan_project()
        return stats.to_dict()

    def get_context_info(self) -> Dict[str, Any]:
        """获取上下文信息"""
        if not self._context_manager:
            return {}
        
        ctx = self._context_manager.get_context(self.session_id)
        history = self._context_manager.get_history(self.session_id)
        
        return {
            'session_id': self.session_id,
            'message_count': ctx.message_count,
            'topic': ctx.topic,
            'intents': [i.value for i in ctx.intents],
            'last_intent': ctx.last_intent.value if ctx.last_intent else None,
            'followup_count': ctx.followup_count,
            'history_length': len(history),
            'language': getattr(ctx, 'language', ''),
        }
    
    def get_conversation_summary(self) -> str:
        """获取对话总结"""
        if not self._context_manager:
            return ""
        return self._context_manager.get_conversation_summary(self.session_id)
    
    def clear_context(self):
        """清除上下文"""
        if self._context_manager:
            self._context_manager.clear_session(self.session_id)
    
    def clear_cache(self):
        """清除压缩缓存"""
        if self._query_compressor:
            self._query_compressor.clear_cache()


# ============== 便捷工厂 ==============

def enhance_agent_chat(
    base_chat,
    enable_intent: bool = True,
    enable_compress: bool = True,
    enable_context: bool = True,
    enable_guidance: bool = True,
    max_guidance_questions: int = 3,
) -> EnhancedAgentChat:
    """
    增强现有 AgentChat
    
    Args:
        base_chat: AgentChat 实例
        enable_intent: 启用意图识别
        enable_compress: 启用 Query 压缩
        enable_context: 启用上下文管理
        enable_guidance: 启用追问生成
        max_guidance_questions: 最大追问数量
        
    Returns:
        EnhancedAgentChat: 增强版
    """
    return EnhancedAgentChat(
        base_chat=base_chat,
        enable_intent=enable_intent,
        enable_compress=enable_compress,
        enable_context=enable_context,
        enable_guidance=enable_guidance,
        max_guidance_questions=max_guidance_questions
    )


# ============== 使用示例 ==============

def example_usage():
    """使用示例"""
    from core.agent_chat import create_agent_chat
from core.logger import get_logger
logger = get_logger('agent_chat_enhancer')

    
    # 1. 创建基础 AgentChat
    base_chat = create_agent_chat()
    
    # 2. 增强
    chat = enhance_agent_chat(
        base_chat,
        enable_intent=True,
        enable_compress=True,
        enable_context=True
    )
    
    # 3. 设置回调
    def on_intent(intent: IntentAnalysis):
        logger.info(f"[意图] {intent.intent.value} ({intent.confidence:.0%})")
        logger.info(f"[分类] {intent.category.value}")
        logger.info(f"[模型] {intent.suggested_model}")
        logger.info(f"[语言] {intent.language or 'N/A'}")
        if intent.need_knowledge:
            logger.info("[知识] 需要检索知识库")
        if intent.need_deep_search:
            logger.info("[搜索] 需要深度搜索")
        if intent.entities:
            logger.info(f"[实体] {intent.entities}")
    
    def on_compress(original: str, compressed: str):
        logger.info(f"[压缩] {len(original)} → {len(compressed)} 字")
    
    chat.set_intent_callback(on_intent)
    chat.set_compress_callback(on_compress)
    
    # 4. 测试各种场景
    test_messages = [
        "你好，今天天气怎么样？",
        "帮我写一个快速排序函数",
        "为什么 Python 比 Java 快？",
        "把这段话翻译成英文",
        "总结一下这篇文章的主要内容",
        "这个bug怎么解决",
        "假设有100万用户，如何设计数据库",
    ]
    
    logger.info("\n" + "=" * 60)
    logger.info("通用意图识别测试")
    logger.info("=" * 60)
    
    for msg in test_messages:
        logger.info(f"\n>>> {msg}")
        # 仅测试意图分析
        intent = chat.analyze_intent(msg)
        logger.info(f"    意图: {intent.intent.value} ({intent.confidence:.0%})")
        logger.info(f"    分类: {intent.category.value}")
        logger.info(f"    模型: {intent.suggested_model}")
    
    logger.info("\n" + "=" * 60)


def quick_test():
    """快速测试"""
    logger.info("=" * 60)
    logger.info("Agent Chat 增强模块 - 通用意图识别测试")
    logger.info("=" * 60)
    
    classifier = ChatIntentClassifier()
    
    # 测试用例
    test_cases = [
        # 对话类
        ("你好啊", "greeting", "问候"),
        ("今天心情不错", "chitchat", "闲聊"),
        ("什么是量子计算", "question", "问答"),
        
        # 推理类
        ("如果明天降温，我就穿外套", "reasoning", "推理"),
        ("计算 123 * 456", "mathematics", "数学"),
        ("分析一下这个产品的优劣势", "analysis", "分析"),
        
        # 任务类
        ("帮我写个登录函数", "code_generation", "代码生成"),
        ("检查这段代码", "code_review", "代码审查"),
        ("程序报错了怎么办", "debugging", "调试"),
        ("打开 config.json", "file_operation", "文件操作"),
        ("帮我运行测试", "task_execution", "任务执行"),
        
        # 创作类
        ("写一封请假邮件", "writing", "写作"),
        ("翻译成日语", "translation", "翻译"),
        ("总结会议要点", "summarization", "摘要"),
        ("给我一些创业灵感", "creative", "创意"),
        
        # 知识类
        ("查找机器学习的资料", "knowledge_query", "知识查询"),
        ("搜索一下最新新闻", "search", "搜索"),
    ]
    
    passed = 0
    for text, expected, desc in test_cases:
        result = classifier.classify(text)
        match = "✓" if result.intent.value == expected else "✗"
        if match == "✓":
            passed += 1
        logger.info(f"{match} {text[:20]:<20} → {result.intent.value:<18} (期望: {expected:<18}) {desc}")
    
    print()
    logger.info(f"准确率: {passed}/{len(test_cases)} ({passed/len(test_cases)*100:.0f}%)")
    logger.info("=" * 60)


if __name__ == "__main__":
    quick_test()
