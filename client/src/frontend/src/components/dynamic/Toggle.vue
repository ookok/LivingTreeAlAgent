<template>
  <button
    type="button"
    :class="['toggle', { active: modelValue }]"
    @click="$emit('update:modelValue', !modelValue)"
  >
    <span>{{ modelValue ? 'ON' : 'OFF' }}</span>
  </button>
</template>

<script setup>
defineProps({
  modelValue: Boolean
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.toggle {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
}
.toggle.active {
  background-color: #42b983;
  color: white;
}
</style>