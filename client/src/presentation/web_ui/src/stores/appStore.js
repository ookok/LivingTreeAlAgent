/**
 * 应用状态管理
 * 使用响应式API实现简单的状态管理
 */

import { reactive, computed } from 'vue';

const state = reactive({
  activeTab: 'ide',
  systemOnline: true,
  
  systemStatus: {
    system_state: 'uninitialized',
    subsystems: {}
  },
  
  apiStats: {
    total: 0,
    success_rate: 0,
    fallback_rate: 0,
    avg_execution_time: 0
  },
  
  cognitiveLoad: 0.3,
  
  memories: [],
  
  learningTasks: [],
  ewcStatus: { protected_params: 0, strength: 0 },
  
  reasoningStatus: {
    causal_enabled: true,
    symbolic_enabled: true,
    analogical_enabled: true,
    counterfactual_enabled: true
  },
  
  autonomyLevel: 3,
  goalStats: { total: 0, completed: 0, active: 0 },
  activeGoals: [],
  reflectionHistory: [],
  
  mcpStatus: { mode: 'local', service_status: 'disconnected' },
  mcpStats: { total_calls: 0, success_calls: 0, failed_calls: 0, fallback_calls: 0 }
});

export const useAppStore = () => {
  const activeSystems = computed(() => {
    return Object.entries(state.systemStatus.subsystems)
      .filter(([name, status]) => status.status === 'running')
      .map(([name]) => name);
  });

  const totalSystems = computed(() => {
    return Object.keys(state.systemStatus.subsystems).length;
  });

  const setActiveTab = (tab) => {
    state.activeTab = tab;
  };

  const updateSystemStatus = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.systemStatus = parsed;
    } catch (e) {
      console.error('解析系统状态失败:', e);
    }
  };

  const updateAPIStats = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.apiStats = parsed;
    } catch (e) {
      console.error('解析API统计失败:', e);
    }
  };

  const updateMemory = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.memories = parsed;
    } catch (e) {
      console.error('解析记忆数据失败:', e);
    }
  };

  const updateLearning = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.learningTasks = parsed.tasks || [];
      state.ewcStatus = parsed.ewc || { protected_params: 0, strength: 0 };
    } catch (e) {
      console.error('解析学习数据失败:', e);
    }
  };

  const updateSelfAwareness = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.autonomyLevel = parsed.autonomy?.level || 3;
      state.goalStats = parsed.goals || { total: 0, completed: 0, active: 0 };
      state.activeGoals = parsed.activeGoals || [];
      state.reflectionHistory = parsed.reflectionHistory || [];
      state.cognitiveLoad = parsed.cognitiveLoad || 0.3;
    } catch (e) {
      console.error('解析自我意识数据失败:', e);
    }
  };

  const updateMCPStatus = (data) => {
    try {
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      state.mcpStatus = parsed.status || { mode: 'disabled', service_status: 'disconnected' };
      state.mcpStats = parsed.stats || { total_calls: 0, success_calls: 0, failed_calls: 0, fallback_calls: 0 };
    } catch (e) {
      console.error('解析MCP状态失败:', e);
    }
  };

  const getStatusClass = (status) => {
    switch(status) {
      case 'running': return 'status-online';
      case 'error': return 'status-offline';
      default: return 'status-warning';
    }
  };

  const formatSystemName = (name) => {
    const map = {
      'brain_memory': '大脑记忆系统',
      'self_healing': '自修复系统',
      'continual_learning': '持续学习系统',
      'cognitive_reasoning': '认知推理系统',
      'self_awareness': '自我意识系统',
      'mcp_service': 'MCP服务',
      'api_gateway': 'API网关'
    };
    return map[name] || name;
  };

  const formatStatus = (status) => {
    const map = {
      'running': '运行中',
      'uninitialized': '未初始化',
      'error': '错误',
      'connecting': '连接中',
      'connected': '已连接',
      'disconnected': '已断开'
    };
    return map[status] || status;
  };

  const getPriorityClass = (priority) => {
    if (priority >= 0.7) return 'priority-high';
    if (priority >= 0.4) return 'priority-medium';
    return 'priority-low';
  };

  const getPriorityLabel = (priority) => {
    if (priority >= 0.7) return '高';
    if (priority >= 0.4) return '中';
    return '低';
  };

  return {
    state,
    activeSystems,
    totalSystems,
    setActiveTab,
    updateSystemStatus,
    updateAPIStats,
    updateMemory,
    updateLearning,
    updateSelfAwareness,
    updateMCPStatus,
    getStatusClass,
    formatSystemName,
    formatStatus,
    getPriorityClass,
    getPriorityLabel
  };
};

export default useAppStore;