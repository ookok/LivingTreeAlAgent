<template>
  <div class="chat-area">
    <div v-if="!chatStore.currentSession" class="empty-chat">
      <NIcon :component="BotIcon" :size="64" />
      <h2>开始新对话</h2>
      <p>选择一个会话或创建新会话开始聊天</p>
      <NButton type="primary" @click="createNewSession">
        <NIcon :component="PlusIcon" :size="18" />
        创建新会话
      </NButton>
    </div>
    
    <div v-else class="chat-container">
      <div ref="messageContainer" class="message-list">
        <div
          v-for="message in chatStore.messages"
          :key="message.id"
          class="message-item"
          :class="{ 'is-ai': message.role === 'assistant' }"
        >
          <div class="message-avatar">
            <NIcon :component="message.role === 'assistant' ? BotIcon : UserIcon" :size="24" />
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-role">{{ message.role === 'assistant' ? 'LivingTree AI' : '我' }}</span>
              <span class="message-time">{{ formatTime(message.timestamp) }}</span>
            </div>
            <div class="message-body" v-html="renderMarkdown(message.content)"></div>
            <div class="message-actions">
              <NButton text size="small" @click="copyMessage(message)">
                <NIcon :component="CopyIcon" :size="14" />
                复制
              </NButton>
              <NButton text size="small" @click="regenerateMessage(message)">
                <NIcon :component="RefreshIcon" :size="14" />
                重新生成
              </NButton>
              <NButton text size="small" @click="editMessage(message)">
                <NIcon :component="EditIcon" :size="14" />
                编辑
              </NButton>
            </div>
          </div>
        </div>
        
        <div v-if="chatStore.isLoading" class="loading-message">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>AI正在思考...</span>
        </div>
      </div>
      
      <div class="input-area">
        <div class="input-toolbar">
          <NButton text @click="uploadFile">
            <NIcon :component="PaperclipIcon" :size="18" />
          </NButton>
          <NButton text @click="showPresets = !showPresets">
            <NIcon :component="SparklesIcon" :size="18" />
          </NButton>
          <NButton text @click="insertTemplate">
            <NIcon :component="FileTextIcon" :size="18" />
          </NButton>
          <NButton text @click="chatStore.stopGeneration" v-if="chatStore.isLoading">
            <NIcon :component="StopIcon" :size="18" />
            停止
          </NButton>
        </div>
        
        <div v-if="showPresets" class="preset-list">
          <NButton
            v-for="preset in presets"
            :key="preset.id"
            text
            size="small"
            class="preset-btn"
            @click="applyPreset(preset)"
          >
            <NIcon :component="preset.icon" :size="14" />
            {{ preset.name }}
          </NButton>
        </div>
        
        <div class="input-wrapper">
          <textarea
            v-model="inputMessage"
            class="message-input"
            placeholder="输入消息..."
            rows="1"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.shift.enter="handleShiftEnter"
          ></textarea>
          <NButton
            type="primary"
            :disabled="!inputMessage.trim() || chatStore.isLoading"
            @click="sendMessage"
            class="send-btn"
          >
            <NIcon :component="SendIcon" :size="18" />
          </NButton>
        </div>
        
        <div class="input-footer">
          <span class="model-info">{{ currentModelName }}</span>
          <span class="tips">Shift + Enter 换行</span>
        </div>
      </div>
    </div>
    
    <NModal v-if="showFileUpload" @update:show="showFileUpload = false">
      <div class="upload-modal">
        <h3>上传文件</h3>
        <div class="upload-area" @drop.prevent="handleDrop" @dragover.prevent>
          <NIcon :component="UploadIcon" :size="48" />
          <p>拖拽文件到这里</p>
          <p class="hint">支持 PDF、Word、图片等格式</p>
        </div>
        <div class="upload-actions">
          <NButton text @click="showFileUpload = false">取消</NButton>
          <NButton type="primary">上传</NButton>
        </div>
      </div>
    </NModal>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch, computed } from 'vue'
import { NButton, NIcon, NModal } from 'naive-ui'
import { 
  Bot, User, Copy, RefreshCw, Paperclip, Sparkles, Send, Square, 
  FileText, Plus, Upload, Mail, Code, PenTool, Translate, FileSearch 
} from '@vicons/ionicons5'
import { marked } from 'marked'
import hljs from 'highlight.js'
import { useChatStore } from '../stores/chatStore'
import { useConfigStore } from '../stores/configStore'

const chatStore = useChatStore()
const configStore = useConfigStore()

const BotIcon = { render: () => h(Bot) }
const UserIcon = { render: () => h(User) }
const CopyIcon = { render: () => h(Copy) }
const RefreshIcon = { render: () => h(RefreshCw) }
const PaperclipIcon = { render: () => h(Paperclip) }
const SparklesIcon = { render: () => h(Sparkles) }
const SendIcon = { render: () => h(Send) }
const StopIcon = { render: () => h(Square) }
const FileTextIcon = { render: () => h(FileText) }
const PlusIcon = { render: () => h(Plus) }
const UploadIcon = { render: () => h(Upload) }

const MailIcon = { render: () => h(Mail) }
const CodeIcon = { render: () => h(Code) }
const PenToolIcon = { render: () => h(PenTool) }
const TranslateIcon = { render: () => h(Translate) }
const SearchIcon = { render: () => h(FileSearch) }

const inputMessage = ref('')
const showPresets = ref(false)
const showFileUpload = ref(false)
const messageContainer = ref(null)

const presets = [
  { id: 1, name: '写一封邮件', content: '帮我写一封正式邮件，主题是...', icon: MailIcon },
  { id: 2, name: '代码审查', content: '帮我审查这段代码：\n\n```\n', icon: CodeIcon },
  { id: 3, name: '创意写作', content: '帮我创作一个故事开头：', icon: PenToolIcon },
  { id: 4, name: '翻译', content: '翻译以下内容为英文：\n\n', icon: TranslateIcon },
  { id: 5, name: '文档总结', content: '总结以下内容：\n\n', icon: SearchIcon },
]

const currentModelName = computed(() => {
  const model = configStore.models.find(m => m.value === configStore.currentModel)
  return model?.label || '未知模型'
})

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

function sendMessage() {
  if (!inputMessage.value.trim()) return
  chatStore.sendMessage(inputMessage.value)
  inputMessage.value = ''
}

function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

function copyMessage(message) {
  navigator.clipboard.writeText(message.content).then(() => {
    showToast('已复制到剪贴板')
  })
}

function regenerateMessage(message) {
  if (message.role === 'assistant') {
    const index = chatStore.messages.findIndex(m => m.id === message.id)
    if (index > 0) {
      const userMessage = chatStore.messages[index - 1]
      inputMessage.value = userMessage.content
      chatStore.messages = chatStore.messages.slice(0, index)
    }
  }
}

function editMessage(message) {
  console.log('Edit message:', message)
}

function stopGeneration() {
  chatStore.stopGeneration()
}

function uploadFile() {
  showFileUpload.value = true
}

function handleDrop(e) {
  const files = e.dataTransfer.files
  console.log('Dropped files:', files)
}

function applyPreset(preset) {
  inputMessage.value = preset.content
  showPresets.value = false
}

function insertTemplate() {
  console.log('Insert template')
}

function createNewSession() {
  chatStore.createSession()
}

function handleShiftEnter(e) {
  e.target.value += '\n'
}

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function renderMarkdown(content) {
  marked.setOptions({
    highlight: (code, lang) => {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    }
  })
  return marked(content)
}

function showToast(message) {
  const toast = document.createElement('div')
  toast.className = 'toast-message'
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 2000)
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-dark);
}

.empty-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-chat h2 {
  margin: 16px 0 8px;
  color: var(--text-primary);
}

.empty-chat p {
  margin-bottom: 24px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message-item.is-ai .message-avatar {
  background: var(--primary-color);
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
  max-width: 80%;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.message-role {
  font-weight: 600;
}

.message-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.message-body {
  background: var(--bg-card);
  padding: 12px 16px;
  border-radius: 0 12px 12px 12px;
  line-height: 1.6;
}

.message-item.is-ai .message-body {
  border-radius: 12px 0 12px 12px;
  background: var(--primary-color);
}

.message-body pre {
  background: rgba(0,0,0,0.3);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-body code {
  background: rgba(0,0,0,0.2);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.message-body pre code {
  background: transparent;
  padding: 0;
}

.message-body blockquote {
  border-left: 3px solid var(--primary-color);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.message-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-item:hover .message-actions {
  opacity: 1;
}

.loading-message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 12px 0 12px 12px;
  color: var(--text-secondary);
}

.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--primary-color);
  border-radius: 50%;
  animation: typingPulse 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typingPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.input-area {
  padding: 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}

.input-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
  background: var(--bg-dark);
  border-radius: 8px;
}

.preset-btn {
  background: var(--bg-hover);
  padding: 6px 12px;
  border-radius: 20px;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.message-input {
  flex: 1;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 16px;
  color: var(--text-primary);
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  min-height: 48px;
}

.message-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.message-input::placeholder {
  color: var(--text-secondary);
}

.send-btn {
  border-radius: 12px;
  padding: 12px 24px;
}

.input-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.model-info {
  background: var(--bg-hover);
  padding: 4px 10px;
  border-radius: 12px;
}

.upload-modal {
  width: 400px;
  padding: 24px;
}

.upload-modal h3 {
  margin-bottom: 20px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.upload-area:hover {
  border-color: var(--primary-color);
}

.upload-area p {
  margin: 12px 0 4px;
}

.upload-area .hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.upload-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

.toast-message {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  color: var(--text-primary);
  animation: fadeInUp 0.3s ease;
}

@keyframes fadeInUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>