<template>
  <img
    :src="src"
    :alt="alt"
    :width="width"
    :height="height"
    class="image"
  />
</template>

<script setup>
defineProps({
  src: String,
  alt: String,
  width: [Number, String],
  height: [Number, String]
});
</script>

<style scoped>
.image {
  max-width: 100%;
  height: auto;
}
</style>