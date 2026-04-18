# =================================================================
# 格式自动校正 - Format Normalizer
# =================================================================
# 功能：
# 1. 日期格式标准化
# 2. 电话号码格式化
# 3. 金额/价格格式化
# 4. 地址拆分
# 5. 证件号验证
# =================================================================

import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from datetime import datetime


class FormatType(Enum):
    """格式类型"""
    DATE = "date"
    PHONE = "phone"
    MOBILE = "mobile"
    EMAIL = "email"
    ID_CARD = "id_card"
    PASSPORT = "passport"
    AMOUNT = "amount"
    PRICE = "price"
    PERCENTAGE = "percentage"
    ADDRESS = "address"
    BANK_ACCOUNT = "bank_account"
    POSTAL_CODE = "postal_code"
    URL = "url"
    UNKNOWN = "unknown"


@dataclass
class FormatRule:
    """格式规则"""
    format_type: FormatType
    input_pattern: str               # 输入模式（正则）
    output_template: str             # 输出模板
    normalize_fn: str = ""           # 标准化函数名


@dataclass
class FormatResult:
    """格式化结果"""
    success: bool
    original: str
    formatted: str
    format_type: FormatType
    confidence: float               # 置信度 0-1
    warnings: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)


class FormatNormalizer:
    """
    格式自动校正器

    功能：
    1. 自动识别输入格式类型
    2. 标准化输出格式
    3. 验证合法性
    4. 提供修正建议
    """

    # 手机号格式模板
    PHONE_PATTERNS = [
        (r"^(\d{3})(\d{4})(\d{4})$", r"\1-\2-\3"),           # 13812345678 -> 138-1234-5678
        (r"^(\d{11})$", r"\1"),                               # 已是11位数字
        (r"^(\+86)(\d{11})$", r"\1 \2"),                     # +8613812345678
        (r"^\+86\s*(\d{11})$", r"\1"),                       # +86 13812345678
    ]

    # 日期格式模板
    DATE_PATTERNS = [
        # 输入模式 -> (正则, 替换模板, 输出格式)
        (r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", r"\1-\2-\3", "YYYY-MM-DD"),
        (r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$", r"\1-\2-\3", "YYYY-MM-DD"),
        (r"^(\d{4})/(\d{1,2})/(\d{1,2})$", r"\1-\2-\3", "YYYY-MM-DD"),
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", r"\1-\2-\3", "YYYY-MM-DD"),  # 已是标准格式
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", r"\3-\1-\2", "YYYY-MM-DD"),  # MM/DD/YYYY
        (r"^(\d{1,2})-(\d{1,2})-(\d{4})$", r"\3-\1-\2", "YYYY-MM-DD"),  # DD-MM-YYYY
    ]

    # 金额格式
    AMOUNT_PATTERNS = [
        (r"^[¥￥]$", ""),                     # 移除货币符号
        (r",", ""),                            # 移除千分位逗号
        (r"元$", ""),                          # 移除"元"
        (r"美元$", ""),                        # 移除"美元"
    ]

    def __init__(self):
        self._custom_rules: Dict[str, FormatRule] = {}

    def normalize(
        self,
        value: str,
        target_type: FormatType = None,
        strict: bool = False
    ) -> FormatResult:
        """
        标准化值

        Args:
            value: 输入值
            target_type: 目标格式类型（如果为 None，自动检测）
            strict: 是否严格模式（严格模式下低置信度返回原值）

        Returns:
            FormatResult: 格式化结果
        """
        original = value
        warnings = []
        corrections = []

        # 空值处理
        if not value or not value.strip():
            return FormatResult(
                success=False,
                original=original,
                formatted=original,
                format_type=FormatType.UNKNOWN,
                confidence=0.0
            )

        value = value.strip()

        # 自动检测类型
        if target_type is None:
            target_type, confidence = self._detect_type(value)
        else:
            confidence = 0.9

        # 严格模式下低置信度不处理
        if strict and confidence < 0.5:
            return FormatResult(
                success=False,
                original=original,
                formatted=value,
                format_type=target_type,
                confidence=confidence,
                warnings=["置信度过低，保持原值"]
            )

        # 根据类型标准化
        formatted = value
        if target_type == FormatType.PHONE or target_type == FormatType.MOBILE:
            formatted, warns, corrects = self._normalize_phone(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        elif target_type == FormatType.DATE:
            formatted, warns, corrects = self._normalize_date(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        elif target_type == FormatType.AMOUNT or target_type == FormatType.PRICE:
            formatted, warns, corrects = self._normalize_amount(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        elif target_type == FormatType.EMAIL:
            formatted, warns, corrects = self._normalize_email(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        elif target_type == FormatType.ID_CARD:
            formatted, warns, corrects = self._normalize_id_card(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        elif target_type == FormatType.POSTAL_CODE:
            formatted, warns, corrects = self._normalize_postal_code(value)
            warnings.extend(warns)
            corrections.extend(corrects)

        return FormatResult(
            success=True,
            original=original,
            formatted=formatted,
            format_type=target_type,
            confidence=1.0 if corrections else confidence,
            warnings=warnings,
            corrections=corrections
        )

    def _detect_type(self, value: str) -> Tuple[FormatType, float]:
        """检测值类型"""
        # 手机号
        if re.match(r"^1[3-9]\d{9}$", value.replace("-", "")):
            return FormatType.MOBILE, 0.95

        # 固定电话
        if re.match(r"^0\d{2,3}-?\d{7,8}$", value):
            return FormatType.PHONE, 0.9

        # 日期
        for pattern, _, _ in self.DATE_PATTERNS:
            if re.search(pattern, value):
                return FormatType.DATE, 0.9

        # 金额
        if re.search(r"[¥￥$]|[0-9]+\.[0-9]{2}", value):
            return FormatType.AMOUNT, 0.8

        # 邮箱
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
            return FormatType.EMAIL, 0.95

        # 身份证
        if re.match(r"^\d{17}[\dXx]$", value):
            return FormatType.ID_CARD, 0.95

        # 邮政编码
        if re.match(r"^\d{6}$", value):
            return FormatType.POSTAL_CODE, 0.95

        return FormatType.UNKNOWN, 0.3

    def _normalize_phone(self, value: str) -> Tuple[str, list, list]:
        """标准化电话号码"""
        formatted = value
        warnings = []
        corrections = []

        # 移除非数字字符
        digits = re.sub(r"\D", "", value)

        # 补齐 86
        if len(digits) == 11 and digits.startswith("1"):
            # 11位手机号
            formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            if len(value) != 13:  # 不是标准格式
                corrections.append(f"格式化手机号: {value} -> {formatted}")

        elif len(digits) == 12 and digits.startswith("86"):
            # 86开头的12位数字
            digits = digits[2:]
            formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            corrections.append(f"标准化手机号: {value} -> {formatted}")

        elif len(digits) == 10:
            # 固定电话（带区号）
            if value.startswith("0"):
                formatted = f"{digits[:3]}-{digits[3:]}"
                corrections.append(f"格式化固定电话: {value} -> {formatted}")

        elif len(digits) == 7 or len(digits) == 8:
            # 纯号码
            formatted = digits
            warnings.append("请确认区号是否正确")

        return formatted, warnings, corrections

    def _normalize_date(self, value: str) -> Tuple[str, list, list]:
        """标准化日期"""
        formatted = value
        warnings = []
        corrections = []

        for pattern, template, _ in self.DATE_PATTERNS:
            match = re.search(pattern, value)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups

                    # 确保月份和日期是两位数
                    if len(month) == 1:
                        month = "0" + month
                    if len(day) == 1:
                        day = "0" + day

                    # 处理两位数年份
                    if len(year) == 2:
                        year = "20" + year

                    formatted = f"{year}-{month}-{day}"

                    # 验证日期合法性
                    try:
                        datetime.strptime(formatted, "%Y-%m-%d")
                    except ValueError:
                        warnings.append(f"日期可能无效: {formatted}")
                        continue

                    if formatted != value:
                        corrections.append(f"标准化日期: {value} -> {formatted}")

                break

        return formatted, warnings, corrections

    def _normalize_amount(self, value: str) -> Tuple[str, list, list]:
        """标准化金额"""
        formatted = value
        warnings = []
        corrections = []

        # 移除货币符号和千分位
        for pattern in self.AMOUNT_PATTERNS:
            formatted = re.sub(pattern[0], pattern[1], formatted)

        formatted = formatted.strip()

        # 尝试转换为浮点数再格式化
        try:
            amount = float(formatted)
            # 确保两位小数
            formatted = f"{amount:.2f}"
            if formatted != value.strip():
                corrections.append(f"标准化金额: {value} -> {formatted}")
        except ValueError:
            warnings.append(f"无法解析金额: {value}")

        return formatted, warnings, corrections

    def _normalize_email(self, value: str) -> Tuple[str, list, list]:
        """标准化邮箱"""
        formatted = value.strip().lower()
        warnings = []
        corrections = []

        if formatted != value:
            corrections.append(f"邮箱小写化: {value} -> {formatted}")

        return formatted, warnings, corrections

    def _normalize_id_card(self, value: str) -> Tuple[str, list, list]:
        """标准化身份证"""
        formatted = value.strip().upper()
        warnings = []
        corrections = []

        # 验证校验位
        if len(formatted) == 18:
            if not self._validate_id_card_checksum(formatted):
                warnings.append("身份证校验位验证失败，可能有误")

        return formatted, warnings, corrections

    def _normalize_postal_code(self, value: str) -> Tuple[str, list, list]:
        """标准化邮政编码"""
        formatted = value.strip()
        warnings = []

        if len(formatted) != 6:
            warnings.append("邮政编码应为6位")

        return formatted, warnings, []

    def _validate_id_card_checksum(self, id_card: str) -> bool:
        """验证身份证校验位"""
        if len(id_card) != 18:
            return False

        # 权重因子
        factors = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        # 校验码映射
        checksum_map = '10X98765432'

        total = 0
        for i in range(17):
            try:
                total += int(id_card[i]) * factors[i]
            except ValueError:
                return False

        expected = checksum_map[total % 11]
        return id_card[17].upper() == expected

    # ========== 高级格式化 ==========

    def split_address(self, address: str) -> Dict[str, str]:
        """
        拆分地址

        Returns:
            {province, city, district, street, detail}
        """
        result = {
            "province": "",
            "city": "",
            "district": "",
            "street": "",
            "detail": address
        }

        # 省市区识别
        provinces = ["北京", "天津", "上海", "重庆"]
        autonomous_regions = ["内蒙古", "广西", "西藏", "宁夏", "新疆"]
        province_short = ["河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽",
                         "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
                         "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾"]

        address = address.strip()

        # 简化实现：按关键字拆分
        for prov in provinces + autonomous_regions + province_short:
            if address.startswith(prov):
                result["province"] = prov
                remaining = address[len(prov):]
                # 尝试拆分市
                if len(remaining) > 2:
                    result["detail"] = remaining
                break

        return result

    def split_id_card(self, id_card: str) -> Dict[str, str]:
        """
        拆分身份证号

        Returns:
            {birthplace, birthdate, gender}
        """
        if len(id_card) != 18:
            return {}

        result = {}

        # 出生地（前6位）
        result["birthplace_code"] = id_card[:6]

        # 出生日期（7-14位）
        birthdate = id_card[6:14]
        try:
            dt = datetime.strptime(birthdate, "%Y%m%d")
            result["birthdate"] = dt.strftime("%Y-%m-%d")
            result["birth_year"] = dt.year
            result["birth_month"] = dt.month
            result["birth_day"] = dt.day
        except ValueError:
            pass

        # 性别（17位，奇数男，偶数女）
        gender_digit = int(id_card[16])
        result["gender"] = "男" if gender_digit % 2 == 1 else "女"

        return result

    def format_currency(
        self,
        amount: float,
        currency: str = "CNY",
        show_symbol: bool = True
    ) -> str:
        """
        格式化货币

        Args:
            amount: 金额
            currency: 货币类型 (CNY, USD, EUR)
            show_symbol: 是否显示符号

        Returns:
            格式化后的字符串
        """
        symbols = {
            "CNY": "¥",
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥"
        }

        symbol = symbols.get(currency, "") if show_symbol else ""

        if currency == "JPY":
            return f"{symbol}{int(amount):,}"
        else:
            return f"{symbol}{amount:,.2f}"

    def register_rule(self, rule: FormatRule):
        """注册自定义规则"""
        key = f"{rule.format_type.value}:{rule.input_pattern}"
        self._custom_rules[key] = rule

    def get_supported_types(self) -> List[str]:
        """获取支持的格式类型"""
        return [ft.value for ft in FormatType]
