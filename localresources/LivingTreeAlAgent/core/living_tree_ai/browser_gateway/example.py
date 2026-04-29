"""
浏览器网关使用示例
================

演示如何构建"双向协议网关"
"""

import asyncio
from pathlib import Path

# 导入浏览器网关
from browser_gateway import (
    BrowserGateway,
    create_browser_gateway,
    HyperOSProtocol,
    parse_hyperos_uri,
    node_status_uri,
    send_mail_uri,
    search_uri,
    OfflineMirror,
    CSSRewriter,
    ThemeType,
    CrawlerDispatcher,
    SelectorRule,
)


async def example_protocol_handling():
    """示例：协议处理"""
    print("\n" + "="*60)
    print("🌐 示例1: hyperos:// 协议处理")
    print("="*60)

    gateway = create_browser_gateway()

    # 测试 URI 解析
    test_uris = [
        "hyperos://node/alice@laptop-001/status",
        "hyperos://mail/send?to=bob&subject=Hello",
        "hyperos://content/abc123def456",
        "hyperos://cid/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
        "hyperos://search?q=distributed+AI",
    ]

    for uri in test_uris:
        parsed = parse_hyperos_uri(uri)
        if parsed:
            print(f"\n📌 URI: {uri}")
            print(f"   路径: {parsed.path}")
            print(f"   操作: {parsed.action}")
            print(f"   参数: {parsed.params}")

    # 协议处理器
    print("\n📋 已注册协议:")
    for p in gateway.get_protocols():
        print(f"   - {p['protocol']}: {p['description']}")


async def example_javascript_injection():
    """示例：JavaScript 注入"""
    print("\n" + "="*60)
    print("💉 示例2: window.hyperos 注入脚本")
    print("="*60)

    gateway = create_browser_gateway()

    # 生成注入脚本
    script = gateway.generate_injection_script()

    print("\n📋 注入脚本长度:", len(script), "字符")
    print("\n核心 API:")
    print("""
    window.hyperos.getNodeStatus()      // 获取节点状态
    window.hyperos.sendMail(to, subject, content)  // 发送邮件
    window.hyperos.getMails(limit)      // 获取邮件
    window.hyperos.search(query)        // 统一搜索
    window.hyperos.open(url)             // 打开内部内容
    window.hyperos.publishToForum(title, content, tags)  // 发布到论坛
    """)

    # CSP 头
    print("\n🔒 Content Security Policy:")
    print(f"   {gateway.get_csp_header()}")


async def example_offline_mirror():
    """示例：离线镜像"""
    print("\n" + "="*60)
    print("📦 示例3: 离线镜像")
    print("="*60)

    mirror = OfflineMirror(Path.home() / ".hermes-desktop" / "demo" / "offline_mirror")

    # 镜像 URL
    print("\n🌐 镜像网页...")
    snapshot = await mirror.mirror_url("https://example.com")

    if snapshot:
        print(f"\n✅ 镜像成功!")
        print(f"   CID: {snapshot.cid}")
        print(f"   标题: {snapshot.title}")
        print(f"   大小: {len(snapshot.content)} 字节")
        print(f"   提取文本: {snapshot.text_content[:100]}...")

    # 统计数据
    stats = await mirror.get_mirror_stats()
    print(f"\n📊 镜像统计:")
    print(f"   总镜像数: {stats['total_mirrors']}")
    print(f"   总大小: {stats['total_size_mb']:.2f} MB")


async def example_css_rewriter():
    """示例：CSS 重写引擎"""
    print("\n" + "="*60)
    print("🎨 示例4: CSS 重写引擎")
    print("="*60)

    rewriter = CSSRewriter(Path.home() / ".hermes-desktop" / "demo" / "css_rewriter")

    # 添加自定义规则
    print("\n➕ 添加自定义规则...")
    rule_id = rewriter.add_rule(
        domain="github.com",
        selector=".header",
        styles="background-color: #0d1117 !important;",
        theme=ThemeType.CUSTOM
    )
    print(f"   规则 ID: {rule_id}")

    # 应用预设主题
    print("\n🎭 应用深夜模式到 github.com...")
    rewriter.apply_builtin_theme("github.com", ThemeType.DARK)

    # 生成注入脚本
    script = rewriter.get_injection_script("github.com")
    print(f"\n📋 注入脚本长度: {len(script)} 字符")

    # 列出规则
    print("\n📜 github.com 的 CSS 规则:")
    rules = rewriter.list_rules("github.com")
    for rule in rules[:5]:
        print(f"   [{rule['theme']}] {rule['selector']}: {rule['styles'][:50]}...")


async def example_crawler_dispatcher():
    """示例：爬虫调度器"""
    print("\n" + "="*60)
    print("🕷️ 示例5: 爬虫调度器")
    print("="*60)

    dispatcher = CrawlerDispatcher(
        Path.home() / ".hermes-desktop" / "demo" / "crawler"
    )

    # 创建爬取任务
    print("\n📝 创建爬取任务...")
    task_id = dispatcher.create_task(
        name="科技新闻监控",
        url="https://news.example.com/tech",
        selectors=[
            SelectorRule(name="标题", selector="h2.title", extract_type="text"),
            SelectorRule(name="链接", selector="h2.title a", extract_type="attr", attribute="href"),
            SelectorRule(name="摘要", selector="p.summary", extract_type="text"),
        ],
        interval_hours=6,  # 每6小时爬取一次
        sink_type=DataSinkType.EMAIL,
        sink_config={"to": "alice@local"}
    )
    print(f"   任务 ID: {task_id}")

    # 列出任务
    print("\n📋 爬取任务列表:")
    tasks = dispatcher.list_tasks()
    for task in tasks:
        print(f"   [{task['status']}] {task['name']} - {task['url']}")
        print(f"           间隔: {task['interval_hours']}h, 下次: {task['next_run']}")


async def example_builtin_hyperos_links():
    """示例：内置 hyperos:// 链接"""
    print("\n" + "="*60)
    print("🔗 示例6: 内置 hyperos:// 链接生成")
    print("="*60)

    print("\n📌 生成常用链接:")

    # 节点状态
    uri = node_status_uri("alice@laptop-001")
    print(f"   节点状态: {uri}")

    # 发送邮件
    uri = send_mail_uri("bob@desktop", "项目更新", "今天的进度...")
    print(f"   发送邮件: {uri}")

    # 搜索
    uri = search_uri("分布式系统 设计")
    print(f"   搜索: {uri}")

    # 在 HTML 中使用
    print("\n📄 HTML 链接示例:")
    html = f'''
    <a href="{node_status_uri("alice@laptop-001")}">查看节点状态</a>
    <a href="{send_mail_uri("bob@desktop", "你好")}">发邮件给 Bob</a>
    '''
    print(html)


async def example_full_workflow():
    """示例：完整工作流"""
    print("\n" + "="*60)
    print("🚀 示例7: 完整工作流 - 浏览器作为双向网关")
    print("="*60)

    print("""
    场景：用户在外部博客看到一篇技术文章，想同步到内部论坛

    步骤：
    """)

    gateway = create_browser_gateway()

    # 1. 用户在博客页面点击"同步到内部"
    print("""
    1️⃣ 用户点击博客上的"同步到内部"按钮
       → 调用 window.hyperos.publishToForum()
    """)

    # 2. 网页脚本通过 RPC 调用
    script = '''
    window.hyperos.publishToForum(
        "分布式系统设计原则",
        "本文介绍了微服务的核心设计原则...",
        ["微服务", "架构", "翻译"]
    ).then(result => {
        console.log("已发布到内部论坛:", result.post_id);
    });
    '''
    print(f"    2️⃣ RPC 调用:\n{script}")

    # 3. 内容被存储并索引
    print("""
    3️⃣ 客户端处理:
       → 解析 RPC 请求
       → 内容存入本地存储
       → 生成 CID: QmXoypizjW3WknFiJnKLw...
       → 索引到知识图谱
       → 发送通知邮件
    """)

    # 4. 生成永恒链接
    cid_uri = "hyperos://cid/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
    print(f"    4️⃣ 生成永恒链接: {cid_uri}")
    print("       → 任何节点可通过此 CID 访问内容")

    # 5. CSS 重写实现视觉统一
    print("""
    5️⃣ CSS 重写:
       → 博客应用"内部主题"皮肤
       → 保持与企业风格一致
    """)


async def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("🧠 浏览器网关演示 - 双向协议网关")
    print("="*60)

    await example_protocol_handling()
    await example_javascript_injection()
    await example_offline_mirror()
    await example_css_rewriter()
    await example_crawler_dispatcher()
    await example_builtin_hyperos_links()
    await example_full_workflow()

    print("\n" + "="*60)
    print("✨ 所有演示完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())