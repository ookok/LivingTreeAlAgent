<template>
  <div class="grid" :style="{ gridTemplateColumns: columns }">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  columns: {
    type: String,
    default: '1fr'
  }
});
</script>

<style scoped>
.grid {
  display: grid;
  gap: 16px;
}
</style>