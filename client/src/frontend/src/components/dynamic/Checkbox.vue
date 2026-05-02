<template>
  <label class="checkbox-label">
    <input
      type="checkbox"
      :id="id"
      :checked="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <span>{{ label }}</span>
  </label>
</template>

<script setup>
defineProps({
  id: String,
  modelValue: Boolean,
  label: String,
  disabled: Boolean
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>