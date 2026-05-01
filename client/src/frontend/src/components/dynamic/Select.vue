<template>
  <div class="select-component">
    <label v-if="label">{{ label }}<span v-if="required" class="required">*</span></label>
    <select
      :value="modelValue"
      :disabled="disabled"
      :required="required"
      @change="$emit('update:modelValue', $event.target.value)"
      class="select"
    >
      <option value="">请选择</option>
      <option
        v-for="option in options"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>
  </div>
</template>

<script setup>
defineProps({
  id: String,
  label: String,
  modelValue: {
    type: String,
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  required: Boolean,
  disabled: Boolean
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.select-component {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.select-component label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.select {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  background: white;
  cursor: pointer;
  transition: border-color 0.2s;
}

.select:focus {
  outline: none;
  border-color: #3b82f6;
}

.select:disabled {
  background: #f3f4f6;
  color: #9ca3af;
}
</style>