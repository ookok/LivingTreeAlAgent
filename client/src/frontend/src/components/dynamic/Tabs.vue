<template>
  <div class="tabs">
    <div class="tabs-header">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-button', { active: activeTab === tab.id }]"
        @click="$emit('update:activeTab', tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="tabs-content">
      <slot :activeTab="activeTab" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  tabs: Array,
  activeTab: String
});

defineEmits(['update:activeTab']);
</script>

<style scoped>
.tabs-header {
  display: flex;
  border-bottom: 1px solid #ccc;
}
.tab-button {
  padding: 8px 16px;
  border: none;
  background: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.tab-button.active {
  border-bottom-color: #42b983;
}
.tabs-content {
  padding: 16px 0;
}
</style>