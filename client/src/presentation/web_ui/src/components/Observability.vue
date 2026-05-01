<template>
  <div class="observability-panel">
    <div class="panel-header">
      <h2>📊 任务链可观测性</h2>
      <div class="header-actions">
        <button @click="refreshData" class="refresh-btn">🔄 刷新</button>
        <button @click="clearData" class="clear-btn">🗑️ 清除</button>
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-grid">
      <div 
        v-for="metric in metrics" 
        :key="metric.title"
        :class="['metric-card', metric.status]"
      >
        <div class="metric-icon">{{ getMetricIcon(metric.title) }}</div>
        <div class="metric-content">
          <div class="metric-title">{{ metric.title }}</div>
          <div class="metric-value">
            {{ metric.value }}
            <span v-if="metric.unit" class="metric-unit">{{ metric.unit }}</span>
          </div>
        </div>
        <div v-if="metric.trend" class="metric-trend" :class="metric.trend >= 0 ? 'up' : 'down'">
          {{ metric.trend >= 0 ? '↑' : '↓' }} {{ Math.abs(metric.trend) }}%
        </div>
      </div>
    </div>

    <div class="content-row">
      <!-- 追踪时间线 -->
      <div class="section">
        <h3>⏱️ 追踪时间线</h3>
        <div v-if="timeline.trace_id" class="timeline-container">
          <div class="timeline-header">
            <span>Trace ID: {{ timeline.trace_id }}</span>
            <span class="duration">总耗时: {{ formatDuration(timeline.duration) }}</span>
          </div>
          <div class="timeline-tree">
            <div 
              v-for="node in timeline.nodes" 
              :key="node.span_id"
              class="tree-node"
            >
              <div :class="['node-header', node.status]">
                <span class="node-name">{{ node.name }}</span>
                <span class="node-duration">{{ formatDuration(node.duration) }}</span>
                <span :class="['status-badge', node.status]">{{ node.status }}</span>
              </div>
              <div v-if="node.children.length > 0" class="tree-children">
                <div 
                  v-for="child in node.children" 
                  :key="child.span_id"
                  class="child-node"
                >
                  <div :class="['child-header', child.status]">
                    <span class="child-name">{{ child.name }}</span>
                    <span class="child-duration">{{ formatDuration(child.duration) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <span>暂无追踪数据</span>
        </div>
      </div>

      <!-- 告警列表 -->
      <div class="section">
        <h3>⚠️ 告警</h3>
        <div v-if="alerts.length > 0" class="alerts-list">
          <div 
            v-for="alert in alerts" 
            :key="alert.alert_id"
            :class="['alert-item', alert.level, { resolved: alert.resolved }]"
          >
            <div class="alert-icon">{{ getAlertIcon(alert.level) }}</div>
            <div class="alert-content">
              <div class="alert-message">{{ alert.message }}</div>
              <div class="alert-time">{{ alert.formatted_time }}</div>
            </div>
            <button 
              v-if="!alert.resolved" 
              @click="resolveAlert(alert.alert_id)"
              class="resolve-btn"
            >
              ✓
            </button>
          </div>
        </div>
        <div v-else class="empty-state">
          <span>暂无告警</span>
        </div>
      </div>
    </div>

    <!-- 日志面板 -->
    <div class="section full-width">
      <h3>📝 日志</h3>
      <div class="logs-container">
        <div 
          v-for="log in logs" 
          :key="log.timestamp"
          :class="['log-item', log.level]"
        >
          <span class="log-time">{{ log.formatted_time }}</span>
          <span :class="['log-level', log.level]">{{ log.level.toUpperCase() }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const metrics = ref([]);
const timeline = ref({ trace_id: null, nodes: [], duration: 0 });
const logs = ref([]);
const alerts = ref([]);

let refreshInterval = null;

const fetchData = async () => {
  try {
    const data = await window.observability.getDashboardData();
    metrics.value = data.metrics;
    timeline.value = data.timeline;
    logs.value = data.logs;
    alerts.value = data.alerts;
  } catch (error) {
    console.error('获取可观测性数据失败:', error);
  }
};

const refreshData = () => {
  fetchData();
};

const clearData = async () => {
  try {
    await window.observability.clearAll();
    metrics.value = [];
    timeline.value = { trace_id: null, nodes: [], duration: 0 };
    logs.value = [];
    alerts.value = [];
  } catch (error) {
    console.error('清除数据失败:', error);
  }
};

const resolveAlert = async (alertId) => {
  try {
    await window.observability.resolveAlert(alertId);
    const alert = alerts.value.find(a => a.alert_id === alertId);
    if (alert) {
      alert.resolved = true;
    }
  } catch (error) {
    console.error('解决告警失败:', error);
  }
};

const formatDuration = (seconds) => {
  if (!seconds || seconds < 0) return '0ms';
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
};

const getMetricIcon = (title) => {
  if (title.includes('总数')) return '📊';
  if (title.includes('成功')) return '✅';
  if (title.includes('延迟')) return '⏱️';
  if (title.includes('活跃')) return '⚡';
  return '📈';
};

const getAlertIcon = (level) => {
  if (level === 'critical') return '🔴';
  if (level === 'warning') return '🟡';
  return '🔵';
};

onMounted(() => {
  fetchData();
  refreshInterval = setInterval(fetchData, 5000);
});

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});
</script>

<style scoped>
.observability-panel {
  padding: 20px;
  background: #ffffff;
  border-radius: 12px;
  min-height: 100%;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
  color: #1a1a2e;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.refresh-btn, .clear-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn {
  background: #667eea;
  color: white;
}

.clear-btn {
  background: #f3f4f6;
  color: #374151;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 10px;
  border-left: 4px solid #e5e7eb;
}

.metric-card.normal {
  border-left-color: #10b981;
}

.metric-card.warning {
  border-left-color: #f59e0b;
  background: #fffbeb;
}

.metric-card.critical {
  border-left-color: #ef4444;
  background: #fef2f2;
}

.metric-icon {
  font-size: 28px;
}

.metric-content {
  flex: 1;
}

.metric-title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.metric-unit {
  font-size: 14px;
  font-weight: normal;
  color: #6b7280;
  margin-left: 4px;
}

.metric-trend {
  font-size: 14px;
  font-weight: 600;
}

.metric-trend.up {
  color: #10b981;
}

.metric-trend.down {
  color: #ef4444;
}

.content-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.section {
  background: #f9fafb;
  border-radius: 10px;
  padding: 16px;
}

.section.full-width {
  grid-column: span 2;
}

.section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #1a1a2e;
}

.timeline-container {
  background: white;
  border-radius: 8px;
  padding: 12px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
  color: #6b7280;
}

.duration {
  font-weight: 600;
  color: #374151;
}

.tree-node {
  margin-bottom: 8px;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #f3f4f6;
  border-radius: 6px;
}

.node-header.ok {
  background: #ecfdf5;
}

.node-header.error {
  background: #fef2f2;
}

.node-name {
  flex: 1;
  font-weight: 500;
  color: #1f2937;
}

.node-duration {
  font-size: 12px;
  color: #6b7280;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.ok {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.error {
  background: #fee2e2;
  color: #991b1b;
}

.tree-children {
  margin-left: 20px;
  margin-top: 8px;
}

.child-node {
  margin-bottom: 4px;
}

.child-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 10px;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 13px;
}

.child-header.ok {
  background: #f0fdf4;
}

.child-header.error {
  background: #fef2f2;
}

.child-name {
  flex: 1;
  color: #374151;
}

.child-duration {
  font-size: 11px;
  color: #9ca3af;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 6px;
  background: white;
}

.alert-item.critical {
  border-left: 3px solid #ef4444;
  background: #fef2f2;
}

.alert-item.warning {
  border-left: 3px solid #f59e0b;
  background: #fffbeb;
}

.alert-item.info {
  border-left: 3px solid #3b82f6;
  background: #eff6ff;
}

.alert-item.resolved {
  opacity: 0.6;
}

.alert-icon {
  font-size: 18px;
}

.alert-content {
  flex: 1;
}

.alert-message {
  font-size: 13px;
  color: #1f2937;
  margin-bottom: 2px;
}

.alert-time {
  font-size: 11px;
  color: #9ca3af;
}

.resolve-btn {
  padding: 4px 8px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.empty-state {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
  font-size: 14px;
}

.logs-container {
  background: #1f2937;
  border-radius: 8px;
  padding: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid #374151;
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: #9ca3af;
  font-family: monospace;
}

.log-level {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.log-level.DEBUG {
  background: #3b82f6;
  color: white;
}

.log-level.INFO {
  background: #10b981;
  color: white;
}

.log-level.WARNING {
  background: #f59e0b;
  color: white;
}

.log-level.ERROR {
  background: #ef4444;
  color: white;
}

.log-level.CRITICAL {
  background: #dc2626;
  color: white;
}

.log-message {
  flex: 1;
  color: #d1d5db;
}

@media (max-width: 768px) {
  .content-row {
    grid-template-columns: 1fr;
  }
  
  .section.full-width {
    grid-column: span 1;
  }
  
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>