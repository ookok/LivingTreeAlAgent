<template>
  <div id="app" class="app-container">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-icon">🌱</span>
          <span class="logo-text">环评智能工作台</span>
        </div>
      </div>
      <div class="header-center">
        <div class="evolution-indicator" :class="evolutionStage">
          <span class="pulse"></span>
          <span>{{ evolutionStageLabel }}</span>
        </div>
      </div>
      <div class="header-right">
        <button class="nav-btn" @click="refreshUI">🔄 刷新</button>
        <button class="nav-btn" @click="showStats">📊 统计</button>
        <button class="nav-btn" @click="showSettings">⚙️ 设置</button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <div class="content-layout">
        <!-- 左侧：对话区域 -->
        <div class="conversation-panel">
          <div class="conversation-header">
            <h2>对话</h2>
            <span class="message-count">{{ messages.length }} 条消息</span>
          </div>
          
          <div class="message-list" ref="messageList">
            <div
              v-for="(message, index) in messages"
              :key="index"
              class="message"
              :class="{ user: message.isUser, ai: !message.isUser }"
            >
              <div class="message-header">
                <span class="sender">{{ message.sender }}</span>
                <span class="timestamp">{{ message.timestamp }}</span>
              </div>
              <div class="message-content">
                <p>{{ message.content }}</p>
                
                <!-- 动态渲染的UI -->
                <DynamicRenderer
                  v-if="message.uiSchema"
                  :schema="message.uiSchema"
                  @componentClick="handleComponentClick"
                  @formSubmit="handleFormSubmit"
                  @valueChange="handleValueChange"
                />
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <input
              v-model="userInput"
              type="text"
              placeholder="输入您的需求..."
              class="user-input"
              @keyup.enter="sendMessage"
            />
            <button class="send-btn" @click="sendMessage">发送</button>
          </div>
        </div>

        <!-- 右侧：控制面板 -->
        <div class="control-panel">
          <!-- 进化指标 -->
          <div class="panel">
            <h3>📈 进化指标</h3>
            <div class="metrics-grid">
              <div class="metric-item">
                <div class="metric-circle" :style="{ background: getMetricColor(metrics.compliance_score) }">
                  {{ metrics.compliance_score }}
                </div>
                <span>合规性</span>
              </div>
              <div class="metric-item">
                <div class="metric-circle" :style="{ background: getMetricColor(metrics.efficiency_score) }">
                  {{ metrics.efficiency_score }}
                </div>
                <span>效率</span>
              </div>
              <div class="metric-item">
                <div class="metric-circle" :style="{ background: getMetricColor(metrics.quality_score) }">
                  {{ metrics.quality_score }}
                </div>
                <span>质量</span>
              </div>
            </div>
          </div>

          <!-- 学习统计 -->
          <div class="panel">
            <h3>🧠 学习统计</h3>
            <div class="stats-list">
              <div class="stat-item">
                <span class="stat-label">学习周期</span>
                <span class="stat-value">{{ learningStats.total_learning_cycles || 0 }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">发现模式</span>
                <span class="stat-value">{{ learningStats.patterns_discovered || 0 }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">更新策略</span>
                <span class="stat-value">{{ learningStats.strategies_updated || 0 }}</span>
              </div>
            </div>
          </div>

          <!-- 推荐操作 -->
          <div class="panel">
            <h3>💡 推荐操作</h3>
            <div class="suggestions-list">
              <button
                v-for="(suggestion, index) in suggestions"
                :key="index"
                class="suggestion-btn"
                @click="executeSuggestion(suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部状态栏 -->
    <footer class="footer">
      <span class="footer-text">AI-Centric Pipeline v1.0</span>
      <span class="footer-status">系统在线</span>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import DynamicRenderer from './components/DynamicRenderer.vue';
import { useBackend } from './utils/backend';

const backend = useBackend;

// 响应式状态
const messages = ref([]);
const userInput = ref('');
const messageList = ref(null);

// 指标数据
const metrics = ref({
  compliance_score: 75,
  efficiency_score: 68,
  quality_score: 82
});

// 学习统计
const learningStats = ref({
  total_learning_cycles: 0,
  patterns_discovered: 0,
  strategies_updated: 0
});

// 推荐操作
const suggestions = ref(['上传文件', '填写表单', '检索知识', '生成报告']);

// 进化阶段
const evolutionStage = ref('pattern_discovery');

const evolutionStageLabel = computed(() => {
  const stages = {
    seed: '种子期',
    imitation: '模仿学习期',
    pattern_discovery: '模式发现期',
    proactive_optimization: '主动优化期'
  };
  return stages[evolutionStage.value] || '未知';
});

// 获取指标颜色
function getMetricColor(score) {
  if (score >= 80) return 'linear-gradient(135deg, #10b981, #059669)';
  if (score >= 60) return 'linear-gradient(135deg, #f59e0b, #d97706)';
  return 'linear-gradient(135deg, #ef4444, #dc2626)';
}

// 发送消息
async function sendMessage() {
  if (!userInput.value.trim()) return;

  // 添加用户消息
  messages.value.push({
    id: Date.now(),
    sender: '用户',
    content: userInput.value,
    isUser: true,
    timestamp: new Date().toLocaleTimeString()
  });

  const inputText = userInput.value;
  userInput.value = '';

  // 滚动到底部
  await nextTick();
  scrollToBottom();

  // 记录行为
  await backend.recordBehavior('default_user', {
    type: 'message_sent',
    data: { content: inputText }
  });

  // 获取AI响应
  await getAIResponse(inputText);
}

// 获取AI响应
async function getAIResponse(text) {
  try {
    // 生成动态UI
    const uiSchema = await backend.generateUI({ text });
    
    // 获取进化指标
    const newMetrics = await backend.getEvolutionMetrics('default_user');
    if (newMetrics) {
      metrics.value = newMetrics;
      evolutionStage.value = newMetrics.evolution_stage || 'pattern_discovery';
    }

    // 获取学习统计
    const stats = await backend.getLearningStats('default_user');
    if (stats) {
      learningStats.value = stats;
    }

    // 添加AI消息
    messages.value.push({
      id: Date.now() + 1,
      sender: 'AI助手',
      content: '根据您的需求，我为您生成了以下内容：',
      isUser: false,
      timestamp: new Date().toLocaleTimeString(),
      uiSchema: uiSchema
    });

    // 滚动到底部
    await nextTick();
    scrollToBottom();

  } catch (error) {
    console.error('获取AI响应失败:', error);
    messages.value.push({
      id: Date.now() + 1,
      sender: 'AI助手',
      content: '抱歉，处理您的请求时出现错误。',
      isUser: false,
      timestamp: new Date().toLocaleTimeString()
    });
  }
}

// 滚动到底部
function scrollToBottom() {
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight;
  }
}

// 处理组件点击
async function handleComponentClick(data) {
  await backend.recordBehavior('default_user', {
    type: 'suggestion_clicked',
    data: data
  });
}

// 处理表单提交
async function handleFormSubmit(data) {
  await backend.recordBehavior('default_user', {
    type: 'form_submitted',
    data: data
  });
}

// 处理值变化
async function handleValueChange(data) {
  await backend.handleEvent('value_change', data);
}

// 执行推荐操作
async function executeSuggestion(suggestion) {
  userInput.value = suggestion;
}

// 刷新UI
async function refreshUI() {
  // 重新加载页面或刷新数据
  window.location.reload();
}

// 显示统计
async function showStats() {
  const stats = await backend.getLearningStats('default_user');
  alert(JSON.stringify(stats, null, 2));
}

// 显示设置
function showSettings() {
  alert('设置功能开发中...');
}

// 初始化
onMounted(async () => {
  // 添加欢迎消息
  messages.value.push({
    id: 1,
    sender: 'AI助手',
    content: '您好！我是您的环评智能助手。请描述您的需求，我来帮您处理。',
    isUser: false,
    timestamp: new Date().toLocaleTimeString()
  });

  // 获取初始指标
  const initialMetrics = await backend.getEvolutionMetrics('default_user');
  if (initialMetrics) {
    metrics.value = initialMetrics;
    evolutionStage.value = initialMetrics.evolution_stage || 'pattern_discovery';
  }

  // 获取初始学习统计
  const initialStats = await backend.getLearningStats('default_user');
  if (initialStats) {
    learningStats.value = initialStats;
  }
});
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f7fa;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 头部 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: linear-gradient(135deg, #1e3a8a, #3b82f6);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
}

.evolution-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  font-size: 13px;
}

.evolution-indicator .pulse {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.nav-btn {
  padding: 6px 12px;
  margin-left: 8px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* 主内容区 */
.main-content {
  flex: 1;
  overflow: hidden;
  padding: 16px;
}

.content-layout {
  display: flex;
  height: 100%;
  gap: 16px;
}

/* 对话面板 */
.conversation-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.conversation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.conversation-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.message-count {
  font-size: 12px;
  color: #9ca3af;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message {
  margin-bottom: 16px;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.message.user .message-header .sender {
  color: #3b82f6;
}

.message.ai .message-header .sender {
  color: #10b981;
}

.sender {
  font-size: 13px;
  font-weight: 500;
}

.timestamp {
  font-size: 11px;
  color: #9ca3af;
}

.message-content {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f3f4f6;
}

.message.user .message-content {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
}

.message-content p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}

/* 输入区域 */
.input-area {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}

.user-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.user-input:focus {
  border-color: #3b82f6;
}

.user-input::placeholder {
  color: #9ca3af;
}

.send-btn {
  padding: 10px 20px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border: none;
  border-radius: 20px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.send-btn:hover {
  transform: translateY(-1px);
}

/* 控制面板 */
.control-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.panel h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
}

/* 指标网格 */
.metrics-grid {
  display: flex;
  justify-content: space-around;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.metric-circle {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.metric-item span {
  font-size: 11px;
  color: #6b7280;
}

/* 统计列表 */
.stats-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f3f4f6;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

/* 推荐操作 */
.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-btn {
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(99, 102, 241, 0.1));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  color: #3b82f6;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-btn:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(99, 102, 241, 0.2));
}

/* 底部 */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  background: #f3f4f6;
  border-top: 1px solid #e5e7eb;
}

.footer-text {
  font-size: 12px;
  color: #6b7280;
}

.footer-status {
  font-size: 12px;
  color: #10b981;
}
</style>