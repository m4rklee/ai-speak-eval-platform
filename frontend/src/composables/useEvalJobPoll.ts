import { message } from 'ant-design-vue'

type TerminalJob = {
  status: string
  error?: string
}

export function useEvalJobPoll(options: {
  onRefreshRecent?: () => void | Promise<void>
  completedMessage?: string
}) {
  function handlePollTerminal(job: TerminalJob) {
    if (options.onRefreshRecent) {
      void options.onRefreshRecent()
    }
    if (job.status === 'completed') {
      if (options.completedMessage) {
        message.success(options.completedMessage)
      }
    } else if (job.status === 'failed') {
      message.error(job.error || '任务失败')
    }
  }

  function handlePollCatch(err?: unknown) {
    message.error(err instanceof Error ? err.message : '网络错误，无法获取任务状态')
  }

  return { handlePollTerminal, handlePollCatch }
}
