<template>
  <div class="progressive-thinking">
    <!-- 头部 -->
    <div class="header">
      <h2>🧠 渐进式思考</h2>
      <div class="controls">
        <input 
          v-model="problem" 
          type="text" 
          placeholder="输入问题..." 
          class="problem-input"
        />
        <button class="think-btn" @click="startThinking">开始思考</button>
        <button class="clear-btn" @click="clearThinking">清空</button>
      </div>
    </div>

    <!-- 进度指示器 -->
    <div class="progress-container">
      <div class="progress-steps">
        <div 
          v-for="(step, index) in steps" 
          :key="index"
          class="step"
          :class="{ 
            active: currentStep === index, 
            completed: currentStep > index 
          }"
        >
          <div class="step-icon">{{ step.icon }}</div>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- 思考过程 -->
    <div class="thinking-content">
      <div class="thoughts-container">
        <div 
          v-for="(thought, index) in thoughts" 
          :key="index"
          class="thought-card"
          :class="{ active: index === thoughts.length - 1 }"
        >
          <div class="thought-header">
            <span class="thought-phase">{{ getPhaseLabel(thought.phase) }}</span>
            <span class="thought-confidence" :class="thought.confidence">
              {{ getConfidenceLabel(thought.confidence) }}
            </span>
          </div>
          <div class="thought-content">
            {{ thought.content }}
          </div>
          <div v-if="thought.evidence && thought.evidence.length" class="thought-evidence">
            <span class="evidence-label">证据:</span>
            <span v-for="(ev, idx) in thought.evidence" :key="idx" class="evidence-item">
              {{ ev }}
            </span>
          </div>
          <div class="thought-timestamp">{{ formatTime(thought.timestamp) }}</div>
        </div>
      </div>

      <!-- 最终结果 -->
      <div v-if="finalAnswer" class="final-result">
        <div class="result-header">
          <span class="result-title">🎯 最终答案</span>
          <span class="result-confidence" :class="overallConfidence">
            置信度: {{ getConfidenceLabel(overallConfidence) }}
          </span>
        </div>
        <div class="result-content">{{ finalAnswer }}</div>
      </div>
    </div>

    <!-- 证据链视图 -->
    <div class="evidence-chain">
      <h3>🔗 证据链</h3>
      <div class="evidence-flow">
        <div 
          v-for="(thought, index) in thoughts" 
          :key="index"
          class="evidence-node"
        >
          <div class="node-dot"></div>
          <div v-if="index < thoughts.length - 1" class="node-line"></div>
        </div>
      </div>
      <div class="evidence-summary">
        <div class="evidence-stat">
          <span class="stat-label">思考步骤</span>
          <span class="stat-value">{{ thoughts.length }}</span>
        </div>
        <div class="evidence-stat">
          <span class="stat-label">证据数量</span>
          <span class="stat-value">{{ totalEvidence }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, markRaw } from 'vue';
import { get_progressive_thinking_engine } from '@/business/ai_pipeline';

const thinkingEngine = get_progressive_thinking_engine();

// 响应式状态
const problem = ref('');
const thoughts = ref([]);
const finalAnswer = ref('');
const currentStep = ref(-1);
const overallConfidence = ref('medium');

// 步骤定义
const steps = [
  { icon: '🔍', label: '分析' },
  { icon: '💡', label: '创意' },
  { icon: '⚖️', label: '评估' },
  { icon: '🔗', label: '综合' },
  { icon: '✅', label: '验证' }
];

// 计算属性
const totalEvidence = computed(() => {
  return thoughts.value.reduce((sum, t) => sum + (t.evidence?.length || 0), 0);
});

// 开始思考
const startThinking = async () => {
  if (!problem.value.trim()) return;
  
  // 重置状态
  thoughts.value = [];
  finalAnswer.value = '';
  currentStep.value = -1;
  
  // 执行渐进式思考
  const trace = await thinkingEngine.think(problem.value);
  
  // 更新状态
  thoughts.value = trace.thoughts.map(t => ({
    id: t.id,
    phase: t.phase.value,
    content: t.content,
    confidence: t.confidence.value,
    evidence: t.evidence,
    timestamp: t.timestamp
  }));
  
  finalAnswer.value = trace.final_answer || '';
  overallConfidence.value = trace.confidence.value;
  currentStep.value = thoughts.value.length - 1;
};

// 清空
const clearThinking = () => {
  problem.value = '';
  thoughts.value = [];
  finalAnswer.value = '';
  currentStep.value = -1;
  overallConfidence.value = 'medium';
};

// 获取阶段标签
const getPhaseLabel = (phase) => {
  const labels = {
    analysis: '🔍 分析',
    ideation: '💡 创意',
    evaluation: '⚖️ 评估',
    synthesis: '🔗 综合',
    verification: '✅ 验证'
  };
  return labels[phase] || phase;
};

// 获取置信度标签
const getConfidenceLabel = (confidence) => {
  const labels = {
    low: '低',
    medium: '中',
    high: '高',
    very_high: '极高'
  };
  return labels[confidence] || confidence;
};

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
};
</script>

<style scoped>
.progressive-thinking {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
  border-radius: 12px;
  overflow: hidden;
}

.header {
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  color: white;
  padding: 20px;
}

.header h2 {
  margin: 0 0 15px 0;
  font-size: 20px;
}

.controls {
  display: flex;
  gap: 10px;
}

.problem-input {
  flex: 1;
  padding: 10px 14px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
}

.think-btn {
  padding: 10px 24px;
  background: white;
  color: #8b5cf6;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.think-btn:hover {
  transform: translateY(-1px);
}

.clear-btn {
  padding: 10px 16px;
  background: rgba(255,255,255,0.2);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.progress-container {
  background: white;
  padding: 15px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.progress-steps {
  display: flex;
  justify-content: space-around;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  opacity: 0.4;
  transition: all 0.3s ease;
}

.step.active {
  opacity: 1;
  transform: scale(1.05);
}

.step.completed {
  opacity: 0.7;
}

.step-icon {
  font-size: 24px;
}

.step-label {
  font-size: 12px;
  color: #64748b;
}

.thinking-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.thoughts-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.thought-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border-left: 4px solid #e2e8f0;
  transition: all 0.3s ease;
}

.thought-card.active {
  border-left-color: #8b5cf6;
  box-shadow: 0 4px 16px rgba(139, 92, 246, 0.15);
}

.thought-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.thought-phase {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.thought-confidence {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.thought-confidence.low {
  background: #fee2e2;
  color: #dc2626;
}

.thought-confidence.medium {
  background: #fef3c7;
  color: #d97706;
}

.thought-confidence.high {
  background: #dcfce7;
  color: #16a34a;
}

.thought-confidence.very_high {
  background: #dbeafe;
  color: #2563eb;
}

.thought-content {
  font-size: 14px;
  line-height: 1.6;
  color: #1e293b;
  margin-bottom: 10px;
}

.thought-evidence {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.evidence-label {
  font-size: 12px;
  color: #94a3b8;
}

.evidence-item {
  font-size: 11px;
  padding: 3px 8px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #64748b;
}

.thought-timestamp {
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
}

.final-result {
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  border-radius: 12px;
  padding: 20px;
  margin-top: 20px;
  color: white;
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.result-title {
  font-size: 16px;
  font-weight: 600;
}

.result-confidence {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 500;
  background: rgba(255,255,255,0.2);
}

.result-content {
  font-size: 14px;
  line-height: 1.7;
  opacity: 0.95;
}

.evidence-chain {
  background: white;
  padding: 20px;
  border-top: 1px solid #e2e8f0;
}

.evidence-chain h3 {
  margin: 0 0 15px 0;
  font-size: 14px;
  font-weight: 600;
}

.evidence-flow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.evidence-node {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.node-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #e2e8f0;
  transition: all 0.3s ease;
}

.evidence-node:first-child .node-dot {
  background: #8b5cf6;
}

.node-line {
  width: 100%;
  height: 2px;
  background: #e2e8f0;
  margin-top: 4px;
}

.evidence-summary {
  display: flex;
  gap: 30px;
}

.evidence-stat {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 11px;
  color: #94a3b8;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #8b5cf6;
}
</style>