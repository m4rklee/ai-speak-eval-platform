<template>
  <a-alert
    v-if="visible"
    :type="alertType"
    show-icon
    class="job-interrupted-banner"
  >
    <template #message>{{ title }}</template>
    <template #description>
      <div class="job-interrupted-banner__desc">{{ description }}</div>
      <a-button
        v-if="canResume"
        type="primary"
        size="small"
        :loading="loading"
        class="job-interrupted-banner__btn"
        @click="emit('resume')"
      >
        {{ resumeLabel }}
      </a-button>
    </template>
  </a-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type JobResumeBannerStatus = {
  status: string
  progress?: number
  completedCount?: number
  totalCount?: number
  totalSamples?: number
  totalFiles?: number
  hasCheckpoint?: boolean
  canResume?: boolean
}

const props = withDefaults(
  defineProps<{
    job?: JobResumeBannerStatus | null
    loading?: boolean
    resumeLabel?: string
  }>(),
  {
    job: null,
    loading: false,
    resumeLabel: '续跑',
  },
)

const emit = defineEmits<{
  resume: []
}>()

const visible = computed(() => {
  const s = props.job?.status
  return s === 'interrupted' || s === 'awaiting_eval'
})

const alertType = computed(() =>
  props.job?.status === 'awaiting_eval' ? 'info' : 'warning',
)

const title = computed(() => {
  if (props.job?.status === 'awaiting_eval') return '待确认评测'
  return '任务已中断'
})

const total = computed(() => {
  const j = props.job
  if (!j) return 0
  return j.totalCount ?? j.totalSamples ?? j.totalFiles ?? 0
})

const completed = computed(() => {
  const j = props.job
  if (!j) return 0
  if (j.completedCount != null) return j.completedCount
  if (total.value > 0 && j.progress != null) {
    return Math.round((j.progress / 100) * total.value)
  }
  return 0
})

const canResume = computed(() => props.job?.canResume !== false)

const description = computed(() => {
  const j = props.job
  if (!j) return ''
  const t = total.value
  const c = completed.value
  if (j.status === 'awaiting_eval') {
    return t > 0
      ? `回复生成已完成 ${c}/${t}，请点击续跑开始综合评测。`
      : '回复生成已完成，请点击续跑开始综合评测。'
  }
  if (t > 0) {
    const base = `已完成 ${c} / ${t}。`
    if (j.hasCheckpoint === false && c === 0 && (j.progress ?? 0) > 0) {
      return `${base}无断点数据（历史任务），续跑将从头补跑剩余项。`
    }
    if (j.hasCheckpoint === false && c === 0) {
      return `${base}无已保存进度，续跑将从第一项开始。`
    }
    return `${base}服务重启后任务已暂停，可手动续跑。`
  }
  return '服务重启后任务已暂停，可手动续跑。'
})
</script>

<style scoped>
.job-interrupted-banner {
  margin-bottom: 12px;
}
.job-interrupted-banner__desc {
  margin-bottom: 8px;
}
.job-interrupted-banner__btn {
  margin-top: 4px;
}
</style>
