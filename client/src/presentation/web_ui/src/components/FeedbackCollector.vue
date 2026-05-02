<template>
  <div class="feedback-collector">
    <div class="feedback-header">
      <span class="feedback-icon">📝</span>
      <span class="feedback-title">反馈采集</span>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>

    <div class="feedback-body">
      <div class="experience-info">
        <div class="info-item">
          <span class="info-label">任务类型:</span>
          <span class="info-value">{{ experience.task_type }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">任务描述:</span>
          <span class="info-value">{{ experience.task_description }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">执行状态:</span>
          <span :class="['info-value', experience.success ? 'success' : 'failed']">
            {{ experience.success ? '✓ 成功' : '✗ 失败' }}
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">执行时间:</span>
          <span class="info-value">{{ experience.execution_time.toFixed(2) }}秒</span>
        </div>
      </div>

      <div class="quick-feedback">
        <div class="quick-title">快速评价</div>
        <div class="rating-buttons">
          <button 
            :class="['rating-btn', { selected: quickRating === 5 }]"
            @click="quickRating = 5"
          >
            <span>⭐</span>
            <span>非常满意</span>
          </button>
          <button 
            :class="['rating-btn', { selected: quickRating === 4 }]"
            @click="quickRating = 4"
          >
            <span>👍</span>
            <span>满意</span>
          </button>
          <button 
            :class="['rating-btn', { selected: quickRating === 3 }]"
            @click="quickRating = 3"
          >
            <span>🤔</span>
            <span>一般</span>
          </button>
          <button 
            :class="['rating-btn', { selected: quickRating === 2 }]"
            @click="quickRating = 2"
          >
            <span>👎</span>
            <span>不满意</span>
          </button>
          <button 
            :class="['rating-btn', { selected: quickRating === 1 }]"
            @click="quickRating = 1"
          >
            <span>😞</span>
            <span>非常不满意</span>
          </button>
        </div>
      </div>

      <div class="detailed-feedback" v-if="quickRating <= 3 || showDetailed">
        <div class="detailed-title">详细反馈</div>
        
        <div class="feedback-section">
          <label class="section-label">问题类型</label>
          <div class="checkbox-group">
            <label 
              v-for="issue in issueTypes" 
              :key="issue.value"
              class="checkbox-item"
            >
              <input type="checkbox" v-model="selectedIssues" :value="issue.value" />
              <span>{{ issue.label }}</span>
            </label>
          </div>
        </div>

        <div class="feedback-section">
          <label class="section-label">具体问题描述</label>
          <textarea 
            v-model="detailedComment"
            class="feedback-textarea"
            placeholder="请详细描述您遇到的问题或建议..."
            rows="4"
          ></textarea>
        </div>

        <div class="feedback-section">
          <label class="section-label">改进建议</label>
          <textarea 
            v-model="improvementSuggestions"
            class="feedback-textarea"
            placeholder="您希望如何改进？..."
            rows="3"
          ></textarea>
        </div>
      </div>

      <div class="skill-feedback" v-if="experience.skills_used && experience.skills_used.length > 0">
        <div class="skill-title">使用的工具评价</div>
        <div class="skill-list">
          <div 
            v-for="(skill, index) in experience.skills_used" 
            :key="index"
            class="skill-item"
          >
            <div class="skill-header">
              <span class="skill-name">{{ skill.skill_name }}</span>
              <span :class="['skill-status', skill.success ? 'success' : 'failed']">
                {{ skill.success ? '✓' : '✗' }}
              </span>
            </div>
            <div class="skill-meta">
              <span class="skill-time">耗时: {{ skill.execution_time.toFixed(2) }}s</span>
            </div>
            <div class="skill-rating">
              <button 
                v-for="star in 5" 
                :key="star"
                :class="['star-btn', { active: skillRating[index] >= star }]"
                @click="setSkillRating(index, star)"
              >★</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="feedback-footer">
      <button class="footer-btn cancel" @click="$emit('close')">取消</button>
      <button 
        class="footer-btn submit" 
        @click="submitFeedback"
        :disabled="!quickRating"
      >提交反馈</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

const props = defineProps({
  experience: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['close', 'submit']);

const quickRating = ref(null);
const showDetailed = ref(false);
const detailedComment = ref('');
const improvementSuggestions = ref('');
const selectedIssues = ref([]);
const skillRating = reactive({});

const issueTypes = [
  { value: 'incorrect', label: '结果不正确' },
  { value: 'slow', label: '执行太慢' },
  { value: 'incomplete', label: '结果不完整' },
  { value: 'unclear', label: '输出难以理解' },
  { value: 'format', label: '格式问题' },
  { value: 'other', label: '其他问题' }
];

const setSkillRating = (index, rating) => {
  skillRating[index] = rating;
};

const submitFeedback = () => {
  if (!quickRating.value) return;

  const feedback = {
    experience_id: props.experience.experience_id,
    rating: quickRating.value,
    feedback_type: quickRating.value >= 4 ? 'thumbs_up' : 'thumbs_down',
    issues: selectedIssues.value,
    comment: detailedComment.value,
    suggestions: improvementSuggestions.value,
    skill_ratings: Object.entries(skillRating).reduce((acc, [index, rating]) => {
      const skill = props.experience.skills_used[index];
      if (skill) {
        acc[skill.skill_name] = rating;
      }
      return acc;
    }, {}),
    timestamp: new Date().toISOString()
  };

  emit('submit', feedback);
  emit('close');
};
</script>

<style scoped>
.feedback-collector {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
  border-radius: 12px;
  overflow: hidden;
  width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.feedback-icon {
  font-size: 20px;
}

.feedback-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #e0e7ff;
}

.close-btn {
  background: none;
  border: none;
  color: #9ca3af;
  font-size: 20px;
  cursor: pointer;
  padding: 0 8px;
}

.close-btn:hover {
  color: white;
}

.feedback-body {
  padding: 16px;
}

.experience-info {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 12px;
  color: #93c5fd;
}

.info-value {
  font-size: 12px;
  color: #e2e8f0;
}

.info-value.success {
  color: #4ade80;
}

.info-value.failed {
  color: #f87171;
}

.quick-feedback {
  margin-bottom: 16px;
}

.quick-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
  margin-bottom: 10px;
}

.rating-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rating-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.rating-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.rating-btn.selected {
  background: rgba(139, 92, 246, 0.5);
  border-color: #a78bfa;
  color: white;
}

.rating-btn span:first-child {
  font-size: 18px;
}

.detailed-feedback {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

.detailed-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
  margin-bottom: 12px;
}

.feedback-section {
  margin-bottom: 12px;
}

.feedback-section:last-child {
  margin-bottom: 0;
}

.section-label {
  display: block;
  font-size: 12px;
  color: #93c5fd;
  margin-bottom: 8px;
}

.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #e2e8f0;
  cursor: pointer;
}

.checkbox-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #a78bfa;
}

.feedback-textarea {
  width: 100%;
  padding: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  font-size: 12px;
  resize: vertical;
  outline: none;
}

.feedback-textarea:focus {
  border-color: #a78bfa;
}

.feedback-textarea::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.skill-feedback {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.skill-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e7ff;
  margin-bottom: 10px;
}

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-item {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  padding: 10px;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.skill-name {
  font-size: 12px;
  font-weight: 500;
  color: #e2e8f0;
}

.skill-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.skill-status.success {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.skill-status.failed {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.skill-meta {
  margin-bottom: 8px;
}

.skill-time {
  font-size: 11px;
  color: #64748b;
}

.skill-rating {
  display: flex;
  gap: 4px;
}

.star-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: #4b5563;
  cursor: pointer;
  transition: color 0.2s;
}

.star-btn:hover,
.star-btn.active {
  color: #fbbf24;
}

.feedback-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.footer-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.footer-btn.cancel {
  background: rgba(255, 255, 255, 0.1);
  color: #9ca3af;
}

.footer-btn.cancel:hover {
  background: rgba(255, 255, 255, 0.2);
}

.footer-btn.submit {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.footer-btn.submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.footer-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>