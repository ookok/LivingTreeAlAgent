# core/flash_listing/vision_analyzer.py
# 图片特征提取与理解 - AI视觉模块
#
# 使用轻量级视觉模型提取商品特征：
# - 品类识别
# - 关键属性（材质/尺寸/接口）
# - OCR铭牌提取

import os
import io
import base64
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """
    图片特征提取器

    使用多策略提取图片特征：
    1. 颜色/纹理分析（基础）
    2. 形状检测（轮廓/边缘）
    3. OCR文字识别（如有铭牌）
    4. 可扩展：集成MobileViT/CNN等视觉模型
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 图片尺寸限制
        self.max_image_size = self.config.get("max_image_size", 2048)

        # OCR 引擎（待集成）
        self.ocr_enabled = self.config.get("ocr_enabled", True)

        # 视觉模型（待集成）
        self.vision_model = None
        self._model_loaded = False

        # 回调
        self.on_progress: Optional[Callable] = None

    async def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        分析图片并提取特征

        Args:
            image_path: 图片路径

        Returns:
            特征字典
        """
        try:
            # 检查文件
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片不存在: {image_path}")

            # 加载图片
            image = Image.open(image_path)
            width, height = image.size

            # 提取特征
            features = {
                "feature_id": "",
                "category": "",
                "category_confidence": 0.0,
                "material": None,
                "size_estimate": None,
                "interface_type": None,
                "application": None,
                "ocr_text": None,
                "model_number": None,
                "power_rating": None,
                "voltage": None,
                "original_image_path": image_path,
                "thumbnail_path": None,
                "width": width,
                "height": height,
                "format": image.format or "UNKNOWN",
            }

            # 进度更新
            if self.on_progress:
                await self.on_progress("正在分析图片...", 20)

            # 1. 颜色分析
            color_features = self._analyze_colors(image)

            # 2. 纹理分析
            texture_features = self._analyze_texture(image)

            # 3. 形状分析
            shape_features = self._analyze_shape(image)

            # 4. OCR（如启用）
            if self.ocr_enabled:
                ocr_result = await self._extract_ocr(image)
                features.update(ocr_result)

            # 5. 综合推理品类
            category, confidence = self._infer_category(
                color_features, texture_features, shape_features, features
            )
            features["category"] = category
            features["category_confidence"] = confidence

            # 6. 生成缩略图
            thumbnail_path = self._generate_thumbnail(image, image_path)
            features["thumbnail_path"] = thumbnail_path

            # 7. 推断材质/属性
            material, size, interface = self._infer_attributes(
                color_features, texture_features, shape_features, features
            )
            features["material"] = material
            features["size_estimate"] = size
            features["interface_type"] = interface

            if self.on_progress:
                await self.on_progress("分析完成", 100)

            logger.info(f"[VisionAnalyzer] 图片分析完成: {category} ({confidence:.1%})")
            return features

        except Exception as e:
            logger.error(f"[VisionAnalyzer] 图片分析失败: {e}")
            raise

    async def analyze_images_batch(
        self, image_paths: List[str], max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        批量分析图片

        Args:
            image_paths: 图片路径列表
            max_concurrent: 最大并发数

        Returns:
            特征列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(path):
            async with semaphore:
                return await self.analyze_image(path)

        tasks = [analyze_with_limit(p) for p in image_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤异常
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[VisionAnalyzer] 第{i}张图片分析失败: {result}")
            else:
                valid_results.append(result)

        return valid_results

    def _analyze_colors(self, image: Image.Image) -> Dict[str, Any]:
        """分析颜色特征"""
        # 缩放以加速
        img = image.copy()
        img.thumbnail((100, 100))

        # 转换为RGB
        if img.mode != "RGB":
            img = img.convert("RGB")

        pixels = np.array(img)
        pixels = pixels.reshape(-1, 3)

        # 计算平均颜色
        avg_color = pixels.mean(axis=0)
        r, g, b = avg_color

        # 判断主色调
        if r > 150 and g > 150 and b > 150:
            main_tone = "light"
        elif r < 80 and g < 80 and b < 80:
            main_tone = "dark"
        elif r > g and r > b:
            main_tone = "red"
        elif g > r and g > b:
            main_tone = "green"
        elif b > r and b > g:
            main_tone = "blue"
        elif max(r, g, b) - min(r, g, b) < 30:
            main_tone = "gray"
        else:
            main_tone = "neutral"

        # 判断是否为金属色（高对比度/镜面效果）
        std = pixels.std(axis=0).mean()
        is_metallic = std > 50

        return {
            "avg_rgb": (float(r), float(g), float(b)),
            "main_tone": main_tone,
            "is_metallic": is_metallic,
            "brightness": float((r + g + b) / 3 / 255),
        }

    def _analyze_texture(self, image: Image.Image) -> Dict[str, Any]:
        """分析纹理特征"""
        img = image.copy()
        img.thumbnail((64, 64))

        if img.mode != "L":
            img = img.convert("L")

        pixels = np.array(img, dtype=np.float32)

        # 简化的纹理分析
        variance = float(pixels.var())
        edges = self._count_edges(pixels)

        # 判断粗糙度
        if variance < 100:
            roughness = "smooth"
        elif variance < 500:
            roughness = "medium"
        else:
            roughness = "rough"

        return {
            "variance": variance,
            "edge_count": edges,
            "roughness": roughness,
        }

    def _count_edges(self, pixels: np.ndarray) -> int:
        """计数边缘（简化）"""
        # 简化的边缘检测
        diff_x = np.abs(np.diff(pixels, axis=1)).mean()
        diff_y = np.abs(np.diff(pixels, axis=0)).mean()
        return int((diff_x + diff_y) * 100)

    def _analyze_shape(self, image: Image.Image) -> Dict[str, Any]:
        """分析形状特征"""
        img = image.copy()
        img.thumbnail((100, 100))

        if img.mode != "L":
            img = img.convert("L")

        pixels = np.array(img)
        binary = pixels < 128

        # 计算非零像素比例（形状占比）
        shape_ratio = float(binary.sum() / binary.size)

        # 简化形状判断
        if shape_ratio < 0.1:
            shape_type = "small_object"
        elif shape_ratio < 0.3:
            shape_type = "compact"
        elif shape_ratio < 0.6:
            shape_type = "regular"
        else:
            shape_type = "flat"

        return {
            "shape_ratio": shape_ratio,
            "shape_type": shape_type,
        }

    async def _extract_ocr(self, image: Image.Image) -> Dict[str, Any]:
        """
        提取OCR文字（待集成专业OCR）

        目前返回空结果，后续可集成：
        - Tesseract OCR
        - 百度OCR
        - PaddleOCR
        """
        # TODO: 集成专业OCR引擎
        return {
            "ocr_text": None,
            "model_number": None,
            "power_rating": None,
            "voltage": None,
        }

    def _infer_category(
        self,
        color: Dict,
        texture: Dict,
        shape: Dict,
        features: Dict,
    ) -> tuple:
        """
        综合推理商品品类

        Returns:
            (category: str, confidence: float)
        """
        # 基于颜色和纹理的规则判断
        category_hints = []

        # 金属检测
        if color.get("is_metallic"):
            if color["main_tone"] in ["gray", "neutral"]:
                category_hints.append(("metal", 0.7))
            elif color["main_tone"] in ["red", "blue", "green"]:
                category_hints.append(("machinery", 0.6))

        # 塑料检测
        if not color.get("is_metallic"):
            if texture.get("roughness") == "smooth":
                if color["brightness"] > 0.7:
                    category_hints.append(("plastic", 0.6))

        # 电子产品检测（LED发光）
        if color["main_tone"] in ["light"] and color["brightness"] > 0.8:
            category_hints.append(("electronics", 0.5))

        # 基于OCR（如识别到型号）
        if features.get("ocr_text"):
            text = features["ocr_text"]
            if any(kw in text for kw in ["LED", "灯", "电源"]):
                category_hints.append(("electronics", 0.8))
            if any(kw in text for kw in ["电机", "马达"]):
                category_hints.append(("machinery", 0.8))
            if any(kw in text for kw in ["ABS", "PVC", "塑料"]):
                category_hints.append(("plastic", 0.8))

        # 综合评分
        if not category_hints:
            return "other", 0.3

        # 取最高分
        best = max(category_hints, key=lambda x: x[1])
        return best[0], best[1]

    def _infer_attributes(
        self,
        color: Dict,
        texture: Dict,
        shape: Dict,
        features: Dict,
    ) -> tuple:
        """
        推断材质/尺寸/接口

        Returns:
            (material, size_estimate, interface_type)
        """
        material = None
        size_estimate = None
        interface_type = None

        # 材质推断
        if color.get("is_metallic"):
            material = "金属"
        elif texture.get("roughness") == "smooth":
            material = "塑料"

        # OCR提取的参数
        if features.get("power_rating"):
            size_estimate = features["power_rating"]
        if features.get("model_number"):
            interface_type = self._extract_interface_hint(features["model_number"])

        return material, size_estimate, interface_type

    def _extract_interface_hint(self, model: str) -> Optional[str]:
        """从型号提取接口提示"""
        interface_keywords = {
            "E27": "E27螺口",
            "E14": "E14螺口",
            "GU10": "GU10卡口",
            "MR16": "MR16卡口",
            "G13": "G13灯管",
            "T8": "T8灯管",
        }

        for kw, interface in interface_keywords.items():
            if kw in model.upper():
                return interface

        return None

    def _generate_thumbnail(self, image: Image.Image, original_path: str) -> str:
        """生成缩略图"""
        try:
            # 创建缩略图
            thumb = image.copy()
            thumb.thumbnail((300, 300))

            # 保存
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            thumb_dir = os.path.join(os.path.dirname(original_path), ".thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)

            thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb.jpg")
            thumb.save(thumb_path, "JPEG", quality=85)

            return thumb_path
        except Exception as e:
            logger.warning(f"[VisionAnalyzer] 缩略图生成失败: {e}")
            return original_path

    async def load_vision_model(self):
        """加载视觉模型（待实现）"""
        if self._model_loaded:
            return

        # TODO: 集成轻量级视觉模型
        # 建议使用：
        # - MobileViT (onnxruntime)
        # - EfficientNet-Lite
        # - CLIP (用于图像-文本对齐)

        logger.info("[VisionAnalyzer] 使用基础特征提取，视觉模型待集成")
        self._model_loaded = True


# ========== 便捷函数 ==========

async def analyze_product_image(image_path: str) -> Dict[str, Any]:
    """快捷函数：分析商品图片"""
    analyzer = VisionAnalyzer()
    return await analyzer.analyze_image(image_path)


async def analyze_product_images(image_paths: List[str]) -> List[Dict[str, Any]]:
    """快捷函数：批量分析商品图片"""
    analyzer = VisionAnalyzer()
    return await analyzer.analyze_images_batch(image_paths)
