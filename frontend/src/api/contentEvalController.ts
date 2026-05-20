import request from '@/request'
import type { ModelEvalSlot } from '@/api/unifiedEvalController'
import type { EvalJobCommonFields, EvalJobCreateMeta } from '@/types/evalJobCommon'
import { appendCreateMeta, updateEvalJobDisplayName, pauseEvalJob, rerunEvalJob } from '@/api/evalJobApiHelpers'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type ContentEvalHealth = {
  questionDirOk: boolean
  questionDirMessage: string
  questionCount: number
  questionDir: string
  judgeModel: string
  maxFilesPerJob: number
}

export type ContentEvalSingleResult = {
  status: string
  fileName: string
  questionId: string
  question: string
  answer?: string
  grammarScore?: number
  themeFocusScore?: number
  answerClarityScore?: number
  compositeScore?: number
  reason?: string
  dimensions?: Record<string, unknown>
  error?: string
}

export type ContentEvalProgressDetail = {
  phase?: string
  phaseLabel?: string
  current?: number
  total?: number
  elapsedSec?: number
  etaSec?: number
  elapsedText?: string
  etaText?: string
  ratePerSec?: number
  message?: string
  tqdmLine?: string
}

export type ContentEvalJobSummary = {
  fileCount?: number
  okCount?: number
  grammarMean?: number
  themeFocusMean?: number
  answerClarityMean?: number
  compositeMean?: number
  dimensions?: Array<{ dimNameCn: string; dimNameEn: string; score: number }>
}

export type ContentEvalModelComparison = {
  modelName: string
  fileCount?: number
  grammarMean?: number
  themeFocusMean?: number
  answerClarityMean?: number
  compositeMean?: number
}

export type ContentEvalModelResult = {
  modelName: string
  summary?: ContentEvalJobSummary
  perFile?: Array<Record<string, unknown>>
}

export type ContentEvalJob = {
  jobId: string
  jobType?: 'single' | 'multi_model'
  status: string
  progress: number
  totalFiles: number
  modelCount?: number
  error?: string
  progressDetail?: ContentEvalProgressDetail
  summary?: ContentEvalJobSummary
  perFile?: Array<Record<string, unknown>>
  models?: ContentEvalModelResult[]
  comparison?: { byModel?: ContentEvalModelComparison[] }
  result?: Record<string, unknown>
  createdAt?: string
  finishedAt?: string
  completedCount?: number
  totalCount?: number
  canResume?: boolean
  interruptedAt?: string
  hasCheckpoint?: boolean
} & EvalJobCommonFields

function unwrap<T>(res: { data: BaseResponse<T> }): T {
  const body = res.data
  if (body.code !== 0) {
    throw new Error(body.message || '请求失败')
  }
  return body.data as T
}

export async function getContentEvalHealth() {
  const res = await request.get<BaseResponse<ContentEvalHealth>>('/content-eval/health')
  return unwrap(res)
}

export async function listContentEvalQuestions(q?: string) {
  const res = await request.get<BaseResponse<{ ids: string[]; count: number }>>('/content-eval/questions', {
    params: q ? { q } : undefined,
  })
  return unwrap(res)
}

export async function getContentEvalQuestion(questionId: string) {
  const res = await request.get<BaseResponse<{ questionId: string; question: string }>>(
    `/content-eval/questions/${encodeURIComponent(questionId)}`,
  )
  return unwrap(res)
}

export async function evaluateContentSingle(params: {
  questionId?: string
  answer?: string
  file?: File
}) {
  const form = new FormData()
  if (params.questionId) form.append('question_id', params.questionId)
  if (params.answer) form.append('answer', params.answer)
  if (params.file) form.append('file', params.file)
  const res = await request.post<BaseResponse<ContentEvalSingleResult>>('/content-eval/evaluate', form, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function createContentEvalJob(
  files: File[],
  archive?: File,
  meta?: EvalJobCreateMeta,
) {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  if (archive) {
    form.append('archive', archive)
  }
  appendCreateMeta(form, meta)
  const res = await request.post<BaseResponse<string>>('/content-eval/jobs', form, {
    timeout: 120000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function createContentMultiModelJob(slots: ModelEvalSlot[], meta?: EvalJobCreateMeta) {
  const form = new FormData()
  for (const slot of slots) {
    form.append('modelNames', slot.modelName.trim())
  }
  slots.forEach((slot, idx) => {
    if (slot.zipFile) {
      form.append(`archive_${idx}`, slot.zipFile)
    } else {
      const allFiles = slot.files.length ? slot.files : slot.dirFiles
      for (const f of allFiles) {
        form.append(`files_${idx}`, f)
      }
    }
  })
  appendCreateMeta(form, meta)
  const res = await request.post<BaseResponse<string>>('/content-eval/multi-model-jobs', form, {
    timeout: 300000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function getContentEvalJob(jobId: string) {
  const res = await request.get<BaseResponse<ContentEvalJob>>(`/content-eval/jobs/${jobId}`)
  return unwrap(res)
}

export async function listContentEvalJobs() {
  const res = await request.get<BaseResponse<{ jobs: ContentEvalJob[] }>>('/content-eval/jobs')
  return unwrap(res)
}

export async function resumeContentEvalJob(jobId: string) {
  const res = await request.post<BaseResponse<null>>(`/content-eval/jobs/${jobId}/resume`)
  return unwrap(res)
}

export async function updateContentEvalJobDisplayName(jobId: string, displayName: string) {
  return updateEvalJobDisplayName('content-eval', jobId, displayName)
}

export async function pauseContentEvalJob(jobId: string) {
  return pauseEvalJob('content-eval', jobId)
}

export async function rerunContentEvalJob(jobId: string) {
  return rerunEvalJob('content-eval', jobId)
}
