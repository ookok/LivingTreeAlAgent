<template>
  <input
    type="date"
    :id="id"
    :value="modelValue"
    class="date-picker"
    @input="$emit('update:modelValue', $event.target.value)"
  />
</template>

<script setup>
defineProps({
  id: String,
  modelValue: String
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.date-picker {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>