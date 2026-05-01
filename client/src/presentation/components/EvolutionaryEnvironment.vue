<template>
  <div class="evolutionary-environment">
    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <div class="status-left">
        <div class="evolution-indicator">
          <div class="evolution-pulse"></div>
          <span class="evolution-label">进化中</span>
        </div>
        <div class="system-status">
          <span class="status-dot online"></span>
          <span>系统在线</span>
        </div>
      </div>
      <div class="status-center">
        <h1 class="title">环评智能工作台</h1>
        <p class="subtitle">基于自进化理念的AI协作环境</p>
      </div>
      <div class="status-right">
        <button class="action-btn" @click="toggleEvolutionMode">
          <span>{{ evolutionMode ? '🌱 进化模式' : '🎯 标准模式' }}</span>
        </button>
        <button class="action-btn secondary" @click="showKnowledgeGraph">
          <span>📊 知识图谱</span>
        </button>
      </div>
    </div>

    <!-- 主工作区 -->
    <div class="main-workspace">
      <!-- 左侧：对话区域 -->
      <div class="conversation-panel">
        <!-- 对话历史 -->
        <div class="conversation-history" ref="historyRef">
          <div 
            v-for="(turn, index) in conversationHistory" 
            :key="turn.id"
            class="message"
            :class="{ user: turn.isUser, ai: !turn.isUser, system: turn.isSystem }"
          >
            <div class="message-header">
              <span class="sender">{{ turn.sender }}</span>
              <span class="timestamp">{{ turn.timestamp }}</span>
              <span v-if="turn.confidence" class="confidence" :style="{ background: getConfidenceColor(turn.confidence) }">
                {{ (turn.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="message-content">
              <!-- 文本消息 -->
              <div v-if="turn.type === 'text'" class="text-content" v-html="formatMessage(turn.content)"></div>
              
              <!-- 建议操作 -->
              <div v-else-if="turn.type === 'suggestion'" class="suggestion-content">
                <div class="suggestion-title">💡 建议操作</div>
                <div class="suggestion-list">
                  <button 
                    v-for="(suggestion, idx) in turn.content" 
                    :key="idx"
                    class="suggestion-btn"
                    @click="executeSuggestion(suggestion)"
                  >
                    {{ suggestion.icon }} {{ suggestion.label }}
                  </button>
                </div>
              </div>
              
              <!-- 动态表单 -->
              <div v-else-if="turn.type === 'form'" class="form-content">
                <div class="form-title">{{ turn.content.title }}</div>
                <div class="form-description">{{ turn.content.description }}</div>
                <div v-for="field in turn.content.fields" :key="field.id" class="form-field">
                  <label>{{ field.label }}<span v-if="field.required" class="required">*</span></label>
                  
                  <!-- 文本输入 -->
                  <input 
                    v-if="field.type === 'text_input'"
                    v-model="formData[field.id]"
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
                        v-model="selectedOptions[field.id]"
                      />
                      <span>{{ option.label }}</span>
                    </label>
                  </div>
                  
                  <!-- 文件上传 -->
                  <div v-else-if="field.type === 'file_upload'" class="file-upload" @click="triggerFileUpload(field)">
                    <input type="file" :accept="field.accept.join(',')" class="file-input" @change="handleFileUpload($event, field)" />
                    <div class="upload-icon">📁</div>
                    <span class="upload-text">点击上传 {{ field.accept.join(', ') }}</span>
                  </div>
                  
                  <!-- 下拉选择 -->
                  <select v-else-if="field.type === 'select'" v-model="formData[field.id]" class="form-select">
                    <option value="">请选择</option>
                    <option v-for="option in field.options" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  
                  <!-- 滑块 -->
                  <div v-else-if="field.type === 'slider'" class="slider-field">
                    <input type="range" :min="field.min" :max="field.max" :step="field.step || 1" v-model="formData[field.id]" class="form-slider" />
                    <span class="slider-value">{{ formData[field.id] }}</span>
                  </div>
                </div>
                <div class="form-actions">
                  <button class="btn btn-secondary" @click="cancelForm">取消</button>
                  <button class="btn btn-primary" @click="submitForm(turn.content)">提交</button>
                </div>
              </div>
              
              <!-- 报告预览 -->
              <div v-else-if="turn.type === 'report'" class="report-content">
                <div class="report-header">
                  <span class="report-title">📄 {{ turn.content.title }}</span>
                  <div class="report-actions">
                    <button class="mini-btn" @click="exportReport(turn.content)">导出</button>
                    <button class="mini-btn" @click="editReport(turn.content)">编辑</button>
                  </div>
                </div>
                <div class="report-body" v-html="turn.content.content"></div>
                <div class="report-footer">
                  <span class="compliance-score">合规性评分: {{ turn.content.complianceScore }}/100</span>
                  <span class="revision-hint">AI辅助生成，需专家复核</span>
                </div>
              </div>
            </div>
            
            <!-- 学习反馈 -->
            <div v-if="!turn.isUser && !turn.isSystem" class="learning-feedback">
              <button class="feedback-btn helpful" @click="provideFeedback(turn.id, 'helpful')">
                👍 有帮助
              </button>
              <button class="feedback-btn not-helpful" @click="provideFeedback(turn.id, 'not_helpful')">
                👎 需要改进
              </button>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-tools">
            <button class="tool-btn" @click="insertTemplate">📋 模板</button>
            <button class="tool-btn" @click="insertKnowledge">📚 知识</button>
            <button class="tool-btn" @click="insertReport">📄 报告章节</button>
            <button class="tool-btn" @click="uploadDocument">📁 上传文件</button>
            <button class="tool-btn" @click="openMap">🗺️ 地图</button>
            <button class="tool-btn" @click="openTable">📊 表格</button>
          </div>
          <div class="input-wrapper">
            <input 
              v-model="userInput"
              type="text" 
              :placeholder="evolutionMode ? '描述您的环评需求，我来帮您探索最佳路径...' : '输入您的问题或需求...'"
              class="user-input"
              @keyup.enter="sendMessage"
            />
            <button class="send-btn" @click="sendMessage">
              <span>{{ evolutionMode ? '🌱' : '➤' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧：控制面板 -->
      <div class="control-panel">
        <!-- 项目概览 -->
        <div class="panel">
          <div class="panel-header">
            <h3>📋 项目概览</h3>
            <button class="panel-action" @click="editProjectInfo">✏️</button>
          </div>
          <div class="project-info">
            <div class="info-item">
              <span class="info-label">项目名称</span>
              <span class="info-value">{{ projectInfo.name || '未设置' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">项目类型</span>
              <span class="info-value">{{ projectInfo.type || '未选择' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">评价等级</span>
              <span class="info-value">{{ projectInfo.level || '未确定' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">进度</span>
              <div class="progress-mini">
                <div class="progress-fill" :style="{ width: projectProgress + '%' }"></div>
              </div>
              <span class="progress-text">{{ projectProgress }}%</span>
            </div>
          </div>
        </div>

        <!-- 知识图谱预览 -->
        <div class="panel">
          <div class="panel-header">
            <h3>🔗 关联知识</h3>
            <span class="panel-badge">{{ relatedKnowledge.length }} 条</span>
          </div>
          <div class="knowledge-list">
            <div 
              v-for="(item, index) in relatedKnowledge.slice(0, 5)" 
              :key="index"
              class="knowledge-item"
              @click="viewKnowledge(item)"
            >
              <span class="knowledge-icon">{{ item.icon }}</span>
              <div class="knowledge-content">
                <span class="knowledge-title">{{ item.title }}</span>
                <span class="knowledge-type">{{ item.type }}</span>
              </div>
            </div>
            <button v-if="relatedKnowledge.length > 5" class="view-more" @click="showKnowledgeGraph">
              查看全部
            </button>
          </div>
        </div>

        <!-- 智能助手 -->
        <div class="panel">
          <div class="panel-header">
            <h3>🤖 智能助手</h3>
          </div>
          <div class="assistant-suggestions">
            <button 
              v-for="(suggestion, index) in smartSuggestions" 
              :key="index"
              class="suggestion-item"
              @click="executeSmartAction(suggestion)"
            >
              <span class="suggestion-icon">{{ suggestion.icon }}</span>
              <span class="suggestion-text">{{ suggestion.text }}</span>
            </button>
          </div>
        </div>

        <!-- 进化指标 -->
        <div class="panel evolution-panel">
          <div class="panel-header">
            <h3>📈 进化指标</h3>
          </div>
          <div class="evolution-metrics">
            <div class="metric">
              <div class="metric-circle" :style="{ background: getMetricColor(complianceScore) }">
                {{ complianceScore }}
              </div>
              <span class="metric-label">合规性</span>
            </div>
            <div class="metric">
              <div class="metric-circle" :style="{ background: getMetricColor(efficiencyScore) }">
                {{ efficiencyScore }}
              </div>
              <span class="metric-label">效率</span>
            </div>
            <div class="metric">
              <div class="metric-circle" :style="{ background: getMetricColor(qualityScore) }">
                {{ qualityScore }}
              </div>
              <span class="metric-label">质量</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="bottom-bar">
      <div class="bar-left">
        <span class="status-item">📊 已处理 {{ processedCount }} 条消息</span>
        <span class="status-item">🧠 学习次数 {{ learningCount }}</span>
      </div>
      <div class="bar-center">
        <span class="evolution-status">
          进化阶段: {{ getEvolutionStage() }}
        </span>
      </div>
      <div class="bar-right">
        <span class="status-item">💾 自动保存已开启</span>
      </div>
    </div>

    <!-- 文件上传弹窗 -->
    <div v-if="showUploadModal" class="modal-overlay" @click="showUploadModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>📁 上传文件</h3>
          <button class="modal-close" @click="showUploadModal = false">✕</button>
        </div>
        <div class="upload-area" @click="triggerFileInput">
          <input type="file" multiple accept=".pdf,.docx,.xlsx,.jpg,.png,.cad" class="hidden-file-input" @change="handleMultipleFileUpload" />
          <div class="upload-icon-large">📤</div>
          <p>点击或拖拽文件到此处</p>
          <p class="upload-hint">支持 PDF, DOCX, XLSX, JPG, PNG, CAD</p>
        </div>
        <div v-if="uploadingFiles.length > 0" class="upload-progress">
          <div v-for="file in uploadingFiles" :key="file.name" class="progress-item">
            <span class="file-name">{{ file.name }}</span>
            <div class="mini-progress">
              <div class="mini-fill" :style="{ width: file.progress + '%' }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed } from 'vue';

// 响应式状态
const conversationHistory = ref([]);
const userInput = ref('');
const evolutionMode = ref(true);
const projectInfo = reactive({
  name: '',
  type: '',
  level: ''
});
const projectProgress = ref(0);
const relatedKnowledge = ref([]);
const smartSuggestions = ref([]);
const complianceScore = ref(75);
const efficiencyScore = ref(68);
const qualityScore = ref(82);
const processedCount = ref(0);
const learningCount = ref(0);
const showUploadModal = ref(false);
const uploadingFiles = ref([]);
const formData = reactive({});
const selectedOptions = reactive({});

// 引用
const historyRef = ref(null);

// 计算属性
const evolutionStage = computed(() => {
  if (processedCount.value < 5) return '种子期';
  if (processedCount.value < 20) return '模仿学习期';
  if (processedCount.value < 50) return '模式发现期';
  return '主动优化期';
});

// 滚动到最新消息
const scrollToBottom = async () => {
  await nextTick();
  if (historyRef.value) {
    historyRef.value.scrollTop = historyRef.value.scrollHeight;
  }
};

// 获取置信度颜色
const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return '#10b981';
  if (confidence >= 0.6) return '#f59e0b';
  return '#ef4444';
};

// 获取指标颜色
const getMetricColor = (score) => {
  if (score >= 80) return 'linear-gradient(135deg, #10b981, #059669)';
  if (score >= 60) return 'linear-gradient(135deg, #f59e0b, #d97706)';
  return 'linear-gradient(135deg, #ef4444, #dc2626)';
};

// 获取进化阶段描述
const getEvolutionStage = () => evolutionStage.value;

// 格式化消息
const formatMessage = (content) => {
  // 简单的 markdown 解析
  let formatted = content
    .replace(/### (.+)/g, '<h3>$1</h3>')
    .replace(/## (.+)/g, '<h2>$1</h2>')
    .replace(/### (.+)/g, '<h3>$1</h3>')
    .replace(/\*\*(.+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
  return formatted;
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim()) return;
  
  // 记录用户行为
  recordBehavior('message_sent', { content: userInput.value });
  
  // 添加用户消息
  conversationHistory.value.push({
    id: Date.now(),
    sender: '用户',
    content: userInput.value,
    isUser: true,
    isSystem: false,
    type: 'text',
    timestamp: new Date().toLocaleTimeString()
  });
  
  const input = userInput.value;
  userInput.value = '';
  await scrollToBottom();
  
  // 模拟 AI 响应（实际调用后端）
  await simulateAIResponse(input);
};

// 模拟 AI 响应
const simulateAIResponse = async (input) => {
  processedCount.value++;
  
  // 基于输入类型返回不同响应
  if (input.includes('化工厂') || input.includes('化工项目')) {
    // 化工项目相关，触发知识库检索和建议
    conversationHistory.value.push({
      id: Date.now() + 1,
      sender: 'AI助手',
      content: [
        { icon: '📚', label: '检索化工环评导则' },
        { icon: '🗺️', label: '标绘敏感目标' },
        { icon: '📊', label: '污染源强分析' },
        { icon: '🧪', label: '水环境影响预测' }
      ],
      isUser: false,
      isSystem: false,
      type: 'suggestion',
      confidence: 0.85,
      timestamp: new Date().toLocaleTimeString()
    });
    
    // 更新关联知识
    relatedKnowledge.value = [
      { icon: '📖', title: '化工建设项目环境影响评价导则', type: '导则' },
      { icon: '📍', title: '水环境功能区划标准', type: '标准' },
      { icon: '📊', title: '污染源强核算方法', type: '方法' }
    ];
    
    // 更新进度
    projectProgress.value = Math.min(projectProgress.value + 5, 100);
  } else if (input.includes('上传') || input.includes('文件')) {
    showUploadModal.value = true;
  } else if (input.includes('报告') || input.includes('生成')) {
    // 生成报告
    conversationHistory.value.push({
      id: Date.now() + 1,
      sender: 'AI助手',
      content: {
        title: '环境影响评价报告书（草案）',
        content: `<h3>一、项目概述</h3><p>根据您的描述，本项目为新建化工项目，位于水源地附近，需进行一级评价。</p><h3>二、现状调查</h3><p>待补充项目所在地环境现状数据...</p><h3>三、环境影响预测</h3><p>待进行水环境、大气环境影响预测...</p><h3>四、环保措施</h3><p>待制定污染防治措施...</p>`,
        complianceScore: 78
      },
      isUser: false,
      isSystem: false,
      type: 'report',
      confidence: 0.78,
      timestamp: new Date().toLocaleTimeString()
    });
  } else {
    // 开放式问题
    conversationHistory.value.push({
      id: Date.now() + 1,
      sender: 'AI助手',
      content: `我理解您的需求。为了更好地帮助您完成环评工作，请告诉我更多信息：<br><br>• 项目的具体类型是什么？<br>• 项目所在地是否有敏感保护目标？<br>• 您目前处于环评的哪个阶段？`,
      isUser: false,
      isSystem: false,
      type: 'text',
      confidence: 0.72,
      timestamp: new Date().toLocaleTimeString()
    });
  }
  
  // 更新进化指标
  updateEvolutionMetrics();
  
  await scrollToBottom();
};

// 记录行为
const recordBehavior = (action, data) => {
  // 发送到后端进行学习
  console.log('记录行为:', action, data);
};

// 更新进化指标
const updateEvolutionMetrics = () => {
  complianceScore.value = Math.min(95, complianceScore.value + Math.random() * 2);
  efficiencyScore.value = Math.min(95, efficiencyScore.value + Math.random() * 1.5);
  qualityScore.value = Math.min(95, qualityScore.value + Math.random() * 1);
  learningCount.value++;
};

// 执行建议
const executeSuggestion = (suggestion) => {
  recordBehavior('suggestion_clicked', suggestion);
  
  if (suggestion.label.includes('检索')) {
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: `正在检索相关知识库...\n\n找到以下相关资料：\n• 《化工建设项目环境影响评价导则》\n• 《水环境质量标准》\n• 《大气污染物综合排放标准》`,
      isUser: false,
      isSystem: true,
      type: 'text',
      timestamp: new Date().toLocaleTimeString()
    });
  } else if (suggestion.label.includes('标绘')) {
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: {
        title: '敏感目标标绘',
        description: '请在地图上圈定敏感目标区域',
        fields: [
          { id: 'coordinates', type: 'text_input', label: '中心点坐标', placeholder: '例如：32.0603, 118.7969', required: true },
          { id: 'radius', type: 'slider', label: '影响半径(km)', min: 1, max: 10, required: true },
          { id: 'sensitive_types', type: 'multi_select', label: '敏感目标类型', options: [
            { value: 'water', label: '水源地' },
            { value: 'residential', label: '居民区' },
            { value: 'school', label: '学校' },
            { value: 'hospital', label: '医院' }
          ]}
        ]
      },
      isUser: false,
      isSystem: false,
      type: 'form',
      timestamp: new Date().toLocaleTimeString()
    });
  }
  
  scrollToBottom();
};

// 执行智能动作
const executeSmartAction = (action) => {
  recordBehavior('smart_action', action);
  
  if (action.text.includes('模板')) {
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: `可用模板：\n\n📋 化工项目环评报告模板\n📋 生态影响评价模板\n📋 大气环境影响预测模板\n📋 水环境影响预测模板`,
      isUser: false,
      isSystem: true,
      type: 'text',
      timestamp: new Date().toLocaleTimeString()
    });
  } else if (action.text.includes('合规')) {
    complianceScore.value = Math.min(100, complianceScore.value + 5);
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: `合规性检查完成：\n\n✅ 已包含"三线一单"符合性分析\n✅ 已包含环境风险评价章节\n⚠️ 缺少公众参与章节（建议补充）`,
      isUser: false,
      isSystem: true,
      type: 'text',
      timestamp: new Date().toLocaleTimeString()
    });
  }
  
  scrollToBottom();
};

// 表单相关
const submitForm = (formSchema) => {
  const data = { ...formData };
  for (const key in selectedOptions) {
    data[key] = selectedOptions[key];
  }
  
  recordBehavior('form_submitted', { formId: formSchema.title, data });
  
  conversationHistory.value.push({
    id: Date.now(),
    sender: '系统',
    content: `已收到您的输入：\n${JSON.stringify(data, null, 2)}`,
    isUser: false,
    isSystem: true,
    type: 'text',
    timestamp: new Date().toLocaleTimeString()
  });
  
  // 清空表单
  Object.keys(formData).forEach(key => delete formData[key]);
  Object.keys(selectedOptions).forEach(key => delete selectedOptions[key]);
  
  scrollToBottom();
};

const cancelForm = () => {
  Object.keys(formData).forEach(key => delete formData[key]);
  Object.keys(selectedOptions).forEach(key => delete selectedOptions[key]);
};

// 文件上传
const triggerFileUpload = (field) => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = field.accept.join(',');
  input.onchange = (e) => handleFileUpload(e, field);
  input.click();
};

const handleFileUpload = (event, field) => {
  const file = event.target.files[0];
  if (file) {
    recordBehavior('file_uploaded', { fileName: file.name, fileType: file.type });
    
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: `📎 已上传文件：${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`,
      isUser: false,
      isSystem: true,
      type: 'text',
      timestamp: new Date().toLocaleTimeString()
    });
    
    // 更新相关知识
    relatedKnowledge.value.push({
      icon: '📄',
      title: file.name,
      type: '上传文件'
    });
  }
};

const triggerFileInput = () => {
  document.querySelector('.hidden-file-input')?.click();
};

const handleMultipleFileUpload = (event) => {
  const files = Array.from(event.target.files);
  uploadingFiles.value = files.map(f => ({ name: f.name, progress: 0 }));
  
  files.forEach((file, index) => {
    setTimeout(() => {
      uploadingFiles.value[index].progress = 50;
    }, 500);
    setTimeout(() => {
      uploadingFiles.value[index].progress = 100;
      recordBehavior('file_uploaded', { fileName: file.name });
    }, 1000);
  });
  
  setTimeout(() => {
    showUploadModal.value = false;
    uploadingFiles.value = [];
    
    conversationHistory.value.push({
      id: Date.now(),
      sender: '系统',
      content: `📎 已成功上传 ${files.length} 个文件`,
      isUser: false,
      isSystem: true,
      type: 'text',
      timestamp: new Date().toLocaleTimeString()
    });
    scrollToBottom();
  }, 1500);
};

// 反馈功能
const provideFeedback = (messageId, feedback) => {
  recordBehavior('feedback_provided', { messageId, feedback });
  
  // 更新置信度或学习模型
  if (feedback === 'helpful') {
    const message = conversationHistory.value.find(m => m.id === messageId);
    if (message) {
      message.confidence = Math.min(1, (message.confidence || 0.7) + 0.05);
    }
  }
};

// 其他功能
const toggleEvolutionMode = () => {
  evolutionMode.value = !evolutionMode.value;
};

const showKnowledgeGraph = () => {
  alert('知识图谱视图');
};

const insertTemplate = () => {
  userInput.value = '使用【化工项目环评报告】模板';
};

const insertKnowledge = () => {
  userInput.value = '检索关于';
};

const insertReport = () => {
  userInput.value = '生成【';
};

const uploadDocument = () => {
  showUploadModal.value = true;
};

const openMap = () => {
  conversationHistory.value.push({
    id: Date.now(),
    sender: '系统',
    content: {
      title: '地图标绘工具',
      description: '请在地图上进行标绘操作',
      fields: []
    },
    isUser: false,
    isSystem: true,
    type: 'form',
    timestamp: new Date().toLocaleTimeString()
  });
  scrollToBottom();
};

const openTable = () => {
  conversationHistory.value.push({
    id: Date.now(),
    sender: '系统',
    content: {
      title: '数据表格',
      description: '请填写监测数据',
      fields: [
        { id: 'parameter', type: 'text_input', label: '监测项目', required: true },
        { id: 'value', type: 'text_input', label: '监测值', required: true },
        { id: 'unit', type: 'select', label: '单位', options: [
          { value: 'mg/L', label: 'mg/L' },
          { value: 'μg/m³', label: 'μg/m³' },
          { value: 'dB(A)', label: 'dB(A)' }
        ]},
        { id: 'standard', type: 'text_input', label: '标准值', placeholder: '填写对应标准限值' }
      ]
    },
    isUser: false,
    isSystem: true,
    type: 'form',
    timestamp: new Date().toLocaleTimeString()
  });
  scrollToBottom();
};

const editProjectInfo = () => {
  alert('编辑项目信息');
};

const viewKnowledge = (item) => {
  conversationHistory.value.push({
    id: Date.now(),
    sender: '系统',
    content: `正在打开知识：${item.title}`,
    isUser: false,
    isSystem: true,
    type: 'text',
    timestamp: new Date().toLocaleTimeString()
  });
  scrollToBottom();
};

const exportReport = (report) => {
  recordBehavior('report_exported', { reportTitle: report.title });
  alert(`导出报告: ${report.title}`);
};

const editReport = (report) => {
  recordBehavior('report_edited', { reportTitle: report.title });
  alert(`编辑报告: ${report.title}`);
};

// 初始化
onMounted(() => {
  // 添加欢迎消息
  conversationHistory.value.push({
    id: Date.now(),
    sender: 'AI助手',
    content: `您好！我是您的环评智能助手。🌱\n\n这是一个自进化的工作环境，我会在与您的协作中不断学习和进步。\n\n请告诉我您的项目情况，例如："我要做一个化工厂的环评报告"`,
    isUser: false,
    isSystem: false,
    type: 'text',
    confidence: 0.8,
    timestamp: new Date().toLocaleTimeString()
  });
  
  // 初始化智能建议
  smartSuggestions.value = [
    { icon: '📋', text: '使用报告模板' },
    { icon: '✅', text: '合规性检查' },
    { icon: '📊', text: '导入监测数据' },
    { icon: '🔄', text: '生成目录大纲' }
  ];
  
  // 初始化相关知识
  relatedKnowledge.value = [
    { icon: '📖', title: '建设项目环境影响评价技术导则', type: '导则' },
    { icon: '📋', title: '环评报告编写规范', type: '规范' },
    { icon: '⚖️', title: '环境影响评价法', type: '法规' }
  ];
});
</script>

<style scoped>
.evolutionary-environment {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #e2e8f0;
}

/* 顶部状态栏 */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: rgba(30, 41, 59, 0.9);
  border-bottom: 1px solid #334155;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.evolution-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evolution-pulse {
  width: 10px;
  height: 10px;
  background: #10b981;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.evolution-label {
  font-size: 12px;
  color: #10b981;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: #10b981;
}

.status-center {
  text-align: center;
}

.title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.status-right {
  display: flex;
  gap: 10px;
}

.action-btn {
  padding: 8px 16px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.action-btn.secondary {
  background: #334155;
}

.action-btn.secondary:hover {
  background: #475569;
}

/* 主工作区 */
.main-workspace {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 对话面板 */
.conversation-panel {
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
  gap: 20px;
  padding-right: 10px;
}

.message {
  max-width: 70%;
}

.message.user {
  margin-left: auto;
}

.message.ai {
  margin-right: auto;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.sender {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
}

.message.user .sender {
  color: #60a5fa;
}

.message.system .sender {
  color: #f59e0b;
}

.timestamp {
  font-size: 10px;
  color: #64748b;
}

.confidence {
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
  color: white;
  font-weight: 500;
}

.message-content {
  background: #1e293b;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #334155;
}

.message.user .message-content {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border: none;
}

.text-content {
  font-size: 14px;
  line-height: 1.6;
}

.text-content h2 {
  font-size: 16px;
  margin: 10px 0;
  color: #f1f5f9;
}

.text-content h3 {
  font-size: 14px;
  margin: 8px 0;
  color: #e2e8f0;
}

.text-content strong {
  color: #fbbf24;
}

/* 建议内容 */
.suggestion-content {
  background: #0f172a;
  border-radius: 8px;
  padding: 12px;
}

.suggestion-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 10px;
  color: #fbbf24;
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggestion-btn {
  padding: 8px 14px;
  background: #334155;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  color: #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-btn:hover {
  background: #475569;
  transform: translateY(-1px);
}

/* 表单内容 */
.form-content {
  background: #0f172a;
  border-radius: 8px;
  padding: 16px;
}

.form-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #f1f5f9;
}

.form-description {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 16px;
}

.form-field {
  margin-bottom: 14px;
}

.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
  color: #cbd5e1;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.form-input, .form-select {
  width: 100%;
  padding: 10px 12px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  font-size: 13px;
  color: #e2e8f0;
}

.form-input:focus, .form-select:focus {
  outline: none;
  border-color: #3b82f6;
}

.multi-select {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #1e293b;
  border-radius: 20px;
  cursor: pointer;
  font-size: 12px;
}

.checkbox-label:hover {
  background: #334155;
}

.checkbox-label input {
  width: 14px;
  height: 14px;
}

.file-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px;
  border: 2px dashed #334155;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.file-upload:hover {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}

.file-input {
  display: none;
}

.upload-icon {
  font-size: 24px;
}

.upload-text {
  font-size: 12px;
  color: #94a3b8;
}

.slider-field {
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-slider {
  flex: 1;
  height: 6px;
  background: #334155;
  border-radius: 3px;
  appearance: none;
}

.form-slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  background: #3b82f6;
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  font-size: 12px;
  color: #60a5fa;
  min-width: 40px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-1px);
}

.btn-secondary {
  background: #334155;
  color: #cbd5e1;
}

.btn-secondary:hover {
  background: #475569;
}

/* 报告内容 */
.report-content {
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}

.report-title {
  font-size: 14px;
  font-weight: 600;
}

.report-actions {
  display: flex;
  gap: 8px;
}

.mini-btn {
  padding: 4px 10px;
  background: #334155;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  color: #cbd5e1;
  cursor: pointer;
}

.mini-btn:hover {
  background: #475569;
}

.report-body {
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
}

.report-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(16, 185, 129, 0.1);
  border-top: 1px solid rgba(16, 185, 129, 0.2);
}

.compliance-score {
  font-size: 12px;
  color: #10b981;
  font-weight: 500;
}

.revision-hint {
  font-size: 11px;
  color: #f59e0b;
}

/* 学习反馈 */
.learning-feedback {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.message:hover .learning-feedback {
  opacity: 1;
}

.feedback-btn {
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.feedback-btn.helpful {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.feedback-btn.helpful:hover {
  background: rgba(16, 185, 129, 0.3);
}

.feedback-btn.not-helpful {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.feedback-btn.not-helpful:hover {
  background: rgba(239, 68, 68, 0.3);
}

/* 输入区域 */
.input-area {
  background: rgba(30, 41, 59, 0.9);
  padding: 12px 16px;
  border-radius: 12px;
  margin-top: 16px;
  border: 1px solid #334155;
}

.input-tools {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.tool-btn {
  padding: 6px 12px;
  background: #334155;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-btn:hover {
  background: #475569;
}

.input-wrapper {
  display: flex;
  gap: 10px;
}

.user-input {
  flex: 1;
  padding: 12px 16px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 24px;
  font-size: 14px;
  color: #e2e8f0;
  transition: all 0.2s;
}

.user-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.user-input::placeholder {
  color: #64748b;
}

.send-btn {
  padding: 12px 20px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border: none;
  border-radius: 24px;
  font-size: 14px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

/* 控制面板 */
.control-panel {
  width: 320px;
  background: rgba(30, 41, 59, 0.8);
  border-left: 1px solid #334155;
  padding: 16px;
  overflow-y: auto;
}

.panel {
  background: #0f172a;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 16px;
  border: 1px solid #334155;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.panel-action {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 14px;
}

.panel-action:hover {
  color: #94a3b8;
}

.panel-badge {
  padding: 2px 8px;
  background: rgba(59, 130, 246, 0.2);
  border-radius: 10px;
  font-size: 11px;
  color: #60a5fa;
}

/* 项目信息 */
.project-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 12px;
  color: #64748b;
}

.info-value {
  font-size: 12px;
  color: #e2e8f0;
  font-weight: 500;
}

.progress-mini {
  flex: 1;
  height: 4px;
  background: #334155;
  border-radius: 2px;
  overflow: hidden;
  margin: 0 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 12px;
  color: #60a5fa;
  min-width: 35px;
  text-align: right;
}

/* 知识列表 */
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.knowledge-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: #1e293b;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.knowledge-item:hover {
  background: #334155;
}

.knowledge-icon {
  font-size: 18px;
}

.knowledge-content {
  flex: 1;
  min-width: 0;
}

.knowledge-title {
  display: block;
  font-size: 12px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.knowledge-type {
  display: block;
  font-size: 10px;
  color: #64748b;
}

.view-more {
  text-align: center;
  padding: 8px;
  font-size: 12px;
  color: #60a5fa;
  cursor: pointer;
  background: rgba(96, 165, 250, 0.1);
  border-radius: 6px;
}

.view-more:hover {
  background: rgba(96, 165, 250, 0.2);
}

/* 智能助手 */
.assistant-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(99, 102, 241, 0.1));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-item:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(99, 102, 241, 0.2));
}

.suggestion-icon {
  font-size: 16px;
}

.suggestion-text {
  font-size: 12px;
  color: #e2e8f0;
}

/* 进化指标 */
.evolution-panel {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(59, 130, 246, 0.1));
  border-color: rgba(16, 185, 129, 0.2);
}

.evolution-metrics {
  display: flex;
  justify-content: space-around;
}

.metric {
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

.metric-label {
  font-size: 11px;
  color: #94a3b8;
}

/* 底部状态栏 */
.bottom-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  background: rgba(30, 41, 59, 0.95);
  border-top: 1px solid #334155;
  font-size: 11px;
  color: #64748b;
}

.bar-left, .bar-right {
  display: flex;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.evolution-status {
  color: #10b981;
  font-weight: 500;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 400px;
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #334155;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #334155;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
}

.modal-close {
  background: none;
  border: none;
  color: #64748b;
  font-size: 18px;
  cursor: pointer;
}

.modal-close:hover {
  color: #94a3b8;
}

.upload-area {
  padding: 40px;
  text-align: center;
  border: 2px dashed #334155;
  margin: 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}

.upload-icon-large {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 8px;
}

.hidden-file-input {
  display: none;
}

.upload-progress {
  padding: 0 16px 16px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.file-name {
  font-size: 12px;
  color: #e2e8f0;
  flex: 1;
}

.mini-progress {
  width: 100px;
  height: 4px;
  background: #334155;
  border-radius: 2px;
  overflow: hidden;
}

.mini-fill {
  height: 100%;
  background: #10b981;
  transition: width 0.3s;
}
</style>