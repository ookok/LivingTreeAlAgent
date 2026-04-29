"""
URL智能分类器
"""

import re
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from .models import URLType, URLMetadata


class URLClassifier:
    """URL智能分类器"""
    
    # URL类型识别模式
    PATTERNS: Dict[URLType, List[str]] = {
        URLType.CODE_REPO: [
            r"github\.com/[\w-]+/[\w.-]+",
            r"gitlab\.com/[\w-]+/[\w.-]+",
            r"bitbucket\.org/[\w-]+/[\w.-]+",
            r"gitee\.com/[\w-]+/[\w.-]+",
            r"sourceforge\.net/projects/[\w-]+",
        ],
        URLType.PACKAGE_MANAGER: [
            r"npmjs\.com/package/[\w-]+",
            r"pypi\.org/(project|simple)/[\w-]+",
            r"rubygems\.org/gems/[\w-]+",
            r"pub\.dartlang\.org/packages/[\w-]+",
            r"crates\.io/crates/[\w-]+",
            r"repo\.maven.apache\.org/maven2",
            r"mvnrepository\.com/artifact",
            r"packagist\.org/packages/[\w-]+",
        ],
        URLType.DOCUMENTATION: [
            r"readthedocs\.io/[\w-]+",
            r"readthedocs\.org/[\w-]+",
            r"gitbook\.io/[\w-]+",
            r"docs\.[\w.-]+\.(io|com|org)",
            r"documentation\.[\w.-]+\.(io|com|org)",
        ],
        URLType.API_DOCS: [
            r"swagger\.io/[\w-]+",
            r"openapi\.spec\.json",
            r"api\.docs\.[\w.-]+",
            r"restfulapi\.net",
            r"api[\w]*\.(io|com|org)/[\w-]+",
        ],
        URLType.PAPER_DATABASE: [
            r"arxiv\.org/abs/[\d.]+",
            r"arxiv\.org/pdf/[\d.]+",
            r"arxiv\.org/(?:html|pdf)/[\d.]+",
            r"ieeexplore\.ieee\.org/document/\d+",
            r"dl\.acm\.org/doi/\d+[./]\d+",
            r"pubmed\.ncbi\.nlm\.nih\.gov/\d+",
            r"nature\.com/articles/\w+",
            r"science\.org/doi/\d+",
            r"dblp\.org/entry/\w+/\d+",
        ],
        URLType.ACADEMIC_JOURNAL: [
            r"journals\.aps\.org/\w+/\d+",
            r"pubs\.acs\.org/doi/\w+/\d+",
            r"wiley\.com/doi/\w+/\d+",
            r"springer\.com/\d+/\d+",
            r"elifesciences\.org/articles/\d+",
        ],
        URLType.PREPRINT: [
            r"biorxiv\.org/content/\w+/\d+",
            r"medrxiv\.org/content/\w+/\d+",
            r"chemrxiv\.org/articlex/\w+",
            r"preprints\.org/\w+/\d+",
        ],
        URLType.SOCIAL_MEDIA: [
            r"(twitter|x)\.com/[\w-]+",
            r"facebook\.com/[\w-]+",
            r"instagram\.com/[\w-]+",
            r"linkedin\.com/in/[\w-]+",
            r"reddit\.com/r/\w+",
        ],
        URLType.VIDEO_PLATFORM: [
            r"youtube\.com/watch\?v=[\w-]+",
            r"youtu\.be/[\w-]+",
            r"vimeo\.com/\d+",
            r"bilibili\.com/video/\w+",
            r"twitch\.tv/\w+",
        ],
        URLType.NEWS_MEDIA: [
            r"bbc\.com/news/\w+",
            r"cnn\.com/\d+/\d+/\w+",
            r"reuters\.com/article/\w+",
            r"apnews\.com/article/\w+",
            r"nytimes\.com/\d+/\d+/\w+",
        ],
        URLType.BLOG: [
            r"medium\.com/@[\w-]+",
            r"dev\.to/[\w-]+",
            r"blog\.[\w.-]+/[\w-]+",
            r"substack\.com/p/\w+",
        ],
    }
    
    # 域名到类型的直接映射
    DOMAIN_MAP: Dict[str, URLType] = {
        "github.com": URLType.CODE_REPO,
        "gitlab.com": URLType.CODE_REPO,
        "bitbucket.org": URLType.CODE_REPO,
        "gitee.com": URLType.CODE_REPO,
        "sourceforge.net": URLType.CODE_REPO,
        
        "npmjs.com": URLType.PACKAGE_MANAGER,
        "pypi.org": URLType.PACKAGE_MANAGER,
        "rubygems.org": URLType.PACKAGE_MANAGER,
        "pub.dev": URLType.PACKAGE_MANAGER,
        "crates.io": URLType.PACKAGE_MANAGER,
        "pub.dartlang.org": URLType.PACKAGE_MANAGER,
        
        "arxiv.org": URLType.PAPER_DATABASE,
        "ieeexplore.ieee.org": URLType.PAPER_DATABASE,
        "dl.acm.org": URLType.PAPER_DATABASE,
        "pubmed.ncbi.nlm.nih.gov": URLType.PAPER_DATABASE,
        
        "youtube.com": URLType.VIDEO_PLATFORM,
        "youtu.be": URLType.VIDEO_PLATFORM,
        "vimeo.com": URLType.VIDEO_PLATFORM,
        "bilibili.com": URLType.VIDEO_PLATFORM,
        
        "twitter.com": URLType.SOCIAL_MEDIA,
        "x.com": URLType.SOCIAL_MEDIA,
        "reddit.com": URLType.SOCIAL_MEDIA,
        
        "medium.com": URLType.BLOG,
        "dev.to": URLType.BLOG,
        "substack.com": URLType.BLOG,
        
        "huggingface.co": URLType.CODE_REPO,  # 模型仓库
        "replicate.com": URLType.CODE_REPO,    # 模型平台
        
        # 学术相关
        "nature.com": URLType.PAPER_DATABASE,
        "science.org": URLType.PAPER_DATABASE,
        "springer.com": URLType.ACADEMIC_JOURNAL,
        "wiley.com": URLType.ACADEMIC_JOURNAL,
        "elsevier.com": URLType.ACADEMIC_JOURNAL,
        "sciencedirect.com": URLType.ACADEMIC_JOURNAL,
        
        # Docker
        "hub.docker.com": URLType.PACKAGE_MANAGER,
        "docker.io": URLType.PACKAGE_MANAGER,
        
        # 文档站点
        "readthedocs.io": URLType.DOCUMENTATION,
        "readthedocs.org": URLType.DOCUMENTATION,
        "gitbook.io": URLType.DOCUMENTATION,
        
        # 云服务商
        "aws.amazon.com": URLType.CODE_REPO,
        "console.aws.amazon.com": URLType.CODE_REPO,
        "cloud.google.com": URLType.CODE_REPO,
        "azure.microsoft.com": URLType.CODE_REPO,
        
        # 模型相关
        "modelscope.cn": URLType.CODE_REPO,
        "modelscope.com": URLType.CODE_REPO,
        "ollama.ai": URLType.CODE_REPO,
        "groq.com": URLType.API_DOCS,
        "openai.com": URLType.API_DOCS,
        "anthropic.com": URLType.API_DOCS,
    }
    
    # GitHub相关提取
    GITHUB_PATTERN = re.compile(r"https?://(?:www\.)?github\.com/([^/]+)/([^/\s?#]+)")
    
    # npm相关提取
    NPM_PATTERN = re.compile(r"https?://(?:www\.)?npmjs\.com/package/([^/\s?#]+)")
    
    # PyPI相关提取
    PYPI_PATTERN = re.compile(r"https?://pypi\.org/(?:project|simple)/([^/\s?#]+)")
    
    # arXiv相关提取
    ARXIV_PATTERN = re.compile(r"https?://arxiv\.org/(?:abs|pdf|html)/(\d+\.\d+)")
    
    # Docker Hub相关提取
    DOCKER_PATTERN = re.compile(r"https?://hub\.docker\.com/(?:r/)?([^/\s?#]+)/([^/\s?#]+)")
    
    def classify(self, url: str) -> URLMetadata:
        """对URL进行分类"""
        metadata = URLMetadata(original_url=url)
        
        # 解析URL
        parsed = urlparse(url)
        metadata.domain = parsed.netloc.lower()
        metadata.path = parsed.path
        
        # 优先使用域名映射
        if metadata.domain in self.DOMAIN_MAP:
            metadata.url_type = self.DOMAIN_MAP[metadata.domain]
        else:
            # 使用正则模式匹配
            for url_type, patterns in self.PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, url, re.IGNORECASE):
                        metadata.url_type = url_type
                        break
                if metadata.url_type != URLType.UNKNOWN:
                    break
        
        # 提取特定类型的额外信息
        self._extract_github_info(url, metadata)
        self._extract_npm_info(url, metadata)
        self._extract_pypi_info(url, metadata)
        self._extract_arxiv_info(url, metadata)
        self._extract_docker_info(url, metadata)
        
        # 添加标签
        metadata.tags = self._generate_tags(metadata)
        
        return metadata
    
    def _extract_github_info(self, url: str, metadata: URLMetadata):
        """提取GitHub仓库信息"""
        match = self.GITHUB_PATTERN.search(url)
        if match:
            metadata.owner = match.group(1)
            metadata.repo = match.group(2).rstrip('.git')
            metadata.extra["github"] = {
                "full_name": f"{metadata.owner}/{metadata.repo}",
                "url": f"https://github.com/{metadata.owner}/{metadata.repo}",
            }
    
    def _extract_npm_info(self, url: str, metadata: URLMetadata):
        """提取npm包信息"""
        match = self.NPM_PATTERN.search(url)
        if match:
            metadata.package_name = match.group(1)
            metadata.extra["npm"] = {
                "package": metadata.package_name,
                "url": f"https://www.npmjs.com/package/{metadata.package_name}",
            }
    
    def _extract_pypi_info(self, url: str, metadata: URLMetadata):
        """提取PyPI包信息"""
        match = self.PYPI_PATTERN.search(url)
        if match:
            metadata.package_name = match.group(1)
            metadata.extra["pypi"] = {
                "package": metadata.package_name,
                "url": f"https://pypi.org/project/{metadata.package_name}",
            }
    
    def _extract_arxiv_info(self, url: str, metadata: URLMetadata):
        """提取arXiv论文信息"""
        match = self.ARXIV_PATTERN.search(url)
        if match:
            metadata.paper_id = match.group(1)
            metadata.extra["arxiv"] = {
                "paper_id": metadata.paper_id,
                "abs_url": f"https://arxiv.org/abs/{metadata.paper_id}",
                "pdf_url": f"https://arxiv.org/pdf/{metadata.paper_id}.pdf",
            }
    
    def _extract_docker_info(self, url: str, metadata: URLMetadata):
        """提取Docker镜像信息"""
        match = self.DOCKER_PATTERN.search(url)
        if match:
            namespace = match.group(1)
            image = match.group(2)
            metadata.extra["docker"] = {
                "namespace": namespace,
                "image": image,
                "pull_url": f"{namespace}/{image}",
            }
    
    def _generate_tags(self, metadata: URLMetadata) -> List[str]:
        """生成标签"""
        tags = []
        
        # 基于类型添加标签
        type_tags = {
            URLType.CODE_REPO: ["代码", "开源"],
            URLType.PACKAGE_MANAGER: ["包管理", "依赖"],
            URLType.DOCUMENTATION: ["文档", "教程"],
            URLType.API_DOCS: ["API", "开发者"],
            URLType.PAPER_DATABASE: ["学术", "论文"],
            URLType.ACADEMIC_JOURNAL: ["学术", "期刊"],
            URLType.PREPRINT: ["预印本", "学术"],
            URLType.SOCIAL_MEDIA: ["社交"],
            URLType.VIDEO_PLATFORM: ["视频", "教程"],
            URLType.NEWS_MEDIA: ["新闻"],
            URLType.BLOG: ["博客", "文章"],
        }
        tags.extend(type_tags.get(metadata.url_type, []))
        
        # 基于域名添加标签
        if "github" in metadata.domain:
            tags.append("GitHub")
        elif "gitlab" in metadata.domain:
            tags.append("GitLab")
        elif "gitee" in metadata.domain:
            tags.append("Gitee")
        elif "npm" in metadata.domain:
            tags.append("npm")
        elif "pypi" in metadata.domain:
            tags.append("PyPI")
        elif "arxiv" in metadata.domain:
            tags.append("arXiv")
        elif "bilibili" in metadata.domain:
            tags.append("B站")
        elif "youtube" in metadata.domain:
            tags.append("YouTube")
        
        return list(set(tags))
    
    def get_category_for_mirror(self, metadata: URLMetadata) -> Optional[str]:
        """根据URL类型获取对应的镜像类别"""
        # GitHub相关
        if "github" in metadata.domain:
            if metadata.owner and metadata.repo:
                return "github"
        
        # npm相关
        if "npmjs" in metadata.domain or metadata.extra.get("npm"):
            return "npm"
        
        # PyPI相关
        if "pypi" in metadata.domain or metadata.extra.get("pypi"):
            return "pypi"
        
        # Docker相关
        if "docker" in metadata.domain or metadata.extra.get("docker"):
            return "docker"
        
        # HuggingFace相关
        if "huggingface" in metadata.domain:
            return "huggingface"
        
        # Maven相关
        if "maven" in metadata.domain or "gradle" in metadata.domain:
            return "maven"
        
        # Go模块相关
        if "go.dev" in metadata.domain or "golang" in metadata.domain:
            return "go"
        
        # TensorFlow相关
        if "tensorflow" in metadata.domain:
            return "tensorflow"
        
        # Homebrew相关
        if "brew" in metadata.domain or "homebrew" in metadata.domain:
            return "brew"
        
        # arXiv论文相关
        if "arxiv" in metadata.domain:
            return "arxiv"
        
        return None
