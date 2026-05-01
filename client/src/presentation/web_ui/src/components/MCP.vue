<template>
  <div class="mcp-page">
    <div class="header">
      <h1>MCP服务</h1>
      <p>管理MCP服务和降级策略</p>
    </div>
    
    <div class="panel">
      <div class="panel-title">服务状态</div>
      <div class="status-row">
        <span class="status-indicator" :class="mcpStatus.service_status === 'connected' ? 'status-online' : 'status-offline'"></span>
        <div class="status-info">
          <div class="status-text">{{ mcpStatus.service_status === 'connected' ? 'MCP服务已连接' : 'MCP服务未连接' }}</div>
          <div class="mode-text">模式: {{ getModeLabel(mcpStatus.mode) }}</div>
        </div>
        <button class="btn btn-primary" @click="$emit('toggleMCP')">
          {{ mcpStatus.service_status === 'connected' ? '断开' : '连接' }}
        </button>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">调用统计</div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-title">总调用</div>
          <div class="stat-value">{{ mcpStats.total_calls.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">成功</div>
          <div class="stat-value success">{{ mcpStats.success_calls.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">失败</div>
          <div class="stat-value error">{{ mcpStats.failed_calls.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">降级调用</div>
          <div class="stat-value warning">{{ mcpStats.fallback_calls.toLocaleString() }}</div>
        </div>
      </div>
    </div>
    
    <div class="panel">
      <div class="panel-title">测试工具调用</div>
      <div class="form-group">
        <label>工具名称</label>
        <select class="form-control" v-model="toolName">
          <option value="web_search">web_search</option>
          <option value="calculator">calculator</option>
          <option value="file_read">file_read</option>
          <option value="code_execution">code_execution</option>
        </select>
      </div>
      <div class="form-group">
        <label>参数 (JSON)</label>
        <textarea class="form-control" rows="3" v-model="toolParams" placeholder='{"query": "test"}'></textarea>
      </div>
      <button class="btn btn-primary" @click="testTool">执行调用</button>
      
      <div v-if="toolResult" class="result-card">
        <div class="result-title">调用结果</div>
        <pre class="result-content">{{ JSON.stringify(toolResult, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue';

defineProps({
  mcpStatus: {
    type: Object,
    default: () => ({ mode: 'local', service_status: 'disconnected' })
  },
  mcpStats: {
    type: Object,
    default: () => ({ total_calls: 0, success_calls: 0, failed_calls: 0, fallback_calls: 0 })
  }
});

const emit = defineEmits(['toggleMCP', 'callMCPTool']);

const toolName = ref('web_search');
const toolParams = ref('{"query": "test"}');
const toolResult = ref(null);

const getModeLabel = (mode) => {
  const labels = {
    'local': '本地模式',
    'remote': '远程模式',
    'fallback': '降级模式',
    'disabled': '已禁用'
  };
  return labels[mode] || mode;
};

const testTool = () => {
  try {
    const params = JSON.parse(toolParams.value);
    emit('callMCPTool', toolName.value, params);
  } catch (e) {
    alert('无效的JSON参数');
  }
};

const setToolResult = (result) => {
  toolResult.value = result;
};

defineExpose({ setToolResult });
</script>

<style scoped>
.mcp-page {
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

.status-row {
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-online {
  background: #00ff88;
  box-shadow: 0 0 10px #00ff88;
}

.status-offline {
  background: #ff4757;
  box-shadow: 0 0 10px #ff4757;
}

.status-info {
  flex: 1;
}

.status-text {
  font-weight: 600;
}

.mode-text {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
}

.stat-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 10px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-value.success {
  background: linear-gradient(90deg, #00ff88, #00cc6a);
  -webkit-background-clip: text;
  background-clip: text;
}

.stat-value.error {
  background: linear-gradient(90deg, #ff4757, #ff6b81);
  -webkit-background-clip: text;
  background-clip: text;
}

.stat-value.warning {
  background: linear-gradient(90deg, #ffa502, #ff8c00);
  -webkit-background-clip: text;
  background-clip: text;
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
  white-space: pre-wrap;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}
</style>