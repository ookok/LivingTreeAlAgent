<template>
  <div class="column" :style="{ flex: flex }">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  flex: {
    type: [Number, String],
    default: 1
  }
});
</script>

<style scoped>
.column {
  display: flex;
  flex-direction: column;
}
</style>