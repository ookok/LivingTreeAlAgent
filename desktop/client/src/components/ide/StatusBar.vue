<template>
  <div class="status-bar">
    <div class="status-left">
      <span class="status-item">Ln {{ currentLine }}, Col {{ currentCol }}</span>
      <span class="status-divider"></span>
      <span class="status-item">Spaces: {{ indentSize }}</span>
      <span class="status-divider"></span>
      <span class="status-item">{{ encoding }}</span>
      <span class="status-divider"></span>
      <span class="status-item">{{ lineEnding }}</span>
      <span class="status-divider"></span>
      <span class="status-item">{{ language }}</span>
    </div>
    
    <div class="status-center">
      <div class="git-status">
        <NIcon :component="GitIcon" :size="14" />
        <span>{{ gitBranch }}</span>
        <span v-if="gitChanges > 0" class="git-changes">*{{ gitChanges }}</span>
      </div>
      <div class="save-status" :class="{ modified: isModified }">
        {{ isModified ? '● 未保存' : '● 已保存' }}
      </div>
    </div>
    
    <div class="status-right">
      <span class="status-item battery">⚡ {{ battery }}%</span>
      <span class="status-item">{{ currentTime }}</span>
      <span class="status-item">🌐 {{ networkStatus }}</span>
      <NButton text size="small" @click="showUserMenu = !showUserMenu">
        <NIcon :component="UserIcon" :size="14" />
        <span>用户</span>
      </NButton>
      <NButton text size="small">
        <NIcon :component="BellIcon" :size="14" />
        <span>{{ notificationCount }}</span>
      </NButton>
    </div>
    
    <div v-if="showUserMenu" class="user-menu">
      <div class="menu-item">个人资料</div>
      <div class="menu-item">设置</div>
      <div class="menu-separator"></div>
      <div class="menu-item logout">退出登录</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { GitBranch, User, Bell } from '@vicons/ionicons5'

const GitIcon = { render: () => h(GitBranch) }
const UserIcon = { render: () => h(User) }
const BellIcon = { render: () => h(Bell) }

const currentLine = ref(10)
const currentCol = ref(5)
const indentSize = ref(4)
const encoding = ref('UTF-8')
const lineEnding = ref('LF')
const language = ref('Python')

const gitBranch = ref('main')
const gitChanges = ref(1)
const isModified = ref(true)

const battery = ref(84)
const currentTime = ref('')
const networkStatus = ref('在线')
const notificationCount = ref(3)
const showUserMenu = ref(false)

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

let timer = null

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  
  document.addEventListener('click', () => {
    showUserMenu.value = false
  })
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
}

.status-left, .status-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-center {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  padding: 2px 6px;
}

.status-divider {
  width: 1px;
  height: 12px;
  background: var(--border-color);
}

.git-status {
  display: flex;
  align-items: center;
  gap: 4px;
}

.git-changes {
  color: var(--warning-color);
}

.save-status {
  color: var(--success-color);
}

.save-status.modified {
  color: var(--warning-color);
}

.user-menu {
  position: absolute;
  bottom: 32px;
  right: 80px;
  min-width: 150px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 4px;
  z-index: 100;
}

.menu-item {
  padding: 6px 12px;
  cursor: pointer;
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-item.logout {
  color: var(--danger-color);
}

.menu-separator {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}
</style>