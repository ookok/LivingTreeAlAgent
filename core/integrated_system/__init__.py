"""
集成系统模块
Integrated System Module

将用户认证、数字分身、积分经济和游戏系统整合起来，实现完整的功能流程。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..user_auth import UserAuthManager, get_auth_manager
from ..digital_twin import UserTwinManager, get_user_twin_manager, Activity, ActivityType, TwinStatus
from ..credit_economy.system import CreditEconomySystem, get_credit_system, TransactionType, AchievementType, BadgeType
from ..living_tree_game import ForestAdventure, NumberPuzzleGame, LifeTreeNurturing, EcologyMiniGames, SeasonalFestival


@dataclass
class UserSession:
    """用户会话"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    active: bool = True


class IntegratedSystem:
    """集成系统"""

    def __init__(self):
        # 初始化各个子系统
        self.auth_manager = get_auth_manager()
        self.twin_manager = get_user_twin_manager()
        self.credit_system = get_credit_system()
        
        # 初始化游戏系统
        self.forest_adventure = ForestAdventure()
        self.number_puzzle = NumberPuzzleGame()
        self.life_tree = LifeTreeNurturing()
        self.ecology_games = EcologyMiniGames()
        self.seasonal_festival = SeasonalFestival()
        
        # 会话管理
        self.sessions: Dict[str, UserSession] = {}

    # ============ 用户认证 ============

    async def register_user(self, username: str, nickname: str, phone: str) -> Dict:
        """注册用户"""
        # 创建用户
        user = self.auth_manager.create_user(username=username, nickname=nickname, phone=phone)
        
        # 初始化积分账户
        self.credit_system.get_user_credit(user.id)
        
        # 创建默认数字分身
        self.twin_manager.create_twin(user_id=user.id, name=f"{nickname}的分身")
        
        # 记录首次登录成就
        self.credit_system.create_achievement(
            user_id=user.id,
            achievement_type=AchievementType.FIRST_LOGIN.value,
            name="初次登录",
            description="完成首次登录"
        )
        
        # 奖励新手积分
        self.credit_system.add_credit(
            user_id=user.id,
            amount=1000,
            transaction_type=TransactionType.REWARD.value,
            description="新手奖励"
        )
        
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "message": "注册成功"
        }

    async def login_user(self, identifier: str, auth_type: str = "phone") -> Dict:
        """登录用户"""
        user = self.auth_manager.login(identifier, auth_type)
        if not user:
            return {"success": False, "error": "登录失败"}
        
        # 创建会话
        session = UserSession(user_id=user.id, user=user)
        self.sessions[session.session_id] = session
        
        # 更新最后登录时间
        user.last_login_at = datetime.now().isoformat()
        
        return {
            "success": True,
            "session_id": session.session_id,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname
        }

    async def logout_user(self, session_id: str) -> Dict:
        """登出用户"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.active = False
            del self.sessions[session_id]
            return {"success": True, "message": "登出成功"}
        return {"success": False, "error": "会话不存在"}

    # ============ 数字分身管理 ============

    async def create_digital_twin(self, user_id: str, name: str, avatar_url: str = "") -> Dict:
        """创建数字分身"""
        twin = self.twin_manager.create_twin(user_id, name, avatar_url)
        
        # 记录成就
        self.credit_system.create_achievement(
            user_id=user_id,
            achievement_type=AchievementType.TWIN_CREATED.value,
            name="数字分身",
            description="创建第一个数字分身"
        )
        
        # 奖励积分
        self.credit_system.add_credit(
            user_id=user_id,
            amount=500,
            transaction_type=TransactionType.REWARD.value,
            description="创建数字分身奖励"
        )
        
        return {
            "success": True,
            "twin_id": twin.twin_id,
            "name": twin.name
        }

    async def list_user_twins(self, user_id: str) -> Dict:
        """列出用户的数字分身"""
        twins = self.twin_manager.get_user_twins(user_id)
        return {
            "success": True,
            "twins": [twin.to_dict() for twin in twins]
        }

    # ============ 活动管理 ============

    async def create_activity(self, user_id: str, name: str, description: str, activity_type: str, 
                            start_time: str, end_time: str, duration_minutes: int, 
                            required_skills: Dict[str, int] = None, rewards: Dict[str, Any] = None) -> Dict:
        """创建活动"""
        activity = self.twin_manager.create_activity(
            name=name,
            description=description,
            activity_type=activity_type,
            organizer_id=user_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            required_skills=required_skills or {},
            rewards=rewards or {}
        )
        
        return {
            "success": True,
            "activity_id": activity.activity_id,
            "name": activity.name
        }

    async def list_activities(self, activity_type: str = None, status: str = None) -> Dict:
        """列出活动"""
        activities = self.twin_manager.list_activities(activity_type, status)
        return {
            "success": True,
            "activities": [activity.to_dict() for activity in activities]
        }

    # ============ 数字分身出租 ============

    async def rent_twin(self, renter_id: str, twin_id: str, activity_id: str, 
                      start_time: str, end_time: str, duration_minutes: int, price: float) -> Dict:
        """租用数字分身"""
        try:
            # 创建出租请求
            rental = self.twin_manager.create_rental_request(
                twin_id=twin_id,
                renter_id=renter_id,
                activity_id=activity_id,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                price=price
            )
            
            return {
                "success": True,
                "request_id": rental.request_id,
                "message": "出租请求已创建"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    async def accept_rental(self, request_id: str) -> Dict:
        """接受出租请求"""
        # 接受出租请求
        success = self.twin_manager.accept_rental_request(request_id)
        if not success:
            return {"success": False, "error": "接受出租请求失败"}
        
        # 获取出租信息
        rental = self.twin_manager.get_rental_request(request_id)
        if not rental:
            return {"success": False, "error": "出租请求不存在"}
        
        # 获取数字分身信息
        twin = self.twin_manager.get_twin(rental.twin_id)
        if not twin:
            return {"success": False, "error": "数字分身不存在"}
        
        # 处理积分交易
        amount = int(rental.price)
        transaction_success = self.credit_system.process_twin_rental(
            twin_owner_id=twin.user_id,
            renter_id=rental.renter_id,
            amount=amount,
            rental_id=request_id
        )
        
        if not transaction_success:
            # 回滚出租状态
            self.twin_manager.cancel_rental_request(request_id)
            return {"success": False, "error": "积分交易失败"}
        
        return {
            "success": True,
            "message": "出租请求已接受"
        }

    async def complete_rental(self, request_id: str) -> Dict:
        """完成出租"""
        success = self.twin_manager.complete_rental_request(request_id)
        if not success:
            return {"success": False, "error": "完成出租失败"}
        
        # 获取出租信息
        rental = self.twin_manager.get_rental_request(request_id)
        if not rental:
            return {"success": False, "error": "出租请求不存在"}
        
        # 获取数字分身信息
        twin = self.twin_manager.get_twin(rental.twin_id)
        if not twin:
            return {"success": False, "error": "数字分身不存在"}
        
        # 处理活动参与
        self.credit_system.process_activity_participation(
            user_id=twin.user_id,
            activity_id=rental.activity_id
        )
        
        return {
            "success": True,
            "message": "出租已完成"
        }

    # ============ 积分系统 ============

    async def get_user_credits(self, user_id: str) -> Dict:
        """获取用户积分"""
        credit = self.credit_system.get_user_credit(user_id)
        return {
            "success": True,
            "balance": credit.balance,
            "total_earned": credit.total_earned,
            "total_spent": credit.total_spent
        }

    async def get_user_achievements(self, user_id: str) -> Dict:
        """获取用户成就"""
        achievements = self.credit_system.get_user_achievements(user_id)
        return {
            "success": True,
            "achievements": [a.to_dict() for a in achievements]
        }

    async def get_user_badges(self, user_id: str) -> Dict:
        """获取用户徽章"""
        badges = self.credit_system.get_user_badges(user_id)
        return {
            "success": True,
            "badges": [b.to_dict() for b in badges]
        }

    async def get_user_stats(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        stats = self.credit_system.get_user_stats(user_id)
        return {
            "success": True,
            "stats": stats
        }

    # ============ 游戏系统 ============

    async def dig_for_treasure(self, user_id: str, location: str, tool_level: int = 1) -> Dict:
        """森林探险挖宝"""
        result = await self.forest_adventure.dig_for_treasure(user_id, location, tool_level)
        
        if result["success"]:
            # 奖励积分
            credits = result["treasure"]["credits"]
            self.credit_system.add_credit(
                user_id=user_id,
                amount=credits,
                transaction_type=TransactionType.EARN.value,
                description=f"挖宝获得: {result['treasure']['name']}"
            )
        
        return result

    async def start_puzzle(self, user_id: str, difficulty: str = "medium") -> Dict:
        """开始数字猜谜游戏"""
        return await self.number_puzzle.start_puzzle(user_id, difficulty)

    async def make_puzzle_guess(self, puzzle_id: str, guess: str) -> Dict:
        """猜数字"""
        result = await self.number_puzzle.make_guess(puzzle_id, guess)
        
        if result.get("success") and result.get("solved"):
            # 奖励积分
            reward = result["reward"]
            self.credit_system.add_credit(
                user_id=result.get("user_id", ""),
                amount=reward,
                transaction_type=TransactionType.EARN.value,
                description="猜谜游戏奖励"
            )
        
        return result

    async def nurture_tree(self, user_id: str, action: str, item_id: str = None) -> Dict:
        """生命之树养成"""
        result = await self.life_tree.nurture_tree(user_id, action, item_id)
        
        if result["success"]:
            # 奖励积分
            daily_yield = result["daily_yield"]
            self.credit_system.add_credit(
                user_id=user_id,
                amount=daily_yield,
                transaction_type=TransactionType.EARN.value,
                description="生命之树养护奖励"
            )
        
        return result

    async def play_mini_game(self, user_id: str, game_id: str) -> Dict:
        """玩生态小游戏"""
        result = await self.ecology_games.play_mini_game(user_id, game_id)
        
        if result["success"]:
            # 奖励积分
            credits = result["credits"]
            self.credit_system.add_credit(
                user_id=user_id,
                amount=credits,
                transaction_type=TransactionType.EARN.value,
                description=f"小游戏奖励: {result['game_name']}"
            )
        
        return result

    async def start_seasonal_event(self, season: str = None) -> Dict:
        """开始季节庆典活动"""
        return await self.seasonal_festival.start_seasonal_event(season)

    async def participate_in_event(self, user_id: str, event_id: str, activity: str) -> Dict:
        """参与季节庆典活动"""
        result = await self.seasonal_festival.participate_in_event(user_id, event_id, activity)
        
        if result["success"]:
            # 奖励积分
            total_reward = result["total_reward"]
            self.credit_system.add_credit(
                user_id=user_id,
                amount=total_reward,
                transaction_type=TransactionType.EARN.value,
                description=f"活动奖励: {activity}"
            )
        
        return result


# 全局实例
_integrated_system: Optional[IntegratedSystem] = None


def get_integrated_system() -> IntegratedSystem:
    """获取集成系统"""
    global _integrated_system
    if _integrated_system is None:
        _integrated_system = IntegratedSystem()
    return _integrated_system


# 便捷函数

async def register_user(username: str, nickname: str, phone: str) -> Dict:
    """注册用户"""
    return await get_integrated_system().register_user(username, nickname, phone)


async def login_user(identifier: str, auth_type: str = "phone") -> Dict:
    """登录用户"""
    return await get_integrated_system().login_user(identifier, auth_type)


async def logout_user(session_id: str) -> Dict:
    """登出用户"""
    return await get_integrated_system().logout_user(session_id)


async def create_digital_twin(user_id: str, name: str, avatar_url: str = "") -> Dict:
    """创建数字分身"""
    return await get_integrated_system().create_digital_twin(user_id, name, avatar_url)


async def list_user_twins(user_id: str) -> Dict:
    """列出用户的数字分身"""
    return await get_integrated_system().list_user_twins(user_id)


async def create_activity(user_id: str, name: str, description: str, activity_type: str, 
                        start_time: str, end_time: str, duration_minutes: int, 
                        required_skills: Dict[str, int] = None, rewards: Dict[str, Any] = None) -> Dict:
    """创建活动"""
    return await get_integrated_system().create_activity(
        user_id, name, description, activity_type, start_time, end_time, 
        duration_minutes, required_skills, rewards
    )


async def list_activities(activity_type: str = None, status: str = None) -> Dict:
    """列出活动"""
    return await get_integrated_system().list_activities(activity_type, status)


async def rent_twin(renter_id: str, twin_id: str, activity_id: str, 
                  start_time: str, end_time: str, duration_minutes: int, price: float) -> Dict:
    """租用数字分身"""
    return await get_integrated_system().rent_twin(
        renter_id, twin_id, activity_id, start_time, end_time, duration_minutes, price
    )


async def accept_rental(request_id: str) -> Dict:
    """接受出租请求"""
    return await get_integrated_system().accept_rental(request_id)


async def complete_rental(request_id: str) -> Dict:
    """完成出租"""
    return await get_integrated_system().complete_rental(request_id)


async def get_user_credits(user_id: str) -> Dict:
    """获取用户积分"""
    return await get_integrated_system().get_user_credits(user_id)


async def get_user_achievements(user_id: str) -> Dict:
    """获取用户成就"""
    return await get_integrated_system().get_user_achievements(user_id)


async def get_user_badges(user_id: str) -> Dict:
    """获取用户徽章"""
    return await get_integrated_system().get_user_badges(user_id)


async def get_user_stats(user_id: str) -> Dict:
    """获取用户统计信息"""
    return await get_integrated_system().get_user_stats(user_id)


async def dig_for_treasure(user_id: str, location: str, tool_level: int = 1) -> Dict:
    """森林探险挖宝"""
    return await get_integrated_system().dig_for_treasure(user_id, location, tool_level)


async def start_puzzle(user_id: str, difficulty: str = "medium") -> Dict:
    """开始数字猜谜游戏"""
    return await get_integrated_system().start_puzzle(user_id, difficulty)


async def make_puzzle_guess(puzzle_id: str, guess: str) -> Dict:
    """猜数字"""
    return await get_integrated_system().make_puzzle_guess(puzzle_id, guess)


async def nurture_tree(user_id: str, action: str, item_id: str = None) -> Dict:
    """生命之树养成"""
    return await get_integrated_system().nurture_tree(user_id, action, item_id)


async def play_mini_game(user_id: str, game_id: str) -> Dict:
    """玩生态小游戏"""
    return await get_integrated_system().play_mini_game(user_id, game_id)


async def start_seasonal_event(season: str = None) -> Dict:
    """开始季节庆典活动"""
    return await get_integrated_system().start_seasonal_event(season)


async def participate_in_event(user_id: str, event_id: str, activity: str) -> Dict:
    """参与季节庆典活动"""
    return await get_integrated_system().participate_in_event(user_id, event_id, activity)


__all__ = [
    "IntegratedSystem",
    "get_integrated_system",
    "register_user",
    "login_user",
    "logout_user",
    "create_digital_twin",
    "list_user_twins",
    "create_activity",
    "list_activities",
    "rent_twin",
    "accept_rental",
    "complete_rental",
    "get_user_credits",
    "get_user_achievements",
    "get_user_badges",
    "get_user_stats",
    "dig_for_treasure",
    "start_puzzle",
    "make_puzzle_guess",
    "nurture_tree",
    "play_mini_game",
    "start_seasonal_event",
    "participate_in_event"
]
