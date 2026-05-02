# -*- coding: utf-8 -*-
"""
斗地主特效系统
Special Effects System for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import math
import random


class EffectType(Enum):
    """特效类型"""
    FLASH = "flash"                    # 闪光
    SHOCKWAVE = "shockwave"            # 冲击波
    PARTICLE = "particle"              # 粒子
    GLOW = "glow"                     # 发光
    SHAKE = "shake"                   # 震动
    ROCKET = "rocket"                 # 火箭
    BOMB = "bomb"                     # 炸弹


@dataclass
class EffectConfig:
    """特效配置"""
    effect_type: EffectType
    position: Tuple[int, int]
    duration: int = 500  # 毫秒
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    size: int = 100
    particle_count: int = 20


class EffectLayer:
    """特效层管理器"""

    def __init__(self):
        self.active_effects: List['BaseEffect'] = []
        self.effect_queue: List['BaseEffect'] = []

    def add_effect(self, effect: 'BaseEffect'):
        """添加特效"""
        self.active_effects.append(effect)

    def remove_effect(self, effect: 'BaseEffect'):
        """移除特效"""
        if effect in self.active_effects:
            self.active_effects.remove(effect)

    def update(self, delta_time: float):
        """更新特效"""
        for effect in self.active_effects[:]:
            effect.update(delta_time)
            if effect.is_finished:
                self.remove_effect(effect)

    def clear(self):
        """清除所有特效"""
        self.active_effects.clear()


class BaseEffect:
    """基础特效类"""

    def __init__(self, config: EffectConfig):
        self.config = config
        self.elapsed = 0
        self.is_finished = False
        self.progress = 0.0

    def update(self, delta_time: float):
        """更新特效"""
        self.elapsed += delta_time * 1000  # 转换为毫秒
        self.progress = min(1.0, self.elapsed / self.config.duration)

        if self.elapsed >= self.config.duration:
            self.is_finished = True

    def get_position(self) -> Tuple[int, int]:
        """获取位置"""
        return self.config.position


class FlashEffect(BaseEffect):
    """闪光特效"""

    def __init__(self, config: EffectConfig):
        super().__init__(config)
        self.max_radius = config.size
        self.opacity = 1.0

    def get_radius(self) -> float:
        """获取当前半径"""
        # 快速扩大然后缩小
        if self.progress < 0.3:
            return self.max_radius * (self.progress / 0.3)
        else:
            return self.max_radius * (1 - (self.progress - 0.3) / 0.7)

    def get_opacity(self) -> float:
        """获取透明度"""
        return 1.0 - self.progress


class ShockwaveEffect(BaseEffect):
    """冲击波特效"""

    def __init__(self, config: EffectConfig):
        super().__init__(config)
        self.max_radius = config.size

    def get_radius(self) -> float:
        """获取当前半径"""
        return self.max_radius * self.progress

    def get_opacity(self) -> float:
        """获取透明度"""
        return 1.0 - self.progress


class ParticleEffect(BaseEffect):
    """粒子特效"""

    def __init__(self, config: EffectConfig):
        super().__init__(config)
        self.particles = self._generate_particles()

    def _generate_particles(self) -> List[Dict]:
        """生成粒子"""
        particles = []
        count = self.config.particle_count

        for i in range(count):
            angle = (2 * math.pi * i) / count + random.uniform(-0.2, 0.2)
            speed = random.uniform(0.5, 1.5)
            particles.append({
                "angle": angle,
                "speed": speed,
                "size": random.uniform(3, 8),
                "color": self._shift_color(self.config.color, random.uniform(-30, 30))
            })

        return particles

    def _shift_color(self, color: Tuple[int, int, int, int], shift: float) -> Tuple[int, int, int, int]:
        """偏移颜色"""
        return (
            max(0, min(255, int(color[0] + shift))),
            max(0, min(255, int(color[1] + shift))),
            max(0, min(255, int(color[2] + shift))),
            color[3]
        )

    def get_particles(self) -> List[Dict]:
        """获取粒子列表"""
        result = []
        for p in self.particles:
            distance = self.progress * self.config.size * p["speed"]
            x = self.config.position[0] + math.cos(p["angle"]) * distance
            y = self.config.position[1] + math.sin(p["angle"]) * distance
            result.append({
                "x": x,
                "y": y,
                "size": p["size"] * (1 - self.progress * 0.5),
                "color": p["color"],
                "opacity": 1.0 - self.progress
            })
        return result


class BombEffect(BaseEffect):
    """炸弹特效组合"""

    def __init__(self, config: EffectConfig):
        super().__init__(config)
        # 闪光效果
        flash_config = EffectConfig(
            EffectType.FLASH,
            config.position,
            duration=300,
            size=150,
            color=(255, 200, 50, 255)
        )
        self.flash = FlashEffect(flash_config)

        # 冲击波效果
        shock_config = EffectConfig(
            EffectType.SHOCKWAVE,
            config.position,
            duration=500,
            size=200,
            color=(255, 100, 0, 200)
        )
        self.shockwave = ShockwaveEffect(shock_config)

        # 粒子效果
        particle_config = EffectConfig(
            EffectType.PARTICLE,
            config.position,
            duration=600,
            size=150,
            particle_count=30
        )
        self.particles = ParticleEffect(particle_config)

    def update(self, delta_time: float):
        """更新所有子特效"""
        super().update(delta_time)
        self.flash.update(delta_time)
        self.shockwave.update(delta_time)
        self.particles.update(delta_time)


class RocketEffect(BaseEffect):
    """火箭特效组合"""

    def __init__(self, config: EffectConfig, start_pos: Tuple[int, int], end_pos: Tuple[int, int]):
        super().__init__(config)
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.trail_particles = []

    def get_current_position(self) -> Tuple[int, int]:
        """获取当前位置"""
        # 抛物线轨迹
        t = self.progress
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * t

        # 抛物线高度
        arc_height = abs(self.end_pos[1] - self.start_pos[1]) * 0.5
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * t - \
            4 * arc_height * t * (1 - t)

        return (int(x), int(y))

    def get_trail(self) -> List[Dict]:
        """获取尾迹"""
        if len(self.trail_particles) > 20:
            self.trail_particles.pop(0)

        current_pos = self.get_current_position()
        self.trail_particles.append({
            "x": current_pos[0],
            "y": current_pos[1],
            "opacity": 1.0,
            "size": 10 * (1 - self.progress)
        })

        return self.trail_particles


class CardEffectSystem:
    """卡牌特效系统"""

    def __init__(self):
        self.effect_layer = EffectLayer()
        self.sound_enabled = True
        self.screen_shake_enabled = True

    def play_combo_effect(self, combo_type: str, position: Tuple[int, int]) -> Optional[BaseEffect]:
        """播放组合特效"""
        effects = {
            "single": self._single_effect,
            "pair": self._pair_effect,
            "triple": self._triple_effect,
            "straight": self._straight_effect,
            "consecutive_pairs": self._pairs_effect,
            "airplane": self._airplane_effect,
            "bomb": self._bomb_effect,
            "rocket": self._rocket_effect,
            "triple_with_single": self._triple_single_effect,
            "triple_with_pair": self._triple_pair_effect,
            "four_with_two": self._four_two_effect
        }

        effect_func = effects.get(combo_type)
        if effect_func:
            effect = effect_func(position)
            self.effect_layer.add_effect(effect)
            return effect

        return None

    def _single_effect(self, position: Tuple[int, int]) -> FlashEffect:
        """单张特效"""
        config = EffectConfig(
            EffectType.FLASH,
            position,
            duration=200,
            size=50,
            color=(200, 200, 255, 255)
        )
        return FlashEffect(config)

    def _pair_effect(self, position: Tuple[int, int]) -> FlashEffect:
        """对子特效"""
        config = EffectConfig(
            EffectType.GLOW,
            position,
            duration=300,
            size=60,
            color=(100, 150, 255, 255)
        )
        return FlashEffect(config)

    def _triple_effect(self, position: Tuple[int, int]) -> FlashEffect:
        """三张特效"""
        config = EffectConfig(
            EffectType.FLASH,
            position,
            duration=400,
            size=80,
            color=(255, 150, 100, 255)
        )
        return FlashEffect(config)

    def _straight_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """顺子特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=500,
            size=100,
            particle_count=15
        )
        return ParticleEffect(config)

    def _pairs_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """连对特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=600,
            size=120,
            particle_count=20
        )
        return ParticleEffect(config)

    def _airplane_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """飞机特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=800,
            size=150,
            particle_count=30,
            color=(100, 200, 255, 255)
        )
        return ParticleEffect(config)

    def _bomb_effect(self, position: Tuple[int, int]) -> BombEffect:
        """炸弹特效"""
        config = EffectConfig(
            EffectType.BOMB,
            position,
            duration=600,
            size=200,
            color=(255, 150, 0, 255)
        )
        return BombEffect(config)

    def _rocket_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """火箭特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=1000,
            size=250,
            particle_count=50,
            color=(255, 50, 50, 255)
        )
        return ParticleEffect(config)

    def _triple_single_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """三带一特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=400,
            size=90,
            particle_count=15
        )
        return ParticleEffect(config)

    def _triple_pair_effect(self, position: Tuple[int, int]) -> ParticleEffect:
        """三带二特效"""
        config = EffectConfig(
            EffectType.PARTICLE,
            position,
            duration=500,
            size=100,
            particle_count=20
        )
        return ParticleEffect(config)

    def _four_two_effect(self, position: Tuple[int, int]) -> BombEffect:
        """四带二特效"""
        config = EffectConfig(
            EffectType.BOMB,
            position,
            duration=500,
            size=150,
            color=(200, 100, 255, 255)
        )
        return BombEffect(config)

    def shake_screen(self, intensity: int = 10, duration: int = 300):
        """屏幕震动"""
        if self.screen_shake_enabled:
            # 返回震动参数，实际震动由UI层处理
            return {"intensity": intensity, "duration": duration}
        return None

    def play_sound(self, sound_name: str):
        """播放音效"""
        if self.sound_enabled:
            # 返回音效名称，实际播放由UI层处理
            return sound_name
        return None

    def update(self, delta_time: float):
        """更新特效"""
        self.effect_layer.update(delta_time)

    def clear(self):
        """清除所有特效"""
        self.effect_layer.clear()
