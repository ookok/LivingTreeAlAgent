<template>
  <div class="thinking-panel">
    <div class="panel-header">
      <div class="header-title">
        <span class="thinking-icon">🧠</span>
        <span>AI 思考过程</span>
      </div>
      <button 
        :class="['collapse-btn', { collapsed: isCollapsed }]"
        @click="isCollapsed = !isCollapsed"
      >
        {{ isCollapsed ? '展开' : '折叠' }}
      </button>
    </div>

    <div v-show="!isCollapsed" class="thinking-content">
      <div class="thinking-tabs">
        <button 
          v-for="tab in thinkingTabs"
          :key="tab.id"
          :class="['tab-btn', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.name }}</span>
        </button>
      </div>

      <div class="tab-content">
        <!-- 需求理解 -->
        <div v-if="activeTab === 'understanding'" class="tab-panel">
          <div class="section-header">
            <span>📋 需求分析</span>
            <span class="confidence" :class="getConfidenceClass(thinkingData.understanding.confidence)">
              {{ thinkingData.understanding.confidence }}%
            </span>
          </div>
          <div class="analysis-content">
            <div class="analysis-item">
              <span class="label">用户意图:</span>
              <span class="value">{{ thinkingData.understanding.intent }}</span>
            </div>
            <div class="analysis-item">
              <span class="label">核心需求:</span>
              <span class="value">{{ thinkingData.understanding.coreRequirement }}</span>
            </div>
            <div class="analysis-item">
              <span class="label">关键实体:</span>
              <div class="tags">
                <span 
                  v-for="entity in thinkingData.understanding.entities" 
                  :key="entity" 
                  class="tag"
                >{{ entity }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 技术决策 -->
        <div v-if="activeTab === 'decision'" class="tab-panel">
          <div class="section-header">
            <span>⚙️ 技术决策</span>
          </div>
          <div class="decision-tree">
            <div 
              v-for="(decision, index) in thinkingData.decisions" 
              :key="index"
              class="decision-item"
            >
              <div class="decision-header">
                <span class="decision-num">{{ index + 1 }}</span>
                <span class="decision-question">{{ decision.question }}</span>
              </div>
              <div class="decision-options">
                <div 
                  v-for="(option, optIndex) in decision.options" 
                  :key="optIndex"
                  :class="['option', { selected: option.selected }]"
                >
                  <span class="option-radio">{{ option.selected ? '●' : '○' }}</span>
                  <span class="option-text">{{ option.value }}</span>
                  <span v-if="option.selected" class="option-score">得分: {{ option.score }}</span>
                </div>
              </div>
              <div v-if="decision.reason" class="decision-reason">
                <span>💡 选择理由: {{ decision.reason }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 风险判断 -->
        <div v-if="activeTab === 'risk'" class="tab-panel">
          <div class="section-header">
            <span>⚠️ 风险评估</span>
          </div>
          <div class="risk-list">
            <div 
              v-for="(risk, index) in thinkingData.risks" 
              :key="index"
              :class="['risk-item', risk.level.toLowerCase()]"
            >
              <div class="risk-header">
                <span :class="['risk-icon', risk.level.toLowerCase()]">
                  {{ getRiskIcon(risk.level) }}
                </span>
                <span class="risk-title">{{ risk.title }}</span>
                <span :class="['risk-level', risk.level.toLowerCase()]">{{ risk.level }}</span>
              </div>
              <div class="risk-description">{{ risk.description }}</div>
              <div class="risk-mitigation">
                <span class="mitigation-label">应对方案:</span>
                <span class="mitigation-content">{{ risk.mitigation }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 替代方案 -->
        <div v-if="activeTab === 'alternatives'" class="tab-panel">
          <div class="section-header">
            <span>🔄 替代方案</span>
          </div>
          <div class="alternatives-grid">
            <div 
              v-for="(alt, index) in thinkingData.alternatives" 
              :key="index"
              :class="['alt-card', { preferred: alt.preferred }]"
            >
              <div class="alt-header">
                <span class="alt-num">{{ index + 1 }}</span>
                <span v-if="alt.preferred" class="preferred-badge">推荐</span>
              </div>
              <div class="alt-title">{{ alt.title }}</div>
              <div class="alt-pros">
                <span class="pros-label">优点:</span>
                <ul>
                  <li v-for="(pro, i) in alt.pros" :key="i">{{ pro }}</li>
                </ul>
              </div>
              <div class="alt-cons">
                <span class="cons-label">缺点:</span>
                <ul>
                  <li v-for="(con, i) in alt.cons" :key="i">{{ con }}</li>
                </ul>
              </div>
              <div class="alt-score">综合评分: {{ alt.score }}/10</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

const isCollapsed = ref(false);
const activeTab = ref('understanding');

const thinkingTabs = [
  { id: 'understanding', name: '需求理解', icon: '📋' },
  { id: 'decision', name: '技术决策', icon: '⚙️' },
  { id: 'risk', name: '风险判断', icon: '⚠️' },
  { id: 'alternatives', name: '替代方案', icon: '🔄' }
];

const thinkingData = reactive({
  understanding: {
    confidence: 92,
    intent: '代码生成',
    coreRequirement: '创建一个员工管理系统的CRUD页面',
    entities: ['员工', '管理系统', 'CRUD', '页面']
  },
  decisions: [
    {
      question: '选择前端框架',
      options: [
        { value: 'Vue 3', selected: true, score: 85 },
        { value: 'React', selected: false, score: 78 },
        { value: 'Angular', selected: false, score: 65 }
      ],
      reason: '团队熟悉Vue，生态成熟，适合快速开发'
    },
    {
      question: '选择UI组件库',
      options: [
        { value: 'Element Plus', selected: true, score: 90 },
        { value: 'Ant Design Vue', selected: false, score: 82 },
        { value: 'Naive UI', selected: false, score: 75 }
      ],
      reason: 'Element Plus文档完善，组件丰富'
    }
  ],
  risks: [
    {
      level: 'HIGH',
      title: '数据安全风险',
      description: '员工信息包含敏感数据，需要加密存储',
      mitigation: '1. 使用HTTPS传输 2. 数据库加密 3. 权限控制'
    },
    {
      level: 'MEDIUM',
      title: '性能风险',
      description: '大量员工数据可能导致页面加载缓慢',
      mitigation: '1. 分页处理 2. 虚拟滚动 3. 数据缓存'
    }
  ],
  alternatives: [
    {
      title: '前后端分离架构',
      pros: ['职责清晰', '易于扩展', '可独立部署'],
      cons: ['开发复杂度高', '需要额外的API开发'],
      score: 9,
      preferred: true
    },
    {
      title: '单体应用',
      pros: ['开发简单', '部署方便', '调试容易'],
      cons: ['扩展性差', '耦合度高'],
      score: 7,
      preferred: false
    }
  ]
});

const getConfidenceClass = (confidence) => {
  if (confidence >= 80) return 'high';
  if (confidence >= 60) return 'medium';
  return 'low';
};

const getRiskIcon = (level) => {
  const icons = {
    HIGH: '🔴',
    MEDIUM: '🟡',
    LOW: '🟢',
    CRITICAL: '💀'
  };
  return icons[level] || '⚪';
};
</script>

<style scoped>
.thinking-panel {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #e0e7ff;
}

.thinking-icon {
  font-size: 20px;
}

.collapse-btn {
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #e0e7ff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.thinking-content {
  padding: 16px;
}

.thinking-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  background: rgba(0, 0, 0, 0.2);
  padding: 4px;
  border-radius: 8px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #a5b4fc;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tab-btn.active {
  background: rgba(139, 92, 246, 0.5);
  color: white;
}

.tab-content {
  min-height: 200px;
}

.tab-panel {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #e0e7ff;
}

.confidence {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.confidence.high {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.confidence.medium {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.confidence.low {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.analysis-content {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.analysis-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.analysis-item:last-child {
  border-bottom: none;
}

.analysis-item .label {
  font-size: 12px;
  color: #93c5fd;
}

.analysis-item .value {
  font-size: 14px;
  color: white;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 4px 10px;
  background: rgba(139, 92, 246, 0.4);
  border-radius: 4px;
  font-size: 12px;
  color: #c4b5fd;
}

.decision-tree {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.decision-item {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.decision-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.decision-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(139, 92, 246, 0.5);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.decision-question {
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
}

.decision-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 32px;
}

.option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  transition: all 0.2s;
}

.option.selected {
  background: rgba(139, 92, 246, 0.3);
  border: 1px solid rgba(139, 92, 246, 0.5);
}

.option-radio {
  font-size: 12px;
  color: #9ca3af;
}

.option.selected .option-radio {
  color: #a855f7;
}

.option-text {
  flex: 1;
  font-size: 12px;
  color: #d1d5db;
}

.option.selected .option-text {
  color: white;
}

.option-score {
  font-size: 11px;
  color: #fbbf24;
}

.decision-reason {
  margin-top: 8px;
  padding-left: 32px;
  font-size: 12px;
  color: #a5b4fc;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-item {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
  border-left: 3px solid transparent;
}

.risk-item.high {
  border-left-color: #ef4444;
}

.risk-item.medium {
  border-left-color: #f59e0b;
}

.risk-item.low {
  border-left-color: #22c55e;
}

.risk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.risk-icon {
  font-size: 16px;
}

.risk-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
}

.risk-level {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.risk-level.high {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.risk-level.medium {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.risk-level.low {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.risk-description {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 8px;
}

.risk-mitigation {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mitigation-label {
  font-size: 11px;
  color: #60a5fa;
}

.mitigation-content {
  font-size: 12px;
  color: #a5b4fc;
  padding-left: 8px;
}

.alternatives-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.alt-card {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.alt-card.preferred {
  border-color: rgba(139, 92, 246, 0.5);
  background: rgba(139, 92, 246, 0.1);
}

.alt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.alt-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.5);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.preferred-badge {
  padding: 2px 8px;
  background: rgba(139, 92, 246, 0.5);
  border-radius: 4px;
  font-size: 10px;
  color: #c4b5fd;
}

.alt-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
  margin-bottom: 8px;
}

.alt-pros, .alt-cons {
  font-size: 11px;
  margin-bottom: 6px;
}

.pros-label, .cons-label {
  display: block;
  color: #4ade80;
  margin-bottom: 2px;
}

.cons-label {
  color: #f87171;
}

.alt-pros ul, .alt-cons ul {
  margin: 0;
  padding-left: 16px;
}

.alt-pros li, .alt-cons li {
  color: #9ca3af;
  margin-bottom: 2px;
}

.alt-score {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: #fbbf24;
  text-align: right;
}
</style>