<template>
  <svg
    class="app-logo"
    :width="size"
    :height="size"
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="app-logo-bg" x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse">
        <stop stop-color="#1677ff" />
        <stop offset="1" stop-color="#4096ff" />
      </linearGradient>
      <linearGradient id="app-logo-accent" x1="20" y1="10" x2="32" y2="30" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ffffff" stop-opacity="0.95" />
        <stop offset="1" stop-color="#ffffff" stop-opacity="0.75" />
      </linearGradient>
    </defs>
    <rect width="40" height="40" rx="10" fill="url(#app-logo-bg)" />
    <!-- 声波条 -->
    <rect x="9" y="15" width="3" height="10" rx="1.5" fill="url(#app-logo-accent)" />
    <rect x="14" y="11" width="3" height="18" rx="1.5" fill="url(#app-logo-accent)" />
    <rect x="19" y="13" width="3" height="14" rx="1.5" fill="url(#app-logo-accent)" />
    <rect x="24" y="9" width="3" height="22" rx="1.5" fill="url(#app-logo-accent)" />
    <!-- 评测勾选 -->
    <path
      d="M27.5 27.5L30.2 30.2L34.5 25"
      stroke="#fff"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 36 },
)
</script>

<style scoped>
.app-logo {
  display: block;
  flex-shrink: 0;
  filter: drop-shadow(0 1px 2px rgba(22, 119, 255, 0.2));
}
</style>
