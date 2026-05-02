"""
AntiRationalizationTable - 反合理化表

参考 addyosmani/agent-skills 的反合理化机制，防止智能体使用错误的推理为自己
的错误决策辩护。

设计原则：
1. 常见错误决策模式识别
2. 提供反驳依据
3. 强制验证要求
4. 不允许以"看起来没问题"作为完成标准

反合理化表用于：
- SelfReflectionEngine 进行反思时参考
- ToolResult 验证时提供标准
- 智能体决策时避免常见陷阱
"""

from typing import List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class AntiRationalizationRule:
    """反合理化规则"""
    pattern: str
    description: str
    counter_argument: str
    verification_required: str
    category: str = "general"


class AntiRationalizationTable:
    """
    反合理化表
    
    核心功能：
    1. 常见错误决策模式识别
    2. 提供反驳依据
    3. 强制验证要求
    4. 分类管理（代码、测试、架构、安全等）
    """
    
    def __init__(self):
        self._logger = logger.bind(component="AntiRationalizationTable")
        self._rules: List[AntiRationalizationRule] = self._load_default_rules()
    
    def _load_default_rules(self) -> List[AntiRationalizationRule]:
        """加载默认反合理化规则"""
        return [
            # 代码质量类
            AntiRationalizationRule(
                pattern="看起来没问题",
                category="code_quality",
                description="以主观感觉代替客观验证",
                counter_argument="必须提供具体的测试证据或验证结果，不能仅凭主观判断",
                verification_required="提供测试用例通过证据或代码审查记录"
            ),
            AntiRationalizationRule(
                pattern="应该能工作",
                category="code_quality",
                description="假设代码能工作而不验证",
                counter_argument="假设不等于事实，必须实际运行并验证输出",
                verification_required="提供实际运行截图或测试输出"
            ),
            AntiRationalizationRule(
                pattern="其他地方也是这样做的",
                category="code_quality",
                description="以其他代码的错误做法为借口",
                counter_argument="别人的错误不能成为你的错误的理由，应该指出并修复所有问题",
                verification_required="提供代码符合最佳实践的证据"
            ),
            AntiRationalizationRule(
                pattern="暂时这样，后面再改",
                category="code_quality",
                description="推迟修复已知问题",
                counter_argument="技术债务会累积，应该在发现时立即修复",
                verification_required="问题已修复或已记录为高优先级任务"
            ),
            
            # 测试类
            AntiRationalizationRule(
                pattern="测试通过了",
                category="testing",
                description="测试通过不等于代码正确",
                counter_argument="测试可能覆盖不全或有漏洞，需要检查测试质量和覆盖率",
                verification_required="提供测试覆盖率报告（>80%）和边界测试用例"
            ),
            AntiRationalizationRule(
                pattern="没有报错",
                category="testing",
                description="没有报错不等于功能正确",
                counter_argument="静默失败是常见模式，必须验证输出是否符合预期",
                verification_required="提供预期输出与实际输出的对比证据"
            ),
            AntiRationalizationRule(
                pattern="本地能跑",
                category="testing",
                description="本地能跑不等于生产环境能跑",
                counter_argument="环境差异可能导致问题，必须在目标环境验证",
                verification_required="提供目标环境的测试通过证据"
            ),
            
            # 架构类
            AntiRationalizationRule(
                pattern="简单改动",
                category="architecture",
                description="低估改动的复杂性",
                counter_argument="简单改动可能引入连锁反应，需要全面影响分析",
                verification_required="提供影响分析报告和回归测试结果"
            ),
            AntiRationalizationRule(
                pattern="先实现，后面再优化",
                category="architecture",
                description="推迟性能优化到后期",
                counter_argument="架构决策会影响性能，应该在初期就考虑性能设计",
                verification_required="提供性能基准测试和优化计划"
            ),
            
            # 安全类
            AntiRationalizationRule(
                pattern="内部使用，不需要验证",
                category="security",
                description="内部系统忽略安全验证",
                counter_argument="内部系统同样可能受到攻击，安全不能省略",
                verification_required="提供安全审计报告和权限验证证据"
            ),
            AntiRationalizationRule(
                pattern="用户不会输入恶意数据",
                category="security",
                description="假设用户输入是安全的",
                counter_argument="永远不要信任用户输入，必须进行验证和转义",
                verification_required="提供输入验证和输出转义的代码证据"
            ),
            
            # 工具使用类
            AntiRationalizationRule(
                pattern="工具返回了结果",
                category="tool_usage",
                description="工具返回结果不等于结果正确",
                counter_argument="工具可能返回错误或不完整的结果，必须验证",
                verification_required="提供结果验证和交叉检查证据"
            ),
            AntiRationalizationRule(
                pattern="这个工具以前能用",
                category="tool_usage",
                description="假设工具行为不变",
                counter_argument="工具可能更新或环境变化，必须重新验证",
                verification_required="提供当前环境下的工具测试证据"
            ),
        ]
    
    def get_rules_for_category(self, category: str) -> List[AntiRationalizationRule]:
        """获取指定类别的反合理化规则"""
        return [r for r in self._rules if r.category == category]
    
    def check_statement(self, statement: str) -> List[AntiRationalizationRule]:
        """
        检查语句是否触发反合理化规则
        
        Args:
            statement: 要检查的语句
        
        Returns:
            触发的规则列表
        """
        triggered = []
        for rule in self._rules:
            if rule.pattern.lower() in statement.lower():
                triggered.append(rule)
        return triggered
    
    def get_verification_requirements(self, context: str) -> List[str]:
        """
        根据上下文获取验证要求
        
        Args:
            context: 上下文描述
        
        Returns:
            验证要求列表
        """
        triggered = self.check_statement(context)
        return [rule.verification_required for rule in triggered]
    
    def add_custom_rule(self, pattern: str, description: str, counter_argument: str,
                       verification_required: str, category: str = "custom"):
        """
        添加自定义反合理化规则
        
        Args:
            pattern: 错误模式
            description: 描述
            counter_argument: 反驳依据
            verification_required: 验证要求
            category: 类别
        """
        rule = AntiRationalizationRule(
            pattern=pattern,
            description=description,
            counter_argument=counter_argument,
            verification_required=verification_required,
            category=category
        )
        self._rules.append(rule)
        self._logger.info(f"添加自定义反合理化规则: {pattern}")
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """获取所有规则"""
        return [
            {
                "pattern": rule.pattern,
                "description": rule.description,
                "counter_argument": rule.counter_argument,
                "verification_required": rule.verification_required,
                "category": rule.category
            }
            for rule in self._rules
        ]
    
    def generate_reflection_prompt(self, task: str, result: str) -> str:
        """
        生成包含反合理化的反思提示词
        
        Args:
            task: 任务描述
            result: 执行结果
        
        Returns:
            反思提示词
        """
        triggered = self.check_statement(result)
        
        prompt = f"""
请反思以下任务执行情况：

任务：{task}
结果：{result}
"""
        
        if triggered:
            prompt += "\n\n检测到以下可能的错误推理模式：\n"
            for rule in triggered:
                prompt += f"\n⚠️ 模式: {rule.pattern}\n"
                prompt += f"   问题: {rule.description}\n"
                prompt += f"   反驳: {rule.counter_argument}\n"
                prompt += f"   需要验证: {rule.verification_required}\n"
        
        prompt += """
请根据以上反合理化规则，重新评估任务完成情况，并提供具体的验证证据。

请以 JSON 格式输出：
{
    "success": true/false,
    "evidence": "具体的验证证据",
    "anti_rationalization_checks": {
        "triggered_patterns": ["pattern1", "pattern2"],
        "verification_provided": true/false,
        "verification_details": "验证详情"
    }
}
"""
        
        return prompt