<template>
  <div class="task-chain-panel">
    <div class="panel-header">
      <div class="header-title">
        <span class="chain-icon">🔗</span>
        <span>任务链</span>
        <span class="task-count">{{ taskChain.totalTasks }} 个任务</span>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="refreshTasks" title="刷新">
          <span>🔄</span>
        </button>
        <button class="action-btn" @click="toggleAutoRefresh" :title="autoRefresh ? '关闭自动刷新' : '开启自动刷新'">
          <span>{{ autoRefresh ? '🔁' : '⏸️' }}</span>
        </button>
      </div>
    </div>

    <div class="chain-stats">
      <div class="stat-item">
        <span class="stat-value completed">{{ taskChain.completedTasks }}</span>
        <span class="stat-label">已完成</span>
      </div>
      <div class="stat-item">
        <span class="stat-value in-progress">{{ taskChain.inProgressTasks }}</span>
        <span class="stat-label">进行中</span>
      </div>
      <div class="stat-item">
        <span class="stat-value pending">{{ taskChain.pendingTasks }}</span>
        <span class="stat-label">待处理</span>
      </div>
      <div class="stat-item">
        <span class="stat-value failed">{{ taskChain.failedTasks }}</span>
        <span class="stat-label">失败</span>
      </div>
    </div>

    <div class="progress-bar">
      <div 
        class="progress-fill" 
        :style="{ width: progressPercent + '%' }"
        :class="getProgressClass()"
      ></div>
    </div>

    <div class="chain-content">
      <div class="dag-container">
        <svg ref="dagSvg" class="dag-svg">
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#667eea" />
            </marker>
            <marker id="arrowhead-active" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#10b981" />
            </marker>
            <marker id="arrowhead-failed" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#ef4444" />
            </marker>
          </defs>
          
          <!-- 连接线 -->
          <g class="connections">
            <path 
              v-for="(connection, index) in connections" 
              :key="'conn-' + index"
              :d="connection.path"
              :class="['connection', connection.class]"
              marker-end="url(#arrowhead)"
            />
          </g>
          
          <!-- 任务节点 -->
          <g 
            v-for="(task, index) in taskChain.tasks" 
            :key="'task-' + task.id"
            :transform="`translate(${task.x}, ${task.y})`"
            class="task-node"
            @click="selectTask(task)"
            @contextmenu.prevent="showTaskMenu(task, $event)"
          >
            <rect 
              :width="task.width" 
              :height="task.height"
              :rx="8"
              :class="['task-box', task.status]"
            />
            <text 
              :x="task.width / 2" 
              :y="task.height / 2 - 8"
              class="task-title"
              text-anchor="middle"
            >{{ task.title }}</text>
            <text 
              :x="task.width / 2" 
              :y="task.height / 2 + 8"
              class="task-status-text"
              text-anchor="middle"
            >{{ getStatusText(task.status) }}</text>
            <circle 
              v-if="task.status === 'in_progress'" 
              class="progress-ring"
              :cx="task.width - 15"
              :cy="15"
              r="8"
            />
          </g>
        </svg>
      </div>

      <div class="task-details" v-if="selectedTask">
        <div class="detail-header">
          <span class="detail-title">{{ selectedTask.title }}</span>
          <button class="close-detail" @click="selectedTask = null">×</button>
        </div>
        <div class="detail-body">
          <div class="detail-row">
            <span class="detail-label">状态:</span>
            <span :class="['detail-value', selectedTask.status]">{{ getStatusText(selectedTask.status) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">优先级:</span>
            <span class="detail-value">{{ getPriorityText(selectedTask.priority) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">预估时间:</span>
            <span class="detail-value">{{ selectedTask.estimatedTime }} 分钟</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">负责人:</span>
            <span class="detail-value">{{ selectedTask.assignee || '未分配' }}</span>
          </div>
          <div v-if="selectedTask.description" class="detail-row description">
            <span class="detail-label">描述:</span>
            <p class="detail-value">{{ selectedTask.description }}</p>
          </div>
          <div v-if="selectedTask.dependencies.length > 0" class="detail-row">
            <span class="detail-label">依赖任务:</span>
            <div class="detail-value">
              <span 
                v-for="dep in selectedTask.dependencies" 
                :key="dep" 
                class="dependency-tag"
              >{{ dep }}</span>
            </div>
          </div>
        </div>
        <div class="detail-actions">
          <button 
            v-if="selectedTask.status === 'pending'" 
            class="detail-btn primary"
            @click="startTask(selectedTask)"
          >▶️ 开始执行</button>
          <button 
            v-if="selectedTask.status === 'in_progress'" 
            class="detail-btn warning"
            @click="pauseTask(selectedTask)"
          >⏸️ 暂停</button>
          <button 
            v-if="selectedTask.status === 'failed'" 
            class="detail-btn success"
            @click="retryTask(selectedTask)"
          >🔄 重试</button>
          <button class="detail-btn" @click="editTask(selectedTask)">✏️ 编辑</button>
          <button class="detail-btn danger" @click="deleteTask(selectedTask)">🗑️ 删除</button>
        </div>
      </div>
    </div>

    <div v-if="showMenu" class="context-menu" :style="menuStyle">
      <div class="menu-item" @click="startTask(menuTask)">▶️ 开始执行</div>
      <div class="menu-item" @click="editTask(menuTask)">✏️ 编辑任务</div>
      <div class="menu-item" @click="viewTaskLog(menuTask)">📋 查看日志</div>
      <div class="menu-item danger" @click="deleteTask(menuTask)">🗑️ 删除任务</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';

const autoRefresh = ref(true);
const selectedTask = ref(null);
const showMenu = ref(false);
const menuTask = ref(null);
const menuStyle = reactive({ left: '0px', top: '0px' });
const dagSvg = ref(null);

const taskChain = reactive({
  totalTasks: 6,
  completedTasks: 2,
  inProgressTasks: 1,
  pendingTasks: 2,
  failedTasks: 1,
  tasks: [
    {
      id: 'task-1',
      title: '创建项目',
      status: 'completed',
      priority: 'critical',
      estimatedTime: 30,
      assignee: '架构师AI',
      description: '初始化项目结构和配置文件',
      dependencies: [],
      x: 50,
      y: 40,
      width: 140,
      height: 60
    },
    {
      id: 'task-2',
      title: '生成数据模型',
      status: 'completed',
      priority: 'high',
      estimatedTime: 45,
      assignee: '后端AI',
      description: '设计并生成数据库模型',
      dependencies: ['task-1'],
      x: 250,
      y: 40,
      width: 140,
      height: 60
    },
    {
      id: 'task-3',
      title: '生成API',
      status: 'in_progress',
      priority: 'high',
      estimatedTime: 60,
      assignee: '后端AI',
      description: '开发RESTful API接口',
      dependencies: ['task-2'],
      x: 450,
      y: 40,
      width: 140,
      height: 60
    },
    {
      id: 'task-4',
      title: '生成前端页面',
      status: 'pending',
      priority: 'high',
      estimatedTime: 90,
      assignee: '前端AI',
      description: '创建员工管理页面',
      dependencies: ['task-2'],
      x: 250,
      y: 140,
      width: 140,
      height: 60
    },
    {
      id: 'task-5',
      title: '列表页开发',
      status: 'failed',
      priority: 'medium',
      estimatedTime: 40,
      assignee: '前端AI',
      description: '开发员工列表页面',
      dependencies: ['task-4'],
      x: 450,
      y: 140,
      width: 140,
      height: 60
    },
    {
      id: 'task-6',
      title: '表单页开发',
      status: 'pending',
      priority: 'medium',
      estimatedTime: 40,
      assignee: '前端AI',
      description: '开发员工表单页面',
      dependencies: ['task-4'],
      x: 650,
      y: 140,
      width: 140,
      height: 60
    }
  ]
});

const connections = computed(() => {
  const conns = [];
  taskChain.tasks.forEach(task => {
    task.dependencies.forEach(depId => {
      const depTask = taskChain.tasks.find(t => t.id === depId);
      if (depTask) {
        const startX = depTask.x + depTask.width;
        const startY = depTask.y + depTask.height / 2;
        const endX = task.x;
        const endY = task.y + task.height / 2;
        
        let pathClass = 'connection-default';
        if (depTask.status === 'completed' && task.status === 'in_progress') {
          pathClass = 'connection-active';
        } else if (task.status === 'failed') {
          pathClass = 'connection-failed';
        }
        
        conns.push({
          path: `M ${startX} ${startY} L ${startX + 30} ${startY} L ${endX - 30} ${endY} L ${endX} ${endY}`,
          class: pathClass
        });
      }
    });
  });
  return conns;
});

const progressPercent = computed(() => {
  return Math.round((taskChain.completedTasks / taskChain.totalTasks) * 100);
});

const getProgressClass = () => {
  if (progressPercent.value >= 80) return 'success';
  if (progressPercent.value >= 50) return 'medium';
  return 'low';
};

const getStatusText = (status) => {
  const texts = {
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  };
  return texts[status] || status;
};

const getPriorityText = (priority) => {
  const texts = {
    critical: '🔴 关键',
    high: '🟠 高',
    medium: '🟡 中',
    low: '🟢 低'
  };
  return texts[priority] || priority;
};

const selectTask = (task) => {
  selectedTask.value = task;
};

const showTaskMenu = (task, event) => {
  menuTask.value = task;
  menuStyle.left = `${event.clientX}px`;
  menuStyle.top = `${event.clientY}px`;
  showMenu.value = true;
  
  document.addEventListener('click', closeMenu);
};

const closeMenu = () => {
  showMenu.value = false;
  document.removeEventListener('click', closeMenu);
};

const refreshTasks = () => {
  console.log('刷新任务');
};

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value;
};

const startTask = (task) => {
  task.status = 'in_progress';
  selectedTask.value = task;
  showMenu.value = false;
};

const pauseTask = (task) => {
  task.status = 'pending';
  selectedTask.value = task;
};

const retryTask = (task) => {
  task.status = 'in_progress';
  selectedTask.value = task;
};

const editTask = (task) => {
  showMenu.value = false;
  console.log('编辑任务:', task);
};

const deleteTask = (task) => {
  showMenu.value = false;
  const index = taskChain.tasks.findIndex(t => t.id === task.id);
  if (index > -1) {
    taskChain.tasks.splice(index, 1);
    taskChain.totalTasks--;
    if (task.status === 'completed') taskChain.completedTasks--;
    else if (task.status === 'in_progress') taskChain.inProgressTasks--;
    else if (task.status === 'pending') taskChain.pendingTasks--;
    else if (task.status === 'failed') taskChain.failedTasks--;
    selectedTask.value = null;
  }
};

const viewTaskLog = (task) => {
  showMenu.value = false;
  console.log('查看日志:', task);
};

let refreshInterval = null;

onMounted(() => {
  if (autoRefresh.value) {
    refreshInterval = setInterval(() => {
      console.log('自动刷新任务链');
    }, 5000);
  }
});

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});
</script>

<style scoped>
.task-chain-panel {
  background: linear-gradient(135deg, #166534 0%, #15803d 100%);
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
  color: #dcfce7;
}

.chain-icon {
  font-size: 20px;
}

.task-count {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  font-size: 12px;
  font-weight: normal;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  padding: 6px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.chain-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.1);
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
}

.stat-value.completed {
  color: #4ade80;
}

.stat-value.in-progress {
  color: #60a5fa;
}

.stat-value.pending {
  color: #eab308;
}

.stat-value.failed {
  color: #f87171;
}

.stat-label {
  font-size: 11px;
  color: #86efac;
}

.progress-bar {
  height: 6px;
  margin: 0 16px 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-fill.success {
  background: linear-gradient(90deg, #22c55e, #4ade80);
}

.progress-fill.medium {
  background: linear-gradient(90deg, #eab308, #facc15);
}

.progress-fill.low {
  background: linear-gradient(90deg, #f87171, #fca5a5);
}

.chain-content {
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.dag-container {
  position: relative;
  min-height: 200px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  overflow-x: auto;
}

.dag-svg {
  width: 100%;
  min-width: 800px;
  height: 200px;
}

.connection {
  fill: none;
  stroke-width: 2;
  transition: stroke 0.3s;
}

.connection-default {
  stroke: rgba(255, 255, 255, 0.3);
}

.connection-active {
  stroke: #10b981;
  stroke-dasharray: 5, 5;
  animation: dash 1s linear infinite;
}

.connection-failed {
  stroke: #ef4444;
}

@keyframes dash {
  to { stroke-dashoffset: -10; }
}

.task-node {
  cursor: pointer;
}

.task-box {
  fill: rgba(255, 255, 255, 0.15);
  stroke-width: 2;
  transition: all 0.3s;
}

.task-box:hover {
  transform: scale(1.02);
}

.task-box.completed {
  fill: rgba(34, 197, 94, 0.3);
  stroke: #22c55e;
}

.task-box.in_progress {
  fill: rgba(59, 130, 246, 0.3);
  stroke: #3b82f6;
}

.task-box.pending {
  fill: rgba(251, 191, 36, 0.2);
  stroke: #f59e0b;
}

.task-box.failed {
  fill: rgba(239, 68, 68, 0.3);
  stroke: #ef4444;
}

.task-title {
  fill: white;
  font-size: 12px;
  font-weight: 600;
}

.task-status-text {
  fill: rgba(255, 255, 255, 0.7);
  font-size: 10px;
}

.progress-ring {
  fill: none;
  stroke: #3b82f6;
  stroke-width: 2;
  animation: spin 2s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.task-details {
  margin-top: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.3);
}

.detail-title {
  font-size: 14px;
  font-weight: 600;
  color: #dcfce7;
}

.close-detail {
  background: none;
  border: none;
  color: #9ca3af;
  font-size: 20px;
  cursor: pointer;
  padding: 0 8px;
}

.detail-body {
  padding: 12px;
}

.detail-row {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.detail-row.description {
  flex-direction: column;
}

.detail-label {
  font-size: 12px;
  color: #86efac;
  min-width: 70px;
}

.detail-value {
  flex: 1;
  font-size: 12px;
  color: white;
}

.detail-value.completed {
  color: #4ade80;
}

.detail-value.in_progress {
  color: #60a5fa;
}

.detail-value.pending {
  color: #facc15;
}

.detail-value.failed {
  color: #f87171;
}

.dependency-tag {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(139, 92, 246, 0.4);
  border-radius: 4px;
  font-size: 11px;
  color: #c4b5fd;
  margin-right: 6px;
  margin-bottom: 4px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.detail-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.detail-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.detail-btn.primary {
  background: #3b82f6;
}

.detail-btn.success {
  background: #22c55e;
}

.detail-btn.warning {
  background: #f59e0b;
}

.detail-btn.danger {
  background: #ef4444;
}

.context-menu {
  position: fixed;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  z-index: 1000;
  min-width: 160px;
}

.menu-item {
  padding: 10px 16px;
  font-size: 13px;
  color: #e5e7eb;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-item:hover {
  background: #374151;
}

.menu-item.danger {
  color: #f87171;
}

.menu-item.danger:hover {
  background: rgba(239, 68, 68, 0.2);
}
</style>