# -*- coding: utf-8 -*-
"""
图像生成动作处理器
==================

处理图像生成意图：
- IMAGE_GENERATION: 文本生成图像

使用外部图像生成 API（DALL-E / Stable Diffusion）。
from __future__ import annotations
"""


import logging
import os
from typing import Optional

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
)

logger = logging.getLogger(__name__)


class ImageGenerationHandler(BaseActionHandler):
    """
    图像生成处理器

    支持的意图：
    - IMAGE_GENERATION

    上下文参数：
    - prompt: 图像描述（必需）
    - size: 图像尺寸（default: 512x512, 可选: 256x256/512x512/1024x1024）
    - style: 风格（photorealistic/artistic/anime/cyberpunk/...）
    - n: 生成数量（default: 1）
    - output_dir: 保存目录（default: ./generated_images/）
    """

    @property
    def name(self) -> str:
        return "ImageGenerationHandler"

    @property
    def supported_intents(self) -> list:
        return [IntentType.IMMAGE_GENERATION]

    @property
    def priority(self) -> int:
        return 50

    async def handle(self, ctx: ActionContext) -> ActionResult:
        """
        执行图像生成

        ctx.kwargs 可以包含：
        - prompt: 图像描述
        - size: 尺寸（256x256/512x512/1024x1024）
        - style: 风格
        - n: 生成数量
        - output_dir: 保存目录
        """
        try:
            prompt = ctx.extra.get("prompt", "")
            if not prompt and ctx.intent.target:
                prompt = ctx.intent.target

            if not prompt:
                return ActionResult(
                    status=ActionResultStatus.NEED_CLARIFY,
                    clarification_prompt="请描述你想生成什么样的图像？",
                )

            size = ctx.extra.get("size", "512x512")
            style = ctx.extra.get("style", "photorealistic")
            n = ctx.extra.get("n", 1)
            output_dir = ctx.extra.get("output_dir", "./generated_images")

            logger.info(f"执行图像生成: prompt='{prompt[:50]}...', size={size}, style={style}")

            result = await self._do_generate(prompt, size, style, n, output_dir)

            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                output=result["message"],
                output_type="image_paths",
                artifacts=result.get("image_paths", []),
                suggestions=[
                    f"已生成 {n} 张图像，保存在：{result.get('output_dir', output_dir)}",
                    "可调整 style 参数改变图像风格",
                    "可指定 size 参数改变图像尺寸",
                ],
            )

        except Exception as e:
            logger.error(f"图像生成失败: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                error=f"图像生成失败: {str(e)}",
            )

    async def _do_generate(self, prompt: str, size: str,
                             style: str, n: int, output_dir: str) -> dict:
        """执行图像生成（优先使用 GlobalModelRouter，fallback 到外部 API）"""
        # 尝试使用 GlobalModelRouter（如果支持图像生成）
        try:
            from client.src.business.global_model_router import (
                get_global_router, ModelCapability,
            )
            router = get_global_router()
            # 注意：当前 GlobalModelRouter 尚未支持 IMAGE_GENERATION 能力
            # 将来可在此处调用
            # result = await router.call_model(
            #     capability=ModelCapability.IMAGE_GENERATION,
            #     prompt=prompt,
            # )
        except (ImportError, Exception):
            pass

        # 使用外部 API（DALL-E / Stable Diffusion）
        return await self._generate_via_external_api(prompt, size, style, n, output_dir)

    async def _generate_via_external_api(self, prompt: str, size: str,
                                         style: str, n: int, output_dir: str) -> dict:
        """通过外部 API 生成图像"""
        # 构建增强提示词（加入风格）
        style_hint = {
            "photorealistic": "photorealistic, high quality, detailed",
            "artistic": "artistic style, creative, vibrant colors",
            "anime": "anime style, cel shading, vibrant",
            "cyberpunk": "cyberpunk style, neon lights, futuristic",
            "oil_painting": "oil painting style, classical art",
            "watercolor": "watercolor style, soft colors, flowing",
        }.get(style, style)

        enhanced_prompt = f"{prompt}, {style_hint}"

        # 解析尺寸
        width, height = 512, 512
        if "x" in size:
            try:
                width, height = map(int, size.split("x"))
            except ValueError:
                pass

        # 尝试调用 Stable Diffusion API（本地）
        import os
        sd_url = os.environ.get("STABLE_DIFFUSION_URL", "http://localhost:7860")

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                payload = {
                    "prompt": enhanced_prompt,
                    "negative_prompt": "low quality, blurry, distorted",
                    "width": width,
                    "height": height,
                    "num_images": n,
                    "num_inference_steps": 20,
                }

                # Stable Diffusion Web UI API
                async with session.post(
                    f"{sd_url}/sdapi/v1/txt2img",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        import base64
                        import pathlib

                        output_path = pathlib.Path(output_dir)
                        output_path.mkdir(parents=True, exist_ok=True)

                        image_paths = []
                        for i, img_b64 in enumerate(data.get("images", [])):
                            img_data = base64.b64decode(img_b64)
                            img_path = output_path / f"generated_{i+1}.png"
                            img_path.write_bytes(img_data)
                            image_paths.append(str(img_path))

                        return {
                            "message": f"成功生成 {len(image_paths)} 张图像",
                            "image_paths": image_paths,
                            "output_dir": str(output_path),
                        }
                    else:
                        error_text = await resp.text()
                        raise RuntimeError(f"Stable Diffusion API 错误 {resp.status}: {error_text}")

        except ImportError:
            logger.warning("aiohttp 未安装，无法调用 Stable Diffusion API")
            return self._generate_placeholder(prompt, output_dir)
        except Exception as e:
            logger.warning(f"Stable Diffusion API 调用失败: {e}")
            return self._generate_placeholder(prompt, output_dir)

    def _generate_placeholder(self, prompt: str, output_dir: str) -> dict:
        """生成占位符（当 API 不可用时）"""
        import pathlib

        output_path = pathlib.Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        placeholder_path = output_path / "placeholder.txt"
        placeholder_path.write_text(
            f"图像生成请求（API 不可用）\n\n"
            f"Prompt: {prompt}\n"
            f"请配置 Stable Diffusion 或 DALL-E API 以生成真实图像。\n"
        )

        return {
            "message": "图像生成 API 不可用，已创建占位符文件。"
                        "请配置 STABLE_DIFFUSION_URL 环境变量，"
                        "或安装 Stable Diffusion Web UI。",
            "image_paths": [str(placeholder_path)],
            "output_dir": str(output_path),
        }
