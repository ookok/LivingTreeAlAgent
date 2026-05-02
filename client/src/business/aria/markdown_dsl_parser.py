"""
Markdown DSL解析器 - 解析带指令的Markdown

支持的指令格式：
<!-- STYLE: heading_1 -->
<!-- VALIDATE: required_if(industry='化工') -->
<!-- SECTION: basic_info -->
<!-- TABLE: emission_data -->

输出结构化AST供后续处理。
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class NodeType(Enum):
    """节点类型"""
    TEXT = "text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    CODE = "code"
    TABLE = "table"
    STYLE = "style"
    VALIDATE = "validate"
    SECTION = "section"
    TABLE_DEF = "table_def"


class StyleType(Enum):
    """样式类型"""
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    NORMAL_TEXT = "normal_text"
    ENV_TABLE = "env_table"
    CODE_BLOCK = "code_block"


@dataclass
class DSLNode:
    """DSL节点"""
    node_type: NodeType
    content: str = ""
    style: Optional[StyleType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['DSLNode'] = field(default_factory=list)


class MarkdownDSLParser:
    """
    Markdown DSL解析器
    
    解析带指令的Markdown文本，生成结构化AST。
    """
    
    # 指令正则表达式
    DIRECTIVE_PATTERN = re.compile(r'<!--\s*(\w+)\s*:\s*([^-->]+)\s*-->')
    
    # Markdown模式
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.*)')
    LIST_ITEM_PATTERN = re.compile(r'^(\s*[-*+])\s+(.*)')
    CODE_BLOCK_PATTERN = re.compile(r'^```(\w+)?\n(.*?)```', re.DOTALL)
    TABLE_PATTERN = re.compile(r'^\|.*\|$')
    
    def __init__(self):
        self.current_style = StyleType.NORMAL_TEXT
        self.current_section = None
        self.validation_rules = []
    
    def parse(self, text: str) -> List[DSLNode]:
        """
        解析Markdown DSL文本
        
        Args:
            text: 带指令的Markdown文本
        
        Returns:
            DSL节点列表（AST）
        """
        lines = text.split('\n')
        nodes = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检查指令
            directive_match = self.DIRECTIVE_PATTERN.match(line.strip())
            if directive_match:
                directive_type = directive_match.group(1).upper()
                directive_value = directive_match.group(2).strip()
                node = self._parse_directive(directive_type, directive_value)
                if node:
                    nodes.append(node)
                i += 1
                continue
            
            # 检查代码块
            # 需要读取多行
            if line.startswith('```'):
                code_content = line + '\n'
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code_content += lines[i] + '\n'
                    i += 1
                if i < len(lines):
                    code_content += lines[i] + '\n'
                    i += 1
                node = self._parse_code_block(code_content)
                if node:
                    nodes.append(node)
                continue
            
            # 检查表格
            if self.TABLE_PATTERN.match(line):
                table_lines = [line]
                i += 1
                while i < len(lines) and self.TABLE_PATTERN.match(lines[i]):
                    table_lines.append(lines[i])
                    i += 1
                node = self._parse_table('\n'.join(table_lines))
                if node:
                    nodes.append(node)
                continue
            
            # 检查标题
            heading_match = self.HEADING_PATTERN.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                node = DSLNode(
                    node_type=NodeType.HEADING,
                    content=content,
                    style=self._heading_style(level),
                    metadata={'level': level}
                )
                nodes.append(node)
                i += 1
                continue
            
            # 检查列表项
            list_match = self.LIST_ITEM_PATTERN.match(line)
            if list_match:
                # 收集连续的列表项
                list_items = [list_match.group(2)]
                i += 1
                while i < len(lines):
                    list_match2 = self.LIST_ITEM_PATTERN.match(lines[i])
                    if list_match2:
                        list_items.append(list_match2.group(2))
                        i += 1
                    else:
                        break
                node = DSLNode(
                    node_type=NodeType.LIST,
                    content='\n'.join(list_items),
                    style=self.current_style,
                    metadata={'items': list_items}
                )
                nodes.append(node)
                continue
            
            # 普通文本段落
            if line.strip():
                # 收集连续的文本行
                paragraph_lines = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() and not self._is_special_line(next_line):
                        paragraph_lines.append(next_line)
                        i += 1
                    else:
                        break
                node = DSLNode(
                    node_type=NodeType.PARAGRAPH,
                    content='\n'.join(paragraph_lines),
                    style=self.current_style
                )
                nodes.append(node)
            else:
                i += 1
        
        return nodes
    
    def _parse_directive(self, directive_type: str, value: str) -> Optional[DSLNode]:
        """解析指令"""
        if directive_type == 'STYLE':
            style_type = self._parse_style(value)
            if style_type:
                self.current_style = style_type
                return DSLNode(
                    node_type=NodeType.STYLE,
                    content=value,
                    style=style_type
                )
        
        elif directive_type == 'VALIDATE':
            rule = self._parse_validation_rule(value)
            if rule:
                self.validation_rules.append(rule)
                return DSLNode(
                    node_type=NodeType.VALIDATE,
                    content=value,
                    metadata={'rule': rule}
                )
        
        elif directive_type == 'SECTION':
            self.current_section = value
            return DSLNode(
                node_type=NodeType.SECTION,
                content=value,
                metadata={'section_id': value}
            )
        
        elif directive_type == 'TABLE':
            return DSLNode(
                node_type=NodeType.TABLE_DEF,
                content=value,
                metadata={'table_id': value}
            )
        
        return None
    
    def _parse_style(self, style_str: str) -> Optional[StyleType]:
        """解析样式类型"""
        style_map = {
            'heading_1': StyleType.HEADING_1,
            'heading_2': StyleType.HEADING_2,
            'heading_3': StyleType.HEADING_3,
            'normal_text': StyleType.NORMAL_TEXT,
            'env_table': StyleType.ENV_TABLE,
            'code_block': StyleType.CODE_BLOCK,
        }
        return style_map.get(style_str.lower())
    
    def _parse_validation_rule(self, rule_str: str) -> Dict[str, Any]:
        """解析验证规则"""
        # 简单解析：required_if(industry='化工')
        match = re.match(r'(\w+)\((.*)\)', rule_str)
        if match:
            rule_name = match.group(1)
            params_str = match.group(2)
            
            params = {}
            param_pairs = params_str.split(',')
            for pair in param_pairs:
                pair = pair.strip()
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    # 去除引号
                    value = value.strip().strip("'\"")
                    params[key.strip()] = value
            
            return {
                'rule': rule_name,
                'params': params
            }
        
        return {}
    
    def _parse_code_block(self, text: str) -> DSLNode:
        """解析代码块"""
        match = self.CODE_BLOCK_PATTERN.match(text)
        if match:
            language = match.group(1) or 'text'
            content = match.group(2)
        else:
            language = 'text'
            content = text
        
        return DSLNode(
            node_type=NodeType.CODE,
            content=content.strip(),
            style=StyleType.CODE_BLOCK,
            metadata={'language': language}
        )
    
    def _parse_table(self, text: str) -> DSLNode:
        """解析表格"""
        rows = text.strip().split('\n')
        headers = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
        
        data_rows = []
        for row in rows[1:]:
            cells = [cell.strip() for cell in row.split('|') if cell.strip()]
            if cells and cells != ['---'] * len(cells):  # 跳过分隔行
                data_rows.append(cells)
        
        return DSLNode(
            node_type=NodeType.TABLE,
            content=text,
            style=self.current_style,
            metadata={
                'headers': headers,
                'rows': data_rows
            }
        )
    
    def _heading_style(self, level: int) -> StyleType:
        """获取标题样式"""
        mapping = {
            1: StyleType.HEADING_1,
            2: StyleType.HEADING_2,
            3: StyleType.HEADING_3,
        }
        return mapping.get(level, StyleType.HEADING_3)
    
    def _is_special_line(self, line: str) -> bool:
        """检查是否为特殊行"""
        return (
            self.HEADING_PATTERN.match(line) or
            self.LIST_ITEM_PATTERN.match(line) or
            self.TABLE_PATTERN.match(line) or
            line.startswith('```') or
            self.DIRECTIVE_PATTERN.match(line.strip())
        )
    
    def validate(self, nodes: List[DSLNode], context: Dict[str, Any]) -> List[str]:
        """
        根据验证规则验证节点
        
        Args:
            nodes: DSL节点列表
            context: 上下文数据
        
        Returns:
            错误消息列表
        """
        errors = []
        
        for rule in self.validation_rules:
            rule_name = rule['rule']
            params = rule['params']
            
            if rule_name == 'required_if':
                condition_field = list(params.keys())[0]
                condition_value = params[condition_field]
                
                if context.get(condition_field) == condition_value:
                    # 检查是否缺少必需内容
                    has_required = False
                    for node in nodes:
                        if '必需' in node.content or '必须' in node.content:
                            has_required = True
                    
                    if not has_required:
                        errors.append(
                            f"当{condition_field}='{condition_value}'时，需要包含必需章节"
                        )
        
        return errors
    
    def to_html(self, nodes: List[DSLNode]) -> str:
        """转换为HTML"""
        html_parts = []
        
        for node in nodes:
            if node.node_type == NodeType.HEADING:
                level = node.metadata.get('level', 1)
                html_parts.append(f'<h{level}>{node.content}</h{level}>')
            
            elif node.node_type == NodeType.PARAGRAPH:
                html_parts.append(f'<p>{node.content}</p>')
            
            elif node.node_type == NodeType.LIST:
                items = node.metadata.get('items', [])
                items_html = ''.join(f'<li>{item}</li>' for item in items)
                html_parts.append(f'<ul>{items_html}</ul>')
            
            elif node.node_type == NodeType.CODE:
                language = node.metadata.get('language', 'text')
                html_parts.append(f'<pre><code class="{language}">{node.content}</code></pre>')
            
            elif node.node_type == NodeType.TABLE:
                headers = node.metadata.get('headers', [])
                rows = node.metadata.get('rows', [])
                
                headers_html = ''.join(f'<th>{h}</th>' for h in headers)
                rows_html = ''
                for row in rows:
                    cells_html = ''.join(f'<td>{c}</td>' for c in row)
                    rows_html += f'<tr>{cells_html}</tr>'
                
                html_parts.append(f'<table><thead><tr>{headers_html}</tr></thead><tbody>{rows_html}</tbody></table>')
        
        return '\n'.join(html_parts)