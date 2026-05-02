<template>
  <div class="code-diff-panel">
    <div class="panel-header">
      <div class="header-title">
        <span class="diff-icon">🔍</span>
        <span>代码变更预览</span>
        <span class="diff-stats">{{ addedLines }} 新增 | {{ removedLines }} 删除</span>
      </div>
      <div class="header-actions">
        <button 
          :class="['view-btn', { active: viewMode === 'split' }]"
          @click="viewMode = 'split'"
        >🔗 对比视图</button>
        <button 
          :class="['view-btn', { active: viewMode === 'unified' }]"
          @click="viewMode = 'unified'"
        >📝 统一视图</button>
        <button class="action-btn" @click="applyChanges" title="应用变更">
          <span>✅ 应用</span>
        </button>
        <button class="action-btn" @click="discardChanges" title="丢弃变更">
          <span>❌ 丢弃</span>
        </button>
      </div>
    </div>

    <div class="diff-content">
      <div v-if="viewMode === 'split'" class="split-view">
        <div class="diff-panel old">
          <div class="panel-label">
            <span>📄 原始文件</span>
            <span class="file-path">{{ originalFile }}</span>
          </div>
          <div class="code-container">
            <div 
              v-for="(line, index) in originalLines" 
              :key="'old-' + index"
              :class="['code-line', getLineClass(index, 'old')]"
            >
              <span class="line-number">{{ index + 1 }}</span>
              <span class="line-content">{{ line }}</span>
            </div>
          </div>
        </div>
        
        <div class="diff-arrow">
          <div class="arrow-content">
            <span v-if="hasChanges" class="arrow-icon">→</span>
            <span v-else class="arrow-icon">↔</span>
          </div>
        </div>
        
        <div class="diff-panel new">
          <div class="panel-label">
            <span>✨ 新文件</span>
            <span class="file-path">{{ newFile }}</span>
          </div>
          <div class="code-container">
            <div 
              v-for="(line, index) in newLines" 
              :key="'new-' + index"
              :class="['code-line', getLineClass(index, 'new')]"
            >
              <span class="line-number">{{ index + 1 }}</span>
              <span class="line-content">{{ line }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="unified-view">
        <div class="unified-header">
          <span class="file-info">{{ originalFile }}</span>
          <span class="diff-type">→</span>
          <span class="file-info">{{ newFile }}</span>
        </div>
        <div class="unified-content">
          <div 
            v-for="(hunk, hunkIndex) in unifiedHunks" 
            :key="'hunk-' + hunkIndex"
            class="diff-hunk"
          >
            <div class="hunk-header">
              <span>@@ -{{ hunk.oldStart },{{ hunk.oldCount }} +{{ hunk.newStart },{{ hunk.newCount }} @@</span>
            </div>
            <div 
              v-for="(line, lineIndex) in hunk.lines" 
              :key="'line-' + hunkIndex + '-' + lineIndex"
              :class="['unified-line', line.type]"
            >
              <span class="line-marker">{{ line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ' }}</span>
              <span class="line-content">{{ line.content }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="change-summary">
      <div class="summary-title">
        <span>📋 变更摘要</span>
      </div>
      <div class="summary-content">
        <div class="summary-row">
          <span class="summary-label">文件:</span>
          <span class="summary-value">{{ newFile }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">变更类型:</span>
          <span :class="['summary-value', changeType]">{{ getChangeTypeText() }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">代码质量:</span>
          <span :class="['summary-value', qualityStatus]">{{ getQualityText() }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">安全检查:</span>
          <span :class="['summary-value', securityStatus]">{{ getSecurityText() }}</span>
        </div>
      </div>
    </div>

    <div class="suggestions-panel" v-if="suggestions.length > 0">
      <div class="suggestions-header">
        <span>💡 AI 优化建议</span>
      </div>
      <div class="suggestions-list">
        <div 
          v-for="(suggestion, index) in suggestions" 
          :key="index"
          class="suggestion-item"
        >
          <span class="suggestion-icon">{{ suggestion.icon }}</span>
          <div class="suggestion-content">
            <span class="suggestion-title">{{ suggestion.title }}</span>
            <span class="suggestion-desc">{{ suggestion.description }}</span>
          </div>
          <button class="suggestion-action" @click="applySuggestion(suggestion)">应用</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const viewMode = ref('split');
const originalFile = ref('client/src/business/user_service.py');
const newFile = ref('client/src/business/user_service.py');
const changeType = ref('modify');
const qualityStatus = ref('good');
const securityStatus = ref('safe');

const originalCode = `class UserService:
    """用户服务类"""
    
    def __init__(self):
        self.users = []
    
    def get_user(self, user_id):
        """获取用户信息"""
        for user in self.users:
            if user.id == user_id:
                return user
        return None
    
    def create_user(self, user_data):
        """创建用户"""
        user = User(**user_data)
        self.users.append(user)
        return user`;

const newCode = `class UserService:
    """用户服务类 - 提供用户管理功能"""
    
    def __init__(self):
        self.users = []
        self.logger = logging.getLogger(__name__)
    
    def get_user(self, user_id):
        """获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            User对象或None
        """
        self.logger.debug(f"查找用户: {user_id}")
        for user in self.users:
            if user.id == user_id:
                return user
        return None
    
    def create_user(self, user_data):
        """创建用户
        
        Args:
            user_data: 用户数据字典
            
        Returns:
            创建的User对象
        """
        try:
            user = User(**user_data)
            self.users.append(user)
            self.logger.info(f"用户创建成功: {user.id}")
            return user
        except Exception as e:
            self.logger.error(f"用户创建失败: {e}")
            raise`;

const originalLines = computed(() => originalCode.split('\n'));
const newLines = computed(() => newCode.split('\n'));

const addedLines = computed(() => {
  let count = 0;
  newLines.value.forEach((line, index) => {
    if (!originalLines.value[index] || line !== originalLines.value[index]) {
      count++;
    }
  });
  return count;
});

const removedLines = computed(() => {
  let count = 0;
  originalLines.value.forEach((line, index) => {
    if (!newLines.value[index] || line !== newLines.value[index]) {
      count++;
    }
  });
  return count;
});

const hasChanges = computed(() => addedLines.value > 0 || removedLines.value > 0);

const unifiedHunks = computed(() => {
  return [
    {
      oldStart: 1,
      oldCount: 20,
      newStart: 1,
      newCount: 32,
      lines: [
        { type: 'same', content: 'class UserService:' },
        { type: 'modify', content: '    """用户服务类 - 提供用户管理功能"""' },
        { type: 'same', content: '' },
        { type: 'same', content: '    def __init__(self):' },
        { type: 'same', content: '        self.users = []' },
        { type: 'add', content: '        self.logger = logging.getLogger(__name__)' },
        { type: 'same', content: '' },
        { type: 'same', content: '    def get_user(self, user_id):' },
        { type: 'add', content: '        """获取用户信息' },
        { type: 'add', content: '' },
        { type: 'add', content: '        Args:' },
        { type: 'add', content: '            user_id: 用户ID' },
        { type: 'add', content: '' },
        { type: 'add', content: '        Returns:' },
        { type: 'add', content: '            User对象或None' },
        { type: 'add', content: '        """' },
        { type: 'add', content: '        self.logger.debug(f"查找用户: {user_id}")' },
        { type: 'same', content: '        for user in self.users:' },
        { type: 'same', content: '            if user.id == user_id:' },
        { type: 'same', content: '                return user' },
        { type: 'same', content: '        return None' },
        { type: 'same', content: '' },
        { type: 'same', content: '    def create_user(self, user_data):' },
        { type: 'add', content: '        """创建用户' },
        { type: 'add', content: '' },
        { type: 'add', content: '        Args:' },
        { type: 'add', content: '            user_data: 用户数据字典' },
        { type: 'add', content: '' },
        { type: 'add', content: '        Returns:' },
        { type: 'add', content: '            创建的User对象' },
        { type: 'add', content: '        """' },
        { type: 'add', content: '        try:' },
        { type: 'modify', content: '            user = User(**user_data)' },
        { type: 'modify', content: '            self.users.append(user)' },
        { type: 'add', content: '            self.logger.info(f"用户创建成功: {user.id}")' },
        { type: 'modify', content: '            return user' },
        { type: 'add', content: '        except Exception as e:' },
        { type: 'add', content: '            self.logger.error(f"用户创建失败: {e}")' },
        { type: 'add', content: '            raise' }
      ]
    }
  ];
});

const suggestions = ref([
  {
    icon: '📝',
    title: '添加类型注解',
    description: '建议为方法参数和返回值添加类型注解，提高代码可读性和类型检查',
    action: 'add_type_hints'
  },
  {
    icon: '🧪',
    title: '添加单元测试',
    description: '建议为新增的日志记录功能添加单元测试',
    action: 'add_tests'
  },
  {
    icon: '🔒',
    title: '输入验证',
    description: '建议对 user_data 进行输入验证，防止注入攻击',
    action: 'add_validation'
  }
]);

const getLineClass = (index, side) => {
  const oldLine = originalLines.value[index];
  const newLine = newLines.value[index];
  
  if (side === 'old') {
    if (!oldLine) return 'empty';
    if (!newLine || oldLine !== newLine) return 'removed';
    return 'same';
  } else {
    if (!newLine) return 'empty';
    if (!oldLine || oldLine !== newLine) return 'added';
    return 'same';
  }
};

const getChangeTypeText = () => {
  const texts = {
    create: '🆕 新建',
    modify: '✏️ 修改',
    delete: '🗑️ 删除',
    rename: '📝 重命名'
  };
  return texts[changeType.value] || changeType.value;
};

const getQualityText = () => {
  const texts = {
    excellent: '🌟 优秀',
    good: '✅ 良好',
    warning: '⚠️ 需要改进',
    error: '❌ 有问题'
  };
  return texts[qualityStatus.value] || qualityStatus.value;
};

const getSecurityText = () => {
  const texts = {
    safe: '✅ 安全',
    warning: '⚠️ 有潜在风险',
    danger: '🔴 有安全隐患'
  };
  return texts[securityStatus.value] || securityStatus.value;
};

const applyChanges = () => {
  console.log('应用变更');
};

const discardChanges = () => {
  console.log('丢弃变更');
};

const applySuggestion = (suggestion) => {
  console.log('应用建议:', suggestion.action);
};
</script>

<style scoped>
.code-diff-panel {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.3);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #cbd5e1;
}

.diff-icon {
  font-size: 20px;
}

.diff-stats {
  padding: 2px 8px;
  background: rgba(34, 197, 94, 0.2);
  border-radius: 10px;
  font-size: 12px;
  font-weight: normal;
  color: #4ade80;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.view-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.view-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.view-btn.active {
  background: rgba(99, 102, 241, 0.3);
  border-color: #6366f1;
  color: #c7d2fe;
}

.action-btn {
  padding: 6px 12px;
  background: rgba(34, 197, 94, 0.2);
  border: 1px solid rgba(34, 197, 94, 0.4);
  border-radius: 6px;
  color: #4ade80;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(34, 197, 94, 0.3);
}

.action-btn:last-child {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
  color: #f87171;
}

.action-btn:last-child:hover {
  background: rgba(239, 68, 68, 0.3);
}

.diff-content {
  padding: 16px;
}

.split-view {
  display: flex;
  gap: 12px;
  height: 300px;
}

.diff-panel {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  overflow: hidden;
}

.diff-panel.old .panel-label {
  background: rgba(239, 68, 68, 0.2);
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
}

.diff-panel.new .panel-label {
  background: rgba(34, 197, 94, 0.2);
  border-bottom: 1px solid rgba(34, 197, 94, 0.3);
}

.panel-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
  color: #cbd5e1;
}

.file-path {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  color: #64748b;
}

.code-container {
  height: calc(100% - 40px);
  overflow-y: auto;
  padding: 8px 0;
}

.code-line {
  display: flex;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 20px;
  transition: background 0.1s;
}

.code-line:hover {
  background: rgba(255, 255, 255, 0.05);
}

.code-line.same {
  background: transparent;
}

.code-line.added {
  background: rgba(34, 197, 94, 0.15);
}

.code-line.removed {
  background: rgba(239, 68, 68, 0.15);
}

.code-line.empty {
  background: rgba(255, 255, 255, 0.02);
}

.line-number {
  width: 50px;
  padding: 0 12px;
  text-align: right;
  color: #475569;
  user-select: none;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.line-content {
  flex: 1;
  padding: 0 12px;
  color: #e2e8f0;
  white-space: pre;
}

.diff-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
}

.arrow-content {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}

.arrow-icon {
  font-size: 20px;
  color: #6366f1;
}

.unified-view {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  overflow: hidden;
}

.unified-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.3);
  font-size: 12px;
}

.file-info {
  font-family: 'Fira Code', 'Consolas', monospace;
  color: #94a3b8;
}

.diff-type {
  color: #6366f1;
}

.unified-content {
  max-height: 300px;
  overflow-y: auto;
  padding: 8px 0;
}

.diff-hunk {
  margin-bottom: 8px;
}

.hunk-header {
  padding: 4px 12px;
  background: rgba(99, 102, 241, 0.2);
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  color: #a5b4fc;
}

.unified-line {
  display: flex;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 20px;
  transition: background 0.1s;
}

.unified-line:hover {
  background: rgba(255, 255, 255, 0.05);
}

.unified-line.add {
  background: rgba(34, 197, 94, 0.15);
}

.unified-line.remove {
  background: rgba(239, 68, 68, 0.15);
}

.line-marker {
  width: 30px;
  padding: 0 12px;
  font-weight: 600;
}

.unified-line.add .line-marker {
  color: #22c55e;
}

.unified-line.remove .line-marker {
  color: #ef4444;
}

.unified-line.modify .line-content {
  color: #fbbf24;
}

.change-summary {
  margin: 0 16px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.summary-title {
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.3);
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
}

.summary-content {
  padding: 12px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.summary-row:last-child {
  border-bottom: none;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.summary-value {
  font-size: 12px;
  color: #e2e8f0;
}

.summary-value.modify {
  color: #fbbf24;
}

.summary-value.create {
  color: #4ade80;
}

.summary-value.delete {
  color: #f87171;
}

.summary-value.good, .summary-value.safe {
  color: #4ade80;
}

.summary-value.warning {
  color: #fbbf24;
}

.summary-value.error, .summary-value.danger {
  color: #f87171;
}

.suggestions-panel {
  margin: 0 16px 16px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 8px;
  overflow: hidden;
}

.suggestions-header {
  padding: 10px 12px;
  background: rgba(139, 92, 246, 0.2);
  font-size: 13px;
  font-weight: 600;
  color: #c4b5fd;
}

.suggestions-list {
  padding: 8px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  margin-bottom: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.suggestion-item:last-child {
  margin-bottom: 0;
}

.suggestion-icon {
  font-size: 18px;
}

.suggestion-content {
  flex: 1;
}

.suggestion-title {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
}

.suggestion-desc {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.suggestion-action {
  padding: 6px 12px;
  background: rgba(139, 92, 246, 0.3);
  border: 1px solid rgba(139, 92, 246, 0.5);
  border-radius: 4px;
  color: #c4b5fd;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.2s;
}

.suggestion-action:hover {
  background: rgba(139, 92, 246, 0.5);
}
</style>