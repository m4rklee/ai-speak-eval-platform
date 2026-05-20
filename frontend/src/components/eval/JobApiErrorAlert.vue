<template>
  <a-alert
    v-if="visible"
    :type="alertType"
    show-icon
    class="job-api-error-alert"
  >
    <template #message>{{ title }}</template>
    <template #description>
      <div v-if="lastApiError" class="job-api-error-alert__msg">{{ lastApiError }}</div>
      <div v-if="apiErrorCount != null && apiErrorCount > 0" class="job-api-error-alert__count">
        累计 API/评测错误 {{ apiErrorCount }} 条
      </div>
    </template>
  </a-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvalJobApiErrorFields } from '@/types/evalJobCommon'

const props = defineProps<{
  job?: EvalJobApiErrorFields | null
}>()

const apiErrorCount = computed(() => props.job?.apiErrorCount ?? 0)
const lastApiError = computed(() => props.job?.lastApiError?.trim() || '')

const visible = computed(
  () => apiErrorCount.value > 0 || !!lastApiError.value,
)

const alertType = computed(() => (apiErrorCount.value >= 3 ? 'error' : 'warning'))

const title = computed(() =>
  apiErrorCount.value >= 3 ? 'API 错误较多，请检查配置或稍后重试' : '部分样本 API 调用失败',
)
</script>

<style scoped>
.job-api-error-alert {
  margin-bottom: 12px;
}
.job-api-error-alert__msg {
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 4px;
}
.job-api-error-alert__count {
  color: rgba(0, 0, 0, 0.45);
  font-size: 12px;
}
</style>
