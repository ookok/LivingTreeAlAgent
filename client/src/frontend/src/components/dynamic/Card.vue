<template>
  <div class="card">
    <slot />
  </div>
</template>

<script setup>
</script>

<style scoped>
.card {
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>