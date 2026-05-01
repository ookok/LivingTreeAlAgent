<template>
  <div class="chat-layout">
    <Sidebar />
    <div class="chat-main">
      <ChatHeader />
      <ChatArea />
    </div>
  </div>
</template>

<script setup>
import Sidebar from './Sidebar.vue'
import ChatHeader from './ChatHeader.vue'
import ChatArea from './ChatArea.vue'
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>