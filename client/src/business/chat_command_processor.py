"""
聊天命令处理器 (Chat Command Processor)

支持在聊天窗口中执行命令：
- /model: 查看连接的 LLM 信息和状态
- /llmfit: 扫描硬件并推荐最适合的本地 LLM 及量化版本
- /help: 显示帮助信息

支持自然语言命令调用：
- "帮我查看模型信息" → /model
- "开始记录操作" → /record start
- "查询知识库" → /query

设计模式：命令模式 + 工厂模式 + 策略模式
"""

import os
import platform
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入统一意图定义中心和自然语言命令解析器
try:
    from business.intent_definitions import Intent
    from business.natural_command_parser import (
        get_natural_command_parser,
        ParsedCommand
    )
    NATURAL_PARSER_AVAILABLE = True
except ImportError:
    NATURAL_PARSER_AVAILABLE = False


@dataclass
class HardwareInfo:
    """硬件信息"""
    cpu_name: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    os_type: str = ""
    os_version: str = ""


@dataclass
class ModelRecommendation:
    """模型推荐"""
    model_name: str
    model_size: str  # 7B, 14B, 70B 等
    quantization: str  # Q4_K_M, Q8_0, GGUF 等
    required_ram_gb: float
    required_vram_gb: float
    recommended: bool = False
    reason: str = ""


@dataclass
class ModelInfo:
    """模型信息"""
    model_name: str
    model_type: str  # local, openai, qwen
    status: str  # connected, disconnected, loading
    context_window: int = 0
    max_tokens: int = 0
    temperature: float = 0.0
    last_used: Optional[datetime] = None
    request_count: int = 0


class CommandProcessor:
    """
    聊天命令处理器
    
    解析并执行聊天窗口中的命令，支持：
    1. 直接命令调用：/model, /llmfit, /help 等
    2. 自然语言调用："帮我查看模型信息", "开始记录操作" 等
    """
    
    def __init__(self):
        self.commands = {
            "/model": self._handle_model_command,
            "/llmfit": self._handle_llmfit_command,
            "/help": self._handle_help_command,
            "/clear": self._handle_clear_command,
            "/stats": self._handle_stats_command,
            "/ingest": self._handle_ingest_command,
            "/query": self._handle_query_command,
            "/lint": self._handle_lint_command,
            "/kb": self._handle_kb_command,
            "/record": self._handle_record_command,
            "/video": self._handle_video_command
        }
        
        # 初始化自然语言命令解析器
        self._init_natural_parser()
        
        print("[CommandProcessor] 初始化完成（含知识库、操作记录和视频录制命令，支持自然语言调用）")
    
    def _init_natural_parser(self):
        """初始化自然语言命令解析器"""
        if NATURAL_PARSER_AVAILABLE:
            try:
                self.natural_parser = get_natural_command_parser()
                print("[CommandProcessor] 自然语言命令解析器初始化完成")
            except Exception as e:
                print(f"[CommandProcessor] 自然语言命令解析器初始化失败: {e}")
                self.natural_parser = None
        else:
            self.natural_parser = None
    
    def is_command(self, message: str) -> bool:
        """判断消息是否为命令（支持直接命令和自然语言命令）"""
        message = message.strip()
        
        # 检查直接命令
        if message.startswith("/"):
            command = message.split()[0]
            return command in self.commands
        
        # 检查自然语言命令
        if self.natural_parser:
            return self.natural_parser.is_command(message)
        
        return False
    
    def parse_command(self, message: str) -> Tuple[str, str]:
        """解析命令（支持直接命令和自然语言命令）"""
        message = message.strip()
        
        # 如果是直接命令（以 / 开头）
        if message.startswith("/"):
            parts = message.split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            return command, args
        
        # 如果是自然语言命令
        if self.natural_parser:
            parsed = self.natural_parser.parse(message)
            
            # 使用统一意图定义中心判断
            if parsed.intent != Intent.NLU_FALLBACK and parsed.confidence >= 0.7:
                # 返回映射后的命令和参数
                return parsed.command, parsed.args
        
        # 默认返回原消息作为参数（非命令）
        return "", message
    
    async def execute_command(self, message: str) -> str:
        """执行命令并返回结果（支持直接命令和自然语言命令）"""
        command, args = self.parse_command(message)
        
        # 如果没有解析出命令，尝试自然语言解析
        if not command and self.natural_parser:
            parsed = self.natural_parser.parse(message)
            
            # 使用统一意图定义中心判断
            if parsed.intent != Intent.NLU_FALLBACK and parsed.confidence >= 0.7:
                command = parsed.command
                args = parsed.args
        
        if command in self.commands:
            try:
                result = await self.commands[command](args)
                # 如果是自然语言触发的命令，添加提示
                if not message.startswith("/"):
                    result = f"🔧 已识别命令: `{command}`\n\n" + result
                return result
            except Exception as e:
                return f"命令执行失败: {e}"
        
        return f"未知命令: {command}"
    
    def suggest_commands(self, message: str) -> List[Tuple[str, float]]:
        """给出命令建议（基于自然语言解析）"""
        if self.natural_parser:
            return self.natural_parser.suggest_commands(message)
        return []
    
    async def _handle_model_command(self, args: str) -> str:
        """处理 /model 命令 - 查看连接的 LLM 信息"""
        try:
            models = self._get_model_info()
            
            if not models:
                return "当前没有连接的 LLM 模型"
            
            result = "📦 已连接的 LLM 模型:\n"
            result += "──────────────────────────\n"
            
            for model in models:
                result += f"\n**{model.model_name}**\n"
                result += f"  类型: {model.model_type}\n"
                result += f"  状态: {model.status}\n"
                result += f"  上下文窗口: {model.context_window:,} tokens\n"
                result += f"  最大输出: {model.max_tokens:,} tokens\n"
                result += f"  温度: {model.temperature}\n"
                if model.last_used:
                    result += f"  最后使用: {model.last_used.strftime('%Y-%m-%d %H:%M:%S')}\n"
                result += f"  请求次数: {model.request_count}\n"
            
            return result
        
        except Exception as e:
            return f"获取模型信息失败: {e}"
    
    def _get_model_info(self) -> List[ModelInfo]:
        """获取模型信息"""
        models = []
        
        # 从 Agent Adapter 获取模型信息
        try:
            from business.agent_adapter import (
                create_agent_adapter,
                AgentConfig
            )
            
            # 检查本地模型
            local_config = AgentConfig(agent_type="local")
            local_adapter = create_agent_adapter(local_config)
            supported_models = local_adapter.get_supported_models()
            
            for model_name in supported_models[:3]:  # 只显示前3个
                models.append(ModelInfo(
                    model_name=model_name,
                    model_type="local",
                    status="connected" if local_adapter.is_available() else "disconnected",
                    context_window=8192,
                    max_tokens=2048,
                    temperature=0.7,
                    last_used=datetime.now(),
                    request_count=0
                ))
            
        except Exception as e:
            # 如果 Agent Adapter 不可用，返回空列表
            pass
        
        return models
    
    async def _handle_llmfit_command(self, args: str) -> str:
        """处理 /llmfit 命令 - 扫描硬件并推荐 LLM"""
        try:
            hardware = self._detect_hardware()
            recommendations = self._recommend_models(hardware)
            
            result = "💻 硬件检测结果:\n"
            result += "──────────────────────────\n"
            result += f"CPU: {hardware.cpu_name} ({hardware.cpu_cores}核{hardware.cpu_threads}线程)\n"
            result += f"内存: {hardware.total_ram_gb:.1f} GB (可用: {hardware.available_ram_gb:.1f} GB)\n"
            result += f"显卡: {hardware.gpu_name} ({hardware.gpu_vram_gb:.1f} GB VRAM)\n"
            result += f"系统: {hardware.os_type} {hardware.os_version}\n"
            
            result += "\n📊 推荐的本地 LLM 模型:\n"
            result += "──────────────────────────\n"
            
            for rec in recommendations:
                prefix = "✅ " if rec.recommended else "   "
                result += f"\n{prefix}**{rec.model_name}**\n"
                result += f"   模型大小: {rec.model_size}\n"
                result += f"   量化版本: {rec.quantization}\n"
                result += f"   内存需求: {rec.required_ram_gb:.1f} GB\n"
                result += f"   VRAM需求: {rec.required_vram_gb:.1f} GB\n"
                if rec.reason:
                    result += f"   {rec.reason}\n"
            
            return result
        
        except Exception as e:
            return f"硬件检测或模型推荐失败: {e}"
    
    def _detect_hardware(self) -> HardwareInfo:
        """检测硬件信息"""
        info = HardwareInfo()
        
        # 操作系统
        info.os_type = platform.system()
        info.os_version = platform.version()
        
        # CPU 信息
        try:
            if info.os_type == "Windows":
                import win32api
                import win32con
                cpu_info = win32api.GetSystemMetrics(win32con.SM_PROCESSOR_COUNT)
                info.cpu_cores = os.cpu_count() or 0
                info.cpu_threads = info.cpu_cores * 2  # 假设超线程
            else:
                info.cpu_cores = os.cpu_count() or 0
                info.cpu_threads = info.cpu_cores
            
            # 获取 CPU 名称
            if info.os_type == "Windows":
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                    info.cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                    winreg.CloseKey(key)
                except:
                    info.cpu_name = platform.processor()
            else:
                info.cpu_name = platform.processor()
        except:
            info.cpu_name = "Unknown"
        
        # 内存信息
        try:
            if info.os_type == "Windows":
                import psutil
                mem = psutil.virtual_memory()
                info.total_ram_gb = mem.total / (1024 ** 3)
                info.available_ram_gb = mem.available / (1024 ** 3)
            else:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            info.total_ram_gb = int(line.split()[1]) / 1024 / 1024
                        elif line.startswith('MemAvailable:'):
                            info.available_ram_gb = int(line.split()[1]) / 1024 / 1024
        except:
            info.total_ram_gb = 8.0
            info.available_ram_gb = 4.0
        
        # GPU 信息
        try:
            if info.os_type == "Windows":
                import wmi
                w = wmi.WMI()
                for gpu in w.Win32_VideoController():
                    info.gpu_name = gpu.Name
                    try:
                        vram = int(gpu.AdapterRAM) / (1024 ** 3)
                        info.gpu_vram_gb = vram
                    except:
                        info.gpu_vram_gb = 0
                    break
            else:
                # Linux/Mac
                try:
                    result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split(',')
                        if len(parts) >= 2:
                            info.gpu_name = parts[0].strip()
                            info.gpu_vram_gb = float(parts[1].strip()) / 1024
                except:
                    info.gpu_name = "Unknown"
        except:
            info.gpu_name = "Unknown"
            info.gpu_vram_gb = 0.0
        
        return info
    
    def _recommend_models(self, hardware: HardwareInfo) -> List[ModelRecommendation]:
        """根据硬件推荐模型"""
        recommendations = []
        
        # 定义可用模型
        models = [
            {"name": "Qwen/Qwen2.5-7B-Instruct", "size": "7B", "ram": 8, "vram": 4},
            {"name": "Qwen/Qwen2.5-14B-Instruct", "size": "14B", "ram": 16, "vram": 8},
            {"name": "Qwen/Qwen2.5-72B-Instruct", "size": "72B", "ram": 48, "vram": 24},
            {"name": "deepseek-ai/DeepSeek-V3", "size": "67B", "ram": 40, "vram": 20},
            {"name": "deepseek-ai/DeepSeek-R1", "size": "7B", "ram": 8, "vram": 4},
            {"name": "meta-llama/Meta-Llama-3-8B-Instruct", "size": "8B", "ram": 8, "vram": 4},
            {"name": "meta-llama/Meta-Llama-3-70B-Instruct", "size": "70B", "ram": 48, "vram": 24},
            {"name": "mistralai/Mistral-7B-Instruct-v0.3", "size": "7B", "ram": 8, "vram": 4},
            {"name": "mistralai/Mixtral-8x7B-Instruct-v0.1", "size": "47B", "ram": 32, "vram": 16},
        ]
        
        available_ram = min(hardware.total_ram_gb, hardware.available_ram_gb + 2)
        available_vram = hardware.gpu_vram_gb
        
        for model in models:
            # 确定量化版本
            if available_vram >= model["vram"] * 2:
                quantization = "Q8_0 (高质量)"
                required_ram = model["ram"]
                required_vram = model["vram"] * 1.5
            elif available_vram >= model["vram"]:
                quantization = "Q4_K_M (平衡)"
                required_ram = model["ram"] * 0.6
                required_vram = model["vram"] * 0.7
            elif available_vram >= model["vram"] * 0.5:
                quantization = "Q2_K (轻量化)"
                required_ram = model["ram"] * 0.4
                required_vram = model["vram"] * 0.4
            else:
                quantization = "GGUF Q4 (CPU运行)"
                required_ram = model["ram"] * 0.7
                required_vram = 0
            
            recommended = False
            reason = ""
            
            if available_ram >= required_ram and (available_vram >= required_vram or required_vram == 0):
                if available_ram >= model["ram"] * 1.5 and available_vram >= model["vram"] * 1.2:
                    recommended = True
                    reason = "✅ 推荐：硬件配置充足"
                else:
                    reason = "⚠️ 可用：硬件刚好满足需求"
            else:
                reason = "❌ 不推荐：硬件资源不足"
            
            recommendations.append(ModelRecommendation(
                model_name=model["name"],
                model_size=model["size"],
                quantization=quantization,
                required_ram_gb=required_ram,
                required_vram_gb=required_vram,
                recommended=recommended,
                reason=reason
            ))
        
        # 按推荐优先级排序
        recommendations.sort(key=lambda x: (x.recommended, -x.required_ram_gb))
        
        return recommendations
    
    async def _handle_help_command(self, args: str) -> str:
        """处理 /help 命令 - 显示帮助信息"""
        result = "📋 聊天命令帮助:\n"
        result += "──────────────────────────\n"
        result += "\n【系统命令】\n"
        result += "/model - 查看连接的 LLM 模型信息和状态\n"
        result += "/llmfit - 扫描硬件并推荐最适合的本地 LLM 及量化版本\n"
        result += "/stats - 查看系统统计信息\n"
        result += "/clear - 清空聊天记录\n"
        result += "/help - 显示此帮助信息\n"
        result += "\n【知识库命令】\n"
        result += "/kb init - 初始化知识库规则\n"
        result += "/kb status - 查看知识库状态\n"
        result += "/ingest - 从 raw/ 摄入资料到 wiki/\n"
        result += "/query <问题> - 查询知识库并返回带引用的答案\n"
        result += "/lint - 知识库健康检查（找矛盾、补缺口、清孤儿页面）\n"
        result += "\n【操作记录命令】\n"
        result += "/record start - 开始记录屏幕操作（低资源消耗）\n"
        result += "/record stop - 停止记录并生成会话总结\n"
        result += "/record summary - 获取当前会话总结\n"
        result += "/record status - 查看记录状态\n"
        result += "\n【视频录制命令】\n"
        result += "/video start - 开始视频录制\n"
        result += "/video stop - 停止视频录制\n"
        result += "/video status - 查看录制状态\n"
        result += "/video list - 列出录制文件\n"
        result += "/video config - 查看/设置录制配置\n"
        result += "\n──────────────────────────\n"
        result += "提示：输入命令时无需加引号，直接输入即可"
        return result
    
    async def _handle_clear_command(self, args: str) -> str:
        """处理 /clear 命令 - 清空聊天记录"""
        # 触发清空事件
        from business.shared.event_bus import EventBus, get_event_bus, EVENTS
        
        event_bus = get_event_bus()
        event_bus.publish(EVENTS["CHAT_CLEAR"], {})
        
        return "聊天记录已清空"
    
    async def _handle_stats_command(self, args: str) -> str:
        """处理 /stats 命令 - 显示系统统计信息"""
        try:
            # 获取 FusionRAG 统计
            try:
                from business.fusion_rag import create_fusion_rag
                
                fusion_rag = create_fusion_rag()
                stats = fusion_rag.get_stats()
                
                result = "📊 系统统计信息:\n"
                result += "──────────────────────────\n"
                
                if "governance" in stats:
                    g = stats["governance"]
                    result += f"\n治理模块:\n"
                    result += f"  检查文档数: {g.get('total_docs_checked', 0)}\n"
                    result += f"  通过文档数: {g.get('passed_docs', 0)}\n"
                    result += f"  通过率: {g.get('pass_rate', 0):.1f}%\n"
                
                if "tier_manager" in stats:
                    t = stats["tier_manager"]
                    result += f"\n分层管理器:\n"
                    result += f"  L1 文档数: {t.get('l1_docs', 0)}\n"
                    result += f"  L2 文档数: {t.get('l2_docs', 0)}\n"
                    result += f"  L3 文档数: {t.get('l3_docs', 0)}\n"
                
                return result
            
            except Exception as e:
                return f"获取统计信息失败: {e}"
        
        except Exception as e:
            return f"获取统计信息失败: {e}"
    
    async def _handle_ingest_command(self, args: str) -> str:
        """处理 /ingest 命令 - 从 raw/ 摄入资料到 wiki/"""
        try:
            from business.knowledge_base_manager import get_knowledge_manager
            
            kb_manager = get_knowledge_manager()
            result = await kb_manager.ingest_from_raw()
            
            response = "📥 资料摄入完成!\n"
            response += "──────────────────────────\n"
            response += f"处理文件数: {result.files_processed}\n"
            response += f"抽取术语数: {result.terms_extracted}\n"
            response += f"更新页面数: {result.pages_updated}\n"
            response += f"新建页面数: {result.new_pages_created}\n"
            
            if result.errors:
                response += f"\n❌ 错误: {len(result.errors)} 个"
            
            return response
        
        except Exception as e:
            return f"资料摄入失败: {e}"
    
    async def _handle_query_command(self, args: str) -> str:
        """处理 /query 命令 - 查询知识库"""
        try:
            from business.knowledge_base_manager import get_knowledge_manager
            
            if not args:
                return "请输入查询内容，例如: /query 工业AI应用场景"
            
            kb_manager = get_knowledge_manager()
            result = await kb_manager.query(args)
            
            response = "📚 查询结果:\n"
            response += "──────────────────────────\n"
            response += f"\n{result.answer}\n"
            
            if result.sources:
                response += "\n📖 来源:\n"
                for source in result.sources[:3]:
                    response += f"- {source.get('title', '')}\n"
            
            if result.related_topics:
                response += "\n🔗 关联主题:\n"
                for topic in result.related_topics[:5]:
                    response += f"- [[{topic}]]\n"
            
            return response
        
        except Exception as e:
            return f"查询失败: {e}"
    
    async def _handle_lint_command(self, args: str) -> str:
        """处理 /lint 命令 - 知识库健康检查"""
        try:
            from business.knowledge_base_manager import get_knowledge_manager
            
            kb_manager = get_knowledge_manager()
            issues = await kb_manager.lint()
            
            # 统计各类问题
            issue_counts = {
                "contradictions": 0,
                "gaps": 0,
                "orphans": 0,
                "outdated": 0
            }
            
            for issue in issues:
                issue_counts[issue.issue_type] += 1
            
            response = "🔍 知识库健康检查完成!\n"
            response += "──────────────────────────\n"
            response += f"知识矛盾: {issue_counts['contradictions']}\n"
            response += f"内容缺口: {issue_counts['gaps']}\n"
            response += f"孤儿页面: {issue_counts['orphans']}\n"
            response += f"过期信息: {issue_counts['outdated']}\n"
            
            if issues:
                response += "\n📋 问题详情:\n"
                for issue in issues[:5]:
                    severity = "🔴" if issue.severity == "high" else "🟡" if issue.severity == "medium" else "🟢"
                    response += f"{severity} {issue.page_title}: {issue.description}\n"
            
            # 自动修复
            if issues:
                fixed = await kb_manager.auto_fix(issues)
                response += f"\n✅ 自动修复: {fixed}/{len(issues)} 个问题"
            
            return response
        
        except Exception as e:
            return f"健康检查失败: {e}"
    
    async def _handle_kb_command(self, args: str) -> str:
        """处理 /kb 命令 - 知识库管理"""
        try:
            from business.knowledge_base_manager import get_knowledge_manager
            
            kb_manager = get_knowledge_manager()
            
            if args == "init":
                kb_manager.create_default_rules()
                return "✅ 知识库规则已创建! 路径: knowledge_base/KNOWLEDGE_RULES.md"
            
            elif args == "status":
                # 统计 wiki 页面数量
                pages = list(kb_manager.wiki_path.glob("*.md"))
                raw_files = list(kb_manager.raw_path.glob("**/*.md")) + list(kb_manager.raw_path.glob("**/*.txt"))
                
                response = "📊 知识库状态:\n"
                response += "──────────────────────────\n"
                response += f"wiki/ 页面数: {len(pages)}\n"
                response += f"raw/ 文件数: {len(raw_files)}\n"
                response += f"规则文件: {'存在' if kb_manager.rules_file.exists() else '不存在'}\n"
                
                return response
            
            else:
                return "📋 知识库命令:\n" \
                       "- /kb init: 初始化知识库规则\n" \
                       "- /kb status: 查看知识库状态\n" \
                       "- /ingest: 摄入资料\n" \
                       "- /query <问题>: 查询知识库\n" \
                       "- /lint: 健康检查"
        
        except Exception as e:
            return f"知识库操作失败: {e}"
    
    async def _handle_record_command(self, args: str) -> str:
        """处理 /record 命令 - 操作记录管理"""
        try:
            from business.action_memory_system import get_action_memory_system
            
            action_memory = get_action_memory_system()
            
            if args == "start":
                session_id = action_memory.start_session()
                return f"✅ 开始操作记录! 会话ID: {session_id}\n\n系统将每30秒捕获一次屏幕状态，记录您的操作。\n使用 /record stop 停止记录。"
            
            elif args == "stop":
                action_memory.end_session()
                return "⏹️ 操作记录已停止。\n\n会话总结已保存到记忆图，可用于后续分析和知识关联。"
            
            elif args == "summary":
                summary = action_memory.get_session_summary()
                if summary:
                    return f"📊 当前会话总结:\n\n{summary}"
                else:
                    return "❌ 没有活跃的会话或未记录任何操作。"
            
            elif args == "status":
                return "📋 操作记录状态:\n" \
                       "- 状态: " + ("🟢 正在记录" if action_memory.is_recording else "🔴 未记录") + "\n" \
                       "- 快照间隔: 30秒\n" \
                       "- 会话操作数: " + str(len(action_memory.active_session.actions) if action_memory.active_session else 0)
            
            else:
                return "📋 操作记录命令:\n" \
                       "- /record start: 开始记录操作\n" \
                       "- /record stop: 停止记录并总结\n" \
                       "- /record summary: 获取当前会话总结\n" \
                       "- /record status: 查看记录状态"
        
        except Exception as e:
            return f"操作记录失败: {e}"
    
    async def _handle_video_command(self, args: str) -> str:
        """处理 /video 命令 - 视频录制管理"""
        try:
            from business.video_recording_service import (
                get_video_recording_service,
                RecordingQuality
            )
            
            video_service = get_video_recording_service()
            
            parts = args.split()
            sub_command = parts[0] if parts else ""
            options = parts[1:] if len(parts) > 1 else []
            
            if sub_command == "start":
                # 解析选项
                quality = "medium"
                mode = "full_screen"
                
                for opt in options:
                    if opt.startswith("quality="):
                        quality = opt.split("=")[1]
                    elif opt.startswith("mode="):
                        mode = opt.split("=")[1]
                
                session_id = video_service.start_recording(quality=quality, mode=mode)
                return f"🎥 开始视频录制! 会话ID: {session_id}\n\n质量: {quality}\n模式: {mode}\n使用 /video stop 停止录制。"
            
            elif sub_command == "stop":
                video_path = video_service.stop_recording()
                if video_path:
                    return f"⏹️ 视频录制已停止。\n\n文件已保存到: {video_path}\n\n自动生成的摘要已保存到知识库和记忆图。"
                else:
                    return "❌ 没有正在进行的录制。"
            
            elif sub_command == "status":
                status = video_service.get_recording_status()
                if status["is_recording"]:
                    return f"📹 录制状态:\n" \
                           f"- 状态: 🟢 正在录制\n" \
                           f"- 会话ID: {status['session_id']}\n" \
                           f"- 已录制: {status['elapsed_seconds']} 秒\n" \
                           f"- 质量: {status['quality']}\n" \
                           f"- 模式: {status['mode']}"
                else:
                    return "📹 录制状态: 🔴 未在录制"
            
            elif sub_command == "list":
                recordings = video_service.list_recordings()
                if recordings:
                    result = "📋 录制文件列表:\n\n"
                    for i, rec in enumerate(recordings, 1):
                        result += f"{i}. {rec['filename']} ({rec['size']} bytes)\n"
                    return result
                else:
                    return "📋 暂无录制文件。"
            
            elif sub_command == "config":
                config = video_service.get_config()
                return f"⚙️ 当前视频配置:\n" \
                       f"- 质量: {config.quality.value}\n" \
                       f"- 模式: {config.mode.value}\n" \
                       f"- 帧率: {config.frame_rate} fps\n" \
                       f"- 最大时长: {config.max_duration} 秒\n" \
                       f"- 自动压缩: {'是' if config.auto_compress else '否'}\n" \
                       f"- 自动摘要: {'是' if config.auto_summarize else '否'}"
            
            elif sub_command.startswith("config set"):
                # 设置配置
                config_args = {}
                for opt in options:
                    if "=" in opt:
                        key, value = opt.split("=", 1)
                        config_args[key] = value
                
                if config_args:
                    video_service.set_config(**config_args)
                    return f"✅ 视频配置已更新:\n{config_args}"
                else:
                    return "❌ 请指定要设置的配置项，如: /video config set quality=high"
            
            else:
                return "📹 视频录制命令:\n" \
                       "- /video start [quality=high|medium|low] [mode=full_screen|active_window]: 开始录制\n" \
                       "- /video stop: 停止录制\n" \
                       "- /video status: 查看录制状态\n" \
                       "- /video list: 列出录制文件\n" \
                       "- /video config: 查看当前配置\n" \
                       "- /video config set <key=value>: 设置配置"
        
        except Exception as e:
            return f"视频录制失败: {e}"


# 创建全局实例
_command_processor = CommandProcessor()


def get_command_processor() -> CommandProcessor:
    """获取命令处理器实例"""
    return _command_processor


async def process_command(message: str) -> Optional[str]:
    """处理消息，如果是命令则执行并返回结果"""
    processor = get_command_processor()
    
    if processor.is_command(message):
        return await processor.execute_command(message)
    
    return None


__all__ = [
    "CommandProcessor",
    "HardwareInfo",
    "ModelRecommendation",
    "ModelInfo",
    "get_command_processor",
    "process_command"
]