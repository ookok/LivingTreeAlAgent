"""
数据飞轮 - Data Flywheel

负责收集、清洗、格式化高质量交互数据，
为模型训练提供源源不断的燃料。

工作流程：
1. 收集交互数据（用户好评、RAG成功记录、专家回复）
2. 数据清洗和去重
3. 格式化为训练数据格式
4. 存入训练数据池
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class InteractionRecord:
    """交互记录"""
    query: str
    response: str
    intent: str
    source: str
    rating: Optional[int] = None  # 1-5 评分
    confidence: float = 0.0
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "query": self.query,
            "response": self.response,
            "intent": self.intent,
            "source": self.source,
            "rating": self.rating,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "InteractionRecord":
        """从字典创建"""
        return cls(
            query=data.get("query", ""),
            response=data.get("response", ""),
            intent=data.get("intent", ""),
            source=data.get("source", ""),
            rating=data.get("rating"),
            confidence=data.get("confidence", 0.0),
            timestamp=data.get("timestamp", "")
        )


class DataFlywheel:
    """
    数据飞轮组件
    
    持续收集高质量交互数据，为模型进化提供燃料
    """
    
    def __init__(self):
        self._logger = logger.bind(component="DataFlywheel")
        self._data_dir = Path.home() / ".livingtree_agent" / "data" / "flywheel"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._records: List[InteractionRecord] = []
        self._load_records()
    
    def _load_records(self):
        """加载已存储的记录"""
        records_file = self._data_dir / "records.json"
        if records_file.exists():
            try:
                data = json.loads(records_file.read_text(encoding="utf-8"))
                self._records = [InteractionRecord.from_dict(r) for r in data]
                self._logger.info(f"加载了 {len(self._records)} 条交互记录")
            except Exception as e:
                self._logger.error(f"加载记录失败: {e}")
    
    def _save_records(self):
        """保存记录到文件"""
        records_file = self._data_dir / "records.json"
        try:
            data = [r.to_dict() for r in self._records]
            records_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            self._logger.error(f"保存记录失败: {e}")
    
    def record_interaction(self, interaction: Dict):
        """
        记录交互数据
        
        Args:
            interaction: 交互数据字典
        """
        record = InteractionRecord(
            query=interaction.get("query", ""),
            response=interaction.get("response", ""),
            intent=interaction.get("intent", ""),
            source=interaction.get("source", ""),
            rating=interaction.get("rating"),
            confidence=interaction.get("confidence", 0.0),
            timestamp=interaction.get("timestamp", datetime.now().isoformat())
        )
        
        # 去重检查
        if not self._is_duplicate(record):
            self._records.append(record)
            self._save_records()
            self._logger.debug(f"记录交互: {record.intent}")
    
    def _is_duplicate(self, record: InteractionRecord) -> bool:
        """检查是否重复"""
        record_hash = self._hash_record(record)
        
        for r in self._records:
            if self._hash_record(r) == record_hash:
                return True
        
        return False
    
    def _hash_record(self, record: InteractionRecord) -> str:
        """计算记录哈希值"""
        content = f"{record.query}{record.response}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def collect_recent_interactions(self) -> int:
        """
        收集最近的交互数据
        
        Returns:
            新收集的记录数量
        """
        # 从各种来源收集数据
        new_count = 0
        
        # 1. 从 RAG 引擎收集成功查询
        new_count += self._collect_from_rag()
        
        # 2. 从专家系统收集
        new_count += self._collect_from_experts()
        
        # 3. 从用户反馈收集
        new_count += self._collect_from_feedback()
        
        return new_count
    
    def _collect_from_rag(self) -> int:
        """从 RAG 引擎收集数据"""
        try:
            from client.src.business.fusion_rag.rag_engine import RAGEngine
            rag = RAGEngine()
            successful_queries = rag.get_successful_queries(limit=50)
            
            count = 0
            for query in successful_queries:
                interaction = {
                    "query": query.get("query", ""),
                    "response": query.get("response", ""),
                    "intent": "document_query",
                    "source": "RAG",
                    "confidence": query.get("confidence", 0.0),
                    "timestamp": datetime.now().isoformat()
                }
                self.record_interaction(interaction)
                count += 1
            
            return count
        except Exception as e:
            self._logger.warning(f"从 RAG 收集失败: {e}")
            return 0
    
    def _collect_from_experts(self) -> int:
        """从专家系统收集数据"""
        try:
            from client.src.business.expert_system.expert_manager import ExpertManager
            expert = ExpertManager()
            expert_interactions = expert.get_recent_interactions(limit=50)
            
            count = 0
            for interaction in expert_interactions:
                self.record_interaction({
                    "query": interaction.get("query", ""),
                    "response": interaction.get("response", ""),
                    "intent": interaction.get("intent", "complex_reasoning"),
                    "source": "Expert",
                    "confidence": 1.0,
                    "timestamp": datetime.now().isoformat()
                })
                count += 1
            
            return count
        except Exception as e:
            self._logger.warning(f"从专家系统收集失败: {e}")
            return 0
    
    def _collect_from_feedback(self) -> int:
        """从用户反馈收集数据"""
        try:
            feedback_file = self._data_dir / "feedback.json"
            if feedback_file.exists():
                feedback_data = json.loads(feedback_file.read_text(encoding="utf-8"))
                
                count = 0
                for feedback in feedback_data:
                    if feedback.get("rating", 0) >= 4:  # 只收集好评
                        self.record_interaction({
                            "query": feedback.get("query", ""),
                            "response": feedback.get("response", ""),
                            "intent": feedback.get("intent", ""),
                            "source": "UserFeedback",
                            "rating": feedback.get("rating"),
                            "timestamp": datetime.now().isoformat()
                        })
                        count += 1
                
                # 清空已处理的反馈
                feedback_file.write_text("[]")
                return count
            
            return 0
        except Exception as e:
            self._logger.warning(f"从反馈收集失败: {e}")
            return 0
    
    def prepare_training_dataset(self) -> str:
        """
        准备训练数据集
        
        Returns:
            训练数据集文件路径
        """
        # 筛选高质量数据
        high_quality = self._filter_high_quality()
        
        # 格式化为训练格式
        training_data = self._format_for_training(high_quality)
        
        # 保存到文件
        output_file = self._data_dir / f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.write_text(json.dumps(training_data, indent=2, ensure_ascii=False), encoding="utf-8")
        
        self._logger.info(f"训练数据集准备完成: {output_file} ({len(training_data)} 条)")
        return str(output_file)
    
    def _filter_high_quality(self) -> List[InteractionRecord]:
        """筛选高质量数据"""
        filtered = []
        
        for record in self._records:
            # 条件1: 评分 >= 4 或没有评分
            if record.rating is not None and record.rating < 4:
                continue
            
            # 条件2: 置信度 >= 0.7
            if record.confidence < 0.7 and record.confidence > 0:
                continue
            
            # 条件3: 查询和响应都不为空
            if not record.query or not record.response:
                continue
            
            # 条件4: 来源是可靠的
            if record.source in ["RAG", "Expert", "LLM"]:
                filtered.append(record)
        
        return filtered
    
    def _format_for_training(self, records: List[InteractionRecord]) -> List[Dict]:
        """格式化为训练数据格式"""
        training_data = []
        
        for record in records:
            training_data.append({
                "instruction": record.query,
                "output": record.response,
                "intent": record.intent,
                "source": record.source
            })
        
        return training_data
    
    def get_record_count(self) -> int:
        """获取记录总数"""
        return len(self._records)
    
    def get_records_by_intent(self, intent: str) -> List[InteractionRecord]:
        """按意图获取记录"""
        return [r for r in self._records if r.intent == intent]
    
    def clear_records(self):
        """清空所有记录"""
        self._records = []
        self._save_records()
        self._logger.info("已清空所有交互记录")


# 快捷函数
def get_data_flywheel() -> DataFlywheel:
    """获取数据飞轮实例"""
    return DataFlywheel()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("数据飞轮测试")
    print("=" * 60)
    
    flywheel = DataFlywheel()
    
    # 记录测试交互
    flywheel.record_interaction({
        "query": "什么是 AI?",
        "response": "人工智能是模拟人类智能的技术...",
        "intent": "simple_qa",
        "source": "LLM",
        "confidence": 0.95,
        "timestamp": datetime.now().isoformat()
    })
    
    print(f"记录总数: {flywheel.get_record_count()}")
    
    # 准备训练数据
    dataset_path = flywheel.prepare_training_dataset()
    print(f"训练数据集: {dataset_path}")
    
    print("\n" + "=" * 60)