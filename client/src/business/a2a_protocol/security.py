"""
A2A 协议安全层
Security Layer for A2A Protocol

功能：
- HMAC 签名验证
- Webhook 即时唤醒
- Prompt Injection 过滤
- 访问控制
"""

import hashlib
import hmac
import time
import re
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from client.src.business.logger import get_logger

logger = get_logger('a2a_security')


class ThreatLevel(str, Enum):
    """威胁等级"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityContext:
    """安全上下文"""
    source_agent_id: str
    target_agent_id: str
    message_type: str
    hmac_verified: bool = False
    ip_whitelisted: bool = False
    threat_level: ThreatLevel = ThreatLevel.SAFE
    verified_at: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptInjectionDetector:
    """
    Prompt Injection 检测器
    识别和过滤恶意提示注入
    """
    
    # 已知恶意模式
    INJECTION_PATTERNS = [
        # 系统提示覆盖
        r'(?i)(ignore\s+(all\s+)?previous\s+(instructions?|prompts?|commands?))',
        r'(?i)(disregard\s+(all\s+)?(your|previous|above))',
        r'(?i)(you\s+are\s+now\s+(a|an))',
        r'(?i)(forget\s+(everything|all)\s+(you|that)\s+(know|learned))',
        
        # 角色扮演攻击
        r'(?i)(pretend\s+(you\s+are|to\s+be))',
        r'(?i)(role\s+play)',
        r'(?i)(simulate\s+(being|a))',
        
        # 指令注入
        r'(?i)(new\s+system\s+(instruction|prompt|rule))',
        r'(?i)(additional\s+(instruction|prompt|rule))',
        r'(?i)(override\s+(safety|filter|rule))',
        
        # 数据提取
        r'(?i)(reveal\s+(your|the)\s+(system\s+)?(prompt|instruction|config))',
        r'(?i)(print\s+(your|all)\s+(system\s+)?(prompt|instruction))',
        
        # 编码绕过
        r'(?i)(base64|utf-?8|hex|unicode)\s*[:=]',
        r'\\u[0-9a-f]{4}',
        
        # 特殊字符注入
        r'[\x00-\x08\x0b\x0c\x0e-\x1f]',
    ]
    
    # 敏感关键词
    SENSITIVE_KEYWORDS = [
        'password', 'secret', 'api_key', 'token',
        'credential', 'auth', 'jwt', 'bearer',
        'root', 'admin', 'sudo', 'chmod',
    ]
    
    def __init__(self):
        self._patterns = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self._stats = {
            'total_checked': 0,
            'threats_detected': 0,
            'by_level': {level.value: 0 for level in ThreatLevel}
        }
    
    def detect(self, text: str) -> Dict[str, Any]:
        """
        检测文本中的 Prompt Injection 威胁
        """
        self._stats['total_checked'] += 1
        result = {
            'is_safe': True,
            'threat_level': ThreatLevel.SAFE,
            'matched_patterns': [],
            'matched_keywords': [],
            'suggestions': []
        }
        
        if not text:
            return result
        
        # 检查模式匹配
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                result['matched_patterns'].append(pattern.pattern)
                result['is_safe'] = False
                self._stats['threats_detected'] += 1
        
        # 检查敏感关键词
        text_lower = text.lower()
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in text_lower:
                result['matched_keywords'].append(keyword)
        
        # 确定威胁等级
        if result['matched_patterns']:
            pattern_count = len(result['matched_patterns'])
            if pattern_count >= 3:
                result['threat_level'] = ThreatLevel.CRITICAL
                result['suggestions'].append("多条恶意模式匹配，建议直接拒绝")
            elif pattern_count >= 2:
                result['threat_level'] = ThreatLevel.HIGH
                result['suggestions'].append("多次恶意模式匹配，需要人工审核")
            else:
                result['threat_level'] = ThreatLevel.MEDIUM
                result['suggestions'].append("检测到可疑模式，进行内容清理")
            
            self._stats['by_level'][result['threat_level'].value] += 1
        
        return result
    
    def sanitize(self, text: str) -> str:
        """清理文本中的可疑内容"""
        sanitized = text
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        return sanitized.strip()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取检测统计"""
        return self._stats.copy()


class WebhookValidator:
    """
    Webhook 验证器 - HMAC 签名验证
    用于即时唤醒机制
    """
    
    def __init__(self, secret_key: str, timestamp_tolerance_ms: int = 300000):
        """
        Args:
            secret_key: HMAC 密钥
            timestamp_tolerance_ms: 时间戳容差（毫秒），默认 5 分钟
        """
        self._secret_key = secret_key
        self._timestamp_tolerance_ms = timestamp_tolerance_ms
        self._recent_signatures: Dict[str, int] = {}  # 防止重放攻击
    
    def generate_signature(self, payload: str, timestamp: Optional[int] = None) -> str:
        """生成 HMAC 签名"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        
        message = f"{timestamp}.{payload}"
        signature = hmac.new(
            self._secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}.{signature}"
    
    def verify_signature(self, signature: str, payload: str) -> bool:
        """验证 HMAC 签名"""
        try:
            parts = signature.split('.')
            if len(parts) != 2:
                logger.warning("Invalid signature format")
                return False
            
            timestamp_str, sig = parts
            timestamp = int(timestamp_str)
            
            # 检查时间戳
            current_time = int(time.time() * 1000)
            if abs(current_time - timestamp) > self._timestamp_tolerance_ms:
                logger.warning(f"Timestamp out of range: {timestamp}")
                return False
            
            # 检查重放攻击
            if signature in self._recent_signatures:
                logger.warning("Replay attack detected")
                return False
            
            # 验证签名
            expected_signature = hmac.new(
                self._secret_key.encode('utf-8'),
                f"{timestamp}.{payload}".encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(sig, expected_signature):
                logger.warning("Signature mismatch")
                return False
            
            # 记录签名
            self._recent_signatures[signature] = timestamp
            self._cleanup_expired_signatures()
            
            return True
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def _cleanup_expired_signatures(self):
        """清理过期的签名记录"""
        current_time = int(time.time() * 1000)
        expired = [
            sig for sig, ts in self._recent_signatures.items()
            if current_time - ts > self._timestamp_tolerance_ms * 2
        ]
        for sig in expired:
            del self._recent_signatures[sig]


class SecurityFilter:
    """
    A2A 协议安全过滤器
    整合 HMAC 验证、Prompt Injection 检测、访问控制
    """
    
    def __init__(self, hmac_secret: str, allowed_agents: Optional[List[str]] = None):
        """
        Args:
            hmac_secret: HMAC 密钥
            allowed_agents: 允许的 Agent ID 列表，None 表示允许所有
        """
        self._webhook_validator = WebhookValidator(hmac_secret)
        self._injection_detector = PromptInjectionDetector()
        self._allowed_agents = set(allowed_agents) if allowed_agents else None
    
    def verify_instant_wake(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证即时唤醒请求"""
        try:
            payload_str = str(payload)
            return self._webhook_validator.verify_signature(signature, payload_str)
        except Exception as e:
            logger.error(f"Instant wake verification failed: {e}")
            return False
    
    def check_agent_access(self, source_id: str, target_id: str) -> bool:
        """检查 Agent 访问权限"""
        if self._allowed_agents is None:
            return True
        
        return source_id in self._allowed_agents and target_id in self._allowed_agents
    
    def filter_message(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """过滤消息内容"""
        payload = message.get('payload', {})
        task = payload.get('task', {})
        
        if isinstance(task, dict):
            description = task.get('description', '')
            input_data = task.get('input_data', {})
            
            if description:
                result = self._injection_detector.detect(description)
                if not result['is_safe']:
                    return False, f"Threat in task description: {result['threat_level'].value}"
            
            if isinstance(input_data, dict):
                for key, value in input_data.items():
                    if isinstance(value, str):
                        result = self._injection_detector.detect(value)
                        if not result['is_safe']:
                            return False, f"Threat in input '{key}': {result['threat_level'].value}"
        
        session_context = payload.get('session_context')
        if session_context and isinstance(session_context, dict):
            injected = session_context.get('injected_context', {})
            if injected:
                for key, value in injected.items():
                    if isinstance(value, str):
                        result = self._injection_detector.detect(value)
                        if not result['is_safe']:
                            return False, f"Threat in injected context '{key}'"
        
        return True, None
    
    def sanitize_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """清理消息中的可疑内容"""
        import copy
        sanitized = copy.deepcopy(message)
        payload = sanitized.get('payload', {})
        task = payload.get('task', {})
        
        if isinstance(task, dict):
            if task.get('description'):
                task['description'] = self._injection_detector.sanitize(task['description'])
        
        return sanitized
