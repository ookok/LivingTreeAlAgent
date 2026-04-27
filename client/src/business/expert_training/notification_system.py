"""
智能体通知系统 - 专家角色创建/更新后自动通知其他智能体
支持多种通知方式：文件通知、消息总线、WebSocket推送
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
from queue import Queue, Empty


class AgentNotificationSystem:
    """
    智能体通知系统
    
    通知方式：
    1. 文件通知（默认）：写入通知文件，其他智能体轮询读取
    2. 消息总线（可选）：通过消息队列发布通知
    3. WebSocket推送（可选）：实时推送给在线智能体
    """
    
    def __init__(self, notification_dir: Optional[str] = None):
        """
        初始化通知系统
        
        Args:
            notification_dir: 通知文件存储目录
        """
        if notification_dir is None:
            project_root = Path(__file__).parent.parent.parent
            notification_dir = project_root / ".livingtree" / "notifications"
        
        self.notification_dir = Path(notification_dir)
        self.notification_dir.mkdir(parents=True, exist_ok=True)
        
        # 消息队列（内存中，用于进程内通知）
        self._message_queue = Queue()
        
        # 通知监听器
        self._listeners: List[Callable] = []
        
        # 轮询线程（用于文件通知）
        self._polling_thread = None
        self._polling_active = False
        
    def send_notification(self, notification: Dict) -> bool:
        """
        发送通知
        
        Args:
            notification: 通知内容字典
            
        Returns:
            是否发送成功
        """
        try:
            # 1. 写入通知文件
            self._write_notification_file(notification)
            
            # 2. 放入内存消息队列
            self._message_queue.put(notification)
            
            # 3. 调用注册的监听器
            for listener in self._listeners:
                try:
                    listener(notification)
                except Exception as e:
                    print(f"[通知系统] 监听器执行失败：{e}")
            
            # 4. TODO: 发送到消息总线
            # self._send_to_message_bus(notification)
            
            # 5. TODO: WebSocket推送
            # self._send_via_websocket(notification)
            
            print(f"[通知系统] 通知已发送：{notification.get('type')} - {notification.get('message')}")
            return True
            
        except Exception as e:
            print(f"[通知系统] 发送通知失败：{e}")
            return False
    
    def _write_notification_file(self, notification: Dict):
        """写入通知文件"""
        timestamp = int(time.time() * 1000)  # 毫秒时间戳，避免冲突
        notification_type = notification.get("type", "unknown")
        notification_file = self.notification_dir / f"{notification_type}_{timestamp}.json"
        
        # 添加通知元数据
        notification_with_meta = {
            "notification_id": f"NOTIF_{timestamp}",
            "timestamp": datetime.now().isoformat(),
            "source": "expert_training_system",
            "payload": notification
        }
        
        notification_file.write_text(
            json.dumps(notification_with_meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        # 清理旧通知文件（保留最近100个）
        self._cleanup_old_notifications()
    
    def _cleanup_old_notifications(self, keep_count: int = 100):
        """清理旧的通知文件"""
        try:
            notification_files = sorted(
                self.notification_dir.glob("*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            for old_file in notification_files[keep_count:]:
                try:
                    old_file.unlink()
                except Exception as e:
                    print(f"[通知系统] 删除旧通知失败 {old_file.name}: {e}")
        except Exception as e:
            print(f"[通知系统] 清理旧通知失败：{e}")
    
    def register_listener(self, listener: Callable[[Dict], None]):
        """
        注册通知监听器
        
        Args:
            listener: 回调函数，接收通知字典作为参数
        """
        self._listeners.append(listener)
        print(f"[通知系统] 已注册监听器，当前共 {len(self._listeners)} 个监听器")
    
    def unregister_listener(self, listener: Callable[[Dict], None]) -> bool:
        """取消注册通知监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
            print(f"[通知系统] 已取消注册监听器，剩余 {len(self._listeners)} 个")
            return True
        return False
    
    def start_polling(self, poll_interval: float = 5.0):
        """
        启动轮询线程，监听新的通知文件
        
        Args:
            poll_interval: 轮询间隔（秒）
        """
        if self._polling_active:
            print("[通知系统] 轮询已在运行")
            return
        
        self._polling_active = True
        self._polling_thread = threading.Thread(
            target=self._poll_notifications,
            args=(poll_interval,),
            daemon=True,
            name="NotificationPollingThread"
        )
        self._polling_thread.start()
        print(f"[通知系统] 轮询已启动，间隔 {poll_interval} 秒")
    
    def stop_polling(self):
        """停止轮询线程"""
        self._polling_active = False
        if self._polling_thread:
            self._polling_thread.join(timeout=5)
            print("[通知系统] 轮询已停止")
    
    def _poll_notifications(self, poll_interval: float):
        """轮询通知文件（在线程中运行）"""
        processed_files = set()
        
        while self._polling_active:
            try:
                # 扫描通知文件
                notification_files = list(self.notification_dir.glob("*.json"))
                
                for file_path in notification_files:
                    if file_path in processed_files:
                        continue
                    
                    try:
                        notification_data = json.loads(file_path.read_text(encoding="utf-8"))
                        
                        # 调用监听器
                        for listener in self._listeners:
                            try:
                                listener(notification_data.get("payload", notification_data))
                            except Exception as e:
                                print(f"[通知系统] 监听器执行失败：{e}")
                        
                        processed_files.add(file_path)
                        
                    except Exception as e:
                        print(f"[通知系统] 处理通知文件失败 {file_path.name}: {e}")
                
                # 限制已处理文件集合的大小
                if len(processed_files) > 1000:
                    processed_files = set(list(processed_files)[-500:])
                
            except Exception as e:
                print(f"[通知系统] 轮询出错：{e}")
            
            time.sleep(poll_interval)
    
    def get_pending_notifications(self, since_timestamp: Optional[float] = None) -> List[Dict]:
        """
        获取待处理的通知
        
        Args:
            since_timestamp: 只获取指定时间戳之后的通知
            
        Returns:
            通知列表
        """
        notifications = []
        
        try:
            notification_files = sorted(
                self.notification_dir.glob("*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            for file_path in notification_files:
                if since_timestamp:
                    if file_path.stat().st_mtime < since_timestamp:
                        break
                
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    notifications.append(data)
                except Exception as e:
                    print(f"[通知系统] 读取通知失败 {file_path.name}: {e}")
        
        except Exception as e:
            print(f"[通知系统] 获取待处理通知失败：{e}")
        
        return notifications
    
    def create_expert_notification(self,
                                   expert_name: str,
                                   expert_path: str,
                                   action: str,
                                   details: Optional[Dict] = None) -> Dict:
        """
        创建专家相关的通知
        
        Args:
            expert_name: 专家名称
            expert_path: 专家路径
            action: 动作（created/updated/deleted）
            details: 额外详情
            
        Returns:
            通知字典
        """
        action_text = {
            "created": "创建",
            "updated": "更新",
            "deleted": "删除"
        }.get(action, action)
        
        notification = {
            "type": f"expert_{action}",
            "timestamp": datetime.now().isoformat(),
            "message": f"专家角色「{expert_name}」已{action_text}",
            "expert_name": expert_name,
            "expert_path": expert_path,
            "action": action,
            "details": details or {}
        }
        
        return notification


# 全局通知系统实例
_notification_system_instance = None
_notification_system_lock = threading.Lock()

def get_notification_system() -> AgentNotificationSystem:
    """获取通知系统单例"""
    global _notification_system_instance
    
    with _notification_system_lock:
        if _notification_system_instance is None:
            _notification_system_instance = AgentNotificationSystem()
        return _notification_system_instance


# 便捷函数
def notify_expert_created(expert_name: str, expert_path: str, details: Optional[Dict] = None):
    """通知：专家已创建"""
    system = get_notification_system()
    notification = system.create_expert_notification(expert_name, expert_path, "created", details)
    return system.send_notification(notification)

def notify_expert_updated(expert_name: str, expert_path: str, details: Optional[Dict] = None):
    """通知：专家已更新"""
    system = get_notification_system()
    notification = system.create_expert_notification(expert_name, expert_path, "updated", details)
    return system.send_notification(notification)

def notify_expert_deleted(expert_name: str, expert_path: str, details: Optional[Dict] = None):
    """通知：专家已删除"""
    system = get_notification_system()
    notification = system.create_expert_notification(expert_name, expert_path, "deleted", details)
    return system.send_notification(notification)


if __name__ == "__main__":
    # 测试代码
    import time as ttime
    
    # 初始化通知系统
    notification_system = get_notification_system()
    
    # 注册监听器
    def print_listener(notification: Dict):
        print(f"[监听器1] 收到通知：{notification.get('message')}")
    
    def log_listener(notification: Dict):
        print(f"[监听器2] 记录通知：{notification.get('type')}")
    
    notification_system.register_listener(print_listener)
    notification_system.register_listener(log_listener)
    
    # 发送测试通知
    test_notification = {
        "type": "expert_created",
        "expert_name": "环评专家",
        "expert_path": ".livingtree/skills/agency-agents-zh/environmental-impact-assessment-expert",
        "message": "专家角色「环评专家」已创建"
    }
    
    notification_system.send_notification(test_notification)
    
    # 启动轮询
    notification_system.start_polling(poll_interval=2.0)
    
    # 等待一下，让轮询线程处理
    ttime.sleep(3)
    
    # 停止轮询
    notification_system.stop_polling()
    
    print("\n[测试] 通知系统测试完成")
