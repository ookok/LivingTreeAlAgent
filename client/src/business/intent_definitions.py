"""
统一意图定义中心

将系统中所有意图集中管理，避免硬编码。

使用方式：
from business.intent_definitions import Intent

# 访问意图常量
intent = Intent.GREET
intent_name = Intent.get_name(intent)

# 检查意图类型
if Intent.is_general(intent):
    # 通用意图处理
"""

from enum import Enum
from typing import Dict, List, Optional, Set


class Intent(Enum):
    """
    系统意图枚举定义
    
    意图分类：
    - 通用意图 (General): 问候、感谢、告别等
    - 查询意图 (Query): 知识查询、文档查询、搜索等
    - 操作意图 (Action): 代码生成、错误修复、执行任务等
    - 系统意图 (System): 进化、配置、管理等
    - 回退意图 (Fallback): 无法识别的意图
    """
    
    # === 通用意图 ===
    GREET = "greet"                    # 问候
    GOODBYE = "goodbye"                # 告别
    THANKS = "thanks"                  # 感谢
    HELP = "help"                      # 求助
    
    # === 查询意图 ===
    QUERY_KNOWLEDGE = "query_knowledge"        # 知识查询
    DOCUMENT_QUERY = "document_query"          # 文档查询
    SEARCH_QUERY = "search_query"              # 搜索查询
    SIMPLE_QA = "simple_qa"                    # 简单问答
    
    # === 操作意图 ===
    CODE_GENERATION = "code_generation"        # 代码生成
    ERROR_RECOVERY = "error_recovery"          # 错误修复
    FORMAT整理 = "format整理"                  # 格式化整理
    JSON_EXTRACT = "json_extract"              # JSON提取
    TASK_EXECUTION = "task_execution"          # 任务执行
    
    # === 系统意图 ===
    EVOLUTION_DECISION = "evolution_decision"  # 进化决策
    CONFIGURATION = "configuration"            # 配置管理
    TRAINING = "training"                      # 训练
    CACHE_QUERY = "cached_query"               # 缓存查询
    
    # === 路由意图（来自L0）===
    SIMPLE_TASK = "simple_task"                # 简单任务
    COMPLEX_TASK = "complex_task"              # 复杂任务
    HUMAN_ESCALATION = "human_escalation"      # 转人工
    
    # === 回退意图 ===
    NLU_FALLBACK = "nlu_fallback"              # 无法识别
    
    # === 多模态意图 ===
    MULTI_MODAL_QUERY = "multi_modal_query"    # 多模态查询
    
    # === 新增意图 ===
    WEATHER_QUERY = "weather_query"            # 天气查询
    LONG_WRITING = "long_writing"              # 长篇写作
    COMPLEX_REASONING = "complex_reasoning"    # 复杂推理
    
    @classmethod
    def get_name(cls, intent: 'Intent') -> str:
        """获取意图显示名称"""
        names = {
            cls.GREET: "问候",
            cls.GOODBYE: "告别",
            cls.THANKS: "感谢",
            cls.HELP: "求助",
            cls.QUERY_KNOWLEDGE: "知识查询",
            cls.DOCUMENT_QUERY: "文档查询",
            cls.SEARCH_QUERY: "搜索查询",
            cls.SIMPLE_QA: "简单问答",
            cls.CODE_GENERATION: "代码生成",
            cls.ERROR_RECOVERY: "错误修复",
            cls.FORMAT整理: "格式整理",
            cls.JSON_EXTRACT: "JSON提取",
            cls.TASK_EXECUTION: "任务执行",
            cls.EVOLUTION_DECISION: "进化决策",
            cls.CONFIGURATION: "配置管理",
            cls.TRAINING: "训练",
            cls.CACHE_QUERY: "缓存查询",
            cls.SIMPLE_TASK: "简单任务",
            cls.COMPLEX_TASK: "复杂任务",
            cls.HUMAN_ESCALATION: "转人工",
            cls.NLU_FALLBACK: "无法识别",
            cls.MULTI_MODAL_QUERY: "多模态查询",
            cls.WEATHER_QUERY: "天气查询",
            cls.LONG_WRITING: "长篇写作",
            cls.COMPLEX_REASONING: "复杂推理",
        }
        return names.get(intent, intent.value)
    
    @classmethod
    def from_value(cls, value: str) -> Optional['Intent']:
        """从字符串值获取意图枚举"""
        try:
            return cls(value)
        except ValueError:
            return None
    
    @classmethod
    def is_general(cls, intent: 'Intent') -> bool:
        """是否为通用意图"""
        return intent in {cls.GREET, cls.GOODBYE, cls.THANKS, cls.HELP}
    
    @classmethod
    def is_query(cls, intent: 'Intent') -> bool:
        """是否为查询意图"""
        return intent in {cls.QUERY_KNOWLEDGE, cls.DOCUMENT_QUERY, cls.SEARCH_QUERY, cls.SIMPLE_QA}
    
    @classmethod
    def is_action(cls, intent: 'Intent') -> bool:
        """是否为操作意图"""
        return intent in {cls.CODE_GENERATION, cls.ERROR_RECOVERY, cls.FORMAT整理, 
                          cls.JSON_EXTRACT, cls.TASK_EXECUTION}
    
    @classmethod
    def is_system(cls, intent: 'Intent') -> bool:
        """是否为系统意图"""
        return intent in {cls.EVOLUTION_DECISION, cls.CONFIGURATION, cls.TRAINING, cls.CACHE_QUERY}
    
    @classmethod
    def is_fallback(cls, intent: 'Intent') -> bool:
        """是否为回退意图"""
        return intent == cls.NLU_FALLBACK
    
    @classmethod
    def get_all_intents(cls) -> List['Intent']:
        """获取所有意图列表"""
        return list(cls)
    
    @classmethod
    def get_intent_categories(cls) -> Dict[str, List['Intent']]:
        """获取意图分类"""
        return {
            "general": [cls.GREET, cls.GOODBYE, cls.THANKS, cls.HELP],
            "query": [cls.QUERY_KNOWLEDGE, cls.DOCUMENT_QUERY, cls.SEARCH_QUERY, cls.SIMPLE_QA],
            "action": [cls.CODE_GENERATION, cls.ERROR_RECOVERY, cls.FORMAT整理, 
                       cls.JSON_EXTRACT, cls.TASK_EXECUTION],
            "system": [cls.EVOLUTION_DECISION, cls.CONFIGURATION, cls.TRAINING, cls.CACHE_QUERY],
            "routing": [cls.SIMPLE_TASK, cls.COMPLEX_TASK, cls.HUMAN_ESCALATION],
            "fallback": [cls.NLU_FALLBACK],
            "multi_modal": [cls.MULTI_MODAL_QUERY],
            "other": [cls.WEATHER_QUERY, cls.LONG_WRITING, cls.COMPLEX_REASONING],
        }
    
    @classmethod
    def get_intent_keywords(cls) -> Dict[str, List[str]]:
        """获取意图关键词映射"""
        return {
            cls.GREET.value: ["你好", "您好", "hi", "hello", "嗨", "早上好", "晚上好", "早安"],
            cls.GOODBYE.value: ["再见", "拜拜", "再见了", "下次见", "回见", "拜拜了"],
            cls.THANKS.value: ["谢谢", "感谢", "太感谢了", "谢谢啦", "多谢"],
            cls.HELP.value: ["帮助", "求助", "帮忙", "怎么用", "使用说明"],
            cls.QUERY_KNOWLEDGE.value: ["什么是", "什么叫", "解释一下", "介绍一下", "说明", "什么"],
            cls.DOCUMENT_QUERY.value: ["文档", "手册", "指南", "资料", "查找", "手册在哪里"],
            cls.SEARCH_QUERY.value: ["查一下", "查询", "搜索", "库存", "行情", "价格"],
            cls.SIMPLE_QA.value: ["如何", "为什么", "哪个", "哪里", "何时"],
            cls.CODE_GENERATION.value: ["写代码", "代码", "编程", "python", "java", "函数", "方法"],
            cls.ERROR_RECOVERY.value: ["错误", "失败", "异常", "重试", "修复", "问题", "崩溃", "bug"],
            cls.FORMAT整理.value: ["整理", "格式化", "规范", "格式化输出"],
            cls.JSON_EXTRACT.value: ["提取", "json", "解析", "结构化"],
            cls.TASK_EXECUTION.value: ["执行", "运行", "开始", "启动", "任务"],
            cls.EVOLUTION_DECISION.value: ["进化", "升级", "优化", "训练", "自适应", "升级系统"],
            cls.CONFIGURATION.value: ["配置", "设置", "参数", "选项"],
            cls.TRAINING.value: ["训练", "学习", "训练模型", "微调"],
            cls.SIMPLE_TASK.value: ["简单", "快速", "基础", "普通"],
            cls.COMPLEX_TASK.value: ["复杂", "深入", "详细", "全面", "分析"],
            cls.WEATHER_QUERY.value: ["天气", "温度", "预报", "气候"],
            cls.LONG_WRITING.value: ["写一篇", "报告", "文章", "论文", "文档"],
            cls.COMPLEX_REASONING.value: ["分析", "推理", "论证", "深入分析"],
        }
    
    @classmethod
    def get_routing_map(cls) -> Dict[str, str]:
        """获取路由类型到意图的映射（兼容L0 Router）"""
        return {
            "cache": cls.CACHE_QUERY.value,
            "local": cls.SIMPLE_TASK.value,
            "search": cls.SEARCH_QUERY.value,
            "heavy": cls.COMPLEX_TASK.value,
            "human": cls.HUMAN_ESCALATION.value,
        }


# 便捷函数
def get_intent_by_keyword(keyword: str) -> Optional[Intent]:
    """通过关键词获取意图"""
    intent_keywords = Intent.get_intent_keywords()
    for intent_value, keywords in intent_keywords.items():
        if keyword in keywords:
            return Intent.from_value(intent_value)
    return None


def get_intent_category(intent: Intent) -> str:
    """获取意图所属分类"""
    categories = Intent.get_intent_categories()
    for category, intents in categories.items():
        if intent in intents:
            return category
    return "other"


def is_valid_intent(intent_str: str) -> bool:
    """检查是否为有效的意图字符串"""
    return Intent.from_value(intent_str) is not None


# 导出常用意图常量（兼容旧代码）
INTENT_GREET = Intent.GREET.value
INTENT_GOODBYE = Intent.GOODBYE.value
INTENT_THANKS = Intent.THANKS.value
INTENT_HELP = Intent.HELP.value
INTENT_QUERY_KNOWLEDGE = Intent.QUERY_KNOWLEDGE.value
INTENT_DOCUMENT_QUERY = Intent.DOCUMENT_QUERY.value
INTENT_SEARCH_QUERY = Intent.SEARCH_QUERY.value
INTENT_SIMPLE_QA = Intent.SIMPLE_QA.value
INTENT_CODE_GENERATION = Intent.CODE_GENERATION.value
INTENT_ERROR_RECOVERY = Intent.ERROR_RECOVERY.value
INTENT_FORMAT整理 = Intent.FORMAT整理.value
INTENT_JSON_EXTRACT = Intent.JSON_EXTRACT.value
INTENT_TASK_EXECUTION = Intent.TASK_EXECUTION.value
INTENT_EVOLUTION_DECISION = Intent.EVOLUTION_DECISION.value
INTENT_CONFIGURATION = Intent.CONFIGURATION.value
INTENT_TRAINING = Intent.TRAINING.value
INTENT_CACHE_QUERY = Intent.CACHE_QUERY.value
INTENT_SIMPLE_TASK = Intent.SIMPLE_TASK.value
INTENT_COMPLEX_TASK = Intent.COMPLEX_TASK.value
INTENT_HUMAN_ESCALATION = Intent.HUMAN_ESCALATION.value
INTENT_NLU_FALLBACK = Intent.NLU_FALLBACK.value
INTENT_MULTI_MODAL_QUERY = Intent.MULTI_MODAL_QUERY.value
INTENT_WEATHER_QUERY = Intent.WEATHER_QUERY.value
INTENT_LONG_WRITING = Intent.LONG_WRITING.value
INTENT_COMPLEX_REASONING = Intent.COMPLEX_REASONING.value


if __name__ == "__main__":
    print("=" * 60)
    print("统一意图定义中心测试")
    print("=" * 60)
    
    # 测试枚举访问
    print("\n[1] 意图枚举测试")
    print(f"GREET: {Intent.GREET}")
    print(f"CODE_GENERATION: {Intent.CODE_GENERATION}")
    
    # 测试从值获取
    print("\n[2] 从值获取意图")
    intent = Intent.from_value("code_generation")
    print(f"from_value('code_generation'): {intent}")
    
    # 测试分类判断
    print("\n[3] 分类判断")
    print(f"is_general(GREET): {Intent.is_general(Intent.GREET)}")
    print(f"is_query(QUERY_KNOWLEDGE): {Intent.is_query(Intent.QUERY_KNOWLEDGE)}")
    print(f"is_action(CODE_GENERATION): {Intent.is_action(Intent.CODE_GENERATION)}")
    print(f"is_fallback(NLU_FALLBACK): {Intent.is_fallback(Intent.NLU_FALLBACK)}")
    
    # 测试获取关键词
    print("\n[4] 获取意图关键词")
    keywords = Intent.get_intent_keywords()
    for intent_value, kw_list in list(keywords.items())[:5]:
        print(f"  {intent_value}: {kw_list}")
    
    # 测试获取分类
    print("\n[5] 获取意图分类")
    categories = Intent.get_intent_categories()
    for category, intents in categories.items():
        print(f"  {category}: {[i.value for i in intents]}")
    
    # 测试便捷函数
    print("\n[6] 便捷函数测试")
    print(f"get_intent_by_keyword('你好'): {get_intent_by_keyword('你好')}")
    print(f"get_intent_category(Intent.CODE_GENERATION): {get_intent_category(Intent.CODE_GENERATION)}")
    print(f"is_valid_intent('code_generation'): {is_valid_intent('code_generation')}")
    print(f"is_valid_intent('invalid_intent'): {is_valid_intent('invalid_intent')}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)