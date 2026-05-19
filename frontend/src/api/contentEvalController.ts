import request from '@/request'

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

export type ContentEvalJob = {
  jobId: string
  status: string
  progress: number
  totalFiles: number
  error?: string
  progressDetail?: ContentEvalProgressDetail
  summary?: ContentEvalJobSummary
  perFile?: Array<Record<string, unknown>>
  result?: Record<string, unknown>
  createdAt?: string
  finishedAt?: string
}

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

export async function createContentEvalJob(files: File[], archive?: File) {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  if (archive) {
    form.append('archive', archive)
  }
  const res = await request.post<BaseResponse<string>>('/content-eval/jobs', form, {
    timeout: 120000,
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
