"""
共脑系统 Demo 启动脚本

使用方法：
1. 模拟演示（无需模型）：python launch_streaming_demo.py --demo
2. 真实执行（需要模型）：python launch_streaming_demo.py
"""

import sys
import argparse
from PyQt6.QtWidgets import QApplication

def main():
    parser = argparse.ArgumentParser(description="共脑系统 Demo")
    parser.add_argument("--demo", action="store_true", help="使用模拟数据")
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用 Fusion 样式
    
    if args.demo:
        # 模拟演示模式
        print("启动模拟演示模式...")
        from client.src.presentation.panels.streaming_thought_demo_panel import (
            StreamingThoughtDemoPanel
        )
        
        window = QWidget()
        window.setWindowTitle("共脑系统 Demo（模拟模式）")
        window.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(window)
        
        panel = StreamingThoughtDemoPanel()
        
        # 替换为模拟执行
        def mock_execute(intent, context):
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
            panel.demo_btn.setEnabled(False)
            
            # 模拟数据
            demo_thoughts = panel.demo_thoughts
            demo_actions = panel.demo_actions
            demo_final = panel.demo_final
            
            # 使用 QTimer 逐步显示
            step_index = 0
            steps = []
            
            # 添加思考步骤
            for thought in demo_thoughts:
                steps.append({"type": "thought", "content": thought + "\n"})
            
            # 添加动作步骤
            for action in demo_actions:
                steps.append({"type": "action", "data": action})
            
            # 添加最终步骤
            steps.append({"type": "final", "data": demo_final})
            
            def do_step():
                nonlocal step_index
                if step_index >= len(steps):
                    # 完成
                    panel.execute_btn.setEnabled(True)
                    panel.demo_btn.setEnabled(True)
                    panel.progress_bar.setVisible(False)
                    panel.status_label.setText("模拟演示完成")
                    panel.status_label.setStyleSheet("color: #008000;")
                    return
                
                step = steps[step_index]
                step_type = step["type"]
                
                if step_type == "thought":
                    panel._append_thought(step["content"])
                elif step_type == "action":
                    data = step["data"]
                    panel._append_action(
                        data["type"],
                        data["status"],
                        data.get("result", ""),
                        data.get("error", "")
                    )
                elif step_type == "final":
                    panel._show_final_result(step["data"])
                
                step_index += 1
                QTimer.singleShot(800, do_step)  # 800ms 后执行下一步
            
            # 启动
            QTimer.singleShot(100, do_step)
        
        # 替换按钮事件
        panel.execute_btn.clicked.disconnect()
        panel.execute_btn.clicked.connect(lambda: mock_execute(
            panel.intent_input.toPlainText(),
            {}
        ))
        
        panel.demo_btn.clicked.disconnect()
        panel.demo_btn.clicked.connect(lambda: mock_execute(
            "模拟意图",
            {}
        ))
        
        # 设置默认输入
        panel.intent_input.setPlainText("帮我查一下今天的天气，然后计算 2+2，最后总结")
        panel.context_input.setPlainText('{"user_location": "北京"}')
        
        layout.addWidget(panel)
        window.show()
    
    else:
        # 真实执行模式
        print("启动真实执行模式...")
        print("注意：需要确保模型路由器已配置")
        
        from client.src.presentation.panels.streaming_thought_demo_panel import (
            StreamingThoughtDemoWindow
        )
        
        window = StreamingThoughtDemoWindow()
        window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
