<template>
  <div class="ide-container">
    <!-- 顶部工具栏 -->
    <div class="ide-toolbar">
      <div class="toolbar-left">
        <NButton text size="small" @click="toggleSidebar">
          <NIcon :component="sidebarOpen ? ChevronLeftIcon : ChevronRightIcon" :size="16" />
        </NButton>
        <div class="project-name">LivingTree AI</div>
      </div>
      
      <div class="toolbar-center">
        <NButton text size="small" @click="openFile">
          <NIcon :component="FolderOpenIcon" :size="14" />
          打开文件
        </NButton>
        <NButton text size="small" @click="saveFile">
          <NIcon :component="SaveIcon" :size="14" />
          保存
        </NButton>
        <NButton text size="small" @click="saveAll">
          <NIcon :component="SaveAllIcon" :size="14" />
          全部保存
        </NButton>
        <div class="toolbar-divider"></div>
        <NButton text size="small" @click="toggleSearch">
          <NIcon :component="SearchIcon" :size="14" />
          搜索
        </NButton>
        <NButton text size="small" @click="toggleGit">
          <NIcon :component="GitIcon" :size="14" />
          Git
        </NButton>
        <NButton text size="small" @click="toggleDebug">
          <NIcon :component="DebugIcon" :size="14" />
          调试
        </NButton>
        <NButton text size="small" @click="toggleTerminal">
          <NIcon :component="TerminalIcon" :size="14" />
          终端
        </NButton>
        <NButton text size="small" @click="toggleAI">
          <NIcon :component="AiIcon" :size="14" />
          AI
        </NButton>
      </div>
      
      <div class="toolbar-right">
        <NButton text size="small" @click="zoomOut">
          <NIcon :component="ZoomOutIcon" :size="14" />
        </NButton>
        <span class="zoom-level">100%</span>
        <NButton text size="small" @click="zoomIn">
          <NIcon :component="ZoomInIcon" :size="14" />
        </NButton>
        <NButton text size="small" @click="toggleWordWrap">
          <NIcon :component="WrapIcon" :size="14" />
        </NButton>
        <NButton text size="small" @click="toggleTheme">
          <NIcon :component="isDark ? MoonIcon : SunIcon" :size="14" />
        </NButton>
      </div>
    </div>
    
    <div class="ide-main">
      <!-- 左侧边栏 -->
      <div class="sidebar" :class="{ collapsed: !sidebarOpen }">
        <div class="sidebar-tabs">
          <NButton 
            text 
            size="small" 
            :class="{ active: activeSidebarTab === 'explorer' }"
            @click="activeSidebarTab = 'explorer'"
          >
            <NIcon :component="ExplorerIcon" :size="18" />
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeSidebarTab === 'search' }"
            @click="activeSidebarTab = 'search'"
          >
            <NIcon :component="SearchIcon" :size="18" />
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeSidebarTab === 'git' }"
            @click="activeSidebarTab = 'git'"
          >
            <NIcon :component="GitIcon" :size="18" />
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeSidebarTab === 'debug' }"
            @click="activeSidebarTab = 'debug'"
          >
            <NIcon :component="DebugIcon" :size="18" />
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeSidebarTab === 'ai' }"
            @click="activeSidebarTab = 'ai'"
          >
            <NIcon :component="AiIcon" :size="18" />
          </NButton>
        </div>
        
        <div class="sidebar-content">
          <FileExplorer 
            v-show="activeSidebarTab === 'explorer'" 
            @open-file="handleOpenFile"
          />
          <SearchPanel 
            v-show="activeSidebarTab === 'search'" 
            @close="activeSidebarTab = 'explorer'"
          />
          <GitPanel 
            v-show="activeSidebarTab === 'git'" 
          />
          <DebugPanel 
            v-show="activeSidebarTab === 'debug'" 
          />
          <AiPanel 
            v-show="activeSidebarTab === 'ai'" 
          />
        </div>
      </div>
      
      <!-- 主编辑区 -->
      <div class="editor-main">
        <EditorArea ref="editorArea" />
      </div>
      
      <!-- 底部面板 -->
      <div class="bottom-panel" :class="{ hidden: !bottomPanelOpen }">
        <div class="panel-tabs">
          <NButton 
            text 
            size="small" 
            :class="{ active: activeBottomTab === 'terminal' }"
            @click="activeBottomTab = 'terminal'"
          >
            <NIcon :component="TerminalIcon" :size="14" />
            终端
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeBottomTab === 'output' }"
            @click="activeBottomTab = 'output'"
          >
            <NIcon :component="OutputIcon" :size="14" />
            输出
          </NButton>
          <NButton 
            text 
            size="small" 
            :class="{ active: activeBottomTab === 'problems' }"
            @click="activeBottomTab = 'problems'"
          >
            <NIcon :component="AlertIcon" :size="14" />
            问题
          </NButton>
          <NButton text size="small" @click="bottomPanelOpen = false">
            <NIcon :component="XIcon" :size="14" />
          </NButton>
        </div>
        
        <div class="panel-content">
          <Terminal 
            v-show="activeBottomTab === 'terminal'" 
            @close="bottomPanelOpen = false"
          />
          <div v-show="activeBottomTab === 'output'" class="output-panel">
            <div class="output-header">构建输出</div>
            <div class="output-content">
              <div class="output-line">> Building project...</div>
              <div class="output-line success">> Build completed successfully</div>
              <div class="output-line">> No errors found</div>
            </div>
          </div>
          <div v-show="activeBottomTab === 'problems'" class="problems-panel">
            <div class="problem-item error">
              <NIcon :component="AlertIcon" :size="14" />
              <span>main.py:15 - 未定义的变量 'result'</span>
            </div>
            <div class="problem-item warning">
              <NIcon :component="AlertCircleIcon" :size="14" />
              <span>utils.py:8 - 未使用的导入</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 状态栏 -->
    <div class="status-bar">
      <div class="status-left">
        <span class="status-item">Python</span>
        <span class="status-item">UTF-8</span>
        <span class="status-item">行 1, 列 1</span>
      </div>
      <div class="status-right">
        <span class="status-item">Git: main</span>
        <span class="status-item">LSP: 已连接</span>
        <span class="status-item">Ready</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import {
  ChevronLeft, ChevronRight, FolderOpen, Save, SaveAll,
  Search, GitCommit, Bug, Terminal, Brain, ZoomOut, ZoomIn,
  Maximize, Moon, Sun, FileText, AlertCircle, X
} from '@vicons/ionicons5'

const ChevronLeftIcon = { render: () => h(ChevronLeft) }
const ChevronRightIcon = { render: () => h(ChevronRight) }
const FolderOpenIcon = { render: () => h(FolderOpen) }
const SaveIcon = { render: () => h(Save) }
const SaveAllIcon = { render: () => h(SaveAll) }
const SearchIcon = { render: () => h(Search) }
const GitIcon = { render: () => h(GitCommit) }
const DebugIcon = { render: () => h(Bug) }
const TerminalIcon = { render: () => h(Terminal) }
const AiIcon = { render: () => h(Brain) }
const ZoomOutIcon = { render: () => h(ZoomOut) }
const ZoomInIcon = { render: () => h(ZoomIn) }
const WrapIcon = { render: () => h(Maximize) }
const MoonIcon = { render: () => h(Moon) }
const SunIcon = { render: () => h(Sun) }
const ExplorerIcon = { render: () => h(FileText) }
const OutputIcon = { render: () => h(FileText) }
const AlertIcon = { render: () => h(AlertCircle) }
const AlertCircleIcon = { render: () => h(AlertCircle) }
const XIcon = { render: () => h(X) }

const sidebarOpen = ref(true)
const activeSidebarTab = ref('explorer')
const bottomPanelOpen = ref(true)
const activeBottomTab = ref('terminal')
const isDark = ref(true)
const editorArea = ref(null)

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function toggleSearch() {
  activeSidebarTab.value = 'search'
  sidebarOpen.value = true
}

function toggleGit() {
  activeSidebarTab.value = 'git'
  sidebarOpen.value = true
}

function toggleDebug() {
  activeSidebarTab.value = 'debug'
  sidebarOpen.value = true
}

function toggleTerminal() {
  bottomPanelOpen.value = !bottomPanelOpen.value
  if (bottomPanelOpen.value) {
    activeBottomTab.value = 'terminal'
  }
}

function toggleAI() {
  activeSidebarTab.value = 'ai'
  sidebarOpen.value = true
}

function toggleWordWrap() {
  editorArea.value?.toggleWordWrap()
}

function zoomIn() {
  editorArea.value?.zoomIn()
}

function zoomOut() {
  editorArea.value?.zoomOut()
}

function toggleTheme() {
  isDark.value = !isDark.value
  editorArea.value?.setTheme(isDark.value)
}

function openFile() {
  console.log('Open file')
}

function saveFile() {
  console.log('Save file')
}

function saveAll() {
  console.log('Save all')
}

function handleOpenFile(file) {
  console.log('Open file:', file)
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

function handleKeydown(e) {
  if (e.ctrlKey && e.key === 'b') {
    e.preventDefault()
    toggleSidebar()
  }
  if (e.ctrlKey && e.shiftKey && e.key === 'f') {
    e.preventDefault()
    toggleSearch()
  }
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault()
    toggleTerminal()
  }
  if (e.ctrlKey && e.key === '+') {
    e.preventDefault()
    zoomIn()
  }
  if (e.ctrlKey && e.key === '-') {
    e.preventDefault()
    zoomOut()
  }
}
</script>

<style scoped>
.ide-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-dark);
  color: var(--text-primary);
}

.ide-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.toolbar-left, .toolbar-center, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-left: 8px;
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--border-color);
  margin: 0 4px;
}

.zoom-level {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 50px;
  text-align: center;
}

.ide-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 280px;
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
  border-right: 1px solid var(--border-color);
}

.sidebar.collapsed {
  width: 48px;
}

.sidebar-tabs {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 4px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-tabs button {
  display: flex;
  justify-content: center;
  padding: 10px 8px;
  border-radius: 4px;
}

.sidebar-tabs button.active {
  background: var(--bg-hover);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
}

.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bottom-panel {
  height: 200px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: height 0.2s;
}

.bottom-panel.hidden {
  height: 0;
  border-top: none;
}

.panel-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-color);
}

.panel-tabs button {
  padding: 6px 12px;
  border-radius: 4px 4px 0 0;
}

.panel-tabs button.active {
  background: var(--bg-dark);
}

.panel-content {
  flex: 1;
  overflow: hidden;
}

.output-panel, .problems-panel {
  height: 100%;
  padding: 12px;
}

.output-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.output-content {
  font-family: monospace;
  font-size: 12px;
}

.output-line {
  padding: 4px 0;
  color: var(--text-primary);
}

.output-line.success {
  color: var(--success-color);
}

.problem-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  margin-bottom: 4px;
  border-radius: 4px;
}

.problem-item.error {
  background: rgba(239, 68, 68, 0.1);
}

.problem-item.warning {
  background: rgba(245, 158, 11, 0.1);
}

.status-bar {
  display: flex;
  justify-content: space-between;
  padding: 4px 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
}

.status-left, .status-right {
  display: flex;
  gap: 16px;
}

.status-item {
  padding: 0 8px;
}
</style>