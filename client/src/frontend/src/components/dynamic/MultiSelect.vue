<template>
  <select
    :id="id"
    multiple
    class="multi-select"
    @change="handleChange"
  >
    <option
      v-for="option in options"
      :key="option.value"
      :value="option.value"
      :selected="modelValue?.includes(option.value)"
    >
      {{ option.label }}
    </option>
  </select>
</template>

<script setup>
const props = defineProps({
  id: String,
  modelValue: Array,
  options: Array
});

const emit = defineEmits(['update:modelValue']);

function handleChange(event) {
  const selected = Array.from(event.target.selectedOptions).map(opt => opt.value);
  emit('update:modelValue', selected);
}
</script>

<style scoped>
.multi-select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>