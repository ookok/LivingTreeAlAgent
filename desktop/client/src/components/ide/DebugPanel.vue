<template>
  <div class="debug-panel">
    <div class="panel-header">
      <NIcon :component="BugIcon" :size="14" />
      <span>调试</span>
      <div class="header-right">
        <NButton text size="tiny" @click="toggleBreakpoints">
          <NIcon :component="toggleBreakpointsActive ? EyeOffIcon : EyeIcon" :size="12" />
        </NButton>
      </div>
    </div>
    
    <div class="panel-content">
      <div class="debug-toolbar">
        <NButton 
          :type="isDebugging ? 'primary' : 'default'" 
          size="small" 
          @click="startDebug"
        >
          <NIcon :component="isDebugging ? SquareIcon : PlayIcon" :size="14" />
          {{ isDebugging ? '停止' : '启动' }}
        </NButton>
        <NButton text size="small" @click="stepOver" :disabled="!isDebugging">
          <NIcon :component="StepOverIcon" :size="14" />
          跳过
        </NButton>
        <NButton text size="small" @click="stepInto" :disabled="!isDebugging">
          <NIcon :component="StepIntoIcon" :size="14" />
          进入
        </NButton>
        <NButton text size="small" @click="stepOut" :disabled="!isDebugging">
          <NIcon :component="StepOutIcon" :size="14" />
          退出
        </NButton>
        <NButton text size="small" @click="continueDebug" :disabled="!isDebugging">
          <NIcon :component="PlayIcon" :size="14" />
          继续
        </NButton>
      </div>
      
      <div class="debug-sections">
        <div class="section">
          <div class="section-header" @click="toggleSection('breakpoints')">
            <NIcon 
              :component="sections.breakpoints ? ChevronDownIcon : ChevronRightIcon" 
              :size="12" 
            />
            <span>断点</span>
            <span class="count">{{ breakpoints.length }}</span>
          </div>
          <div v-if="sections.breakpoints" class="section-content">
            <div 
              v-for="bp in breakpoints" 
              :key="bp.id" 
              class="breakpoint-item"
              :class="{ disabled: bp.disabled }"
            >
              <NButton text size="tiny" @click="toggleBreakpoint(bp)">
                <NIcon :component="bp.disabled ? CircleIcon : CircleDotIcon" :size="12" />
              </NButton>
              <span class="bp-file">{{ bp.file }}</span>
              <span class="bp-line">行 {{ bp.line }}</span>
              <NButton text size="tiny" @click="removeBreakpoint(bp)">
                <NIcon :component="XIcon" :size="12" />
              </NButton>
            </div>
            <div v-if="breakpoints.length === 0" class="empty">
              暂无断点
            </div>
          </div>
        </div>
        
        <div class="section">
          <div class="section-header" @click="toggleSection('watch')">
            <NIcon 
              :component="sections.watch ? ChevronDownIcon : ChevronRightIcon" 
              :size="12" 
            />
            <span>监视</span>
            <NButton text size="tiny" @click="addWatchExpression">
              <NIcon :component="PlusIcon" :size="12" />
            </NButton>
          </div>
          <div v-if="sections.watch" class="section-content">
            <div 
              v-for="(expr, index) in watchExpressions" 
              :key="index" 
              class="watch-item"
            >
              <input
                :value="expr.expression"
                @input="updateWatchExpression(index, $event)"
                class="watch-input"
              />
              <span class="watch-value">{{ expr.value }}</span>
              <NButton text size="tiny" @click="removeWatchExpression(index)">
                <NIcon :component="XIcon" :size="12" />
              </NButton>
            </div>
            <div v-if="watchExpressions.length === 0" class="empty">
              暂无监视表达式
            </div>
          </div>
        </div>
        
        <div class="section">
          <div class="section-header" @click="toggleSection('callstack')">
            <NIcon 
              :component="sections.callstack ? ChevronDownIcon : ChevronRightIcon" 
              :size="12" 
            />
            <span>调用栈</span>
          </div>
          <div v-if="sections.callstack" class="section-content">
            <div 
              v-for="(frame, index) in callStack" 
              :key="index" 
              class="stack-item"
              :class="{ active: index === 0 }"
            >
              <NIcon :component="ArrowRightIcon" :size="12" />
              <span class="stack-function">{{ frame.function }}</span>
              <span class="stack-location">{{ frame.file }}:{{ frame.line }}</span>
            </div>
            <div v-if="callStack.length === 0" class="empty">
              暂无调用栈
            </div>
          </div>
        </div>
        
        <div class="section">
          <div class="section-header" @click="toggleSection('variables')">
            <NIcon 
              :component="sections.variables ? ChevronDownIcon : ChevronRightIcon" 
              :size="12" 
            />
            <span>变量</span>
          </div>
          <div v-if="sections.variables" class="section-content">
            <div 
              v-for="(value, name) in variables" 
              :key="name" 
              class="variable-item"
            >
              <span class="var-name">{{ name }}</span>
              <span class="var-value">{{ value }}</span>
            </div>
            <div v-if="Object.keys(variables).length === 0" class="empty">
              暂无变量
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="isDebugging" class="debug-output">
        <div class="output-header">调试输出</div>
        <div class="output-content">
          <div 
            v-for="(log, index) in debugLogs" 
            :key="index" 
            class="log-item"
            :class="log.type"
          >
            <span class="log-time">{{ log.time }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { 
  Bug, Eye, EyeOff, Play, Square, ArrowRight, 
  ArrowDown, ChevronRight, ChevronDown, Circle, CircleDot,
  Plus, X
} from '@vicons/ionicons5'

const BugIcon = { render: () => h(Bug) }
const EyeIcon = { render: () => h(Eye) }
const EyeOffIcon = { render: () => h(EyeOff) }
const PlayIcon = { render: () => h(Play) }
const SquareIcon = { render: () => h(Square) }
const StepOverIcon = { render: () => h(ArrowRight) }
const StepIntoIcon = { render: () => h(ArrowDown) }
const StepOutIcon = { render: () => h(ArrowRight) }
const ChevronRightIcon = { render: () => h(ChevronRight) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const CircleIcon = { render: () => h(Circle) }
const CircleDotIcon = { render: () => h(CircleDot) }
const PlusIcon = { render: () => h(Plus) }
const XIcon = { render: () => h(X) }

const isDebugging = ref(false)
const toggleBreakpointsActive = ref(true)
const sections = reactive({
  breakpoints: true,
  watch: true,
  callstack: true,
  variables: true
})

const breakpoints = ref([
  { id: 1, file: 'main.py', line: 15, disabled: false },
  { id: 2, file: 'utils.py', line: 8, disabled: true },
])

const watchExpressions = ref([
  { expression: 'result', value: '100' },
  { expression: 'name', value: '"World"' },
])

const callStack = ref([
  { function: 'main()', file: 'main.py', line: 20 },
  { function: 'calculate_sum()', file: 'main.py', line: 15 },
])

const variables = ref({
  'name': '"World"',
  'i': '5',
  'result': '100',
  'total': '5050',
})

const debugLogs = ref([
  { time: '14:32:15', type: 'info', message: 'Starting debugger...' },
  { time: '14:32:16', type: 'break', message: 'Breakpoint hit at main.py:15' },
])

function toggleSection(section) {
  sections[section] = !sections[section]
}

function startDebug() {
  isDebugging.value = !isDebugging.value
  if (isDebugging.value) {
    debugLogs.value.push({
      time: new Date().toLocaleTimeString(),
      type: 'info',
      message: 'Debugger started'
    })
  } else {
    debugLogs.value.push({
      time: new Date().toLocaleTimeString(),
      type: 'info',
      message: 'Debugger stopped'
    })
  }
}

function stepOver() {
  debugLogs.value.push({
    time: new Date().toLocaleTimeString(),
    type: 'step',
    message: 'Step over'
  })
}

function stepInto() {
  debugLogs.value.push({
    time: new Date().toLocaleTimeString(),
    type: 'step',
    message: 'Step into'
  })
}

function stepOut() {
  debugLogs.value.push({
    time: new Date().toLocaleTimeString(),
    type: 'step',
    message: 'Step out'
  })
}

function continueDebug() {
  debugLogs.value.push({
    time: new Date().toLocaleTimeString(),
    type: 'info',
    message: 'Continue execution'
  })
}

function toggleBreakpoints() {
  toggleBreakpointsActive.value = !toggleBreakpointsActive.value
}

function toggleBreakpoint(bp) {
  bp.disabled = !bp.disabled
}

function removeBreakpoint(bp) {
  const index = breakpoints.value.findIndex(b => b.id === bp.id)
  if (index !== -1) {
    breakpoints.value.splice(index, 1)
  }
}

function addWatchExpression() {
  watchExpressions.value.push({ expression: '', value: '' })
}

function updateWatchExpression(index, event) {
  watchExpressions.value[index].expression = event.target.value
}

function removeWatchExpression(index) {
  watchExpressions.value.splice(index, 1)
}
</script>

<style scoped>
.debug-panel {
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

.header-right {
  display: flex;
  gap: 4px;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.debug-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.debug-toolbar button {
  flex: 1;
}

.debug-sections {
  margin-bottom: 16px;
}

.section {
  margin-bottom: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: 10px;
}

.section-content {
  padding-left: 16px;
}

.breakpoint-item, .watch-item, .stack-item, .variable-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  font-size: 12px;
}

.breakpoint-item.disabled {
  opacity: 0.5;
}

.bp-file, .stack-function {
  flex: 1;
  color: var(--text-primary);
}

.bp-line, .stack-location {
  color: var(--text-secondary);
}

.watch-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 12px;
}

.watch-value {
  color: var(--success-color);
}

.stack-item.active {
  background: var(--bg-hover);
}

.var-name {
  flex: 1;
  color: var(--text-primary);
}

.var-value {
  color: var(--warning-color);
}

.empty {
  padding: 8px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
}

.debug-output {
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}

.output-header {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.output-content {
  background: var(--bg-dark);
  border-radius: 4px;
  padding: 8px;
  max-height: 150px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  font-size: 12px;
}

.log-time {
  color: var(--text-secondary);
  font-family: monospace;
}

.log-message {
  color: var(--text-primary);
}

.log-item.info .log-message {
  color: var(--text-primary);
}

.log-item.break .log-message {
  color: var(--warning-color);
}

.log-item.step .log-message {
  color: var(--info-color);
}
</style>