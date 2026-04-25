"""
决策支持系统
Decision Support System

核心功能：
1. 概率情景分析 - 生成乐观/中性/悲观三种情景
2. 个性化策略生成 - 基于用户画像的投资建议
3. 风险收益矩阵 - 量化不同策略的特征
4. 决策框架 - 帮助用户理清思路、量化风险、制定计划

设计原则：
- 不预测，只分析 - 提供框架而非结论
- 量化风险 - 所有建议都有数字支撑
- 合规性 - 严格免责声明
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from dataclasses import asdict
import threading


class ScenarioType(Enum):
    """情景类型"""
    OPTIMISTIC = "optimistic"   # 乐观情景
    NEUTRAL = "neutral"         # 中性情景
    PESSIMISTIC = "pessimistic" # 悲观情景


class StrategyType(Enum):
    """策略类型"""
    AGGRESSIVE = "aggressive"   # 激进
    MODERATE = "moderate"       # 稳健
    CONSERVATIVE = "conservative" # 保守


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class MarketScenario:
    """市场情景"""
    type: str                    # optimistic/neutral/pessimistic
    probability: float          # 概率 (0-1)
    price_target_low: float     # 价格下限
    price_target_high: float    # 价格上限
    timeframe_days: int         # 时间框架（天）
    trigger_conditions: List[str]  # 触发条件
    confirmation_signals: List[str]  # 确认信号
    invalidation_signals: List[str]  # 失效信号
    key_factors: List[str]      # 关键因素
    description: str = ""


@dataclass
class InvestmentStrategy:
    """投资策略"""
    type: str                    # aggressive/moderate/conservative
    name: str                    # 策略名称
    position_ratio: float       # 仓位比例 (0-1)
    entry_price_low: float      # 入场价格下限
    entry_price_high: float     # 入场价格上限
    stop_loss: float             # 止损点
    take_profit: float           # 止盈点
    holding_period_days: int     # 建议持仓时间
    risk_reward_ratio: float    # 风险收益比
    expected_return: float       # 预期收益率
    max_drawdown: float          # 最大回撤估计
    advantages: List[str]        # 优点
    disadvantages: List[str]     # 缺点
    suitable_for: str            # 适合人群
    execution_steps: List[str] = field(default_factory=list)


@dataclass
class RiskRewardMetric:
    """风险收益指标"""
    strategy_name: str
    expected_return: str         # 预期收益
    max_drawdown: str            # 最大回撤
    sharpe_ratio: str             # 夏普比率估计
    win_rate: str                 # 胜率估计
    risk_level: str               # 风险等级
    risk_adjusted_score: float   # 风险调整分数


@dataclass
class UserProfile:
    """用户画像（投资维度）"""
    risk_tolerance: float = 0.5   # 风险承受能力 (0-1)
    investment_experience: str = "beginner"  # beginner/intermediate/experienced
    capital_size: str = "small"   # small/medium/large
    investment_horizon: str = "short"  # short/medium/long
    preferred_sectors: List[str] = field(default_factory=list)
    excluded_sectors: List[str] = field(default_factory=list)
    has_stop_loss_experience: bool = False
    has_margin_experience: bool = False


@dataclass
class DecisionSupportReport:
    """决策支持报告"""
    timestamp: float = field(default_factory=time.time)
    scenarios: List[MarketScenario] = field(default_factory=list)
    strategies: List[InvestmentStrategy] = field(default_factory=list)
    risk_matrix: List[RiskRewardMetric] = field(default_factory=list)
    recommended_strategy: str = ""  # 推荐策略类型
    decision_framework: Dict[str, Any] = field(default_factory=dict)
    disclaimer: str = ""


class DecisionDatabase:
    """决策数据库"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                -- 用户投资画像表
                CREATE TABLE IF NOT EXISTS investment_profiles (
                    user_id TEXT PRIMARY KEY,
                    risk_tolerance REAL DEFAULT 0.5,
                    investment_experience TEXT DEFAULT 'beginner',
                    capital_size TEXT DEFAULT 'small',
                    investment_horizon TEXT DEFAULT 'short',
                    preferred_sectors TEXT DEFAULT '[]',
                    excluded_sectors TEXT DEFAULT '[]',
                    has_stop_loss_experience INTEGER DEFAULT 0,
                    has_margin_experience INTEGER DEFAULT 0,
                    updated_at REAL DEFAULT 0
                );

                -- 决策记录表
                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    symbol TEXT,
                    report_data TEXT NOT NULL,
                    selected_strategy TEXT,
                    execution_status TEXT DEFAULT 'pending',
                    outcome TEXT,
                    created_at REAL DEFAULT 0,
                    updated_at REAL DEFAULT 0
                );

                -- 情景分析历史表
                CREATE TABLE IF NOT EXISTS scenario_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    symbol TEXT,
                    scenario_type TEXT,
                    probability REAL,
                    price_target_low REAL,
                    price_target_high REAL,
                    trigger_conditions TEXT,
                    created_at REAL DEFAULT 0
                );

                -- 策略回测表
                CREATE TABLE IF NOT EXISTS strategy_backtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    symbol TEXT,
                    strategy_type TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    return_pct REAL,
                    holding_days INTEGER,
                    created_at REAL DEFAULT 0
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_decision_user ON decision_records(user_id);
                CREATE INDEX IF NOT EXISTS idx_decision_symbol ON decision_records(symbol);
                CREATE INDEX IF NOT EXISTS idx_scenario_symbol ON scenario_history(symbol);
            """)
            conn.commit()
        finally:
            conn.close()

    def save_profile(self, user_id: str, profile: UserProfile):
        """保存用户画像"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO investment_profiles
                    (user_id, risk_tolerance, investment_experience, capital_size,
                     investment_horizon, preferred_sectors, excluded_sectors,
                     has_stop_loss_experience, has_margin_experience, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, profile.risk_tolerance, profile.investment_experience,
                    profile.capital_size, profile.investment_horizon,
                    json.dumps(profile.preferred_sectors),
                    json.dumps(profile.excluded_sectors),
                    int(profile.has_stop_loss_experience),
                    int(profile.has_margin_experience),
                    time.time()
                ))
                conn.commit()
            finally:
                conn.close()

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT * FROM investment_profiles WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                if row:
                    return UserProfile(
                        risk_tolerance=row[1],
                        investment_experience=row[2],
                        capital_size=row[3],
                        investment_horizon=row[4],
                        preferred_sectors=json.loads(row[5] or "[]"),
                        excluded_sectors=json.loads(row[6] or "[]"),
                        has_stop_loss_experience=bool(row[7]),
                        has_margin_experience=bool(row[8])
                    )
                return None
            finally:
                conn.close()

    def save_decision(
        self,
        user_id: str,
        symbol: str,
        report: DecisionSupportReport,
        selected_strategy: str = ""
    ) -> int:
        """保存决策记录"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("""
                    INSERT INTO decision_records
                    (user_id, symbol, report_data, selected_strategy, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id, symbol,
                    json.dumps(asdict(report), ensure_ascii=False),
                    selected_strategy,
                    time.time()
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_decision_history(
        self,
        user_id: str,
        symbol: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取决策历史"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if symbol:
                    rows = conn.execute("""
                        SELECT * FROM decision_records
                        WHERE user_id = ? AND symbol = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (user_id, symbol, limit)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT * FROM decision_records
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (user_id, limit)).fetchall()

                return [{
                    "id": r[0],
                    "symbol": r[2],
                    "selected_strategy": r[4],
                    "execution_status": r[5],
                    "outcome": r[6],
                    "created_at": r[7]
                } for r in rows]
            finally:
                conn.close()

    def update_decision_outcome(self, decision_id: int, outcome: str, status: str = "completed"):
        """更新决策结果"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    UPDATE decision_records
                    SET outcome = ?, execution_status = ?, updated_at = ?
                    WHERE id = ?
                """, (outcome, status, time.time(), decision_id))
                conn.commit()
            finally:
                conn.close()


class ProbabilityAnalyzer:
    """概率分析器"""

    @staticmethod
    def estimate_scenario_probabilities(
        current_data: Dict[str, Any],
        indicators: Dict[str, Any],
        news_sentiment: float  # -1 到 1
    ) -> Dict[str, float]:
        """
        估算情景概率

        基于技术面、基本面、消息面综合判断
        """
        # 基础概率
        base_prob = {
            "optimistic": 0.25,
            "neutral": 0.50,
            "pessimistic": 0.25
        }

        # 技术面调整
        tech_score = 0  # -1 到 1
        if indicators.get("trend") == "up":
            tech_score += 0.2
        elif indicators.get("trend") == "down":
            tech_score -= 0.2

        if indicators.get("momentum") == "strong":
            tech_score += 0.1

        # 消息面调整
        sentiment_score = news_sentiment  # -1 到 1

        # 综合调整
        total_adjustment = (tech_score + sentiment_score) / 2

        # 调整概率
        adjusted = {
            "optimistic": base_prob["optimistic"] + total_adjustment * 0.1,
            "neutral": base_prob["neutral"],
            "pessimistic": base_prob["pessimistic"] - total_adjustment * 0.1
        }

        # 确保概率合法且总和为1
        for key in adjusted:
            adjusted[key] = max(0.05, min(0.60, adjusted[key]))

        # 归一化
        total = sum(adjusted.values())
        for key in adjusted:
            adjusted[key] = round(adjusted[key] / total, 2)

        return adjusted

    @staticmethod
    def estimate_price_range(
        current_price: float,
        volatility: float,
        scenario_type: str
    ) -> Tuple[float, float]:
        """
        估算价格区间

        Args:
            current_price: 当前价格
            volatility: 波动率 (0-1)
            scenario_type: 情景类型

        Returns:
            (最低价, 最高价)
        """
        if scenario_type == "optimistic":
            factor = 1 + volatility * 0.5
        elif scenario_type == "pessimistic":
            factor = 1 - volatility * 0.4
        else:
            factor = 1 + volatility * 0.1

        high = round(current_price * factor, 2)
        low = round(current_price / factor if scenario_type != "optimistic" else current_price, 2)

        return low, high


class StrategyGenerator:
    """策略生成器"""

    @staticmethod
    def generate_strategies(
        scenarios: List[MarketScenario],
        profile: UserProfile
    ) -> List[InvestmentStrategy]:
        """基于情景和用户画像生成策略"""

        strategies = []

        # 基础价格（从情景中取）
        current_price = 100  # 实际应该从数据中获取
        for s in scenarios:
            if s.type == "neutral":
                current_price = (s.price_target_low + s.price_target_high) / 2
                break

        # 激进策略
        if profile.risk_tolerance >= 0.6:
            strategies.append(InvestmentStrategy(
                type="aggressive",
                name="高胜率突破策略",
                position_ratio=min(0.8, profile.risk_tolerance),
                entry_price_low=current_price * 0.98,
                entry_price_high=current_price * 1.02,
                stop_loss=current_price * 0.92,
                take_profit=current_price * 1.25,
                holding_period_days=14,
                risk_reward_ratio=3.0,
                expected_return=0.20,
                max_drawdown=0.15,
                advantages=["收益潜力大", "适合趋势行情"],
                disadvantages=["止损频繁", "需要严格纪律"],
                suitable_for="有经验的激进投资者"
            ))

        # 稳健策略
        strategies.append(InvestmentStrategy(
            type="moderate",
            name="均值回归策略",
            position_ratio=min(0.5, profile.risk_tolerance * 0.7),
            entry_price_low=current_price * 0.95,
            entry_price_high=current_price * 1.05,
            stop_loss=current_price * 0.90,
            take_profit=current_price * 1.15,
            holding_period_days=30,
            risk_reward_ratio=1.5,
            expected_return=0.10,
            max_drawdown=0.08,
            advantages=["风险适中", "适合震荡行情"],
            disadvantages=["收益有限", "需要耐心"],
            suitable_for="中等风险承受者"
        ))

        # 保守策略
        if profile.risk_tolerance <= 0.5:
            strategies.append(InvestmentStrategy(
                type="conservative",
                name="定投积累策略",
                position_ratio=min(0.3, profile.risk_tolerance * 0.5),
                entry_price_low=current_price * 0.90,
                entry_price_high=current_price * 1.10,
                stop_loss=current_price * 0.80,
                take_profit=current_price * 1.20,
                holding_period_days=90,
                risk_reward_ratio=1.0,
                expected_return=0.05,
                max_drawdown=0.05,
                advantages=["风险低", "适合长期持有"],
                disadvantages=["收益较慢", "机会成本"],
                suitable_for="保守型投资者"
            ))

        return strategies

    @staticmethod
    def calculate_risk_metrics(
        strategies: List[InvestmentStrategy],
        scenarios: List[MarketScenario]
    ) -> List[RiskRewardMetric]:
        """计算风险收益指标"""

        metrics = []

        for strategy in strategies:
            # 估算夏普比率（简化版）
            if strategy.risk_reward_ratio > 2:
                sharpe = 1.5
            elif strategy.risk_reward_ratio > 1:
                sharpe = 1.0
            else:
                sharpe = 0.5

            # 估算胜率
            win_rate = 1 / (1 + strategy.risk_reward_ratio)

            # 风险等级
            if strategy.max_drawdown < 0.05:
                risk_level = "低"
            elif strategy.max_drawdown < 0.10:
                risk_level = "中"
            else:
                risk_level = "高"

            # 风险调整分数
            risk_adjusted = strategy.expected_return / max(strategy.max_drawdown, 0.01)

            metrics.append(RiskRewardMetric(
                strategy_name=strategy.name,
                expected_return=f"{strategy.expected_return:.1%}",
                max_drawdown=f"{strategy.max_drawdown:.1%}",
                sharpe_ratio=f"{sharpe:.2f}",
                win_rate=f"{win_rate:.1%}",
                risk_level=risk_level,
                risk_adjusted_score=risk_adjusted
            ))

        return metrics


class DecisionSupportEngine:
    """
    决策支持引擎

    功能：
    - 生成概率情景分析
    - 创建个性化投资策略
    - 计算风险收益矩阵
    - 构建决策框架
    """

    DEFAULT_DISCLAIMER = """
⚠️ 【重要免责声明】

本系统提供的分析基于公开数据和概率模型，不构成投资建议。

• 市场有风险，决策需谨慎
• 您的投资决策应基于自身独立判断
• 过去表现不代表未来收益
• 请根据自身风险承受能力理性投资

如有任何疑问，请咨询专业的金融顾问。
    """.strip()

    def __init__(self, db_path: str | Path = None):
        from client.src.business.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "decision_support.db"

        self.db = DecisionDatabase(db_path)
        self.probability_analyzer = ProbabilityAnalyzer()
        self.strategy_generator = StrategyGenerator()

    def generate_analysis(
        self,
        symbol: str,
        current_price: float,
        current_data: Dict[str, Any],
        indicators: Dict[str, Any],
        news: List[str],
        news_sentiment: float,
        user_profile: UserProfile = None
    ) -> DecisionSupportReport:
        """
        生成完整的决策支持报告

        Args:
            symbol: 标的代码
            current_price: 当前价格
            current_data: 当前市场数据
            indicators: 技术指标
            news: 最新消息列表
            news_sentiment: 消息情绪 (-1 到 1)
            user_profile: 用户画像

        Returns:
            DecisionSupportReport
        """

        # 使用默认用户画像
        if user_profile is None:
            user_profile = UserProfile()

        # 1. 估算情景概率
        probabilities = self.probability_analyzer.estimate_scenario_probabilities(
            current_data, indicators, news_sentiment
        )

        # 波动率（从指标中获取或估算）
        volatility = indicators.get("volatility", 0.15)

        # 2. 生成情景
        scenarios = []
        for scenario_type in ["optimistic", "neutral", "pessimistic"]:
            prob = probabilities[scenario_type]
            price_low, price_high = self.probability_analyzer.estimate_price_range(
                current_price, volatility, scenario_type
            )

            # 时间框架
            timeframe = {
                "optimistic": 14,
                "neutral": 30,
                "pessimistic": 21
            }[scenario_type]

            scenario = MarketScenario(
                type=scenario_type,
                probability=prob,
                price_target_low=price_low,
                price_target_high=price_high,
                timeframe_days=timeframe,
                trigger_conditions=self._generate_triggers(scenario_type, indicators),
                confirmation_signals=self._generate_confirmations(scenario_type),
                invalidation_signals=self._generate_invalidations(scenario_type),
                key_factors=self._extract_key_factors(news, indicators),
                description=self._generate_scenario_description(
                    scenario_type, prob, price_low, price_high
                )
            )
            scenarios.append(scenario)

        # 3. 生成策略
        strategies = self.strategy_generator.generate_strategies(scenarios, user_profile)

        # 4. 计算风险收益矩阵
        risk_matrix = self.strategy_generator.calculate_risk_metrics(strategies, scenarios)

        # 5. 推荐策略
        recommended = self._recommend_strategy(user_profile, strategies)

        # 6. 构建决策框架
        framework = self._build_decision_framework(
            symbol, scenarios, strategies, recommended
        )

        return DecisionSupportReport(
            scenarios=scenarios,
            strategies=strategies,
            risk_matrix=risk_matrix,
            recommended_strategy=recommended.type if recommended else "",
            decision_framework=framework,
            disclaimer=self.DEFAULT_DISCLAIMER
        )

    def save_decision(
        self,
        user_id: str,
        symbol: str,
        report: DecisionSupportReport,
        selected_strategy: str = ""
    ) -> int:
        """保存决策记录"""
        return self.db.save_decision(user_id, symbol, report, selected_strategy)

    def get_user_profile(self, user_id: str) -> UserProfile:
        """获取用户画像"""
        profile = self.db.get_profile(user_id)
        return profile if profile else UserProfile()

    def save_user_profile(self, user_id: str, profile: UserProfile):
        """保存用户画像"""
        self.db.save_profile(user_id, profile)

    def get_decision_history(
        self,
        user_id: str,
        symbol: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取决策历史"""
        return self.db.get_decision_history(user_id, symbol, limit)

    def update_decision_outcome(self, decision_id: int, outcome: str):
        """更新决策结果"""
        self.db.update_decision_outcome(decision_id, outcome)

    # === 辅助方法 ===

    def _generate_triggers(self, scenario_type: str, indicators: Dict) -> List[str]:
        """生成触发条件"""
        base_triggers = {
            "optimistic": [
                "放量突破关键阻力位",
                "利好消息持续发酵",
                "技术指标形成金叉"
            ],
            "neutral": [
                "维持当前震荡区间",
                "没有明显突破信号",
                "多空力量相对平衡"
            ],
            "pessimistic": [
                "跌破关键支撑位",
                "出现利空消息",
                "技术指标形成死叉"
            ]
        }
        return base_triggers.get(scenario_type, [])

    def _generate_confirmations(self, scenario_type: str) -> List[str]:
        """生成确认信号"""
        return {
            "optimistic": [
                "连续3日收阳线",
                "成交量放大至均量1.5倍",
                "突破20日均线"
            ],
            "neutral": [
                "价格稳定在均线附近",
                "成交量萎缩",
                "波动率下降"
            ],
            "pessimistic": [
                "连续3日收阴线",
                "成交量放大",
                "跌破所有均线"
            ]
        }.get(scenario_type, [])

    def _generate_invalidations(self, scenario_type: str) -> List[str]:
        """生成失效信号"""
        return {
            "optimistic": [
                "价格回落到入场点以下",
                "成交量萎缩",
                "出现反向消息"
            ],
            "neutral": [
                "大幅突破区间",
                "成交量异常放大",
                "出现重大消息"
            ],
            "pessimistic": [
                "价格反弹至入场点以上",
                "出现利好消息",
                "技术指标背离"
            ]
        }.get(scenario_type, [])

    def _extract_key_factors(
        self,
        news: List[str],
        indicators: Dict
    ) -> List[str]:
        """提取关键因素"""
        factors = []

        # 从消息中提取
        for n in news[:3]:
            if len(n) > 10:
                factors.append(n[:50] + "..." if len(n) > 50 else n)

        # 从指标中提取
        if indicators.get("trend"):
            factors.append(f"趋势: {indicators['trend']}")
        if indicators.get("support"):
            factors.append(f"支撑位: {indicators['support']}")
        if indicators.get("resistance"):
            factors.append(f"阻力位: {indicators['resistance']}")

        return factors[:5]

    def _generate_scenario_description(
        self,
        scenario_type: str,
        probability: float,
        price_low: float,
        price_high: float
    ) -> str:
        """生成情景描述"""
        prob_pct = probability * 100
        type_names = {
            "optimistic": "乐观",
            "neutral": "中性",
            "pessimistic": "悲观"
        }

        return (
            f"{type_names[scenario_type]}情景发生的概率约为 {prob_pct:.0f}%。"
            f"在此情景下，预计价格将在 {price_low:.2f} 至 {price_high:.2f} 之间波动。"
        )

    def _recommend_strategy(
        self,
        profile: UserProfile,
        strategies: List[InvestmentStrategy]
    ) -> Optional[InvestmentStrategy]:
        """推荐策略"""
        if profile.risk_tolerance >= 0.7:
            for s in strategies:
                if s.type == "aggressive":
                    return s
        elif profile.risk_tolerance >= 0.4:
            for s in strategies:
                if s.type == "moderate":
                    return s
        else:
            for s in strategies:
                if s.type == "conservative":
                    return s

        return strategies[0] if strategies else None

    def _build_decision_framework(
        self,
        symbol: str,
        scenarios: List[MarketScenario],
        strategies: List[InvestmentStrategy],
        recommended: InvestmentStrategy
    ) -> Dict[str, Any]:
        """构建决策框架"""

        framework = {
            "title": f"{symbol} 投资决策框架",
            "steps": [
                {
                    "step": 1,
                    "title": "理解现状",
                    "content": "综合技术面、基本面、消息面，评估当前市场状态",
                    "scenarios": [s.type for s in scenarios],
                    "probability_summary": {
                        s.type: f"{s.probability:.0%}" for s in scenarios
                    }
                },
                {
                    "step": 2,
                    "title": "评估风险",
                    "content": "使用止损和仓位管理控制风险",
                    "strategies": [
                        {
                            "type": s.type,
                            "stop_loss": s.stop_loss,
                            "max_position": s.position_ratio
                        }
                        for s in strategies
                    ]
                },
                {
                    "step": 3,
                    "title": "制定策略",
                    "content": "根据风险承受能力选择合适的策略",
                    "recommended": recommended.type if recommended else "none",
                    "recommended_name": recommended.name if recommended else ""
                },
                {
                    "step": 4,
                    "title": "执行与复盘",
                    "content": "设定触发条件，确认信号和失效信号",
                    "action_plan": [
                        "设定入场点",
                        "设定止损点",
                        "设定止盈点",
                        "记录决策理由",
                        "定期复盘"
                    ]
                }
            ],
            "key_questions": [
                "我的风险承受能力是多少？",
                "我的投资周期是多长？",
                "如果止损被触发，我能承受多大损失？",
                "我是否理解了所有可能的情景？"
            ]
        }

        return framework

    def format_report_text(self, report: DecisionSupportReport) -> str:
        """格式化报告为文本"""

        lines = []

        # 标题
        lines.append("=" * 50)
        lines.append("📊 决策支持报告")
        lines.append("=" * 50)
        lines.append("")

        # 情景分析
        lines.append("📈 情景概率分析")
        lines.append("-" * 30)
        for scenario in report.scenarios:
            emoji = {"optimistic": "🟢", "neutral": "🟡", "pessimistic": "🔴"}.get(scenario.type, "⚪")
            lines.append(f"{emoji} {scenario.type.upper()}: {scenario.probability:.0%}")
            lines.append(f"   价格区间: {scenario.price_target_low:.2f} - {scenario.price_target_high:.2f}")
            lines.append(f"   时间框架: {scenario.timeframe_days}天")
            lines.append(f"   {scenario.description}")
            lines.append("")

        # 策略建议
        lines.append("🎯 个性化策略建议")
        lines.append("-" * 30)
        for strategy in report.strategies:
            lines.append(f"\n【{strategy.name}】({strategy.type})")
            lines.append(f"  仓位: {strategy.position_ratio:.0%}")
            lines.append(f"  入场: {strategy.entry_price_low:.2f} - {strategy.entry_price_high:.2f}")
            lines.append(f"  止损: {strategy.stop_loss:.2f}")
            lines.append(f"  止盈: {strategy.take_profit:.2f}")
            lines.append(f"  预期收益: {strategy.expected_return:.1%}")
            lines.append(f"  最大回撤: {strategy.max_drawdown:.1%}")
            lines.append(f"  适合: {strategy.suitable_for}")

        # 风险矩阵
        lines.append("\n\n📉 风险收益矩阵")
        lines.append("-" * 30)
        lines.append(f"{'策略':<20} {'预期收益':>10} {'最大回撤':>10} {'夏普比率':>10} {'风险':>6}")
        lines.append("-" * 50)
        for metric in report.risk_matrix:
            lines.append(
                f"{metric.strategy_name:<18} "
                f"{metric.expected_return:>10} "
                f"{metric.max_drawdown:>10} "
                f"{metric.sharpe_ratio:>10} "
                f"{metric.risk_level:>6}"
            )

        # 推荐
        if report.recommended_strategy:
            lines.append(f"\n✅ 推荐策略: {report.recommended_strategy}")

        # 免责声明
        lines.append("\n" + "=" * 50)
        lines.append(report.disclaimer)

        return "\n".join(lines)


# 单例
_decision_engine: Optional[DecisionSupportEngine] = None


def get_decision_engine() -> DecisionSupportEngine:
    """获取决策支持引擎单例"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionSupportEngine()
    return _decision_engine
