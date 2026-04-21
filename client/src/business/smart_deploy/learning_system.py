"""
新手学习系统 - LearningSystem
核心理念：为每行代码提供三层解释

功能：
1. 生活化比喻（让新手理解概念）
2. 技术原理说明（让进阶者理解机制）
3. 最佳实践建议（让专家优化方案）

游戏化学习：
- 技能树解锁
- 成就系统
- 每日任务
- 进度追踪
"""

import json
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SkillLevel(Enum):
    """技能等级"""
    BEGINNER = "beginner"      # 萌新
    JUNIOR = "junior"          # 见习
    INTERMEDIATE = "intermediate"  # 熟练
    ADVANCED = "advanced"      # 精英
    EXPERT = "expert"          # 专家


@dataclass
class Explanation:
    """三层解释"""
    metaphor: str              # 生活化比喻
    technical: str             # 技术原理
    best_practice: str         # 最佳实践
    code_example: Optional[str] = None


@dataclass
class Skill:
    """技能"""
    skill_id: str
    name: str
    description: str
    category: str
    level_required: SkillLevel
    xp_required: int
    prerequisites: List[str]
    is_unlocked: bool = False
    is_mastered: bool = False
    current_xp: int = 0


@dataclass
class Achievement:
    """成就"""
    achievement_id: str
    name: str
    description: str
    icon: str
    xp_reward: int
    is_unlocked: bool = False
    unlocked_at: Optional[datetime] = None


@dataclass
class DailyTask:
    """每日任务"""
    task_id: str
    name: str
    description: str
    xp_reward: int
    is_completed: bool = False
    progress: float = 0.0


@dataclass
class UserProgress:
    """用户进度"""
    total_xp: int = 0
    level: SkillLevel = SkillLevel.BEGINNER
    skills: Dict[str, Skill] = field(default_factory=dict)
    achievements: Dict[str, Achievement] = field(default_factory=dict)
    daily_tasks: List[DailyTask] = field(default_factory=list)
    streak_days: int = 0
    last_active_date: Optional[datetime] = None


class LearningSystem:
    """
    新手学习系统

    提供三层解释和游戏化学习体验
    """

    def __init__(self):
        self._progress = UserProgress()
        self._explanation_cache: Dict[str, Explanation] = {}
        self._skill_tree = self._build_skill_tree()
        self._achievement_list = self._build_achievements()
        self._daily_tasks = self._build_daily_tasks()
        self._listeners: List[Callable] = []
        self._lock = threading.Lock()

    def _build_skill_tree(self) -> Dict[str, Skill]:
        """构建技能树"""
        return {
            "linux_basics": Skill(
                skill_id="linux_basics",
                name="Linux基础",
                description="掌握Linux基本命令",
                category="操作系统",
                level_required=SkillLevel.BEGINNER,
                xp_required=0,
                prerequisites=[]
            ),
            "shell_scripting": Skill(
                skill_id="shell_scripting",
                name="Shell脚本",
                description="编写自动化Shell脚本",
                category="操作系统",
                level_required=SkillLevel.JUNIOR,
                xp_required=100,
                prerequisites=["linux_basics"]
            ),
            "docker_basics": Skill(
                skill_id="docker_basics",
                name="Docker基础",
                description="容器化部署入门",
                category="DevOps",
                level_required=SkillLevel.INTERMEDIATE,
                xp_required=300,
                prerequisites=["linux_basics"]
            ),
            "python_deploy": Skill(
                skill_id="python_deploy",
                name="Python部署",
                description="Python项目部署与运维",
                category="开发",
                level_required=SkillLevel.JUNIOR,
                xp_required=150,
                prerequisites=["linux_basics"]
            ),
            "nginx_config": Skill(
                skill_id="nginx_config",
                name="Nginx配置",
                description="Web服务器配置与优化",
                category="运维",
                level_required=SkillLevel.INTERMEDIATE,
                xp_required=250,
                prerequisites=["linux_basics"]
            ),
            "git_workflow": Skill(
                skill_id="git_workflow",
                name="Git工作流",
                description="团队协作Git工作流",
                category="开发",
                level_required=SkillLevel.JUNIOR,
                xp_required=100,
                prerequisites=[]
            )
        }

    def _build_achievements(self) -> Dict[str, Achievement]:
        """构建成就列表"""
        return {
            "first_deploy": Achievement(
                achievement_id="first_deploy",
                name="首次部署",
                description="完成第一次成功部署",
                icon="🚀",
                xp_reward=50
            ),
            "docker_master": Achievement(
                achievement_id="docker_master",
                name="容器大师",
                description="成功使用Docker部署5个项目",
                icon="🐳",
                xp_reward=200
            ),
            "zero_downtime": Achievement(
                achievement_id="zero_downtime",
                name="零宕机",
                description="完成10次无中断部署",
                icon="⚡",
                xp_reward=150
            ),
            "auto_rollback": Achievement(
                achievement_id="auto_rollback",
                name="自动回滚",
                description="成功执行自动回滚3次",
                icon="🔄",
                xp_reward=100
            ),
            "streak_week": Achievement(
                achievement_id="streak_week",
                name="连续7天",
                description="保持7天学习 streak",
                icon="🔥",
                xp_reward=300
            )
        }

    def _build_daily_tasks(self) -> List[DailyTask]:
        """构建每日任务"""
        return [
            DailyTask(
                task_id="daily_deploy",
                name="每日一部署",
                description="完成至少1次部署",
                xp_reward=20
            ),
            DailyTask(
                task_id="daily_learn",
                name="每日一学",
                description="学习1个新概念",
                xp_reward=10
            ),
            DailyTask(
                task_id="daily_help",
                name="互助问答",
                description="回答1个其他用户的问题",
                xp_reward=15
            )
        ]

    def explain_command(self, command: str) -> Explanation:
        """
        获取命令的三层解释

        Args:
            command: 要解释的命令

        Returns:
            Explanation: 三层解释
        """
        # 检查缓存
        if command in self._explanation_cache:
            return self._explanation_cache[command]

        explanation = self._generate_explanation(command)

        # 缓存
        with self._lock:
            self._explanation_cache[command] = explanation

        return explanation

    def _generate_explanation(self, command: str) -> Explanation:
        """生成三层解释"""
        # 命令库
        command_library = {
            "pip install": Explanation(
                metaphor="就像去超市买材料，pip install就是从网上下载做菜需要的原料",
                technical="pip是Python的包管理器，通过PyPI仓库安装Python包。会检查依赖兼容性并自动处理版本冲突",
                best_practice="使用requirements.txt管理依赖版本，生产环境建议使用虚拟环境隔离",
                code_example="pip install -r requirements.txt"
            ),
            "docker run": Explanation(
                metaphor="就像买了一个预装好系统的集装箱，你不需要关心里面怎么搭建，只管使用",
                technical="docker run会基于镜像创建容器，分配独立的文件系统、网络、进程空间。镜像类似只读模板",
                best_practice="生产环境使用docker-compose编排，指定资源限制，设置健康检查",
                code_example="docker run -d -p 8000:8000 --name myapp myimage:latest"
            ),
            "systemctl start": Explanation(
                metaphor="就像让一个服务员开始工作，systemctl会启动后台服务并管理它的生命周期",
                technical="systemctl与systemd交互，systemd是Linux的服务管理器，负责启动、停止、重启服务",
                best_practice="编写完整的service文件，配置Restart=always实现自动重启，设置合理的RestartSec",
                code_example="sudo systemctl start myservice"
            ),
            "chmod +x": Explanation(
                metaphor="就像给钥匙加一个功能，chmod +x就是让文件变成可执行的",
                technical="Linux通过权限位控制文件访问，+x表示添加执行权限",
                best_practice="生产环境避免使用777权限，使用最小权限原则，如755(脚本)或644(配置)",
                code_example="chmod +x deploy.sh && ./deploy.sh"
            ),
            "sudo": Explanation(
                metaphor="就像获得管理员身份证，sudo让你临时拥有root权限",
                technical="sudo(superuser do)允许授权用户以其他用户身份执行命令，默认是root",
                best_practice="最小化sudo使用，避免运行未知脚本，优先使用特定用户而非root",
                code_example="sudo apt-get update && sudo apt-get install nginx"
            ),
            "nohup": Explanation(
                metaphor="就像把任务交给后台管家，nohup确保命令在退出终端后继续运行",
                technical="nohup忽略挂断信号，使进程不响应SIGHUP，适合后台长期运行的任务",
                best_practice="配合&后台执行和>重定向输出，或使用screen/tmux更好的管理会话",
                code_example="nohup python app.py > app.log 2>&1 &"
            ),
            "curl": Explanation(
                metaphor="就像用对讲机发送请求，curl能向服务器发送各种协议的消息",
                technical="curl支持HTTP/HTTPS/FTP等多种协议，常用于API测试、文件下载",
                best_practice="使用-k忽略证书验证，生产环境要验证证书；使用-w输出详细信息",
                code_example="curl -X POST -H 'Content-Type: application/json' -d '{\"key\":\"value\"}' https://api.example.com"
            ),
            "grep": Explanation(
                metaphor="就像在图书馆用检索系统，grep能在文件中快速找到包含关键词的内容",
                technical="grep(global regular expression print)使用正则表达式匹配文本行，支持多种模式",
                best_practice="使用-i忽略大小写，-r递归搜索，-n显示行号，-E支持扩展正则",
                code_example="grep -rn 'ERROR' /var/log/"
            )
        }

        # 精确匹配
        cmd_lower = command.lower().strip()
        if cmd_lower in command_library:
            return command_library[cmd_lower]

        # 模糊匹配
        for key, exp in command_library.items():
            if key in cmd_lower or cmd_lower in key:
                return exp

        # 默认解释
        return Explanation(
            metaphor=f"这是一个命令，'{command}'是它的名字",
            technical=f"执行{command}会调用相应的程序完成特定任务",
            best_practice="查阅官方文档了解具体用法，注意参数顺序和格式",
            code_example=command
        )

    def unlock_skill(self, skill_id: str) -> bool:
        """解锁技能"""
        with self._lock:
            if skill_id not in self._skill_tree:
                return False

            skill = self._skill_tree[skill_id]

            # 检查前置技能
            for prereq in skill.prerequisites:
                if prereq not in self._skill_tree or not self._skill_tree[prereq].is_unlocked:
                    return False

            skill.is_unlocked = True
            self._notify_progress_update()

            return True

    def add_xp(self, amount: int, reason: str):
        """增加经验值"""
        with self._lock:
            self._progress.total_xp += amount

            # 检查升级
            old_level = self._progress.level
            self._progress.level = self._calculate_level(self._progress.total_xp)

            if self._progress.level != old_level:
                self._notify_level_up(old_level, self._progress.level)

            # 检查技能解锁
            for skill in self._skill_tree.values():
                if not skill.is_unlocked and self._progress.total_xp >= skill.xp_required:
                    skill.is_unlocked = True

            self._notify_progress_update()

    def _calculate_level(self, xp: int) -> SkillLevel:
        """根据经验值计算等级"""
        if xp < 100:
            return SkillLevel.BEGINNER
        elif xp < 300:
            return SkillLevel.JUNIOR
        elif xp < 600:
            return SkillLevel.INTERMEDIATE
        elif xp < 1000:
            return SkillLevel.ADVANCED
        else:
            return SkillLevel.EXPERT

    def unlock_achievement(self, achievement_id: str) -> bool:
        """解锁成就"""
        with self._lock:
            if achievement_id not in self._achievement_list:
                return False

            achievement = self._achievement_list[achievement_id]
            if achievement.is_unlocked:
                return False

            achievement.is_unlocked = True
            achievement.unlocked_at = datetime.now()

            # 奖励XP
            self.add_xp(achievement.xp_reward, f"成就解锁: {achievement.name}")

            self._notify_achievement(achievement)

            return True

    def complete_daily_task(self, task_id: str) -> bool:
        """完成每日任务"""
        with self._lock:
            for task in self._daily_tasks:
                if task.task_id == task_id and not task.is_completed:
                    task.is_completed = True
                    self.add_xp(task.xp_reward, f"每日任务: {task.name}")
                    return True

            return False

    def get_progress(self) -> UserProgress:
        """获取用户进度"""
        with self._lock:
            return self._progress

    def get_skill_tree(self) -> Dict[str, Skill]:
        """获取技能树"""
        return self._skill_tree

    def get_achievements(self) -> Dict[str, Achievement]:
        """获取成就列表"""
        return self._achievement_list

    def get_daily_tasks(self) -> List[DailyTask]:
        """获取每日任务"""
        return self._daily_tasks

    def add_listener(self, listener: Callable):
        """添加进度监听器"""
        self._listeners.append(listener)

    def _notify_progress_update(self):
        """通知进度更新"""
        for listener in self._listeners:
            try:
                listener({"type": "progress_update", "progress": self._progress})
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def _notify_level_up(self, old_level: SkillLevel, new_level: SkillLevel):
        """通知升级"""
        for listener in self._listeners:
            try:
                listener({
                    "type": "level_up",
                    "old_level": old_level,
                    "new_level": new_level
                })
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def _notify_achievement(self, achievement: Achievement):
        """通知成就解锁"""
        for listener in self._listeners:
            try:
                listener({
                    "type": "achievement",
                    "achievement": achievement
                })
            except Exception as e:
                logger.error(f"Listener error: {e}")


# 全局实例
learning_system = LearningSystem()
