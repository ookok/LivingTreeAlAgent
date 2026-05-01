<template>
  <div class="bottom-panel" :class="{ expanded: expanded }">
    <div class="panel-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-item"
        :class="{ active: activeTab === tab.id }"
        @click="switchTab(tab.id)"
      >
        <NIcon :component="tab.icon" :size="14" />
        <span>{{ tab.name }}</span>
        <span v-if="tab.count" class="tab-count">{{ tab.count }}</span>
        <NButton text size="small" @click.stop="closeTab(tab.id)">
          <NIcon :component="CloseIcon" :size="12" />
        </NButton>
      </div>
      
      <div class="panel-actions">
        <NButton text size="small" @click="toggleExpand">
          <NIcon :component="expanded ? ChevronDownIcon : ChevronUpIcon" :size="14" />
        </NButton>
      </div>
    </div>
    
    <div class="panel-content">
      <!-- 终端 -->
      <div v-if="activeTab === 'terminal'" class="terminal-panel">
        <div class="terminal-tabs">
          <div
            v-for="term in terminals"
            :key="term.id"
            class="terminal-tab"
            :class="{ active: activeTerminal === term.id }"
            @click="switchTerminal(term.id)"
          >
            <NIcon :component="TerminalIcon" :size="12" />
            <span>{{ term.name }}</span>
            <NButton text size="small" @click.stop="closeTerminal(term.id)">
              <NIcon :component="XIcon" :size="10" />
            </NButton>
          </div>
          <div class="new-terminal-btn" @click="newTerminal">
            <NIcon :component="PlusIcon" :size="14" />
          </div>
        </div>
        <div class="terminal-content">
          <pre class="terminal-output">{{ terminalOutput }}</pre>
          <div class="terminal-input-wrapper">
            <span class="terminal-prompt">></span>
            <input 
              v-model="terminalInput" 
              class="terminal-input" 
              @keydown.enter="executeCommand"
              placeholder="输入命令..."
            />
          </div>
        </div>
      </div>
      
      <!-- 问题面板 -->
      <div v-if="activeTab === 'problems'" class="problems-panel">
        <div class="problems-tabs">
          <NButton text :class="{ active: problemFilter === 'all' }" @click="problemFilter = 'all'">全部</NButton>
          <NButton text :class="{ active: problemFilter === 'errors' }" @click="problemFilter = 'errors'">错误({{ errorCount }})</NButton>
          <NButton text :class="{ active: problemFilter === 'warnings' }" @click="problemFilter = 'warnings'">警告({{ warningCount }})</NButton>
          <NButton text :class="{ active: problemFilter === 'info' }" @click="problemFilter = 'info'">信息({{ infoCount }})</NButton>
        </div>
        <div class="problems-list">
          <div v-for="problem in filteredProblems" :key="problem.id" class="problem-item">
            <NIcon :component="getProblemIcon(problem.type)" :size="14" />
            <span class="problem-file">{{ problem.file }}</span>
            <span class="problem-message">{{ problem.message }}</span>
            <span class="problem-line">L{{ problem.line }}</span>
          </div>
        </div>
      </div>
      
      <!-- 输出面板 -->
      <div v-if="activeTab === 'output'" class="output-panel">
        <div class="output-tabs">
          <NButton text :class="{ active: outputTab === 'debug' }" @click="outputTab = 'debug'">调试</NButton>
          <NButton text :class="{ active: outputTab === 'terminal' }" @click="outputTab = 'terminal'">终端</NButton>
          <NButton text :class="{ active: outputTab === 'test' }" @click="outputTab = 'test'">测试</NButton>
        </div>
        <pre class="output-content">{{ outputContent }}</pre>
        <div class="output-actions">
          <NButton text size="small">清除</NButton>
          <NButton text size="small">保存到文件</NButton>
        </div>
      </div>
      
      <!-- 调试控制台 -->
      <div v-if="activeTab === 'debug'" class="debug-panel">
        <div class="debug-tabs">
          <NButton text :class="{ active: debugTab === 'variables' }" @click="debugTab = 'variables'">变量</NButton>
          <NButton text :class="{ active: debugTab === 'stack' }" @click="debugTab = 'stack'">调用堆栈</NButton>
          <NButton text :class="{ active: debugTab === 'breakpoints' }" @click="debugTab = 'breakpoints'">断点</NButton>
        </div>
        
        <div v-if="debugTab === 'variables'" class="variables-panel">
          <div v-for="var in variables" :key="var.name" class="variable-item">
            <span class="var-name">{{ var.name }}</span>
            <span class="var-value">{{ var.value }}</span>
          </div>
        </div>
        
        <div v-if="debugTab === 'stack'" class="stack-panel">
          <div v-for="(frame, idx) in callStack" :key="idx" class="stack-item">
            <span class="stack-function">{{ frame.function }}</span>
            <span class="stack-location">{{ frame.location }}</span>
          </div>
        </div>
        
        <div v-if="debugTab === 'breakpoints'" class="breakpoints-panel">
          <div v-for="bp in breakpoints" :key="bp.id" class="breakpoint-item">
            <NIcon :component="CircleIcon" :size="14" />
            <span>{{ bp.location }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { 
  Terminal, AlertCircle, FileText, Bug, ChevronDown, ChevronUp,
  X, Plus, Circle, AlertTriangle, Info
} from '@vicons/ionicons5'

const CloseIcon = { render: () => h(X) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const ChevronUpIcon = { render: () => h(ChevronUp) }
const TerminalIcon = { render: () => h(Terminal) }
const PlusIcon = { render: () => h(Plus) }
const XIcon = { render: () => h(X) }
const CircleIcon = { render: () => h(Circle) }

const expanded = ref(true)
const activeTab = ref('terminal')
const activeTerminal = ref(1)

const tabs = ref([
  { id: 'terminal', name: '终端', icon: TerminalIcon, count: null },
  { id: 'problems', name: '问题', icon: AlertCircle, count: 10 },
  { id: 'output', name: '输出', icon: FileText, count: null },
  { id: 'debug', name: '调试控制台', icon: Bug, count: null },
])

const terminals = ref([
  { id: 1, name: '终端1' },
  { id: 2, name: '终端2' },
])

const terminalOutput = ref('> python main.py\nHello World!\n')
const terminalInput = ref('')

const problemFilter = ref('all')
const errorCount = ref(2)
const warningCount = ref(5)
const infoCount = ref(3)

const problems = ref([
  { id: 1, type: 'error', file: 'main.py', message: '未定义变量 \'x\'', line: 10 },
  { id: 2, type: 'error', file: 'utils.py', message: '语法错误', line: 5 },
  { id: 3, type: 'warning', file: 'main.py', message: '函数过长', line: 25 },
  { id: 4, type: 'warning', file: 'main.py', message: '可优化', line: 30 },
  { id: 5, type: 'info', file: 'main.py', message: '未使用的导入', line: 3 },
])

const filteredProblems = computed(() => {
  if (problemFilter.value === 'all') return problems.value
  return problems.value.filter(p => p.type === problemFilter.value)
})

const outputTab = ref('terminal')
const outputContent = ref(`程序启动成功
监听端口: 8080
数据库连接成功
收到请求: GET /api/data
响应时间: 120ms`)

const debugTab = ref('variables')
const variables = ref([
  { name: 'name', value: '"John"' },
  { name: 'age', value: '25' },
  { name: 'scores', value: '[90, 85, 88]' },
])

const callStack = ref([
  { function: 'main()', location: 'main.py:10' },
  { function: 'helper()', location: 'utils.py:5' },
])

const breakpoints = ref([
  { id: 1, location: 'main.py:8' },
  { id: 2, location: 'utils.py:15' },
])

function switchTab(tabId) {
  activeTab.value = tabId
}

function closeTab(tabId) {
  const index = tabs.value.findIndex(t => t.id === tabId)
  if (index !== -1) {
    tabs.value.splice(index, 1)
    if (activeTab.value === tabId) {
      activeTab.value = tabs.value[0]?.id || null
    }
  }
}

function toggleExpand() {
  expanded.value = !expanded.value
}

function switchTerminal(termId) {
  activeTerminal.value = termId
}

function closeTerminal(termId) {
  const index = terminals.value.findIndex(t => t.id === termId)
  if (index !== -1) {
    terminals.value.splice(index, 1)
    if (activeTerminal.value === termId) {
      activeTerminal.value = terminals.value[0]?.id || null
    }
  }
}

function newTerminal() {
  const newId = Date.now()
  terminals.value.push({ id: newId, name: `终端${terminals.value.length + 1}` })
  activeTerminal.value = newId
}

function executeCommand() {
  if (!terminalInput.value.trim()) return
  terminalOutput.value += `> ${terminalInput.value}\n`
  terminalOutput.value += `Command executed: ${terminalInput.value}\n`
  terminalInput.value = ''
}

function getProblemIcon(type) {
  if (type === 'error') return { render: () => h(AlertCircle) }
  if (type === 'warning') return { render: () => h(AlertTriangle) }
  return { render: () => h(Info) }
}
</script>

<style scoped>
.bottom-panel {
  height: 200px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.bottom-panel.expanded {
  height: 400px;
}

.panel-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-bottom: 1px solid var(--border-color);
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
}

.tab-item.active {
  background: var(--bg-hover);
}

.tab-count {
  background: var(--danger-color);
  color: white;
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 10px;
}

.panel-actions {
  margin-left: auto;
}

.panel-content {
  flex: 1;
  overflow: hidden;
}

.terminal-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.terminal-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-bottom: 1px solid var(--border-color);
}

.terminal-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
}

.terminal-tab.active {
  background: var(--bg-hover);
}

.new-terminal-btn {
  padding: 4px 8px;
  cursor: pointer;
}

.terminal-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 8px;
  font-family: monospace;
  font-size: 14px;
  overflow-y: auto;
}

.terminal-output {
  flex: 1;
  margin: 0;
  white-space: pre-wrap;
  overflow-y: auto;
}

.terminal-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-prompt {
  color: var(--success-color);
}

.terminal-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: monospace;
}

.problems-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.problems-tabs {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.problems-tabs .active {
  background: var(--bg-hover);
}

.problems-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.problem-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}

.problem-file {
  font-family: monospace;
}

.problem-message {
  flex: 1;
}

.problem-line {
  font-family: monospace;
  color: var(--text-secondary);
}

.output-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.output-tabs {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.output-tabs .active {
  background: var(--bg-hover);
}

.output-content {
  flex: 1;
  margin: 0;
  padding: 8px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  overflow-y: auto;
}

.output-actions {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid var(--border-color);
}

.debug-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.debug-tabs {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.debug-tabs .active {
  background: var(--bg-hover);
}

.variables-panel, .stack-panel, .breakpoints-panel {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.variable-item {
  display: flex;
  justify-content: space-between;
  padding: 4px;
}

.var-name {
  font-weight: 600;
}

.stack-item {
  display: flex;
  justify-content: space-between;
  padding: 4px;
}

.breakpoint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}
</style>