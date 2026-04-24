"""
AI Script Generator - 智能脚本生成引擎
=======================================

核心理念：从"工具"到"伙伴"，用户用自然语言描述需求，AI生成可执行脚本

三层架构：
1. 自然语言交互层 - 意图识别、需求解析
2. AI代码生成引擎 - 上下文感知、安全生成
3. 可执行沙箱环境 - 隔离执行、热重载

Author: Hermes Desktop Team
"""

import asyncio
import ast
import hashlib
import importlib
import inspect
import json
import os
import re
import sys
import uuid
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import logging

logger = logging.getLogger(__name__)

# ============= 枚举定义 =============


class ScriptType(Enum):
    """脚本类型"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SHELL = "shell"


class GenerationStatus(Enum):
    """生成状态"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionStatus(Enum):
    """执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


class SafetyLevel(Enum):
    """安全级别"""
    SAFE = "safe"           # 无危险操作
    CAUTION = "caution"    # 需要确认
    DANGEROUS = "dangerous"  # 高风险操作


# ============= 数据模型 =============


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: str           # 主要意图
    entities: Dict[str, Any]      # 实体提取
    parameters: Dict[str, Any]    # 参数解析
    confidence: float             # 置信度
    suggested_script_type: ScriptType = ScriptType.PYTHON


@dataclass
class CodeContext:
    """代码生成上下文"""
    user_id: str
    session_id: str
    current_app_state: Dict[str, Any] = field(default_factory=dict)
    recent_operations: List[Dict] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    available_modules: List[str] = field(default_factory=list)
    active_windows: List[Dict] = field(default_factory=list)


@dataclass
class GenerationRequest:
    """生成请求"""
    request_id: str
    description: str               # 自然语言描述
    intent: Optional[IntentResult] = None
    context: Optional[CodeContext] = None
    script_type: ScriptType = ScriptType.PYTHON
    safety_level: SafetyLevel = SafetyLevel.SAFE
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ScriptCode:
    """生成的脚本代码"""
    script_id: str
    code: str
    language: ScriptType
    entry_function: str = "main"
    dependencies: List[str] = field(default_factory=list)
    permissions_required: Set[str] = field(default_factory=set)
    safety_warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    request_id: str
    script: Optional[ScriptCode] = None
    status: GenerationStatus = GenerationStatus.PENDING
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """执行结果"""
    script_id: str
    status: ExecutionStatus
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_usage: int = 0
    warnings: List[str] = field(default_factory=list)


# ============= 安全检查规则 =============


DANGEROUS_PATTERNS = {
    'file_operations': [
        (r'os\.remove', '删除文件'),
        (r'os\.rmdir', '删除目录'),
        (r'shutil\.rmtree', '递归删除'),
        (r'pathlib.*\.unlink', '删除文件'),
        (r'\.delete\(', '数据库删除'),
    ],
    'network': [
        (r'urllib.*open', '网络请求'),
        (r'requests\.', 'HTTP请求'),
        (r'http\.client', 'HTTP客户端'),
        (r'socket\.', 'socket连接'),
    ],
    'system': [
        (r'os\.system', '系统命令'),
        (r'subprocess\.', '子进程'),
        (r'exec\(|eval\(|compile\(', '动态代码执行'),
        (r'__import__', '动态导入'),
    ],
    'security': [
        (r'password|passwd', '密码操作'),
        (r'key|token|secret', '密钥操作'),
        (r'chmod|chown', '权限修改'),
    ]
}

SAFE_PATTERNS = [
    r'print\(',
    r'return ',
    r'def \w+\(',
    r'class \w+:',
    r'import ',
    r'from .* import',
    r'if .*:',
    r'for .* in',
    r'while .*:',
    r'with .* as',
]


# ============= 意图识别 =============


class IntentRecognizer:
    """
    意图识别器 - 理解用户想要什么
    """

    # 意图模式库
    INTENT_PATTERNS = {
        'create_ui': {
            'keywords': ['创建', '新建', '添加', '面板', '窗口', '按钮', '界面', '显示', '弹出'],
            'examples': [
                '我想在页面旁边显示一个分析面板',
                '帮我创建一个设置窗口',
                '添加一个快捷键触发的浮窗',
            ]
        },
        'automate_workflow': {
            'keywords': ['自动', '批量', '一键', '每次', '自动化', '流程'],
            'examples': [
                '每次打开文件夹时自动压缩',
                '帮我自动化这个配置过程',
                '一键配置代理',
            ]
        },
        'data_visualization': {
            'keywords': ['图表', '可视化', '数据', '监控', '实时', '仪表盘'],
            'examples': [
                '把这个数据显示成图表',
                '创建实时数据监控面板',
                '帮我可视化API返回的数据',
            ]
        },
        'content_enhancement': {
            'keywords': ['翻译', '总结', '增强', '优化', '摘要', '解释'],
            'examples': [
                '帮我翻译这篇文章',
                '总结一下这个文档的主要内容',
                '增强这个页面的阅读体验',
            ]
        },
        'network_routing': {
            'keywords': ['路由', '代理', '镜像', '加速', '转发', '链接'],
            'examples': [
                '把所有YouTube链接转B站',
                '设置自动代理规则',
                '创建智能路由策略',
            ]
        },
        'code_generation': {
            'keywords': ['生成', '写', '创建', '函数', '算法', '代码', '编程', '实现', '开发'],
            'examples': [
                '帮我生成一个排序算法',
                '写一个处理JSON的函数',
                '创建API调用代码',
            ]
        },
        'file_conversion': {
            'keywords': ['转换', '转成', '导出', '导入', '格式', 'pdf', 'word', 'excel', '图片'],
            'examples': [
                '把这个PDF转成Word',
                '批量转换图片格式',
                '导出为Excel',
            ]
        },
    }

    def recognize(self, description: str) -> IntentResult:
        """
        识别用户意图

        Args:
            description: 自然语言描述

        Returns:
            IntentResult: 意图识别结果
        """
        description_lower = description.lower()

        # 计算每个意图的匹配度
        intent_scores = {}
        for intent_name, intent_info in self.INTENT_PATTERNS.items():
            score = 0.0

            # 关键词匹配
            for keyword in intent_info['keywords']:
                if keyword in description_lower:
                    score += 1.0

            # 示例匹配
            for example in intent_info['examples']:
                if any(word in description_lower for word in example[:10].split()):
                    score += 0.5

            if score > 0:
                intent_scores[intent_name] = score

        # 选择最佳意图
        if not intent_scores:
            return IntentResult(
                primary_intent='unknown',
                entities={},
                parameters={},
                confidence=0.0
            )

        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent] / 10.0  # 归一化

        # 提取实体
        entities = self._extract_entities(description)

        # 解析参数
        parameters = self._extract_parameters(description)

        return IntentResult(
            primary_intent=best_intent,
            entities=entities,
            parameters=parameters,
            confidence=min(confidence, 1.0)
        )

    def _extract_entities(self, description: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {}

        # URL
        urls = re.findall(r'https?://[^\s]+', description)
        if urls:
            entities['urls'] = urls

        # 文件路径
        paths = re.findall(r'[A-Za-z]:\\[^:\s]+|/[^:\s]+', description)
        if paths:
            entities['paths'] = paths

        # 数字
        numbers = re.findall(r'\d+', description)
        if numbers:
            entities['numbers'] = [int(n) for n in numbers]

        return entities

    def _extract_parameters(self, description: str) -> Dict[str, Any]:
        """提取参数"""
        params = {}

        # 时间参数
        if '每次' in description or '每次打开' in description:
            params['trigger'] = 'on_open'

        if '一键' in description:
            params['one_click'] = True

        # 数量参数
        numbers = re.findall(r'(\d+)个', description)
        if numbers:
            params['count'] = int(numbers[0])

        return params


# ============= 安全检查器 =============


class SecurityChecker:
    """
    安全检查器 - 确保生成的代码安全
    """

    def __init__(self):
        self.dangerous_patterns = DANGEROUS_PATTERNS

    def check(self, code: str) -> tuple[SafetyLevel, List[str]]:
        """
        检查代码安全性

        Returns:
            (SafetyLevel, warnings)
        """
        warnings = []
        danger_score = 0

        # 检查危险模式
        for category, patterns in self.dangerous_patterns.items():
            for pattern, description in patterns:
                if re.search(pattern, code):
                    danger_score += 1
                    warnings.append(f"⚠️ 检测到{category}.{description}操作")

        # 检查是否有异常处理
        has_exception_handling = 'try:' in code or 'except' in code
        if danger_score > 0 and not has_exception_handling:
            warnings.append("⚠️ 代码缺少异常处理，建议添加 try-except")

        # 检查是否有资源清理
        has_cleanup = 'finally:' in code or 'with ' in code
        if danger_score > 0 and not has_cleanup:
            warnings.append("⚠️ 建议使用 with 语句确保资源正确释放")

        # 确定安全级别
        if danger_score == 0:
            level = SafetyLevel.SAFE
        elif danger_score <= 2:
            level = SafetyLevel.CAUTION
        else:
            level = SafetyLevel.DANGEROUS
            warnings.append("🚨 高风险操作，需要人工审核")

        return level, warnings

    def check_permission(self, code: str) -> Set[str]:
        """
        检查需要的权限

        Returns:
            需要的权限集合
        """
        permissions = set()

        # 文件操作 - extract pattern from tuple (pattern, description)
        if any(re.search(p[0], code) for p in self.dangerous_patterns['file_operations']):
            permissions.add('file:read')
            if 'remove' in code or 'delete' in code or 'rm' in code:
                permissions.add('file:write')

        # 网络操作
        if any(re.search(p[0], code) for p in self.dangerous_patterns['network']):
            permissions.add('network:internet')

        # 系统操作
        if any(re.search(p[0], code) for p in self.dangerous_patterns['system']):
            permissions.add('system:execute')

        return permissions


# ============= AI代码生成器 =============


class AICodeGenerator:
    """
    AI代码生成器 - 根据意图生成代码
    """

    # 模板库
    TEMPLATES = {
        'create_ui': '''
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit

class {class_name}Panel(QWidget):
    """自动生成的{panel_name}面板"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 标题
        title = QLabel("{title_text}")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 内容区域
        self.content = QTextEdit()
        self.content.setPlaceholderText("{placeholder}")
        layout.addWidget(self.content)

        # 操作按钮
        self.action_btn = QPushButton("{button_text}")
        self.action_btn.clicked.connect(self.on_action)
        layout.addWidget(self.action_btn)

        self.setLayout(layout)

    def on_action(self):
        """处理操作"""
        content = self.content.toPlainText()
        # TODO: 实现具体逻辑
        logger.info(f"Content: {{content}}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = {class_name}Panel()
    panel.show()
    sys.exit(app.exec())
''',

        'automate_workflow': '''
import os
import sys
from pathlib import Path
from typing import List, Callable

class WorkflowAutomator:
    """自动化的{workflow_name}工作流"""

    def __init__(self):
        self.steps: List[Callable] = []
        self.results = []

    def add_step(self, name: str, func: Callable):
        """添加工作流步骤"""
        self.steps.append(func)
        logger.info(f"[+] 添加步骤: {{name}}")

    def execute(self):
        """执行工作流"""
        logger.info(f"开始执行工作流: {len(self.steps)} 个步骤")
        for i, step in enumerate(self.steps, 1):
            logger.info(f"  步骤 {{i}}: {{step.__name__}}")
            try:
                result = step()
                self.results.append(result)
                logger.info(f"  ✓ 完成")
            except Exception as e:
                logger.info(f"  ✗ 失败: {{e}}")
                self.results.append(None)
        logger.info(f"工作流执行完成: {{len([r for r in self.results if r])}} 成功")

    def generate_script(self) -> str:
        """生成可执行脚本"""
        return """
# {workflow_name} - 自动执行脚本
# 生成时间: {timestamp}

import sys
sys.path.insert(0, '.')

from pathlib import Path

def main():
    # TODO: 实现具体工作流逻辑
    logger.info("执行{workflow_name}...")

if __name__ == "__main__":
    main()
"""

# 使用示例
automator = WorkflowAutomator()
# automator.add_step("步骤1", lambda: logger.info("执行步骤1"))
# automator.execute()
''',

        'data_visualization': '''
import sys
from typing import Dict, List, Any
from datetime import datetime

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
    from PyQt6.QtChart import QChartView, QChart, QBarSeries, QBarSet, QValueAxis
    HAS_PYQT_CHART = True
except ImportError:
    HAS_PYQT_CHART = False

class DataVisualizer:
    """数据可视化器 - {viz_name}"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.chart = None

    def create_chart(self) -> Any:
        """创建图表"""
        if not HAS_PYQT_CHART:
            logger.info("PyQt6 Charts 未安装，使用文本模式")
            return self._text_chart()

        # 创建柱状图示例
        series = QBarSeries()
        bar_set = QBarSet("数据")

        for key, value in self.data.items():
            if isinstance(value, (int, float)):
                bar_set.append([value])

        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("{viz_name}")
        chart.createDefaultAxes()

        return chart

    def _text_chart(self) -> str:
        """文本模式图表"""
        result = "=== {viz_name} ===\\n"
        max_val = max(self.data.values()) if self.data else 1

        for key, value in self.data.items():
            bar = "█" * int(value / max_val * 30)
            result += f"{{key}}: {{bar}} ({{value}})\\n"

        return result

    def get_summary(self) -> str:
        """获取数据摘要"""
        if not self.data:
            return "无数据"

        return f"""
数据摘要:
- 数据点数: {{len(self.data)}}
- 更新时间: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}
- 数值范围: {{min(self.data.values()) if self.data.values() else 0}} ~ {{max(self.data.values()) if self.data.values() else 0}}
"""

def main():
    # 示例数据
    sample_data = {{
        "类别A": 100,
        "类别B": 75,
        "类别C": 50,
        "类别D": 25,
    }}

    viz = DataVisualizer(sample_data)
    logger.info(viz._text_chart())
    logger.info(viz.get_summary())

if __name__ == "__main__":
    main()
''',

        'network_routing': '''
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

@dataclass
class RouteRule:
    """路由规则"""
    name: str
    match_pattern: str  # URL正则
    action: str         # direct/mirror/proxy/block
    target: Optional[str] = None
    priority: int = 0

class SmartRouter:
    """智能路由 - {router_name}"""

    def __init__(self):
        self.rules: List[RouteRule] = []
        self.fallback_action = "direct"

    def add_rule(self, rule: RouteRule):
        """添加路由规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)  # 按优先级排序

    def route(self, url: str) -> str:
        """路由决策"""
        for rule in self.rules:
            if re.search(rule.match_pattern, url):
                logger.info(f"匹配规则: {{rule.name}} -> {{rule.action}}")
                return self._execute_action(url, rule)
            else:
                return self.fallback_action

    def _execute_action(self, url: str, rule: RouteRule) -> str:
        """执行路由动作"""
        if rule.action == "mirror":
            return rule.target or self._find_mirror(url)
        elif rule.action == "proxy":
            return f"proxy://{{rule.target}}"
        elif rule.action == "block":
            return "BLOCKED"
        return url

    def _find_mirror(self, url: str) -> str:
        """查找镜像"""
        mirrors = {{
            "github.com": "hub.fastgit.xyz",
            "youtube.com": "bilibili.com",
        }}

        for domain, mirror in mirrors.items():
            if domain in url:
                return url.replace(domain, mirror)
        return url

    def export_rules(self) -> str:
        """导出规则配置"""
        return """
# Smart Router Rules
# 生成时间: {timestamp}

RULES = [
    # TODO: 添加你的路由规则
]
"""
''',

        'content_enhancement': '''
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ContentBlock:
    """内容块"""
    type: str  # paragraph/code/heading/list
    content: str
    language: Optional[str] = None

class ContentEnhancer:
    """内容增强器 - {enhance_name}"""

    def __init__(self, content: str):
        self.content = content
        self.blocks: List[ContentBlock] = []

    def parse(self) -> List[ContentBlock]:
        """解析内容"""
        lines = self.content.split('\\n')
        current_block = ""

        for line in lines:
            if line.startswith('```'):
                # 代码块
                if current_block.strip():
                    self.blocks.append(ContentBlock("paragraph", current_block.strip()))
                    current_block = ""
                lang = line[3:].strip() if line[3:].strip() else None
                self.blocks.append(ContentBlock("code", "", lang))
            elif line.startswith('#'):
                # 标题
                if current_block.strip():
                    self.blocks.append(ContentBlock("paragraph", current_block.strip()))
                    current_block = ""
                self.blocks.append(ContentBlock("heading", line))
            elif line.startswith('- ') or line.startswith('* '):
                # 列表
                if current_block.strip() and not current_block.startswith('- '):
                    self.blocks.append(ContentBlock("paragraph", current_block.strip()))
                current_block += line + "\\n"
            else:
                current_block += line + "\\n"

        if current_block.strip():
            self.blocks.append(ContentBlock("paragraph", current_block.strip()))

        return self.blocks

    def translate(self, text: str, target_lang: str = "zh") -> str:
        """翻译文本"""
        # TODO: 调用翻译API
        return f"[翻译] {{text}}"

    def summarize(self, text: str, max_length: int = 200) -> str:
        """总结文本"""
        # 简单实现：取前max_length字符
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def enhance(self) -> str:
        """增强内容"""
        self.parse()
        enhanced = []

        for block in self.blocks:
            if block.type == "paragraph":
                # 翻译
                if len(block.content) > 500:
                    block.content = self.summarize(block.content)
                enhanced.append(block.content)
            elif block.type == "code":
                enhanced.append(f"```{{block.language or ''}}\\n{block.content}\\n```")
            else:
                enhanced.append(block.content)

        return "\\n\\n".join(enhanced)
''',

    # 扩展模板
    'file_conversion': '''
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ConversionTask:
    source_path: str
    target_path: str
    source_format: str
    target_format: str
    options: Dict[str, Any] = None

class FileConverter:
    def __init__(self):
        self.tasks: List[ConversionTask] = []
        self.results: List[Dict] = []

    def convert(self, source_path: str, target_path: str, target_format: str) -> bool:
        try:
            source_path = Path(source_path)
            target_path = Path(target_path)
            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if target_format == 'csv':
                result = self._to_csv(content)
            elif target_format == 'json':
                result = self._to_json(content)
            else:
                result = content
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"[OK] Converted: {source_path.name}")
            return True
        except Exception as e:
            logger.info(f"[ERROR] {e}")
            return False

    def _to_csv(self, content: str) -> str:
        try:
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0:
                headers = list(data[0].keys())
                rows = [headers] + [[str(item.get(h, '')) for h in headers] for item in data]
                return '\\n'.join([','.join(row) for row in rows])
        except:
            pass
        return content

    def _to_json(self, content: str) -> str:
        lines = content.strip().split('\\n')
        if len(lines) > 1:
            headers = lines[0].split(',')
            data = [dict(zip(headers, line.split(','))) for line in lines[1:]]
            return json.dumps(data, ensure_ascii=False, indent=2)
        return content

if __name__ == "__main__":
    logger.info("File Converter Ready")
''',

    'web_scraping': '''
import re
import json
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ScrapedContent:
    url: str
    title: str
    content: str
    author: Optional[str] = None

class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.content_cache: Dict[str, ScrapedContent] = {}

    def fetch(self, url: str, timeout: int = 30) -> Optional[str]:
        try:
            r = self.session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.info(f"[ERROR] {e}")
            return None

    def extract(self, html: str) -> str:
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        return re.sub(r'<[^>]+>', '', html).strip()

    def scrape(self, url: str) -> Optional[ScrapedContent]:
        html = self.fetch(url)
        if not html:
            return None
        title = re.search(r'<title>([^<]+)</title>', html)
        return ScrapedContent(url=url, title=title.group(1) if title else "No Title", content=self.extract(html))

    def export(self, filepath: str = "scraped.json"):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([{'url': c.url, 'title': c.title, 'content': c.content} for c in self.content_cache.values()], f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] Exported to {filepath}")

if __name__ == "__main__":
    logger.info("Web Scraper Ready")
''',

    'image_processing': '''
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ImageInfo:
    path: str
    filename: str
    format: str
    size: Tuple[int, int]
    file_size: int

class ImageProcessor:
    def __init__(self):
        self.supported = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        self.processed: List[ImageInfo] = []

    def get_info(self, filepath: str) -> Optional[ImageInfo]:
        p = Path(filepath)
        if not p.exists() or p.suffix.lower() not in self.supported:
            return None
        return ImageInfo(path=str(p), filename=p.name, format=p.suffix[1:], size=(0, 0), file_size=p.stat().st_size)

    def batch_resize(self, paths: List[str], size: Tuple[int, int]) -> List[str]:
        results = []
        for path in paths:
            info = self.get_info(path)
            if info:
                logger.info(f"[OK] {info.filename} ready for resize to {size}")
                results.append(info.path)
        return results

if __name__ == "__main__":
    logger.info("Image Processor Ready")
''',

    'data_export': '''
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from enum import Enum
from core.logger import get_logger
logger = get_logger('ai_script_generator.script_engine')


class ExportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    MARKDOWN = "md"

class DataExporter:
    def __init__(self):
        self.history: List[Dict] = []

    def export(self, data: List[Dict[str, Any]], path: str, fmt: ExportFormat = ExportFormat.JSON) -> bool:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if fmt == ExportFormat.JSON:
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            elif fmt == ExportFormat.CSV:
                if data:
                    with open(p, 'w', encoding='utf-8', newline='') as f:
                        w = csv.DictWriter(f, fieldnames=data[0].keys())
                        w.writeheader()
                        w.writerows(data)
            logger.info(f"[OK] Exported {len(data)} records to {path}")
            self.history.append({'path': path, 'count': len(data)})
            return True
        except Exception as e:
            logger.info(f"[ERROR] {e}")
            return False

if __name__ == "__main__":
    logger.info("Data Exporter Ready")
'''
    }

    def __init__(self, security_checker: SecurityChecker):
        self.security_checker = security_checker
        self.intent_recognizer = IntentRecognizer()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        根据请求生成代码

        Args:
            request: 生成请求

        Returns:
            GenerationResult: 生成结果
        """
        try:
            # 1. 意图识别（如果未提供）
            if not request.intent:
                intent = self.intent_recognizer.recognize(request.description)
                request.intent = intent

            # 2. 选择模板
            template = self._select_template(request)

            # 3. 填充模板
            code = self._fill_template(request, template)

            # 4. 安全检查
            safety_level, warnings = self.security_checker.check(code)

            # 5. 提取依赖和权限
            dependencies = self._extract_dependencies(code)
            permissions = self.security_checker.check_permission(code)

            # 6. 生成脚本
            script = ScriptCode(
                script_id=f"script_{uuid.uuid4().hex[:12]}",
                code=code,
                language=request.script_type,
                dependencies=dependencies,
                permissions_required=permissions,
                safety_warnings=warnings,
                metadata={
                    'intent': request.intent.primary_intent,
                    'generated_at': datetime.now().isoformat(),
                    'safety_level': safety_level.value,
                }
            )

            return GenerationResult(
                success=True,
                request_id=request.request_id,
                script=script,
                status=GenerationStatus.COMPLETED,
                warnings=warnings,
                suggestions=self._generate_suggestions(request.intent)
            )

        except Exception as e:
            logger.error(f"代码生成失败: {e}")
            return GenerationResult(
                success=False,
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                error_message=str(e)
            )

    def _select_template(self, request: GenerationRequest) -> str:
        """选择模板"""
        intent = request.intent.primary_intent if request.intent else 'unknown'

        # 根据意图选择模板
        if intent in self.TEMPLATES:
            template_key = intent
        else:
            # 默认使用通用模板
            template_key = 'automate_workflow'

        return self.TEMPLATES.get(template_key, self.TEMPLATES['automate_workflow'])

    def _fill_template(self, request: GenerationRequest, template: str) -> str:
        """填充模板"""
        intent = request.intent

        # 生成类名
        class_name = f"AutoGenerated{intent.primary_intent.title() if intent else 'Script'}"

        # 填充参数
        params = {
            'class_name': class_name,
            'panel_name': request.description[:20] if request.description else '自定义',
            'title_text': request.description[:50] if request.description else '自动生成的面板',
            'placeholder': f'请输入内容...' if request.description else '输入内容',
            'button_text': '执行' if request.description else '确定',
            'workflow_name': request.description[:30] if request.description else '工作流',
            'viz_name': request.description[:20] if request.description else '数据可视化',
            'router_name': request.description[:20] if request.description else '智能路由',
            'enhance_name': request.description[:20] if request.description else '内容增强',
            'timestamp': datetime.now().isoformat(),
        }

        # 替换模板中的占位符
        code = template
        for key, value in params.items():
            code = code.replace(f'{{{key}}}', str(value))

        return code

    def _extract_dependencies(self, code: str) -> List[str]:
        """提取依赖"""
        dependencies = []

        # 提取 import 语句
        import_pattern = r'^(?:from\s+(\S+)\s+import|import\s+(\S+))'
        for line in code.split('\n'):
            match = re.match(import_pattern, line.strip())
            if match:
                module = match.group(1) or match.group(2)
                if module and not module.startswith('.'):
                    dependencies.append(module)

        # 常见依赖
        common_deps = {
            'PyQt6', 'PyQt5', 'requests', 'urllib', 'json',
            'datetime', 'pathlib', 'collections', 'asyncio'
        }

        return list(set(dependencies) & common_deps)

    def _generate_suggestions(self, intent: IntentResult) -> List[str]:
        """生成建议"""
        suggestions = []

        if intent.primary_intent == 'create_ui':
            suggestions = [
                "可以添加数据刷新定时器",
                "考虑添加右键菜单",
                "可以绑定快捷键提升体验"
            ]
        elif intent.primary_intent == 'automate_workflow':
            suggestions = [
                "建议添加执行日志",
                "可以添加进度回调",
                "支持批量执行多个工作流"
            ]
        elif intent.primary_intent == 'data_visualization':
            suggestions = [
                "可以添加数据筛选功能",
                "支持导出图片",
                "可以添加实时更新"
            ]

        return suggestions


# ============= AI脚本生成引擎主类 =============


class AIScriptEngine:
    """
    AI脚本生成引擎 - 整合所有组件

    使用示例：
    ```python
    engine = AIScriptEngine()

    # 生成脚本
    request = GenerationRequest(
        request_id="req_001",
        description="我想创建一个显示数据分析的面板"
    )
    result = await engine.generate(request)

    if result.success:
        logger.info(result.script.code)
    ```
    """

    def __init__(self, scripts_dir: str = "./data/ai_scripts"):
        self.scripts_dir = Path(scripts_dir)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.security_checker = SecurityChecker()
        self.code_generator = AICodeGenerator(self.security_checker)
        self.intent_recognizer = IntentRecognizer()

        # 脚本注册表
        self.script_registry: Dict[str, ScriptCode] = {}

        logger.info(f"AI脚本引擎初始化完成，脚本目录: {self.scripts_dir}")

    async def generate(self, description: str, context: CodeContext = None) -> GenerationResult:
        """
        从自然语言描述生成脚本

        Args:
            description: 自然语言描述
            context: 可选的上下文信息

        Returns:
            GenerationResult: 生成结果
        """
        request = GenerationRequest(
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            description=description,
            context=context
        )

        # 生成代码
        result = await self.code_generator.generate(request)

        # 注册脚本
        if result.success and result.script:
            self.script_registry[result.script.script_id] = result.script

            # 保存到文件
            await self._save_script(result.script)

        return result

    async def _save_script(self, script: ScriptCode):
        """保存脚本到文件"""
        script_path = self.scripts_dir / f"{script.script_id}.py"

        content = f'''"""
AI生成的脚本: {script.script_id}
生成时间: {script.metadata.get('generated_at', 'N/A')}
意图: {script.metadata.get('intent', 'unknown')}
安全级别: {script.metadata.get('safety_level', 'unknown')}

⚠️ 安全警告:
{chr(10).join(f"- {w}" for w in script.safety_warnings) if script.safety_warnings else "无"}

📦 依赖: {script.dependencies}
🔐 需要权限: {script.permissions_required}
"""

{script.code}
'''

        script_path.write_text(content, encoding='utf-8')
        logger.info(f"脚本已保存: {script_path}")

    async def execute(self, script_id: str, params: Dict[str, Any] = None) -> ExecutionResult:
        """
        执行脚本

        Args:
            script_id: 脚本ID
            params: 执行参数

        Returns:
            ExecutionResult: 执行结果
        """
        if script_id not in self.script_registry:
            return ExecutionResult(
                script_id=script_id,
                status=ExecutionStatus.ERROR,
                error=f"脚本不存在: {script_id}"
            )

        script = self.script_registry[script_id]

        # TODO: 实现沙箱执行
        # 目前只是简单返回
        return ExecutionResult(
            script_id=script_id,
            status=ExecutionStatus.IDLE,
            output="脚本已注册，待执行"
        )

    def get_script_info(self, script_id: str) -> Optional[Dict]:
        """获取脚本信息"""
        if script_id not in self.script_registry:
            return None

        script = self.script_registry[script_id]
        return {
            'script_id': script.script_id,
            'language': script.language.value,
            'dependencies': script.dependencies,
            'permissions': list(script.permissions_required),
            'safety_level': script.metadata.get('safety_level'),
            'safety_warnings': script.safety_warnings,
            'generated_at': script.metadata.get('generated_at'),
        }

    def list_scripts(self) -> List[Dict]:
        """列出所有脚本"""
        return [
            self.get_script_info(sid)
            for sid in self.script_registry.keys()
        ]

    def recognize_intent(self, description: str) -> IntentResult:
        """识别意图（公开接口）"""
        return self.intent_recognizer.recognize(description)


# 全局实例
_engine_instance: Optional[AIScriptEngine] = None


def get_ai_script_engine() -> AIScriptEngine:
    """获取AI脚本引擎全局实例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AIScriptEngine()
    return _engine_instance
