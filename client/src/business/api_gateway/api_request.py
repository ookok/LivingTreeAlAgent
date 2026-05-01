"""
API请求封装 - API Request

功能：
1. 请求数据封装
2. 参数验证
3. 请求上下文管理
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class APIRequest:
    """API请求封装"""
    endpoint: str
    method: str = "POST"
    params: Dict = None
    headers: Dict = None
    body: Any = None
    timestamp: float = None
    request_id: str = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.headers is None:
            self.headers = {}
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.request_id is None:
            self.request_id = self._generate_request_id()
    
    def _generate_request_id(self) -> str:
        """生成请求ID"""
        return f"req_{int(self.timestamp * 1000)}_{hash(self.endpoint) % 1000}"
    
    def validate(self) -> bool:
        """验证请求"""
        if not self.endpoint:
            return False
        if not isinstance(self.params, dict):
            return False
        return True
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'endpoint': self.endpoint,
            'method': self.method,
            'params': self.params,
            'headers': self.headers,
            'timestamp': self.timestamp,
            'request_id': self.request_id
        }