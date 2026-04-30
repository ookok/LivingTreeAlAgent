"""
IdeaGenerator - 创意引擎

实现多模型投票（生成-评审-筛选）工作流，支持创意生成和优化。

核心功能：
1. 多模型生成 - 使用多个模型生成创意
2. 投票机制 - 多模型投票选择最佳创意
3. 创意优化 - 迭代优化创意质量
4. 多样性保证 - 确保创意多样性
5. 评审机制 - 内部评审筛选

设计原理：
- 生成-评审-筛选三阶段工作流
- 多模型投票提高创意质量
- 迭代优化机制
- 创意多样性评估

使用示例：
    generator = IdeaGenerator()
    
    # 生成创意
    ideas = generator.generate(
        prompt="如何改进用户体验",
        num_ideas=5
    )
    
    # 投票选择最佳创意
    best = generator.vote(ideas)
    
    # 优化创意
    refined = generator.refine(best)
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class IdeaStatus(Enum):
    """创意状态"""
    GENERATED = "generated"
    REVIEWED = "reviewed"
    SELECTED = "selected"
    REFINED = "refined"
    REJECTED = "rejected"


class VoteResult(Enum):
    """投票结果"""
    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class Idea:
    """创意"""
    idea_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    source: str = ""  # 生成来源（模型名称）
    confidence: float = 0.0
    quality_score: float = 0.0
    diversity_score: float = 0.0
    status: IdeaStatus = IdeaStatus.GENERATED
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "idea_id": self.idea_id,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "diversity_score": self.diversity_score,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Vote:
    """投票"""
    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idea_id: str = ""
    voter: str = ""
    score: int = 0  # 1-5 分
    comment: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "idea_id": self.idea_id,
            "voter": self.voter,
            "score": self.score,
            "comment": self.comment,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class GenerationResult:
    """生成结果"""
    ideas: List[Idea] = field(default_factory=list)
    generation_time_ms: int = 0
    model_count: int = 0
    diversity: float = 0.0
    avg_quality: float = 0.0


class IdeaGenerator:
    """创意生成器"""
    
    def __init__(self):
        self._logger = logger.bind(component="IdeaGenerator")
        
        # 可用模型列表
        self._models = []
        
        # 投票存储
        self._votes: Dict[str, List[Vote]] = {}
        
        # 评审员
        self._reviewers = []
        
        # 参数配置
        self._default_num_ideas = 5
        self._vote_threshold = 3.5
        self._diversity_weight = 0.3
        
        self._logger.info("创意引擎初始化完成")
    
    def register_model(self, model_name: str, generator: Callable):
        """
        注册生成模型
        
        Args:
            model_name: 模型名称
            generator: 生成函数，接收prompt返回创意列表
        """
        self._models.append({
            "name": model_name,
            "generator": generator
        })
        self._logger.info(f"模型已注册: {model_name}")
    
    def register_reviewer(self, reviewer_name: str, reviewer: Callable):
        """
        注册评审员
        
        Args:
            reviewer_name: 评审员名称
            reviewer: 评审函数，接收idea返回评分
        """
        self._reviewers.append({
            "name": reviewer_name,
            "reviewer": reviewer
        })
    
    async def generate(self, prompt: str, num_ideas: int = None) -> GenerationResult:
        """
        生成创意
        
        Args:
            prompt: 创意生成提示
            num_ideas: 创意数量
        
        Returns:
            生成结果
        """
        num_ideas = num_ideas or self._default_num_ideas
        
        start_time = datetime.now()
        ideas = []
        
        # 使用每个模型生成创意
        for model_info in self._models:
            try:
                if asyncio.iscoroutinefunction(model_info["generator"]):
                    model_ideas = await model_info["generator"](prompt, num_ideas // len(self._models) + 1)
                else:
                    model_ideas = model_info["generator"](prompt, num_ideas // len(self._models) + 1)
                
                for content in model_ideas:
                    idea = Idea(
                        content=content,
                        source=model_info["name"],
                        confidence=0.7  # 默认置信度
                    )
                    ideas.append(idea)
            
            except Exception as e:
                self._logger.error(f"模型 {model_info['name']} 生成失败: {e}")
        
        # 如果没有注册模型，使用简单生成
        if not self._models:
            ideas = self._simple_generate(prompt, num_ideas)
        
        # 评估创意质量和多样性
        self._evaluate_ideas(ideas)
        
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return GenerationResult(
            ideas=ideas[:num_ideas],
            generation_time_ms=int(elapsed_ms),
            model_count=len(self._models),
            diversity=self._calculate_diversity(ideas),
            avg_quality=sum(i.quality_score for i in ideas) / len(ideas) if ideas else 0.0
        )
    
    def _simple_generate(self, prompt: str, num_ideas: int) -> List[Idea]:
        """简单生成（备用）"""
        ideas = []
        
        for i in range(num_ideas):
            idea = Idea(
                content=f"创意 {i+1}: 基于提示 '{prompt}' 的解决方案",
                source="simple_generator",
                confidence=0.6
            )
            ideas.append(idea)
        
        return ideas
    
    def _evaluate_ideas(self, ideas: List[Idea]):
        """评估创意质量和多样性"""
        if not ideas:
            return
        
        # 计算质量分数
        for idea in ideas:
            idea.quality_score = self._calculate_quality(idea)
        
        # 计算多样性分数
        for i, idea in enumerate(ideas):
            diversity_sum = 0.0
            count = 0
            for j, other in enumerate(ideas):
                if i != j:
                    diversity_sum += self._calculate_diversity_between(idea, other)
                    count += 1
            idea.diversity_score = diversity_sum / count if count > 0 else 0.5
    
    def _calculate_quality(self, idea: Idea) -> float:
        """计算创意质量"""
        # 基于内容长度和复杂度
        length_score = min(1.0, len(idea.content) / 100)
        complexity_score = min(1.0, len(idea.content.split()) / 20)
        
        return (length_score + complexity_score) / 2 * idea.confidence
    
    def _calculate_diversity_between(self, idea1: Idea, idea2: Idea) -> float:
        """计算两个创意之间的多样性"""
        words1 = set(idea1.content.lower().split())
        words2 = set(idea2.content.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard距离
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 1.0
        
        return 1.0 - (intersection / union)
    
    def _calculate_diversity(self, ideas: List[Idea]) -> float:
        """计算创意集合的整体多样性"""
        if len(ideas) < 2:
            return 0.0
        
        diversity_sum = 0.0
        count = 0
        
        for i in range(len(ideas)):
            for j in range(i + 1, len(ideas)):
                diversity_sum += self._calculate_diversity_between(ideas[i], ideas[j])
                count += 1
        
        return diversity_sum / count if count > 0 else 0.0
    
    def vote(self, ideas: List[Idea], voter: str = "system") -> VoteResult:
        """
        投票选择最佳创意
        
        Args:
            ideas: 创意列表
            voter: 投票者
        
        Returns:
            投票结果
        """
        if not ideas:
            return VoteResult.REJECTED
        
        # 计算综合分数（质量 + 多样性）
        scored_ideas = []
        
        for idea in ideas:
            combined_score = (1 - self._diversity_weight) * idea.quality_score + \
                           self._diversity_weight * idea.diversity_score
            scored_ideas.append((combined_score, idea))
        
        # 排序
        scored_ideas.sort(key=lambda x: x[0], reverse=True)
        
        # 记录投票
        for score, idea in scored_ideas:
            vote = Vote(
                idea_id=idea.idea_id,
                voter=voter,
                score=min(5, max(1, int(score * 5)))
            )
            
            if idea.idea_id not in self._votes:
                self._votes[idea.idea_id] = []
            self._votes[idea.idea_id].append(vote)
        
        # 获取最佳创意
        best_score, best_idea = scored_ideas[0]
        
        # 判断结果
        if best_score >= self._vote_threshold / 5:
            best_idea.status = IdeaStatus.SELECTED
            return VoteResult.ACCEPTED
        else:
            return VoteResult.PENDING
    
    def get_top_ideas(self, ideas: List[Idea], limit: int = 3) -> List[Idea]:
        """获取最佳创意"""
        scored = [((1 - self._diversity_weight) * i.quality_score + 
                   self._diversity_weight * i.diversity_score, i) 
                  for i in ideas]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in scored[:limit]]
    
    async def refine(self, idea: Idea, iterations: int = 2) -> Idea:
        """
        迭代优化创意
        
        Args:
            idea: 原始创意
            iterations: 迭代次数
        
        Returns:
            优化后的创意
        """
        current_idea = idea
        
        for i in range(iterations):
            refine_prompt = f"请优化以下创意，使其更加完善和具体：\n\n{current_idea.content}"
            
            # 使用注册的模型进行优化
            for model_info in self._models[:1]:  # 使用第一个模型进行优化
                try:
                    if asyncio.iscoroutinefunction(model_info["generator"]):
                        results = await model_info["generator"](refine_prompt, 1)
                    else:
                        results = model_info["generator"](refine_prompt, 1)
                    
                    if results:
                        current_idea = Idea(
                            content=results[0],
                            source=f"{model_info['name']}_refined",
                            confidence=min(1.0, current_idea.confidence + 0.1),
                            status=IdeaStatus.REFINED
                        )
                except Exception as e:
                    self._logger.error(f"创意优化失败: {e}")
                    break
        
        # 更新质量分数
        current_idea.quality_score = self._calculate_quality(current_idea)
        current_idea.status = IdeaStatus.REFINED
        
        return current_idea
    
    async def review(self, ideas: List[Idea]) -> List[Idea]:
        """
        评审创意
        
        Args:
            ideas: 创意列表
        
        Returns:
            评审后的创意列表
        """
        reviewed = []
        
        for idea in ideas:
            scores = []
            
            # 使用每个评审员评审
            for reviewer_info in self._reviewers:
                try:
                    if asyncio.iscoroutinefunction(reviewer_info["reviewer"]):
                        score = await reviewer_info["reviewer"](idea)
                    else:
                        score = reviewer_info["reviewer"](idea)
                    scores.append(score)
                except Exception as e:
                    self._logger.error(f"评审员 {reviewer_info['name']} 评审失败: {e}")
            
            # 如果没有评审员，使用默认评分
            if not scores:
                scores = [idea.quality_score * 5]
            
            avg_score = sum(scores) / len(scores)
            
            if avg_score >= 3.0:
                idea.status = IdeaStatus.REVIEWED
                idea.confidence = min(1.0, avg_score / 5)
                reviewed.append(idea)
            else:
                idea.status = IdeaStatus.REJECTED
            
            idea.quality_score = avg_score / 5
        
        return reviewed
    
    def get_votes(self, idea_id: str) -> List[Vote]:
        """获取创意的投票记录"""
        return self._votes.get(idea_id, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_votes = sum(len(votes) for votes in self._votes.values())
        
        return {
            "registered_models": len(self._models),
            "registered_reviewers": len(self._reviewers),
            "total_votes": total_votes,
            "vote_threshold": self._vote_threshold,
            "diversity_weight": self._diversity_weight
        }


def create_idea_generator() -> IdeaGenerator:
    """创建创意引擎实例"""
    return IdeaGenerator()
