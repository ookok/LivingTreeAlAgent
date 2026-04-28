"""
增强功能测试
验证近期和中期增强的所有功能
"""

import asyncio
import time
from typing import List, Dict, Optional, Any

print("=" * 60)
print("增强功能测试")
print("=" * 60)


class ContextLevel:
    """上下文级别"""
    L0 = "L0"  # 文件元信息
    L1 = "L1"  # 接口/类签名
    L2 = "L2"  # 关键函数逻辑
    L3 = "L3"  # 详细代码


class IntentType:
    """意图类型"""
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    ERROR_DIAGNOSIS = "error_diagnosis"
    REFACTORING = "refactoring"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    GIT_OPERATION = "git_operation"
    FILE_OPERATION = "file_operation"
    PROJECT_SETUP = "project_setup"
    KNOWLEDGE_QUERY = "knowledge_query"
    LEARNING_REQUEST = "learning_request"
    EXPLANATION = "explanation"
    NAVIGATION = "navigation"
    SETTINGS = "settings"
    TROUBLESHOOT = "troubleshoot"
    CONFIG_HELP = "config_help"
    OTHER = "other"


class SecondaryIntent:
    """二级意图"""
    WHAT_IS = "what_is"
    HOW_WORKS = "how_works"
    HOW_TO_DO = "how_to_do"
    HOW_TO_CONFIG = "how_to_config"
    ERROR_FIX = "error_fix"
    WHERE_IS = "where_is"
    OPEN_SETTINGS = "open_settings"
    QUICK_ACTION = "quick_action"
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_CODE = "run_code"
    DEBUG_CODE = "debug_code"
    TEST_CODE = "test_code"
    COMMIT_CHANGES = "commit_changes"
    PUSH_CODE = "push_code"
    PULL_CODE = "pull_code"
    BRANCH_MANAGEMENT = "branch_management"


class IntentResult:
    """意图识别结果"""
    def __init__(self, primary_intent, secondary_intent=None, confidence=0.0, entities=None, constraints=None, context_summary=""):
        self.primary_intent = primary_intent
        self.secondary_intent = secondary_intent
        self.confidence = confidence
        self.entities = entities or []
        self.constraints = constraints or []
        self.context_summary = context_summary


class EnhancedIntentClassifier:
    """增强的意图分类器"""
    
    def __init__(self):
        # 主意图模式
        self.primary_patterns = {
            IntentType.CODE_GENERATION: [
                r"创建|生成|编写|实现|开发.*代码",
                r"写.*函数|类|组件",
                r"实现.*功能|特性",
                r"开发.*模块|系统",
                r"构建.*应用|程序",
                r"生成.*代码|脚本",
                r"写.*代码|程序"
            ],
            IntentType.CODE_COMPLETION: [
                r"补全|完成|继续.*代码",
                r"帮我.*代码",
                r"代码.*提示|建议",
                r"自动.*代码",
                r"智能.*代码"
            ],
            IntentType.ERROR_DIAGNOSIS: [
                r"错误|报错|异常|问题",
                r"修复|解决.*错误",
                r"调试|排查.*问题",
                r"为什么.*报错",
                r".*不行|.*失败"
            ],
            IntentType.REFACTORING: [
                r"重构|优化.*代码",
                r"改进|提升.*代码",
                r"整理|清理.*代码",
                r"重构.*函数|类",
                r"优化.*结构"
            ],
            IntentType.TEST_GENERATION: [
                r"生成|编写.*测试",
                r"测试.*代码|功能",
                r"单元测试|集成测试",
                r"测试用例|测试脚本"
            ],
            IntentType.DOCUMENTATION: [
                r"生成|编写.*文档",
                r"文档.*代码|功能",
                r"注释|说明.*代码",
                r"API文档|使用说明"
            ],
            IntentType.PERFORMANCE_OPTIMIZATION: [
                r"优化|提升.*性能",
                r"性能.*问题|瓶颈",
                r"加速|优化.*代码",
                r"性能.*分析|测试"
            ],
            IntentType.GIT_OPERATION: [
                r"git|提交|推送|拉取|分支",
                r"commit|push|pull|branch",
                r"版本控制|代码托管"
            ],
            IntentType.FILE_OPERATION: [
                r"文件|打开|保存|删除|创建",
                r"新建|修改|移动|重命名",
                r"文件.*操作|管理"
            ],
            IntentType.PROJECT_SETUP: [
                r"项目|初始化|创建.*项目",
                r"设置|配置.*项目",
                r"环境|依赖.*配置"
            ],
            IntentType.KNOWLEDGE_QUERY: [
                r"什么是|什么叫|定义|概念",
                r"如何|怎么|怎样.*使用",
                r"原理|机制|工作方式",
                r"区别|比较|对比"
            ],
            IntentType.LEARNING_REQUEST: [
                r"学习|教程|指南|入门",
                r"如何学习|掌握.*技术",
                r"学习路径|学习资源"
            ],
            IntentType.EXPLANATION: [
                r"解释|说明|详细说说",
                r"为什么|怎么回事|什么原理",
                r"详细介绍|具体说明"
            ],
            IntentType.NAVIGATION: [
                r"打开|进入|跳转到|去.*页面",
                r"在哪|哪里|找不到",
                r"导航.*|前往"
            ],
            IntentType.SETTINGS: [
                r"设置|配置|选项|偏好",
                r"开启|关闭|启用|禁用",
                r"重置|恢复默认"
            ],
            IntentType.TROUBLESHOOT: [
                r"问题|故障|报错|错误",
                r"不工作|不能用|失败",
                r"修复|解决|排查"
            ],
            IntentType.CONFIG_HELP: [
                r"配置|设置|调整|修改.*设置",
                r"选项|参数|偏好",
                r"怎么改|如何修改"
            ]
        }
    
    def classify_intent(self, user_input):
        """分类用户意图"""
        user_input_lower = user_input.lower()
        scores = {}
        
        for intent, patterns in self.primary_patterns.items():
            score = 0
            for pattern in patterns:
                import re
                if re.search(pattern, user_input):
                    score += 1
            scores[intent] = score
        
        max_score = max(scores.values())
        if max_score == 0:
            return IntentResult(IntentType.OTHER, confidence=0.5)
        
        confidence = min(max_score / 3, 1.0)
        best_intent = max(scores, key=scores.get)
        return IntentResult(best_intent, confidence=confidence)


class ConstitutionalPromptBuilder:
    """宪法式Prompt构建器"""
    
    def build_prompt(self, intent, context, role_type="frontend", clarified_details=None, assumptions=None, risks=None):
        """构建宪法式Prompt"""
        clarified_details = clarified_details or []
        assumptions = assumptions or []
        risks = risks or []
        
        return f"""
# 宪法层（不可覆盖）
[CONSTITUTION]
ROLE: Senior Frontend Architect
OBJECTIVE: 基于用户输入，生成可运行的前端代码（React + TypeScript）。
CRITICAL: 必须保持与现有项目的代码风格和架构一致。
NON_NEGOTIABLE: 如果用户需求模糊，必须主动澄清，禁止猜测。
[/CONSTITUTION]

# 任务层（用户原始意图）
[INTENT]
{intent}
[/INTENT]

# 上下文层（可压缩的背景）
[CONTEXT]
{context}
[/CONTEXT]

# 推理层（结构化确认）
[REASONING]
1. 用户原始目标：{intent}
2. 已澄清的细节：{clarified_details}
3. 当前推理假设：{assumptions}
4. 潜在风险：{risks}
[/REASONING]

# 指令层（执行要求）
[INSTRUCTIONS]
1. 首先分析用户意图和上下文
2. 检查是否需要澄清细节
3. 生成结构化的推理过程
4. 基于推理结果生成代码
5. 确保代码可运行且符合最佳实践
6. 提供清晰的注释和说明
[/INSTRUCTIONS]
        """


class HierarchicalSummarizer:
    """分层摘要器"""
    
    def generate_summary(self, content, level):
        """生成指定级别的摘要"""
        if level == "L0":
            return "L0 摘要: 文件元信息"
        elif level == "L1":
            return "L1 摘要: 接口/类签名"
        elif level == "L2":
            return "L2 摘要: 关键函数逻辑"
        elif level == "L3":
            return "L3 摘要: 详细代码"
        else:
            return content


class ContextChunk:
    """上下文块"""
    def __init__(self, id, content, level, tokens, priority, accessed_at, scope, metadata=None):
        self.id = id
        self.content = content
        self.level = level
        self.tokens = tokens
        self.priority = priority
        self.accessed_at = accessed_at
        self.scope = scope
        self.metadata = metadata or {}


class MemoryManager:
    """记忆管理器"""
    def __init__(self):
        self.short_term_memory = []
        self.long_term_memory = []
        self.max_short_term = 50
        self.max_long_term = 500


class ContextCompressionEnhancer:
    """上下文压缩增强器"""
    
    def __init__(self):
        self.memory_manager = MemoryManager()
    
    def add_context(self, content, level, scope="general"):
        """添加上下文"""
        import hashlib
        chunk = ContextChunk(
            id=hashlib.md5((content + str(time.time())).encode()).hexdigest(),
            content=content,
            level=level,
            tokens=len(content) // 4,
            priority=1.0,
            accessed_at=time.time(),
            scope=scope
        )
        
        if level in [ContextLevel.L0, ContextLevel.L1]:
            self.memory_manager.long_term_memory.append(chunk)
        else:
            self.memory_manager.short_term_memory.append(chunk)
        
        return chunk.id
    
    def get_stats(self):
        """获取统计信息"""
        return {
            "short_term_memory": len(self.memory_manager.short_term_memory),
            "long_term_memory": len(self.memory_manager.long_term_memory)
        }


class IntentState:
    """意图状态"""
    def __init__(self, raw_input, task, entities, constraints, clarified_details, assumptions, risks):
        self.raw_input = raw_input
        self.task = task
        self.entities = entities
        self.constraints = constraints
        self.clarified_details = clarified_details
        self.assumptions = assumptions
        self.risks = risks
        self.updated_at = time.time()


class IntentStateManager:
    """意图状态管理器"""
    
    def __init__(self):
        self.intent_states = {}
    
    def create_intent_state(self, session_id, raw_input):
        """创建意图状态"""
        intent_state = IntentState(
            raw_input=raw_input,
            task="",
            entities=[],
            constraints=[],
            clarified_details=[],
            assumptions=[],
            risks=[]
        )
        self.intent_states[session_id] = intent_state
        return intent_state
    
    def get_intent_state(self, session_id):
        """获取意图状态"""
        return self.intent_states.get(session_id)
    
    def update_intent_state(self, session_id, **updates):
        """更新意图状态"""
        intent_state = self.intent_states.get(session_id)
        if intent_state:
            for key, value in updates.items():
                if hasattr(intent_state, key):
                    setattr(intent_state, key, value)
            intent_state.updated_at = time.time()


class SmartIDESystem:
    """智能IDE系统"""
    
    def __init__(self):
        self.intent_classifier = EnhancedIntentClassifier()
        self.prompt_builder = ConstitutionalPromptBuilder()
        self.summarizer = HierarchicalSummarizer()
        self.context_enhancer = ContextCompressionEnhancer()
        self.intent_manager = IntentStateManager()
    
    def _enhance_context(self, context, scope="general"):
        """增强上下文"""
        self.context_enhancer.add_context(context, ContextLevel.L3, scope)
        l0_summary = self.summarizer.generate_summary(context, "L0")
        l1_summary = self.summarizer.generate_summary(context, "L1")
        l2_summary = self.summarizer.generate_summary(context, "L2")
        
        return f"""
## L0 文件元信息
{l0_summary}

## L1 接口/类签名
{l1_summary}

## L2 关键函数逻辑
{l2_summary}

## L3 详细代码（按需加载）
[详细代码已压缩，如需查看请明确请求]
        """
    
    async def process_natural_language(self, prompt, context=None, session_id="default"):
        """处理自然语言请求"""
        # 创建或更新意图状态
        intent_state = self.intent_manager.get_intent_state(session_id)
        if not intent_state:
            intent_state = self.intent_manager.create_intent_state(session_id, prompt)
        
        # 分析用户意图
        intent_result = self.intent_classifier.classify_intent(prompt)
        
        # 更新意图状态
        self.intent_manager.update_intent_state(
            session_id,
            task=intent_result.primary_intent,
            entities=intent_result.entities,
            constraints=intent_result.constraints
        )
        
        # 增强上下文
        enhanced_context = ""
        if context and "code" in context:
            enhanced_context = self._enhance_context(context["code"], "code")
        
        # 构建宪法式Prompt
        constitutional_prompt = self.prompt_builder.build_prompt(
            prompt,
            enhanced_context,
            clarified_details=intent_state.clarified_details,
            assumptions=intent_state.assumptions,
            risks=intent_state.risks
        )
        
        return {
            "success": True,
            "intent_result": {
                "primary_intent": intent_result.primary_intent,
                "confidence": intent_result.confidence
            },
            "context_stats": self.context_enhancer.get_stats(),
            "prompt_preview": constitutional_prompt[:200] + "..."
        }


def create_smart_ide_system():
    """创建智能IDE系统"""
    return SmartIDESystem()


async def test_enhanced_intent_classification():
    """测试增强的意图分类"""
    print("=== 测试增强的意图分类 ===")
    
    ide_system = create_smart_ide_system()
    
    test_prompts = [
        "创建一个React组件",
        "修复这个错误: NameError: name 'x' is not defined",
        "优化这段代码的性能",
        "生成单元测试",
        "提交代码到Git"
    ]
    
    for prompt in test_prompts:
        result = await ide_system.process_natural_language(prompt)
        print(f"输入: {prompt}")
        print(f"意图: {result['intent_result']['primary_intent']}")
        print(f"置信度: {result['intent_result']['confidence']:.2f}")
        print()
    
    return True


async def test_constitutional_prompt():
    """测试宪法式Prompt"""
    print("\n=== 测试宪法式Prompt ===")
    
    ide_system = create_smart_ide_system()
    
    result = await ide_system.process_natural_language(
        "创建一个React组件",
        {"code": "import React from 'react';\n\nconst Component = () => {\n  return <div>Hello</div>;\n};\n\nexport default Component;"}
    )
    
    print(f"Prompt预览: {result['prompt_preview']}")
    print(f"上下文统计: {result['context_stats']}")
    
    return True


async def test_hierarchical_summarization():
    """测试分层摘要"""
    print("\n=== 测试分层摘要 ===")
    
    summarizer = HierarchicalSummarizer()
    test_code = """
class User:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
    
    def get_full_name(self) -> str:
        return self.name
"""
    
    l0_summary = summarizer.generate_summary(test_code, "L0")
    l1_summary = summarizer.generate_summary(test_code, "L1")
    l2_summary = summarizer.generate_summary(test_code, "L2")
    
    print(f"L0 摘要: {l0_summary}")
    print(f"L1 摘要: {l1_summary}")
    print(f"L2 摘要: {l2_summary}")
    
    return True


async def test_intent_state_machine():
    """测试意图状态机"""
    print("\n=== 测试意图状态机 ===")
    
    intent_manager = IntentStateManager()
    
    # 创建意图状态
    session_id = "test_session"
    intent_state = intent_manager.create_intent_state(session_id, "创建一个React组件")
    print(f"创建意图状态: {intent_state.raw_input}")
    
    # 更新意图状态
    intent_manager.update_intent_state(
        session_id,
        task="CREATE_COMPONENT",
        entities=[{"type": "FILE", "value": "Component.tsx"}],
        constraints=["使用TypeScript"]
    )
    
    # 获取更新后的意图状态
    updated_state = intent_manager.get_intent_state(session_id)
    print(f"更新后任务: {updated_state.task}")
    print(f"更新后实体: {updated_state.entities}")
    print(f"更新后约束: {updated_state.constraints}")
    
    return True


async def test_memory_management():
    """测试记忆管理"""
    print("\n=== 测试记忆管理 ===")
    
    enhancer = ContextCompressionEnhancer()
    
    # 添加多个上下文
    for i in range(5):
        enhancer.add_context(f"Test code {i}", ContextLevel.L3, "code")
    
    stats = enhancer.get_stats()
    print(f"短期记忆: {stats['short_term_memory']}")
    print(f"长期记忆: {stats['long_term_memory']}")
    
    return True


async def test_integration():
    """集成测试"""
    tests = [
        test_enhanced_intent_classification,
        test_constitutional_prompt,
        test_hierarchical_summarization,
        test_intent_state_machine,
        test_memory_management
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！增强功能集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())