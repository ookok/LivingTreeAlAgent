"""
工具函数模块
=============

Author: Hermes Desktop Team
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional


def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    import uuid
    uid = str(uuid.uuid4())
    return f"{prefix}{uid}" if prefix else uid


def hash_text(text: str) -> str:
    """文本哈希"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def normalize_text(text: str) -> str:
    """文本标准化"""
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 转为小写
    text = text.lower()
    # 移除特殊字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    return text.strip()


def extract_numbers(text: str) -> List[float]:
    """提取数字"""
    pattern = r'-?\d+(?:\.\d+)?'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


def extract_keywords(text: str, min_length: int = 2) -> List[str]:
    """提取关键词"""
    # 简单的中英文分词
    chinese = re.findall(r'[\u4e00-\u9fff]+', text)
    english = re.findall(r'[a-zA-Z]+(?:\'[a-zA-Z]+)?', text)

    keywords = []
    for word in chinese + english:
        if len(word) >= min_length:
            keywords.append(word.lower())

    return keywords


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """深度合并字典"""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """扁平化字典"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def safe_get(d: Dict, path: str, default: Any = None) -> Any:
    """安全获取嵌套字典值"""
    keys = path.split('.')
    current = d

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current


def to_snake_case(text: str) -> str:
    """转为蛇形命名"""
    text = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', text)
    return text.lower()


def to_camel_case(text: str) -> str:
    """转为驼峰命名"""
    components = text.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


__all__ = [
    'generate_id', 'hash_text', 'normalize_text',
    'extract_numbers', 'extract_keywords', 'truncate_text',
    'format_size', 'deep_merge', 'flatten_dict',
    'safe_get', 'to_snake_case', 'to_camel_case'
]
