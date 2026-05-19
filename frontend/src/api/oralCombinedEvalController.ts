import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type OralCombinedHealth = {
  pathsOk: boolean
  pathsMessage: string
  daemonRunning: boolean
  daemonReady: boolean
  questionDirOk: boolean
  questionDirMessage: string
  questionCount: number
  judgeModel: string
  maxFilesPerJob: number
  engine: string
}

export type OralCombinedProgressDetail = {
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

export type OralCombinedSpeechSide = {
  status: string
  accuracy?: number
  fluency?: number
  naturalness?: number
  apgMos?: { bvcc?: number; somos?: number }
  transcriptS?: string
  transcriptW?: string
  reason?: string
  error?: string
}

export type OralCombinedContentSide = {
  status: string
  questionId?: string
  question?: string
  grammarScore?: number
  themeFocusScore?: number
  answerClarityScore?: number
  compositeScore?: number
  reason?: string
  error?: string
}

export type OralCombinedPerFile = {
  stem: string
  wavName: string
  txtName: string
  status: string
  speech?: OralCombinedSpeechSide
  content?: OralCombinedContentSide
}

export type OralCombinedSummary = {
  pairCount?: number
  okCount?: number
  partialCount?: number
  errorCount?: number
  accuracyMean?: number
  fluencyMean?: number
  naturalnessMean?: number
  apgMosBvccMean?: number
  apgMosSomosMean?: number
  grammarMean?: number
  themeFocusMean?: number
  answerClarityMean?: number
  compositeMean?: number
}

export type OralCombinedJob = {
  jobId: string
  status: string
  progress: number
  totalFiles: number
  error?: string
  summary?: OralCombinedSummary
  perFile?: OralCombinedPerFile[]
  createdAt?: string
  finishedAt?: string
  progressDetail?: OralCombinedProgressDetail
  audioAvailable?: boolean
}

function unwrap<T>(res: { data: BaseResponse<T> }): T {
  const body = res.data
  if (body.code !== 0) {
    throw new Error(body.message || '请求失败')
  }
  return body.data as T
}

export async function getOralCombinedHealth() {
  const res = await request.get<BaseResponse<OralCombinedHealth>>('/oral-combined/health')
  return unwrap(res)
}

export async function createOralCombinedJob(files: File[], archive?: File) {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  if (archive) {
    form.append('archive', archive)
  }
  const res = await request.post<BaseResponse<string>>('/oral-combined/jobs', form, {
    timeout: 120000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function getOralCombinedJob(jobId: string) {
  const res = await request.get<BaseResponse<OralCombinedJob>>(`/oral-combined/jobs/${jobId}`)
  return unwrap(res)
}

export async function listOralCombinedJobs() {
  const res = await request.get<BaseResponse<{ jobs: OralCombinedJob[] }>>('/oral-combined/jobs')
  return unwrap(res)
}

export function getOralCombinedAudioUrl(jobId: string, wavname: string) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  return `${base}/oral-combined/jobs/${encodeURIComponent(jobId)}/audio/${encodeURIComponent(wavname)}`
}
