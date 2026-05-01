<template>
  <div class="skill-panel">
    <div class="panel-header">
      <div class="header-left">
        <h2>🛠️ 技能市场</h2>
        <span class="skill-count">{{ filteredSkills.length }} 个技能</span>
      </div>
      <div class="header-right">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input 
            v-model="searchQuery"
            class="search-input"
            placeholder="搜索技能..."
          />
        </div>
        <select class="filter-select" v-model="selectedCategory">
          <option value="all">全部分类</option>
          <option value="development">开发工具</option>
          <option value="design">设计工具</option>
          <option value="data">数据分析</option>
          <option value="security">安全工具</option>
          <option value="automation">自动化</option>
          <option value="ai">AI能力</option>
        </select>
      </div>
    </div>

    <div class="skill-grid">
      <div 
        v-for="skill in filteredSkills" 
        :key="skill.id"
        class="skill-card"
        @click="selectSkill(skill)"
      >
        <div class="skill-icon">{{ skill.icon }}</div>
        <div class="skill-content">
          <div class="skill-header">
            <span class="skill-name">{{ skill.name }}</span>
            <span :class="['skill-badge', skill.category]">{{ getCategoryLabel(skill.category) }}</span>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
          <div class="skill-footer">
            <span class="skill-author">by {{ skill.author }}</span>
            <span class="skill-rating">{{ skill.rating }} ⭐</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="selectedSkill" class="skill-detail-modal">
      <div class="modal-overlay" @click="selectedSkill = null"></div>
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-icon">{{ selectedSkill.icon }}</div>
          <div class="modal-info">
            <h3>{{ selectedSkill.name }}</h3>
            <span :class="['modal-badge', selectedSkill.category]">{{ getCategoryLabel(selectedSkill.category) }}</span>
          </div>
          <button class="close-btn" @click="selectedSkill = null">×</button>
        </div>
        <div class="modal-body">
          <p>{{ selectedSkill.description }}</p>
          <div class="skill-features">
            <h4>功能特性</h4>
            <ul>
              <li v-for="(feature, index) in selectedSkill.features" :key="index">{{ feature }}</li>
            </ul>
          </div>
          <div class="skill-meta">
            <div class="meta-item">
              <span class="meta-label">作者</span>
              <span class="meta-value">{{ selectedSkill.author }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">评分</span>
              <span class="meta-value">{{ selectedSkill.rating }} ⭐</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">使用次数</span>
              <span class="meta-value">{{ selectedSkill.usageCount }} 次</span>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="install-btn" @click="installSkill(selectedSkill)">
            <span>➕</span>
            <span>{{ selectedSkill.installed ? '已安装' : '安装技能' }}</span>
          </button>
          <button class="use-btn" @click="useSkill(selectedSkill)">
            <span>🚀</span>
            <span>立即使用</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const searchQuery = ref('');
const selectedCategory = ref('all');
const selectedSkill = ref(null);

const skills = ref([
  {
    id: 'git-commit',
    name: 'Git Commit',
    icon: '📦',
    category: 'development',
    description: '智能暂存、自动检测规范提交信息生成，支持类型、范围和描述的自定义覆盖。',
    author: 'GitHub',
    rating: 4.8,
    usageCount: 12580,
    installed: true,
    features: ['智能暂存', '规范提交信息', '自定义覆盖', '自动检测']
  },
  {
    id: 'security-best-practices',
    name: '安全最佳实践',
    icon: '🛡️',
    category: 'security',
    description: '针对 Python、JavaScript/TypeScript 和 Go 进行安全最佳实践审查并提供改进建议。',
    author: 'OpenAI',
    rating: 4.7,
    usageCount: 8920,
    installed: true,
    features: ['多语言支持', '安全审查', '改进建议', '代码分析']
  },
  {
    id: 'chart-visualization',
    name: '图表可视化',
    icon: '📊',
    category: 'data',
    description: '从 26 种图表类型中智能选择最适合的方案，根据详细规格生成图表图像。',
    author: 'ByteDance',
    rating: 4.9,
    usageCount: 15670,
    installed: true,
    features: ['26种图表', '智能选择', '自定义规格', '高质量输出']
  },
  {
    id: 'frontend-design',
    name: '前端设计',
    icon: '🎨',
    category: 'design',
    description: '构建具有独特风格、生产级质量的前端界面，避免千篇一律的 AI 审美。',
    author: 'Anthropic',
    rating: 4.6,
    usageCount: 9450,
    installed: false,
    features: ['独特风格', '生产级质量', 'AI审美避免', '响应式设计']
  },
  {
    id: 'react-best-practices',
    name: 'React 最佳实践',
    icon: '⚛️',
    category: 'development',
    description: '应用 Vercel Engineering 的 React 和 Next.js 性能优化规范。',
    author: 'Vercel',
    rating: 4.8,
    usageCount: 11230,
    installed: true,
    features: ['性能优化', '代码规范', 'Next.js支持', '最佳实践']
  },
  {
    id: 'redis-development',
    name: 'Redis 开发',
    icon: '🗄️',
    category: 'development',
    description: '应用 Redis 最佳实践与性能优化，涵盖数据结构、向量搜索和语义缓存。',
    author: 'Redis',
    rating: 4.5,
    usageCount: 6780,
    installed: false,
    features: ['性能优化', '向量搜索', '语义缓存', '数据结构']
  },
  {
    id: 'mcp-builder',
    name: 'MCP 构建器',
    icon: '🔧',
    category: 'automation',
    description: '构建高质量 MCP 服务器的指南，将 LLM 与外部 API 和服务连接。',
    author: 'Anthropic',
    rating: 4.7,
    usageCount: 5430,
    installed: true,
    features: ['MCP构建', 'API连接', 'LLM集成', '服务管理']
  },
  {
    id: 'data-analysis',
    name: '数据分析',
    icon: '📈',
    category: 'data',
    description: '分析 Excel 和 CSV 文件，支持多工作表、聚合、过滤、关联查询及导出。',
    author: 'ByteDance',
    rating: 4.9,
    usageCount: 14320,
    installed: true,
    features: ['Excel/CSV支持', '多工作表', '聚合过滤', '关联查询']
  },
  {
    id: 'webapp-testing',
    name: 'Web应用测试',
    icon: '🧪',
    category: 'development',
    description: '使用 Playwright 对本地 Web 应用进行测试与调试，支持截图和浏览器日志查看。',
    author: 'Anthropic',
    rating: 4.6,
    usageCount: 7890,
    installed: false,
    features: ['Playwright', '截图支持', '日志查看', '调试工具']
  },
  {
    id: 'algorithm-art',
    name: '算法艺术',
    icon: '🎭',
    category: 'ai',
    description: '使用 p5.js 创作原创算法艺术，支持种子随机、交互参数、流场和粒子系统。',
    author: 'Anthropic',
    rating: 4.8,
    usageCount: 4560,
    installed: false,
    features: ['p5.js', '算法艺术', '交互参数', '粒子系统']
  },
  {
    id: 'figma',
    name: 'Figma 集成',
    icon: '✏️',
    category: 'design',
    description: '通过 MCP 获取 Figma 设计上下文、截图、变量和资源，并将节点转译为生产代码。',
    author: 'Figma',
    rating: 4.7,
    usageCount: 8230,
    installed: false,
    features: ['设计上下文', '截图获取', '变量资源', '代码转译']
  },
  {
    id: 'shadcn',
    name: 'shadcn/ui',
    icon: '🧩',
    category: 'design',
    description: '管理 shadcn/ui 组件与项目，支持添加、搜索、修复、样式调整和 UI 组合。',
    author: 'shadcn',
    rating: 4.9,
    usageCount: 13450,
    installed: true,
    features: ['组件管理', '搜索修复', '样式调整', 'UI组合']
  }
]);

const filteredSkills = computed(() => {
  return skills.value.filter(skill => {
    const matchesSearch = skill.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
                          skill.description.toLowerCase().includes(searchQuery.value.toLowerCase());
    const matchesCategory = selectedCategory.value === 'all' || skill.category === selectedCategory.value;
    return matchesSearch && matchesCategory;
  });
});

const getCategoryLabel = (category) => {
  const labels = {
    development: '开发',
    design: '设计',
    data: '数据',
    security: '安全',
    automation: '自动化',
    ai: 'AI'
  };
  return labels[category] || category;
};

const selectSkill = (skill) => {
  selectedSkill.value = skill;
};

const installSkill = (skill) => {
  skill.installed = true;
  alert(`技能 "${skill.name}" 已安装！`);
};

const useSkill = (skill) => {
  alert(`正在使用技能: ${skill.name}`);
};
</script>

<style scoped>
.skill-panel {
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

.skill-count {
  padding: 4px 10px;
  background: #e9ecef;
  border-radius: 12px;
  font-size: 12px;
  color: #666;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  display: flex;
  align-items: center;
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 6px 12px;
}

.search-icon {
  font-size: 14px;
  margin-right: 8px;
}

.search-input {
  border: none;
  outline: none;
  font-size: 13px;
  width: 180px;
}

.filter-select {
  padding: 6px 12px;
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.skill-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  padding: 20px;
  overflow-y: auto;
}

.skill-card {
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.skill-card:hover {
  border-color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.skill-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.skill-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.skill-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.skill-badge.development {
  background: #dbeafe;
  color: #1d4ed8;
}

.skill-badge.design {
  background: #fce7f3;
  color: #be185d;
}

.skill-badge.data {
  background: #d1fae5;
  color: #059669;
}

.skill-badge.security {
  background: #fef3c7;
  color: #d97706;
}

.skill-badge.automation {
  background: #ede9fe;
  color: #6366f1;
}

.skill-badge.ai {
  background: #f0f9ff;
  color: #0284c7;
}

.skill-desc {
  margin: 0 0 12px 0;
  font-size: 13px;
  line-height: 1.5;
  color: #666;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-author {
  font-size: 12px;
  color: #999;
}

.skill-rating {
  font-size: 12px;
  color: #f59e0b;
  font-weight: 500;
}

.skill-detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.modal-content {
  position: relative;
  width: 90%;
  max-width: 500px;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.modal-icon {
  font-size: 48px;
}

.modal-info {
  flex: 1;
}

.modal-info h3 {
  margin: 0 0 6px 0;
  font-size: 20px;
  color: #333;
}

.modal-badge {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.close-btn {
  padding: 6px 12px;
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
}

.close-btn:hover {
  color: #333;
}

.modal-body {
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.modal-body p {
  margin: 0 0 16px 0;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}

.skill-features {
  margin-bottom: 16px;
}

.skill-features h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #333;
}

.skill-features ul {
  margin: 0;
  padding-left: 20px;
}

.skill-features li {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}

.skill-meta {
  display: flex;
  gap: 24px;
  padding-top: 16px;
  border-top: 1px solid #e9ecef;
}

.meta-item {
  display: flex;
  flex-direction: column;
}

.meta-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.meta-value {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.modal-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #f8f9fa;
  border-top: 1px solid #e9ecef;
}

.install-btn, .use-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.install-btn {
  background: #f3f4f6;
  color: #374151;
}

.install-btn:hover {
  background: #e5e7eb;
}

.use-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.use-btn:hover {
  transform: translateY(-2px);
}
</style>