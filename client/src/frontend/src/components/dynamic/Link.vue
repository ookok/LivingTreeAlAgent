<template>
  <a
    :href="href"
    :target="target"
    class="link"
  >
    <slot />
  </a>
</template>

<script setup>
defineProps({
  href: String,
  target: {
    type: String,
    default: '_self'
  }
});
</script>

<style scoped>
.link {
  color: #42b983;
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}
</style>