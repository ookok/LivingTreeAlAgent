"""
管理员授权系统使用示例
Admin Authorization System Usage Examples

本文件展示如何使用管理员授权系统的各项功能。
"""

from core.admin_license_system import (
    get_author_config_manager,
    get_admin_auth,
    get_admin_manager,
    get_license_auth,
    Platform,
    AdminRole,
    AdminPermission,
)


def example_1_setup_author():
    """示例1: 配置作者信息（三端发布时）"""
    print("=" * 50)
    print("示例1: 配置作者信息")
    print("=" * 50)

    config_manager = get_author_config_manager()

    # 检查是否已有作者配置
    if config_manager.has_author_config():
        print(f"已有作者配置: {config_manager.get_author_info()}")
        return

    # 创建作者配置
    config = config_manager.create_author_config(
        name="沐歌科技",
        email="ceo@mogoo.com.cn",
        company="南京沐歌环保科技有限公司",
        website="https://mogoo.com.cn",
        phone="15951865326",
        license_type="enterprise",
        max_admins=100
    )
    print(f"作者配置创建成功: {config.author_info.author_id}")

    # 添加平台绑定（Windows）
    app_id, app_secret = config_manager.generate_author_credentials()
    config_manager.add_platform_binding(Platform.WINDOWS, app_id, app_secret)
    print(f"平台绑定创建成功: APP_ID={app_id}")

    # 导出构建配置
    build_config = config_manager.get_build_config(Platform.WINDOWS)
    print(f"构建配置: {build_config}")


def example_2_author_login():
    """示例2: 作者登录"""
    print("\n" + "=" * 50)
    print("示例2: 作者登录")
    print("=" * 50)

    auth = get_admin_auth()
    config_manager = get_author_config_manager()

    # 获取作者信息
    author_info = config_manager.get_author_info()
    if not author_info:
        print("请先配置作者信息")
        return

    # 作者登录（无需密码）
    result = auth.author_login(email=author_info.email)
    print(f"登录结果: {result.success}, {result.message}")

    if result.success:
        print(f"用户角色: {result.user.role}")
        print(f"是否作者: {result.user.is_author}")
        print(f"权限: {result.user.permissions}")


def example_3_admin_management():
    """示例3: 管理员管理"""
    print("\n" + "=" * 50)
    print("示例3: 管理员管理")
    print("=" * 50)

    auth = get_admin_auth()
    manager = get_admin_manager()

    # 先登录作者
    config_manager = get_author_config_manager()
    author_info = config_manager.get_author_info()
    if author_info:
        auth.author_login(email=author_info.email)

    # 检查是否可以添加管理员
    can_add, current, max_count, msg = manager.can_add_admin()
    print(f"管理员状态: {current}/{max_count}, 可添加: {can_add}")

    # 添加管理员
    result = manager.add_admin(
        username="admin001",
        password="password123",
        email="admin@mogoo.com.cn",
        display_name="系统管理员",
        role=AdminRole.ADMIN,
        created_by=auth.current_user.id if auth.current_user else ""
    )
    print(f"添加管理员: {result.success}, {result.message}")

    # 列出所有管理员
    all_admins = auth.get_all_admins()
    print(f"所有管理员: {len(all_admins)}")
    for admin in all_admins:
        print(f"  - {admin.username} ({admin.role})")


def example_4_generate_license():
    """示例4: 生成序列号（需管理员权限）"""
    print("\n" + "=" * 50)
    print("示例4: 生成序列号")
    print("=" * 50)

    auth = get_admin_auth()
    license_auth = get_license_auth()
    config_manager = get_author_config_manager()

    # 先登录作者
    author_info = config_manager.get_author_info()
    if author_info:
        auth.author_login(email=author_info.email)

    # 检查是否有权限生成序列号
    can_generate, reason = license_auth.can_generate_license()
    print(f"生成序列号权限: {can_generate}, {reason}")

    if can_generate:
        # 生成单个序列号
        success, msg, key = license_auth.generate_license_with_auth(
            version='PRO',
            expires_days=365,
            features=['basic_chat', 'advanced_ai'],
            max_users=1
        )
        print(f"生成结果: {success}, {msg}")
        if key:
            print(f"序列号: {key.key_string}")

        # 批量生成
        success, msg, batch = license_auth.generate_batch_with_auth(
            version='ENT',
            count=10,
            expires_days=365,
            features=['full_access'],
            max_users=5,
            batch_name="企业版测试批次"
        )
        print(f"批量生成: {success}, {msg}")


def example_5_regular_user_no_permission():
    """示例5: 普通用户无权限生成序列号"""
    print("\n" + "=" * 50)
    print("示例5: 普通用户权限测试")
    print("=" * 50)

    auth = get_admin_auth()
    manager = get_admin_manager()
    license_auth = get_license_auth()

    # 创建普通操作员账号（需要作者权限）
    config_manager = get_author_config_manager()
    author_info = config_manager.get_author_info()
    if author_info:
        auth.author_login(email=author_info.email)

        # 添加操作员
        result = manager.add_admin(
            username="operator001",
            password="password123",
            email="operator@mogoo.com.cn",
            display_name="操作员",
            role=AdminRole.OPERATOR
        )
        print(f"创建操作员: {result.success}")

    # 登出
    auth.logout()

    # 操作员尝试登录
    result = auth.login("operator001", "password123")
    print(f"操作员登录: {result.success}")

    if result.success:
        # 检查权限
        print(f"角色: {result.user.role}")
        print(f"是否可生成序列号: {result.user.can_generate_license()}")

        # 尝试生成序列号
        can_generate, reason = license_auth.can_generate_license()
        print(f"生成权限检查: {can_generate}, {reason}")


def example_6_audit_log():
    """示例6: 审计日志"""
    print("\n" + "=" * 50)
    print("示例6: 审计日志")
    print("=" * 50)

    manager = get_admin_manager()

    # 获取统计
    stats = manager.get_admin_stats()
    print(f"管理员统计: {stats}")

    # 获取审计日志
    logs = manager.get_audit_logs(limit=10)
    print(f"审计日志 ({len(logs)} 条):")
    for log in logs:
        print(f"  [{log.created_at}] {log.admin_username}: {log.action} - {log.details}")


def run_all_examples():
    """运行所有示例"""
    print("\n" + "#" * 60)
    print("# 管理员授权系统使用示例")
    print("#" * 60)

    try:
        example_1_setup_author()
        example_2_author_login()
        example_3_admin_management()
        example_4_generate_license()
        example_5_regular_user_no_permission()
        example_6_audit_log()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "#" * 60)
    print("# 示例运行完成")
    print("#" * 60)


if __name__ == "__main__":
    run_all_examples()