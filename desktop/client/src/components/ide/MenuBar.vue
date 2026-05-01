<template>
  <menu class="menu-bar">
    <div class="menu-item" @click="toggleMenu('file')">
      <span>文件</span>
      <div v-if="activeMenu === 'file'" class="menu-dropdown">
        <div class="menu-option" @click="newFile">新建文件</div>
        <div class="menu-option" @click="openFile">打开文件...</div>
        <div class="menu-option" @click="saveFile">保存</div>
        <div class="menu-option" @click="saveAs">另存为...</div>
        <div class="menu-separator"></div>
        <div class="menu-option" @click="closeFile">关闭文件</div>
        <div class="menu-option" @click="closeAll">关闭全部</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('edit')">
      <span>编辑</span>
      <div v-if="activeMenu === 'edit'" class="menu-dropdown">
        <div class="menu-option">撤销</div>
        <div class="menu-option">重做</div>
        <div class="menu-separator"></div>
        <div class="menu-option">剪切</div>
        <div class="menu-option">复制</div>
        <div class="menu-option">粘贴</div>
        <div class="menu-separator"></div>
        <div class="menu-option">查找</div>
        <div class="menu-option">替换</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('view')">
      <span>视图</span>
      <div v-if="activeMenu === 'view'" class="menu-dropdown">
        <div class="menu-option">切换侧边栏</div>
        <div class="menu-option">切换底部面板</div>
        <div class="menu-option">全屏</div>
        <div class="menu-separator"></div>
        <div class="menu-option">放大</div>
        <div class="menu-option">缩小</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('run')">
      <span>运行</span>
      <div v-if="activeMenu === 'run'" class="menu-dropdown">
        <div class="menu-option">运行文件</div>
        <div class="menu-option">运行选中</div>
        <div class="menu-option">运行配置</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('debug')">
      <span>调试</span>
      <div v-if="activeMenu === 'debug'" class="menu-dropdown">
        <div class="menu-option">开始调试</div>
        <div class="menu-option">停止调试</div>
        <div class="menu-option">单步跳过</div>
        <div class="menu-option">单步进入</div>
        <div class="menu-option">切换断点</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('terminal')">
      <span>终端</span>
      <div v-if="activeMenu === 'terminal'" class="menu-dropdown">
        <div class="menu-option">新建终端</div>
        <div class="menu-option">切换终端</div>
        <div class="menu-option">关闭终端</div>
      </div>
    </div>
    
    <div class="menu-item" @click="toggleMenu('help')">
      <span>帮助</span>
      <div v-if="activeMenu === 'help'" class="menu-dropdown">
        <div class="menu-option">查看帮助</div>
        <div class="menu-option">关于</div>
      </div>
    </div>
  </menu>
</template>

<script setup>
import { ref } from 'vue'

const activeMenu = ref(null)

function toggleMenu(menu) {
  activeMenu.value = activeMenu.value === menu ? null : menu
}

function newFile() {
  console.log('New file')
  activeMenu.value = null
}

function openFile() {
  console.log('Open file')
  activeMenu.value = null
}

function saveFile() {
  console.log('Save file')
  activeMenu.value = null
}

function saveAs() {
  console.log('Save as')
  activeMenu.value = null
}

function closeFile() {
  console.log('Close file')
  activeMenu.value = null
}

function closeAll() {
  console.log('Close all')
  activeMenu.value = null
}
</script>

<style scoped>
.menu-bar {
  display: flex;
  gap: 1px;
  background: var(--bg-card);
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-color);
}

.menu-item {
  position: relative;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 150px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 4px;
  z-index: 100;
}

.menu-option {
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
}

.menu-option:hover {
  background: var(--bg-hover);
}

.menu-separator {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}
</style>