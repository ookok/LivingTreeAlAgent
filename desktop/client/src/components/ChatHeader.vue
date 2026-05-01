<template>
  <header class="chat-header">
    <div class="header-left">
      <NSelect
        :model-value="configStore.currentModel"
        @update:model-value="configStore.changeModel"
        :options="configStore.models"
        placeholder="选择模型"
        class="model-select"
      />
    </div>
    
    <div class="header-center">
      <span v-if="chatStore.currentSession">{{ chatStore.currentSession.name }}</span>
      <span v-else>选择会话</span>
    </div>
    
    <div class="header-right">
      <NButton text @click="showSettings = true">
        <NIcon :component="SettingsIcon" :size="18" />
      </NButton>
    </div>
    
    <NModal v-if="showSettings" @update:show="showSettings = false">
      <div class="settings-modal">
        <h3>AI设置</h3>
        <div class="settings-section">
          <label>温度</label>
          <NInputNumber v-model="configStore.temperature" :min="0" :max="2" :step="0.1" />
        </div>
        <div class="settings-section">
          <label>最大Token</label>
          <NInputNumber v-model="configStore.maxTokens" :min="100" :max="32000" :step="100" />
        </div>
        <div class="settings-actions">
          <NButton text @click="showSettings = false">取消</NButton>
          <NButton type="primary" @click="saveAndClose">保存</NButton>
        </div>
      </div>
    </NModal>
  </header>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NButton, NSelect, NIcon, NModal, NInputNumber } from 'naive-ui'
import { Settings } from '@vicons/ionicons5'
import { useConfigStore } from '../stores/configStore'
import { useChatStore } from '../stores/chatStore'

const SettingsIcon = { render: () => h(Settings) }

const configStore = useConfigStore()
const chatStore = useChatStore()
const showSettings = ref(false)

function saveAndClose() {
  configStore.saveSettings()
  showSettings.value = false
}

onMounted(() => {
  configStore.loadModels()
})
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  flex: 1;
}

.model-select {
  width: 200px;
}

.header-center {
  flex: 2;
  text-align: center;
}

.header-right {
  flex: 1;
  text-align: right;
}

.settings-modal {
  width: 400px;
  padding: 24px;
}

.settings-modal h3 {
  margin-bottom: 20px;
}

.settings-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.settings-section label {
  width: 100px;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>