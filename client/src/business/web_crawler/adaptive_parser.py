"""
AdaptiveParser - Scrapling 自适应解析器

Scrapling 的核心亮点：当网站改版后，能自动适配新的 DOM 结构。
不需要手动维护 CSS 选择器。

原理：
1. 首次运行：记录成功的选择器
2. 网站改版：旧选择器失效
3. 自适应模式：自动尝试相似选择器，找到新位置
4. 更新记录：下次直接用新选择器

用法：
    parser = AdaptiveParser()
    content = await parser.extract("https://example.com", "article")
"""

import asyncio
import json
import logging
import hashlib
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

    用法：
        parser = AdaptiveParser()
        content = await parser.extract(
            "https://example.com/blog/post-1",
            content_selector="article .content"
        )
        # 下次即使网站改版，也会自动适配
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        auto_adapt: bool = True,
    ):
        """
        Args:
            cache_dir: 规则缓存目录（用于跨会话持久化）
            auto_adapt: 是否启用自适应（选择器失效时自动修复）
        """
        self.auto_adapt = auto_adapt
        self._rules: Dict[str, ParseRule] = {}
        self._cache_file: Optional[Path] = None

        if cache_dir:
            self._cache_file = Path(cache_dir) / "scrapling_rules.json"
            self._load_rules()

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
            content_selector: 内容区域选择器（如 "article"、".post-content"）
                             如果为 None，则自动寻找正文区域
            title_selector: 标题选择器

        Returns:
            str: 提取的 Markdown 内容
        """
        try:
            from scrapling import Fetcher
        except ImportError:
            logger.warning("Scrapling 未安装，使用降级方案")
            return await self._extract_fallback(url, content_selector)

        try:
            fetcher = Fetcher(auto_adapt=self.auto_adapt, timeout=30)
            response = fetcher.get(url, allow_redirects=True)
            page = response.page

            # 提取标题
            title = ""
            title_elem = page.find(title_selector)
            if title_elem:
                title = title_elem.text.strip()

            # 自适应提取正文
            content = self._adaptive_extract_content(
                page, url, content_selector
            )

            # 如果内容为空，尝试自动寻找正文区域
            if not content and self.auto_adapt:
                content = self._auto_find_content(page)

            return content or ""

        except Exception as e:
            logger.error(f"自适应解析失败: {url} - {e}")
            if self.auto_adapt:
                logger.info("尝试降级方案")
                return await self._extract_fallback(url, content_selector)
            return ""

    def _adaptive_extract_content(
        self,
        page: "Page",
        url: str,
        selector: Optional[str],
    ) -> str:
        """自适应提取正文内容

        Scrapling 的 Page 对象支持自适应：
        - 如果选择器失效，会自动尝试相似的元素
        - 返回 Markdown 格式（保持格式）
        """
        if not selector:
            # 没有指定选择器，尝试自动识别正文区域
            return self._auto_find_content(page)

        # 尝试用指定选择器提取
        elem = page.find(selector)
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
            return elem.markdown

        # 选择器失效，触发自适应
        if self.auto_adapt:
            logger.info(f"选择器失效，启动自适应: {selector}")
            new_selector = self._adapt_selector(page, selector)
            if new_selector:
                elem = page.find(new_selector)
                if elem:
                    # 更新规则
                    key = self._get_rule_key(url, "content")
                    self._rules[key].selector = new_selector
                    self._rules[key].success_count += 1
                    self._save_rules()
                    logger.info(f"自适应成功: {selector} -> {new_selector}")
                    return elem.markdown

        return ""

    def _auto_find_content(self, page: "Page") -> str:
        """自动寻找正文区域（无选择器时）

        启发式策略：
        1. 找 <article> 标签
        2. 找 .content / .post-content / .article-body 等常见类
        3. 找最长的 <p> 标签集合
        """
        # 策略1：常见正文标签
        for tag in ["article", "main", '[role="main"]']:
            elem = page.find(tag)
            if elem:
                text = elem.text or ""
                if len(text) > 200:  # 至少 200 字符
                    return elem.markdown

        # 策略2：常见 CSS 类
        for cls in [".content", ".post-content", ".article-body", ".entry-content", ".post-body"]:
            elem = page.find(cls)
            if elem:
                text = elem.text or ""
                if len(text) > 200:
                    return elem.markdown

        # 策略3：找最长的文本块
        paragraphs = page.find_all("p")
        if paragraphs:
            # 找包含最多 <p> 的父元素
            from collections import Counter
            import asyncio
            parents = []
            for p in paragraphs[:20]:  # 限制数量
                parent = p.parent
                if parent is not None:
                    parents.append(str(parent))
            
            if parents:
                most_common = Counter(parents).most_common(1)
                if most_common:
                    parent_str = most_common[0][0]
                    # 重新查找（这里简化处理，直接返回所有 <p> 的 Markdown）
                    return "\n\n".join(p.markdown for p in paragraphs if p.text.strip())

        return ""

    def _adapt_selector(self, page: "Page", old_selector: str) -> Optional[str]:
        """自适应：当旧选择器失效时，寻找新的选择器

        简化实现：
        1. 提取旧选择器的关键信息（标签名、类名、ID）
        2. 在页面中寻找相似的元素
        """
        import re
        
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
            elem = page.find(f"#{id_}")
            if elem:
                return f"#{id_}"

        if cls:
            # 尝试精确类名
            elem = page.find(f".{cls}")
            if elem:
                return f".{cls}"
            
            # 尝试包含该类名的部分匹配
            all_elements = page.find_all("*")
            for elem in all_elements:
                elem_classes = elem.attrs.get("class", [])
                if isinstance(elem_classes, list):
                    for c in elem_classes:
                        if cls in c or c in cls:
                            # 返回这个元素的 CSS 选择器
                            tag_name = elem.name or "div"
                            return f"{tag_name}.{c}"

        if tag:
            elems = page.find_all(tag)
            if elems:
                # 找最长的那个
                longest = max(elems, key=lambda e: len(e.text or ""))
                if len(longest.text or "") > 200:
                    return tag  # 简化：返回标签名

        return None

    def _get_url_pattern(self, url: str) -> str:
        """提取 URL 模式（用于规则匹配）"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path or ""
        
        # 简化路径（去掉具体的 ID/数字）
        import re
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
                # 简单解析选择器
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
