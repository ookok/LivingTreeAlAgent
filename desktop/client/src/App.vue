<template>
  <div class="app-container" :class="{ 'dark': configStore.isDark, 'light': !configStore.isDark }">
    <div class="app-header">
      <div class="logo-section">
        <NIcon :component="LogoIcon" :size="24" />
        <span class="logo-text">LivingTree AI</span>
      </div>
      
      <div class="nav-tabs">
        <NButton 
          text 
          :class="{ active: currentPage === 'chat' }"
          @click="currentPage = 'chat'"
        >
          <NIcon :component="ChatIcon" :size="18" />
          <span>聊天</span>
        </NButton>
        <NButton 
          text 
          :class="{ active: currentPage === 'ide' }"
          @click="currentPage = 'ide'"
        >
          <NIcon :component="CodeIcon" :size="18" />
          <span>IDE</span>
        </NButton>
        <NButton 
          text 
          :class="{ active: currentPage === 'explorer' }"
          @click="currentPage = 'explorer'"
        >
          <NIcon :component="FolderIcon" :size="18" />
          <span>资源管理器</span>
        </NButton>
      </div>
      
      <div class="header-center">
        <NSelect
          v-if="currentPage === 'chat'"
          :model-value="configStore.currentModel"
          @update:model-value="configStore.changeModel"
          :options="configStore.models"
          placeholder="选择模型"
          class="model-select"
        />
        <div v-else class="page-title">
          {{ pageTitle }}
        </div>
      </div>
      
      <div class="header-actions">
        <NButton text @click="showSystemSettings = true">
          <NIcon :component="SettingsIcon" :size="20" />
        </NButton>
        <NButton text @click="showUserSettings = true">
          <NIcon :component="UserIcon" :size="20" />
        </NButton>
        <NButton text @click="configStore.toggleTheme">
          <NIcon :component="themeIcon" :size="20" />
        </NButton>
      </div>
    </div>
    
    <div class="main-content">
      <ChatLayout v-if="currentPage === 'chat'" />
      <IdePage v-else-if="currentPage === 'ide'" />
      <ExplorerPage v-else-if="currentPage === 'explorer'" />
    </div>
    
    <NModal v-if="showSystemSettings" @update:show="showSystemSettings = false">
      <div class="settings-modal large">
        <SystemSettings @close="showSystemSettings = false" />
      </div>
    </NModal>
    
    <NModal v-if="showUserSettings" @update:show="showUserSettings = false">
      <div class="settings-modal large">
        <UserSettings @close="showUserSettings = false" />
      </div>
    </NModal>
    
    <div v-if="showToast" class="toast" :class="toastType">
      <NIcon :component="toastIcon" :size="18" />
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { NButton, NIcon, NSelect, NModal } from 'naive-ui'
import { Bot, MessageSquare, Code, Settings, Sun, Moon, User, FolderOpen, CheckCircle, AlertCircle, Info } from '@vicons/ionicons5'
import ChatLayout from './components/ChatLayout.vue'
import IdePage from './components/IdePage.vue'
import ExplorerPage from './components/ExplorerPage.vue'
import SystemSettings from './components/SystemSettings.vue'
import UserSettings from './components/UserSettings.vue'
import { useConfigStore } from './stores/configStore'

const configStore = useConfigStore()

const LogoIcon = { render: () => h(Bot) }
const ChatIcon = { render: () => h(MessageSquare) }
const CodeIcon = { render: () => h(Code) }
const SettingsIcon = { render: () => h(Settings) }
const SunIcon = { render: () => h(Sun) }
const MoonIcon = { render: () => h(Moon) }
const UserIcon = { render: () => h(User) }
const FolderIcon = { render: () => h(FolderOpen) }
const SuccessIcon = { render: () => h(CheckCircle) }
const ErrorIcon = { render: () => h(AlertCircle) }
const InfoIcon = { render: () => h(Info) }

const currentPage = ref('chat')
const showSystemSettings = ref(false)
const showUserSettings = ref(false)
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('success')

const themeIcon = computed(() => configStore.isDark ? SunIcon : MoonIcon)

const toastIcon = computed(() => {
  switch (toastType.value) {
    case 'success': return SuccessIcon
    case 'error': return ErrorIcon
    default: return InfoIcon
  }
})

const pageTitle = computed(() => {
  const titles = {
    chat: 'AI 聊天助手',
    ide: '代码编辑器',
    explorer: '资源管理器'
  }
  return titles[currentPage.value] || ''
})

function showToastMessage(message, type = 'success') {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

watch(() => configStore.isDark, (isDark) => {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
})

onMounted(() => {
  configStore.loadSettings()
  configStore.loadModels()
  if (configStore.isDark) {
    document.documentElement.setAttribute('data-theme', 'dark')
  }
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-container.light {
  --bg-dark: #ffffff;
  --bg-card: #f8fafc;
  --bg-hover: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --border-color: #e2e8f0;
}

.app-container.dark {
  --bg-dark: #0f172a;
  --bg-card: #1e293b;
  --bg-hover: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --border-color: #334155;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
}

.nav-tabs {
  display: flex;
  gap: 8px;
}

.nav-tabs .active {
  background: var(--bg-hover);
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.model-select {
  width: 200px;
}

.page-title {
  font-size: 14px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  gap: 8px;
  min-width: 120px;
  justify-content: flex-end;
}

.main-content {
  flex: 1;
  overflow: hidden;
}

.settings-modal {
  width: 900px;
  max-height: 85vh;
  overflow: hidden;
}

.settings-modal.large {
  width: 950px;
}

.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  background: var(--bg-card);
  border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  z-index: 9999;
  animation: slideIn 0.3s ease;
}

.toast.success {
  border-left: 4px solid var(--success-color);
}

.toast.error {
  border-left: 4px solid var(--danger-color);
}

.toast.info {
  border-left: 4px solid var(--primary-color);
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>