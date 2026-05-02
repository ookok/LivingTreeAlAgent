<template>
  <form :id="id" class="form" @submit.prevent="handleSubmit">
    <slot />
    <button type="submit" class="submit-btn">Submit</button>
  </form>
</template>

<script setup>
const props = defineProps({
  id: String
});

const emit = defineEmits(['submit']);

function handleSubmit() {
  emit('submit');
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.submit-btn {
  align-self: flex-end;
  padding: 8px 16px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style>