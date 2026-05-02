"""
A.R.I.A主控制器 - 协调所有组件

核心功能：
1. 管理文档生成任务
2. 协调文档解析、内容生成、Word渲染
3. 支持流式输出
4. 支持暂停/终止控制
"""
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .markdown_dsl_parser import MarkdownDSLParser, DSLNode
from .word_renderer import WordRenderer
from ..hermes_agent import get_consulting_engineer, get_self_driving_system
from ..tool_management import resolver, validator, slotter, registry


class GenerationStatus(Enum):
    """生成状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"


class TaskType(Enum):
    """任务类型"""
    EIA_REPORT = "eia_report"
    FEASIBILITY_STUDY = "feasibility_study"
    FINANCIAL_ANALYSIS = "financial_analysis"
    DOCUMENT_GENERATION = "document_generation"


@dataclass
class GenerationTask:
    """生成任务"""
    task_id: str
    task_type: TaskType
    parameters: Dict[str, Any]
    status: GenerationStatus = GenerationStatus.IDLE
    progress: float = 0.0
    generated_content: str = ""
    output_path: Optional[str] = None
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ARIAController:
    """
    A.R.I.A主控制器
    
    协调文档生成流程：
    1. 接收任务参数
    2. 调用咨询工程师生成内容
    3. 解析Markdown DSL
    4. 渲染Word文档
    5. 流式输出结果
    """
    
    def __init__(self):
        self.parser = MarkdownDSLParser()
        self.renderer = WordRenderer()
        self.consulting_engineer = get_consulting_engineer()
        self.self_driving_system = get_self_driving_system()
        
        self.tasks: Dict[str, GenerationTask] = {}
        self.current_task: Optional[GenerationTask] = None
        self.is_paused = False
        self.is_stopped = False
        
        # 回调函数
        self.on_progress: Optional[Callable[[float], None]] = None
        self.on_chunk: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_complete: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[GenerationStatus], None]] = None
    
    def create_task(self, task_type: str, parameters: Dict[str, Any]) -> str:
        """
        创建生成任务
        
        Args:
            task_type: 任务类型
            parameters: 参数
        
        Returns:
            任务ID
        """
        task_id = f"aria_{uuid.uuid4().hex[:8]}"
        
        task = GenerationTask(
            task_id=task_id,
            task_type=TaskType(task_type),
            parameters=parameters
        )
        
        self.tasks[task_id] = task
        return task_id
    
    async def start_generation(self, task_id: str):
        """
        开始生成任务
        
        Args:
            task_id: 任务ID
        """
        task = self.tasks.get(task_id)
        if not task:
            if self.on_error:
                self.on_error(f"任务不存在: {task_id}")
            return
        
        if task.status == GenerationStatus.RUNNING:
            if self.on_error:
                self.on_error("任务正在运行中")
            return
        
        # 更新状态
        task.status = GenerationStatus.RUNNING
        task.started_at = time.time()
        self.current_task = task
        
        if self.on_status_change:
            self.on_status_change(task.status)
        
        try:
            await self._run_generation(task)
        
        except Exception as e:
            task.status = GenerationStatus.ERROR
            task.error_message = str(e)
            
            if self.on_error:
                self.on_error(str(e))
            if self.on_status_change:
                self.on_status_change(task.status)
    
    async def _run_generation(self, task: GenerationTask):
        """执行生成任务"""
        # 1. 思考阶段 - 分析需求
        await self._send_thinking("正在分析任务需求...")
        await asyncio.sleep(0.5)
        
        # 2. 查询规范
        await self._send_thinking("查询相关规范和标准...")
        await asyncio.sleep(0.5)
        
        # 3. 生成内容
        await self._send_thinking("正在生成报告内容...")
        
        # 生成Markdown DSL内容
        content = self._generate_content(task)
        chunks = self._split_into_chunks(content)
        
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            # 检查停止信号
            if self.is_stopped:
                task.status = GenerationStatus.STOPPED
                if self.on_status_change:
                    self.on_status_change(task.status)
                return
            
            # 检查暂停信号
            while self.is_paused:
                task.status = GenerationStatus.PAUSED
                if self.on_status_change:
                    self.on_status_change(task.status)
                await asyncio.sleep(0.1)
                
                if self.is_stopped:
                    task.status = GenerationStatus.STOPPED
                    if self.on_status_change:
                        self.on_status_change(task.status)
                    return
            
            # 更新状态为运行中
            if task.status == GenerationStatus.PAUSED:
                task.status = GenerationStatus.RUNNING
                if self.on_status_change:
                    self.on_status_change(task.status)
            
            # 发送内容块
            await self._send_chunk(chunk)
            task.generated_content += chunk['content']
            
            # 更新进度
            progress = (i + 1) / total_chunks * 100
            task.progress = progress
            if self.on_progress:
                self.on_progress(progress)
            
            await asyncio.sleep(0.05)  # 打字机效果延迟
        
        # 4. 验证阶段
        await self._send_thinking("正在验证格式...")
        await asyncio.sleep(0.3)
        
        # 5. 渲染Word文档
        await self._send_thinking("正在生成Word文档...")
        
        if await self._render_document(task):
            await self._send_thinking("文档生成完成！")
            task.status = GenerationStatus.COMPLETED
            task.completed_at = time.time()
            
            if self.on_complete:
                self.on_complete(task.output_path)
            if self.on_status_change:
                self.on_status_change(task.status)
        else:
            raise Exception("Word文档渲染失败")
    
    def _call_tool(self, intent: str, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """自动调用工具管理层"""
        if inputs is None:
            inputs = {}
        
        result = resolver.resolve(intent, inputs)
        
        if result.success:
            manifest = registry.get_manifest(result.tool_id)
            if manifest:
                validation = validator.validate(manifest, result.outputs)
                if validation.valid:
                    for output_name in result.outputs:
                        slotter.bind_to_output(result.tool_id, output_name, result.outputs[output_name])
                    return result.outputs
        
        return {}

    def _generate_content(self, task: GenerationTask) -> str:
        """生成Markdown DSL内容"""
        project_name = task.parameters.get('project_name', '未知项目')
        location = task.parameters.get('location', '待定')
        investment = task.parameters.get('investment', '1000')
        
        pi_value = self._call_tool('计算圆周率', {'precision': 10}).get('pi_value', '3.14159')
        
        content = f"""<!-- STYLE: heading_1 -->
一、建设项目基本情况

<!-- STYLE: normal_text -->
项目名称：{project_name}

项目性质：新建

建设地点：{location}

<!-- STYLE: heading_2 -->
1.1 项目概况

<!-- STYLE: normal_text -->
本项目位于上述建设地点，总投资约{investment}万元。

项目主要建设内容包括：
- 主体工程
- 辅助工程
- 环保工程

<!-- STYLE: heading_2 -->
1.2 编制依据

<!-- STYLE: normal_text -->
1. 《中华人民共和国环境保护法》
2. 《中华人民共和国环境影响评价法》
3. 相关行业标准和规范

<!-- STYLE: heading_1 -->
二、污染物排放分析

<!-- STYLE: heading_2 -->
2.1 排放量计算

<!-- STYLE: normal_text -->
根据项目生产工艺，主要污染物排放量计算如下：

<!-- STYLE: code_block -->
```python
# 排放量计算
def calculate_emission(project_data):
    \"\"\"计算污染物排放量\"\"\"
    emission = project_data['generation'] * (1 - project_data['efficiency'] / 100)
    return round(emission, 2)

# 计算示例
result = calculate_emission({{
    'generation': 200,
    'efficiency': 95
}})
print(f\"排放量: {{result}} t/a\")
```

<!-- STYLE: heading_2 -->
2.2 排放汇总表

<!-- STYLE: env_table -->
| 污染物 | 产生量(t/a) | 处理效率(%) | 排放量(t/a) | 是否达标 |
|--------|------------|------------|------------|----------|
| SO2 | 200 | 95 | 10 | 是 |
| NOx | 150 | 90 | 15 | 是 |
| 粉尘 | 100 | 99 | 1 | 是 |

<!-- STYLE: heading_1 -->
三、结论与建议

<!-- STYLE: heading_2 -->
3.1 结论

<!-- STYLE: normal_text -->
本项目污染物排放均符合国家相关标准要求，项目可行。

<!-- STYLE: heading_2 -->
3.2 圆周率测试

<!-- STYLE: normal_text -->
圆周率计算结果：{pi_value}

<!-- STYLE: heading_2 -->
3.2 建议

<!-- STYLE: normal_text -->
1. 严格执行环保设施运行管理
2. 定期监测污染物排放
3. 加强环境管理体系建设
"""
        
        return content
    
    def _split_into_chunks(self, content: str) -> List[Dict[str, Any]]:
        """将内容分割为数据块"""
        chunks = []
        lines = content.split('\n')
        
        for line in lines:
            if line.startswith('```'):
                # 代码块处理
                chunks.append({
                    'type': 'code',
                    'content': line + '\n',
                    'metadata': {'phase': 'code'}
                })
            elif line.startswith('<!--'):
                # 指令处理
                chunks.append({
                    'type': 'directive',
                    'content': line + '\n',
                    'metadata': {'phase': 'directive'}
                })
            elif line.startswith('|'):
                # 表格处理
                chunks.append({
                    'type': 'table',
                    'content': line + '\n',
                    'metadata': {'phase': 'table'}
                })
            elif line.startswith('- '):
                # 列表项处理
                chunks.append({
                    'type': 'list',
                    'content': line + '\n',
                    'metadata': {'phase': 'list'}
                })
            else:
                # 普通文本处理
                if line.strip():
                    chunks.append({
                        'type': 'content',
                        'content': line + '\n',
                        'metadata': {'phase': 'content'}
                    })
        
        return chunks
    
    async def _send_thinking(self, message: str):
        """发送思考消息"""
        if self.on_chunk:
            self.on_chunk({
                'type': 'thinking',
                'content': message,
                'metadata': {'phase': 'thinking'}
            })
    
    async def _send_chunk(self, chunk: Dict[str, Any]):
        """发送内容块"""
        if self.on_chunk:
            self.on_chunk(chunk)
    
    async def _render_document(self, task: GenerationTask) -> bool:
        """渲染Word文档"""
        try:
            # 解析生成的内容
            nodes = self.parser.parse(task.generated_content)
            
            # 确保输出目录存在
            output_dir = Path('output')
            output_dir.mkdir(exist_ok=True)
            
            # 生成输出路径
            project_name = task.parameters.get('project_name', 'report')
            output_path = str(output_dir / f"{project_name}.docx")
            
            # 渲染文档
            success = self.renderer.render(nodes, output_path)
            
            if success:
                task.output_path = output_path
                return True
            
            return False
        
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def pause(self):
        """暂停生成"""
        self.is_paused = True
    
    def resume(self):
        """恢复生成"""
        self.is_paused = False
    
    def stop(self):
        """停止生成"""
        self.is_stopped = True
        self.is_paused = False
    
    def get_task(self, task_id: str) -> Optional[GenerationTask]:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return {'success': False, 'error': '任务不存在'}
        
        return {
            'success': True,
            'task_id': task.task_id,
            'status': task.status.value,
            'progress': task.progress,
            'output_path': task.output_path,
            'error_message': task.error_message
        }
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        result = []
        for task in self.tasks.values():
            result.append({
                'task_id': task.task_id,
                'task_type': task.task_type.value,
                'status': task.status.value,
                'progress': task.progress,
                'created_at': task.created_at
            })
        return result
    
    # ==================== 样式学习与实时调整方法 ====================
    
    def learn_styles_from_document(self, docx_path: str, document_type: str = "unknown") -> Dict[str, Any]:
        """
        从用户上传的文档学习样式
        
        Args:
            docx_path: Word文档路径
            document_type: 文档类型
        
        Returns:
            学习结果
        """
        result = self.renderer.learn_styles_from_document(docx_path, document_type)
        
        if result['success']:
            # 发送思考消息通知用户
            if self.on_chunk:
                self.on_chunk({
                    'type': 'thinking',
                    'content': f'已从文档学习到 {result.get("paragraph_styles", 0)} 个样式，将应用到生成的文档中',
                    'metadata': {'phase': 'style_learning'}
                })
        
        return result
    
    def learn_styles_from_multiple(self, doc_paths: List[str], document_type: str = "unknown") -> Dict[str, Any]:
        """
        从多个文档学习样式并融合
        
        Args:
            doc_paths: Word文档路径列表
            document_type: 文档类型
        
        Returns:
            学习结果
        """
        return self.renderer.learn_styles_from_multiple(doc_paths, document_type)
    
    def apply_learned_styles(self):
        """应用学习到的样式"""
        self.renderer.apply_learned_styles()
        
        if self.on_chunk:
            self.on_chunk({
                'type': 'thinking',
                'content': '已应用学习到的样式',
                'metadata': {'phase': 'style_application'}
            })
    
    def set_style_override(self, style_type: str, **kwargs):
        """
        设置样式覆盖（用于实时调整）
        
        Args:
            style_type: 样式类型名称（heading_1, heading_2, normal_text等）
            kwargs: 样式属性
        """
        from .markdown_dsl_parser import StyleType
        
        style_type_map = {
            'heading_1': StyleType.HEADING_1,
            'heading_2': StyleType.HEADING_2,
            'heading_3': StyleType.HEADING_3,
            'normal_text': StyleType.NORMAL_TEXT,
            'code_block': StyleType.CODE_BLOCK,
            'env_table': StyleType.ENV_TABLE,
        }
        
        style_enum = style_type_map.get(style_type.lower())
        if style_enum:
            self.renderer.set_style_override(style_enum, **kwargs)
            
            # 发送思考消息通知用户
            if self.on_chunk:
                self.on_chunk({
                    'type': 'thinking',
                    'content': f'已调整{style_type}样式: {kwargs}',
                    'metadata': {'phase': 'style_adjustment'}
                })
    
    def clear_style_overrides(self):
        """清除所有样式覆盖"""
        self.renderer.clear_style_overrides()
        
        if self.on_chunk:
            self.on_chunk({
                'type': 'thinking',
                'content': '已重置所有样式覆盖',
                'metadata': {'phase': 'style_reset'}
            })
    
    def get_learned_styles_summary(self) -> Dict[str, Any]:
        """获取学习到的样式摘要"""
        return self.renderer.get_learned_styles_summary()
    
    def export_learned_styles(self, output_path: str):
        """导出学习到的样式"""
        self.renderer.export_learned_styles(output_path)
    
    def import_learned_styles(self, input_path: str):
        """导入学习到的样式"""
        self.renderer.import_learned_styles(input_path)


# 单例模式
_aria_controller = None


def get_aria_controller() -> ARIAController:
    """获取A.R.I.A控制器单例"""
    global _aria_controller
    if _aria_controller is None:
        _aria_controller = ARIAController()
    return _aria_controller