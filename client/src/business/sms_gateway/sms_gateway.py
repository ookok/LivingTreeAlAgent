"""
智能短信网关 (Smart SMS Gateway)

核心功能：
1. 统一入口：对外提供 send_sms() 接口
2. 策略模式：封装阿里云、腾讯云短信服务
3. 额度计数器：利用 Redis 做原子计数
4. 智能路由：自动选择最划算（免费）的渠道
5. 熔断机制：额度耗尽自动切换，触发告警
6. 自动重置：定时任务每月重置额度
7. 邮箱兜底：短信不可用时自动切换到邮件通知

目标：将阿里云（100条/月）+ 腾讯云（1000条/月）免费额度无缝叠加。
"""
import json
import os
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.header import Header
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path


class SmsChannel(Enum):
    """短信渠道"""
    ALIYUN = "aliyun"      # 阿里云短信
    TENCENT = "tencent"    # 腾讯云短信
    ALIBABA = "alibaba"    # 备用渠道


class ChannelStatus(Enum):
    """渠道状态"""
    NORMAL = "normal"          # 正常可用
    EXHAUSTED = "exhausted"    # 额度耗尽
    SUSPENDED = "suspended"    # 暂停使用（熔断）


@dataclass
class ChannelConfig:
    """渠道配置"""
    channel: SmsChannel
    enabled: bool = True
    access_key: str = ""
    secret_key: str = ""
    region: str = "cn-hangzhou"
    sign_name: str = ""
    template_code: str = ""
    daily_limit: int = 100    # 日限额（免费额度）
    monthly_limit: int = 100  # 月限额（免费额度）
    status: ChannelStatus = ChannelStatus.NORMAL


@dataclass
class EmailConfig:
    """邮箱配置"""
    enabled: bool = True
    smtp_server: str = "smtp.126.com"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    sender_email: str = ""
    default_subject: str = "【系统通知】"


@dataclass
class SmsResult:
    """短信发送结果"""
    success: bool
    message: str = ""
    channel: SmsChannel = None
    request_id: str = ""
    error_code: str = ""


@dataclass
class GatewayStats:
    """网关统计"""
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    channel_usage: Dict[str, int] = field(default_factory=dict)
    last_reset_time: float = 0


class SmsStrategy(ABC):
    """短信发送策略接口"""
    
    @abstractmethod
    def send(self, phone_number: str, template_param: Dict[str, str]) -> SmsResult:
        """发送短信"""
        pass
    
    @abstractmethod
    def get_channel(self) -> SmsChannel:
        """获取渠道类型"""
        pass


class AliyunSmsStrategy(SmsStrategy):
    """阿里云短信策略"""
    
    def __init__(self, config: ChannelConfig):
        self.config = config
        self.client = None
    
    def _get_client(self):
        """获取阿里云SDK客户端"""
        if self.client is None:
            try:
                from aliyunsdkcore.client import AcsClient
                from aliyunsdkcore.profile import region_profiles
                self.client = AcsClient(
                    self.config.access_key,
                    self.config.secret_key,
                    self.config.region
                )
            except ImportError:
                pass
        return self.client
    
    def send(self, phone_number: str, template_param: Dict[str, str]) -> SmsResult:
        """发送阿里云短信"""
        try:
            from aliyunsdkcore.request import CommonRequest
            
            client = self._get_client()
            if not client:
                return SmsResult(
                    success=False,
                    message="阿里云SDK未安装",
                    channel=SmsChannel.ALIYUN
                )
            
            request = CommonRequest()
            request.set_method("POST")
            request.set_domain("dysmsapi.aliyuncs.com")
            request.set_version("2017-05-25")
            request.set_action_name("SendSms")
            
            request.add_query_param("PhoneNumbers", phone_number)
            request.add_query_param("SignName", self.config.sign_name)
            request.add_query_param("TemplateCode", self.config.template_code)
            request.add_query_param("TemplateParam", json.dumps(template_param))
            
            response = client.do_action_with_exception(request)
            result = json.loads(response.decode("utf-8"))
            
            if result.get("Code") == "OK":
                return SmsResult(
                    success=True,
                    message="发送成功",
                    channel=SmsChannel.ALIYUN,
                    request_id=result.get("RequestId")
                )
            else:
                return SmsResult(
                    success=False,
                    message=result.get("Message", "发送失败"),
                    channel=SmsChannel.ALIYUN,
                    error_code=result.get("Code")
                )
        
        except Exception as e:
            return SmsResult(
                success=False,
                message=str(e),
                channel=SmsChannel.ALIYUN
            )
    
    def get_channel(self) -> SmsChannel:
        return SmsChannel.ALIYUN


class TencentSmsStrategy(SmsStrategy):
    """腾讯云短信策略"""
    
    def __init__(self, config: ChannelConfig):
        self.config = config
        self.client = None
    
    def _get_client(self):
        """获取腾讯云SDK客户端"""
        if self.client is None:
            try:
                from tencentcloud.common import credential
                from tencentcloud.sms.v20210111 import sms_client, models
                
                cred = credential.Credential(
                    self.config.access_key,
                    self.config.secret_key
                )
                self.client = sms_client.SmsClient(cred, self.config.region)
            except ImportError:
                pass
        return self.client
    
    def send(self, phone_number: str, template_param: Dict[str, str]) -> SmsResult:
        """发送腾讯云短信"""
        try:
            from tencentcloud.sms.v20210111 import models
            
            client = self._get_client()
            if not client:
                return SmsResult(
                    success=False,
                    message="腾讯云SDK未安装",
                    channel=SmsChannel.TENCENT
                )
            
            req = models.SendSmsRequest()
            req.PhoneNumberSet = [phone_number]
            req.SmsSdkAppId = self.config.access_key  # 腾讯云使用AppId作为key
            req.SignName = self.config.sign_name
            req.TemplateId = self.config.template_code
            
            # 转换参数格式
            template_param_list = [str(v) for v in template_param.values()]
            req.TemplateParamSet = template_param_list
            
            response = client.SendSms(req)
            result = response.SendStatusSet[0]
            
            if result.Code == "Ok":
                return SmsResult(
                    success=True,
                    message="发送成功",
                    channel=SmsChannel.TENCENT,
                    request_id=result.RequestId
                )
            else:
                return SmsResult(
                    success=False,
                    message=result.Message,
                    channel=SmsChannel.TENCENT,
                    error_code=result.Code
                )
        
        except Exception as e:
            return SmsResult(
                success=False,
                message=str(e),
                channel=SmsChannel.TENCENT
            )
    
    def get_channel(self) -> SmsChannel:
        return SmsChannel.TENCENT


class MockSmsStrategy(SmsStrategy):
    """模拟短信策略（用于测试）"""
    
    def __init__(self):
        self.count = 0
    
    def send(self, phone_number: str, template_param: Dict[str, str]) -> SmsResult:
        """模拟发送短信"""
        self.count += 1
        return SmsResult(
            success=True,
            message=f"模拟发送成功，第 {self.count} 条",
            channel=SmsChannel.ALIYUN,
            request_id=f"mock-{self.count}"
        )
    
    def get_channel(self) -> SmsChannel:
        return SmsChannel.ALIYUN


class QuotaManager:
    """额度管理器"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._use_mock = False
        
        if not self.redis_client:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", 6379)),
                    decode_responses=True
                )
                # 测试连接
                self.redis_client.ping()
            except Exception:
                # Redis不可用，使用内存模拟
                self._use_mock = True
                self._mock_store = {}
    
    def get_quota_key(self, channel: SmsChannel, period: str = "monthly") -> str:
        """生成额度Key"""
        now = time.localtime()
        if period == "daily":
            return f"quota:{channel.value}:{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d}"
        else:
            return f"quota:{channel.value}:{now.tm_year}-{now.tm_mon:02d}"
    
    def increment_quota(self, channel: SmsChannel, limit: int, period: str = "monthly") -> bool:
        """
        原子性增加配额计数
        
        Returns:
            True if within limit, False if exceeded
        """
        key = self.get_quota_key(channel, period)
        
        if self._use_mock:
            # 内存模拟
            current = self._mock_store.get(key, 0)
            if current >= limit:
                return False
            self._mock_store[key] = current + 1
            return True
        else:
            # Redis原子操作
            current = self.redis_client.incr(key)
            return current <= limit
    
    def get_quota_usage(self, channel: SmsChannel, period: str = "monthly") -> int:
        """获取当前配额使用量"""
        key = self.get_quota_key(channel, period)
        
        if self._use_mock:
            return self._mock_store.get(key, 0)
        else:
            value = self.redis_client.get(key)
            return int(value) if value else 0
    
    def reset_quota(self, channel: SmsChannel, period: str = "monthly"):
        """重置配额计数"""
        key = self.get_quota_key(channel, period)
        
        if self._use_mock:
            if key in self._mock_store:
                del self._mock_store[key]
        else:
            self.redis_client.delete(key)
    
    def reset_all_quotas(self):
        """重置所有配额"""
        if self._use_mock:
            self._mock_store.clear()
        else:
            # 删除所有quota开头的key
            keys = self.redis_client.keys("quota:*")
            if keys:
                self.redis_client.delete(*keys)


class SmsGateway:
    """
    智能短信网关
    
    核心能力：
    1. 统一入口：send_sms() 接口
    2. 智能路由：自动选择可用渠道
    3. 额度管理：原子计数，熔断控制
    4. 故障兜底：邮件/Webhook通知
    """
    
    def __init__(self):
        # 渠道配置
        self.channels: Dict[SmsChannel, ChannelConfig] = self._load_channel_configs()
        
        # 邮箱配置（兜底通知）
        self.email_config = self._load_email_config()
        
        # 策略映射
        self.strategies: Dict[SmsChannel, SmsStrategy] = {}
        
        # 额度管理器
        self.quota_manager = QuotaManager()
        
        # 统计信息
        self.stats = GatewayStats()
        self.stats.last_reset_time = time.time()
        
        # 告警回调
        self.alert_callbacks: List[Callable[[str, Dict], None]] = []
        
        # 初始化策略
        self._init_strategies()
    
    def _load_email_config(self) -> EmailConfig:
        """加载邮箱配置"""
        return EmailConfig(
            enabled=True,
            smtp_server=os.environ.get("SMTP_SERVER", "smtp.163.com"),
            smtp_port=int(os.environ.get("SMTP_PORT", 465)),
            smtp_username=os.environ.get("SMTP_USERNAME", "livingtreeai"),
            smtp_password=os.environ.get("SMTP_PASSWORD", "XYUJfjusnELCQZvc"),
            sender_email=os.environ.get("SENDER_EMAIL", "livingtreeai@163.com"),
            default_subject="【LivingTreeAI通知】"
        )
    
    def _load_channel_configs(self) -> Dict[SmsChannel, ChannelConfig]:
        """加载渠道配置"""
        return {
            SmsChannel.ALIYUN: ChannelConfig(
                channel=SmsChannel.ALIYUN,
                enabled=True,
                access_key=os.environ.get("ALIYUN_SMS_ACCESS_KEY", ""),
                secret_key=os.environ.get("ALIYUN_SMS_SECRET_KEY", ""),
                region=os.environ.get("ALIYUN_SMS_REGION", "cn-hangzhou"),
                sign_name=os.environ.get("ALIYUN_SMS_SIGN_NAME", ""),
                template_code=os.environ.get("ALIYUN_SMS_TEMPLATE_CODE", ""),
                daily_limit=100,
                monthly_limit=100
            ),
            SmsChannel.TENCENT: ChannelConfig(
                channel=SmsChannel.TENCENT,
                enabled=True,
                access_key=os.environ.get("TENCENT_SMS_APP_ID", ""),
                secret_key=os.environ.get("TENCENT_SMS_APP_KEY", ""),
                region=os.environ.get("TENCENT_SMS_REGION", "ap-beijing"),
                sign_name=os.environ.get("TENCENT_SMS_SIGN_NAME", ""),
                template_code=os.environ.get("TENCENT_SMS_TEMPLATE_ID", ""),
                daily_limit=1000,
                monthly_limit=1000
            )
        }
    
    def _init_strategies(self):
        """初始化策略对象"""
        for channel, config in self.channels.items():
            if config.enabled:
                if channel == SmsChannel.ALIYUN:
                    self.strategies[channel] = AliyunSmsStrategy(config)
                elif channel == SmsChannel.TENCENT:
                    self.strategies[channel] = TencentSmsStrategy(config)
        
        # 如果没有配置任何渠道，使用模拟策略
        if not self.strategies:
            self.strategies[SmsChannel.ALIYUN] = MockSmsStrategy()
            self.channels[SmsChannel.ALIYUN] = ChannelConfig(
                channel=SmsChannel.ALIYUN,
                enabled=True,
                daily_limit=99999,
                monthly_limit=99999
            )
    
    def _select_channel(self) -> Optional[SmsChannel]:
        """
        智能选择短信渠道
        
        选择策略：
        1. 优先选择未熔断、未耗尽额度的渠道
        2. 优先选择免费额度更高的渠道
        3. 按配置顺序轮询
        """
        candidates = []
        
        for channel, config in self.channels.items():
            # 跳过禁用的渠道
            if not config.enabled:
                continue
            
            # 检查额度是否充足
            monthly_used = self.quota_manager.get_quota_usage(channel, "monthly")
            daily_used = self.quota_manager.get_quota_usage(channel, "daily")
            
            monthly_ok = monthly_used < config.monthly_limit
            daily_ok = daily_used < config.daily_limit
            
            if monthly_ok and daily_ok:
                # 计算优先级：剩余额度越多优先级越高
                monthly_ratio = (config.monthly_limit - monthly_used) / config.monthly_limit
                daily_ratio = (config.daily_limit - daily_used) / config.daily_limit
                priority = (monthly_ratio + daily_ratio) / 2
                
                candidates.append((channel, priority))
        
        if not candidates:
            return None
        
        # 选择优先级最高的渠道
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _try_send(self, phone_number: str, template_param: Dict[str, str], 
                 channel: SmsChannel) -> SmsResult:
        """尝试通过指定渠道发送短信"""
        config = self.channels[channel]
        
        # 检查并增加配额计数
        if not self.quota_manager.increment_quota(channel, config.monthly_limit, "monthly"):
            config.status = ChannelStatus.EXHAUSTED
            self._trigger_alert(f"渠道 {channel.value} 月额度已耗尽", {
                "channel": channel.value,
                "limit": config.monthly_limit,
                "type": "monthly"
            })
            return SmsResult(
                success=False,
                message=f"{channel.value} 月额度已耗尽",
                channel=channel
            )
        
        if not self.quota_manager.increment_quota(channel, config.daily_limit, "daily"):
            config.status = ChannelStatus.EXHAUSTED
            self._trigger_alert(f"渠道 {channel.value} 日额度已耗尽", {
                "channel": channel.value,
                "limit": config.daily_limit,
                "type": "daily"
            })
            return SmsResult(
                success=False,
                message=f"{channel.value} 日额度已耗尽",
                channel=channel
            )
        
        # 调用策略发送
        strategy = self.strategies.get(channel)
        if not strategy:
            return SmsResult(
                success=False,
                message=f"渠道 {channel.value} 策略未初始化",
                channel=channel
            )
        
        return strategy.send(phone_number, template_param)
    
    def _trigger_alert(self, message: str, details: Dict = None):
        """触发告警"""
        alert_info = {
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "details": details or {}
        }
        
        # 记录日志
        self._log_alert(alert_info)
        
        # 调用告警回调
        for callback in self.alert_callbacks:
            try:
                callback(message, alert_info)
            except Exception as e:
                print(f"告警回调执行失败: {e}")
    
    def _log_alert(self, alert_info: Dict):
        """记录告警日志"""
        log_dir = Path("logs/sms_gateway")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"alert_{time.strftime('%Y-%m-%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{alert_info['timestamp']} - {alert_info['message']}\n")
            if alert_info.get('details'):
                f.write(f"  Details: {json.dumps(alert_info['details'], ensure_ascii=False)}\n")
    
    def _fallback_notify(self, phone_number: str, template_param: Dict[str, str]):
        """兜底通知（所有渠道都不可用时）"""
        alert_message = f"所有短信渠道均不可用，无法发送短信至 {phone_number}"
        self._trigger_alert(alert_message, {
            "phone_number": phone_number,
            "template_param": template_param,
            "channels": {k.value: v.status.value for k, v in self.channels.items()}
        })
        
        # 尝试发送邮件兜底通知
        self._send_email_notification(phone_number, template_param)
    
    def _send_email_notification(self, phone_number: str, template_param: Dict[str, str]):
        """发送邮件兜底通知"""
        if not self.email_config.enabled:
            return
        
        try:
            # 将手机号转换为邮箱（假设用户手机号注册了邮箱）
            # 尝试常见的邮箱格式
            possible_emails = [
                f"{phone_number}@qq.com",
                f"{phone_number}@163.com",
                f"{phone_number}@126.com",
                f"{phone_number}@gmail.com"
            ]
            
            # 构建邮件内容
            param_str = "\n".join([f"{k}: {v}" for k, v in template_param.items()])
            content = f"""尊敬的用户：

由于短信渠道暂时不可用，我们通过邮件向您发送此通知。

通知内容：
{param_str}

如有疑问，请联系客服。

此致
系统通知
"""
            
            # 发送邮件到所有可能的邮箱
            for to_email in possible_emails:
                result = self._send_email(to_email, self.email_config.default_subject, content)
                if result:
                    print(f"✅ 邮件已发送至 {to_email}")
                    break
            
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
    
    def _send_email(self, to_email: str, subject: str, content: str) -> bool:
        """发送邮件"""
        try:
            config = self.email_config
            
            msg = MIMEText(content, 'plain', 'utf-8')
            msg['From'] = Header(config.sender_email, 'utf-8')
            msg['To'] = Header(to_email, 'utf-8')
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 连接SMTP服务器
            if config.smtp_port == 465:
                server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
            else:
                server = smtplib.SMTP(config.smtp_server, config.smtp_port)
            
            # 登录并发送
            server.login(config.smtp_username, config.smtp_password)
            server.sendmail(config.sender_email, to_email, msg.as_string())
            server.quit()
            
            return True
        
        except Exception as e:
            print(f"邮件发送失败 ({to_email}): {e}")
            return False
    
    def send_email(self, to_email: str, subject: str, content: str) -> bool:
        """
        直接发送邮件（公开接口）
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容
        
        Returns:
            True if success
        """
        return self._send_email(to_email, subject, content)
    
    def send_sms(self, phone_number: str, **kwargs) -> SmsResult:
        """
        发送短信（统一入口）
        
        Args:
            phone_number: 手机号码
            **kwargs: 模板参数
        
        Returns:
            SmsResult
        """
        self.stats.total_requests += 1
        
        # 验证手机号码格式
        if not self._validate_phone(phone_number):
            return SmsResult(
                success=False,
                message="手机号码格式无效"
            )
        
        # 智能选择渠道
        channel = self._select_channel()
        if not channel:
            self.stats.fail_count += 1
            self._fallback_notify(phone_number, kwargs)
            return SmsResult(
                success=False,
                message="所有渠道额度均已耗尽"
            )
        
        # 尝试发送
        result = self._try_send(phone_number, kwargs, channel)
        
        if result.success:
            self.stats.success_count += 1
            self.stats.channel_usage[channel.value] = self.stats.channel_usage.get(channel.value, 0) + 1
        else:
            self.stats.fail_count += 1
            # 尝试下一个渠道
            result = self._try_next_channel(phone_number, kwargs, [channel])
        
        return result
    
    def _try_next_channel(self, phone_number: str, template_param: Dict[str, str], 
                         tried_channels: List[SmsChannel]) -> SmsResult:
        """尝试下一个可用渠道"""
        available_channels = []
        
        for channel, config in self.channels.items():
            if channel in tried_channels:
                continue
            if not config.enabled:
                continue
            
            monthly_used = self.quota_manager.get_quota_usage(channel, "monthly")
            daily_used = self.quota_manager.get_quota_usage(channel, "daily")
            
            if monthly_used < config.monthly_limit and daily_used < config.daily_limit:
                available_channels.append(channel)
        
        if not available_channels:
            self._fallback_notify(phone_number, template_param)
            return SmsResult(
                success=False,
                message="所有渠道均不可用"
            )
        
        # 选择第一个可用渠道
        next_channel = available_channels[0]
        result = self._try_send(phone_number, template_param, next_channel)
        
        if result.success:
            self.stats.success_count += 1
            self.stats.channel_usage[next_channel.value] = self.stats.channel_usage.get(next_channel.value, 0) + 1
        
        return result
    
    def _validate_phone(self, phone_number: str) -> bool:
        """验证手机号码格式"""
        import re
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone_number))
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def get_stats(self) -> GatewayStats:
        """获取统计信息"""
        return self.stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = GatewayStats()
        self.stats.last_reset_time = time.time()
    
    def get_channel_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有渠道状态"""
        status = {}
        for channel, config in self.channels.items():
            status[channel.value] = {
                "enabled": config.enabled,
                "status": config.status.value,
                "daily_used": self.quota_manager.get_quota_usage(channel, "daily"),
                "daily_limit": config.daily_limit,
                "monthly_used": self.quota_manager.get_quota_usage(channel, "monthly"),
                "monthly_limit": config.monthly_limit
            }
        return status
    
    def print_status(self):
        """打印网关状态"""
        print("=" * 60)
        print("Smart SMS Gateway Status")
        print("=" * 60)
        print(f"Total Requests: {self.stats.total_requests}")
        print(f"Success: {self.stats.success_count}")
        print(f"Failed: {self.stats.fail_count}")
        print(f"Success Rate: {self.stats.success_count / max(self.stats.total_requests, 1) * 100:.1f}%")
        print()
        print("Channel Status:")
        for channel, status in self.get_channel_status().items():
            daily_ratio = status['daily_used'] / status['daily_limit'] * 100
            monthly_ratio = status['monthly_used'] / status['monthly_limit'] * 100
            status_icon = "🟢" if status['status'] == 'normal' else "🔴"
            print(f"  {status_icon} {channel}:")
            print(f"    Daily: {status['daily_used']}/{status['daily_limit']} ({daily_ratio:.1f}%)")
            print(f"    Monthly: {status['monthly_used']}/{status['monthly_limit']} ({monthly_ratio:.1f}%)")
            print(f"    Status: {status['status']}")
        print("=" * 60)


# 单例模式
_sms_gateway = None


def get_sms_gateway() -> SmsGateway:
    """获取SMS网关单例"""
    global _sms_gateway
    if _sms_gateway is None:
        _sms_gateway = SmsGateway()
    return _sms_gateway


# 定时任务：每月1号重置配额
def setup_monthly_reset():
    """设置每月重置配额的定时任务"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        
        scheduler = BackgroundScheduler()
        
        def reset_job():
            gateway = get_sms_gateway()
            gateway.quota_manager.reset_all_quotas()
            print("✅ 配额已重置")
        
        # 每月1号 00:00 执行
        scheduler.add_job(reset_job, 'cron', day=1, hour=0, minute=0)
        
        scheduler.start()
        print("✅ 配额重置定时任务已启动")
        
    except ImportError:
        print("⚠️ 未安装 apscheduler，配额重置需手动执行")


# 启动时设置定时任务
setup_monthly_reset()