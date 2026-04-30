"""
训练数据构造模块 (Training Data Constructor)

构建工业级训练三元组：(指令, 输入, 输出)

核心功能：
1. 从真实项目文档提取训练数据
2. 从仿真/计算报告构造推理样本
3. 从专家修订记录学习纠错逻辑
4. 数据质量控制与清洗

集成共享基础设施：
- 统一术语模型：使用共享的 Term 类处理术语
- 缓存层：缓存训练样本，提升数据准备速度
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 导入共享基础设施
from client.src.business.shared import (
    Term,
    CacheLayer,
    get_cache
)


@dataclass
class TrainingSample:
    """训练样本"""
    instruction: str           # 指令/任务描述
    input_data: str            # 输入数据
    output: str               # 期望输出
    reasoning: Optional[List[str]] = None  # 思维链
    uncertainty: Optional[str] = None      # 不确定性说明
    task_type: str = "general"
    stage: int = 1             # 训练阶段 1-4
    source: str = "unknown"
    quality_score: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DataSource:
    """数据源配置"""
    name: str
    type: str  # project_doc, simulation_report, expert_revision
    path: str
    enabled: bool = True
    priority: int = 1


class TrainingDataConstructor:
    """
    训练数据构造器
    
    从多种来源构造工业级训练三元组：
    1. 真实项目文档 → (需求, 方案) 配对
    2. 仿真/计算报告 → (参数, 计算过程, 结论) 配对
    3. 专家修订记录 → (初稿, 修订指令) 配对
    
    集成共享基础设施：
    - 统一术语模型：使用共享的 Term 类处理术语
    - 缓存层：缓存训练样本，提升数据准备速度
    """
    
    def __init__(self):
        # 获取共享基础设施
        self.cache = get_cache()
        
        # 数据源配置
        self.sources: Dict[str, DataSource] = {}
        
        # 已构造的训练样本
        self.samples: List[TrainingSample] = []
        
        # 工业术语词典（使用统一术语模型）
        self.industry_term_tables: Dict[str, List[Term]] = {}
        self._load_industry_terms()
        
        # 格式模式（用于质量控制）
        self.format_patterns = {
            "standard": r'GB/T\s*\d+(?:\.\d+)*|GB\s*\d+(?:\.\d+)*|IEC\s*\d+',
            "model": r'[A-Z]+\d+[-_]?\d*',
            "tolerance": r'\d+(?:\.\d+)?\s*(mm|μm|°|%)',
            "parameter": r'[\u4e00-\u9fa5]+[\s：:]+\d+(?:\.\d+)?\s*[a-zA-Z]*'
        }
        
        # 统计
        self.total_samples = 0
        self.samples_by_stage = {1: 0, 2: 0, 3: 0, 4: 0}
        
        print("[TrainingDataConstructor] 初始化完成（已集成统一术语模型、缓存层）")
    
    def _load_industry_terms(self):
        """加载工业术语（使用统一术语模型）"""
        terms_data = {
            "机械制造": [
                ("公差", "公差配合", "设备"), ("配合", "公差配合", "设备"),
                ("粗糙度", "表面粗糙度", "参数"), ("热处理", "热处理工艺", "工艺"),
                ("CNC", "数控加工", "工艺"), ("加工中心", "数控加工中心", "设备")
            ],
            "电子电气": [
                ("PLC", "可编程逻辑控制器", "设备"), ("MCU", "微控制器", "设备"),
                ("PCB", "印制电路板", "设备"), ("继电器", "电磁继电器", "设备"),
                ("变频器", "变频调速器", "设备"), ("传感器", "检测传感器", "设备")
            ],
            "化工": [
                ("反应釜", "反应釜反应器", "设备"), ("精馏塔", "精馏分离塔", "设备"),
                ("换热器", "热交换器", "设备"), ("催化剂", "化学催化剂", "材料"),
                ("工艺参数", "工艺操作参数", "参数")
            ],
            "汽车": [
                ("ECU", "电子控制单元", "设备"), ("ESP", "电子稳定程序", "系统"),
                ("ABS", "防抱死制动系统", "系统"), ("动力电池", "动力锂电池", "设备"),
                ("ADAS", "高级驾驶辅助系统", "系统")
            ],
            "能源": [
                ("光伏", "光伏发电系统", "系统"), ("风电", "风力发电系统", "系统"),
                ("储能", "储能系统", "系统"), ("逆变器", "光伏逆变器", "设备"),
                ("充电桩", "电动汽车充电桩", "设备")
            ]
        }
        
        for industry, terms in terms_data.items():
            self.industry_term_tables[industry] = []
            for dialect, standard, term_type in terms:
                term = Term(
                    dialect_term=dialect,
                    standard_term=standard,
                    source_file="preset",
                    confidence=1.0,
                    term_type=term_type,
                    industry=industry
                )
                self.industry_term_tables[industry].append(term)
                
                # 缓存术语
                cache_key = f"data_constructor:term:{industry}:{dialect}"
                self.cache.set(cache_key, term.to_dict())
    
    def cache_samples(self, samples: List[TrainingSample], key: str):
        """缓存训练样本"""
        cache_data = []
        for sample in samples:
            cache_data.append({
                "instruction": sample.instruction,
                "input_data": sample.input_data,
                "output": sample.output,
                "reasoning": sample.reasoning,
                "uncertainty": sample.uncertainty,
                "task_type": sample.task_type,
                "stage": sample.stage,
                "quality_score": sample.quality_score
            })
        
        self.cache.set(f"data_constructor:samples:{key}", cache_data, ttl=86400)
        print(f"[TrainingDataConstructor] 缓存 {len(samples)} 条样本")
    
    def get_cached_samples(self, key: str) -> Optional[List[Dict]]:
        """获取缓存的训练样本"""
        cached = self.cache.get(f"data_constructor:samples:{key}")
        if cached:
            print(f"[TrainingDataConstructor] 从缓存加载 {len(cached)} 条样本")
            return cached
        return None
    
    def add_source(self, name: str, source_type: str, path: str, priority: int = 1):
        """
        添加数据源
        
        Args:
            name: 数据源名称
            source_type: 类型 (project_doc, simulation_report, expert_revision)
            path: 文件/目录路径
            priority: 优先级
        """
        source = DataSource(
            name=name,
            type=source_type,
            path=path,
            priority=priority
        )
        self.sources[name] = source
        print(f"[TrainingDataConstructor] 添加数据源: {name} ({source_type})")
    
    def construct_from_project_docs(self, source_name: str) -> List[TrainingSample]:
        """
        从项目文档构造训练样本
        
        将"需求书-方案书"配对为 (需求, 方案)
        
        Args:
            source_name: 数据源名称
            
        Returns:
            构造的训练样本列表
        """
        source = self.sources.get(source_name)
        if not source or source.type != "project_doc":
            return []
        
        samples = []
        docs_path = Path(source.path)
        
        if docs_path.is_dir():
            # 查找需求书和方案书
            req_files = list(docs_path.glob("*需求*.md")) + list(docs_path.glob("*需求*.txt"))
            sol_files = list(docs_path.glob("*方案*.md")) + list(docs_path.glob("*方案*.txt"))
            
            for req_file in req_files:
                # 尝试找到对应的方案书
                req_name = req_file.stem.replace("需求", "").strip()
                sol_file = None
                
                for sf in sol_files:
                    if req_name in sf.stem or sf.stem.replace("方案", "").strip() == req_name:
                        sol_file = sf
                        break
                
                if sol_file:
                    try:
                        req_content = req_file.read_text(encoding='utf-8')
                        sol_content = sol_file.read_text(encoding='utf-8')
                        
                        sample = TrainingSample(
                            instruction="根据需求文档生成技术方案",
                            input_data=req_content,
                            output=sol_content,
                            task_type="project_design",
                            stage=4,
                            source=f"project_doc:{source_name}"
                        )
                        samples.append(sample)
                    except Exception as e:
                        print(f"[TrainingDataConstructor] 读取文档失败: {e}")
        
        self._add_samples(samples)
        return samples
    
    def construct_from_simulation_reports(self, source_name: str) -> List[TrainingSample]:
        """
        从仿真/计算报告构造训练样本
        
        将"输入参数-计算过程-结论"配对
        
        Args:
            source_name: 数据源名称
            
        Returns:
            构造的训练样本列表
        """
        source = self.sources.get(source_name)
        if not source or source.type != "simulation_report":
            return []
        
        samples = []
        reports_path = Path(source.path)
        
        if reports_path.is_dir():
            report_files = list(reports_path.glob("*.md")) + list(reports_path.glob("*.txt"))
            
            for report_file in report_files:
                try:
                    content = report_file.read_text(encoding='utf-8')
                    
                    # 提取输入参数、计算过程、结论
                    params = self._extract_section(content, ["输入参数", "参数设置", "工况条件"])
                    process = self._extract_section(content, ["计算过程", "仿真步骤", "分析过程"])
                    conclusion = self._extract_section(content, ["结论", "结果分析", "总结"])
                    
                    if params and conclusion:
                        reasoning = []
                        if process:
                            # 从计算过程提取关键步骤
                            steps = re.split(r'[0-9]+[\.\uff0e、]', process)
                            reasoning = [s.strip() for s in steps if s.strip()]
                        
                        sample = TrainingSample(
                            instruction="根据输入参数进行计算分析并给出结论",
                            input_data=params,
                            output=conclusion,
                            reasoning=reasoning[:5],  # 最多5步
                            task_type="calculation",
                            stage=2,
                            source=f"simulation_report:{source_name}"
                        )
                        samples.append(sample)
                except Exception as e:
                    print(f"[TrainingDataConstructor] 读取报告失败: {e}")
        
        self._add_samples(samples)
        return samples
    
    def construct_from_expert_revisions(self, source_name: str) -> List[TrainingSample]:
        """
        从专家修订记录构造训练样本
        
        将"初稿-专家修改稿"配对为 (初稿, 修订指令)
        
        Args:
            source_name: 数据源名称
            
        Returns:
            构造的训练样本列表
        """
        source = self.sources.get(source_name)
        if not source or source.type != "expert_revision":
            return []
        
        samples = []
        revisions_path = Path(source.path)
        
        if revisions_path.is_dir():
            # 查找包含修订标记的文件
            revision_files = list(revisions_path.glob("*修订*.md")) + list(revisions_path.glob("*修改*.md"))
            
            for rev_file in revision_files:
                try:
                    content = rev_file.read_text(encoding='utf-8')
                    
                    # 提取初稿和修改建议
                    original = self._extract_section(content, ["初稿", "原始内容"])
                    revision = self._extract_section(content, ["修改建议", "专家意见", "修订说明"])
                    
                    if original and revision:
                        sample = TrainingSample(
                            instruction="根据专家修订意见改进技术文档",
                            input_data=original,
                            output=revision,
                            task_type="revision",
                            stage=2,
                            source=f"expert_revision:{source_name}"
                        )
                        samples.append(sample)
                except Exception as e:
                    print(f"[TrainingDataConstructor] 读取修订记录失败: {e}")
        
        self._add_samples(samples)
        return samples
    
    def _extract_section(self, content: str, section_names: List[str]) -> Optional[str]:
        """
        从文档中提取指定章节
        
        Args:
            content: 文档内容
            section_names: 章节名称列表
            
        Returns:
            章节内容，如果未找到返回 None
        """
        lines = content.split('\n')
        result = []
        in_section = False
        
        for line in lines:
            # 检查是否进入目标章节
            if not in_section:
                for name in section_names:
                    if name in line and len(line) < 50:  # 章节标题通常较短
                        in_section = True
                        continue
            else:
                # 检查是否到达下一章节
                if line.startswith('#') or line.startswith('##'):
                    break
                result.append(line)
        
        if result:
            return '\n'.join(result).strip()
        return None
    
    def _add_samples(self, samples: List[TrainingSample]):
        """添加样本并更新统计"""
        for sample in samples:
            # 质量检查
            sample.quality_score = self._evaluate_quality(sample)
            
            # 过滤低质量样本
            if sample.quality_score >= 0.7:
                self.samples.append(sample)
                self.total_samples += 1
                self.samples_by_stage[sample.stage] += 1
    
    def _evaluate_quality(self, sample: TrainingSample) -> float:
        """
        评估样本质量
        
        Returns:
            质量分数 (0-1)
        """
        score = 0.5
        
        # 检查长度
        if len(sample.input_data) > 50 and len(sample.output) > 50:
            score += 0.2
        
        # 检查是否包含行业术语
        for industry, terms in self.industry_terms.items():
            for term in terms:
                if term in sample.input_data or term in sample.output:
                    score += 0.05
                    break
        
        # 检查格式正确性（标准号、型号等）
        for pattern_name, pattern in self.format_patterns.items():
            if re.search(pattern, sample.output):
                score += 0.05
        
        # 检查是否包含不确定性说明
        if sample.uncertainty and len(sample.uncertainty) > 10:
            score += 0.1
        
        return min(1.0, score)
    
    def generate_synthetic_samples(self, count: int, task_type: str = "general") -> List[TrainingSample]:
        """
        生成合成训练样本
        
        Args:
            count: 生成数量
            task_type: 任务类型
            
        Returns:
            合成样本列表
        """
        samples = []
        
        # 工业场景模板
        templates = {
            "selection": {
                "instruction": "根据给定条件选择合适的工业设备",
                "examples": [
                    {"input": "为化工厂强腐蚀环境选择流量计，介质为硫酸，温度80℃",
                     "reasoning": ["环境判定：强腐蚀+硫酸 → 材质必须为耐酸合金或PTFE",
                                  "温度排除：80℃ 排除部分塑料流量计",
                                  "类型筛选：电磁流量计（无接触）或金属管浮子流量计",
                                  "精度权衡：化工过程控制需±1%，选电磁"],
                     "output": "推荐选用电磁流量计，电极材质建议哈氏C-276，衬里选用PTFE。",
                     "uncertainty": "需确认硫酸的具体浓度，浓度>80%时材质需重新评估。"},
                    {"input": "为汽车发动机测试台选择温度传感器，测量范围-40~200℃，精度要求±0.5℃",
                     "reasoning": ["温度范围分析：-40~200℃ 需宽温域传感器",
                                  "精度要求：±0.5℃ 需要PT100或热电偶",
                                  "环境考量：发动机舱振动大，需抗振设计",
                                  "安装方式：建议采用螺纹安装"],
                     "output": "推荐选用PT100铂电阻温度传感器，精度等级A级，防护等级IP67。",
                     "uncertainty": "需确认安装空间和连接方式。"}
                ]
            },
            "calculation": {
                "instruction": "根据输入参数进行工程计算",
                "examples": [
                    {"input": "计算直径100mm的钢管在2MPa压力下的壁厚，材质为Q235",
                     "reasoning": ["查阅GB/T 8163标准",
                                  "计算许用应力：Q235的许用应力约为113MPa",
                                  "使用壁厚计算公式：S = PD/(2[σ]φ)",
                                  "代入计算：S = 2×100/(2×113×0.85) ≈ 1.07mm"],
                     "output": "根据GB/T 8163标准计算，所需壁厚约为1.07mm，建议选用DN100×3.5规格的无缝钢管。",
                     "uncertainty": "未考虑腐蚀余量，实际工程中需增加0.5~1mm腐蚀余量。"}
                ]
            },
            "validation": {
                "instruction": "验证参数是否符合标准要求",
                "examples": [
                    {"input": "验证某轴的尺寸公差：直径50mm，上偏差+0.02mm，下偏差-0.01mm，公差等级IT7",
                     "reasoning": ["查阅GB/T 1800.1标准",
                                  "IT7级公差在50mm尺寸段的公差值为0.025mm",
                                  "计算实际公差带：0.02 - (-0.01) = 0.03mm",
                                  "比较：0.03mm > 0.025mm，不符合要求"],
                     "output": "不符合要求。IT7级在50mm尺寸段的标准公差为0.025mm，而实际公差带为0.03mm，超出标准要求。",
                     "uncertainty": "需确认基准温度和测量方法是否符合标准规定。"}
                ]
            }
        }
        
        template = templates.get(task_type, templates["selection"])
        
        for i in range(count):
            example = template["examples"][i % len(template["examples"])]
            sample = TrainingSample(
                instruction=template["instruction"],
                input_data=example["input"],
                output=example["output"],
                reasoning=example["reasoning"],
                uncertainty=example["uncertainty"],
                task_type=task_type,
                stage=self._determine_stage(task_type),
                source="synthetic"
            )
            samples.append(sample)
        
        self._add_samples(samples)
        return samples
    
    def _determine_stage(self, task_type: str) -> int:
        """根据任务类型确定训练阶段"""
        stage_map = {
            "classification": 1,      # 片段分类
            "entity_recognition": 1,  # 实体识别
            "style_conversion": 1,    # 风格改写
            "validation": 2,          # 参数校验
            "fault_diagnosis": 2,     # 故障归因
            "comparison": 2,          # 方案对比
            "tool_selection": 3,      # 工具选择
            "task_decomposition": 3,  # 步骤拆解
            "gap_detection": 3,       # 缺口检测
            "project_design": 4,      # 项目设计
            "report_generation": 4    # 报告生成
        }
        return stage_map.get(task_type, 2)
    
    def export_to_json(self, filepath: str, stage_filter: Optional[int] = None):
        """
        导出训练数据为JSON格式
        
        Args:
            filepath: 输出文件路径
            stage_filter: 阶段过滤（可选）
        """
        export_samples = self.samples
        if stage_filter:
            export_samples = [s for s in self.samples if s.stage == stage_filter]
        
        data = []
        for sample in export_samples:
            data.append({
                "instruction": sample.instruction,
                "input": sample.input_data,
                "output": sample.output,
                "reasoning": sample.reasoning,
                "uncertainty": sample.uncertainty,
                "task_type": sample.task_type,
                "stage": sample.stage,
                "source": sample.source,
                "quality_score": sample.quality_score,
                "created_at": sample.created_at.isoformat()
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[TrainingDataConstructor] 导出 {len(data)} 条样本到 {filepath}")
    
    def import_from_json(self, filepath: str):
        """
        从JSON导入训练数据
        
        Args:
            filepath: 输入文件路径
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        samples = []
        for item in data:
            sample = TrainingSample(
                instruction=item["instruction"],
                input_data=item["input"],
                output=item["output"],
                reasoning=item.get("reasoning"),
                uncertainty=item.get("uncertainty"),
                task_type=item.get("task_type", "general"),
                stage=item.get("stage", 1),
                source=item.get("source", "imported"),
                quality_score=item.get("quality_score", 1.0)
            )
            samples.append(sample)
        
        self._add_samples(samples)
        print(f"[TrainingDataConstructor] 导入 {len(samples)} 条样本")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_samples": self.total_samples,
            "samples_by_stage": self.samples_by_stage,
            "sources": {name: s.type for name, s in self.sources.items()},
            "average_quality": sum(s.quality_score for s in self.samples) / max(len(self.samples), 1)
        }


def create_data_constructor() -> TrainingDataConstructor:
    """创建训练数据构造器实例"""
    return TrainingDataConstructor()


__all__ = [
    "TrainingDataConstructor",
    "TrainingSample",
    "DataSource",
    "create_data_constructor"
]