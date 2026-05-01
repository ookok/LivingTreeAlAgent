"""
QWebChannel后端 - Web Channel Backend

功能：
1. 实现QWebChannel通信接口
2. 提供前端调用的API
3. 处理前端事件和回调
"""

import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from client.src.business.system_integration import get_system_manager
from client.src.business.api_gateway import get_api_gateway


class WebChannelBackend(QObject):
    """
    QWebChannel后端服务
    
    提供前端可调用的API方法：
    - getSystemStatus: 获取系统状态
    - getAPIStats: 获取API统计
    - getMCPStatus: 获取MCP状态
    - callMCPTool: 调用MCP工具
    - setAutonomyLevel: 设置自主级别
    - addGoal: 添加目标
    - triggerReflection: 触发自我反思
    - toggleMCP: 切换MCP状态
    - executeReasoning: 执行推理
    - addMemory: 添加记忆
    - refreshMemory: 刷新记忆
    """
    
    # 信号定义
    onStatusUpdate = pyqtSignal(str)
    onAPIStats = pyqtSignal(str)
    onMemoryUpdate = pyqtSignal(str)
    onLearningUpdate = pyqtSignal(str)
    onReasoningResult = pyqtSignal(str)
    onSelfAwarenessUpdate = pyqtSignal(str)
    onMCPStatus = pyqtSignal(str)
    onToolResult = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.system_manager = get_system_manager()
        self.api_gateway = get_api_gateway()
    
    @pyqtSlot()
    def initialize(self):
        """初始化系统"""
        self.system_manager.initialize()
        self.onStatusUpdate.emit(json.dumps(self.system_manager.get_status()))
    
    @pyqtSlot()
    def getSystemStatus(self):
        """获取系统状态"""
        status = self.system_manager.get_status()
        self.onStatusUpdate.emit(json.dumps(status))
    
    @pyqtSlot()
    def getAPIStats(self):
        """获取API统计"""
        result = self.api_gateway.call('system/stats')
        self.onAPIStats.emit(json.dumps(result.get('data', result)))
    
    @pyqtSlot()
    def getMCPStatus(self):
        """获取MCP状态"""
        mcp_manager = self.system_manager.get_subsystem('mcp_service')
        if mcp_manager:
            status = mcp_manager.get_status()
            stats = status.get('stats', {})
            self.onMCPStatus.emit(json.dumps({
                'status': {
                    'mode': status.get('mode', 'disabled'),
                    'service_status': status.get('service_status', 'disconnected')
                },
                'stats': stats
            }))
        else:
            self.onMCPStatus.emit(json.dumps({
                'status': {'mode': 'disabled', 'service_status': 'disconnected'},
                'stats': {'total_calls': 0, 'success_calls': 0, 'failed_calls': 0, 'fallback_calls': 0}
            }))
    
    @pyqtSlot(str, str)
    def callMCPTool(self, tool_name: str, params_json: str):
        """调用MCP工具"""
        try:
            params = json.loads(params_json)
        except json.JSONDecodeError:
            self.onToolResult.emit(json.dumps({'success': False, 'error': '无效的JSON参数'}))
            return
        
        mcp_manager = self.system_manager.get_subsystem('mcp_service')
        if mcp_manager:
            result = mcp_manager.call_tool(tool_name, **params)
            self.onToolResult.emit(json.dumps(result))
        else:
            self.onToolResult.emit(json.dumps({'success': False, 'error': 'MCP服务未初始化'}))
    
    @pyqtSlot(int)
    def setAutonomyLevel(self, level: int):
        """设置自主级别"""
        result = self.api_gateway.call('self_awareness/set_autonomy_level', level=level)
        self._update_self_awareness()
    
    @pyqtSlot(str, float)
    def addGoal(self, description: str, priority: float):
        """添加目标"""
        result = self.api_gateway.call('self_awareness/set_goal', description=description, priority=priority)
        self._update_self_awareness()
    
    @pyqtSlot()
    def triggerReflection(self):
        """触发自我反思"""
        result = self.api_gateway.call('self_awareness/reflect')
        self._update_self_awareness()
    
    @pyqtSlot()
    def toggleMCP(self):
        """切换MCP状态"""
        mcp_manager = self.system_manager.get_subsystem('mcp_service')
        if mcp_manager:
            current_mode = mcp_manager.get_status().get('mode', 'disabled')
            new_mode = 'disabled' if current_mode != 'disabled' else 'local'
            mcp_manager.set_mode(new_mode)
            
            if new_mode != 'disabled':
                mcp_manager.start()
            
        self.getMCPStatus()
    
    @pyqtSlot(str, str)
    def executeReasoning(self, query: str, reasoning_type: str):
        """执行推理"""
        reasoning = self.system_manager.get_subsystem('cognitive_reasoning')
        if reasoning:
            result = reasoning.reason(query, reasoning_type)
            self.onReasoningResult.emit(result.get('result', '推理失败'))
        else:
            self.onReasoningResult.emit('推理系统未初始化')
    
    @pyqtSlot(str, str)
    def addMemory(self, content: str, memory_type: str = 'short'):
        """添加记忆"""
        memory = self.system_manager.get_subsystem('brain_memory')
        if memory:
            if memory_type == 'short':
                memory.store_short_term(content, {})
            else:
                memory.store_long_term(content, {})
            self.refreshMemory()
    
    @pyqtSlot()
    def refreshMemory(self):
        """刷新记忆"""
        memory = self.system_manager.get_subsystem('brain_memory')
        if memory:
            short_memories = memory.retrieve_recent_short_term(10)
            long_memories = memory.retrieve_recent_long_term(10)
            
            memories = []
            for mem in short_memories:
                memories.append({
                    'id': mem.id,
                    'content': mem.content,
                    'type': 'short',
                    'timestamp': mem.timestamp,
                    'relevance': mem.relevance
                })
            
            for mem in long_memories:
                memories.append({
                    'id': mem.id,
                    'content': mem.content,
                    'type': 'long',
                    'timestamp': mem.timestamp,
                    'relevance': mem.relevance
                })
            
            self.onMemoryUpdate.emit(json.dumps(memories))
        else:
            self.onMemoryUpdate.emit(json.dumps([]))
    
    def _update_self_awareness(self):
        """更新自我意识状态"""
        status = self.api_gateway.call('self_awareness/get_status')
        data = status.get('data', status)
        
        self.onSelfAwarenessUpdate.emit(json.dumps({
            'autonomy': data.get('autonomy', {'level': 3}),
            'goals': data.get('goals', {'count': 0}),
            'activeGoals': self._get_active_goals(),
            'reflectionHistory': self._get_reflection_history(),
            'cognitiveLoad': data.get('system_state', {}).get('cognitive_load', 0.3)
        }))
    
    def _get_active_goals(self):
        """获取活跃目标"""
        result = self.api_gateway.call('self_awareness/get_all_goals')
        goals = result.get('data', [])
        return [
            {
                'id': goal.get('id', ''),
                'description': goal.get('description', ''),
                'priority': goal.get('priority', 0.5),
                'progress': goal.get('progress', 0)
            }
            for goal in goals
        ]
    
    def _get_reflection_history(self):
        """获取反思历史"""
        result = self.api_gateway.call('self_awareness/get_reflection_history', limit=5)
        history = result.get('data', [])
        return [
            {
                'timestamp': item.get('timestamp', ''),
                'suggestions': item.get('suggestions', [])
            }
            for item in history
        ]