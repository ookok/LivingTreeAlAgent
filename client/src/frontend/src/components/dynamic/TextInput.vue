<template>
  <div class="text-input-component">
    <label v-if="label">{{ label }}<span v-if="required" class="required">*</span></label>
    <input
      type="text"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :required="required"
      @input="$emit('update:modelValue', $event.target.value)"
      @change="$emit('change', $event)"
      class="text-input"
    />
    <span v-if="error" class="error">{{ error }}</span>
  </div>
</template>

<script setup>
defineProps({
  id: String,
  label: String,
  placeholder: String,
  modelValue: {
    type: String,
    default: ''
  },
  required: Boolean,
  disabled: Boolean,
  error: String,
  validation: Object
});

defineEmits(['update:modelValue', 'change']);
</script>

<style scoped>
.text-input-component {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.text-input-component label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.text-input {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.text-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.text-input:disabled {
  background: #f3f4f6;
  color: #9ca3af;
}

.error {
  font-size: 12px;
  color: #ef4444;
}
</style>