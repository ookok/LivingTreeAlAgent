"""验证依赖项安装情况"""

def check_package(package_name):
    """检查包是否安装"""
    try:
        __import__(package_name)
        print(f"{package_name} 已安装")
        return True
    except ImportError:
        print(f"{package_name} 未安装")
        return False

# 检查关键依赖项
packages = [
    "PyQt6",
    "ollama",
    "numpy",
    "requests",
    "fastapi",
    "uvicorn",
    "pydantic",
    "aiohttp",
    "pillow"
]

print("开始验证依赖项...")
installed = 0
for package in packages:
    if check_package(package):
        installed += 1

print(f"\n依赖项验证完成！")
print(f"已安装: {installed}/{len(packages)}")

