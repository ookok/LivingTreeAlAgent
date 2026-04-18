"""
最短路径引导系统 - Shortest Path Guide

核心理念：找到从当前状态到目标功能的最短配置路径

功能：
1. 配置路径发现 - 自动寻找最简单的配置方案
2. 智能引导流程 - 根据用户画像定制引导
3. 进度保存与恢复 - 随时中断，随时继续
4. 浏览器自动化 - 辅助第三方网站注册

使用示例：
    guide = ShortestPathGuide()
    
    # 创建引导流程
    flow = guide.create_guide_flow("weather_api")
    print(f"需要 {len(flow.steps)} 步完成")
    
    # 执行引导
    result = await guide.execute_guide(flow)
"""

import os
import json
import logging
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StepType(Enum):
    """步骤类型"""
    VISIT_URL = "visit_url"          # 访问URL
    COPY_TEXT = "copy_text"          # 复制文本
    PASTE_TEXT = "paste_text"        # 粘贴文本
    OPEN_APP = "open_app"           # 打开应用
    INPUT_TEXT = "input_text"        # 输入文本
    CLICK_BUTTON = "click_button"    # 点击按钮
    WAIT_FOR = "wait_for"           # 等待某个元素
    VALIDATE = "validate"           # 验证配置
    RUN_COMMAND = "run_command"     # 运行命令


@dataclass
class GuideStep:
    """
    引导步骤
    
    Attributes:
        step_id: 步骤ID
        title: 标题
        description: 描述
        step_type: 步骤类型
        action: 执行动作
        target: 目标（URL、元素选择器等）
        expected_result: 期望结果
        time_estimate: 预估时间（秒）
        skippable: 是否可跳过
        auto_detect: 是否自动检测完成
        validation_func: 验证函数
    """
    step_id: str
    title: str
    description: str
    step_type: StepType = StepType.VISIT_URL
    action: Optional[Dict[str, Any]] = None
    target: Optional[str] = None
    expected_result: str = ""
    time_estimate: int = 30
    skippable: bool = True
    auto_detect: bool = True
    validation_func: Optional[Callable] = None
    status: StepStatus = StepStatus.PENDING
    error_message: str = ""
    completed_at: Optional[str] = None


@dataclass
class GuideFlow:
    """
    引导流程
    
    Attributes:
        flow_id: 流程ID
        feature_id: 功能标识符
        name: 流程名称
        description: 描述
        steps: 步骤列表
        current_step_index: 当前步骤索引
        created_at: 创建时间
        estimated_total_time: 预估总时间
        simplicity_score: 简单度评分
    """
    flow_id: str
    feature_id: str
    name: str
    description: str
    steps: List[GuideStep] = field(default_factory=list)
    current_step_index: int = 0
    created_at: str = ""
    estimated_total_time: int = 0
    simplicity_score: float = 0.0
    guide_type: str = "step_by_step"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.steps and self.estimated_total_time == 0:
            self.estimated_total_time = sum(s.time_estimate for s in self.steps)
    
    def get_current_step(self) -> Optional[GuideStep]:
        """获取当前步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def get_next_step(self) -> Optional[GuideStep]:
        """获取下一步"""
        next_index = self.current_step_index + 1
        if 0 <= next_index < len(self.steps):
            return self.steps[next_index]
        return None
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度"""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        total = len(self.steps)
        return {
            "current": self.current_step_index + 1,
            "total": total,
            "completed": completed,
            "percentage": (completed / total * 100) if total > 0 else 0,
            "current_step": self.get_current_step().title if self.get_current_step() else None,
        }
    
    def is_completed(self) -> bool:
        """是否完成"""
        return all(s.status == StepStatus.COMPLETED for s in self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "flow_id": self.flow_id,
            "feature_id": self.feature_id,
            "name": self.name,
            "description": self.description,
            "current_step_index": self.current_step_index,
            "created_at": self.created_at,
            "estimated_total_time": self.estimated_total_time,
            "simplicity_score": self.simplicity_score,
            "guide_type": self.guide_type,
            "progress": self.get_progress(),
        }


@dataclass
class GuideProgress:
    """
    引导进度
    
    用于保存和恢复引导进度
    """
    user_id: str
    guide_id: str
    flow_id: str
    current_step_index: int
    completed_steps: List[str]
    context_data: Dict[str, Any]
    timestamp: str
    estimated_remaining: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "guide_id": self.guide_id,
            "flow_id": self.flow_id,
            "current_step_index": self.current_step_index,
            "completed_steps": self.completed_steps,
            "context_data": self.context_data,
            "timestamp": self.timestamp,
            "estimated_remaining": self.estimated_remaining,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuideProgress":
        """从字典创建"""
        return cls(
            user_id=data["user_id"],
            guide_id=data["guide_id"],
            flow_id=data["flow_id"],
            current_step_index=data["current_step_index"],
            completed_steps=data.get("completed_steps", []),
            context_data=data.get("context_data", {}),
            timestamp=data.get("timestamp", ""),
            estimated_remaining=data.get("estimated_remaining", 0),
        )


class ShortestPathGuide:
    """
    最短路径引导系统
    
    核心功能：
    1. 发现所有配置路径
    2. 计算简单度评分
    3. 选择最短路径
    4. 执行引导流程
    """
    
    _instance: Optional["ShortestPathGuide"] = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._progress_store_path = Path.home() / ".hermes" / "guide_progress"
        self._progress_store_path.mkdir(parents=True, exist_ok=True)
        
        # 已知的配置路径模板
        self._config_path_templates: Dict[str, List[Dict]] = {}
        self._init_config_templates()
        
        self._initialized = True
        logger.info("ShortestPathGuide initialized")
    
    def _init_config_templates(self):
        """初始化配置路径模板"""
        
        # OpenWeatherMap API Key 配置路径
        self._config_path_templates["weather_api"] = [
            {
                "name": "OpenWeatherMap (推荐)",
                "guide_type": "one_click",
                "steps": [
                    GuideStep(
                        step_id="step_1",
                        title="打开注册页面",
                        description="点击下方按钮跳转到OpenWeatherMap注册页面",
                        step_type=StepType.VISIT_URL,
                        target="https://openweathermap.org/signup",
                        time_estimate=10,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="step_2",
                        title="注册账号",
                        description="使用邮箱注册一个免费账号",
                        step_type=StepType.VISIT_URL,
                        target="https://openweathermap.org/signup",
                        expected_result="注册成功，跳转到API Keys页面",
                        time_estimate=120,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="step_3",
                        title="复制API Key",
                        description="在API Keys页面复制您的API Key",
                        step_type=StepType.COPY_TEXT,
                        target="input[name='api_key']",
                        expected_result="API Key已复制到剪贴板",
                        time_estimate=30,
                        auto_detect=True,
                    ),
                    GuideStep(
                        step_id="step_4",
                        title="自动配置",
                        description="系统将自动检测并填入API Key",
                        step_type=StepType.PASTE_TEXT,
                        target="config.openweather_api_key",
                        expected_result="API Key配置成功",
                        time_estimate=10,
                        auto_detect=True,
                    ),
                ],
                "simplicity_score": 0.95,
                "time_estimate": 180,
                "success_rate": 0.95,
                "is_free": True,
            },
            {
                "name": "手动配置",
                "guide_type": "step_by_step",
                "steps": [
                    GuideStep(
                        step_id="manual_1",
                        title="打开配置文件",
                        description="找到并打开配置文件",
                        step_type=StepType.OPEN_APP,
                        target="~/.hermes/config.yaml",
                        time_estimate=30,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="manual_2",
                        title="添加API Key",
                        description="在配置文件中添加 openweather_api_key: YOUR_KEY",
                        step_type=StepType.INPUT_TEXT,
                        target="config.yaml",
                        time_estimate=60,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="manual_3",
                        title="验证配置",
                        description="保存并验证配置是否正确",
                        step_type=StepType.VALIDATE,
                        target="config.openweather_api_key",
                        time_estimate=30,
                        auto_detect=True,
                    ),
                ],
                "simplicity_score": 0.5,
                "time_estimate": 120,
                "success_rate": 0.7,
                "is_free": True,
            },
        ]
        
        # 高德地图配置路径
        self._config_path_templates["map_service"] = [
            {
                "name": "高德地图 (国内推荐)",
                "guide_type": "one_click",
                "steps": [
                    GuideStep(
                        step_id="amap_1",
                        title="打开高德开放平台",
                        description="访问高德开放平台注册开发者账号",
                        step_type=StepType.VISIT_URL,
                        target="https://lbs.amap.com/dev/key/app",
                        time_estimate=10,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="amap_2",
                        title="创建应用获取Key",
                        description="创建一个应用并获取Web服务API Key",
                        step_type=StepType.VISIT_URL,
                        target="https://console.amap.com/dev/key/app",
                        expected_result="获得API Key",
                        time_estimate=60,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="amap_3",
                        title="配置Key",
                        description="将Key填入系统配置",
                        step_type=StepType.PASTE_TEXT,
                        target="config.amap_api_key",
                        time_estimate=10,
                        auto_detect=True,
                    ),
                ],
                "simplicity_score": 0.9,
                "time_estimate": 80,
                "success_rate": 0.9,
                "is_free": True,
            },
        ]
        
        # OpenAI API Key 配置路径
        self._config_path_templates["openai_api"] = [
            {
                "name": "OpenAI API Key (推荐)",
                "guide_type": "one_click",
                "steps": [
                    GuideStep(
                        step_id="openai_1",
                        title="打开API Key页面",
                        description="访问OpenAI平台获取API Key",
                        step_type=StepType.VISIT_URL,
                        target="https://platform.openai.com/api-keys",
                        time_estimate=10,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="openai_2",
                        title="创建API Key",
                        description="点击 Create new secret key 按钮创建Key",
                        step_type=StepType.CLICK_BUTTON,
                        target="button:contains('Create new secret key')",
                        time_estimate=30,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="openai_3",
                        title="复制并配置",
                        description="复制生成的API Key，系统将自动配置",
                        step_type=StepType.PASTE_TEXT,
                        target="config.openai_api_key",
                        expected_result="API Key配置成功",
                        time_estimate=20,
                        auto_detect=True,
                    ),
                ],
                "simplicity_score": 0.9,
                "time_estimate": 60,
                "success_rate": 0.9,
                "is_free": False,
            },
        ]
        
        # Ollama 本地模型配置
        self._config_path_templates["ollama"] = [
            {
                "name": "自动安装 Ollama (推荐)",
                "guide_type": "one_click",
                "steps": [
                    GuideStep(
                        step_id="ollama_1",
                        title="下载安装包",
                        description="系统将自动下载 Ollama 安装包",
                        step_type=StepType.VISIT_URL,
                        target="https://ollama.com/download",
                        time_estimate=60,
                        auto_detect=False,
                    ),
                    GuideStep(
                        step_id="ollama_2",
                        title="运行安装",
                        description="下载完成后运行安装程序",
                        step_type=StepType.RUN_COMMAND,
                        target="ollama",
                        expected_result="Ollama 安装成功",
                        time_estimate=120,
                        auto_detect=True,
                    ),
                    GuideStep(
                        step_id="ollama_3",
                        title="拉取模型",
                        description="安装推荐模型 qwen2.5:7b",
                        step_type=StepType.RUN_COMMAND,
                        target="ollama pull qwen2.5:7b",
                        expected_result="模型下载完成",
                        time_estimate=300,
                        auto_detect=True,
                    ),
                ],
                "simplicity_score": 0.85,
                "time_estimate": 480,
                "success_rate": 0.85,
                "is_free": True,
            },
        ]
    
    def find_all_paths(self, feature_id: str) -> List[Dict]:
        """
        找到目标功能的所有配置路径
        
        Args:
            feature_id: 功能标识符
        
        Returns:
            配置路径列表
        """
        return self._config_path_templates.get(feature_id, [])
    
    def calculate_simplicity(
        self, 
        path: Dict, 
        user_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        计算路径简单度分数
        
        考虑因素：
        - 步骤数量
        - 预估时间
        - 是否免费
        - 历史成功率
        - 用户技术等级
        
        Args:
            path: 配置路径
            user_context: 用户上下文
        
        Returns:
            简单度分数 (0-1)
        """
        user_context = user_context or {}
        
        # 基础因素
        steps_weight = 0.3
        time_weight = 0.2
        cost_weight = 0.2
        success_rate_weight = 0.2
        complexity_weight = 0.1
        
        # 1. 步骤数因素
        steps = path.get("steps", [])
        num_steps = len(steps)
        steps_score = max(0, 1 - (num_steps - 1) * 0.2)  # 1步=1.0, 2步=0.8, 3步=0.6...
        
        # 2. 时间因素
        time_estimate = path.get("time_estimate", 0)
        time_score = max(0, 1 - (time_estimate - 60) / 600)  # 1分钟=1.0, 10分钟=0.0
        
        # 3. 费用因素
        is_free = path.get("is_free", True)
        cost_score = 1.0 if is_free else 0.5
        
        # 4. 历史成功率
        success_rate = path.get("success_rate", 0.8)
        
        # 5. 复杂度（引导类型）
        guide_type = path.get("guide_type", "step_by_step")
        complexity_scores = {
            "one_click": 1.0,
            "step_by_step": 0.7,
            "config_file": 0.5,
            "video_tutorial": 0.4,
        }
        complexity_score = complexity_scores.get(guide_type, 0.5)
        
        # 综合评分
        total_score = (
            steps_score * steps_weight +
            time_score * time_weight +
            cost_score * cost_weight +
            success_rate * success_rate_weight +
            complexity_score * complexity_weight
        )
        
        return round(total_score, 3)
    
    def find_shortest_path(
        self, 
        feature_id: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[GuideFlow]:
        """
        找到最短配置路径
        
        Args:
            feature_id: 功能标识符
            user_context: 用户上下文（用于个性化）
        
        Returns:
            GuideFlow 或 None
        """
        all_paths = self.find_all_paths(feature_id)
        
        if not all_paths:
            logger.warning("No config paths found for feature: %s", feature_id)
            return None
        
        # 计算每个路径的简单度
        scored_paths = []
        for path in all_paths:
            score = self.calculate_simplicity(path, user_context)
            scored_paths.append((score, path))
        
        # 按简单度排序
        scored_paths.sort(key=lambda x: x[0], reverse=True)
        
        # 选择最简单路径
        best_score, best_path = scored_paths[0]
        
        # 创建 GuideFlow
        flow = self._create_flow_from_path(feature_id, best_path)
        flow.simplicity_score = best_score
        
        return flow
    
    def _create_flow_from_path(self, feature_id: str, path: Dict) -> GuideFlow:
        """从路径字典创建 GuideFlow"""
        steps = path.get("steps", [])
        
        guide_flow = GuideFlow(
            flow_id=f"{feature_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            feature_id=feature_id,
            name=path.get("name", "配置引导"),
            description=path.get("description", ""),
            steps=steps,
            guide_type=path.get("guide_type", "step_by_step"),
            estimated_total_time=path.get("time_estimate", 0),
            simplicity_score=path.get("simplicity_score", 0.5),
        )
        
        return guide_flow
    
    def create_guide_flow(
        self, 
        feature_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        preferred_guide_type: Optional[str] = None
    ) -> Optional[GuideFlow]:
        """
        创建引导流程（主入口）
        
        Args:
            feature_id: 功能标识符
            user_context: 用户上下文
            preferred_guide_type: 偏好的引导类型
        
        Returns:
            GuideFlow 或 None
        """
        # 如果指定了引导类型，优先选择该类型
        if preferred_guide_type:
            all_paths = self.find_all_paths(feature_id)
            for path in all_paths:
                if path.get("guide_type") == preferred_guide_type:
                    flow = self._create_flow_from_path(feature_id, path)
                    flow.simplicity_score = self.calculate_simplicity(path, user_context)
                    return flow
        
        # 否则选择最短路径
        return self.find_shortest_path(feature_id, user_context)
    
    def save_progress(self, progress: GuideProgress) -> bool:
        """
        保存引导进度
        
        Args:
            progress: 引导进度
        
        Returns:
            是否保存成功
        """
        try:
            file_path = self._progress_store_path / f"{progress.user_id}_{progress.guide_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(progress.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Guide progress saved: %s", file_path)
            return True
        except Exception as e:
            logger.error("Failed to save guide progress: %s", e)
            return False
    
    def load_progress(self, user_id: str, guide_id: str) -> Optional[GuideProgress]:
        """
        加载引导进度
        
        Args:
            user_id: 用户ID
            guide_id: 引导ID
        
        Returns:
            GuideProgress 或 None
        """
        try:
            file_path = self._progress_store_path / f"{user_id}_{guide_id}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return GuideProgress.from_dict(data)
        except Exception as e:
            logger.error("Failed to load guide progress: %s", e)
        
        return None
    
    def delete_progress(self, user_id: str, guide_id: str) -> bool:
        """
        删除引导进度
        
        Args:
            user_id: 用户ID
            guide_id: 引导ID
        
        Returns:
            是否删除成功
        """
        try:
            file_path = self._progress_store_path / f"{user_id}_{guide_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            logger.error("Failed to delete guide progress: %s", e)
            return False
    
    def resume_flow(self, user_id: str, guide_id: str) -> Optional[GuideFlow]:
        """
        恢复引导流程
        
        Args:
            user_id: 用户ID
            guide_id: 引导ID
        
        Returns:
            GuideFlow 或 None
        """
        progress = self.load_progress(user_id, guide_id)
        
        if progress is None:
            return None
        
        # 重建流程
        feature_id = progress.flow_id.split("_")[0]
        flow = self.create_guide_flow(feature_id)
        
        if flow:
            flow.current_step_index = progress.current_step_index
        
        return flow
    
    def get_step_action(self, step: GuideStep) -> Dict[str, Any]:
        """
        获取步骤执行动作
        
        返回用于UI或自动化的动作指令
        """
        action = {
            "type": step.step_type.value,
            "target": step.target,
            "title": step.title,
            "description": step.description,
            "auto_detect": step.auto_detect,
        }
        
        if step.step_type == StepType.VISIT_URL:
            action["url"] = step.target
            action["auto_open"] = True
        elif step.step_type == StepType.COPY_TEXT:
            action["selector"] = step.target
        elif step.step_type == StepType.PASTE_TEXT:
            action["config_key"] = step.target
        elif step.step_type == StepType.VALIDATE:
            action["validation_key"] = step.target
        
        return action
    
    def validate_step_completion(
        self, 
        step: GuideStep, 
        context: Dict[str, Any]
    ) -> bool:
        """
        验证步骤是否完成
        
        Args:
            step: 引导步骤
            context: 执行上下文
        
        Returns:
            是否完成
        """
        if step.validation_func:
            return step.validation_func(context)
        
        # 自动检测逻辑
        if step.auto_detect:
            if step.step_type == StepType.PASTE_TEXT:
                # 检查配置是否已填入
                config_key = step.target
                value = context.get(config_key)
                return value is not None and value != ""
            elif step.step_type == StepType.VALIDATE:
                # 检查配置是否有效
                config_key = step.target
                value = context.get(config_key)
                return value is not None and value != ""
        
        # 手动确认
        return step.status == StepStatus.COMPLETED
    
    def get_alternative_paths(self, feature_id: str) -> List[Dict]:
        """获取备选路径"""
        return self._config_path_templates.get(feature_id, [])[1:]  # 排除第一个（最短路径）
    
    def register_config_path(self, feature_id: str, path: Dict):
        """
        注册新的配置路径
        
        Args:
            feature_id: 功能标识符
            path: 配置路径定义
        """
        if feature_id not in self._config_path_templates:
            self._config_path_templates[feature_id] = []
        
        self._config_path_templates[feature_id].append(path)
    
    def get_supported_features(self) -> List[str]:
        """获取支持的功能列表"""
        return list(self._config_path_templates.keys())


# 全局实例
_guide: Optional[ShortestPathGuide] = None


def get_shortest_path_guide() -> ShortestPathGuide:
    """获取最短路径引导系统全局实例"""
    global _guide
    if _guide is None:
        _guide = ShortestPathGuide()
    return _guide