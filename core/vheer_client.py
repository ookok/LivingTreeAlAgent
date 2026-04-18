"""
Vheer 多模态客户端
=================

Vheer AI 平台集成 - 免费图像/视频生成

官网: https://vheer.com (示例)
功能:
- 文生图 (Text to Image)
- 图生视频 (Image to Video)
- 文生视频 (Text to Video)
- 多种 AI 模型支持
"""

import json
import time
import asyncio
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import urllib.request
import urllib.error


class VheerModel(Enum):
    """Vheer 支持的模型"""
    # 图像模型
    FLUX_DEV = "flux-dev"
    FLUX_SCHNELL = "flux-schnell"
    SDXL = "sdxl"
    SD_15 = "sd-1.5"
    PLAYGROUND = "playground"

    # 视频模型
    WAN2_1 = "wan-2.1"
    LTXV = "ltxv"
    COSMOS = "cosmos"

    # 专业模型
    PROTAX = "protax"
    RELINE = "reline"


class ImageStyle(Enum):
    """图像风格"""
    REALISTIC = "realistic"
    ANIME = "anime"
    DIGITAL_ART = "digital-art"
    OIL_PAINTING = "oil-painting"
    WATERCOLOR = "watercolor"
    ABSTRACT = "abstract"
    CYBERPUNK = "cyberpunk"
    FANTASY = "fantasy"


@dataclass
class ImageGenerationParams:
    """图像生成参数"""
    model: str = VheerModel.FLUX_SCHNELL.value
    width: int = 1024
    height: int = 1024
    style: str = ImageStyle.REALISTIC.value
    quality: str = "standard"  # standard/high/ultra
    seed: Optional[int] = None
    steps: int = 25
    guidance_scale: float = 7.5


@dataclass
class VideoGenerationParams:
    """视频生成参数"""
    model: str = VheerModel.WAN2_1.value
    duration: int = 5  # 秒
    fps: int = 24
    resolution: str = "720p"  # 480p/720p/1080p
    seed: Optional[int] = None


@dataclass
class GenerationResult:
    """生成结果"""
    task_id: str
    status: str  # pending/processing/completed/failed
    result_url: Optional[str] = None
    preview_url: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VheerClient:
    """
    Vheer 多模态客户端

    支持:
    - 文生图
    - 图生视频
    - 文生视频
    - 免费无限制生成
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.vheer.com/v1",
        timeout: int = 120
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # 速率限制
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 秒

    def _wait_for_rate_limit(self):
        """速率限制等待"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        files: Dict = None
    ) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        self._wait_for_rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            if method == "GET":
                req = urllib.request.Request(
                    url,
                    headers=headers,
                    method="GET"
                )
            else:
                body = json.dumps(data).encode("utf-8") if data else None
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers=headers,
                    method=method
                )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            try:
                error_json = json.loads(error_body)
                return {"error": error_json.get("message", error_body), "status_code": e.code}
            except json.JSONDecodeError:
                return {"error": error_body, "status_code": e.code}

        except urllib.error.URLError as e:
            return {"error": f"Network error: {e.reason}"}

        except Exception as e:
            return {"error": str(e)}

    async def text_to_image(
        self,
        prompt: str,
        params: ImageGenerationParams = None,
        **kwargs
    ) -> GenerationResult:
        """
        文生图

        Args:
            prompt: 文本描述
            params: 生成参数
            **kwargs: 其他参数覆盖

        Returns:
            GenerationResult
        """
        if params is None:
            params = ImageGenerationParams()

        # 合并参数
        config = {
            "prompt": prompt,
            "model": kwargs.get("model", params.model),
            "width": kwargs.get("width", params.width),
            "height": kwargs.get("height", params.height),
            "style": kwargs.get("style", params.style),
            "quality": kwargs.get("quality", params.quality),
            "steps": kwargs.get("steps", params.steps),
            "guidance_scale": kwargs.get("guidance_scale", params.guidance_scale),
        }

        if params.seed is not None:
            config["seed"] = params.seed

        # 发送请求
        result = self._make_request("POST", "/images/generate", config)

        if "error" in result:
            return GenerationResult(
                task_id="",
                status="failed",
                error=result["error"]
            )

        return GenerationResult(
            task_id=result.get("task_id", ""),
            status=result.get("status", "pending"),
            result_url=result.get("image_url"),
            preview_url=result.get("preview_url"),
            metadata=result
        )

    async def image_to_video(
        self,
        image_path: str,
        params: VideoGenerationParams = None,
        **kwargs
    ) -> GenerationResult:
        """
        图生视频

        Args:
            image_path: 输入图像路径
            params: 生成参数
            **kwargs: 其他参数覆盖

        Returns:
            GenerationResult
        """
        if params is None:
            params = VideoGenerationParams()

        # 读取图像
        image_path = Path(image_path)
        if not image_path.exists():
            return GenerationResult(
                task_id="",
                status="failed",
                error=f"Image not found: {image_path}"
            )

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        config = {
            "image": image_base64,
            "model": kwargs.get("model", params.model),
            "duration": kwargs.get("duration", params.duration),
            "fps": kwargs.get("fps", params.fps),
            "resolution": kwargs.get("resolution", params.resolution),
        }

        if params.seed is not None:
            config["seed"] = params.seed

        result = self._make_request("POST", "/videos/image-to-video", config)

        if "error" in result:
            return GenerationResult(
                task_id="",
                status="failed",
                error=result["error"]
            )

        return GenerationResult(
            task_id=result.get("task_id", ""),
            status=result.get("status", "pending"),
            result_url=result.get("video_url"),
            preview_url=result.get("preview_url"),
            metadata=result
        )

    async def text_to_video(
        self,
        prompt: str,
        params: VideoGenerationParams = None,
        **kwargs
    ) -> GenerationResult:
        """
        文生视频

        Args:
            prompt: 文本描述
            params: 生成参数
            **kwargs: 其他参数覆盖

        Returns:
            GenerationResult
        """
        if params is None:
            params = VideoGenerationParams()

        config = {
            "prompt": prompt,
            "model": kwargs.get("model", params.model),
            "duration": kwargs.get("duration", params.duration),
            "fps": kwargs.get("fps", params.fps),
            "resolution": kwargs.get("resolution", params.resolution),
        }

        if params.seed is not None:
            config["seed"] = params.seed

        result = self._make_request("POST", "/videos/text-to-video", config)

        if "error" in result:
            return GenerationResult(
                task_id="",
                status="failed",
                error=result["error"]
            )

        return GenerationResult(
            task_id=result.get("task_id", ""),
            status=result.get("status", "pending"),
            result_url=result.get("video_url"),
            preview_url=result.get("preview_url"),
            metadata=result
        )

    def get_task_status(self, task_id: str) -> GenerationResult:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            GenerationResult
        """
        result = self._make_request("GET", f"/tasks/{task_id}")

        if "error" in result:
            return GenerationResult(
                task_id=task_id,
                status="failed",
                error=result["error"]
            )

        return GenerationResult(
            task_id=task_id,
            status=result.get("status", "unknown"),
            result_url=result.get("result_url"),
            preview_url=result.get("preview_url"),
            metadata=result
        )

    def download_result(self, url: str, save_path: Path) -> bool:
        """
        下载结果

        Args:
            url: 结果 URL
            save_path: 保存路径

        Returns:
            是否下载成功
        """
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=300) as response:
                content = response.read()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)
                return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def list_available_models(self, type: str = "image") -> List[Dict[str, Any]]:
        """
        列出可用模型

        Args:
            type: 模型类型 (image/video)

        Returns:
            模型列表
        """
        result = self._make_request("GET", f"/models?type={type}")

        if "error" in result:
            return []

        return result.get("models", [])


class VheerService:
    """
    Vheer 服务封装

    提供更高级的接口
    """

    def __init__(self, client: VheerClient = None):
        self.client = client or VheerClient()

    async def generate_image(
        self,
        prompt: str,
        style: str = None,
        size: str = "square",
        **kwargs
    ) -> Optional[str]:
        """
        生成图像并返回 URL

        Args:
            prompt: 提示词
            style: 风格
            size: 尺寸 (square/portrait/landscape)
            **kwargs: 其他参数

        Returns:
            图像 URL 或 None
        """
        # 尺寸映射
        size_map = {
            "square": (1024, 1024),
            "portrait": (768, 1024),
            "landscape": (1024, 768),
            "wide": (1024, 576),
        }

        width, height = size_map.get(size, (1024, 1024))

        params = ImageGenerationParams(
            width=width,
            height=height,
            style=style or ImageStyle.REALISTIC.value
        )

        result = await self.client.text_to_image(prompt, params, **kwargs)

        if result.status == "completed":
            return result.result_url

        # 轮询状态
        for _ in range(60):  # 最多等待 60 次
            await asyncio.sleep(2)
            status = self.client.get_task_status(result.task_id)
            if status.status == "completed":
                return status.result_url
            elif status.status == "failed":
                return None

        return None

    async def generate_video_from_image(
        self,
        image_path: str,
        duration: int = 5,
        **kwargs
    ) -> Optional[str]:
        """
        从图像生成视频

        Args:
            image_path: 输入图像
            duration: 时长（秒）
            **kwargs: 其他参数

        Returns:
            视频 URL 或 None
        """
        params = VideoGenerationParams(duration=duration)
        result = await self.client.image_to_video(image_path, params, **kwargs)

        if result.status == "completed":
            return result.result_url

        # 轮询状态
        for _ in range(120):  # 视频生成需要更长时间
            await asyncio.sleep(3)
            status = self.client.get_task_status(result.task_id)
            if status.status == "completed":
                return status.result_url
            elif status.status == "failed":
                return None

        return None

    async def generate_video_from_text(
        self,
        prompt: str,
        duration: int = 5,
        **kwargs
    ) -> Optional[str]:
        """
        从文本生成视频

        Args:
            prompt: 提示词
            duration: 时长（秒）
            **kwargs: 其他参数

        Returns:
            视频 URL 或 None
        """
        params = VideoGenerationParams(duration=duration)
        result = await self.client.text_to_video(prompt, params, **kwargs)

        if result.status == "completed":
            return result.result_url

        # 轮询状态
        for _ in range(120):
            await asyncio.sleep(3)
            status = self.client.get_task_status(result.task_id)
            if status.status == "completed":
                return status.result_url
            elif status.status == "failed":
                return None

        return None


# 单例
_vheer_client: Optional[VheerClient] = None
_vheer_service: Optional[VheerService] = None


def get_vheer_client() -> VheerClient:
    """获取 Vheer 客户端"""
    global _vheer_client
    if _vheer_client is None:
        _vheer_client = VheerClient()
    return _vheer_client


def get_vheer_service() -> VheerService:
    """获取 Vheer 服务"""
    global _vheer_service
    if _vheer_service is None:
        _vheer_service = VheerService(get_vheer_client())
    return _vheer_service
