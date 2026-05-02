<template>
  <div class="dynamic-ui-panel">
    <div class="panel-header">
      <div class="header-title">
        <span class="ui-icon">🎨</span>
        <span>动态 UI 渲染</span>
      </div>
      <div class="header-actions">
        <select class="intent-select" v-model="selectedIntent" @change="renderUI">
          <option value="">选择意图...</option>
          <option value="create_crud">创建 CRUD 页面</option>
          <option value="form_fill">表单填写</option>
          <option value="data_upload">数据上传</option>
          <option value="search">知识检索</option>
          <option value="analysis">数据分析</option>
          <option value="report">生成报告</option>
        </select>
        <button class="refresh-btn" @click="renderUI">🔄 重新渲染</button>
      </div>
    </div>

    <div class="ui-content">
      <div v-if="currentSchema" class="schema-preview">
        <div class="schema-header">
          <span class="schema-title">📋 当前 Schema</span>
          <button class="export-btn" @click="exportSchema">📤 导出 Schema</button>
        </div>
        <pre class="schema-code">{{ formatSchema(currentSchema) }}</pre>
      </div>

      <div class="ui-canvas">
        <div 
          v-for="component in renderedComponents" 
          :key="component.id"
          :class="['ui-component', component.type]"
        >
          <div v-if="component.type === 'heading'" class="component-heading">
            <span>{{ component.label }}</span>
          </div>

          <div v-else-if="component.type === 'text'" class="component-text">
            {{ component.value }}
          </div>

          <div v-else-if="component.type === 'text_input'" class="component-input">
            <label class="input-label">{{ component.label }}</label>
            <input 
              type="text" 
              :placeholder="component.placeholder"
              :required="component.required"
              class="text-field"
            />
          </div>

          <div v-else-if="component.type === 'textarea'" class="component-textarea">
            <label class="input-label">{{ component.label }}</label>
            <textarea 
              :placeholder="component.placeholder"
              :rows="component.rows || 4"
              class="textarea-field"
            ></textarea>
          </div>

          <div v-else-if="component.type === 'select'" class="component-select">
            <label class="input-label">{{ component.label }}</label>
            <select class="select-field">
              <option value="">请选择...</option>
              <option 
                v-for="option in component.options" 
                :key="option.value"
                :value="option.value"
              >{{ option.label }}</option>
            </select>
          </div>

          <div v-else-if="component.type === 'multi_select'" class="component-multi-select">
            <label class="input-label">{{ component.label }}</label>
            <div class="multi-select-container">
              <span 
                v-for="option in component.options" 
                :key="option.value"
                :class="['multi-option', { selected: isSelected(option.value) }]"
                @click="toggleSelection(option.value)"
              >{{ option.label }}</span>
            </div>
          </div>

          <div v-else-if="component.type === 'checkbox'" class="component-checkbox">
            <label class="checkbox-label">
              <input type="checkbox" />
              <span>{{ component.label }}</span>
            </label>
          </div>

          <div v-else-if="component.type === 'file_upload'" class="component-upload">
            <div class="upload-area" @click="triggerUpload">
              <span class="upload-icon">📁</span>
              <span class="upload-text">{{ component.label }}</span>
              <span class="upload-hint">支持: {{ component.accept.join(', ') }}</span>
            </div>
            <input type="file" class="upload-input" @change="handleFileSelect" multiple />
          </div>

          <div v-else-if="component.type === 'button'" class="component-button">
            <button 
              :class="['btn', { primary: component.primary, secondary: component.secondary }]"
            >{{ component.label }}</button>
          </div>

          <div v-else-if="component.type === 'row'" class="component-row">
            <div 
              v-for="child in component.children" 
              :key="child.id"
              :class="['ui-component', child.type]"
            >
              <button 
                v-if="child.type === 'button'"
                :class="['btn', { primary: child.primary, secondary: child.secondary }]"
              >{{ child.label }}</button>
            </div>
          </div>

          <div v-else-if="component.type === 'table'" class="component-table">
            <table class="data-table">
              <thead>
                <tr>
                  <th v-for="col in component.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in component.data" :key="rowIndex">
                  <td v-for="(cell, colIndex) in row" :key="colIndex">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="component.type === 'form'" class="component-form">
            <form @submit.prevent="handleFormSubmit">
              <div 
                v-for="field in component.fields" 
                :key="field.id"
                :class="['form-field', field.type]"
              >
                <label class="input-label">{{ field.label }}</label>
                <input 
                  v-if="field.type === 'text'"
                  type="text" 
                  :placeholder="field.placeholder"
                  class="text-field"
                />
                <select v-else-if="field.type === 'select'" class="select-field">
                  <option value="">请选择...</option>
                  <option 
                    v-for="opt in field.options" 
                    :key="opt.value"
                    :value="opt.value"
                  >{{ opt.label }}</option>
                </select>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn primary">提交</button>
                <button type="button" class="btn">重置</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>

    <div class="component-stats">
      <div class="stat-item">
        <span class="stat-icon">🧩</span>
        <span class="stat-label">组件数</span>
        <span class="stat-value">{{ renderedComponents.length }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-icon">📊</span>
        <span class="stat-label">表单字段</span>
        <span class="stat-value">{{ formFieldCount }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-icon">✨</span>
        <span class="stat-label">交互组件</span>
        <span class="stat-value">{{ interactionCount }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const selectedIntent = ref('');
const currentSchema = ref(null);
const selectedOptions = ref([]);

const intentSchemas = {
  create_crud: {
    intent: 'create_crud',
    entity: 'Employee',
    fields: [
      { name: 'name', type: 'string', label: '员工姓名', required: true },
      { name: 'department', type: 'enum', label: '部门', options: ['研发部', '产品部', '销售部', '财务部'] },
      { name: 'position', type: 'string', label: '职位' },
      { name: 'salary', type: 'number', label: '薪资' },
      { name: 'hire_date', type: 'date', label: '入职日期' },
      { name: 'status', type: 'boolean', label: '在职状态' }
    ],
    actions: ['create', 'read', 'update', 'delete']
  },
  form_fill: {
    intent: 'form_fill',
    title: '项目信息表单',
    fields: [
      { name: 'project_name', type: 'string', label: '项目名称', required: true },
      { name: 'project_type', type: 'select', label: '项目类型', options: ['化工项目', '制造业', '基础设施', '其他'] },
      { name: 'sensitive_area', type: 'multiselect', label: '涉及敏感区域', options: ['水源地', '居民区', '学校', '医院'] },
      { name: 'description', type: 'textarea', label: '项目描述' }
    ]
  },
  data_upload: {
    intent: 'data_upload',
    title: '数据上传',
    accept: ['.pdf', '.docx', '.xlsx', '.csv'],
    description: '上传环评相关文件'
  },
  search: {
    intent: 'search',
    title: '知识检索',
    placeholder: '输入搜索关键词...',
    scopeOptions: ['全部', '导则标准', '报告范本', '法律法规']
  },
  analysis: {
    intent: 'analysis',
    title: '数据分析',
    analysisType: ['环境影响分析', '合规性分析', '风险评估', '对比分析'],
    dataSources: ['监测数据', '标准限值', '现状基线', '预测结果']
  },
  report: {
    intent: 'report',
    title: '生成报告',
    reportType: ['完整报告', '报告摘要', '特定章节'],
    sections: ['项目概述', '现状调查', '影响预测', '环保措施', '结论与建议'],
    formats: ['markdown', 'word', 'pdf']
  }
};

const renderedComponents = computed(() => {
  if (!selectedIntent.value) return [];
  
  const schema = intentSchemas[selectedIntent.value];
  if (!schema) return [];
  
  return generateComponents(schema);
});

const formFieldCount = computed(() => {
  return renderedComponents.value.filter(c => 
    ['text_input', 'textarea', 'select', 'multi_select'].includes(c.type)
  ).length;
});

const interactionCount = computed(() => {
  return renderedComponents.value.filter(c => 
    ['button', 'file_upload'].includes(c.type)
  ).length;
});

const generateComponents = (schema) => {
  const components = [];
  
  switch(schema.intent) {
    case 'create_crud':
      components.push({
        id: 'crud_title',
        type: 'heading',
        label: `创建 ${schema.entity} 管理页面`
      });
      
      components.push({
        id: 'crud_desc',
        type: 'text',
        value: '请配置以下字段信息：'
      });
      
      schema.fields.forEach((field, index) => {
        if (field.type === 'string' || field.type === 'number' || field.type === 'date') {
          components.push({
            id: `field_${field.name}`,
            type: 'text_input',
            label: field.label,
            placeholder: `请输入${field.label}`,
            required: field.required
          });
        } else if (field.type === 'enum') {
          components.push({
            id: `field_${field.name}`,
            type: 'select',
            label: field.label,
            options: field.options.map(opt => ({ value: opt, label: opt }))
          });
        } else if (field.type === 'boolean') {
          components.push({
            id: `field_${field.name}`,
            type: 'checkbox',
            label: field.label
          });
        }
      });
      
      components.push({
        id: 'crud_actions',
        type: 'row',
        children: [
          { id: 'btn_create', type: 'button', label: '生成代码', primary: true },
          { id: 'btn_preview', type: 'button', label: '预览' },
          { id: 'btn_export', type: 'button', label: '导出', secondary: true }
        ]
      });
      
      components.push({
        id: 'crud_table',
        type: 'table',
        columns: schema.fields.map(f => f.label),
        data: [
          ['张三', '研发部', '工程师', '15000', '2024-01-15', '在职'],
          ['李四', '产品部', '产品经理', '18000', '2023-06-20', '在职'],
          ['王五', '销售部', '销售代表', '12000', '2024-03-10', '在职']
        ]
      });
      break;
      
    case 'form_fill':
      components.push({
        id: 'form_title',
        type: 'heading',
        label: schema.title
      });
      
      schema.fields.forEach(field => {
        if (field.type === 'string') {
          components.push({
            id: `field_${field.name}`,
            type: 'text_input',
            label: field.label,
            placeholder: `请输入${field.label}`,
            required: field.required
          });
        } else if (field.type === 'select') {
          components.push({
            id: `field_${field.name}`,
            type: 'select',
            label: field.label,
            options: field.options.map(opt => ({ value: opt, label: opt }))
          });
        } else if (field.type === 'multiselect') {
          components.push({
            id: `field_${field.name}`,
            type: 'multi_select',
            label: field.label,
            options: field.options.map(opt => ({ value: opt, label: opt }))
          });
        } else if (field.type === 'textarea') {
          components.push({
            id: `field_${field.name}`,
            type: 'textarea',
            label: field.label,
            placeholder: `请详细描述...`,
            rows: 4
          });
        }
      });
      
      components.push({
        id: 'form_actions',
        type: 'row',
        children: [
          { id: 'btn_submit', type: 'button', label: '提交', primary: true },
          { id: 'btn_reset', type: 'button', label: '重置' },
          { id: 'btn_cancel', type: 'button', label: '取消', secondary: true }
        ]
      });
      break;
      
    case 'data_upload':
      components.push({
        id: 'upload_title',
        type: 'heading',
        label: schema.title
      });
      
      components.push({
        id: 'upload_desc',
        type: 'text',
        value: schema.description
      });
      
      components.push({
        id: 'file_upload',
        type: 'file_upload',
        label: '选择文件',
        accept: schema.accept
      });
      break;
      
    case 'search':
      components.push({
        id: 'search_title',
        type: 'heading',
        label: schema.title
      });
      
      components.push({
        id: 'search_input',
        type: 'text_input',
        label: '搜索关键词',
        placeholder: schema.placeholder
      });
      
      components.push({
        id: 'search_scope',
        type: 'select',
        label: '搜索范围',
        options: schema.scopeOptions.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'search_actions',
        type: 'row',
        children: [
          { id: 'btn_search', type: 'button', label: '搜索', primary: true },
          { id: 'btn_clear', type: 'button', label: '清除' }
        ]
      });
      break;
      
    case 'analysis':
      components.push({
        id: 'analysis_title',
        type: 'heading',
        label: schema.title
      });
      
      components.push({
        id: 'analysis_type',
        type: 'select',
        label: '分析类型',
        options: schema.analysisType.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'data_sources',
        type: 'multi_select',
        label: '数据源',
        options: schema.dataSources.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'analysis_actions',
        type: 'row',
        children: [
          { id: 'btn_analyze', type: 'button', label: '开始分析', primary: true },
          { id: 'btn_export', type: 'button', label: '导出结果' }
        ]
      });
      break;
      
    case 'report':
      components.push({
        id: 'report_title',
        type: 'heading',
        label: schema.title
      });
      
      components.push({
        id: 'report_type',
        type: 'select',
        label: '报告类型',
        options: schema.reportType.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'report_sections',
        type: 'multi_select',
        label: '包含章节',
        options: schema.sections.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'report_format',
        type: 'select',
        label: '输出格式',
        options: schema.formats.map(opt => ({ value: opt, label: opt }))
      });
      
      components.push({
        id: 'report_actions',
        type: 'row',
        children: [
          { id: 'btn_generate', type: 'button', label: '生成报告', primary: true },
          { id: 'btn_preview', type: 'button', label: '预览' }
        ]
      });
      break;
  }
  
  return components;
};

const renderUI = () => {
  if (selectedIntent.value) {
    currentSchema.value = intentSchemas[selectedIntent.value];
  }
};

const formatSchema = (schema) => {
  return JSON.stringify(schema, null, 2);
};

const exportSchema = () => {
  if (currentSchema.value) {
    const blob = new Blob([formatSchema(currentSchema.value)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentSchema.value.intent}_schema.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
};

const isSelected = (value) => {
  return selectedOptions.value.includes(value);
};

const toggleSelection = (value) => {
  const index = selectedOptions.value.indexOf(value);
  if (index > -1) {
    selectedOptions.value.splice(index, 1);
  } else {
    selectedOptions.value.push(value);
  }
};

const triggerUpload = () => {
  document.querySelector('.upload-input').click();
};

const handleFileSelect = (event) => {
  const files = event.target.files;
  console.log('Selected files:', files);
};

const handleFormSubmit = () => {
  console.log('Form submitted');
};
</script>

<style scoped>
.dynamic-ui-panel {
  background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%);
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
  color: #e9d5ff;
}

.ui-icon {
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.intent-select {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  font-size: 12px;
  cursor: pointer;
  outline: none;
}

.intent-select option {
  background: #4c1d95;
  color: white;
}

.refresh-btn {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.ui-content {
  padding: 16px;
}

.schema-preview {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}

.schema-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.3);
}

.schema-title {
  font-size: 13px;
  font-weight: 600;
  color: #e9d5ff;
}

.export-btn {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 11px;
  cursor: pointer;
}

.export-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.schema-code {
  margin: 0;
  padding: 12px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  color: #a5b4fc;
  white-space: pre-wrap;
  overflow-x: auto;
}

.ui-canvas {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ui-component {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.component-heading {
  font-size: 18px;
  font-weight: 700;
  color: white;
  text-align: center;
  padding: 16px;
}

.component-text {
  font-size: 14px;
  color: #e0e7ff;
  line-height: 1.6;
}

.component-input, .component-textarea, .component-select, .component-multi-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-label {
  font-size: 12px;
  font-weight: 500;
  color: #c4b5fd;
}

.text-field, .textarea-field, .select-field {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.text-field:focus, .textarea-field:focus, .select-field:focus {
  border-color: #a78bfa;
}

.text-field::placeholder, .textarea-field::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.textarea-field {
  resize: vertical;
  min-height: 80px;
}

.select-field option {
  background: #4c1d95;
  color: white;
}

.multi-select-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.multi-option {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #e0e7ff;
  cursor: pointer;
  transition: all 0.2s;
}

.multi-option:hover {
  background: rgba(255, 255, 255, 0.2);
}

.multi-option.selected {
  background: rgba(167, 139, 250, 0.5);
  border-color: #a78bfa;
}

.component-checkbox {
  display: flex;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #e0e7ff;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #a78bfa;
}

.component-upload {
  position: relative;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  border: 2px dashed rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #a78bfa;
  background: rgba(255, 255, 255, 0.05);
}

.upload-icon {
  font-size: 32px;
}

.upload-text {
  font-size: 14px;
  font-weight: 500;
  color: white;
}

.upload-hint {
  font-size: 12px;
  color: #a5b4fc;
}

.upload-input {
  display: none;
}

.component-button {
  display: flex;
  justify-content: center;
}

.btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn.primary {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.btn.primary:hover {
  background: linear-gradient(135deg, #16a34a, #15803d);
}

.btn.secondary {
  background: rgba(255, 255, 255, 0.15);
  color: #c4b5fd;
}

.component-row {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}

.component-table {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
}

.data-table th {
  background: rgba(0, 0, 0, 0.2);
  color: #c4b5fd;
  font-weight: 600;
}

.data-table td {
  color: #e0e7ff;
}

.data-table tr:hover td {
  background: rgba(255, 255, 255, 0.05);
}

.component-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.component-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.1);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-icon {
  font-size: 16px;
}

.stat-label {
  font-size: 11px;
  color: #a5b4fc;
}

.stat-value {
  margin-left: auto;
  font-size: 16px;
  font-weight: 600;
  color: white;
}
</style>