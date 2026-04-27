"""
宪法式 Prompt 增强模块
实现更完善的宪法式 Prompt 结构和分层摘要策略
"""

from typing import Optional, Dict, List, Any


class ConstitutionalPromptBuilder:
    """
    宪法式 Prompt 构建器
    实现分层的 Prompt 结构，确保意图不被稀释
    """
    
    def __init__(self):
        # 角色定义
        self.roles = {
            "frontend": {
                "role": "Senior Frontend Architect",
                "objective": "基于用户输入，生成可运行的前端代码（React + TypeScript）。",
                "critical": "必须保持与现有项目的代码风格和架构一致。",
                "non_negotiable": "如果用户需求模糊，必须主动澄清，禁止猜测。"
            },
            "backend": {
                "role": "Senior Backend Engineer",
                "objective": "基于用户输入，生成可运行的后端代码（Python + FastAPI）。",
                "critical": "必须保持代码的安全性和性能。",
                "non_negotiable": "如果用户需求模糊，必须主动澄清，禁止猜测。"
            },
            "fullstack": {
                "role": "Fullstack Engineer",
                "objective": "基于用户输入，生成完整的全栈应用代码。",
                "critical": "必须保持前后端代码的一致性和可维护性。",
                "non_negotiable": "如果用户需求模糊，必须主动澄清，禁止猜测。"
            },
            "data_science": {
                "role": "Data Scientist",
                "objective": "基于用户输入，生成数据分析和机器学习代码。",
                "critical": "必须确保代码的准确性和可复现性。",
                "non_negotiable": "如果用户需求模糊，必须主动澄清，禁止猜测。"
            }
        }
    
    def build_prompt(self, intent: str, context: str, role_type: str = "frontend", 
                    clarified_details: List[str] = None, 
                    assumptions: List[str] = None, 
                    risks: List[str] = None) -> str:
        """
        构建宪法式 Prompt
        
        Args:
            intent: 用户意图
            context: 上下文信息
            role_type: 角色类型
            clarified_details: 已澄清的细节
            assumptions: 推理假设
            risks: 潜在风险
            
        Returns:
            str: 宪法式 Prompt
        """
        # 获取角色定义
        role = self.roles.get(role_type, self.roles["frontend"])
        
        # 构建宪法层
        constitutional_layer = self._build_constitutional_layer(role)
        
        # 构建任务层
        task_layer = self._build_task_layer(intent)
        
        # 构建上下文层
        context_layer = self._build_context_layer(context)
        
        # 构建推理层
        reasoning_layer = self._build_reasoning_layer(
            intent, 
            clarified_details or [], 
            assumptions or [], 
            risks or []
        )
        
        # 构建指令层
        instruction_layer = self._build_instruction_layer()
        
        # 组合所有层
        prompt = f"""
{constitutional_layer}

{task_layer}

{context_layer}

{reasoning_layer}

{instruction_layer}
        """
        
        return prompt
    
    def _build_constitutional_layer(self, role: Dict[str, str]) -> str:
        """构建宪法层"""
        return f"""
# 🎯 宪法层（不可覆盖）
[CONSTITUTION]
ROLE: {role['role']}
OBJECTIVE: {role['objective']}
CRITICAL: {role['critical']}
NON_NEGOTIABLE: {role['non_negotiable']}
[/CONSTITUTION]
        """
    
    def _build_task_layer(self, intent: str) -> str:
        """构建任务层"""
        return f"""
# 📝 任务层（用户原始意图）
[INTENT]
{intent}
[/INTENT]
        """
    
    def _build_context_layer(self, context: str) -> str:
        """
        构建上下文层
        使用分层摘要策略
        """
        # 生成分层上下文
        layered_context = self._generate_layered_context(context)
        
        return f"""
# 🗂️ 上下文层（可压缩的背景）
[CONTEXT]
{layered_context}
[/CONTEXT]
        """
    
    def _build_reasoning_layer(self, intent: str, clarified_details: List[str], 
                             assumptions: List[str], risks: List[str]) -> str:
        """构建推理层"""
        details_str = "[]" if not clarified_details else f"[{', '.join(f'\"{d}\"' for d in clarified_details)}]"
        assumptions_str = "[]" if not assumptions else f"[{', '.join(f'\"{a}\"' for a in assumptions)}]"
        risks_str = "[]" if not risks else f"[{', '.join(f'\"{r}\"' for r in risks)}]"
        
        return f"""
# 🔍 推理层（结构化确认）
[REASONING]
1. 用户原始目标：{intent}
2. 已澄清的细节：{details_str}
3. 当前推理假设：{assumptions_str}
4. 潜在风险：{risks_str}
[/REASONING]
        """
    
    def _build_instruction_layer(self) -> str:
        """构建指令层"""
        return """
# 📖 指令层（执行要求）
[INSTRUCTIONS]
1. 首先分析用户意图和上下文
2. 检查是否需要澄清细节
3. 生成结构化的推理过程
4. 基于推理结果生成代码
5. 确保代码可运行且符合最佳实践
6. 提供清晰的注释和说明
[/INSTRUCTIONS]
        """
    
    def _generate_layered_context(self, context: str) -> str:
        """
        生成分层上下文
        实现分层摘要策略
        """
        if not context:
            return "无上下文信息"
        
        # 分层摘要
        l0_summary = self._generate_l0_summary(context)
        l1_summary = self._generate_l1_summary(context)
        l2_summary = self._generate_l2_summary(context)
        
        layered_context = f"""
## L0 文件元信息
{l0_summary}

## L1 接口/类签名
{l1_summary}

## L2 关键函数逻辑
{l2_summary}

## L3 详细代码（按需加载）
[详细代码已压缩，如需查看请明确请求]
        """
        
        return layered_context
    
    def _generate_l0_summary(self, context: str) -> str:
        """
        生成 L0 摘要（文件元信息）
        """
        lines = context.split('\n')
        summary = []
        
        # 提取注释和导入
        for line in lines[:50]:  # 只处理前50行
            line = line.strip()
            if line.startswith('#') or line.startswith('//') or line.startswith('import') or line.startswith('from'):
                summary.append(line)
        
        if not summary:
            return "无文件元信息"
        
        return '\n'.join(summary[:10])  # 最多10行
    
    def _generate_l1_summary(self, context: str) -> str:
        """
        生成 L1 摘要（接口/类签名）
        """
        import re
        patterns = [
            r'class\s+\w+\s*\([^\)]*\)',
            r'interface\s+\w+\s*{',
            r'type\s+\w+\s*=',
            r'def\s+\w+\s*\([^\)]*\)\s*(->\s*\w+)?',
            r'function\s+\w+\s*\([^\)]*\)',
            r'const\s+\w+\s*=\s*\(.*\)\s*=>'
        ]
        
        summary = []
        for pattern in patterns:
            matches = re.findall(pattern, context, re.MULTILINE)
            summary.extend(matches[:5])  # 每种类型最多5个
        
        if not summary:
            return "无接口/类签名"
        
        return '\n'.join(summary[:15])  # 最多15个签名
    
    def _generate_l2_summary(self, context: str) -> str:
        """
        生成 L2 摘要（关键函数逻辑）
        """
        lines = context.split('\n')
        summary = []
        
        in_function = False
        function_lines = []
        
        for line in lines:
            import re
            if re.match(r'def\s+\w+\s*\(', line) or re.match(r'function\s+\w+\s*\(', line):
                if in_function and function_lines:
                    summary.append('\n'.join(function_lines[:10]))  # 每个函数最多10行
                in_function = True
                function_lines = [line.strip()]
            elif in_function:
                if line.strip().startswith('}') or (line.strip() and not line.startswith('    ') and not line.startswith('\t')):
                    summary.append('\n'.join(function_lines[:10]))
                    in_function = False
                    function_lines = []
                else:
                    function_lines.append(line.strip())
        
        if not summary:
            return "无关键函数逻辑"
        
        return '\n\n'.join(summary[:3])  # 最多3个函数


class HierarchicalSummarizer:
    """
    分层摘要器
    实现更完善的分层摘要策略
    """
    
    def __init__(self):
        # 摘要配置
        self.summary_config = {
            "L0": {
                "max_lines": 10,
                "max_tokens": 100,
                "priority": 1.0
            },
            "L1": {
                "max_lines": 15,
                "max_tokens": 500,
                "priority": 0.9
            },
            "L2": {
                "max_lines": 30,
                "max_tokens": 2000,
                "priority": 0.8
            },
            "L3": {
                "max_lines": 100,
                "max_tokens": 5000,
                "priority": 0.7
            }
        }
    
    def generate_summary(self, content: str, level: str) -> str:
        """
        生成指定级别的摘要
        
        Args:
            content: 原始内容
            level: 摘要级别 (L0, L1, L2, L3)
            
        Returns:
            str: 摘要内容
        """
        if level == "L0":
            return self._generate_l0_summary(content)
        elif level == "L1":
            return self._generate_l1_summary(content)
        elif level == "L2":
            return self._generate_l2_summary(content)
        elif level == "L3":
            return self._generate_l3_summary(content)
        else:
            return content
    
    def _generate_l0_summary(self, content: str) -> str:
        """
        生成 L0 摘要（文件元信息）
        """
        config = self.summary_config["L0"]
        lines = content.split('\n')
        summary = []
        
        # 提取注释和导入
        for line in lines[:50]:  # 只处理前50行
            line = line.strip()
            if line.startswith('#') or line.startswith('//') or line.startswith('import') or line.startswith('from'):
                summary.append(line)
                if len(summary) >= config["max_lines"]:
                    break
        
        if not summary:
            return "无文件元信息"
        
        return '\n'.join(summary)
    
    def _generate_l1_summary(self, content: str) -> str:
        """
        生成 L1 摘要（接口/类签名）
        """
        config = self.summary_config["L1"]
        import re
        patterns = [
            r'class\s+\w+\s*\([^\)]*\)',
            r'interface\s+\w+\s*{',
            r'type\s+\w+\s*=',
            r'def\s+\w+\s*\([^\)]*\)\s*(->\s*\w+)?',
            r'function\s+\w+\s*\([^\)]*\)',
            r'const\s+\w+\s*=\s*\(.*\)\s*=>'
        ]
        
        summary = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            summary.extend(matches)
            if len(summary) >= config["max_lines"]:
                break
        
        if not summary:
            return "无接口/类签名"
        
        return '\n'.join(summary)
    
    def _generate_l2_summary(self, content: str) -> str:
        """
        生成 L2 摘要（关键函数逻辑）
        """
        config = self.summary_config["L2"]
        lines = content.split('\n')
        summary = []
        
        in_function = False
        function_lines = []
        function_count = 0
        
        for line in lines:
            import re
            if re.match(r'def\s+\w+\s*\(', line) or re.match(r'function\s+\w+\s*\(', line):
                if in_function and function_lines:
                    summary.append('\n'.join(function_lines))
                    function_count += 1
                    if function_count >= 3:  # 最多3个函数
                        break
                in_function = True
                function_lines = [line.strip()]
            elif in_function:
                if line.strip().startswith('}') or (line.strip() and not line.startswith('    ') and not line.startswith('\t')):
                    summary.append('\n'.join(function_lines))
                    function_count += 1
                    if function_count >= 3:
                        break
                    in_function = False
                    function_lines = []
                else:
                    function_lines.append(line.strip())
                    if len(function_lines) >= 10:  # 每个函数最多10行
                        summary.append('\n'.join(function_lines))
                        function_count += 1
                        if function_count >= 3:
                            break
                        in_function = False
                        function_lines = []
        
        if not summary:
            return "无关键函数逻辑"
        
        return '\n\n'.join(summary)
    
    def _generate_l3_summary(self, content: str) -> str:
        """
        生成 L3 摘要（详细代码）
        """
        config = self.summary_config["L3"]
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 保留开头、中间和结尾
        summary = []
        summary.extend(lines[:30])  # 前30行
        if total_lines > 60:
            summary.extend(lines[total_lines//2-15:total_lines//2+15])  # 中间30行
        summary.extend(lines[-40:])  # 后40行
        
        if not summary:
            return "无详细代码"
        
        return '\n'.join(summary[:config["max_lines"]])


def create_constitutional_prompt_builder() -> ConstitutionalPromptBuilder:
    """
    创建宪法式 Prompt 构建器
    
    Returns:
        ConstitutionalPromptBuilder: 宪法式 Prompt 构建器实例
    """
    return ConstitutionalPromptBuilder()


def create_hierarchical_summarizer() -> HierarchicalSummarizer:
    """
    创建分层摘要器
    
    Returns:
        HierarchicalSummarizer: 分层摘要器实例
    """
    return HierarchicalSummarizer()