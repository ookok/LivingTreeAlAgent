"""
本地加密凭证存储模块
使用Fernet对称加密算法，安全存储各网站的用户名和密码
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.exceptions import InvalidKey
from loguru import logger


class CredentialManager:
    """加密凭证管理器，负责凭证的安全存储与读取"""
    
    def __init__(self, key_dir: Optional[str] = None, cred_file: Optional[str] = None):
        """
        初始化凭证管理器
        
        Args:
            key_dir: 密钥存储目录，默认~/.livingtree
            cred_file: 加密凭证存储路径，默认~/.livingtree/credentials.enc
        """
        # 设置默认路径
        self.key_dir = Path(key_dir) if key_dir else Path.home() / ".livingtree"
        self.key_path = self.key_dir / "credentials.key"
        self.cred_path = Path(cred_file) if cred_file else self.key_dir / "credentials.enc"
        
        # 确保存储目录存在
        self.key_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载或生成加密密钥
        self.key = self._load_or_generate_key()
        self.fernet = Fernet(self.key)
        
        logger.bind(tool="CredentialManager").info(f"凭证管理器初始化完成，存储路径: {self.cred_path}")
    
    def _load_or_generate_key(self) -> bytes:
        """
        加载已有密钥，不存在则生成新密钥
        
        Returns:
            有效的Fernet密钥
        """
        if self.key_path.exists():
            try:
                with open(self.key_path, "rb") as f:
                    key = f.read()
                # 验证密钥有效性
                Fernet(key)
                logger.bind(tool="CredentialManager").debug(f"加载已有密钥: {self.key_path}")
                return key
            except (InvalidKey, Exception) as e:
                logger.bind(tool="CredentialManager").error(f"密钥文件损坏: {e}，将生成新密钥，原有凭证将无法解密")
                # 备份损坏的密钥
                backup_path = self.key_path.with_suffix(".key.bak")
                self.key_path.rename(backup_path)
                logger.bind(tool="CredentialManager").warning(f"已备份损坏密钥到: {backup_path}")
        
        # 生成新密钥并保存
        key = Fernet.generate_key()
        with open(self.key_path, "wb") as f:
            f.write(key)
        
        # 设置文件权限（仅当前用户可读，Windows下暂用系统默认权限）
        try:
            import stat
            self.key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 仅所有者读写
        except Exception as e:
            logger.bind(tool="CredentialManager").warning(f"设置密钥权限失败: {e}")
        
        logger.bind(tool="CredentialManager").info(f"生成新密钥并保存到: {self.key_path}")
        return key
    
    def _load_credentials(self) -> dict:
        """
        加载并解密凭证文件
        
        Returns:
            凭证字典，格式为 {域名: {"username": 用户名, "password": 密码}}
        """
        if not self.cred_path.exists():
            return {}
        
        try:
            with open(self.cred_path, "rb") as f:
                encrypted_data = f.read()
            
            # 解密数据
            decrypted_data = self.fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode("utf-8"))
            
            logger.bind(tool="CredentialManager").debug(f"成功加载凭证文件: {self.cred_path}")
            return credentials
        except InvalidToken:
            error_msg = "凭证文件解密失败，密钥不匹配或文件损坏"
            logger.bind(tool="CredentialManager").error(error_msg)
            raise ValueError(error_msg + "，请删除凭证文件后重新保存")
        except json.JSONDecodeError as e:
            error_msg = f"凭证文件格式错误: {e}"
            logger.bind(tool="CredentialManager").error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"加载凭证文件失败: {e}"
            logger.bind(tool="CredentialManager").error(error_msg)
            raise RuntimeError(error_msg)
    
    def _save_credentials(self, credentials: dict):
        """
        加密并保存凭证文件
        
        Args:
            credentials: 凭证字典
        """
        try:
            # 序列化并加密
            json_data = json.dumps(credentials, ensure_ascii=False, indent=2).encode("utf-8")
            encrypted_data = self.fernet.encrypt(json_data)
            
            # 保存到文件
            with open(self.cred_path, "wb") as f:
                f.write(encrypted_data)
            
            logger.bind(tool="CredentialManager").info(f"凭证已成功保存 to {self.cred_path}")
        except Exception as e:
            error_msg = f"保存凭证文件失败: {e}"
            logger.bind(tool="CredentialManager").error(error_msg)
            raise RuntimeError(error_msg)
    
    def save_credential(self, domain: str, username: str, password: str):
        """
        保存指定域名的登录凭证
        
        Args:
            domain: 网站域名，如 "qianwen.com"
            username: 登录用户名
            password: 登录密码
        """
        if not domain or not username or not password:
            raise ValueError("域名、用户名、密码均不能为空")
        
        credentials = self._load_credentials()
        credentials[domain] = {
            "username": username,
            "password": password
        }
        
        self._save_credentials(credentials)
        logger.bind(tool="CredentialManager").info(f"已保存域名 {domain} 的凭证")
    
    def load_credential(self, domain: str) -> Optional[Tuple[str, str]]:
        """
        加载指定域名的登录凭证
        
        Args:
            domain: 网站域名，如 "qianwen.com"
            
        Returns:
            (用户名, 密码) 元组，未找到则返回None
        """
        credentials = self._load_credentials()
        if domain not in credentials:
            logger.bind(tool="CredentialManager").warning(f"未找到域名 {domain} 的凭证")
            return None
        
        cred = credentials[domain]
        logger.bind(tool="CredentialManager").debug(f"成功加载域名 {domain} 的凭证")
        return cred["username"], cred["password"]
    
    def delete_credential(self, domain: str) -> bool:
        """
        删除指定域名的登录凭证
        
        Args:
            domain: 网站域名，如 "qianwen.com"
            
        Returns:
            是否删除成功
        """
        credentials = self._load_credentials()
        if domain not in credentials:
            logger.bind(tool="CredentialManager").warning(f"未找到域名 {domain} 的凭证，无需删除")
            return False
        
        del credentials[domain]
        self._save_credentials(credentials)
        logger.bind(tool="CredentialManager").info(f"已删除域名 {domain} 的凭证")
        return True
    
    def list_domains(self) -> list:
        """
        列出所有已保存凭证的域名
        
        Returns:
            域名列表
        """
        credentials = self._load_credentials()
        return list(credentials.keys())


# 单例实例，方便全局调用
_default_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """获取默认的凭证管理器单例"""
    global _default_credential_manager
    if _default_credential_manager is None:
        _default_credential_manager = CredentialManager()
    return _default_credential_manager


if __name__ == "__main__":
    # 简单测试
    import logging
    logging.basicConfig(level=logging.INFO)
    
    cm = CredentialManager()
    
    # 测试保存凭证
    cm.save_credential("test.com", "test_user", "test_pass123")
    print(f"保存凭证成功")
    
    # 测试加载凭证
    cred = cm.load_credential("test.com")
    if cred:
        print(f"加载凭证成功: username={cred[0]}, password={cred[1]}")
    
    # 测试列出域名
    domains = cm.list_domains()
    print(f"已保存的域名: {domains}")
    
    # 测试删除凭证
    cm.delete_credential("test.com")
    print(f"删除凭证成功")
    
    # 再次加载应返回None
    cred = cm.load_credential("test.com")
    print(f"删除后加载凭证: {cred}")
