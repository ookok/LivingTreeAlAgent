"""
主动学习引擎 (Active Learning Engine)

核心功能：
1. 实时测试工具 - 生成测验题目
2. 练习工具 - 强制执行知识检索
3. 理解力验证 - 工程化验证掌握程度
4. 复习调度 - 根据记忆曲线安排复习

参考 Wondering 的主动学习机制设计
"""

import random
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class QuizQuestion:
    """测验题目"""
    id: str
    question: str
    options: List[str]
    correct_answer: int  # 正确选项索引
    difficulty: int = 3
    topic: str = ""
    explanation: str = ""
    hint: str = ""


@dataclass
class QuizResult:
    """测验结果"""
    question_id: str
    user_answer: int
    is_correct: bool
    confidence: float = 0.0
    response_time_ms: int = 0


@dataclass
class PracticeSession:
    """练习会话"""
    id: str
    user_id: str
    topic: str
    questions: List[QuizQuestion] = field(default_factory=list)
    results: List[QuizResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    mastery_score: float = 0.0
    completed: bool = False


@dataclass
class ReviewSchedule:
    """复习计划"""
    user_id: str
    topic: str
    node_id: str
    next_review_time: float
    review_interval_hours: int
    review_count: int = 0
    last_mastery_score: float = 0.0


class ActiveLearningEngine:
    """主动学习引擎"""
    
    DIFFICULTY_LABELS = {
        1: "入门",
        2: "基础",
        3: "进阶",
        4: "高级",
        5: "专家"
    }
    
    REVIEW_INTERVALS = [1, 3, 7, 14, 30]  # 复习间隔（天）
    
    def __init__(self):
        self._logger = logger.bind(component="ActiveLearningEngine")
        self._questions: Dict[str, QuizQuestion] = {}
        self._practice_sessions: Dict[str, PracticeSession] = {}
        self._review_schedules: List[ReviewSchedule] = []
        
        # 内置题目模板
        self._question_templates = {
            "definition": {
                "pattern": "什么是{concept}？",
                "options": ["{correct}", "{distractor1}", "{distractor2}", "{distractor3}"]
            },
            "comparison": {
                "pattern": "{concept1}和{concept2}的主要区别是什么？",
                "options": ["{correct}", "{distractor1}", "{distractor2}", "{distractor3}"]
            },
            "application": {
                "pattern": "在{场景}中，应该使用{concept}吗？",
                "options": ["是", "否", "视情况而定", "不确定"]
            },
            "comprehension": {
                "pattern": "{concept}是{topic}的核心概念吗？",
                "options": ["正确", "错误", "部分正确", "无法判断"]
            }
        }
        
        self._logger.info("主动学习引擎初始化完成")
    
    def generate_quiz(self, topic: str, difficulty: int = 3, count: int = 5) -> List[QuizQuestion]:
        """
        生成测验题目
        
        Args:
            topic: 主题
            difficulty: 难度等级 (1-5)
            count: 题目数量
        
        Returns:
            题目列表
        """
        questions = []
        
        # 生成基于模板的题目
        templates = list(self._question_templates.keys())
        
        for i in range(count):
            template_key = random.choice(templates)
            template = self._question_templates[template_key]
            
            # 生成题目内容（简化实现）
            question_text = self._generate_question_text(template["pattern"], topic, difficulty)
            options = self._generate_options(template["options"], topic, difficulty)
            correct_idx = random.randint(0, 3)
            
            # 确保正确答案在选项中
            if correct_idx == 0:
                options[0] = self._generate_correct_answer(topic, difficulty)
            else:
                options[correct_idx] = options[0]
                options[0] = self._generate_distractor(topic, difficulty)
            
            question = QuizQuestion(
                id=f"q_{int(time.time() * 1000)}_{i}",
                question=question_text,
                options=options,
                correct_answer=correct_idx,
                difficulty=difficulty,
                topic=topic,
                explanation=self._generate_explanation(topic, difficulty),
                hint=self._generate_hint(topic, difficulty)
            )
            
            self._questions[question.id] = question
            questions.append(question)
        
        self._logger.info(f"生成测验题目: {topic} (难度: {difficulty}, 数量: {count})")
        return questions
    
    def _generate_question_text(self, pattern: str, topic: str, difficulty: int) -> str:
        """生成题目文本"""
        concepts = {
            "AI": ["人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理"],
            "编程": ["Python", "函数", "类", "算法", "数据结构"],
            "数学": ["线性代数", "微积分", "概率", "统计", "优化"]
        }
        
        topic_concepts = concepts.get(topic, concepts["AI"])
        concept = random.choice(topic_concepts)
        
        return pattern.format(
            concept=concept,
            concept1=concept,
            concept2=random.choice([c for c in topic_concepts if c != concept]),
            场景=f"{concept}的应用场景",
            topic=topic
        )
    
    def _generate_options(self, options_pattern: List[str], topic: str, difficulty: int) -> List[str]:
        """生成选项"""
        return [
            self._generate_correct_answer(topic, difficulty),
            self._generate_distractor(topic, difficulty),
            self._generate_distractor(topic, difficulty),
            self._generate_distractor(topic, difficulty)
        ]
    
    def _generate_correct_answer(self, topic: str, difficulty: int) -> str:
        """生成正确答案"""
        answers = {
            "AI": [
                "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新技术科学",
                "机器学习是一种人工智能技术，使计算机能够从数据中学习而无需显式编程",
                "深度学习是机器学习的一个分支，使用多层神经网络来学习数据的高级特征",
                "神经网络是由大量人工神经元相互连接组成的计算系统，用于模拟人脑的信息处理"
            ],
            "编程": [
                "Python是一种高级、通用、解释型编程语言",
                "函数是一段可重复使用的代码块，用于执行特定任务",
                "类是面向对象编程中的模板，用于创建对象",
                "算法是解决特定问题的一组有限步骤"
            ]
        }
        topic_answers = answers.get(topic, answers["AI"])
        return topic_answers[min(difficulty - 1, len(topic_answers) - 1)]
    
    def _generate_distractor(self, topic: str, difficulty: int) -> str:
        """生成干扰选项"""
        distractors = [
            "这是一个常见的误解",
            "这是相关但不完全正确的说法",
            "这是旧版的定义",
            "这是其他领域的概念",
            "这是部分正确但不够全面",
            "这是一个类似但不同的概念"
        ]
        return random.choice(distractors)
    
    def _generate_explanation(self, topic: str, difficulty: int) -> str:
        """生成答案解释"""
        return f"本题考察{topic}的核心概念。正确答案反映了{self.DIFFICULTY_LABELS[difficulty]}级别的理解要求。"
    
    def _generate_hint(self, topic: str, difficulty: int) -> str:
        """生成提示"""
        return f"提示：思考{topic}的{self.DIFFICULTY_LABELS[difficulty]}级核心知识点"
    
    def create_practice_session(self, user_id: str, topic: str, difficulty: int = 3, 
                               question_count: int = 5) -> PracticeSession:
        """
        创建练习会话
        
        Args:
            user_id: 用户ID
            topic: 主题
            difficulty: 难度等级
            question_count: 题目数量
        
        Returns:
            练习会话
        """
        session_id = f"session_{int(time.time() * 1000)}"
        questions = self.generate_quiz(topic, difficulty, question_count)
        
        session = PracticeSession(
            id=session_id,
            user_id=user_id,
            topic=topic,
            questions=questions,
            start_time=time.time()
        )
        
        self._practice_sessions[session_id] = session
        self._logger.info(f"创建练习会话: {session_id} - {topic}")
        return session
    
    def submit_answer(self, session_id: str, question_id: str, user_answer: int,
                      response_time_ms: int = 0) -> QuizResult:
        """
        提交答案
        
        Args:
            session_id: 会话ID
            question_id: 题目ID
            user_answer: 用户答案索引
            response_time_ms: 响应时间（毫秒）
        
        Returns:
            答题结果
        """
        if session_id not in self._practice_sessions:
            raise ValueError(f"会话不存在: {session_id}")
        
        session = self._practice_sessions[session_id]
        
        # 找到题目
        question = next((q for q in session.questions if q.id == question_id), None)
        if not question:
            raise ValueError(f"题目不存在: {question_id}")
        
        # 判断是否正确
        is_correct = (user_answer == question.correct_answer)
        
        # 计算置信度（基于响应时间和正确性）
        confidence = self._calculate_confidence(is_correct, response_time_ms, question.difficulty)
        
        result = QuizResult(
            question_id=question_id,
            user_answer=user_answer,
            is_correct=is_correct,
            confidence=confidence,
            response_time_ms=response_time_ms
        )
        
        session.results.append(result)
        
        # 检查是否完成
        if len(session.results) >= len(session.questions):
            self._complete_session(session)
        
        return result
    
    def _calculate_confidence(self, is_correct: bool, response_time_ms: int, difficulty: int) -> float:
        """计算置信度"""
        base_score = 0.5 if is_correct else 0.2
        
        # 时间因素：越快置信度越高
        time_factor = min(1.0, max(0.3, 1000 / response_time_ms)) if response_time_ms > 0 else 0.7
        
        # 难度因素：高难度答对置信度更高
        difficulty_factor = 1.0 + (difficulty - 3) * 0.1
        
        return min(1.0, base_score * time_factor * difficulty_factor)
    
    def _complete_session(self, session: PracticeSession):
        """完成练习会话"""
        session.end_time = time.time()
        session.completed = True
        
        # 计算掌握分数
        if session.results:
            correct_count = sum(1 for r in session.results if r.is_correct)
            avg_confidence = sum(r.confidence for r in session.results) / len(session.results)
            session.mastery_score = (correct_count / len(session.results)) * 0.7 + avg_confidence * 0.3
        else:
            session.mastery_score = 0.0
        
        # 更新复习计划
        self._update_review_schedule(session)
        
        self._logger.info(f"练习会话完成: {session.id} - 掌握分数: {session.mastery_score:.2f}")
    
    def _update_review_schedule(self, session: PracticeSession):
        """更新复习计划"""
        # 根据掌握分数确定复习间隔
        score = session.mastery_score
        if score >= 0.9:
            interval_idx = 4  # 30天
        elif score >= 0.7:
            interval_idx = 3  # 14天
        elif score >= 0.5:
            interval_idx = 2  # 7天
        elif score >= 0.3:
            interval_idx = 1  # 3天
        else:
            interval_idx = 0  # 1天
        
        interval_hours = self.REVIEW_INTERVALS[interval_idx] * 24
        
        # 创建或更新复习计划
        existing_schedule = next(
            (s for s in self._review_schedules 
             if s.user_id == session.user_id and s.topic == session.topic),
            None
        )
        
        if existing_schedule:
            existing_schedule.next_review_time = time.time() + interval_hours * 3600
            existing_schedule.review_interval_hours = interval_hours
            existing_schedule.review_count += 1
            existing_schedule.last_mastery_score = session.mastery_score
        else:
            schedule = ReviewSchedule(
                user_id=session.user_id,
                topic=session.topic,
                node_id="",
                next_review_time=time.time() + interval_hours * 3600,
                review_interval_hours=interval_hours,
                review_count=1,
                last_mastery_score=session.mastery_score
            )
            self._review_schedules.append(schedule)
    
    def evaluate_mastery(self, user_id: str, topic: str = None) -> Dict:
        """
        评估知识掌握程度
        
        Args:
            user_id: 用户ID
            topic: 主题（可选）
        
        Returns:
            评估结果
        """
        # 获取用户的练习会话
        user_sessions = [
            s for s in self._practice_sessions.values() 
            if s.user_id == user_id and s.completed
        ]
        
        if topic:
            user_sessions = [s for s in user_sessions if s.topic == topic]
        
        if not user_sessions:
            return {
                "user_id": user_id,
                "topic": topic,
                "mastery_score": 0.0,
                "session_count": 0,
                "average_score": 0.0,
                "suggestion": "建议开始练习以评估掌握程度"
            }
        
        # 计算统计数据
        avg_score = sum(s.mastery_score for s in user_sessions) / len(user_sessions)
        session_count = len(user_sessions)
        
        # 生成建议
        suggestion = self._generate_mastery_suggestion(avg_score, topic)
        
        return {
            "user_id": user_id,
            "topic": topic,
            "mastery_score": avg_score,
            "session_count": session_count,
            "average_score": avg_score,
            "suggestion": suggestion
        }
    
    def _generate_mastery_suggestion(self, score: float, topic: str) -> str:
        """生成掌握建议"""
        if score >= 0.9:
            return f"🎉 {topic}掌握优秀！建议尝试更高难度或学习相关主题"
        elif score >= 0.7:
            return f"👍 {topic}掌握良好！建议定期复习保持记忆"
        elif score >= 0.5:
            return f"💪 {topic}掌握一般！建议加强练习，重点关注错题"
        elif score >= 0.3:
            return f"📚 {topic}需要更多练习！建议从基础概念开始复习"
        else:
            return f"🚀 {topic}刚开始学习！建议系统学习基础内容"
    
    def schedule_review(self, user_id: str) -> List[Dict]:
        """
        获取用户的复习计划
        
        Args:
            user_id: 用户ID
        
        Returns:
            复习计划列表
        """
        now = time.time()
        
        # 获取需要复习的主题
        due_schedules = [
            {
                "topic": s.topic,
                "next_review_time": s.next_review_time,
                "is_due": s.next_review_time <= now,
                "review_count": s.review_count,
                "last_score": s.last_mastery_score,
                "interval_hours": s.review_interval_hours
            }
            for s in self._review_schedules if s.user_id == user_id
        ]
        
        # 按时间排序
        due_schedules.sort(key=lambda x: x["next_review_time"])
        
        return due_schedules
    
    def get_practice_session(self, session_id: str) -> Optional[PracticeSession]:
        """获取练习会话"""
        return self._practice_sessions.get(session_id)
    
    def get_question(self, question_id: str) -> Optional[QuizQuestion]:
        """获取题目"""
        return self._questions.get(question_id)


# 单例模式
_active_learning_engine_instance = None

def get_active_learning_engine() -> ActiveLearningEngine:
    """获取主动学习引擎实例"""
    global _active_learning_engine_instance
    if _active_learning_engine_instance is None:
        _active_learning_engine_instance = ActiveLearningEngine()
    return _active_learning_engine_instance


if __name__ == "__main__":
    print("=" * 60)
    print("主动学习引擎测试")
    print("=" * 60)
    
    engine = get_active_learning_engine()
    
    # 1. 生成测验题目
    print("\n[1] 生成测验题目")
    questions = engine.generate_quiz("AI", difficulty=3, count=3)
    for q in questions:
        print(f"题目: {q.question[:50]}...")
        print(f"  选项: {[o[:30] for o in q.options]}")
        print(f"  正确答案: 选项{q.correct_answer + 1}")
    
    # 2. 创建练习会话
    print("\n[2] 创建练习会话")
    session = engine.create_practice_session("user_001", "AI", difficulty=3, question_count=3)
    print(f"会话ID: {session.id}")
    print(f"主题: {session.topic}")
    print(f"题目数量: {len(session.questions)}")
    
    # 3. 模拟答题
    print("\n[3] 模拟答题")
    for i, question in enumerate(session.questions):
        user_answer = question.correct_answer if i % 2 == 0 else (question.correct_answer + 1) % 4
        result = engine.submit_answer(session.id, question.id, user_answer, response_time_ms=2000)
        print(f"题目{i+1}: {'正确' if result.is_correct else '错误'} (置信度: {result.confidence:.2f})")
    
    # 4. 评估掌握程度
    print("\n[4] 评估掌握程度")
    evaluation = engine.evaluate_mastery("user_001", "AI")
    print(f"用户ID: {evaluation['user_id']}")
    print(f"主题: {evaluation['topic']}")
    print(f"掌握分数: {evaluation['mastery_score']:.2f}")
    print(f"练习次数: {evaluation['session_count']}")
    print(f"建议: {evaluation['suggestion']}")
    
    # 5. 获取复习计划
    print("\n[5] 获取复习计划")
    reviews = engine.schedule_review("user_001")
    for review in reviews:
        status = "需要复习" if review["is_due"] else "尚未到期"
        print(f"主题: {review['topic']} - {status} (复习次数: {review['review_count']})")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)