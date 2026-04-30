#!/usr/bin/env python3
"""
独立适配器批量生成器（无需包导入）
======================================

根据内置列表，直接生成 80+ 个网站适配器文件。
每个适配器包含通用实现（登录检测 + 内容提取）。
"""

import os

ADAPTERS_DIR = os.path.dirname(os.path.abspath(__file__))

WEBSITES = [
    # 开发平台
    ("gitlab", "GitLabAdapter", ["gitlab.com"], "https://gitlab.com"),
    ("bitbucket", "BitbucketAdapter", ["bitbucket.org"], "https://bitbucket.org"),
    ("gitee", "GiteeAdapter", ["gitee.com"], "https://gitee.com"),
    ("coding", "CodingAdapter", ["coding.net"], "https://coding.net"),
    ("sourceforge", "SourceForgeAdapter", ["sourceforge.net"], "https://sourceforge.net"),
    ("codeberg", "CodebergAdapter", ["codeberg.org"], "https://codeberg.org"),
    ("azure_devops", "AzureDevOpsAdapter", ["dev.azure.com"], "https://dev.azure.com"),
    ("google_cloud_source", "GoogleCloudSourceAdapter", ["source.cloud.google.com"], "https://source.cloud.google.com"),
    ("aws_codecommit", "AWSCodeCommitAdapter", ["console.aws.amazon.com/codecommit"], "https://console.aws.amazon.com/codecommit"),
    # 技术社区
    ("reddit", "RedditAdapter", ["reddit.com", "old.reddit.com"], "https://reddit.com"),
    ("hackernews", "HackerNewsAdapter", ["news.ycombinator.com"], "https://news.ycombinator.com"),
    ("v2ex", "V2EXAdapter", ["v2ex.com"], "https://v2ex.com"),
    ("juejin", "JuejinAdapter", ["juejin.cn"], "https://juejin.cn"),
    ("devto", "DevToAdapter", ["dev.to"], "https://dev.to"),
    ("hashnode", "HashnodeAdapter", ["hashnode.com"], "https://hashnode.com"),
    ("lobsters", "LobstersAdapter", ["lobsters.rs"], "https://lobsters.rs"),
    ("programmers_stack", "ProgrammersStackAdapter", ["programmers.stackexchange.com"], "https://programmers.stackexchange.com"),
    ("codeproject", "CodeProjectAdapter", ["codeproject.com"], "https://codeproject.com"),
    # 云服务商
    ("aws", "AWSAdapter", ["aws.amazon.com", "console.aws.amazon.com"], "https://aws.amazon.com"),
    ("azure", "AzureAdapter", ["portal.azure.com"], "https://portal.azure.com"),
    ("gcp", "GCPAdapter", ["console.cloud.google.com"], "https://console.cloud.google.com"),
    ("aliyun", "AliyunAdapter", ["aliyun.com", "console.aliyun.com"], "https://aliyun.com"),
    ("tencent_cloud", "TencentCloudAdapter", ["cloud.tencent.com"], "https://cloud.tencent.com"),
    ("huawei_cloud", "HuaweiCloudAdapter", ["console.huaweicloud.com"], "https://console.huaweicloud.com"),
    ("baidu_cloud", "BaiduCloudAdapter", ["cloud.baidu.com"], "https://cloud.baidu.com"),
    ("oracle_cloud", "OracleCloudAdapter", ["cloud.oracle.com"], "https://cloud.oracle.com"),
    ("ibm_cloud", "IBMCloudAdapter", ["cloud.ibm.com"], "https://cloud.ibm.com"),
    ("digitalocean", "DigitalOceanAdapter", ["cloud.digitalocean.com"], "https://cloud.digitalocean.com"),
    # AI 平台
    ("openai", "OpenAIAdapter", ["chat.openai.com", "platform.openai.com"], "https://openai.com"),
    ("claude", "ClaudeAdapter", ["claude.ai"], "https://claude.ai"),
    ("huggingface", "HuggingFaceAdapter", ["huggingface.co"], "https://huggingface.co"),
    ("modelscope", "ModelScopeAdapter", ["modelscope.cn"], "https://modelscope.cn"),
    ("wenxin_yiyan", "WenxinYiyanAdapter", ["yiyan.baidu.com"], "https://yiyan.baidu.com"),
    ("gemini", "GeminiAdapter", ["gemini.google.com"], "https://gemini.google.com"),
    ("copilot", "CopilotAdapter", ["copilot.microsoft.com"], "https://copilot.microsoft.com"),
    ("stability_ai", "StabilityAIAdapter", ["platform.stability.ai"], "https://platform.stability.ai"),
    ("midjourney", "MidjourneyAdapter", ["www.midjourney.com"], "https://www.midjourney.com"),
    ("replicate", "ReplicateAdapter", ["replicate.com"], "https://replicate.com"),
    # 社交媒体
    ("twitter", "TwitterAdapter", ["twitter.com", "x.com"], "https://twitter.com"),
    ("linkedin", "LinkedInAdapter", ["linkedin.com"], "https://linkedin.com"),
    ("weibo", "WeiboAdapter", ["weibo.com"], "https://weibo.com"),
    ("zhihu", "ZhihuAdapter", ["zhihu.com"], "https://zhihu.com"),
    ("bilibili", "BilibiliAdapter", ["bilibili.com", "www.bilibili.com"], "https://bilibili.com"),
    ("douyin", "DouyinAdapter", ["douyin.com"], "https://douyin.com"),
    ("facebook", "FacebookAdapter", ["facebook.com"], "https://facebook.com"),
    ("instagram", "InstagramAdapter", ["instagram.com"], "https://instagram.com"),
    ("tiktok", "TiktokAdapter", ["tiktok.com"], "https://tiktok.com"),
    ("youtube", "YouTubeAdapter", ["youtube.com"], "https://youtube.com"),
    # 电子邮件
    ("gmail", "GmailAdapter", ["mail.google.com"], "https://mail.google.com"),
    ("outlook_mail", "OutlookMailAdapter", ["outlook.com", "outlook.office.com"], "https://outlook.com"),
    ("qq_mail", "QQMailAdapter", ["mail.qq.com"], "https://mail.qq.com"),
    ("163_mail", "Mail163Adapter", ["mail.163.com"], "https://mail.163.com"),
    ("proton_mail", "ProtonMailAdapter", ["proton.me"], "https://proton.me"),
    # 文档协作
    ("google_docs", "GoogleDocsAdapter", ["docs.google.com"], "https://docs.google.com"),
    ("notion", "NotionAdapter", ["notion.so"], "https://notion.so"),
    ("yushi", "YushiAdapter", ["yushi.com"], "https://yushi.com"),
    ("feishu_docs", "FeishuDocsAdapter", ["feishu.cn"], "https://feishu.cn"),
    ("quip", "QuipAdapter", ["quip.com"], "https://quip.com"),
    # 电商
    ("taobao", "TaobaoAdapter", ["taobao.com", "www.taobao.com"], "https://taobao.com"),
    ("jd", "JDAdapter", ["jd.com", "www.jd.com"], "https://jd.com"),
    ("amazon", "AmazonAdapter", ["amazon.com", "www.amazon.com"], "https://amazon.com"),
    ("ebay", "EBayAdapter", ["ebay.com"], "https://ebay.com"),
    ("pinduoduo", "PinduoduoAdapter", ["pinduoduo.com"], "https://pinduoduo.com"),
    # 新闻资讯
    ("xinhua", "XinhuaAdapter", ["xinhuanet.com"], "https://xinhuanet.com"),
    ("people", "PeopleAdapter", ["people.com.cn"], "https://people.com.cn"),
    ("bbc", "BBCAdapter", ["bbc.com", "www.bbc.com"], "https://bbc.com"),
    ("cnn", "CNNAdapter", ["cnn.com"], "https://cnn.com"),
    ("reuters", "ReutersAdapter", ["reuters.com"], "https://reuters.com"),
    # 其他
    ("wikipedia", "WikipediaAdapter", ["wikipedia.org", "en.wikipedia.org"], "https://wikipedia.org"),
    ("arxiv", "ArxivAdapter", ["arxiv.org"], "https://arxiv.org"),
    ("pubmed", "PubMedAdapter", ["pubmed.ncbi.nlm.nih.gov"], "https://pubmed.ncbi.nlm.nih.gov"),
    ("cnki", "CNKIAdapter", ["cnki.net"], "https://cnki.net"),
    ("github_gist", "GitHubGistAdapter", ["gist.github.com"], "https://gist.github.com"),
    ("npm", "NPMAdapter", ["npmjs.com"], "https://npmjs.com"),
    ("pypi", "PyPIAdapter", ["pypi.org"], "https://pypi.org"),
    ("docker_hub", "DockerHubAdapter", ["hub.docker.com"], "https://hub.docker.com"),
    ("kaggle", "KaggleAdapter", ["kaggle.com"], "https://kaggle.com"),
    ("leetcode", "LeetCodeAdapter", ["leetcode.com", "leetcode.cn"], "https://leetcode.com"),
]


TEMPLATE = '''\
"""
{name_title} Adapter - {name} 网站适配器
======================================{sep}

支持：
- 登录状态检测（通用：检查登录/登出按钮）
- 内容提取（通用：提取 title + body text）
- 会话复用：直接使用已登录的 Chrome
"""

from typing import Dict, Any
from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class {class_name}(BaseWebsiteAdapter):
    """"{name} 网站适配器（通用实现）"""""

    def get_name(self) -> str:
        return "{name}"

    def get_domains(self) -> list:
        return {domains}

    def get_homepage(self) -> str:
        return "{homepage}"

    def get_login_url(self) -> str:
        return None  # 通用适配器不指定登录 URL

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """通用登录检测：检查页面是否有登出/登录相关元素"""
        try:
            # 检测登出按钮（已登录标志）
            has_logout = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\\"logout\\"], a[href*=\\"sign-out\\"], a[href*=\\"sign_out\\"')"
            )
            if has_logout:
                return {{"logged_in": True, "method": "logout_button_check"}}

            # 检测登录按钮（未登录标志）
            has_login = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\\"login\\"], a[href*=\\"sign-in\\"], button:contains(\\"登录\\"), button:contains(\\"Sign in\\")')"
            )
            if has_login:
                return {{"logged_in": False, "method": "login_button_check"}}

            # 检测用户头像（已登录标志）
            has_avatar = await cdp.evaluate(
                page_id,
                "!!document.querySelector('.avatar, [class*=\\"avatar\\"], img[alt*=\\"profile\\"')"
            )
            return {{"logged_in": has_avatar, "method": "avatar_check"}}
        except Exception as e:
            return {{"logged_in": None, "error": str(e), "method": "generic"}}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """通用内容提取：提取 title + body text"""
        try:
            title = await cdp.evaluate(page_id, "document.title")
            text = await cdp.evaluate(page_id, "document.body.innerText?.slice(0, 3000) || ''")
            html_lang = await cdp.evaluate(page_id, "document.documentElement.lang || ''")
            return {{
                "type": "generic",
                "title": title,
                "text": text,
                "lang": html_lang,
                "extractor": "generic_{name}",
            }}
        except Exception as e:
            return {{"type": "generic", "error": str(e), "extractor": "generic_{name}"}}
'''


def main():
    generated = 0
    skipped = 0
    for (module, class_name, domains, homepage) in WEBSITES:
        filepath = os.path.join(ADAPTERS_DIR, f"{module}.py")
        if os.path.exists(filepath):
            print(f"⏭  跳过（已存在）: {module}.py")
            skipped += 1
            continue
        name = module
        name_title = module.replace("_", " ").title()
        sep = "=" * (len(class_name) + 6)
        code = TEMPLATE.format(
            name=name,
            name_title=name_title,
            class_name=class_name,
            domains=domains,
            homepage=homepage,
            sep=sep,
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ 生成: {module}.py")
        generated += 1
    print(f"\n📊 完成：生成 {generated} 个，跳过 {skipped} 个")


if __name__ == "__main__":
    main()
