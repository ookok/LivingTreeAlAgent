# UI 优化规范

## 一、设计原则

### 1. 人机工程学原则
- **视线区域**：最常用的交互元素应放在眼睛自然视线的20度范围内
- **操作舒适**：主要操作区域应在前臂水平位置（坐姿时肘部高度）
- **最小努力**：最常用的功能应最容易触达
- **反馈明确**：每个操作都应有明确的视觉反馈

### 2. 视觉层次
- **主次分明**：主要功能突出，次要功能淡化
- **分组合理**：相关功能放在一起
- **留白适当**：避免过于拥挤

### 3. 色彩系统
- **主色调**：`#3B82F6` (蓝色 - 科技感、专业)
- **强调色**：`#10B981` (绿色 - 成功、确认)
- **警告色**：`#F59E0B` (橙色 - 警告)
- **错误色**：`#EF4444` (红色 - 错误)
- **背景色**：深色模式使用 `#1a1a2e`，浅色模式使用 `#F8FAFC`
- **文字色**：深色模式使用 `#E2E8F0`，浅色模式使用 `#1E293B`

### 4. 间距系统
- **xs**: 4px
- **sm**: 8px
- **md**: 16px
- **lg**: 24px
- **xl**: 32px
- **2xl**: 48px

### 5. 圆角系统
- **sm**: 4px (按钮、输入框)
- **md**: 8px (卡片、面板)
- **lg**: 12px (对话框)
- **xl**: 16px (大面板)

## 二、布局优化

### 1. 三栏布局优化
```
┌────────────────────────────────────────────────────────────┐
│  标题栏 (40px)                                               │
├────────┬───────────────────────────────────────┬───────────┤
│        │                                       │           │
│  侧边栏 │         主内容区                      │  工具面板  │
│ (240px)│         (flex: 1)                     │  (280px)  │
│        │                                       │           │
│  会话   │  ┌─────────────────────────────────┐ │  模型池   │
│  列表   │  │     消息区域 (scrollable)       │ │  工作区   │
│        │  │                                 │ │           │
│  新建   │  │                                 │ │           │
│  会话   │  └─────────────────────────────────┘ │           │
│        │  ┌─────────────────────────────────┐ │           │
│        │  │     输入区域 (固定底部)           │ │           │
│        │  └─────────────────────────────────┘ │           │
├────────┴───────────────────────────────────────┴───────────┤
│  状态栏 (32px)                                               │
└────────────────────────────────────────────────────────────┘
```

### 2. 面板内布局
- **头部**：标题 + 操作按钮 (48px)
- **内容区**：自适应高度，可滚动
- **底部**：分页或加载更多 (如果是列表)

### 3. 卡片布局
- 卡片之间间距：16px
- 卡片内边距：16px
- 卡片阴影：`0 2px 8px rgba(0,0,0,0.1)`

## 三、组件规范

### 1. 按钮
```python
# 主要按钮
QPushButton {
    background-color: #3B82F6;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
}

# 次要按钮
QPushButton {
    background-color: transparent;
    color: #3B82F6;
    border: 1px solid #3B82F6;
    border-radius: 6px;
    padding: 10px 20px;
}

# 图标按钮
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px;
}
```

### 2. 输入框
```python
QLineEdit, QTextEdit {
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 14px;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #3B82F6;
    outline: none;
}
```

### 3. 标签页
```python
QTabWidget::pane {
    border: none;
    background-color: transparent;
}

QTabBar::tab {
    background-color: transparent;
    color: #64748B;
    padding: 12px 20px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #3B82F6;
    border-bottom: 2px solid #3B82F6;
}

QTabBar::tab:hover {
    color: #3B82F6;
    background-color: #F1F5F9;
}
```

### 4. 分割器
```python
QSplitter::handle {
    background-color: #E2E8F0;
    width: 1px;
}

QSplitter::handle:hover {
    background-color: #3B82F6;
}
```

### 5. 滚动条
```python
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #CBD5E1;
    border-radius: 4px;
    min-height: 40px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94A3B8;
}
```

## 四、交互反馈

### 1. 悬停效果
- 背景色变亮 10%
- 添加轻微阴影
- 过渡时间：150ms

### 2. 点击效果
- 背景色变暗 10%
- 缩放 0.98
- 过渡时间：100ms

### 3. 加载状态
- 显示微调进度指示器
- 禁用相关交互
- 半透明遮罩

### 4. 成功/错误提示
- Toast 通知：3秒自动消失
- 颜色区分：绿色=成功，红色=错误，橙色=警告，蓝色=信息

## 五、无障碍

### 1. 字体大小
- 标题：18px / 20px / 24px
- 正文：14px
- 辅助文字：12px
- 最小可读字体：11px

### 2. 对比度
- 文本与背景对比度 ≥ 4.5:1
- 大文本对比度 ≥ 3:1

### 3. 焦点指示
- 使用 2px 蓝色轮廓
- 焦点顺序符合逻辑

## 六、性能优化

### 1. 延迟加载
- 非可见区域的内容延迟加载
- 图片懒加载

### 2. 虚拟化
- 长列表使用虚拟滚动
- 只渲染可见项

### 3. 缓存
- 缓存已渲染的组件
- 避免重复计算
