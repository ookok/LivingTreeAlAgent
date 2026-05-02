<template>
  <div class="radio-group">
    <label
      v-for="option in options"
      :key="option.value"
      class="radio-label"
    >
      <input
        type="radio"
        :name="name || id"
        :value="option.value"
        :checked="modelValue === option.value"
        @change="$emit('update:modelValue', option.value)"
      />
      <span>{{ option.label }}</span>
    </label>
  </div>
</template>

<script setup>
defineProps({
  id: String,
  name: String,
  modelValue: [String, Number],
  options: Array
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>