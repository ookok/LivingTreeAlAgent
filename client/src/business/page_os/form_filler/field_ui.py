# =================================================================
# 字段级悬浮建议卡 - Field Enhancement UI
# =================================================================
# 功能：
# 1. 非模态悬浮卡片，不打断用户操作
# 2. 字段聚焦时显示建议，失焦时隐藏
# 3. 支持粘贴、查看来源、反馈等操作
# =================================================================

import time
import uuid
from enum import Enum
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field

from .form_parser import FormField, FieldSemanticType
from .auto_fill_engine import FillSuggestion, FillPriority


class FieldState(Enum):
    """字段状态"""
    IDLE = "idle"
    FOCUSED = "focused"
    HAS_SUGGESTIONS = "has_suggestions"
    FILLED = "filled"
    ERROR = "error"


@dataclass
class SuggestionCard:
    """建议卡片"""
    card_id: str
    field_name: str

    # 建议列表
    suggestions: List[FillSuggestion] = field(default_factory=list)

    # 状态
    state: FieldState = FieldState.IDLE
    visible: bool = False

    # 位置
    position: Dict[str, int] = field(default_factory=dict)  # {x, y, width, height}

    # 回调
    on_select: Callable = None      # 选择建议时回调
    on_feedback: Callable = None     # 反馈时回调
    on_dismiss: Callable = None      # 关闭时回调

    def __post_init__(self):
        if not self.card_id:
            self.card_id = f"card_{uuid.uuid4().hex[:8]}"


class FieldEnhancementUI:
    """
    字段级悬浮建议卡 UI 管理器

    核心特性：
    - 非模态：不阻挡页面内容
    - 智能显示：字段聚焦时显示建议
    - 紧凑设计：卡片在字段右下角，不遮挡内容
    - 可交互：支持粘贴、查看来源、反馈
    """

    # CSS 样式（注入到网页）
    INJECT_CSS = """
    /* 字段增强建议卡容器 */
    .hermes-field-enhancement-container {
        position: fixed;
        z-index: 2147483647;
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
    }

    /* 建议卡片 */
    .hermes-suggestion-card {
        position: absolute;
        width: 280px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05);
        pointer-events: auto;
        opacity: 0;
        transform: translateY(8px);
        transition: opacity 0.2s ease, transform 0.2s ease;
        overflow: hidden;
    }

    .hermes-suggestion-card.visible {
        opacity: 1;
        transform: translateY(0);
    }

    .hermes-suggestion-card.hidden {
        display: none;
    }

    /* 卡片头部 */
    .hermes-card-header {
        background: linear-gradient(135deg, #1a5f2a 0%, #2e8b3d 100%);
        color: white;
        padding: 10px 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .hermes-card-title {
        font-weight: 600;
        font-size: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .hermes-card-close {
        background: none;
        border: none;
        color: rgba(255,255,255,0.8);
        cursor: pointer;
        font-size: 16px;
        padding: 0;
        line-height: 1;
    }

    .hermes-card-close:hover {
        color: white;
    }

    /* 字段标签 */
    .hermes-field-label {
        padding: 8px 14px;
        background: #f8f9fa;
        border-bottom: 1px solid #eee;
        font-size: 11px;
        color: #666;
    }

    .hermes-field-label strong {
        color: #333;
    }

    /* 建议列表 */
    .hermes-suggestions {
        max-height: 200px;
        overflow-y: auto;
    }

    .hermes-suggestion-item {
        padding: 10px 14px;
        border-bottom: 1px solid #f0f0f0;
        cursor: pointer;
        transition: background 0.15s;
    }

    .hermes-suggestion-item:last-child {
        border-bottom: none;
    }

    .hermes-suggestion-item:hover {
        background: #f0f8f4;
    }

    .hermes-suggestion-item.selected {
        background: #e8f5e9;
    }

    /* 建议值 */
    .hermes-suggestion-value {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }

    .hermes-suggestion-value .badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        background: #e8f5e9;
        color: #1a5f2a;
    }

    .hermes-suggestion-value .value {
        flex: 1;
        color: #333;
        word-break: break-all;
    }

    .hermes-suggestion-value .masked {
        color: #999;
        font-size: 12px;
    }

    /* 来源信息 */
    .hermes-suggestion-source {
        font-size: 10px;
        color: #999;
        margin-bottom: 6px;
    }

    /* 操作按钮 */
    .hermes-suggestion-actions {
        display: flex;
        gap: 6px;
        margin-top: 6px;
    }

    .hermes-action-btn {
        padding: 4px 10px;
        border: none;
        border-radius: 4px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.15s;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .hermes-action-btn.primary {
        background: #1a5f2a;
        color: white;
    }

    .hermes-action-btn.primary:hover {
        background: #2e8b3d;
    }

    .hermes-action-btn.secondary {
        background: #f0f0f0;
        color: #666;
    }

    .hermes-action-btn.secondary:hover {
        background: #e0e0e0;
    }

    /* 反馈按钮 */
    .hermes-feedback-btns {
        display: flex;
        gap: 8px;
        margin-top: 4px;
    }

    .hermes-feedback-btn {
        background: none;
        border: none;
        color: #999;
        cursor: pointer;
        font-size: 11px;
        padding: 2px 4px;
    }

    .hermes-feedback-btn:hover {
        color: #666;
    }

    .hermes-feedback-btn.positive:hover {
        color: #43a047;
    }

    .hermes-feedback-btn.negative:hover {
        color: #e53935;
    }

    /* 已填充状态 */
    .hermes-filled-card .hermes-card-header {
        background: linear-gradient(135deg, #43a047 0%, #66bb6a 100%);
    }

    .hermes-filled-content {
        padding: 14px;
        text-align: center;
    }

    .hermes-filled-icon {
        font-size: 24px;
        margin-bottom: 6px;
    }

    .hermes-filled-text {
        color: #43a047;
        font-weight: 500;
    }

    .hermes-filled-next {
        color: #666;
        font-size: 11px;
        margin-top: 4px;
    }

    /* 下一个建议 */
    .hermes-next-suggestion {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        background: #fffbeb;
        border-top: 1px solid #ffeaa7;
        cursor: pointer;
        font-size: 11px;
        color: #666;
    }

    .hermes-next-suggestion:hover {
        background: #fff3cd;
    }

    /* 进度指示 */
    .hermes-progress-bar {
        height: 3px;
        background: #e0e0e0;
        border-radius: 0 0 10px 10px;
        overflow: hidden;
    }

    .hermes-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #1a5f2a, #2e8b3d);
        transition: width 0.3s ease;
    }

    /* 滚动条样式 */
    .hermes-suggestions::-webkit-scrollbar {
        width: 6px;
    }

    .hermes-suggestions::-webkit-scrollbar-track {
        background: #f0f0f0;
    }

    .hermes-suggestions::-webkit-scrollbar-thumb {
        background: #ccc;
        border-radius: 3px;
    }

    .hermes-suggestions::-webkit-scrollbar-thumb:hover {
        background: #aaa;
    }
    """

    # JavaScript 代码（注入到网页）
    INJECT_JS = """
    (function() {
        // 避免重复注入
        if (window.__hermesFormEnhancement__) return;
        window.__hermesFormEnhancement__ = true;

        // 注入样式
        var style = document.createElement('style');
        style.textContent = __HERMES_CSS__;
        document.head.appendChild(style);

        // 状态管理
        var activeField = null;
        var cards = {};

        // 监听焦点事件
        document.addEventListener('focusin', handleFocus, true);
        document.addEventListener('focusout', handleBlur, true);

        function handleFocus(e) {
            var field = e.target;
            if (!isFormField(field)) return;

            activeField = field;
            showCardForField(field);
        }

        function handleBlur(e) {
            var field = e.target;
            if (!isFormField(field)) return;

            // 延迟隐藏，等待点击事件
            setTimeout(function() {
                if (activeField === field && !isCardHovered()) {
                    hideCard(getCardId(field));
                }
            }, 200);
        }

        function isFormField(elem) {
            var tag = elem.tagName.toLowerCase();
            return tag === 'input' || tag === 'select' || tag === 'textarea';
        }

        function getCardId(field) {
            return 'hermes-card-' + (field.id || field.name || 'unknown');
        }

        function showCardForField(field) {
            var cardId = getCardId(field);
            var card = cards[cardId];

            if (!card) {
                card = createCard(field);
                cards[cardId] = card;
                document.body.appendChild(card);
            }

            positionCard(card, field);
            showCard(card);

            // 通知扩展
            window.postMessage({
                type: 'hermes:field:focused',
                fieldName: field.name,
                fieldId: field.id,
                fieldLabel: getFieldLabel(field)
            }, '*');
        }

        function createCard(field) {
            var card = document.createElement('div');
            card.className = 'hermes-suggestion-card';
            card.id = getCardId(field);
            card.innerHTML = __HERMES_CARD_HTML__;
            return card;
        }

        function positionCard(card, field) {
            var rect = field.getBoundingClientRect();
            var cardHeight = 280;
            var cardWidth = 280;

            // 放置在字段右下角
            var left = rect.right + 10;
            var top = rect.top;

            // 边界检测
            if (left + cardWidth > window.innerWidth) {
                left = rect.left - cardWidth - 10;
            }
            if (top + cardHeight > window.innerHeight) {
                top = window.innerHeight - cardHeight - 10;
            }

            card.style.left = Math.max(10, left) + 'px';
            card.style.top = Math.max(10, top) + 'px';
        }

        function showCard(card) {
            card.classList.add('visible');
            card.classList.remove('hidden');
        }

        function hideCard(cardId) {
            var card = cards[cardId];
            if (card) {
                card.classList.remove('visible');
                setTimeout(function() {
                    if (!card.classList.contains('visible')) {
                        card.classList.add('hidden');
                    }
                }, 200);
            }
        }

        function isCardHovered() {
            for (var id in cards) {
                if (cards[id].matches(':hover')) return true;
            }
            return false;
        }

        function getFieldLabel(field) {
            // 尝试查找 label
            var label = document.querySelector('label[for="' + field.id + '"]');
            if (label) return label.textContent.trim();

            // 查找父级 label
            var parent = field.closest('label');
            if (parent) return parent.textContent.replace(field.value || '', '').trim();

            return field.name || field.id || '未知字段';
        }

        // 暴露 API
        window.__hermesFormEnhancement__ = {
            updateSuggestions: function(fieldName, suggestions) {
                // 找到对应的卡片并更新建议
                for (var id in cards) {
                    var card = cards[id];
                    // 更新建议内容
                    updateCardContent(card, suggestions);
                }
            },
            setFilled: function(fieldName, value) {
                // 标记字段已填充
                for (var id in cards) {
                    var card = cards[id];
                    markCardAsFilled(card, value);
                }
            },
            showNextSuggestion: function(fieldName) {
                // 显示下一个待填充字段的建议
            },
            getFieldLabel: getFieldLabel
        };

        function updateCardContent(card, suggestions) {
            // 更新建议列表
        }

        function markCardAsFilled(card, value) {
            card.classList.add('hermes-filled-card');
        }
    })();
    """

    def __init__(self, page_id: str = None):
        self.page_id = page_id or str(uuid.uuid4())[:12]
        self._cards: Dict[str, SuggestionCard] = {}
        self._active_field: Optional[str] = None
        self._enabled = True
        self._rendered = False

        # 回调
        self._on_field_focused: Callable = None
        self._on_suggestion_selected: Callable = None
        self._on_feedback: Callable = None

    def enable(self):
        """启用增强 UI"""
        self._enabled = True
        self._inject_to_page()

    def disable(self):
        """禁用增强 UI"""
        self._enabled = False
        self._remove_from_page()

    def _inject_to_page(self):
        """注入 CSS 和初始化 JS"""
        if self._rendered:
            return

        # 这里会通过 QWebChannel 注入到网页
        # 实际实现需要与 WebPage 通信
        pass

    def _remove_from_page(self):
        """从页面移除"""
        self._rendered = False

    # ========== 卡片管理 ==========

    def create_card(self, field: FormField) -> SuggestionCard:
        """为字段创建建议卡片"""
        card_id = f"card_{field.name}_{uuid.uuid4().hex[:6]}"
        card = SuggestionCard(
            card_id=card_id,
            field_name=field.name,
            on_select=self._handle_select,
            on_feedback=self._handle_feedback,
            on_dismiss=self._handle_dismiss
        )
        self._cards[card_id] = card
        return card

    def update_card_suggestions(
        self,
        card_id: str,
        suggestions: List[FillSuggestion]
    ):
        """更新卡片建议"""
        if card_id in self._cards:
            self._cards[card_id].suggestions = suggestions

    def show_card(self, card_id: str, position: Dict[str, int]):
        """显示卡片"""
        if card_id in self._cards:
            card = self._cards[card_id]
            card.visible = True
            card.position = position
            card.state = FieldState.HAS_SUGGESTIONS

    def hide_card(self, card_id: str):
        """隐藏卡片"""
        if card_id in self._cards:
            self._cards[card_id].visible = False
            self._cards[card_id].state = FieldState.IDLE

    def mark_field_filled(
        self,
        card_id: str,
        value: str,
        next_field_label: str = ""
    ):
        """标记字段已填充"""
        if card_id in self._cards:
            card = self._cards[card_id]
            card.state = FieldState.FILLED
            card.metadata["filled_value"] = value
            card.metadata["next_field"] = next_field_label

    # ========== 事件处理 ==========

    def _handle_select(
        self,
        card_id: str,
        suggestion: FillSuggestion
    ):
        """处理选择建议"""
        if self._on_suggestion_selected:
            self._on_suggestion_selected(card_id, suggestion)

    def _handle_feedback(
        self,
        card_id: str,
        suggestion: FillSuggestion,
        is_positive: bool
    ):
        """处理反馈"""
        if self._on_feedback:
            self._on_feedback(card_id, suggestion, is_positive)

    def _handle_dismiss(self, card_id: str):
        """处理关闭"""
        self.hide_card(card_id)

    # ========== 生成注入代码 ==========

    def generate_inject_code(self) -> tuple[str, str]:
        """生成要注入到网页的 CSS 和 JS"""
        return self.INJECT_CSS, self.INJECT_JS

    def generate_card_html(
        self,
        field: FormField,
        suggestions: List[FillSuggestion]
    ) -> str:
        """生成卡片 HTML"""
        if not suggestions:
            return self._generate_empty_card(field)

        suggestions_html = ""
        for i, sug in enumerate(suggestions[:3]):
            priority_badge = self._get_priority_badge(sug.priority)
            source_icon = self._get_source_icon(sug.source)

            masked_value = self._mask_value(sug.value, sug.source)

            suggestions_html += f"""
            <div class="hermes-suggestion-item" data-index="{i}">
                <div class="hermes-suggestion-value">
                    {priority_badge}
                    <span class="value {'masked' if masked_value != sug.value else ''}">{masked_value}</span>
                </div>
                <div class="hermes-suggestion-source">
                    {source_icon} {sug.source_detail}
                </div>
                <div class="hermes-suggestion-actions">
                    <button class="hermes-action-btn primary" onclick="__hermesFill({i})">
                        📋 粘贴
                    </button>
                    <button class="hermes-action-btn secondary" onclick="__hermesViewSource({i})">
                        📁 来源
                    </button>
                </div>
                <div class="hermes-feedback-btns">
                    <button class="hermes-feedback-btn positive" onclick="__hermesFeedback({i}, true)">✓ 正确</button>
                    <button class="hermes-feedback-btn negative" onclick="__hermesFeedback({i}, false)">✗ 不准</button>
                </div>
            </div>
            """

        return f"""
        <div class="hermes-card-header">
            <span class="hermes-card-title">
                <span>🌿</span>
                <span>智能建议</span>
            </span>
            <button class="hermes-card-close" onclick="__hermesClose()">×</button>
        </div>
        <div class="hermes-field-label">
            字段：<strong>{field.label or field.name}</strong>
        </div>
        <div class="hermes-suggestions">
            {suggestions_html}
        </div>
        <div class="hermes-progress-bar">
            <div class="hermes-progress-fill" style="width: 0%"></div>
        </div>
        """

    def _generate_empty_card(self, field: FormField) -> str:
        """生成空状态卡片"""
        return f"""
        <div class="hermes-card-header">
            <span class="hermes-card-title">
                <span>🌿</span>
                <span>智能填表助手</span>
            </span>
            <button class="hermes-card-close" onclick="__hermesClose()">×</button>
        </div>
        <div class="hermes-field-label">
            字段：<strong>{field.label or field.name}</strong>
        </div>
        <div style="padding: 20px; text-align: center; color: #999;">
            <div style="font-size: 24px; margin-bottom: 8px;">🔍</div>
            <div>暂无建议</div>
            <div style="font-size: 11px; margin-top: 4px;">
                {self._get_hint_for_type(field.semantic_type)}
            </div>
        </div>
        """

    def _generate_filled_card(
        self,
        field: FormField,
        value: str,
        next_field_label: str = ""
    ) -> str:
        """生成已填充状态卡片"""
        next_html = f"""
        <div class="hermes-next-suggestion" onclick="__hermesNextField()">
            <span>→</span>
            <span>下一个：{next_field_label}</span>
        </div>
        """ if next_field_label else ""

        return f"""
        <div class="hermes-card-header">
            <span class="hermes-card-title">
                <span>✓</span>
                <span>已填充</span>
            </span>
        </div>
        <div class="hermes-filled-content">
            <div class="hermes-filled-icon">✅</div>
            <div class="hermes-filled-text">已填充</div>
            <div class="hermes-filled-next" style="font-size: 11px; color: #666; margin-top: 4px;">
                {value[:30]}{'...' if len(value) > 30 else ''}
            </div>
        </div>
        {next_html}
        """

    def _get_priority_badge(self, priority: FillPriority) -> str:
        """获取优先级徽章"""
        badges = {
            FillPriority.HIGH: '<span class="badge" style="background: #c8e6c9; color: #1a5f2a;">推荐</span>',
            FillPriority.MEDIUM: '<span class="badge" style="background: #fff3e0; color: #e65100;">可选</span>',
            FillPriority.LOW: '',
        }
        return badges.get(priority, '')

    def _get_source_icon(self, source: FillSource) -> str:
        """获取来源图标"""
        icons = {
            FillSource.KNOWLEDGE_BASE: '📚',
            FillSource.HISTORY: '📝',
            FillSource.CONTEXT: '🔗',
            FillSource.BROWSER_AUTOFILL: '🌐',
            FillSource.TEMPLATE: '📋',
            FillSource.AI_GENERATED: '🤖',
            FillSource.CLIPBOARD: '📎',
        }
        return icons.get(source, '📄')

    def _mask_value(self, value: str, source: FillSource) -> str:
        """遮罩敏感值"""
        if source == FillSource.KNOWLEDGE_BASE:
            return value  # 知识库来源不遮罩

        str_value = str(value)
        # 手机号遮罩
        if len(str_value) == 11 and str_value.isdigit():
            return f"{str_value[:3]}-****-{str_value[7:]}"
        # 身份证遮罩
        if len(str_value) == 18 and str_value[:-1].isdigit():
            return f"{str_value[:6]}********{str_value[-4:]}"
        # 邮箱遮罩
        if '@' in str_value:
            parts = str_value.split('@')
            return f"{parts[0][:2]}***@{parts[1]}"

        return str_value

    def _get_hint_for_type(self, sem_type: FieldSemanticType) -> str:
        """根据类型获取提示"""
        hints = {
            FieldSemanticType.COMPANY_NAME: "可从知识库导入企业信息",
            FieldSemanticType.EMAIL: "试试常用的工作邮箱",
            FieldSemanticType.PHONE_MOBILE: "检查手机号是否正确",
            FieldSemanticType.DESCRIPTION: "让 AI 为你生成描述",
            FieldSemanticType.CAPTCHA: "请手动输入验证码",
            FieldSemanticType.FILE_UPLOAD: "可上传相关证件或文件",
        }
        return hints.get(sem_type, "尝试从历史记录或上下文获取")

    # ========== 回调设置 ==========

    def set_on_field_focused(self, callback: Callable):
        """设置字段聚焦回调"""
        self._on_field_focused = callback

    def set_on_suggestion_selected(self, callback: Callable):
        """设置建议选择回调"""
        self._on_suggestion_selected = callback

    def set_on_feedback(self, callback: Callable):
        """设置反馈回调"""
        self._on_feedback = callback

    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "page_id": self.page_id,
            "enabled": self._enabled,
            "active_field": self._active_field,
            "card_count": len(self._cards),
            "rendered": self._rendered,
        }
