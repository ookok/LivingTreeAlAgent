"""
智能客户端AI助手系统测试
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')


def test_knowledge_graph():
    """测试知识图谱"""
    print("\n=== 测试知识图谱 ===")
    
    from core.smart_assistant.knowledge_graph import get_knowledge_graph
    
    kg = get_knowledge_graph()
    
    # 测试统计
    stats = kg.get_stats()
    print(f"知识库统计: {stats}")
    
    # 测试查找页面
    pages = kg.find_pages("设置")
    print(f"查找「设置」相关页面: {[p.title for p in pages]}")
    
    # 测试查找操作路径
    paths = kg.find_operation_paths("配置模型")
    print(f"查找「配置模型」路径: {[p.name for p in paths]}")
    
    # 测试路由生成
    url = kg.generate_route_url("settings_model", highlight="api_key")
    print(f"生成路由URL: {url}")
    
    # 测试路由解析
    result = kg.resolve_route(url)
    if result:
        route, params = result
        print(f"解析路由: page={route.page_id}, params={params}")
    
    print("[PASS] 知识图谱测试通过")
    return True


def test_intent_recognizer():
    """测试意图识别器"""
    print("\n=== 测试意图识别器 ===")
    
    from core.smart_assistant.intent_recognizer import get_intent_recognizer
    from core.smart_assistant.models import IntentType
    
    recognizer = get_intent_recognizer()
    
    test_queries = [
        ("如何配置AI模型？", "操作指导"),
        ("设置页面在哪里？", "导航"),
        ("什么是MCP服务器？", "功能查询"),
        ("API密钥怎么填？", "配置帮助"),
        ("连接失败了怎么办？", "故障排查"),
    ]
    
    for query, expected_type in test_queries:
        result = recognizer.recognize(query)
        print(f"查询: 「{query}」")
        print(f"  识别意图: {result.primary_intent.name}")
        print(f"  置信度: {result.confidence:.0%}")
        print(f"  相关页面: {result.related_pages}")
        print()
    
    print("[PASS] 意图识别器测试通过")
    return True


def test_guide_system():
    """测试指引系统"""
    print("\n=== 测试指引系统 ===")
    
    from core.smart_assistant.guide_system import get_guide_system
    from core.smart_assistant.knowledge_graph import get_knowledge_graph
    
    guide_system = get_guide_system()
    kg = get_knowledge_graph()
    
    # 获取指引
    guides = kg.find_guide(tags=["新手"])
    if guides:
        guide = guides[0]
        print(f"找到指引: {guide.name}")
        print(f"步骤数: {len(guide.steps)}")
        
        # 开始指引
        guide_system.start_guide(guide)
        print(f"指引已启动: {guide_system.is_running()}")
        
        # 获取当前步骤
        current_step = guide_system.get_current_step()
        if current_step:
            print(f"当前步骤: {current_step.instruction}")
        
        # 渲染指引
        card = guide_system.render_step_card(current_step)
        print(f"步骤卡片:\n{card[:100]}...")
        
        # 完成步骤
        next_step = guide_system.next_step(success=True)
        if next_step:
            print(f"下一步: {next_step.instruction[:50]}...")
        
        # 渲染进度
        progress = guide_system.get_progress()
        print(f"进度: {progress['completion_rate']:.0%}")
        
        # 中止指引
        guide_system.abort_guide()
        print("指引已中止")
    
    print("[PASS] 指引系统测试通过")
    return True


def test_smart_assistant():
    """测试智能助手"""
    print("\n=== 测试智能助手 ===")
    
    from core.smart_assistant import get_smart_assistant
    
    assistant = get_smart_assistant()
    
    test_queries = [
        "如何配置模型？",
        "打开设置页面",
        "MCP是什么？",
        "连接失败了",
    ]
    
    for query in test_queries:
        print(f"\n查询: 「{query}」")
        response = assistant.chat(query)
        
        print(f"置信度: {response.confidence:.0%}")
        print(f"导航成功: {response.navigation.success}")
        print(f"显示指引: {response.show_guide}")
        print(f"响应预览:\n{response.text[:150]}...")
    
    # 测试导航
    print("\n测试路由导航:")
    success = assistant.process_link("app://settings/model")
    print(f"导航到 model 配置页: {success}")
    
    # 测试统计
    print("\n系统统计:")
    stats = assistant.get_stats()
    print(f"页面数: {stats['knowledge_base']['total_pages']}")
    print(f"指引数: {stats['guide_system']['total_guides']}")
    
    print("[PASS] 智能助手测试通过")
    return True


def main():
    """主测试函数"""
    print("=" * 50)
    print("智能客户端AI助手系统测试")
    print("=" * 50)
    
    results = []
    
    results.append(("知识图谱", test_knowledge_graph()))
    results.append(("意图识别器", test_intent_recognizer()))
    results.append(("指引系统", test_guide_system()))
    results.append(("智能助手", test_smart_assistant()))
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("🎉 所有测试通过!")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
