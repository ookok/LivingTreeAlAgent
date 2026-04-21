"""
虚拟形象 Avatar 模块

支持虚拟形象的生成、驱动和展示
"""

import asyncio
import uuid
import json
import base64
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from PIL import Image
import io
import numpy as np


class AvatarType(Enum):
    """虚拟形象类型"""
    2D = "2d"
    3D = "3d"
    HYBRID = "hybrid"


class AvatarExpression(Enum):
    """虚拟形象表情"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"


@dataclass
class AvatarConfig:
    """虚拟形象配置"""
    avatar_id: str
    name: str
    avatar_type: AvatarType = AvatarType.HYBRID
    style: str = "professional"
    voice_id: Optional[str] = None
    language: str = "zh"
    background: str = "office"


@dataclass
class AvatarState:
    """虚拟形象状态"""
    expression: AvatarExpression = AvatarExpression.NEUTRAL
    speaking: bool = False
    listening: bool = False
    text: str = ""
    emotion_score: float = 0.5


@dataclass
class AvatarFrame:
    """虚拟形象帧"""
    avatar_id: str
    image_data: Optional[bytes] = None
    expression: AvatarExpression = AvatarExpression.NEUTRAL
    speaking: bool = False
    timestamp: float = 0


class AvatarRenderer:
    """虚拟形象渲染器"""

    def __init__(self):
        self._is_initialized = False
        self._render_engine = None

    async def initialize(self) -> bool:
        """
        初始化渲染器

        Returns:
            bool: 是否初始化成功
        """
        if self._is_initialized:
            return True

        try:
            from diffusers import StableDiffusionPipeline
            import torch

            print("[AvatarRenderer] 正在加载 2D 渲染模型...")
            self._render_engine = "diffusion"
            self._is_initialized = True
            print("[AvatarRenderer] 渲染器初始化成功")
            return True

        except ImportError:
            print("[AvatarRenderer] diffusers 未安装，将使用简化渲染")
            self._render_engine = "simple"
            self._is_initialized = True
            return True

        except Exception as e:
            print(f"[AvatarRenderer] 初始化失败: {e}")
            self._render_engine = "simple"
            self._is_initialized = True
            return True

    async def render_avatar(
        self,
        config: AvatarConfig,
        expression: AvatarExpression = AvatarExpression.NEUTRAL,
        size: tuple = (512, 512)
    ) -> Optional[bytes]:
        """
        渲染虚拟形象

        Args:
            config: 虚拟形象配置
            expression: 表情
            size: 图像大小

        Returns:
            Optional[bytes]: 渲染的图像数据
        """
        if not self._is_initialized:
            await self.initialize()

        if self._render_engine == "simple":
            return self._render_simple_avatar(config, expression, size)
        elif self._render_engine == "diffusion":
            return await self._render_diffusion_avatar(config, expression, size)

        return None

    def _render_simple_avatar(
        self,
        config: AvatarConfig,
        expression: AvatarExpression,
        size: tuple
    ) -> bytes:
        """简化渲染"""
        img = Image.new('RGBA', size, (240, 240, 245, 255))

        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)

        center_x, center_y = size[0] // 2, size[1] // 2
        avatar_size = min(size) // 2

        draw.ellipse(
            [center_x - avatar_size, center_y - avatar_size,
             center_x + avatar_size, center_y + avatar_size],
            fill=(100, 150, 200, 255)
        )

        eye_y = center_y - avatar_size // 3
        eye_spacing = avatar_size // 3

        draw.ellipse(
            [center_x - eye_spacing - 10, eye_y - 10,
             center_x - eye_spacing + 10, eye_y + 10],
            fill=(50, 50, 50, 255)
        )
        draw.ellipse(
            [center_x + eye_spacing - 10, eye_y - 10,
             center_x + eye_spacing + 10, eye_y + 10],
            fill=(50, 50, 50, 255)
        )

        mouth_y = center_y + avatar_size // 3
        if expression == AvatarExpression.HAPPY:
            draw.arc(
                [center_x - 40, mouth_y - 20, center_x + 40, mouth_y + 20],
                0, 180, fill=(50, 50, 50, 255), width=3
            )
        elif expression == AvatarExpression.SAD:
            draw.arc(
                [center_x - 40, mouth_y, center_x + 40, mouth_y + 40],
                180, 360, fill=(50, 50, 50, 255), width=3
            )
        else:
            draw.line(
                [center_x - 30, mouth_y, center_x + 30, mouth_y],
                fill=(50, 50, 50, 255), width=3
            )

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    async def _render_diffusion_avatar(
        self,
        config: AvatarConfig,
        expression: AvatarExpression,
        size: tuple
    ) -> bytes:
        """使用 Diffusion 模型渲染"""
        prompt = self._build_prompt(config, expression)

        try:
            pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5"
            )

            result = pipe(prompt, num_inference_steps=20)
            image = result.images[0]

            image = image.resize(size)

            buf = io.BytesIO()
            image.save(buf, format='PNG')
            return buf.getvalue()

        except Exception as e:
            print(f"[AvatarRenderer] Diffusion 渲染失败: {e}")
            return self._render_simple_avatar(config, expression, size)

    def _build_prompt(self, config: AvatarConfig, expression: AvatarExpression) -> str:
        """构建提示词"""
        expression_map = {
            AvatarExpression.NEUTRAL: "neutral face",
            AvatarExpression.HAPPY: "smiling happily",
            AvatarExpression.SAD: "sad expression",
            AvatarExpression.ANGRY: "angry expression",
            AvatarExpression.SURPRISED: "surprised expression",
            AvatarExpression.THINKING: "thoughtful expression",
            AvatarExpression.SPEAKING: "speaking confidently",
            AvatarExpression.LISTENING: "attentive listening"
        }

        prompt = f"professional avatar, {config.name}, {expression_map.get(expression, 'neutral')}, {config.background} background, high quality, 4k"
        return prompt


class VirtualAvatar:
    """虚拟形象"""

    def __init__(
        self,
        config: AvatarConfig,
        renderer: Optional[AvatarRenderer] = None
    ):
        self.config = config
        self.renderer = renderer or AvatarRenderer()
        self.state = AvatarState()
        self._is_active = False
        self._frame_callback: Optional[Callable[[AvatarFrame], None]] = None

    async def initialize(self) -> bool:
        """初始化"""
        return await self.renderer.initialize()

    async def activate(self):
        """激活虚拟形象"""
        if not self._is_active:
            await self.initialize()
            self._is_active = True

    def deactivate(self):
        """停用虚拟形象"""
        self._is_active = False

    async def update_state(
        self,
        expression: Optional[AvatarExpression] = None,
        speaking: Optional[bool] = None,
        listening: Optional[bool] = None,
        text: Optional[str] = None
    ):
        """更新状态"""
        if expression is not None:
            self.state.expression = expression
        if speaking is not None:
            self.state.speaking = speaking
        if listening is not None:
            self.state.listening = listening
        if text is not None:
            self.state.text = text

        if self._is_active and self._frame_callback:
            frame = await self.render_frame()
            self._frame_callback(frame)

    async def render_frame(self) -> AvatarFrame:
        """渲染帧"""
        image_data = await self.renderer.render_avatar(
            self.config,
            self.state.expression
        )

        return AvatarFrame(
            avatar_id=self.config.avatar_id,
            image_data=image_data,
            expression=self.state.expression,
            speaking=self.state.speaking,
            timestamp=asyncio.get_event_loop().time()
        )

    def set_frame_callback(self, callback: Callable[[AvatarFrame], None]):
        """设置帧回调"""
        self._frame_callback = callback

    def get_config(self) -> AvatarConfig:
        """获取配置"""
        return self.config

    def get_state(self) -> AvatarState:
        """获取状态"""
        return self.state


class AvatarManager:
    """虚拟形象管理器"""

    def __init__(self):
        self.avatars: Dict[str, VirtualAvatar] = {}
        self.renderer = AvatarRenderer()
        self._is_initialized = False

    async def initialize(self) -> bool:
        """初始化"""
        if self._is_initialized:
            return True

        await self.renderer.initialize()
        self._is_initialized = True
        return True

    async def create_avatar(
        self,
        name: str,
        avatar_type: AvatarType = AvatarType.HYBRID,
        style: str = "professional",
        voice_id: Optional[str] = None,
        language: str = "zh"
    ) -> str:
        """
        创建虚拟形象

        Args:
            name: 名称
            avatar_type: 类型
            style: 风格
            voice_id: 声音 ID
            language: 语言

        Returns:
            str: 虚拟形象 ID
        """
        await self.initialize()

        avatar_id = str(uuid.uuid4())

        config = AvatarConfig(
            avatar_id=avatar_id,
            name=name,
            avatar_type=avatar_type,
            style=style,
            voice_id=voice_id,
            language=language
        )

        avatar = VirtualAvatar(config, self.renderer)
        await avatar.initialize()

        self.avatars[avatar_id] = avatar

        print(f"[AvatarManager] 创建虚拟形象: {name} ({avatar_id})")
        return avatar_id

    async def create_participant_avatar(
        self,
        participant_name: str,
        role: str
    ) -> str:
        """
        创建参与者虚拟形象

        Args:
            participant_name: 参与者名称
            role: 角色

        Returns:
            str: 虚拟形象 ID
        """
        role_styles = {
            "expert": "technical professional",
            "government": "formal government official",
            "enterprise": "business professional",
            "employee": "friendly colleague",
            "chairman": "distinguished leader"
        }

        style = role_styles.get(role, "professional")

        return await self.create_avatar(
            name=participant_name,
            style=style
        )

    def get_avatar(self, avatar_id: str) -> Optional[VirtualAvatar]:
        """获取虚拟形象"""
        return self.avatars.get(avatar_id)

    def remove_avatar(self, avatar_id: str) -> bool:
        """移除虚拟形象"""
        if avatar_id in self.avatars:
            avatar = self.avatars[avatar_id]
            avatar.deactivate()
            del self.avatars[avatar_id]
            return True
        return False

    def list_avatars(self) -> List[Dict]:
        """列出所有虚拟形象"""
        return [
            {
                "avatar_id": vid,
                "name": avatar.config.name,
                "type": avatar.config.avatar_type.value,
                "active": avatar._is_active
            }
            for vid, avatar in self.avatars.items()
        ]


class AvatarWebRTC:
    """虚拟形象 WebRTC 集成"""

    def __init__(self, avatar_manager: AvatarManager):
        self.avatar_manager = avatar_manager
        self._stream_callback: Optional[Callable[[bytes], None]] = None

    async def start_streaming(
        self,
        avatar_id: str,
        on_frame: Callable[[bytes], None]
    ):
        """
        开始流式传输

        Args:
            avatar_id: 虚拟形象 ID
            on_frame: 帧回调
        """
        avatar = self.avatar_manager.get_avatar(avatar_id)
        if not avatar:
            return

        self._stream_callback = on_frame

        async def frame_callback(frame: AvatarFrame):
            if frame.image_data and self._stream_callback:
                self._stream_callback(frame.image_data)

        avatar.set_frame_callback(frame_callback)
        await avatar.activate()

    def stop_streaming(self, avatar_id: str):
        """停止流式传输"""
        avatar = self.avatar_manager.get_avatar(avatar_id)
        if avatar:
            avatar.deactivate()
            avatar.set_frame_callback(lambda f: None)


class AvatarPanel:
    """虚拟形象面板"""

    def __init__(self):
        self.manager = AvatarManager()
        self._is_running = False

    async def initialize(self):
        """初始化"""
        await self.manager.initialize()

    async def create_avatar(
        self,
        name: str,
        role: str
    ) -> Optional[str]:
        """
        创建参与者虚拟形象

        Args:
            name: 名称
            role: 角色

        Returns:
            Optional[str]: 虚拟形象 ID
        """
        return await self.manager.create_participant_avatar(name, role)

    async def update_expression(
        self,
        avatar_id: str,
        expression: AvatarExpression
    ):
        """更新表情"""
        avatar = self.manager.get_avatar(avatar_id)
        if avatar:
            await avatar.update_state(expression=expression)

    async def update_speaking(
        self,
        avatar_id: str,
        speaking: bool
    ):
        """更新说话状态"""
        avatar = self.manager.get_avatar(avatar_id)
        if avatar:
            await avatar.update_state(
                speaking=speaking,
                expression=AvatarExpression.SPEAKING if speaking else AvatarExpression.NEUTRAL
            )

    async def render_avatar(self, avatar_id: str) -> Optional[bytes]:
        """渲染虚拟形象"""
        avatar = self.manager.get_avatar(avatar_id)
        if avatar:
            frame = await avatar.render_frame()
            return frame.image_data
        return None


_global_manager: Optional[AvatarManager] = None


def get_avatar_manager() -> AvatarManager:
    """获取虚拟形象管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = AvatarManager()
    return _global_manager
