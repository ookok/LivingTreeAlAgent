<template>
  <div class="dashboard">
    <div class="header">
      <h1>控制面板</h1>
      <p>实时监控系统状态和性能指标</p>
    </div>
    
    <div class="dashboard-cards">
      <div class="card">
        <div class="card-title">系统状态</div>
        <div class="card-value">{{ systemStatus.system_state }}</div>
        <div class="card-subtitle">
          <span class="status-indicator" :class="systemStatus.system_state === 'running' ? 'status-online' : 'status-offline'"></span>
          {{ systemStatus.system_state === 'running' ? '运行中' : '未运行' }}
        </div>
      </div>
      
      <div class="card">
        <div class="card-title">活跃子系统</div>
        <div class="card-value">{{ activeSystems.length }}</div>
        <div class="card-subtitle">共 {{ totalSystems }} 个子系统</div>
      </div>
      
      <div class="card">
        <div class="card-title">API调用次数</div>
        <div class="card-value">{{ apiStats.total.toLocaleString() }}</div>
        <div class="card-subtitle">成功率 {{ (apiStats.success_rate * 100).toFixed(1) }}%</div>
      </div>
      
      <div class="card">
        <div class="card-title">认知负载</div>
        <div class="card-value">{{ (cognitiveLoad * 100).toFixed(0) }}%</div>
        <div class="card-subtitle">
          <span v-if="cognitiveLoad > 0.7" class="status-indicator status-warning"></span>
          {{ cognitiveLoad > 0.7 ? '负载较高' : '正常' }}
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">系统状态概览</div>
      <div class="system-list">
        <div v-for="(status, name) in systemStatus.subsystems" :key="name" class="system-item">
          <div class="system-info">
            <span class="status-indicator" :class="getStatusClass(status.status)"></span>
            <span class="system-name">{{ formatSystemName(name) }}</span>
          </div>
          <span class="system-status-text">{{ formatStatus(status.status) }}</span>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">性能指标</div>
      <div class="metrics-grid">
        <div class="metric-item">
          <div class="metric-header">
            <span class="metric-label">API平均响应时间</span>
            <span class="metric-value">{{ apiStats.avg_execution_time.toFixed(2) }}s</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill blue" :style="{ width: Math.min(apiStats.avg_execution_time * 20, 100) + '%' }"></div>
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-header">
            <span class="metric-label">降级调用率</span>
            <span class="metric-value">{{ (apiStats.fallback_rate * 100).toFixed(1) }}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill orange" :style="{ width: apiStats.fallback_rate * 100 + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue';

defineProps({
  systemStatus: {
    type: Object,
    required: true
  },
  apiStats: {
    type: Object,
    required: true
  },
  cognitiveLoad: {
    type: Number,
    default: 0.3
  },
  activeSystems: {
    type: Array,
    default: () => []
  },
  totalSystems: {
    type: Number,
    default: 0
  },
  getStatusClass: {
    type: Function,
    required: true
  },
  formatSystemName: {
    type: Function,
    required: true
  },
  formatStatus: {
    type: Function,
    required: true
  }
});
</script>

<style scoped>
.dashboard {
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

.dashboard-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 40px rgba(0, 212, 255, 0.2);
}

.card-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 10px;
}

.card-value {
  font-size: 32px;
  font-weight: bold;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 5px;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 8px;
}

.status-online {
  background: #00ff88;
  box-shadow: 0 0 10px #00ff88;
}

.status-offline {
  background: #ff4757;
  box-shadow: 0 0 10px #ff4757;
}

.status-warning {
  background: #ffa502;
  box-shadow: 0 0 10px #ffa502;
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

.system-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.system-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
}

.system-info {
  display: flex;
  align-items: center;
}

.system-name {
  margin-left: 12px;
}

.system-status-text {
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.metric-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 15px;
}

.metric-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.metric-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.metric-value {
  font-size: 14px;
  font-weight: 600;
}

.progress-bar {
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

.progress-fill.blue {
  background: linear-gradient(90deg, #00d4ff, #0099cc);
}

.progress-fill.orange {
  background: linear-gradient(90deg, #ffa502, #ff8c00);
}
</style>