<template>
  <div class="requirement-clarifier">
    <!-- 头部 -->
    <div class="header">
      <h1>智能需求澄清助手</h1>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <div class="stage-indicators">
        <div 
          v-for="(stage, index) in stages" 
          :key="index"
          class="stage-indicator"
          :class="{ active: currentStage >= index, completed: currentStage > index }"
        >
          <span class="stage-number">{{ index + 1 }}</span>
          <span class="stage-name">{{ stage }}</span>
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 对话历史 -->
      <div class="conversation-history" ref="historyRef">
        <div 
          v-for="(turn, index) in conversationHistory" 
          :key="index"
          class="message"
          :class="{ user: turn.isUser }"
        >
          <div class="avatar">
            <span>{{ turn.isUser ? '👤' : '🤖' }}</span>
          </div>
          <div class="message-content">
            <div class="message-text">{{ turn.text }}</div>
            <div class="message-time">{{ turn.timestamp }}</div>
          </div>
        </div>
      </div>

      <!-- 动态表单区域 -->
      <div v-if="currentForm" class="dynamic-form">
        <div v-for="field in currentForm.fields" :key="field.label" class="form-field">
          <label>{{ field.label }}<span v-if="field.required" class="required">*</span></label>
          
          <!-- 文本输入 -->
          <input 
            v-if="field.type === 'text_input'"
            v-model="formData[field.label]"
            :type="field.inputType || 'text'"
            :placeholder="field.placeholder"
            class="form-input"
          />
          
          <!-- 多选框 -->
          <div v-else-if="field.type === 'multi_select'" class="multi-select">
            <label 
              v-for="option in field.options" 
              :key="option.value"
              class="checkbox-label"
            >
              <input 
                type="checkbox" 
                :value="option.value"
                v-model="selectedOptions[field.label]"
              />
              <span>{{ option.label }}</span>
            </label>
          </div>
          
          <!-- 文件上传 -->
          <div v-else-if="field.type === 'file_upload'" class="file-upload">
            <input type="file" :accept="field.accept.join(',')" @change="handleFileUpload" />
            <span class="upload-hint">支持: {{ field.accept.join(', ') }}</span>
          </div>
          
          <!-- 下拉选择 -->
          <select v-else-if="field.type === 'select'" v-model="formData[field.label]" class="form-select">
            <option value="">请选择</option>
            <option v-for="option in field.options" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          
          <!-- 文本域 -->
          <textarea 
            v-else-if="field.type === 'textarea'"
            v-model="formData[field.label]"
            :rows="field.rows || 3"
            :placeholder="field.placeholder"
            class="form-textarea"
          ></textarea>
        </div>
        
        <div class="form-actions">
          <button class="btn btn-secondary" @click="goBack">返回上一步</button>
          <button class="btn btn-primary" @click="submitForm">保存并继续</button>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-wrapper">
          <input 
            v-model="userInput"
            type="text" 
            placeholder="请输入您的需求描述..."
            class="user-input"
            @keyup.enter="sendMessage"
          />
          <button class="send-btn" @click="sendMessage">
            <span>发送</span>
          </button>
        </div>
        
        <!-- 快捷操作 -->
        <div class="quick-actions">
          <button class="quick-btn" @click="uploadFile">📁 上传文件</button>
          <button class="quick-btn" @click="showTemplates">📋 需求模板</button>
          <button class="quick-btn" @click="clearConversation">🗑️ 清空对话</button>
        </div>
      </div>
    </div>

    <!-- 侧边栏 -->
    <div class="sidebar">
      <!-- 需求摘要 -->
      <div class="panel">
        <h3>📋 需求摘要</h3>
        <div class="summary-content">
          <div v-if="requirementSummary" class="summary-item">
            <span class="summary-label">核心需求</span>
            <span class="summary-value">{{ requirementSummary }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">功能点</span>
            <span class="summary-value">{{ functionalCount }} 个</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">非功能需求</span>
            <span class="summary-value">{{ nonFunctionalCount }} 项</span>
          </div>
        </div>
      </div>

      <!-- 验收标准 -->
      <div class="panel">
        <h3>✅ 验收标准</h3>
        <div v-if="acceptanceCriteria.length > 0" class="criteria-list">
          <div v-for="(criteria, index) in acceptanceCriteria" :key="index" class="criteria-item">
            {{ index + 1 }}. {{ criteria }}
          </div>
        </div>
        <div v-else class="empty-state">暂无验收标准</div>
      </div>

      <!-- 生成按钮 -->
      <button class="generate-btn" @click="generateDocument">
        📄 生成需求文档
      </button>
    </div>
  </div>
</template>

<script setup>import { ref, reactive, computed, onMounted, nextTick } from 'vue';
import { get_conversation_orchestrator } from '@/business/ai_pipeline';
// 对话编排器
const orchestrator = get_conversation_orchestrator();
// 响应式状态
const conversationHistory = ref([]);
const userInput = ref('');
const currentStage = ref(0);
const conversationId = ref('');
// 表单相关
const currentForm = ref(null);
const formData = reactive({});
const selectedOptions = reactive({});
// 摘要数据
const requirementSummary = ref('');
const functionalCount = ref(0);
const nonFunctionalCount = ref(0);
const acceptanceCriteria = ref([]);
// 阶段定义
const stages = [
 '需求探索',
 '上下文建立',
 '深度挖掘',
 '规格化',
 '确认与生成'
];
// 进度百分比
const progressPercent = computed(() => {
 return ((currentStage.value + 1) / stages.length) * 100;
});
// 滚动到最新消息
const historyRef = ref(null);
const scrollToBottom = async () => {
 await nextTick();
 if (historyRef.value) {
 historyRef.value.scrollTop = historyRef.value.scrollHeight;
 }
};
// 发送消息
const sendMessage = async () => {
 if (!userInput.value.trim())
 return;
 // 添加用户消息
 conversationHistory.value.push({
 text: userInput.value,
 isUser: true,
 timestamp: new Date().toLocaleTimeString()
 });
 const input = userInput.value;
 userInput.value = '';
 await scrollToBottom();
 // 处理用户输入
 const result = await orchestrator.process_user_input(conversationId.value, input);
 // 添加助手回复
 conversationHistory.value.push({
 text: result.response,
 isUser: false,
 timestamp: new Date().toLocaleTimeString()
 });
 // 更新状态
 if (result.next_state) {
 updateStage(result.next_state);
 }
 // 更新上下文
 if (result.context_update) {
 updateContext(result.context_update);
 }
 // 检查是否需要显示表单
 if (result.form_schema) {
 currentForm.value = result.form_schema;
 }
 else {
 currentForm.value = null;
 }
 await scrollToBottom();
};
// 更新阶段
const updateStage = (state) => {
 const stateOrder = [
 'initial',
 'exploring',
 'context_building',
 'deep_dive',
 'specification',
 'confirming',
 'complete'
 ];
 const index = stateOrder.indexOf(state.value);
 if (index > 0) {
 currentStage.value = Math.min(index - 1, stages.length - 1);
 }
};
// 更新上下文摘要
const updateContext = (update) => {
 if (update.requirement) {
 requirementSummary.value = update.requirement;
 }
 if (update.functional_count) {
 functionalCount.value = update.functional_count;
 }
};
// 表单相关
const submitForm = () => {
 // 收集表单数据
 const data = { ...formData };
 // 处理多选框
 for (const key in selectedOptions) {
 data[key] = selectedOptions[key];
 }
 // 发送表单数据
 sendMessage(JSON.stringify(data));
};
const goBack = () => {
 currentForm.value = null;
};
// 文件上传
const handleFileUpload = (event) => {
 const file = event.target.files[0];
 if (file) {
 sendMessage(`📎 上传文件: ${file.name}`);
 }
};
const uploadFile = () => {
 const input = document.createElement('input');
 input.type = 'file';
 input.accept = '.pdf,.docx,.jpg,.png';
 input.onchange = handleFileUpload;
 input.click();
};
// 模板
const showTemplates = () => {
 const templates = [
 { name: '用户管理模块', desc: '包含用户注册、登录、权限管理' },
 { name: '订单系统', desc: '订单创建、支付、发货流程' },
 { name: '数据报表', desc: '数据可视化、图表展示' }
 ];
 alert(`可用模板:\n\n${templates.map(t => `${t.name}: ${t.desc}`).join('\n')}`);
};
// 清空对话
const clearConversation = () => {
 if (confirm('确定要清空对话吗？')) {
 conversationHistory.value = [];
 currentStage.value = 0;
 requirementSummary.value = '';
 functionalCount.value = 0;
 nonFunctionalCount.value = 0;
 acceptanceCriteria.value = [];
 conversationId.value = orchestrator.start_conversation('current_user');
 // 添加欢迎消息
 conversationHistory.value.push({
 text: '您好！我是您的需求分析助手。请描述您的需求，我会帮助您逐步澄清并生成完整的需求文档。',
 isUser: false,
 timestamp: new Date().toLocaleTimeString()
 });
 }
};
// 生成文档
const generateDocument = async () => {
 const context = orchestrator.get_conversation_context(conversationId.value);
 if (context) {
 conversationHistory.value.push({
 text: '正在生成需求文档...',
 isUser: false,
 timestamp: new Date().toLocaleTimeString()
 });
 await scrollToBottom();
 // 模拟文档生成
 setTimeout(() => {
 conversationHistory.value.push({
 text: `## 需求规格说明书\n\n### 1. 项目概述\n根据对话分析，您需要开发一个新功能模块。\n\n### 2. 功能需求\n已收集到 ${functionalCount.value} 个功能点。\n\n### 3. 验收标准\n${acceptanceCriteria.value.map((c, i) => `${i + 1}. ${c}`).join('\n')}\n\n### 4. 成功指标\n待补充。`,
 isUser: false,
 timestamp: new Date().toLocaleTimeString()
 });
 scrollToBottom();
 }, 1000);
 }
};
// 初始化
onMounted(() => {
 conversationId.value = orchestrator.start_conversation('current_user');
 // 添加欢迎消息
 conversationHistory.value.push({
 text: '您好！我是您的需求分析助手。请描述您的需求，我会帮助您逐步澄清并生成完整的需求文档。',
 isUser: false,
 timestamp: new Date().toLocaleTimeString()
 });
});
</script>

<style scoped>
.requirement-clarifier {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 30px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.header h1 {
  margin: 0 0 15px 0;
  font-size: 24px;
}

.progress-bar {
  height: 4px;
  background: rgba(255,255,255,0.3);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 15px;
}

.progress-fill {
  height: 100%;
  background: white;
  transition: width 0.5s ease;
}

.stage-indicators {
  display: flex;
  gap: 20px;
}

.stage-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.5;
  transition: all 0.3s ease;
}

.stage-indicator.active {
  opacity: 1;
}

.stage-indicator.completed .stage-number {
  background: #4ade80;
}

.stage-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255,255,255,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.stage-name {
  font-size: 12px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.conversation-history {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 15px;
  padding-right: 10px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
}

.message.user {
  margin-left: auto;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message-content {
  background: white;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message-text {
  font-size: 14px;
  line-height: 1.5;
}

.message-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.message.user .message-time {
  color: rgba(255,255,255,0.7);
}

.dynamic-form {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin: 15px 0;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.form-field {
  margin-bottom: 16px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: #667eea;
}

.form-textarea {
  resize: vertical;
}

.multi-select {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 6px 12px;
  background: #f1f5f9;
  border-radius: 20px;
  transition: all 0.2s;
}

.checkbox-label:hover {
  background: #e2e8f0;
}

.checkbox-label input {
  width: 16px;
  height: 16px;
}

.file-upload {
  border: 2px dashed #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}

.file-upload:hover {
  border-color: #667eea;
}

.file-upload input {
  display: none;
}

.upload-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
  display: block;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: #f1f5f9;
  color: #64748b;
}

.btn-secondary:hover {
  background: #e2e8f0;
}

.input-area {
  background: white;
  padding: 15px 20px;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
}

.input-wrapper {
  display: flex;
  gap: 10px;
}

.user-input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.user-input:focus {
  outline: none;
  border-color: #667eea;
}

.send-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.quick-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.quick-btn {
  padding: 6px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.quick-btn:hover {
  background: #e2e8f0;
}

.sidebar {
  width: 300px;
  background: white;
  padding: 20px;
  overflow-y: auto;
  border-left: 1px solid #e2e8f0;
}

.panel {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.panel h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
}

.summary-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.summary-value {
  font-size: 12px;
  font-weight: 500;
  color: #1e293b;
}

.criteria-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.criteria-item {
  font-size: 12px;
  padding: 6px 10px;
  background: #ecfdf5;
  border-radius: 6px;
  color: #059669;
}

.empty-state {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 10px;
}

.generate-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.generate-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}
</style>