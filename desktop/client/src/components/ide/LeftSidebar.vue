<template>
  <aside class="left-sidebar">
    <div class="sidebar-tabs">
      <NButton text @click="activeTab = 'explorer'" :class="{ active: activeTab === 'explorer' }">
        <NIcon :component="ExplorerIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'search'" :class="{ active: activeTab === 'search' }">
        <NIcon :component="SearchIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'git'" :class="{ active: activeTab === 'git' }">
        <NIcon :component="GitIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'extensions'" :class="{ active: activeTab === 'extensions' }">
        <NIcon :component="ExtensionIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'outline'" :class="{ active: activeTab === 'outline' }">
        <NIcon :component="OutlineIcon" :size="18" />
      </NButton>
    </div>
    
    <div class="sidebar-content">
      <!-- 文件资源管理器 -->
      <div v-if="activeTab === 'explorer'" class="panel">
        <div class="panel-header">
          <span>资源管理器</span>
          <div class="panel-actions">
            <NButton text size="small" @click="newFile">
              <NIcon :component="NewFileIcon" :size="14" />
            </NButton>
            <NButton text size="small" @click="newFolder">
              <NIcon :component="NewFolderIcon" :size="14" />
            </NButton>
            <NButton text size="small" @click="refreshExplorer">
              <NIcon :component="RefreshIcon" :size="14" />
            </NButton>
          </div>
        </div>
        <div class="explorer-tree">
          <div class="tree-item" v-for="item in fileTree" :key="item.name">
            <div class="tree-item-header" @click="toggleFolder(item)">
              <NIcon v-if="item.type === 'folder'" :component="item.expanded ? ChevronDownIcon : ChevronRightIcon" :size="14" />
              <NIcon :component="item.type === 'folder' ? FolderIcon : FileIcon" :size="16" />
              <span>{{ item.name }}</span>
              <span v-if="item.modified" class="modified-dot"></span>
            </div>
            <div v-if="item.type === 'folder' && item.expanded" class="tree-children">
              <div v-for="child in item.children" :key="child.name" class="tree-item">
                <NIcon :component="child.type === 'folder' ? FolderIcon : FileIcon" :size="16" />
                <span>{{ child.name }}</span>
                <span v-if="child.modified" class="modified-dot"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 搜索面板 -->
      <div v-if="activeTab === 'search'" class="panel">
        <div class="search-input-wrapper">
          <NInput v-model="searchQuery" placeholder="搜索..." />
        </div>
        <div class="search-options">
          <label><NCheckbox v-model="searchOptions.caseSensitive" /> 区分大小写</label>
          <label><NCheckbox v-model="searchOptions.wholeWord" /> 全字匹配</label>
          <label><NCheckbox v-model="searchOptions.regex" /> 使用正则</label>
        </div>
        <div class="replace-input-wrapper">
          <NInput v-model="replaceQuery" placeholder="替换为..." />
        </div>
        <div class="search-scope">
          <label><NRadio v-model="searchScope" value="current" /> 当前文件</label>
          <label><NRadio v-model="searchScope" value="project" /> 整个项目</label>
        </div>
        <div class="search-results">
          <div v-for="result in searchResults" :key="result.file">
            <div class="result-header">{{ result.file }} ({{ result.count }}处匹配)</div>
            <div v-for="(match, idx) in result.matches" :key="idx" class="result-item">
              <span class="line-number">L{{ match.line }}</span>
              <span class="line-content">{{ match.content }}</span>
            </div>
          </div>
        </div>
        <div class="search-actions">
          <NButton text size="small">全部替换</NButton>
          <NButton text size="small">替换选中</NButton>
        </div>
      </div>
      
      <!-- Git面板 -->
      <div v-if="activeTab === 'git'" class="panel">
        <div class="git-header">
          <span>{{ gitBranch }} *{{ gitChanges }} ↑{{ gitAhead }}</span>
        </div>
        <div class="git-section">
          <div class="section-title">更改({{ gitChanges }})</div>
          <div v-for="change in gitChangesList" :key="change.file" class="git-change">
            <NIcon :component="change.type === 'added' ? PlusIcon : change.type === 'deleted' ? MinusIcon : GitModifiedIcon" :size="14" />
            <span>{{ change.file }}</span>
          </div>
        </div>
        <div class="git-staging">
          <NInput v-model="commitMessage" placeholder="提交信息..." />
          <div class="git-actions">
            <NButton type="primary" size="small">提交</NButton>
            <NButton text size="small">推送</NButton>
            <NButton text size="small">拉取</NButton>
          </div>
        </div>
        <div class="git-branches">
          <div class="section-title">分支</div>
          <div v-for="branch in gitBranches" :key="branch.name" class="git-branch" :class="{ active: branch.active }">
            <NIcon :component="branch.active ? GitBranchIcon : CircleIcon" :size="14" />
            <span>{{ branch.name }}</span>
          </div>
        </div>
      </div>
      
      <!-- 扩展面板 -->
      <div v-if="activeTab === 'extensions'" class="panel">
        <div class="search-input-wrapper">
          <NInput v-model="extSearchQuery" placeholder="搜索扩展..." />
        </div>
        <div class="ext-section">
          <div class="section-title">已安装({{ installedExtensions.length }})</div>
          <div v-for="ext in installedExtensions" :key="ext.name" class="ext-item">
            <NIcon :component="ExtensionIcon" :size="20" />
            <div class="ext-info">
              <span class="ext-name">{{ ext.name }}</span>
              <span class="ext-version">{{ ext.version }}</span>
            </div>
            <NButton text size="small" v-if="ext.enabled">禁用</NButton>
            <NButton text size="small" v-else>启用</NButton>
          </div>
        </div>
        <div class="ext-section">
          <div class="section-title">推荐扩展</div>
          <div v-for="ext in recommendedExtensions" :key="ext.name" class="ext-item">
            <NIcon :component="ExtensionIcon" :size="20" />
            <div class="ext-info">
              <span class="ext-name">{{ ext.name }}</span>
              <span class="ext-desc">{{ ext.description }}</span>
            </div>
            <NButton type="primary" size="small">安装</NButton>
          </div>
        </div>
      </div>
      
      <!-- 大纲视图 -->
      <div v-if="activeTab === 'outline'" class="panel">
        <div class="outline-section">
          <div class="outline-item header">导入</div>
          <div class="outline-item function">
            <NIcon :component="FunctionIcon" :size="14" />
            <span>main()</span>
          </div>
          <div class="outline-item function">
            <NIcon :component="FunctionIcon" :size="14" />
            <span>helper()</span>
          </div>
          <div class="outline-item header">类</div>
          <div class="outline-item class">
            <NIcon :component="ClassIcon" :size="14" />
            <span>User</span>
          </div>
          <div class="outline-item header">主程序块</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { NButton, NIcon, NInput, NCheckbox, NRadio } from 'naive-ui'
import { 
  FolderOpen, Search, GitBranch, Puzzle, List,
  FilePlus, FolderPlus, RefreshCw, ChevronRight, ChevronDown,
  Folder, File, Plus, Minus, Circle
} from '@vicons/ionicons5'

const ExplorerIcon = { render: () => h(FolderOpen) }
const SearchIcon = { render: () => h(Search) }
const GitIcon = { render: () => h(GitBranch) }
const ExtensionIcon = { render: () => h(Puzzle) }
const OutlineIcon = { render: () => h(List) }
const NewFileIcon = { render: () => h(FilePlus) }
const NewFolderIcon = { render: () => h(FolderPlus) }
const RefreshIcon = { render: () => h(RefreshCw) }
const ChevronRightIcon = { render: () => h(ChevronRight) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const FolderIcon = { render: () => h(Folder) }
const FileIcon = { render: () => h(File) }
const PlusIcon = { render: () => h(Plus) }
const MinusIcon = { render: () => h(Minus) }
const CircleIcon = { render: () => h(Circle) }
const GitBranchIcon = { render: () => h(GitBranch) }
const GitModifiedIcon = { render: () => h(File) }
const FunctionIcon = { render: () => h(File) }
const ClassIcon = { render: () => h(Folder) }

const activeTab = ref('explorer')

const fileTree = ref([
  { name: 'src', type: 'folder', expanded: true, children: [
    { name: 'main.py', type: 'file', modified: true },
    { name: 'utils.py', type: 'file' },
    { name: 'components', type: 'folder', children: [] }
  ]},
  { name: 'tests', type: 'folder', expanded: false, children: [] },
  { name: 'docs', type: 'folder', expanded: false, children: [] },
  { name: 'requirements.txt', type: 'file' },
  { name: 'README.md', type: 'file' },
])

const searchQuery = ref('')
const replaceQuery = ref('')
const searchOptions = reactive({
  caseSensitive: false,
  wholeWord: false,
  regex: false
})
const searchScope = ref('project')
const searchResults = ref([
  { file: 'main.py', count: 2, matches: [
    { line: 10, content: 'print("Hello World")' },
    { line: 25, content: 'console.log("Hello")' }
  ]}
])

const gitBranch = ref('main')
const gitChanges = ref(3)
const gitAhead = ref(2)
const commitMessage = ref('')
const gitChangesList = ref([
  { file: 'main.py', type: 'modified' },
  { file: 'README.md', type: 'modified' },
  { file: 'new_file.py', type: 'added' }
])
const gitBranches = ref([
  { name: 'main', active: true },
  { name: 'feature/new', active: false },
  { name: 'hotfix/bug', active: false }
])

const extSearchQuery = ref('')
const installedExtensions = ref([
  { name: 'Python扩展', version: '1.2.3', enabled: true },
  { name: 'GitLens', version: '14.0.0', enabled: true },
  { name: 'Prettier', version: '1.0.0', enabled: true },
  { name: 'ESLint', version: '2.0.0', enabled: true },
  { name: 'Docker', version: '1.5.0', enabled: true }
])
const recommendedExtensions = ref([
  { name: 'GitHub Copilot', description: 'AI代码补全' },
  { name: 'Material Icon Theme', description: '图标主题' },
  { name: 'Bracket Pair Colorizer', description: '括号高亮' }
])

function toggleFolder(item) {
  if (item.type === 'folder') {
    item.expanded = !item.expanded
  }
}

function newFile() { console.log('New file') }
function newFolder() { console.log('New folder') }
function refreshExplorer() { console.log('Refresh') }
</script>

<style scoped>
.left-sidebar {
  width: 250px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-tabs {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-tabs .active {
  background: var(--bg-hover);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
}

.panel {
  padding: 8px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-weight: 600;
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.tree-item {
  padding: 2px 0;
}

.tree-item-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  cursor: pointer;
}

.tree-item-header:hover {
  background: var(--bg-hover);
}

.tree-children {
  padding-left: 16px;
}

.modified-dot {
  width: 8px;
  height: 8px;
  background: var(--warning-color);
  border-radius: 50%;
  margin-left: auto;
}

.search-input-wrapper, .replace-input-wrapper {
  margin-bottom: 8px;
}

.search-options, .search-scope {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.search-results {
  margin-bottom: 8px;
}

.result-header {
  font-weight: 600;
  margin: 8px 0 4px;
}

.result-item {
  display: flex;
  gap: 8px;
  padding: 4px;
}

.line-number {
  color: var(--text-secondary);
  font-family: monospace;
}

.line-content {
  font-family: monospace;
}

.search-actions {
  display: flex;
  gap: 8px;
}

.git-header {
  padding: 8px;
  background: var(--bg-hover);
  font-weight: 600;
}

.git-section, .git-staging, .git-branches {
  padding: 8px 0;
}

.section-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.git-change {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}

.git-staging {
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.git-staging input {
  margin-bottom: 8px;
}

.git-actions {
  display: flex;
  gap: 8px;
}

.git-branch {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}

.git-branch.active {
  background: var(--bg-hover);
}

.ext-section {
  margin-bottom: 16px;
}

.ext-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
}

.ext-info {
  flex: 1;
}

.ext-name {
  display: block;
}

.ext-version, .ext-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
}

.outline-section {
  padding: 8px;
}

.outline-item {
  padding: 4px 8px;
  cursor: pointer;
}

.outline-item:hover {
  background: var(--bg-hover);
}

.outline-item.header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.outline-item.function, .outline-item.class {
  padding-left: 16px;
}
</style>