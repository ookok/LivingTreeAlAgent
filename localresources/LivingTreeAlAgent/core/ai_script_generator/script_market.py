"""
Script Market - 脚本市场与分享系统
===================================

核心理念：共享智慧，集体创造

功能：
1. 脚本市场 - 浏览/搜索/安装脚本
2. 脚本分享 - 导出/导入/版本管理
3. 贡献者激励 - 积分/排行榜
4. 社区生态 - UGC内容

Author: Hermes Desktop Team
"""

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import logging

logger = logging.getLogger(__name__)


# ============= 数据模型 =============


@dataclass
class ScriptMetadata:
    """脚本元数据"""
    script_id: str
    name: str
    description: str
    author: str
    version: str = "1.0.0"
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    language: str = "python"
    dependencies: List[str] = field(default_factory=list)
    permissions_required: Set[str] = field(default_factory=set)
    safety_level: str = "safe"
    downloads: int = 0
    rating: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    author_id: str = ""


@dataclass
class ScriptPackage:
    """脚本包"""
    metadata: ScriptMetadata
    code: str
    tests: str = ""
    readme: str = ""
    license: str = "MIT"


@dataclass
class ContributorStats:
    """贡献者统计"""
    user_id: str
    scripts_published: int = 0
    total_downloads: int = 0
    average_rating: float = 0.0
    points: int = 0  # 贡献积分
    rank: str = "newcomer"  # newcomer/contributor/expert/master


# ============= 内置脚本库 =============


BUILTIN_SCRIPTS = [
    {
        'script_id': 'builtin_001',
        'name': 'GitHub镜像加速',
        'description': '自动将GitHub链接转换为国内镜像，支持fastgit、ghproxy等',
        'author': 'Hermes Team',
        'category': 'network',
        'tags': ['github', '镜像', '加速', '代理'],
        'permissions_required': ['network:internet'],
        'safety_level': 'safe',
        'downloads': 1523,
        'rating': 4.8,
        'code': '''
import re
from typing import Dict, Optional

class GitHubMirror:
    """GitHub镜像加速器"""

    MIRRORS = {
        'fastgit': 'https://hub.fastgit.xyz',
        'ghproxy': 'https://ghproxy.com',
        'gitclone': 'https://gitclone.com',
    }

    def __init__(self, preferred_mirror: str = 'fastgit'):
        self.preferred = preferred_mirror

    def convert(self, url: str) -> str:
        """转换GitHub URL到镜像"""
        if 'github.com' not in url:
            return url

        # 处理不同类型的URL
        patterns = [
            (r'https?://github\.com/([^/]+)/([^/]+)/archive/([^.]+\\.zip)',
             f'{self.MIRRORS[self.preferred]}/\\1/\\2/archive/\\3'),
            (r'https?://github\.com/([^/]+)/([^/]+)\\.git',
             f'{self.MIRRORS[self.preferred]}/\\1/\\2.git'),
            (r'https?://github\.com/([^/]+)/([^/]+)',
             f'{self.MIRRORS[self.preferred]}/\\1/\\2'),
        ]

        for pattern, replacement in patterns:
            new_url = re.sub(pattern, replacement, url)
            if new_url != url:
                return new_url

        return url

    def batch_convert(self, urls: List[str]) -> List[str]:
        """批量转换"""
        return [self.convert(url) for url in urls]

def main():
    mirror = GitHubMirror()

    test_urls = [
        'https://github.com/user/repo',
        'https://github.com/user/repo.git',
        'https://github.com/user/repo/archive/v1.0.zip',
    ]

    for url in test_urls:
        print(f"原始: {{url}}")
        print(f"转换: {{mirror.convert(url)}}")
        print()

if __name__ == '__main__':
    main()
'''
    },
    {
        'script_id': 'builtin_002',
        'name': 'PyPI镜像自动配置',
        'description': '一键配置pip国内镜像源，支持清华、阿里云、豆瓣源',
        'author': 'Hermes Team',
        'category': 'tool',
        'tags': ['pypi', 'pip', '镜像', '配置'],
        'permissions_required': ['file:read', 'file:write'],
        'safety_level': 'safe',
        'downloads': 2341,
        'rating': 4.9,
        'code': '''
import os
import platform
from pathlib import Path
from typing import Dict

class PyPIConfigurator:
    """PyPI镜像配置器"""

    MIRRORS = {
        'tsinghua': {
            'name': '清华镜像',
            'url': 'https://pypi.tuna.tsinghua.edu.cn/simple',
        },
        'aliyun': {
            'name': '阿里云镜像',
            'url': 'https://mirrors.aliyun.com/pypi/simple',
        },
        'douban': {
            'name': '豆瓣镜像',
            'url': 'https://pypi.doubanio.com/simple',
        },
        'official': {
            'name': '官方源',
            'url': 'https://pypi.org/simple',
        }
    }

    def __init__(self):
        self.system = platform.system()
        self.home = Path.home()

    def get_pip_config_path(self) -> Path:
        """获取pip配置文件路径"""
        if self.system == 'Windows':
            return self.home / 'pip' / 'pip.ini'
        else:
            return self.home / '.pip' / 'pip.conf'

    def configure(self, mirror_key: str = 'tsinghua') -> bool:
        """配置镜像"""
        if mirror_key not in self.MIRRORS:
            print(f"未知的镜像: {{mirror_key}}")
            return False

        mirror = self.MIRRORS[mirror_key]
        config_path = self.get_pip_config_path()

        # 确保目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入配置
        config_content = f"""[global]
index-url = {mirror['url']}
[install]
trusted-host = {mirror['url'].split('/')[2]}
"""

        try:
            config_path.write_text(config_content)
            print(f"✓ 配置成功: {{mirror['name']}}")
            print(f"  配置文件: {{config_path}}")
            return True
        except Exception as e:
            print(f"✗ 配置失败: {{e}}")
            return False

    def list_mirrors(self):
        """列出可用镜像"""
        print("可用镜像源:")
        for key, mirror in self.MIRRORS.items():
            print(f"  [{key}] {{mirror['name']}} - {{mirror['url']}}")

def main():
    configurator = PyPIConfigurator()

    print("PyPI镜像配置工具")
    print("=" * 40)

    configurator.list_mirrors()
    print()

    # 默认配置清华镜像
    configurator.configure('tsinghua')

if __name__ == '__main__':
    main()
'''
    },
    {
        'script_id': 'builtin_003',
        'name': '代码复杂度分析',
        'description': '分析Python代码的圈复杂度，提供优化建议',
        'author': 'Hermes Team',
        'category': 'analysis',
        'tags': ['代码分析', '复杂度', '质量'],
        'permissions_required': [],
        'safety_level': 'safe',
        'downloads': 876,
        'rating': 4.5,
        'code': '''
import ast
import sys
from collections import defaultdict
from typing import Dict, List, Set

class ComplexityAnalyzer:
    """代码复杂度分析器"""

    def __init__(self):
        self.functions: List[Dict] = []
        self.classes: List[Dict] = []

    def analyze_file(self, filepath: str) -> Dict:
        """分析文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.analyze_code(code)
        except Exception as e:
            return {'error': str(e)}

    def analyze_code(self, code: str) -> Dict:
        """分析代码"""
        try:
            tree = ast.parse(code)
            self._visit(tree)

            return {
                'total_functions': len(self.functions),
                'total_classes': len(self.classes),
                'functions': self.functions,
                'classes': self.classes,
                'summary': self._get_summary()
            }
        except SyntaxError as e:
            return {'error': f'语法错误: {e}'}

    def _visit(self, node: ast.AST, depth: int = 0):
        """遍历AST节点"""
        if isinstance(node, ast.FunctionDef):
            complexity = self._calculate_complexity(node)
            self.functions.append({
                'name': node.name,
                'line': node.lineno,
                'complexity': complexity,
                'params': len(node.args.args),
            })

        if isinstance(node, ast.ClassDef):
            self.classes.append({
                'name': node.name,
                'line': node.lineno,
                'methods': sum(1 for m in node.body if isinstance(m, ast.FunctionDef))
            })

        for child in ast.iter_child_nodes(node):
            self._visit(child, depth + 1)

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1  # 基础复杂度

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _get_summary(self) -> str:
        """获取摘要"""
        if not self.functions:
            return "未发现函数"

        complexities = [f['complexity'] for f in self.functions]
        avg = sum(complexities) / len(complexities)

        high = [f for f in self.functions if f['complexity'] > 10]

        summary = f"""
复杂度统计:
- 函数总数: {{len(self.functions)}}
- 平均复杂度: {{avg:.1f}}
- 高复杂度函数: {{len(high)}}
"""

        if high:
            summary += "\\n高复杂度函数 (>10):"
            for f in high:
                summary += f"\\n  - {{f['name']}} (行{{f['line']}}, 复杂度{{f['complexity']}})"

        return summary

def main():
    if len(sys.argv) < 2:
        print("用法: python complexity_analyzer.py <file.py>")
        return

    analyzer = ComplexityAnalyzer()
    result = analyzer.analyze_file(sys.argv[1])

    if 'error' in result:
        print(f"错误: {result['error']}")
        return

    print(f"分析结果:")
    print(f"  函数数量: {{result['total_functions']}}")
    print(f"  类数量: {{result['total_classes']}}")
    print(result['summary'])

if __name__ == '__main__':
    main()
'''
    },
    {
        'script_id': 'builtin_004',
        'name': '批量文件重命名',
        'description': '支持正则表达式批量重命名文件，预览模式确保安全',
        'author': 'Hermes Team',
        'category': 'tool',
        'tags': ['文件', '重命名', '批量'],
        'permissions_required': ['file:read', 'file:write'],
        'safety_level': 'caution',
        'downloads': 1234,
        'rating': 4.6,
        'code': '''
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

class BatchRenamer:
    """批量文件重命名器"""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.renames: List[Tuple[str, str]] = []
        self.preview_mode = True

    def add_rule(self, pattern: str, replacement: str, flags: int = 0):
        """添加重命名规则"""
        self.pattern = re.compile(pattern, flags)
        self.replacement = replacement

    def preview(self, files: List[str] = None) -> List[Tuple[str, str]]:
        """预览重命名结果"""
        if files is None:
            files = [f.name for f in self.directory.iterdir() if f.is_file()]

        self.renames = []
        for filename in files:
            if self.pattern.search(filename):
                new_name = self.pattern.sub(self.replacement, filename)
                if new_name != filename:
                    self.renames.append((filename, new_name))

        return self.renames

    def execute(self) -> int:
        """执行重命名"""
        if self.preview_mode:
            print("预览模式，请先调用 execute() 确认")
            return 0

        count = 0
        for old_name, new_name in self.renames:
            old_path = self.directory / old_name
            new_path = self.directory / new_name

            try:
                old_path.rename(new_path)
                print(f"✓ {{old_name}} → {{new_name}}")
                count += 1
            except Exception as e:
                print(f"✗ {{old_name}} 失败: {{e}}")

        return count

    def set_preview_mode(self, enabled: bool):
        """设置预览模式"""
        self.preview_mode = enabled

def main():
    if len(sys.argv) < 2:
        print("用法: python batch_rename.py <目录> [模式] [替换]")
        return

    directory = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else r'(.*)'
    replacement = sys.argv[3] if len(sys.argv) > 3 else r'\\1'

    renamer = BatchRenamer(directory)

    print(f"目录: {{directory}}")
    print(f"模式: {{pattern}} → {{replacement}}")
    print()

    # 预览
    renamer.add_rule(pattern, replacement)
    changes = renamer.preview()

    if not changes:
        print("没有文件匹配模式")
        return

    print(f"发现 {{len(changes)}} 个文件待重命名:")
    for old, new in changes:
        print(f"  {{old}} → {{new}}")
    print()

    # 执行
    confirm = input("确认执行? (y/n): ")
    if confirm.lower() == 'y':
        renamer.set_preview_mode(False)
        count = renamer.execute()
        print(f"\\n完成: {{count}} 个文件已重命名")

if __name__ == '__main__':
    main()
'''
    },
]


# ============= 脚本市场 =============


class ScriptMarket:
    """
    脚本市场

    功能：
    1. 脚本浏览与搜索
    2. 脚本安装与卸载
    3. 脚本分享
    4. 贡献者系统
    """

    def __init__(self, market_dir: str = "./data/script_market"):
        self.market_dir = Path(market_dir)
        self.market_dir.mkdir(parents=True, exist_ok=True)

        # 脚本目录
        self.scripts_dir = self.market_dir / "scripts"
        self.scripts_dir.mkdir(exist_ok=True)

        # 用户数据目录
        self.user_dir = self.market_dir / "users"
        self.user_dir.mkdir(exist_ok=True)

        # 内置脚本
        self._builtin_scripts = {s['script_id']: s for s in BUILTIN_SCRIPTS}

        # 已安装脚本
        self._installed: Dict[str, ScriptMetadata] = {}

        # 加载已安装脚本
        self._load_installed()

        logger.info(f"脚本市场初始化完成: {self.market_dir}")

    def _load_installed(self):
        """加载已安装脚本"""
        metadata_file = self.market_dir / "installed.json"

        if metadata_file.exists():
            try:
                data = json.loads(metadata_file.read_text())
                for script_data in data.values():
                    self._installed[script_data['script_id']] = ScriptMetadata(**script_data)
            except Exception as e:
                logger.error(f"加载已安装脚本失败: {e}")

    def _save_installed(self):
        """保存已安装脚本"""
        metadata_file = self.market_dir / "installed.json"

        try:
            data = {
                sid: sm.__dict__ for sid, sm in self._installed.items()
            }
            metadata_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"保存已安装脚本失败: {e}")

    def list_scripts(self, category: str = None, search: str = None) -> List[Dict]:
        """
        列出脚本

        Args:
            category: 分类筛选
            search: 搜索关键词

        Returns:
            List[Dict]: 脚本列表
        """
        scripts = []

        # 内置脚本
        for script_id, script in self._builtin_scripts.items():
            if category and script.get('category') != category:
                continue
            if search:
                if search.lower() not in script['name'].lower():
                    if search.lower() not in script['description'].lower():
                        continue

            scripts.append({
                'script_id': script_id,
                'name': script['name'],
                'description': script['description'],
                'author': script['author'],
                'category': script['category'],
                'tags': script['tags'],
                'downloads': script['downloads'],
                'rating': script['rating'],
                'safety_level': script['safety_level'],
                'is_builtin': True,
                'is_installed': script_id in self._installed,
            })

        # 已安装的自定义脚本
        for script_id, metadata in self._installed.items():
            if script_id in self._builtin_scripts:
                continue

            if category and metadata.category != category:
                continue
            if search:
                if search.lower() not in metadata.name.lower():
                    if search.lower() not in metadata.description.lower():
                        continue

            scripts.append({
                'script_id': script_id,
                'name': metadata.name,
                'description': metadata.description,
                'author': metadata.author,
                'category': metadata.category,
                'tags': metadata.tags,
                'downloads': metadata.downloads,
                'rating': metadata.rating,
                'safety_level': metadata.safety_level,
                'is_builtin': False,
                'is_installed': True,
            })

        return scripts

    def get_script(self, script_id: str) -> Optional[Dict]:
        """获取脚本详情"""
        # 内置脚本
        if script_id in self._builtin_scripts:
            script = self._builtin_scripts[script_id]
            return {
                **script,
                'is_builtin': True,
                'is_installed': script_id in self._installed,
            }

        # 已安装脚本
        if script_id in self._installed:
            metadata = self._installed[script_id]
            code_file = self.scripts_dir / f"{script_id}.py"

            if code_file.exists():
                return {
                    'script_id': metadata.script_id,
                    'name': metadata.name,
                    'description': metadata.description,
                    'author': metadata.author,
                    'code': code_file.read_text(encoding='utf-8'),
                    'category': metadata.category,
                    'tags': metadata.tags,
                    'permissions_required': list(metadata.permissions_required),
                    'safety_level': metadata.safety_level,
                    'is_builtin': False,
                    'is_installed': True,
                }

        return None

    def install_script(self, script_id: str) -> bool:
        """安装脚本"""
        if script_id in self._installed:
            logger.warning(f"脚本已安装: {script_id}")
            return True

        script = self.get_script(script_id)
        if not script:
            logger.error(f"脚本不存在: {script_id}")
            return False

        try:
            # 保存脚本代码
            if 'code' in script:
                code_file = self.scripts_dir / f"{script_id}.py"
                code_file.write_text(script['code'], encoding='utf-8')

            # 保存元数据
            metadata = ScriptMetadata(
                script_id=script_id,
                name=script['name'],
                description=script['description'],
                author=script.get('author', 'Unknown'),
                category=script.get('category', 'general'),
                tags=script.get('tags', []),
                permissions_required=set(script.get('permissions_required', [])),
                safety_level=script.get('safety_level', 'safe'),
            )
            self._installed[script_id] = metadata
            self._save_installed()

            logger.info(f"脚本安装成功: {script_id}")
            return True

        except Exception as e:
            logger.error(f"脚本安装失败: {script_id} - {e}")
            return False

    def uninstall_script(self, script_id: str) -> bool:
        """卸载脚本"""
        if script_id not in self._installed:
            logger.warning(f"脚本未安装: {script_id}")
            return False

        try:
            # 删除文件
            code_file = self.scripts_dir / f"{script_id}.py"
            if code_file.exists():
                code_file.unlink()

            # 移除元数据
            del self._installed[script_id]
            self._save_installed()

            logger.info(f"脚本卸载成功: {script_id}")
            return True

        except Exception as e:
            logger.error(f"脚本卸载失败: {script_id} - {e}")
            return False

    def publish_script(
        self,
        name: str,
        description: str,
        code: str,
        category: str = "general",
        tags: List[str] = None,
        author: str = "Anonymous"
    ) -> Optional[str]:
        """
        发布脚本到本地市场

        Args:
            name: 脚本名称
            description: 描述
            code: 代码
            category: 分类
            tags: 标签
            author: 作者

        Returns:
            script_id: 脚本ID
        """
        script_id = f"local_{uuid.uuid4().hex[:12]}"

        try:
            # 保存代码
            code_file = self.scripts_dir / f"{script_id}.py"
            code_file.write_text(code, encoding='utf-8')

            # 保存元数据
            metadata = ScriptMetadata(
                script_id=script_id,
                name=name,
                description=description,
                author=author,
                category=category,
                tags=tags or [],
                author_id=author,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self._installed[script_id] = metadata
            self._save_installed()

            logger.info(f"脚本发布成功: {script_id}")
            return script_id

        except Exception as e:
            logger.error(f"脚本发布失败: {e}")
            return None

    def export_script(self, script_id: str, export_path: str) -> bool:
        """导出脚本为压缩包"""
        script = self.get_script(script_id)
        if not script:
            return False

        try:
            export_file = Path(export_path)

            with zipfile.ZipFile(export_file, 'w') as zf:
                # 写入代码
                if 'code' in script:
                    zf.writestr(f"{script_id}.py", script['code'])

                # 写入元数据
                metadata = {
                    'script_id': script_id,
                    'name': script['name'],
                    'description': script['description'],
                    'author': script.get('author', 'Unknown'),
                    'category': script.get('category', 'general'),
                    'tags': script.get('tags', []),
                    'version': '1.0.0',
                    'exported_at': datetime.now().isoformat(),
                }
                zf.writestr('metadata.json', json.dumps(metadata, indent=2, ensure_ascii=False))

            logger.info(f"脚本导出成功: {export_file}")
            return True

        except Exception as e:
            logger.error(f"脚本导出失败: {e}")
            return False

    def import_script(self, import_path: str) -> Optional[str]:
        """从压缩包导入脚本"""
        import_file = Path(import_path)

        if not import_file.exists():
            return None

        try:
            with zipfile.ZipFile(import_file, 'r') as zf:
                # 读取元数据
                metadata_str = zf.read('metadata.json')
                metadata = json.loads(metadata_str)

                # 读取代码
                script_id = metadata['script_id']
                code = zf.read(f"{script_id}.py").decode('utf-8')

                # 发布脚本
                return self.publish_script(
                    name=metadata['name'],
                    description=metadata['description'],
                    code=code,
                    category=metadata.get('category', 'general'),
                    tags=metadata.get('tags', []),
                    author=metadata.get('author', 'Anonymous')
                )

        except Exception as e:
            logger.error(f"脚本导入失败: {e}")
            return None

    def get_categories(self) -> List[Dict]:
        """获取分类列表"""
        categories = {}

        for script in self._builtin_scripts.values():
            cat = script.get('category', 'general')
            if cat not in categories:
                categories[cat] = {'id': cat, 'name': cat, 'count': 0}
            categories[cat]['count'] += 1

        for metadata in self._installed.values():
            cat = metadata.category
            if cat not in categories:
                categories[cat] = {'id': cat, 'name': cat, 'count': 0}
            categories[cat]['count'] += 1

        return list(categories.values())


# 全局实例
_market_instance: Optional[ScriptMarket] = None


def get_script_market() -> ScriptMarket:
    """获取脚本市场全局实例"""
    global _market_instance
    if _market_instance is None:
        _market_instance = ScriptMarket()
    return _market_instance
