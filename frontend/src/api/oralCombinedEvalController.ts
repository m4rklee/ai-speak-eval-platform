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
  oralGenReady?: boolean
  questionwavCount?: number
  oralGenMessage?: string
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

export type OralCombinedGenRow = {
  stem: string
  text?: string
  hasAudio?: boolean
  error?: string
  inputTokens?: number
  outputTokens?: number
}

export type OralCombinedGenSummary = {
  total?: number
  success?: number
  failed?: number
  evalSkipped?: number
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
  genSummary?: OralCombinedGenSummary
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
  pipelineMode?: boolean
  model?: string
  genRows?: OralCombinedGenRow[]
  genSummary?: OralCombinedGenSummary
  autoStartEval?: boolean
}

export type OralCombinedPipelineCreate = {
  model: string
  source: 'builtin' | 'upload'
  sampleMode?: 'all' | 'random'
  sampleCount?: number
  seed?: number
  requestInterval?: number
  autoStartEval: boolean
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

export async function createOralCombinedPipelineJob(body: OralCombinedPipelineCreate) {
  const res = await request.post<BaseResponse<string>>('/oral-combined/jobs/pipeline', body)
  return unwrap(res)
}

export async function createOralCombinedPipelineUpload(
  model: string,
  files: File[],
  autoStartEval: boolean,
  requestInterval?: number,
) {
  const form = new FormData()
  form.append('model', model)
  form.append('auto_start_eval', String(autoStartEval))
  if (requestInterval != null) {
    form.append('request_interval', String(requestInterval))
  }
  for (const f of files) {
    form.append('files', f)
  }
  const res = await request.post<BaseResponse<string>>(
    '/oral-combined/jobs/pipeline/upload',
    form,
    {
      timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  )
  return unwrap(res)
}

export async function createOralCombinedFromOralGen(
  oralGenJobId: string,
  autoStartEval: boolean,
) {
  const res = await request.post<BaseResponse<string>>(
    `/oral-combined/jobs/from-oral-gen/${encodeURIComponent(oralGenJobId)}`,
    { autoStartEval },
  )
  return unwrap(res)
}

export async function continueOralCombinedJob(jobId: string) {
  const res = await request.post<BaseResponse<null>>(
    `/oral-combined/jobs/${encodeURIComponent(jobId)}/continue`,
  )
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
