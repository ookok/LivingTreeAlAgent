<template>
  <div class="learning-page">
    <div class="header">
      <h1>持续学习</h1>
      <p>管理学习进度和任务</p>
    </div>
    
    <div class="panel">
      <div class="panel-title">学习任务</div>
      <div v-if="learningTasks.length === 0" class="alert alert-warning">
        暂无学习任务
      </div>
      <div v-else class="task-list">
        <div v-for="task in learningTasks" :key="task.id" class="task-item">
          <div class="task-title">{{ task.name }}</div>
          <div class="task-progress">
            <div class="progress-bar">
              <div class="progress-fill purple" :style="{ width: task.progress + '%' }"></div>
            </div>
            <span>进度: {{ task.progress }}%</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">EWC保护状态</div>
      <div class="ewc-grid">
        <div class="ewc-item">
          <div class="ewc-label">保护参数数量</div>
          <div class="ewc-value">{{ ewcStatus.protected_params }}</div>
        </div>
        <div class="ewc-item">
          <div class="ewc-label">保护强度</div>
          <div class="ewc-value">{{ ewcStatus.strength }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue';

defineProps({
  learningTasks: {
    type: Array,
    default: () => []
  },
  ewcStatus: {
    type: Object,
    default: () => ({ protected_params: 0, strength: 0 })
  }
});
</script>

<style scoped>
.learning-page {
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

.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #7b2fff;
}

.task-title {
  font-weight: 600;
  margin-bottom: 10px;
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-fill.purple {
  background: linear-gradient(90deg, #7b2fff, #a855f7);
}

.ewc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.ewc-item {
  text-align: center;
  padding: 30px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
}

.ewc-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 10px;
}

.ewc-value {
  font-size: 32px;
  font-weight: bold;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
</style>