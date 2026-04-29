"""
语义解析器 - 解析AI响应生成UI描述

负责从AI响应中提取结构化的UI描述信息，支持：
1. 解析AI返回的JSON格式UI描述
2. 从自然语言中识别需求澄清请求
3. 解析命令/工具调用
4. 提取Markdown内容
"""

import json
import re
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger

from .ui_descriptor import (
    UIResponse, UIComponent, ClarificationRequest,
    ControlType, ActionType, FormField, ActionButton,
    ClarificationOption, ValidationRule
)


class SemanticParser:
    """
    语义解析器
    
    核心功能：
    1. 从AI响应中提取UI描述（JSON格式）
    2. 解析需求澄清请求
    3. 识别工具调用命令
    4. 提取纯文本内容
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SemanticParser")
        
        # 正则表达式模式
        self._json_pattern = re.compile(
            r'\{\s*"ui".*?\}',
            re.DOTALL | re.MULTILINE
        )
        self._json_block_pattern = re.compile(
            r'```(?:json)?\s*(\{.*?\})\s*```',
            re.DOTALL
        )
        self._clarification_pattern = re.compile(
            r'((?:你希望|你需要|请问|是否|选择|确认|哪个|什么|如何|哪里).*?\?)',
            re.IGNORECASE
        )
        self._command_pattern = re.compile(
            r'(/\w+)(?:\s+(.+))?'
        )
    
    def parse(self, ai_response: str) -> UIResponse:
        """
        解析AI响应，提取UI描述
        
        Args:
            ai_response: AI返回的响应文本
            
        Returns:
            UIResponse对象，包含内容、组件和澄清请求
        """
        response = UIResponse()
        
        # 1. 提取纯文本内容（去除JSON块）
        content = self._extract_text_content(ai_response)
        response.content = content
        
        # 2. 解析JSON格式的UI描述
        ui_components = self._parse_json_ui(ai_response)
        response.components.extend(ui_components)
        
        # 3. 识别需求澄清请求
        clarifications = self._parse_clarifications(ai_response)
        response.clarifications.extend(clarifications)
        
        # 4. 检查是否需要用户输入
        response.requires_input = len(clarifications) > 0 or len(ui_components) > 0
        
        self._logger.debug(f"解析完成: {len(response.components)} 个组件, {len(response.clarifications)} 个澄清请求")
        
        return response
    
    def _extract_text_content(self, text: str) -> str:
        """提取纯文本内容，去除代码块和JSON"""
        # 移除代码块
        result = re.sub(r'```[\s\S]*?```', '', text)
        # 移除内联代码
        result = re.sub(r'`([^`]+)`', r'\1', result)
        # 移除JSON对象
        result = re.sub(r'\{\s*"ui".*?\}', '', result, flags=re.DOTALL)
        return result.strip()
    
    def _parse_json_ui(self, text: str) -> List[UIComponent]:
        """解析JSON格式的UI描述"""
        components = []
        
        # 尝试从代码块中提取JSON
        matches = self._json_block_pattern.findall(text)
        if matches:
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict):
                        component = self._parse_ui_component(data)
                        if component:
                            components.append(component)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"JSON解析失败: {e}")
        
        # 如果代码块中没有，尝试直接匹配JSON对象
        if not components:
            json_match = self._json_pattern.search(text)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    if isinstance(data, dict):
                        component = self._parse_ui_component(data)
                        if component:
                            components.append(component)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"JSON解析失败: {e}")
        
        return components
    
    def _parse_ui_component(self, data: Dict[str, Any]) -> Optional[UIComponent]:
        """解析单个UI组件"""
        try:
            ui_data = data.get("ui", data)
            
            if "id" not in ui_data or "type" not in ui_data:
                return None
            
            return UIComponent.from_dict(ui_data)
        except Exception as e:
            self._logger.error(f"解析UI组件失败: {e}")
            return None
    
    def _parse_clarifications(self, text: str) -> List[ClarificationRequest]:
        """识别需求澄清请求"""
        clarifications = []
        
        # 尝试从JSON中提取澄清请求
        try:
            matches = self._json_block_pattern.findall(text)
            for match in matches:
                data = json.loads(match)
                if "clarifications" in data:
                    for clar_data in data["clarifications"]:
                        clar = ClarificationRequest.from_dict(clar_data)
                        clarifications.append(clar)
        except Exception:
            pass
        
        # 如果JSON中没有，尝试从自然语言中识别
        if not clarifications:
            questions = self._clarification_pattern.findall(text)
            for question in questions[:3]:  # 最多提取3个问题
                if len(question) > 5:  # 过滤过短的问题
                    options = self._extract_options_from_text(text, question)
                    clar = ClarificationRequest(
                        id=f"clar_{hash(question)}",
                        question=question.strip(),
                        options=options,
                        required=True,
                        allow_custom=True
                    )
                    clarifications.append(clar)
        
        return clarifications
    
    def _extract_options_from_text(self, text: str, question: str) -> List[ClarificationOption]:
        """从文本中提取选项"""
        options = []
        
        # 查找有序列表
        list_pattern = re.compile(r'([\d一二三四五六七八九十]+[\.\uff0e、])\s*([^\n]+)')
        matches = list_pattern.findall(text)
        if matches:
            for i, (num, label) in enumerate(matches[:6]):
                options.append(ClarificationOption(
                    id=f"opt_{i}",
                    label=label.strip(),
                    value=label.strip(),
                    is_default=(i == 0)
                ))
        
        # 查找无序列表
        if not options:
            bullet_pattern = re.compile(r'[-•●*]\s*([^\n]+)')
            matches = bullet_pattern.findall(text)
            if matches:
                for i, label in enumerate(matches[:6]):
                    options.append(ClarificationOption(
                        id=f"opt_{i}",
                        label=label.strip(),
                        value=label.strip(),
                        is_default=(i == 0)
                    ))
        
        # 如果没有找到列表，尝试查找"是/否"选项
        if not options and ("是否" in question or "确认" in question):
            options = [
                ClarificationOption(id="opt_yes", label="是", value=True, is_default=True),
                ClarificationOption(id="opt_no", label="否", value=False)
            ]
        
        return options
    
    def parse_command(self, input_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        解析用户输入中的命令
        
        Args:
            input_text: 用户输入文本
            
        Returns:
            (命令名, 参数) 或 None
        """
        if not input_text.startswith("/"):
            return None
        
        match = self._command_pattern.match(input_text.strip())
        if not match:
            return None
        
        command_name = match.group(1)
        params_str = match.group(2)
        
        params = self._parse_parameters(params_str)
        
        return (command_name, params)
    
    def _parse_parameters(self, params_str: Optional[str]) -> Dict[str, Any]:
        """解析命令参数"""
        params = {}
        
        if not params_str:
            return params
        
        parts = params_str.split()
        
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
            else:
                params[part] = True
        
        return params
    
    def parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析工具调用
        
        支持格式：
        1. JSON格式：{"tool_name": "...", "params": {...}}
        2. 自然语言："使用工具[工具名]，参数：..."
        
        Returns:
            工具调用信息 {"tool_name": "...", "params": {...}}
        """
        # 尝试解析JSON格式
        matches = self._json_block_pattern.findall(text)
        for match in matches:
            try:
                data = json.loads(match)
                if "tool_name" in data or "name" in data:
                    return {
                        "tool_name": data.get("tool_name") or data.get("name"),
                        "params": data.get("params", data.get("arguments", {}))
                    }
            except json.JSONDecodeError:
                pass
        
        # 尝试自然语言模式
        tool_pattern = re.compile(
            r'(?:使用|调用|执行)\s*(?:工具)?\[?(\w+)\]?',
            re.IGNORECASE
        )
        match = tool_pattern.search(text)
        if match:
            tool_name = match.group(1)
            return {
                "tool_name": tool_name,
                "params": {}
            }
        
        return None
    
    def parse_markdown(self, text: str) -> str:
        """
        解析Markdown内容，提取纯文本
        
        Args:
            text: 包含Markdown的文本
            
        Returns:
            清理后的文本（保留基本格式提示）
        """
        # 移除标题标记
        result = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # 移除粗体/斜体标记
        result = re.sub(r'\*\*(.+?)\*\*', r'\1', result)
        result = re.sub(r'\*(.+?)\*', r'\1', result)
        # 移除链接标记
        result = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', result)
        # 移除图片标记
        result = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', result)
        # 移除表格
        result = re.sub(r'\|.*\|\n\|[-:]+\|', '', result)
        # 移除分隔线
        result = re.sub(r'^[-*_]{3,}$', '', result, flags=re.MULTILINE)
        
        return result.strip()
    
    def extract_key_points(self, text: str, max_points: int = 5) -> List[str]:
        """
        从文本中提取关键点
        
        Args:
            text: 输入文本
            max_points: 最大提取数量
            
        Returns:
            关键点列表
        """
        points = []
        
        # 查找列表项
        list_pattern = re.compile(r'^[\d一二三四五六七八九十]+[\.\uff0e、]\s+(.+)', re.MULTILINE)
        matches = list_pattern.findall(text)
        points.extend(matches[:max_points])
        
        # 如果列表不够，查找加粗文本
        if len(points) < max_points:
            bold_pattern = re.compile(r'\*\*(.+?)\*\*')
            bold_matches = bold_pattern.findall(text)
            for match in bold_matches[:max_points - len(points)]:
                if match not in points:
                    points.append(match)
        
        # 如果还不够，查找带符号的要点
        if len(points) < max_points:
            bullet_pattern = re.compile(r'^[-•●*]\s+(.+)', re.MULTILINE)
            bullet_matches = bullet_pattern.findall(text)
            for match in bullet_matches[:max_points - len(points)]:
                if match not in points:
                    points.append(match)
        
        return points
    
    def is_ui_response(self, text: str) -> bool:
        """判断响应是否包含UI描述"""
        return self._json_block_pattern.search(text) is not None or \
               self._json_pattern.search(text) is not None
    
    def is_clarification(self, text: str) -> bool:
        """判断响应是否包含澄清请求"""
        return len(self._parse_clarifications(text)) > 0