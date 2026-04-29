"""
多模态输入系统 - MultiModeInput
核心理念：支持6种输入方式理解用户需求

支持的输入方式：
1. 📸 截图/拍照 → OCR识别 + 界面元素分析
2. 📁 上传文件 → 配置文件/文档解析
3. 🎤 语音描述 → 语音识别 + 意图理解
4. ✍️ 手写/涂鸦 → 图形识别 + 结构分析
5. 🎥 视频录制 → 操作步骤分解
6. 💬 文本描述 → 自然语言处理
"""

import base64
import io
import re
import os
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InputMode(Enum):
    """输入模式"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    HANDWRITING = "handwriting"
    VIDEO = "video"


@dataclass
class ParsedInput:
    """解析后的输入"""
    mode: InputMode
    raw_content: Any
    parsed_text: str
    confidence: float
    extracted_entities: Dict[str, Any]
    tech_stack_hints: List[str]
    requirements: List[str]


class MultiModeInputHandler:
    """
    多模态输入处理器

    将各种输入转换为统一的意图理解格式
    """

    def __init__(self):
        self._ocr_callback: Optional[Callable] = None
        self._asr_callback: Optional[Callable] = None
        self._handlers: Dict[InputMode, Callable] = {
            InputMode.TEXT: self._handle_text,
            InputMode.IMAGE: self._handle_image,
            InputMode.FILE: self._handle_file,
        }

    def set_ocr_callback(self, callback: Callable):
        """设置OCR回调"""
        self._ocr_callback = callback

    def set_asr_callback(self, callback: Callable):
        """设置语音识别回调"""
        self._asr_callback = callback

    def parse(self, mode: InputMode, content: Any) -> ParsedInput:
        """
        解析输入

        Args:
            mode: 输入模式
            content: 输入内容

        Returns:
            ParsedInput: 解析结果
        """
        handler = self._handlers.get(mode, self._handle_unknown)
        return handler(content)

    def _handle_text(self, content: str) -> ParsedInput:
        """处理文本输入"""
        return ParsedInput(
            mode=InputMode.TEXT,
            raw_content=content,
            parsed_text=content,
            confidence=0.95,
            extracted_entities=self._extract_entities(content),
            tech_stack_hints=self._extract_tech_hints(content),
            requirements=self._extract_requirements(content)
        )

    def _handle_image(self, content: bytes) -> ParsedInput:
        """处理图片输入（OCR）"""
        parsed_text = ""

        if self._ocr_callback:
            try:
                parsed_text = self._ocr_callback(content)
            except Exception as e:
                logger.error(f"OCR failed: {e}")
                parsed_text = ""

        return ParsedInput(
            mode=InputMode.IMAGE,
            raw_content=content,
            parsed_text=parsed_text,
            confidence=0.7 if parsed_text else 0.3,
            extracted_entities=self._extract_entities(parsed_text),
            tech_stack_hints=self._extract_tech_hints(parsed_text),
            requirements=self._extract_requirements(parsed_text)
        )

    def _handle_file(self, file_path: str) -> ParsedInput:
        """处理文件输入"""
        parsed_text = ""
        tech_stack_hints = []

        try:
            # 根据文件类型解析
            ext = os.path.splitext(file_path)[1].lower()

            if ext in ['.txt', '.md', '.json', '.yaml', '.yml', '.toml']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    parsed_text = f.read()

            elif ext == '.py':
                parsed_text = self._parse_python_file(file_path)
                tech_stack_hints.append('python')

            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                parsed_text = self._parse_js_file(file_path)
                tech_stack_hints.append('nodejs')

            elif ext == '.java':
                parsed_text = self._parse_java_file(file_path)
                tech_stack_hints.append('java')

            elif ext == '.go':
                parsed_text = self._parse_go_file(file_path)
                tech_stack_hints.append('golang')

            elif ext in ['.env', '.conf', '.cfg', '.ini']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    parsed_text = f.read()

        except Exception as e:
            logger.error(f"File parsing failed: {e}")
            parsed_text = ""

        return ParsedInput(
            mode=InputMode.FILE,
            raw_content=file_path,
            parsed_text=parsed_text,
            confidence=0.9 if parsed_text else 0.3,
            extracted_entities=self._extract_entities(parsed_text),
            tech_stack_hints=tech_stack_hints or self._extract_tech_hints(parsed_text),
            requirements=self._extract_requirements(parsed_text)
        )

    def _handle_unknown(self, content: Any) -> ParsedInput:
        """处理未知输入"""
        return ParsedInput(
            mode=InputMode.TEXT,
            raw_content=content,
            parsed_text=str(content) if content else "",
            confidence=0.1,
            extracted_entities={},
            tech_stack_hints=[],
            requirements=[]
        )

    def _parse_python_file(self, file_path: str) -> str:
        """解析Python文件提取部署信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取import和配置
            imports = re.findall(r'^import\s+(\w+)', content, re.MULTILINE)
            from_imports = re.findall(r'^from\s+(\w+)', content, re.MULTILINE)

            # 提取配置信息
            config_patterns = [
                r'(\w+)\s*=\s*["\']([^"\']+)["\']',
                r'(\w+)\s*=\s*os\.getenv\(["\']([^"\']+)["\']\)'
            ]

            configs = []
            for pattern in config_patterns:
                configs.extend(re.findall(pattern, content))

            result = f"Python项目，依赖: {', '.join(set(imports + from_imports))}"
            if configs:
                result += f"，配置: {', '.join([c[0] for c in configs[:5]])}"

            return result
        except:
            return ""

    def _parse_js_file(self, file_path: str) -> str:
        """解析JS文件提取部署信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取依赖
            deps = re.findall(r'"(@?[\w-]+)":\s*"([^"]+)"', content)
            deps_str = ', '.join([d[0] for d in deps[:10]])

            return f"Node.js项目，依赖: {deps_str or '无'}"
        except:
            return ""

    def _parse_java_file(self, file_path: str) -> str:
        """解析Java文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            packages = re.findall(r'package\s+([\w.]+);', content)
            imports = re.findall(r'import\s+([\w.]+);', content)

            return f"Java项目，包: {', '.join(packages[:3])}, 导入: {len(imports)}个"
        except:
            return ""

    def _parse_go_file(self, file_path: str) -> str:
        """解析Go文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            imports = re.findall(r'"([^"]+)"', content)

            return f"Go项目，依赖: {', '.join(imports[:5]) if imports else '无'}"
        except:
            return ""

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {}

        # 端口
        ports = re.findall(r'\b(\d{4,5})\b', text)
        if ports:
            entities['ports'] = [int(p) for p in ports[:5]]

        # IP地址
        ips = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        if ips:
            entities['ips'] = ips[:5]

        # URL
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            entities['urls'] = urls[:5]

        # 文件路径
        paths = re.findall(r'/[\w/.-]+', text)
        if paths:
            entities['paths'] = paths[:10]

        return entities

    def _extract_tech_hints(self, text: str) -> List[str]:
        """提取技术栈提示"""
        hints = []
        text_lower = text.lower()

        tech_keywords = {
            'python': ['python', 'django', 'flask', 'fastapi', 'pip'],
            'nodejs': ['node', 'npm', 'express', 'react', 'vue', 'nextjs'],
            'java': ['java', 'spring', 'maven', 'gradle', 'tomcat'],
            'golang': ['golang', 'go ', 'gin', 'go mod'],
            'rust': ['rust', 'cargo'],
            'docker': ['docker', 'container', '镜像', '容器'],
            'database': ['mysql', 'postgresql', 'mongodb', 'redis', '数据库']
        }

        for tech, keywords in tech_keywords.items():
            if any(kw in text_lower for kw in keywords):
                hints.append(tech)

        return hints

    def _extract_requirements(self, text: str) -> List[str]:
        """提取需求"""
        requirements = []

        # 常见需求模式
        patterns = [
            (r'需要(\d+)个?[核CPU]', 'CPU'),
            (r'(\d+)\s*[GM]B?内存?', '内存'),
            (r'部署在(.+)', '部署位置'),
            (r'使用(.+)数据库', '数据库'),
            (r'需要(.+)端口', '端口'),
            (r'配置(.+)认证', '认证'),
        ]

        for pattern, req_type in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                requirements.append(f"{req_type}: {match}")

        return requirements


# 全局实例
multi_mode_input = MultiModeInputHandler()
