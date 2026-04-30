"""
Kachilu Browser 集成模块

将 Kachilu Browser 的反检测和验证码绕过功能集成到本项目中
"""

from typing import Optional, Dict, Any, List
import time
import random
from dataclasses import dataclass, field

from browser_use import Agent, Browser

from business.living_tree_ai.browser_gateway.browser_pool import BrowserSession
from business.living_tree_ai.browser_gateway.security_manager import SecurityManager


@dataclass
class KachiluConfig:
    """Kachilu 配置"""
    # 反检测配置
    anti_detection: bool = True
    # 验证码绕过
    captcha_bypass: bool = True
    # 人类行为模拟
    human_simulation: bool = True
    # 延迟配置
    min_delay: float = 0.5
    max_delay: float = 2.0
    # 随机点击
    random_click: bool = True
    # 鼠标移动路径
    mouse_movement: bool = True
    # 浏览器指纹混淆
    fingerprint_obfuscation: bool = True
    # WSL2 支持
    wsl2_support: bool = False


class KachiluIntegrator:
    """Kachilu 集成器"""
    
    def __init__(self, config: Optional[KachiluConfig] = None):
        self.config = config or KachiluConfig()
        self.security_manager: Optional[SecurityManager] = None
    
    def set_security_manager(self, security_manager: SecurityManager):
        """设置安全管理器"""
        self.security_manager = security_manager
    
    def apply_anti_detection(self, browser: Browser) -> None:
        """应用反检测策略"""
        if not self.config.anti_detection:
            return
        
        # 设置浏览器指纹混淆
        if self.config.fingerprint_obfuscation:
            self._obfuscate_fingerprint(browser)
        
        # 禁用自动化特征
        self._disable_automation_features(browser)
        
        # 设置随机用户代理
        self._set_random_user_agent(browser)
    
    def simulate_human_behavior(self, browser: Browser) -> None:
        """模拟人类行为"""
        if not self.config.human_simulation:
            return
        
        # 随机延迟
        self._random_delay()
        
        # 随机鼠标移动
        if self.config.mouse_movement:
            self._simulate_mouse_movement(browser)
        
        # 随机点击
        if self.config.random_click:
            self._simulate_random_click(browser)
    
    def bypass_captcha(self, browser: Browser, captcha_type: str = "auto") -> bool:
        """绕过验证码"""
        if not self.config.captcha_bypass:
            return False
        
        try:
            if captcha_type == "reCAPTCHA":
                return self._bypass_recaptcha(browser)
            elif captcha_type == "hCaptcha":
                return self._bypass_hcaptcha(browser)
            else:
                return self._bypass_generic_captcha(browser)
        except Exception as e:
            print(f"验证码绕过失败: {e}")
            return False
    
    def _obfuscate_fingerprint(self, browser: Browser) -> None:
        """混淆浏览器指纹"""
        # 混淆 Canvas 指纹
        browser.execute_script("""
            Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
                value: function() {
                    const ctx = this.getContext('2d');
                    if (ctx) {
                        ctx.fillStyle = '#FFFFFF';
                        ctx.fillRect(0, 0, this.width, this.height);
                    }
                    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
                }
            });
        """)
        
        # 混淆 WebGL 指纹
        browser.execute_script("""
            Object.defineProperty(WebGLRenderingContext.prototype, 'getParameter', {
                value: function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return this.getParameter(parameter);
                }
            });
        """)
        
        # 混淆 Navigator 信息
        browser.execute_script("""
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                value: Math.floor(Math.random() * 4) + 4
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                value: Math.floor(Math.random() * 4) + 4
            });
        """)
    
    def _disable_automation_features(self, browser: Browser) -> None:
        """禁用自动化特征"""
        # 禁用 webdriver 检测
        browser.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                value: undefined
            });
        """)
        
        # 禁用自动化工具检测
        browser.execute_script("""
            Object.defineProperty(window, 'chrome', {
                value: {
                    runtime: {}
                }
            });
        """)
    
    def _set_random_user_agent(self, browser: Browser) -> None:
        """设置随机用户代理"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        user_agent = random.choice(user_agents)
        browser.execute_script(f"""
            Object.defineProperty(navigator, 'userAgent', {
                value: '{user_agent}',
                writable: false
            });
        """)
    
    def _random_delay(self) -> None:
        """随机延迟"""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)
    
    def _simulate_mouse_movement(self, browser: Browser) -> None:
        """模拟鼠标移动"""
        # 生成随机鼠标路径
        browser.execute_script("""
            function simulateMouseMove() {
                const startX = Math.random() * window.innerWidth;
                const startY = Math.random() * window.innerHeight;
                const endX = Math.random() * window.innerWidth;
                const endY = Math.random() * window.innerHeight;
                const steps = 20;
                
                for (let i = 0; i <= steps; i++) {
                    const x = startX + (endX - startX) * i / steps;
                    const y = startY + (endY - startY) * i / steps;
                    const event = new MouseEvent('mousemove', {
                        clientX: x,
                        clientY: y,
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    document.dispatchEvent(event);
                }
            }
            simulateMouseMove();
        """)
        time.sleep(0.1)  # 短暂延迟
    
    def _simulate_random_click(self, browser: Browser) -> None:
        """
        模拟随机点击
        注意：只点击页面空白区域，避免影响正常操作
        """
        browser.execute_script("""
            function simulateRandomClick() {
                const x = Math.random() * window.innerWidth * 0.8 + window.innerWidth * 0.1;
                const y = Math.random() * window.innerHeight * 0.8 + window.innerHeight * 0.1;
                
                const event = new MouseEvent('click', {
                    clientX: x,
                    clientY: y,
                    bubbles: true,
                    cancelable: true,
                    view: window
                });
                document.dispatchEvent(event);
            }
            simulateRandomClick();
        """)
        time.sleep(0.1)  # 短暂延迟
    
    def _bypass_recaptcha(self, browser: Browser) -> bool:
        """绕过 reCAPTCHA"""
        try:
            # 检查是否存在 reCAPTCHA
            captcha_exists = browser.execute_script("""
                return document.querySelector('.g-recaptcha') !== null || 
                       document.querySelector('[data-sitekey]') !== null;
            """)
            
            if not captcha_exists:
                return True
            
            # 尝试点击 reCAPTCHA 复选框
            browser.execute_script("""
                const checkbox = document.querySelector('.g-recaptcha-checkbox');
                if (checkbox) {
                    checkbox.click();
                }
            """)
            
            # 等待 2 秒让验证码加载
            time.sleep(2)
            
            # 检查是否通过
            is_passed = browser.execute_script("""
                const checkbox = document.querySelector('.g-recaptcha-checkbox');
                return checkbox && checkbox.classList.contains('recaptcha-checkbox-checked');
            """)
            
            return is_passed
        except Exception:
            return False
    
    def _bypass_hcaptcha(self, browser: Browser) -> bool:
        """绕过 hCaptcha"""
        try:
            # 检查是否存在 hCaptcha
            captcha_exists = browser.execute_script("""
                return document.querySelector('.h-captcha') !== null || 
                       document.querySelector('[data-sitekey]') !== null;
            """)
            
            if not captcha_exists:
                return True
            
            # 尝试点击 hCaptcha 复选框
            browser.execute_script("""
                const checkbox = document.querySelector('.h-captcha-checkbox');
                if (checkbox) {
                    checkbox.click();
                }
            """)
            
            # 等待 2 秒让验证码加载
            time.sleep(2)
            
            # 检查是否通过
            is_passed = browser.execute_script("""
                const checkbox = document.querySelector('.h-captcha-checkbox');
                return checkbox && checkbox.classList.contains('h-captcha-checkbox--checked');
            """)
            
            return is_passed
        except Exception:
            return False
    
    def _bypass_generic_captcha(self, browser: Browser) -> bool:
        """绕过通用验证码"""
        try:
            # 检查是否存在常见的验证码元素
            captcha_exists = browser.execute_script("""
                return document.querySelector('input[type="text"][name*="captcha"]') !== null ||
                       document.querySelector('input[type="text"][id*="captcha"]') !== null ||
                       document.querySelector('.captcha') !== null;
            """)
            
            if not captcha_exists:
                return True
            
            # 这里可以集成 OCR 服务来识别验证码
            # 暂时返回 False，表示需要人工处理
            return False
        except Exception:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            "anti_detection": self.config.anti_detection,
            "captcha_bypass": self.config.captcha_bypass,
            "human_simulation": self.config.human_simulation,
            "wsl2_support": self.config.wsl2_support
        }


def create_kachilu_integrator(config: Optional[Dict[str, Any]] = None) -> KachiluIntegrator:
    """
    创建 Kachilu 集成器
    
    Args:
        config: 配置参数
        
    Returns:
        KachiluIntegrator: 集成器实例
    """
    kachilu_config = KachiluConfig(**(config or {}))
    return KachiluIntegrator(kachilu_config)


def integrate_kachilu() -> KachiluIntegrator:
    """
    集成 Kachilu 功能
    
    Returns:
        KachiluIntegrator: 集成器实例
    """
    return create_kachilu_integrator()