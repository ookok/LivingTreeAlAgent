<template>
  <div class="settings-container">
    <div class="settings-header">
      <h2>用户设置</h2>
      <div class="header-actions">
        <NButton text @click="resetSettings">重置</NButton>
        <NButton type="primary" @click="saveSettings">保存</NButton>
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
        <div v-if="activeTab === 'profile'" class="settings-panel">
          <h3>个人资料</h3>
          
          <div class="section">
            <label class="section-title">头像</label>
            <div class="avatar-section">
              <div class="avatar-preview">
                <img v-if="profile.avatar" :src="profile.avatar" alt="Avatar" />
                <div v-else class="avatar-placeholder">
                  <NIcon :component="UserIcon" :size="40" />
                </div>
              </div>
              <div class="avatar-actions">
                <NButton type="primary" size="small">上传头像</NButton>
                <NButton text size="small" @click="removeAvatar">移除</NButton>
              </div>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">基本信息</label>
            <NInput v-model="profile.name" placeholder="显示名称" maxlength="30" />
            <div class="input-group">
              <NInput v-model="profile.email" placeholder="邮箱地址" disabled />
              <NButton text size="small">更换邮箱</NButton>
            </div>
            <NInput v-model="profile.phone" placeholder="手机号码" />
            <NTextarea v-model="profile.bio" placeholder="个人简介" maxlength="500" />
          </div>
          
          <div class="section">
            <label class="section-title">社交绑定</label>
            <div class="social-links">
              <div class="social-item">
                <span>GitHub</span>
                <NButton text size="small" v-if="!profile.social.github">绑定</NButton>
                <div v-else class="bound-badge">
                  <span>已绑定</span>
                  <NButton text size="small" danger>解绑</NButton>
                </div>
              </div>
              <div class="social-item">
                <span>Google</span>
                <div class="bound-badge">
                  <span>已绑定</span>
                  <NButton text size="small" danger>解绑</NButton>
                </div>
              </div>
              <div class="social-item">
                <span>微信</span>
                <NButton text size="small">扫码绑定</NButton>
              </div>
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'security'" class="settings-panel">
          <h3>账户与安全</h3>
          
          <div class="section">
            <label class="section-title">密码管理</label>
            <NInput type="password" v-model="security.currentPassword" placeholder="当前密码" />
            <NInput type="password" v-model="security.newPassword" placeholder="新密码" />
            <NInput type="password" v-model="security.confirmPassword" placeholder="确认密码" />
            <NButton type="primary" @click="changePassword">更改密码</NButton>
          </div>
          
          <div class="section">
            <label class="section-title">双重验证</label>
            <div class="toggle-row">
              <NSwitch v-model="security.twoFA" />
              <span>启用双重验证（2FA）</span>
            </div>
            <p class="hint">建议启用双重验证以提高账户安全性</p>
          </div>
          
          <div class="section">
            <label class="section-title">登录设备</label>
            <NTable :columns="deviceColumns" :data="devices" />
            <NButton text size="small" danger @click="logoutAllDevices">退出所有设备</NButton>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'notifications'" class="settings-panel">
          <h3>通知偏好</h3>
          
          <div class="section">
            <label class="section-title">桌面通知</label>
            <div class="toggle-row">
              <NSwitch v-model="notifications.desktop" />
              <span>启用桌面通知</span>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">通知类型</label>
            <div class="checkbox-group">
              <label><NCheckbox v-model="notifications.types.newMessage" /> 新消息提醒</label>
              <label><NCheckbox v-model="notifications.types.aiResponse" /> AI响应完成</label>
              <label><NCheckbox v-model="notifications.types.system" /> 系统通知</label>
              <label><NCheckbox v-model="notifications.types.errors" /> 错误提醒</label>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">邮件通知</label>
            <div class="checkbox-group">
              <label><NCheckbox v-model="notifications.email.daily" /> 每日摘要</label>
              <label><NCheckbox v-model="notifications.email.weekly" /> 每周摘要</label>
              <label><NCheckbox v-model="notifications.email.important" /> 重要更新</label>
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'appearance'" class="settings-panel">
          <h3>外观与显示</h3>
          
          <div class="section">
            <label class="section-title">主题模式</label>
            <div class="theme-selector">
              <div 
                class="theme-option"
                :class="{ active: appearance.theme === 'light' }"
                @click="appearance.theme = 'light'; updateTheme()"
              >
                <NIcon :component="SunIcon" :size="32" />
                <span>浅色</span>
              </div>
              <div 
                class="theme-option"
                :class="{ active: appearance.theme === 'dark' }"
                @click="appearance.theme = 'dark'; updateTheme()"
              >
                <NIcon :component="MoonIcon" :size="32" />
                <span>深色</span>
              </div>
              <div 
                class="theme-option"
                :class="{ active: appearance.theme === 'system' }"
                @click="appearance.theme = 'system'; updateTheme()"
              >
                <NIcon :component="MonitorIcon" :size="32" />
                <span>跟随系统</span>
              </div>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">字体大小</label>
            <div class="slider-control">
              <NSlider v-model="appearance.fontSize" :min="12" :max="20" />
              <span>{{ appearance.fontSize }}px</span>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">界面密度</label>
            <div class="radio-group">
              <label><NRadio v-model="appearance.density" value="compact" /> 紧凑</label>
              <label><NRadio v-model="appearance.density" value="normal" /> 标准</label>
              <label><NRadio v-model="appearance.density" value="comfortable" /> 舒适</label>
            </div>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'ai'" class="settings-panel">
          <h3>AI助手配置</h3>
          
          <div class="section">
            <label class="section-title">模型偏好</label>
            <NSelect v-model="aiConfig.defaultModel" :options="modelOptions" />
            <NSelect v-model="aiConfig.backupModel" :options="modelOptions" />
          </div>
          
          <div class="section">
            <label class="section-title">温度设置</label>
            <div class="slider-control">
              <NSlider v-model="aiConfig.temperature" :min="0" :max="2" :step="0.1" />
              <span>{{ aiConfig.temperature }}</span>
            </div>
            <p class="hint">较低的值使输出更确定性，较高的值使输出更多样化</p>
          </div>
          
          <div class="section">
            <label class="section-title">响应限制</label>
            <NInputNumber v-model="aiConfig.maxTokens" :min="100" :max="32000" :step="100" />
            <span>最大 Token 数</span>
          </div>
          
          <div class="section">
            <label class="section-title">快速回复</label>
            <NSwitch v-model="aiConfig.quickReply" />
            <span>启用快速回复模式</span>
          </div>
        </div>
        
        <div v-else-if="activeTab === 'privacy'" class="settings-panel">
          <h3>数据与隐私</h3>
          
          <div class="section">
            <label class="section-title">数据存储</label>
            <div class="path-input">
              <NInput v-model="privacy.storagePath" placeholder="数据存储路径" />
              <NButton text size="small">浏览</NButton>
            </div>
          </div>
          
          <div class="section">
            <label class="section-title">数据导出</label>
            <div class="radio-group">
              <label><NRadio v-model="privacy.exportFormat" value="md" /> Markdown</label>
              <label><NRadio v-model="privacy.exportFormat" value="json" /> JSON</label>
              <label><NRadio v-model="privacy.exportFormat" value="html" /> HTML</label>
            </div>
            <NButton type="primary" @click="exportData">导出数据</NButton>
          </div>
          
          <div class="section">
            <label class="section-title">自动删除</label>
            <NSelect v-model="privacy.autoDelete" :options="deleteOptions" />
            <p class="hint">自动删除指定天数前的聊天记录</p>
          </div>
          
          <div class="section danger-section">
            <label class="section-title">危险操作</label>
            <NButton danger @click="confirmDeleteAccount">删除账户</NButton>
            <p class="hint">此操作不可撤销，请谨慎操作</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { 
  NButton, NInput, NTextarea, NSwitch, NTable, NCheckbox, 
  NRadio, NSlider, NSelect, NInputNumber, NIcon 
} from 'naive-ui'
import { 
  User, Shield, Bell, Palette, Bot, Lock, Settings, 
  Sun, Moon, Monitor, Github, Globe, MessageSquare, 
  RefreshCw, Mail, Clock 
} from '@vicons/ionicons5'

const emit = defineEmits(['close'])

const UserIcon = { render: () => h(User) }
const ShieldIcon = { render: () => h(Shield) }
const BellIcon = { render: () => h(Bell) }
const PaletteIcon = { render: () => h(Palette) }
const BotIcon = { render: () => h(Bot) }
const LockIcon = { render: () => h(Lock) }
const SunIcon = { render: () => h(Sun) }
const MoonIcon = { render: () => h(Moon) }
const MonitorIcon = { render: () => h(Monitor) }

const activeTab = ref('profile')

const tabs = [
  { id: 'profile', name: '个人资料', icon: UserIcon },
  { id: 'security', name: '账户与安全', icon: ShieldIcon },
  { id: 'notifications', name: '通知偏好', icon: BellIcon },
  { id: 'appearance', name: '外观与显示', icon: PaletteIcon },
  { id: 'ai', name: 'AI助手配置', icon: BotIcon },
  { id: 'privacy', name: '数据与隐私', icon: LockIcon },
]

const profile = reactive({
  avatar: '',
  name: 'LivingTree User',
  email: 'user@example.com',
  phone: '',
  bio: 'AI 助手爱好者',
  social: { github: false, google: true, wechat: false }
})

const security = reactive({ 
  twoFA: false,
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const notifications = reactive({
  desktop: true,
  types: { newMessage: true, aiResponse: true, system: true, errors: false },
  email: { daily: false, weekly: true, important: true }
})

const appearance = reactive({ theme: 'dark', fontSize: 14, density: 'normal' })

const aiConfig = reactive({
  defaultModel: 'gpt4',
  backupModel: 'gpt3.5',
  temperature: 0.7,
  maxTokens: 4000,
  quickReply: false
})

const privacy = reactive({
  storagePath: '',
  exportFormat: 'md',
  autoDelete: 'never'
})

const modelOptions = [
  { label: 'GPT-4 Turbo', value: 'gpt4' },
  { label: 'GPT-3.5 Turbo', value: 'gpt3.5' },
  { label: 'Claude 3', value: 'claude' },
  { label: 'Gemini Pro', value: 'gemini' },
]

const deleteOptions = [
  { label: '永不删除', value: 'never' },
  { label: '7天后', value: '7' },
  { label: '30天后', value: '30' },
  { label: '90天后', value: '90' },
]

const deviceColumns = [
  { title: '设备名称', key: 'name' },
  { title: 'IP地址', key: 'ip' },
  { title: '最后活跃', key: 'time' },
  { title: '操作', key: 'action' },
]

const devices = [
  { name: 'Chrome Windows', ip: '192.168.1.100', time: '刚刚', action: '退出登录' },
  { name: 'Safari Mac', ip: '192.168.1.101', time: '2小时前', action: '退出登录' },
  { name: 'Edge Windows', ip: '10.0.0.5', time: '1天前', action: '退出登录' },
]

function updateTheme() {
  if (appearance.theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else if (appearance.theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light')
  }
}

function saveSettings() {
  localStorage.setItem('userSettings', JSON.stringify({
    profile,
    security: { twoFA: security.twoFA },
    notifications,
    appearance,
    aiConfig,
    privacy
  }))
  emit('close')
}

function resetSettings() {
  profile.name = 'LivingTree User'
  profile.phone = ''
  profile.bio = 'AI 助手爱好者'
  security.twoFA = false
  notifications.desktop = true
  notifications.types = { newMessage: true, aiResponse: true, system: true, errors: false }
  appearance.theme = 'dark'
  appearance.fontSize = 14
  appearance.density = 'normal'
  aiConfig.temperature = 0.7
  aiConfig.maxTokens = 4000
}

function removeAvatar() {
  profile.avatar = ''
}

function changePassword() {
  if (!security.currentPassword || !security.newPassword) {
    alert('请填写所有密码字段')
    return
  }
  if (security.newPassword !== security.confirmPassword) {
    alert('新密码和确认密码不一致')
    return
  }
  alert('密码修改成功')
  security.currentPassword = ''
  security.newPassword = ''
  security.confirmPassword = ''
}

function logoutAllDevices() {
  if (confirm('确定要退出所有设备吗？')) {
    alert('已退出所有设备')
  }
}

function exportData() {
  alert('数据导出功能开发中')
}

function confirmDeleteAccount() {
  if (confirm('确定要删除账户吗？此操作不可撤销！')) {
    alert('账户删除功能开发中')
  }
}
</script>

<style scoped>
.settings-container {
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
  width: 200px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  padding: 16px 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
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
  max-width: 800px;
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

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-preview {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: var(--bg-hover);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-placeholder {
  color: var(--text-secondary);
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.social-links {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.social-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-card);
  border-radius: 8px;
}

.bound-badge {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--success-color);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.checkbox-group, .radio-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.checkbox-group label, .radio-group label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-control {
  display: flex;
  align-items: center;
  gap: 16px;
}

.slider-control span {
  min-width: 40px;
  text-align: right;
}

.theme-selector {
  display: flex;
  gap: 16px;
}

.theme-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  background: var(--bg-card);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.theme-option:hover {
  background: var(--bg-hover);
}

.theme-option.active {
  background: var(--primary-color);
}

.path-input {
  display: flex;
  gap: 12px;
}

.path-input .n-input {
  flex: 1;
}

.danger-section {
  padding: 16px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
}

.danger-section .section-title {
  color: var(--danger-color);
}
</style>