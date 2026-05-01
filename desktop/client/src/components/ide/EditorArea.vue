<template>
  <div class="editor-area">
    <!-- 标签页 -->
    <div class="tabs-bar">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-item"
        :class="{ active: activeTab === tab.id, modified: tab.modified }"
        @click="switchTab(tab.id)"
      >
        <NIcon :component="getFileIcon(tab.type)" :size="16" />
        <span>{{ tab.name }}</span>
        <span v-if="tab.modified" class="modified-indicator"></span>
        <NButton text size="small" @click.stop="closeTab(tab.id)">
          <NIcon :component="CloseIcon" :size="12" />
        </NButton>
      </div>
      <div class="new-tab-btn" @click="newTab">
        <NIcon :component="PlusIcon" :size="16" />
      </div>
    </div>
    
    <!-- 编辑器主体 -->
    <div class="editor-container">
      <MonacoEditor
        v-if="currentTab"
        ref="monacoEditor"
        :model-value="currentTab.content"
        :filename="currentTab.name"
        @update:model-value="handleContentChange"
      />
    </div>
    
    <!-- 右键菜单 -->
    <div v-if="showContextMenu" class="context-menu" :style="contextMenuStyle">
      <div class="menu-item" @click="copy">复制</div>
      <div class="menu-item" @click="paste">粘贴</div>
      <div class="menu-separator"></div>
      <div class="menu-item" @click="formatDocument">格式化文档</div>
      <div class="menu-item" @click="toggleComment">切换注释</div>
      <div class="menu-separator"></div>
      <div class="menu-item" @click="goToDefinition">转到定义</div>
      <div class="menu-item" @click="findReferences">查找所有引用</div>
      <div class="menu-item" @click="rename">重命名符号</div>
      <div class="menu-separator"></div>
      <div class="menu-item" @click="aiExplain">AI 解释代码</div>
      <div class="menu-item" @click="aiGenerate">AI 生成代码</div>
      <div class="menu-separator"></div>
      <div class="menu-item" @click="runTerminal">在终端中运行</div>
      <div class="menu-item" @click="runDebug">在调试器中运行</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { File, FileCode, FileText, X, Plus } from '@vicons/ionicons5'
import MonacoEditor from './MonacoEditor.vue'

const CloseIcon = { render: () => h(X) }
const PlusIcon = { render: () => h(Plus) }

const tabs = ref([
  { id: 1, name: 'main.py', type: 'python', modified: false, content: sampleCode },
  { id: 2, name: 'utils.py', type: 'python', modified: false, content: '' },
  { id: 3, name: 'README.md', type: 'markdown', modified: false, content: '# LivingTree AI\n\nA powerful AI agent platform.' },
])

const activeTab = ref(1)
const showContextMenu = ref(false)
const contextMenuStyle = ref({ left: '0px', top: '0px' })
const monacoEditor = ref(null)

const sampleCode = `def main():
    """
    Main function - Entry point of the application
    """
    name = "World"
    print(f"Hello, {name}!")
    
    for i in range(10):
        if i % 2 == 0:
            print(f"Even: {i}")
        else:
            print(f"Odd: {i}")
    
    result = calculate_sum(1, 100)
    print(f"Sum: {result}")

def calculate_sum(start, end):
    """Calculate sum from start to end (inclusive)"""
    total = 0
    for num in range(start, end + 1):
        total += num
    return total

if __name__ == "__main__":
    main()`

const currentTab = computed(() => {
  return tabs.value.find(t => t.id === activeTab.value)
})

function getFileIcon(type) {
  if (type === 'python') return { render: () => h(FileCode) }
  if (type === 'markdown') return { render: () => h(FileText) }
  return { render: () => h(File) }
}

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

function newTab() {
  const newId = Date.now()
  tabs.value.push({
    id: newId,
    name: 'untitled.py',
    type: 'python',
    modified: false,
    content: ''
  })
  activeTab.value = newId
  nextTick(() => {
    monacoEditor.value?.focus()
  })
}

function handleContentChange(content) {
  const tab = tabs.value.find(t => t.id === activeTab.value)
  if (tab) {
    tab.content = content
    tab.modified = true
  }
}

function saveFile() {
  const tab = tabs.value.find(t => t.id === activeTab.value)
  if (tab) {
    tab.modified = false
  }
}

function formatDocument() {
  monacoEditor.value?.formatDocument()
  showContextMenu.value = false
}

function toggleComment() {
  monacoEditor.value?.toggleComment()
  showContextMenu.value = false
}

function copy() { showContextMenu.value = false }
function paste() { showContextMenu.value = false }
function goToDefinition() { showContextMenu.value = false }
function findReferences() { showContextMenu.value = false }
function rename() { showContextMenu.value = false }
function aiExplain() { showContextMenu.value = false }
function aiGenerate() { showContextMenu.value = false }
function runTerminal() { showContextMenu.value = false }
function runDebug() { showContextMenu.value = false }

onMounted(() => {
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 's') {
      e.preventDefault()
      saveFile()
    }
  })
  
  document.addEventListener('contextmenu', (e) => {
    e.preventDefault()
    contextMenuStyle.value = {
      left: e.clientX + 'px',
      top: e.clientY + 'px'
    }
    showContextMenu.value = true
  })
  
  document.addEventListener('click', () => {
    showContextMenu.value = false
  })
})
</script>

<style scoped>
.editor-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-dark);
  overflow: hidden;
}

.tabs-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px 4px 0 0;
  background: var(--bg-hover);
  transition: background 0.2s;
}

.tab-item.active {
  background: var(--bg-dark);
}

.tab-item.modified .modified-indicator {
  width: 8px;
  height: 8px;
  background: var(--warning-color);
  border-radius: 50%;
}

.new-tab-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 28px;
  cursor: pointer;
  border-radius: 4px;
}

.new-tab-btn:hover {
  background: var(--bg-hover);
}

.editor-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.context-menu {
  position: fixed;
  min-width: 180px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 4px;
  z-index: 1000;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.menu-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-separator {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}
</style>