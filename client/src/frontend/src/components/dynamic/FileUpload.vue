<template>
  <div class="file-upload-component">
    <label v-if="label">{{ label }}<span v-if="required" class="required">*</span></label>
    <div
      class="upload-area"
      :class="{ 'drag-over': isDragOver }"
      @click="triggerUpload"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="accept.join(',')"
        :multiple="multiple"
        @change="handleFileSelect"
        class="file-input"
      />
      <div class="upload-icon">📁</div>
      <span class="upload-text">{{ buttonText }}</span>
      <span class="upload-hint">支持 {{ accept.join(', ') }}</span>
    </div>
    
    <div v-if="files.length > 0" class="file-list">
      <div v-for="(file, index) in files" :key="index" class="file-item">
        <span class="file-name">{{ file.name }}</span>
        <span class="file-size">{{ formatSize(file.size) }}</span>
        <button class="remove-btn" @click.stop="removeFile(index)">×</button>
      </div>
    </div>
  </div>
</template>

<script setup>import { ref, computed } from 'vue';
const props = defineProps({
 id: String,
 label: String,
 accept: {
 type: Array,
 default: () => ['.pdf', '.docx', '.xlsx', '.jpg', '.png']
 },
 multiple: Boolean,
 required: Boolean
});
const emit = defineEmits(['filesSelected']);
const fileInput = ref(null);
const isDragOver = ref(false);
const files = ref([]);
const buttonText = computed(() => {
 return files.value.length > 0 ? `已选择 ${files.value.length} 个文件` : '点击上传文件';
});
function triggerUpload() {
 fileInput.value?.click();
}
function handleFileSelect(event) {
 const selectedFiles = Array.from(event.target.files);
 files.value = [...files.value, ...selectedFiles];
 emit('filesSelected', files.value);
}
function handleDrop(event) {
 isDragOver.value = false;
 const droppedFiles = Array.from(event.dataTransfer.files);
 files.value = [...files.value, ...droppedFiles];
 emit('filesSelected', files.value);
}
function removeFile(index) {
 files.value.splice(index, 1);
 emit('filesSelected', files.value);
}
function formatSize(bytes) {
 if (bytes < 1024)
 return bytes + ' B';
 if (bytes < 1024 * 1024)
 return (bytes / 1024).toFixed(1) + ' KB';
 return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
</script>

<style scoped>
.file-upload-component {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-upload-component label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.upload-area.drag-over {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}

.file-input {
  display: none;
}

.upload-icon {
  font-size: 32px;
}

.upload-text {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
}

.file-list {
  margin-top: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 4px;
  margin-bottom: 4px;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
}

.file-size {
  font-size: 12px;
  color: #9ca3af;
}

.remove-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: #ef4444;
  color: white;
  border-radius: 50%;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-btn:hover {
  background: #dc2626;
}
</style>