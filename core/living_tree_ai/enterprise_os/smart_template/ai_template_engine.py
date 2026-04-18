"""
AI推理模板引擎 (AI Template Inference Engine)

核心功能：分析文档 JSON AST，推理出"模板骨架"和"动态数据"，
生成可复用的 template_config.json，无需手动制作模板。

工作流程：
1. 结构分析：遍历 AST，识别段落、表格、标题层级
2. 语义推理：调用本地 LLM 判断每个内容块是"固定文本"还是"可变数据"
3. 键值提取：为每个可变数据生成唯一的 data_key 和示例值
4. 模板生成：输出 template_config.json 描述文件
"""

import json
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class ContentCategory(Enum):
    """内容类别"""
    STATIC_TEXT = "static_text"        # 固定文本（法律条款、章节标题、单位名称）
    DYNAMIC_VALUE = "dynamic_value"    # 可变数据（企业名称、监测数值、日期）
    FORMULA = "formula"               # 公式表达式
    TABLE_STRUCTURE = "table_structure" # 表格结构
    METADATA = "metadata"             # 元信息（编号、日期等）


class VariablePattern(Enum):
    """变量模式"""
    COMPANY_NAME = "company_name"       # 企业名称
    PERSON_NAME = "person_name"        # 人名
    DATE = "date"                      # 日期
    TIME = "time"                      # 时间
    NUMBER = "number"                   # 数字
    PERCENTAGE = "percentage"          # 百分比
    LOCATION = "location"              # 地点
    MONITORING_VALUE = "monitoring_value"  # 监测值
    EMISSION_VALUE = "emission_value"  # 排放值
    CURRENCY = "currency"              # 金额
    ADDRESS = "address"                # 地址
    PHONE = "phone"                    # 电话
    EMAIL = "email"                    # 邮箱
    ID_NUMBER = "id_number"            # 身份证/统一信用代码
    UNKNOWN = "unknown"                # 未知类型


@dataclass
class TemplateBlock:
    """模板块"""
    block_id: str
    block_type: str  # "static" | "dynamic" | "table"
    content: str = ""  # 原始内容
    data_key: Optional[str] = None  # 变量键名
    sample_value: Optional[Any] = None  # 示例值
    variable_pattern: Optional[str] = None  # 变量模式
    confidence: float = 1.0  # 置信度
    description: str = ""  # 描述
    children: List['TemplateBlock'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_type": self.block_type,
            "content": self.content,
            "data_key": self.data_key,
            "sample_value": self.sample_value,
            "variable_pattern": self.variable_pattern,
            "confidence": self.confidence,
            "description": self.description,
            "children": [c.to_dict() if isinstance(c, TemplateBlock) else c for c in self.children],
            "attributes": self.attributes
        }


@dataclass
class TableTemplate:
    """表格模板"""
    table_id: str
    data_key: str
    headers: List[Dict[str, str]]  # [{"key": "col1", "name": "第一列", "type": "string"}]
    data_rows: List[Dict[str, Any]]  # 示例数据行
    row_template: Optional[Dict[str, Any]] = None  # 行模板
    is_repeatable: bool = True  # 是否可重复
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "data_key": self.data_key,
            "headers": self.headers,
            "data_rows": self.data_rows,
            "row_template": self.row_template,
            "is_repeatable": self.is_repeatable,
            "confidence": self.confidence
        }


@dataclass
class TemplateConfig:
    """智能模板配置"""
    template_id: str
    template_name: str
    template_version: str = "1.0.0"
    document_type: str = ""  # 报告类型（环评/安评/能评等）
    source_file: str = ""  # 来源文件
    checksum: str = ""  # 源文件校验和
    description: str = ""
    blocks: List[TemplateBlock] = field(default_factory=list)
    tables: List[TableTemplate] = field(default_factory=list)
    data_schema: Dict[str, Any] = field(default_factory=dict)  # 数据 schema
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "template_version": self.template_version,
            "document_type": self.document_type,
            "source_file": self.source_file,
            "checksum": self.checksum,
            "description": self.description,
            "blocks": [b.to_dict() if isinstance(b, TemplateBlock) else b for b in self.blocks],
            "tables": [t.to_dict() if isinstance(t, TableTemplate) else t for t in self.tables],
            "data_schema": self.data_schema,
            "metadata": self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, output_path: str):
        """保存模板配置"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"模板配置已保存到: {output_path}")


# ==================== AI推理模板引擎 ====================

class AITemplateEngine:
    """
    AI推理模板引擎

    通过结构化分析和 LLM 推理，将文档 AST 自动解耦为：
    - template_skeleton: 固定骨架
    - dynamic_data: 可变数据键
    """

    def __init__(self, llm_callable: Optional[Callable] = None):
        """
        初始化引擎

        Args:
            llm_callable: LLM 调用函数，签名为 (prompt: str) -> str
                         如果不提供，使用内置的正则匹配规则
        """
        self._llm = llm_callable
        self._block_counter = 0
        self._table_counter = 0

    def _generate_block_id(self) -> str:
        self._block_counter += 1
        return f"block_{self._block_counter:04d}"

    def _generate_table_id(self) -> str:
        self._table_counter += 1
        return f"table_{self._table_counter:04d}"

    async def infer_template(
        self,
        document_ast: Dict[str, Any],
        document_type: str = "",
        domain_hint: str = "environmental_assessment"  # 领域提示：环保/安全/能源等
    ) -> TemplateConfig:
        """
        从文档 AST 推理模板配置

        Args:
            document_ast: 文档 JSON AST
            document_type: 文档类型
            domain_hint: 领域提示，帮助 LLM 更好地理解上下文

        Returns:
            TemplateConfig: 智能模板配置
        """
        template = TemplateConfig(
            template_id=self._generate_block_id(),
            template_name=document_ast.get('file_name', '未知文档'),
            document_type=document_type,
            source_file=document_ast.get('file_path', ''),
            checksum=document_ast.get('checksum', '')
        )

        root = document_ast.get('root')
        if not root:
            logger.warning("文档 AST 为空")
            return template

        # 遍历 AST 节点
        await self._process_node(root, template, domain_hint)

        # 生成数据 schema
        template.data_schema = self._generate_data_schema(template)

        # 添加元数据
        template.metadata = {
            "inferred_at": "",
            "engine_version": "1.0.0",
            "domain_hint": domain_hint,
            "total_blocks": len(template.blocks),
            "total_tables": len(template.tables)
        }

        return template

    async def _process_node(
        self,
        node: Dict[str, Any],
        template: TemplateConfig,
        domain_hint: str
    ):
        """递归处理 AST 节点"""
        node_type = node.get('node_type', '')
        content = node.get('content', '')
        children = node.get('children', [])

        if node_type == 'document':
            # 文档根节点，递归处理子节点
            for child in children:
                await self._process_node(child, template, domain_hint)

        elif node_type == 'heading' or (node.get('attributes', {}).get('is_heading')):
            # 标题节点 - 通常是固定文本
            block = TemplateBlock(
                block_id=self._generate_block_id(),
                block_type="static",
                content=content,
                description="章节标题",
                confidence=0.95
            )
            template.blocks.append(block)

        elif node_type == 'paragraph':
            # 段落节点
            if content.strip():
                await self._process_paragraph(node, template, domain_hint)
            # 递归处理子节点（可能包含强调文本等）
            for child in children:
                if isinstance(child, dict):
                    await self._process_node(child, template, domain_hint)

        elif node_type == 'table':
            # 表格节点
            await self._process_table(node, template, domain_hint)

    async def _process_paragraph(
        self,
        node: Dict[str, Any],
        template: TemplateConfig,
        domain_hint: str
    ):
        """处理段落节点"""
        content = node.get('content', '').strip()
        if not content:
            return

        # 尝试 LLM 推理（如果提供了 LLM）
        if self._llm:
            classification = await self._llm_classify(content, domain_hint)
        else:
            classification = self._rule_classify(content, domain_hint)

        if classification['is_dynamic']:
            # 可变数据
            block = TemplateBlock(
                block_id=self._generate_block_id(),
                block_type="dynamic",
                content=content,
                data_key=classification.get('data_key', self._suggest_data_key(content)),
                sample_value=classification.get('sample_value', content),
                variable_pattern=classification.get('pattern', 'unknown'),
                confidence=classification.get('confidence', 0.7),
                description=classification.get('description', '')
            )
        else:
            # 固定文本
            block = TemplateBlock(
                block_id=self._generate_block_id(),
                block_type="static",
                content=content,
                description=classification.get('description', '固定文本'),
                confidence=0.95
            )

        template.blocks.append(block)

    async def _process_table(
        self,
        node: Dict[str, Any],
        template: TemplateConfig,
        domain_hint: str
    ):
        """处理表格节点"""
        attrs = node.get('attributes', {})
        headers = attrs.get('headers', [])
        data_rows = attrs.get('data_rows', [])

        if not headers and not data_rows:
            return

        # 为表格生成 data_key
        table_key = self._suggest_table_key(headers, domain_hint)

        # 处理表头
        header_templates = []
        for idx, header in enumerate(headers):
            header_type = self._infer_column_type(
                [row[idx] if idx < len(row) else '' for row in data_rows],
                domain_hint
            )
            header_templates.append({
                "key": self._to_snake_case(header) if header else f"col_{idx}",
                "name": header,
                "type": header_type
            })

        # 处理数据行
        data_row_templates = []
        for row in data_rows[:5]:  # 最多取5行作为示例
            row_dict = {}
            for idx, cell in enumerate(row):
                key = header_templates[idx]['key'] if idx < len(header_templates) else f"col_{idx}"
                row_dict[key] = cell
            data_row_templates.append(row_dict)

        table_template = TableTemplate(
            table_id=self._generate_table_id(),
            data_key=table_key,
            headers=header_templates,
            data_rows=data_row_templates,
            is_repeatable=True,
            confidence=0.85
        )
        template.tables.append(table_template)

    async def _llm_classify(self, content: str, domain_hint: str) -> Dict[str, Any]:
        """使用 LLM 分类内容"""
        prompt = f"""分析以下文本内容，判断它是"固定文本"还是"可变数据"：

领域：{domain_hint}
内容：{content}

输出 JSON 格式：
{{
    "is_dynamic": true/false,
    "data_key": "建议的变量键名（如果是可变数据）",
    "sample_value": "示例值（如果是可变数据）",
    "pattern": "变量模式（number/date/company_name等）",
    "confidence": 0.0-1.0,
    "description": "内容描述"
}}
"""
        try:
            result = await self._llm(prompt)
            return json.loads(result)
        except Exception as e:
            logger.warning(f"LLM 分类失败，回退到规则匹配: {e}")
            return self._rule_classify(content, domain_hint)

    def _rule_classify(self, content: str, domain_hint: str) -> Dict[str, Any]:
        """
        基于规则的分类（当没有 LLM 时使用）

        规则：
        1. 包含数字/百分比的可能是可变数据
        2. 包含日期格式的可能是可变数据
        3. 包含企业名称/地址的可能是可变数据
        4. 法律条款/标准引用通常是固定文本
        """
        import re

        classification: Dict[str, Any] = {
            "is_dynamic": False,
            "description": "固定文本"
        }

        # 检测模式
        patterns = {
            VariablePattern.DATE.value: r'\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}',
            VariablePattern.NUMBER.value: r'\d+\.?\d*\s*(mg/Nm³|t/a|万元|元|kW|MW|°C|%)?',
            VariablePattern.COMPANY_NAME.value: r'[\u4e00-\u9fa5]{2,}(公司|厂|企业|集团|有限|股份)',
            VariablePattern.PERCENTAGE.value: r'\d+\.?\d*%',
            VariablePattern.CURRENCY.value: r'\d+\.?\d*\s*(万元|亿元|元)',
            VariablePattern.MONITORING_VALUE.value: r'\d+\.?\d*\s*(mg/Nm³|μg/m³|mg/L|dB)',
        }

        for pattern_name, pattern_regex in patterns.items():
            if re.search(pattern_regex, content):
                classification["is_dynamic"] = True
                classification["pattern"] = pattern_name
                classification["confidence"] = 0.7
                classification["data_key"] = self._suggest_data_key(content)
                classification["description"] = f"检测到{pattern_name}模式"

                # 提取示例值
                match = re.search(pattern_regex, content)
                if match:
                    classification["sample_value"] = match.group()
                break

        # 法律/标准引用 - 固定文本
        law_patterns = [r'依据', r'根据', r'《', r'》', r'规定', r'标准', r'规范', r'法']
        if not classification["is_dynamic"]:
            for law_pat in law_patterns:
                if law_pat in content:
                    classification["is_dynamic"] = False
                    classification["description"] = "法规/标准引用"
                    break

        return classification

    def _suggest_data_key(self, content: str) -> str:
        """根据内容建议数据键名"""
        # 常见前缀映射
        prefix_map = {
            '企业': 'company_name',
            '名称': 'name',
            '地址': 'address',
            '电话': 'phone',
            '传真': 'fax',
            '邮编': 'postal_code',
            '联系人': 'contact_person',
            '监测': 'monitoring_value',
            '排放': 'emission_value',
            '浓度': 'concentration',
            '总量': 'total_amount',
            '投资': 'investment',
            '建设': 'construction',
            '生产': 'production',
            '面积': 'area',
            '规模': 'scale',
            '产能': 'capacity',
            '日期': 'date',
            '时间': 'time',
            '编号': 'serial_number',
        }

        for prefix, key in prefix_map.items():
            if prefix in content:
                return key

        # 默认使用内容哈希
        return f"var_{hashlib.md5(content.encode()).hexdigest()[:8]}"

    def _suggest_table_key(self, headers: List[str], domain_hint: str) -> str:
        """根据表头建议表格键名"""
        if not headers:
            return "table_data"

        # 尝试从第一列推断
        first_header = headers[0] if headers else ""

        # 常见表格键名映射
        table_key_map = {
            '设备': 'equipment_list',
            '原辅': 'raw_material_list',
            '产品': 'product_list',
            '污染物': 'pollutant_list',
            '排放口': 'emission_point_list',
            '监测': 'monitoring_data',
            '人员': 'personnel_list',
            '投资': 'investment_list',
            '设备': 'equipment_list',
            '工序': 'process_list',
            '车间': 'workshop_list',
        }

        for key, value in table_key_map.items():
            if key in first_header:
                return value

        # 默认使用第一列名称
        return f"table_{self._to_snake_case(first_header)}" if first_header else "table_data"

    def _infer_column_type(self, values: List[str], domain_hint: str) -> str:
        """推断列类型"""
        import re

        if not values:
            return "string"

        sample = str(values[0]) if values else ""

        # 检测数值类型
        if re.match(r'^-?\d+\.?\d*$', sample):
            return "number"

        # 检测日期
        if re.match(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', sample):
            return "date"

        # 检测百分比
        if '%' in sample:
            return "percentage"

        # 检测金额
        if any(u in sample for u in ['万', '亿', '元', 'USD', 'RMB']):
            return "currency"

        # 检测监测值（带单位）
        if any(u in sample for u in ['mg/Nm³', 'μg/m³', 'mg/L', 'dB', 'ppm']):
            return "monitoring_value"

        return "string"

    def _to_snake_case(self, text: str) -> str:
        """转换为蛇形命名"""
        import re
        # 去除括号及其内容
        text = re.sub(r'[（(].*?[）)]', '', text)
        # 替换空格和特殊字符
        text = re.sub(r'[\s\-/]', '_', text)
        # 去除非字母数字
        text = re.sub(r'[^\w]', '', text)
        return text.lower()

    def _generate_data_schema(self, template: TemplateConfig) -> Dict[str, Any]:
        """生成数据 schema"""
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": []
        }

        # 从 blocks 提取
        for block in template.blocks:
            if block.block_type == "dynamic" and block.data_key:
                schema["properties"][block.data_key] = {
                    "type": "string",
                    "description": block.description or block.content,
                    "example": block.sample_value
                }

        # 从 tables 提取
        for table in template.tables:
            table_schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {}
                },
                "description": f"表格数据: {table.data_key}"
            }
            for header in table.headers:
                key = header.get('key', '')
                table_schema["items"]["properties"][key] = {
                    "type": header.get('type', 'string'),
                    "description": header.get('name', '')
                }
            schema["properties"][table.data_key] = table_schema

        return schema


# ==================== 便捷函数 ====================

_engine: Optional[AITemplateEngine] = None


def get_ai_template_engine(llm_callable: Optional[Callable] = None) -> AITemplateEngine:
    """获取 AI 模板引擎单例"""
    global _engine
    if _engine is None:
        _engine = AITemplateEngine(llm_callable)
    return _engine


async def infer_template(
    document_ast: Dict[str, Any],
    document_type: str = "",
    domain_hint: str = "environmental_assessment",
    llm_callable: Optional[Callable] = None
) -> TemplateConfig:
    """从文档 AST 推理模板"""
    engine = get_ai_template_engine(llm_callable)
    return await engine.infer_template(document_ast, document_type, domain_hint)