<template>
  <div class="streaming-output">
    <!-- 工具栏 -->
    <div class="streaming-toolbar">
      <div class="status-indicator">
        <span :class="['status-dot', generationStatus]"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>
      
      <div class="control-buttons">
        <!-- 文件上传按钮 -->
        <label class="control-btn upload-btn" title="上传文档学习样式">
          <span>📤</span>
          <input type="file" class="file-input" accept=".docx" @change="handleFileUpload">
        </label>
        
        <button 
          v-if="generationStatus === 'running'"
          class="control-btn pause-btn"
          @click="handlePause"
          title="暂停"
        >
          <span>⏸️</span>
        </button>
        <button 
          v-if="generationStatus === 'paused'"
          class="control-btn resume-btn"
          @click="handleResume"
          title="继续"
        >
          <span>▶️</span>
        </button>
        <button 
          v-if="generationStatus !== 'idle' && generationStatus !== 'completed'"
          class="control-btn stop-btn"
          @click="handleStop"
          title="终止"
        >
          <span>⏹️</span>
        </button>
        <button 
          v-if="generationStatus === 'completed' && outputPath"
          class="control-btn download-btn"
          @click="handleDownload"
          title="下载文档"
        >
          <span>📥</span>
        </button>
        
        <!-- 样式调整按钮 -->
        <button 
          class="control-btn style-btn"
          @click="showStylePanel = !showStylePanel"
          title="样式调整"
        >
          <span>🎨</span>
        </button>
      </div>
      
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
    </div>
    
    <!-- 样式调整面板 -->
    <div v-if="showStylePanel" class="style-panel">
      <h3>样式调整</h3>
      <div class="style-section">
        <label class="style-label">标题1字体:</label>
        <input type="text" v-model="styleOverrides.heading1.fontName" @change="applyStyleChanges">
      </div>
      <div class="style-section">
        <label class="style-label">标题1字号:</label>
        <input type="number" v-model="styleOverrides.heading1.fontSize" @change="applyStyleChanges">
      </div>
      <div class="style-section">
        <label class="style-label">正文字体:</label>
        <input type="text" v-model="styleOverrides.normal.fontName" @change="applyStyleChanges">
      </div>
      <div class="style-section">
        <label class="style-label">正文字号:</label>
        <input type="number" v-model="styleOverrides.normal.fontSize" @change="applyStyleChanges">
      </div>
      <button class="reset-btn" @click="resetStyles">重置样式</button>
    </div>
    
    <!-- 输出区域 -->
    <div class="output-content">
      <!-- 思考消息 -->
      <div v-if="thinkingMessage" class="thinking-message">
        <span class="thinking-icon">🧠</span>
        <span class="thinking-text">{{ thinkingMessage }}</span>
      </div>
      
      <!-- Markdown内容 -->
      <div class="markdown-content" ref="markdownContainer">
        <div v-html="renderedContent"></div>
      </div>
      
      <!-- 代码块 -->
      <div v-if="currentCodeBlock" class="code-block-container">
        <div class="code-header">
          <span class="code-lang">{{ currentCodeLang || 'python' }}</span>
          <button class="copy-btn" @click="copyCode(currentCodeBlock)">📋</button>
        </div>
        <pre><code>{{ currentCodeBlock }}</code></pre>
      </div>
      
      <!-- 表格 -->
      <div v-if="currentTable" class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="(header, index) in tableHeaders" :key="index">{{ header }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in tableRows" :key="rowIndex">
              <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- 光标闪烁 -->
      <span v-if="generationStatus === 'running'" class="cursor-blink">|</span>
    </div>
    
    <!-- 任务列表 -->
    <div v-if="showTaskList" class="task-list">
      <h3>生成任务</h3>
      <div 
        v-for="task in tasks" 
        :key="task.task_id"
        class="task-item"
        :class="task.status"
      >
        <span class="task-name">{{ task.task_type }}</span>
        <span class="task-status">{{ task.status }}</span>
        <span class="task-progress">{{ task.progress }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup>import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { marked } from 'marked';
const props = defineProps({
 modelValue: String
});
const emit = defineEmits(['update:modelValue', 'pause', 'resume', 'stop', 'download', 'styleChanged']);
// 状态
const generationStatus = ref('idle'); // idle, running, paused, completed, error
const progress = ref(0);
const thinkingMessage = ref('');
const rawContent = ref('');
const currentCodeBlock = ref('');
const currentCodeLang = ref('python');
const currentTable = ref('');
const tableHeaders = ref([]);
const tableRows = ref([]);
const outputPath = ref('');
const tasks = ref([]);
const showTaskList = ref(false);
const showStylePanel = ref(false);
const markdownContainer = ref(null);
// 样式覆盖（用于实时调整）
const styleOverrides = ref({
 heading1: {
 fontName: '',
 fontSize: 0
 },
 normal: {
 fontName: '',
 fontSize: 0
 }
});
// 状态文本
const statusText = computed(() => {
 const texts = {
 idle: '就绪',
 running: '生成中...',
 paused: '已暂停',
 completed: '已完成',
 error: '出错'
 };
 return texts[generationStatus.value] || '未知';
});
// 渲染内容
const renderedContent = computed(() => {
 try {
 return marked(rawContent.value);
 }
 catch (e) {
 return rawContent.value;
 }
});
// 处理数据块
const handleChunk = (chunk) => {
 if (!chunk)
 return;
 const type = chunk.type;
 const content = chunk.content || '';
 switch (type) {
 case 'thinking':
 thinkingMessage.value = content;
 break;
 case 'content':
 thinkingMessage.value = '';
 rawContent.value += content;
 scrollToBottom();
 break;
 case 'code':
 thinkingMessage.value = '';
 currentCodeBlock.value += content;
 break;
 case 'table':
 thinkingMessage.value = '';
 parseTable(content);
 break;
 case 'directive':
 // 忽略指令，由后端处理
 break;
 default:
 thinkingMessage.value = '';
 rawContent.value += content;
 scrollToBottom();
 }
};
// 解析表格
const parseTable = (content) => {
 const lines = content.trim().split('\n');
 if (lines.length === 0)
 return;
 // 解析表头
 const headers = lines[0].split('|').filter(cell => cell.trim());
 tableHeaders.value = headers;
 // 解析数据行
 const rows = [];
 for (let i = 1; i < lines.length; i++) {
 const cells = lines[i].split('|').filter(cell => cell.trim());
 if (cells.length > 0 && !cells.every(c => c === '---')) {
 rows.push(cells);
 }
 }
 tableRows.value = rows;
 currentTable.value = content;
};
// 滚动到底部
const scrollToBottom = () => {
 setTimeout(() => {
 if (markdownContainer.value) {
 markdownContainer.value.scrollTop = markdownContainer.value.scrollHeight;
 }
 }, 50);
};
// 控制方法
const handlePause = () => {
 generationStatus.value = 'paused';
 emit('pause');
};
const handleResume = () => {
 generationStatus.value = 'running';
 emit('resume');
};
const handleStop = () => {
 generationStatus.value = 'idle';
 emit('stop');
};
const handleDownload = () => {
 if (outputPath.value) {
 emit('download', outputPath.value);
 }
};
// 复制代码
const copyCode = async (code) => {
 try {
 await navigator.clipboard.writeText(code);
 alert('代码已复制到剪贴板');
 }
 catch (e) {
 console.error('复制失败:', e);
 }
};
// 重置状态
const resetState = () => {
 generationStatus.value = 'idle';
 progress.value = 0;
 thinkingMessage.value = '';
 rawContent.value = '';
 currentCodeBlock.value = '';
 currentCodeLang.value = 'python';
 currentTable.value = '';
 tableHeaders.value = [];
 tableRows.value = [];
 outputPath.value = '';
};
// 开始生成
const startGeneration = (taskType, parameters) => {
 resetState();
 generationStatus.value = 'running';
 thinkingMessage.value = '正在初始化...';
};
// 完成生成
const completeGeneration = (path) => {
 generationStatus.value = 'completed';
 outputPath.value = path;
 thinkingMessage.value = '';
};
// 出错
const handleError = (error) => {
 generationStatus.value = 'error';
 thinkingMessage.value = `错误: ${error}`;
};
// 更新进度
const updateProgress = (value) => {
 progress.value = value;
};
// 监听modelValue变化
watch(() => props.modelValue, (newValue) => {
 if (newValue) {
 try {
 const chunk = JSON.parse(newValue);
 handleChunk(chunk);
 }
 catch (e) {
 console.error('解析数据块失败:', e);
 }
 }
});
// 生命周期
onMounted(() => {
 // 初始化webchannel连接
 setupWebChannel();
});
onUnmounted(() => {
 // 清理
});
// WebChannel设置
const setupWebChannel = () => {
 if (typeof window !== 'undefined' && window.qt && window.qt.webChannelTransport) {
 new QWebChannel(window.qt.webChannelTransport, function (channel) {
 const backend = channel.objects.backend;
 // 连接A.R.I.A信号
 backend.onARIAGenerationStarted.connect((data) => {
 const info = JSON.parse(data);
 startGeneration(info.task_type, info.parameters);
 });
 backend.onARIAGenerationProgress.connect((data) => {
 const progressInfo = JSON.parse(data);
 updateProgress(progressInfo.progress);
 });
 backend.onARIAGenerationChunk.connect((data) => {
 handleChunk(JSON.parse(data));
 });
 backend.onARIAGenerationPaused.connect(() => {
 generationStatus.value = 'paused';
 });
 backend.onARIAGenerationResumed.connect(() => {
 generationStatus.value = 'running';
 });
 backend.onARIAGenerationCompleted.connect((data) => {
 const result = JSON.parse(data);
 completeGeneration(result.document_path);
 });
 backend.onARIAGenerationError.connect((error) => {
 handleError(error);
 });
 });
 }
};
// 文件上传处理
const handleFileUpload = (event) => {
 const file = event.target.files[0];
 if (file) {
 // 发送文件到后端学习样式
 thinkingMessage.value = `正在学习文档样式: ${file.name}...`;
 
 if (typeof window !== 'undefined' && window.qt && window.qt.webChannelTransport) {
 new QWebChannel(window.qt.webChannelTransport, function (channel) {
 const backend = channel.objects.backend;
 // 注意：QWebChannel文件上传需要特殊处理
 // 这里发送文件路径或使用其他方式
 alert(`已选择文件: ${file.name}\n样式学习功能需要后端支持文件上传`);
 thinkingMessage.value = '';
 });
 }
 }
};
// 应用样式更改
const applyStyleChanges = () => {
 const changes = {};
 
 if (styleOverrides.value.heading1.fontName) {
 changes.heading1 = { fontName: styleOverrides.value.heading1.fontName };
 }
 if (styleOverrides.value.heading1.fontSize > 0) {
 changes.heading1 = changes.heading1 || {};
 changes.heading1.fontSize = styleOverrides.value.heading1.fontSize;
 }
 if (styleOverrides.value.normal.fontName) {
 changes.normal = { fontName: styleOverrides.value.normal.fontName };
 }
 if (styleOverrides.value.normal.fontSize > 0) {
 changes.normal = changes.normal || {};
 changes.normal.fontSize = styleOverrides.value.normal.fontSize;
 }
 
 if (Object.keys(changes).length > 0) {
 emit('styleChanged', changes);
 thinkingMessage.value = `已调整样式: ${JSON.stringify(changes)}`;
 }
};
// 重置样式
const resetStyles = () => {
 styleOverrides.value = {
 heading1: { fontName: '', fontSize: 0 },
 normal: { fontName: '', fontSize: 0 }
 };
 emit('styleChanged', {});
 thinkingMessage.value = '已重置样式';
};
// 暴露方法给父组件
defineExpose({
 startGeneration,
 pause: handlePause,
 resume: handleResume,
 stop: handleStop,
 reset: resetState,
 applyStyleChanges,
 resetStyles
});
</script>

<style scoped>
.streaming-output {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
}

.streaming-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #2d2d2d;
  border-bottom: 1px solid #3d3d3d;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}

.status-dot.idle {
  background: #666;
}

.status-dot.running {
  background: #4CAF50;
  animation: pulse 1s infinite;
}

.status-dot.paused {
  background: #FF9800;
}

.status-dot.completed {
  background: #2196F3;
}

.status-dot.error {
  background: #f44336;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  color: #ccc;
  font-size: 14px;
}

.control-buttons {
  display: flex;
  gap: 8px;
}

.control-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.pause-btn {
  background: #FF9800;
  color: white;
}

.resume-btn {
  background: #4CAF50;
  color: white;
}

.stop-btn {
  background: #f44336;
  color: white;
}

.download-btn {
  background: #2196F3;
  color: white;
}

.control-btn:hover {
  opacity: 0.9;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: #3d3d3d;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #2196F3);
  transition: width 0.3s;
}

.output-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #e0e0e0;
}

.thinking-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(76, 175, 80, 0.1);
  border-radius: 4px;
  margin-bottom: 12px;
}

.thinking-icon {
  font-size: 16px;
}

.thinking-text {
  color: #4CAF50;
  font-style: italic;
}

.markdown-content {
  min-height: 200px;
}

.markdown-content :deep(h1) {
  color: #61afef;
  border-bottom: 1px solid #3d3d3d;
  padding-bottom: 8px;
  margin: 20px 0 10px;
}

.markdown-content :deep(h2) {
  color: #e6c07b;
  margin: 16px 0 8px;
}

.markdown-content :deep(h3) {
  color: #98c379;
  margin: 12px 0 6px;
}

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.code-block-container {
  background: #2d2d2d;
  border-radius: 4px;
  overflow: hidden;
  margin: 12px 0;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #3d3d3d;
}

.code-lang {
  color: #e6c07b;
  font-size: 12px;
}

.copy-btn {
  background: transparent;
  border: none;
  color: #ccc;
  cursor: pointer;
  font-size: 14px;
}

.copy-btn:hover {
  color: #fff;
}

.code-block-container pre {
  margin: 0;
  padding: 12px;
  overflow-x: auto;
  color: #abb2bf;
}

.table-container {
  margin: 12px 0;
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #3d3d3d;
}

.data-table th,
.data-table td {
  padding: 8px 12px;
  border: 1px solid #3d3d3d;
  text-align: left;
}

.data-table th {
  background: #3d3d3d;
  color: #e6c07b;
}

.cursor-blink {
  display: inline-block;
  animation: blink 1s infinite;
  color: #4CAF50;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.task-list {
  padding: 12px 16px;
  background: #2d2d2d;
  border-top: 1px solid #3d3d3d;
}

.task-list h3 {
  margin: 0 0 8px;
  color: #ccc;
  font-size: 14px;
}

.task-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  margin: 4px 0;
  background: #3d3d3d;
  border-radius: 4px;
}

.task-name {
  color: #e0e0e0;
}

.task-status {
  color: #4CAF50;
}

.task-status.paused {
  color: #FF9800;
}

.task-status.error {
  color: #f44336;
}

.task-progress {
  color: #2196F3;
}
</style>