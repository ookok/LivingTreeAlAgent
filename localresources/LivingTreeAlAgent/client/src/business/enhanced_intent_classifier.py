"""
L0 意图分类增强模块
增强现有的意图分类能力，支持更精准的意图识别
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class IntentType(Enum):
    """意图类型"""
    # 核心编程意图
    CODE_GENERATION = "code_generation"      # 代码生成
    CODE_COMPLETION = "code_completion"      # 代码补全
    ERROR_DIAGNOSIS = "error_diagnosis"      # 错误诊断
    REFACTORING = "refactoring"            # 代码重构
    TEST_GENERATION = "test_generation"      # 测试生成
    DOCUMENTATION = "documentation"        # 文档生成
    PERFORMANCE_OPTIMIZATION = "performance_optimization"  # 性能优化
    
    # 项目管理意图
    GIT_OPERATION = "git_operation"        # Git操作
    FILE_OPERATION = "file_operation"      # 文件操作
    PROJECT_SETUP = "project_setup"        # 项目设置
    
    # 学习和查询意图
    KNOWLEDGE_QUERY = "knowledge_query"    # 知识查询
    LEARNING_REQUEST = "learning_request"  # 学习请求
    EXPLANATION = "explanation"            # 解释说明
    
    # 其他意图
    NAVIGATION = "navigation"              # 导航
    SETTINGS = "settings"                  # 设置
    TROUBLESHOOT = "troubleshoot"          # 故障排除
    CONFIG_HELP = "config_help"            # 配置帮助
    OTHER = "other"                        # 其他


class SecondaryIntent(Enum):
    """二级意图"""
    # 核心意图
    WHAT_IS = "what_is"                    # 是什么
    HOW_WORKS = "how_works"                # 如何工作
    HOW_TO_DO = "how_to_do"                # 如何做
    HOW_TO_CONFIG = "how_to_config"        # 如何配置
    ERROR_FIX = "error_fix"                # 错误修复
    WHERE_IS = "where_is"                  # 在哪里
    OPEN_SETTINGS = "open_settings"        # 打开设置
    QUICK_ACTION = "quick_action"          # 快速操作
    
    # 编程相关
    CREATE_FILE = "create_file"            # 创建文件
    MODIFY_FILE = "modify_file"            # 修改文件
    DELETE_FILE = "delete_file"            # 删除文件
    RUN_CODE = "run_code"                  # 运行代码
    DEBUG_CODE = "debug_code"              # 调试代码
    TEST_CODE = "test_code"                # 测试代码
    
    # Git相关
    COMMIT_CHANGES = "commit_changes"      # 提交变更
    PUSH_CODE = "push_code"                # 推送代码
    PULL_CODE = "pull_code"                # 拉取代码
    BRANCH_MANAGEMENT = "branch_management"  # 分支管理


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: IntentType
    secondary_intent: Optional[SecondaryIntent] = None
    confidence: float = 0.0
    entities: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    context_summary: str = ""


class EnhancedIntentClassifier:
    """
    增强的意图分类器
    基于现有实现进行增强，支持更精准的意图识别
    """
    
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
        
        # 二级意图模式
        self.secondary_patterns = {
            SecondaryIntent.WHAT_IS: [
                r"什么是|是.*吗|介绍一下|解释.*|定义",
                r"是.*东西|是什么|叫.*"
            ],
            SecondaryIntent.HOW_WORKS: [
                r"怎么工作|如何工作|原理|工作机制",
                r".*原理|工作方式"
            ],
            SecondaryIntent.HOW_TO_DO: [
                r"如何|怎么|怎样.*做",
                r".*步骤|.*流程",
                r"请.*帮我.*"
            ],
            SecondaryIntent.HOW_TO_CONFIG: [
                r"怎么配置|如何设置|配置.*方法",
                r"设置.*选项|调整.*参数"
            ],
            SecondaryIntent.ERROR_FIX: [
                r".*错误|.*报错|.*失败",
                r"解决.*问题|修复.*",
                r".*不行|.*不能用"
            ],
            SecondaryIntent.WHERE_IS: [
                r"在哪|哪里|找不到",
                r"怎么.*找|如何.*打开"
            ],
            SecondaryIntent.OPEN_SETTINGS: [
                r"打开.*设置|进入.*设置",
                r"去.*设置|转到.*设置"
            ],
            SecondaryIntent.QUICK_ACTION: [
                r"直接|快捷|一键",
                r"帮我.*一下"
            ],
            SecondaryIntent.CREATE_FILE: [
                r"创建|新建.*文件",
                r"添加.*文件",
                r"新建.*模块"
            ],
            SecondaryIntent.MODIFY_FILE: [
                r"修改|编辑.*文件",
                r"更新.*文件",
                r"更改.*文件"
            ],
            SecondaryIntent.DELETE_FILE: [
                r"删除|移除.*文件",
                r"清理.*文件"
            ],
            SecondaryIntent.RUN_CODE: [
                r"运行|执行.*代码",
                r"测试运行|试运行"
            ],
            SecondaryIntent.DEBUG_CODE: [
                r"调试|排查.*代码",
                r"断点|调试模式"
            ],
            SecondaryIntent.TEST_CODE: [
                r"测试|运行测试",
                r"单元测试|集成测试"
            ],
            SecondaryIntent.COMMIT_CHANGES: [
                r"提交|commit.*代码",
                r"保存.*更改"
            ],
            SecondaryIntent.PUSH_CODE: [
                r"推送|push.*代码",
                r"上传.*代码"
            ],
            SecondaryIntent.PULL_CODE: [
                r"拉取|pull.*代码",
                r"更新.*代码"
            ],
            SecondaryIntent.BRANCH_MANAGEMENT: [
                r"分支|branch.*管理",
                r"创建|切换.*分支"
            ]
        }
        
        # 实体提取模式
        self.entity_patterns = {
            "file": [
                r"文件|代码文件|脚本|模块",
                r"\.py|\.js|\.ts|\.jsx|\.tsx|\.html|\.css|\.json"
            ],
            "language": [
                r"Python|JavaScript|TypeScript|React|Vue|Angular",
                r"python|javascript|typescript|react|vue|angular"
            ],
            "framework": [
                r"React|Vue|Angular|Flask|Django|Express",
                r"react|vue|angular|flask|django|express"
            ],
            "feature": [
                r"功能|特性|模块|组件",
                r"登录|注册|搜索|支付|聊天"
            ],
            "error": [
                r"错误|异常|问题|bug",
                r"NameError|TypeError|SyntaxError|ImportError"
            ]
        }
    
    def classify_intent(self, user_input: str) -> IntentResult:
        """
        分类用户意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            IntentResult: 意图识别结果
        """
        user_input_lower = user_input.lower()
        
        # 识别主意图
        primary_intent, primary_confidence = self._classify_primary_intent(user_input_lower)
        
        # 识别二级意图
        secondary_intent, secondary_confidence = self._classify_secondary_intent(user_input_lower, primary_intent)
        
        # 提取实体
        entities = self._extract_entities(user_input)
        
        # 提取约束
        constraints = self._extract_constraints(user_input)
        
        # 构建上下文摘要
        context_summary = self._build_context_summary(user_input, primary_intent, secondary_intent, entities)
        
        # 计算总置信度
        total_confidence = (primary_confidence * 0.7) + (secondary_confidence * 0.3)
        
        return IntentResult(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=total_confidence,
            entities=entities,
            constraints=constraints,
            context_summary=context_summary
        )
    
    def _classify_primary_intent(self, user_input: str) -> Tuple[IntentType, float]:
        """分类主意图"""
        scores = {}
        
        for intent, patterns in self.primary_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, user_input):
                    score += 1
            scores[intent] = score
        
        # 找出得分最高的意图
        max_score = max(scores.values())
        if max_score == 0:
            return IntentType.OTHER, 0.5
        
        # 计算置信度
        total_patterns = sum(len(patterns) for patterns in self.primary_patterns.values())
        confidence = min(max_score / 3, 1.0)  # 最高得分3分，对应1.0置信度
        
        # 返回得分最高的意图
        best_intent = max(scores, key=scores.get)
        return best_intent, confidence
    
    def _classify_secondary_intent(self, user_input: str, primary_intent: IntentType) -> Tuple[Optional[SecondaryIntent], float]:
        """分类二级意图"""
        scores = {}
        
        for intent, patterns in self.secondary_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, user_input):
                    score += 1
            scores[intent] = score
        
        # 找出得分最高的意图
        max_score = max(scores.values())
        if max_score == 0:
            return None, 0.0
        
        # 计算置信度
        confidence = min(max_score / 2, 1.0)  # 最高得分2分，对应1.0置信度
        
        # 返回得分最高的意图
        best_intent = max(scores, key=scores.get)
        return best_intent, confidence
    
    def _extract_entities(self, user_input: str) -> List[Dict[str, Any]]:
        """提取实体"""
        entities = []
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for match in matches:
                    entities.append({
                        "type": entity_type,
                        "value": match,
                        "confidence": 0.8
                    })
        
        return entities
    
    def _extract_constraints(self, user_input: str) -> List[str]:
        """提取约束条件"""
        constraints = []
        
        # 提取约束关键词
        constraint_keywords = [
            "必须", "需要", "要求", "希望", "要", "应该",
            "不能", "不要", "避免", "禁止", "不允许"
        ]
        
        for keyword in constraint_keywords:
            if keyword in user_input:
                # 提取包含约束的句子
                sentences = re.split(r'[。！？.!?]', user_input)
                for sentence in sentences:
                    if keyword in sentence:
                        constraints.append(sentence.strip())
        
        return constraints
    
    def _build_context_summary(self, user_input: str, primary_intent: IntentType, 
                             secondary_intent: Optional[SecondaryIntent], 
                             entities: List[Dict[str, Any]]) -> str:
        """构建上下文摘要"""
        summary_parts = []
        
        # 添加主意图
        summary_parts.append(f"主意图: {primary_intent.value}")
        
        # 添加二级意图
        if secondary_intent:
            summary_parts.append(f"二级意图: {secondary_intent.value}")
        
        # 添加实体
        if entities:
            entity_str = ", ".join([f"{e['type']}: {e['value']}" for e in entities])
            summary_parts.append(f"实体: {entity_str}")
        
        # 添加输入摘要
        input_summary = user_input[:100] + ("..." if len(user_input) > 100 else "")
        summary_parts.append(f"输入摘要: {input_summary}")
        
        return "; ".join(summary_parts)
    
    def get_intent_suggestions(self, user_input: str) -> List[str]:
        """
        获取意图建议
        
        Args:
            user_input: 用户输入
            
        Returns:
            List[str]: 意图建议
        """
        suggestions = []
        
        # 基于输入生成建议
        if "代码" in user_input:
            suggestions.append("生成代码")
            suggestions.append("代码补全")
            suggestions.append("代码重构")
        elif "错误" in user_input or "问题" in user_input:
            suggestions.append("错误诊断")
            suggestions.append("故障排除")
        elif "测试" in user_input:
            suggestions.append("生成测试")
            suggestions.append("运行测试")
        elif "文档" in user_input:
            suggestions.append("生成文档")
            suggestions.append("文档查询")
        elif "git" in user_input.lower() or "提交" in user_input:
            suggestions.append("Git操作")
            suggestions.append("提交代码")
        elif "文件" in user_input:
            suggestions.append("文件操作")
            suggestions.append("创建文件")
        elif "项目" in user_input:
            suggestions.append("项目设置")
            suggestions.append("项目初始化")
        
        return suggestions


def create_enhanced_intent_classifier() -> EnhancedIntentClassifier:
    """
    创建增强的意图分类器
    
    Returns:
        EnhancedIntentClassifier: 增强的意图分类器实例
    """
    return EnhancedIntentClassifier()