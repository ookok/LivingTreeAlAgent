# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - 知识库集成
====================================

支持的知识库类型：
- 本地文件系统
- Git仓库
- Confluence
- Notion
- 语雀
- 自定义API

作者：Hermes Desktop Team
版本：1.0.0
"""

import os
import re
import subprocess
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field
import json

from .models import (
    SourceType, KnowledgeSource, SourceConfig,
    ConversionConfig
)


@dataclass
class DocumentInfo:
    """文档信息"""
    doc_id: str
    title: str
    path: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    modified_at: Optional[str] = None
    size: int = 0


class KnowledgeBaseConnector:
    """知识库连接器基类"""

    def __init__(self, source: KnowledgeSource):
        self.source = source

    def connect(self) -> bool:
        """连接知识库"""
        raise NotImplementedError

    def disconnect(self):
        """断开连接"""
        raise NotImplementedError

    def list_documents(self) -> List[DocumentInfo]:
        """列出文档"""
        raise NotImplementedError

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取文档"""
        raise NotImplementedError

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        raise NotImplementedError


class LocalFolderConnector(KnowledgeBaseConnector):
    """本地文件夹连接器"""

    def __init__(self, source: KnowledgeSource):
        super().__init__(source)
        self.folder_path = source.config.folder_path
        self.recursive = source.config.recursive
        self.file_patterns = source.config.file_patterns
        self.exclude_patterns = source.config.exclude_patterns

    def connect(self) -> bool:
        """连接（检查文件夹是否存在）"""
        return os.path.isdir(self.folder_path)

    def disconnect(self):
        """断开（无需操作）"""
        pass

    def list_documents(self) -> List[DocumentInfo]:
        """列出文件夹中的文档"""
        documents = []

        if not os.path.isdir(self.folder_path):
            return documents

        for root, dirs, files in os.walk(self.folder_path):
            # 检查是否应该跳过
            rel_path = os.path.relpath(root, self.folder_path)
            if not self.recursive and rel_path != '.':
                continue

            for file in files:
                if self._is_markdown_file(file):
                    file_path = os.path.join(root, file)
                    doc = self._create_document_info(file_path)
                    documents.append(doc)

        return documents

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取文档内容"""
        if os.path.exists(doc_id):
            return self._create_document_info(doc_id)
        return None

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        documents = self.list_documents()

        for i, doc in enumerate(documents):
            try:
                with open(doc.path, 'r', encoding='utf-8') as f:
                    doc.content = f.read()
            except Exception:
                doc.content = ""

            if progress_callback:
                progress_callback(i + 1, len(documents), doc.title)

        return documents

    def _is_markdown_file(self, filename: str) -> bool:
        """检查是否为Markdown文件"""
        md_extensions = ['.md', '.markdown', '.mdown', '.mkd', '.mkdn']
        return any(filename.lower().endswith(ext) for ext in md_extensions)

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除"""
        for pattern in self.exclude_patterns:
            if self._match_pattern(path, pattern):
                return True
        return False

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """简单的模式匹配"""
        pattern = pattern.replace('**/', '')
        pattern = pattern.replace('**', '*')
        return pattern in path

    def _create_document_info(self, file_path: str) -> DocumentInfo:
        """创建文档信息"""
        stat = os.stat(file_path)

        return DocumentInfo(
            doc_id=file_path,
            title=os.path.splitext(os.path.basename(file_path))[0],
            path=file_path,
            metadata={
                'extension': os.path.splitext(file_path)[1],
                'relative_path': os.path.relpath(file_path, self.folder_path),
            },
            modified_at=str(stat.st_mtime),
            size=stat.st_size,
        )


class GitRepoConnector(KnowledgeBaseConnector):
    """Git仓库连接器"""

    def __init__(self, source: KnowledgeSource):
        super().__init__(source)
        self.repo_url = source.config.repo_url
        self.branch = source.config.branch
        self.local_path = None

    def connect(self) -> bool:
        """克隆或更新仓库"""
        try:
            # 尝试使用gitpython
            import git

            repo_name = self.repo_url.split('/')[-1].replace('.git', '')
            self.local_path = os.path.join(os.path.expanduser('~'), '.md2doc_cache', repo_name)

            if os.path.exists(self.local_path):
                # 更新
                repo = git.Repo(self.local_path)
                origin = repo.remotes.origin
                origin.pull()
            else:
                # 克隆
                os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
                git.Repo.clone_from(self.repo_url, self.local_path, branch=self.branch)

            return True
        except ImportError:
            # 使用命令行git
            return self._connect_with_git()
        except Exception:
            return False

    def _connect_with_git(self) -> bool:
        """使用命令行git连接"""
        try:
            repo_name = self.repo_url.split('/')[-1].replace('.git', '')
            self.local_path = os.path.join(os.path.expanduser('~'), '.md2doc_cache', repo_name)

            if os.path.exists(self.local_path):
                subprocess.run(['git', 'pull'], cwd=self.local_path, check=True)
            else:
                os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
                subprocess.run(['git', 'clone', self.repo_url, self.local_path], check=True)

            return True
        except Exception:
            return False

    def disconnect(self):
        """断开（可选：清理本地副本）"""
        pass

    def list_documents(self) -> List[DocumentInfo]:
        """列出仓库中的文档"""
        documents = []

        if not self.local_path or not os.path.isdir(self.local_path):
            return documents

        for root, dirs, files in os.walk(self.local_path):
            # 跳过.git目录
            if '.git' in root:
                continue

            for file in files:
                if file.endswith('.md') or file.endswith('.markdown'):
                    file_path = os.path.join(root, file)
                    doc = DocumentInfo(
                        doc_id=file_path,
                        title=os.path.splitext(file)[0],
                        path=file_path,
                        metadata={
                            'repo': self.repo_url,
                            'branch': self.branch,
                        }
                    )
                    documents.append(doc)

        return documents

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取文档"""
        if os.path.exists(doc_id):
            try:
                with open(doc_id, 'r', encoding='utf-8') as f:
                    content = f.read()

                return DocumentInfo(
                    doc_id=doc_id,
                    title=os.path.splitext(os.path.basename(doc_id))[0],
                    path=doc_id,
                    content=content,
                )
            except Exception:
                pass
        return None

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        documents = self.list_documents()

        for i, doc in enumerate(documents):
            full_doc = self.get_document(doc.doc_id)
            if full_doc:
                documents[i] = full_doc

            if progress_callback:
                progress_callback(i + 1, len(documents), doc.title)

        return documents


class ConfluenceConnector(KnowledgeBaseConnector):
    """Confluence连接器"""

    def __init__(self, source: KnowledgeSource):
        super().__init__(source)
        self.base_url = source.config.base_url
        self.auth_token = source.config.auth_token

    def connect(self) -> bool:
        """连接Confluence"""
        # 简单的连接测试
        return bool(self.base_url and self.auth_token)

    def disconnect(self):
        """断开连接"""
        pass

    def list_documents(self) -> List[DocumentInfo]:
        """列出空间中的页面（需要atlassian-python-api库）"""
        documents = []

        try:
            from atlassian import Confluence

            confluence = Confluence(
                url=self.base_url,
                username=self.auth_token.split(':')[0] if ':' in self.auth_token else self.auth_token,
                password=self.auth_token.split(':')[1] if ':' in self.auth_token else '',
            )

            pages = confluence.get_all_pages_from_space(space='MARKDOWN', expand='body.storage')
            for page in pages:
                doc = DocumentInfo(
                    doc_id=str(page['id']),
                    title=page.get('title', ''),
                    path=f"{self.base_url}/pages/{page['id']}",
                    metadata={
                        'space': page.get('space', {}).get('key', ''),
                        'type': page.get('type', ''),
                    }
                )
                documents.append(doc)

        except ImportError:
            # 库未安装，使用模拟数据
            documents.append(DocumentInfo(
                doc_id='demo',
                title='示例文档（请安装atlassian-python-api）',
                path='',
            ))
        except Exception:
            pass

        return documents

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取页面内容"""
        try:
            from atlassian import Confluence

            confluence = Confluence(
                url=self.base_url,
                username=self.auth_token.split(':')[0] if ':' in self.auth_token else self.auth_token,
                password=self.auth_token.split(':')[1] if ':' in self.auth_token else '',
            )

            page = confluence.get_page_by_id(doc_id, expand='body.storage')
            if page:
                return DocumentInfo(
                    doc_id=doc_id,
                    title=page.get('title', ''),
                    path=f"{self.base_url}/pages/{doc_id}",
                    content=page.get('body', {}).get('storage', {}).get('value', ''),
                    metadata=page,
                )

        except ImportError:
            pass
        except Exception:
            pass

        return None

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        documents = self.list_documents()

        for i, doc in enumerate(documents):
            full_doc = self.get_document(doc.doc_id)
            if full_doc:
                documents[i] = full_doc

            if progress_callback:
                progress_callback(i + 1, len(documents), doc.title)

        return documents


class NotionConnector(KnowledgeBaseConnector):
    """Notion连接器"""

    def __init__(self, source: KnowledgeSource):
        super().__init__(source)
        self.auth_token = source.config.auth_token

    def connect(self) -> bool:
        """连接Notion"""
        return bool(self.auth_token)

    def disconnect(self):
        """断开连接"""
        pass

    def list_documents(self) -> List[DocumentInfo]:
        """列出数据库中的页面"""
        documents = []

        try:
            from notion_client import NotionClient

            client = NotionClient(auth_token=self.auth_token)

            # 搜索所有页面
            search_results = client.search(filter={'property': 'object', 'value': 'page'})

            for page in search_results.get('results', []):
                doc = DocumentInfo(
                    doc_id=page['id'],
                    title=self._get_page_title(page),
                    path=f"notion://{page['id']}",
                    metadata={'type': 'page'}
                )
                documents.append(doc)

        except ImportError:
            # 库未安装
            documents.append(DocumentInfo(
                doc_id='demo',
                title='示例文档（请安装notion-client）',
                path='',
            ))
        except Exception:
            pass

        return documents

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取页面内容"""
        try:
            from notion_client import NotionClient

            client = NotionClient(auth_token=self.auth_token)
            page = client.get_block(doc_id)

            return DocumentInfo(
                doc_id=doc_id,
                title=self._get_page_title(page),
                path=f"notion://{doc_id}",
                content=self._extract_block_content(page),
            )

        except ImportError:
            pass
        except Exception:
            pass

        return None

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        documents = self.list_documents()

        for i, doc in enumerate(documents):
            full_doc = self.get_document(doc.doc_id)
            if full_doc:
                documents[i] = full_doc

            if progress_callback:
                progress_callback(i + 1, len(documents), doc.title)

        return documents

    def _get_page_title(self, page: Dict) -> str:
        """获取页面标题"""
        try:
            properties = page.get('properties', {})
            for prop_name, prop_value in properties.items():
                if prop_value.get('type') == 'title':
                    return ''.join([t.get('plain_text', '') for t in prop_value.get('title', [])])
        except Exception:
            pass
        return 'Untitled'

    def _extract_block_content(self, block: Dict) -> str:
        """提取块内容"""
        content = []
        try:
            for child in block.get('children', []):
                content.append(child.get('paragraph', {}).get('rich_text', [{}])[0].get('plain_text', ''))
        except Exception:
            pass
        return '\n'.join(content)


class YuqueConnector(KnowledgeBaseConnector):
    """语雀连接器"""

    def __init__(self, source: KnowledgeSource):
        super().__init__(source)
        self.base_url = source.config.base_url or 'https://www.yuque.com/api/v2'
        self.auth_token = source.config.auth_token

    def connect(self) -> bool:
        """连接语雀"""
        return bool(self.auth_token)

    def disconnect(self):
        """断开连接"""
        pass

    def list_documents(self) -> List[DocumentInfo]:
        """列出知识库中的文档"""
        documents = []

        try:
            import requests

            headers = {'X-Auth-Token': self.auth_token}
            response = requests.get(
                f"{self.base_url}/repos",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                repos = response.json().get('data', [])
                for repo in repos:
                    docs = self._list_repo_docs(repo.get('namespace', ''))
                    documents.extend(docs)

        except ImportError:
            documents.append(DocumentInfo(
                doc_id='demo',
                title='示例文档（请安装requests）',
                path='',
            ))
        except Exception:
            pass

        return documents

    def _list_repo_docs(self, namespace: str) -> List[DocumentInfo]:
        """列出知识库中的文档"""
        docs = []

        try:
            import requests

            headers = {'X-Auth-Token': self.auth_token}
            response = requests.get(
                f"{self.base_url}/repos/{namespace}/docs",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json().get('data', [])
                for doc in data:
                    docs.append(DocumentInfo(
                        doc_id=str(doc.get('id', '')),
                        title=doc.get('title', ''),
                        path=f"yuque://{namespace}/{doc.get('slug', '')}",
                        metadata={
                            'namespace': namespace,
                            'slug': doc.get('slug', ''),
                        }
                    ))

        except Exception:
            pass

        return docs

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取文档"""
        # doc_id 格式: namespace/slug
        parts = doc_id.split('/')
        if len(parts) != 2:
            return None

        namespace, slug = parts

        try:
            import requests

            headers = {'X-Auth-Token': self.auth_token}
            response = requests.get(
                f"{self.base_url}/repos/{namespace}/docs/{slug}",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                doc = response.json().get('data', {})
                return DocumentInfo(
                    doc_id=doc_id,
                    title=doc.get('title', ''),
                    path=doc_id,
                    content=doc.get('body', ''),
                )

        except Exception:
            pass

        return None

    def sync_documents(self,
                      progress_callback: Optional[Callable] = None) -> List[DocumentInfo]:
        """同步文档"""
        documents = self.list_documents()

        for i, doc in enumerate(documents):
            full_doc = self.get_document(doc.doc_id)
            if full_doc:
                documents[i] = full_doc

            if progress_callback:
                progress_callback(i + 1, len(documents), doc.title)

        return documents


class KnowledgeBaseManager:
    """知识库管理器"""

    def __init__(self):
        self._connectors: Dict[str, KnowledgeBaseConnector] = {}
        self._sources: Dict[str, KnowledgeSource] = {}

    def register_source(self, source: KnowledgeSource) -> bool:
        """注册知识源"""
        try:
            connector = self._create_connector(source)
            if connector and connector.connect():
                self._connectors[source.source_id] = connector
                self._sources[source.source_id] = source
                source.is_connected = True
                return True
        except Exception:
            pass
        return False

    def unregister_source(self, source_id: str) -> bool:
        """注销知识源"""
        if source_id in self._connectors:
            self._connectors[source_id].disconnect()
            del self._connectors[source_id]

        if source_id in self._sources:
            del self._sources[source_id]

        return True

    def list_sources(self) -> List[KnowledgeSource]:
        """列出所有知识源"""
        return list(self._sources.values())

    def get_connector(self, source_id: str) -> Optional[KnowledgeBaseConnector]:
        """获取连接器"""
        return self._connectors.get(source_id)

    def sync_all(self,
                progress_callback: Optional[Callable] = None) -> Dict[str, List[DocumentInfo]]:
        """同步所有知识源"""
        results = {}

        for source_id, connector in self._connectors.items():
            try:
                docs = connector.sync_documents()
                results[source_id] = docs
            except Exception:
                results[source_id] = []

        return results

    def _create_connector(self, source: KnowledgeSource) -> Optional[KnowledgeBaseConnector]:
        """创建连接器"""
        connectors = {
            SourceType.LOCAL_FOLDER: LocalFolderConnector,
            SourceType.GIT_REPO: GitRepoConnector,
            SourceType.CONFLUENCE: ConfluenceConnector,
            SourceType.NOTION: NotionConnector,
            SourceType.YUQUE: YuqueConnector,
        }

        connector_class = connectors.get(source.source_type)
        if connector_class:
            return connector_class(source)

        return None


# ============================================================================
# 便捷函数
# ============================================================================

def create_local_source(folder_path: str,
                        recursive: bool = True,
                        include_patterns: Optional[List[str]] = None) -> KnowledgeSource:
    """创建本地文件夹知识源"""
    return KnowledgeSource(
        source_name=os.path.basename(folder_path),
        source_type=SourceType.LOCAL_FOLDER,
        config=SourceConfig(
            source_type=SourceType.LOCAL_FOLDER,
            folder_path=folder_path,
            recursive=recursive,
            include_patterns=include_patterns or ['*.md', '*.markdown'],
        )
    )


def create_git_source(repo_url: str,
                     branch: str = 'main') -> KnowledgeSource:
    """创建Git仓库知识源"""
    return KnowledgeSource(
        source_name=repo_url.split('/')[-1].replace('.git', ''),
        source_type=SourceType.GIT_REPO,
        config=SourceConfig(
            source_type=SourceType.GIT_REPO,
            repo_url=repo_url,
            branch=branch,
        )
    )


# ============================================================================
# 全局实例
# ============================================================================

_global_manager: Optional[KnowledgeBaseManager] = None


def get_knowledge_base_manager() -> KnowledgeBaseManager:
    """获取全局知识库管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = KnowledgeBaseManager()
    return _global_manager
