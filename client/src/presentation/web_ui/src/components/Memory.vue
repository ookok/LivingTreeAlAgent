<template>
  <div class="memory-page">
    <div class="header">
      <h1>记忆系统</h1>
      <p>管理短期和长期记忆</p>
    </div>
    
    <div class="action-bar">
      <button class="btn btn-primary" @click="$emit('addMemory')">添加记忆</button>
      <button class="btn btn-secondary" @click="$emit('refreshMemory')">刷新</button>
    </div>
    
    <div v-if="memories.length === 0" class="alert alert-warning">
      暂无记忆记录
    </div>
    
    <div v-else class="memory-list">
      <div v-for="memory in memories" :key="memory.id" class="memory-item">
        <div class="memory-header">
          <span class="memory-type">{{ memory.type === 'short' ? '短期记忆' : '长期记忆' }}</span>
          <span class="memory-timestamp">{{ memory.timestamp }}</span>
        </div>
        <div class="memory-content">{{ memory.content }}</div>
        <div class="memory-score">关联度: {{ (memory.relevance * 100).toFixed(0) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';

defineProps({
  memories: {
    type: Array,
    default: () => []
  }
});

defineEmits(['addMemory', 'refreshMemory']);
</script>

<style scoped>
.memory-page {
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

.action-bar {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
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

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.2);
}

.alert {
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 15px;
  font-size: 14px;
}

.alert-warning {
  background: rgba(255, 165, 2, 0.1);
  border: 1px solid rgba(255, 165, 2, 0.3);
  color: #ffa502;
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.memory-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #00d4ff;
}

.memory-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.memory-type {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.memory-timestamp {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

.memory-content {
  font-size: 14px;
  line-height: 1.5;
}

.memory-score {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 8px;
}
</style>