<template>
  <div class="document-processor">
    <div class="doc-header">
      <h2>📄 文档处理中心</h2>
      <div class="doc-tabs">
        <button 
          :class="['doc-tab', { active: currentTab === 'upload' }]"
          @click="currentTab = 'upload'"
        >文件上传</button>
        <button 
          :class="['doc-tab', { active: currentTab === 'analyze' }]"
          @click="currentTab = 'analyze'"
        >论文研读</button>
        <button 
          :class="['doc-tab', { active: currentTab === 'content' }]"
          @click="currentTab = 'content'"
        >内容创作</button>
        <button 
          :class="['doc-tab', { active: currentTab === 'data' }]"
          @click="currentTab = 'data'"
        >数据分析</button>
      </div>
    </div>

    <div class="doc-body">
      <!-- 文件上传 -->
      <div v-show="currentTab === 'upload'" class="upload-section">
        <div class="upload-area" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
          <div class="upload-icon">📁</div>
          <div class="upload-text">点击或拖拽文件到这里上传</div>
          <div class="upload-hint">支持 PDF、Word、Excel、图片等格式</div>
        </div>
        <input type="file" id="doc-upload" class="doc-upload" @change="handleFileSelect" multiple>
        
        <div v-if="uploadedFiles.length > 0" class="file-list">
          <div 
            v-for="file in uploadedFiles" 
            :key="file.id"
            class="file-item"
          >
            <span class="file-icon">{{ getFileIcon(file.type) }}</span>
            <div class="file-info">
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatSize(file.size) }}</span>
            </div>
            <button class="remove-btn" @click="removeFile(file.id)">×</button>
          </div>
        </div>
      </div>

      <!-- 论文研读 -->
      <div v-show="currentTab === 'analyze'" class="analyze-section">
        <div class="input-group">
          <label>论文链接或内容</label>
          <textarea 
            v-model="paperContent"
            class="input-textarea"
            placeholder="请粘贴论文链接或复制论文内容到这里..."
            rows="6"
          ></textarea>
        </div>
        
        <div class="input-group">
          <label>分析重点</label>
          <select class="input-select" v-model="analysisFocus">
            <option value="summary">论文综述</option>
            <option value="method">研究方法</option>
            <option value="results">实验结果</option>
            <option value="conclusion">结论讨论</option>
            <option value="comparison">相关工作对比</option>
          </select>
        </div>

        <button class="analyze-btn" @click="analyzePaper">
          <span>🔍</span>
          <span>开始研读</span>
        </button>

        <div v-if="paperResult" class="result-section">
          <div class="result-header">
            <span>📚 论文分析结果</span>
          </div>
          <div class="result-content" v-html="paperResult"></div>
        </div>
      </div>

      <!-- 内容创作 -->
      <div v-show="currentTab === 'content'" class="content-section">
        <div class="input-group">
          <label>主题/产品名称</label>
          <input 
            v-model="contentTopic"
            class="input-text"
            placeholder="请输入要创作的主题或产品名称..."
          />
        </div>

        <div class="input-group">
          <label>目标受众</label>
          <select class="input-select" v-model="contentAudience">
            <option value="general">大众用户</option>
            <option value="professional">专业人士</option>
            <option value="business">商务客户</option>
            <option value="tech">技术人员</option>
          </select>
        </div>

        <div class="input-group">
          <label>内容风格</label>
          <select class="input-select" v-model="contentStyle">
            <option value="formal">正式专业</option>
            <option value="casual">轻松活泼</option>
            <option value="creative">创意有趣</option>
            <option value="technical">技术详解</option>
          </select>
        </div>

        <div class="input-group">
          <label>内容类型</label>
          <select class="input-select" v-model="contentType">
            <option value="article">文章报道</option>
            <option value="promotion">宣传文案</option>
            <option value="blog">博客文章</option>
            <option value="social">社交媒体</option>
          </select>
        </div>

        <button class="create-btn" @click="createContent">
          <span>✍️</span>
          <span>开始创作</span>
        </button>

        <div v-if="contentResult" class="result-section">
          <div class="result-header">
            <span>📝 创作结果</span>
          </div>
          <div class="result-content" v-html="contentResult"></div>
        </div>
      </div>

      <!-- 数据分析 -->
      <div v-show="currentTab === 'data'" class="data-section">
        <div class="input-group">
          <label>数据来源描述</label>
          <textarea 
            v-model="dataSource"
            class="input-textarea"
            placeholder="请描述数据来源或粘贴数据..."
            rows="4"
          ></textarea>
        </div>

        <div class="input-group">
          <label>分析目标</label>
          <select class="input-select" v-model="dataGoal">
            <option value="trend">趋势分析</option>
            <option value="comparison">对比分析</option>
            <option value="correlation">相关性分析</option>
            <option value="forecast">预测分析</option>
          </select>
        </div>

        <div class="input-group">
          <label>输出图表类型</label>
          <select class="input-select" v-model="chartType">
            <option value="line">折线图</option>
            <option value="bar">柱状图</option>
            <option value="pie">饼图</option>
            <option value="table">数据表格</option>
          </select>
        </div>

        <button class="analyze-btn" @click="analyzeData">
          <span>📊</span>
          <span>开始分析</span>
        </button>

        <div v-if="dataResult" class="result-section">
          <div class="result-header">
            <span>📈 数据分析结果</span>
          </div>
          <div class="result-content" v-html="dataResult"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>import { ref } from 'vue';
const currentTab = ref('upload');
const uploadedFiles = ref([]);
const paperContent = ref('');
const analysisFocus = ref('summary');
const paperResult = ref('');
const contentTopic = ref('');
const contentAudience = ref('general');
const contentStyle = ref('formal');
const contentType = ref('article');
const contentResult = ref('');
const dataSource = ref('');
const dataGoal = ref('trend');
const chartType = ref('line');
const dataResult = ref('');
const getFileIcon = (type) => {
 const icons = {
 pdf: '📕',
 doc: '📘',
 docx: '📘',
 xlsx: '📗',
 xls: '📗',
 pptx: '📙',
 ppt: '📙',
 jpg: '🖼️',
 jpeg: '🖼️',
 png: '🖼️',
 txt: '📄'
 };
 const ext = type.split('/')[1] || type.split('.').pop().toLowerCase();
 return icons[ext] || '📄';
};
const formatSize = (bytes) => {
 if (bytes < 1024)
 return bytes + ' B';
 if (bytes < 1024 * 1024)
 return (bytes / 1024).toFixed(1) + ' KB';
 return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};
const triggerUpload = () => {
 document.getElementById('doc-upload').click();
};
const handleFileSelect = (event) => {
 const files = event.target.files;
 for (let i = 0; i < files.length; i++) {
 uploadedFiles.value.push({
 id: Date.now() + i,
 name: files[i].name,
 type: files[i].type,
 size: files[i].size
 });
 }
 event.target.value = '';
};
const handleDrop = (event) => {
 const files = event.dataTransfer.files;
 for (let i = 0; i < files.length; i++) {
 uploadedFiles.value.push({
 id: Date.now() + i,
 name: files[i].name,
 type: files[i].type,
 size: files[i].size
 });
 }
};
const removeFile = (id) => {
 const index = uploadedFiles.value.findIndex(f => f.id === id);
 if (index > -1) {
 uploadedFiles.value.splice(index, 1);
 }
};
const analyzePaper = async () => {
 if (!paperContent.value.trim())
 return;
 paperResult.value = `<p><strong>正在研读论文...</strong></p>`;
 await new Promise(resolve => setTimeout(resolve, 2000));
 paperResult.value = `<h3>论文综述</h3>
<p>根据您提供的论文内容，我为您整理了以下分析：</p>
<h4>📌 核心研究内容</h4>
<p>该论文探讨了人工智能在环境影响评价领域的应用，提出了一种基于深度学习的环境预测模型。</p>
<h4>🔬 研究方法</h4>
<p>作者采用了卷积神经网络(CNN)和长短期记忆网络(LSTM)相结合的混合架构，对历史环境监测数据进行训练。</p>
<h4>📊 关键发现</h4>
<ul>
<li>模型预测准确率达到95.2%</li>
<li>相比传统方法效率提升40%</li>
<li>在复杂环境场景下表现稳健</li>
</ul>
<h4>💡 研究意义</h4>
<p>该研究为环评领域提供了新的技术手段，有望推动环境影响评价的智能化进程。</p>`;
};
const createContent = async () => {
 if (!contentTopic.value.trim())
 return;
 contentResult.value = `<p><strong>正在创作内容...</strong></p>`;
 await new Promise(resolve => setTimeout(resolve, 2000));
 contentResult.value = `<h3>《${contentTopic.value}》宣传文案</h3>
<p>在当今数字化时代，${contentTopic.value}已经成为行业创新的核心驱动力。</p>
<h4>✨ 核心优势</h4>
<p>我们的${contentTopic.value}解决方案具有以下独特优势：</p>
<ul>
<li><strong>智能化</strong>：采用先进的AI技术，实现自动化和智能化</li>
<li><strong>高效性</strong>：大幅提升工作效率，节省时间成本</li>
<li><strong>可靠性</strong>：经过严格测试，稳定可靠</li>
<li><strong>易用性</strong>：简洁直观的用户界面，易于上手</li>
</ul>
<h4>🚀 应用场景</h4>
<p>${contentTopic.value}广泛应用于多个领域，包括环境监测、数据分析、智能办公等。</p>
<h4>📞 联系我们</h4>
<p>如果您对${contentTopic.value}感兴趣，欢迎联系我们了解更多详情！</p>`;
};
const analyzeData = async () => {
 if (!dataSource.value.trim())
 return;
 dataResult.value = `<p><strong>正在分析数据...</strong></p>`;
 await new Promise(resolve => setTimeout(resolve, 2000));
 dataResult.value = `<h3>数据分析报告</h3>
<h4>📈 趋势分析结果</h4>
<p>基于您提供的数据，我为您进行了深入分析：</p>
<h4>📊 关键指标</h4>
<table>
<tr><th>指标</th><th>数值</th><th>同比变化</th></tr>
<tr><td>市场规模</td><td>¥12.5亿</td><td><span style="color: green;">+15.3%</span></td></tr>
<tr><td>用户增长</td><td>85,000人</td><td><span style="color: green;">+23.1%</span></td></tr>
<tr><td>活跃度</td><td>68.5%</td><td><span style="color: red;">-2.3%</span></td></tr>
<tr><td>转化率</td><td>12.8%</td><td><span style="color: green;">+4.5%</span></td></tr>
</table>
<h4>🔍 洞察发现</h4>
<ul>
<li>Q3市场规模持续增长，同比上升15.3%</li>
<li>用户增长势头良好，环比增长显著</li>
<li>活跃度略有下降，建议优化用户留存策略</li>
<li>转化率表现优异，值得持续关注</li>
</ul>
<h4>💡 建议措施</h4>
<p>针对活跃度下降的问题，建议推出新功能或运营活动提升用户粘性。</p>`;
};
</script>

<style scoped>
.document-processor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}

.doc-header {
  padding: 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.doc-header h2 {
  margin: 0 0 12px 0;
  font-size: 18px;
  color: #1a1a2e;
}

.doc-tabs {
  display: flex;
  gap: 4px;
}

.doc-tab {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.doc-tab:hover {
  background: #e9ecef;
}

.doc-tab.active {
  background: #667eea;
  border-color: #667eea;
  color: white;
}

.doc-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #f8f9fa;
  border: 2px dashed #dee2e6;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f0f0ff;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 13px;
  color: #666;
}

.doc-upload {
  display: none;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.file-icon {
  font-size: 24px;
}

.file-info {
  flex: 1;
}

.file-name {
  display: block;
  font-size: 14px;
  color: #333;
}

.file-size {
  font-size: 12px;
  color: #666;
}

.remove-btn {
  padding: 6px 10px;
  background: #e9ecef;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  color: #666;
  cursor: pointer;
}

.remove-btn:hover {
  background: #dc3545;
  color: white;
}

.input-group {
  margin-bottom: 16px;
}

.input-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}

.input-text {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}

.input-text:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.input-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  resize: none;
  outline: none;
}

.input-textarea:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.input-select {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  cursor: pointer;
}

.input-select:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.analyze-btn, .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.analyze-btn:hover, .create-btn:hover {
  transform: translateY(-2px);
}

.result-section {
  margin-top: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.result-header {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.result-content {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}

.result-content h3 {
  font-size: 16px;
  margin-top: 0;
}

.result-content h4 {
  font-size: 14px;
  margin-bottom: 8px;
}

.result-content ul {
  margin: 8px 0;
  padding-left: 20px;
}

.result-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.result-content th, .result-content td {
  padding: 8px;
  border: 1px solid #dee2e6;
  text-align: left;
}

.result-content th {
  background: #e9ecef;
  font-weight: 500;
}
</style>