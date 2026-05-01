<template>
  <div class="git-panel">
    <div class="panel-header">
      <NIcon :component="GitIcon" :size="14" />
      <span>源代码管理</span>
    </div>
    
    <div class="panel-content">
      <div v-if="gitStatus" class="git-status">
        <div class="branch-info">
          <NIcon :component="GitBranchIcon" :size="16" />
          <span class="branch-name">{{ gitStatus.branch }}</span>
          <NButton text size="tiny" @click="showBranchMenu = !showBranchMenu">
            <NIcon :component="ChevronDownIcon" :size="12" />
          </NButton>
        </div>
        
        <div class="status-summary">
          <span class="stat added">{{ gitStatus.added }} 已添加</span>
          <span class="stat modified">{{ gitStatus.modified }} 已修改</span>
          <span class="stat deleted">{{ gitStatus.deleted }} 已删除</span>
        </div>
      </div>
      
      <div v-else class="no-repo">
        <NIcon :component="GitIcon" :size="24" />
        <p>未检测到 Git 仓库</p>
        <NButton text @click="initRepo">初始化仓库</NButton>
      </div>
      
      <div v-if="gitStatus" class="staged-files">
        <div class="section-title">已暂存</div>
        <div 
          v-for="file in stagedFiles" 
          :key="file.path" 
          class="file-item"
        >
          <NIcon :component="AddedIcon" :size="14" class="status-icon added" />
          <span class="file-path">{{ file.path }}</span>
          <NButton text size="tiny" @click="unstageFile(file)">
            <NIcon :component="XIcon" :size="12" />
          </NButton>
        </div>
        <div v-if="stagedFiles.length === 0" class="empty-list">
          暂无暂存文件
        </div>
      </div>
      
      <div v-if="gitStatus" class="unstaged-files">
        <div class="section-title">未暂存</div>
        <div 
          v-for="file in unstagedFiles" 
          :key="file.path" 
          class="file-item"
        >
          <NIcon 
            :component="getFileStatusIcon(file.status)" 
            :size="14" 
            class="status-icon"
            :class="file.status"
          />
          <span class="file-path">{{ file.path }}</span>
          <NButton text size="tiny" @click="stageFile(file)">
            <NIcon :component="PlusIcon" :size="12" />
          </NButton>
        </div>
        <div v-if="unstagedFiles.length === 0" class="empty-list">
          暂无未暂存文件
        </div>
      </div>
      
      <div v-if="gitStatus" class="git-actions">
        <div class="commit-input">
          <input
            v-model="commitMessage"
            class="commit-message"
            placeholder="提交信息..."
            @keydown.enter="commit"
          />
        </div>
        <div class="action-buttons">
          <NButton type="primary" @click="commit">提交</NButton>
          <NButton text @click="pull">拉取</NButton>
          <NButton text @click="push">推送</NButton>
        </div>
      </div>
    </div>
    
    <div v-if="showBranchMenu" class="branch-menu">
      <div 
        v-for="branch in branches" 
        :key="branch" 
        class="branch-item"
        :class="{ active: branch === gitStatus?.branch }"
        @click="checkoutBranch(branch)"
      >
        <NIcon :component="GitBranchIcon" :size="14" />
        <span>{{ branch }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { 
  GitBranch, ChevronDown, Plus, X, GitCommit, 
  ArrowUpCircle, ArrowDownCircle, AlertCircle, Trash2
} from '@vicons/ionicons5'

const GitIcon = { render: () => h(GitCommit) }
const GitBranchIcon = { render: () => h(GitBranch) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const PlusIcon = { render: () => h(Plus) }
const XIcon = { render: () => h(X) }
const AddedIcon = { render: () => h(Plus) }
const ModifiedIcon = { render: () => h(AlertCircle) }
const DeletedIcon = { render: () => h(Trash2) }
const PullIcon = { render: () => h(ArrowDownCircle) }
const PushIcon = { render: () => h(ArrowUpCircle) }

const gitStatus = ref(null)
const stagedFiles = ref([])
const unstagedFiles = ref([])
const branches = ref([])
const commitMessage = ref('')
const showBranchMenu = ref(false)

function getFileStatusIcon(status) {
  if (status === 'modified') return ModifiedIcon
  if (status === 'deleted') return DeletedIcon
  return AddedIcon
}

async function loadGitStatus() {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    
    const status = await git.status()
    const branch = await git.branch()
    
    gitStatus.value = {
      branch: branch.current || 'main',
      added: status.added.length,
      modified: status.modified.length,
      deleted: status.deleted.length
    }
    
    stagedFiles.value = status.staged.map(path => ({ path, status: 'added' }))
    unstagedFiles.value = [
      ...status.modified.map(path => ({ path, status: 'modified' })),
      ...status.deleted.map(path => ({ path, status: 'deleted' })),
      ...status.renamed.map(r => ({ path: r.to, status: 'modified' }))
    ]
    
    const branchList = await git.branchLocal()
    branches.value = branchList.all || []
  } catch (e) {
    gitStatus.value = null
    console.error('Git status error:', e)
  }
}

async function initRepo() {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.init()
    await loadGitStatus()
  } catch (e) {
    console.error('Init repo error:', e)
  }
}

async function stageFile(file) {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.add(file.path)
    await loadGitStatus()
  } catch (e) {
    console.error('Stage file error:', e)
  }
}

async function unstageFile(file) {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.reset('HEAD', file.path)
    await loadGitStatus()
  } catch (e) {
    console.error('Unstage file error:', e)
  }
}

async function commit() {
  if (!commitMessage.value.trim()) return
  
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.commit(commitMessage.value)
    commitMessage.value = ''
    await loadGitStatus()
  } catch (e) {
    console.error('Commit error:', e)
  }
}

async function pull() {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.pull()
    await loadGitStatus()
  } catch (e) {
    console.error('Pull error:', e)
  }
}

async function push() {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.push()
    await loadGitStatus()
  } catch (e) {
    console.error('Push error:', e)
  }
}

async function checkoutBranch(branch) {
  try {
    const simpleGit = await import('simple-git')
    const git = simpleGit.default()
    await git.checkout(branch)
    showBranchMenu.value = false
    await loadGitStatus()
  } catch (e) {
    console.error('Checkout branch error:', e)
  }
}

onMounted(() => {
  loadGitStatus()
})
</script>

<style scoped>
.git-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
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

.git-status {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-dark);
  border-radius: 8px;
}

.branch-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.branch-name {
  font-weight: 600;
  color: var(--text-primary);
}

.status-summary {
  display: flex;
  gap: 16px;
}

.stat {
  font-size: 12px;
}

.stat.added {
  color: var(--success-color);
}

.stat.modified {
  color: var(--warning-color);
}

.stat.deleted {
  color: var(--danger-color);
}

.no-repo {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.no-repo p {
  margin: 12px 0;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 8px;
  padding: 4px 0;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.file-item:hover {
  background: var(--bg-hover);
}

.status-icon {
  flex-shrink: 0;
}

.status-icon.added {
  color: var(--success-color);
}

.status-icon.modified {
  color: var(--warning-color);
}

.status-icon.deleted {
  color: var(--danger-color);
}

.file-path {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-list {
  padding: 12px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
}

.git-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.commit-input {
  margin-bottom: 12px;
}

.commit-message {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.commit-message::placeholder {
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-buttons button {
  flex: 1;
}

.branch-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-top: none;
  z-index: 100;
}

.branch-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.branch-item:hover {
  background: var(--bg-hover);
}

.branch-item.active {
  background: var(--primary-color);
  color: white;
}
</style>