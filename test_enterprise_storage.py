"""
测试企业虚拟网盘系统
Test Enterprise Storage System
"""

import asyncio
import time
from core.enterprise import get_enterprise_storage


def generate_test_content(size: int) -> bytes:
    """生成测试内容"""
    return b"A" * size


async def test_enterprise_storage():
    """测试企业存储系统"""
    print("=== 测试企业虚拟网盘系统 ===")

    # 1. 初始化企业存储系统
    print("\n1. 初始化企业存储系统...")
    enterprise_id = "test_enterprise"
    node_id = f"node_{int(time.time())}"
    storage = get_enterprise_storage(enterprise_id, node_id)
    await storage.start()
    print(f"✓ 企业存储系统初始化成功 (Enterprise: {enterprise_id}, Node: {node_id})")

    # 2. 获取统计信息
    stats = storage.get_stats()
    print(f"\n2. 系统统计信息:")
    print(f"   企业ID: {stats['enterprise_id']}")
    print(f"   节点ID: {stats['node_id']}")
    print(f"   总节点数: {stats['total_nodes']}")
    print(f"   在线节点数: {stats['online_nodes']}")
    print(f"   总存储空间: {stats['total_storage'] / (1024 * 1024 * 1024):.2f} GB")
    print(f"   已使用存储空间: {stats['used_storage'] / (1024 * 1024 * 1024):.2f} GB")

    # 3. 创建文件夹
    print("\n3. 创建文件夹...")
    root_folder_id = storage.virtual_fs.root_folder_id
    print(f"   根文件夹ID: {root_folder_id}")

    # 创建测试文件夹
    folder1_id = await storage.create_folder("Documents", root_folder_id, "user1")
    print(f"   创建文件夹 'Documents' 成功，ID: {folder1_id}")

    folder2_id = await storage.create_folder("Images", root_folder_id, "user1")
    print(f"   创建文件夹 'Images' 成功，ID: {folder2_id}")

    # 4. 上传文件
    print("\n4. 上传文件...")

    # 上传文档文件
    doc_content = generate_test_content(1024 * 100)  # 100KB
    doc_file_id = await storage.upload_file(
        "report.txt", folder1_id, doc_content, "text/plain", "user1"
    )
    print(f"   上传文件 'report.txt' 成功，ID: {doc_file_id}")

    # 上传图片文件
    img_content = generate_test_content(1024 * 200)  # 200KB
    img_file_id = await storage.upload_file(
        "photo.jpg", folder2_id, img_content, "image/jpeg", "user1"
    )
    print(f"   上传文件 'photo.jpg' 成功，ID: {img_file_id}")

    # 5. 列出文件夹内容
    print("\n5. 列出文件夹内容...")

    # 列出根文件夹
    root_content = await storage.list_folder(root_folder_id)
    print(f"   根文件夹内容:")
    print(f"   - 文件夹: {len(root_content['folders'])}")
    for folder in root_content['folders']:
        print(f"     - {folder['name']} (ID: {folder['id']})")
    print(f"   - 文件: {len(root_content['files'])}")

    # 列出Documents文件夹
    doc_content = await storage.list_folder(folder1_id)
    print(f"   Documents文件夹内容:")
    print(f"   - 文件夹: {len(doc_content['folders'])}")
    print(f"   - 文件: {len(doc_content['files'])}")
    for file in doc_content['files']:
        print(f"     - {file['name']} (ID: {file['id']}, 大小: {file['size']} bytes)")

    # 6. 下载文件
    print("\n6. 下载文件...")
    downloaded_content = await storage.download_file(doc_file_id)
    if downloaded_content:
        print(f"   下载文件 'report.txt' 成功，大小: {len(downloaded_content)} bytes")
        print(f"   内容匹配: {downloaded_content == doc_content}")
    else:
        print(f"   下载文件 'report.txt' 失败")

    # 7. 获取文件信息
    print("\n7. 获取文件信息...")
    file_info = await storage.get_item_info(doc_file_id)
    if file_info:
        print(f"   文件 'report.txt' 信息:")
        print(f"   - 名称: {file_info['name']}")
        print(f"   - 大小: {file_info['size']} bytes")
        print(f"   - 类型: {file_info['mime_type']}")
        print(f"   - 路径: {file_info['path']}")
        print(f"   - 副本数: {len(file_info['replicas'])}")
    else:
        print(f"   获取文件信息失败")

    # 8. 搜索文件
    print("\n8. 搜索文件...")
    search_results = await storage.search("report")
    print(f"   搜索 'report' 结果 ({len(search_results)} 项):")
    for result in search_results:
        print(f"   - {result['name']} (类型: {result['type']}, 路径: {result['path']})")

    # 9. 移动文件
    print("\n9. 移动文件...")
    move_result = await storage.move_item(doc_file_id, folder2_id, "moved_report.txt")
    if move_result:
        print(f"   移动文件 'report.txt' 到 'Images' 文件夹并重命名为 'moved_report.txt' 成功")
        # 验证移动结果
        folder2_content = await storage.list_folder(folder2_id)
        print(f"   Images文件夹现在包含 {len(folder2_content['files'])} 个文件")
    else:
        print(f"   移动文件失败")

    # 10. 删除文件
    print("\n10. 删除文件...")
    delete_result = await storage.delete_file(img_file_id)
    if delete_result:
        print(f"   删除文件 'photo.jpg' 成功")
        # 验证删除结果
        folder2_content = await storage.list_folder(folder2_id)
        print(f"   Images文件夹现在包含 {len(folder2_content['files'])} 个文件")
    else:
        print(f"   删除文件失败")

    # 11. 删除文件夹
    print("\n11. 删除文件夹...")
    # 先删除文件夹内的文件
    for file in folder2_content['files']:
        await storage.delete_file(file['id'])
        print(f"   删除文件 '{file['name']}' 成功")
    
    # 删除文件夹
    delete_folder_result = await storage.delete_folder(folder2_id)
    if delete_folder_result:
        print(f"   删除文件夹 'Images' 成功")
        # 验证删除结果
        root_content = await storage.list_folder(root_folder_id)
        print(f"   根文件夹现在包含 {len(root_content['folders'])} 个文件夹")
    else:
        print(f"   删除文件夹失败")

    # 12. 最终统计信息
    print("\n12. 最终统计信息:")
    final_stats = storage.get_stats()
    print(f"   总文件数: {final_stats.get('total_files', 0)}")
    print(f"   总文件夹数: {final_stats.get('total_folders', 0)}")
    print(f"   存储使用: {final_stats['used_storage'] / (1024 * 1024):.2f} MB")

    # 13. 停止系统
    print("\n13. 停止企业存储系统...")
    await storage.stop()
    print("✓ 企业存储系统停止成功")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_enterprise_storage())
