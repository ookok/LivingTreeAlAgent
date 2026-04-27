"""
AdaptiveParser - 自适应解析器（修正版，基于 Scrapling 0.4.7 真实 API）

Scrapling 的核心亮点：当网站改版后，能自动适配新的 DOM 结构。
不需要手动维护 CSS 选择器。

基于真实 API：
- Fetcher.configure(adaptive=True)  # 类方法
- f = Fetcher()
- r = f.get(url, timeout=...)
- r.status, r.url, r.text, r.body, r.prettify
- r.find(selector), r.find_all(selector)
- r.css(selector), r.xpath(xpath)
- NO r.page attribute!

用法：
    parser = AdaptiveParser()
    content = await parser.extract("https://example.com", "article")
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParseRule:
    """解析规则（可自适应）"""
    url_pattern: str          # URL 模式（用于匹配同类页面）
    selector: str            # CSS 选择器
    success_count: int = 0  # 成功次数
    last_used: str = ""     # 最后使用时间
    alternatives: List[str] = field(default_factory=list)  # 备选选择器


class AdaptiveParser:
    """自适应解析器

    当网站改版导致选择器失效时，自动寻找新的选择器。
    这是 Scrapling 相比 BeautifulSoup 的核心优势。
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        auto_adapt: bool = True,
    ):
        self.auto_adapt = auto_adapt
        self._rules: Dict[str, ParseRule] = {}
        self._cache_file: Optional[Path] = None
        self._configured = False

        if cache_dir:
            self._cache_file = Path(cache_dir) / "scrapling_rules.json"
            self._load_rules()

    def _ensure_configured(self):
        """确保 Scrapling Fetcher 类已配置"""
        if self.auto_adapt and not self._configured:
            try:
                from scrapling import Fetcher
                Fetcher.configure(adaptive=True)
                self._configured = True
                logger.info("Scrapling Fetcher 自适应模式已启用")
            except Exception as e:
                logger.warning(f"Scrapling 配置失败: {e}")

    def _load_rules(self):
        """加载持久化的规则"""
        if self._cache_file and self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, rule_data in data.items():
                    self._rules[key] = ParseRule(**rule_data)
                logger.info(f"加载了 {len(self._rules)} 条自适应规则")
            except Exception as e:
                logger.warning(f"加载规则失败: {e}")

    def _save_rules(self):
        """保存规则到文件"""
        if self._cache_file:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = {}
                for key, rule in self._rules.items():
                    data[key] = {
                        "url_pattern": rule.url_pattern,
                        "selector": rule.selector,
                        "success_count": rule.success_count,
                        "last_used": rule.last_used,
                        "alternatives": rule.alternatives,
                    }
                with open(self._cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"保存规则失败: {e}")

    def _get_rule_key(self, url: str, field: str) -> str:
        """生成规则键（基于 URL 域名 + 字段名）"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        return f"{domain}:{field}"

    async def extract(
        self,
        url: str,
        content_selector: Optional[str] = None,
        title_selector: str = "title",
    ) -> str:
        """自适应提取网页内容

        Args:
            url: 目标 URL
            content_selector: 内容区域选择器
            title_selector: 标题选择器

        Returns:
            str: 提取的文本内容
        """
        self._ensure_configured()

        try:
            from scrapling import Fetcher
        except ImportError:
            logger.warning("Scrapling 未安装，使用降级方案")
            return await self._extract_fallback(url, content_selector)

        try:
            f = Fetcher()
            response = f.get(url, timeout=30)

            if response.status != 200:
                logger.warning(f"HTTP {response.status}: {url}")
                return ""

            # 提取标题
            title = ""
            title_elem = response.find(title_selector)
            if title_elem:
                # 用 get_all_text() 获取完整文本（.text 可能为空）
                if hasattr(title_elem, 'get_all_text'):
                    title = title_elem.get_all_text().strip()
                elif hasattr(title_elem, 'text'):
                    title = title_elem.text.strip()

            # 自适应提取正文
            content = self._adaptive_extract_content(
                response, url, content_selector
            )

            # 如果内容为空，尝试自动寻找正文区域
            if not content and self.auto_adapt:
                content = self._auto_find_content(response)

            return content or ""

        except Exception as e:
            logger.error(f"自适应解析失败: {url} - {e}")
            if self.auto_adapt:
                logger.info("尝试降级方案")
                return await self._extract_fallback(url, content_selector)
            return ""

    def _adaptive_extract_content(
        self,
        response,
        url: str,
        selector: Optional[str],
    ) -> str:
        """自适应提取正文内容

        Scrapling 的 Response.find() 支持自适应：
        - 如果选择器失效，会自动尝试相似的元素
        """
        if not selector:
            return self._auto_find_content(response)

        # 尝试用指定选择器提取
        elem = response.find(selector)
        if elem:
            # 记录成功规则
            key = self._get_rule_key(url, "content")
            if key not in self._rules:
                self._rules[key] = ParseRule(
                    url_pattern=self._get_url_pattern(url),
                    selector=selector,
                    success_count=1,
                )
            else:
                self._rules[key].success_count += 1
            self._save_rules()

            # 返回文本（优先用 get_all_text()）
            if hasattr(elem, 'get_all_text'):
                return elem.get_all_text()
            elif hasattr(elem, 'text'):
                return elem.text or ""
            return ""

        # 选择器失效，触发自适应
        if self.auto_adapt:
            logger.info(f"选择器失效，启动自适应: {selector}")
            new_selector = self._adapt_selector(response, selector)
            if new_selector:
                elem = response.find(new_selector)
                if elem:
                    # 更新规则
                    key = self._get_rule_key(url, "content")
                    self._rules[key].selector = new_selector
                    self._rules[key].success_count += 1
                    self._save_rules()
                    logger.info(f"自适应成功: {selector} -> {new_selector}")
                    return elem.text or ""

        return ""

    def _auto_find_content(self, response) -> str:
        """自动寻找正文区域（无选择器时）"""
        def _safe_text(obj) -> str:
            """安全获取对象文本"""
            if hasattr(obj, 'get_all_text'):
                result = obj.get_all_text()
                if result:
                    return result
            if hasattr(obj, 'text'):
                result = obj.text
                if result:
                    return result
            return ""

        # 策略1：常见正文标签
        for tag in ["article", "main"]:
            elem = response.find(tag)
            if elem:
                text = _safe_text(elem)
                if len(text) > 200:
                    return text

        # 策略2：常见 CSS 类
        for cls in [".content", ".post-content", ".article-body",
                     ".entry-content", ".post-body"]:
            elem = response.find(cls)
            if elem:
                text = _safe_text(elem)
                if len(text) > 200:
                    return text

        # 策略3：拼接所有 <p> 的文本
        paragraphs = response.find_all("p")
        if paragraphs:
            texts = []
            for p in paragraphs:
                t = _safe_text(p)
                if t and t.strip():
                    texts.append(t)
            if texts:
                return "\n\n".join(texts)[:5000]

        # 策略4：直接返回 body 文本
        body = response.find("body")
        if body:
            return _safe_text(body)

        return ""

    def _adapt_selector(self, response, old_selector: str) -> Optional[str]:
        """自适应：当旧选择器失效时，寻找新的选择器"""

        # 解析旧选择器
        tag = ""
        cls = ""
        id_ = ""

        tag_match = re.match(r'^(\w+)', old_selector)
        if tag_match:
            tag = tag_match.group(1)

        class_match = re.search(r'\.([\w-]+)', old_selector)
        if class_match:
            cls = class_match.group(1)

        id_match = re.search(r'#([\w-]+)', old_selector)
        if id_match:
            id_ = id_match.group(1)

        # 尝试用关键信息重新查找
        if id_:
            elem = response.find(f"#{id_}")
            if elem:
                return f"#{id_}"

        if cls:
            elem = response.find(f".{cls}")
            if elem:
                return f".{cls}"

            # 尝试包含该类名的部分匹配（遍历所有元素）
            all_elems = response.find_all("*")
            for elem in all_elems:
                attrs = getattr(elem, 'attrs', {})
                elem_classes = attrs.get('class', [])
                if isinstance(elem_classes, list):
                    for c in elem_classes:
                        if cls in c or c in cls:
                            name = getattr(elem, 'name', 'div')
                            return f".{c}"

        if tag:
            elems = response.find_all(tag)
            if elems:
                longest = max(
                    (e for e in elems if getattr(e, 'text', '')),
                    key=lambda e: len(getattr(e, 'text', '') or ""),
                    default=None
                )
                if longest and len(getattr(longest, 'text', '') or "") > 200:
                    return tag

        return None

    def _get_url_pattern(self, url: str) -> str:
        """提取 URL 模式（用于规则匹配）"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path or ""

        # 简化路径
        simplified = re.sub(r'/\d+', '/:id', path)
        simplified = re.sub(r'/[a-f0-9-]{36}', '/:uuid', simplified)

        return f"{parsed.netloc}{simplified}"

    async def _extract_fallback(
        self,
        url: str,
        selector: Optional[str] = None,
    ) -> str:
        """降级方案：使用 requests + lxml"""
        try:
            import requests
            from lxml import html as lxml_html
            import re

            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                return ""

            doc = lxml_html.fromstring(resp.content)

            # 去掉 script/style
            for tag in doc.xpath("//script | //style"):
                tag.getparent().remove(tag)

            # 提取正文
            if selector:
                if selector.startswith("."):
                    cls = selector[1:]
                    elem = doc.find(f'.//*[contains(@class, "{cls}")]')
                elif selector.startswith("#"):
                    id_ = selector[1:]
                    elem = doc.find(f'.//*[@id="{id_}"]')
                else:
                    elem = doc.find(f".//{selector}")

                if elem is not None:
                    return elem.text_content().strip()

            # 没有选择器：找 <article> 或 <main>
            for tag in ["article", "main"]:
                elem = doc.find(f".//{tag}")
                if elem is not None:
                    return elem.text_content().strip()

            # 最后：返回 body 文本
            body = doc.find(".//body")
            if body is not None:
                text = body.text_content()
                return re.sub(r'\s+', ' ', text).strip()

            return ""

        except Exception as e:
            logger.error(f"降级方案失败: {url} - {e}")
            return ""
