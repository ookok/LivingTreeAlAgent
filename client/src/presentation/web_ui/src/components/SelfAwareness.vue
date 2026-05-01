<template>
  <div class="selfawareness-page">
    <div class="header">
      <h1>自我意识</h1>
      <p>自我反思、目标管理、自主控制</p>
    </div>
    
    <div class="stats-grid">
      <div class="panel">
        <div class="panel-title">自主级别</div>
        <div class="autonomy-display">
          <div class="autonomy-value">L{{ autonomyLevel }}</div>
          <div class="autonomy-label">{{ getAutonomyLabel(autonomyLevel) }}</div>
        </div>
        <div class="autonomy-controls">
          <button class="btn btn-secondary" @click="$emit('setAutonomyLevel', 0)">L0</button>
          <button class="btn btn-secondary" @click="$emit('setAutonomyLevel', 2)">L2</button>
          <button class="btn btn-secondary" @click="$emit('setAutonomyLevel', 4)">L4</button>
          <button class="btn btn-primary" @click="$emit('setAutonomyLevel', 5)">L5</button>
        </div>
      </div>
      
      <div class="panel">
        <div class="panel-title">目标统计</div>
        <div class="goal-stats">
          <div class="goal-stat">
            <div class="stat-value">{{ goalStats.total }}</div>
            <div class="stat-label">总目标</div>
          </div>
          <div class="goal-stat">
            <div class="stat-value">{{ goalStats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
          <div class="goal-stat">
            <div class="stat-value">{{ goalStats.active }}</div>
            <div class="stat-label">进行中</div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">活跃目标</div>
      <button class="btn btn-primary" style="margin-bottom: 15px;" @click="showAddGoalModal = true">添加目标</button>
      
      <div v-if="activeGoals.length === 0" class="alert alert-warning">
        暂无活跃目标
      </div>
      
      <div v-else class="goal-list">
        <div v-for="goal in activeGoals" :key="goal.id" class="goal-item">
          <div class="goal-title">
            {{ goal.description }}
            <span :class="['goal-priority', getPriorityClass(goal.priority)]">
              {{ getPriorityLabel(goal.priority) }}
            </span>
          </div>
          <div class="goal-progress">
            <div class="progress-bar">
              <div class="progress-fill green" :style="{ width: goal.progress + '%' }"></div>
            </div>
            <span>进度: {{ goal.progress }}%</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">自我反思记录</div>
      <button class="btn btn-secondary" style="margin-bottom: 15px;" @click="$emit('triggerReflection')">执行反思</button>
      
      <div v-if="reflectionHistory.length === 0" class="alert alert-warning">
        暂无反思记录
      </div>
      
      <div v-else class="reflection-list">
        <div v-for="reflection in reflectionHistory" :key="reflection.timestamp" class="reflection-item">
          <div class="reflection-time">{{ reflection.timestamp }}</div>
          <div v-for="(suggestion, index) in reflection.suggestions" :key="index" class="reflection-suggestion">
            {{ suggestion }}
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showAddGoalModal" class="modal-overlay" @click.self="showAddGoalModal = false">
      <div class="modal-content">
        <div class="modal-title">添加目标</div>
        <div class="form-group">
          <label>目标描述</label>
          <input type="text" class="form-control" v-model="newGoal.description" placeholder="输入目标描述">
        </div>
        <div class="form-group">
          <label>优先级 (0-1)</label>
          <input type="range" class="form-control" v-model="newGoal.priority" min="0" max="1" step="0.1">
          <span class="priority-value">{{ newGoal.priority }}</span>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showAddGoalModal = false">取消</button>
          <button class="btn btn-primary" @click="addGoal">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue';

defineProps({
  autonomyLevel: {
    type: Number,
    default: 3
  },
  goalStats: {
    type: Object,
    default: () => ({ total: 0, completed: 0, active: 0 })
  },
  activeGoals: {
    type: Array,
    default: () => []
  },
  reflectionHistory: {
    type: Array,
    default: () => []
  },
  getPriorityClass: {
    type: Function,
    required: true
  },
  getPriorityLabel: {
    type: Function,
    required: true
  }
});

const emit = defineEmits(['setAutonomyLevel', 'addGoal', 'triggerReflection']);

const showAddGoalModal = ref(false);
const newGoal = ref({ description: '', priority: 0.5 });

const getAutonomyLabel = (level) => {
  const labels = {
    0: '完全手动',
    1: '辅助模式',
    2: '半自主',
    3: '条件自主',
    4: '高度自主',
    5: '完全自主'
  };
  return labels[level] || '未知';
};

const addGoal = () => {
  if (!newGoal.value.description.trim()) {
    alert('请输入目标描述');
    return;
  }
  emit('addGoal', newGoal.value.description, parseFloat(newGoal.value.priority));
  showAddGoalModal.value = false;
  newGoal.value = { description: '', priority: 0.5 };
};
</script>

<style scoped>
.selfawareness-page {
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

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
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

.autonomy-display {
  text-align: center;
  padding: 30px;
}

.autonomy-value {
  font-size: 64px;
  font-weight: bold;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.autonomy-label {
  margin-top: 10px;
  color: rgba(255, 255, 255, 0.6);
}

.autonomy-controls {
  display: flex;
  justify-content: space-around;
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

.goal-stats {
  display: flex;
  justify-content: space-around;
  padding: 30px;
}

.goal-stat {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
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

.goal-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.goal-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #00d4ff;
}

.goal-title {
  font-weight: 600;
  margin-bottom: 10px;
}

.goal-priority {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 12px;
  margin-left: 10px;
}

.priority-high {
  background: rgba(255, 71, 87, 0.2);
  color: #ff4757;
}

.priority-medium {
  background: rgba(255, 165, 2, 0.2);
  color: #ffa502;
}

.priority-low {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.goal-progress {
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

.progress-fill.green {
  background: linear-gradient(90deg, #00ff88, #00cc6a);
}

.reflection-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reflection-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
}

.reflection-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 8px;
}

.reflection-suggestion {
  background: rgba(123, 47, 255, 0.1);
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 5px;
  font-size: 14px;
}

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
  background: rgba(26, 26, 46, 0.95);
  border-radius: 15px;
  padding: 25px;
  width: 90%;
  max-width: 500px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-title {
  font-size: 20px;
  margin-bottom: 20px;
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

.priority-value {
  color: rgba(255, 255, 255, 0.6);
  margin-left: 10px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>