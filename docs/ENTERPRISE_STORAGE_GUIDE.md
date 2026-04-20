# 企业虚拟网盘系统使用指南

## 1. 系统概述

企业虚拟网盘系统是基于P2P CDN技术实现的分布式存储系统，专为企业内部使用设计。系统允许企业内的多个节点贡献存储空间，形成一个统一的虚拟网盘，支持类似文件夹的可视化管理方式。

### 核心功能

- **分布式存储**：企业内多个节点贡献存储空间，形成统一的虚拟存储池
- **文件夹式管理**：支持创建、删除、移动文件夹和文件，提供类似传统文件系统的使用体验
- **数据冗余**：自动在多个节点上创建数据副本，提高数据可靠性
- **智能路由**：基于网络延迟和节点能力选择最优存储节点
- **安全访问**：支持文件权限管理，确保数据安全

## 2. 快速开始

### 2.1 初始化企业存储系统

```python
from core.enterprise import get_enterprise_storage
import asyncio

async def main():
    # 初始化企业存储系统
    enterprise_id = "your_enterprise"
    node_id = "node_1"
    storage = get_enterprise_storage(enterprise_id, node_id)
    
    # 启动系统
    await storage.start()
    print("企业存储系统启动成功")
    
    # 获取系统状态
    stats = storage.get_stats()
    print(f"系统状态: {stats}")
    
    # 停止系统
    await storage.stop()
    print("企业存储系统停止成功")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2.2 基本操作

#### 创建文件夹

```python
# 获取根文件夹ID
root_folder_id = storage.virtual_fs.root_folder_id

# 创建文件夹
folder_id = await storage.create_folder("Documents", root_folder_id, "user1")
print(f"创建文件夹成功，ID: {folder_id}")
```

#### 上传文件

```python
# 准备文件内容
content = b"Hello, Enterprise Storage!"

# 上传文件
file_id = await storage.upload_file(
    "example.txt", folder_id, content, "text/plain", "user1"
)
print(f"上传文件成功，ID: {file_id}")
```

#### 下载文件

```python
# 下载文件
content = await storage.download_file(file_id)
if content:
    print(f"下载文件成功，大小: {len(content)} bytes")
    print(f"内容: {content.decode()}")
else:
    print("下载文件失败")
```

#### 列出文件夹内容

```python
# 列出文件夹内容
content = await storage.list_folder(folder_id)
print(f"文件夹内容:")
print(f"- 文件夹: {len(content['folders'])}")
for folder in content['folders']:
    print(f"  - {folder['name']} (ID: {folder['id']})")
print(f"- 文件: {len(content['files'])}")
for file in content['files']:
    print(f"  - {file['name']} (ID: {file['id']}, 大小: {file['size']} bytes)")
```

#### 删除文件

```python
# 删除文件
success = await storage.delete_file(file_id)
if success:
    print("删除文件成功")
else:
    print("删除文件失败")
```

#### 删除文件夹

```python
# 删除文件夹（注意：文件夹必须为空）
success = await storage.delete_folder(folder_id)
if success:
    print("删除文件夹成功")
else:
    print("删除文件夹失败")
```

## 3. 系统架构

### 3.1 核心组件

| 组件 | 功能 | 文件位置 |
|------|------|----------|
| 节点管理器 | 管理企业内的节点，负责节点发现和资源分配 | `core/enterprise/node_manager.py` |
| 虚拟文件系统 | 实现文件和文件夹的管理，提供类似传统文件系统的接口 | `core/enterprise/virtual_filesystem.py` |
| 企业存储 | 整合P2P CDN和虚拟文件系统，提供完整的存储服务 | `core/enterprise/storage.py` |

### 3.2 数据流程

1. **文件上传**：
   - 创建虚拟文件记录
   - 选择存储节点
   - 将文件数据存储到P2P CDN
   - 更新文件元数据

2. **文件下载**：
   - 根据文件ID获取文件元数据
   - 从P2P CDN获取文件数据
   - 返回文件内容

3. **文件管理**：
   - 文件夹操作：创建、删除、移动
   - 文件操作：上传、下载、删除、移动
   - 搜索和查询

## 4. 高级功能

### 4.1 节点管理

```python
# 获取节点管理器
from core.enterprise import get_enterprise_manager

node_manager = get_enterprise_manager("your_enterprise")

# 获取节点列表
nodes = node_manager.get_nodes(status="online")
print(f"在线节点数: {len(nodes)}")

# 获取节点统计信息
stats = node_manager.get_stats()
print(f"节点统计: {stats}")
```

### 4.2 搜索功能

```python
# 搜索文件和文件夹
results = await storage.search("report")
print(f"搜索结果 ({len(results)} 项):")
for result in results:
    print(f"- {result['name']} (类型: {result['type']}, 路径: {result['path']})")
```

### 4.3 文件信息查询

```python
# 获取文件信息
file_info = await storage.get_item_info(file_id)
if file_info:
    print(f"文件信息:")
    print(f"- 名称: {file_info['name']}")
    print(f"- 大小: {file_info['size']} bytes")
    print(f"- 类型: {file_info['mime_type']}")
    print(f"- 路径: {file_info['path']}")
    print(f"- 副本数: {len(file_info['replicas'])}")
    print(f"- 校验和: {file_info['checksum']}")
```

### 4.4 移动文件

```python
# 移动文件到新文件夹
new_folder_id = await storage.create_folder("Archive", root_folder_id, "user1")
success = await storage.move_item(file_id, new_folder_id, "archived_report.txt")
if success:
    print("移动文件成功")
else:
    print("移动文件失败")
```

## 5. 配置选项

### 5.1 存储配置

- **节点存储空间**：每个节点可配置贡献的存储空间大小
- **副本数**：可配置文件的副本数量，默认为3
- **缓存大小**：P2P CDN的缓存大小，默认为10GB

### 5.2 网络配置

- **节点发现**：支持自动发现和手动添加节点
- **心跳间隔**：节点心跳间隔，默认为30秒
- **节点超时**：节点超时时间，默认为90秒

## 6. 性能优化

### 6.1 存储优化

- **数据分片**：大文件自动分片存储
- **热点数据**：热门数据自动缓存到多个节点
- **存储均衡**：自动平衡各节点的存储负载

### 6.2 网络优化

- **智能路由**：基于网络延迟选择最优节点
- **并行传输**：大文件支持并行下载
- **断点续传**：支持文件传输断点续传

## 7. 故障排除

### 7.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 上传失败 | 存储空间不足 | 检查节点存储空间，添加新节点 |
| 下载失败 | 网络连接问题 | 检查网络连接，尝试从其他节点下载 |
| 节点离线 | 网络中断或节点故障 | 检查节点状态，重启节点服务 |
| 搜索无结果 | 索引未更新 | 等待索引更新，或手动触发索引重建 |

### 7.2 日志查看

系统日志位于 `~/.enterprise_storage/{enterprise_id}/{node_id}/logs/` 目录，可用于排查问题。

## 8. 示例应用

### 8.1 企业文件共享

```python
async def share_file_with_team():
    """与团队共享文件"""
    # 初始化存储系统
    storage = get_enterprise_storage("my_company", "node_1")
    await storage.start()
    
    # 创建团队文件夹
    root_id = storage.virtual_fs.root_folder_id
    team_folder_id = await storage.create_folder("Team Documents", root_id, "admin")
    
    # 上传共享文件
    with open("project_plan.pdf", "rb") as f:
        content = f.read()
    file_id = await storage.upload_file(
        "project_plan.pdf", team_folder_id, content, "application/pdf", "admin"
    )
    
    # 分享文件路径
    file_info = await storage.get_item_info(file_id)
    print(f"文件已共享，路径: {file_info['path']}")
    
    await storage.stop()
```

### 8.2 自动备份

```python
async def backup_files():
    """自动备份文件"""
    storage = get_enterprise_storage("my_company", "node_1")
    await storage.start()
    
    # 创建备份文件夹
    root_id = storage.virtual_fs.root_folder_id
    backup_folder_id = await storage.create_folder("Backups", root_id, "backup_user")
    
    # 备份重要文件
    files_to_backup = ["config.json", "data.csv", "report.docx"]
    for file_name in files_to_backup:
        try:
            with open(file_name, "rb") as f:
                content = f.read()
            await storage.upload_file(
                f"{file_name}.bak", backup_folder_id, content, "application/octet-stream", "backup_user"
            )
            print(f"备份文件 {file_name} 成功")
        except Exception as e:
            print(f"备份文件 {file_name} 失败: {e}")
    
    await storage.stop()
```

## 9. 高级功能

### 9.1 版本控制

企业虚拟网盘系统支持完整的文件版本管理功能，可追踪文件的历史版本并支持回滚操作。

```python
# 上传文件时添加版本注释
file_id = await storage.upload_file(
    "document.txt", folder_id, content, "text/plain", "user1", "Initial version"
)

# 获取文件的所有版本
versions = await storage.get_file_versions(file_id)
print(f"文件版本数量: {len(versions)}")

# 回滚到指定版本
rollback_version = await storage.rollback_to_version(file_id, 1, "user1")
print(f"回滚成功，新版本号: {rollback_version['version_number']}")

# 删除指定版本
await storage.delete_file_version(file_id, 2)
```

### 9.2 权限管理

系统提供细粒度的权限管理功能，支持用户、组和角色级别的权限控制。

```python
# 授予用户权限
permission = await storage.grant_permission(
    "user", "user1", file_id, ["read", "write"]
)

# 拒绝用户权限
await storage.deny_permission(
    "user", "user1", file_id, ["delete"]
)

# 检查权限
has_permission = await storage.check_permission("user1", file_id, "read")
print(f"用户有读权限: {has_permission}")

# 添加用户到组
await storage.add_user_to_group("user1", "developers")
```

### 9.3 文件预览

系统支持常见文件格式的在线预览，包括文本、图片、PDF等。

```python
# 生成文件预览
preview = await storage.generate_file_preview(file_id)
if preview['success']:
    print(f"预览类型: {preview['type']}")
    if preview['type'] == 'text':
        print(f"预览内容: {preview['content'][:100]}...")
    elif preview['type'] == 'image':
        print("图像预览生成成功")
```

### 9.4 同步功能

系统支持企业网盘与虚拟（聚合）云盘的同步功能，可设置单向或双向同步。

```python
from core.enterprise import SyncDirection

# 创建同步任务
sync_job = await storage.create_sync_job(
    job_id="sync_1",
    local_root="/path/to/local/folder",
    cloud_root="/path/to/cloud/folder",
    direction=SyncDirection.BIDIRECTIONAL
)

# 启动同步任务
await storage.start_sync_job("sync_1")

# 获取同步任务状态
job_status = await storage.get_sync_job("sync_1")
print(f"同步状态: {job_status['status']}")

# 列出所有同步任务
jobs = await storage.list_sync_jobs()
```

## 10. 未来规划

- **Web界面**：提供Web管理界面，方便用户操作
- **移动端支持**：开发移动端应用，支持随时随地访问文件
- **多云存储集成**：支持与AWS S3、Azure Blob等云存储服务集成
- **文件加密**：支持文件加密存储，提高数据安全性
- **高级搜索**：支持全文搜索和高级过滤功能
- **文件共享**：支持生成共享链接，方便与外部用户共享文件

## 10. 结论

企业虚拟网盘系统基于P2P CDN技术，为企业提供了一个安全、可靠、高效的分布式存储解决方案。通过整合多个节点的存储空间，形成一个统一的虚拟存储池，企业可以更有效地管理和共享文件。系统支持类似传统文件系统的操作方式，同时提供了分布式存储的优势，如数据冗余、负载均衡和智能路由等。

随着企业数据量的不断增长，传统的集中式存储解决方案面临着存储容量、性能和可靠性的挑战。企业虚拟网盘系统通过分布式架构，为这些挑战提供了有效的解决方案，是企业存储现代化的重要选择。