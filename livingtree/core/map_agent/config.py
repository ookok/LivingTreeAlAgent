"""
高德地图配置模块

配置项：
- API_KEY: 高德地图Web服务API密钥
- SECRET_KEY: 安全密钥（可选）
- DEFAULT_ZOOM: 默认缩放级别
- DEFAULT_FORMAT: 默认输出格式
- TIMEOUT: 请求超时时间（秒）
- MAX_RETRIES: 最大重试次数

使用方法：
    from business.map_agent.config import MAP_CONFIG
    
    # 获取API Key
    api_key = MAP_CONFIG['api_key']
    
    # 使用配置初始化工具
    tool = PerceptionTool(api_key=api_key)
"""

# 高德地图配置
MAP_CONFIG = {
    # API Key（从您的高德开放平台获取 - LivingTree应用）
    'api_key': '32aecc8d64d7d2f74df23cfd3d19de23d4d',
    
    # 安全密钥（可选，用于某些高级功能）
    'secret_key': '',
    
    # 默认缩放级别（1-20，数字越大越详细）
    'default_zoom': 15,
    
    # 默认输出格式（png, jpeg, pdf, svg）
    'default_format': 'png',
    
    # 默认DPI（screen: 96, print: 150, high_quality: 300）
    'default_dpi': 'print',
    
    # 请求超时时间（秒）
    'timeout': 30,
    
    # 最大重试次数
    'max_retries': 3,
    
    # 是否启用调试模式
    'debug': False,
    
    # 高德地图API基础URL
    'base_url': 'https://restapi.amap.com/v3',
    
    # 静态地图API URL
    'static_map_url': 'https://restapi.amap.com/v3/staticmap',
    
    # 地理编码API路径
    'geocode_path': '/geocode/geo',
    
    # 逆地理编码API路径
    'reverse_geocode_path': '/geocode/regeo',
    
    # 路径规划API路径
    'direction_path': '/direction',
}


def get_api_key() -> str:
    """获取API Key"""
    return MAP_CONFIG.get('api_key', '')


def get_secret_key() -> str:
    """获取安全密钥"""
    return MAP_CONFIG.get('secret_key', '')


def get_base_url() -> str:
    """获取API基础URL"""
    return MAP_CONFIG.get('base_url', 'https://restapi.amap.com/v3')


def get_timeout() -> int:
    """获取超时时间"""
    return MAP_CONFIG.get('timeout', 30)


def is_debug_enabled() -> bool:
    """检查是否启用调试模式"""
    return MAP_CONFIG.get('debug', False)


def update_config(**kwargs):
    """
    更新配置
    
    Args:
        kwargs: 要更新的配置项
    
    Example:
        update_config(api_key='your_new_key', timeout=60)
    """
    MAP_CONFIG.update(kwargs)
    print(f"✅ 配置已更新: {list(kwargs.keys())}")


def validate_config() -> bool:
    """
    验证配置是否有效
    
    Returns:
        True if config is valid, False otherwise
    """
    api_key = MAP_CONFIG.get('api_key', '').strip()
    
    if not api_key:
        print("❌ 错误：API Key未配置")
        return False
    
    # 验证API Key格式（高德API Key通常为32位或其他长度的十六进制字符）
    if not all(c in '0123456789abcdefABCDEF' for c in api_key):
        print("❌ 错误：API Key格式不正确（应为十六进制）")
        return False
    
    print("✅ 配置验证通过")
    return True


def print_config_summary():
    """打印配置摘要（隐藏敏感信息）"""
    print("=" * 50)
    print("高德地图配置摘要")
    print("=" * 50)
    print(f"API Key: {MAP_CONFIG['api_key'][:8]}...{MAP_CONFIG['api_key'][-4:]}")
    print(f"安全密钥: {'已配置' if MAP_CONFIG['secret_key'] else '未配置'}")
    print(f"默认缩放: {MAP_CONFIG['default_zoom']}")
    print(f"默认格式: {MAP_CONFIG['default_format']}")
    print(f"超时时间: {MAP_CONFIG['timeout']}秒")
    print(f"调试模式: {'开启' if MAP_CONFIG['debug'] else '关闭'}")
    print("=" * 50)