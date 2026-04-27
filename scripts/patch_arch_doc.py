"""
Patch architecture doc to add new capabilities
"""
import re

filepath = r"f:\mhzyapp\LivingTreeAlAgent\docs\统一架构层改造方案_完整版_v3.md"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the status line (line 7)
old_status = '**状态**: 🚀 **实施中** - 阶段1/2/3/5已完成（阶段4进行中）'
new_status = '**状态**: 🚀 **实施中** - 阶段1/2/3/5已完成，阶段4/6进行中（实时错别字检查已集成）'
content = content.replace(old_status, new_status)

# 2. Add TextCorrectionTool to Section 3 (工具模块梳理)
# Find the learning/evolution tools section and add after it
old_section3_end = '''#### 🧠 学习与进化工具（3 个）

| 工具名称 | 文件路径 | 关键类 | 功能描述 | 状态 |
|---------|---------|--------|---------|------|
| 专家学习 | `client/src/business/expert_learning/` | `ExpertGuidedLearningSystem` | 三层学习架构 | ✅ 完整 |
| 技能进化 | `client/src/business/skill_evolution/` | `SkillEvolutionAgent`, `EvolutionEngine` | L0-L4 分层记忆系统 | ✅ 完整 |
| 实验循环 | `client/src/business/experiment_loop/` | `ExperimentDrivenEvolution` | 实验驱动进化 | ✅ 完整 |'''

new_section3_extra = '''#### ✏️ 文本处理工具（1 个）

| 工具名称 | 文件路径 | 关键类 | 功能描述 | 状态 |
|---------|---------|--------|---------|------|
| 错别字纠正 | `client/src/business/tools/text_correction_tool.py` | `TextCorrectionTool` | 上下文感知的错别字识别与纠正 | ✅ 完整 |

#### 🖊️ UI 组件（1 个）

| 组件名称 | 文件路径 | 关键类 | 功能描述 | 状态 |
|---------|---------|--------|---------|------|
| 拼写检查输入框 | `client/src/presentation/components/spell_check_edit.py` | `SpellCheckTextEdit` | 实时错别字检查（红色下划线+右键纠正） | ✅ 完整 |'''

# Insert after 学习与进化工具 section
insertion_point = '### 3.2 需要新建的工具模块（6 个）'
content = content.replace(insertion_point, new_section3_extra + '\n\n' + insertion_point)

# 3. Add new capabilities to Section 4 (统一架构层设计方案)
# Add after the BaseTool section
old_section4 = '''#### 🔧 BaseTool（工具基类）'''

new_section4_extra = '''#### ✏️ 错别字纠正工具（新增）

```python
# client/src/business/tools/text_correction_tool.py
class TextCorrectionTool(BaseTool):
    """
    上下文感知的错别字纠正工具
    
    功能：
    - 识别同音、形近、语法错别字
    - 从上下文推理正确用词
    - 使用 LLM (GlobalModelRouter) 进行语义理解
    - 支持批量处理
    """
    
    def execute(self, text: str = None, texts: list = None, 
                 context: str = "", auto_correct: bool = False) -> ToolResult:
        """执行错别字纠正"""
        # 调用 LLM 进行语义理解
        # 返回纠正建议和置信度
        pass
```

#### 🖊️ 实时拼写检查（UI 集成）

```python
# client/src/presentation/components/spell_check_edit.py
class SpellCheckTextEdit(QTextEdit):
    """
    实时错别字检查输入框
    
    功能：
    - 实时检测错别字（防抖 500ms）
    - 红色下划线标注疑似错别字
    - 右键点击错别字显示纠正建议
    - 异步调用，不阻塞 UI
    """
    
    corrections_found = pyqtSignal(list)  # 发现错别字时发出
    correction_requested = pyqtSignal(str, int)  # 用户请求纠正建议
```

**集成位置**：
- `ei_wizard_chat.py`: `self.message_input = SpellCheckTextEdit(...)`
- `ide/panel.py`: `self.message_input = SpellCheckTextEdit(...)`

#### 🔍 主动工具发现（新增）

```python
# client/src/business/hermes_agent/proactive_discovery_agent.py
class ProactiveDiscoveryAgent(BaseToolAgent):
    """
    主动工具发现智能体
    
    流程：
    1. 分析任务所需工具
    2. 检查 ToolRegistry 是否已有
    3. 缺失时调用 NaturalLanguageToolAdder 安装
    4. 刷新 ToolRegistry
    5. 执行原任务
    """
```

#### 🔗 工具链自动编排（新增）

```python
# client/src/business/tool_chain_orchestrator.py
class ToolChainOrchestrator:
    """
    基于 TaskDecomposer 的工具链自动编排系统
    
    功能：
    - 将复杂任务拆解为工具链
    - 按依赖顺序执行
    - 支持并行执行、失败重试
    - 步骤间自动传递数据
    """
```

#### 🔧 工具自我修复（新增）

```python
# client/src/business/self_evolution/tool_self_repairer.py
class ToolSelfRepairer:
    """
    工具自我修复器
    
    修复策略：
    - INSTALL_DEPENDENCY: 安装缺失依赖
    - FIX_CODE: 修复工具代码
    - FIX_CONFIG: 修复配置问题
    - REINSTALL_TOOL: 重装工具
    - UPDATE_REGISTRY: 更新注册表
    """
```

''' 

if old_section4 in content:
    content = content.replace(old_section4, new_section4_extra + '\n' + old_section4)

# 4. Update Section 8 (实施计划) - add progress
old_progress = '''### 8.5 阶段 5：智能体集成与测试（预计 2 天）'''
new_progress_extra = '''### 8.6 阶段 6：实时错别字检查集成（✅ 已完成 - 2026-04-28）

**目标**：集成实时错别字检查到聊天界面

**已完成**：
1. ✅ 创建 `TextCorrectionTool`（上下文感知错别字纠正）
2. ✅ 创建 `SpellCheckTextEdit`（实时拼写检查组件）
3. ✅ 集成到 `ei_wizard_chat.py`（环评助手聊天界面）
4. ✅ 集成到 `ide/panel.py`（IDE 聊天界面）

**文件清单**：
| 文件 | 操作 | 说明 |
|------|------|------|
| `client/src/business/tools/text_correction_tool.py` | 创建 | 错别字纠正工具（LLM 语义理解） |
| `client/src/presentation/components/spell_check_edit.py` | 创建 | 实时拼写检查组件 |
| `client/src/presentation/wizards/ei_wizard_chat.py` | 修改 | 集成 SpellCheckTextEdit |
| `client/src/presentation/modules/ide/panel.py` | 修改 | 集成 SpellCheckTextEdit |

'''

insertion_point2 = '### 8.6 阶段 6'
if insertion_point2 not in content:
    # Add before Section 9
    old_section9 = '### 8.5 阶段 5'
    content = content.replace(old_section9, new_progress_extra + '\n' + old_section9)

# Write back
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("架构文档更新完成")
print(f"  + 状态更新")
print(f"  + TextCorrectionTool 添加到工具清单")
print(f"  + SpellCheckTextEdit 添加到 UI 组件清单")
print(f"  + 主动工具发现/工具链编排/工具自我修复添加到架构设计")
print(f"  + 阶段 6 进度更新")
