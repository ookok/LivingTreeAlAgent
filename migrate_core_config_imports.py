"""
批量迁移 core.config 导入到 client.src.business.config
"""
import os
import re


def migrate_imports_in_file(file_path):
    """迁移单个文件中的 core.config 导入"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. from client.src.business.config import XXX → from client.src.business.config import XXX
        content = re.sub(
            r'from core\.config import ',
            'from client.src.business.config import ',
            content
        )
        
        # 2. from client.src.business.config import XXX → from client.src.business.config import XXX
        content = re.sub(
            r'from core\.config\.unified_config import ',
            'from client.src.business.config import ',
            content
        )
        
        # 3. from client.src.business.nanochat_config import XXX → from client.src.business.nanochat_config import XXX
        content = re.sub(
            r'from core\.config\.nanochat_config import ',
            'from client.src.business.nanochat_config import ',
            content
        )
        
        # 4. import core.config → import client.src.business.config as config
        content = re.sub(
            r'^import core\.config$',
            'import client.src.business.config as config',
            content,
            flags=re.MULTILINE
        )
        
        # 5. from client.src.business.config import get_config_dir → from client.src.business.config import get_config_dir
        # （这个已经被规则1覆盖了）
        
        # 只有当内容发生变化时才写回
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, file_path
        
        return False, file_path
        
    except Exception as e:
        return False, f"{file_path}: {e}"


def main():
    """主函数"""
    migrated_files = []
    error_files = []
    
    for root, dirs, files in os.walk('.'):
        # 跳过特定目录
        dirs[:] = [d for d in dirs if d not in [
            '.git', '__pycache__', 'node_modules', '.workbuddy', 'client', 'server'
        ]]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                modified, result = migrate_imports_in_file(file_path)
                
                if modified:
                    migrated_files.append(result)
                elif isinstance(result, str) and "Error" in result:
                    error_files.append(result)
    
    # 输出结果
    print(f"[OK] 成功迁移 {len(migrated_files)} 个文件:")
    for f in migrated_files[:20]:  # 只显示前20个
        print(f"  - {f}")
    if len(migrated_files) > 20:
        print(f"  ... 还有 {len(migrated_files) - 20} 个文件")
    
    if error_files:
        print(f"\n[ERROR] 处理失败 {len(error_files)} 个文件:")
        for f in error_files:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
