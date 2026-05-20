import request from '@/request'
import type { UploadProps } from 'ant-design-vue'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type UnifiedEvalHealth = {
  unifiedEvalEnabled: boolean
  useDaemon: boolean
  pathsOk: boolean
  pathsMessage: string
  daemonRunning: boolean
  daemonReady: boolean
  multipaPort: number
  apgPort: number
  engine: string
}

export type UnifiedEvalSingleResult = {
  status: string
  fileName: string
  accuracy?: number
  fluency?: number
  naturalness?: number
  apgMos?: Record<string, number>
  apgMosErrors?: Record<string, string>
  transcripts?: { transcript_S?: string; transcript_W?: string }
  reason?: string
}

export type UnifiedEvalProgressDetail = {
  phase?: string
  phaseLabel?: string
  current?: number
  total?: number
  multipaCurrent?: number
  multipaTotal?: number
  apgCurrent?: number
  apgTotal?: number
  multipaDone?: boolean
  apgDone?: boolean
  elapsedSec?: number
  etaSec?: number
  elapsedText?: string
  etaText?: string
  ratePerSec?: number
  message?: string
  tqdmLine?: string
}

export type UnifiedEvalModelComparison = {
  modelName: string
  fileCount?: number
  accuracyMean?: number
  fluencyMean?: number
  naturalnessMean?: number
  apgMosBvccMean?: number
  apgMosSomosMean?: number
}

export type UnifiedEvalModelResult = {
  modelName: string
  summary?: {
    multipa?: Record<string, number>
    apgMosBvccMean?: number
    apgMosSomosMean?: number
    fileCount?: number
  }
  perFile?: Array<Record<string, unknown>>
}

export type UnifiedEvalJob = {
  jobId: string
  jobType?: 'single' | 'multi_model'
  status: string
  progress: number
  totalFiles: number
  modelCount?: number
  error?: string
  progressDetail?: UnifiedEvalProgressDetail
  audioAvailable?: boolean
  summary?: {
    multipa?: Record<string, number>
    apgMosBvccMean?: number
    apgMosSomosMean?: number
    fileCount?: number
  }
  perFile?: Array<{
    wavname: string
    modelName?: string
    status: string
    accuracy?: number
    fluency?: number
    naturalness?: number
    apgMos?: Record<string, number>
    transcriptS?: string
    transcriptW?: string
    reason?: string
  }>
  models?: UnifiedEvalModelResult[]
  comparison?: { byModel: UnifiedEvalModelComparison[] }
  result?: Record<string, unknown>
  createdAt?: string
  finishedAt?: string
}

export type ModelEvalSlot = {
  id: string
  modelName: string
  files: File[]
  fileList: UploadProps['fileList']
  dirFiles: File[]
  /** 通过「选文件夹」上传时的根目录名（来自 webkitRelativePath） */
  dirFolderName?: string
  zipFile: File | null
}

function unwrap<T>(res: { data: BaseResponse<T> }): T {
  const body = res.data
  if (body.code !== 0) {
    throw new Error(body.message || '请求失败')
  }
  return body.data as T
}

export async function getUnifiedEvalHealth() {
  const res = await request.get<BaseResponse<UnifiedEvalHealth>>('/unified-eval/health')
  return unwrap(res)
}

export async function evaluateSingleWav(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await request.post<BaseResponse<UnifiedEvalSingleResult>>('/unified-eval/evaluate', form, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function createUnifiedEvalJob(files: File[], archive?: File) {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  if (archive) {
    form.append('archive', archive)
  }
  const res = await request.post<BaseResponse<string>>('/unified-eval/jobs', form, {
    timeout: 120000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function createMultiModelEvalJob(slots: ModelEvalSlot[]) {
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
  const res = await request.post<BaseResponse<string>>('/unified-eval/multi-model-jobs', form, {
    timeout: 300000,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return unwrap(res)
}

export async function getUnifiedEvalJob(jobId: string) {
  const res = await request.get<BaseResponse<UnifiedEvalJob>>(`/unified-eval/jobs/${jobId}`)
  return unwrap(res)
}

export async function listUnifiedEvalJobs() {
  const res = await request.get<BaseResponse<{ jobs: UnifiedEvalJob[] }>>('/unified-eval/jobs')
  return unwrap(res)
}

export function getJobAudioUrl(jobId: string, wavname: string, modelName?: string) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  const params = modelName ? `?modelName=${encodeURIComponent(modelName)}` : ''
  return `${base}/unified-eval/jobs/${encodeURIComponent(jobId)}/audio/${encodeURIComponent(wavname)}${params}`
}
