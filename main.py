#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - Unified Entry Point

Usage:
    python main.py client      # Start desktop client
    python main.py relay       # Start relay server
    python main.py tracker     # Start tracker server
    python main.py app         # Start enterprise app
    python main.py bootstrap   # Auto-configure and deploy services (first run)
    python main.py install     # Install as background service
    python main.py uninstall   # Uninstall background service
    python main.py status      # Check service status
"""

import sys
import os
import subprocess


def safe_print(msg):
    """安全打印 - 处理 Windows 控制台编码问题"""
    try:
        print(msg)
    except UnicodeEncodeError:
        ascii_msg = msg.encode('ascii', errors='ignore').decode('ascii')
        print(ascii_msg)


def start_client():
    """Start desktop client"""
    safe_print("🌳 Starting LivingTree AI Agent Client...")
    client_main = os.path.join(os.path.dirname(__file__), 'client', 'src', 'main.py')
    os.execv(sys.executable, [sys.executable, client_main])


def start_relay():
    """Start relay server"""
    print("🔄 Starting Relay Server...")
    relay_main = os.path.join(os.path.dirname(__file__), 'server', 'relay_server', 'main.py')
    os.execv(sys.executable, [sys.executable, relay_main])


def start_tracker():
    """Start tracker server"""
    print("📊 Starting Tracker Server...")
    tracker_server = os.path.join(os.path.dirname(__file__), 'server', 'tracker_server.py')
    os.execv(sys.executable, [sys.executable, tracker_server])


def start_app():
    """Start enterprise app"""
    print("🏢 Starting Enterprise App...")
    app_main = os.path.join(os.path.dirname(__file__), 'app', 'main.py')
    os.execv(sys.executable, [sys.executable, app_main])


def run_bootstrap():
    """Run platform bootstrap (auto-configure and deploy)"""
    print("🚀 Running Platform Bootstrap...")
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
    
    from client.src.infrastructure.platform_bootstrapper import (
        PlatformBootstrapper, ServiceDeployer, EnvironmentManager
    )
    
    try:
        # 1. 初始化启动器
        bootstrapper = PlatformBootstrapper()
        config = bootstrapper.detect_and_configure()
        
        print(f"\n📋 平台检测结果:")
        print(f"   操作系统: {config['hardware']['os']}")
        print(f"   CPU核心: {config['hardware']['cpu_cores']}")
        print(f"   内存: {config['hardware']['ram_gb']} GB")
        print(f"   GPU显存: {config['hardware']['gpu_vram']} GB")
        print(f"   推理引擎: {config['inference_engine']}")
        print(f"   模型: {config['ollama']['model']}")
        
        # 2. 检查并安装 Ollama
        print("\n🔧 检查 Ollama 依赖...")
        bootstrapper._check_dependencies()
        
        # 3. 下载模型
        print("\n📥 下载模型...")
        bootstrapper._download_model()
        
        # 4. 设置虚拟环境
        print("\n🔨 设置虚拟环境...")
        env_manager = EnvironmentManager(config)
        env_manager.setup_environment()
        
        # 5. 部署服务
        print("\n📦 部署服务...")
        deployer = ServiceDeployer(config)
        deployer.deploy_all()
        
        print("\n✅ 零部署完成！")
        print("   应用目录: " + config['app_dir'])
        print("   日志目录: " + config['log_path'])
        print("   模型: " + config['ollama']['model'])
        
        # 6. 启动客户端
        print("\n🌳 启动客户端...")
        start_client()
        
    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_install():
    """Install as background service"""
    print("📥 Installing as background service...")
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
    
    from client.src.infrastructure.platform_bootstrapper import (
        PlatformBootstrapper, ServiceDeployer, EnvironmentManager
    )
    
    try:
        bootstrapper = PlatformBootstrapper()
        config = bootstrapper.detect_and_configure()
        
        env_manager = EnvironmentManager(config)
        env_manager.setup_environment()
        
        deployer = ServiceDeployer(config)
        deployer.deploy_all()
        
        print("✅ 服务安装完成")
    except Exception as e:
        print(f"❌ 安装失败: {e}")
        sys.exit(1)


def run_uninstall():
    """Uninstall background service"""
    print("🗑️ Uninstalling background service...")
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
    
    from client.src.infrastructure.platform_bootstrapper import (
        PlatformBootstrapper, ServiceDeployer
    )
    
    try:
        bootstrapper = PlatformBootstrapper()
        config = bootstrapper.detect_and_configure()
        
        deployer = ServiceDeployer(config)
        deployer.uninstall()
        
        print("✅ 服务卸载完成")
    except Exception as e:
        print(f"❌ 卸载失败: {e}")
        sys.exit(1)


def run_status():
    """Check service status"""
    print("📊 Checking service status...")
    
    os_type = os.name
    
    if os_type == 'posix':
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "livingtree-agent"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ LivingTree Agent 服务运行中")
            else:
                print("❌ LivingTree Agent 服务未运行")
        except FileNotFoundError:
            print("⚠️ 无法检测服务状态 (systemctl不可用)")
    else:
        try:
            result = subprocess.run(
                ["sc", "query", "LivingTreeAgent"],
                capture_output=True,
                text=True,
                encoding='gbk'
            )
            if "RUNNING" in result.stdout:
                print("✅ LivingTree Agent 服务运行中")
            else:
                print("❌ LivingTree Agent 服务未运行")
        except Exception as e:
            print(f"⚠️ 无法检测服务状态: {e}")


def main():
    if len(sys.argv) < 2:
        print("🌳 LivingTree AI Agent - Unified Entry Point")
        print()
        print("Usage:")
        print("  python main.py client      # Start desktop client")
        print("  python main.py relay       # Start relay server")
        print("  python main.py tracker     # Start tracker server")
        print("  python main.py app         # Start enterprise app")
        print("  python main.py bootstrap   # Auto-configure and deploy (first run)")
        print("  python main.py install     # Install as background service")
        print("  python main.py uninstall   # Uninstall background service")
        print("  python main.py status      # Check service status")
        print()
        print("Default: client")
        
        start_client()
        return

    command = sys.argv[1].lower()

    if command == 'client':
        start_client()
    elif command == 'relay':
        start_relay()
    elif command == 'tracker':
        start_tracker()
    elif command == 'app':
        start_app()
    elif command == 'bootstrap':
        run_bootstrap()
    elif command == 'install':
        run_install()
    elif command == 'uninstall':
        run_uninstall()
    elif command == 'status':
        run_status()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: client, relay, tracker, app, bootstrap, install, uninstall, status")
        sys.exit(1)


if __name__ == '__main__':
    main()