<template>
  <div class="code-editor">
    <div class="editor-header">
      <div class="file-tabs">
        <div 
          v-for="(file, index) in openFiles" 
          :key="index"
          :class="['file-tab', { active: activeFileIndex === index }]"
          @click="setActiveFile(index)"
        >
          <span class="file-icon">{{ getFileIcon(file.extension) }}</span>
          <span class="file-name">{{ file.name }}</span>
          <span class="close-tab" @click.stop="closeFile(index)">×</span>
        </div>
      </div>
      <div class="editor-actions">
        <button class="action-btn" @click="saveFile">💾</button>
        <button class="action-btn" @click="runCode">▶️</button>
        <button class="action-btn" @click="formatCode">🔧</button>
      </div>
    </div>
    <div class="editor-container" ref="editorContainer"></div>
    <div class="editor-footer">
      <span class="status-item">Ln {{ cursorPosition.line + 1 }}, Col {{ cursorPosition.column + 1 }}</span>
      <span class="status-item">{{ activeLanguage }}</span>
      <span class="status-item">UTF-8</span>
    </div>
  </div>
</template>

<script setup>import { ref, onMounted, onUnmounted, watch } from 'vue';
const props = defineProps({
 modelValue: {
 type: String,
 default: ''
 },
 language: {
 type: String,
 default: 'python'
 }
});
const emit = defineEmits(['update:modelValue', 'codeChange', 'runCode', 'saveFile']);
const editorContainer = ref(null);
let monacoEditor = null;
const openFiles = ref([
 { name: 'main.py', extension: 'py', content: '# Hello World\nprint("Hello, LivingTree!")' },
 { name: 'app.js', extension: 'js', content: '// JavaScript file\nconsole.log("Hello");' },
 { name: 'config.json', extension: 'json', content: '{\n "name": "livingtree"\n}' }
]);
const activeFileIndex = ref(0);
const cursorPosition = ref({ line: 0, column: 0 });
const languages = {
 py: 'python',
 js: 'javascript',
 json: 'json',
 html: 'html',
 css: 'css',
 md: 'markdown'
};
const getActiveFile = () => openFiles.value[activeFileIndex.value];
const activeLanguage = ref('python');
const getFileIcon = (ext) => {
 const icons = {
 py: '🐍',
 js: '📜',
 json: '📋',
 html: '🌐',
 css: '🎨',
 md: '📝'
 };
 return icons[ext] || '📄';
};
const setActiveFile = (index) => {
 activeFileIndex.value = index;
 if (monacoEditor && openFiles.value[index]) {
 monacoEditor.setValue(openFiles.value[index].content);
 activeLanguage.value = languages[openFiles.value[index].extension] || 'plaintext';
 monacoEditor.setModelLanguage(monacoEditor.getModel(), activeLanguage.value);
 }
};
const closeFile = (index) => {
 if (openFiles.value.length > 1) {
 openFiles.value.splice(index, 1);
 if (activeFileIndex.value >= openFiles.value.length) {
 activeFileIndex.value = openFiles.value.length - 1;
 }
 setActiveFile(activeFileIndex.value);
 }
};
const saveFile = () => {
 if (monacoEditor && getActiveFile()) {
 getActiveFile().content = monacoEditor.getValue();
 emit('saveFile', {
 name: getActiveFile().name,
 content: getActiveFile().content
 });
 }
};
const runCode = () => {
 if (monacoEditor) {
 emit('runCode', {
 language: activeLanguage.value,
 code: monacoEditor.getValue()
 });
 }
};
const formatCode = () => {
 if (monacoEditor) {
 monacoEditor.trigger('format', 'editor.action.formatDocument');
 }
};
const initEditor = async () => {
 if (!editorContainer.value)
 return;
 const loaderScript = document.createElement('script');
 loaderScript.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs/loader.js';
 loaderScript.onload = () => {
 window.require.config({
 paths: {
 vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@latest/min/vs'
 }
 });
 window.require(['vs/editor/editor.main'], () => {
 monacoEditor = window.monaco.editor.create(editorContainer.value, {
 value: getActiveFile()?.content || props.modelValue,
 language: languages[getActiveFile()?.extension] || props.language,
 theme: 'vs-dark',
 fontSize: 14,
 fontFamily: "'Fira Code', 'Consolas', monospace",
 minimap: { enabled: true },
 scrollBeyondLastLine: false,
 automaticLayout: true,
 tabSize: 4,
 insertSpaces: true,
 wordWrap: 'on',
 folding: true,
 foldingHighlight: true,
 bracketPairColorization: { enabled: true },
 renderLineHighlight: 'line',
 cursorBlinking: 'smooth',
 cursorSmoothCaretAnimation: 'on',
 smoothScrolling: true,
 padding: { top: 16, bottom: 16 }
 });
 monacoEditor.onDidChangeModelContent(() => {
 const value = monacoEditor.getValue();
 emit('update:modelValue', value);
 emit('codeChange', value);
 });
 monacoEditor.onDidChangeCursorPosition((event) => {
 const position = event.position;
 cursorPosition.value = {
 line: position.lineNumber - 1,
 column: position.column - 1
 };
 });
 };
 };
 document.head.appendChild(loaderScript);
};
watch(() => props.language, (newLang) => {
 if (monacoEditor) {
 monacoEditor.setModelLanguage(monacoEditor.getModel(), newLang);
 }
});
onMounted(() => {
 initEditor();
});
onUnmounted(() => {
 if (monacoEditor) {
 monacoEditor.dispose();
 }
});
</script>

<style scoped>
.code-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #252526;
  border-bottom: 1px solid #3c3c3c;
}

.file-tabs {
  display: flex;
  gap: 4px;
}

.file-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #2d2d2d;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
}

.file-tab.active {
  background: #1e1e1e;
}

.file-tab:hover {
  background: #37373d;
}

.file-icon {
  font-size: 14px;
}

.file-name {
  color: #c6c6c6;
}

.close-tab {
  color: #858585;
  font-size: 16px;
  padding: 0 4px;
}

.close-tab:hover {
  color: #c6c6c6;
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
}

.action-btn:hover {
  background: #3c3c3c;
}

.editor-container {
  flex: 1;
  min-height: 0;
}

.editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 20px;
  padding: 4px 12px;
  background: #252526;
  border-top: 1px solid #3c3c3c;
  font-size: 12px;
  color: #858585;
}

.status-item {
  padding: 2px 8px;
}
</style>