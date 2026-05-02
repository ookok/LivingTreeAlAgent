"""
ModelNativeDSL - LLM优化的领域特定语言

核心功能：
1. 为LLM设计的简洁语法
2. 支持多模态输入输出
3. 内置工具调用语法
4. 支持链式思考和反思
5. 可扩展的指令集

遵循自我进化原则：
- 从交互中学习优化语法
- 动态扩展指令集
- 支持自动语法进化
"""

import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum


class DSLTokenType(Enum):
    """DSL token 类型"""
    COMMAND = "command"
    ARGUMENT = "argument"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    VARIABLE = "variable"
    COMMENT = "comment"
    EOF = "eof"


class DSLCommand(Enum):
    """DSL 内置命令"""
    THINK = "think"
    CALL = "call"
    OBSERVE = "observe"
    REFLECT = "reflect"
    DECIDE = "decide"
    LEARN = "learn"
    MEMORIZE = "memorize"
    FORGET = "forget"
    ANALYZE = "analyze"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    SEARCH = "search"
    SUMMARIZE = "summarize"
    ASK = "ask"
    ANSWER = "answer"
    END = "end"


@dataclass
class DSLToken:
    """DSL token"""
    type: DSLTokenType
    value: Any
    line: int = 0
    column: int = 0


@dataclass
class DSLNode:
    """DSL 抽象语法树节点"""
    type: str
    children: List['DSLNode'] = field(default_factory=list)
    value: Any = None
    line: int = 0
    column: int = 0


class ModelNativeDSL:
    """
    Model-Native DSL - LLM优化的领域特定语言
    
    专为大语言模型设计的简洁语法，支持：
    - 链式思考
    - 工具调用
    - 反思学习
    - 多模态交互
    
    遵循自我进化原则：
    - 从交互中学习优化语法
    - 动态扩展指令集
    - 支持自动语法进化
    """

    def __init__(self):
        self._logger = logger.bind(component="ModelNativeDSL")
        self._commands: Dict[str, Callable] = {}
        self._learned_patterns: List[Dict[str, Any]] = []
        self._register_builtin_commands()

    def _register_builtin_commands(self):
        """注册内置命令"""
        self._commands["think"] = self._execute_think
        self._commands["call"] = self._execute_call
        self._commands["observe"] = self._execute_observe
        self._commands["reflect"] = self._execute_reflect
        self._commands["decide"] = self._execute_decide
        self._commands["learn"] = self._execute_learn
        self._commands["memorize"] = self._execute_memorize
        self._commands["forget"] = self._execute_forget
        self._commands["analyze"] = self._execute_analyze
        self._commands["create"] = self._execute_create
        self._commands["modify"] = self._execute_modify
        self._commands["delete"] = self._execute_delete
        self._commands["search"] = self._execute_search
        self._commands["summarize"] = self._execute_summarize
        self._commands["ask"] = self._execute_ask
        self._commands["answer"] = self._execute_answer
        self._commands["end"] = self._execute_end

    def tokenize(self, code: str) -> List[DSLToken]:
        """
        分词器
        
        将 DSL 代码转换为 token 流
        """
        tokens = []
        lines = code.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            
            # 移除行尾注释
            if "#" in line:
                line = line[:line.index("#")].strip()
            
            pos = 0
            while pos < len(line):
                # 匹配命令（以 @ 开头）
                if line[pos] == "@":
                    end_pos = pos + 1
                    while end_pos < len(line) and (line[end_pos].isalnum() or line[end_pos] == "_"):
                        end_pos += 1
                    cmd = line[pos:end_pos]
                    tokens.append(DSLToken(
                        type=DSLTokenType.COMMAND,
                        value=cmd[1:],  # 去掉 @
                        line=line_num,
                        column=pos + 1
                    ))
                    pos = end_pos
                    continue
                
                # 匹配字符串（单引号或双引号）
                if line[pos] in "'\"":
                    quote = line[pos]
                    end_pos = pos + 1
                    while end_pos < len(line) and line[end_pos] != quote:
                        if line[end_pos] == "\\" and end_pos + 1 < len(line):
                            end_pos += 2
                        else:
                            end_pos += 1
                    if end_pos < len(line):
                        end_pos += 1
                    tokens.append(DSLToken(
                        type=DSLTokenType.STRING,
                        value=line[pos+1:end_pos-1],
                        line=line_num,
                        column=pos + 1
                    ))
                    pos = end_pos
                    continue
                
                # 匹配数字
                if line[pos].isdigit() or (line[pos] == "." and pos + 1 < len(line) and line[pos+1].isdigit()):
                    end_pos = pos
                    has_dot = False
                    while end_pos < len(line):
                        if line[end_pos] == ".":
                            if has_dot:
                                break
                            has_dot = True
                        elif not line[end_pos].isdigit():
                            break
                        end_pos += 1
                    num_str = line[pos:end_pos]
                    if has_dot:
                        tokens.append(DSLToken(
                            type=DSLTokenType.NUMBER,
                            value=float(num_str),
                            line=line_num,
                            column=pos + 1
                        ))
                    else:
                        tokens.append(DSLToken(
                            type=DSLTokenType.NUMBER,
                            value=int(num_str),
                            line=line_num,
                            column=pos + 1
                        ))
                    pos = end_pos
                    continue
                
                # 匹配布尔值
                if line[pos:pos+5] == "true":
                    tokens.append(DSLToken(
                        type=DSLTokenType.BOOLEAN,
                        value=True,
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 5
                    continue
                if line[pos:pos+6] == "false":
                    tokens.append(DSLToken(
                        type=DSLTokenType.BOOLEAN,
                        value=False,
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 6
                    continue
                
                # 匹配变量（以 $ 开头）
                if line[pos] == "$":
                    end_pos = pos + 1
                    while end_pos < len(line) and (line[end_pos].isalnum() or line[end_pos] == "_"):
                        end_pos += 1
                    tokens.append(DSLToken(
                        type=DSLTokenType.VARIABLE,
                        value=line[pos:end_pos],
                        line=line_num,
                        column=pos + 1
                    ))
                    pos = end_pos
                    continue
                
                # 匹配列表
                if line[pos] == "[":
                    tokens.append(DSLToken(
                        type=DSLTokenType.LIST,
                        value="start",
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 1
                    continue
                if line[pos] == "]":
                    tokens.append(DSLToken(
                        type=DSLTokenType.LIST,
                        value="end",
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 1
                    continue
                
                # 匹配字典
                if line[pos] == "{":
                    tokens.append(DSLToken(
                        type=DSLTokenType.DICT,
                        value="start",
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 1
                    continue
                if line[pos] == "}":
                    tokens.append(DSLToken(
                        type=DSLTokenType.DICT,
                        value="end",
                        line=line_num,
                        column=pos + 1
                    ))
                    pos += 1
                    continue
                
                # 跳过空白
                if line[pos].isspace():
                    pos += 1
                    continue
                
                # 匹配参数名
                if line[pos].isalpha() or line[pos] == "_":
                    end_pos = pos
                    while end_pos < len(line) and (line[end_pos].isalnum() or line[end_pos] == "_"):
                        end_pos += 1
                    tokens.append(DSLToken(
                        type=DSLTokenType.ARGUMENT,
                        value=line[pos:end_pos],
                        line=line_num,
                        column=pos + 1
                    ))
                    pos = end_pos
                    continue
                
                pos += 1
        
        tokens.append(DSLToken(
            type=DSLTokenType.EOF,
            value=None,
            line=len(lines) + 1,
            column=1
        ))
        
        return tokens

    def parse(self, code: str) -> DSLNode:
        """
        解析器
        
        将 DSL 代码解析为抽象语法树
        """
        tokens = self.tokenize(code)
        return self._parse_tokens(tokens, 0)[0]

    def _parse_tokens(self, tokens: List[DSLToken], pos: int) -> tuple:
        """递归解析 token 流"""
        nodes = []
        
        while pos < len(tokens) and tokens[pos].type != DSLTokenType.EOF:
            token = tokens[pos]
            
            if token.type == DSLTokenType.COMMAND:
                # 解析命令及其参数
                cmd_node = DSLNode(
                    type="command",
                    value=token.value,
                    line=token.line,
                    column=token.column
                )
                
                pos += 1
                args_node = DSLNode(type="arguments")
                
                # 解析参数（直到下一个命令或 EOF）
                while pos < len(tokens):
                    next_token = tokens[pos]
                    if next_token.type == DSLTokenType.COMMAND:
                        break
                    if next_token.type == DSLTokenType.EOF:
                        break
                    
                    arg_node, pos = self._parse_expression(tokens, pos)
                    args_node.children.append(arg_node)
                
                cmd_node.children.append(args_node)
                nodes.append(cmd_node)
            
            else:
                pos += 1
        
        root = DSLNode(type="program", children=nodes)
        return root, pos

    def _parse_expression(self, tokens: List[DSLToken], pos: int) -> tuple:
        """解析表达式"""
        token = tokens[pos]
        
        if token.type == DSLTokenType.STRING:
            return DSLNode(type="string", value=token.value, line=token.line, column=token.column), pos + 1
        
        if token.type == DSLTokenType.NUMBER:
            return DSLNode(type="number", value=token.value, line=token.line, column=token.column), pos + 1
        
        if token.type == DSLTokenType.BOOLEAN:
            return DSLNode(type="boolean", value=token.value, line=token.line, column=token.column), pos + 1
        
        if token.type == DSLTokenType.VARIABLE:
            return DSLNode(type="variable", value=token.value, line=token.line, column=token.column), pos + 1
        
        if token.type == DSLTokenType.LIST and token.value == "start":
            list_node = DSLNode(type="list", line=token.line, column=token.column)
            pos += 1
            while pos < len(tokens):
                if tokens[pos].type == DSLTokenType.LIST and tokens[pos].value == "end":
                    return list_node, pos + 1
                if tokens[pos].type == DSLTokenType.COMMAND:
                    break
                child, pos = self._parse_expression(tokens, pos)
                list_node.children.append(child)
            return list_node, pos
        
        if token.type == DSLTokenType.DICT and token.value == "start":
            dict_node = DSLNode(type="dict", line=token.line, column=token.column)
            pos += 1
            while pos < len(tokens):
                if tokens[pos].type == DSLTokenType.DICT and tokens[pos].value == "end":
                    return dict_node, pos + 1
                if tokens[pos].type == DSLTokenType.COMMAND:
                    break
                
                # 解析键值对
                if pos + 2 < len(tokens) and tokens[pos + 1].value == ":":
                    key_node = DSLNode(type="key", value=tokens[pos].value, line=tokens[pos].line, column=tokens[pos].column)
                    pos += 2
                    value_node, pos = self._parse_expression(tokens, pos)
                    pair_node = DSLNode(type="pair", children=[key_node, value_node])
                    dict_node.children.append(pair_node)
                else:
                    pos += 1
            return dict_node, pos
        
        if token.type == DSLTokenType.ARGUMENT:
            return DSLNode(type="argument", value=token.value, line=token.line, column=token.column), pos + 1
        
        return DSLNode(type="unknown", value=token.value), pos + 1

    async def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行 DSL 代码
        
        Args:
            code: DSL 代码
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if context is None:
            context = {}
        
        self._logger.info(f"执行 DSL 代码: {code[:100]}...")
        
        ast = self.parse(code)
        return await self._execute_ast(ast, context)

    async def _execute_ast(self, node: DSLNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行抽象语法树"""
        results = []
        
        for child in node.children:
            if child.type == "command":
                cmd_name = child.value
                args = self._extract_args(child)
                
                if cmd_name in self._commands:
                    result = await self._commands[cmd_name](args, context)
                    results.append({"command": cmd_name, "result": result})
                else:
                    results.append({"command": cmd_name, "error": f"未知命令: {cmd_name}"})
        
        return {"results": results, "context": context}

    def _extract_args(self, cmd_node: DSLNode) -> Dict[str, Any]:
        """提取命令参数"""
        args = {}
        
        for child in cmd_node.children:
            if child.type == "arguments":
                for arg in child.children:
                    if arg.type == "argument":
                        args[arg.value] = True
                    elif arg.type == "string":
                        args.setdefault("_args", []).append(arg.value)
                    elif arg.type == "number":
                        args.setdefault("_args", []).append(arg.value)
                    elif arg.type == "boolean":
                        args.setdefault("_args", []).append(arg.value)
                    elif arg.type == "variable":
                        args.setdefault("_args", []).append(arg.value)
                    elif arg.type == "list":
                        list_value = [self._node_to_value(c) for c in arg.children]
                        args.setdefault("_args", []).append(list_value)
                    elif arg.type == "dict":
                        dict_value = {}
                        for pair in arg.children:
                            if pair.type == "pair" and len(pair.children) >= 2:
                                key = self._node_to_value(pair.children[0])
                                value = self._node_to_value(pair.children[1])
                                dict_value[key] = value
                        args.setdefault("_args", []).append(dict_value)
        
        return args

    def _node_to_value(self, node: DSLNode) -> Any:
        """将节点转换为值"""
        if node.type == "string":
            return node.value
        if node.type == "number":
            return node.value
        if node.type == "boolean":
            return node.value
        if node.type == "variable":
            return node.value
        if node.type == "list":
            return [self._node_to_value(c) for c in node.children]
        if node.type == "dict":
            result = {}
            for pair in node.children:
                if pair.type == "pair" and len(pair.children) >= 2:
                    key = self._node_to_value(pair.children[0])
                    value = self._node_to_value(pair.children[1])
                    result[key] = value
            return result
        if node.type == "argument":
            return node.value
        return None

    async def _execute_think(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """思考命令"""
        thought = args.get("_args", [""])[0] if "_args" in args else ""
        context.setdefault("thoughts", []).append(thought)
        return {"thought": thought, "status": "thinking"}

    async def _execute_call(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """工具调用命令"""
        tool_name = args.get("_args", [""])[0] if "_args" in args else ""
        tool_args = args.get("_args", [])[1] if len(args.get("_args", [])) > 1 else {}
        
        return {
            "tool": tool_name,
            "args": tool_args,
            "status": "calling",
            "context": context.get("tool_results", {})
        }

    async def _execute_observe(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """观察命令"""
        return {"status": "observing", "observation": args.get("_args", [])}

    async def _execute_reflect(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """反思命令"""
        return {"status": "reflecting", "reflection": args.get("_args", [])}

    async def _execute_decide(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """决策命令"""
        options = args.get("_args", [])
        return {"status": "deciding", "options": options}

    async def _execute_learn(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """学习命令"""
        return {"status": "learning", "content": args.get("_args", [])}

    async def _execute_memorize(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """记忆命令"""
        key = args.get("_args", [""])[0] if "_args" in args else ""
        value = args.get("_args", [""])[1] if len(args.get("_args", [])) > 1 else None
        if key:
            context[key] = value
        return {"status": "memorized", "key": key, "value": value}

    async def _execute_forget(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """遗忘命令"""
        key = args.get("_args", [""])[0] if "_args" in args else ""
        if key in context:
            del context[key]
        return {"status": "forgotten", "key": key}

    async def _execute_analyze(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """分析命令"""
        return {"status": "analyzing", "input": args.get("_args", [])}

    async def _execute_create(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """创建命令"""
        return {"status": "creating", "params": args.get("_args", [])}

    async def _execute_modify(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """修改命令"""
        return {"status": "modifying", "params": args.get("_args", [])}

    async def _execute_delete(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """删除命令"""
        return {"status": "deleting", "target": args.get("_args", [])}

    async def _execute_search(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """搜索命令"""
        query = args.get("_args", [""])[0] if "_args" in args else ""
        return {"status": "searching", "query": query}

    async def _execute_summarize(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """总结命令"""
        return {"status": "summarizing", "content": args.get("_args", [])}

    async def _execute_ask(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """提问命令"""
        question = args.get("_args", [""])[0] if "_args" in args else ""
        return {"status": "asking", "question": question}

    async def _execute_answer(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """回答命令"""
        answer = args.get("_args", [""])[0] if "_args" in args else ""
        context["answer"] = answer
        return {"status": "answered", "answer": answer}

    async def _execute_end(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """结束命令"""
        return {"status": "ended", "summary": args.get("_args", [""])[0] if "_args" in args else ""}

    def register_command(self, name: str, handler: Callable):
        """
        注册自定义命令
        
        Args:
            name: 命令名称
            handler: 命令处理函数
        """
        self._commands[name] = handler
        self._logger.info(f"注册自定义命令: {name}")

    async def learn_pattern(self, pattern: str, meaning: str):
        """
        学习新的语法模式
        
        Args:
            pattern: 语法模式
            meaning: 模式含义
        """
        self._learned_patterns.append({
            "pattern": pattern,
            "meaning": meaning,
            "timestamp": len(self._learned_patterns)
        })
        self._logger.info(f"学习新语法模式: {pattern} -> {meaning}")

    def generate_prompt(self, task: str) -> str:
        """
        生成 DSL 提示词
        
        Args:
            task: 任务描述
            
        Returns:
            DSL 代码
        """
        prompt = f"""
# 任务: {task}

# DSL 语法参考:
# @think [思考内容] - 思考
# @call [工具名] [参数] - 调用工具
# @reflect [反思内容] - 反思
# @decide [选项1, 选项2, ...] - 决策
# @learn [内容] - 学习
# @memorize [键] [值] - 记忆
# @search [查询] - 搜索
# @summarize [内容] - 总结
# @answer [答案] - 回答
# @end [总结] - 结束

# 请生成完成此任务的 DSL 代码:
"""
        return prompt

    def format_code(self, code: str) -> str:
        """格式化 DSL 代码"""
        lines = code.split("\n")
        formatted = []
        
        for line in lines:
            line = line.strip()
            if line:
                formatted.append(line)
        
        return "\n".join(formatted)