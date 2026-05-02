<template>
  <div class="slider-container">
    <input
      type="range"
      :min="min"
      :max="max"
      :step="step"
      :value="modelValue"
      class="slider"
      @input="$emit('update:modelValue', Number($event.target.value))"
    />
    <span class="slider-value">{{ modelValue }}</span>
  </div>
</template>

<script setup>
defineProps({
  modelValue: {
    type: Number,
    default: 0
  },
  min: {
    type: Number,
    default: 0
  },
  max: {
    type: Number,
    default: 100
  },
  step: {
    type: Number,
    default: 1
  }
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.slider-container {
  display: flex;
  align-items: center;
  gap: 12px;
}
.slider {
  flex: 1;
}
.slider-value {
  min-width: 40px;
  text-align: right;
}
</style>