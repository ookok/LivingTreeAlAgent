<template>
  <Teleport to="body">
    <div v-if="visible" class="dialog-overlay">
      <div class="dialog">
        <div class="dialog-header">
          <h3>{{ title }}</h3>
          <button class="close-btn" @click="$emit('update:visible', false)">×</button>
        </div>
        <div class="dialog-content">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: Boolean,
  title: String
});

defineEmits(['update:visible']);
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}
.dialog {
  background-color: white;
  border-radius: 8px;
  width: 90%;
  max-width: 400px;
}
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #ccc;
}
.close-btn {
  font-size: 24px;
  border: none;
  background: none;
  cursor: pointer;
}
.dialog-content {
  padding: 16px;
}
</style>