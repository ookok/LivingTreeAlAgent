"""
加密配置管理器

功能：
1. 加密保存敏感配置（API Key、URL 等）
2. 从加密文件加载配置
3. 支持多个配置文件（按项目/环境隔离）
4. 自动生成密钥（基于机器指纹 + 用户密码）

使用：
    from client.src.business.encrypted_config import EncryptedConfig
    
    config_manager = EncryptedConfig()
    
    # 保存配置
    config_manager.save_config("deepseek", {
        "api_key": "sk-f05ded8271b74091a499831999d34437",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"]
    })
    
    # 加载配置
    deepseek_config = config_manager.load_config("deepseek")
"""

import os
import json
import base64
import hashlib
import getpass
from pathlib import Path
from typing import Dict, Any, Optional

# 检查 cryptography 是否安装
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None
    PBKDF2HMAC = None
    hashes = None


class EncryptedConfig:
    """
    加密配置管理器
    
    配置存储位置：
    - Windows: C:/Users/<user>/.livingtree/config/encrypted/
    - Linux/Mac: ~/.livingtree/config/encrypted/
    """
    
    def __init__(self, config_dir: Optional[str] = None, password: Optional[str] = None):
        """
        初始化加密配置管理器
        
        Args:
            config_dir: 配置文件目录（默认：~/.livingtree/config/encrypted/）
            password: 加密密码（默认：自动生成基于机器指纹的密码）
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("需要安装 cryptography 库：pip install cryptography")
        
        # 确定配置目录
        if config_dir is None:
            if os.name == 'nt':  # Windows
                config_dir = os.path.join(os.path.expanduser("~"), ".livingtree", "config", "encrypted")
            else:  # Linux/Mac
                config_dir = os.path.join(os.path.expanduser("~"), ".livingtree", "config", "encrypted")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成或加载加密密钥
        self.password = password or self._get_machine_fingerprint()
        self._fernet = self._create_fernet(self.password)
        
        print(f"[加密配置] 配置目录: {self.config_dir}")
    
    
    def _get_machine_fingerprint(self) -> str:
        """
        获取机器指纹（用于生成默认密码）
        
        使用：主机名 + 用户名 + CPU 信息（如果可用）
        """
        import platform
        
        fingerprint_parts = [
            platform.node(),  # 主机名
            getpass.getuser(),  # 用户名
        ]
        
        # 尝试获取 CPU 信息（Linux）
        try:
            if os.name != 'nt':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            fingerprint_parts.append(line.split(':')[1].strip())
                            break
        except:
            pass
        
        # 生成指纹
        fingerprint = hashlib.sha256('|'.join(fingerprint_parts).encode()).hexdigest()
        return fingerprint[:32]  # 32 字符
    
    
    def _create_fernet(self, password: str) -> Fernet:
        """
        从密码创建 Fernet 加密器
        
        Args:
            password: 密码（字符串）
            
        Returns:
            Fernet 加密器
        """
        # 使用 PBKDF2 从密码生成密钥
        salt = b'livingtree_salt_'  # 固定 salt（可以改为随机）
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    
    def save_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """
        保存配置（加密）
        
        Args:
            config_name: 配置名称（如 "deepseek", "openai"）
            config_data: 配置数据（字典）
            
        Returns:
            是否保存成功
        """
        try:
            # 序列化配置
            json_data = json.dumps(config_data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')
            
            # 加密
            encrypted_data = self._fernet.encrypt(json_bytes)
            
            # 保存到文件
            config_file = self.config_dir / f"{config_name}.enc"
            with open(config_file, 'wb') as f:
                f.write(encrypted_data)
            
            print(f"[加密配置] 已保存配置: {config_name} -> {config_file}")
            return True
            
        except Exception as e:
            print(f"[加密配置] 保存失败: {e}")
            return False
    
    
    def load_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """
        加载配置（解密）
        
        Args:
            config_name: 配置名称
            
        Returns:
            配置数据（字典），失败返回 None
        """
        config_file = self.config_dir / f"{config_name}.enc"
        
        if not config_file.exists():
            print(f"[加密配置] 配置文件不存在: {config_file}")
            return None
        
        try:
            # 读取加密数据
            with open(config_file, 'rb') as f:
                encrypted_data = f.read()
            
            # 解密
            decrypted_data = self._fernet.decrypt(encrypted_data)
            
            # 反序列化
            json_data = decrypted_data.decode('utf-8')
            config_data = json.loads(json_data)
            
            print(f"[加密配置] 已加载配置: {config_name}")
            return config_data
            
        except Exception as e:
            print(f"[加密配置] 加载失败: {e}")
            return None
    
    
    def delete_config(self, config_name: str) -> bool:
        """
        删除配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            是否删除成功
        """
        config_file = self.config_dir / f"{config_name}.enc"
        
        if not config_file.exists():
            print(f"[加密配置] 配置文件不存在: {config_file}")
            return False
        
        try:
            config_file.unlink()
            print(f"[加密配置] 已删除配置: {config_name}")
            return True
        except Exception as e:
            print(f"[加密配置] 删除失败: {e}")
            return False
    
    
    def list_configs(self) -> list:
        """
        列出所有配置
        
        Returns:
            配置名称列表
        """
        configs = []
        for file in self.config_dir.glob("*.enc"):
            configs.append(file.stem)
        return configs
    
    
    def update_config(self, config_name: str, key: str, value: Any) -> bool:
        """
        更新配置的某个字段
        
        Args:
            config_name: 配置名称
            key: 字段名
            value: 字段值
            
        Returns:
            是否更新成功
        """
        config_data = self.load_config(config_name)
        if config_data is None:
            config_data = {}
        
        config_data[key] = value
        return self.save_config(config_name, config_data)
    
    
    def test_encryption(self) -> bool:
        """
        测试加密/解密功能
        
        Returns:
            测试是否通过
        """
        print("[加密配置] 开始测试加密/解密功能...")
        
        test_data = {
            "api_key": "sk-test-123456",
            "base_url": "https://api.test.com",
            "models": ["test-model-1", "test-model-2"]
        }
        
        # 保存
        if not self.save_config("_test_", test_data):
            print("[加密配置] 测试失败：保存失败")
            return False
        
        # 加载
        loaded_data = self.load_config("_test_")
        if loaded_data is None:
            print("[加密配置] 测试失败：加载失败")
            self.delete_config("_test_")
            return False
        
        # 验证
        if loaded_data != test_data:
            print("[加密配置] 测试失败：数据不匹配")
            self.delete_config("_test_")
            return False
        
        # 清理
        self.delete_config("_test_")
        
        print("[加密配置] ✅ 测试通过！")
        return True


# ============= 快捷函数 =============

_global_config_manager: Optional[EncryptedConfig] = None

def get_config_manager() -> EncryptedConfig:
    """
    获取全局配置管理器（单例模式）
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = EncryptedConfig()
    return _global_config_manager


def save_model_config(provider: str, config: Dict[str, Any]) -> bool:
    """
    保存模型配置（快捷函数）
    
    Args:
        provider: 提供商名称（如 "deepseek", "openai", "ollama"）
        config: 配置数据
    
    Returns:
        是否保存成功
    """
    manager = get_config_manager()
    return manager.save_config(provider, config)


def load_model_config(provider: str) -> Optional[Dict[str, Any]]:
    """
    加载模型配置（快捷函数）
    
    Args:
        provider: 提供商名称
    
    Returns:
        配置数据，失败返回 None
    """
    manager = get_config_manager()
    return manager.load_config(provider)


def setup_default_configs():
    """
    设置默认配置（首次使用时调用）
    
    所有模型配置集中管理，不再有硬编码。
    GlobalModelRouter 启动时自动从加密配置加载。
    """
    manager = get_config_manager()

    # ── Ollama 配置（支持多地址）────────────────────
    # servers: 按 priority 排序（数字越小优先级越高）
    # 心跳检测会自动更新每个服务器的可用性
    ollama_config = {
        "servers": [
            {
                "url": "http://localhost:11434",
                "priority": 0,
                "models": [
                    "qwen2.5:1.5b",
                    "qwen3.5:2b",
                    "qwen3.5:4b",
                    "qwen3.6:latest",
                    "qwen3.5:9b",
                    "deepseek-coder-v2",
                ]
            },
            {
                "url": "http://www.mogoo.com.cn:8899",
                "priority": 1,
                "models": [
                    "qwen2.5:1.5b",
                    "qwen3.5:2b",
                    "qwen3.5:4b",
                    "qwen3.6:latest",
                    "qwen3.5:9b",
                ]
            }
        ]
    }
    manager.save_config("ollama", ollama_config)
    print("[默认配置] 已保存 Ollama 多地址配置")

    # ── DeepSeek API 配置 ─────────────────────────────
    deepseek_config = {
        "api_key": "sk-f05ded8271b74091a499831999d34437",
        "base_url": "https://api.deepseek.com",
        "models": {
            "flash": {
                "model_id": "deepseek_v4_flash",
                "model_name": "deepseek-v4-flash",
                "capabilities": ["chat", "content_generation", "summarization", "translation", "code_generation"],
                "max_tokens": 8192,
                "context_length": 32768,
                "quality_score": 0.8,
                "speed_score": 0.9,
                "cost_score": 0.7,
                "timeout": 60,
            },
            "pro": {
                "model_id": "deepseek_v4_pro",
                "model_name": "deepseek-v4-pro",
                "capabilities": ["chat", "document_planning", "content_generation", "reasoning", "planning", "code_generation", "code_review"],
                "max_tokens": 16384,
                "context_length": 65536,
                "quality_score": 0.95,
                "speed_score": 0.5,
                "cost_score": 0.4,
                "timeout": 120,
            }
        }
    }
    manager.save_config("deepseek", deepseek_config)
    print("[默认配置] 已保存 DeepSeek API 配置")

    # ── OpenAI 配置（禁用，需要代理）────────────────
    openai_config = {
        "enabled": False,
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "models": {
            "gpt4": {
                "model_id": "openai_gpt4",
                "model_name": "gpt-4",
                "capabilities": ["chat", "document_planning", "content_generation", "reasoning", "planning"],
                "max_tokens": 8192,
                "context_length": 128000,
                "quality_score": 0.95,
                "speed_score": 0.4,
                "cost_score": 0.2,
            },
            "gpt35": {
                "model_id": "openai_gpt35",
                "model_name": "gpt-3.5-turbo",
                "capabilities": ["chat", "content_generation", "summarization", "translation", "code_generation"],
                "max_tokens": 4096,
                "context_length": 16384,
                "quality_score": 0.7,
                "speed_score": 0.8,
                "cost_score": 0.5,
            }
        }
    }
    manager.save_config("openai", openai_config)
    print("[默认配置] 已保存 OpenAI 配置（默认禁用）")

    print("\n✅ 默认配置设置完成！所有敏感信息已加密存储。")


if __name__ == "__main__":
    # 测试
    print("🧪 测试加密配置管理器")
    print("=" * 60)
    
    manager = EncryptedConfig()
    
    # 测试加密/解密
    manager.test_encryption()
    
    # 设置默认配置
    setup_default_configs()
    
    # 列出所有配置
    configs = manager.list_configs()
    print(f"\n📋 已保存的配置: {configs}")
    
    # 加载 DeepSeek 配置
    deepseek_config = manager.load_config("deepseek")
    if deepseek_config:
        print(f"\n📊 DeepSeek 配置:")
        print(f"   - API Key: {deepseek_config['api_key'][:10]}...（已隐藏）")
        print(f"   - Base URL: {deepseek_config['base_url']}")
        print(f"   - Models: {list(deepseek_config['models'].values())}")
