<template>
  <div class="toolbar">
    <NButton text @click="newFile">
      <NIcon :component="NewIcon" :size="18" />
    </NButton>
    <NButton text @click="openFile">
      <NIcon :component="OpenIcon" :size="18" />
    </NButton>
    <NButton text @click="saveFile">
      <NIcon :component="SaveIcon" :size="18" />
    </NButton>
    
    <div class="toolbar-divider"></div>
    
    <NButton text @click="undo">
      <NIcon :component="UndoIcon" :size="18" />
    </NButton>
    <NButton text @click="redo">
      <NIcon :component="RedoIcon" :size="18" />
    </NButton>
    
    <div class="toolbar-divider"></div>
    
    <NButton text @click="runCode">
      <NIcon :component="PlayIcon" :size="18" />
    </NButton>
    <NButton text @click="debugCode">
      <NIcon :component="BugIcon" :size="18" />
    </NButton>
    
    <div class="toolbar-spacer"></div>
    
    <NButton text @click="toggleSidebar">
      <NIcon :component="SidebarIcon" :size="18" />
    </NButton>
    <NButton text @click="toggleBottomPanel">
      <NIcon :component="PanelIcon" :size="18" />
    </NButton>
    <NButton text @click="splitEditor">
      <NIcon :component="SplitIcon" :size="18" />
    </NButton>
    
    <div class="toolbar-spacer"></div>
    
    <NButton text @click="formatCode">
      <NIcon :component="FormatIcon" :size="18" />
    </NButton>
    <NButton text @click="toggleComment">
      <NIcon :component="CommentIcon" :size="18" />
    </NButton>
  </div>
</template>

<script setup>
import { NButton, NIcon } from 'naive-ui'
import { 
  FilePlus, FolderOpen, Save, Undo2, Redo2, Play, Bug, 
  PanelLeftClose, PanelBottomClose, SplitSquareHorizontal,
  Code, MessageSquare
} from '@vicons/ionicons5'

const NewIcon = { render: () => h(FilePlus) }
const OpenIcon = { render: () => h(FolderOpen) }
const SaveIcon = { render: () => h(Save) }
const UndoIcon = { render: () => h(Undo2) }
const RedoIcon = { render: () => h(Redo2) }
const PlayIcon = { render: () => h(Play) }
const BugIcon = { render: () => h(Bug) }
const SidebarIcon = { render: () => h(PanelLeftClose) }
const PanelIcon = { render: () => h(PanelBottomClose) }
const SplitIcon = { render: () => h(SplitSquareHorizontal) }
const FormatIcon = { render: () => h(Code) }
const CommentIcon = { render: () => h(MessageSquare) }

function newFile() { console.log('New file') }
function openFile() { console.log('Open file') }
function saveFile() { console.log('Save file') }
function undo() { console.log('Undo') }
function redo() { console.log('Redo') }
function runCode() { console.log('Run') }
function debugCode() { console.log('Debug') }
function toggleSidebar() { console.log('Toggle sidebar') }
function toggleBottomPanel() { console.log('Toggle bottom panel') }
function splitEditor() { console.log('Split editor') }
function formatCode() { console.log('Format code') }
function toggleComment() { console.log('Toggle comment') }
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.toolbar-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
  margin: 0 4px;
}

.toolbar-spacer {
  flex: 1;
}
</style>