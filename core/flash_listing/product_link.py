# core/flash_listing/product_link.py
# 商品伪域名标签生成器
#
# 基于伪域名引擎生成商品短链：
# - product.{node_id}.tree/{short_code}
# - 生成可点击的展示文案
# - 生成 QR 码数据

import hashlib
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ProductLinkGenerator:
    """
    商品伪域名标签生成器

    利用伪域名引擎生成商品访问链接：
    - 短码格式：item_{hash}
    - 完整链接：product.{node_id}.tree/item_{hash}
    - 显示文案：[🛒 查看商品：{title}]
    """

    # 伪域名后缀
    TREE_SUFFIX = ".tree"

    def __init__(self, node_id: str, config: Optional[Dict] = None):
        """
        Args:
            node_id: 当前节点ID
            config: 配置字典
        """
        self.node_id = node_id
        self.config = config or {}

        # 链接前缀
        self.link_prefix = self.config.get("link_prefix", "product")

        # 短码长度
        self.short_code_length = self.config.get("short_code_length", 12)

    def generate_link(
        self,
        listing_id: str,
        title: str = "",
    ) -> "ProductLink":
        """
        生成商品链接

        Args:
            listing_id: 商品ID
            title: 商品标题（用于显示）

        Returns:
            ProductLink 对象
        """
        # 生成短码
        short_code = self._generate_short_code(listing_id)

        # 构建完整链接
        full_link = f"{self.link_prefix}.{self.node_id}{self.TREE_SUFFIX}/{short_code}"

        # 生成QR码数据
        qr_data = self._generate_qr_data(full_link)

        # 创建链接对象
        link = ProductLink(
            full_link=full_link,
            short_code=short_code,
            qr_code_data=qr_data,
            node_id=self.node_id,
            listing_id=listing_id,
        )

        logger.info(f"[ProductLinkGenerator] 生成商品链接: {full_link}")
        return link

    def generate_clickable_text(
        self,
        link: "ProductLink",
        title: str = "",
        max_title_len: int = 15,
    ) -> str:
        """
        生成可点击的展示文本

        Args:
            link: ProductLink 对象
            title: 商品标题
            max_title_len: 标题最大长度

        Returns:
            可点击的Markdown文本
        """
        # 截断标题
        display_title = title[:max_title_len] + "..." if len(title) > max_title_len else title

        if display_title:
            return f"[🛒 查看商品：{display_title}]({link.full_link})"
        else:
            return f"[🛒 查看商品]({link.full_link})"

    def generate_markdown_card(
        self,
        link: "ProductLink",
        title: str = "",
        price: Optional[float] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """
        生成 Markdown 商品卡片

        Args:
            link: ProductLink 对象
            title: 商品标题
            price: 价格
            image_url: 图片URL

        Returns:
            Markdown 格式的商品卡片
        """
        # 构建卡片
        card_lines = []

        # 标题
        if title:
            card_lines.append(f"### {title}")
        else:
            card_lines.append("### 🛒 商品")

        # 图片（如果有）
        if image_url:
            card_lines.append(f"![商品图片]({image_url})")

        # 价格
        if price:
            card_lines.append(f"**💰 价格：** ¥{price:.2f}")

        # 链接
        card_lines.append(f"[👉 点击查看/购买]({link.full_link})")

        # 提示
        card_lines.append(f"\n_商品来自节点 {self.node_id[:8]}..._")

        return "\n".join(card_lines)

    def parse_link(self, link_text: str) -> Optional[Dict[str, str]]:
        """
        解析商品链接

        Args:
            link_text: 链接文本

        Returns:
            解析结果：{node_id, short_code} 或 None
        """
        try:
            # 尝试解析格式: product.{node_id}.tree/{short_code}
            if "/item_" not in link_text:
                return None

            parts = link_text.split("/")
            if len(parts) < 2:
                return None

            domain_part = parts[0]
            short_code = parts[1]

            # 提取 node_id
            # product.{node_id}.tree
            node_id = domain_part.replace("product.", "").replace(".tree", "")

            return {
                "node_id": node_id,
                "short_code": short_code,
                "listing_id": self._recover_listing_id(short_code),
            }

        except Exception as e:
            logger.warning(f"[ProductLinkGenerator] 链接解析失败: {e}")
            return None

    def _generate_short_code(self, listing_id: str) -> str:
        """
        生成短码

        规则：
        - 以 item_ 开头
        - 后面跟 listing_id 的哈希前 N 位
        """
        # 哈希
        hash_input = f"{listing_id}:{self.node_id}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()

        return f"item_{hash_val[:self.short_code_length]}"

    def _recover_listing_id(self, short_code: str) -> Optional[str]:
        """
        从短码恢复 listing_id（需要遍历/索引）

        注意：这个是单向的，实际上需要维护 short_code -> listing_id 的映射
        """
        # 简化实现：存储映射表
        # 实际使用时应该从数据库查询
        return None

    def _generate_qr_data(self, link: str) -> str:
        """
        生成 QR 码数据

        返回可被 QR 码库使用的数据
        """
        # 返回链接本身，QR码由UI层生成
        return link


# ========== 数据类 ==========

@dataclass
class ProductLink:
    """商品伪域名标签"""

    full_link: str = ""                                        # 完整链接
    short_code: str = ""                                       # 短码
    qr_code_data: Optional[str] = None                          # QR码数据
    node_id: str = ""                                          # 节点ID
    listing_id: str = ""                                       # 商品ID
    click_count: int = 0                                      # 点击次数
    view_count: int = 0                                       # 查看次数
    is_active: bool = True                                    # 是否激活
    is_blacklisted: bool = False                              # 是否被封禁

    @property
    def display_text(self) -> str:
        """显示文案"""
        return f"[🛒 查看商品：{self.short_code}]"

    @property
    def clickable_link(self) -> str:
        """可点击链接（用于消息）"""
        return f"[🛒 查看商品]({self.full_link})"


# ========== 便捷函数 ==========

def create_product_link(
    node_id: str,
    listing_id: str,
    title: str = "",
) -> ProductLink:
    """快捷函数：创建商品链接"""
    generator = ProductLinkGenerator(node_id)
    return generator.generate_link(listing_id, title)


def create_clickable_text(
    node_id: str,
    listing_id: str,
    title: str = "",
) -> str:
    """快捷函数：创建可点击文本"""
    generator = ProductLinkGenerator(node_id)
    link = generator.generate_link(listing_id, title)
    return generator.generate_clickable_text(link, title)


def create_markdown_card(
    node_id: str,
    listing_id: str,
    title: str = "",
    price: Optional[float] = None,
    image_url: Optional[str] = None,
) -> str:
    """快捷函数：创建 Markdown 商品卡片"""
    generator = ProductLinkGenerator(node_id)
    link = generator.generate_link(listing_id, title)
    return generator.generate_markdown_card(link, title, price, image_url)
