<template>
  <textarea
    :id="id"
    :value="modelValue"
    :placeholder="placeholder"
    :rows="rows || 4"
    class="text-area"
    @input="$emit('update:modelValue', $event.target.value)"
  />
</template>

<script setup>
defineProps({
  id: String,
  modelValue: String,
  placeholder: String,
  rows: Number
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.text-area {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  resize: vertical;
}
</style>