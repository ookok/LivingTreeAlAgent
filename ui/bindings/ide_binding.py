# -*- coding: utf-8 -*-
"""
IDE Binding - IDE面板与业务逻辑绑定

将 PyDracula UI IDE 组件与 IDE 服务层连接
"""

from typing import Optional, Callable
import asyncio

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit


class IDEBinding(QObject):
    """
    IDE 面板业务逻辑绑定

    Signals:
        code_generated: 代码生成完成
        execution_result: 执行结果
        completion_ready: 补全准备就绪
        error_occurred: 错误发生
    """

    code_generated = Signal(str, str)  # (code, language)
    execution_result = Signal(dict)  # {'success': bool, 'output': str, 'error': str}
    completion_ready = Signal(str, int)  # (completion_text, cursor_position)
    error_occurred = Signal(str)  # error_message

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent = parent
        self._ide_service = None
        self._ide_agent = None
        self._initialized = False

        # UI 组件引用
        self._code_editor: Optional[QPlainTextEdit] = None
        self._output_widget: Optional[QTextEdit] = None
        self._status_widget = None

        # IDE 状态
        self._current_language: str = "python"
        self._is_executing: bool = False

    def initialize(self):
        """初始化 IDE 绑定"""
        if self._initialized:
            return

        try:
            # 延迟导入 IDE 服务
            from client.src.business.ide_service import IdeService
            self._ide_service = IdeService()

            # 尝试导入 IDE Agent
            try:
                from client.src.business.ide_agent import IdeAgent
                self._ide_agent = IdeAgent()
            except ImportError:
                print("[IDEBinding] IdeAgent not available, using IdeService only")

            self._initialized = True
            print("[IDEBinding] Initialized successfully")

        except Exception as e:
            print(f"[IDEBinding] Initialize error: {e}")
            self.error_occurred.emit(f"IDE初始化失败: {e}")

    def bind_ui(self, code_editor: QPlainTextEdit, output_widget: QTextEdit, status_widget=None):
        """
        绑定 UI 组件

        Args:
            code_editor: 代码编辑器
            output_widget: 输出显示区
            status_widget: 状态显示区 (可选)
        """
        self._code_editor = code_editor
        self._output_widget = output_widget
        self._status_widget = status_widget

        # 设置编辑器属性
        if code_editor:
            # 启用语法高亮提示
            code_editor.setPlaceholderText("# 在这里编写代码\n# 或输入自然语言描述，AI 将为您生成代码")

    def set_language(self, language: str):
        """
        设置编程语言

        Args:
            language: 语言名称 (python, javascript, java, etc.)
        """
        self._current_language = language.lower()
        self._update_status(f"语言: {language}")

    def get_code(self) -> str:
        """获取编辑器中的代码"""
        if self._code_editor:
            return self._code_editor.toPlainText()
        return ""

    def set_code(self, code: str):
        """设置编辑器中的代码"""
        if self._code_editor:
            self._code_editor.setPlainText(code)

    @Slot()
    def generate_code(self, description: str = None):
        """
        生成代码

        Args:
            description: 代码描述/需求 (如果为空则使用编辑器内容作为需求)
        """
        if not self._initialized:
            self.initialize()

        if description is None and self._code_editor:
            description = self._code_editor.toPlainText()

        if not description:
            self.error_occurred.emit("请输入代码需求或描述")
            return

        self._update_status("正在生成代码...")

        # 异步生成
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._async_generate_code(description))
            else:
                asyncio.run(self._async_generate_code(description))
        except Exception as e:
            self.error_occurred.emit(f"生成失败: {e}")

    async def _async_generate_code(self, description: str):
        """异步生成代码"""
        try:
            if self._ide_agent:
                result = await self._ide_agent.generate_code(
                    description,
                    language=self._current_language
                )
            elif self._ide_service:
                result = await self._ide_service.generate_code(
                    description,
                    language=self._current_language
                )
            else:
                result = {'code': '', 'error': 'No IDE service available'}

            if result.get('error'):
                self.error_occurred.emit(result['error'])
            else:
                code = result.get('code', '')
                self.code_generated.emit(code, self._current_language)
                self.set_code(code)
                self._update_status("代码生成完成")

        except Exception as e:
            self.error_occurred.emit(f"生成异常: {e}")

    @Slot()
    def execute_code(self):
        """执行编辑器中的代码"""
        if self._is_executing:
            self._update_status("正在执行...")
            return

        code = self.get_code()
        if not code.strip():
            self.error_occurred.emit("编辑器内容为空")
            return

        self._is_executing = True
        self._update_status("正在执行...")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._async_execute_code(code))
            else:
                asyncio.run(self._async_execute_code(code))
        except Exception as e:
            self._is_executing = False
            self.error_occurred.emit(f"执行失败: {e}")

    async def _async_execute_code(self, code: str):
        """异步执行代码"""
        try:
            if self._ide_service:
                result = await self._ide_service.execute_code(
                    code,
                    language=self._current_language
                )
            else:
                # 简单本地执行
                result = await self._local_execute(code)

            self.execution_result.emit(result)
            self._display_execution_result(result)

        except Exception as e:
            self.execution_result.emit({
                'success': False,
                'output': '',
                'error': str(e)
            })
        finally:
            self._is_executing = False
            self._update_status("就绪")

    async def _local_execute(self, code: str) -> dict:
        """本地简单执行 (仅支持 Python)"""
        if self._current_language != "python":
            return {
                'success': False,
                'output': '',
                'error': f'本地执行不支持 {self._current_language}'
            }

        try:
            import io
            from contextlib import redirect_stdout

            output = io.StringIO()
            exec(code, {'__name__': '__main__'})
            return {
                'success': True,
                'output': output.getvalue() or '执行完成 (无输出)',
                'error': ''
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }

    def _display_execution_result(self, result: dict):
        """显示执行结果"""
        if not self._output_widget:
            return

        success = result.get('success', False)
        output = result.get('output', '')
        error = result.get('error', '')

        if success:
            html = f'''
            <div style="color: #4CAF50; margin: 8px 0;">
                <b>✅ 执行成功</b><br>
                <pre style="background: #1E1E1E; padding: 8px; border-radius: 4px;">{self._escape_html(output)}</pre>
            </div>
            '''
        else:
            html = f'''
            <div style="color: #F44336; margin: 8px 0;">
                <b>❌ 执行失败</b><br>
                <pre style="background: #1E1E1E; padding: 8px; border-radius: 4px; color: #F44336;">{self._escape_html(error)}</pre>
            </div>
            '''

        self._output_widget.append(html)

    @Slot()
    def explain_code(self):
        """解释代码"""
        code = self.get_code()
        if not code.strip():
            self.error_occurred.emit("编辑器内容为空")
            return

        self._update_status("正在解释...")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._async_explain_code(code))
            else:
                asyncio.run(self._async_explain_code(code))
        except Exception as e:
            self.error_occurred.emit(f"解释失败: {e}")

    async def _async_explain_code(self, code: str):
        """异步解释代码"""
        try:
            if self._ide_service:
                result = await self._ide_service.explain_code(
                    code,
                    language=self._current_language
                )
            else:
                result = {'explanation': 'IDE服务不可用', 'error': None}

            if result.get('error'):
                self.error_occurred.emit(result['error'])
            else:
                explanation = result.get('explanation', '')
                self._display_explanation(explanation)

        except Exception as e:
            self.error_occurred.emit(f"解释异常: {e}")

    def _display_explanation(self, explanation: str):
        """显示代码解释"""
        if not self._output_widget:
            return

        html = f'''
        <div style="color: #2196F3; margin: 8px 0;">
            <b>📖 代码解释</b><br>
            <div style="background: #1E1E1E; padding: 8px; border-radius: 4px; color: #E0E0E0;">
                {self._escape_html(explanation)}
            </div>
        </div>
        '''
        self._output_widget.append(html)
        self._update_status("解释完成")

    @Slot()
    def complete_code(self):
        """代码补全"""
        if not self._code_editor:
            return

        cursor_pos = self._code_editor.textCursor().position()
        code_before = self._code_editor.toPlainText()[:cursor_pos]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._async_complete_code(code_before, cursor_pos))
            else:
                asyncio.run(self._async_complete_code(code_before, cursor_pos))
        except Exception as e:
            self.error_occurred.emit(f"补全失败: {e}")

    async def _async_complete_code(self, code_before: str, cursor_pos: int):
        """异步代码补全"""
        try:
            if self._ide_service:
                result = await self._ide_service.complete_code(
                    code_before,
                    language=self._current_language
                )
            else:
                result = {'completion': '', 'error': 'IDE服务不可用'}

            if result.get('completion'):
                self.completion_ready.emit(result['completion'], cursor_pos)
        except Exception as e:
            print(f"[IDEBinding] Complete error: {e}")

    def _update_status(self, message: str):
        """更新状态"""
        if self._status_widget:
            self._status_widget.setText(message)

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace('\n', '<br>'))

    def cleanup(self):
        """清理资源"""
        self._initialized = False
        self._ide_service = None
        self._ide_agent = None
