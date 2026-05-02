"""
QWebChannel后端 - Web Channel Backend

功能：
1. 实现QWebChannel通信接口
2. 提供前端调用的API
3. 处理前端事件和回调
4. A.R.I.A流式输出支持
"""

import asyncio
import json
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from client.src.business.system_integration import get_system_manager
from client.src.business.api_gateway import get_api_gateway
from client.src.business.hermes_agent import get_self_driving_system


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
    
    A.R.I.A相关方法：
    - startARIAGeneration: 启动A.R.I.A文档生成
    - pauseARIAGeneration: 暂停生成
    - resumeARIAGeneration: 恢复生成
    - stopARIAGeneration: 终止生成
    - getARIAGenerationStatus: 获取生成状态
    - downloadGeneratedDocument: 下载生成的文档
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
    
    # A.R.I.A流式输出信号
    onARIAGenerationStarted = pyqtSignal(str)
    onARIAGenerationProgress = pyqtSignal(str)
    onARIAGenerationChunk = pyqtSignal(str)
    onARIAGenerationPaused = pyqtSignal()
    onARIAGenerationResumed = pyqtSignal()
    onARIAGenerationCompleted = pyqtSignal(str)
    onARIAGenerationError = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.system_manager = get_system_manager()
        self.api_gateway = get_api_gateway()
        self.aria_controller = None
        self.generation_task = None
        self.generation_paused = False
        self.generation_stopped = False
        self.current_document_path = None
    
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
    
    # ==================== A.R.I.A 流式输出方法 ====================
    
    @pyqtSlot(str, str)
    def startARIAGeneration(self, task_type: str, parameters_json: str):
        """
        启动A.R.I.A文档生成
        
        Args:
            task_type: 任务类型 (eia_report, feasibility_study, etc.)
            parameters_json: 参数JSON
        """
        if self.generation_task and self.generation_task.is_alive():
            self.onARIAGenerationError.emit('已有生成任务在运行中')
            return
        
        try:
            parameters = json.loads(parameters_json)
        except json.JSONDecodeError:
            self.onARIAGenerationError.emit('无效的JSON参数')
            return
        
        self.generation_paused = False
        self.generation_stopped = False
        
        # 发送启动信号
        self.onARIAGenerationStarted.emit(json.dumps({
            'task_type': task_type,
            'parameters': parameters
        }))
        
        # 在后台线程中执行生成
        self.generation_task = threading.Thread(
            target=self._run_aria_generation,
            args=(task_type, parameters),
            daemon=True
        )
        self.generation_task.start()
    
    def _run_aria_generation(self, task_type: str, parameters: dict):
        """
        执行A.R.I.A生成任务（在后台线程中运行）
        """
        try:
            # 模拟流式生成过程
            chunks = self._generate_document_chunks(task_type, parameters)
            
            for chunk in chunks:
                # 检查是否停止
                if self.generation_stopped:
                    self.onARIAGenerationError.emit('生成已终止')
                    return
                
                # 检查是否暂停
                while self.generation_paused:
                    time.sleep(0.1)
                    if self.generation_stopped:
                        self.onARIAGenerationError.emit('生成已终止')
                        return
                
                # 发送数据块
                self.onARIAGenerationChunk.emit(json.dumps(chunk))
                time.sleep(0.1)  # 模拟打字机效果延迟
            
            # 生成完成
            self.onARIAGenerationCompleted.emit(json.dumps({
                'document_path': self.current_document_path,
                'task_type': task_type
            }))
            
        except Exception as e:
            self.onARIAGenerationError.emit(str(e))
    
    def _generate_document_chunks(self, task_type: str, parameters: dict):
        """
        生成文档数据块（模拟）
        
        返回格式：
        {
            'type': 'thinking' | 'content' | 'code' | 'table',
            'content': '...',
            'metadata': {...}
        }
        """
        project_name = parameters.get('project_name', '未知项目')
        
        # 思考阶段
        yield {
            'type': 'thinking',
            'content': f'正在分析{task_type}任务需求...',
            'metadata': {'phase': 'analysis'}
        }
        
        yield {
            'type': 'thinking',
            'content': '查询相关规范和标准...',
            'metadata': {'phase': 'research'}
        }
        
        yield {
            'type': 'thinking',
            'content': '准备生成报告内容...',
            'metadata': {'phase': 'generation'}
        }
        
        # 内容阶段 - Markdown DSL格式
        content_chunks = [
            '<!-- STYLE: heading_1 -->\n',
            f'一、建设项目基本情况\n\n',
            '<!-- STYLE: normal_text -->\n',
            f'项目名称：{project_name}\n\n',
            f'项目性质：新建\n\n',
            f'建设地点：{parameters.get("location", "待定")}\n\n',
            '<!-- STYLE: heading_2 -->\n',
            '1.1 项目概况\n\n',
            '<!-- STYLE: normal_text -->\n',
            '本项目位于上述建设地点，总投资约',
            f'{parameters.get("investment", "1000")}万元。',
            '\n\n项目主要建设内容包括：\n',
            '- 主体工程\n',
            '- 辅助工程\n',
            '- 环保工程\n',
            '\n',
            '<!-- STYLE: heading_2 -->\n',
            '1.2 编制依据\n\n',
            '<!-- STYLE: normal_text -->\n',
            '1. 《中华人民共和国环境保护法》\n',
            '2. 《中华人民共和国环境影响评价法》\n',
            '3. 相关行业标准和规范\n',
        ]
        
        for chunk in content_chunks:
            yield {
                'type': 'content',
                'content': chunk,
                'metadata': {'phase': 'content'}
            }
        
        # 代码阶段
        yield {
            'type': 'code',
            'content': '''```python
# 排放量计算
def calculate_emission(project_data):
    return project_data['generation'] * (1 - project_data['efficiency'] / 100)

result = calculate_emission({
    'generation': 200,
    'efficiency': 95
})
print(f"排放量: {result} t/a")
```''',
            'metadata': {'phase': 'code', 'language': 'python'}
        }
        
        # 表格阶段
        yield {
            'type': 'table',
            'content': '''<!-- STYLE: env_table -->
| 污染物 | 产生量(t/a) | 处理效率(%) | 排放量(t/a) |
|--------|------------|------------|------------|
| SO2 | 200 | 95 | 10 |
| NOx | 150 | 90 | 15 |
| 粉尘 | 100 | 99 | 1 |''',
            'metadata': {'phase': 'table'}
        }
        
        # 完成思考
        yield {
            'type': 'thinking',
            'content': '报告生成完成，正在验证格式...',
            'metadata': {'phase': 'validation'}
        }
        
        # 设置文档路径
        self.current_document_path = f'/output/{project_name}_report.docx'
    
    @pyqtSlot()
    def pauseARIAGeneration(self):
        """暂停生成"""
        self.generation_paused = True
        self.onARIAGenerationPaused.emit()
    
    @pyqtSlot()
    def resumeARIAGeneration(self):
        """恢复生成"""
        self.generation_paused = False
        self.onARIAGenerationResumed.emit()
    
    @pyqtSlot()
    def stopARIAGeneration(self):
        """终止生成"""
        self.generation_stopped = True
        self.generation_paused = False
    
    @pyqtSlot(result=str)
    def getARIAGenerationStatus(self):
        """获取生成状态"""
        status = 'idle'
        if self.generation_task and self.generation_task.is_alive():
            if self.generation_paused:
                status = 'paused'
            else:
                status = 'running'
        elif self.generation_stopped:
            status = 'stopped'
        
        return json.dumps({
            'status': status,
            'document_path': self.current_document_path
        })
    
    @pyqtSlot(result=str)
    def downloadGeneratedDocument(self):
        """下载生成的文档"""
        if self.current_document_path:
            return json.dumps({
                'success': True,
                'path': self.current_document_path,
                'filename': self.current_document_path.split('/')[-1]
            })
        else:
            return json.dumps({
                'success': False,
                'error': '没有已生成的文档'
            })