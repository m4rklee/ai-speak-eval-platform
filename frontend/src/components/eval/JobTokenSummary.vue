<template>
  <div v-if="hasData" class="job-token-summary">
    <a-space wrap :size="16">
      <span v-if="totalInputTokens != null">
        输入 Token：<strong>{{ formatNum(totalInputTokens) }}</strong>
      </span>
      <span v-if="totalOutputTokens != null">
        输出 Token：<strong>{{ formatNum(totalOutputTokens) }}</strong>
      </span>
      <span>
        估算费用：<strong>{{ costLabel }}</strong>
      </span>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvalJobTokenFields } from '@/types/evalJobCommon'

const props = defineProps<{
  job?: EvalJobTokenFields | null
}>()

const totalInputTokens = computed(() => props.job?.totalInputTokens)
const totalOutputTokens = computed(() => props.job?.totalOutputTokens)

const hasData = computed(() => {
  const tin = totalInputTokens.value ?? 0
  const tout = totalOutputTokens.value ?? 0
  return tin > 0 || tout > 0 || props.job?.estimatedCostUsd != null
})

const costLabel = computed(() => {
  const cost = props.job?.estimatedCostUsd
  if (cost == null) return '暂无定价'
  if (cost === 0) return '$0.00'
  return `约 $${cost.toFixed(4)}`
})

function formatNum(n: number) {
  return n.toLocaleString()
}
</script>

<style scoped>
.job-token-summary {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 6px;
  font-size: 13px;
  color: #595959;
}
</style>
