"""
新功能使用示例
展示 UI 自动化和推理模型的使用方法
"""

# ============================================================
# 1. UI 自动化 - 根据自然语言操作软件界面
# ============================================================

def ui_automation_example():
    """UI 自动化示例"""
    from client.src.business.system_brain import get_system_brain

    # 获取系统大脑
    brain = get_system_brain()

    # 执行 UI 操作
    result = brain.execute_ui_instruction("点击确定按钮")
    print(f"操作结果: {result}")

    # 分析当前屏幕
    analysis = brain.analyze_screen()
    print(f"屏幕分析: {analysis}")

    # 组合操作：分析 + 执行
    result = brain.analyze_ui_and_act("点击打开菜单")
    print(f"组合操作: {result}")


# ============================================================
# 2. 推理模型 - 使用 DeepSeek-R1 获取思考过程
# ============================================================

def reasoning_model_example():
    """推理模型示例"""
    from client.src.business.system_brain import get_system_brain

    brain = get_system_brain()

    # 方法1：使用系统大脑的增强生成
    def show_thinking(text):
        print(f"[思考] {text}", end="", flush=True)

    result = brain.generate_with_reasoning(
        prompt="为什么天空是蓝色的？",
        reasoning_callback=show_thinking
    )

    print(f"\n最终答案: {result['final_answer']}")
    print(f"思考过程: {result['reasoning']}")
    print(f"输入参数: {result['input_params']}")

    # 方法2：直接使用推理客户端
    from core.reasoning_client import create_reasoning_client

    client = create_reasoning_client(
        model_name="deepseek-r1:7b",
        base_url="http://localhost:11434"
    )

    # 连接并生成
    if client.connect():
        result = client.generate_with_retry(
            prompt="解释量子纠缠的原理",
            reasoning_callback=lambda x: print(f"[思考] {x}", end="")
        )

        print(f"\n答案: {result.final_answer}")
        print(f"耗时: {result.duration:.2f}s")

        # 查看连接统计
        stats = client.get_connection_stats()
        print(f"连接统计: {stats}")

    client.close()


# ============================================================
# 3. 推理分析 - 专业分析任务
# ============================================================

def reasoning_analyzer_example():
    """推理分析工具示例"""
    from core.reasoning_analyzer import get_reasoning_analyzer

    # 获取分析器
    analyzer = get_reasoning_analyzer(model_name="deepseek-r1:7b")

    # 示例1：分析情节漏洞
    text = """
    主角小明早上8点说要去北京出差，下午3点却出现在上海的酒吧里，
    没有解释他是怎么在7小时内从北京到上海的。
    """

    result = analyzer.analyze_plot_holes(text)

    print(f"任务: {result.task}")
    print(f"置信度: {result.confidence:.2f}")
    print(f"思考过程:\n{result.reasoning}")
    print(f"最终结论:\n{result.final_answer}")
    print(f"建议: {result.recommendations}")
    print(f"耗时: {result.duration:.2f}s")

    # 示例2：代码审查
    code = """
    def fibonacci(n):
        if n <= 1:
            return n
        return fibonacci(n-1) + fibonacci(n-2)
    """

    result = analyzer.review_code(code, language="python")

    print(f"\n代码审查结果:\n{result.final_answer}")

    # 示例3：决策支持
    result = analyzer.support_decision(
        question="应该选择 Python 还是 JavaScript 作为入门语言？",
        context="学习者是零基础，目标是快速找到工作"
    )

    print(f"\n决策分析:\n{result.final_answer}")

    analyzer.close()


# ============================================================
# 4. 系统大脑增强功能
# ============================================================

def system_brain_enhanced_example():
    """系统大脑增强功能示例"""
    from client.src.business.system_brain import get_system_brain

    brain = get_system_brain()

    # 检查是否为推理模型
    print(f"当前模型: {brain.current_model}")
    print(f"是否推理模型: {brain.is_reasoning_model()}")

    # 获取连接统计
    stats = brain.get_connection_stats()
    print(f"连接统计: {stats}")

    # 获取最优超时
    optimal = brain.get_optimal_timeout()
    print(f"最优超时: {optimal:.2f}s")

    # 使用 think 方法（思考问题）
    result = brain.think("如何提高代码质量？")

    print(f"\n思考结果:")
    print(f"答案: {result['answer']}")
    print(f"思考: {result['reasoning']}")
    print(f"置信度: {result['confidence']:.2f}")


# ============================================================
# 5. 连接超时重连机制
# ============================================================

def timeout_retry_example():
    """超时重连示例"""
    from core.reasoning_client import ReasoningModelClient, ReasoningConfig

    config = ReasoningConfig(
        model_name="deepseek-r1:7b",
        timeout=60.0,  # 初始超时
        connect_timeout=30.0,
        max_retries=3,
        retry_delay=2.0,
        track_connection_times=True
    )

    client = ReasoningModelClient(config)

    # 尝试连接
    if not client.connect():
        # 自动重连
        if client.reconnect():
            print("重连成功")
        else:
            print("重连失败")
            return

    # 生成（带自动重试）
    result = client.generate_with_retry(
        prompt="解释什么是机器学习",
        reasoning_callback=lambda x: print(f"[思考] {x}", end="")
    )

    print(f"\n生成成功: {result.success}")
    print(f"耗时: {result.duration:.2f}s")

    # 查看优化后的超时
    stats = client.get_connection_stats()
    print(f"优化后超时: {stats.get('optimal_timeout', 'N/A')}")

    client.close()


# ============================================================
# 运行所有示例
# ============================================================

if __name__ == "__main__":
    import sys

    # 确保 Ollama 正在运行
    print("=" * 60)
    print("UI 自动化与推理模型示例")
    print("=" * 60)

    # 1. UI 自动化示例
    print("\n[1] UI 自动化示例")
    print("-" * 40)
    try:
        ui_automation_example()
    except ImportError as e:
        print(f"需要安装依赖: {e}")
        print("运行: pip install mss pyautogui Pillow opencv-python")
    except Exception as e:
        print(f"UI 自动化示例: {e}")

    # 2. 推理模型示例
    print("\n[2] 推理模型示例")
    print("-" * 40)
    try:
        reasoning_model_example()
    except Exception as e:
        print(f"推理模型示例: {e}")

    # 3. 推理分析示例
    print("\n[3] 推理分析示例")
    print("-" * 40)
    try:
        reasoning_analyzer_example()
    except Exception as e:
        print(f"推理分析示例: {e}")

    # 4. 系统大脑增强
    print("\n[4] 系统大脑增强示例")
    print("-" * 40)
    try:
        system_brain_enhanced_example()
    except Exception as e:
        print(f"系统大脑示例: {e}")

    # 5. 超时重连
    print("\n[5] 超时重连示例")
    print("-" * 40)
    try:
        timeout_retry_example()
    except Exception as e:
        print(f"超时重连示例: {e}")

    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)
