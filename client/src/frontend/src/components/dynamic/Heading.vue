<template>
  <heading :level="level" class="heading">
    {{ content }}
  </heading>
</template>

<script setup>
import { computed, h } from 'vue';

const props = defineProps({
  id: String,
  content: String,
  level: {
    type: Number,
    default: 2
  }
});

const heading = computed(() => {
  const levels = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  return levels[Math.min(props.level - 1, 5)];
});
</script>

<style scoped>
.heading {
  margin: 0;
  font-weight: 600;
  color: #1f2937;
}

:deep(h1) { font-size: 24px; }
:deep(h2) { font-size: 20px; }
:deep(h3) { font-size: 18px; }
:deep(h4) { font-size: 16px; }
:deep(h5) { font-size: 14px; }
:deep(h6) { font-size: 13px; }
</style>