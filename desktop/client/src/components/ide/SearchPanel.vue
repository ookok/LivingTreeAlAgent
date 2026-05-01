<template>
  <div class="search-panel">
    <div class="panel-header">
      <NIcon :component="SearchIcon" :size="14" />
      <span>搜索</span>
      <NButton text size="tiny" @click="$emit('close')">
        <NIcon :component="XIcon" :size="12" />
      </NButton>
    </div>
    
    <div class="panel-content">
      <div class="search-input-area">
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索..."
          @input="performSearch"
          @keydown.enter="findNext"
        />
        <input
          v-model="replaceQuery"
          class="replace-input"
          placeholder="替换为..."
          @keydown.enter="replaceNext"
        />
      </div>
      
      <div class="search-options">
        <label class="option">
          <input type="checkbox" v-model="options.caseSensitive" />
          <span>大小写敏感</span>
        </label>
        <label class="option">
          <input type="checkbox" v-model="options.regex" />
          <span>正则表达式</span>
        </label>
        <label class="option">
          <input type="checkbox" v-model="options.wholeWord" />
          <span>全字匹配</span>
        </label>
      </div>
      
      <div class="search-actions">
        <NButton text @click="findNext">
          <NIcon :component="ArrowDownIcon" :size="12" />
          查找下一个
        </NButton>
        <NButton text @click="findPrev">
          <NIcon :component="ArrowUpIcon" :size="12" />
          查找上一个
        </NButton>
        <NButton text @click="replaceNext">
          <NIcon :component="ReplaceIcon" :size="12" />
          替换
        </NButton>
        <NButton text @click="replaceAll">
          <NIcon :component="ReplaceAllIcon" :size="12" />
          全部替换
        </NButton>
      </div>
      
      <div class="search-results">
        <div class="results-header">
          找到 {{ searchResults.length }} 个结果
        </div>
        <div class="results-list">
          <div 
            v-for="(result, index) in searchResults" 
            :key="index" 
            class="result-item"
            :class="{ active: index === currentMatch }"
            @click="goToResult(result)"
          >
            <NIcon :component="FileIcon" :size="14" />
            <span class="result-file">{{ result.file }}</span>
            <span class="result-line">行 {{ result.line }}</span>
            <div class="result-preview">{{ result.preview }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { 
  Search, X, ArrowDown, ArrowUp, Replace, File 
} from '@vicons/ionicons5'

const SearchIcon = { render: () => h(Search) }
const XIcon = { render: () => h(X) }
const ArrowDownIcon = { render: () => h(ArrowDown) }
const ArrowUpIcon = { render: () => h(ArrowUp) }
const ReplaceIcon = { render: () => h(Replace) }
const ReplaceAllIcon = { render: () => h(Replace) }
const FileIcon = { render: () => h(File) }

const emit = defineEmits(['close', 'go-to'])

const searchQuery = ref('')
const replaceQuery = ref('')
const currentMatch = ref(0)
const searchResults = ref([])

const options = reactive({
  caseSensitive: false,
  regex: false,
  wholeWord: false
})

function performSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  
  searchResults.value = [
    { file: 'main.py', line: 5, preview: `def ${searchQuery.value}():` },
    { file: 'main.py', line: 12, preview: `    ${searchQuery.value} = "Hello"` },
    { file: 'utils.py', line: 3, preview: `from ${searchQuery.value} import *` },
    { file: 'utils.py', line: 15, preview: `    return ${searchQuery.value}` },
  ]
  currentMatch.value = 0
}

function findNext() {
  if (searchResults.value.length > 0) {
    currentMatch.value = (currentMatch.value + 1) % searchResults.value.length
    goToResult(searchResults.value[currentMatch.value])
  }
}

function findPrev() {
  if (searchResults.value.length > 0) {
    currentMatch.value = (currentMatch.value - 1 + searchResults.value.length) % searchResults.value.length
    goToResult(searchResults.value[currentMatch.value])
  }
}

function replaceNext() {
  if (searchResults.value.length > 0) {
    searchResults.value[currentMatch.value].preview = 
      searchResults.value[currentMatch.value].preview.replace(searchQuery.value, replaceQuery.value)
    findNext()
  }
}

function replaceAll() {
  searchResults.value.forEach(result => {
    result.preview = result.preview.replace(searchQuery.value, replaceQuery.value)
  })
}

function goToResult(result) {
  emit('go-to', result)
}

watch(searchQuery, performSearch)
</script>

<style scoped>
.search-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.search-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.search-input, .replace-input {
  padding: 10px 12px;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.search-input:focus, .replace-input:focus {
  border-color: var(--primary-color);
}

.search-input::placeholder, .replace-input::placeholder {
  color: var(--text-secondary);
}

.search-options {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}

.option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.search-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.search-actions button {
  flex: 1;
  min-width: 100px;
}

.search-results {
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}

.results-header {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.results-list {
  max-height: 200px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.result-item:hover {
  background: var(--bg-hover);
}

.result-item.active {
  background: var(--primary-color);
}

.result-item.active .result-file,
.result-item.active .result-line,
.result-item.active .result-preview {
  color: white;
}

.result-file {
  font-size: 13px;
  color: var(--text-primary);
}

.result-line {
  font-size: 12px;
  color: var(--text-secondary);
}

.result-preview {
  font-size: 12px;
  color: var(--text-primary);
  font-family: monospace;
  padding-left: 16px;
}
</style>