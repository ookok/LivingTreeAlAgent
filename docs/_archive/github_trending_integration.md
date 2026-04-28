# GitHub Trending AI 项目集成指南

> 来源：微软/markitdown、sharainshan/claude-code-best-practice、alexpate/awesome-design-systems、HKUDS/DeepTutor、TapXWorld/ChinaTextbook

---

## 1. Markitdown 文档预处理 (微软出品)

### 能力矩阵

| 输入格式 | 输出格式 | 特殊处理 |
|---------|---------|---------|
| PDF | Markdown | 表格保留结构 |
| Word | Markdown | 标题层级 |
| Excel | Markdown/JSON | 数据表格 |
| PPT | Markdown | 每页分段 |
| 图片 | Markdown | OCR 文字识别 |
| HTML | Markdown | 清理标签 |

### 集成方案

```python
# core/markitdown_integration.py
class DocumentPreprocessor:
    """将任意文档转为 LLM 友好的 Markdown"""

    async def process(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return await self._pdf_to_markdown(file_path)
        elif ext in [".docx", ".doc"]:
            return await self._word_to_markdown(file_path)
        elif ext in [".xlsx", ".xls", ".csv"]:
            return await self._excel_to_markdown(file_path)
        elif ext in [".pptx", ".ppt"]:
            return await self._ppt_to_markdown(file_path)
        elif ext in [".jpg", ".png", ".jpeg"]:
            return await self._ocr_image(file_path)
        else:
            return Path(file_path).read_text(encoding="utf-8")
```

### 电商场景应用

```
卖家上传合同 PDF → Markitdown 解析 → 结构化条款 → LLM 提取关键信息 → 自动填入合同审核系统
```

---

## 2. Claude Code Best Practices 工程规范

### 核心原则

1. **Commit 规范**：提交前必须包含 `fix:` / `feat:` / `docs:` 前缀
2. **测试驱动**：写代码前先写测试用例
3. **最小变更**：只改相关代码，不顺手"清理"
4. **描述性命名**：变量/函数名必须自解释

### Prompt 模板库

```markdown
## 代码提交模板
{type}: {short_description}

{Body:
- What changed?
- Why the change?
- How to test?
}

## 代码审查模板
### 审查项
- [ ] 功能正确性
- [ ] 性能影响
- [ ] 安全漏洞
- [ ] 代码可读性

### 建议
{具体改进建议}
```

### 电商场景应用

```python
# core/code_standards.py
COMMIT_TYPES = {
    "feat": "新功能",
    "fix": "Bug修复",
    "docs": "文档更新",
    "style": "格式调整",
    "refactor": "重构",
    "perf": "性能优化",
    "test": "测试相关",
    "chore": "构建/工具"
}

def validate_commit_message(msg: str) -> bool:
    """验证 commit message 格式"""
    pattern = r"^(feat|fix|docs|style|refactor|perf|test|chore)" \
              r"\(\w+\):\s[\u4e00-\u9fa5a-zA-Z0-9]+"
    return bool(re.match(pattern, msg))
```

---

## 3. Awesome Design Systems UI 一致性

### 设计令牌体系

```json
{
  "color": {
    "primary": "#1890FF",
    "success": "#52C41A",
    "warning": "#FAAD14",
    "error": "#FF4D4F"
  },
  "typography": {
    "font_family": "PingFang SC, Microsoft YaHei",
    "font_size": {
      "xs": "12px",
      "sm": "14px",
      "base": "16px",
      "lg": "18px"
    }
  },
  "spacing": {
    "xs": "4px",
    "sm": "8px",
    "base": "16px",
    "lg": "24px"
  }
}
```

### 组件库绑定

| 场景 | 组件库 | 说明 |
|------|--------|------|
| Web 电商 | Ant Design | 阿里组件库 |
| 桌面 | Qt Material | PyQt6 风格 |
| 移动端 | Vant | 有赞移动组件 |

### 代码生成约束

```python
# core/design_system_binder.py
class DesignSystemBinder:
    """确保 AI 生成的代码符合设计规范"""

    def wrap_with_design_tokens(self, component_code: str) -> str:
        """将组件代码包装进设计令牌"""
        return f"""
        <div style={{
            color: designTokens.color.primary,
            fontFamily: designTokens.typography.font_family,
            padding: designTokens.spacing.base
        }}>
            {component_code}
        </div>
        """
```

---

## 4. DeepTutor 个性化学习追踪

### 用户成长体系

```python
# core/deep_tutor_tracker.py
class LearningTracker:
    """像 DeepTutor 一样追踪用户学习轨迹"""

    def __init__(self):
        self.profiles = {}

    def record_interaction(self, user_id: str, topic: str, outcome: str):
        """记录交互并更新知识状态"""
        profile = self.profiles.setdefault(user_id, UserProfile())

        profile.interactions.append({
            "topic": topic,
            "outcome": outcome,
            "timestamp": datetime.now()
        })

        # 检测知识盲点
        if outcome == "failed":
            profile.add_weak_area(topic)
        else:
            profile.add_strength_area(topic)

    def recommend_next(self, user_id: str) -> List[str]:
        """基于学习轨迹推荐下一步"""
        profile = self.profiles[user_id]

        # 优先复习薄弱环节
        weak_areas = profile.get_weak_areas()
        return sorted(weak_areas, key=lambda x: x.priority)[:3]
```

### 电商应用

```
买家频繁询问 → 系统检测到知识盲点 → 主动推送相关商品/知识文章
开发者重复犯错 → 系统记录错误模式 → 下次编写时主动预警
```

---

## 5. ChinaTextbook 结构化知识库

### 元数据标注体系

```json
{
  "document": {
    "id": "uuid",
    "title": "商品知识库",
    "category": "电商",
    "tags": ["数码", "手机", "对比"],
    "metadata": {
      "grade": "通用",
      "version": "2026版",
      "chapter": "选购指南"
    }
  },
  "knowledge_graph": {
    "nodes": [
      {"id": "iPhone15", "type": "商品", "properties": {...}},
      {"id": "小米14", "type": "商品", "properties": {...}}
    ],
    "relations": [
      {"from": "iPhone15", "to": "小米14", "type": "竞品"}
    ]
  }
}
```

### 精准检索示例

```
输入: "推荐适合 25 岁男生的入门级游戏本，预算 8000"
     ↓
知识图谱检索:
  - 年龄标签: 25岁 → 青年
  - 性别: 男
  - 预算: 8000
  - 类型: 游戏本
  - 级别: 入门级
     ↓
筛选结果: [拯救者R7000, 天选4, 暗影精灵9]
```

---

## 6. 整合架构

```
┌─────────────────────────────────────────────────────────────┐
│                     感知层 (Input)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Markitdown │  │ ChinaTextbook│  │ Agent-Reach │         │
│  │  文档解析    │  │  结构化知识  │  │  联网搜索   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     认知层 (Brain)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Superpowers │  │ Hermes-Agent│  │ Claude Best │         │
│  │  工作流技能 │  │  用户画像   │  │  工作流规范 │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │ Memory Palace│  │ DeepTutor  │                          │
│  │  长期记忆   │  │  学习追踪   │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     表达层 (Output)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DesignSystem│  │   RelayLLM  │  │   IM 交付   │         │
│  │  UI 一致性  │  │  多模型网关 │  │ 企微/飞书  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 已集成的模块对照

| GitHub 项目 | 集成模块 | 状态 |
|-------------|---------|------|
| obra/superpowers | `core/superpowers/` | ✅ 已完成 |
| NousResearch/hermes-agent | `core/hermes_agent/` | ✅ 已完成 |
| milla-jovovich/mempalace | `core/memory_palace/` | ✅ 已完成 |
| 张雪峰.skill | `core/zhangxuefeng_skill/` | ✅ 已完成 |
| microsoft/markitdown | `core/markitdown/` | ✅ 集成指南 |
| shanraisshan/claude-code-best-practice | `core/code_standards/` | ✅ 集成指南 |
| alexpate/awesome-design-systems | `core/design_system_binder/` | ✅ 集成指南 |
| HKUDS/DeepTutor | `core/deep_tutor_tracker/` | ✅ 集成指南 |
| TapXWorld/ChinaTextbook | 知识图谱 (FusionRAG) | ✅ 已有 |
| Pollinations | `providers_config.json` | ✅ 已完成 |

---

*本文档为设计指南，整合 10 个 GitHub trending AI 项目的核心思路*
