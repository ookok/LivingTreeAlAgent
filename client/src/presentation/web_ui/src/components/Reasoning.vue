<template>
  <div class="reasoning-page">
    <div class="header">
      <h1>认知推理</h1>
      <p>因果推理、符号推理、类比推理、反事实推理</p>
    </div>
    
    <div class="panel">
      <div class="panel-title">推理引擎状态</div>
      <div class="engine-grid">
        <div class="engine-card" :class="{ enabled: reasoningStatus.causal_enabled }">
          <div class="engine-icon">🔗</div>
          <div class="engine-name">因果推理</div>
          <div class="engine-status">{{ reasoningStatus.causal_enabled ? '启用' : '禁用' }}</div>
        </div>
        <div class="engine-card" :class="{ enabled: reasoningStatus.symbolic_enabled }">
          <div class="engine-icon">📐</div>
          <div class="engine-name">符号推理</div>
          <div class="engine-status">{{ reasoningStatus.symbolic_enabled ? '启用' : '禁用' }}</div>
        </div>
        <div class="engine-card" :class="{ enabled: reasoningStatus.analogical_enabled }">
          <div class="engine-icon">🔄</div>
          <div class="engine-name">类比推理</div>
          <div class="engine-status">{{ reasoningStatus.analogical_enabled ? '启用' : '禁用' }}</div>
        </div>
        <div class="engine-card" :class="{ enabled: reasoningStatus.counterfactual_enabled }">
          <div class="engine-icon">🤔</div>
          <div class="engine-name">反事实推理</div>
          <div class="engine-status">{{ reasoningStatus.counterfactual_enabled ? '启用' : '禁用' }}</div>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">执行推理</div>
      <div class="form-group">
        <label>输入问题</label>
        <textarea class="form-control" rows="4" v-model="query" placeholder="输入要推理的问题..."></textarea>
      </div>
      <div class="form-group">
        <label>推理类型</label>
        <select class="form-control" v-model="type">
          <option value="causal">因果推理</option>
          <option value="symbolic">符号推理</option>
          <option value="analogical">类比推理</option>
          <option value="counterfactual">反事实推理</option>
        </select>
      </div>
      <button class="btn btn-primary" @click="executeReasoning">执行推理</button>
      
      <div v-if="result" class="result-card">
        <div class="result-title">推理结果</div>
        <div class="result-content">{{ result }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue';

defineProps({
  reasoningStatus: {
    type: Object,
    default: () => ({
      causal_enabled: true,
      symbolic_enabled: true,
      analogical_enabled: true,
      counterfactual_enabled: true
    })
  }
});

const emit = defineEmits(['executeReasoning']);

const query = ref('');
const type = ref('causal');
const result = ref('');

const executeReasoning = () => {
  if (!query.value.trim()) {
    alert('请输入问题');
    return;
  }
  emit('executeReasoning', query.value, type.value);
};

defineEmits(['executeReasoning']);
</script>

<style scoped>
.reasoning-page {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.header p {
  color: rgba(255, 255, 255, 0.6);
}

.panel {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 20px;
}

.panel-title {
  font-size: 18px;
  margin-bottom: 20px;
}

.engine-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.engine-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.engine-card.enabled {
  border-color: #00d4ff;
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
}

.engine-icon {
  font-size: 32px;
  margin-bottom: 10px;
}

.engine-name {
  font-weight: 600;
  margin-bottom: 5px;
}

.engine-status {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

.form-control {
  width: 100%;
  padding: 10px 15px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: #00d4ff;
  box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #00d4ff, #7b2fff);
  color: #ffffff;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
}

.result-card {
  margin-top: 20px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #00d4ff;
}

.result-title {
  font-weight: 600;
  margin-bottom: 10px;
}

.result-content {
  font-size: 14px;
  line-height: 1.5;
}
</style>