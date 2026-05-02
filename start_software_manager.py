import subprocess
import sys
import threading
import time
import webbrowser
import os

def start_api():
    """启动API服务"""
    env = os.environ.copy()
    env['PYTHONPATH'] = f"client/src;{env.get('PYTHONPATH', '')}"
    
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "client.src.business.software_manager.api:app", 
        "--host", "0.0.0.0", 
        "--port", "8080"
    ], env=env)

if __name__ == "__main__":
    print("=== 启动软件工具箱 ===")
    
    os.environ['PYTHONPATH'] = f"client/src;{os.environ.get('PYTHONPATH', '')}"
    
    # 启动API服务
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # 等待服务启动
    print("正在启动服务...")
    time.sleep(3)
    
    # 打开浏览器
    print("服务已启动，正在打开浏览器...")
    webbrowser.open("http://localhost:8080")
    
    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n服务已停止")