import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type OralGenHealth = {
  questionwavDirOk: boolean
  questionwavDir: string
  wavCount: number
  openrouterConfigured: boolean
  aihubmixConfigured: boolean
  apiConfigured: boolean
  ready: boolean
  message: string
  maxSamplesPerJob: number
  systemPrompt: string
}

export type OralGenProgressDetail = {
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

export type OralGenResultRow = {
  stem: string
  text?: string
  hasAudio?: boolean
  error?: string
  inputTokens?: number
  outputTokens?: number
}

export type OralGenJobSummary = {
  total?: number
  success?: number
  failed?: number
}

export type OralGenJob = {
  jobId: string
  status: string
  progress: number
  totalSamples: number
  model?: string
  source?: string
  sampleMode?: string
  error?: string
  progressDetail?: OralGenProgressDetail
  summary?: OralGenJobSummary
  rows?: OralGenResultRow[]
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

export async function getOralGenHealth() {
  const res = await request.get<BaseResponse<OralGenHealth>>('/oral-gen/health')
  return unwrap(res)
}

export type OralGenJobCreateBuiltin = {
  model: string
  sampleMode: 'all' | 'random'
  sampleCount?: number
  seed?: number
  requestInterval?: number
}

export async function createOralGenJobBuiltin(body: OralGenJobCreateBuiltin) {
  const res = await request.post<BaseResponse<string>>('/oral-gen/jobs', {
    source: 'builtin',
    ...body,
  })
  return unwrap(res)
}

export async function createOralGenJobUpload(
  model: string,
  files: File[],
  requestInterval?: number,
) {
  const form = new FormData()
  form.append('model', model)
  if (requestInterval != null) {
    form.append('request_interval', String(requestInterval))
  }
  for (const f of files) {
    form.append('files', f)
  }
  const res = await request.post<BaseResponse<string>>('/oral-gen/jobs/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return unwrap(res)
}

export async function getOralGenJob(jobId: string) {
  const res = await request.get<BaseResponse<OralGenJob>>(`/oral-gen/jobs/${jobId}`)
  return unwrap(res)
}

export async function listOralGenJobs() {
  const res = await request.get<BaseResponse<{ jobs: OralGenJob[] }>>('/oral-gen/jobs')
  return unwrap(res)
}

export function oralGenAudioUrl(jobId: string, stem: string) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  return `${base}/oral-gen/jobs/${encodeURIComponent(jobId)}/audio/${encodeURIComponent(stem)}`
}

export async function downloadOralGenZip(jobId: string) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  const res = await request.get(`${base}/oral-gen/jobs/${jobId}/export`, {
    responseType: 'blob',
  })
  return res.data as Blob
}
