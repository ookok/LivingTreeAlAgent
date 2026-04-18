"""
PDF 骑缝章工具 - PDF Stamp Tool
支持在 PDF 文档上盖骑缝章

功能：
- 在 PDF 页面边缘盖骑缝章（半章在页面内，半章在页面外）
- 支持多页连续骑缝章
- 印章半透明处理，更自然
- 预览功能

依赖：PyMuPDF (fitz)
"""

import io
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
from PIL import Image
import math

# 尝试导入 PyMuPDF
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


@dataclass
class StampPosition:
    """印章位置"""
    x: float  # 左下角 x 坐标 (points)
    y: float  # 左下角 y 坐标 (points)
    width: float  # 印章宽度 (points)
    height: float  # 印章高度 (points)
    rotation: float = 0  # 旋转角度（度）


@dataclass
class PageStampConfig:
    """页面印章配置"""
    stamp_img: Image.Image  # 印章图像
    position: str = "right"  # left/right - 靠左还是靠右
    vertical_align: str = "center"  # top/center/bottom
    margin: float = 10  # 边缘距离 (points)
    opacity: float = 0.7  # 透明度


class PDFStampTool:
    """PDF 骑缝章工具"""

    def __init__(self):
        self.stamp_img: Optional[Image.Image] = None

    def load_stamp_from_image(self, img: Image.Image):
        """从 PIL Image 加载印章"""
        self.stamp_img = img.convert('RGBA')

    def load_stamp_from_file(self, filepath: str):
        """从文件加载印章"""
        self.stamp_img = Image.open(filepath).convert('RGBA')

    def load_stamp_from_bytes(self, img_bytes: bytes):
        """从字节数据加载印章"""
        self.stamp_img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')

    def apply_stamp_to_pdf(
        self,
        pdf_path: str,
        output_path: str,
        config: PageStampConfig,
        start_page: int = 0,
        end_page: Optional[int] = None,
        stamp_per_page: int = 1
    ) -> str:
        """
        在 PDF 页面上盖骑缝章

        Args:
            pdf_path: PDF 文件路径
            output_path: 输出文件路径
            config: 印章配置
            start_page: 起始页（0-based）
            end_page: 结束页（0-based，None 表示最后一页）
            stamp_per_page: 每页印章数量

        Returns:
            输出文件路径
        """
        if not HAS_FITZ:
            raise RuntimeError("需要安装 PyMuPDF: pip install pymupdf")

        if self.stamp_img is None:
            raise ValueError("请先加载印章图像")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        if end_page is None:
            end_page = total_pages - 1

        # 将印章转换为 bytes
        stamp_bytes = self._image_to_bytes(self.stamp_img)

        for page_num in range(start_page, min(end_page + 1, total_pages)):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height

            for i in range(stamp_per_page):
                # 计算印章位置
                pos = self._calculate_position(
                    page_width, page_height,
                    config.position,
                    config.vertical_align,
                    config.margin,
                    i, stamp_per_page
                )

                # 创建印章图像矩形
                rect = fitz.Rect(pos.x, pos.y, pos.x + pos.width, pos.y + pos.height)

                # 插入印章图像
                page.insert_image(
                    rect,
                    filename=None,
                    stream=stamp_bytes,
                    overlay=True
                )

                # 应用透明度（通过绘制半透明覆盖层）
                if config.opacity < 1.0:
                    self._apply_opacity(page, rect, config.opacity)

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        return output_path

    def apply_rolling_stamp(
        self,
        pdf_path: str,
        output_path: str,
        stamp_img: Image.Image,
        position: str = "right",
        margin: float = 10,
        opacity: float = 0.7
    ) -> str:
        """
        在多页 PDF 上应用连续骑缝章

        骑缝章效果：印章横跨两页或多页，每页只显示一半

        Args:
            pdf_path: PDF 文件路径
            output_path: 输出文件路径
            stamp_img: 印章图像
            position: 靠左(left)还是靠右(right)
            margin: 边缘距离
            opacity: 透明度

        Returns:
            输出文件路径
        """
        if not HAS_FITZ:
            raise RuntimeError("需要安装 PyMuPDF: pip install pymupdf")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # 将印章分成两半
        stamp_half_left, stamp_half_right = self._split_stamp_horizontal(stamp_img)

        stamp_bytes_left = self._image_to_bytes(stamp_half_left)
        stamp_bytes_right = self._image_to_bytes(stamp_half_right)

        page_height = None
        page_width = None

        for page_num in range(total_pages):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height

            # 计算印章尺寸（高度占页面高度的一半左右）
            stamp_height = page_height * 0.4
            stamp_width = stamp_height  # 假设印章是圆形的

            if position == "right":
                # 右侧骑缝章
                # 当前页显示左半章
                x1 = page_width - stamp_width / 2
                y1 = (page_height - stamp_height) / 2
                rect_left = fitz.Rect(x1, y1, x1 + stamp_width / 2, y1 + stamp_height)

                page.insert_image(rect_left, stream=stamp_bytes_left, overlay=True)

                # 下一页显示右半章
                if page_num < total_pages - 1:
                    next_page = doc[page_num + 1]
                    x2 = page_width - stamp_width / 2
                    y2 = (page_height - stamp_height) / 2
                    rect_right = fitz.Rect(x2, y2, x2 + stamp_width / 2, y2 + stamp_height)

                    next_page.insert_image(rect_right, stream=stamp_bytes_right, overlay=True)
            else:
                # 左侧骑缝章
                # 当前页显示右半章
                x1 = 0
                y1 = (page_height - stamp_height) / 2
                rect_right = fitz.Rect(x1, y1, x1 + stamp_width / 2, y1 + stamp_height)

                page.insert_image(rect_right, stream=stamp_bytes_right, overlay=True)

                # 下一页显示左半章
                if page_num < total_pages - 1:
                    next_page = doc[page_num + 1]
                    x2 = 0
                    y2 = (page_height - stamp_height) / 2
                    rect_left = fitz.Rect(x2, y2, x2 + stamp_width / 2, y2 + stamp_height)

                    next_page.insert_image(rect_left, stream=stamp_bytes_left, overlay=True)

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        return output_path

    def _calculate_position(
        self,
        page_width: float,
        page_height: float,
        h_align: str,
        v_align: str,
        margin: float,
        stamp_index: int,
        total_stamps: int
    ) -> StampPosition:
        """计算印章位置"""
        # 印章尺寸（高度约页面宽度的1/4）
        stamp_size = page_width * 0.2

        # 水平位置
        if h_align == "left":
            x = margin
        else:  # right
            x = page_width - stamp_size - margin

        # 垂直位置（如果是多个印章，均匀分布）
        if total_stamps == 1:
            if v_align == "top":
                y = page_height - stamp_size - margin
            elif v_align == "bottom":
                y = margin
            else:  # center
                y = (page_height - stamp_size) / 2
        else:
            # 多个印章均匀分布
            spacing = (page_height - stamp_size * total_stamps) / (total_stamps + 1)
            y = spacing + stamp_index * (stamp_size + spacing)

        return StampPosition(
            x=x,
            y=y,
            width=stamp_size,
            height=stamp_size
        )

    def _split_stamp_horizontal(self, img: Image.Image) -> Tuple[Image.Image, Image.Image]:
        """将印章水平切成两半"""
        width, height = img.size
        half_width = width // 2

        # 左半部分
        left = img.crop((0, 0, half_width, height))
        # 右半部分
        right = img.crop((half_width, 0, width, height))

        return left, right

    def _image_to_bytes(self, img: Image.Image, fmt: str = "PNG") -> bytes:
        """将 PIL Image 转换为 bytes"""
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def _apply_opacity(self, page, rect: 'fitz.Fitz.rect', opacity: float):
        """在指定区域应用半透明效果"""
        # 创建半透明覆盖层
        alpha = int(255 * opacity)
        overlay_img = Image.new('RGBA', (int(rect.width), int(rect.height)), (255, 0, 0, alpha))
        overlay_bytes = self._image_to_bytes(overlay_img)

        # 重新插入带透明度的图像
        page.insert_image(rect, stream=overlay_bytes, overlay=True)

    def preview_stamp_position(
        self,
        pdf_path: str,
        page_num: int = 0,
        config: PageStampConfig = None
    ) -> Image.Image:
        """
        预览印章在 PDF 页面上的位置

        Returns:
            预览图像（PIL Image）
        """
        if not HAS_FITZ:
            raise RuntimeError("需要安装 PyMuPDF: pip install pymupdf")

        if config is None:
            config = PageStampConfig(
                stamp_img=self.stamp_img or Image.new('RGBA', (100, 100), (255, 0, 0, 128)),
                position="right"
            )

        doc = fitz.open(pdf_path)
        page = doc[page_num]

        # 渲染页面为图像
        mat = fitz.Matrix(1, 1)  # 1:1 渲染
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        doc.close()

        # 添加印章位置标记
        page_img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
        page_width, page_height = page_img.size

        # 计算印章位置
        pos = self._calculate_position(
            page_width, page_height,
            config.position,
            config.vertical_align,
            config.margin * 2,  # 预览时放大
            0, 1
        )

        # 缩放印章到合适大小
        stamp_copy = self.stamp_img.copy() if self.stamp_img else Image.new('RGBA', (100, 100), (255, 0, 0, 128))
        stamp_copy.thumbnail((int(pos.width), int(pos.height)), Image.LANCZOS)

        # 合成
        page_img.paste(stamp_copy, (int(pos.x), int(pos.y)), stamp_copy)

        return page_img.convert('RGB')

    @staticmethod
    def get_pdf_page_count(pdf_path: str) -> int:
        """获取 PDF 页数"""
        if not HAS_FITZ:
            raise RuntimeError("需要安装 PyMuPDF: pip install pymupdf")
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def render_page_to_image(pdf_path: str, page_num: int = 0, dpi: int = 150) -> Image.Image:
        """将 PDF 指定页面渲染为图像"""
        if not HAS_FITZ:
            raise RuntimeError("需要安装 PyMuPDF: pip install pymupdf")
        doc = fitz.open(pdf_path)
        page = doc[page_num]

        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        doc.close()
        return Image.open(io.BytesIO(img_bytes)).convert('RGB')


# 全局单例
_pdf_stamp_tool: Optional[PDFStampTool] = None


def get_pdf_stamp_tool() -> PDFStampTool:
    """获取 PDF 印章工具单例"""
    global _pdf_stamp_tool
    if _pdf_stamp_tool is None:
        _pdf_stamp_tool = PDFStampTool()
    return _pdf_stamp_tool