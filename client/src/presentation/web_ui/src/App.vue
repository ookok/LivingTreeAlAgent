<template>
  <div class="app-container">
    <div class="main-layout">
      <!-- 左侧边栏 -->
      <Sidebar 
        :activeTab="store.state.activeTab" 
        :systemOnline="store.state.systemOnline"
        @navigate="handleNavigate"
      />
      
      <!-- 主内容区 -->
      <main class="main-content">
        <!-- 聊天主界面 -->
        <div v-if="store.state.activeTab === 'ide'" class="ai-native-ide">
          <!-- 顶部工具栏 -->
          <div class="ide-toolbar">
            <div class="toolbar-left">
              <div class="project-selector">
                <span class="project-icon">🌳</span>
                <span class="project-name">LivingTree AI Orchestrator</span>
                <span class="dropdown-arrow">▼</span>
              </div>
              <div class="mode-indicator">
                <span class="mode-dot"></span>
                <span>AI-Native 模式</span>
              </div>
            </div>
            <div class="toolbar-center">
              <div class="progress-bar-container">
                <div class="progress-label">任务进度</div>
                <div class="progress-bar-wrapper">
                  <div class="progress-bar-fill" :style="{ width: taskProgress + '%' }"></div>
                </div>
                <div class="progress-percent">{{ taskProgress }}%</div>
              </div>
            </div>
            <div class="toolbar-right">
              <button class="toolbar-btn" @click="toggleThinkingPanel">
                <span>🧠</span>
                <span>思考</span>
              </button>
              <button class="toolbar-btn" @click="toggleTaskChain">
                <span>🔗</span>
                <span>任务链</span>
              </button>
              <button class="toolbar-btn" @click="toggleDynamicUI">
                <span>🎨</span>
                <span>动态UI</span>
              </button>
              <button class="toolbar-btn" @click="toggleCodeDiff">
                <span>🔍</span>
                <span>代码变更</span>
              </button>
              <button class="toolbar-btn" @click="toggleLearningHistory">
                <span>📚</span>
                <span>学习记录</span>
              </button>
              <button class="toolbar-btn" @click="openFeedbackCollector()">
                <span>📝</span>
                <span>反馈</span>
              </button>
              <button class="toolbar-btn primary" @click="runProject">
                <span>▶️</span>
                <span>运行项目</span>
              </button>
            </div>
          </div>

          <!-- 主工作区 -->
          <div class="workspace">
            <!-- 左侧：聊天主界面 -->
            <div class="chat-main">
              <AIAssistant 
                @codeGenerated="handleCodeGenerated"
                @runCode="handleRunCode"
              />
            </div>
            
            <!-- 右侧：可折叠面板区域 -->
            <div :class="['panels-container', { collapsed: allPanelsClosed }]">
              <!-- AI思考过程面板 -->
              <div :class="['panel-wrapper', { hidden: !showThinkingPanel }]">
                <AIThinkingPanel />
              </div>
              
              <!-- 任务链面板 -->
              <div :class="['panel-wrapper', { hidden: !showTaskChain }]">
                <TaskChain />
              </div>
              
              <!-- 动态UI渲染面板 -->
              <div :class="['panel-wrapper', { hidden: !showDynamicUI }]">
                <DynamicUIRenderer />
              </div>
              
              <!-- 代码Diff面板 -->
              <div :class="['panel-wrapper', { hidden: !showCodeDiff }]">
                <CodeDiff />
              </div>
              
              <!-- 学习记录面板 -->
              <div :class="['panel-wrapper', { hidden: !showLearningHistory }]">
                <LearningHistory />
              </div>
              
              <!-- 面板切换器 -->
              <div class="panel-tabs">
                <button 
                  :class="['tab-btn', { active: showThinkingPanel }]"
                  @click="toggleThinkingPanel"
                >🧠</button>
                <button 
                  :class="['tab-btn', { active: showTaskChain }]"
                  @click="toggleTaskChain"
                >🔗</button>
                <button 
                  :class="['tab-btn', { active: showDynamicUI }]"
                  @click="toggleDynamicUI"
                >🎨</button>
                <button 
                  :class="['tab-btn', { active: showCodeDiff }]"
                  @click="toggleCodeDiff"
                >🔍</button>
                <button 
                  :class="['tab-btn', { active: showLearningHistory }]"
                  @click="toggleLearningHistory"
                >📚</button>
              </div>
            </div>
          </div>

          <!-- 底部执行控制台 -->
          <div class="execution-console">
            <div class="console-tabs">
              <button 
                :class="['console-tab', { active: activeConsoleTab === 'logs' }]"
                @click="activeConsoleTab = 'logs'"
              >📋 执行日志</button>
              <button 
                :class="['console-tab', { active: activeConsoleTab === 'output' }]"
                @click="activeConsoleTab = 'output'"
              >💻 终端输出</button>
              <button 
                :class="['console-tab', { active: activeConsoleTab === 'errors' }]"
                @click="activeConsoleTab = 'errors'"
              >❌ 错误信息</button>
            </div>
            <div class="console-content">
              <div v-if="activeConsoleTab === 'logs'" class="logs-panel">
                <div 
                  v-for="(log, index) in consoleLogs" 
                  :key="index"
                  :class="['log-item', log.type]"
                >
                  <span class="log-time">{{ log.time }}</span>
                  <span :class="['log-type', log.type]">{{ log.type.toUpperCase() }}</span>
                  <span class="log-message">{{ log.message }}</span>
                </div>
                <div v-if="consoleLogs.length === 0" class="empty-logs">
                  <span>等待执行任务...</span>
                </div>
              </div>
              <div v-if="activeConsoleTab === 'output'" class="output-panel">
                <pre>{{ terminalOutput }}</pre>
              </div>
              <div v-if="activeConsoleTab === 'errors'" class="errors-panel">
                <div 
                  v-for="(error, index) in errors" 
                  :key="index"
                  class="error-item"
                >
                  <span class="error-line">第 {{ error.line }} 行</span>
                  <span class="error-message">{{ error.message }}</span>
                </div>
                <div v-if="errors.length === 0" class="empty-errors">
                  <span>✓ 没有错误</span>
                </div>
              </div>
            </div>
            <div class="console-actions">
              <button class="console-btn" @click="clearConsole">🗑️ 清空</button>
              <button class="console-btn" @click="copyLogs">📋 复制</button>
              <button class="console-btn" @click="exportLogs">📤 导出</button>
              <button class="console-btn primary" @click="restartTask">🔄 重启任务</button>
            </div>
          </div>
        </div>

        <!-- 反馈收集模态框 -->
        <FeedbackCollector 
          v-if="showFeedbackCollector"
          :experience="currentExperience"
          @submit="handleFeedbackSubmit"
          @close="showFeedbackCollector = false"
        />

        <!-- 其他页面 -->
        <Dashboard 
          v-else-if="store.state.activeTab === 'dashboard'"
          :systemStatus="store.state.systemStatus"
          :apiStats="store.state.apiStats"
          :cognitiveLoad="store.state.cognitiveLoad"
          :activeSystems="store.activeSystems"
          :totalSystems="store.totalSystems"
          :getStatusClass="store.getStatusClass"
          :formatSystemName="store.formatSystemName"
          :formatStatus="store.formatStatus"
        />
        
        <Memory 
          v-else-if="store.state.activeTab === 'memory'"
          :memories="store.state.memories"
          @addMemory="handleAddMemory"
          @refreshMemory="handleRefreshMemory"
        />
        
        <Learning 
          v-else-if="store.state.activeTab === 'learning'"
          :learningTasks="store.state.learningTasks"
          :ewcStatus="store.state.ewcStatus"
        />
        
        <Reasoning 
          v-else-if="store.state.activeTab === 'reasoning'"
          :reasoningStatus="store.state.reasoningStatus"
          @executeReasoning="handleExecuteReasoning"
        />
        
        <SelfAwareness 
          v-else-if="store.state.activeTab === 'selfawareness'"
          :autonomyLevel="store.state.autonomyLevel"
          :goalStats="store.state.goalStats"
          :activeGoals="store.state.activeGoals"
          :reflectionHistory="store.state.reflectionHistory"
          :getPriorityClass="store.getPriorityClass"
          :getPriorityLabel="store.getPriorityLabel"
          @setAutonomyLevel="handleSetAutonomyLevel"
          @addGoal="handleAddGoal"
          @triggerReflection="handleTriggerReflection"
        />
        
        <MCP 
          ref="mcpRef"
          v-else-if="store.state.activeTab === 'mcp'"
          :mcpStatus="store.state.mcpStatus"
          :mcpStats="store.state.mcpStats"
          @toggleMCP="handleToggleMCP"
          @callMCPTool="handleCallMCPTool"
        />
        
        <Observability 
          v-else-if="store.state.activeTab === 'observability'"
        />
        
        <DocumentProcessor 
          v-else-if="store.state.activeTab === 'documents'"
        />
        
        <SkillPanel 
          v-else-if="store.state.activeTab === 'skills'"
        />
        
        <AutomationPanel 
          v-else-if="store.state.activeTab === 'automation'"
        />
        
        <SoftwareManager 
          v-else-if="store.state.activeTab === 'software'"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import Dashboard from './components/Dashboard.vue';
import IDE from './components/IDE.vue';
import Memory from './components/Memory.vue';
import Learning from './components/Learning.vue';
import Reasoning from './components/Reasoning.vue';
import SelfAwareness from './components/SelfAwareness.vue';
import MCP from './components/MCP.vue';
import Observability from './components/Observability.vue';
import DocumentProcessor from './components/DocumentProcessor.vue';
import SkillPanel from './components/SkillPanel.vue';
import AutomationPanel from './components/AutomationPanel.vue';
import AIAssistant from './components/AIAssistant.vue';
import AIThinkingPanel from './components/AIThinkingPanel.vue';
import TaskChain from './components/TaskChain.vue';
import DynamicUIRenderer from './components/DynamicUIRenderer.vue';
import CodeDiff from './components/CodeDiff.vue';
import LearningHistory from './components/LearningHistory.vue';
import FeedbackCollector from './components/FeedbackCollector.vue';
import SoftwareManager from './components/SoftwareManager.vue';
import { useAppStore } from './stores/appStore';
import { backendService } from './utils/backend';

const store = useAppStore();
const mcpRef = ref(null);

// 面板显示状态
const showThinkingPanel = ref(true);
const showTaskChain = ref(false);
const showDynamicUI = ref(false);
const showCodeDiff = ref(false);
const showLearningHistory = ref(false);

// 反馈收集状态
const showFeedbackCollector = ref(false);
const currentExperience = ref({
  experience_id: '',
  task_type: 'code_generation',
  task_description: '',
  success: true,
  execution_time: 25.5,
  skills_used: []
});

const activeConsoleTab = ref('logs');
const taskProgress = ref(45);

const consoleLogs = ref([
  { type: 'info', time: '10:30:01', message: '系统初始化完成' },
  { type: 'success', time: '10:30:02', message: '连接到模型服务' },
  { type: 'info', time: '10:30:03', message: '加载任务链...' },
  { type: 'info', time: '10:30:05', message: '分析用户需求: 创建员工管理系统' },
  { type: 'success', time: '10:30:08', message: '任务规划完成，共6个任务' },
  { type: 'info', time: '10:30:10', message: '开始执行: 创建项目' },
  { type: 'success', time: '10:30:15', message: '任务完成: 创建项目' },
  { type: 'info', time: '10:30:16', message: '开始执行: 生成数据模型' },
  { type: 'success', time: '10:30:22', message: '任务完成: 生成数据模型' },
  { type: 'info', time: '10:30:23', message: '开始执行: 生成API' },
]);

const terminalOutput = ref(`>>> 正在构建项目...
>>> 安装依赖: success
>>> 编译代码: success
>>> 启动开发服务器...
>>> 服务器运行在: http://localhost:5173
>>> 项目构建成功！`);

const errors = ref([]);

const allPanelsClosed = computed(() => {
  return !showThinkingPanel.value && !showTaskChain.value && !showDynamicUI.value && !showCodeDiff.value && !showLearningHistory.value;
});

const toggleThinkingPanel = () => {
  showThinkingPanel.value = !showThinkingPanel.value;
  showLearningHistory.value = false;
};

const toggleTaskChain = () => {
  showTaskChain.value = !showTaskChain.value;
  showLearningHistory.value = false;
};

const toggleDynamicUI = () => {
  showDynamicUI.value = !showDynamicUI.value;
  showLearningHistory.value = false;
};

const toggleCodeDiff = () => {
  showCodeDiff.value = !showCodeDiff.value;
  showLearningHistory.value = false;
};

const toggleLearningHistory = () => {
  showLearningHistory.value = !showLearningHistory.value;
  showThinkingPanel.value = false;
  showTaskChain.value = false;
  showDynamicUI.value = false;
  showCodeDiff.value = false;
};

const openFeedbackCollector = (experience = null) => {
  if (experience) {
    currentExperience.value = experience;
  }
  showFeedbackCollector.value = true;
};

const handleFeedbackSubmit = (feedback) => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: `收到反馈 - 评分: ${feedback.rating}星`
  });
  
  if (feedback.issues && feedback.issues.length > 0) {
    consoleLogs.value.push({
      type: 'warning',
      time: new Date().toLocaleTimeString(),
      message: `问题类型: ${feedback.issues.join(', ')}`
    });
  }
  
  if (feedback.suggestions) {
    consoleLogs.value.push({
      type: 'success',
      time: new Date().toLocaleTimeString(),
      message: `改进建议已记录`
    });
  }
};

const runProject = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '开始运行项目...'
  });
};

const clearConsole = () => {
  consoleLogs.value = [];
};

const copyLogs = () => {
  const logsText = consoleLogs.value.map(log => `${log.time} [${log.type}] ${log.message}`).join('\n');
  navigator.clipboard.writeText(logsText);
};

const exportLogs = () => {
  const logsText = consoleLogs.value.map(log => `${log.time} [${log.type}] ${log.message}`).join('\n');
  const blob = new Blob([logsText], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'console_logs.txt';
  a.click();
  URL.revokeObjectURL(url);
};

const restartTask = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '重启任务执行...'
  });
};

const handleNavigate = (tab) => {
  store.setActiveTab(tab);
};

const handleCodeGenerated = (code) => {
  consoleLogs.value.push({
    type: 'success',
    time: new Date().toLocaleTimeString(),
    message: '代码生成完成'
  });
};

const handleRunCode = (code) => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '执行代码...'
  });
};

const handleAddMemory = () => {
  backendService.addMemory('测试记忆内容', 'short');
};

const handleRefreshMemory = () => {
  backendService.refreshMemory();
};

const handleExecuteReasoning = (query, type) => {
  backendService.executeReasoning(query, type);
};

const handleSetAutonomyLevel = (level) => {
  backendService.setAutonomyLevel(level);
};

const handleAddGoal = (description, priority) => {
  backendService.addGoal(description, priority);
};

const handleTriggerReflection = () => {
  backendService.triggerReflection();
};

const handleToggleMCP = () => {
  backendService.toggleMCP();
};

const handleCallMCPTool = (toolName, params) => {
  backendService.callMCPTool(toolName, params);
};

let updateInterval = null;

onMounted(async () => {
  await backendService.init();
  
  backendService.on('onStatusUpdate', (data) => {
    store.updateSystemStatus(data);
  });
  
  backendService.on('onAPIStats', (data) => {
    store.updateAPIStats(data);
  });
  
  backendService.on('onMemoryUpdate', (data) => {
    store.updateMemory(data);
  });
  
  backendService.on('onLearningUpdate', (data) => {
    store.updateLearning(data);
  });
  
  backendService.on('onReasoningResult', (data) => {
    console.log('推理结果:', data);
  });
  
  backendService.on('onSelfAwarenessUpdate', (data) => {
    store.updateSelfAwareness(data);
  });
  
  backendService.on('onMCPStatus', (data) => {
    store.updateMCPStatus(data);
  });
  
  backendService.on('onToolResult', (data) => {
    if (mcpRef.value) {
      mcpRef.value.setToolResult(JSON.parse(data));
    }
  });
  
  updateInterval = setInterval(() => {
    backendService.getSystemStatus();
    backendService.getAPIStats();
    backendService.getMCPStatus();
  }, 5000);
});

onUnmounted(() => {
  if (updateInterval) {
    clearInterval(updateInterval);
  }
});
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  overflow: hidden;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  color: #ffffff;
}

#app {
  height: 100%;
}

.app-container {
  display: flex;
  height: 100vh;
}

.main-layout {
  display: flex;
  flex: 1;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* AI-Native IDE 样式 */
.ai-native-ide {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
}

.ide-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.project-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.project-icon {
  font-size: 18px;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.dropdown-arrow {
  font-size: 10px;
  color: #64748b;
}

.mode-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mode-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 300px;
}

.progress-label {
  font-size: 12px;
  color: #94a3b8;
}

.progress-bar-wrapper {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e, #10b981);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-percent {
  font-size: 12px;
  font-weight: 600;
  color: #22c55e;
  min-width: 40px;
  text-align: right;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.toolbar-btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
  color: white;
}

.toolbar-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.workspace {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.2);
}

.panels-container {
  width: 420px;
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.3);
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  transition: width 0.3s ease;
}

.panels-container.collapsed {
  width: 40px;
}

.panel-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  transition: opacity 0.3s ease;
}

.panel-wrapper.hidden {
  display: none;
}

.panel-tabs {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
}

.tab-btn {
  padding: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 6px;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.tab-btn.active {
  background: rgba(102, 126, 234, 0.3);
  border-left: 3px solid #667eea;
}

/* 执行控制台 */
.execution-console {
  height: 180px;
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.4);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.console-tabs {
  display: flex;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.console-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.console-tab:hover {
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.05);
}

.console-tab.active {
  color: #667eea;
  background: rgba(102, 126, 234, 0.1);
  border-bottom: 2px solid #667eea;
}

.console-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.logs-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.log-item {
  display: flex;
  gap: 10px;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  font-size: 12px;
}

.log-time {
  color: #64748b;
  font-family: monospace;
}

.log-type {
  font-weight: 600;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
}

.log-type.INFO {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.log-type.SUCCESS {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.log-type.WARNING {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.log-type.ERROR {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.log-message {
  flex: 1;
  color: #e2e8f0;
}

.empty-logs {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #64748b;
}

.output-panel pre {
  margin: 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #e2e8f0;
  white-space: pre-wrap;
}

.errors-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: rgba(239, 68, 68, 0.1);
  border-left: 3px solid #ef4444;
  border-radius: 4px;
}

.error-line {
  font-size: 12px;
  color: #f87171;
  font-weight: 600;
}

.error-message {
  flex: 1;
  font-size: 12px;
  color: #e2e8f0;
}

.empty-errors {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #4ade80;
}

.console-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.console-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.console-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: #e2e8f0;
}

.console-btn.primary {
  background: #667eea;
  color: white;
}

.console-btn.primary:hover {
  background: #764ba2;
}
</style>