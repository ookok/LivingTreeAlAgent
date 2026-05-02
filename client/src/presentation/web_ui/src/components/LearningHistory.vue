<template>
  <div class="learning-history">
    <div class="panel-header">
      <div class="header-title">
        <span class="history-icon">📚</span>
        <span>学习记录</span>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="refreshData">🔄 刷新</button>
        <button class="action-btn" @click="exportHistory">📤 导出</button>
      </div>
    </div>

    <div class="stats-overview">
      <div class="stat-card">
        <span class="stat-value">{{ totalExperiences }}</span>
        <span class="stat-label">总经验</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ successRate }}%</span>
        <span class="stat-label">成功率</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ feedbackCount }}</span>
        <span class="stat-label">反馈数</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ skillCount }}</span>
        <span class="stat-label">技能数</span>
      </div>
    </div>

    <div class="history-content">
      <div class="tabs">
        <button 
          :class="['tab-btn', { active: activeTab === 'timeline' }]"
          @click="activeTab = 'timeline'"
        >📅 时间线</button>
        <button 
          :class="['tab-btn', { active: activeTab === 'skills' }]"
          @click="activeTab = 'skills'"
        >🧠 技能成长</button>
        <button 
          :class="['tab-btn', { active: activeTab === 'policies' }]"
          @click="activeTab = 'policies'"
        >⚙️ 策略进化</button>
        <button 
          :class="['tab-btn', { active: activeTab === 'insights' }]"
          @click="activeTab = 'insights'"
        >💡 洞察</button>
      </div>

      <div class="tab-content">
        <!-- 时间线视图 -->
        <div v-if="activeTab === 'timeline'" class="timeline-view">
          <div class="timeline">
            <div 
              v-for="(event, index) in learningEvents" 
              :key="index"
              class="timeline-item"
            >
              <div :class="['timeline-dot', event.type]"></div>
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="event-title">{{ event.title }}</span>
                  <span class="event-time">{{ event.time }}</span>
                </div>
                <p class="event-description">{{ event.description }}</p>
                <div v-if="event.metrics" class="event-metrics">
                  <span 
                    v-for="(value, key) in event.metrics" 
                    :key="key"
                    class="metric-tag"
                  >{{ key }}: {{ value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 技能成长视图 -->
        <div v-if="activeTab === 'skills'" class="skills-view">
          <div class="skills-search">
            <input 
              type="text" 
              v-model="skillSearch" 
              class="search-input"
              placeholder="搜索技能..."
            />
          </div>
          <div class="skills-list">
            <div 
              v-for="skill in filteredSkills" 
              :key="skill.name"
              class="skill-card"
            >
              <div class="skill-header">
                <span class="skill-name">{{ skill.name }}</span>
                <span :class="['skill-status', skill.status]">{{ getStatusText(skill.status) }}</span>
              </div>
              <p class="skill-desc">{{ skill.description }}</p>
              <div class="skill-stats">
                <div class="stat-item">
                  <span class="stat-value">{{ skill.metrics.usage_count }}</span>
                  <span class="stat-label">使用次数</span>
                </div>
                <div class="stat-item">
                  <span :class="['stat-value', getSuccessClass(skill)]">{{ getSuccessRate(skill) }}%</span>
                  <span class="stat-label">成功率</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ skill.metrics.avg_execution_time.toFixed(1) }}s</span>
                  <span class="stat-label">平均耗时</span>
                </div>
              </div>
              <div class="skill-progress">
                <div class="progress-bar">
                  <div 
                    class="progress-fill" 
                    :style="{ width: getSuccessRate(skill) + '%' }"
                    :class="getSuccessClass(skill)"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 策略进化视图 -->
        <div v-if="activeTab === 'policies'" class="policies-view">
          <div 
            v-for="policy in policies" 
            :key="policy.name"
            class="policy-card"
          >
            <div class="policy-header">
              <span class="policy-name">{{ policy.name }}</span>
              <span :class="['policy-type', policy.policy_type]">{{ getPolicyTypeText(policy.policy_type) }}</span>
            </div>
            <p class="policy-desc">{{ policy.description }}</p>
            <div class="policy-rules">
              <div class="rules-header">规则 ({{ policy.rules.length }})</div>
              <div 
                v-for="(rule, index) in policy.rules" 
                :key="index"
                class="rule-item"
              >
                <span class="rule-condition">{{ rule.condition }}</span>
                <span class="rule-action">{{ getActionText(rule.action) }}</span>
                <span class="rule-confidence">{{ Math.round(rule.confidence * 100) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 洞察视图 -->
        <div v-if="activeTab === 'insights'" class="insights-view">
          <div 
            v-for="insight in insights" 
            :key="insight.insight_id"
            :class="['insight-card', insight.insight_type]"
          >
            <div class="insight-header">
              <span class="insight-icon">{{ getInsightIcon(insight.insight_type) }}</span>
              <div class="insight-info">
                <span class="insight-title">{{ insight.description }}</span>
                <span class="insight-time">{{ insight.timestamp }}</span>
              </div>
              <span :class="['insight-confidence', insight.confidence > 0.8 ? 'high' : insight.confidence > 0.6 ? 'medium' : 'low']">
                {{ Math.round(insight.confidence * 100) }}%
              </span>
            </div>
            <div class="insight-evidence">
              <span class="evidence-label">证据:</span>
              <ul>
                <li v-for="(ev, i) in insight.evidence" :key="i">{{ ev }}</li>
              </ul>
            </div>
            <div class="insight-action">
              <span class="action-label">建议:</span>
              <span class="action-text">{{ insight.recommended_action }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const activeTab = ref('timeline');
const skillSearch = ref('');

const totalExperiences = ref(42);
const successRate = ref(78);
const feedbackCount = ref(15);
const skillCount = ref(23);

const learningEvents = ref([
  {
    type: 'experience',
    title: '完成代码生成任务',
    description: '成功为用户生成员工管理系统的API代码',
    time: '10:30',
    metrics: { 成功率: '100%', 耗时: '25s' }
  },
  {
    type: 'feedback',
    title: '收到用户反馈',
    description: '用户对代码质量表示满意，评分5星',
    time: '10:32',
    metrics: { 评分: '★★★★★' }
  },
  {
    type: 'skill',
    title: '技能使用记录',
    description: '使用 generate_code Skill 成功完成任务',
    time: '10:33',
    metrics: { 成功率: '85%', 使用次数: '12' }
  },
  {
    type: 'insight',
    title: '发现改进机会',
    description: '识别到代码生成速度可以优化',
    time: '10:35',
    metrics: { 置信度: '92%' }
  },
  {
    type: 'policy',
    title: '策略更新',
    description: '基于经验更新代码生成策略',
    time: '10:36',
    metrics: { 更新规则: '3条' }
  },
  {
    type: 'experience',
    title: '完成文档编写任务',
    description: '成功生成项目技术文档',
    time: '10:40',
    metrics: { 成功率: '100%', 耗时: '18s' }
  }
]);

const skills = ref([
  {
    name: 'generate_code',
    description: '根据需求生成代码',
    status: 'active',
    metrics: { usage_count: 45, success_count: 38, avg_execution_time: 15.2 }
  },
  {
    name: 'write_document',
    description: '编写技术文档',
    status: 'active',
    metrics: { usage_count: 32, success_count: 28, avg_execution_time: 12.5 }
  },
  {
    name: 'analyze_data',
    description: '数据分析和处理',
    status: 'active',
    metrics: { usage_count: 28, success_count: 22, avg_execution_time: 20.1 }
  },
  {
    name: 'optimize_code',
    description: '代码优化',
    status: 'experimental',
    metrics: { usage_count: 8, success_count: 5, avg_execution_time: 25.3 }
  },
  {
    name: 'create_ui',
    description: '创建UI组件',
    status: 'active',
    metrics: { usage_count: 35, success_count: 31, avg_execution_time: 18.7 }
  }
]);

const filteredSkills = computed(() => {
  if (!skillSearch.value) return skills.value;
  const search = skillSearch.value.toLowerCase();
  return skills.value.filter(s => 
    s.name.toLowerCase().includes(search) || 
    s.description.toLowerCase().includes(search)
  );
});

const policies = ref([
  {
    name: 'skill_selection',
    policy_type: 'skill_selection',
    description: '基于任务类型选择合适的技能',
    rules: [
      { condition: "task_type == 'code_generation'", action: "USE_SKILL", action_params: { skill: 'generate_code' }, confidence: 0.9 },
      { condition: "task_type == 'document_writing'", action: "USE_SKILL", action_params: { skill: 'write_document' }, confidence: 0.85 },
      { condition: "execution_time > 30", action: "SKIP_SKILL", action_params: {}, confidence: 0.7 }
    ]
  },
  {
    name: 'feedback_handling',
    policy_type: 'feedback_handling',
    description: '处理用户反馈并调整策略',
    rules: [
      { condition: "rating < 3", action: "RETRY_TASK", action_params: {}, confidence: 0.95 },
      { condition: "feedback_type == 'thumbs_down'", action: "ASK_CLARIFICATION", action_params: {}, confidence: 0.8 }
    ]
  }
]);

const insights = ref([
  {
    insight_id: 'insight_1',
    policy_name: 'skill_selection',
    insight_type: 'skill_failure',
    description: 'Skill analyze_data 执行失败率较高',
    evidence: ['最近5次使用失败2次', '错误类型: 超时'],
    recommended_action: '考虑优化或替换该技能',
    confidence: 0.88,
    timestamp: '10:35'
  },
  {
    insight_id: 'insight_2',
    policy_name: 'performance',
    insight_type: 'performance_issue',
    description: '代码生成速度可以优化',
    evidence: ['平均耗时15.2s', '用户反馈希望更快'],
    recommended_action: '考虑引入缓存机制',
    confidence: 0.75,
    timestamp: '10:33'
  },
  {
    insight_id: 'insight_3',
    policy_name: 'feedback_handling',
    insight_type: 'negative_feedback',
    description: '收到负面反馈，需要改进',
    evidence: ['用户评分: 2星', '评论: 结果不够准确'],
    recommended_action: '分析失败原因，调整相关策略',
    confidence: 0.95,
    timestamp: '10:28'
  }
]);

const getStatusText = (status) => {
  const texts = { active: '活跃', disabled: '禁用', experimental: '实验中' };
  return texts[status] || status;
};

const getSuccessRate = (skill) => {
  if (skill.metrics.usage_count === 0) return 0;
  return Math.round((skill.metrics.success_count / skill.metrics.usage_count) * 100);
};

const getSuccessClass = (skill) => {
  const rate = getSuccessRate(skill);
  if (rate >= 80) return 'high';
  if (rate >= 60) return 'medium';
  return 'low';
};

const getPolicyTypeText = (type) => {
  const texts = {
    task_planning: '任务规划',
    skill_selection: '技能选择',
    prompt_optimization: '提示优化',
    feedback_handling: '反馈处理',
    learning_strategy: '学习策略'
  };
  return texts[type] || type;
};

const getActionText = (action) => {
  const texts = {
    USE_SKILL: '使用技能',
    SKIP_SKILL: '跳过技能',
    MODIFY_PARAMS: '修改参数',
    RETRY_TASK: '重试任务',
    ASK_CLARIFICATION: '询问澄清',
    CALL_HUMAN: '呼叫人类'
  };
  return texts[action] || action;
};

const getInsightIcon = (type) => {
  const icons = {
    skill_failure: '❌',
    performance_issue: '⏱️',
    negative_feedback: '👎',
    missing_skills: '🔍',
    skill_failure_pattern: '⚠️',
    performance_feedback: '⚡'
  };
  return icons[type] || '💡';
};

const refreshData = () => {
  console.log('刷新学习记录');
};

const exportHistory = () => {
  const data = {
    totalExperiences: totalExperiences.value,
    successRate: successRate.value,
    feedbackCount: feedbackCount.value,
    learningEvents: learningEvents.value,
    skills: skills.value,
    policies: policies.value,
    insights: insights.value
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'learning_history.json';
  a.click();
  URL.revokeObjectURL(url);
};
</script>

<style scoped>
.learning-history {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #cbd5e1;
}

.history-icon {
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
}

.stat-card {
  text-align: center;
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.stat-card .stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #e2e8f0;
}

.stat-card .stat-label {
  font-size: 11px;
  color: #64748b;
}

.history-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tabs {
  display: flex;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tab-btn {
  flex: 1;
  padding: 10px;
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #cbd5e1;
}

.tab-btn.active {
  color: #667eea;
  background: rgba(102, 126, 234, 0.1);
  border-bottom: 2px solid #667eea;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* 时间线视图 */
.timeline-view {
  padding: 4px;
}

.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: rgba(255, 255, 255, 0.1);
}

.timeline-item {
  position: relative;
  margin-bottom: 20px;
}

.timeline-dot {
  position: absolute;
  left: -20px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.timeline-dot.experience {
  background: #3b82f6;
}

.timeline-dot.feedback {
  background: #fbbf24;
}

.timeline-dot.skill {
  background: #22c55e;
}

.timeline-dot.insight {
  background: #a855f7;
}

.timeline-dot.policy {
  background: #f97316;
}

.timeline-content {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.event-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.event-time {
  font-size: 11px;
  color: #64748b;
}

.event-description {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 8px;
}

.event-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.metric-tag {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-size: 11px;
  color: #94a3b8;
}

/* 技能视图 */
.skills-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skills-search {
  padding: 0 4px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  font-size: 12px;
  outline: none;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.skill-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.skill-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
}

.skill-status.active {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.skill-status.experimental {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.skill-status.disabled {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.skill-desc {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 10px;
}

.skill-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 10px;
}

.skill-stats .stat-item {
  text-align: center;
}

.skill-stats .stat-value {
  display: block;
  font-size: 14px;
  font-weight: 600;
}

.skill-stats .stat-label {
  font-size: 10px;
  color: #64748b;
}

.skill-progress {
  margin-top: 8px;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-fill.high {
  background: #22c55e;
}

.progress-fill.medium {
  background: #fbbf24;
}

.progress-fill.low {
  background: #ef4444;
}

/* 策略视图 */
.policies-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.policy-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
}

.policy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.policy-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.policy-type {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
}

.policy-type.skill_selection {
  background: rgba(139, 92, 246, 0.2);
  color: #c4b5fd;
}

.policy-type.feedback_handling {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.policy-desc {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 10px;
}

.policy-rules {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 8px;
}

.rules-header {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}

.rule-item {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 11px;
}

.rule-item:last-child {
  border-bottom: none;
}

.rule-condition {
  flex: 1;
  color: #94a3b8;
}

.rule-action {
  color: #22c55e;
}

.rule-confidence {
  color: #fbbf24;
}

/* 洞察视图 */
.insights-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.insight-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
  border-left: 3px solid #a855f7;
}

.insight-card.skill_failure {
  border-left-color: #ef4444;
}

.insight-card.performance_issue {
  border-left-color: #fbbf24;
}

.insight-card.negative_feedback {
  border-left-color: #f87171;
}

.insight-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.insight-icon {
  font-size: 18px;
}

.insight-info {
  flex: 1;
}

.insight-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.insight-time {
  font-size: 11px;
  color: #64748b;
}

.insight-confidence {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.insight-confidence.high {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.insight-confidence.medium {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.insight-confidence.low {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.insight-evidence {
  margin-bottom: 8px;
}

.evidence-label {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.insight-evidence ul {
  margin: 0;
  padding-left: 18px;
}

.insight-evidence li {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.insight-action {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.action-label {
  font-size: 11px;
  color: #60a5fa;
  font-weight: 500;
}

.action-text {
  font-size: 12px;
  color: #e2e8f0;
}
</style>