#!/usr/bin/env python3
"""
为所有工具包装器添加自动注册代码

在每个 *_tool.py 文件末尾添加模块级别注册代码
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def add_auto_registration(file_path: str) -> bool:
    """
    为单个工具文件添加自动注册代码
    
    Args:
        file_path: 工具文件的绝对路径
        
    Returns:
        是否成功添加
    """
    try:
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否已经包含自动注册代码
        if "Auto-register" in content or "Auto-registration" in content:
            print(f"[SKIP] 已包含注册代码: {os.path.basename(file_path)}")
            return True
        
        # 自动注册代码模板
        auto_reg_code = '''

# =============================================================================
# Auto-Registration
# =============================================================================

_registration_done = False

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    global _registration_done
    
    if _registration_done:
        return
    
    try:
        # 创建工具实例
        _tool_instance = {class_name}()
        
        # 获取 ToolRegistry 单例
        from client.src.business.tools.tool_registry import ToolRegistry
        _registry = ToolRegistry.get_instance()
        
        # 注册工具
        success = _registry.register_tool(_tool_instance)
        
        if success:
            import loguru
            loguru.logger.info(f"Auto-registered: {{_tool_instance.name}}")
        else:
            import loguru
            loguru.logger.warning(f"Auto-registration failed (tool already exists): {{_tool_instance.name}}")
        
        _registration_done = True
        
    except Exception as e:
        import loguru
        loguru.logger.error(f"Auto-registration error: {{e}}")


# 执行自动注册
_auto_register()
'''
        
        # 获取类名
        class_name = None
        for line in content.split("\n"):
            if line.startswith("class ") and "BaseTool" in line:
                # 格式：class ClassName(BaseTool):
                class_name = line.split("class ")[1].split("(")[0].strip()
                break
        
        if class_name is None:
            print(f"[FAIL] 未找到 BaseTool 子类: {os.path.basename(file_path)}")
            return False
        
        # 添加自动注册代码
        auto_reg_code = auto_reg_code.format(class_name=class_name)
        new_content = content + auto_reg_code
        
        # 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        print(f"[PASS] 添加注册代码: {os.path.basename(file_path)} (class: {class_name})")
        return True
        
    except Exception as e:
        print(f"[FAIL] 处理失败 {os.path.basename(file_path)}: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("为所有工具添加自动注册代码")
    print("=" * 60)
    
    # 查找所有 *_tool.py 文件
    tools_dir = os.path.join(project_root, "client", "src", "business", "tools")
    
    if not os.path.exists(tools_dir):
        print(f"[FAIL] 目录不存在: {tools_dir}")
        return
    
    success_count = 0
    failed_count = 0
    skip_count = 0
    
    for file in os.listdir(tools_dir):
        if file.endswith("_tool.py") and file != "base_tool.py":
            file_path = os.path.join(tools_dir, file)
            
            # 检查是否已经包含自动注册代码
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "Auto-register" in content or "Auto-registration" in content:
                print(f"[SKIP] 已包含注册代码: {file}")
                skip_count += 1
                continue
            
            # 添加自动注册代码
            success = add_auto_registration(file_path)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"处理完成: 成功 {success_count} 个, 失败 {failed_count} 个, 跳过 {skip_count} 个")
    print("=" * 60)


if __name__ == "__main__":
    main()
