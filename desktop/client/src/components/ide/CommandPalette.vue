<template>
  <div class="command-palette-overlay" @click="$emit('close')">
    <div class="command-palette" @click.stop>
      <div class="palette-header">
        <NIcon :component="SearchIcon" :size="18" />
        <input 
          v-model="searchQuery" 
          class="palette-input" 
          placeholder="输入命令..."
          autofocus
          @keydown.escape="$emit('close')"
        />
      </div>
      
      <div class="palette-results">
        <div 
          v-for="(cmd, idx) in filteredCommands" 
          :key="cmd.id"
          class="command-item"
          :class="{ selected: selectedIndex === idx }"
          @click="executeCommand(cmd)"
          @mouseenter="selectedIndex = idx"
        >
          <NIcon :component="cmd.icon" :size="16" />
          <div class="command-info">
            <span class="command-name">{{ cmd.name }}</span>
            <span class="command-category">{{ cmd.category }}</span>
          </div>
          <span v-if="cmd.shortcut" class="command-shortcut">{{ cmd.shortcut }}</span>
        </div>
        
        <div v-if="filteredCommands.length === 0" class="empty-results">
          没有找到匹配的命令
        </div>
      </div>
      
      <div class="palette-footer">
        <span>↑↓ 导航</span>
        <span>↵ 执行</span>
        <span>Esc 关闭</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NIcon } from 'naive-ui'
import { 
  Search, FilePlus, FolderOpen, Save, Code, Eye, 
  GitBranch, Bug, Terminal, Settings, HelpCircle
} from '@vicons/ionicons5'

const SearchIcon = { render: () => h(Search) }

const searchQuery = ref('')
const selectedIndex = ref(0)

const commands = ref([
  { id: 1, name: '新建文件', category: '文件', icon: { render: () => h(FilePlus) }, shortcut: 'Ctrl+N' },
  { id: 2, name: '打开文件...', category: '文件', icon: { render: () => h(FolderOpen) }, shortcut: 'Ctrl+O' },
  { id: 3, name: '保存工作区', category: '文件', icon: { render: () => h(Save) } },
  { id: 4, name: '格式化文档', category: '编辑', icon: { render: () => h(Code) }, shortcut: 'Ctrl+Shift+F' },
  { id: 5, name: '转到符号...', category: '编辑', icon: { render: () => h(Eye) }, shortcut: 'Ctrl+Shift+O' },
  { id: 6, name: '切换侧边栏', category: '视图', icon: { render: () => h(Eye) }, shortcut: 'Ctrl+B' },
  { id: 7, name: '在文件中查找', category: '搜索', icon: { render: () => h(Search) }, shortcut: 'Ctrl+F' },
  { id: 8, name: '提交', category: 'Git', icon: { render: () => h(GitBranch) } },
  { id: 9, name: '开始调试', category: '调试', icon: { render: () => h(Bug) }, shortcut: 'F5' },
  { id: 10, name: '新建终端', category: '终端', icon: { render: () => h(Terminal) }, shortcut: 'Ctrl+`' },
  { id: 11, name: '打开设置', category: '首选项', icon: { render: () => h(Settings) }, shortcut: 'Ctrl+,' },
  { id: 12, name: '显示所有命令', category: '帮助', icon: { render: () => h(HelpCircle) }, shortcut: 'F1' },
])

const filteredCommands = computed(() => {
  if (!searchQuery.value) return commands.value
  const query = searchQuery.value.toLowerCase()
  return commands.value.filter(cmd => 
    cmd.name.toLowerCase().includes(query) ||
    cmd.category.toLowerCase().includes(query)
  )
})

function executeCommand(cmd) {
  console.log('Execute command:', cmd.name)
  searchQuery.value = ''
}
</script>

<style scoped>
.command-palette-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 20vh;
  z-index: 1000;
}

.command-palette {
  width: 600px;
  background: var(--bg-card);
  border-radius: 8px;
  overflow: hidden;
}

.palette-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
}

.palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 14px;
}

.palette-results {
  max-height: 400px;
  overflow-y: auto;
}

.command-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
}

.command-item:hover, .command-item.selected {
  background: var(--bg-hover);
}

.command-info {
  flex: 1;
}

.command-name {
  display: block;
}

.command-category {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
}

.command-shortcut {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
}

.empty-results {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
}

.palette-footer {
  display: flex;
  justify-content: space-around;
  padding: 8px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
}
</style>