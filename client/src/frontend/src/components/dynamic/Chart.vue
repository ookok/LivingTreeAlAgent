<template>
  <div class="chart" :style="{ height: height }">
    <svg v-if="type === 'bar'" viewBox="0 0 400 200">
      <rect
        v-for="(value, index) in data"
        :key="index"
        :x="index * 40 + 40"
        :y="200 - value * 2"
        :width="30"
        :height="value * 2"
        fill="#42b983"
      />
    </svg>
    <div v-else class="chart-placeholder">
      Chart: {{ type }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  type: String,
  data: Array,
  height: {
    type: String,
    default: '200px'
  }
});
</script>

<style scoped>
.chart {
  border: 1px solid #ccc;
  border-radius: 4px;
}
.chart-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>