"""
感知层（Perception Layer）：让AI"看见"工作现场

核心功能：
1. 多模态信号捕获：解析CAD图纸、监测数据Excel、现状照片、地图截图
2. 操作行为埋点：记录用户的每一个微交互
"""

import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

@dataclass
class UserAction:
    action_id: str
    action_type: str
    timestamp: float
    context: Dict[str, Any]
    payload: Dict[str, Any]

@dataclass
class MultimodalContext:
    text_content: str = ""
    file_paths: List[str] = None
    image_features: Dict[str, Any] = None
    tabular_data: List[Dict[str, Any]] = None
    geo_coordinates: Dict[str, float] = None

class PerceptionLayer:
    def __init__(self):
        self.action_history = []
        self.current_context = MultimodalContext()
        self.action_counter = 0
    
    def capture_action(self, action_type: str, context: Dict[str, Any] = None, payload: Dict[str, Any] = None):
        """
        记录用户的每一个微交互
        
        Args:
            action_type: 操作类型，如 'upload_file', 'edit_cell', 'select_region', 'insert_section'
            context: 当前上下文信息
            payload: 操作的具体数据
        """
        action = UserAction(
            action_id=f"action_{self.action_counter}_{int(time.time())}",
            action_type=action_type,
            timestamp=time.time(),
            context=context or {},
            payload=payload or {}
        )
        self.action_history.append(action)
        self.action_counter += 1
        
        # 更新当前上下文
        self._update_context(action)
        
        return action
    
    def _update_context(self, action: UserAction):
        """根据用户行为更新多模态上下文"""
        if action.action_type == 'upload_file':
            file_path = action.payload.get('file_path')
            if file_path:
                self.current_context.file_paths = self.current_context.file_paths or []
                self.current_context.file_paths.append(file_path)
                self._parse_uploaded_file(file_path)
        
        elif action.action_type == 'edit_cell':
            sheet_name = action.payload.get('sheet')
            cell = action.payload.get('cell')
            value = action.payload.get('value')
            if sheet_name and cell and value is not None:
                self.current_context.tabular_data = self.current_context.tabular_data or []
                self.current_context.tabular_data.append({
                    'sheet': sheet_name,
                    'cell': cell,
                    'value': value,
                    'timestamp': action.timestamp
                })
        
        elif action.action_type == 'select_region':
            coords = action.payload.get('coordinates')
            if coords:
                self.current_context.geo_coordinates = coords
        
        elif action.action_type == 'message':
            self.current_context.text_content = action.payload.get('content', '')
    
    def _parse_uploaded_file(self, file_path: str):
        """解析上传的文件，提取关键信息"""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext in ['.xlsx', '.xls']:
            self._parse_excel(file_path)
        elif ext in ['.dwg', '.dxf']:
            self._parse_cad(file_path)
        elif ext in ['.jpg', '.png', '.jpeg']:
            self._parse_image(file_path)
    
    def _parse_excel(self, file_path: str):
        """解析Excel文件，提取监测数据"""
        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            
            # 检测是否为监测数据表格
            if any(col.lower() in ['cod', '浓度', '监测', '污染', '排放'] for col in df.columns):
                self.current_context.tabular_data = df.to_dict('records')
                print(f"[感知层] 解析监测数据: {len(self.current_context.tabular_data)} 行")
        except Exception as e:
            print(f"[感知层] 解析Excel失败: {e}")
    
    def _parse_cad(self, file_path: str):
        """解析CAD图纸"""
        print(f"[感知层] 检测到CAD图纸: {file_path}")
    
    def _parse_image(self, file_path: str):
        """解析图片"""
        print(f"[感知层] 检测到图片: {file_path}")
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取当前上下文摘要，供AI决策使用"""
        return {
            'text_content': self.current_context.text_content,
            'has_files': len(self.current_context.file_paths or []) > 0,
            'file_count': len(self.current_context.file_paths or []),
            'has_tabular_data': self.current_context.tabular_data is not None,
            'tabular_row_count': len(self.current_context.tabular_data or []),
            'has_geo_data': self.current_context.geo_coordinates is not None,
            'action_count': len(self.action_history),
            'recent_actions': [a.action_type for a in self.action_history[-5:]]
        }
    
    def get_action_sequence(self, window_size: int = 10) -> List[Dict[str, Any]]:
        """获取最近的操作序列，用于模式发现"""
        recent = self.action_history[-window_size:]
        return [{
            'type': a.action_type,
            'timestamp': a.timestamp,
            'context': a.context,
            'payload': a.payload
        } for a in recent]
    
    def reset_context(self):
        """重置上下文，开始新会话"""
        self.current_context = MultimodalContext()
        # 保留最近100条行为记录用于学习
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]

    def export_learning_data(self) -> Dict[str, Any]:
        """导出学习数据，用于训练"""
        return {
            'actions': [
                {
                    'action_type': a.action_type,
                    'timestamp': a.timestamp,
                    'context': a.context,
                    'payload': a.payload
                } for a in self.action_history
            ],
            'context_snapshots': [self.get_context_summary()]
        }