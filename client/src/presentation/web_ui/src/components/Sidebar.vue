<template>
  <aside class="sidebar">
    <div class="logo">🌳 LivingTree</div>
    <nav class="nav-items">
      <div 
        v-for="item in navItems" 
        :key="item.id"
        :class="['nav-item', { active: activeTab === item.id }]"
        @click="$emit('navigate', item.id)"
      >
        <span v-html="item.icon"></span>
        <span>{{ item.label }}</span>
      </div>
    </nav>
    <div class="system-status">
      <span class="status-indicator" :class="systemOnline ? 'status-online' : 'status-offline'"></span>
      <span class="status-text">{{ systemOnline ? '系统在线' : '系统离线' }}</span>
    </div>
  </aside>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';

defineProps({
  activeTab: {
    type: String,
    default: 'dashboard'
  },
  systemOnline: {
    type: Boolean,
    default: true
  }
});

defineEmits(['navigate']);

const navItems = [
  { id: 'ide', label: 'AI协同开发', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>' },
  { id: 'documents', label: '文档处理', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>' },
  { id: 'software', label: '软件工具箱', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>' },
  { id: 'skills', label: '技能市场', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L3 11c-1.1 1.3-.4 3 1.2 4.2l9.9 9.9c1.2 1.2 2.9 1.9 4.6 1.2l7.3-3.2c1.1-.5 1.5-1.9.8-3zM6.8 13.8l-2.7-2.7 9.3-9.3 2.7 2.7-9.3 9.3z"></path></svg>' },
  { id: 'automation', label: '自动化', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 15v2m-6 4h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2zm10-10V7a4 4 0 0 0-8 0v4h8z"></path></svg>' },
  { id: 'dashboard', label: '控制面板', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>' },
  { id: 'memory', label: '记忆系统', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"></path><polyline points="12 10 12 14 14 14"></polyline><line x1="16" y1="10" x2="8" y2="10"></line></svg>' },
  { id: 'learning', label: '持续学习', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>' },
  { id: 'reasoning', label: '认知推理', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' },
  { id: 'selfawareness', label: '自我意识', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>' },
  { id: 'observability', label: '任务观测', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"></path><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>' },
  { id: 'mcp', label: 'MCP服务', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10"></path><path d="M18 20V4"></path><path d="M6 20v-6"></path></svg>' }
];
</script>

<style scoped>
.sidebar {
  width: 280px;
  background: rgba(255, 255, 255, 0.05);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.logo {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 30px;
  text-align: center;
  background: linear-gradient(90deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-items {
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: rgba(255, 255, 255, 0.7);
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.nav-item.active {
  background: linear-gradient(135deg, #00d4ff, #7b2fff);
  color: #ffffff;
}

.nav-item svg {
  width: 20px;
  height: 20px;
  margin-right: 12px;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-online {
  background: #00ff88;
  box-shadow: 0 0 10px #00ff88;
}

.status-offline {
  background: #ff4757;
  box-shadow: 0 0 10px #ff4757;
}

.status-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
</style>