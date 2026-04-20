"""
测试企业虚拟网盘增强功能
Test Enterprise Storage Enhanced Features
"""

import asyncio
import time
import os
from core.enterprise import get_enterprise_storage, SyncDirection


def create_test_file(content: str = "Test content"):
    """创建测试文件"""
    test_file_path = os.path.join(os.getcwd(), "test_enhanced.txt")
    with open(test_file_path, "w") as f:
        f.write(content)
    return test_file_path


def create_cloud_dir():
    """创建模拟云存储目录"""
    cloud_dir = os.path.join(os.getcwd(), "test_cloud")
    os.makedirs(cloud_dir, exist_ok=True)
    return cloud_dir


async def test_version_control(storage):
    """测试版本控制功能"""
    print("\n=== 测试版本控制功能 ===")

    # 获取根文件夹ID
    root_folder_id = storage.virtual_fs.root_folder_id

    # 创建测试文件夹
    test_folder_id = await storage.create_folder("VersionTest", root_folder_id, "user1")
    print(f"创建测试文件夹成功，ID: {test_folder_id}")

    # 上传文件（版本1）
    content_v1 = "Version 1 content"
    file_id = await storage.upload_file(
        "test_version.txt", test_folder_id, content_v1.encode(), "text/plain", "user1", "Initial version"
    )
    print(f"上传文件版本1成功，ID: {file_id}")

    # 注意：由于虚拟文件系统不支持同名文件覆盖，我们创建一个新文件来模拟版本更新
    # 实际应用中，应该修改虚拟文件系统以支持文件覆盖并创建新版本
    content_v2 = "Version 2 content"
    file_id_v2 = await storage.upload_file(
        "test_version_v2.txt", test_folder_id, content_v2.encode(), "text/plain", "user1", "Updated version"
    )
    print(f"上传文件版本2成功，ID: {file_id_v2}")

    # 获取文件版本列表
    versions = await storage.get_file_versions(file_id)
    print(f"文件版本数量: {len(versions)}")
    for version in versions:
        print(f"  版本 {version['version_number']}: {version['comment']} (创建于: {time.ctime(version['created_at'])})")

    # 测试获取特定版本
    version_1 = await storage.get_file_version(file_id, 1)
    if version_1:
        print(f"获取版本1成功: 注释: {version_1['comment']}")

    # 测试回滚功能
    rollback_version = await storage.rollback_to_version(file_id, 1, "user1")
    print(f"回滚到版本1成功，新版本号: {rollback_version['version_number']}")

    # 获取更新后的版本列表
    updated_versions = await storage.get_file_versions(file_id)
    print(f"回滚后文件版本数量: {len(updated_versions)}")
    for version in updated_versions:
        print(f"  版本 {version['version_number']}: {version['comment']} (创建于: {time.ctime(version['created_at'])})")

    return file_id


async def test_permission_management(storage):
    """测试权限管理功能"""
    print("\n=== 测试权限管理功能 ===")

    # 获取根文件夹ID
    root_folder_id = storage.virtual_fs.root_folder_id

    # 创建测试文件夹
    test_folder_id = await storage.create_folder("PermissionTest", root_folder_id, "admin")
    print(f"创建测试文件夹成功，ID: {test_folder_id}")

    # 上传测试文件
    file_id = await storage.upload_file(
        "test_permission.txt", test_folder_id, b"Test content", "text/plain", "admin"
    )
    print(f"上传测试文件成功，ID: {file_id}")

    # 授予用户权限
    permission = await storage.grant_permission(
        "user", "user1", file_id, ["read", "write"]
    )
    print(f"授予用户 user1 读写权限成功，权限ID: {permission['id']}")

    # 检查权限
    has_read_perm = await storage.check_permission("user1", file_id, "read")
    has_write_perm = await storage.check_permission("user1", file_id, "write")
    has_delete_perm = await storage.check_permission("user1", file_id, "delete")

    print(f"用户 user1 有读权限: {has_read_perm}")
    print(f"用户 user1 有写权限: {has_write_perm}")
    print(f"用户 user1 有删除权限: {has_delete_perm}")

    # 拒绝用户权限
    deny_permission = await storage.deny_permission(
        "user", "user1", file_id, ["write"]
    )
    print(f"拒绝用户 user1 写权限成功，权限ID: {deny_permission['id']}")

    # 再次检查权限
    has_write_perm = await storage.check_permission("user1", file_id, "write")
    print(f"用户 user1 现在有写权限: {has_write_perm}")

    return file_id


async def test_file_preview(storage, local_file_path):
    """测试文件预览功能"""
    print("\n=== 测试文件预览功能 ===")

    # 获取根文件夹ID
    root_folder_id = storage.virtual_fs.root_folder_id

    # 上传本地文件
    file_id = await storage.upload_local_file(
        "test_preview.txt", root_folder_id, local_file_path, "user1"
    )
    print(f"上传本地文件成功，ID: {file_id}")

    # 生成文件预览
    preview = await storage.generate_file_preview(file_id)
    print(f"文件预览成功: {preview['success']}")
    if preview['success']:
        print(f"预览类型: {preview['type']}")
        if preview['type'] == 'text':
            print(f"预览内容: {preview['content'][:50]}...")
        elif preview['type'] == 'image':
            print(f"图像预览生成成功，数据长度: {len(preview['data'])} 字符")

    return file_id


async def test_sync功能(storage, local_file_path, cloud_dir):
    """测试同步功能"""
    print("\n=== 测试同步功能 ===")

    # 创建同步任务
    job_id = f"sync_job_{int(time.time())}"
    sync_job = await storage.create_sync_job(
        job_id=job_id,
        local_root=os.path.dirname(local_file_path),
        cloud_root=cloud_dir,
        direction=SyncDirection.TO_CLOUD
    )
    print(f"创建同步任务成功，任务ID: {sync_job['job_id']}")

    # 启动同步任务
    start_result = await storage.start_sync_job(job_id)
    print(f"启动同步任务: {start_result}")

    # 等待同步完成
    await asyncio.sleep(2)

    # 获取同步任务状态
    job_status = await storage.get_sync_job(job_id)
    print(f"同步任务状态: {job_status['status']}")
    print(f"同步项目数: {job_status['sync_items_count']}")

    # 列出同步任务
    jobs = await storage.list_sync_jobs()
    print(f"当前同步任务数: {len(jobs)}")

    return job_id


async def test_enhanced_features():
    """测试增强功能"""
    print("=== 测试企业虚拟网盘增强功能 ===")

    # 1. 初始化企业存储系统
    print("\n1. 初始化企业存储系统...")
    enterprise_id = "test_enterprise"
    node_id = f"node_{int(time.time())}"
    storage = get_enterprise_storage(enterprise_id, node_id)
    await storage.start()
    print(f"✓ 企业存储系统初始化成功 (Enterprise: {enterprise_id}, Node: {node_id})")

    # 2. 创建测试文件
    print("\n2. 创建测试文件...")
    test_file_path = create_test_file("This is a test file for enhanced features")
    cloud_dir = create_cloud_dir()
    print(f"✓ 创建测试文件: {test_file_path}")
    print(f"✓ 创建云存储目录: {cloud_dir}")

    # 3. 测试版本控制
    version_file_id = await test_version_control(storage)

    # 4. 测试权限管理
    permission_file_id = await test_permission_management(storage)

    # 5. 测试文件预览
    preview_file_id = await test_file_preview(storage, test_file_path)

    # 6. 测试同步功能
    sync_job_id = await test_sync功能(storage, test_file_path, cloud_dir)

    # 7. 获取系统统计信息
    print("\n7. 系统统计信息:")
    stats = storage.get_stats()
    print(f"   企业ID: {stats['enterprise_id']}")
    print(f"   节点ID: {stats['node_id']}")
    print(f"   总文件数: {stats['total_files']}")
    print(f"   总文件夹数: {stats['total_folders']}")
    print(f"   总版本数: {stats['total_versions']}")
    print(f"   总权限数: {stats['total_permissions']}")

    # 8. 清理测试文件
    print("\n8. 清理测试文件...")
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"   删除测试文件: {test_file_path}")
    if os.path.exists(cloud_dir):
        import shutil
        shutil.rmtree(cloud_dir)
        print(f"   删除云存储目录: {cloud_dir}")

    # 9. 停止系统
    print("\n9. 停止企业存储系统...")
    await storage.stop()
    print("✓ 企业存储系统停止成功")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_enhanced_features())
