# scanner.py — 开源库多源扫描器

import re
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import asdict
import hashlib

from .scanner_models import (
    ScanSource, ScanTask, LibraryInfo, CandidateLibrary,
    CompareResult, CompareDimension, ReplacementDecision,
    generate_task_id,
)


logger = logging.getLogger(__name__)


# ============ 预置热点库 (离线兜底) ============

PRESET_HOT_LIBRARIES = {
    "pdf_parser": [
        LibraryInfo(
            name="PyPDF2",
            version="3.0.1",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/py-pdf/pypdf",
            description="Pure-Python library for PDF manipulation",
            language="Python",
            license="MIT",
            stars=5200,
            forks=890,
            categories=["pdf", "document"],
            tags=["pdf", "parser", "extraction"],
        ),
        LibraryInfo(
            name="pdfplumber",
            version="0.10.3",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/jsvine/pdfplumber",
            description="Plumb PDF for detailed information and extract data",
            language="Python",
            license="MIT",
            stars=4100,
            forks=420,
            categories=["pdf", "document"],
            tags=["pdf", "table", "extraction"],
        ),
    ],
    "markdown": [
        LibraryInfo(
            name="markdown-it-py",
            version="3.0.0",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/executablebooks/markdown-it-py",
            description="Python port of markdown-it markdown parser",
            language="Python",
            license="MIT",
            stars=3200,
            forks=280,
            categories=["markdown", "parser"],
            tags=["markdown", "parser", "commonmark"],
        ),
        LibraryInfo(
            name="mistune",
            version="2.0.5",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/lepture/mistune",
            description="A fast markdown parser with plugins support",
            language="Python",
            license="BSD-3-Clause",
            stars=2100,
            forks=190,
            categories=["markdown", "parser"],
            tags=["markdown", "fast", "plugins"],
        ),
    ],
    "async_http": [
        LibraryInfo(
            name="aiohttp",
            version="3.9.1",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/aio-libs/aiohttp",
            description="Async HTTP client/server framework",
            language="Python",
            license="Apache-2.0",
            stars=12300,
            forks=2100,
            categories=["http", "async"],
            tags=["async", "http", "client", "server"],
        ),
        LibraryInfo(
            name="httpx",
            version="0.25.2",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/encode/httpx",
            description="HTTPX - A fully featured HTTP client",
            language="Python",
            license="BSD-3-Clause",
            stars=10500,
            forks=780,
            categories=["http", "async"],
            tags=["http", "client", "async", "sync"],
        ),
    ],
    "config_yaml": [
        LibraryInfo(
            name="PyYAML",
            version="6.0.1",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/yaml/pyyaml",
            description="YAML parser and emitter for Python",
            language="Python",
            license="MIT",
            stars=1400,
            forks=280,
            categories=["yaml", "config"],
            tags=["yaml", "parser", "config"],
        ),
        LibraryInfo(
            name="ruamel.yaml",
            version="0.18.6",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/adrienben/rull",
            description="YAML parser with round-trip and comments preservation",
            language="Python",
            license="MIT",
            stars=1200,
            forks=130,
            categories=["yaml", "config"],
            tags=["yaml", "comments", "roundtrip"],
        ),
    ],
    "json_schema": [
        LibraryInfo(
            name="jsonschema",
            version="4.20.0",
            source=ScanSource.PRESET_HOT,
            url="https://github.com/Julian/jsonschema",
            description="Python JSON Schema draft-07/2019-09/2020-12 validator",
            language="Python",
            license="MIT",
            stars=3400,
            forks=320,
            categories=["json", "schema", "validation"],
            tags=["json", "schema", "validator", "draft7"],
        ),
    ],
}


# ============ 扫描结果缓存 ============

class ScanCache:
    """扫描结果缓存"""

    def __init__(self, cache_dir: Path = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = cache_dir
        self._memory_cache: Dict[str, tuple] = {}  # key -> (result, timestamp)
        self._cache_ttl = 3600  # 1小时

    def _get_cache_key(self, module: str, sources: List[ScanSource]) -> str:
        raw = f"{module}:{','.join(s.value for s in sorted(sources))}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, module: str, sources: List[ScanSource]) -> Optional[List[LibraryInfo]]:
        """获取缓存的扫描结果"""
        key = self._get_cache_key(module, sources)
        if key in self._memory_cache:
            result, timestamp = self._memory_cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            del self._memory_cache[key]

        # 尝试从文件缓存读取
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                age = time.time() - cache_file.stat().st_mtime
                if age < self._cache_ttl:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    result = [LibraryInfo.from_dict(d) for d in data]
                    self._memory_cache[key] = (result, time.time())
                    return result
                else:
                    cache_file.unlink()  # 删除过期缓存
            except Exception:
                pass

        return None

    def set(self, module: str, sources: List[ScanSource], result: List[LibraryInfo]):
        """设置扫描结果缓存"""
        key = self._get_cache_key(module, sources)
        self._memory_cache[key] = (result, time.time())

        # 写入文件缓存
        try:
            cache_file = self._cache_dir / f"{key}.json"
            cache_file.write_text(
                json.dumps([r.to_dict() for r in result], ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to write scan cache: {e}")

    def clear(self):
        """清空缓存"""
        self._memory_cache.clear()
        for f in self._cache_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass


# ============ 多源扫描器 ============

class MultiSourceScanner:
    """
    多源开源库扫描器

    扫描优先级:
    1. GitHub API (主)
    2. Gitee / 国内镜像 (备)
    3. 本地缓存
    4. 预置热点库 (离线兜底)
    """

    def __init__(self, cache: ScanCache = None):
        self._cache = cache or ScanCache()
        self._github_token: Optional[str] = None
        self._session = None

    def set_github_token(self, token: str):
        """设置GitHub Token (避免API限流)"""
        self._github_token = token

    async def _create_session(self):
        """创建HTTP会话"""
        if self._session is None:
            import aiohttp
            headers = {}
            if self._github_token:
                headers["Authorization"] = f"token {self._github_token}"
            self._session = aiohttp.ClientSession(headers=headers)

    async def scan_github(self, query: str, per_page: int = 5) -> List[LibraryInfo]:
        """从GitHub API扫描"""
        await self._create_session()
        results = []

        try:
            url = "https://api.github.com/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
            }

            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("items", []):
                        lib = LibraryInfo(
                            name=item.get("name", ""),
                            version=item.get("default_branch", "main"),
                            source=ScanSource.GITHUB,
                            url=item.get("html_url", ""),
                            description=item.get("description", ""),
                            language=item.get("language", "Python"),
                            license=item.get("license", {}).get("spdx_id", "Unknown"),
                            stars=item.get("stargazers_count", 0),
                            forks=item.get("forks_count", 0),
                            issues=item.get("open_issues_count", 0),
                            last_commit=item.get("pushed_at", ""),
                            homepage=item.get("homepage", ""),
                        )
                        results.append(lib)
                elif resp.status == 403:
                    logger.warning("GitHub API rate limit exceeded")
                else:
                    logger.warning(f"GitHub API error: {resp.status}")

        except Exception as e:
            logger.error(f"GitHub scan failed: {e}")

        return results

    async def scan_gitee(self, query: str, per_page: int = 5) -> List[LibraryInfo]:
        """从Gitee API扫描"""
        await self._create_session()
        results = []

        try:
            url = "https://gitee.com/api/v5/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "per_page": per_page,
            }

            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data:
                        lib = LibraryInfo(
                            name=item.get("name", ""),
                            version=item.get("default_branch", "master"),
                            source=ScanSource.Gitee,
                            url=item.get("html_url", ""),
                            description=item.get("description", ""),
                            language=item.get("language", "Python"),
                            license=item.get("license", "Unknown"),
                            stars=item.get("stargazers_count", 0),
                            forks=item.get("forks_count", 0),
                            issues=item.get("open_issues_count", 0),
                            last_commit=item.get("pushed_at", ""),
                            homepage=item.get("homepage", ""),
                        )
                        results.append(lib)
                else:
                    logger.warning(f"Gitee API error: {resp.status}")

        except Exception as e:
            logger.error(f"Gitee scan failed: {e}")

        return results

    def scan_preset(self, module_category: str) -> List[LibraryInfo]:
        """从预置热点库扫描"""
        # 精确匹配
        if module_category in PRESET_HOT_LIBRARIES:
            return PRESET_HOT_LIBRARIES[module_category].copy()

        # 模糊匹配
        results = []
        keywords = module_category.lower().split("_")
        for category, libs in PRESET_HOT_LIBRARIES.items():
            cat_words = category.lower().split("_")
            if any(k in cat_words for k in keywords):
                results.extend(libs)

        return results

    async def scan_all(
        self,
        module_name: str,
        module_category: str,
        custom_code_patterns: List[str] = None,
        sources: List[ScanSource] = None,
    ) -> ScanTask:
        """
        执行全源扫描

        Args:
            module_name: 模块名
            module_category: 模块分类 (用于匹配预置热点库)
            custom_code_patterns: 自研代码特征列表 (用于比对)
            sources: 指定扫描来源

        Returns:
            ScanTask: 扫描任务结果
        """
        if sources is None:
            sources = [ScanSource.GITHUB, ScanSource.Gitee, ScanSource.PRESET_HOT]

        task = ScanTask(
            id=generate_task_id(module_name),
            module_name=module_name,
            scan_sources=sources,
            status="running",
            started_at=int(time.time()),
        )

        all_candidates = []

        # 检查缓存
        cached = self._cache.get(module_name, sources)
        if cached:
            for lib in cached:
                candidate = self._create_candidate(lib, module_name, custom_code_patterns)
                if candidate:
                    all_candidates.append(candidate)

            task.candidates = all_candidates
            task.status = "completed"
            task.completed_at = int(time.time())
            return task

        # 多源扫描
        try:
            for source in sources:
                if source == ScanSource.GITHUB:
                    query = f"{module_category} language:Python stars:>100"
                    libs = await self.scan_github(query)
                    for lib in libs:
                        candidate = self._create_candidate(lib, module_name, custom_code_patterns)
                        if candidate:
                            all_candidates.append(candidate)

                elif source == ScanSource.Gitee:
                    query = module_category
                    libs = await self.scan_gitee(query)
                    for lib in libs:
                        candidate = self._create_candidate(lib, module_name, custom_code_patterns)
                        if candidate:
                            all_candidates.append(candidate)

                elif source == ScanSource.PRESET_HOT:
                    libs = self.scan_preset(module_category)
                    for lib in libs:
                        candidate = self._create_candidate(lib, module_name, custom_code_patterns)
                        if candidate:
                            all_candidates.append(candidate)

                elif source == ScanSource.LOCAL_CACHE:
                    # 本地缓存扫描
                    local_libs = await self._scan_local_cache(module_category)
                    for lib in local_libs:
                        candidate = self._create_candidate(lib, module_name, custom_code_patterns)
                        if candidate:
                            all_candidates.append(candidate)

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            logger.error(f"Scan failed for {module_name}: {e}")

        # 去重
        seen = set()
        unique_candidates = []
        for c in all_candidates:
            if c.library.name not in seen:
                seen.add(c.library.name)
                unique_candidates.append(c)

        # 排序 (按置信度)
        unique_candidates.sort(key=lambda c: c.confidence, reverse=True)

        task.candidates = unique_candidates
        task.status = "completed"
        task.completed_at = int(time.time())

        # 缓存结果
        self._cache.set(module_name, sources, [c.library for c in unique_candidates])

        return task

    async def _scan_local_cache(self, category: str) -> List[LibraryInfo]:
        """扫描本地缓存 (检查是否已有同类库安装)"""
        results = []

        # 检查site-packages中是否有相关库
        try:
            import site
            site_packages = site.getsitepackages()

            keywords = category.lower().replace("_", " ")
            for pkg_dir in site_packages:
                pkg_path = Path(pkg_dir)
                if not pkg_path.exists():
                    continue

                for pkg in pkg_path.iterdir():
                    if not pkg.is_dir():
                        continue
                    pkg_name = pkg.name.lower()
                    if any(k in pkg_name for k in keywords.split()):
                        # 尝试获取版本
                        version = "unknown"
                        try:
                            ver_file = pkg / "version.py"
                            if ver_file.exists():
                                version = ver_file.read_text().split("=")[1].strip().strip("'\"")
                        except Exception:
                            pass

                        lib = LibraryInfo(
                            name=pkg.name,
                            version=version,
                            source=ScanSource.LOCAL_CACHE,
                            url="",
                            description=f"Locally installed package: {pkg.name}",
                        )
                        results.append(lib)
        except Exception as e:
            logger.warning(f"Local cache scan failed: {e}")

        return results

    def _create_candidate(
        self,
        library: LibraryInfo,
        module_name: str,
        custom_code_patterns: List[str] = None,
    ) -> Optional[CandidateLibrary]:
        """创建候选库对象 (带比对结果)"""
        if custom_code_patterns is None:
            custom_code_patterns = self._analyze_custom_features(module_name)

        compare_results = self._compare_with_custom(library, module_name, custom_code_patterns)
        decision = self._make_decision(compare_results, library)
        adapter_template = self._generate_adapter_template(library, module_name)
        migration_guide = self._generate_migration_guide(library, module_name)

        # 计算置信度
        confidence = sum(r.oss_score * (1 if r.winner == "oss" else 0.3) for r in compare_results) / max(len(compare_results), 1)

        # 评估收益和风险
        benefits, risks = self._assess_benefits_risks(library, decision, compare_results)

        return CandidateLibrary(
            library=library,
            compare_results=compare_results,
            overall_recommendation=decision,
            adapter_template=adapter_template,
            migration_guide=migration_guide,
            confidence=confidence,
            benefits=benefits,
            risks=risks,
            estimated_effort_hours=self._estimate_effort(library, decision),
        )

    def _analyze_custom_features(self, module_name: str) -> List[str]:
        """分析自研代码特征"""
        features = []

        # 根据模块名推断功能
        feature_map = {
            "pdf": ["text_extraction", "table_extraction", "metadata_read"],
            "markdown": ["parse", "render", "toc_generation"],
            "http": ["request", "session", "retry", "timeout"],
            "json": ["parse", "validate", "schema"],
            "yaml": ["parse", "dump", "comments"],
            "database": ["query", "transaction", "pool"],
            "cache": ["get", "set", "expire", "evict"],
            "async": ["await", "gather", "sleep"],
        }

        for key, feats in feature_map.items():
            if key in module_name.lower():
                features.extend(feats)

        return features if features else ["basic_functionality"]

    def _compare_with_custom(
        self,
        library: LibraryInfo,
        module_name: str,
        custom_features: List[str],
    ) -> List[CompareResult]:
        """与自研实现比对"""
        results = []

        # 1. 功能覆盖
        feature_score = min(1.0, library.stars / 5000)  # Stars越高功能越完善
        results.append(CompareResult(
            dimension=CompareDimension.FEATURE_COVERAGE,
            custom_score=0.6,  # 自研通常只覆盖核心功能
            oss_score=feature_score,
            winner="oss" if feature_score > 0.7 else "tie",
            delta=abs(feature_score - 0.6),
            notes=f"Library stars: {library.stars}",
        ))

        # 2. RFC兼容性 (开源库通常更好)
        results.append(CompareResult(
            dimension=CompareDimension.RFC_COMPATIBILITY,
            custom_score=0.5,
            oss_score=0.8,
            winner="oss",
            delta=0.3,
            notes="开源库通常遵循标准",
        ))

        # 3. 内存占用 (自研通常更轻量)
        results.append(CompareResult(
            dimension=CompareDimension.MEMORY_FOOTPRINT,
            custom_score=0.9,
            oss_score=0.6,
            winner="custom",
            delta=0.3,
            notes="自研通常更轻量，无依赖",
        ))

        # 4. 协议合规
        license_ok = library.license in ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause"]
        results.append(CompareResult(
            dimension=CompareDimension.LICENSE_COMPLIANCE,
            custom_score=1.0,
            oss_score=1.0 if license_ok else 0.5,
            winner="tie" if license_ok else "custom",
            delta=0 if license_ok else 0.5,
            notes=f"License: {library.license}",
        ))

        # 5. 维护状态
        maintenance_score = 0.5
        if library.stars > 1000:
            maintenance_score = 0.9
        elif library.stars > 100:
            maintenance_score = 0.7
        results.append(CompareResult(
            dimension=CompareDimension.MAINTENANCE_STATUS,
            custom_score=0.8,  # 自研有团队维护
            oss_score=maintenance_score,
            winner="tie",
            delta=abs(maintenance_score - 0.8),
            notes=f"Stars: {library.stars}",
        ))

        # 6. 社区活跃度
        activity_score = min(1.0, (library.stars + library.forks * 2 + library.issues * 0.1) / 10000)
        results.append(CompareResult(
            dimension=CompareDimension.COMMUNITY活跃度,
            custom_score=0.4,  # 自研社区有限
            oss_score=activity_score,
            winner="oss" if activity_score > 0.5 else "custom",
            delta=abs(activity_score - 0.4),
            notes=f"Activity score: {activity_score:.2f}",
        ))

        return results

    def _make_decision(
        self,
        compare_results: List[CompareResult],
        library: LibraryInfo,
    ) -> ReplacementDecision:
        """根据比对结果做出决策"""
        oss_wins = sum(1 for r in compare_results if r.winner == "oss")
        custom_wins = sum(1 for r in compare_results if r.winner == "custom")

        # 得分计算
        oss_total = sum(r.oss_score for r in compare_results)
        custom_total = sum(r.custom_score for r in compare_results)

        # 决策逻辑
        if oss_wins >= 4 and oss_total > custom_total * 1.2:
            if library.stars > 1000:
                return ReplacementDecision.ADOPT
            else:
                return ReplacementDecision.WRAP_AND_ADOPT
        elif custom_wins >= 3 and custom_total > oss_total:
            return ReplacementDecision.KEEP_CUSTOM
        elif library.stars < 100:
            return ReplacementDecision.DEFER
        else:
            return ReplacementDecision.WRAP_AND_ADOPT

    def _generate_adapter_template(self, library: LibraryInfo, module_name: str) -> str:
        """生成适配器模板代码"""
        return f'''"""
{library.name} 适配器

自动生成的适配器代码，用于封装 {library.name}
保持原有接口不变，业务代码零改动
"""

from typing import Any, Optional

class {self._to_class_name(library.name)}Adapter:
    """
    {library.name} 适配器

    封装 {library.name} ({library.description[:50]}...)
    """

    def __init__(self, config: dict = None):
        self._config = config or {{}}
        self._instance = None

    def _get_instance(self):
        """延迟初始化"""
        if self._instance is None:
            import {library.name.lower().replace("-", "_")}
            self._instance = {library.name.lower().replace("-", "_")}
        return self._instance

    def extract_text(self, path: str) -> str:
        """提取文本 (原接口)"""
        return self._get_instance().extract(path)

    def extract_metadata(self, path: str) -> dict:
        """提取元数据 (原接口)"""
        return self._get_instance().get_metadata(path)

    # === 扩展接口 (可选) ===
    def batch_extract(self, paths: list) -> list:
        """批量提取"""
        return [self.extract_text(p) for p in paths]
'''

    def _generate_migration_guide(self, library: LibraryInfo, module_name: str) -> str:
        """生成迁移指南"""
        return f'''# 从 {{module_name}} 迁移到 {library.name}

## 概述
- 原模块: {{module_name}}
- 目标库: {library.name}
- 目标版本: {library.version}

## 迁移步骤

### 1. 安装依赖
```bash
pip install {library.name.lower().replace("-", "_")}
```

### 2. 替换引用
```python
# 旧
from {{module_name}} import PDFParser
parser = PDFParser()

# 新
from {{module_name}}_adapter import {self._to_class_name(library.name)}Adapter
parser = {self._to_class_name(library.name)}Adapter()
```

### 3. 适配接口
适配器已封装兼容接口，详见 adapter_template

### 4. 测试验证
建议使用原有测试用例进行回归测试

## 回滚方案
如需回滚，删除适配器层，恢复原有导入
'''

    def _assess_benefits_risks(
        self,
        library: LibraryInfo,
        decision: ReplacementDecision,
        compare_results: List[CompareResult],
    ) -> tuple:
        """评估收益和风险"""
        benefits = []
        risks = []

        if decision in [ReplacementDecision.ADOPT, ReplacementDecision.WRAP_AND_ADOPT]:
            benefits.append("减少自研维护成本")
            benefits.append("提升功能稳定性和覆盖")
            if library.stars > 5000:
                benefits.append("成熟社区支持")
            benefits.append("持续更新和Bug修复")

            risks.append("引入外部依赖")
            risks.append("可能增加包体积")
            if library.license != "MIT":
                risks.append(f"需遵守 {library.license} 协议")

        else:
            benefits.append("保持零外部依赖")
            benefits.append("完全可控")
            benefits.append("无协议风险")

            risks.append("维护成本高")
            risks.append("功能可能不如开源库完善")

        return benefits, risks

    def _estimate_effort(self, library: LibraryInfo, decision: ReplacementDecision) -> float:
        """预估工作量(小时)"""
        if decision == ReplacementDecision.KEEP_CUSTOM:
            return 0.0
        elif decision == ReplacementDecision.WRAP_AND_ADOPT:
            return 2.0  # 封装适配器
        elif decision == ReplacementDecision.ADOPT:
            return 8.0  # 直接替换
        else:
            return 1.0  # 评估

    def _to_class_name(self, name: str) -> str:
        """将库名转换为类名"""
        return "".join(word.capitalize() for word in re.split(r"[-_]", name))


# ============ 全局实例 ============

_scanner: Optional[MultiSourceScanner] = None


def get_scanner() -> MultiSourceScanner:
    """获取扫描器全局实例"""
    global _scanner
    if _scanner is None:
        _scanner = MultiSourceScanner()
    return _scanner
