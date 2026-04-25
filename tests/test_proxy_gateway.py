"""
Proxy Gateway 单元测试

Author: LivingTreeAI Team
"""

import pytest
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from core.proxy import (
    ProxyType, RequestPriority, ProxyConfig, EndpointConfig,
    SmartProxyGateway
)


class TestProxyConfig:
    """测试代理配置"""
    
    def test_direct_proxy(self):
        """测试直连配置"""
        proxy = ProxyConfig(proxy_type=ProxyType.DIRECT)
        
        assert proxy.url == ""
        assert proxy.is_valid
        assert proxy.is_valid  # 无需主机端口
    
    def test_http_proxy(self):
        """测试 HTTP 代理"""
        proxy = ProxyConfig(
            proxy_type=ProxyType.HTTP,
            host="127.0.0.1",
            port=7890
        )
        
        assert proxy.url == "http://127.0.0.1:7890"
        assert proxy.is_valid
    
    def test_proxy_with_auth(self):
        """测试带认证的代理"""
        proxy = ProxyConfig(
            proxy_type=ProxyType.HTTPS,
            host="proxy.example.com",
            port=443,
            username="user",
            password="pass"
        )
        
        assert "user:pass@" in proxy.url
        assert proxy.is_valid


class TestEndpointConfig:
    """测试端点配置"""
    
    def test_create_endpoint(self):
        """测试创建端点"""
        endpoint = EndpointConfig(
            name="GitHub",
            url="https://api.github.com",
            timeout=30,
            max_retries=3
        )
        
        assert endpoint.name == "GitHub"
        assert endpoint.is_available
        assert not endpoint.circuit_open
    
    def test_circuit_breaker(self):
        """测试熔断器"""
        endpoint = EndpointConfig(
            name="TestAPI",
            url="https://api.test.com",
            timeout=10,
            max_retries=1
        )
        
        # 模拟失败
        endpoint.failure_count = 5
        
        # 触发熔断
        assert not endpoint.is_available
        endpoint.circuit_open = True
        endpoint.circuit_open_time = 0
        
        # 未超时前不可用
        assert not endpoint.is_available


class TestSmartProxyGateway:
    """测试代理网关"""
    
    @pytest.fixture
    def gateway(self):
        """创建网关实例"""
        # 重置单例
        SmartProxyGateway._instance = None
        gateway = SmartProxyGateway()
        gateway._initialized = False
        gateway.__init__()
        return gateway
    
    def test_singleton(self):
        """测试单例模式"""
        gw1 = SmartProxyGateway()
        gw2 = SmartProxyGateway()
        
        assert gw1 is gw2
    
    def test_set_proxy(self, gateway):
        """测试设置代理"""
        success = gateway.set_proxy("http://127.0.0.1:7890")
        
        assert success
        assert gateway.default_proxy.enabled
        assert gateway.default_proxy.host == "127.0.0.1"
        assert gateway.default_proxy.port == 7890
    
    def test_set_proxy_with_auth(self, gateway):
        """测试设置带认证的代理"""
        success = gateway.set_proxy("http://user:pass@proxy.com:8080")
        
        assert success
        assert gateway.default_proxy.username == "user"
        assert gateway.default_proxy.password == "pass"
    
    def test_disable_proxy(self, gateway):
        """测试禁用代理"""
        gateway.set_proxy("http://127.0.0.1:7890")
        gateway.disable_proxy()
        
        assert not gateway.default_proxy.enabled
    
    def test_enable_proxy(self, gateway):
        """测试启用代理"""
        gateway.disable_proxy()
        gateway.enable_proxy()
        
        assert gateway.default_proxy.enabled
    
    def test_add_endpoint(self, gateway):
        """测试添加端点"""
        endpoint = EndpointConfig(
            name="CustomAPI",
            url="https://api.custom.com",
            timeout=30
        )
        
        gateway.add_endpoint("custom", endpoint)
        
        retrieved = gateway.get_endpoint("custom")
        assert retrieved is not None
        assert retrieved.name == "CustomAPI"
    
    def test_remove_endpoint(self, gateway):
        """测试移除端点"""
        endpoint = EndpointConfig(name="Temp", url="https://temp.com")
        gateway.add_endpoint("temp", endpoint)
        
        success = gateway.remove_endpoint("temp")
        assert success
        assert gateway.get_endpoint("temp") is None
    
    def test_get_available_endpoints(self, gateway):
        """测试获取可用端点"""
        # 添加多个端点
        for name, url in [("api1", "https://api1.com"), 
                          ("api2", "https://api2.com")]:
            endpoint = EndpointConfig(name=name, url=url)
            gateway.add_endpoint(name, endpoint)
        
        available = gateway.get_available_endpoints()
        assert len(available) >= 2
    
    def test_get_stats(self, gateway):
        """测试获取统计"""
        gateway.request_stats["total"] = 100
        gateway.request_stats["success"] = 95
        gateway.request_stats["failed"] = 5
        
        stats = gateway.get_stats()
        
        assert stats["total_requests"] == 100
        assert stats["success"] == 95
        assert stats["failed"] == 5
        assert stats["success_rate"] == 0.95
    
    def test_reset_stats(self, gateway):
        """测试重置统计"""
        gateway.request_stats["total"] = 100
        gateway.reset_stats()
        
        stats = gateway.request_stats
        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0
    
    def test_proxy_url_parsing(self, gateway):
        """测试代理 URL 解析"""
        test_cases = [
            ("http://proxy.com:8080", ProxyType.HTTP, "proxy.com", 8080),
            ("https://proxy.com:443", ProxyType.HTTPS, "proxy.com", 443),
            ("socks5://proxy.com:1080", ProxyType.SOCKS5, "proxy.com", 1080),
        ]
        
        for url, expected_type, expected_host, expected_port in test_cases:
            success = gateway.set_proxy(url)
            assert success
            assert gateway.default_proxy.proxy_type == expected_type
            assert gateway.default_proxy.host == expected_host
            assert gateway.default_proxy.port == expected_port


class TestProxyGatewaySingleton:
    """测试全局实例"""
    
    def test_get_proxy_gateway(self):
        """测试获取全局实例"""
        from core.proxy import get_proxy_gateway
        
        # 重置单例
        SmartProxyGateway._instance = None
        
        gw1 = get_proxy_gateway()
        gw2 = get_proxy_gateway()
        
        assert gw1 is gw2
        assert isinstance(gw1, SmartProxyGateway)


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
