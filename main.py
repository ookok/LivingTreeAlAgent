#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - Unified Entry Point

Usage:
    python main.py client          # Start desktop client
    python main.py relay           # Start relay server
    python main.py tracker         # Start tracker server
    python main.py app             # Start enterprise app
    python main.py bootstrap       # Auto-configure and deploy services (first run)
    python main.py install         # Install as background service
    python main.py uninstall       # Uninstall background service
    python main.py status          # Check service status
    python main.py check           # Run environment check
    python main.py update          # Check and apply updates
    python main.py heal            # Start auto-heal monitoring
    python main.py config          # Run configuration wizard
    python main.py model <name>    # Ensure model is installed
    python main.py livingtree      # Start with new livingtree/ core
    python main.py test            # Run livingtree integration tests
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
    """Start desktop client (PyQt6)"""
    safe_print("🌳 Starting LivingTree AI Agent Client...")
    client_main = os.path.join(os.path.dirname(__file__), 'client', 'src', 'main.py')
    # 传递额外命令行参数
    args = [sys.executable, client_main] + sys.argv[2:]
    os.execv(sys.executable, args)


def start_edifice_client():
    """Start desktop client (Edifice)"""
    safe_print("🌳 Starting LivingTree AI Agent Client (Edifice)...")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
    from client.src.presentation.edifice_app import run_edifice_app
    run_edifice_app()


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
        bootstrapper = PlatformBootstrapper()
        config = bootstrapper.detect_and_configure()
        
        print(f"\n📋 平台检测结果:")
        print(f"   操作系统: {config['hardware']['os']}")
        print(f"   CPU核心: {config['hardware']['cpu_cores']}")
        print(f"   内存: {config['hardware']['ram_gb']} GB")
        print(f"   GPU显存: {config['hardware']['gpu_vram']} GB")
        print(f"   推理引擎: {config['inference_engine']}")
        print(f"   模型: {config['ollama']['model']}")
        
        print("\n🔧 检查 Ollama 依赖...")
        bootstrapper._check_dependencies()
        
        print("\n📥 下载模型...")
        bootstrapper._download_model()
        
        print("\n🔨 设置虚拟环境...")
        env_manager = EnvironmentManager(config)
        env_manager.setup_environment()
        
        print("\n📦 部署服务...")
        deployer = ServiceDeployer(config)
        deployer.deploy_all()
        
        print("\n✅ 零部署完成！")
        print("   应用目录: " + config['app_dir'])
        print("   日志目录: " + config['log_path'])
        print("   模型: " + config['ollama']['model'])
        
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


def run_sync_models():
    """Sync model list from external repositories"""
    print("🔄 Syncing model list from external repositories...")
    print("   使用索引+分片策略优化内存使用")
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
    
    from client.src.infrastructure.model_registry import ModelRegistrySync, LazyModelRegistry
    
    try:
        sync = ModelRegistrySync()
        success = sync.sync_models()
        
        if success:
            print("✅ 模型列表同步成功")
            
            registry = LazyModelRegistry()
            registry.load_index()
            
            total_models = registry.index.get("total_models", 0)
            families = registry.index.get("families", [])
            
            print(f"   共同步 {total_models} 个模型")
            print(f"   共 {len(families)} 个模型系列")
            print(f"   系列列表: {families[:10]}...")
            
            qwen_count = len(registry.get_models_by_family("qwen"))
            print(f"   Qwen 系列模型: {qwen_count} 个")
            
            registry_dir = sync.get_registry_dir()
            print(f"   注册表目录: {registry_dir}")
            
            import glob
            index_files = glob.glob(str(registry_dir / "*.json"))
            shard_files = glob.glob(str(registry_dir / "*.json.gz"))
            print(f"   索引文件: {len(index_files)} 个")
            print(f"   分片文件: {len(shard_files)} 个")
        else:
            print("❌ 模型列表同步失败")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_check():
    """Run environment check"""
    from scripts.check import EnvironmentChecker
    checker = EnvironmentChecker()
    success = checker.run()
    sys.exit(0 if success else 1)


def run_update():
    """Check and apply updates"""
    from scripts.auto_update import AutoUpdater
    updater = AutoUpdater()
    success, message = updater.run(auto_apply=False)
    print(message)
    sys.exit(0 if success else 1)


def run_heal():
    """Start auto-heal monitoring"""
    from scripts.auto_heal import AutoHealer
    healer = AutoHealer()
    healer.run()


def run_config():
    """Run configuration wizard"""
    from scripts.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    wizard.run()


def run_model():
    """Ensure model is installed"""
    if len(sys.argv) < 3:
        print("❌ 请指定模型名称")
        print("Usage: python main.py model <model_name>")
        sys.exit(1)
    
    model_name = sys.argv[2]
    from scripts.model_manager import ModelManager
    manager = ModelManager()
    success = manager.ensure_model(model_name)
    sys.exit(0 if success else 1)


def _check_first_run():
    """Check if this is the first run and run config wizard"""
    from scripts.config_wizard import ConfigWizard
    if not ConfigWizard.exists():
        print("👋 首次启动，正在配置...")
        wizard = ConfigWizard()
        wizard.run()


def _auto_update_check():
    """Check for updates automatically"""
    from scripts.config_wizard import ConfigWizard
    config = ConfigWizard.load_config()
    
    if config.get("auto_update", True):
        from scripts.auto_update import AutoUpdater
        updater = AutoUpdater()
        success, updates, _ = updater.check_updates()
        if success and updates > 0:
            print(f"📥 发现 {updates} 个更新")
            try:
                response = input("是否更新? (Y/N): ").strip().upper()
                if response == 'Y':
                    updater.apply_update()
            except KeyboardInterrupt:
                pass


def main():
    if len(sys.argv) < 2:
        _check_first_run()
        _auto_update_check()
        start_client()
        return

    command = sys.argv[1].lower()

    if command == 'client':
        _check_first_run()
        _auto_update_check()
        start_client()
    elif command == 'edifice':
        _check_first_run()
        start_edifice_client()
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
    elif command == 'sync-models':
        run_sync_models()
    elif command == 'check':
        run_check()
    elif command == 'update':
        run_update()
    elif command == 'heal':
        run_heal()
    elif command == 'config':
        run_config()
    elif command == 'model':
        run_model()
    elif command == 'livingtree':
        safe_print("[livingtree] Starting with new livingtree core...")
        from livingtree.main import main as lt_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        lt_main()
    elif command == 'test':
        safe_print("[livingtree] Running integration tests...")
        from livingtree.main import main as lt_main
        sys.argv = [sys.argv[0], 'test']
        lt_main()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: client, relay, tracker, app, livingtree, bootstrap, install, uninstall, status, sync-models, check, update, heal, config, model, test")
        sys.exit(1)


if __name__ == '__main__':
    main()