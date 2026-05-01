<template>
  <div class="file-explorer">
    <div class="explorer-header">
      <NButton text size="small" @click="refreshFiles">
        <NIcon :component="RefreshIcon" :size="14" />
      </NButton>
      <span class="header-title">资源管理器</span>
      <NButton text size="small" @click="toggleCollapseAll">
        <NIcon :component="CollapseIcon" :size="14" />
      </NButton>
    </div>
    
    <div class="explorer-content">
      <div class="folder-tree">
        <div
          v-for="item in fileTree"
          :key="item.path"
          class="tree-item"
        >
          <div 
            class="tree-row"
            :class="{ 
              'is-folder': item.type === 'folder',
              'is-file': item.type === 'file',
              'is-expanded': item.expanded
            }"
            @click="toggleExpand(item)"
          >
            <span class="expand-icon" v-if="item.type === 'folder'">
              <NIcon 
                :component="item.expanded ? ChevronDownIcon : ChevronRightIcon" 
                :size="14" 
              />
            </span>
            <span class="expand-placeholder" v-else></span>
            
            <NIcon 
              :component="getFileIcon(item)" 
              :size="16" 
              class="file-icon"
              :class="{ 'folder-open': item.expanded && item.type === 'folder' }"
            />
            
            <span class="item-name">{{ item.name }}</span>
            
            <div class="item-actions" @click.stop>
              <NButton text size="tiny" @click="newFile(item)">
                <NIcon :component="FileIcon" :size="12" />
              </NButton>
              <NButton text size="tiny" @click="newFolder(item)">
                <NIcon :component="FolderPlusIcon" :size="12" />
              </NButton>
              <NButton text size="tiny" @click="deleteItem(item)">
                <NIcon :component="TrashIcon" :size="12" />
              </NButton>
            </div>
          </div>
          
          <div 
            v-if="item.type === 'folder' && item.expanded && item.children" 
            class="tree-children"
          >
            <FileExplorerItem
              v-for="child in item.children"
              :key="child.path"
              :item="child"
              :depth="1"
              @toggle="handleChildToggle"
              @open="openFile"
              @delete="deleteItem"
              @new-file="newFile"
              @new-folder="newFolder"
            />
          </div>
        </div>
      </div>
      
      <div v-if="fileTree.length === 0" class="empty-state">
        <NIcon :component="FolderOpenIcon" :size="32" />
        <p>暂无文件</p>
        <NButton text @click="newFile()">创建文件</NButton>
      </div>
    </div>
  </div>
</template>

<script setup>import { ref, onMounted } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import { RefreshCw, ChevronRight, ChevronDown, File, Folder, FolderOpen, Plus, Trash2, FolderPlus } from '@vicons/ionicons5';
const RefreshIcon = { render: () => h(RefreshCw) };
const ChevronRightIcon = { render: () => h(ChevronRight) };
const ChevronDownIcon = { render: () => h(ChevronDown) };
const FileIcon = { render: () => h(File) };
const FolderPlusIcon = { render: () => h(FolderPlus) };
const TrashIcon = { render: () => h(Trash2) };
const FolderOpenIcon = { render: () => h(FolderOpen) };
const emit = defineEmits(['open-file']);
const fileTree = ref([]);
const currentPath = ref('.');
function getFileIcon(item) {
 if (item.type === 'folder') {
 return { render: () => h(item.expanded ? FolderOpen : Folder) };
 }
 const ext = item.name.split('.').pop().toLowerCase();
 if (ext === 'py')
 return { render: () => h(File) };
 if (ext === 'md')
 return { render: () => h(File) };
 if (ext === 'json')
 return { render: () => h(File) };
 return { render: () => h(File) };
}
function buildFileTree(dirPath, depth = 0) {
 const items = [];
 try {
 const fs = require('fs');
 const path = require('path');
 const fullPath = path.resolve(dirPath);
 if (!fs.existsSync(fullPath)) {
 fs.mkdirSync(fullPath, { recursive: true });
 }
 const files = fs.readdirSync(fullPath);
 const directories = [];
 const fileList = [];
 files.forEach(file => {
 const filePath = path.join(fullPath, file);
 const stat = fs.statSync(filePath);
 if (stat.isDirectory()) {
 directories.push(file);
 }
 else {
 fileList.push(file);
 }
 });
 directories.sort();
 fileList.sort();
 directories.forEach(dir => {
 const dirPathFull = path.join(dirPath, dir);
 const children = depth < 2 ? buildFileTree(dirPathFull, depth + 1) : [];
 items.push({
 name: dir,
 path: dirPathFull,
 type: 'folder',
 expanded: depth === 0,
 children: children
 });
 });
 fileList.forEach(file => {
 items.push({
 name: file,
 path: path.join(dirPath, file),
 type: 'file',
 expanded: false,
 children: []
 });
 });
 }
 catch (e) {
 console.error('Error building file tree:', e);
 }
 return items;
}
function refreshFiles() {
 fileTree.value = buildFileTree(currentPath.value);
}
function toggleExpand(item) {
 if (item.type === 'folder') {
 item.expanded = !item.expanded;
 if (item.expanded && !item.children.length) {
 item.children = buildFileTree(item.path, 1);
 }
 }
 else {
 openFile(item);
 }
}
function handleChildToggle(item) {
 toggleExpand(item);
}
function openFile(item) {
 if (item.type === 'file') {
 try {
 const fs = require('fs');
 const content = fs.readFileSync(item.path, 'utf-8');
 emit('open-file', {
 name: item.name,
 path: item.path,
 content: content,
 type: item.name.split('.').pop().toLowerCase()
 });
 }
 catch (e) {
 console.error('Error opening file:', e);
 }
 }
}
function newFile(parent = null) {
 const fs = require('fs');
 const path = require('path');
 const parentPath = parent?.path || currentPath.value;
 const newFilePath = path.join(parentPath, 'untitled.py');
 if (!fs.existsSync(newFilePath)) {
 fs.writeFileSync(newFilePath, '# New File\n');
 refreshFiles();
 }
 else {
 let i = 1;
 while (fs.existsSync(path.join(parentPath, `untitled${i}.py`))) {
 i++;
 }
 fs.writeFileSync(path.join(parentPath, `untitled${i}.py`), '# New File\n');
 refreshFiles();
 }
}
function newFolder(parent = null) {
 const fs = require('fs');
 const path = require('path');
 const parentPath = parent?.path || currentPath.value;
 const newFolderPath = path.join(parentPath, 'new_folder');
 if (!fs.existsSync(newFolderPath)) {
 fs.mkdirSync(newFolderPath);
 refreshFiles();
 }
 else {
 let i = 1;
 while (fs.existsSync(path.join(parentPath, `new_folder${i}`))) {
 i++;
 }
 fs.mkdirSync(path.join(parentPath, `new_folder${i}`));
 refreshFiles();
 }
}
function deleteItem(item) {
 if (confirm(`确定要删除 "${item.name}" 吗？`)) {
 const fs = require('fs');
 const path = require('path');
 const fullPath = path.resolve(item.path);
 if (item.type === 'folder') {
 fs.rmSync(fullPath, { recursive: true });
 }
 else {
 fs.unlinkSync(fullPath);
 }
 refreshFiles();
 }
}
function toggleCollapseAll() {
 function toggleAll(items, expanded) {
 items.forEach(item => {
 item.expanded = expanded;
 if (item.children) {
 toggleAll(item.children, expanded);
 }
 });
 }
 const expanded = fileTree.value.some(item => item.type === 'folder' && item.expanded);
 toggleAll(fileTree.value, !expanded);
}
onMounted(() => {
 refreshFiles();
});
</script>

<style scoped>
.file-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.explorer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
}

.header-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.explorer-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.folder-tree {
  padding: 4px 0;
}

.tree-item {
  min-width: 0;
}

.tree-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.tree-row:hover {
  background: var(--bg-hover);
}

.tree-row:hover .item-actions {
  opacity: 1;
}

.expand-icon, .expand-placeholder {
  width: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.expand-placeholder {
  visibility: hidden;
}

.file-icon {
  flex-shrink: 0;
  color: var(--text-secondary);
}

.file-icon.folder-open {
  color: var(--warning-color);
}

.item-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.tree-children {
  padding-left: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.empty-state p {
  margin: 12px 0;
}
</style>