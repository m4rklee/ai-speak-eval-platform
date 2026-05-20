import { ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import type { EvalJobRuntimeOptions } from '@/types/evalJobCommon'

export function useEvalJobControls(options: {
  jobId: Ref<string | null | undefined>
  resumeJob: (id: string, opts?: EvalJobRuntimeOptions) => Promise<unknown>
  pauseJob: (id: string) => Promise<unknown>
  rerunJob: (id: string, opts?: EvalJobRuntimeOptions) => Promise<unknown>
  startPolling: (id: string) => void
  pollJob?: (id: string) => Promise<void>
  onRefreshRecent?: () => void
  onResumeSuccess?: () => void | Promise<void>
  resumePausedMessage?: string
  getResumeMessage?: () => string
  getRuntimeOptions?: () => EvalJobRuntimeOptions
}) {
  const pauseLoading = ref(false)
  const rerunLoading = ref(false)
  const resumeLoading = ref(false)

  function runtimePayload(extra?: EvalJobRuntimeOptions): EvalJobRuntimeOptions {
    return { ...(options.getRuntimeOptions?.() ?? {}), ...extra }
  }

  async function handlePause() {
    if (!options.jobId.value) return
    pauseLoading.value = true
    try {
      await options.pauseJob(options.jobId.value)
      message.success('已请求暂停，当前样本完成后生效')
      if (options.pollJob) {
        await options.pollJob(options.jobId.value)
      }
      options.onRefreshRecent?.()
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '暂停失败')
    } finally {
      pauseLoading.value = false
    }
  }

  async function handleRerun(rerunOpts?: EvalJobRuntimeOptions) {
    if (!options.jobId.value) return
    rerunLoading.value = true
    try {
      await options.rerunJob(options.jobId.value, runtimePayload(rerunOpts))
      message.success(rerunOpts?.skipCompleted ? '已开始续跑剩余题目' : '已开始重跑')
      options.onRefreshRecent?.()
      options.startPolling(options.jobId.value)
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '重跑失败')
    } finally {
      rerunLoading.value = false
    }
  }

  async function handleResume() {
    if (!options.jobId.value) return
    resumeLoading.value = true
    try {
      await options.resumeJob(options.jobId.value, runtimePayload())
      message.success(
        options.getResumeMessage?.() || options.resumePausedMessage || '已开始续跑',
      )
      await options.onResumeSuccess?.()
      options.onRefreshRecent?.()
      options.startPolling(options.jobId.value)
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '续跑失败')
    } finally {
      resumeLoading.value = false
    }
  }

  return {
    pauseLoading,
    rerunLoading,
    resumeLoading,
    handlePause,
    handleRerun,
    handleResume,
  }
}
