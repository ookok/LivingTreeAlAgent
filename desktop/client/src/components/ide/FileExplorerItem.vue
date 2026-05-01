<template>
  <div class="tree-item" :style="{ paddingLeft: `${depth * 16}px` }">
    <div 
      class="tree-row"
      :class="{ 
        'is-folder': item.type === 'folder',
        'is-file': item.type === 'file',
        'is-expanded': item.expanded
      }"
      @click="$emit('toggle', item)"
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
        <NButton text size="tiny" @click="$emit('new-file', item)">
          <NIcon :component="FileIcon" :size="12" />
        </NButton>
        <NButton text size="tiny" @click="$emit('new-folder', item)">
          <NIcon :component="FolderPlusIcon" :size="12" />
        </NButton>
        <NButton text size="tiny" @click="$emit('delete', item)">
          <NIcon :component="TrashIcon" :size="12" />
        </NButton>
      </div>
    </div>
    
    <div 
      v-if="item.type === 'folder' && item.expanded && item.children?.length" 
      class="tree-children"
    >
      <FileExplorerItem
        v-for="child in item.children"
        :key="child.path"
        :item="child"
        :depth="depth + 1"
        @toggle="$emit('toggle', $event)"
        @open="$emit('open', $event)"
        @delete="$emit('delete', $event)"
        @new-file="$emit('new-file', $event)"
        @new-folder="$emit('new-folder', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { NButton, NIcon } from 'naive-ui'
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Trash2, FolderPlus } from '@vicons/ionicons5'

defineProps({
  item: {
    type: Object,
    required: true
  },
  depth: {
    type: Number,
    default: 0
  }
})

defineEmits(['toggle', 'open', 'delete', 'new-file', 'new-folder'])

const ChevronRightIcon = { render: () => h(ChevronRight) }
const ChevronDownIcon = { render: () => h(ChevronDown) }
const FileIcon = { render: () => h(File) }
const FolderPlusIcon = { render: () => h(FolderPlus) }
const TrashIcon = { render: () => h(Trash2) }

function getFileIcon(item) {
  if (item.type === 'folder') {
    return { render: () => h(item.expanded ? FolderOpen : Folder) }
  }
  return { render: () => h(File) }
}
</script>

<style scoped>
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
  overflow: hidden;
}
</style>