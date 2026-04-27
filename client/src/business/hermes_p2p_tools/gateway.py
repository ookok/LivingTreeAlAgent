"""
Hermes P2P Gateway - UI与Hermes消息打通
==========================================

核心理念：作为P2P系统的"交互大脑"，Hermes Gateway将：
1. UI事件 → Hermes消息格式
2. Hermes响应 → UI可执行指令
3. 工具调用结果 → 实时UI更新

架构流程：
UI事件 → Gateway.format_message() → Hermes消息 → Agent处理
                                                         ↓
UI更新 ← Gateway.format_response() ← 响应格式化 ← 工具结果

Author: Hermes Desktop AI Assistant
"""

import json
import logging
import threading
import asyncio
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    # 用户操作
    USER_ACTION = "user_action"           # UI用户操作
    USER_TEXT = "user_text"              # 文本输入
    USER_CLICK = "user_click"            # 按钮点击

    # 系统事件
    CONFIG_CHANGE = "config_change"      # 配置变更
    NETWORK_EVENT = "network_event"       # 网络事件
    TOOL_RESULT = "tool_result"          # 工具执行结果

    # Hermes响应
    HERMES_INSIGHT = "hermes_insight"     # Hermes洞察
    HERMES_GUIDE = "hermes_guide"         # 引导指令
    HERMES_WARNING = "hermes_warning"      # 警告提示
    HERMES_SUCCESS = "hermes_success"      # 成功通知


@dataclass
class GatewayMessage:
    """Gateway消息格式"""
    type: MessageType
    content: Any
    source: str = "gateway"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "metadata": self.metadata
        }


@dataclass
class UIAction:
    """UI操作指令"""
    action_type: str          # 操作类型：navigate, show_toast, highlight, open_url, etc.
    target: str               # 目标元素或组件
    params: Dict = field(default_factory=dict)
    priority: int = 0         # 优先级


class HermesGateway:
    """
    Hermes P2P Gateway

    功能：
    1. 接收UI事件，转换为Hermes可处理的格式
    2. 接收Hermes响应，转换为UI可执行指令
    3. 管理对话上下文，支持多轮交互
    4. 集成自适应引导系统

    使用示例：
        gateway = HermesGateway()
        gateway.set_ui_callback(self.update_ui)

        # 发送用户点击事件
        gateway.send_ui_event("button_click", {"id": "enable_advanced"})

        # 获取Hermes建议
        suggestions = gateway.get_hermes_suggestions()
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._lock = threading.RLock()

        # 回调
        self._ui_callback: Optional[Callable] = None
        self._agent_callback: Optional[Callable] = None

        # 上下文
        self._session_id: Optional[str] = None
        self._conversation_history: List[Dict] = []
        self._pending_actions: List[UIAction] = []

        # 组件
        self._agent = None
        self._adaptive_guide = None
        self._p2p_tools = None

        # 配置
        self._enable_auto_guide = self.config.get("enable_auto_guide", True)
        self._enable记忆 = self.config.get("enable_memory", True)

        logger.info("HermesGateway 初始化完成")

    # ── 初始化 ─────────────────────────────────────────────────────────

    def initialize(self, agent=None):
        """
        初始化Gateway及其依赖组件

        Args:
            agent: HermesAgent实例（如不提供则创建）
        """
        with self._lock:
            # 初始化P2P工具
            from client.src.business.hermes_p2p_tools import register_p2p_tools
            register_p2p_tools()

            # 初始化自适应引导
            if self._enable_auto_guide:
                from client.src.business.adaptive_guide import get_guide_manager
                self._adaptive_guide = get_guide_manager()

            # 关联Agent
            if agent:
                self._agent = agent

            # 初始化会话
            self._session_id = self._generate_session_id()

            logger.info(f"HermesGateway 初始化完成，会话: {self._session_id}")

    def set_ui_callback(self, callback: Callable[[UIAction], None]):
        """设置UI回调"""
        self._ui_callback = callback

    def set_agent_callback(self, callback: Callable):
        """设置Agent回调"""
        self._agent_callback = callback

    # ── 消息转换 ───────────────────────────────────────────────────────

    def format_ui_event(self, event_type: str, event_data: Dict) -> GatewayMessage:
        """
        将UI事件转换为Hermes消息格式

        Args:
            event_type: 事件类型（click, change, input等）
            event_data: 事件数据

        Returns:
            GatewayMessage: Hermes可处理的格式
        """
        content = {
            "event": event_type,
            "data": event_data,
            "intent": self._infer_intent(event_type, event_data)
        }

        msg = GatewayMessage(
            type=MessageType.USER_ACTION,
            content=content,
            session_id=self._session_id,
            metadata={"event_type": event_type}
        )

        # 记录到历史
        self._add_to_history("user", content)

        return msg

    def format_hermes_response(self, response: Dict) -> List[UIAction]:
        """
        将Hermes响应转换为UI可执行指令

        Args:
            response: Hermes响应

        Returns:
            List[UIAction]: UI操作指令列表
        """
        actions = []

        # 解析Hermes响应类型
        response_type = response.get("type", "text")
        content = response.get("content", {})

        if response_type == "tool_call":
            # 工具调用响应
            actions.extend(self._parse_tool_response(content))
        elif response_type == "guide":
            # 引导指令
            actions.extend(self._parse_guide_response(content))
        elif response_type == "insight":
            # 洞察建议
            actions.append(UIAction(
                action_type="show_insight",
                target="insight_panel",
                params={"content": content},
                priority=1
            ))
        elif response_type == "text":
            # 文本响应
            actions.append(UIAction(
                action_type="show_message",
                target="chat_panel",
                params={"text": content.get("text", ""), "type": "assistant"},
                priority=0
            ))

        return actions

    def _infer_intent(self, event_type: str, event_data: Dict) -> str:
        """从UI事件推断用户意图"""
        # 基于事件类型和数据推断意图
        if event_type == "button_click":
            button_id = event_data.get("id", "")
            if "config" in button_id:
                return "configure"
            elif "enable" in button_id:
                return "enable_feature"
            elif "search" in button_id:
                return "search"
            elif "download" in button_id:
                return "download"
        elif event_type == "form_submit":
            return "submit_config"
        elif event_type == "tab_change":
            return "navigate"

        return "unknown"

    def _parse_tool_response(self, content: Dict) -> List[UIAction]:
        """解析工具调用响应"""
        actions = []
        tool_name = content.get("tool")
        result = content.get("result", {})

        if tool_name == "p2p_check_config":
            if not result.get("success"):
                actions.append(UIAction(
                    action_type="show_error",
                    target="config_panel",
                    params={"message": result.get("error", "配置检查失败")},
                    priority=2
                ))
            else:
                missing = result.get("missing_items", [])
                if missing:
                    actions.append(UIAction(
                        action_type="show_config_guide",
                        target="guide_panel",
                        params={"missing": missing},
                        priority=1
                    ))

        elif tool_name == "p2p_download_model":
            if result.get("success"):
                task_id = result.get("task_id")
                actions.append(UIAction(
                    action_type="show_download_progress",
                    target="download_panel",
                    params={"task_id": task_id},
                    priority=1
                ))

        return actions

    def _parse_guide_response(self, content: Dict) -> List[UIAction]:
        """解析引导响应"""
        actions = []

        guide_type = content.get("guide_type")
        steps = content.get("steps", [])

        if guide_type == "shortest_path":
            actions.append(UIAction(
                action_type="start_guide_flow",
                target="guide_panel",
                params={"steps": steps},
                priority=1
            ))
        elif guide_type == "browser_automation":
            url = content.get("url")
            actions.append(UIAction(
                action_type="open_browser",
                target="browser",
                params={"url": url, "highlight": content.get("highlight")},
                priority=2
            ))

        return actions

    # ── 对话管理 ──────────────────────────────────────────────────────

    def send_ui_event(self, event_type: str, event_data: Dict) -> Dict:
        """
        发送UI事件到Hermes处理

        Args:
            event_type: 事件类型
            event_data: 事件数据

        Returns:
            处理结果
        """
        # 1. 格式化消息
        msg = self.format_ui_event(event_type, event_data)

        # 2. 发送到Hermes
        if self._agent:
            response = self._process_with_hermes(msg)
        else:
            # 无Agent时，使用自适应引导
            response = self._process_with_guide(msg)

        # 3. 格式化响应为UI动作
        actions = self.format_hermes_response(response)

        # 4. 执行UI回调
        for action in actions:
            self._execute_ui_action(action)

        # 5. 保存到记忆（如果启用）
        if self._enable记忆:
            self._save_to_memory(msg, response)

        return {"success": True, "actions": len(actions)}

    def _process_with_hermes(self, msg: GatewayMessage) -> Dict:
        """使用Hermes Agent处理消息"""
        try:
            # 构建Hermes消息格式
            hermes_msg = self._build_hermes_message(msg)

            # 调用Agent
            if self._agent_callback:
                return self._agent_callback(hermes_msg)

            # 如果Agent有run方法
            if hasattr(self._agent, 'run_conversation'):
                # 同步调用
                return {"type": "text", "content": {"text": "Agent处理中..."}}

            return {"type": "text", "content": {"text": "Agent未初始化"}}
        except Exception as e:
            logger.error(f"Hermes处理失败: {e}")
            return {"type": "error", "content": {"error": str(e)}}

    def _process_with_guide(self, msg: GatewayMessage) -> Dict:
        """使用自适应引导处理消息（无Agent时）"""
        try:
            event_content = msg.content
            intent = event_content.get("intent", "")

            if intent == "configure":
                # 配置相关，触发引导
                if self._adaptive_guide:
                    feature = event_content.get("data", {}).get("feature", "general")
                    result = self._adaptive_guide.check_and_retrieve_api_keys(feature)
                    return {
                        "type": "guide",
                        "content": {
                            "guide_type": "api_key_config",
                            "result": result
                        }
                    }

            elif intent == "enable_feature":
                # 启用功能，检查配置
                if self._adaptive_guide:
                    feature = event_content.get("data", {}).get("feature")
                    validation = self._adaptive_guide.validate_config(feature)
                    return {
                        "type": "tool_call",
                        "content": {
                            "tool": "p2p_check_config",
                            "result": validation
                        }
                    }

            return {"type": "text", "content": {"text": f"收到事件: {intent}"}}
        except Exception as e:
            logger.error(f"引导处理失败: {e}")
            return {"type": "error", "content": {"error": str(e)}}

    def _build_hermes_message(self, msg: GatewayMessage) -> str:
        """构建Hermes系统消息"""
        content = msg.content

        system_prompt = f"""你是一个P2P系统配置助手。用户刚刚执行了一个操作：

事件类型: {content.get('event')}
意图: {content.get('intent')}
数据: {json.dumps(content.get('data', {}), ensure_ascii=False)}

请分析这个操作：
1. 用户想要完成什么？
2. 需要哪些配置？
3. 是否需要引导用户完成配置？

以JSON格式返回你的分析和建议。
"""

        return system_prompt

    def _execute_ui_action(self, action: UIAction):
        """执行UI动作"""
        if self._ui_callback:
            try:
                self._ui_callback(action)
            except Exception as e:
                logger.error(f"执行UI动作失败: {e}")

    # ── 记忆管理 ──────────────────────────────────────────────────────

    def _add_to_history(self, role: str, content: Any):
        """添加到对话历史"""
        with self._lock:
            self._conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            # 限制历史长度
            if len(self._conversation_history) > 100:
                self._conversation_history = self._conversation_history[-100:]

    def _save_to_memory(self, msg: GatewayMessage, response: Dict):
        """保存到长期记忆"""
        try:
            # 提取关键信息
            event_type = msg.content.get("event")
            intent = msg.content.get("intent")

            # 重要交互才保存
            if intent in ("configure", "enable_feature") and response.get("success"):
                from client.src.business.memory_manager import MemoryManager
                mm = MemoryManager()
                mm.append_memory(
                    f"用户完成了{intent}操作: {event_type}。"
                    f"系统响应: {response.get('type', 'unknown')}"
                )
        except Exception as e:
            logger.warning(f"保存记忆失败: {e}")

    # ── 辅助方法 ───────────────────────────────────────────────────────

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        import uuid
        return f"p2p_{uuid.uuid4().hex[:8]}"

    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self._conversation_history.copy()

    def get_pending_actions(self) -> List[UIAction]:
        """获取待执行的UI动作"""
        return self._pending_actions.copy()

    def clear_history(self):
        """清空对话历史"""
        with self._lock:
            self._conversation_history = []


# ── 全局单例 ──────────────────────────────────────────────────────────────

_gateway_instance: Optional[HermesGateway] = None
_gateway_lock = threading.Lock()


def get_hermes_gateway(config: Optional[Dict] = None) -> HermesGateway:
    """获取Gateway单例"""
    global _gateway_instance

    with _gateway_lock:
        if _gateway_instance is None:
            _gateway_instance = HermesGateway(config)
        return _gateway_instance


def reset_gateway():
    """重置Gateway"""
    global _gateway_instance

    with _gateway_lock:
        if _gateway_instance:
            _gateway_instance.clear_history()
        _gateway_instance = None