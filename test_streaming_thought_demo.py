"""
共脑系统 Demo 测试脚本（模拟数据版）

使用模拟数据展示 UI 效果，无需真实 LLM 连接
"""

import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

# 模拟数据
MOCK_THOUGHTS = [
    "思考：用户想要查询天气信息...",
    "思考：需要调用 weather 动作来获取天气数据...",
    "思考：用户还想要计算 2+2，需要调用 calculate 动作...",
    "思考：已获取所有必要信息，可以给出最终答案了...",
]

MOCK_ACTIONS = [
    {"type": "weather", "status": "running", "result": "", "error": ""},
    {"type": "weather", "status": "success", "result": "北京今天晴天，温度 20-25 度", "error": ""},
    {"type": "calculate", "status": "running", "result": "", "error": ""},
    {"type": "calculate", "status": "success", "result": "计算结果: 2+2 = 4", "error": ""},
]

MOCK_FINAL = {
    "summary": "已成功查询天气并计算结果",
    "full_result": {
        "executed_actions": ["weather", "calculate"],
        "weather_result": "北京今天晴天，温度 20-25 度",
        "calc_result": "2+2 = 4",
    }
}


class MockStreamingExecutor:
    """模拟的流式执行器（用于测试 UI）"""
    
    def __init__(self):
        self.current_step = 0
    
    async def execute_stream(self, intent: str, context: dict = None):
        """模拟流式执行"""
        import asyncio
        
        # 1. 输出思考片段
        for i, thought in enumerate(MOCK_THOUGHTS):
            await asyncio.sleep(0.5)  # 模拟延迟
            yield {
                "type": "thought",
                "content": thought + "\n",
                "confidence": 0.9,
                "is_final": False,
            }
        
        # 2. 执行动作
        for i, action in enumerate(MOCK_ACTIONS):
            await asyncio.sleep(0.8)  # 模拟执行延迟
            yield {
                "type": "action",
                "action_type": action["type"],
                "action_params": {"test": "param"},
                "status": action["status"],
                "result": action["result"],
                "error": action["error"],
            }
        
        # 3. 输出最终结果
        await asyncio.sleep(0.3)
        yield {
            "type": "final",
            "summary": MOCK_FINAL["summary"],
            "full_result": MOCK_FINAL["full_result"],
        }


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 导入 UI 面板
    from client.src.presentation.panels.streaming_thought_demo_panel import (
        StreamingThoughtDemoPanel
    )
    
    # 创建窗口
    window = QWidget()
    window.setWindowTitle("共脑系统 Demo（模拟数据版）")
    window.setMinimumSize(1000, 700)
    
    layout = QVBoxLayout(window)
    
    # 创建 Demo 面板
    panel = StreamingThoughtDemoPanel()
    
    # 替换执行器为模拟执行器
    mock_executor = MockStreamingExecutor()
    
    # 修改面板的执行逻辑（使用模拟数据）
    def mock_execute(intent: str, context: dict):
        """模拟执行"""
        import asyncio
        
        # 清空输出
        panel.thought_display.clear()
        panel.action_list.clear()
        panel.result_display.clear()
        
        # 更新状态
        panel.status_label.setText("正在执行（模拟）...")
        panel.progress_bar.setVisible(True)
        panel.execute_btn.setEnabled(False)
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 运行模拟执行
        async def run_mock():
            all_thoughts = []
            
            async for chunk in mock_executor.execute_stream(intent, context):
                chunk_type = chunk.get("type")
                
                # 处理思考片段
                if chunk_type == "thought":
                    content = chunk.get("content", "")
                    if content:
                        panel._append_thought(content)
                        all_thoughts.append(content)
                
                # 处理动作片段
                elif chunk_type == "action":
                    action_type = chunk.get("action_type", "")
                    status = chunk.get("status", "")
                    result = chunk.get("result", "")
                    error = chunk.get("error", "")
                    
                    panel._append_action(action_type, status, result, error)
                
                # 处理最终总结
                elif chunk_type == "final":
                    summary = chunk.get("summary", "")
                    full_result = chunk.get("full_result", {})
                    
                    panel._show_final_result({
                        "summary": summary,
                        "full_result": full_result,
                    })
            
            # 执行完成
            panel.execute_btn.setEnabled(True)
            panel.progress_bar.setVisible(False)
            panel.status_label.setText("执行完成（模拟）")
            panel.status_label.setStyleSheet("color: #008000;")
        
        loop.run_until_complete(run_mock())
    
    # 替换按钮点击事件
    panel.execute_btn.clicked.disconnect()
    panel.execute_btn.clicked.connect(lambda: mock_execute(
        panel.intent_input.toPlainText(),
        {}
    ))
    
    # 设置默认输入
    panel.intent_input.setPlainText("帮我查一下今天的天气，然后计算 2+2，最后总结")
    panel.context_input.setPlainText('{"user_location": "北京"}')
    
    layout.addWidget(panel)
    
    # 显示窗口
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
