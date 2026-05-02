<template>
  <div class="map" :style="{ height: height }">
    <div class="map-placeholder">
      Map Component ({{ lat }}, {{ lng }})
    </div>
  </div>
</template>

<script setup>
defineProps({
  lat: Number,
  lng: Number,
  height: {
    type: String,
    default: '300px'
  }
});
</script>

<style scoped>
.map {
  border: 1px solid #ccc;
  border-radius: 4px;
}
.map-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background-color: #f0f0f0;
}
</style>