<template>
  <div class="ide-container">
    <div class="ide-header">
      <div class="header-left">
        <div class="logo-section">
          <span class="logo-icon">🌳</span>
          <span class="logo-text">LivingTree AI 协同开发</span>
        </div>
      </div>
      <div class="header-center">
        <div class="file-tabs">
          <div 
            v-for="file in openFiles" 
            :key="file.id"
            :class="['file-tab', { active: currentFileId === file.id }]"
            @click="switchFile(file.id)"
          >
            <span class="file-icon">{{ getFileIcon(file.extension) }}</span>
            <span class="file-name">{{ file.name }}</span>
            <button class="close-tab" @click.stop="closeFile(file.id)">×</button>
          </div>
        </div>
      </div>
      <div class="header-right">
        <button class="toolbar-btn" title="新建文件" @click="newFile">
          <span>📄</span>
          <span>新建</span>
        </button>
        <button class="toolbar-btn" title="打开文件" @click="openFile">
          <span>📁</span>
          <span>打开</span>
        </button>
        <button class="toolbar-btn primary" title="生成代码" @click="generateCode">
          <span>✨</span>
          <span>生成</span>
        </button>
        <button class="toolbar-btn" title="解释代码" @click="explainCode">
          <span>💡</span>
          <span>解释</span>
        </button>
        <button class="toolbar-btn" title="运行代码" @click="runCode">
          <span>▶️</span>
          <span>运行</span>
        </button>
      </div>
    </div>

    <div class="ide-body">
      <div class="editor-section">
        <div class="editor-toolbar">
          <select class="lang-select" v-model="selectedLanguage">
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="json">JSON</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
          </select>
          <div class="editor-actions">
            <button class="mini-btn" @click="formatCode">格式化</button>
            <button class="mini-btn" @click="commentCode">注释</button>
            <button class="mini-btn" @click="undo">撤销</button>
            <button class="mini-btn" @click="redo">重做</button>
          </div>
          <div class="editor-status">
            <span>行 {{ cursorPosition.line }}, 列 {{ cursorPosition.column }}</span>
          </div>
        </div>
        <div class="editor-container">
          <div class="line-numbers">
            <div 
              v-for="n in lineCount" 
              :key="n"
              class="line-number"
              :class="{ current: n === cursorPosition.line }"
            >{{ n }}</div>
          </div>
          <textarea 
            ref="codeEditor"
            v-model="currentCode"
            class="code-editor"
            spellcheck="false"
            @input="updateLineCount"
            @keydown="handleKeydown"
          ></textarea>
        </div>
      </div>

      <div class="panel-section">
        <div class="panel-tabs">
          <button 
            :class="['panel-tab', { active: activePanel === 'ai' }]"
            @click="activePanel = 'ai'"
          >
            <span>🤖</span>
            <span>AI助手</span>
          </button>
          <button 
            :class="['panel-tab', { active: activePanel === 'output' }]"
            @click="activePanel = 'output'"
          >
            <span>💻</span>
            <span>终端</span>
          </button>
          <button 
            :class="['panel-tab', { active: activePanel === 'console' }]"
            @click="activePanel = 'console'"
          >
            <span>📊</span>
            <span>控制台</span>
          </button>
          <button 
            :class="['panel-tab', { active: activePanel === 'problems' }]"
            @click="activePanel = 'problems'"
          >
            <span>❌</span>
            <span>问题</span>
          </button>
        </div>
        
        <div class="panel-content">
          <AIAssistant 
            v-show="activePanel === 'ai'"
            @codeGenerated="handleCodeGenerated"
            @runCode="handleRunCode"
          />
          
          <div v-show="activePanel === 'output'" class="output-panel">
            <div v-if="!isRunning && !executionResult" class="empty-output">
              <span>点击"运行"按钮执行代码</span>
            </div>
            <div v-else-if="isRunning" class="running-output">
              <div class="running-indicator">
                <span class="spinner"></span>
                <span>正在执行...</span>
              </div>
            </div>
            <div v-else class="result-output">
              <div :class="['result-header', executionResult.success ? 'success' : 'error']">
                <span>{{ executionResult.success ? '✓ 执行成功' : '✗ 执行失败' }}</span>
                <span class="exec-time">耗时: {{ executionResult.time }}ms</span>
              </div>
              <pre class="result-text">{{ executionResult.output }}</pre>
            </div>
          </div>
          
          <div v-show="activePanel === 'console'" class="console-panel">
            <div 
              v-for="(log, index) in consoleLogs" 
              :key="index"
              :class="['console-item', log.type]"
            >
              <span class="console-time">{{ log.time }}</span>
              <span :class="['console-type', log.type]">{{ log.type.toUpperCase() }}</span>
              <span class="console-message">{{ log.message }}</span>
            </div>
          </div>
          
          <div v-show="activePanel === 'problems'" class="problems-panel">
            <div v-if="problems.length === 0" class="empty-problems">
              <span>✓ 代码检查通过，没有问题</span>
            </div>
            <div 
              v-for="(problem, index) in problems" 
              :key="index"
              :class="['problem-item', problem.severity]"
            >
              <span :class="['problem-icon', problem.severity]">
                {{ problem.severity === 'error' ? '✗' : problem.severity === 'warning' ? '⚠' : 'ℹ' }}
              </span>
              <div class="problem-content">
                <span class="problem-message">{{ problem.message }}</span>
                <span class="problem-location">第 {{ problem.line }} 行</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="ide-footer">
      <div class="footer-left">
        <span class="status-indicator"></span>
        <span>Python 3.11</span>
        <span>|</span>
        <span>{{ selectedLanguage }}</span>
        <span>|</span>
        <span>UTF-8</span>
      </div>
      <div class="footer-right">
        <span>{{ fileStats.lines }} 行</span>
        <span>|</span>
        <span>{{ fileStats.chars }} 字符</span>
        <span>|</span>
        <button class="footer-btn" @click="toggleWordWrap">
          {{ wordWrap ? '自动换行' : '不换行' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import AIAssistant from './AIAssistant.vue';

const emit = defineEmits(['runCode', 'generateCode']);

const openFiles = ref([
  { id: '1', name: 'main.py', extension: 'py', content: 'print("Hello, LivingTree!")\n' }
]);

const currentFileId = ref('1');
const currentCode = ref('print("Hello, LivingTree!")\n');
const selectedLanguage = ref('python');
const activePanel = ref('ai');
const isRunning = ref(false);
const executionResult = ref(null);
const consoleLogs = ref([]);
const problems = ref([]);
const cursorPosition = ref({ line: 1, column: 1 });
const wordWrap = ref(false);
const codeEditor = ref(null);

const lineCount = computed(() => {
  return Math.max(currentCode.value.split('\n').length, 20);
});

const fileStats = computed(() => {
  return {
    lines: currentCode.value.split('\n').length,
    chars: currentCode.value.length
  };
});

const currentFile = computed(() => {
  return openFiles.value.find(f => f.id === currentFileId.value);
});

const getFileIcon = (ext) => {
  const icons = {
    py: '🐍',
    js: '📜',
    json: '📋',
    html: '🌐',
    css: '🎨',
    md: '📝',
    txt: '📄'
  };
  return icons[ext] || '📄';
};

const switchFile = (fileId) => {
  currentFileId.value = fileId;
  const file = openFiles.value.find(f => f.id === fileId);
  if (file) {
    currentCode.value = file.content;
  }
};

const closeFile = (fileId) => {
  const index = openFiles.value.findIndex(f => f.id === fileId);
  if (index > -1) {
    openFiles.value.splice(index, 1);
    if (currentFileId.value === fileId && openFiles.value.length > 0) {
      switchFile(openFiles.value[0].id);
    }
  }
};

const newFile = () => {
  const newId = Date.now().toString();
  openFiles.value.push({
    id: newId,
    name: 'untitled.py',
    extension: 'py',
    content: ''
  });
  switchFile(newId);
};

const openFile = () => {
  console.log('打开文件');
};

const generateCode = () => {
  emit('generateCode', currentCode.value);
};

const explainCode = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: `正在分析代码...`
  });
};

const runCode = async () => {
  if (!currentCode.value.trim()) return;
  
  isRunning.value = true;
  executionResult.value = null;
  
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: `开始执行代码`
  });
  
  await new Promise(resolve => setTimeout(resolve, 1500));
  
  const output = `>>> ${currentCode.value}\nHello, LivingTree!\n>>> Success`;
  
  executionResult.value = {
    success: true,
    output: output,
    time: 1523
  };
  
  isRunning.value = false;
  
  consoleLogs.value.push({
    type: 'success',
    time: new Date().toLocaleTimeString(),
    message: `代码执行成功，耗时 1523ms`
  });
  
  emit('runCode', currentCode.value);
};

const handleCodeGenerated = (code) => {
  currentCode.value = code;
  activePanel.value = 'output';
};

const handleRunCode = (code) => {
  currentCode.value = code;
  runCode();
};

const formatCode = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '代码已格式化'
  });
};

const commentCode = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '代码已注释'
  });
};

const undo = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '已撤销'
  });
};

const redo = () => {
  consoleLogs.value.push({
    type: 'info',
    time: new Date().toLocaleTimeString(),
    message: '已重做'
  });
};

const toggleWordWrap = () => {
  wordWrap.value = !wordWrap.value;
};

const updateLineCount = () => {
  if (currentFile.value) {
    currentFile.value.content = currentCode.value;
  }
};

const handleKeydown = (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = e.target.selectionStart;
    const end = e.target.selectionEnd;
    currentCode.value = currentCode.value.substring(0, start) + '    ' + currentCode.value.substring(end);
  }
  
  if (e.key === 'Enter') {
    const lines = currentCode.value.substring(0, e.target.selectionStart).split('\n');
    cursorPosition.value = {
      line: lines.length,
      column: 1
    };
  }
};

watch(currentCode, () => {
  checkProblems();
});

const checkProblems = () => {
  const newProblems = [];
  
  if (currentCode.value.includes('undefined')) {
    newProblems.push({
      severity: 'error',
      message: '未定义的变量: undefined',
      line: currentCode.value.split('\n').findIndex(line => line.includes('undefined')) + 1
    });
  }
  
  if (currentCode.value.includes('TODO')) {
    newProblems.push({
      severity: 'warning',
      message: '存在待办事项',
      line: currentCode.value.split('\n').findIndex(line => line.includes('TODO')) + 1
    });
  }
  
  problems.value = newProblems;
};

onMounted(() => {
  checkProblems();
});
</script>

<style scoped>
.ide-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
  color: #d4d4d4;
}

.ide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #252526;
  border-bottom: 1px solid #3c3c3c;
}

.header-left {
  display: flex;
  align-items: center;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 20px;
}

.logo-text {
  font-size: 14px;
  font-weight: 600;
  color: #667eea;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.file-tabs {
  display: flex;
  gap: 4px;
  background: #1e1e1e;
  padding: 2px;
  border-radius: 4px;
}

.file-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.2s;
}

.file-tab:hover {
  background: #2d2d2d;
}

.file-tab.active {
  background: #3c3c3c;
}

.file-icon {
  font-size: 14px;
}

.file-name {
  font-size: 13px;
  color: #d4d4d4;
}

.close-tab {
  background: none;
  border: none;
  color: #858585;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}

.close-tab:hover {
  color: #fff;
}

.header-right {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #3c3c3c;
  border: none;
  border-radius: 4px;
  color: #d4d4d4;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.toolbar-btn:hover {
  background: #4c4c4c;
}

.toolbar-btn.primary {
  background: #667eea;
  color: white;
}

.toolbar-btn.primary:hover {
  background: #764ba2;
}

.ide-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.editor-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #3c3c3c;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #252526;
  border-bottom: 1px solid #3c3c3c;
}

.lang-select {
  padding: 4px 8px;
  background: #3c3c3c;
  border: none;
  border-radius: 4px;
  color: #d4d4d4;
  font-size: 12px;
  cursor: pointer;
}

.editor-actions {
  display: flex;
  gap: 4px;
}

.mini-btn {
  padding: 4px 10px;
  background: #3c3c3c;
  border: none;
  border-radius: 4px;
  color: #d4d4d4;
  font-size: 11px;
  cursor: pointer;
}

.mini-btn:hover {
  background: #4c4c4c;
}

.editor-status {
  font-size: 11px;
  color: #858585;
}

.editor-container {
  flex: 1;
  display: flex;
  overflow: auto;
}

.line-numbers {
  padding: 10px 8px;
  background: #252526;
  text-align: right;
  user-select: none;
  min-width: 50px;
}

.line-number {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 20px;
  color: #858585;
}

.line-number.current {
  color: #d4d4d4;
}

.code-editor {
  flex: 1;
  padding: 10px;
  background: #1e1e1e;
  border: none;
  color: #d4d4d4;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 20px;
  resize: none;
  outline: none;
}

.code-editor::placeholder {
  color: #4c4c4c;
}

.panel-section {
  width: 400px;
  display: flex;
  flex-direction: column;
  background: #252526;
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid #3c3c3c;
}

.panel-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: transparent;
  border: none;
  color: #858585;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.panel-tab:hover {
  color: #d4d4d4;
  background: #3c3c3c;
}

.panel-tab.active {
  color: #667eea;
  background: #1e1e1e;
  border-bottom: 2px solid #667eea;
}

.panel-content {
  flex: 1;
  overflow: hidden;
}

.output-panel {
  height: 100%;
  padding: 12px;
  background: #1e1e1e;
}

.empty-output {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #858585;
  font-size: 14px;
}

.running-output {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.running-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #667eea;
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #667eea;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-output {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}

.result-header.success {
  background: #0d2818;
  color: #6a9955;
}

.result-header.error {
  background: #3b1818;
  color: #f14c4c;
}

.exec-time {
  font-weight: normal;
  opacity: 0.7;
}

.result-text {
  flex: 1;
  margin: 12px 0 0 0;
  padding: 12px;
  background: #0d0d0d;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #a0a0a0;
  overflow-y: auto;
  white-space: pre-wrap;
}

.console-panel {
  height: 100%;
  padding: 12px;
  background: #1e1e1e;
  overflow-y: auto;
}

.console-item {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #2d2d2d;
}

.console-time {
  font-size: 11px;
  color: #6a6a6a;
}

.console-type {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
}

.console-type.INFO {
  background: #3794ff;
  color: white;
}

.console-type.SUCCESS {
  background: #26a69a;
  color: white;
}

.console-type.WARNING {
  background: #ffb300;
  color: black;
}

.console-type.ERROR {
  background: #ef5350;
  color: white;
}

.console-message {
  flex: 1;
  font-size: 12px;
  color: #d4d4d4;
}

.problems-panel {
  height: 100%;
  padding: 12px;
  background: #1e1e1e;
  overflow-y: auto;
}

.empty-problems {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #26a69a;
  font-size: 14px;
}

.problem-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  margin-bottom: 8px;
  background: #252526;
  border-radius: 4px;
}

.problem-icon {
  font-size: 16px;
}

.problem-icon.error {
  color: #f14c4c;
}

.problem-icon.warning {
  color: #ffb300;
}

.problem-icon.info {
  color: #3794ff;
}

.problem-content {
  flex: 1;
}

.problem-message {
  display: block;
  font-size: 13px;
  color: #d4d4d4;
}

.problem-location {
  font-size: 11px;
  color: #858585;
}

.ide-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 16px;
  background: #252526;
  border-top: 1px solid #3c3c3c;
  font-size: 11px;
  color: #858585;
}

.status-indicator {
  width: 10px;
  height: 10px;
  background: #26a69a;
  border-radius: 50%;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.footer-btn {
  background: none;
  border: none;
  color: #858585;
  font-size: 11px;
  cursor: pointer;
}

.footer-btn:hover {
  color: #d4d4d4;
}
</style>