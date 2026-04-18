"""
企业级 GGUF 模型管理系统
主入口
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import get_model_manager, metrics_collector, get_app_config

# 配置日志
def setup_logging():
    """配置日志"""
    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


class GGUFManager:
    """GGUF 模型管理器"""
    
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.config = get_app_config()
        self.model_manager = get_model_manager()
        
        # 启动监控
        metrics_collector.start()
        
        self.logger.info(f"GGUF Manager 启动完成 - v{self.config.version}")
    
    def list_models(self):
        """列出所有本地模型"""
        models = self.model_manager.list_local_models()
        print("\n" + "=" * 60)
        print("📦 本地模型列表")
        print("=" * 60)
        
        if not models:
            print("  没有找到 GGUF 模型")
            print("  请将 .gguf 文件放入 models/ 目录")
            return
        
        for i, model in enumerate(models, 1):
            status_icon = "✅" if model.status.value == "loaded" else "📁"
            print(f"\n  {i}. {status_icon} {model.name}")
            print(f"     大小: {model.size_bytes / (1024**3):.2f} GB")
            print(f"     推荐: {model.recommendation_score:.0%}")
            for reason in model.recommendation_reasons[:2]:
                print(f"     • {reason}")
            if model.path:
                print(f"     路径: {model.path}")
        
        print("\n" + "=" * 60)
    
    def show_hardware(self):
        """显示硬件信息"""
        hw = self.model_manager.refresh_hardware()
        print("\n" + "=" * 60)
        print("🖥️  硬件配置")
        print("=" * 60)
        print(f"  CPU 核心: {hw.cpu_cores}")
        print(f"  内存: {hw.available_ram_gb:.1f}GB / {hw.total_ram_gb:.1f}GB")
        print(f"  磁盘: {hw.disk_free_gb:.1f}GB 可用")
        
        if hw.gpu_count > 0:
            print(f"  GPU: {hw.gpu_count} 个")
            for i, mem in enumerate(hw.gpu_memory_gb):
                print(f"    GPU {i}: {mem:.1f} GB")
        else:
            print("  GPU: 未检测到")
        
        print("=" * 60 + "\n")
    
    def show_metrics(self):
        """显示系统指标"""
        metrics = metrics_collector.get_current_metrics()
        
        if not metrics:
            print("等待指标数据...")
            return
        
        print("\n" + "=" * 60)
        print("📊 系统状态")
        print("=" * 60)
        print(f"  CPU:    {metrics.cpu_percent:5.1f}%")
        print(f"  内存:   {metrics.memory_percent:5.1f}% ({metrics.memory_used_gb:.1f}GB)")
        print(f"  磁盘:   {metrics.disk_percent:5.1f}%")
        
        if metrics.gpu_count > 0:
            for i, (util, mem) in enumerate(zip(metrics.gpu_utilization, metrics.gpu_memory_percent)):
                print(f"  GPU {i}: 使用 {util:.1f}% | 显存 {mem:.1f}%")
        
        # 显示告警
        alerts = metrics_collector.get_active_alerts()
        if alerts:
            print("\n  ⚠️  告警:")
            for alert in alerts:
                print(f"    - {alert.message}")
        
        print("=" * 60 + "\n")
    
    def load_model(self, model_name: str):
        """加载模型"""
        models = self.model_manager.list_local_models()
        
        for model in models:
            if model_name.lower() in model.name.lower():
                if model.path:
                    success = self.model_manager.load_model(model.path, model.id)
                    if success:
                        print(f"✅ 模型已加载: {model.name}")
                    else:
                        print(f"❌ 模型加载失败: {model.name}")
                    return
        
        print(f"❌ 未找到模型: {model_name}")
    
    def unload_model(self, model_name: str):
        """卸载模型"""
        # 查找匹配的模型ID
        for model_id in list(self.model_manager.model_instances.keys()):
            if model_name.lower() in model_id.lower():
                success = self.model_manager.unload_model(model_id)
                if success:
                    print(f"✅ 模型已卸载: {model_id}")
                return
        
        print(f"❌ 未找到已加载的模型: {model_name}")
    
    def interactive_mode(self):
        """交互模式"""
        print("\n" + "=" * 60)
        print("🎯 GGUF 模型管理器 - 交互模式")
        print("=" * 60)
        print("  命令:")
        print("    list      - 列出本地模型")
        print("    load      - 加载模型")
        print("    unload    - 卸载模型")
        print("    hardware  - 显示硬件信息")
        print("    metrics   - 显示系统指标")
        print("    help      - 显示帮助")
        print("    exit      - 退出")
        print("=" * 60 + "\n")
        
        while True:
            try:
                cmd = input(">>> ").strip().lower()
                
                if cmd == "exit":
                    break
                elif cmd == "list":
                    self.list_models()
                elif cmd == "load":
                    name = input("模型名称: ").strip()
                    if name:
                        self.load_model(name)
                elif cmd == "unload":
                    name = input("模型名称: ").strip()
                    if name:
                        self.unload_model(name)
                elif cmd == "hardware":
                    self.show_hardware()
                elif cmd == "metrics":
                    self.show_metrics()
                elif cmd == "help":
                    print("\n  命令列表:")
                    print("    list      - 列出本地模型")
                    print("    load <name> - 加载模型")
                    print("    unload <name> - 卸载模型")
                    print("    hardware  - 显示硬件信息")
                    print("    metrics   - 显示系统指标")
                    print("    exit      - 退出程序\n")
                elif not cmd:
                    continue
                else:
                    print(f"  未知命令: {cmd}")
                    print("  输入 'help' 查看帮助")
            except KeyboardInterrupt:
                print("\n\n退出中...")
                break
            except Exception as e:
                print(f"  错误: {e}")
        
        self.shutdown()
    
    def shutdown(self):
        """关闭"""
        print("\n正在关闭...")
        metrics_collector.stop()
        print("✅ 已关闭")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GGUF 模型管理器")
    parser.add_argument("--list", action="store_true", help="列出本地模型")
    parser.add_argument("--hardware", action="store_true", help="显示硬件信息")
    parser.add_argument("--metrics", action="store_true", help="显示系统指标")
    parser.add_argument("--load", type=str, help="加载模型")
    parser.add_argument("--unload", type=str, help="卸载模型")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    manager = GGUFManager()
    
    if args.list:
        manager.list_models()
    elif args.hardware:
        manager.show_hardware()
    elif args.metrics:
        manager.show_metrics()
    elif args.load:
        manager.load_model(args.load)
    elif args.unload:
        manager.unload_model(args.unload)
    else:
        manager.interactive_mode()


if __name__ == "__main__":
    main()
