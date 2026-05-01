<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <NButton type="primary" block @click="chatStore.createSession()">
        <NIcon :component="PlusIcon" :size="18" />
        新建会话
      </NButton>
    </div>
    
    <div class="search-bar">
      <NInput
        v-model="chatStore.searchQuery"
        placeholder="搜索会话..."
        size="small"
        class="search-input"
      >
        <template #prefix>
          <NIcon :component="SearchIcon" :size="16" />
        </template>
      </NInput>
    </div>
    
    <div class="session-list">
      <div
        v-for="session in chatStore.filteredSessions"
        :key="session.id"
        class="session-item"
        :class="{ active: chatStore.currentSession?.id === session.id }"
        @click="chatStore.selectSession(session)"
      >
        <div class="session-icon">
          <NIcon :component="session.starred ? StarIcon : MessageIcon" :size="18" />
        </div>
        <div class="session-info">
          <span class="session-name">{{ session.name }}</span>
          <span class="session-time">{{ formatTime(session.timestamp) }}</span>
        </div>
        <div class="session-actions">
          <NButton
            v-if="session.starred"
            text
            size="small"
            @click.stop="toggleStar(session)"
          >
            <NIcon :component="StarIcon" :size="16" />
          </NButton>
          <NButton text size="small" @click.stop="confirmDelete(session)">
            <NIcon :component="TrashIcon" :size="16" />
          </NButton>
        </div>
      </div>
      
      <div v-if="chatStore.filteredSessions.length === 0" class="empty-state">
        <NIcon :component="MessageIcon" :size="32" />
        <p>暂无会话</p>
        <p class="hint">点击上方按钮创建新会话</p>
      </div>
    </div>
    
    <div class="sidebar-footer">
      <NButton text @click="showUserSettings = true">
        <NIcon :component="SettingsIcon" :size="18" />
        设置
      </NButton>
    </div>
    
    <NModal v-if="showUserSettings" @update:show="showUserSettings = false">
      <div class="settings-content">
        <UserSettings @close="showUserSettings = false" />
      </div>
    </NModal>
  </aside>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NButton, NInput, NIcon, NModal } from 'naive-ui'
import { Plus, Search, MessageSquare, Star, Trash2, Settings } from '@vicons/ionicons5'
import { useChatStore } from '../stores/chatStore'
import UserSettings from './UserSettings.vue'

const chatStore = useChatStore()
const showUserSettings = ref(false)

const PlusIcon = { render: () => h(Plus) }
const SearchIcon = { render: () => h(Search) }
const MessageIcon = { render: () => h(MessageSquare) }
const StarIcon = { render: () => h(Star) }
const TrashIcon = { render: () => h(Trash2) }
const SettingsIcon = { render: () => h(Settings) }

function toggleStar(session) {
  chatStore.updateSession(session.id, { starred: !session.starred })
}

function confirmDelete(session) {
  if (confirm(`确定要删除会话 "${session.name}" 吗？`)) {
    chatStore.deleteSession(session.id)
  }
}

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  
  return date.toLocaleDateString()
}

onMounted(() => {
  chatStore.initConnection()
})
</script>

<style scoped>
.sidebar {
  width: 280px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.search-bar {
  padding: 12px;
}

.search-input {
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: var(--bg-hover);
}

.session-item.active {
  background: var(--primary-color);
}

.session-icon {
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-name {
  display: block;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
}

.session-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.empty-state p {
  margin: 8px 0;
}

.empty-state .hint {
  font-size: 12px;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color);
}

.settings-content {
  width: 900px;
  height: 80vh;
  overflow-y: auto;
}
</style>