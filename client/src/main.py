# LivingTree AI Agent - Client Main Entry
# 支持三种部署方式：ollama / vllm / local

import sys
import os
import asyncio
import subprocess
import shutil
from typing import Dict, Any, List, Optional

# Add project root to path
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, '..', '..')))


class DeploymentManager:
    """部署管理器 - 支持 ollama / vllm / local 三种模式"""
    
    DEPLOYMENT_MODES = ["ollama", "vllm", "local"]
    
    def __init__(self, mode: str = "local"):
        self.mode = mode.lower()
        self._ollama_installed = False
        self._ollama_running = False
        self._vllm_running = False
        self._selected_model = "qwen3.5:4b"
        
    async def detect_deployment_mode(self) -> str:
        """自动检测最佳部署方式"""
        checks = await asyncio.gather(
            self._check_ollama_service(),
            self._check_vllm_service()
        )
        
        ollama_result, vllm_result = checks
        
        if vllm_result["status"] == "success":
            print("🔍 检测到 VLLM 服务，使用 vllm 模式")
            return "vllm"
        elif ollama_result["status"] == "success":
            print("🔍 检测到 Ollama 服务，使用 ollama 模式")
            return "ollama"
        else:
            print("🔍 未检测到服务，使用 local 模式（自动安装）")
            return "local"
    
    async def _check_ollama_service(self) -> Dict[str, Any]:
        """检查 Ollama 服务状态"""
        try:
            import ollama
            models = await asyncio.to_thread(ollama.list)
            model_names = [m["name"] for m in models.get("models", [])]
            
            self._ollama_running = True
            self._ollama_installed = True
            
            return {
                "status": "success",
                "message": f"Ollama 服务运行中，检测到 {len(model_names)} 个模型",
                "models": model_names
            }
        except Exception as e:
            # 检查是否安装了 ollama CLI
            if shutil.which("ollama"):
                self._ollama_installed = True
                return {
                    "status": "warning",
                    "message": "Ollama 已安装但服务未运行"
                }
            return {
                "status": "error",
                "message": f"Ollama 未安装或未运行: {str(e)[:30]}..."
            }
    
    async def _check_vllm_service(self) -> Dict[str, Any]:
        """检查 VLLM 服务状态"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get("http://localhost:8000/v1/models")
                if response.status_code == 200:
                    self._vllm_running = True
                    return {
                        "status": "success",
                        "message": "VLLM 服务运行中"
                    }
            return {"status": "error", "message": "VLLM 服务未响应"}
        except Exception as e:
            return {"status": "error", "message": f"VLLM 不可用: {str(e)[:30]}..."}
    
    async def install_ollama(self) -> bool:
        """使用 PowerShell 脚本安装 Ollama"""
        if shutil.which("ollama"):
            print("✅ Ollama 已安装")
            self._ollama_installed = True
            return True
        
        print("📥 正在安装 Ollama...")
        print("   下载地址: https://ollama.com/install.ps1")
        
        try:
            # 使用 PowerShell 执行安装脚本
            command = 'powershell -Command "irm https://ollama.com/install.ps1 | iex"'
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print("✅ Ollama 安装成功")
                self._ollama_installed = True
                return True
            else:
                print(f"❌ Ollama 安装失败: {stderr.decode()[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ 安装过程出错: {e}")
            return False
    
    async def pull_model(self, model_name: str) -> bool:
        """下载模型"""
        print(f"📥 正在下载模型: {model_name}")
        
        try:
            import ollama
            await asyncio.to_thread(ollama.pull, model_name)
            print(f"✅ 模型 {model_name} 下载成功")
            return True
        except Exception as e:
            print(f"❌ 模型下载失败: {e}")
            return False
    
    async def start_ollama_service(self) -> bool:
        """启动 Ollama 服务"""
        if self._ollama_running:
            return True
            
        print("🔧 启动 Ollama 服务...")
        
        try:
            # 在后台启动 ollama serve
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            # 等待服务启动
            await asyncio.sleep(3)
            
            # 验证服务是否启动成功
            import ollama
            models = await asyncio.to_thread(ollama.list)
            self._ollama_running = True
            print("✅ Ollama 服务启动成功")
            return True
            
        except Exception as e:
            print(f"❌ 服务启动失败: {e}")
            return False
    
    async def setup_local_mode(self) -> Dict[str, Any]:
        """完整的 local 模式安装流程"""
        print("\n📦 === Local 模式安装 ===")
        
        steps = [
            ("安装 Ollama", self.install_ollama),
            ("启动服务", self.start_ollama_service),
            ("下载模型", lambda: self.pull_model(self._selected_model))
        ]
        
        for step_name, step_func in steps:
            print(f"\n🔧 {step_name}...")
            success = await step_func()
            if not success:
                return {"status": "error", "message": f"{step_name} 失败"}
        
        print("\n✅ Local 模式安装完成")
        return {"status": "success", "message": "Local 模式已就绪"}


class StartupChecker:
    """异步启动检查器 - 并行执行所有环境检查"""
    
    def __init__(self):
        self.results: Dict[str, Any] = {
            "success": True,
            "messages": [],
            "warnings": [],
            "errors": []
        }
        self._ollama_available = False
        self._models_available = False
        self._selected_model = "qwen3.5:4b"
        self._deployment_manager = None
    
    def _add_message(self, type_: str, message: str, emoji: str = ""):
        """添加消息"""
        self.results[type_].append(f"{emoji} {message}")
    
    async def _check_hardware(self) -> Dict[str, Any]:
        """检查硬件配置"""
        try:
            import psutil
            
            hardware = {
                "cpu_cores": psutil.cpu_count(logical=False) or 4,
                "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
                "arch": os.uname().machine if hasattr(os, 'uname') else "Unknown"
            }
            
            if hardware["ram_gb"] >= 32:
                recommendation = "推荐使用大型模型 (qwen3.5:35b+)"
                self._selected_model = "qwen3.5:9b"
            elif hardware["ram_gb"] >= 16:
                recommendation = "推荐使用中型模型 (qwen3.5:9b/4b)"
                self._selected_model = "qwen3.5:4b"
            elif hardware["ram_gb"] >= 8:
                recommendation = "推荐使用小型模型 (qwen3.5:4b/2b)"
                self._selected_model = "qwen3.5:4b"
            else:
                recommendation = "建议增加内存以获得更好的体验"
                self._selected_model = "qwen3.5:2b"
            
            return {
                "status": "success",
                "message": f"CPU: {hardware['cpu_cores']}核 | 内存: {hardware['ram_gb']}GB",
                "hardware": hardware,
                "recommendation": recommendation
            }
        except Exception as e:
            return {
                "status": "warning",
                "message": f"硬件检测失败: {str(e)[:30]}..."
            }
    
    async def _select_optimal_model(self, hardware: Dict) -> str:
        """智能选择最优模型（使用 ModelFitter 动态获取）"""
        try:
            from infrastructure.model_fitter import get_model_fitter
            
            fitter = get_model_fitter()
            results = await asyncio.to_thread(fitter.fit, "qwen")
            
            if results:
                best_model, score, reason = results[0]
                self._selected_model = best_model
                return f"{best_model} (评分: {score}/100, {reason.split(';')[0]})"
            
            return self._fallback_model_selection(hardware)
        
        except Exception as e:
            print(f"⚠️  模型选择失败，使用备用方案: {e}")
            return self._fallback_model_selection(hardware)
    
    def _fallback_model_selection(self, hardware: Dict) -> str:
        """备用模型选择策略（从配置动态获取）"""
        ram_gb = hardware.get("ram_gb", 8)
        
        model_map = self._get_model_map_from_config()
        
        for min_ram, model, desc in model_map:
            if ram_gb >= min_ram:
                self._selected_model = model
                return f"{model} ({desc})"
        
        # 默认返回最小模型
        if model_map:
            self._selected_model = model_map[-1][1]
            return f"{model_map[-1][1]} ({model_map[-1][2]})"
        
        self._selected_model = "qwen3.5:4b"
        return "qwen3.5:4b (小型模型，适合入门)"
    
    def _get_model_map_from_config(self) -> List[tuple]:
        """从配置中心动态获取模型列表"""
        try:
            from business.config import UnifiedConfig
            
            config = UnifiedConfig.get_instance()
            model_config = config.get("models.local_models", None)
            
            if model_config and isinstance(model_config, list):
                return self._parse_model_config(model_config)
            
        except Exception as e:
            print(f"⚠️  从配置获取模型列表失败，使用默认值: {e}")
        
        return self._get_default_model_map()
    
    def _parse_model_config(self, config_list: List[dict]) -> List[tuple]:
        """解析配置中的模型列表"""
        model_map = []
        
        for item in config_list:
            if isinstance(item, dict):
                min_ram = item.get("min_ram", 0)
                model = item.get("name", "")
                desc = item.get("description", "")
                if min_ram and model:
                    model_map.append((min_ram, model, desc))
            elif isinstance(item, str):
                # 简单字符串格式: "qwen3.5:4b"
                model_map.append(self._infer_model_requirements(item))
        
        # 按内存需求降序排序
        model_map.sort(key=lambda x: x[0], reverse=True)
        return model_map
    
    def _infer_model_requirements(self, model_name: str) -> tuple:
        """根据模型名称推断内存需求"""
        size_mapping = {
            "122b": (64, "超大型模型，需要高端配置"),
            "35b": (32, "大型模型，性能优异"),
            "27b": (24, "中大型模型，平衡性能与资源"),
            "9b": (16, "中型模型，推荐配置"),
            "4b": (8, "小型模型，适合入门"),
            "2b": (4, "微型模型，低资源占用"),
            "0.8b": (2, "超小模型，快速响应"),
            "1.5b": (4, "小型模型，适合入门"),
            "mini": (2, "超小模型，快速响应"),
            "tiny": (1, "微型模型，极低资源占用")
        }
        
        for size_key, (min_ram, desc) in size_mapping.items():
            if size_key.lower() in model_name.lower():
                return (min_ram, model_name, desc)
        
        return (8, model_name, "中型模型")
    
    def _get_default_model_map(self) -> List[tuple]:
        """获取默认模型列表"""
        return [
            (64, "qwen3.5:122b", "超大型模型，需要高端配置"),
            (32, "qwen3.5:35b", "大型模型，性能优异"),
            (24, "qwen3.5:27b", "中大型模型，平衡性能与资源"),
            (16, "qwen3.5:9b", "中型模型，推荐配置"),
            (8, "qwen3.5:4b", "小型模型，适合入门"),
            (4, "qwen3.5:2b", "微型模型，低资源占用"),
            (2, "qwen3.5:0.8b", "超小模型，快速响应")
        ]
    
    async def run_checks(self, deployment_mode: str = None) -> Dict[str, Any]:
        """并行运行所有检查"""
        print("\n🚀 === LivingTree AI Agent 启动检查 ===")
        
        # 创建部署管理器
        self._deployment_manager = DeploymentManager()
        
        # 自动检测或使用指定模式
        if deployment_mode is None:
            deployment_mode = await self._deployment_manager.detect_deployment_mode()
        
        print(f"\n🎯 使用部署模式: {deployment_mode}")
        
        # 如果是 local 模式，执行安装流程
        if deployment_mode == "local":
            await self._handle_local_mode()
        
        # 并行执行检查
        hardware_result = await self._check_hardware()
        
        # 打印硬件检测结果
        self._print_progress("硬件检测", hardware_result["status"])
        print(f"   {hardware_result['message']}")
        if "recommendation" in hardware_result:
            print(f"   💡 {hardware_result['recommendation']}")
        
        # 智能模型选择
        if hardware_result["status"] == "success":
            model_info = await self._select_optimal_model(hardware_result["hardware"])
            self._print_progress("模型推荐", "success")
            print(f"   推荐模型: {model_info}")
        
        # 更新部署管理器的选中模型
        if self._deployment_manager:
            self._deployment_manager._selected_model = self._selected_model
        
        # 生成引导信息
        self._generate_guidance(deployment_mode)
        
        print("\n✅ === 启动检查完成 ===")
        return self.results
    
    async def _handle_local_mode(self):
        """处理 local 模式的安装流程"""
        result = await self._deployment_manager.setup_local_mode()
        
        if result["status"] == "success":
            self._print_progress("Local安装", "success")
            print(f"   {result['message']}")
        else:
            self._print_progress("Local安装", "error")
            print(f"   {result['message']}")
    
    def _print_progress(self, title: str, status: str):
        """打印进度状态"""
        symbols = {
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "info": "🔍"
        }
        print(f"\n{symbols.get(status, '🔍')} {title}...")
    
    def _generate_guidance(self, deployment_mode: str):
        """生成智能用户引导"""
        print("\n📋 快速开始指南")
        print("────────────────")
        
        guidance_map = {
            "ollama": """
🎉 Ollama 模式已就绪!

当前状态:
   ✅ Ollama 服务运行中
   ✅ 模型已加载

💡 快速命令:
   /analyze    - 分析文本
   /search     - 搜索知识库
   /summarize  - 总结内容
   /help       - 查看所有命令
            """,
            "vllm": """
🚀 VLLM 模式已就绪!

当前状态:
   ✅ VLLM 服务运行中
   ✅ 高性能推理已启用

💡 特性:
   - 高吞吐量推理
   - 连续批处理支持
   - 极低延迟响应
            """,
            "local": """
📦 Local 模式已配置完成!

当前状态:
   ✅ Ollama 已安装
   ✅ 服务已启动
   ✅ 模型已下载

💡 提示:
   模型存储位置: ~/.ollama/models
   如需切换模型: ollama run <model_name>
            """
        }
        
        print(guidance_map.get(deployment_mode, guidance_map["local"]))


async def check_environment_async(deployment_mode: str = None) -> Dict[str, Any]:
    """异步环境检查"""
    checker = StartupChecker()
    return await checker.run_checks(deployment_mode)


def check_environment(deployment_mode: str = None):
    """同步包装器"""
    return asyncio.run(check_environment_async(deployment_mode))


def main():
    print("🚀 LivingTree AI Agent")
    
    # 解析命令行参数
    deployment_mode = None
    skip_startup = False
    
    for arg in sys.argv[1:]:
        if arg in ["ollama", "vllm", "local"]:
            deployment_mode = arg
            print(f"🎯 使用指定模式: {deployment_mode}")
        elif arg in ["--skip-startup", "-s"]:
            skip_startup = True
            print("⏭️ 跳过启动检查对话框")
    
    from PyQt6.QtWidgets import QApplication
    
    print("📱 初始化界面...")
    app = QApplication(sys.argv)
    
    startup_result = None
    
    if not skip_startup:
        # 显示启动进度对话框
        from presentation.dialogs.startup_dialog import StartupDialog
        
        startup_dialog = StartupDialog()
        
        def on_startup_completed(result):
            nonlocal startup_result
            startup_result = result
            print(f"📋 启动检查完成: {result}")
        
        startup_dialog.startup_completed.connect(on_startup_completed)
        
        # 显示启动对话框
        print("🔍 显示启动检查对话框...")
        dialog_result = startup_dialog.exec()
        
        if dialog_result == 0:
            # 用户取消
            print("❌ 用户取消启动")
            sys.exit(0)
    else:
        # 跳过启动检查，使用默认配置
        print("⏭️ 跳过启动检查，使用默认配置")
        startup_result = {
            "deployment_mode": deployment_mode or "local",
            "hardware": {
                "cpu_cores": 4,
                "ram_gb": 8.0,
                "arch": "x86_64"
            },
            "model": "qwen3.5:4b"
        }
    
    # 加载主窗口
    print("🖼️ 加载主窗口...")
    
    from presentation.layouts import MainWindow
    from business.config import UnifiedConfig
    
    config = UnifiedConfig.get_instance()
    window = MainWindow()
    
    # 传递启动结果给主窗口
    if startup_result:
        window.startup_result = startup_result
    
    window.show()
    window.activateWindow()
    window.raise_()
    
    print("✅ 客户端已启动")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()