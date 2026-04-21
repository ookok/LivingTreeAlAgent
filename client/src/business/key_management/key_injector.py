"""
第1层：密钥注入器 (Key Injection Layer)
========================================

功能：从多个来源自动获取密钥，零交互注入

支持的密钥来源（按优先级）：
1. 环境变量 (Environment Variables)
2. CI/CD Secrets (GitHub/GitLab/Jenkins)
3. 云服务元数据 (AWS/Azure/GCP)
4. 外部密钥库 (HashiCorp Vault, AWS Secrets Manager)
5. 加密配置文件（后备）

Author: Hermes Desktop AI Assistant
"""

import os
import json
import logging
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class CIPlatform(Enum):
    """支持的CI/CD平台"""
    UNKNOWN = "unknown"
    GITHUB_ACTIONS = "github"
    GITLAB_CI = "gitlab"
    JENKINS = "jenkins"
    AZURE_DEVOPS = "azure"
    BITBUCKET = "bitbucket"


@dataclass
class KeySource:
    """密钥来源信息"""
    name: str
    source_type: str
    count: int
    timestamp: datetime
    success: bool
    error: Optional[str] = None


@dataclass
class InjectionResult:
    """注入结果"""
    total_keys: int
    sources_attempted: int
    sources_succeeded: int
    keys_by_source: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class KeyInjector:
    """
    密钥注入器 - 自动从多个来源获取密钥

    设计原则：
    1. 零交互：部署过程中无需人工输入任何密钥
    2. 多源容错：多个来源并行尝试，至少有一个成功即可
    3. 优先级策略：按配置的优先级依次尝试
    4. 静默失败：单个源失败不影响其他源

    使用示例：
        injector = KeyInjector()
        keys = injector.inject_all_keys()
    """

    # 支持的环境变量命名模式
    ENV_PATTERNS = [
        # ECO_PROVIDER_API_KEY 格式（标准）
        lambda key: (key.startswith("ECO_") and key.endswith("_API_KEY"),
                     lambda k: k[4:-8].lower()),  # 移除 ECO_ 和 _API_KEY
        # PROVIDER_API_KEY 格式（简化）
        lambda key: (key.endswith("_API_KEY") and not key.startswith("ECO_"),
                     lambda k: k[:-8].lower()),
        # API_KEY_PROVIDER 格式（反向）
        lambda key: (key.startswith("API_KEY_"),
                     lambda k: k[8:].lower()),
        # HERMES_PROVIDER_KEY 格式
        lambda key: (key.startswith("HERMES_") and key.endswith("_KEY"),
                     lambda k: k[7:-4].lower()),
    ]

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化密钥注入器

        Args:
            config: 可选配置字典
                - priority: 密钥来源优先级列表
                - timeout: 各来源超时时间（秒）
                - retry_count: 重试次数
        """
        self.config = config or {}
        self.priority = self.config.get('priority', [
            'env_vars',
            'ci_secrets',
            'cloud_metadata',
            'external_vault',
            'encrypted_file'
        ])
        self.timeout = self.config.get('timeout', 5)
        self.retry_count = self.config.get('retry_count', 1)

        # 密钥来源注册表
        self.sources: Dict[str, Callable] = {
            'env_vars': self._from_env_vars,
            'ci_secrets': self._from_ci_secrets,
            'cloud_metadata': self._from_cloud_metadata,
            'external_vault': self._from_external_vault,
            'encrypted_file': self._from_encrypted_file,
        }

        # 注入历史
        self.injection_history: List[InjectionResult] = []

        # 检测当前环境
        self._ci_platform = self._detect_ci_platform()
        self._cloud_platform = self._detect_cloud_platform()

        logger.info(f"KeyInjector 初始化完成，CI平台: {self._ci_platform.value}, 云平台: {self._cloud_platform}")

    def inject_all_keys(self) -> Dict[str, str]:
        """
        注入所有密钥（主入口）

        Returns:
            Dict[str, str]: provider -> key 的映射字典
        """
        collected_keys: Dict[str, str] = {}
        sources_result: Dict[str, int] = {}
        errors: List[str] = []
        sources_succeeded = 0

        logger.info(f"开始密钥注入，优先级: {self.priority}")

        for source_name in self.priority:
            if source_name not in self.sources:
                logger.warning(f"未知的密钥来源: {source_name}")
                continue

            try:
                source_func = self.sources[source_name]
                keys = source_func()

                if keys:
                    # 避免覆盖已有密钥（按优先级保留）
                    new_keys = {k: v for k, v in keys.items() if k not in collected_keys}
                    collected_keys.update(new_keys)
                    sources_result[source_name] = len(new_keys)
                    sources_succeeded += 1
                    logger.info(f"从 {source_name} 获取到 {len(new_keys)} 个新密钥")
                else:
                    sources_result[source_name] = 0
                    logger.debug(f"从 {source_name} 未获取到密钥")

            except Exception as e:
                error_msg = f"密钥来源 {source_name} 失败: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)

        # 记录注入历史
        result = InjectionResult(
            total_keys=len(collected_keys),
            sources_attempted=len(self.priority),
            sources_succeeded=sources_succeeded,
            keys_by_source=sources_result,
            errors=errors
        )
        self.injection_history.append(result)

        logger.info(f"密钥注入完成，共 {len(collected_keys)} 个密钥，来自 {sources_succeeded} 个来源")

        return collected_keys

    def get_key(self, provider: str) -> Optional[str]:
        """
        获取指定提供商的密钥

        Args:
            provider: 提供商名称（如 openai, anthropic 等）

        Returns:
            密钥值，如果未找到则返回 None
        """
        keys = self.inject_all_keys()
        return keys.get(provider.lower()) or keys.get(provider.upper()) or keys.get(provider)

    def _from_env_vars(self) -> Dict[str, str]:
        """从环境变量获取密钥"""
        env_keys: Dict[str, str] = {}

        for env_key, env_value in os.environ.items():
            if not env_value or len(env_value) < 5:
                continue

            # 尝试各种命名模式
            for pattern_func in self.ENV_PATTERNS:
                try:
                    matches, extractor = pattern_func(env_key)
                    if matches:
                        provider = extractor(env_key)
                        if provider and provider not in env_keys:
                            env_keys[provider] = env_value
                            break
                except Exception:
                    continue

        return env_keys

    def _from_ci_secrets(self) -> Dict[str, str]:
        """从CI/CD Secrets获取密钥"""
        ci_keys: Dict[str, str] = {}

        if self._ci_platform == CIPlatform.GITHUB_ACTIONS:
            ci_keys.update(self._from_github_secrets())
        elif self._ci_platform == CIPlatform.GITLAB_CI:
            ci_keys.update(self._from_gitlab_secrets())
        elif self._ci_platform == CIPlatform.JENKINS:
            ci_keys.update(self._from_jenkins_secrets())
        elif self._ci_platform == CIPlatform.AZURE_DEVOPS:
            ci_keys.update(self._from_azure_secrets())

        return ci_keys

    def _from_github_secrets(self) -> Dict[str, str]:
        """GitHub Actions Secrets（通过环境变量自动注入）"""
        # GitHub Actions 会自动将 Secrets 注入为环境变量
        # 命名规范：SECRET_NAME -> 环境变量名全大写
        github_keys: Dict[str, str] = {}

        # GitHub 特定的密钥模式
        github_patterns = [
            ('GITHUB_', ''),  # GITHUB_TOKEN 等
        ]

        for env_key, env_value in os.environ.items():
            if env_key.startswith('GITHUB_'):
                # 标准化提供商名称
                provider = env_key[7:].lower()
                if provider and '_' not in provider:
                    github_keys[provider] = env_value

        return github_keys

    def _from_gitlab_secrets(self) -> Dict[str, str]:
        """GitLab CI/CD Variables"""
        gitlab_keys: Dict[str, str] = {}

        for env_key, env_value in os.environ.items():
            if env_key.startswith('CI_'):
                continue
            if '_API_KEY' in env_key or '_TOKEN' in env_key:
                provider = env_key.replace('_API_KEY', '').replace('_TOKEN', '').lower()
                gitlab_keys[provider] = env_value

        return gitlab_keys

    def _from_jenkins_secrets(self) -> Dict[str, str]:
        """Jenkins Credentials"""
        jenkins_keys: Dict[str, str] = {}

        # Jenkins 通过 withCredentials 绑定为环境变量
        for env_key, env_value in os.environ.items():
            if '_API_KEY' in env_key or '_TOKEN' in env_key or '_PASSWORD' in env_key:
                provider = env_key.replace('_API_KEY', '').replace('_TOKEN', '').replace('_PASSWORD', '').lower()
                jenkins_keys[provider] = env_value

        return jenkins_keys

    def _from_azure_secrets(self) -> Dict[str, str]:
        """Azure DevOps Secrets"""
        azure_keys: Dict[str, str] = {}

        for env_key, env_value in os.environ.items():
            if env_key.startswith('AZURE_') and ('KEY' in env_key or 'TOKEN' in env_key or 'SECRET' in env_key):
                provider = env_key[7:].replace('_KEY', '').replace('_TOKEN', '').replace('_SECRET', '').lower()
                azure_keys[provider] = env_value

        return azure_keys

    def _from_cloud_metadata(self) -> Dict[str, str]:
        """从云服务元数据获取（AWS/Azure/GCP）"""
        metadata_keys: Dict[str, str] = {}

        # AWS IMDSv2
        if self._cloud_platform == 'aws':
            try:
                metadata_keys.update(self._get_aws_metadata())
            except Exception as e:
                logger.debug(f"AWS 元数据获取失败: {e}")

        # Azure Instance Metadata Service
        elif self._cloud_platform == 'azure':
            try:
                metadata_keys.update(self._get_azure_metadata())
            except Exception as e:
                logger.debug(f"Azure 元数据获取失败: {e}")

        # GCP Metadata
        elif self._cloud_platform == 'gcp':
            try:
                metadata_keys.update(self._get_gcp_metadata())
            except Exception as e:
                logger.debug(f"GCP 元数据获取失败: {e}")

        return metadata_keys

    def _get_aws_metadata(self) -> Dict[str, str]:
        """获取AWS EC2元数据"""
        import urllib.request
        import urllib.error

        aws_keys: Dict[str, str] = {}

        try:
            # IMDSv2 需要 token
            token_req = urllib.request.Request(
                'http://169.254.169.254/latest/api/token',
                headers={'X-aws-ec2-metadata-token-ttl-seconds': '300'},
                method='PUT'
            )
            token = urllib.request.urlopen(token_req, timeout=2).read().decode()

            # 获取 IAM 角色的临时凭证
            iam_req = urllib.request.Request(
                'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
                headers={'X-aws-ec2-metadata-token': token}
            )
            iam_role = urllib.request.urlopen(iam_req, timeout=2).read().decode()

            creds_req = urllib.request.Request(
                f'http://169.254.169.254/latest/meta-data/iam/security-credentials/{iam_role}',
                headers={'X-aws-ec2-metadata-token': token}
            )
            creds = json.loads(urllib.request.urlopen(creds_req, timeout=2).read())

            aws_keys['aws_access_key'] = creds.get('AccessKeyId', '')
            aws_keys['aws_secret_key'] = creds.get('SecretAccessKey', '')
            aws_keys['aws_token'] = creds.get('Token', '')

        except Exception:
            pass

        return aws_keys

    def _get_azure_metadata(self) -> Dict[str, str]:
        """获取Azure实例元数据"""
        import urllib.request

        azure_keys: Dict[str, str] = {}

        try:
            req = urllib.request.Request(
                'http://169.254.169.254/metadata/instance/compute/storageAccount?api-version=2021-01-01&format=json',
                headers={'Metadata': 'true'}
            )
            # Azure 元数据服务可能不可用
        except Exception:
            pass

        return azure_keys

    def _get_gcp_metadata(self) -> Dict[str, str]:
        """获取GCP元数据"""
        import urllib.request

        gcp_keys: Dict[str, str] = {}

        try:
            req = urllib.request.Request(
                'http://metadata.google.internal/computeMetadata/v1/',
                headers={'Metadata-Flavor': 'Google'}
            )
            # GCP 元数据服务
        except Exception:
            pass

        return gcp_keys

    def _from_external_vault(self) -> Dict[str, str]:
        """从外部密钥库获取（HashiCorp Vault, AWS Secrets Manager等）"""
        vault_keys: Dict[str, str] = {}

        # 尝试 HashiCorp Vault
        vault_addr = os.getenv('VAULT_ADDR')
        if vault_addr:
            try:
                vault_keys.update(self._from_hashicorp_vault(vault_addr))
            except Exception as e:
                logger.debug(f"HashiCorp Vault 连接失败: {e}")

        # 尝试 AWS Secrets Manager
        aws_region = os.getenv('AWS_REGION')
        if aws_region:
            try:
                vault_keys.update(self._from_aws_secrets_manager(aws_region))
            except Exception as e:
                logger.debug(f"AWS Secrets Manager 连接失败: {e}")

        return vault_keys

    def _from_hashicorp_vault(self, vault_addr: str) -> Dict[str, str]:
        """从HashiCorp Vault获取密钥"""
        import urllib.request
        import urllib.error

        vault_keys: Dict[str, str] = {}

        try:
            # 获取 Vault token
            vault_token = os.getenv('VAULT_TOKEN')
            if not vault_token:
                # 尝试 kubernetes 认证
                vault_token = self._vault_kubernetes_auth()

            if not vault_token:
                return vault_keys

            # 读取密钥路径
            secret_path = os.getenv('VAULT_SECRET_PATH', 'secret/data/ecohub')
            req = urllib.request.Request(
                f'{vault_addr}/v1/{secret_path}',
                headers={'X-Vault-Token': vault_token}
            )

            try:
                response = urllib.request.urlopen(req, timeout=self.timeout)
                data = json.loads(response.read())

                if 'data' in data and 'data' in data['data']:
                    for key, value in data['data']['data'].items():
                        vault_keys[key.lower()] = str(value)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    logger.debug(f"Vault 路径不存在: {secret_path}")
                else:
                    raise

        except Exception as e:
            logger.debug(f"HashiCorp Vault 错误: {e}")

        return vault_keys

    def _vault_kubernetes_auth(self) -> Optional[str]:
        """Kubernetes认证获取Vault Token"""
        import urllib.request

        try:
            # 读取 Kubernetes Service Account Token
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                k8s_token = f.read().strip()

            vault_addr = os.getenv('VAULT_ADDR', '')
            vault_role = os.getenv('VAULT_K8S_ROLE', 'ecohub')

            req = urllib.request.Request(
                f'{vault_addr}/v1/auth/kubernetes/login',
                data=json.dumps({
                    'role': vault_role,
                    'jwt': k8s_token
                }).encode(),
                headers={'Content-Type': 'application/json'}
            )

            response = urllib.request.urlopen(req, timeout=self.timeout)
            data = json.loads(response.read())

            return data.get('auth', {}).get('client_token')

        except Exception:
            return None

    def _from_aws_secrets_manager(self, region: str) -> Dict[str, str]:
        """从AWS Secrets Manager获取密钥"""
        aws_keys: Dict[str, str] = {}

        try:
            import boto3
            from botocore.config import Config

            config = Config(timeout=self.timeout)
            client = boto3.client('secretsmanager', region_name=region, config=config)

            secret_name = os.getenv('AWS_SECRETS_NAME', 'ecohub/production')

            response = client.get_secret_value(SecretId=secret_name)
            secret = response['SecretString']

            # 解析JSON格式的密钥
            if secret.startswith('{'):
                secret_data = json.loads(secret)
                for key, value in secret_data.items():
                    aws_keys[key.lower()] = str(value)
            else:
                aws_keys['secret'] = secret

        except Exception as e:
            logger.debug(f"AWS Secrets Manager 错误: {e}")

        return aws_keys

    def _from_encrypted_file(self) -> Dict[str, str]:
        """从加密配置文件获取（后备方案）"""
        encrypted_keys: Dict[str, str] = {}

        # 标准密钥文件位置
        key_file_paths = [
            os.path.expanduser('~/.ecohub/keys.enc'),
            os.path.expanduser('~/.hermes/keys.enc'),
            '/etc/ecohub/keys.enc',
            os.path.join(os.getcwd(), '.keys.enc'),
        ]

        for key_file in key_file_paths:
            if os.path.exists(key_file):
                try:
                    encrypted_keys.update(self._decrypt_key_file(key_file))
                    logger.info(f"从加密文件加载密钥: {key_file}")
                    break
                except Exception as e:
                    logger.warning(f"解密密钥文件失败 {key_file}: {e}")

        return encrypted_keys

    def _decrypt_key_file(self, file_path: str) -> Dict[str, str]:
        """解密密钥文件"""
        from cryptography.fernet import Fernet

        # 获取解密密钥
        master_key = os.getenv('ECO_MASTER_KEY') or os.getenv('HERMES_MASTER_KEY')
        if not master_key:
            raise ValueError("需要 ECO_MASTER_KEY 环境变量来解密密钥文件")

        # 如果是 base64 编码的密钥
        if isinstance(master_key, str):
            master_key = master_key.encode()

        cipher = Fernet(master_key if len(master_key) == 44 else 
                       __import__('base64').urlsafe_b64encode(master_key.ljust(32, b'\0')[:32]))

        with open(file_path, 'rb') as f:
            encrypted_data = f.read()

        decrypted = cipher.decrypt(encrypted_data)
        return json.loads(decrypted.decode())

    def _detect_ci_platform(self) -> CIPlatform:
        """检测CI/CD平台"""
        # GitHub Actions
        if os.getenv('GITHUB_ACTIONS') == 'true':
            return CIPlatform.GITHUB_ACTIONS

        # GitLab CI
        if os.getenv('GITLAB_CI') == 'true':
            return CIPlatform.GITLAB_CI

        # Jenkins
        if os.getenv('JENKINS_HOME') and os.getenv('JENKINS_URL'):
            return CIPlatform.JENKINS

        # Azure DevOps
        if os.getenv('SYSTEM_TEAMFOUNDATIONCOLLECTIONURI'):
            return CIPlatform.AZURE_DEVOPS

        # Bitbucket
        if os.getenv('BITBUCKET_COMMIT'):
            return CIPlatform.BITBUCKET

        return CIPlatform.UNKNOWN

    def _detect_cloud_platform(self) -> str:
        """检测云平台"""
        # AWS
        if os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION'):
            return 'aws'

        # Azure
        if os.getenv('AZURE_FUNCTIONS_ENVIRONMENT') or os.getenv('IDENTITY_HEADER'):
            return 'azure'

        # GCP
        if os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT'):
            return 'gcp'

        # 尝试元数据服务
        try:
            import urllib.request
            urllib.request.urlopen('http://169.254.169.254/', timeout=1)
            return 'aws'  # AWS, Azure, GCP 都使用相同的169.254地址
        except Exception:
            pass

        return 'unknown'

    def get_injection_history(self) -> List[InjectionResult]:
        """获取注入历史"""
        return self.injection_history

    def get_source_status(self) -> Dict[str, bool]:
        """获取各来源状态"""
        status = {}
        for source_name in self.priority:
            if source_name in self.sources:
                try:
                    keys = self.sources[source_name]()
                    status[source_name] = len(keys) > 0
                except Exception:
                    status[source_name] = False
            else:
                status[source_name] = False
        return status