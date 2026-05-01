<template>
  <p :class="textClass" v-html="content"></p>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  id: String,
  content: String,
  style: Object
});

const textClass = computed(() => ({
  'text-small': props.style?.size === 'small',
  'text-large': props.style?.size === 'large',
  'text-muted': props.style?.muted
}));
</script>

<style scoped>
p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #4b5563;
}

.text-small {
  font-size: 12px;
}

.text-large {
  font-size: 16px;
}

.text-muted {
  color: #9ca3af;
}
</style>