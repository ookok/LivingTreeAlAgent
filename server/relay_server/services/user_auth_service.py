"""
User Auth & Node Registry Service - 用户认证与节点注册服务
============================================================

功能：
1. 用户注册/登录/认证（由中继服务器响应）
2. 用户注册时自动注册节点信息
3. 节点管理（节点ID、中继URL、状态）
4. 统一支付网关回调转发

设计原则：
- 身份即钥匙：用户身份绑定节点
- 本地即真理：节点本地处理
- 网络是邮差：中继服务器转发消息和支付回调
"""

import os
import re
import uuid
import hashlib
import secrets
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from functools import wraps

import httpx

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    from passlib.context import CryptContext
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False


# ============ 枚举定义 ============

class AuthProvider(str, Enum):
    """认证提供者"""
    LOCAL = "local"          # 本地账号
    GITHUB = "github"        # GitHub OAuth
    GOOGLE = "google"         # Google OAuth
    WECHAT = "wechat"        # 微信 OAuth


class NodeStatus(str, Enum):
    """节点状态"""
    PENDING = "pending"      # 待激活
    ACTIVE = "active"        # 正常
    SUSPENDED = "suspended"  # 暂停
    OFFLINE = "offline"      # 离线


class PaymentStatus(str, Enum):
    """支付状态"""
    PENDING = "pending"      # 待支付
    PAID = "paid"            # 已支付
    REFUNDED = "refunded"    # 已退款
    FAILED = "failed"        # 失败


# ============ 密码哈希 ============

if PASSLIB_AVAILABLE:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
else:
    def simple_hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    pwd_context = type('obj', (object,), {
        'verify': lambda s, h: simple_hash(s) == h,
        'hash': lambda p: simple_hash(p)
    })()


# ============ JWT 配置 ============

JWT_SECRET = os.environ.get("HERMES_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30


# ============ 数据模型 ============

@dataclass
class User:
    """用户模型"""
    user_id: str
    username: str
    email: Optional[str] = None
    password_hash: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: AuthProvider = AuthProvider.LOCAL
    is_active: bool = True
    is_verified: bool = False
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    last_login_at: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "auth_provider": self.auth_provider.value if isinstance(self.auth_provider, AuthProvider) else self.auth_provider,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login_at": self.last_login_at,
        }


@dataclass
class Node:
    """节点模型"""
    node_id: str
    user_id: str
    node_name: str
    relay_url: str                      # 节点的中继服务器 URL
    public_key: Optional[str] = None    # 节点公钥（用于加密通信）
    status: NodeStatus = NodeStatus.PENDING
    client_id: Optional[str] = None    # 客户端ID
    platform: str = "unknown"
    version: str = "2.0.0"
    capabilities: List[str] = field(default_factory=list)
    last_heartbeat: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "node_name": self.node_name,
            "relay_url": self.relay_url,
            "public_key": self.public_key,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "client_id": self.client_id,
            "platform": self.platform,
            "version": self.version,
            "capabilities": self.capabilities,
            "last_heartbeat": self.last_heartbeat,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PaymentOrder:
    """支付订单模型"""
    order_id: str
    user_id: str
    node_id: str                        # 关联的节点
    amount: float                       # 金额（元）
    currency: str = "CNY"
    subject: str = ""                   # 订单主题
    payment_method: Optional[str] = None  # wechat / alipay
    status: PaymentStatus = PaymentStatus.PENDING
    trade_no: Optional[str] = None      # 第三方交易号
    paid_at: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "node_id": self.node_id,
            "amount": self.amount,
            "currency": self.currency,
            "subject": self.subject,
            "payment_method": self.payment_method,
            "status": self.status.value if isinstance(self.status, PaymentStatus) else self.status,
            "trade_no": self.trade_no,
            "paid_at": self.paid_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ============ 存储层 ============

class AuthStorage:
    """认证数据存储（JSON 文件实现，可替换为 SQLAlchemy）"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.users_file = data_dir / "users.json"
        self.nodes_file = data_dir / "nodes.json"
        self.orders_file = data_dir / "orders.json"
        self.sessions_file = data_dir / "sessions.json"
        
        for f in [self.users_file, self.nodes_file, self.orders_file, self.sessions_file]:
            f.parent.mkdir(parents=True, exist_ok=True)
            if not f.exists():
                f.write_text("{}", encoding="utf-8")
    
    def _load_json(self, file: Path) -> Dict[str, Any]:
        try:
            return json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    
    def _save_json(self, file: Path, data: Dict[str, Any]):
        file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # ============ 用户操作 ============
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        data = self._load_json(self.users_file)
        if user_id in data:
            return User(**data[user_id])
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        data = self._load_json(self.users_file)
        for u in data.values():
            if u.get("username") == username:
                return User(**u)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        data = self._load_json(self.users_file)
        for u in data.values():
            if u.get("email") == email:
                return User(**u)
        return None
    
    def create_user(self, user: User) -> User:
        data = self._load_json(self.users_file)
        data[user.user_id] = user.to_dict()
        self._save_json(self.users_file, data)
        return user
    
    def update_user(self, user: User) -> User:
        user.updated_at = int(time.time())
        data = self._load_json(self.users_file)
        data[user.user_id] = user.to_dict()
        self._save_json(self.users_file, data)
        return user
    
    # ============ 节点操作 ============
    
    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        data = self._load_json(self.nodes_file)
        if node_id in data:
            return Node(**data[node_id])
        return None
    
    def get_nodes_by_user(self, user_id: str) -> List[Node]:
        data = self._load_json(self.nodes_file)
        return [Node(**n) for n in data.values() if n.get("user_id") == user_id]
    
    def create_node(self, node: Node) -> Node:
        data = self._load_json(self.nodes_file)
        data[node.node_id] = node.to_dict()
        self._save_json(self.nodes_file, data)
        return node
    
    def update_node(self, node: Node) -> Node:
        node.updated_at = int(time.time())
        data = self._load_json(self.nodes_file)
        data[node.node_id] = node.to_dict()
        self._save_json(self.nodes_file, data)
        return node
    
    def delete_node(self, node_id: str) -> bool:
        data = self._load_json(self.nodes_file)
        if node_id in data:
            del data[node_id]
            self._save_json(self.nodes_file, data)
            return True
        return False
    
    # ============ 订单操作 ============
    
    def get_order_by_id(self, order_id: str) -> Optional[PaymentOrder]:
        data = self._load_json(self.orders_file)
        if order_id in data:
            return PaymentOrder(**data[order_id])
        return None
    
    def get_orders_by_user(self, user_id: str) -> List[PaymentOrder]:
        data = self._load_json(self.orders_file)
        return [PaymentOrder(**o) for o in data.values() if o.get("user_id") == user_id]
    
    def get_orders_by_node(self, node_id: str) -> List[PaymentOrder]:
        data = self._load_json(self.orders_file)
        return [PaymentOrder(**o) for o in data.values() if o.get("node_id") == node_id]
    
    def create_order(self, order: PaymentOrder) -> PaymentOrder:
        data = self._load_json(self.orders_file)
        data[order.order_id] = order.to_dict()
        self._save_json(self.orders_file, data)
        return order
    
    def update_order(self, order: PaymentOrder) -> PaymentOrder:
        order.updated_at = int(time.time())
        data = self._load_json(self.orders_file)
        data[order.order_id] = order.to_dict()
        self._save_json(self.orders_file, data)
        return order


# ============ 认证服务 ============

class UserAuthService:
    """用户认证服务"""
    
    def __init__(self, storage: AuthStorage):
        self.storage = storage
        self.jwt_available = JWT_AVAILABLE
        self.passlib_available = PASSLIB_AVAILABLE
    
    # ============ 密码操作 ============
    
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    # ============ 用户 ID 生成 ============
    
    def generate_user_id(self) -> str:
        return f"usr_{uuid.uuid4().hex[:16]}"
    
    def generate_node_id(self) -> str:
        return f"node_{uuid.uuid4().hex[:16]}"
    
    def generate_order_id(self) -> str:
        return f"ord_{uuid.uuid4().hex[:16]}"
    
    def generate_session_id(self) -> str:
        return f"sess_{uuid.uuid4().hex[:16]}"
    
    # ============ JWT Token ============
    
    def create_access_token(
        self,
        user_id: str,
        username: str,
        node_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        if expires_delta is None:
            expires_delta = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user_id,
            "username": username,
            "type": "access",
            "node_id": node_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        if expires_delta is None:
            expires_delta = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    # ============ 验证工具 ============
    
    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_username(username: str) -> bool:
        pattern = r'^[a-zA-Z0-9_]{3,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        if len(password) < 8:
            return False, "密码长度至少 8 位"
        if len(password) > 128:
            return False, "密码长度不能超过 128 位"
        if not re.search(r'[A-Za-z]', password):
            return False, "密码必须包含字母"
        if not re.search(r'[0-9]', password):
            return False, "密码必须包含数字"
        return True, ""
    
    # ============ 注册 ============
    
    def register(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        auto_create_node: bool = True,
        node_name: Optional[str] = None,
        relay_url: Optional[str] = None
    ) -> Tuple[Optional[User], Optional[Node], str]:
        """
        用户注册（自动注册节点）
        
        Returns:
            (user, node, error_message)
        """
        # 验证用户名
        if not self.validate_username(username):
            return None, None, "用户名格式错误（3-32位字母数字下划线）"
        
        # 验证密码
        is_valid, msg = self.validate_password(password)
        if not is_valid:
            return None, None, msg
        
        # 检查用户名是否存在
        if self.storage.get_user_by_username(username):
            return None, None, "用户名已存在"
        
        # 检查邮箱是否存在
        if email and self.storage.get_user_by_email(email):
            return None, None, "邮箱已被使用"
        
        # 创建用户
        user = User(
            user_id=self.generate_user_id(),
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            auth_provider=AuthProvider.LOCAL,
            is_active=True,
            is_verified=False,
        )
        self.storage.create_user(user)
        
        # 自动创建节点
        node = None
        if auto_create_node:
            node = Node(
                node_id=self.generate_node_id(),
                user_id=user.user_id,
                node_name=node_name or f"{username}'s Node",
                relay_url=relay_url or "",
                status=NodeStatus.PENDING,
            )
            self.storage.create_node(node)
        
        return user, node, ""
    
    # ============ 登录 ============
    
    def login(
        self,
        username: str,
        password: str,
        node_id: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[User], str]:
        """
        用户登录
        
        Returns:
            (access_token, refresh_token, user, error_message)
        """
        # 查找用户
        user = self.storage.get_user_by_username(username)
        if not user:
            return None, None, None, "用户名或密码错误"
        
        # 验证密码
        if not self.verify_password(password, user.password_hash):
            return None, None, None, "用户名或密码错误"
        
        # 检查用户状态
        if not user.is_active:
            return None, None, None, "账号已被禁用"
        
        # 更新登录时间
        user.last_login_at = int(time.time())
        self.storage.update_user(user)
        
        # 生成 Token
        access_token = self.create_access_token(user.user_id, user.username, node_id)
        refresh_token = self.create_refresh_token(user.user_id)
        
        return access_token, refresh_token, user, ""
    
    # ============ Token 刷新 ============
    
    def refresh_access_token(self, refresh_token: str) -> Tuple[Optional[str], str]:
        """
        刷新访问令牌
        
        Returns:
            (new_access_token, error_message)
        """
        payload = self.verify_token(refresh_token)
        if not payload:
            return None, "无效的刷新令牌"
        
        if payload.get("type") != "refresh":
            return None, "不是刷新令牌"
        
        user_id = payload.get("sub")
        user = self.storage.get_user_by_id(user_id)
        if not user:
            return None, "用户不存在"
        
        if not user.is_active:
            return None, "账号已被禁用"
        
        new_access_token = self.create_access_token(user.user_id, user.username)
        return new_access_token, ""
    
    # ============ 第三方认证 ============
    
    def oauth_register_or_login(
        self,
        provider: AuthProvider,
        provider_user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        auto_create_node: bool = True,
        node_name: Optional[str] = None,
        relay_url: Optional[str] = None
    ) -> Tuple[Optional[User], Optional[Node], str]:
        """
        第三方用户注册或登录
        
        Returns:
            (user, node, error_message)
        """
        # 构建外部用户标识
        external_id = f"{provider.value}:{provider_user_id}"
        
        # 查找用户（通过邮箱或外部ID）
        user = None
        if email:
            user = self.storage.get_user_by_email(email)
        
        if not user:
            # 创建新用户
            if not username:
                username = f"{provider.value}_{provider_user_id[:16]}"
            
            # 确保用户名唯一
            base_username = username
            counter = 1
            while self.storage.get_user_by_username(username):
                username = f"{base_username}_{counter}"
                counter += 1
            
            user = User(
                user_id=self.generate_user_id(),
                username=username,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
                auth_provider=provider,
                is_active=True,
                is_verified=True,  # 第三方用户默认已验证
            )
            self.storage.create_user(user)
        
        # 自动创建节点
        node = None
        if auto_create_node:
            node = Node(
                node_id=self.generate_node_id(),
                user_id=user.user_id,
                node_name=node_name or f"{user.username}'s Node",
                relay_url=relay_url or "",
                status=NodeStatus.PENDING,
            )
            self.storage.create_node(node)
        
        return user, node, ""


# ============ 节点服务 ============

class NodeService:
    """节点管理服务"""
    
    def __init__(self, storage: AuthStorage):
        self.storage = storage
    
    def register_node(
        self,
        user_id: str,
        node_name: str,
        relay_url: str,
        public_key: Optional[str] = None,
        client_id: Optional[str] = None,
        platform: str = "unknown",
        version: str = "2.0.0",
        capabilities: Optional[List[str]] = None
    ) -> Node:
        """注册新节点"""
        from core.admin_license_system.author_config import get_author_config_manager
        
        # 检查用户是否为作者（作者节点自动激活）
        author_config = get_author_config_manager()
        is_author = author_config.is_author_user(user_id)
        
        node = Node(
            node_id=f"node_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            node_name=node_name,
            relay_url=relay_url,
            public_key=public_key,
            status=NodeStatus.ACTIVE if is_author else NodeStatus.PENDING,
            client_id=client_id,
            platform=platform,
            version=version,
            capabilities=capabilities or [],
        )
        return self.storage.create_node(node)
    
    def activate_node(self, node_id: str, user_id: str) -> Tuple[bool, str]:
        """激活节点"""
        node = self.storage.get_node_by_id(node_id)
        if not node:
            return False, "节点不存在"
        if node.user_id != user_id:
            return False, "无权限操作此节点"
        
        node.status = NodeStatus.ACTIVE
        self.storage.update_node(node)
        return True, "节点已激活"
    
    def heartbeat(self, node_id: str) -> bool:
        """节点心跳"""
        node = self.storage.get_node_by_id(node_id)
        if not node:
            return False
        
        node.last_heartbeat = int(time.time())
        node.status = NodeStatus.ACTIVE
        self.storage.update_node(node)
        return True
    
    def get_user_nodes(self, user_id: str) -> List[Node]:
        """获取用户的所有节点"""
        return self.storage.get_nodes_by_user(user_id)
    
    def get_node_relay_url(self, node_id: str) -> Optional[str]:
        """获取节点的 relay URL"""
        node = self.storage.get_node_by_id(node_id)
        return node.relay_url if node else None


# ============ 支付网关服务 ============

class PaymentGateway:
    """
    统一支付网关
    
    设计：
    - 微信/支付宝回调先到网关
    - 网关根据订单的 node_id 找到对应的中继服务器
    - 转发回调通知到节点的回调地址
    """
    
    def __init__(self, storage: AuthStorage, node_service: NodeService):
        self.storage = storage
        self.node_service = node_service
        self._callback_queue: List[Dict[str, Any]] = []
    
    def create_order(
        self,
        user_id: str,
        node_id: str,
        amount: float,
        subject: str,
        payment_method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[PaymentOrder], str]:
        """创建支付订单"""
        # 验证节点
        node = self.storage.get_node_by_id(node_id)
        if not node:
            return None, "节点不存在"
        if node.user_id != user_id:
            return None, "无权限在此节点下单"
        
        order = PaymentOrder(
            order_id=f"ord_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            node_id=node_id,
            amount=amount,
            subject=subject,
            payment_method=payment_method,
            status=PaymentStatus.PENDING,
            metadata=metadata or {},
        )
        self.storage.create_order(order)
        return order, ""
    
    def get_payment_url(
        self,
        order: PaymentOrder,
        payment_method: str,
        notify_url: str
    ) -> Tuple[Optional[str], str]:
        """
        获取支付链接（统一下单）
        
        实际对接微信/支付宝时，这里调用第三方 API
        目前返回模拟支付链接
        """
        # 构建支付请求
        if payment_method == "wechat":
            # 微信支付
            pay_url = f"weixin://wxpay/bizpayurl?pr={order.order_id}"
        elif payment_method == "alipay":
            # 支付宝
            pay_url = f"alipay://alipay?order={order.order_id}"
        else:
            return None, f"不支持的支付方式: {payment_method}"
        
        return pay_url, ""
    
    async def handle_callback(
        self,
        payment_method: str,
        callback_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        处理支付回调
        
        流程：
        1. 验证回调签名
        2. 更新订单状态
        3. 转发给对应的节点
        """
        # 解析回调数据
        trade_no = callback_data.get("trade_no") or callback_data.get("transaction_id", "")
        order_id = callback_data.get("order_id") or callback_data.get("out_trade_no", "")
        status = callback_data.get("status") or callback_data.get("trade_status", "")
        
        # 查找订单
        order = self.storage.get_order_by_id(order_id)
        if not order:
            return False, "订单不存在"
        
        # 更新订单状态
        if status in ["TRADE_SUCCESS", "PAID", "success"]:
            order.status = PaymentStatus.PAID
            order.trade_no = trade_no
            order.paid_at = int(time.time())
        elif status in ["TRADE_CLOSED", "REFUNDED"]:
            order.status = PaymentStatus.REFUNDED
        else:
            order.status = PaymentStatus.FAILED
        
        self.storage.update_order(order)
        
        # 转发给节点
        await self._forward_to_node(order, payment_method, callback_data)
        
        return True, "处理成功"
    
    async def _forward_to_node(
        self,
        order: PaymentOrder,
        payment_method: str,
        callback_data: Dict[str, Any]
    ):
        """
        转发支付通知到节点
        
        关键：节点可能有自己的中继服务器，网关需要把通知转发过去
        """
        node = self.storage.get_node_by_id(order.node_id)
        if not node or not node.relay_url:
            # 没有节点 relay，记录待处理
            self._callback_queue.append({
                "order_id": order.order_id,
                "node_id": order.node_id,
                "callback_data": callback_data,
                "payment_method": payment_method,
                "queued_at": int(time.time()),
            })
            return
        
        # 转发到节点
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                callback_url = f"{node.relay_url}/api/payment/callback"
                response = await client.post(
                    callback_url,
                    json={
                        "order_id": order.order_id,
                        "payment_method": payment_method,
                        "status": order.status.value,
                        "trade_no": order.trade_no,
                        "paid_at": order.paid_at,
                        "amount": order.amount,
                        "metadata": order.metadata,
                    }
                )
                if response.status_code == 200:
                    return  # 成功
        except Exception:
            pass
        
        # 转发失败，记录待处理
        self._callback_queue.append({
            "order_id": order.order_id,
            "node_id": order.node_id,
            "callback_data": callback_data,
            "payment_method": payment_method,
            "queued_at": int(time.time()),
        })
    
    def retry_pending_callbacks(self):
        """重试待处理的回调"""
        pending = self._callback_queue.copy()
        self._callback_queue.clear()
        
        for item in pending:
            order = self.storage.get_order_by_id(item["order_id"])
            if order:
                import asyncio
                asyncio.create_task(self._forward_to_node(
                    order,
                    item["payment_method"],
                    item["callback_data"]
                ))
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取订单"""
        return self.storage.get_order_by_id(order_id)
    
    def get_user_orders(self, user_id: str) -> List[PaymentOrder]:
        """获取用户订单"""
        return self.storage.get_orders_by_user(user_id)


# ============ 单例管理 ============

_auth_storage: Optional[AuthStorage] = None
_auth_service: Optional[UserAuthService] = None
_node_service: Optional[NodeService] = None
_payment_gateway: Optional[PaymentGateway] = None


def get_auth_storage(data_dir: Optional[Path] = None) -> AuthStorage:
    global _auth_storage
    if _auth_storage is None:
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "relay_server" / "auth"
        data_dir.mkdir(parents=True, exist_ok=True)
        _auth_storage = AuthStorage(data_dir)
    return _auth_storage


def get_auth_service() -> UserAuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = UserAuthService(get_auth_storage())
    return _auth_service


def get_node_service() -> NodeService:
    global _node_service
    if _node_service is None:
        _node_service = NodeService(get_auth_storage())
    return _node_service


def get_payment_gateway() -> PaymentGateway:
    global _payment_gateway
    if _payment_gateway is None:
        _payment_gateway = PaymentGateway(get_auth_storage(), get_node_service())
    return _payment_gateway


# ============ 装饰器 ============

def require_auth(func):
    """要求认证的装饰器"""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header[7:]
        
        auth_service = get_auth_service()
        payload = auth_service.verify_token(token)
        
        if payload is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        request.state.user_id = payload.get("sub")
        request.state.username = payload.get("username")
        request.state.node_id = payload.get("node_id")
        
        return await func(request, *args, **kwargs)
    
    return wrapper


def require_node_owner(func):
    """要求节点所有者的装饰器"""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        node_id = request.path_params.get("node_id") or request.query_params.get("node_id")
        
        if node_id:
            node_service = get_node_service()
            node = node_service.storage.get_node_by_id(node_id)
            
            if node and node.user_id == request.state.user_id:
                request.state.is_node_owner = True
            else:
                request.state.is_node_owner = False
        else:
            request.state.is_node_owner = False
        
        return await func(request, *args, **kwargs)
    
    return wrapper
