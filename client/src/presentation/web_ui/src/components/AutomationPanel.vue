<template>
  <div class="automation-panel">
    <div class="panel-header">
      <div class="header-left">
        <h2>⚙️ 自动化任务</h2>
        <span class="task-count">{{ tasks.length }} 个任务</span>
      </div>
      <div class="header-right">
        <button class="add-btn" @click="showAddModal = true">
          <span>➕</span>
          <span>添加任务</span>
        </button>
      </div>
    </div>

    <div class="task-list">
      <div v-if="tasks.length === 0" class="empty-state">
        <span class="empty-icon">📋</span>
        <span class="empty-text">暂无自动化任务</span>
        <span class="empty-hint">点击上方按钮创建第一个任务</span>
      </div>
      
      <div 
        v-for="task in tasks" 
        :key="task.id"
        :class="['task-card', { running: task.status === 'running', paused: task.status === 'paused' }]"
      >
        <div class="task-header">
          <div class="task-status">
            <span :class="['status-dot', task.status]"></span>
            <span class="task-name">{{ task.name }}</span>
          </div>
          <div class="task-actions">
            <button class="action-btn" @click="toggleTask(task)" :title="task.status === 'running' ? '暂停' : '启动'">
              {{ task.status === 'running' ? '⏸️' : '▶️' }}
            </button>
            <button class="action-btn" @click="editTask(task)" title="编辑">✏️</button>
            <button class="action-btn" @click="deleteTask(task)" title="删除">🗑️</button>
          </div>
        </div>
        
        <div class="task-info">
          <div class="info-row">
            <span class="info-label">⏰ 触发方式</span>
            <span class="info-value">{{ getTriggerLabel(task.trigger) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">📅 下次执行</span>
            <span class="info-value">{{ task.nextRun }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">🔄 重复</span>
            <span class="info-value">{{ getScheduleLabel(task.schedule) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">📊 执行次数</span>
            <span class="info-value">{{ task.executionCount }} 次</span>
          </div>
        </div>
        
        <div v-if="task.lastExecution" class="task-execution">
          <div class="execution-header">
            <span>最近执行</span>
            <span :class="['execution-status', task.lastExecution.success]">
              {{ task.lastExecution.success ? '✓ 成功' : '✗ 失败' }}
            </span>
          </div>
          <div class="execution-info">
            <span>{{ task.lastExecution.time }}</span>
            <span>耗时 {{ task.lastExecution.duration }}ms</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑任务弹窗 -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ editingTask ? '编辑任务' : '添加任务' }}</h3>
          <button class="close-btn" @click="closeModal">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>任务名称</label>
            <input 
              v-model="formData.name"
              class="form-input"
              placeholder="请输入任务名称..."
            />
          </div>
          
          <div class="form-group">
            <label>触发方式</label>
            <select class="form-select" v-model="formData.trigger">
              <option value="schedule">定时触发</option>
              <option value="event">事件触发</option>
              <option value="manual">手动触发</option>
            </select>
          </div>
          
          <div class="form-group" v-if="formData.trigger === 'schedule'">
            <label>执行计划</label>
            <select class="form-select" v-model="formData.schedule">
              <option value="daily">每天</option>
              <option value="weekly">每周</option>
              <option value="monthly">每月</option>
              <option value="hourly">每小时</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          
          <div class="form-group" v-if="formData.schedule === 'custom'">
            <label>自定义表达式</label>
            <input 
              v-model="formData.cronExpression"
              class="form-input"
              placeholder="例如: 0 0 * * *"
            />
          </div>
          
          <div class="form-group">
            <label>执行动作</label>
            <select class="form-select" v-model="formData.action">
              <option value="backup">数据备份</option>
              <option value="sync">同步数据</option>
              <option value="cleanup">清理缓存</option>
              <option value="report">生成报告</option>
              <option value="custom">自定义脚本</option>
            </select>
          </div>
          
          <div class="form-group" v-if="formData.action === 'custom'">
            <label>脚本内容</label>
            <textarea 
              v-model="formData.script"
              class="form-textarea"
              placeholder="输入要执行的脚本..."
              rows="4"
            ></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="cancel-btn" @click="closeModal">取消</button>
          <button class="save-btn" @click="saveTask">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

const showAddModal = ref(false);
const editingTask = ref(null);

const formData = reactive({
  name: '',
  trigger: 'schedule',
  schedule: 'daily',
  cronExpression: '',
  action: 'backup',
  script: ''
});

const tasks = ref([
  {
    id: '1',
    name: '每日数据备份',
    trigger: 'schedule',
    schedule: 'daily',
    action: 'backup',
    status: 'running',
    nextRun: '今天 00:00',
    executionCount: 15,
    lastExecution: {
      success: true,
      time: '2024-01-15 00:00:05',
      duration: 1250
    }
  },
  {
    id: '2',
    name: '每周报告生成',
    trigger: 'schedule',
    schedule: 'weekly',
    action: 'report',
    status: 'running',
    nextRun: '本周日 09:00',
    executionCount: 4,
    lastExecution: {
      success: true,
      time: '2024-01-14 09:00:32',
      duration: 8520
    }
  },
  {
    id: '3',
    name: '缓存清理',
    trigger: 'schedule',
    schedule: 'hourly',
    action: 'cleanup',
    status: 'paused',
    nextRun: '下一小时',
    executionCount: 120,
    lastExecution: {
      success: false,
      time: '2024-01-15 10:00:02',
      duration: 580
    }
  }
]);

const getTriggerLabel = (trigger) => {
  const labels = {
    schedule: '定时触发',
    event: '事件触发',
    manual: '手动触发'
  };
  return labels[trigger] || trigger;
};

const getScheduleLabel = (schedule) => {
  const labels = {
    daily: '每天',
    weekly: '每周',
    monthly: '每月',
    hourly: '每小时',
    custom: '自定义'
  };
  return labels[schedule] || schedule;
};

const closeModal = () => {
  showAddModal.value = false;
  editingTask.value = null;
  formData.name = '';
  formData.trigger = 'schedule';
  formData.schedule = 'daily';
  formData.cronExpression = '';
  formData.action = 'backup';
  formData.script = '';
};

const editTask = (task) => {
  editingTask.value = task;
  formData.name = task.name;
  formData.trigger = task.trigger;
  formData.schedule = task.schedule;
  formData.action = task.action;
  showAddModal.value = true;
};

const saveTask = () => {
  if (!formData.name.trim()) {
    alert('请输入任务名称');
    return;
  }
  
  if (editingTask.value) {
    editingTask.value.name = formData.name;
    editingTask.value.trigger = formData.trigger;
    editingTask.value.schedule = formData.schedule;
    editingTask.value.action = formData.action;
  } else {
    tasks.value.push({
      id: Date.now().toString(),
      name: formData.name,
      trigger: formData.trigger,
      schedule: formData.schedule,
      action: formData.action,
      status: 'running',
      nextRun: '即将执行',
      executionCount: 0,
      lastExecution: null
    });
  }
  
  closeModal();
};

const toggleTask = (task) => {
  task.status = task.status === 'running' ? 'paused' : 'running';
};

const deleteTask = (task) => {
  if (confirm(`确定要删除任务 "${task.name}" 吗？`)) {
    const index = tasks.value.findIndex(t => t.id === task.id);
    if (index > -1) {
      tasks.value.splice(index, 1);
    }
  }
};
</script>

<style scoped>
.automation-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
  color: #1a1a2e;
}

.task-count {
  padding: 4px 10px;
  background: #e9ecef;
  border-radius: 12px;
  font-size: 12px;
  color: #666;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.add-btn:hover {
  transform: translateY(-2px);
}

.task-list {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: #666;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 13px;
  color: #999;
}

.task-card {
  margin-bottom: 12px;
  padding: 16px;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 10px;
  transition: all 0.2s;
}

.task-card.running {
  border-left: 3px solid #10b981;
}

.task-card.paused {
  border-left: 3px solid #f59e0b;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.running {
  background: #10b981;
  animation: pulse-green 2s infinite;
}

.status-dot.paused {
  background: #f59e0b;
}

@keyframes pulse-green {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.task-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.task-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  padding: 6px;
  background: #e9ecef;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}

.action-btn:hover {
  background: #dee2e6;
}

.task-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.info-row {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 2px;
}

.info-value {
  font-size: 13px;
  color: #333;
}

.task-execution {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e9ecef;
}

.execution-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  color: #666;
}

.execution-status {
  font-weight: 500;
}

.execution-status.true {
  color: #10b981;
}

.execution-status.false {
  color: #ef4444;
}

.execution-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #999;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 90%;
  max-width: 450px;
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.close-btn {
  padding: 6px 12px;
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}

.form-input, .form-select {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}

.form-input:focus, .form-select:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  resize: none;
  outline: none;
}

.form-textarea:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.modal-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #f8f9fa;
  border-top: 1px solid #e9ecef;
}

.cancel-btn, .save-btn {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.cancel-btn {
  background: #e9ecef;
  color: #374151;
}

.cancel-btn:hover {
  background: #dee2e6;
}

.save-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.save-btn:hover {
  transform: translateY(-2px);
}
</style>