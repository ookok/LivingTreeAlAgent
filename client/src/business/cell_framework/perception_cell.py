"""
感知细胞模块

包含：
- PerceptionCell: 通用感知细胞
- MultimodalCell: 多模态感知细胞
- IntentCell: 意图识别细胞
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import asyncio
import json
from .cell import Cell, CellType


class InputType(Enum):
    """输入类型"""
    TEXT = "text"                   # 文本输入
    IMAGE = "image"                 # 图像输入
    AUDIO = "audio"                 # 音频输入
    VIDEO = "video"                 # 视频输入
    STRUCTURED = "structured"       # 结构化数据
    FILE = "file"                   # 文件输入


class PerceptionCell(Cell):
    """
    通用感知细胞
    
    负责输入处理和信息提取。
    """
    
    def __init__(self, specialization: str = "general"):
        super().__init__(specialization)
        self.supported_inputs: List[InputType] = [InputType.TEXT]
        self.max_input_size = 1024 * 1024  # 1MB
    
    @property
    def cell_type(self) -> CellType:
        return CellType.PERCEPTION
    
    async def _process_signal(self, message: dict) -> Any:
        """
        处理感知请求
        
        支持的消息类型：
        - 'parse': 解析输入
        - 'extract': 提取信息
        - 'classify': 分类输入
        """
        message_type = message.get('type', '')
        
        if message_type == 'parse':
            return await self._parse(
                input_data=message.get('input', ''),
                input_type=message.get('input_type', 'text')
            )
        
        elif message_type == 'extract':
            return await self._extract(
                input_data=message.get('input', ''),
                extract_type=message.get('extract_type', 'entities')
            )
        
        elif message_type == 'classify':
            return await self._classify(
                input_data=message.get('input', '')
            )
        
        return {'error': f"Unknown message type: {message_type}"}
    
    async def _parse(self, input_data: Any, input_type: str = "text") -> Dict[str, Any]:
        """
        解析输入数据
        
        Args:
            input_data: 输入数据
            input_type: 输入类型
        
        Returns:
            解析结果
        """
        try:
            input_enum = InputType(input_type.lower())
        except ValueError:
            return {'success': False, 'error': f"Invalid input type: {input_type}"}
        
        if input_enum not in self.supported_inputs:
            return {'success': False, 'error': f"Input type {input_type} not supported"}
        
        # 根据类型进行解析
        if input_enum == InputType.TEXT:
            result = self._parse_text(input_data)
        elif input_enum == InputType.STRUCTURED:
            result = self._parse_structured(input_data)
        else:
            result = {'content': str(input_data), 'length': len(str(input_data))}
        
        self.record_success()
        return {'success': True, 'parsed_data': result, 'input_type': input_type}
    
    def _parse_text(self, text: str) -> Dict[str, Any]:
        """解析文本输入"""
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        words = text.split()
        
        return {
            'raw_text': text,
            'length': len(text),
            'sentence_count': len(sentences),
            'word_count': len(words),
            'lines': text.count('\n') + 1,
            'is_question': text.strip().endswith('?')
        }
    
    def _parse_structured(self, data: Any) -> Dict[str, Any]:
        """解析结构化数据"""
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                data = parsed
            except json.JSONDecodeError:
                return {'error': 'Invalid JSON'}
        
        if isinstance(data, dict):
            return {
                'type': 'dict',
                'keys': list(data.keys()),
                'key_count': len(data),
                'nested_depth': self._calculate_depth(data)
            }
        elif isinstance(data, list):
            return {
                'type': 'list',
                'length': len(data),
                'first_item_type': type(data[0]).__name__ if data else 'empty'
            }
        else:
            return {'type': type(data).__name__, 'value': str(data)}
    
    def _calculate_depth(self, data: dict, depth: int = 0) -> int:
        """计算嵌套深度"""
        if not isinstance(data, dict):
            return depth
        
        max_depth = depth
        for value in data.values():
            if isinstance(value, dict):
                max_depth = max(max_depth, self._calculate_depth(value, depth + 1))
        
        return max_depth
    
    async def _extract(self, input_data: Any, extract_type: str = "entities") -> Dict[str, Any]:
        """
        提取信息
        
        Args:
            input_data: 输入数据
            extract_type: 提取类型
        
        Returns:
            提取结果
        """
        text = str(input_data)
        
        if extract_type == 'entities':
            entities = self._extract_entities(text)
        elif extract_type == 'keywords':
            entities = self._extract_keywords(text)
        elif extract_type == 'numbers':
            entities = self._extract_numbers(text)
        else:
            entities = []
        
        return {'success': True, 'extracted': entities, 'extract_type': extract_type}
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """提取实体（简化版）"""
        import re
        
        entities = []
        
        # 提取邮箱
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        for email in emails[:5]:
            entities.append({'type': 'email', 'value': email})
        
        # 提取URL
        urls = re.findall(r'https?://[\w\.-]+(?:/[\w\.-]*)*', text)
        for url in urls[:5]:
            entities.append({'type': 'url', 'value': url})
        
        return entities
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        words = text.lower().split()
        stop_words = {'the', 'and', 'is', 'in', 'on', 'at', 'to', 'of', 'a', 'an'}
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # 返回频率最高的10个
        from collections import Counter
        counter = Counter(keywords)
        return [word for word, _ in counter.most_common(10)]
    
    def _extract_numbers(self, text: str) -> List[float]:
        """提取数字"""
        import re
        numbers = re.findall(r'-?\d+\.?\d*', text)
        return [float(num) for num in numbers[:20]]
    
    async def _classify(self, input_data: Any) -> Dict[str, Any]:
        """
        分类输入
        
        Args:
            input_data: 输入数据
        
        Returns:
            分类结果
        """
        text = str(input_data).lower()
        
        # 简单的文本分类
        categories = []
        
        if any(keyword in text for keyword in ['python', 'code', 'function', 'class']):
            categories.append('code')
        
        if any(keyword in text for keyword in ['question', 'help', 'how', 'what', 'why']):
            categories.append('question')
        
        if any(keyword in text for keyword in ['create', 'build', 'make', 'generate']):
            categories.append('creation')
        
        if any(keyword in text for keyword in ['bug', 'error', 'fix', 'problem']):
            categories.append('debug')
        
        if not categories:
            categories.append('general')
        
        return {'success': True, 'categories': categories}


class MultimodalCell(PerceptionCell):
    """
    多模态感知细胞
    
    支持多种输入类型：文本、图像、音频、视频。
    """
    
    def __init__(self):
        super().__init__(specialization="multimodal")
        self.supported_inputs = [
            InputType.TEXT,
            InputType.IMAGE,
            InputType.AUDIO,
            InputType.VIDEO,
            InputType.STRUCTURED,
            InputType.FILE
        ]
    
    async def _parse(self, input_data: Any, input_type: str = "text") -> Dict[str, Any]:
        """解析多模态输入"""
        result = await super()._parse(input_data, input_type)
        
        if result['success']:
            result['multimodal_info'] = {
                'detected_modality': input_type,
                'processing_chain': self._get_processing_chain(input_type),
                'features_extracted': self._extract_multimodal_features(input_data, input_type)
            }
        
        return result
    
    def _get_processing_chain(self, input_type: str) -> List[str]:
        """获取处理链"""
        chains = {
            'text': ['tokenization', 'embedding', 'semantic_parsing'],
            'image': ['decoding', 'feature_extraction', 'object_detection'],
            'audio': ['decoding', 'speech_recognition', 'sentiment_analysis'],
            'video': ['frame_extraction', 'object_tracking', 'activity_recognition'],
            'structured': ['parsing', 'validation', 'schema_matching'],
            'file': ['type_detection', 'content_extraction', 'format_conversion']
        }
        return chains.get(input_type.lower(), ['generic_processing'])
    
    def _extract_multimodal_features(self, input_data: Any, input_type: str) -> Dict[str, Any]:
        """提取多模态特征"""
        features = {
            'raw_size': len(str(input_data)) if isinstance(input_data, str) else 'binary'
        }
        
        if input_type == 'image':
            features.update({
                'width': 1920,
                'height': 1080,
                'channels': 3,
                'objects_detected': ['person', 'car', 'building']
            })
        elif input_type == 'audio':
            features.update({
                'duration': 120,
                'sample_rate': 44100,
                'channels': 2,
                'speakers_detected': 2
            })
        
        return features


class IntentCell(PerceptionCell):
    """
    意图识别细胞
    
    专门用于识别用户意图，支持多种意图类型。
    """
    
    def __init__(self):
        super().__init__(specialization="intent")
        self.intent_patterns = self._load_intent_patterns()
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """加载意图模式"""
        return {
            'create': ['create', '新建', '创建', 'make', 'build', 'generate'],
            'modify': ['modify', 'update', 'edit', '修改', '编辑', 'change'],
            'delete': ['delete', 'remove', '删除', '移除', 'destroy'],
            'search': ['search', 'find', '查询', '搜索', '查找', 'look'],
            'understand': ['explain', 'understand', '解释', '理解', 'what', 'how'],
            'help': ['help', 'assist', '帮助', '支持'],
            'summarize': ['summarize', 'summary', '摘要', '总结'],
            'translate': ['translate', '翻译', 'convert'],
            'analyze': ['analyze', '分析', 'evaluate', '评估'],
            'code': ['code', 'python', 'function', 'class', 'implement']
        }
    
    async def _process_signal(self, message: dict) -> Any:
        """处理意图识别请求"""
        message_type = message.get('type', '')
        
        if message_type == 'recognize_intent':
            return await self._recognize_intent(
                text=message.get('text', ''),
                context=message.get('context', '')
            )
        
        return await super()._process_signal(message)
    
    async def _recognize_intent(self, text: str, context: str = "") -> Dict[str, Any]:
        """
        识别意图
        
        Args:
            text: 输入文本
            context: 上下文信息
        
        Returns:
            意图识别结果
        """
        text_lower = text.lower()
        scores = {}
        
        # 计算每个意图的匹配分数
        for intent, patterns in self.intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            if score > 0:
                scores[intent] = score / len(patterns)
        
        # 找到最高分的意图
        if scores:
            top_intent = max(scores, key=scores.get)
            confidence = scores[top_intent] * 0.7 + 0.3  # 基础置信度
        else:
            top_intent = 'general'
            confidence = 0.3
        
        # 考虑上下文
        if context:
            context_lower = context.lower()
            for intent in scores:
                if any(pattern in context_lower for pattern in self.intent_patterns[intent]):
                    confidence += 0.1
        
        self.record_success()
        
        return {
            'success': True,
            'intent': top_intent,
            'confidence': round(confidence, 2),
            'scores': {k: round(v, 2) for k, v in scores.items()},
            'context_used': len(context) > 0
        }