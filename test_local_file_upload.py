"""
测试本地文件上传功能
Test Local File Upload Functionality
"""

import asyncio
import time
import os
from core.enterprise import get_enterprise_storage


def create_test_file():
    """创建测试文件"""
    test_content = b"This is a test file for local file upload"
    test_file_path = os.path.join(os.getcwd(), "test_local_file.txt")
    with open(test_file_path, "wb") as f:
        f.write(test_content)
    return test_file_path


def create_test_folder():
    """创建测试文件夹"""
    test_folder_path = os.path.join(os.getcwd(), "test_local_folder")
    os.makedirs(test_folder_path, exist_ok=True)
    # 在文件夹中创建一些文件
    for i in range(3):
        file_path = os.path.join(test_folder_path, f"file{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"Content of file {i}")
    return test_folder_path


async def test_local_file_upload():
    """测试本地文件上传功能"""
    print("=== 测试本地文件上传功能 ===")

    # 1. 初始化企业存储系统
    print("\n1. 初始化企业存储系统...")
    enterprise_id = "test_enterprise"
    node_id = f"node_{int(time.time())}"
    storage = get_enterprise_storage(enterprise_id, node_id)
    await storage.start()
    print(f"✓ 企业存储系统初始化成功 (Enterprise: {enterprise_id}, Node: {node_id})")

    # 2. 创建测试文件和文件夹
    print("\n2. 创建测试文件和文件夹...")
    test_file_path = create_test_file()
    test_folder_path = create_test_folder()
    print(f"✓ 创建测试文件: {test_file_path}")
    print(f"✓ 创建测试文件夹: {test_folder_path}")

    # 3. 获取根文件夹ID
    root_folder_id = storage.virtual_fs.root_folder_id
    print(f"\n3. 根文件夹ID: {root_folder_id}")

    # 4. 创建本地文件文件夹
    local_folder_id = await storage.create_folder("Local Files", root_folder_id, "user1")
    print(f"✓ 创建本地文件文件夹成功，ID: {local_folder_id}")

    # 5. 上传本地文件
    print("\n4. 上传本地文件...")
    file_id = await storage.upload_local_file(
        "test_local_file.txt", local_folder_id, test_file_path, "user1"
    )
    print(f"✓ 上传本地文件成功，ID: {file_id}")

    # 6. 上传本地文件夹
    print("\n5. 上传本地文件夹...")
    folder_id = await storage.upload_local_file(
        "test_local_folder", local_folder_id, test_folder_path, "user1"
    )
    print(f"✓ 上传本地文件夹成功，ID: {folder_id}")

    # 7. 列出本地文件文件夹内容
    print("\n6. 列出本地文件文件夹内容...")
    content = await storage.list_folder(local_folder_id)
    print(f"   文件夹内容:")
    print(f"   - 文件夹: {len(content['folders'])}")
    for folder in content['folders']:
        print(f"     - {folder['name']} (ID: {folder['id']})")
    print(f"   - 文件: {len(content['files'])}")
    for file in content['files']:
        print(f"     - {file['name']} (ID: {file['id']}, 大小: {file['size']} bytes)")

    # 8. 获取本地文件信息
    print("\n7. 获取本地文件信息...")
    file_info = await storage.get_item_info(file_id)
    if file_info:
        print(f"   文件 'test_local_file.txt' 信息:")
        print(f"   - 名称: {file_info['name']}")
        print(f"   - 大小: {file_info['size']} bytes")
        print(f"   - 类型: {file_info['mime_type']}")
        print(f"   - 路径: {file_info['path']}")
        print(f"   - 文件类型: {file_info['file_type']}")
        print(f"   - 本地路径: {file_info['local_path']}")
        print(f"   - 状态: {file_info['status']}")
    else:
        print(f"   获取文件信息失败")

    # 9. 下载本地文件
    print("\n8. 下载本地文件...")
    downloaded_content = await storage.download_file(file_id)
    if downloaded_content:
        print(f"   下载文件成功，大小: {len(downloaded_content)} bytes")
        print(f"   内容: {downloaded_content.decode()}")
    else:
        print(f"   下载文件失败")

    # 10. 下载本地文件夹
    print("\n9. 下载本地文件夹...")
    folder_content = await storage.download_file(folder_id)
    if folder_content:
        print(f"   下载文件夹成功，大小: {len(folder_content)} bytes")
        print(f"   内容: {folder_content.decode()}")
    else:
        print(f"   下载文件夹失败")

    # 11. 模拟本地文件修改
    print("\n10. 模拟本地文件修改...")
    time.sleep(2)  # 等待2秒，确保时间戳不同
    with open(test_file_path, "ab") as f:
        f.write(b"\nModified content")
    print(f"   修改本地文件: {test_file_path}")

    # 12. 等待监控检测到变化
    print("\n11. 等待监控检测到变化...")
    await asyncio.sleep(35)  # 等待监控检查

    # 13. 再次获取文件信息，检查状态变化
    print("\n12. 检查文件状态变化...")
    updated_file_info = await storage.get_item_info(file_id)
    if updated_file_info:
        print(f"   文件 'test_local_file.txt' 最新状态: {updated_file_info['status']}")
    else:
        print(f"   获取文件信息失败")

    # 14. 删除本地文件记录
    print("\n13. 删除本地文件记录...")
    delete_result = await storage.delete_file(file_id)
    if delete_result:
        print(f"   删除本地文件记录成功")
        # 验证文件是否仍然存在
        if os.path.exists(test_file_path):
            print(f"   实际本地文件仍然存在: {test_file_path}")
        else:
            print(f"   实际本地文件已被删除: {test_file_path}")
    else:
        print(f"   删除本地文件记录失败")

    # 15. 删除本地文件夹记录
    print("\n14. 删除本地文件夹记录...")
    delete_folder_result = await storage.delete_file(folder_id)
    if delete_folder_result:
        print(f"   删除本地文件夹记录成功")
        # 验证文件夹是否仍然存在
        if os.path.exists(test_folder_path):
            print(f"   实际本地文件夹仍然存在: {test_folder_path}")
        else:
            print(f"   实际本地文件夹已被删除: {test_folder_path}")
    else:
        print(f"   删除本地文件夹记录失败")

    # 16. 清理测试文件和文件夹
    print("\n15. 清理测试文件和文件夹...")
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"   删除测试文件: {test_file_path}")
    if os.path.exists(test_folder_path):
        import shutil
        shutil.rmtree(test_folder_path)
        print(f"   删除测试文件夹: {test_folder_path}")

    # 17. 停止系统
    print("\n16. 停止企业存储系统...")
    await storage.stop()
    print("✓ 企业存储系统停止成功")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_local_file_upload())
