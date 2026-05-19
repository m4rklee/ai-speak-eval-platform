<template>
  <div class="tqdm-wrap">
    <div class="tqdm-line">{{ detail?.tqdmLine || fallbackLine }}</div>
    <a-progress
      :percent="percent"
      :status="status"
      :stroke-color="{ from: '#108ee9', to: '#87d068' }"
      :show-info="true"
    />
    <div class="tqdm-meta">
      <span v-if="detail?.elapsedText">已用 {{ detail.elapsedText }}</span>
      <span v-if="detail?.etaText && isRunning">剩余约 {{ detail.etaText }}</span>
      <span v-if="detail?.ratePerSec">({{ detail.ratePerSec.toFixed(2) }} 步/秒)</span>
      <span v-if="detail?.message" class="tqdm-msg">{{ detail.message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { UnifiedEvalProgressDetail } from '@/api/unifiedEvalController'

const props = defineProps<{
  percent: number
  detail?: UnifiedEvalProgressDetail | null
  jobStatus?: string
}>()

const isRunning = computed(() =>
  ['pending', 'running'].includes(props.jobStatus || ''),
)

const status = computed(() => {
  if (props.jobStatus === 'failed') return 'exception'
  if (props.jobStatus === 'completed') return 'success'
  return 'active'
})

const fallbackLine = computed(() => {
  const p = props.percent
  return `评测中… ${p}%`
})
</script>

<style scoped>
.tqdm-wrap {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tqdm-line {
  font-size: 13px;
  color: #262626;
  margin-bottom: 8px;
  word-break: break-all;
}

.tqdm-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

.tqdm-msg {
  color: #1890ff;
}
</style>
