"""
Website Adapter Registry - 网站适配器注册表
================================================

管理 80+ 网站适配器的注册、发现和匹配。

注册表包含 80+ 主流网站的元数据，
每个网站对应一个适配器类（或通用适配器）。
"""

import importlib
import logging
from typing import Optional, Dict, List, Any
from loguru import logger

from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


# ============================================================
# 80+ 网站元数据定义
# ============================================================

WEBSITE_REGISTRY_DATA = [
    # ===== 开发平台（10 个）=====
    {"name": "github", "domains": ["github.com", "gist.github.com"], "module": "github", "class": "GitHubAdapter"},
    {"name": "gitlab", "domains": ["gitlab.com"], "module": "gitlab", "class": "GitLabAdapter"},
    {"name": "bitbucket", "domains": ["bitbucket.org"], "module": "bitbucket", "class": "BitbucketAdapter"},
    {"name": "gitee", "domains": ["gitee.com"], "module": "gitee", "class": "GiteeAdapter"},
    {"name": "coding", "domains": ["coding.net"], "module": "coding", "class": "CodingAdapter"},
    {"name": "sourceforge", "domains": ["sourceforge.net"], "module": "sourceforge", "class": "SourceForgeAdapter"},
    {"name": "codeberg", "domains": ["codeberg.org"], "module": "codeberg", "class": "CodebergAdapter"},
    {"name": "azure_devops", "domains": ["dev.azure.com"], "module": "azure_devops", "class": "AzureDevOpsAdapter"},
    {"name": "google_cloud_source", "domains": ["source.cloud.google.com"], "module": "google_cloud_source", "class": "GoogleCloudSourceAdapter"},
    {"name": "aws_codecommit", "domains": ["console.aws.amazon.com/codecommit"], "module": "aws_codecommit", "class": "AWSCodeCommitAdapter"},

    # ===== 技术社区（10 个）=====
    {"name": "stackoverflow", "domains": ["stackoverflow.com"], "module": "stackoverflow", "class": "StackOverflowAdapter"},
    {"name": "reddit", "domains": ["reddit.com", "old.reddit.com"], "module": "reddit", "class": "RedditAdapter"},
    {"name": "hackernews", "domains": ["news.ycombinator.com"], "module": "hackernews", "class": "HackerNewsAdapter"},
    {"name": "v2ex", "domains": ["v2ex.com"], "module": "v2ex", "class": "V2EXAdapter"},
    {"name": "juejin", "domains": ["juejin.cn"], "module": "juejin", "class": "JuejinAdapter"},
    {"name": "devto", "domains": ["dev.to"], "module": "devto", "class": "DevToAdapter"},
    {"name": "hashnode", "domains": ["hashnode.com"], "module": "hashnode", "class": "HashnodeAdapter"},
    {"name": "lobsters", "domains": ["lobsters.rs"], "module": "lobsters", "class": "LobstersAdapter"},
    {"name": "programmers_stack", "domains": ["programmers.stackexchange.com"], "module": "programmers_stack", "class": "ProgrammersStackAdapter"},
    {"name": "codeproject", "domains": ["codeproject.com"], "module": "codeproject", "class": "CodeProjectAdapter"},

    # ===== 云服务商（10 个）=====
    {"name": "aws", "domains": ["aws.amazon.com", "console.aws.amazon.com"], "module": "aws", "class": "AWSAdapter"},
    {"name": "azure", "domains": ["portal.azure.com"], "module": "azure", "class": "AzureAdapter"},
    {"name": "gcp", "domains": ["console.cloud.google.com"], "module": "gcp", "class": "GCPAdapter"},
    {"name": "aliyun", "domains": ["aliyun.com", "concole.aliyun.com"], "module": "aliyun", "class": "AliyunAdapter"},
    {"name": "tencent_cloud", "domains": ["cloud.tencent.com"], "module": "tencent_cloud", "class": "TencentCloudAdapter"},
    {"name": "huawei_cloud", "domains": ["console.huaweicloud.com"], "module": "huawei_cloud", "class": "HuaweiCloudAdapter"},
    {"name": "baidu_cloud", "domains": ["cloud.baidu.com"], "module": "baidu_cloud", "class": "BaiduCloudAdapter"},
    {"name": "oracle_cloud", "domains": ["cloud.oracle.com"], "module": "oracle_cloud", "class": "OracleCloudAdapter"},
    {"name": "ibm_cloud", "domains": ["cloud.ibm.com"], "module": "ibm_cloud", "class": "IBMCloudAdapter"},
    {"name": "digitalocean", "domains": ["cloud.digitalocean.com"], "module": "digitalocean", "class": "DigitalOceanAdapter"},

    # ===== AI 平台（11 个）=====
    {"name": "qianwen", "domains": ["qianwen.com", "www.qianwen.com", "quark.sm.cn", "tongyi.aliyun.com"], "module": "qianwen", "class": "QianwenAdapter"},
    {"name": "openai", "domains": ["chat.openai.com", "platform.openai.com"], "module": "openai", "class": "OpenAIAdapter"},
    {"name": "claude", "domains": ["claude.ai"], "module": "claude", "class": "ClaudeAdapter"},
    {"name": "huggingface", "domains": ["huggingface.co"], "module": "huggingface", "class": "HuggingFaceAdapter"},
    {"name": "modelscope", "domains": ["modelscope.cn"], "module": "modelscope", "class": "ModelScopeAdapter"},
    {"name": "wenxin_yiyan", "domains": ["yiyan.baidu.com"], "module": "wenxin_yiyan", "class": "WenxinYiyanAdapter"},
    {"name": "gemini", "domains": ["gemini.google.com"], "module": "gemini", "class": "GeminiAdapter"},
    {"name": "copilot", "domains": ["copilot.microsoft.com"], "module": "copilot", "class": "CopilotAdapter"},
    {"name": "stability_ai", "domains": ["platform.stability.ai"], "module": "stability_ai", "class": "StabilityAIAdapter"},
    {"name": "midjourney", "domains": ["www.midjourney.com"], "module": "midjourney", "class": "MidjourneyAdapter"},
    {"name": "replicate", "domains": ["replicate.com"], "module": "replicate", "class": "ReplicateAdapter"},

    # ===== 社交媒体（10 个）=====
    {"name": "twitter", "domains": ["twitter.com", "x.com"], "module": "twitter", "class": "TwitterAdapter"},
    {"name": "linkedin", "domains": ["linkedin.com"], "module": "linkedin", "class": "LinkedInAdapter"},
    {"name": "weibo", "domains": ["weibo.com"], "module": "weibo", "class": "WeiboAdapter"},
    {"name": "zhihu", "domains": ["zhihu.com"], "module": "zhihu", "class": "ZhihuAdapter"},
    {"name": "bilibili", "domains": ["bilibili.com", "www.bilibili.com"], "module": "bilibili", "class": "BilibiliAdapter"},
    {"name": "douyin", "domains": ["douyin.com"], "module": "douyin", "class": "DouyinAdapter"},
    {"name": "facebook", "domains": ["facebook.com"], "module": "facebook", "class": "FacebookAdapter"},
    {"name": "instagram", "domains": ["instagram.com"], "module": "instagram", "class": "InstagramAdapter"},
    {"name": "tiktok", "domains": ["tiktok.com"], "module": "tiktok", "class": "TiktokAdapter"},
    {"name": "youtube", "domains": ["youtube.com"], "module": "youtube", "class": "YouTubeAdapter"},

    # ===== 电子邮件（5 个）=====
    {"name": "gmail", "domains": ["mail.google.com"], "module": "gmail", "class": "GmailAdapter"},
    {"name": "outlook", "domains": ["outlook.com", "outlook.office.com"], "module": "outlook", "class": "OutlookAdapter"},
    {"name": "qq_mail", "domains": ["mail.qq.com"], "module": "qq_mail", "class": "QQMailAdapter"},
    {"name": "163_mail", "domains": ["mail.163.com"], "module": "163_mail", "class": "Mail163Adapter"},
    {"name": "proton_mail", "domains": ["proton.me"], "module": "proton_mail", "class": "ProtonMailAdapter"},

    # ===== 文档协作（5 个）=====
    {"name": "google_docs", "domains": ["docs.google.com"], "module": "google_docs", "class": "GoogleDocsAdapter"},
    {"name": "notion", "domains": ["notion.so"], "module": "notion", "class": "NotionAdapter"},
    {"name": "yushi", "domains": ["yushi.com"], "module": "yushi", "class": "YushiAdapter"},
    {"name": "feishu_docs", "domains": ["feishu.cn"], "module": "feishu_docs", "class": "FeishuDocsAdapter"},
    {"name": "quip", "domains": ["quip.com"], "module": "quip", "class": "QuipAdapter"},

    # ===== 电商（5 个）=====
    {"name": "taobao", "domains": ["taobao.com", "www.taobao.com"], "module": "taobao", "class": "TaobaoAdapter"},
    {"name": "jd", "domains": ["jd.com", "www.jd.com"], "module": "jd", "class": "JDAdapter"},
    {"name": "amazon", "domains": ["amazon.com", "www.amazon.com"], "module": "amazon", "class": "AmazonAdapter"},
    {"name": "ebay", "domains": ["ebay.com"], "module": "ebay", "class": "eBayAdapter"},
    {"name": "pinduoduo", "domains": ["pinduoduo.com"], "module": "pinduoduo", "class": "PinduoduoAdapter"},

    # ===== 新闻资讯（5 个）=====
    {"name": "xinhua", "domains": ["xinhuanet.com"], "module": "xinhua", "class": "XinhuaAdapter"},
    {"name": "people", "domains": ["people.com.cn"], "module": "people", "class": "PeopleAdapter"},
    {"name": "bbc", "domains": ["bbc.com", "www.bbc.com"], "module": "bbc", "class": "BBCAdapter"},
    {"name": "cnn", "domains": ["cnn.com"], "module": "cnn", "class": "CNNAdapter"},
    {"name": "reuters", "domains": ["reuters.com"], "module": "reuters", "class": "ReutersAdapter"},

    # ===== 其他（10 个）=====
    {"name": "wikipedia", "domains": ["wikipedia.org", "en.wikipedia.org"], "module": "wikipedia", "class": "WikipediaAdapter"},
    {"name": "arxiv", "domains": ["arxiv.org"], "module": "arxiv", "class": "ArxivAdapter"},
    {"name": "pubmed", "domains": ["pubmed.ncbi.nlm.nih.gov"], "module": "pubmed", "class": "PubMedAdapter"},
    {"name": "cnki", "domains": ["cnki.net"], "module": "cnki", "class": "CNKIAdapter"},
    {"name": "github_gist", "domains": ["gist.github.com"], "module": "github_gist", "class": "GitHubGistAdapter"},
    {"name": "npm", "domains": ["npmjs.com"], "module": "npm", "class": "NPMAdapter"},
    {"name": "pypi", "domains": ["pypi.org"], "module": "pypi", "class": "PyPIAdapter"},
    {"name": "docker_hub", "domains": ["hub.docker.com"], "module": "docker_hub", "class": "DockerHubAdapter"},
    {"name": "kaggle", "domains": ["kaggle.com"], "module": "kaggle", "class": "KaggleAdapter"},
    {"name": "leetcode", "domains": ["leetcode.com", "leetcode.cn"], "module": "leetcode", "class": "LeetCodeAdapter"},
]


# ============================================================
# 通用适配器（用于未单独实现的网站）
# ============================================================

class GenericWebsiteAdapter(BaseWebsiteAdapter):
    """通用网站适配器（兜底）"""

    def __init__(self, name: str, domains: List[str], homepage: str):
        self._name = name
        self._domains = domains
        self._homepage = homepage

    def get_name(self) -> str:
        return self._name

    def get_domains(self) -> List[str]:
        return self._domains

    def get_homepage(self) -> str:
        return self._homepage

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        # 通用登录检测：检查页面是否有登录按钮
        try:
            login_btn = await cdp.evaluate(
                page_id,
                "document.querySelector('a[href*=login], button:contains(\"登录\"), button:contains(\"Sign in\") !== null"
            )
            return {
                "logged_in": not login_btn,
                "method": "generic",
            }
        except Exception:
            return {"logged_in": None, "method": "generic"}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        # 通用内容提取
        title = await cdp.evaluate(page_id, "document.title")
        text = await cdp.evaluate(page_id, "document.body.innerText")
        return {
            "type": "generic",
            "title": title,
            "text": text[:2000] if text else "",
            "extractor": "generic",
        }


# ============================================================
# Registry 主类
# ============================================================

class WebsiteAdapterRegistry:
    """网站适配器注册表"""

    def __init__(self):
        self._adapters: Dict[str, BaseWebsiteAdapter] = {}
        self._domain_index: Dict[str, str] = {}  # domain -> adapter name
        self._loaded = False

    def _ensure_loaded(self):
        """延迟加载所有适配器"""
        if self._loaded:
            return
        self._register_builtin_adapters()
        self._loaded = True

    def _register_builtin_adapters(self):
        """注册内置 80+ 适配器"""
        import sys
        import os

        # 获取当前文件所在目录
        adapters_dir = os.path.dirname(__file__)
        if adapters_dir not in sys.path:
            sys.path.insert(0, adapters_dir)

        for entry in WEBSITE_REGISTRY_DATA:
            name = entry["name"]
            module_name = entry["module"]
            class_name = entry["class"]
            domains = entry["domains"]

            # 尝试导入适配器类
            adapter = None
            try:
                mod = importlib.import_module(f"adapters.{module_name}", package="chrome_bridge")
                adapter_class = getattr(mod, class_name)
                adapter = adapter_class()
            except (ImportError, AttributeError) as e:
                # 导入失败，使用通用适配器
                homepage = f"https://{domains[0]}" if domains else ""
                adapter = GenericWebsiteAdapter(name, domains, homepage)
                logger.debug(f"适配器 {name} 导入失败，使用通用适配器: {e}")

            if adapter:
                self.register(adapter)
                # 索引域名
                for domain in domains:
                    self._domain_index[domain] = name

    def register(self, adapter: BaseWebsiteAdapter):
        """
        注册适配器

        Args:
            adapter: 适配器实例
        """
        name = adapter.get_name()
        self._adapters[name] = adapter

        # 更新域名索引
        for domain in adapter.get_domains():
            self._domain_index[domain] = name

        logger.debug(f"注册适配器: {name}")

    def unregister(self, name: str):
        """取消注册适配器"""
        if name in self._adapters:
            adapter = self._adapters[name]
            for domain in adapter.get_domains():
                self._domain_index.pop(domain, None)
            del self._adapters[name]

    def get_adapter(self, name: str) -> Optional[BaseWebsiteAdapter]:
        """
        根据名称获取适配器

        Args:
            name: 适配器名称

        Returns:
            适配器实例，未找到返回 None
        """
        self._ensure_loaded()
        return self._adapters.get(name)

    def find_adapter_for_url(self, url: str) -> Optional[BaseWebsiteAdapter]:
        """
        根据 URL 查找匹配的适配器

        Args:
            url: 目标 URL

        Returns:
            匹配的适配器，未找到返回 None
        """
        self._ensure_loaded()
        # 精确匹配域名
        for domain, adapter_name in self._domain_index.items():
            if domain in url:
                return self._adapters.get(adapter_name)
        return None

    def list_adapters(self) -> List[Dict[str, Any]]:
        """
        列出所有已注册的适配器

        Returns:
            适配器元信息列表
        """
        self._ensure_loaded()
        return [a.get_meta() for a in self._adapters.values()]

    def count(self) -> int:
        """获取已注册适配器数量"""
        self._ensure_loaded()
        return len(self._adapters)


# ============================================================
# 全局单例
# ============================================================

_registry_instance: Optional[WebsiteAdapterRegistry] = None


def get_adapter_registry() -> WebsiteAdapterRegistry:
    """获取全局适配器注册表实例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = WebsiteAdapterRegistry()
    return _registry_instance
