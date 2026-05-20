import { onBeforeUnmount, watch, type Ref } from 'vue'

const ACTIVE_STATUSES = new Set(['pending', 'running', 'generating'])

export function useEvalRecentJobsPoll(
  jobs: Ref<Array<{ status: string }>>,
  loadRecentJobs: () => void | Promise<void>,
) {
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function hasActiveJobs() {
    return jobs.value.some((j) => ACTIVE_STATUSES.has(j.status))
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startPoll() {
    if (pollTimer) return
    pollTimer = setInterval(() => {
      void loadRecentJobs()
    }, 3000)
  }

  function syncPoll() {
    if (hasActiveJobs()) startPoll()
    else stopPoll()
  }

  watch(jobs, syncPoll, { deep: true, immediate: true })

  onBeforeUnmount(stopPoll)

  return { syncPoll, stopPoll }
}
