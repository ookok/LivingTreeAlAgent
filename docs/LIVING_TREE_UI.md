# 🌿 生命之树 · 无弹窗 UI 设计规范

## 概述

Hermes Desktop V2.0 采用**无弹窗 Web 式范式**设计 UI，摒弃传统的 `QMessageBox`/`QDialog` 弹窗，转而采用固定面板 + 状态条 + 上下文卡片的组合，提供更连贯的视觉体验和更稳定的自动化测试支持。

## 核心理念

| 传统弹窗 | 无弹窗面板 |
|---------|-----------|
| 临时生成，ID 随机 | 固定 ObjectName (canopy-alert) |
| 需轮询弹窗出现（不稳定） | 监听面板 visible 状态 |
| 弹窗抢夺焦点，打断操作链 | 主界面始终可交互 |
| 弹窗遮罩使底层元素不可见 | 面板与内容同帧，全貌可截 |

## 四大核心组件

### 1. 🌲 林冠警报带 (Canopy Alert Band)

**位置**：主界面顶部（状态栏下方），横贯全宽，高度固定 60px

**场景**：升级警告、网络断开、高风险操作预警

**使用方式**：
```python
# 显示警告
self.show_alert(
    message="新版本已就绪，建议重启以应用更新。",
    level="info",  # info/warning/error/success
    actions=[("查看更新", lambda: ...), ("忽略", None)]
)

# 自动隐藏
self.show_alert("保存成功", level="success", auto_hide_ms=3000)
```

**ObjectName**: `canopy-alert-band`

---

### 2. 🌱 根系询问台 (Root Inquiry Deck)

**位置**：右侧边栏（固定宽度 320px），平时收起，需要时滑出

**场景**：装配冲突裁决、补丁应用确认、交易风险提示

**使用方式**：
```python
# 显示冲突确认
self.ask_conflict_resolve(
    tool_new="PDFExtractor",
    tool_old="DocParser",
    options=[
        ("parallel", "分叉共生（并行共存）", None),
        ("replace", "修剪旧枝（替换旧版）", None),
        ("cancel", "取消", None)
    ],
    on_confirm=lambda choice: ...
)

# 删除确认
self.ask_delete("文档.docx", on_confirm=lambda: ...)

# 风险确认
self.ask_risk("确定要执行此操作吗？", risk_level="high", on_confirm=...)
```

**ObjectName**: `root-inquiry-deck`

---

### 3. 🌾 沃土状态栏 (Soil Status Rail)

**位置**：界面底部（固定高度 48px）

**场景**：下载进度、装配步骤、网络同步中

**使用方式**：
```python
# 显示进度
self.show_progress("正在嫁接「OpenDataLoader」...", 35)

# 更新进度
self.update_progress(50, "正在下载模型文件...")

# 成功状态
self.show_success_status("嫁接完成！")

# 错误状态
self.show_error_status("连接失败，请检查网络")

# 信息状态
self.show_info_status("系统就绪")

# 清除
self.clear_status()
```

**ObjectName**: `soil-status-rail`

---

### 4. 💧 晨露提示卡 (Dewdrop Hint Card)

**位置**：附着在相关控件旁（如输入框下方、按钮右侧）

**场景**：表单校验、AI 建议、操作后果说明

**使用方式**：
```python
# 在控件下方显示提示
DewdropHintCard.show_below(
    target=input_field,
    message="输入格式：2024-01-01",
    level="info"  # info/warning/error/success
)

# 在控件右侧显示提示
DewdropHintCard.show_right_of(
    target=submit_btn,
    message="提交后将发送邮件通知",
    level="info"
)

# 自动3秒后消失
DewdropHintCard.show_below(target, "保存成功").auto_hide(3000)
```

**ObjectName**: `dewdrop-hint`

---

## 统一管理器

使用 `LivingTreeUI` 统一管理所有组件：

```python
# 初始化
self._ltui = LivingTreeUI(self)

# 显示各类提醒
self._ltui.alert.show_alert(...)    # 林冠警报带
self._ltui.inquiry.ask(...)         # 根系询问台
self._ltui.status.show_progress(...)# 沃土状态栏

# 便捷方法
self._ltui.show_success("操作成功")
self._ltui.show_warning("请注意")
self._ltui.ask_delete("文件.txt", on_confirm=...)
```

---

## 替换速查表

| 旧 API (QMessageBox) | 新 API |
|---------------------|--------|
| `QMessageBox.information(self, "标题", "消息")` | `self.show_info("消息", "标题")` |
| `QMessageBox.warning(self, "标题", "消息")` | `self.show_warning("消息", "标题")` |
| `QMessageBox.critical(self, "标题", "消息")` | `self.show_error("消息", "标题")` |
| `QMessageBox.question(...)` | `self.confirm("消息", on_confirm=...)` |
| - | `self.confirm_delete("文件名", on_confirm=...)` |

---

## 自动化测试

### 辅助函数

```python
from ui.components import (
    get_alert_band,        # 获取警报带
    get_inquiry_deck,      # 获取询问台
    get_status_rail,       # 获取状态栏
    get_visible_hints,     # 获取所有可见提示
    select_inquiry_option, # 选择询问台选项
    get_status_message,    # 获取状态消息
)
```

### 测试示例

```python
def test_assemble_conflict_resolve(qtbot):
    # 触发装配冲突
    assembler.start("pdf-extract-tool")

    # 断言询问台已展开
    deck = main_window.findChild(QWidget, "root-inquiry-deck")
    assert deck.isVisible()

    # 选择"分叉共生"
    radio = deck.findChild(QRadioButton, "inquiry-option-parallel")
    qtbot.mouseClick(radio, Qt.LeftButton)

    # 点击确认
    confirm_btn = deck.findChild(QPushButton, "inquiry-confirm")
    qtbot.mouseClick(confirm_btn, Qt.LeftButton)

    # 断言状态栏更新
    rail = main_window.findChild(QWidget, "soil-status-rail")
    assert "嫁接中" in rail.label.text()
```

---

## 组件清单

| 组件 | 文件 | ObjectName | 层级 |
|-----|------|-----------|-----|
| CanopyAlertBand | `components/canopy_alert.py` | `canopy-alert-band` | 顶层 |
| RootInquiryDeck | `components/inquiry_deck.py` | `root-inquiry-deck` | 顶层 |
| SoilStatusRail | `components/status_rail.py` | `soil-status-rail` | 底层 |
| DewdropHintCard | `components/dewdrop_hint.py` | `dewdrop-hint` | 浮动 |
| LivingTreeUI | `components/living_tree_ui.py` | - | 管理器 |
