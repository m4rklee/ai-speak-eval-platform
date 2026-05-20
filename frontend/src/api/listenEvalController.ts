import request from '@/request'
import type { EvalJobCommonFields, EvalJobCreateMeta, EvalJobRuntimeOptions } from '@/types/evalJobCommon'
import { updateEvalJobDisplayName, pauseEvalJob, rerunEvalJob } from '@/api/evalJobApiHelpers'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type ListenEvalHealth = {
  packageDirOk: boolean
  packageDir: string
  benchmarkOk: boolean
  benchmarkPath: string
  questionCount: number
  audioDirOk: boolean
  audioDir: string
  audioFileCount: number
  openrouterConfigured: boolean
  aihubmixConfigured: boolean
  apiConfigured: boolean
  ready: boolean
  message: string
  maxSamplesPerJob: number
}

export type ListenEvalProgressDetail = {
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

export type ListenEvalSummary = {
  overall?: {
    correct?: number
    total?: number
    accuracy?: number
    invalid_response?: number
    missing_answer?: number
  }
  byDimension?: Record<string, { correct: number; total: number; accuracy: number }>
  bySourceBenchmark?: Record<string, { correct: number; total: number; accuracy: number }>
  bySourceDataset?: Record<string, { correct: number; total: number; accuracy: number }>
}

export type ListenEvalPerRow = {
  id: string
  question?: string
  choiceA?: string
  choiceB?: string
  choiceC?: string
  choiceD?: string
  choiceE?: string
  dimension?: string
  sourceDataset?: string
  prediction?: string
  answerLabel?: string
  isCorrect?: boolean | null
  response?: string
  error?: string
}

export type ListenEvalJob = {
  jobId: string
  status: string
  progress: number
  totalSamples: number
  model?: string
  sampleMode?: string
  workers?: number
  requestInterval?: number
  error?: string
  progressDetail?: ListenEvalProgressDetail
  summary?: ListenEvalSummary
  perFile?: ListenEvalPerRow[]
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

export async function getListenEvalHealth() {
  const res = await request.get<BaseResponse<ListenEvalHealth>>('/listen-eval/health')
  return unwrap(res)
}

export type ListenEvalJobCreate = {
  model: string
  sampleMode: 'all' | 'random'
  sampleCount?: number
  seed?: number
  requestInterval?: number
  workers?: number
} & EvalJobCreateMeta

export async function createListenEvalJob(body: ListenEvalJobCreate) {
  const res = await request.post<BaseResponse<string>>('/listen-eval/jobs', body)
  return unwrap(res)
}

export async function getListenEvalJob(jobId: string) {
  const res = await request.get<BaseResponse<ListenEvalJob>>(`/listen-eval/jobs/${jobId}`)
  return unwrap(res)
}

export async function listListenEvalJobs() {
  const res = await request.get<BaseResponse<{ jobs: ListenEvalJob[] }>>('/listen-eval/jobs')
  return unwrap(res)
}

export async function resumeListenEvalJob(jobId: string, options?: EvalJobRuntimeOptions) {
  const res = await request.post<BaseResponse<null>>(
    `/listen-eval/jobs/${jobId}/resume`,
    options ?? {},
  )
  return unwrap(res)
}

export async function updateListenEvalJobDisplayName(jobId: string, displayName: string) {
  return updateEvalJobDisplayName('listen-eval', jobId, displayName)
}

export async function pauseListenEvalJob(jobId: string) {
  return pauseEvalJob('listen-eval', jobId)
}

export async function rerunListenEvalJob(jobId: string, options?: EvalJobRuntimeOptions) {
  return rerunEvalJob('listen-eval', jobId, options)
}
