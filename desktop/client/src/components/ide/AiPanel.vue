<template>
  <div class="ai-panel">
    <div class="panel-header">
      <NIcon :component="BrainIcon" :size="14" />
      <span>AI 辅助</span>
      <NButton text size="tiny" @click="toggleMode">
        <NIcon :component="ModeIcon" :size="12" />
      </NButton>
    </div>
    
    <div class="panel-content">
      <div class="ai-modes">
        <NButton 
          v-for="mode in modes" 
          :key="mode.id"
          :type="currentMode === mode.id ? 'primary' : 'default'"
          size="small"
          @click="currentMode = mode.id"
        >
          <NIcon :component="mode.icon" :size="14" />
          {{ mode.name }}
        </NButton>
      </div>
      
      <div class="ai-input-area">
        <textarea
          v-model="prompt"
          class="ai-prompt"
          :placeholder="currentModePlaceholder"
          rows="4"
        ></textarea>
        <NButton type="primary" @click="generate" :disabled="isGenerating">
          <NIcon :component="isGenerating ? LoaderIcon : SparklesIcon" :size="14" />
          {{ isGenerating ? '生成中...' : '生成' }}
        </NButton>
      </div>
      
      <div v-if="currentMode === 'explain'" class="quick-actions">
        <div class="actions-title">快速操作</div>
        <NButton text size="small" @click="explainSelection">
          <NIcon :component="HelpCircleIcon" :size="12" />
          解释选中代码
        </NButton>
        <NButton text size="small" @click="reviewCode">
          <NIcon :component="CheckCircleIcon" :size="12" />
          代码审查
        </NButton>
        <NButton text size="small" @click="optimizeCode">
          <NIcon :component="ZapIcon" :size="12" />
          优化代码
        </NButton>
      </div>
      
      <div v-if="currentMode === 'generate'" class="quick-templates">
        <div class="templates-title">代码模板</div>
        <div 
          v-for="template in codeTemplates" 
          :key="template.id" 
          class="template-item"
          @click="applyTemplate(template)"
        >
          <NIcon :component="template.icon" :size="14" />
          <span>{{ template.name }}</span>
        </div>
      </div>
      
      <div v-if="currentMode === 'debug'" class="debug-suggestions">
        <div class="suggestions-title">调试建议</div>
        <div 
          v-for="(suggestion, index) in debugSuggestions" 
          :key="index" 
          class="suggestion-item"
        >
          <NIcon :component="suggestion.icon" :size="14" />
          <span>{{ suggestion.title }}</span>
          <p>{{ suggestion.description }}</p>
        </div>
      </div>
      
      <div v-if="aiResult" class="ai-result">
        <div class="result-header">
          <span>AI 结果</span>
          <NButton text size="tiny" @click="copyResult">
            <NIcon :component="CopyIcon" :size="12" />
          </NButton>
        </div>
        <div class="result-content">
          <pre class="result-code"><code>{{ aiResult }}</code></pre>
        </div>
        <div class="result-actions">
          <NButton text size="small" @click="insertCode">
            <NIcon :component="PasteIcon" :size="12" />
            插入代码
          </NButton>
          <NButton text size="small" @click="replaceSelection">
            <NIcon :component="ReplaceIcon" :size="12" />
            替换选中
          </NButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { 
  Brain, Wand2, HelpCircle, Bug, Copy, Paste, Replace,
  Sparkles, Loader, CheckCircle, Zap, Code, FileText, 
  Database, Cloud, Server, Lock, RefreshCw
} from '@vicons/ionicons5'

const BrainIcon = { render: () => h(Brain) }
const ModeIcon = { render: () => h(Wand2) }
const SparklesIcon = { render: () => h(Sparkles) }
const LoaderIcon = { render: () => h(Loader) }
const HelpCircleIcon = { render: () => h(HelpCircle) }
const CheckCircleIcon = { render: () => h(CheckCircle) }
const ZapIcon = { render: () => h(Zap) }
const CopyIcon = { render: () => h(Copy) }
const PasteIcon = { render: () => h(Paste) }
const ReplaceIcon = { render: () => h(Replace) }
const CodeIcon = { render: () => h(Code) }
const FileTextIcon = { render: () => h(FileText) }
const DatabaseIcon = { render: () => h(Database) }
const CloudIcon = { render: () => h(Cloud) }
const ServerIcon = { render: () => h(Server) }
const LockIcon = { render: () => h(Lock) }
const RefreshCwIcon = { render: () => h(RefreshCw) }

const modes = [
  { id: 'explain', name: '解释', icon: HelpCircleIcon },
  { id: 'generate', name: '生成', icon: SparklesIcon },
  { id: 'debug', name: '调试', icon: Bug },
]

const currentMode = ref('explain')
const prompt = ref('')
const isGenerating = ref(false)
const aiResult = ref('')

const codeTemplates = [
  { id: 1, name: 'Python 函数模板', icon: CodeIcon },
  { id: 2, name: 'Vue 组件模板', icon: FileTextIcon },
  { id: 3, name: '数据库连接', icon: DatabaseIcon },
  { id: 4, name: 'API 请求', icon: CloudIcon },
  { id: 5, name: '服务器配置', icon: ServerIcon },
  { id: 6, name: '加密函数', icon: LockIcon },
]

const debugSuggestions = [
  { 
    title: '检查变量类型', 
    description: '确保所有变量类型正确匹配',
    icon: CodeIcon 
  },
  { 
    title: '添加日志输出', 
    description: '在关键位置添加调试日志',
    icon: RefreshCwIcon 
  },
  { 
    title: '验证边界条件', 
    description: '检查输入参数的边界情况',
    icon: CheckCircleIcon 
  },
]

const currentModePlaceholder = computed(() => {
  const placeholders = {
    explain: '输入代码或问题，我来帮你解释...',
    generate: '描述你想要的代码，我来帮你生成...',
    debug: '描述问题或粘贴错误信息...',
  }
  return placeholders[currentMode.value]
})

async function generate() {
  if (!prompt.value.trim()) return
  
  isGenerating.value = true
  aiResult.value = ''
  
  await new Promise(resolve => setTimeout(resolve, 1500))
  
  const results = {
    explain: `这是一段 Python 代码，实现了一个简单的问候功能：

**代码分析：**
- 使用 f-string 格式化字符串
- 定义了 greet 函数接收 name 参数
- 返回格式化的问候语

**执行流程：**
1. 函数接收 name 参数
2. 使用 f-string 拼接字符串
3. 返回问候消息

**优化建议：**
可以添加参数验证，确保 name 不为空。`,
    
    generate: `def ${prompt.value.trim()}(arg1, arg2):
    """
    ${prompt.value.trim()} 函数说明
    
    参数:
        arg1: 第一个参数
        arg2: 第二个参数
    
    返回:
        处理结果
    """
    try:
        # 核心逻辑
        result = arg1 + arg2
        
        # 验证结果
        if result < 0:
            raise ValueError("结果不能为负数")
        
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None`,
    
    debug: `**问题分析：**

1. **可能原因**：
   - 变量未初始化
   - 类型不匹配
   - 索引越界
   - 空值引用

2. **建议步骤**：
   - 添加断点检查变量状态
   - 验证输入参数类型
   - 添加异常处理

3. **修复建议**：
   \`\`\`python
   # 添加类型检查
   if not isinstance(value, int):
       raise TypeError("Expected int")
   \`\`\``,
  }
  
  aiResult.value = results[currentMode.value]
  isGenerating.value = false
}

function explainSelection() {
  prompt.value = '请解释这段代码的功能和实现原理'
  generate()
}

function reviewCode() {
  prompt.value = '请审查以下代码，找出潜在问题和改进建议'
  generate()
}

function optimizeCode() {
  prompt.value = '请优化这段代码，提高性能和可读性'
  generate()
}

function applyTemplate(template) {
  const templates = {
    1: `def function_name(params):
    """函数文档字符串"""
    # 实现逻辑
    pass`,
    2: `<template>
  <div class="component">
    <!-- 组件内容 -->
  </div>
</template>

<script setup>
// 组件逻辑
</script>`,
    3: `import sqlite3

def connect_db(db_path):
    """连接数据库"""
    conn = sqlite3.connect(db_path)
    return conn`,
    4: `import requests

def fetch_data(url, params=None):
    """发送 API 请求"""
    response = requests.get(url, params=params)
    return response.json()`,
  }
  
  aiResult.value = templates[template.id] || `# ${template.name}
# 添加你的代码...`
}

function copyResult() {
  navigator.clipboard.writeText(aiResult.value)
}

function insertCode() {
  console.log('Insert code:', aiResult.value)
}

function replaceSelection() {
  console.log('Replace selection:', aiResult.value)
}

function toggleMode() {
  const index = modes.findIndex(m => m.id === currentMode.value)
  currentMode.value = modes[(index + 1) % modes.length].id
}
</script>

<style scoped>
.ai-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.ai-modes {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.ai-modes button {
  flex: 1;
}

.ai-input-area {
  margin-bottom: 16px;
}

.ai-prompt {
  width: 100%;
  padding: 10px 12px;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  resize: none;
  outline: none;
  margin-bottom: 8px;
}

.ai-prompt::placeholder {
  color: var(--text-secondary);
}

.quick-actions, .quick-templates, .debug-suggestions {
  margin-bottom: 16px;
}

.actions-title, .templates-title, .suggestions-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.template-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.template-item:hover {
  background: var(--bg-hover);
}

.template-item span {
  font-size: 13px;
  color: var(--text-primary);
}

.suggestion-item {
  padding: 12px;
  background: var(--bg-dark);
  border-radius: 8px;
  margin-bottom: 8px;
}

.suggestion-item span {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.suggestion-item p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.ai-result {
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.result-content {
  background: var(--bg-dark);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.result-code {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.result-actions button {
  flex: 1;
}
</style>