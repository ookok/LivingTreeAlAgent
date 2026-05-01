<template>
  <div class="ai-assistant">
    <div class="chat-header">
      <div class="header-left">
        <div class="solo-badge">
          <span class="solo-icon">🌳</span>
          <span class="solo-text">SOLO</span>
        </div>
        <div class="project-info">
          <span class="project-name">LivingTreeAlAgent</span>
          <button class="dropdown-btn">▼</button>
        </div>
        <div class="mode-switch">
          <button 
            :class="['mode-btn', { active: currentMode === 'mtc' }]"
            @click="currentMode = 'mtc'"
          >MTC</button>
          <button 
            :class="['mode-btn', { active: currentMode === 'code' }]"
            @click="currentMode = 'code'"
          >Code</button>
        </div>
      </div>
      <div class="header-right">
        <button class="tool-btn" @click="toggleVoiceInput" :title="isRecording ? '停止录音' : '语音输入'">
          <span>{{ isRecording ? '⏹️' : '🎤' }}</span>
        </button>
        <button class="tool-btn" title="刷新"><span>🔄</span></button>
        <button class="tool-btn" title="设置"><span>⚙️</span></button>
        <button class="tool-btn" title="用户"><span>👤</span></button>
      </div>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div 
        v-for="(message, index) in messages" 
        :key="index"
        :class="['message', { user: message.isUser, ai: !message.isUser }]"
      >
        <div v-if="message.thought" class="thought-indicator">
          <span class="thought-icon">💡</span>
          <span class="thought-text">Thought</span>
        </div>
        
        <div class="message-content">
          <div v-if="message.codeChange" class="code-change-card">
            <div class="change-header">
              <span class="file-icon">📄</span>
              <span class="file-path">{{ message.codeChange.file }}</span>
              <span class="change-stats">
                <span class="additions">+{{ message.codeChange.additions }}</span>
                <span class="deletions">-{{ message.codeChange.deletions }}</span>
                <button class="view-change-btn" @click="viewCodeChange(message.codeChange)">查看变更</button>
              </span>
            </div>
          </div>
          
          <div v-if="message.toolCall" class="tool-call-card">
            <div class="tool-header">
              <span class="tool-icon">🔧</span>
              <span class="tool-name">{{ message.toolCall.name }}</span>
            </div>
            <div class="tool-content">
              <pre>{{ message.toolCall.content }}</pre>
            </div>
          </div>
          
          <div v-if="message.executionResult" class="execution-result">
            <div class="result-header">
              <span class="result-icon">▶️</span>
              <span class="result-title">执行结果</span>
              <span :class="['result-status', message.executionResult.success ? 'success' : 'error']">
                {{ message.executionResult.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="result-output">
              <pre>{{ message.executionResult.output }}</pre>
            </div>
          </div>
          
          <div v-if="message.preview" class="preview-card">
            <div class="preview-header">
              <span class="preview-icon">👁️</span>
              <span class="preview-title">预览</span>
            </div>
            <div class="preview-content" v-html="message.preview.content"></div>
          </div>
          
          <div v-if="!message.codeChange && !message.toolCall && !message.executionResult && !message.preview" class="text-content">
            <p>{{ message.content }}</p>
            <div v-if="message.code" class="code-block">
              <div class="code-header">
                <span class="code-lang">{{ message.codeLang || 'python' }}</span>
                <button class="copy-btn" @click="copyCode(message.code)">📋</button>
                <button class="run-btn" @click="runCode(message.code)">▶️</button>
              </div>
              <pre><code>{{ message.code }}</code></pre>
            </div>
          </div>
        </div>
        
        <div class="message-meta">
          <span class="sender">{{ message.isUser ? '我' : 'LivingTree' }}</span>
          <span class="timestamp">{{ message.timestamp }}</span>
        </div>
      </div>
      
      <div v-if="isLoading" class="loading-indicator">
        <div class="thinking-avatar">🧠</div>
        <div class="loading-content">
          <div class="loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="loading-text">{{ loadingText }}</span>
          <div v-if="currentTask" class="current-task">
            <span>正在: {{ currentTask }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="chat-input">
      <div class="input-actions-left">
        <button class="action-btn" title="提及" @click="showMentionMenu = !showMentionMenu">
          <span>@</span>
          <div v-if="showMentionMenu" class="mention-menu">
            <div 
              v-for="skill in skills" 
              :key="skill.id"
              class="mention-item"
              @click="insertSkill(skill)"
            >
              <span class="skill-icon">{{ skill.icon }}</span>
              <span class="skill-name">{{ skill.name }}</span>
            </div>
          </div>
        </button>
        <button class="action-btn" title="标签"><span>#</span></button>
        <button class="action-btn" title="附件" @click="triggerFileUpload">
          <span>📎</span>
        </button>
        <button class="action-btn" title="模板" @click="showTemplateMenu = !showTemplateMenu">
          <span>📋</span>
          <div v-if="showTemplateMenu" class="template-menu">
            <div class="template-grid">
              <div 
                v-for="template in templates" 
                :key="template.id"
                class="template-card"
                @click="applyTemplate(template)"
              >
                <span class="template-icon-large">{{ template.icon }}</span>
                <span class="template-name">{{ template.name }}</span>
                <span class="template-desc">{{ template.desc }}</span>
              </div>
            </div>
          </div>
        </button>
      </div>
      <div class="input-main">
        <textarea 
          v-model="inputMessage"
          class="input-field"
          :placeholder="inputPlaceholder"
          rows="2"
          @keydown.ctrl.enter="sendMessage"
          @keydown.meta.enter="sendMessage"
        ></textarea>
        <div v-if="isRecording" class="recording-indicator">
          <span class="recording-dot"></span>
          <span>录音中...</span>
        </div>
      </div>
      <div class="input-actions-right">
        <select class="model-select" v-model="selectedModel">
          <option value="doubao">Doubao-Speed</option>
          <option value="seed">Seed-Code</option>
          <option value="deepseek">DeepSeek-V4</option>
        </select>
        <button class="action-btn" title="更多"><span>✨</span></button>
        <button class="action-btn" title="清除"><span>🗑️</span></button>
        <button class="send-btn" @click="sendMessage">➤</button>
      </div>
      <input type="file" id="file-upload" class="file-upload" @change="handleFileUpload" multiple>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onMounted, onUnmounted } from 'vue';

const emit = defineEmits(['sendMessage', 'codeGenerated', 'runCode']);

const messages = ref([
  {
    id: 1,
    isUser: false,
    content: '您好！我是 LivingTree AI 助手。请问我可以帮您做什么？',
    timestamp: new Date().toLocaleTimeString(),
    code: null,
    thought: false,
    codeChange: null,
    toolCall: null,
    executionResult: null,
    preview: null
  }
]);

const inputMessage = ref('');
const isLoading = ref(false);
const messagesContainer = ref(null);
const isRecording = ref(false);
const currentMode = ref('code');
const selectedModel = ref('seed');
const showMentionMenu = ref(false);
const showTemplateMenu = ref(false);
const loadingText = ref('LivingTree 正在思考...');
const currentTask = ref('');

const skills = ref([
  { id: 'file', name: '文件操作', icon: '📁' },
  { id: 'search', name: '搜索', icon: '🔍' },
  { id: 'code', name: '代码生成', icon: '💻' },
  { id: 'analyze', name: '数据分析', icon: '📊' },
  { id: 'summarize', name: '总结', icon: '📝' },
  { id: 'translate', name: '翻译', icon: '🌐' }
]);

const templates = ref([
  { id: 'paper', name: '论文研读', icon: '📚', desc: '研读在线论文，产出论文综述' },
  { id: 'ppt', name: '生成PPT', icon: '📊', desc: '调研分析，生成汇报PPT' },
  { id: 'analysis', name: '数据挖掘', icon: '🔍', desc: '挖掘数据，分析发展趋势' },
  { id: 'content', name: '内容创作', icon: '✍️', desc: '根据资料，撰写宣传文稿' },
  { id: 'report', name: '环评报告', icon: '📄', desc: '生成环境影响评价报告' },
  { id: 'meeting', name: '会议纪要', icon: '📋', desc: '整理会议内容' },
  { id: 'email', name: '邮件模板', icon: '📧', desc: '撰写专业邮件' },
  { id: 'code', name: '代码生成', icon: '💻', desc: '编写高质量代码' }
]);

const inputPlaceholder = computed(() => {
  return currentMode.value === 'mtc' 
    ? '输入您的需求，如"帮我写一份数据分析报告"...'
    : '输入代码需求，如"帮我写一个Python爬虫"...';
});

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return;
  
  const userMessage = {
    id: Date.now(),
    isUser: true,
    content: inputMessage.value,
    timestamp: new Date().toLocaleTimeString(),
    code: null,
    thought: false,
    codeChange: null,
    toolCall: null,
    executionResult: null,
    preview: null
  };
  
  messages.value.push(userMessage);
  inputMessage.value = '';
  scrollToBottom();
  
  isLoading.value = true;
  
  await simulateThinking();
  
  const aiResponse = generateResponse(userMessage.content);
  messages.value.push(aiResponse);
  isLoading.value = false;
  scrollToBottom();
  
  if (aiResponse.code) {
    emit('codeGenerated', aiResponse.code);
  }
  
  emit('sendMessage', {
    userMessage: userMessage.content,
    aiResponse: aiResponse.content
  });
};

const simulateThinking = async () => {
  const tasks = ['分析问题...', '检索知识...', '生成方案...', '优化结果...'];
  for (const task of tasks) {
    currentTask.value = task;
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  currentTask.value = '';
};

const generateResponse = (query) => {
  const responses = [
    {
      content: '我来帮您分析这个问题。根据我的理解，您需要帮助完成以下任务：',
      code: null,
      thought: true,
      codeChange: null,
      toolCall: null,
      executionResult: null,
      preview: null
    },
    {
      content: '这是一个很好的问题！让我为您生成相关代码：',
      code: `def hello_world():
    """打印欢迎信息"""
    print("Hello, LivingTree!")
    return "Success"

if __name__ == "__main__":
    hello_world()`,
      codeLang: 'python',
      thought: false,
      codeChange: {
        file: 'client/src/presentation/web_ui/src/components/AIAssistant.vue',
        additions: 5,
        deletions: 2
      },
      toolCall: null,
      executionResult: null,
      preview: null
    },
    {
      content: '',
      code: null,
      thought: true,
      codeChange: {
        file: 'client/src/presentation/web_ui/src/components/CodeEditor.vue',
        additions: 1,
        deletions: 1
      },
      toolCall: null,
      executionResult: null,
      preview: null
    },
    {
      content: '已完成代码修改！执行结果如下：',
      code: null,
      thought: false,
      codeChange: null,
      toolCall: null,
      executionResult: {
        success: true,
        output: '>>> Hello, LivingTree!\n>>> Success'
      },
      preview: null
    },
    {
      content: '这是生成的报告预览：',
      code: null,
      thought: false,
      codeChange: null,
      toolCall: null,
      executionResult: null,
      preview: {
        content: '<h3>环境影响评价报告</h3><p>项目概况：化工厂建设项目</p><p>评价等级：一级</p><p>评价范围：水环境、大气环境、声环境</p>'
      }
    }
  ];
  
  const randomIndex = Math.floor(Math.random() * responses.length);
  return {
    id: Date.now() + 1,
    isUser: false,
    ...responses[randomIndex],
    timestamp: new Date().toLocaleTimeString()
  };
};

const toggleVoiceInput = () => {
  isRecording.value = !isRecording.value;
  if (isRecording.value) {
    loadingText.value = '正在录音...';
  } else {
    loadingText.value = 'LivingTree 正在思考...';
  }
};

const triggerFileUpload = () => {
  document.getElementById('file-upload').click();
};

const handleFileUpload = (event) => {
  const files = event.target.files;
  if (files.length > 0) {
    const fileNames = Array.from(files).map(f => f.name).join(', ');
    inputMessage.value = `已上传文件: ${fileNames}\n`;
  }
  event.target.value = '';
};

const insertSkill = (skill) => {
  inputMessage.value += `@${skill.name} `;
  showMentionMenu.value = false;
};

const applyTemplate = (template) => {
  const templateContents = {
    paper: '帮我研读这篇论文并生成综述：\n- 论文链接/内容：\n- 需要分析的重点：\n- 输出格式要求：',
    ppt: '帮我生成一份汇报PPT：\n- 主题：\n- 目标受众：\n- 需要包含的要点：',
    analysis: '帮我分析数据并发现趋势：\n- 数据来源：\n- 分析目标：\n- 需要输出的图表类型：',
    content: '帮我撰写宣传文稿：\n- 产品/主题：\n- 目标受众：\n- 风格要求：',
    report: '帮我生成一份环评报告，包含以下章节：\n1. 项目概况\n2. 环境现状调查\n3. 影响预测\n4. 环保措施',
    meeting: '帮我整理会议纪要：\n- 会议主题：\n- 参会人员：\n- 主要内容：',
    email: '帮我写一封邮件：\n- 收件人：\n- 主题：\n- 内容：',
    code: '帮我编写代码：\n- 功能需求：\n- 编程语言：\n- 输入输出示例：'
  };
  inputMessage.value = templateContents[template.id] || '';
  showTemplateMenu.value = false;
};

const copyCode = (code) => {
  navigator.clipboard.writeText(code);
};

const runCode = (code) => {
  emit('runCode', code);
};

const viewCodeChange = (codeChange) => {
  console.log('查看代码变更:', codeChange);
};

onMounted(() => {
  scrollToBottom();
});

onUnmounted(() => {
});
</script>

<style scoped>
.ai-assistant {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f6f6f6;
  border-bottom: 1px solid #e5e5e5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.solo-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 4px;
  color: white;
  font-size: 12px;
  font-weight: 600;
}

.solo-icon {
  font-size: 14px;
}

.project-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.dropdown-btn {
  background: none;
  border: none;
  font-size: 10px;
  color: #999;
  cursor: pointer;
}

.mode-switch {
  display: flex;
  background: #e5e7eb;
  border-radius: 4px;
  padding: 2px;
}

.mode-btn {
  padding: 4px 12px;
  border: none;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: #666;
  transition: all 0.2s;
}

.mode-btn.active {
  background: white;
  color: #667eea;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.header-right {
  display: flex;
  gap: 4px;
}

.tool-btn {
  padding: 6px 8px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.tool-btn:hover {
  background: rgba(0, 0, 0, 0.05);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #fafafa;
}

.message {
  margin-bottom: 16px;
}

.thought-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: #666;
  font-size: 12px;
}

.thought-icon {
  font-size: 14px;
}

.message-content {
  background: white;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.code-change-card {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 10px;
  border: 1px solid #e9ecef;
}

.change-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-icon {
  font-size: 14px;
}

.file-path {
  flex: 1;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: #333;
}

.change-stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.additions {
  color: #22c55e;
  font-weight: 600;
  font-size: 12px;
}

.deletions {
  color: #ef4444;
  font-weight: 600;
  font-size: 12px;
}

.view-change-btn {
  padding: 4px 10px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.tool-call-card {
  background: #e0f2fe;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #0ea5e9;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.tool-icon {
  font-size: 14px;
}

.tool-name {
  font-size: 13px;
  font-weight: 600;
  color: #0369a1;
}

.tool-content pre {
  margin: 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
}

.execution-result {
  background: #f0fdf4;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #10b981;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.result-icon {
  font-size: 14px;
}

.result-title {
  font-size: 13px;
  font-weight: 600;
  color: #065f46;
}

.result-status {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.result-status.success {
  background: #d1fae5;
  color: #065f46;
}

.result-status.error {
  background: #fee2e2;
  color: #991b1b;
}

.result-output pre {
  margin: 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
}

.preview-card {
  background: #fef3c7;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #f59e0b;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.preview-icon {
  font-size: 14px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
}

.preview-content {
  font-size: 13px;
  color: #374151;
}

.text-content p {
  margin: 0;
  line-height: 1.6;
  font-size: 14px;
  color: #333;
}

.code-block {
  margin-top: 12px;
  background: #1e1e1e;
  border-radius: 6px;
  overflow: hidden;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #3d3d3d;
}

.code-lang {
  font-size: 12px;
  color: #858585;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.copy-btn, .run-btn {
  padding: 4px 8px;
  background: #3d3d3d;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  margin-left: 8px;
}

.copy-btn:hover, .run-btn:hover {
  background: #4d4d4d;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
  padding-left: 8px;
}

.sender {
  font-size: 12px;
  font-weight: 500;
  color: #666;
}

.timestamp {
  font-size: 11px;
  color: #999;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 8px;
}

.thinking-avatar {
  font-size: 32px;
}

.loading-content {
  flex: 1;
}

.loading-dots {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: loading 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes loading {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.loading-text {
  font-size: 13px;
  color: #666;
  display: block;
}

.current-task {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.chat-input {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px;
  background: white;
  border-top: 1px solid #e5e5e5;
}

.input-actions-left, .input-actions-right {
  display: flex;
  gap: 4px;
}

.action-btn {
  position: relative;
  padding: 8px;
  background: #f3f4f6;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.action-btn:hover {
  background: #e5e7eb;
}

.mention-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 8px;
  min-width: 180px;
  z-index: 100;
}

.template-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 16px;
  min-width: 400px;
  z-index: 100;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.template-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  background: #f3f4f6;
  border-color: #667eea;
  transform: translateY(-2px);
}

.template-icon-large {
  font-size: 24px;
}

.template-desc {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.4;
}

.mention-item, .template-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.mention-item:hover, .template-item:hover {
  background: #f3f4f6;
}

.skill-icon, .template-icon {
  font-size: 16px;
}

.skill-name, .template-name {
  font-size: 13px;
  color: #374151;
}

.input-main {
  flex: 1;
  position: relative;
}

.input-field {
  width: 100%;
  padding: 10px 14px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #333;
  font-size: 14px;
  resize: none;
  outline: none;
  min-height: 44px;
}

.input-field:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.input-field::placeholder {
  color: #9ca3af;
}

.recording-indicator {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #ef4444;
  font-size: 12px;
}

.recording-dot {
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.model-select {
  padding: 8px 12px;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
  color: #374151;
  outline: none;
  cursor: pointer;
}

.send-btn {
  padding: 10px 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: transform 0.2s;
}

.send-btn:hover {
  transform: translateY(-1px);
}

.file-upload {
  display: none;
}
</style>