"""
降级管理器

当核心服务不可用时，提供优雅的降级方案
"""

import logging
from typing import Dict, Optional, Callable, Any
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class FallbackManager:
    """
    降级管理器
    管理系统的降级方案
    """
    
    def __init__(self):
        self._fallback_handlers: Dict[str, Callable] = {}
        self._is_fallback_active = False
        self._fallback_reason = ""
    
    def register_fallback_handler(self, service: str, handler: Callable):
        """
        注册降级处理器
        
        Args:
            service: 服务名称
            handler: 降级处理函数
        """
        self._fallback_handlers[service] = handler
    
    def is_service_available(self, service: str) -> bool:
        """
        检查服务是否可用
        
        Args:
            service: 服务名称
            
        Returns:
            bool: 服务是否可用
        """
        # 这里可以添加具体的服务可用性检查逻辑
        # 例如检查网络连接、服务响应等
        return True
    
    def fallback(self, service: str, reason: str) -> Optional[Any]:
        """
        执行降级处理
        
        Args:
            service: 服务名称
            reason: 降级原因
            
        Returns:
            Optional[Any]: 降级处理结果
        """
        if service in self._fallback_handlers:
            try:
                self._is_fallback_active = True
                self._fallback_reason = reason
                logger.warning(f"Fallback activated for service {service}: {reason}")
                return self._fallback_handlers[service]()
            except Exception as e:
                logger.error(f"Failed to execute fallback for service {service}: {e}")
                return None
        else:
            logger.error(f"No fallback handler registered for service {service}")
            return None
    
    def create_fallback_ui(self, reason: str) -> QWidget:
        """
        创建降级 UI
        
        Args:
            reason: 降级原因
            
        Returns:
            QWidget: 降级 UI 组件
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 添加降级信息
        title_label = QLabel("服务不可用")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        reason_label = QLabel(f"原因: {reason}")
        reason_label.setStyleSheet("color: #666;")
        layout.addWidget(reason_label)
        
        # 添加降级说明
        info_label = QLabel("系统已切换到离线模式，部分功能可能受限")
        info_label.setStyleSheet("margin-top: 10px;")
        layout.addWidget(info_label)
        
        # 添加重试按钮
        retry_button = QPushButton("重试连接")
        retry_button.setStyleSheet("margin-top: 20px;")
        layout.addWidget(retry_button)
        
        return widget
    
    def is_fallback_active(self) -> bool:
        """
        检查是否处于降级模式
        
        Returns:
            bool: 是否处于降级模式
        """
        return self._is_fallback_active
    
    def get_fallback_reason(self) -> str:
        """
        获取降级原因
        
        Returns:
            str: 降级原因
        """
        return self._fallback_reason
    
    def reset_fallback(self):
        """
        重置降级状态
        """
        self._is_fallback_active = False
        self._fallback_reason = ""
