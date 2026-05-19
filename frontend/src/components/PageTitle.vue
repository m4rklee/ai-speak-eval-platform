<template>
  <h1 class="page-title-with-icon">
    <span
      class="page-title-icon"
      :style="{ color: meta.color, background: meta.bg }"
      aria-hidden="true"
    >
      <component :is="meta.icon" />
    </span>
    <span class="page-title-text">{{ title }}</span>
  </h1>
  <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PAGE_ICON_META, type PageIconKey } from '@/constants/pageIcons'

const props = defineProps<{
  iconKey: PageIconKey
  title: string
  subtitle?: string
}>()

const meta = computed(() => PAGE_ICON_META[props.iconKey])
</script>
