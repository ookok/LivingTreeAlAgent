"""
启动进度对话框 - 可视化显示系统检查进度

功能：
1. 显示部署模式检测进度
2. 显示硬件检测结果
3. 显示模型推荐
4. 显示 Ollama 安装进度
5. 智能用户引导
"""

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame, QTextEdit,
    QWidget, QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QFont, QIcon
import asyncio
from typing import Dict, Any, Optional


class StartupWorker(QObject):
    """后台工作线程 - 执行环境检查"""
    
    progress_updated = pyqtSignal(str, int, str)  # (step_name, progress, message)
    step_completed = pyqtSignal(str, str, bool)    # (step_name, message, success)
    all_completed = pyqtSignal(dict)               # 所有检查完成
    error_occurred = pyqtSignal(str)               # 发生错误
    
    def __init__(self, deployment_mode: str = None):
        super().__init__()
        self._deployment_mode = deployment_mode
        self._checker = None
    
    def run(self):
        """执行后台检查"""
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            
            from business.config import UnifiedConfig
            from infrastructure.model_fitter import get_model_fitter
            
            config = UnifiedConfig.get_instance()
            
            # 步骤1: 检测部署模式
            self.progress_updated.emit("部署模式检测", 0, "正在检测可用服务...")
            self._detect_deployment_mode()
            
            # 步骤2: 硬件检测
            self.progress_updated.emit("硬件检测", 0, "正在检测硬件配置...")
            self._check_hardware()
            
            # 步骤3: 模型推荐
            self.progress_updated.emit("模型推荐", 0, "正在分析最优模型...")
            self._select_model()
            
            # 步骤4: Local模式安装
            if self._deployment_mode == "local":
                self.progress_updated.emit("环境安装", 0, "正在安装 Ollama...")
                self._setup_local_mode()
            
            self.all_completed.emit({
                "deployment_mode": self._deployment_mode,
                "hardware": self._hardware_info,
                "model": self._selected_model
            })
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def _detect_deployment_mode(self):
        """检测部署模式"""
        import shutil
        
        self.progress_updated.emit("部署模式检测", 33, "检查 VLLM 服务...")
        vllm_running = self._check_vllm()
        
        self.progress_updated.emit("部署模式检测", 66, "检查 Ollama 服务...")
        ollama_running = self._check_ollama()
        
        self.progress_updated.emit("部署模式检测", 100, "")
        
        if vllm_running:
            self._deployment_mode = "vllm"
            msg = "✅ 检测到 VLLM 服务"
        elif ollama_running:
            self._deployment_mode = "ollama"
            msg = "✅ 检测到 Ollama 服务"
        elif shutil.which("ollama"):
            self._deployment_mode = "ollama"
            msg = "⚠️ Ollama 已安装但未运行"
        else:
            self._deployment_mode = "local"
            msg = "🔧 未检测到服务，使用 Local 模式"
        
        self.step_completed.emit("部署模式检测", msg, True)
    
    def _check_vllm(self) -> bool:
        """检查 VLLM 服务"""
        try:
            import httpx
            with httpx.Client(timeout=2) as client:
                response = client.get("http://localhost:8000/v1/models")
                return response.status_code == 200
        except:
            return False
    
    def _check_ollama(self) -> bool:
        """检查 Ollama 服务"""
        try:
            import ollama
            ollama.list()
            return True
        except:
            return False
    
    def _check_hardware(self):
        """检测硬件配置"""
        try:
            import psutil
            
            self.progress_updated.emit("硬件检测", 50, "分析系统资源...")
            
            self._hardware_info = {
                "cpu_cores": psutil.cpu_count(logical=False) or 4,
                "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
                "arch": "x86_64"
            }
            
            self.progress_updated.emit("硬件检测", 100, "")
            
            msg = f"✅ CPU: {self._hardware_info['cpu_cores']}核 | 内存: {self._hardware_info['ram_gb']}GB"
            self.step_completed.emit("硬件检测", msg, True)
            
        except Exception as e:
            self.step_completed.emit("硬件检测", f"⚠️ 检测失败: {str(e)[:30]}", False)
    
    def _select_model(self):
        """选择最优模型"""
        try:
            fitter = get_model_fitter()
            results = fitter.fit("qwen")
            
            if results:
                self._selected_model, score, reason = results[0]
                msg = f"✅ {self._selected_model} (评分: {score}/100)"
            else:
                # 备用方案
                ram_gb = self._hardware_info.get("ram_gb", 8)
                if ram_gb >= 16:
                    self._selected_model = "qwen3.5:9b"
                elif ram_gb >= 8:
                    self._selected_model = "qwen3.5:4b"
                else:
                    self._selected_model = "qwen3.5:2b"
                msg = f"✅ {self._selected_model} (根据硬件推荐)"
            
            self.progress_updated.emit("模型推荐", 100, "")
            self.step_completed.emit("模型推荐", msg, True)
            
        except Exception as e:
            self._selected_model = "qwen3.5:4b"
            self.step_completed.emit("模型推荐", f"⚠️ 使用默认模型: {self._selected_model}", False)
    
    def _setup_local_mode(self):
        """Local模式安装 - 使用 PowerShell 脚本下载并安装 Ollama"""
        import subprocess
        import shutil
        import tempfile
        import os
        
        # 步骤1: 检查是否已安装
        if shutil.which("ollama"):
            self.progress_updated.emit("环境安装", 33, "Ollama 已安装")
            self.step_completed.emit("环境安装", "✅ Ollama 已安装", True)
            return
        
        # 步骤2: 使用 PowerShell 脚本下载并安装
        self.progress_updated.emit("环境安装", 50, "正在使用 PowerShell 下载...")
        
        try:
            temp_dir = tempfile.gettempdir()
            local_path = os.path.join(temp_dir, "OllamaSetup.exe")
            
            # PowerShell 下载脚本
            download_script = f"""
# 下载 Ollama
Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile "{local_path}" -UseBasicParsing
"""
            
            # 执行下载脚本
            self.progress_updated.emit("环境安装", 60, "执行下载脚本...")
            download_result = subprocess.run(
                ["powershell", "-Command", download_script],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if download_result.returncode != 0:
                error_msg = download_result.stderr[:100] if download_result.stderr else "下载失败"
                self.progress_updated.emit("环境安装", 100, "下载失败")
                self.step_completed.emit("环境安装", f"❌ 下载失败: {error_msg}", False)
                return
            
            # 检查下载是否成功
            if not os.path.exists(local_path):
                self.progress_updated.emit("环境安装", 100, "下载文件不存在")
                self.step_completed.emit("环境安装", "❌ 下载文件不存在", False)
                return
            
            self.progress_updated.emit("环境安装", 85, "下载成功，正在安装...")
            
            # 执行静默安装
            install_result = subprocess.run(
                [local_path, "/S"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if install_result.returncode == 0:
                self.progress_updated.emit("环境安装", 100, "安装成功")
                self.step_completed.emit("环境安装", "✅ Ollama 安装成功", True)
            else:
                error_msg = install_result.stderr[:100] if install_result.stderr else "安装失败"
                self.progress_updated.emit("环境安装", 100, "安装失败")
                self.step_completed.emit("环境安装", f"❌ 安装失败: {error_msg}", False)
                
        except Exception as e:
            self.progress_updated.emit("环境安装", 100, "安装异常")
            self.step_completed.emit("环境安装", f"❌ 安装异常: {str(e)[:50]}", False)
    
    def _download_with_resume(self, url: str, local_path: str) -> bool:
        """支持断点续传的文件下载（支持代理）"""
        import requests
        import os
        
        try:
            # 获取代理配置
            proxies = self._get_proxy_config()
            
            # 检查本地文件大小
            local_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            
            # 获取远程文件大小
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            if local_size > 0:
                try:
                    response = requests.head(url, headers=headers, proxies=proxies, timeout=10)
                    if response.status_code == 200:
                        remote_size = int(response.headers.get("Content-Length", 0))
                        if local_size >= remote_size:
                            self.progress_updated.emit("环境安装", 70, "文件已完整")
                            return True
                except:
                    pass
                
                headers["Range"] = f"bytes={local_size}-"
            
            # 开始下载（增加超时时间）
            response = requests.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=120,
                proxies=proxies,
                verify=False
            )
            
            if response.status_code == 416:
                local_size = 0
                headers.pop("Range", None)
                response = requests.get(
                    url, 
                    headers=headers, 
                    stream=True, 
                    timeout=120,
                    proxies=proxies,
                    verify=False
                )
            
            if response.status_code not in [200, 206]:
                return False
            
            total_size = int(response.headers.get("Content-Length", 0)) + local_size
            downloaded = local_size
            
            # 打开文件进行追加或写入
            mode = "ab" if local_size > 0 else "wb"
            with open(local_path, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = 50 + int((downloaded / total_size) * 30)
                            self.progress_updated.emit("环境安装", progress, 
                                f"下载中: {self._format_size(downloaded)} / {self._format_size(total_size)}")
            
            return True
            
        except requests.exceptions.ConnectTimeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.RequestException:
            return False
        except Exception:
            return False
    
    def _get_proxy_config(self):
        """获取系统代理配置"""
        try:
            from business.unified_proxy_config import UnifiedProxyConfig
            config = UnifiedProxyConfig.get_instance()
            proxy = config.get_proxy()
            
            if proxy:
                return {
                    "http": proxy,
                    "https": proxy
                }
        except Exception:
            pass
        
        # 尝试从环境变量获取
        env_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if env_proxy:
            return {
                "http": env_proxy,
                "https": env_proxy
            }
        
        return None
    
    def _format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        else:
            return f"{bytes_size / (1024 * 1024):.1f} MB"


class StartupDialog(QDialog):
    """启动进度对话框"""
    
    startup_completed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌙 生命之树 AI - 启动中")
        self.setFixedSize(500, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self._init_ui()
        
        # 工作线程
        self._worker = None
        self._thread = None
        
        # 步骤状态
        self._step_results = []
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题区域
        title_frame = QFrame()
        title_layout = QVBoxLayout(title_frame)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel("🌙 生命之树 AI")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ff79c6;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle_label = QLabel("智能助手启动中...")
        subtitle_label.setFont(QFont("Segoe UI", 14))
        subtitle_label.setStyleSheet("color: #6272a4;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        layout.addWidget(title_frame)
        
        # 进度区域
        self._progress_container = QWidget()
        self._progress_layout = QVBoxLayout(self._progress_container)
        self._progress_layout.setSpacing(15)
        layout.addWidget(self._progress_container)
        
        # 创建进度项
        self._create_progress_item("部署模式检测", "🔍")
        self._create_progress_item("硬件检测", "💻")
        self._create_progress_item("模型推荐", "🤖")
        self._create_progress_item("环境安装", "📦")
        
        # 详情日志
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFixedHeight(120)
        self._log_text.setStyleSheet("""
            QTextEdit {
                background-color: #282a36;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 10px;
                color: #f8f8f2;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._log_text)
        
        # 底部按钮
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(10)
        
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #55596e;
            }
        """)
        
        self._continue_btn = QPushButton("继续")
        self._continue_btn.clicked.connect(self._on_continue)
        self._continue_btn.setEnabled(False)
        self._continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #50fa7b;
                color: #282a36;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #44475a;
                color: #6272a4;
            }
        """)
        
        button_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        button_layout.addWidget(self._cancel_btn)
        button_layout.addWidget(self._continue_btn)
        layout.addWidget(button_frame)
        
        # 应用 Dracula 主题背景
        self.setStyleSheet("""
            QDialog {
                background-color: #282a36;
            }
        """)
    
    def _create_progress_item(self, name: str, icon: str):
        """创建进度项"""
        frame = QFrame()
        frame.setObjectName(f"frame_{name}")
        layout = QHBoxLayout(frame)
        layout.setSpacing(10)
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 16))
        
        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 13))
        name_label.setStyleSheet("color: #f8f8f2;")
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName(f"progress_{name}")
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #44475a;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #50fa7b;
                border-radius: 4px;
            }
        """)
        self._progress_bar.setValue(0)
        
        status_label = QLabel("等待中...")
        status_label.setObjectName(f"status_{name}")
        status_label.setFont(QFont("Segoe UI", 11))
        status_label.setStyleSheet("color: #6272a4;")
        
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(status_label)
        
        self._progress_layout.addWidget(frame)
    
    def showEvent(self, event):
        """显示时启动后台检查"""
        super().showEvent(event)
        self._start_checks()
    
    def _start_checks(self):
        """启动后台检查线程"""
        self._worker = StartupWorker()
        self._thread = QThread()
        
        self._worker.moveToThread(self._thread)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.step_completed.connect(self._on_step_completed)
        self._worker.all_completed.connect(self._on_all_completed)
        self._worker.error_occurred.connect(self._on_error)
        
        self._thread.started.connect(self._worker.run)
        self._thread.start()
    
    def _on_progress_updated(self, step_name: str, progress: int, message: str):
        """更新进度"""
        bar = self.findChild(QProgressBar, f"progress_{step_name}")
        if bar:
            bar.setValue(progress)
        
        status = self.findChild(QLabel, f"status_{step_name}")
        if status and message:
            status.setText(message)
    
    def _on_step_completed(self, step_name: str, message: str, success: bool):
        """步骤完成"""
        # 更新状态标签
        status = self.findChild(QLabel, f"status_{step_name}")
        if status:
            status.setText(message)
            if success:
                status.setStyleSheet("color: #50fa7b;")
            else:
                status.setStyleSheet("color: #ff5555;")
        
        # 添加到日志
        self._log_text.append(f"[{step_name}] {message}")
        
        # 记录结果
        self._step_results.append({
            "name": step_name,
            "message": message,
            "success": success
        })
    
    def _on_all_completed(self, result: dict):
        """所有检查完成"""
        self._thread.quit()
        self._thread.wait()
        
        self._log_text.append("\n✅ 启动检查完成！")
        self._continue_btn.setEnabled(True)
        
        # 保存结果
        self._startup_result = result
    
    def _on_error(self, error: str):
        """发生错误"""
        self._log_text.append(f"\n❌ 错误: {error}")
        self._continue_btn.setEnabled(True)
    
    def _on_cancel(self):
        """取消按钮"""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        self.reject()
    
    def _on_continue(self):
        """继续按钮"""
        if hasattr(self, '_startup_result'):
            self.startup_completed.emit(self._startup_result)
        self.accept()
    
    def get_result(self) -> Optional[dict]:
        """获取启动检查结果"""
        return getattr(self, '_startup_result', None)


import os

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = StartupDialog()
    dialog.exec()
    print("启动结果:", dialog.get_result())