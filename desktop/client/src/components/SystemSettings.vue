<template>
  <div class="system-settings">
    <div class="settings-header">
      <h2>系统设置</h2>
      <div class="header-actions">
        <NButton text @click="resetSettings">重置为默认</NButton>
        <NButton type="primary" @click="saveSettings">保存设置</NButton>
      </div>
    </div>
    
    <div class="settings-body">
      <div class="nav-tabs">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-item"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <NIcon :component="tab.icon" :size="18" />
          <span>{{ tab.name }}</span>
        </div>
      </div>
      
      <div class="content-area">
        <div v-if="activeTab === 'general'" class="settings-panel">
          <h3>通用设置</h3>
          
          <div class="section">
            <label class="section-title">主题模式</label>
            <div class="radio-group">
              <label><NRadio v-model="settings.theme" value="dark" /> 深色模式</label>
              <label><NRadio v-model="settings.theme" value="light" /> 浅色模式</label>
              <label><NRadio v-model="settings.theme" value="system" /> 跟随系统</label>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">字体设置</label>
            <NSelect v-model="settings.fontFamily" :options="fontOptions" />
            <div class="slider-row">
              <span>字体大小: {{ settings.fontSize }}px</span>
              <NSlider v-model="settings.fontSize" :min="12" :max="20" />
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">启动选项</label>
            <div class="checkbox-group">
              <label><NCheckbox v-model="settings.startMinimized" /> 启动时最小化</label>
              <label><NCheckbox v-model="settings.autoUpdate" /> 自动检查更新</label>
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'ai'" class="settings-panel">
          <h3>AI 配置</h3>
          
          <div class="section">
            <label class="section-title">默认模型</label>
            <NSelect v-model="settings.aiModel" :options="modelOptions" />
          </div>
          
          <div class="section">
            <label class="section-title">API 设置</label>
            <NInput v-model="settings.apiKey" type="password" placeholder="API Key" />
            <NInput v-model="settings.apiEndpoint" placeholder="API 端点" />
          </div>
          
          <div class="section">
            <label class="section-title">参数设置</label>
            <div class="param-row">
              <span>温度: {{ settings.temperature }}</span>
              <NSlider v-model="settings.temperature" :min="0" :max="2" :step="0.1" />
            </div>
            <div class="param-row">
              <span>最大 Token: {{ settings.maxTokens }}</span>
              <NSlider v-model="settings.maxTokens" :min="500" :max="16000" :step="100" />
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'network'" class="settings-panel">
          <h3>网络设置</h3>
          
          <div class="section">
            <label class="section-title">代理设置</label>
            <NSwitch v-model="settings.useProxy" />
            <div v-if="settings.useProxy" class="proxy-settings">
              <NInput v-model="settings.proxyHost" placeholder="代理地址" />
              <NInputNumber v-model="settings.proxyPort" :min="1" :max="65535" />
              <NInput v-model="settings.proxyUser" placeholder="用户名" />
              <NInput v-model="settings.proxyPass" type="password" placeholder="密码" />
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">连接超时</label>
            <NInputNumber v-model="settings.timeout" :min="10" :max="300" />
            <span>秒</span>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'storage'" class="settings-panel">
          <h3>存储设置</h3>
          
          <div class="section">
            <label class="section-title">数据存储路径</label>
            <div class="path-input">
              <NInput v-model="settings.storagePath" />
              <NButton text size="small">浏览</NButton>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">自动保存</label>
            <NSwitch v-model="settings.autoSave" />
            <div v-if="settings.autoSave" class="save-interval">
              <span>保存间隔:</span>
              <NInputNumber v-model="settings.saveInterval" :min="1" :max="60" />
              <span>分钟</span>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">数据清理</label>
            <NButton type="primary" @click="clearCache">清除缓存</NButton>
            <NButton text @click="exportData">导出数据</NButton>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'shortcuts'" class="settings-panel">
          <h3>快捷键设置</h3>
          
          <div class="section">
            <label class="section-title">常用快捷键</label>
            <div class="shortcut-list">
              <div class="shortcut-item">
                <span>新建会话</span>
                <span class="shortcut-key">Ctrl + N</span>
              </div>
              <div class="shortcut-item">
                <span>搜索会话</span>
                <span class="shortcut-key">Ctrl + F</span>
              </div>
              <div class="shortcut-item">
                <span>命令面板</span>
                <span class="shortcut-key">Ctrl + Shift + P</span>
              </div>
              <div class="shortcut-item">
                <span>打开设置</span>
                <span class="shortcut-key">Ctrl + ,</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { NButton, NInput, NSelect, NSwitch, NSlider, NCheckbox, NRadio, NInputNumber, NIcon } from 'naive-ui'
import { Settings, Palette, Bot, Globe, HardDrive, Keyboard } from '@vicons/ionicons5'

const emit = defineEmits(['close'])

const SettingsIcon = { render: () => h(Settings) }
const PaletteIcon = { render: () => h(Palette) }
const BotIcon = { render: () => h(Bot) }
const GlobeIcon = { render: () => h(Globe) }
const HardDriveIcon = { render: () => h(HardDrive) }
const KeyboardIcon = { render: () => h(Keyboard) }

const activeTab = ref('general')

const tabs = [
  { id: 'general', name: '通用', icon: SettingsIcon },
  { id: 'ai', name: 'AI 配置', icon: BotIcon },
  { id: 'network', name: '网络', icon: GlobeIcon },
  { id: 'storage', name: '存储', icon: HardDriveIcon },
  { id: 'shortcuts', name: '快捷键', icon: KeyboardIcon },
]

const fontOptions = [
  { label: '系统字体', value: 'system' },
  { label: 'Microsoft YaHei', value: 'microsoft' },
  { label: 'JetBrains Mono', value: 'jetbrains' },
  { label: 'SF Mono', value: 'sfmono' },
]

const modelOptions = [
  { label: 'GPT-4 Turbo', value: 'gpt4' },
  { label: 'GPT-3.5 Turbo', value: 'gpt3.5' },
  { label: 'Claude 3 Opus', value: 'claude' },
  { label: 'Gemini Pro', value: 'gemini' },
]

const settings = reactive({
  theme: 'dark',
  fontFamily: 'system',
  fontSize: 14,
  startMinimized: false,
  autoUpdate: true,
  aiModel: 'gpt4',
  apiKey: '',
  apiEndpoint: '',
  temperature: 0.7,
  maxTokens: 4000,
  useProxy: false,
  proxyHost: '',
  proxyPort: 8080,
  proxyUser: '',
  proxyPass: '',
  timeout: 30,
  storagePath: '',
  autoSave: true,
  saveInterval: 5,
})

function saveSettings() {
  localStorage.setItem('systemSettings', JSON.stringify(settings))
  emit('close')
}

function resetSettings() {
  Object.assign(settings, {
    theme: 'dark',
    fontFamily: 'system',
    fontSize: 14,
    startMinimized: false,
    autoUpdate: true,
    aiModel: 'gpt4',
    apiKey: '',
    apiEndpoint: '',
    temperature: 0.7,
    maxTokens: 4000,
    useProxy: false,
    proxyHost: '',
    proxyPort: 8080,
    timeout: 30,
    storagePath: '',
    autoSave: true,
    saveInterval: 5,
  })
}

function clearCache() {
  localStorage.removeItem('chatSessions')
  localStorage.removeItem('messages')
}

function exportData() {
  console.log('Exporting data...')
}
</script>

<style scoped>
.system-settings {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.settings-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.nav-tabs {
  width: 180px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  padding: 16px 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  cursor: pointer;
  transition: background 0.2s;
}

.tab-item:hover {
  background: var(--bg-hover);
}

.tab-item.active {
  background: var(--primary-color);
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.settings-panel {
  max-width: 700px;
}

.settings-panel h3 {
  margin-bottom: 24px;
  font-size: 18px;
}

.section {
  margin-bottom: 32px;
}

.section-title {
  display: block;
  margin-bottom: 12px;
  font-weight: 600;
}

.radio-group, .checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.radio-group label, .checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-row, .param-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.slider-row span, .param-row span {
  min-width: 120px;
}

.proxy-settings {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
  padding: 16px;
  background: var(--bg-dark);
  border-radius: 8px;
}

.path-input {
  display: flex;
  gap: 12px;
}

.path-input .n-input {
  flex: 1;
}

.save-interval {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-item {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: var(--bg-card);
  border-radius: 8px;
}

.shortcut-key {
  font-family: monospace;
  background: var(--bg-hover);
  padding: 4px 12px;
  border-radius: 4px;
}
</style>