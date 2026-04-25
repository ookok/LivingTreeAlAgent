"""
Surface Matcher - 表层技术栈匹配引擎
比较编程语言、框架、依赖、文件结构等表层特征
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from project_analyzer import ProjectData


@dataclass
class MatchInsight:
    """匹配洞察"""
    category: str
    status: str  # 'match', 'partial', 'mismatch'
    message: str
    score_contribution: float = 0.0


@dataclass
class SurfaceMatchResult:
    """表层匹配结果"""
    score: float  # 0-100
    max_score: float = 100.0
    insights: List[MatchInsight] = field(default_factory=list)
    
    # 详细对比
    language_match: float = 0.0
    framework_match: float = 0.0
    database_match: float = 0.0
    dependency_overlap: float = 0.0
    structure_similarity: float = 0.0


class SurfaceMatcher:
    """表层技术栈匹配器"""
    
    # 权重配置
    WEIGHTS = {
        'language': 30,      # 编程语言
        'framework': 25,     # 框架
        'database': 15,     # 数据库
        'dependency': 20,    # 依赖重叠
        'structure': 10,    # 文件结构
    }
    
    # 语言相似度矩阵 (手动定义相似语言)
    LANGUAGE_FAMILIES = {
        'Python': {'Python', 'Python 3', '蟒蛇'},
        'JavaScript': {'JavaScript', 'TypeScript', 'JS', 'TS'},
        'Java': {'Java', 'Kotlin', 'Scala'},
        'Web': {'HTML', 'CSS', 'JavaScript', 'TypeScript'},
        'Qt': {'QML', 'Qt UI', 'C++'},
        'ML': {'Python', 'C++', 'CUDA'},
    }
    
    # 框架兼容性组
    FRAMEWORK_GROUPS = {
        'web_backend': {
            'Django', 'Flask', 'FastAPI', 'Express', 'Spring', 'Rails', 
            'Laravel', 'Gin', 'Echo', 'Fiber'
        },
        'desktop': {
            'PyQt', 'PyQt5', 'PyQt6', 'PySide', 'PySide2', 'PySide6',
            'Tkinter', 'Electron', 'Tauri', 'WxPython', 'Qt'
        },
        'ai_ml': {
            'TensorFlow', 'PyTorch', 'Keras', 'Transformers', 
            'LangChain', 'Scikit-learn', 'Hugging Face'
        },
        'frontend': {
            'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'Nuxt.js'
        }
    }
    
    # 数据库兼容性
    DATABASE_EQUIVALENTS = {
        'PostgreSQL': {'PostgreSQL', 'Postgres', 'psycopg2', 'pg8000'},
        'MySQL': {'MySQL', 'mysql-connector', 'pymysql'},
        'SQLite': {'SQLite', 'sqlite3', 'aiosqlite'},
        'MongoDB': {'MongoDB', 'pymongo', 'mongodriver'},
        'Redis': {'Redis', 'redis-py', 'ioredis'},
    }
    
    def match(self, github: ProjectData, local: ProjectData) -> SurfaceMatchResult:
        """执行表层匹配"""
        result = SurfaceMatchResult(score=0, insights=[])
        
        # 1. 编程语言匹配
        result.language_match = self._match_languages(github, local, result)
        
        # 2. 框架匹配
        result.framework_match = self._match_frameworks(github, local, result)
        
        # 3. 数据库匹配
        result.database_match = self._match_databases(github, local, result)
        
        # 4. 依赖重叠
        result.dependency_overlap = self._match_dependencies(github, local, result)
        
        # 5. 文件结构相似度
        result.structure_similarity = self._match_structure(github, local, result)
        
        # 计算总分
        total_weight = sum(self.WEIGHTS.values())
        result.score = (
            result.language_match * self.WEIGHTS['language'] / 100 +
            result.framework_match * self.WEIGHTS['framework'] / 100 +
            result.database_match * self.WEIGHTS['database'] / 100 +
            result.dependency_overlap * self.WEIGHTS['dependency'] / 100 +
            result.structure_similarity * self.WEIGHTS['structure'] / 100
        )
        
        result.score = min(100, max(0, result.score))
        
        return result
    
    def _match_languages(self, github: ProjectData, local: ProjectData, 
                       result: SurfaceMatchResult) -> float:
        """匹配编程语言"""
        github_langs = self._normalize_languages(github.languages)
        local_langs = self._normalize_languages(local.languages)
        
        if not github_langs or not local_langs:
            result.insights.append(MatchInsight(
                category='language',
                status='unknown',
                message='无法确定编程语言',
                score_contribution=0
            ))
            return 0
        
        # 完全匹配
        exact_match = github_langs & local_langs
        
        # 家族匹配
        family_match = set()
        for lang in github_langs:
            for family, members in self.LANGUAGE_FAMILIES.items():
                if lang in members:
                    family_match |= members & local_langs
        
        all_matches = exact_match | family_match
        
        if all_matches:
            score = 100 * len(all_matches) / max(len(github_langs), len(local_langs))
            result.insights.append(MatchInsight(
                category='language',
                status='match',
                message=f"编程语言匹配: {', '.join(all_matches)}",
                score_contribution=score * self.WEIGHTS['language'] / 100
            ))
            return score
        
        # 部分匹配 (至少一门语言相似)
        if github_langs & local_langs:
            score = 30
            result.insights.append(MatchInsight(
                category='language',
                status='partial',
                message=f"部分语言重叠，但核心语言不同",
                score_contribution=score * self.WEIGHTS['language'] / 100
            ))
            return score
        
        # 无匹配
        result.insights.append(MatchInsight(
            category='language',
            status='mismatch',
            message=f"编程语言不匹配: GitHub={', '.join(github_langs)}, 本地={', '.join(local_langs)}",
            score_contribution=0
        ))
        return 0
    
    def _normalize_languages(self, languages: Set[str]) -> Set[str]:
        """规范化语言名称"""
        normalized = set()
        
        for lang in languages:
            lang_lower = lang.lower()
            
            if 'python' in lang_lower:
                normalized.add('Python')
            elif 'javascript' in lang_lower or lang_lower in ['js', 'ts', 'jsx', 'tsx']:
                normalized.add('JavaScript')
            elif 'typescript' in lang_lower:
                normalized.add('TypeScript')
            elif 'java' in lang_lower:
                normalized.add('Java')
            elif 'c++' in lang_lower or 'cpp' in lang_lower:
                normalized.add('C++')
            elif 'c#' in lang_lower or 'csharp' in lang_lower:
                normalized.add('C#')
            elif 'go' in lang_lower or 'golang' in lang_lower:
                normalized.add('Go')
            elif 'rust' in lang_lower:
                normalized.add('Rust')
            elif 'ruby' in lang_lower:
                normalized.add('Ruby')
            elif 'swift' in lang_lower:
                normalized.add('Swift')
            elif 'kotlin' in lang_lower:
                normalized.add('Kotlin')
            elif 'html' in lang_lower:
                normalized.add('HTML')
            elif 'css' in lang_lower:
                normalized.add('CSS')
            elif 'qml' in lang_lower:
                normalized.add('QML')
            elif lang_lower in ['qt', 'qt ui', 'ui']:
                normalized.add('Qt')
            else:
                normalized.add(lang)
        
        return normalized
    
    def _match_frameworks(self, github: ProjectData, local: ProjectData,
                         result: SurfaceMatchResult) -> float:
        """匹配框架"""
        github_frameworks = self._normalize_frameworks(github.frameworks)
        local_frameworks = self._normalize_frameworks(local.frameworks)
        
        if not github_frameworks:
            result.insights.append(MatchInsight(
                category='framework',
                status='unknown',
                message='GitHub 项目未检测到框架',
                score_contribution=50 * self.WEIGHTS['framework'] / 100
            ))
            return 50
        
        if not local_frameworks:
            result.insights.append(MatchInsight(
                category='framework',
                status='unknown',
                message='本地项目未检测到框架',
                score_contribution=50 * self.WEIGHTS['framework'] / 100
            ))
            return 50
        
        # 完全匹配
        exact_match = github_frameworks & local_frameworks
        
        # 组匹配
        group_match = set()
        for fw in github_frameworks:
            for group_name, members in self.FRAMEWORK_GROUPS.items():
                if fw in members:
                    group_match |= members & local_frameworks
        
        all_matches = exact_match | group_match
        
        if all_matches:
            score = 100 * len(all_matches) / max(len(github_frameworks), 1)
            result.insights.append(MatchInsight(
                category='framework',
                status='match',
                message=f"框架匹配: {', '.join(all_matches)}",
                score_contribution=score * self.WEIGHTS['framework'] / 100
            ))
            return score
        
        # 无匹配但同组
        if self._is_same_group(github_frameworks, local_frameworks):
            score = 40
            result.insights.append(MatchInsight(
                category='framework',
                status='partial',
                message=f"使用同类框架但具体实现不同",
                score_contribution=score * self.WEIGHTS['framework'] / 100
            ))
            return score
        
        result.insights.append(MatchInsight(
            category='framework',
            status='mismatch',
            message=f"框架不匹配: GitHub={', '.join(github_frameworks)}, 本地={', '.join(local_frameworks)}",
            score_contribution=0
        ))
        return 0
    
    def _normalize_frameworks(self, frameworks: Set[str]) -> Set[str]:
        """规范化框架名称"""
        normalized = set()
        
        for fw in frameworks:
            fw_lower = fw.lower()
            
            if 'pyqt' in fw_lower or 'pyside' in fw_lower or 'qt' == fw_lower:
                normalized.add('Qt')
            elif 'django' in fw_lower:
                normalized.add('Django')
            elif 'flask' in fw_lower:
                normalized.add('Flask')
            elif 'fastapi' in fw_lower:
                normalized.add('FastAPI')
            elif 'electron' in fw_lower:
                normalized.add('Electron')
            elif 'react' in fw_lower:
                normalized.add('React')
            elif 'vue' in fw_lower:
                normalized.add('Vue')
            elif 'angular' in fw_lower:
                normalized.add('Angular')
            elif 'tensorflow' in fw_lower:
                normalized.add('TensorFlow')
            elif 'torch' in fw_lower or 'pytorch' in fw_lower:
                normalized.add('PyTorch')
            elif 'transformers' in fw_lower:
                normalized.add('Transformers')
            elif 'langchain' in fw_lower:
                normalized.add('LangChain')
            else:
                normalized.add(fw)
        
        return normalized
    
    def _is_same_group(self, frameworks1: Set, frameworks2: Set) -> bool:
        """检查是否同组"""
        for fw in frameworks1:
            for group_name, members in self.FRAMEWORK_GROUPS.items():
                if fw in members:
                    if members & frameworks2:
                        return True
        return False
    
    def _match_databases(self, github: ProjectData, local: ProjectData,
                        result: SurfaceMatchResult) -> float:
        """匹配数据库"""
        github_dbs = self._normalize_databases(github.databases)
        local_dbs = self._normalize_databases(local.databases)
        
        if not github_dbs and not local_dbs:
            result.insights.append(MatchInsight(
                category='database',
                status='unknown',
                message='两个项目均未检测到数据库',
                score_contribution=50 * self.WEIGHTS['database'] / 100
            ))
            return 50
        
        match_count = len(github_dbs & local_dbs)
        total = max(len(github_dbs), len(local_dbs), 1)
        
        score = 100 * match_count / total
        
        if match_count > 0:
            result.insights.append(MatchInsight(
                category='database',
                status='match' if match_count == total else 'partial',
                message=f"共享数据库: {', '.join(github_dbs & local_dbs)}",
                score_contribution=score * self.WEIGHTS['database'] / 100
            ))
        else:
            result.insights.append(MatchInsight(
                category='database',
                status='mismatch' if github_dbs and local_dbs else 'unknown',
                message='数据库配置不同' if github_dbs and local_dbs else '无需数据库比较',
                score_contribution=score * self.WEIGHTS['database'] / 100
            ))
        
        return score
    
    def _normalize_databases(self, databases: Set[str]) -> Set[str]:
        """规范化数据库名称"""
        normalized = set()
        
        for db in databases:
            db_lower = db.lower()
            
            if 'postgresql' in db_lower or 'postgres' in db_lower:
                normalized.add('PostgreSQL')
            elif 'mysql' in db_lower:
                normalized.add('MySQL')
            elif 'mongodb' in db_lower or 'mongo' in db_lower:
                normalized.add('MongoDB')
            elif 'redis' in db_lower:
                normalized.add('Redis')
            elif 'sqlite' in db_lower:
                normalized.add('SQLite')
            elif 'elasticsearch' in db_lower:
                normalized.add('Elasticsearch')
            else:
                normalized.add(db)
        
        return normalized
    
    def _match_dependencies(self, github: ProjectData, local: ProjectData,
                           result: SurfaceMatchResult) -> float:
        """匹配依赖重叠"""
        # 收集所有依赖
        github_deps = set()
        for dep_info in github.dependencies:
            github_deps.update(dep_info.raw_dependencies.keys())
        
        local_deps = set()
        for dep_info in local.dependencies:
            local_deps.update(dep_info.raw_dependencies.keys())
        
        if not github_deps or not local_deps:
            result.insights.append(MatchInsight(
                category='dependency',
                status='unknown',
                message='依赖信息不完整',
                score_contribution=30 * self.WEIGHTS['dependency'] / 100
            ))
            return 30
        
        # 计算重叠
        overlap = github_deps & local_deps
        union = github_deps | local_deps
        
        # Jaccard 相似度
        score = 100 * len(overlap) / len(union) if union else 0
        
        if overlap:
            # 显示最重要的几个重叠
            top_overlap = list(overlap)[:5]
            result.insights.append(MatchInsight(
                category='dependency',
                status='match',
                message=f"共享依赖: {', '.join(top_overlap)}" + 
                        (f' 等共{len(overlap)}个' if len(overlap) > 5 else ''),
                score_contribution=score * self.WEIGHTS['dependency'] / 100
            ))
        else:
            result.insights.append(MatchInsight(
                category='dependency',
                status='mismatch',
                message='无共享依赖',
                score_contribution=0
            ))
        
        return score
    
    def _match_structure(self, github: ProjectData, local: ProjectData,
                        result: SurfaceMatchResult) -> float:
        """匹配文件结构"""
        # 提取目录特征
        github_dirs = set(github.structure.main_directories.keys())
        local_dirs = set(local.structure.main_directories.keys())
        
        if not github_dirs and not local_dirs:
            return 50
        
        # Jaccard 相似度
        intersection = len(github_dirs & local_dirs)
        union = len(github_dirs | local_dirs)
        
        score = 100 * intersection / union if union else 0
        
        if intersection > 0:
            shared = github_dirs & local_dirs
            result.insights.append(MatchInsight(
                category='structure',
                status='match',
                message=f"共享目录结构: {', '.join(shared)}",
                score_contribution=score * self.WEIGHTS['structure'] / 100
            ))
        else:
            result.insights.append(MatchInsight(
                category='structure',
                status='partial',
                message='目录结构不同',
                score_contribution=score * self.WEIGHTS['structure'] / 100
            ))
        
        return score


# 工厂函数
def create_surface_matcher() -> SurfaceMatcher:
    """创建表层匹配器"""
    return SurfaceMatcher()


if __name__ == '__main__':
    # 测试
    from project_analyzer import ProjectData, ProjectType
    
    github = ProjectData(
        project_type=ProjectType.DESKTOP,
        languages={'Python', 'QML'},
        frameworks={'PyQt6'},
        databases={'SQLite'}
    )
    
    local = ProjectData(
        project_type=ProjectType.IDE_PLUGIN,
        languages={'Python', 'JavaScript'},
        frameworks={'PyQt5'},
        databases={'SQLite', 'PostgreSQL'}
    )
    
    matcher = create_surface_matcher()
    result = matcher.match(github, local)
    
    print(f"Surface Match Score: {result.score:.1f}/100")
    print("\nInsights:")
    for insight in result.insights:
        print(f"  [{insight.status.upper()}] {insight.message}")
