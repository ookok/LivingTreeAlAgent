<template>
  <div ref="editorContainer" class="monaco-editor-container"></div>
</template>

<script setup>import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as monaco from 'monaco-editor';
const props = defineProps({
 modelValue: {
 type: String,
 default: ''
 },
 language: {
 type: String,
 default: 'python'
 },
 filename: {
 type: String,
 default: 'untitled.py'
 }
});
const emit = defineEmits(['update:modelValue', 'change']);
const editorContainer = ref(null);
let editor = null;
let model = null;
const supportedLanguages = [
 'python', 'javascript', 'typescript', 'json', 'markdown', 
 'html', 'css', 'java', 'cpp', 'go', 'rust', 'sql', 'yaml'
];
function getLanguage(filename) {
 const ext = filename.split('.').pop().toLowerCase();
 const extMap = {
 'py': 'python',
 'js': 'javascript',
 'ts': 'typescript',
 'json': 'json',
 'md': 'markdown',
 'html': 'html',
 'css': 'css',
 'java': 'java',
 'cpp': 'cpp',
 'h': 'cpp',
 'go': 'go',
 'rs': 'rust',
 'sql': 'sql',
 'yaml': 'yaml',
 'yml': 'yaml'
 };
 return extMap[ext] || 'plaintext';
}
onMounted(() => {
 if (!editorContainer.value)
 return;
 monaco.editor.defineTheme('livingtree-dark', {
 base: 'vs-dark',
 inherit: true,
 rules: [],
 colors: {
 'editor.background': '#0f172a',
 'editor.foreground': '#f8fafc',
 'editor.lineHighlightBackground': '#1e293b',
 'editor.selectionBackground': '#3b82f6',
 'editorLineNumber.foreground': '#64748b',
 'editorLineNumber.activeForeground': '#f8fafc',
 'editorCursor.foreground': '#f8fafc',
 'editorWhitespace.foreground': '#334155',
 'editor.inactiveSelectionBackground': '#1e3a5f',
 'editorError.foreground': '#ef4444',
 'editorWarning.foreground': '#f59e0b',
 'editorInfo.foreground': '#3b82f6'
 }
 });
 monaco.editor.defineTheme('livingtree-light', {
 base: 'vs',
 inherit: true,
 rules: [],
 colors: {
 'editor.background': '#ffffff',
 'editor.foreground': '#1e293b',
 'editor.lineHighlightBackground': '#f1f5f9',
 'editor.selectionBackground': '#bfdbfe',
 'editorLineNumber.foreground': '#94a3b8',
 'editorLineNumber.activeForeground': '#1e293b',
 'editorCursor.foreground': '#1e293b',
 'editorWhitespace.foreground': '#e2e8f0',
 'editor.inactiveSelectionBackground': '#dbeafe',
 'editorError.foreground': '#dc2626',
 'editorWarning.foreground': '#d97706',
 'editorInfo.foreground': '#2563eb'
 }
 });
 const lang = props.language || getLanguage(props.filename);
 model = monaco.editor.createModel(props.modelValue, lang, monaco.Uri.file(props.filename));
 editor = monaco.editor.create(editorContainer.value, {
 model: model,
 theme: 'livingtree-dark',
 fontSize: 14,
 fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
 lineNumbers: 'on',
 scrollBeyondLastLine: false,
 automaticLayout: true,
 minimap: {
 enabled: true
 },
 folding: true,
 foldingHighlight: true,
 foldingHighlightOptions: {
 borderColor: 'rgba(59, 130, 246, 0.5)'
 },
 bracketPairColorization: {
 enabled: true
 },
 tabSize: 4,
 insertSpaces: true,
 wordWrap: 'on',
 smoothScrolling: true,
 cursorBlinking: 'smooth',
 cursorSmoothCaretAnimation: 'on',
 renderLineHighlight: 'line',
 padding: {
 top: 16,
 bottom: 16
 },
 contextmenu: true,
 suggest: {
 enabled: true,
 snippetsPreventQuickSuggestions: false,
 showKeywords: true,
 showClasses: true,
 showMethods: true,
 showFunctions: true,
 showVariables: true,
 showConstants: true,
 showStructs: true,
 showInterfaces: true,
 showModules: true,
 showProperties: true,
 showEvents: true,
 showOperators: true,
 showConstructors: true,
 showFields: true,
 showEnums: true,
 showFileReferences: true,
 showTypeParameters: true,
 showWords: true,
 filterGraceful: true
 },
 quickSuggestions: {
 other: true,
 comments: true,
 strings: true
 },
 parameterHints: {
 enabled: true
 },
 inlineSuggest: {
 enabled: true
 },
 lightbulb: {
 enabled: true
 },
 codeLens: {
 enabled: true
 },
 glyphMargin: true,
 overviewRulerBorder: false,
 scrollbar: {
 verticalScrollbarSize: 10,
 horizontalScrollbarSize: 10
 },
 rulers: [80, 120],
 renderWhitespace: 'selection',
 wordBasedSuggestions: 'off'
 });
 editor.onDidChangeModelContent(() => {
 emit('update:modelValue', editor.getValue());
 emit('change', editor.getValue());
 });
});
onUnmounted(() => {
 if (editor) {
 editor.dispose();
 }
 if (model) {
 model.dispose();
 }
});
watch(() => props.modelValue, (newValue) => {
 if (editor && editor.getValue() !== newValue) {
 editor.setValue(newValue);
 }
});
watch(() => props.filename, (newFilename) => {
 if (model && editor) {
 const newLang = getLanguage(newFilename);
 model.setLanguage(newLang);
 model.uri = monaco.Uri.file(newFilename);
 }
});
function getEditor() {
 return editor;
}
function focus() {
 editor?.focus();
}
function setTheme(isDark) {
 editor?.updateOptions({
 theme: isDark ? 'livingtree-dark' : 'livingtree-light'
 });
}
function toggleWordWrap() {
 const current = editor?.getOption(monaco.editor.EditorOption.wordWrap);
 editor?.updateOptions({
 wordWrap: current === 'off' ? 'on' : 'off'
 });
}
function zoomIn() {
 const current = editor?.getOption(monaco.editor.EditorOption.fontSize);
 editor?.updateOptions({
 fontSize: Math.min(current + 1, 24)
 });
}
function zoomOut() {
 const current = editor?.getOption(monaco.editor.EditorOption.fontSize);
 editor?.updateOptions({
 fontSize: Math.max(current - 1, 10)
 });
}
function formatDocument() {
 editor?.trigger('editor', 'editor.action.formatDocument');
}
function toggleComment() {
 editor?.trigger('editor', 'editor.action.commentLine');
}
function goToLine(line) {
 editor?.revealLineInCenter(line);
 const position = new monaco.Position(line, 1);
 editor?.setPosition(position);
 editor?.focus();
}
function find(text) {
 editor?.trigger('editor', 'actions.find', {
 query: text
 });
}
function replace(text, replaceText) {
 editor?.trigger('editor', 'actions.find', {
 query: text,
 replace: replaceText
 });
}
defineExpose({
 getEditor,
 focus,
 setTheme,
 toggleWordWrap,
 zoomIn,
 zoomOut,
 formatDocument,
 toggleComment,
 goToLine,
 find,
 replace
});
</script>

<style scoped>
.monaco-editor-container {
  width: 100%;
  height: 100%;
  min-height: 300px;
}
</style>