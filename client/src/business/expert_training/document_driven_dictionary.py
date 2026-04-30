"""
文档驱动的行业方言词典系统 (Document-Driven Dictionary)

基于"文档即词典"理念实现：
1. 从结构化文档目录自动扫描术语
2. 从Excel/CSV导入人工整理的术语映射
3. 支持冲突检测与专家裁决
4. 持续维护与增量更新
5. 作为预设词典集成到训练系统

核心原则：在整理文档的过程中顺手构建词典
"""

import os
import re
import csv
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TermMapping:
    """术语映射条目"""
    dialect_term: str           # 方言/内部叫法
    standard_term: str          # 标准术语
    source_file: str            # 出处文件
    confidence: float = 1.0     # 置信度 (0-1)
    remark: str = ""            # 备注
    project: str = ""           # 所属项目
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConflictItem:
    """冲突项"""
    dialect_term: str
    mappings: List[TermMapping]
    resolved: bool = False
    resolution: Optional[TermMapping] = None


@dataclass
class DictionaryStats:
    """词典统计"""
    total_terms: int = 0
    total_projects: int = 0
    total_sources: int = 0
    conflict_count: int = 0
    resolved_conflicts: int = 0


class DocumentDrivenDictionary:
    """
    文档驱动的行业方言词典
    
    核心功能：
    1. 从结构化文档目录自动扫描术语
    2. 从Excel/CSV导入人工整理的映射
    3. 冲突检测与解决
    4. 持续维护与增量更新
    5. 导出为预设词典格式
    """
    
    def __init__(self):
        # 术语映射存储
        self.mappings: List[TermMapping] = []
        
        # 索引：方言术语 -> 映射列表（支持一词多义）
        self.dialect_index: Dict[str, List[TermMapping]] = {}
        
        # 索引：标准术语 -> 方言术语列表（反向索引）
        self.standard_index: Dict[str, List[str]] = {}
        
        # 项目列表
        self.projects: Set[str] = set()
        
        # 来源文件列表
        self.source_files: Set[str] = set()
        
        # 冲突列表
        self.conflicts: List[ConflictItem] = []
        
        print("[DocumentDrivenDictionary] 初始化完成")
    
    def scan_project_directory(self, project_dir: str):
        """
        扫描结构化项目目录，自动提取术语
        
        Args:
            project_dir: 项目目录路径
        """
        path = Path(project_dir)
        
        if not path.exists():
            raise ValueError(f"项目目录不存在: {project_dir}")
        
        print(f"[DocumentDrivenDictionary] 扫描项目目录: {project_dir}")
        
        # 获取项目名称
        project_name = path.name.replace("_", " ").replace("-", " ")
        
        # 扫描文件
        for file_path in path.rglob("*"):
            if file_path.is_file():
                # 从文件名提取术语
                self._extract_from_filename(file_path, project_name)
                
                # 记录来源文件
                self.source_files.add(str(file_path))
        
        # 查找项目术语表
        term_file = path / "项目术语表.md"
        if term_file.exists():
            self._load_project_terms(term_file, project_name)
        
        # 更新项目列表
        self.projects.add(project_name)
        
        print(f"[DocumentDrivenDictionary] 完成扫描，发现 {len(self.mappings)} 条映射")
    
    def _extract_from_filename(self, file_path: Path, project_name: str):
        """从文件名提取术语"""
        filename = file_path.stem
        
        # 解析文件名格式：项目_设备_类型_版本
        # 示例：LineA_电机底座装配图_R01
        parts = filename.split("_")
        
        if len(parts) >= 2:
            # 提取设备名称
            for part in parts:
                # 跳过版本号和常见后缀
                if not re.match(r'^[RV]\d+$', part) and len(part) >= 2:
                    # 假设中间部分是设备名称
                    self.add_mapping(
                        dialect_term=part,
                        standard_term=part,
                        source_file=str(file_path),
                        project=project_name,
                        confidence=0.8,
                        remark=f"从文件名提取: {filename}"
                    )
    
    def _load_project_terms(self, term_file: Path, project_name: str):
        """加载项目术语表.md"""
        content = term_file.read_text(encoding='utf-8')
        
        # 解析Markdown表格
        lines = content.split('\n')
        in_table = False
        header_found = False
        
        for line in lines:
            # 检测表格开始
            if '|' in line and ('---' in line or ':---' in line):
                header_found = True
                in_table = True
                continue
            
            if in_table and '|' in line and header_found:
                # 解析表格行
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2:
                    dialect = parts[0]
                    standard = parts[1]
                    source = parts[2] if len(parts) > 2 else str(term_file)
                    
                    self.add_mapping(
                        dialect_term=dialect,
                        standard_term=standard,
                        source_file=source,
                        project=project_name,
                        confidence=1.0,
                        remark="从项目术语表导入"
                    )
    
    def import_from_csv(self, csv_path: str):
        """
        从CSV文件导入术语映射
        
        CSV格式：[内部术语, 标准术语, 出处文件, 置信度, 备注, 项目]
        """
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                dialect = row.get('内部术语', row.get('方言', row.get('dialect', ''))).strip()
                standard = row.get('标准术语', row.get('standard', '')).strip()
                source = row.get('出处文件', row.get('source', '')).strip()
                confidence = float(row.get('置信度', row.get('confidence', '1.0')))
                remark = row.get('备注', row.get('remark', '')).strip()
                project = row.get('项目', row.get('project', '')).strip()
                
                if dialect and standard:
                    self.add_mapping(
                        dialect_term=dialect,
                        standard_term=standard,
                        source_file=source,
                        confidence=confidence,
                        remark=remark,
                        project=project
                    )
        
        print(f"[DocumentDrivenDictionary] 从CSV导入完成")
    
    def import_from_excel(self, excel_path: str, sheet_name: str = None):
        """
        从Excel文件导入术语映射
        
        Args:
            excel_path: Excel文件路径
            sheet_name: 工作表名称（可选）
        """
        try:
            import pandas as pd
            
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            
            for _, row in df.iterrows():
                dialect = str(row.get('内部术语', row.get('方言', ''))).strip()
                standard = str(row.get('标准术语', row.get('standard', ''))).strip()
                source = str(row.get('出处文件', row.get('source', ''))).strip()
                confidence = float(row.get('置信度', row.get('confidence', '1.0')))
                remark = str(row.get('备注', row.get('remark', ''))).strip()
                project = str(row.get('项目', row.get('project', ''))).strip()
                
                if dialect and standard and dialect != 'nan' and standard != 'nan':
                    self.add_mapping(
                        dialect_term=dialect,
                        standard_term=standard,
                        source_file=source,
                        confidence=confidence,
                        remark=remark,
                        project=project
                    )
            
            print(f"[DocumentDrivenDictionary] 从Excel导入完成")
        
        except ImportError:
            print("[DocumentDrivenDictionary] 需要安装 pandas 和 openpyxl 来读取Excel文件")
        except Exception as e:
            print(f"[DocumentDrivenDictionary] 导入Excel失败: {e}")
    
    def add_mapping(self, dialect_term: str, standard_term: str, source_file: str,
                   confidence: float = 1.0, remark: str = "", project: str = ""):
        """
        添加术语映射
        
        Args:
            dialect_term: 方言/内部术语
            standard_term: 标准术语
            source_file: 出处文件
            confidence: 置信度
            remark: 备注
            project: 所属项目
        """
        # 规范化术语
        dialect_term = dialect_term.strip()
        standard_term = standard_term.strip()
        
        if not dialect_term or not standard_term:
            return
        
        # 创建映射条目
        mapping = TermMapping(
            dialect_term=dialect_term,
            standard_term=standard_term,
            source_file=source_file,
            confidence=confidence,
            remark=remark,
            project=project
        )
        
        # 添加到列表
        self.mappings.append(mapping)
        
        # 更新索引
        if dialect_term not in self.dialect_index:
            self.dialect_index[dialect_term] = []
        self.dialect_index[dialect_term].append(mapping)
        
        # 更新反向索引
        if standard_term not in self.standard_index:
            self.standard_index[standard_term] = []
        if dialect_term not in self.standard_index[standard_term]:
            self.standard_index[standard_term].append(dialect_term)
    
    def detect_conflicts(self) -> List[ConflictItem]:
        """
        检测术语冲突
        
        冲突定义：同一个方言术语对应多个不同的标准术语
        
        Returns:
            冲突项列表
        """
        self.conflicts = []
        
        for dialect, mappings in self.dialect_index.items():
            # 获取所有不同的标准术语
            standard_terms = set(m.standard_term for m in mappings)
            
            if len(standard_terms) > 1:
                conflict = ConflictItem(
                    dialect_term=dialect,
                    mappings=mappings,
                    resolved=False
                )
                self.conflicts.append(conflict)
        
        print(f"[DocumentDrivenDictionary] 检测到 {len(self.conflicts)} 个冲突")
        return self.conflicts
    
    def resolve_conflict(self, dialect_term: str, resolution: TermMapping):
        """
        解决术语冲突
        
        Args:
            dialect_term: 冲突的方言术语
            resolution: 解决后的映射
        """
        for conflict in self.conflicts:
            if conflict.dialect_term == dialect_term:
                conflict.resolved = True
                conflict.resolution = resolution
                break
    
    def resolve_conflict_by_rules(self, dialect_term: str, rule: str = "frequency"):
        """
        根据规则自动解决冲突
        
        Args:
            dialect_term: 冲突的方言术语
            rule: 解决规则 (frequency=频次优先, authority=权威优先, scene=场景优先)
        """
        mappings = self.dialect_index.get(dialect_term, [])
        
        if len(mappings) <= 1:
            return
        
        if rule == "frequency":
            # 频次优先：选择出现次数最多的标准术语
            term_counts = {}
            for m in mappings:
                term_counts[m.standard_term] = term_counts.get(m.standard_term, 0) + 1
            
            best_term = max(term_counts, key=term_counts.get)
            resolution = next(m for m in mappings if m.standard_term == best_term)
        
        elif rule == "authority":
            # 权威优先：技术协议 > 操作手册 > 会议纪要
            priority = {"技术协议": 3, "协议": 3, "手册": 2, "纪要": 1}
            best_mapping = None
            best_score = 0
            
            for m in mappings:
                score = 0
                for keyword, p in priority.items():
                    if keyword in m.source_file:
                        score = p
                        break
                
                if score > best_score:
                    best_score = score
                    best_mapping = m
            
            resolution = best_mapping
        
        elif rule == "scene":
            # 场景优先：保留所有映射，按项目区分
            # 这里简化处理，选择第一个映射
            resolution = mappings[0]
        
        else:
            resolution = mappings[0]
        
        self.resolve_conflict(dialect_term, resolution)
        print(f"[DocumentDrivenDictionary] 已解决冲突: {dialect_term} -> {resolution.standard_term}")
    
    def get_mapping(self, dialect_term: str, project: str = "") -> Optional[str]:
        """
        获取方言术语对应的标准术语
        
        Args:
            dialect_term: 方言术语
            project: 项目名称（可选，用于场景区分）
            
        Returns:
            标准术语，如果不存在返回 None
        """
        mappings = self.dialect_index.get(dialect_term)
        
        if not mappings:
            return None
        
        # 如果只有一个映射，直接返回
        if len(mappings) == 1:
            return mappings[0].standard_term
        
        # 如果有多个映射，按项目筛选
        if project:
            project_mappings = [m for m in mappings if m.project == project]
            if project_mappings:
                return project_mappings[0].standard_term
        
        # 默认返回置信度最高的
        best_mapping = max(mappings, key=lambda x: x.confidence)
        return best_mapping.standard_term
    
    def export_to_csv(self, csv_path: str):
        """导出术语映射到CSV文件"""
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['内部术语', '标准术语', '出处文件', '置信度', '备注', '项目'])
            
            for mapping in self.mappings:
                writer.writerow([
                    mapping.dialect_term,
                    mapping.standard_term,
                    mapping.source_file,
                    mapping.confidence,
                    mapping.remark,
                    mapping.project
                ])
        
        print(f"[DocumentDrivenDictionary] 已导出到 CSV: {csv_path}")
    
    def export_to_excel(self, excel_path: str):
        """导出术语映射到Excel文件"""
        try:
            import pandas as pd
            
            data = [{
                '内部术语': m.dialect_term,
                '标准术语': m.standard_term,
                '出处文件': m.source_file,
                '置信度': m.confidence,
                '备注': m.remark,
                '项目': m.project
            } for m in self.mappings]
            
            df = pd.DataFrame(data)
            df.to_excel(excel_path, index=False)
            
            print(f"[DocumentDrivenDictionary] 已导出到 Excel: {excel_path}")
        
        except ImportError:
            print("[DocumentDrivenDictionary] 需要安装 pandas 和 openpyxl")
    
    def export_to_json(self, json_path: str):
        """导出术语映射到JSON文件"""
        data = [{
            'dialect_term': m.dialect_term,
            'standard_term': m.standard_term,
            'source_file': m.source_file,
            'confidence': m.confidence,
            'remark': m.remark,
            'project': m.project,
            'created_at': m.created_at.isoformat()
        } for m in self.mappings]
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[DocumentDrivenDictionary] 已导出到 JSON: {json_path}")
    
    def export_as_fusion_rag_dict(self) -> Dict[str, Dict[str, str]]:
        """
        导出为fusion_rag兼容的词典格式
        
        Returns:
            {行业: {方言: 标准术语}}
        """
        result = {}
        
        for mapping in self.mappings:
            industry = mapping.project if mapping.project else "通用"
            
            if industry not in result:
                result[industry] = {}
            
            # 避免重复映射
            if mapping.dialect_term not in result[industry]:
                result[industry][mapping.dialect_term] = mapping.standard_term
        
        return result
    
    def get_stats(self) -> DictionaryStats:
        """获取词典统计信息"""
        return DictionaryStats(
            total_terms=len(self.mappings),
            total_projects=len(self.projects),
            total_sources=len(self.source_files),
            conflict_count=len(self.conflicts),
            resolved_conflicts=sum(1 for c in self.conflicts if c.resolved)
        )
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("=" * 60)
        print("词典统计信息")
        print("=" * 60)
        print(f"术语映射总数: {stats.total_terms}")
        print(f"覆盖项目数: {stats.total_projects}")
        print(f"来源文件数: {stats.total_sources}")
        print(f"冲突数: {stats.conflict_count}")
        print(f"已解决冲突: {stats.resolved_conflicts}")
        print("=" * 60)


def create_document_driven_dictionary() -> DocumentDrivenDictionary:
    """创建文档驱动词典实例"""
    return DocumentDrivenDictionary()


# 示例项目术语表模板
PROJECT_TERMS_TEMPLATE = """# 项目术语映射

## 说明
本文件用于记录项目专用的术语映射关系。

| 内部叫法 | 标准术语 | 出处文件 |
| :--- | :--- | :--- |
| 大炮机 | 液压冲压机 | 操作手册V1.docx |
| 光尺 | 激光位移传感器 | 技术协议.pdf |
| PLC | 可编程逻辑控制器 | 电气原理图.pdf |
| MOT-A01 | 主驱动电机 | 设备清单.xlsx |
"""


# 示例CSV模板
CSV_TEMPLATE = """内部术语,标准术语,出处文件,置信度,备注,项目
大炮机,液压冲压机,操作手册V1.docx,1.0,括号内定义,项目A
光尺,激光位移传感器,技术协议.pdf,1.0,俗称,项目A
PLC,可编程逻辑控制器,技术协议.pdf,1.0,缩写,项目A
MOT-A01,主驱动电机,设备清单.xlsx,0.9,设备代号,项目A
"""


__all__ = [
    "DocumentDrivenDictionary",
    "TermMapping",
    "ConflictItem",
    "DictionaryStats",
    "create_document_driven_dictionary",
    "PROJECT_TERMS_TEMPLATE",
    "CSV_TEMPLATE"
]