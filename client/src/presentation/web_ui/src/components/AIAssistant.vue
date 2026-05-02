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
  { id: 'translate', name: '翻译', icon: '🌐' },
  { id: 'eia', name: '环评报告', icon: '📄' },
  { id: 'feasibility', name: '可研报告', icon: '📊' }
]);

// 咨询意图关键词
const consultingKeywords = {
  eia_report: ['环评', '环境影响', '排放', '污染物', '环境评价', 'EIA'],
  feasibility_study: ['可研', '可行性', 'NPV', 'IRR', '财务分析', '投资估算'],
  financial_analysis: ['财务', '分析', '净现值', '敏感性分析', '蒙特卡洛'],
  code_generation: ['写代码', '生成代码', 'python', '脚本', '编程', '计算'],
  document_generation: ['报告', '文档', '撰写', '编写', '生成']
};

// 检测咨询意图
const detectConsultingIntent = (query) => {
  for (const [intent, keywords] of Object.entries(consultingKeywords)) {
    if (keywords.some(kw => query.includes(kw))) {
      return intent;
    }
  }
  return null;
};

// 获取意图描述
const getIntentDescription = (intent) => {
  const descriptions = {
    eia_report: '环境影响评价报告生成',
    feasibility_study: '可行性研究报告生成',
    financial_analysis: '财务分析报告生成',
    code_generation: 'Python代码生成',
    document_generation: '文档生成'
  };
  return descriptions[intent] || '咨询服务';
};

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
  
  // 检测咨询意图
  const consultingIntent = detectConsultingIntent(userMessage.content);
  
  if (consultingIntent) {
    // 自动触发咨询工程师
    await handleConsultingRequest(consultingIntent, userMessage.content);
  } else {
    await simulateThinking();
    const aiResponse = generateResponse(userMessage.content);
    messages.value.push(aiResponse);
    
    if (aiResponse.code) {
      emit('codeGenerated', aiResponse.code);
    }
  }
  
  isLoading.value = false;
  scrollToBottom();
  
  emit('sendMessage', {
    userMessage: userMessage.content,
    aiResponse: ''
  });
};

// 处理咨询请求
const handleConsultingRequest = async (intent, query) => {
  const intentDesc = getIntentDescription(intent);
  
  // 添加意图识别提示
  const intentMessage = {
    id: Date.now() + 1,
    isUser: false,
    content: `🎯 检测到咨询需求：${intentDesc}`,
    timestamp: new Date().toLocaleTimeString(),
    code: null,
    thought: true,
    codeChange: null,
    toolCall: null,
    executionResult: null,
    preview: null
  };
  messages.value.push(intentMessage);
  await scrollToBottom();
  
  // 模拟咨询工程师处理过程
  const tasks = ['初始化项目...', '分析需求...', '生成代码...', '验证数据...', '生成报告...'];
  for (const task of tasks) {
    currentTask.value = task;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  currentTask.value = '';
  
  // 根据意图生成模拟响应
  const response = generateConsultingResponse(intent, query);
  messages.value.push(response);
};

// 生成咨询响应
const generateConsultingResponse = (intent, query) => {
  const responses = {
    eia_report: {
      content: '已为您创建环评报告项目！',
      code: `# 环评排放量计算工具
import pandas as pd

def calculate_emission(pollutant_data):
    """
    计算污染物排放量
    
    Args:
        pollutant_data (dict): 污染物数据
    Returns:
        float: 排放量(t/a)
    """
    emission = pollutant_data['generation'] * (1 - pollutant_data['efficiency'] / 100)
    return round(emission, 2)

# 示例数据
project_data = {
    'project_name': '化工厂项目',
    'pollutant': 'SO2',
    'generation': 200.0,  # t/a
    'efficiency': 95.0    # %
}

result = calculate_emission(project_data)
print(f"排放量: {result} t/a")`,
      codeLang: 'python',
      codeChange: {
        file: 'emission_calculator.py',
        additions: 20,
        deletions: 0
      },
      executionResult: {
        success: true,
        output: '排放量: 10.0 t/a'
      },
      preview: {
        content: `<h3>环境影响评价报告</h3>
<p><strong>项目名称：</strong>化工厂项目</p>
<p><strong>评价等级：</strong>一级</p>
<p><strong>评价范围：</strong>水环境、大气环境、声环境</p>
<p><strong>主要污染物：</strong>SO2、NOx、粉尘</p>
<p><strong>排放量计算：</strong>10.0 t/a（达标）</p>`
      }
    },
    feasibility_study: {
      content: '已为您完成可行性研究分析！',
      code: `# 净现值(NPV)计算
def calculate_npv(cash_flows, discount_rate):
    """
    计算净现值
    
    Args:
        cash_flows (list): 现金流列表
        discount_rate (float): 折现率(%)
    Returns:
        float: NPV值
    """
    npv = 0
    for i, cf in enumerate(cash_flows):
        npv += cf / (1 + discount_rate / 100) ** i
    return round(npv, 2)

# 示例计算
cash_flows = [-1000, 200, 300, 400, 500, 600]  # 初始投资 + 年收益
discount_rate = 10
npv_result = calculate_npv(cash_flows, discount_rate)
irr = 15.2  # 内部收益率(%)

print(f"NPV: {npv_result} 万元")
print(f"IRR: {irr}%")`,
      codeLang: 'python',
      codeChange: {
        file: 'financial_analysis.py',
        additions: 20,
        deletions: 0
      },
      executionResult: {
        success: true,
        output: 'NPV: 407.89 万元\nIRR: 15.2%'
      },
      preview: {
        content: `<h3>可行性研究报告</h3>
<p><strong>项目名称：</strong>新建厂房项目</p>
<p><strong>总投资额：</strong>1000万元</p>
<p><strong>NPV：</strong>407.89万元（> 0，项目可行）</p>
<p><strong>IRR：</strong>15.2%（> 基准收益率10%）</p>
<p><strong>投资回收期：</strong>3.8年</p>`
      }
    },
    financial_analysis: {
      content: '已完成财务分析！',
      code: `# 敏感性分析
import numpy as np

def sensitivity_analysis(base_value, variables, ranges):
    """
    敏感性分析
    
    Args:
        base_value: 基准值
        variables: 变量列表
        ranges: 变化范围(%)
    Returns:
        dict: 敏感性结果
    """
    results = {}
    for var, rng in zip(variables, ranges):
        results[var] = {
            'low': base_value * (1 - rng / 100),
            'base': base_value,
            'high': base_value * (1 + rng / 100)
        }
    return results

# 示例分析
npv_base = 407.89
variables = ['收入', '成本', '折现率']
ranges = [10, 10, 5]

result = sensitivity_analysis(npv_base, variables, ranges)
print("敏感性分析结果:", result)`,
      codeLang: 'python',
      executionResult: {
        success: true,
        output: '敏感性分析结果: {...}'
      },
      preview: {
        content: `<h3>财务敏感性分析报告</h3>
<p><strong>基准NPV：</strong>407.89万元</p>
<p><strong>收入变化±10%：</strong>367.10 ~ 448.68万元</p>
<p><strong>成本变化±10%：</strong>448.68 ~ 367.10万元</p>
<p><strong>折现率变化±5%：</strong>428.28 ~ 386.50万元</p>`
      }
    },
    code_generation: {
      content: '已为您生成代码！',
      code: `# 自动生成的Python代码
def process_data(input_data):
    """
    数据处理函数
    
    Args:
        input_data (dict): 输入数据
    Returns:
        dict: 处理结果
    """
    result = {}
    # 数据处理逻辑
    for key, value in input_data.items():
        result[key] = value * 2
    return result

# 测试
test_data = {'a': 1, 'b': 2, 'c': 3}
print(process_data(test_data))`,
      codeLang: 'python',
      codeChange: {
        file: 'generated_code.py',
        additions: 15,
        deletions: 0
      },
      executionResult: {
        success: true,
        output: "{'a': 2, 'b': 4, 'c': 6}"
      }
    },
    document_generation: {
      content: '已为您生成文档！',
      preview: {
        content: `<h3>项目报告</h3>
<p>根据您的需求，已生成完整的项目报告，包含以下内容：</p>
<ul>
<li>项目概述</li>
<li>需求分析</li>
<li>技术方案</li>
<li>实施计划</li>
<li>风险评估</li>
</ul>`
      }
    }
  };
  
  const responseData = responses[intent] || responses.document_generation;
  
  return {
    id: Date.now() + 2,
    isUser: false,
    timestamp: new Date().toLocaleTimeString(),
    ...responseData
  };
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