<template>
  <a-space v-if="visible" class="job-progress-actions" :size="8">
    <a-button
      v-if="showPause"
      size="small"
      :loading="pauseLoading"
      @click="emit('pause')"
    >
      暂停
    </a-button>
    <a-button
      v-if="showContinue"
      type="primary"
      size="small"
      :loading="resumeLoading"
      @click="emit('resume')"
    >
      继续
    </a-button>
    <a-button
      v-if="showRerun"
      size="small"
      danger
      :loading="rerunLoading"
      @click="onRerunClick"
    >
      重跑
    </a-button>
  </a-space>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Modal } from 'ant-design-vue'
import type { EvalJobControlFields } from '@/types/evalJobCommon'

const props = defineProps<{
  job?: ({ status: string; completedCount?: number; hasCheckpoint?: boolean } & EvalJobControlFields) | null
  pauseLoading?: boolean
  resumeLoading?: boolean
  rerunLoading?: boolean
}>()

const emit = defineEmits<{
  pause: []
  resume: []
  rerun: [options?: { skipCompleted?: boolean }]
}>()

const status = computed(() => props.job?.status || '')

const showPause = computed(() => {
  if (status.value === 'paused') return false
  if (props.job?.canPause != null) return props.job.canPause
  return ['pending', 'running', 'generating'].includes(status.value)
})

const showContinue = computed(() => status.value === 'paused')

const showRerun = computed(() => {
  if (['pending', 'running', 'generating'].includes(status.value)) return false
  if (props.job?.canRerun != null) return props.job.canRerun
  return ['paused', 'interrupted', 'failed', 'completed', 'awaiting_eval'].includes(status.value)
})

const visible = computed(() => showPause.value || showContinue.value || showRerun.value)

const hasPartialProgress = computed(() => {
  const count = props.job?.completedCount ?? 0
  return count > 0 || Boolean(props.job?.hasCheckpoint)
})

function onRerunClick() {
  const s = status.value
  if (s === 'paused') {
    Modal.confirm({
      title: '确认从头重跑',
      content:
        '将清空当前进度与结果，使用高级选项中的 workers / 请求间隔从头开始。若只想接着跑，请点「继续」。',
      okText: '从头重跑',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => emit('rerun', { skipCompleted: false }),
    })
    return
  }

  if (hasPartialProgress.value) {
    Modal.confirm({
      title: '重跑方式',
      content:
        '保留已完成题目的结果，只跑尚未完成的题目？（会使用高级选项中的 workers / 请求间隔）',
      okText: '保留，仅跑剩余',
      cancelText: '不保留，全部重测',
      maskClosable: false,
      closable: false,
      onOk: () => emit('rerun', { skipCompleted: true }),
      onCancel: () => emit('rerun', { skipCompleted: false }),
    })
    return
  }

  Modal.confirm({
    title: '确认重跑',
    content: '将清空当前进度与结果，使用相同参数从头开始。是否继续？',
    okText: '重跑',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => emit('rerun', { skipCompleted: false }),
  })
}
</script>

<style scoped>
.job-progress-actions {
  flex-wrap: wrap;
}
</style>
