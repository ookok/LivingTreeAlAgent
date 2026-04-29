"""
公司印章生成器 - Company Stamp Generator
基于 Pillow 图像处理生成标准公章/合同章

功能：
- 生成标准红色圆形公章（带五角星）
- 支持带编号和不带编号
- 支持合同章（椭圆形）
- 高分辨率 PNG 输出（透明背景）
- PDF 骑缝章支持

参考：https://gitee.com/simazehao/company-stamp
"""

import math
import io
from pathlib import Path
from typing import Optional, Tuple, Literal
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# 印章颜色
STAMP_RED = (255, 0, 0)
STAMP_RED_DARK = (220, 0, 0)
STAR_COLOR = STAMP_RED

# 标准公章尺寸（毫米转像素，300 DPI）
MM_TO_PX = 300 / 25.4  # 约 11.81 px/mm

# 印章类型
StampType = Literal["official", "contract", "invoice"]
NumberPosition = Literal["bottom", "right"]


@dataclass
class StampConfig:
    """印章配置"""
    company_name: str = "公司名称"
    stamp_type: StampType = "official"  # official=公章, contract=合同章, invoice=发票章
    number: Optional[str] = None  # 印章编号，如 "11010100001234"
    number_position: NumberPosition = "bottom"  # 编号位置

    # 尺寸参数（毫米）
    diameter: float = 42.0  # 圆形直径
    star_diameter: float = 14.0  # 五角星直径
    char_height: float = 7.5  # 字符高度
    char_width: float = 4.0  # 字符宽度

    # 分辨率
    dpi: int = 300

    # 字体
    font_family: str = "simsun"  # 宋体

    def __post_init__(self):
        self.dpi = max(150, min(600, self.dpi))


class CompanyStampGenerator:
    """公司印章生成器"""

    def __init__(self, config: Optional[StampConfig] = None):
        self.config = config or StampConfig()

    def generate(self) -> Image.Image:
        """生成印章图像"""
        if self.config.stamp_type == "official":
            return self._generate_official_seal()
        elif self.config.stamp_type == "contract":
            return self._generate_contract_seal()
        elif self.config.stamp_type == "invoice":
            return self._generate_invoice_seal()
        else:
            return self._generate_official_seal()

    def _generate_official_seal(self) -> Image.Image:
        """生成标准公章（圆形+五角星）"""
        # 计算尺寸
        diameter_px = int(self.config.diameter * MM_TO_PX)
        radius = diameter_px // 2
        center = radius

        # 创建透明背景图像
        img = Image.new('RGBA', (diameter_px, diameter_px), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # 绘制边框（多层圆圈，模拟印章效果）
        self._draw_circular_border(draw, center, radius)

        # 绘制五角星
        star_radius = int(self.config.star_diameter * MM_TO_PX / 2)
        self._draw_five_pointed_star(draw, center, center, star_radius)

        # 绘制文字
        self._draw_circular_text(draw, center, radius)

        # 绘制编号
        if self.config.number:
            self._draw_number(draw, center, radius)

        return img

    def _generate_contract_seal(self) -> Image.Image:
        """生成合同章（椭圆形）"""
        # 椭圆尺寸
        width_mm = 50.0
        height_mm = 30.0
        width_px = int(width_mm * MM_TO_PX)
        height_px = int(height_mm * MM_TO_PX)

        img = Image.new('RGBA', (width_px, height_px), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # 绘制椭圆边框
        self._draw_ellipse_border(draw, width_px, height_px)

        # 绘制文字（弧形排列在椭圆内）
        self._draw_ellipse_text(draw, width_px, height_px)

        # 绘制编号
        if self.config.number:
            self._draw_number_horizontal(draw, width_px, height_px)

        return img

    def _generate_invoice_seal(self) -> Image.Image:
        """生成发票章（方形）"""
        size_mm = 40.0
        size_px = int(size_mm * MM_TO_PX)

        img = Image.new('RGBA', (size_px, size_px), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # 绘制方形边框
        padding = int(2 * MM_TO_PX)
        draw.rectangle(
            [padding, padding, size_px - padding, size_px - padding],
            outline=STAMP_RED,
            width=max(2, int(1.5 * MM_TO_PX))
        )
        # 内部方框
        inner_padding = int(5 * MM_TO_PX)
        draw.rectangle(
            [inner_padding, inner_padding, size_px - inner_padding, size_px - inner_padding],
            outline=STAMP_RED,
            width=1
        )

        # 绘制文字
        self._draw_square_text(draw, size_px)

        # 绘制编号
        if self.config.number:
            self._draw_number_square(draw, size_px)

        return img

    def _draw_circular_border(self, draw: ImageDraw.ImageDraw, center: int, radius: int):
        """绘制圆形边框"""
        # 外圈
        outer_r = radius
        inner_r = radius - int(1.5 * MM_TO_PX)

        # 多层圆圈效果
        for i in range(3):
            r = outer_r - i * int(0.5 * MM_TO_PX)
            draw.ellipse(
                [center - r, center - r, center + r, center + r],
                outline=STAMP_RED,
                width=max(2, int(1.2 * MM_TO_PX) - i)
            )

        # 最内圈实线
        draw.ellipse(
            [center - inner_r, center - inner_r, center + inner_r, center + inner_r],
            outline=STAMP_RED,
            width=1
        )

    def _draw_ellipse_border(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """绘制椭圆边框"""
        padding = int(1.5 * MM_TO_PX)
        draw.ellipse(
            [padding, padding, width - padding, height - padding],
            outline=STAMP_RED,
            width=max(2, int(1.5 * MM_TO_PX))
        )

    def _draw_five_pointed_star(
        self,
        draw: ImageDraw.ImageDraw,
        cx: int,
        cy: int,
        radius: int
    ):
        """绘制五角星"""
        # 计算五角星顶点
        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5  # 从顶部开始
            r = radius if i % 2 == 0 else radius * 0.4
            x = cx + r * math.cos(angle)
            y = cy - r * math.sin(angle)
            points.append((x, y))

        # 绘制实心五角星
        draw.polygon(points, fill=STAR_COLOR, outline=STAR_COLOR)

    def _draw_circular_text(self, draw: ImageDraw.ImageDraw, center: int, radius: int):
        """绘制环形文字（公司名称）"""
        text = self.config.company_name
        if not text:
            return

        # 字符到圆心距离
        char_radius = int(radius * 0.72)

        # 计算每个字符的角度范围
        char_count = len(text)
        # 起始角度（约135度，即左下角）
        start_angle = math.pi * 0.75
        # 用约270度圆周排列
        angle_range = math.pi * 1.5

        # 字体大小
        font_size = int(self.config.char_height * MM_TO_PX * 0.75)

        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("msyh.ttc", font_size)
            except:
                try:
                    font = ImageFont.truetype("simsun.ttc", font_size)
                except:
                    font = ImageFont.load_default()

        for i, char in enumerate(text):
            # 计算字符位置角度
            if char_count > 1:
                char_angle = start_angle + (i / (char_count - 1)) * angle_range
            else:
                char_angle = start_angle + angle_range / 2

            # 字符中心位置
            char_x = center + char_radius * math.cos(char_angle)
            char_y = center - char_radius * math.sin(char_angle)

            # 字符旋转角度（底部指向圆心）
            rotation = math.degrees(char_angle) - 90

            # 创建临时图像绘制旋转字符
            char_img = Image.new('RGBA', (font_size * 2, font_size * 2), (255, 255, 255, 0))
            char_draw = ImageDraw.Draw(char_img)
            char_draw.text(
                (font_size, font_size),
                char,
                font=font,
                fill=STAMP_RED + (255,),
                anchor='mm'
            )

            # 旋转
            char_img = char_img.rotate(rotation, resample=Image.BICUBIC, expand=0)

            # 合成到主图像
            paste_x = int(char_x - char_img.width / 2)
            paste_y = int(char_y - char_img.height / 2)
            img_w, img_h = char_img.size
            for y in range(img_h):
                for x in range(img_w):
                    pixel = char_img.getpixel((x, y))
                    if pixel[3] > 128:  # 非透明
                        px = paste_x + x
                        py = paste_y + y
                        if 0 <= px < center * 2 and 0 <= py < center * 2:
                            draw.point((px, py), fill=pixel[:4])

    def _draw_ellipse_text(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """绘制椭圆内文字（合同章用）"""
        text = self.config.company_name
        if not text:
            return

        font_size = int(6 * MM_TO_PX)
        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # 居中绘制文字
        avg_radius = (width + height) // 4
        char_count = len(text)
        total_width = char_count * font_size * 0.8
        start_x = (width - total_width) // 2

        for i, char in enumerate(text):
            x = start_x + i * font_size * 0.8
            y = height // 2 - font_size // 2
            draw.text((x, y), char, font=font, fill=STAMP_RED + (255,))

    def _draw_square_text(self, draw: ImageDraw.ImageDraw, size: int):
        """绘制方形印章内的文字"""
        text = self.config.company_name
        if not text:
            return

        font_size = int(5 * MM_TO_PX)
        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # 分两行或三行显示
        center = size // 2
        draw.text((center, center - font_size), text[:4], font=font, fill=STAMP_RED + (255,), anchor='mm')
        if len(text) > 4:
            draw.text((center, center + font_size), text[4:8], font=font, fill=STAMP_RED + (255,), anchor='mm')

    def _draw_number(self, draw: ImageDraw.ImageDraw, center: int, radius: int):
        """绘制印章编号（圆形公章）"""
        if not self.config.number:
            return

        font_size = int(5 * MM_TO_PX)
        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            font = ImageFont.load_default()

        number = self.config.number
        number_radius = int(radius * 0.55)

        if self.config.number_position == "bottom":
            # 底部居中
            angle = math.pi / 2  # 底部
            nx = center + number_radius * math.cos(angle)
            ny = center + number_radius * math.sin(angle)
            draw.text((nx, ny), number, font=font, fill=STAMP_RED + (255,), anchor='mm')
        else:
            # 右侧
            angle = 0
            nx = center + number_radius
            ny = center
            draw.text((nx, ny), number, font=font, fill=STAMP_RED + (255,), anchor='lm')

    def _draw_number_horizontal(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """绘制编号（横排，用于合同章）"""
        if not self.config.number:
            return

        font_size = int(4 * MM_TO_PX)
        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            font = ImageFont.load_default()

        number = self.config.number
        text_w = len(number) * font_size * 0.6
        x = (width - text_w) // 2
        y = height - int(6 * MM_TO_PX)
        draw.text((x, y), number, font=font, fill=STAMP_RED + (255,))

    def _draw_number_square(self, draw: ImageDraw.ImageDraw, size: int):
        """绘制编号（方形章）"""
        if not self.config.number:
            return

        font_size = int(4 * MM_TO_PX)
        try:
            font = ImageFont.truetype(f"{self.config.font_family}.ttf", font_size)
        except:
            font = ImageFont.load_default()

        number = self.config.number
        y = size - int(7 * MM_TO_PX)
        text_w = len(number) * font_size * 0.6
        x = (size - text_w) // 2
        draw.text((x, y), number, font=font, fill=STAMP_RED + (255,))

    def save(self, filepath: str, fmt: str = "PNG"):
        """保存印章图像"""
        img = self.generate()
        img.save(filepath, fmt=fmt)
        return filepath

    def to_bytes(self, fmt: str = "PNG") -> bytes:
        """导出为字节数据"""
        img = self.generate()
        buf = io.BytesIO()
        img.save(buf, fmt=fmt)
        return buf.getvalue()

    def to_data_url(self, fmt: str = "PNG") -> str:
        """导出为 Data URL（用于 HTML 显示）"""
        img_bytes = self.to_bytes(fmt)
        import base64
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/{fmt.lower()};base64,{b64}"


class StampPreviewGenerator:
    """印章预览生成器（低分辨率快速预览）"""

    @staticmethod
    def generate_preview(config: StampConfig, max_size: int = 200) -> Image.Image:
        """生成低分辨率预览"""
        # 临时降低 DPI
        original_dpi = config.dpi
        config.dpi = 72  # 低分辨率

        generator = CompanyStampGenerator(config)
        img = generator.generate()

        # 缩放到预览尺寸
        img.thumbnail((max_size, max_size), Image.LANCZOS)

        # 恢复原始 DPI
        config.dpi = original_dpi

        return img


# 全局单例
_generator: Optional[CompanyStampGenerator] = None


def get_stamp_generator() -> CompanyStampGenerator:
    """获取印章生成器单例"""
    global _generator
    if _generator is None:
        _generator = CompanyStampGenerator()
    return _generator


def generate_stamp(
    company_name: str,
    stamp_type: StampType = "official",
    number: Optional[str] = None,
    dpi: int = 300
) -> Image.Image:
    """快捷函数：生成印章"""
    config = StampConfig(
        company_name=company_name,
        stamp_type=stamp_type,
        number=number,
        dpi=dpi
    )
    return CompanyStampGenerator(config).generate()