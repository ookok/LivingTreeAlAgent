"""
🌾 沃土播种 (Soil Sowing)
=========================

从博客/文档/URL提取知识，生成标准化知识条目

输入（文字/博客/代码） → 解析提炼 → 知识库条目（Markdown/JSON）
"""

import re
import json
import asyncio
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

import httpx

from .knowledge_incubator import KnowledgeEntry, KnowledgeType, KnowledgeBank


# ==================== 解析器接口 ====================

class ContentParser:
    """内容解析器基类"""

    async def parse(self, content: str, source_url: str = "") -> KnowledgeEntry:
        """解析内容并生成知识条目"""
        raise NotImplementedError


# ==================== Markdown解析器 ====================

class MarkdownParser(ContentParser):
    """Markdown文档解析器"""

    async def parse(self, content: str, source_url: str = "") -> KnowledgeEntry:
        """解析Markdown内容"""
        # 提取标题
        title = self._extract_title(content)

        # 提取元信息
        metadata = self._extract_metadata(content)

        # 提取代码块
        code_blocks = self._extract_code_blocks(content)

        # 提取标签
        tags = self._extract_tags(content, metadata)

        # 生成摘要
        summary = self._generate_summary(content)

        # 确定知识类型
        knowledge_type = self._determine_type(content, metadata)

        entry = KnowledgeEntry(
            id="",  # 让KnowledgeBank生成
            title=title,
            content_md=content,
            summary=summary,
            source_url=source_url,
            source_type="markdown",
            knowledge_type=knowledge_type,
            tags=tags,
            language=self._detect_language(code_blocks),
        )
        return entry

    def _extract_title(self, content: str) -> str:
        """提取标题"""
        # 尝试从第一行H1提取
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # 尝试从文件名提取（如果提供了）
        return "未命名文档"

    def _extract_metadata(self, content: str) -> dict:
        """提取元信息"""
        metadata = {}

        # 提取YAML frontmatter
        frontmatter_match = re.match(
            r'^---\s*\n(.*?)\n---\s*\n',
            content,
            re.DOTALL
        )
        if frontmatter_match:
            try:
                import yaml
                metadata = yaml.safe_load(frontmatter_match.group(1)) or {}
            except:
                pass

        # 提取常见元数据字段
        patterns = {
            "author": r'(?:author|作者)[:\s]+([^\n]+)',
            "date": r'(?:date|日期)[:\s]+([^\n]+)',
            "tags": r'(?:tags|标签)[:\s]+\[([^\]]+)\]',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()

        return metadata

    def _extract_code_blocks(self, content: str) -> list:
        """提取代码块"""
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        return [{"lang": lang, "code": code.strip()} for lang, code in matches]

    def _extract_tags(self, content: str, metadata: dict) -> list:
        """提取标签"""
        tags = []

        # 从元数据提取
        if "tags" in metadata:
            tag_str = metadata["tags"]
            if isinstance(tag_str, str):
                tags.extend([t.strip() for t in tag_str.replace("[", "").replace("]", "").split(",")])
            elif isinstance(tag_str, list):
                tags.extend(tag_str)

        # 从内容提取（#标签格式）
        hash_tags = re.findall(r'#([a-zA-Z_][a-zA-Z0-9_-]*)', content)
        tags.extend(hash_tags)

        # 从代码语言推断
        code_blocks = self._extract_code_blocks(content)
        for block in code_blocks:
            if block["lang"]:
                tags.append(block["lang"].lower())

        # 去重
        return list(set(tags))[:10]  # 最多10个标签

    def _detect_language(self, code_blocks: list) -> str:
        """检测主要编程语言"""
        lang_counts = {}
        for block in code_blocks:
            if block["lang"]:
                lang_counts[block["lang"]] = lang_counts.get(block["lang"], 0) + 1

        if lang_counts:
            return max(lang_counts, key=lang_counts.get)
        return ""

    def _generate_summary(self, content: str) -> str:
        """生成摘要（简化版本）"""
        # 移除frontmatter
        content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)

        # 移除代码块
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)

        # 移除标题
        content = re.sub(r'^#+\s+', '', content, flags=re.MULTILINE)

        # 移除链接
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

        # 获取前500字符
        summary = content.strip()[:500]

        if len(content) > 500:
            summary += "..."

        return summary

    def _determine_type(self, content: str, metadata: dict) -> str:
        """判断知识类型"""
        content_lower = content.lower()

        if "tutorial" in metadata or "教程" in content:
            return KnowledgeType.TUTORIAL.value
        elif "api" in content_lower or "reference" in content_lower:
            return KnowledgeType.API_REFERENCE.value
        elif "best practice" in content_lower or "最佳实践" in content:
            return KnowledgeType.BEST_PRACTICE.value
        elif content.count("```") > 5:
            return KnowledgeType.CODE_SNIPPET.value
        elif "?" in content and ("answer" in content_lower or "回答" in content):
            return KnowledgeType.QNA.value
        elif "doc" in metadata.get("source_type", ""):
            return KnowledgeType.DOCUMENTATION.value
        else:
            return KnowledgeType.ARTICLE.value


# ==================== URL解析器 ====================

class URLParser(ContentParser):
    """URL内容解析器"""

    def __init__(self):
        self.markdown_parser = MarkdownParser()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._client

    async def parse(self, url: str, source_url: str = "") -> KnowledgeEntry:
        """
        从URL获取并解析内容

        Args:
            url: 内容URL
            source_url: 来源URL（如果url是解析后的内容）

        Returns:
            KnowledgeEntry
        """
        if not source_url:
            source_url = url

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                # HTML -> Markdown
                content = self._html_to_markdown(response.text, url)
            else:
                content = response.text

            # 解析为知识条目
            entry = await self.markdown_parser.parse(content, source_url)

            # 从URL推断标签
            url_tags = self._extract_tags_from_url(url)
            entry.tags.extend(url_tags)
            entry.tags = list(set(entry.tags))[:10]

            return entry

        except Exception as e:
            raise ValueError(f"无法解析URL: {e}")

    def _html_to_markdown(self, html: str, base_url: str = "") -> str:
        """简单HTML转Markdown"""
        import re

        # 移除script和style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 提取标题
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "未命名"

        # 提取主要内容（简化版）
        content_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE)
        if content_match:
            content = content_match.group(1)
        else:
            # 尝试获取body
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
            content = body_match.group(1) if body_match else html

        # 转换基本标签
        content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n', content, flags=re.DOTALL | re.IGNORECASE)

        content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', content, flags=re.DOTALL | re.IGNORECASE)

        # 代码块
        content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>',
                         lambda m: f'```\n{self._unescape_html(m.group(1))}\n```',
                         content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', content, flags=re.DOTALL | re.IGNORECASE)

        # 链接
        content = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>',
                         r'[\2](\1)', content, flags=re.IGNORECASE)

        # 列表
        content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', content, flags=re.DOTALL | re.IGNORECASE)

        # 移除剩余HTML标签
        content = re.sub(r'<[^>]+>', '', content)

        # 转义字符
        content = self._unescape_html(content)

        # 清理空白
        content = re.sub(r'\n{3,}', '\n\n', content)

        return f"# {title}\n\n{content.strip()}"

    def _unescape_html(self, text: str) -> str:
        """反转义HTML实体"""
        replacements = {
            '&nbsp;': ' ',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&#39;': "'",
            '&apos;': "'",
        }
        for key, value in replacements.items():
            text = text.replace(key, value)
        return text

    def _extract_tags_from_url(self, url: str) -> list:
        """从URL提取标签"""
        tags = []

        # 从路径提取关键词
        path = url.lower()
        keywords = {
            "python": "python",
            "javascript": "javascript",
            "typescript": "typescript",
            "rust": "rust",
            "golang": "go",
            "java": "java",
            "react": "react",
            "vue": "vue",
            "api": "api",
            "database": "database",
            "ml": "machine-learning",
            "ai": "ai",
            "tutorial": "tutorial",
            "guide": "guide",
        }

        for keyword, tag in keywords.items():
            if keyword in path:
                tags.append(tag)

        return tags


# ==================== 代码库解析器 ====================

class CodebaseParser(ContentParser):
    """代码库解析器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def parse(self, content: str, source_url: str = "") -> KnowledgeEntry:
        """
        解析代码库README或代码文件

        Args:
            content: 代码文件内容或README
            source_url: 仓库URL

        Returns:
            KnowledgeEntry
        """
        # 检测语言
        language = self._detect_language_from_content(content)

        # 如果是README，分析结构
        if self._is_readme(content):
            return await self._parse_readme(content, source_url, language)

        # 否则作为代码片段处理
        return self._create_code_snippet_entry(content, source_url, language)

    def _detect_language_from_content(self, content: str) -> str:
        """从内容检测语言"""
        # 按文件头检测
        if content.startswith("#!"):
            shebang = content.split("\n")[0]
            if "python" in shebang:
                return "python"
            elif "node" in shebang:
                return "javascript"
            elif "bash" in shebang:
                return "bash"

        # 按关键词检测
        lang_patterns = {
            "python": [r'\bdef\s+\w+\(', r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import'],
            "javascript": [r'\bfunction\s+\w+\(', r'\bconst\s+\w+\s+=', r'\blet\s+\w+\s+='],
            "typescript": [r':\s*(string|number|boolean|any)\b', r'interface\s+\w+', r'type\s+\w+\s*='],
            "rust": [r'\bfn\s+\w+\(', r'\blet\s+mut\s+', r'\bimpl\s+\w+'],
            "go": [r'\bfunc\s+\w+\(', r'\bpackage\s+\w+', r'\bimport\s+\('],
            "java": [r'\bpublic\s+class\s+', r'\bprivate\s+\w+', r'\bSystem\.out\.print'],
        }

        for lang, patterns in lang_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    return lang

        return "unknown"

    def _is_readme(self, content: str) -> bool:
        """判断是否是README"""
        readme_indicators = [
            r'^#\s+\w+',  # Markdown标题
            r'\b##\s+',   # 二级标题
            r'\binstallation\b',
            r'\busage\b',
            r'\bexample\b',
            r'\b##\s+API\b',
        ]

        count = sum(1 for p in readme_indicators if re.search(p, content, re.IGNORECASE))
        return count >= 2

    async def _parse_readme(self, content: str, source_url: str, language: str) -> KnowledgeEntry:
        """解析README文档"""
        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "代码库文档"

        # 提取描述
        desc_match = re.search(r'#{1,2}\s+\w+[^\n]*\n\n([^#]+)', content, re.DOTALL)
        description = desc_match.group(1).strip()[:300] if desc_match else ""

        # 提取代码块
        code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)

        # 提取安装/使用说明
        install_section = self._extract_section(content, ['installation', '安装'])
        usage_section = self._extract_section(content, ['usage', '使用', 'example', '示例'])

        # 生成摘要
        summary = f"{description}\n\n**语言**: {language}\n**代码块数**: {len(code_blocks)}"
        if install_section:
            summary += f"\n\n**安装**: {install_section[:200]}..."
        if usage_section:
            summary += f"\n\n**使用**: {usage_section[:200]}..."

        # 提取标签
        tags = [language] if language != "unknown" else []
        tags.extend(self._extract_keywords(content))

        entry = KnowledgeEntry(
            id="",
            title=title,
            content_md=content,
            summary=summary[:1000],
            source_url=source_url,
            source_type="repository",
            knowledge_type=KnowledgeType.DOCUMENTATION.value,
            tags=tags,
            language=language,
        )

        return entry

    def _extract_section(self, content: str, keywords: list) -> str:
        """提取文档章节"""
        for keyword in keywords:
            # 匹配 ## keyword 或 # keyword
            pattern = rf'#{1,2}\s+{keyword}[^\n]*\n(.*?)(?=\n#{1,2}\s|\Z)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1).strip()
                # 移除代码块
                section = re.sub(r'```.*?```', '[代码]', section, flags=re.DOTALL)
                return section[:500]
        return ""

    def _extract_keywords(self, content: str) -> list:
        """提取关键词"""
        # 常见技术关键词
        keywords = [
            "api", "cli", "http", "websocket", "grpc", "rest",
            "database", "sql", "nosql", "redis", "mongodb",
            "cache", "queue", "async", "concurrent",
            "authentication", "jwt", "oauth",
            "docker", "kubernetes", "cloud",
            "test", "ci", "cd", "deployment",
        ]

        found = []
        content_lower = content.lower()
        for kw in keywords:
            if kw in content_lower:
                found.append(kw)

        return found[:5]

    def _create_code_snippet_entry(self, content: str, source_url: str, language: str) -> KnowledgeEntry:
        """创建代码片段条目"""
        # 取前200字符作为摘要
        lines = content.split("\n")[:20]
        preview = "\n".join(lines)

        return KnowledgeEntry(
            id="",
            title=f"{language} 代码片段",
            content_md=content,
            summary=f"```{language}\n{preview}\n```",
            source_url=source_url,
            source_type="code",
            knowledge_type=KnowledgeType.CODE_SNIPPET.value,
            tags=[language] if language != "unknown" else [],
            language=language,
        )


# ==================== 沃土播种器 ====================

class SoilSower:
    """
    沃土播种器

    统一入口，调度各种解析器
    """

    def __init__(self, knowledge_bank: KnowledgeBank, llm_client=None):
        self.knowledge_bank = knowledge_bank
        self.llm_client = llm_client

        # 初始化解析器
        self.markdown_parser = MarkdownParser()
        self.url_parser = URLParser()
        self.codebase_parser = CodebaseParser(llm_client)

    async def sow(
        self,
        content: str = "",
        source_url: str = "",
        content_type: str = "auto",
        progress_callback: Optional[Callable] = None,
    ) -> tuple[bool, str, KnowledgeEntry]:
        """
        执行播种

        Args:
            content: 内容文本（可选）
            source_url: 来源URL（可选）
            content_type: 内容类型 auto/markdown/url/code
            progress_callback: 进度回调

        Returns:
            (success, message, entry)
        """
        if progress_callback:
            await progress_callback("🌾 开始沃土播种...")

        try:
            # 确定内容类型
            if content_type == "auto":
                content_type = self._detect_content_type(content, source_url)

            # 选择解析器
            if content_type == "url" or (source_url and not content):
                if progress_callback:
                    await progress_callback("📥 获取URL内容...")
                entry = await self.url_parser.parse(source_url or content)
            elif content_type == "code":
                if progress_callback:
                    await progress_callback("🔍 分析代码...")
                entry = await self.codebase_parser.parse(content, source_url)
            else:
                # markdown
                if progress_callback:
                    await progress_callback("📝 解析文档...")
                entry = await self.markdown_parser.parse(content, source_url)

            # 使用LLM增强（如果有）
            if self.llm_client:
                if progress_callback:
                    await progress_callback("🧠 AI增强摘要...")
                entry = await self._enhance_with_llm(entry)

            # 保存
            if progress_callback:
                await progress_callback("💾 保存到知识库...")
            success, message = self.knowledge_bank.save_knowledge(entry)

            if success:
                if progress_callback:
                    await progress_callback(f"✅ {message}")
                return True, message, entry
            else:
                if progress_callback:
                    await progress_callback(f"⚠️ {message}")
                return False, message, entry

        except Exception as e:
            error_msg = f"播种失败: {e}"
            if progress_callback:
                await progress_callback(f"❌ {error_msg}")
            return False, error_msg, None

    def _detect_content_type(self, content: str, source_url: str) -> str:
        """检测内容类型"""
        if source_url:
            if source_url.startswith(("http://", "https://")):
                return "url"

        if not content:
            return "unknown"

        # 检测是否为代码
        code_indicators = [
            r'^\s*def\s+\w+\(',
            r'^\s*function\s+',
            r'^\s*class\s+\w+',
            r'^\s*package\s+\w+',
            r'^\s*import\s+',
            r'^\s*#include',
        ]

        code_score = sum(1 for p in code_indicators if re.search(p, content, re.MULTILINE))

        if code_score >= 2:
            return "code"

        # 默认为markdown
        return "markdown"

    async def _enhance_with_llm(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """使用LLM增强知识条目"""
        if not self.llm_client:
            return entry

        try:
            # 构建prompt
            prompt = f"""请分析以下文档，生成更好的摘要和标签。

标题: {entry.title}
当前摘要: {entry.summary}

内容预览:
{entry.content_md[:2000]}

请以JSON格式返回:
{{
  "improved_summary": "改进的摘要，100-300字",
  "tags": ["tag1", "tag2", "tag3"],
  "knowledge_type": "article/documentation/tutorial等"
}}
"""

            response = await self.llm_client.chat(prompt)

            # 解析响应
            import yaml
            try:
                result = yaml.safe_json.loads(response) or yaml.safe_load(response)
                if result:
                    if "improved_summary" in result:
                        entry.summary = result["improved_summary"]
                    if "tags" in result:
                        entry.tags = list(set(entry.tags + result["tags"]))[:10]
                    if "knowledge_type" in result:
                        entry.knowledge_type = result["knowledge_type"]
            except:
                pass

        except Exception:
            pass  # LLM增强失败不影响主流程

        return entry
