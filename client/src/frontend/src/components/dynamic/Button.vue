<template>
  <button
    :class="buttonClass"
    :disabled="disabled"
    @click="$emit('click', $event)"
    class="btn"
  >
    {{ label }}
  </button>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  id: String,
  label: {
    type: String,
    default: '按钮'
  },
  variant: {
    type: String,
    default: 'default'
  },
  disabled: Boolean
});

defineEmits(['click']);

const buttonClass = computed(() => ({
  'btn-primary': props.variant === 'primary',
  'btn-secondary': props.variant === 'secondary',
  'btn-default': props.variant === 'default',
  'btn-disabled': props.disabled
}));
</script>

<style scoped>
.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
}

.btn-primary:hover:not(.btn-disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
}

.btn-secondary:hover:not(.btn-disabled) {
  background: #d1d5db;
}

.btn-default {
  background: #6b7280;
  color: white;
}

.btn-default:hover:not(.btn-disabled) {
  background: #4b5563;
}

.btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>