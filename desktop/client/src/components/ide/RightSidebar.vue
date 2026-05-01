<template>
  <aside class="right-sidebar">
    <div class="sidebar-tabs">
      <NButton text @click="activeTab = 'outline'" :class="{ active: activeTab === 'outline' }">
        <NIcon :component="OutlineIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'git'" :class="{ active: activeTab === 'git' }">
        <NIcon :component="GitIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'database'" :class="{ active: activeTab === 'database' }">
        <NIcon :component="DatabaseIcon" :size="18" />
      </NButton>
      <NButton text @click="activeTab = 'ai'" :class="{ active: activeTab === 'ai' }">
        <NIcon :component="AIIcon" :size="18" />
      </NButton>
    </div>
    
    <div class="sidebar-content">
      <!-- 大纲 -->
      <div v-if="activeTab === 'outline'" class="panel">
        <div class="panel-header">大纲</div>
        <div class="outline-list">
          <div class="outline-item" v-for="item in outlineItems" :key="item.name">
            <NIcon :component="item.icon" :size="14" />
            <span>{{ item.name }}</span>
            <span class="line-ref">{{ item.line }}</span>
          </div>
        </div>
      </div>
      
      <!-- Git时间线 -->
      <div v-if="activeTab === 'git'" class="panel">
        <div class="panel-header">Git时间线</div>
        <div class="timeline">
          <div class="timeline-date">今天</div>
          <div v-for="event in todayEvents" :key="event.time" class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <span class="timeline-time">{{ event.time }}</span>
              <span class="timeline-desc">{{ event.description }}</span>
            </div>
          </div>
          <div class="timeline-date">昨天</div>
          <div v-for="event in yesterdayEvents" :key="event.time" class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <span class="timeline-time">{{ event.time }}</span>
              <span class="timeline-desc">{{ event.description }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 数据库面板 -->
      <div v-if="activeTab === 'database'" class="panel">
        <div class="panel-header">数据库</div>
        <div class="db-connections">
          <div v-for="conn in dbConnections" :key="conn.name" class="db-connection">
            <NIcon :component="conn.connected ? CheckIcon : CircleIcon" :size="14" />
            <span>{{ conn.name }}</span>
          </div>
        </div>
        <div class="db-tables">
          <div class="section-title">表结构</div>
          <div v-for="table in dbTables" :key="table.name" class="db-table">
            <NIcon :component="TableIcon" :size="14" />
            <span>{{ table.name }}</span>
          </div>
        </div>
        <div class="db-query">
          <div class="section-title">查询窗口</div>
          <textarea class="query-editor" placeholder="输入SQL查询..."></textarea>
          <div class="query-actions">
            <NButton type="primary" size="small">执行</NButton>
            <NButton text size="small">保存</NButton>
          </div>
        </div>
      </div>
      
      <!-- AI助手面板 -->
      <div v-if="activeTab === 'ai'" class="panel">
        <div class="panel-header">AI助手</div>
        <div class="ai-actions">
          <NButton block @click="explainCode">
            <NIcon :component="HelpIcon" :size="16" />
            解释代码
          </NButton>
          <NButton block @click="optimizeCode">
            <NIcon :component="ZapIcon" :size="16" />
            优化代码
          </NButton>
          <NButton block @click="findBug">
            <NIcon :component="BugIcon" :size="16" />
            查找错误
          </NButton>
          <NButton block @click="addComments">
            <NIcon :component="FileTextIcon" :size="16" />
            添加注释
          </NButton>
        </div>
        
        <div class="ai-chat">
          <div class="chat-input-wrapper">
            <NInput v-model="aiQuery" placeholder="输入问题或指令..." />
            <NButton type="primary" @click="sendAIQuery">
              <NIcon :component="SendIcon" :size="16" />
            </NButton>
          </div>
        </div>
        
        <div class="ai-history">
          <div class="section-title">历史记录</div>
          <div v-for="item in aiHistory" :key="item" class="history-item">
            {{ item }}
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { NButton, NIcon, NInput } from 'naive-ui'
import { 
  List, GitBranch, Database, Bot, HelpCircle, Zap, Bug, 
  FileText, Send, Check, Circle, Table
} from '@vicons/ionicons5'

const OutlineIcon = { render: () => h(List) }
const GitIcon = { render: () => h(GitBranch) }
const DatabaseIcon = { render: () => h(Database) }
const AIIcon = { render: () => h(Bot) }
const HelpIcon = { render: () => h(HelpCircle) }
const ZapIcon = { render: () => h(Zap) }
const BugIcon = { render: () => h(Bug) }
const FileTextIcon = { render: () => h(FileText) }
const SendIcon = { render: () => h(Send) }
const CheckIcon = { render: () => h(Check) }
const CircleIcon = { render: () => h(Circle) }
const TableIcon = { render: () => h(Table) }

const activeTab = ref('ai')

const outlineItems = ref([
  { name: 'main()', icon: { render: () => h(FileText) }, line: 'L10' },
  { name: 'helper()', icon: { render: () => h(FileText) }, line: 'L20' },
  { name: 'User', icon: { render: () => h(List) }, line: 'L30' },
])

const todayEvents = ref([
  { time: '10:30', description: '修改main.py' },
  { time: '11:15', description: '提交更新' },
])

const yesterdayEvents = ref([
  { time: '14:20', description: '修复bug' },
  { time: '16:45', description: '添加功能' },
])

const dbConnections = ref([
  { name: '数据库1', connected: true },
  { name: '数据库2', connected: false },
])

const dbTables = ref([
  { name: 'users' },
  { name: 'products' },
  { name: 'orders' },
])

const aiQuery = ref('')
const aiHistory = ref([
  '如何优化这个函数？',
  '解释这段代码',
  '添加错误处理',
])

function explainCode() { console.log('Explain code') }
function optimizeCode() { console.log('Optimize code') }
function findBug() { console.log('Find bug') }
function addComments() { console.log('Add comments') }
function sendAIQuery() { console.log('Send AI query:', aiQuery.value) }
</script>

<style scoped>
.right-sidebar {
  width: 250px;
  background: var(--bg-card);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-tabs {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-tabs .active {
  background: var(--bg-hover);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
}

.panel {
  padding: 8px;
}

.panel-header {
  font-weight: 600;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-color);
}

.outline-list {
  padding: 4px;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
  cursor: pointer;
}

.outline-item:hover {
  background: var(--bg-hover);
}

.line-ref {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}

.timeline {
  padding: 4px;
}

.timeline-date {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 8px 0 4px;
}

.timeline-item {
  display: flex;
  gap: 8px;
  padding: 4px;
}

.timeline-dot {
  width: 8px;
  height: 8px;
  background: var(--primary-color);
  border-radius: 50%;
  margin-top: 4px;
}

.timeline-content {
  flex: 1;
}

.timeline-time {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
}

.timeline-desc {
  display: block;
}

.db-connections {
  padding: 4px;
}

.db-connection {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}

.db-tables {
  margin-top: 16px;
}

.section-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.db-table {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
}

.db-query {
  margin-top: 16px;
}

.query-editor {
  width: 100%;
  height: 100px;
  padding: 8px;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-family: monospace;
  font-size: 12px;
  resize: none;
}

.query-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.ai-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ai-chat {
  margin-top: 16px;
}

.chat-input-wrapper {
  display: flex;
  gap: 4px;
}

.ai-history {
  margin-top: 16px;
}

.history-item {
  padding: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.history-item:hover {
  background: var(--bg-hover);
}
</style>