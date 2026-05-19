import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type ModelVO = {
  id: string
  platform: string
  platforms?: string[]
  alternateIds?: Record<string, string>
  name: string
  provider?: string
  contextLength?: number
  modality?: string
  inputModalities?: string[]
  outputModalities?: string[]
  inputPrice?: string | number
  outputPrice?: string | number
  releasedAt?: string
  modelType?: string
  recommended?: number
  isChina?: number
  totalTokens?: number
  batchCallCount?: number
}

export type ModelListParams = {
  platform?: string
  inputModality?: string
  outputModality?: string
  modelType?: string
  keyword?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export function listModels(params?: ModelListParams) {
  return request.get<BaseResponse<ModelVO[]>>('/model/list', { params })
}

export function listPlatforms() {
  return request.get<BaseResponse<string[]>>('/model/platforms')
}

export function syncModels(platform: 'openrouter' | 'aihubmix' | 'all' = 'all') {
  return request.post<BaseResponse<Record<string, number>>>('/model/sync', null, {
    params: { platform },
    timeout: 300000,
  })
}
