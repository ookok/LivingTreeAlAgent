"""
镜像源智能映射注册表
"""

import re
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass, field
from .models import MirrorSource, MirrorType, AccessStatus, URLType


@dataclass
class MirrorRule:
    """镜像规则"""
    name: str
    pattern: str  # URL匹配模式
    replace_pattern: str  # 替换模式
    extract_pattern: Optional[str] = None  # 提取模式
    mirror_type: MirrorType = MirrorType.OFFICIAL_MIRROR
    sync_frequency: str = "实时"
    location: str = "中国"
    is_official: bool = False
    # 动态URL生成函数
    url_generator: Optional[Callable] = None


class MirrorRegistry:
    """镜像源注册表"""
    
    def __init__(self):
        self._rules: List[MirrorRule] = []
        self._known_mirrors: Dict[str, List[MirrorSource]] = {}
        self._initialize_builtin_rules()
        self._initialize_builtin_mirrors()
    
    def _initialize_builtin_rules(self):
        """初始化内置镜像规则"""
        
        # GitHub镜像规则
        self.register_rule(MirrorRule(
            name="GitHub Gitee镜像",
            pattern=r"https?://github\.com/([^/]+)/([^/\s]+)/?",
            replace_pattern="https://gitee.com/mirrors/{repo}",
            extract_pattern=r"https?://github\.com/([^/]+)/([^/\s]+)",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="每日",
            location="中国",
            is_official=False,
        ))
        
        self.register_rule(MirrorRule(
            name="GitHub CNPMJS镜像",
            pattern=r"https?://github\.com/([^/]+)/([^/\s]+)(\.git)?",
            replace_pattern="https://github.com.cnpmjs.org/{owner}/{repo}",
            mirror_type=MirrorType.PROXY,
            sync_frequency="实时",
            location="中国",
        ))
        
        self.register_rule(MirrorRule(
            name="GitHub FastGit镜像",
            pattern=r"https?://github\.com/([^/]+)/([^/\s]+)(\.git)?",
            replace_pattern="https://hub.fastgit.xyz/{owner}/{repo}",
            mirror_type=MirrorType.PROXY,
            sync_frequency="实时",
            location="海外",
        ))
        
        # Docker镜像规则
        self.register_rule(MirrorRule(
            name="Docker Hub 阿里云镜像",
            pattern=r"https?://hub\.docker\.com/([^/\s]+)/([^/\s]+)",
            replace_pattern="https://registry.cn-hangzhou.aliyuncs.com/{namespace}/{image}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
        ))
        
        # PyPI镜像规则
        self.register_rule(MirrorRule(
            name="PyPI 清华镜像",
            pattern=r"https?://pypi\.org/(simple|project)/([^/\s]+)",
            replace_pattern="https://pypi.tuna.tsinghua.edu.cn/{path}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
            is_official=True,
        ))
        
        self.register_rule(MirrorRule(
            name="PyPI 阿里云镜像",
            pattern=r"https?://pypi\.org/(simple|project)/([^/\s]+)",
            replace_pattern="https://mirrors.aliyun.com/pypi/{path}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
        ))
        
        self.register_rule(MirrorRule(
            name="PyPI 腾讯云镜像",
            pattern=r"https?://pypi\.org/(simple|project)/([^/\s]+)",
            replace_pattern="https://mirrors.cloud.tencent.com/pypi/{path}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
        ))
        
        # npm镜像规则
        self.register_rule(MirrorRule(
            name="npm 淘宝镜像",
            pattern=r"https?://(?:www\.)?npmjs\.com/package/([^/\s]+)",
            replace_pattern="https://registry.npmmirror.com/{package}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
            is_official=True,
        ))
        
        # HuggingFace镜像规则 - 完整文件URL（/resolve/main/{filename}）
        # 注意：使用位置占位符 {0},{1},{2} 因为 apply_rule 支持 positional 替换
        self.register_rule(MirrorRule(
            name="HuggingFace 镜像站",
            pattern=r"https?://huggingface\.co/([^/\s]+)/([^/\s]+)/resolve/main/([^/\s]+)",
            replace_pattern="https://hf-mirror.com/{0}/{1}/resolve/main/{2}",
            mirror_type=MirrorType.CONTENT_MIRROR,
            sync_frequency="每日",
            location="中国",
        ))
        
        # arXiv镜像规则
        self.register_rule(MirrorRule(
            name="arXiv 论文镜像",
            pattern=r"https?://arxiv\.org/abs/([0-9.]+)",
            replace_pattern="https://ar5iv.org/html/{paper_id}",
            mirror_type=MirrorType.CONTENT_MIRROR,
            sync_frequency="每周",
            location="中国",
        ))
        
        # Pypi packages 镜像
        self.register_rule(MirrorRule(
            name="PyPI 中国科技大学镜像",
            pattern=r"https?://pypi\.org/(simple|project)/([^/\s]+)",
            replace_pattern="https://mirrors.ustc.edu.cn/pypi/{path}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="实时",
            location="中国",
            is_official=True,
        ))
        
        # Conda镜像规则
        self.register_rule(MirrorRule(
            name="Conda 清华镜像",
            pattern=r"https?://(?:www\.)?anaconda\.org/([^/\s]+)/([^/\s]+)",
            replace_pattern="https://mirrors.tuna.tsinghua.edu.cn/anaconda/{path}",
            mirror_type=MirrorType.OFFICIAL_MIRROR,
            sync_frequency="每日",
            location="中国",
        ))
    
    def _initialize_builtin_mirrors(self):
        """初始化内置镜像源"""
        
        # GitHub镜像
        self._known_mirrors["github"] = [
            MirrorSource(
                name="Gitee镜像",
                url="https://gitee.com/mirrors",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=85,
                reliability_score=90,
                sync_frequency="每日",
                location="中国",
                is_official=False,
            ),
            MirrorSource(
                name="GitHub CNPMJS",
                url="https://github.com.cnpmjs.org",
                mirror_type=MirrorType.PROXY,
                speed_score=75,
                reliability_score=80,
                sync_frequency="实时",
                location="中国",
            ),
            MirrorSource(
                name="FastGit",
                url="https://hub.fastgit.xyz",
                mirror_type=MirrorType.PROXY,
                speed_score=70,
                reliability_score=75,
                sync_frequency="实时",
                location="海外",
            ),
        ]
        
        # Docker镜像
        self._known_mirrors["docker"] = [
            MirrorSource(
                name="阿里云容器镜像",
                url="https://registry.cn-hangzhou.aliyuncs.com",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=90,
                reliability_score=95,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
            MirrorSource(
                name="DaoCloud镜像",
                url="https://docker.m.daocloud.io",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=85,
                reliability_score=90,
                sync_frequency="实时",
                location="中国",
            ),
        ]
        
        # PyPI镜像
        self._known_mirrors["pypi"] = [
            MirrorSource(
                name="清华PyPI镜像",
                url="https://pypi.tuna.tsinghua.edu.cn",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=95,
                reliability_score=98,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
            MirrorSource(
                name="阿里云PyPI镜像",
                url="https://mirrors.aliyun.com/pypi",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=90,
                reliability_score=95,
                sync_frequency="实时",
                location="中国",
            ),
            MirrorSource(
                name="腾讯云PyPI镜像",
                url="https://mirrors.cloud.tencent.com/pypi",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=88,
                reliability_score=92,
                sync_frequency="实时",
                location="中国",
            ),
            MirrorSource(
                name="中科大PyPI镜像",
                url="https://mirrors.ustc.edu.cn/pypi",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=85,
                reliability_score=90,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
        ]
        
        # npm镜像
        self._known_mirrors["npm"] = [
            MirrorSource(
                name="淘宝npm镜像",
                url="https://registry.npmmirror.com",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=92,
                reliability_score=95,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
            MirrorSource(
                name="腾讯npm镜像",
                url="https://mirrors.tencent.com/npm",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=88,
                reliability_score=92,
                sync_frequency="实时",
                location="中国",
            ),
        ]
        
        # HuggingFace镜像
        self._known_mirrors["huggingface"] = [
            MirrorSource(
                name="HuggingFace国内镜像",
                url="https://hf-mirror.com",
                mirror_type=MirrorType.CONTENT_MIRROR,
                speed_score=85,
                reliability_score=88,
                sync_frequency="每日",
                location="中国",
            ),
        ]
        
        # Google/Maven镜像
        self._known_mirrors["maven"] = [
            MirrorSource(
                name="阿里云Maven镜像",
                url="https://maven.aliyun.com/repository/public",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=90,
                reliability_score=95,
                sync_frequency="实时",
                location="中国",
            ),
            MirrorSource(
                name="腾讯云Maven镜像",
                url="https://mirrors.cloud.tencent.com/maven2",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=85,
                reliability_score=90,
                sync_frequency="实时",
                location="中国",
            ),
        ]
        
        # Go模块镜像
        self._known_mirrors["go"] = [
            MirrorSource(
                name="GOPROXY.CN",
                url="https://goproxy.cn",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=95,
                reliability_score=98,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
            MirrorSource(
                name="GOMIRROR",
                url="https://goproxy.io",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=88,
                reliability_score=92,
                sync_frequency="实时",
                location="海外",
            ),
        ]
        
        # TensorFlow/官方模型镜像
        self._known_mirrors["tensorflow"] = [
            MirrorSource(
                name="TensorFlow国内下载",
                url="https://download.tensorflow.cn",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=90,
                reliability_score=95,
                sync_frequency="实时",
                location="中国",
                is_official=True,
            ),
        ]
        
        # Homebrew镜像
        self._known_mirrors["brew"] = [
            MirrorSource(
                name="清华Homebrew镜像",
                url="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=85,
                reliability_score=90,
                sync_frequency="每日",
                location="中国",
                is_official=True,
            ),
            MirrorSource(
                name="中科大Homebrew镜像",
                url="https://mirrors.ustc.edu.cn/homebrew-bottles",
                mirror_type=MirrorType.OFFICIAL_MIRROR,
                speed_score=88,
                reliability_score=92,
                sync_frequency="每日",
                location="中国",
                is_official=True,
            ),
        ]
    
    def register_rule(self, rule: MirrorRule):
        """注册镜像规则"""
        self._rules.append(rule)
    
    def register_mirror(self, category: str, mirror: MirrorSource):
        """注册镜像源"""
        if category not in self._known_mirrors:
            self._known_mirrors[category] = []
        self._known_mirrors[category].append(mirror)
    
    def find_rules(self, url: str) -> List[MirrorRule]:
        """查找匹配的镜像规则"""
        matched = []
        for rule in self._rules:
            if re.search(rule.pattern, url, re.IGNORECASE):
                matched.append(rule)
        return matched
    
    def get_mirrors(self, category: str) -> List[MirrorSource]:
        """获取指定类别的镜像源"""
        return self._known_mirrors.get(category, [])
    
    def apply_rule(self, rule: MirrorRule, url: str) -> Optional[str]:
        """应用镜像规则转换URL"""
        match = re.search(rule.pattern, url, re.IGNORECASE)
        if not match:
            return None
        
        groups = match.groups()
        result = rule.replace_pattern
        
        # 替换占位符
        for i, group in enumerate(groups):
            result = result.replace(f"{{{i}}}", group or "")
        
        # 替换命名组
        if rule.extract_pattern:
            named_groups = re.search(rule.extract_pattern, url, re.IGNORECASE)
            if named_groups:
                for name, value in named_groups.groupdict().items():
                    if value:
                        result = result.replace(f"{{{name}}}", value)
        
        # 替换通用占位符
        if "{owner}" in result and len(groups) >= 1:
            result = result.replace("{owner}", groups[0])
        if "{repo}" in result and len(groups) >= 2:
            result = result.replace("{repo}", groups[1])
        if "{namespace}" in result and len(groups) >= 1:
            result = result.replace("{namespace}", groups[0])
        if "{image}" in result and len(groups) >= 2:
            result = result.replace("{image}", groups[1])
        if "{package}" in result and len(groups) >= 1:
            result = result.replace("{package}", groups[1] if len(groups) > 1 else groups[0])
        if "{paper_id}" in result and len(groups) >= 1:
            result = result.replace("{paper_id}", groups[0])
        
        # 替换路径占位符
        if "{path}" in result:
            path_match = re.search(r"pypi\.org/(.+)", url)
            if path_match:
                result = result.replace("{path}", path_match.group(1))
        
        return result
    
    def get_all_categories(self) -> List[str]:
        """获取所有镜像类别"""
        return list(self._known_mirrors.keys())
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total_rules = len(self._rules)
        total_mirrors = sum(len(m) for m in self._known_mirrors.values())
        return {
            "total_rules": total_rules,
            "total_mirrors": total_mirrors,
            "categories": len(self._known_mirrors),
            "by_category": {k: len(v) for k, v in self._known_mirrors.items()},
        }
