<template>
  <header class="header">
    <div class="header-left">
      <div class="logo">
        <NIcon :component="BotIcon" :size="24" />
        <span class="logo-text">LivingTree AI</span>
      </div>
    </div>
    
    <div class="header-center">
      <NSelect
        :model-value="configStore.currentModel"
        @update:model-value="configStore.changeModel"
        :options="configStore.models"
        placeholder="选择模型"
        class="model-select"
      />
    </div>
    
    <div class="header-right">
      <NButton text @click="configStore.showSettings = true">
        <NIcon :component="SettingsIcon" :size="20" />
      </NButton>
      <NButton text @click="configStore.toggleTheme">
        <NIcon :component="themeIcon" :size="20" />
      </NButton>
    </div>
    
    <NModal v-if="configStore.showSettings" @update:show="configStore.showSettings = false">
      <div class="settings-modal">
        <h3>设置</h3>
        <div class="settings-section">
          <label>温度</label>
          <NInputNumber v-model="configStore.temperature" :min="0" :max="2" :step="0.1" />
        </div>
        <div class="settings-section">
          <label>最大Token</label>
          <NInputNumber v-model="configStore.maxTokens" :min="100" :max="32000" :step="100" />
        </div>
        <div class="settings-actions">
          <NButton text @click="configStore.showSettings = false">取消</NButton>
          <NButton type="primary" @click="saveAndClose">保存</NButton>
        </div>
      </div>
    </NModal>
  </header>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { NButton, NSelect, NIcon, NModal, NInputNumber } from 'naive-ui'
import { Bot, Settings, Sun, Moon } from '@vicons/ionicons5'
import { useConfigStore } from '../stores/configStore'

const configStore = useConfigStore()

const BotIcon = { render: () => h(Bot) }
const SettingsIcon = { render: () => h(Settings) }
const SunIcon = { render: () => h(Sun) }
const MoonIcon = { render: () => h(Moon) }

const themeIcon = computed(() => configStore.isDark ? SunIcon : MoonIcon)

function saveAndClose() {
  configStore.saveSettings()
  configStore.showSettings = false
}

onMounted(() => {
  configStore.loadModels()
})
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.model-select {
  width: 200px;
}

.header-right {
  display: flex;
  gap: 8px;
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