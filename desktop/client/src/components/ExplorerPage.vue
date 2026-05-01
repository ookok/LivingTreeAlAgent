<template>
  <div class="explorer-container">
    <div class="explorer-sidebar">
      <div class="sidebar-section">
        <div class="section-header">
          <NIcon :component="FolderIcon" :size="16" />
          <span>文件</span>
        </div>
        <div 
          v-for="item in fileTree" 
          :key="item.id" 
          class="tree-item"
          :class="{ active: selectedItem === item.id, expanded: item.expanded }"
          @click="toggleItem(item)"
        >
          <NButton text size="small" v-if="item.children?.length" @click.stop="item.expanded = !item.expanded">
            <NIcon :component="item.expanded ? ChevronDownIcon : ChevronRightIcon" :size="14" />
          </NButton>
          <span v-else class="empty-icon"></span>
          <NIcon :component="item.type === 'folder' ? FolderIcon : FileIcon" :size="16" />
          <span class="item-name">{{ item.name }}</span>
        </div>
      </div>
      
      <div class="sidebar-section">
        <div class="section-header">
          <NIcon :component="StarIcon" :size="16" />
          <span>收藏</span>
        </div>
        <div 
          v-for="item in favorites" 
          :key="item.id" 
          class="tree-item"
          :class="{ active: selectedItem === item.id }"
          @click="selectItem(item)"
        >
          <NIcon :component="item.type === 'folder' ? FolderIcon : FileIcon" :size="16" />
          <span class="item-name">{{ item.name }}</span>
        </div>
      </div>
    </div>
    
    <div class="explorer-main">
      <div v-if="selectedItem" class="file-preview">
        <div class="preview-header">
          <span>{{ selectedFileName }}</span>
          <div class="preview-actions">
            <NButton text size="small" @click="openInIde">
              <NIcon :component="CodeIcon" :size="16" />
              在IDE中打开
            </NButton>
          </div>
        </div>
        <div class="preview-content">
          <pre class="file-content">{{ selectedFileContent }}</pre>
        </div>
      </div>
      <div v-else class="empty-preview">
        <NIcon :component="FolderOpenIcon" :size="64" />
        <h3>选择文件查看内容</h3>
        <p>从左侧选择一个文件来预览其内容</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { FolderOpen, Folder, File, Star, ChevronDown, ChevronRight, Code } from '@vicons/ionicons5'

const FolderIcon = { render: () => h(Folder) }
const FileIcon = { render: () => h(File) }
const StarIcon = { render: () => h(Star) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const ChevronRightIcon = { render: () => h(ChevronRight) }
const CodeIcon = { render: () => h(Code) }
const FolderOpenIcon = { render: () => h(FolderOpen) }

const fileTree = ref([
  {
    id: 'root',
    name: 'Workspace',
    type: 'folder',
    expanded: true,
    children: [
      {
        id: 'src',
        name: 'src',
        type: 'folder',
        expanded: true,
        children: [
          { id: 'app.js', name: 'app.js', type: 'file', content: 'console.log("Hello World");\n\nfunction greet(name) {\n  return `Hello, ${name}!`;\n}' },
          { id: 'main.css', name: 'main.css', type: 'file', content: '.container {\n  display: flex;\n  justify-content: center;\n  align-items: center;\n  height: 100vh;\n}' },
          {
            id: 'components',
            name: 'components',
            type: 'folder',
            expanded: false,
            children: [
              { id: 'Header.vue', name: 'Header.vue', type: 'file', content: '<template>\n  <header class="header">\n    <h1>Welcome</h1>\n  </header>\n</template>' },
              { id: 'Sidebar.vue', name: 'Sidebar.vue', type: 'file', content: '<template>\n  <aside class="sidebar">\n    <nav>Navigation</nav>\n  </aside>\n</template>' }
            ]
          }
        ]
      },
      { id: 'README.md', name: 'README.md', type: 'file', content: '# LivingTree AI\n\nAn intelligent AI assistant platform.\n\n## Features\n\n- AI Chat\n- Code Editor\n- File Management' },
      { id: 'package.json', name: 'package.json', type: 'file', content: '{\n  "name": "livingtree-ai",\n  "version": "1.0.0",\n  "description": "AI Assistant Platform",\n  "scripts": {\n    "start": "npm run dev",\n    "build": "npm run build"\n  }\n}' }
    ]
  }
])

const favorites = ref([
  { id: 'fav1', name: 'app.js', type: 'file', content: 'console.log("Hello World");' },
  { id: 'fav2', name: 'README.md', type: 'file', content: '# LivingTree AI' }
])

const selectedItem = ref(null)

const selectedFileName = computed(() => {
  const item = findItem(selectedItem.value)
  return item?.name || ''
})

const selectedFileContent = computed(() => {
  const item = findItem(selectedItem.value)
  return item?.content || ''
})

function findItem(id, tree = fileTree.value) {
  for (const item of tree) {
    if (item.id === id) return item
    if (item.children) {
      const found = findItem(id, item.children)
      if (found) return found
    }
  }
  for (const item of favorites.value) {
    if (item.id === id) return item
  }
  return null
}

function toggleItem(item) {
  selectItem(item)
}

function selectItem(item) {
  selectedItem.value = item.id
}

function openInIde() {
  console.log('Open in IDE:', selectedItem.value)
}
</script>

<style scoped>
.explorer-container {
  display: flex;
  height: 100%;
}

.explorer-sidebar {
  width: 280px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
}

.sidebar-section {
  padding: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tree-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.tree-item:hover {
  background: var(--bg-hover);
}

.tree-item.active {
  background: var(--primary-color);
}

.empty-icon {
  width: 20px;
}

.item-name {
  font-size: 13px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.explorer-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-dark);
}

.file-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.preview-content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

.file-content {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.empty-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-preview h3 {
  margin: 16px 0 8px;
  color: var(--text-primary);
}
</style>