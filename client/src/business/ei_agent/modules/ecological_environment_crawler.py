"""
生态环境网站爬虫模块 - 复用系统 ScraplingEngine
调用 client.src.business.web_crawler.engine.ScraplingEngine
不再重复造轮子
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# 复用系统已有的 ScraplingEngine
try:
    from business.web_crawler.engine import ScraplingEngine, CrawlResult
    _HAS_SCRAPLING = True
except ImportError:
    ScraplingEngine = None
    CrawlResult = None
    _HAS_SCRAPLING = False
    print("[EcologicalCrawler] 警告: ScraplingEngine 未找到，将使用降级方案")


# 生态环境网站配置
ECO_SITES = {
    # ── 国家级 ─────────────────────────────────────────────────
    "mee": {
        "name": "生态环境部",
        "base_url": "https://www.mee.gov.cn",
        "news_list": [
            "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/",
            "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk02/",
            "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk03/",
        ],
        "selectors": {
            "title": "h1, .title, [class*='title']",
            "content": ".content, .article-content, [class*='content']",
            "publish_time": ".time, .date, [class*='time'], [class*='date']",
            "attachments": "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx']",
        }
    },
    # ── 直辖市 ─────────────────────────────────────────────────
    "beijing": {
        "name": "北京市生态环境局",
        "base_url": "http://sthjj.beijing.gov.cn",
        "news_list": ["http://sthjj.beijing.gov.cn/bjhrb/index/index.html"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "shanghai": {
        "name": "上海市生态环境局",
        "base_url": "https://sthj.sh.gov.cn",
        "news_list": ["https://sthj.sh.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "tianjin": {
        "name": "天津市生态环境局",
        "base_url": "http://sthj.tj.gov.cn",
        "news_list": ["http://sthj.tj.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "chongqing": {
        "name": "重庆市生态环境局",
        "base_url": "http://sthjj.cq.gov.cn",
        "news_list": ["http://sthjj.cq.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    # ── 省份 ─────────────────────────────────────────────────
    "guangdong": {
        "name": "广东省生态环境厅",
        "base_url": "http://gdee.gd.gov.cn",
        "news_list": ["http://gdee.gd.gov.cn/hjjce/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "jiangsu": {
        "name": "江苏省生态环境厅",
        "base_url": "http://sthjt.jiangsu.gov.cn",
        "news_list": ["http://sthjt.jiangsu.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "zhejiang": {
        "name": "浙江省生态环境厅",
        "base_url": "http://sthjt.zj.gov.cn",
        "news_list": ["http://sthjt.zj.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "shandong": {
        "name": "山东省生态环境厅",
        "base_url": "http://sthj.shandong.gov.cn",
        "news_list": ["http://sthj.shandong.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "sichuan": {
        "name": "四川省生态环境厅",
        "base_url": "http://sthjt.sc.gov.cn",
        "news_list": ["http://sthjt.sc.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "hubei": {
        "name": "湖北省生态环境厅",
        "base_url": "http://sthjt.hubei.gov.cn",
        "news_list": ["http://sthjt.hubei.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "hunan": {
        "name": "湖南省生态环境厅",
        "base_url": "http://sthjt.hunan.gov.cn",
        "news_list": ["http://sthjt.hunan.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "hebei": {
        "name": "河北省生态环境厅",
        "base_url": "http://hbepb.hebei.gov.cn",
        "news_list": ["http://hbepb.hebei.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "henan": {
        "name": "河南省生态环境厅",
        "base_url": "http://sthjt.henan.gov.cn",
        "news_list": ["http://sthjt.henan.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "liaoning": {
        "name": "辽宁省生态环境厅",
        "base_url": "http://sthjt.ln.gov.cn",
        "news_list": ["http://sthjt.ln.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "shaanxi": {
        "name": "陕西省生态环境厅",
        "base_url": "http://sthjt.shaanxi.gov.cn",
        "news_list": ["http://sthjt.shaanxi.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    # ── 重点城市 ─────────────────────────────────────────────────
    "shenzhen": {
        "name": "深圳市生态环境局",
        "base_url": "http://sthj.sz.gov.cn",
        "news_list": ["http://sthj.sz.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "guangzhou": {
        "name": "广州市生态环境局",
        "base_url": "http://sthjj.gz.gov.cn",
        "news_list": ["http://sthjj.gz.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "hangzhou": {
        "name": "杭州市生态环境局",
        "base_url": "http://sthjj.hangzhou.gov.cn",
        "news_list": ["http://sthjj.hangzhou.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "nanjing": {
        "name": "南京市生态环境局",
        "base_url": "http://sthjj.nanjing.gov.cn",
        "news_list": ["http://sthjj.nanjing.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "chengdu": {
        "name": "成都市生态环境局",
        "base_url": "http://sthj.chengdu.gov.cn",
        "news_list": ["http://sthj.chengdu.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
    "wuhan": {
        "name": "武汉市生态环境局",
        "base_url": "http://sthjj.wuhan.gov.cn",
        "news_list": ["http://sthjj.wuhan.gov.cn/"],
        "selectors": {"title": "h1", "content": ".content"}
    },
}


class EcologicalEnvironmentCrawler:
    """生态环境网站爬虫 - 复用 ScraplingEngine"""

    def __init__(self, cache_dir: str = None, use_scrapling: bool = True):
        """
        Args:
            cache_dir: 缓存目录
            use_scrapling: 是否使用 ScraplingEngine（默认True）
        """
        self.cache_dir = Path(cache_dir or (Path(__file__).parent.parent / "data" / "crawler_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.use_scrapling = use_scrapling and _HAS_SCRAPLING

        # 初始化 ScraplingEngine（如果可用）
        if self.use_scrapling:
            self.engine = ScraplingEngine(timeout=30, adaptive=True)
            print(f"[EcologicalCrawler] 使用 ScraplingEngine")
        else:
            # 降级方案：使用 requests + BeautifulSoup
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            print(f"[EcologicalCrawler] ScraplingEngine 不可用，使用降级方案")

        # 已抓取URL缓存
        self.crawled_cache_file = self.cache_dir / "crawled_urls.json"
        self.crawled_urls = self._load_crawled_urls()

    def _load_crawled_urls(self) -> dict:
        if self.crawled_cache_file.exists():
            with open(self.crawled_cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_crawled_urls(self):
        with open(self.crawled_cache_file, "w", encoding="utf-8") as f:
            json.dump(self.crawled_urls, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 核心抓取方法（复用 ScraplingEngine）
    # ============================================================

    async def fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        抓取单个页面（复用 ScraplingEngine）
        返回: {"url", "title", "content", "html", "attachments", "success"}
        """
        cache_key = url
        if url in self.crawled_urls:
            print(f"[EcologicalCrawler] 已缓存，跳过: {url}")
            return None

        try:
            if self.use_scrapling:
                result: CrawlResult = await self.engine.extract(url, selector=None, output_format="text")
                if not result.success:
                    print(f"[EcologicalCrawler] 抓取失败: {result.error}")
                    return None

                # 提取附件链接
                attachments = self._extract_attachments_from_html(result.html or result.content, url)

                data = {
                    "url": result.url,
                    "title": result.title,
                    "content": result.content,
                    "html": result.html,
                    "attachments": attachments,
                    "success": True,
                    "crawled_at": datetime.now().isoformat(),
                }
            else:
                # 降级方案
                data = await self._fetch_fallback(url)

            # 标记已抓取
            self.crawled_urls[cache_key] = datetime.now().isoformat()
            if len(self.crawled_urls) % 10 == 0:
                self._save_crawled_urls()

            return data

        except Exception as e:
            print(f"[EcologicalCrawler] 抓取异常 {url}: {e}")
            return None

    def _extract_attachments_from_html(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """从HTML中提取附件链接（PDF/Word/Excel）"""
        if not html:
            return []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            attachments = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)

                # 检查是否是附件链接
                if any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                    # 拼接绝对URL
                    if not href.startswith("http"):
                        from urllib.parse import urljoin
                        href = urljoin(base_url, href)

                    attachments.append({
                        "url": href,
                        "text": text or href.split("/")[-1],
                        "ext": href.split(".")[-1].lower(),
                    })

            return attachments
        except Exception as e:
            print(f"[EcologicalCrawler] 提取附件链接失败: {e}")
            return []

    async def _fetch_fallback(self, url: str) -> Dict[str, Any]:
        """降级方案：使用 requests + lxml"""
        import requests
        from lxml import html as lxml_html

        resp = self.session.get(url, timeout=30)
        resp.encoding = resp.apparent_encoding or "utf-8"

        doc = lxml_html.fromstring(resp.content)
        title_elem = doc.find(".//title")
        title = title_elem.text_content().strip() if title_elem is not None else ""

        # 去掉 script/style
        for tag in doc.xpath("//script | //style"):
            tag.getparent().remove(tag)

        body = doc.find(".//body")
        content = body.text_content() if body is not None else doc.text_content()
        content = re.sub(r"\s+", " ", content).strip()

        attachments = self._extract_attachments_from_html(resp.text, url)

        return {
            "url": url,
            "title": title,
            "content": content,
            "html": resp.text,
            "attachments": attachments,
            "success": True,
            "crawled_at": datetime.now().isoformat(),
        }

    # ============================================================
    # 批量抓取（并发）
    # ============================================================

    async def crawl_mee_gov_cn(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        """抓取生态环境部官网"""
        print(f"[EcologicalCrawler] 开始抓取生态环境部 (max_pages={max_pages})")
        results = []
        site = ECO_SITES["mee"]

        # 收集待抓取URL
        urls = []
        for list_url in site["news_list"]:
            # 先抓取列表页，提取文章链接
            list_data = await self.fetch_page(list_url)
            if list_data and list_data.get("html"):
                article_urls = self._extract_article_urls(list_data["html"], list_url, site["base_url"])
                urls.extend(article_urls[:max_pages])
                if len(urls) >= max_pages:
                    break

        # 并发抓取
        results = await self._batch_fetch(urls[:max_pages])
        self._save_crawled_urls()
        print(f"[EcologicalCrawler] 生态环境部抓取完成: {len(results)} 篇")
        return results

    def _extract_article_urls(self, html: str, page_url: str, base_url: str) -> List[str]:
        """从列表页提取文章链接"""
        if not html:
            return []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            urls = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # 过滤：只保留可能是文章详情页的链接
                if any(x in href for x in ["/xxgk/", "/zwgk/", "/content/"]):
                    if not href.startswith("http"):
                        from urllib.parse import urljoin
                        href = urljoin(page_url, href)
                    if href not in urls:
                        urls.append(href)
            return urls
        except Exception:
            return []

    async def _batch_fetch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """批量并发抓取"""
        import asyncio
        semaphore = asyncio.Semaphore(5)

        async def _fetch_with_semaphore(url):
            async with semaphore:
                return await self.fetch_page(url)

        tasks = [_fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if r is not None and not isinstance(r, Exception)]

    async def crawl_all_provinces(self, max_per_province: int = 3) -> List[Dict[str, Any]]:
        """抓取所有已配置的省份网站"""
        print(f"[EcologicalCrawler] 开始抓取省份网站")
        all_results = []
        for province_key in ECO_SITES:
            if province_key == "mee":
                continue
            results = await self._crawl_province(province_key, max_per_province)
            all_results.extend(results)
        self._save_crawled_urls()
        print(f"[EcologicalCrawler] 省份抓取完成: 共 {len(all_results)} 篇")
        return all_results

    async def _crawl_province(self, province_key: str, max_pages: int) -> List[Dict[str, Any]]:
        """抓取单个省份"""
        site = ECO_SITES.get(province_key)
        if not site:
            return []
        print(f"[EcologicalCrawler] 抓取: {site['name']}")
        urls = []
        for list_url in site.get("news_list", []):
            list_data = await self.fetch_page(list_url)
            if list_data and list_data.get("html"):
                article_urls = self._extract_article_urls(list_data["html"], list_url, site["base_url"])
                urls.extend(article_urls[:max_pages])
                if len(urls) >= max_pages:
                    break

        return await self._batch_fetch(urls[:max_pages])

    # ============================================================
    # 附件下载（复用 ScraplingEngine 的底层能力）
    # ============================================================

    async def download_attachment(self, url: str, save_dir: str = None) -> Dict[str, Any]:
        """
        下载附件（PDF/Word/Excel）
        复用 ScraplingEngine 的 HTTP 能力
        """
        save_dir = Path(save_dir or (self.cache_dir / "attachments"))
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            if self.use_scrapling:
                # ScraplingEngine 的 Fetcher 支持二进制下载
                import scrapling
                fetcher = scrapling.Fetcher()
                response = fetcher.get(url, timeout=60)

                if response.status != 200:
                    return {"success": False, "error": f"HTTP {response.status}"}

                # 获取文件名
                filename = self._get_filename_from_response(response, url)
                save_path = save_dir / filename

                # 保存文件
                with open(save_path, "wb") as f:
                    f.write(response.body)

                return {
                    "success": True,
                    "file_path": str(save_path),
                    "url": url,
                    "size": save_path.stat().st_size,
                }
            else:
                # 降级方案
                import requests
                resp = self.session.get(url, timeout=60)
                resp.raise_for_status()
                filename = url.split("/")[-1].split("?")[0] or f"attachment_{int(time.time())}"
                save_path = save_dir / filename
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "success": True,
                    "file_path": str(save_path),
                    "url": url,
                    "size": save_path.stat().st_size,
                }
        except Exception as e:
            print(f"[EcologicalCrawler] 下载附件失败 {url}: {e}")
            return {"success": False, "url": url, "error": str(e)}

    def _get_filename_from_response(self, response, fallback_url: str) -> str:
        """从响应头或URL中提取文件名"""
        # 尝试从 Content-Disposition 获取
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            import re
            match = re.search(r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\'\\n]+)', cd)
            if match:
                return match.group(1).strip("\"\'")
        # 从URL获取
        filename = fallback_url.split("/")[-1].split("?")[0]
        if filename and "." in filename:
            return filename
        # 生成默认名
        ext = self._guess_ext_from_content_type(response.headers.get("Content-Type", ""))
        return f"attachment_{int(time.time())}{ext}"

    def _guess_ext_from_content_type(self, ct: str) -> str:
        mapping = {"pdf": ".pdf", "word": ".doc", "spreadsheet": ".xls", "text": ".txt"}
        for k, v in mapping.items():
            if k in ct:
                return v
        return ".bin"

    # ============================================================
    # 便捷函数
    # ============================================================

    async def crawl_and_download_all(self, max_pages: int = 5) -> Dict[str, Any]:
        """
        完整流程：抓取网页 + 下载所有附件
        返回：{"pages": [...], "attachments": [...]}
        """
        print(f"[EcologicalCrawler] 开始完整抓取流程")
        pages = await self.crawl_mee_gov_cn(max_pages=max_pages)

        attachments = []
        for page in pages:
            for att in page.get("attachments", []):
                result = await self.download_attachment(att["url"])
                if result.get("success"):
                    attachments.append(result)

        return {
            "pages": pages,
            "attachments": attachments,
            "page_count": len(pages),
            "attachment_count": len(attachments),
        }


# ============================================================
# 便捷函数（保持与原接口兼容）
# ============================================================

async def crawl_mee_website(max_pages: int = 5) -> List[Dict[str, Any]]:
    """抓取生态环境部官网（便捷函数）"""
    crawler = EcologicalEnvironmentCrawler()
    return await crawler.crawl_mee_gov_cn(max_pages=max_pages)


async def crawl_province_website(province: str, base_url: str, max_pages: int = 3) -> List[Dict[str, Any]]:
    """抓取省份网站（便捷函数）"""
    crawler = EcologicalEnvironmentCrawler()
    # 动态添加站点
    ECO_SITES[province] = {"name": province, "base_url": base_url, "news_list": [base_url]}
    return await crawler._crawl_province(province, max_pages)


if __name__ == "__main__":
    import asyncio

    async def test():
        crawler = EcologicalEnvironmentCrawler()
        print("测试: 抓取生态环境部")
        results = await crawler.crawl_mee_gov_cn(max_pages=2)
        print(f"抓取到 {len(results)} 篇")
        if results:
            print(f"第一篇标题: {results[0].get('title', '')[:50]}")
            print(f"附件数: {len(results[0].get('attachments', []))}")

    asyncio.run(test())
